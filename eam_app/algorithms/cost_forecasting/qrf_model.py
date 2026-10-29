"""
Mô hình Rừng Hồi Quy Phân Vị (Quantile Regression Forests - QRF) (Task 11.6).
Dự báo đồng thời 3 phân vị P10 (kịch bản tốt), P50 (trung vị cơ sở) và P90 (rủi ro xấu nhất)
kết hợp biến đổi Log-Transform nén biến độ cực trị và trích xuất đặc trưng trọng yếu.
"""
from typing import Dict, List, Tuple, Any
import numpy as np
from sklearn.ensemble import RandomForestRegressor

from algorithms.cost_forecasting.constants import (
    QRF_N_ESTIMATORS,
    QRF_MAX_DEPTH,
    QRF_MIN_SAMPLES_SPLIT,
    QRF_MIN_SAMPLES_LEAF,
    RANDOM_STATE,
    FEATURE_NAMES
)

HUMAN_READABLE_FEATURE_NAMES = {
    "net_cost_lag_1": "Chi phí ròng kỳ trước (Lag 1)",
    "net_cost_lag_2": "Chi phí ròng cách 2 kỳ (Lag 2)",
    "net_cost_lag_3": "Chi phí ròng cách 3 kỳ (Lag 3)",
    "sma_3_cost": "Trung bình trượt chi phí 3 tháng (SMA 3)",
    "sma_6_cost": "Trung bình trượt chi phí 6 tháng (SMA 6)",
    "rolling_std_3": "Độ biến động chi phí trượt (Rolling Std Dev)",
    "backlog_orders_count": "Khối lượng công việc bảo trì tồn đọng (Backlog Orders)",
    "deferred_maintenance_hours": "Tổng số giờ bảo dưỡng bị hoãn lại (Deferred Hours)",
    "active_assets_count": "Số lượng máy móc đang hoạt động",
    "avg_asset_age_years": "Độ tuổi trung bình dàn thiết bị",
    "breakdown_cm_ratio": "Tần suất sự cố đột xuất 3 tháng gần nhất",
    "rul_critical_liability": "Nghĩa vụ tài chính vật tư từ thiết bị RUL Nguy cấp (Task 11.5)",
    "total_fleet_rav": "Tổng giá trị thay thế toàn bộ dàn máy (Fleet RAV)",
    "class_a_cost_ratio": "Tỷ trọng chi phí nhóm thiết bị trọng yếu Class A",
    "seasonality_month": "Hệ số mùa vụ trong năm",
    "working_days_in_month": "Số ngày làm việc thực tế trong tháng"
}


class QuantileRegressionForestEngine:
    """
    Triển khai chuẩn mực Quantile Regression Forests (Meinshausen, 2006).
    Dự báo hàm phân phối tích lũy có điều kiện F(y|X=x) từ trọng số lá cây trong rừng,
    đảm bảo tính đơn điệu toán học tự nhiên P10 <= P50 <= P90 từ phân phối thực nghiệm có trọng số
    mà không cần dùng thủ thuật max() nhân tạo.
    """

    def __init__(
        self,
        n_estimators: int = QRF_N_ESTIMATORS,
        max_depth: int = QRF_MAX_DEPTH,
        min_samples_split: int = QRF_MIN_SAMPLES_SPLIT,
        min_samples_leaf: int = QRF_MIN_SAMPLES_LEAF,
        random_state: int = RANDOM_STATE
    ):
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.min_samples_split = min_samples_split
        self.min_samples_leaf = min_samples_leaf
        self.random_state = random_state
        self.model = RandomForestRegressor(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            min_samples_split=self.min_samples_split,
            min_samples_leaf=self.min_samples_leaf,
            random_state=self.random_state
        )
        self.is_fitted = False
        self.y_train_ = None
        self.train_leaves_ = None

    def fit(self, X: np.ndarray, y: np.ndarray) -> "QuantileRegressionForestEngine":
        """
        Huấn luyện mô hình với biến đổi Log-Transform: y_log = ln(1 + y),
        và lưu vết phân bổ mẫu huấn luyện vào từng lá cây để ước lượng phân vị có điều kiện.
        """
        X_arr = np.asarray(X, dtype=float)
        y_arr = np.asarray(y, dtype=float)
        y_log = np.log1p(np.maximum(0.0, y_arr))

        self.model.fit(X_arr, y_log)
        self.y_train_ = y_arr
        self.y_log_train_ = y_log
        # Lưu vết chỉ số lá cây của từng mẫu huấn luyện: shape (n_samples, n_estimators)
        self.train_leaves_ = self.model.apply(X_arr)
        self.is_fitted = True
        return self

    def predict_quantiles(
        self,
        X_test: np.ndarray,
        quantiles: List[float] = [0.10, 0.50, 0.90]
    ) -> Dict[str, float]:
        """
        Ước lượng phân vị có điều kiện thực sự theo thuật toán Meinshausen QRF:
        1. Xác định lá cây của điểm dữ liệu x_test trên toàn bộ T cây quyết định.
        2. Tính trọng số w_i(x) cho từng mẫu huấn luyện y_i dựa trên tần suất rơi chung lá.
        3. Tính phân vị từ hàm phân phối thực nghiệm có trọng số sum(w_i * I(y_i <= y)).
        """
        if not self.is_fitted or self.train_leaves_ is None or self.y_train_ is None:
            raise ValueError("Mô hình QRF chưa được huấn luyện (fit).")

        X_test = np.asarray(X_test, dtype=float)
        if X_test.ndim == 1:
            X_test = X_test.reshape(1, -1)

        n_train = len(self.y_train_)
        n_trees = self.n_estimators
        test_leaves = self.model.apply(X_test)  # shape (n_test, n_estimators)

        # Tính toán phân vị cho mẫu đầu tiên (hoặc mẫu duy nhất)
        weights = np.zeros(n_train, dtype=float)
        for t in range(n_trees):
            leaf_idx = test_leaves[0, t]
            leaf_mask = (self.train_leaves_[:, t] == leaf_idx)
            count = np.sum(leaf_mask)
            if count > 0:
                weights[leaf_mask] += 1.0 / (count * n_trees)

        # Sắp xếp các giá trị y thực tế theo thứ tự tăng dần
        order = np.argsort(self.y_train_)
        y_sorted = self.y_train_[order]
        w_sorted = weights[order]

        # Tính hàm phân phối tích lũy thực nghiệm (Empirical CDF)
        cum_weights = np.cumsum(w_sorted)
        if cum_weights[-1] > 0:
            cum_weights = cum_weights / cum_weights[-1]

        # Trích xuất phân vị liên tục (Continuous Quantile Interpolation) từ hàm phân phối thực nghiệm có trọng số
        # Đảm bảo tính đơn điệu toán học P10 <= P50 <= P90 và không bị khóa cứng vào các mẫu rời rạc
        p10 = float(np.interp(quantiles[0], cum_weights, y_sorted))
        p50 = float(np.interp(quantiles[1], cum_weights, y_sorted))
        p90 = float(np.interp(quantiles[2], cum_weights, y_sorted))

        return {
            "p10": p10,
            "p50": p50,
            "p90": p90
        }

    def evaluate_backtest_performance(
        self,
        X_val: np.ndarray,
        y_val: np.ndarray
    ) -> Dict[str, Any]:
        """
        Kiểm định sai số dự báo và độ tin cậy phân vị độc lập theo chuỗi thời gian:
        - MAE (Mean Absolute Error)
        - WAPE (Weighted Absolute Percentage Error)
        - RMSE (Root Mean Squared Error)
        - Độ bao phủ phân vị (Coverage Rate P10 - P90)
        - So sánh đối chuẩn với baseline SMA trượt.
        """
        if not self.is_fitted:
            raise ValueError("Mô hình chưa được fit.")

        X_val = np.asarray(X_val, dtype=float)
        y_val = np.asarray(y_val, dtype=float)
        n_samples = len(y_val)
        if n_samples == 0:
            return {}

        p50_preds = []
        p10_preds = []
        p90_preds = []

        for i in range(n_samples):
            q_res = self.predict_quantiles(X_val[i:i+1])
            p10_preds.append(q_res["p10"])
            p50_preds.append(q_res["p50"])
            p90_preds.append(q_res["p90"])

        p50_arr = np.array(p50_preds)
        p10_arr = np.array(p10_preds)
        p90_arr = np.array(p90_preds)

        errors = np.abs(y_val - p50_arr)
        mae = float(np.mean(errors))
        total_actual = float(np.sum(y_val))
        wape = float(np.sum(errors) / total_actual * 100.0) if total_actual > 0 else 0.0
        rmse = float(np.sqrt(np.mean((y_val - p50_arr) ** 2)))

        # Tỷ lệ giá trị thực tế rơi vào khoảng tin cậy [P10, P90] (Kỳ vọng ~80%)
        coverage_count = np.sum((y_val >= p10_arr) & (y_val <= p90_arr))
        coverage_rate = float(coverage_count / n_samples * 100.0)

        # Baseline SMA 3 tháng gần nhất từ đặc trưng (feature 3 là sma_3_cost)
        sma_baseline = X_val[:, 3] if X_val.shape[1] > 3 else p50_arr
        sma_mae = float(np.mean(np.abs(y_val - sma_baseline)))
        sma_improvement_pct = round(((sma_mae - mae) / sma_mae * 100.0), 1) if sma_mae > 0 else 0.0

        return {
            "is_evaluated": True,
            "test_samples_count": n_samples,
            "sampleCount": n_samples,
            "mae": round(mae, 2),
            "wape": round(wape, 2),
            "wapePercent": round(wape, 2),
            "rmse": round(rmse, 2),
            "coverage_p10_p90": round(coverage_rate, 1),
            "coverageP10P90Percent": round(coverage_rate, 1),
            "baselineSmaMae": round(sma_mae, 2),
            "improvement_vs_sma_percent": sma_improvement_pct,
            "improvementOverBaselinePercent": sma_improvement_pct
        }

    def get_top_cost_drivers(self, top_n: int = 5) -> List[Dict[str, Any]]:
        """
        Trích xuất top đặc trưng ảnh hưởng mạnh nhất theo Gini Feature Importance.
        """
        if not self.is_fitted:
            return []

        importances = self.model.feature_importances_
        indices = np.argsort(importances)[::-1][:top_n]

        top_drivers = []
        for idx in indices:
            raw_name = FEATURE_NAMES[idx] if idx < len(FEATURE_NAMES) else f"feature_{idx}"
            display_name = HUMAN_READABLE_FEATURE_NAMES.get(raw_name, raw_name)
            weight = round(float(importances[idx]), 3)
            top_drivers.append({
                "feature": display_name,
                "raw_key": raw_name,
                "importance": weight
            })

        return top_drivers

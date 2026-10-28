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
    Wrapper mô hình Quantile Regression Forest dựa trên tập hợp lá cây của RandomForestRegressor.
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

    def fit(self, X: np.ndarray, y: np.ndarray) -> "QuantileRegressionForestEngine":
        """
        Huấn luyện mô hình với biến đổi Log-Transform: y_log = ln(1 + y).
        """
        # Quy tắc 2: Áp dụng Log-Transform ổn định phương sai chống sốc cực trị
        X_arr = np.asarray(X, dtype=float)
        y_arr = np.asarray(y, dtype=float)
        y_log = np.log1p(np.maximum(0.0, y_arr))
        self.model.fit(X_arr, y_log)
        self.is_fitted = True
        return self

    def predict_quantiles(
        self,
        X_test: np.ndarray,
        quantiles: List[float] = [0.10, 0.50, 0.90]
    ) -> Dict[str, float]:
        """
        Trích xuất dự đoán theo các phân vị P10, P50, P90 từ toàn bộ tập hợp 100 cây quyết định,
        sau đó giải biến đổi ngược: exp(y_log) - 1.
        """
        if not self.is_fitted:
            raise ValueError("Mô hình QRF chưa được huấn luyện (fit).")

        X_test = np.asarray(X_test, dtype=float)
        if X_test.ndim == 1:
            X_test = X_test.reshape(1, -1)

        # Thu thập dự đoán từ từng cây con (mỗi cây dự đoán trong miền log1p)
        # estimators_predictions shape: (n_estimators, n_samples)
        estimators_predictions = np.array([tree.predict(X_test) for tree in self.model.estimators_])

        # Tính toán phân vị trên trục cây con (axis=0)
        # np.percentile nhận giá trị từ 0 đến 100
        percentiles = [q * 100.0 for q in quantiles]
        quantile_vals_log = np.percentile(estimators_predictions, percentiles, axis=0)

        # Giải biến đổi ngược expm1
        p10_raw = float(np.expm1(quantile_vals_log[0, 0]))
        p50_raw = float(np.expm1(quantile_vals_log[1, 0]))
        p90_raw = float(np.expm1(quantile_vals_log[2, 0]))

        # Đảm bảo tính đơn điệu không suy thoái toán học P10 <= P50 <= P90
        p10 = max(0.0, p10_raw)
        p50 = max(p10, p50_raw)
        p90 = max(p50, p90_raw)

        return {
            "p10": p10,
            "p50": p50,
            "p90": p90
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

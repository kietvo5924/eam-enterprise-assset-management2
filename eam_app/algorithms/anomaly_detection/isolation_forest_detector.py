from typing import List, Optional, Dict, Any
import numpy as np
from sklearn.ensemble import IsolationForest

# Giá trị chuẩn định danh cho vector tương quan đa biến [Vibration, Delta_T, Pressure, Current]
DEFAULT_BASELINE_CENTERS = [2.0, 40.0, 2.5, 15.0]
DEFAULT_BASELINE_SCALES = [0.3, 2.5, 0.2, 1.5]


def compute_delta_t(machine_temp: float, ambient_temp: Optional[float]) -> float:
    """
    Quy Tắc 4 & TC-ANOM-04: Chuẩn hóa độ tăng nhiệt nội tại Delta T = T_machine - T_ambient.
    Triệt tiêu hoàn toàn sự thay đổi thời tiết giữa mùa hè và mùa đông.
    Nếu không có nhiệt độ môi trường, giả định mức chuẩn 25°C.
    """
    t_amb = ambient_temp if ambient_temp is not None else 25.0
    return float(machine_temp) - float(t_amb)


class MultivariateIsolationForestDetector:
    """
    Cấp độ 2: Multivariate Isolation Forest Detector trên vector hiệu số Delta T.
    Vector: [Vibration, Delta T, Pressure, Current]
    """
    def __init__(self, contamination: float = 0.05, threshold: float = 0.65):
        self.contamination = contamination
        self.threshold = threshold
        self.model: Optional[IsolationForest] = None

    def build_vector(
        self,
        vibration: float = 2.0,
        temperature: float = 65.0,
        ambient_temperature: Optional[float] = 25.0,
        pressure: float = 2.5,
        current: float = 15.0
    ) -> np.ndarray:
        delta_t = compute_delta_t(temperature, ambient_temperature)
        return np.array([float(vibration), float(delta_t), float(pressure), float(current)])

    def train_or_fit(self, historical_vectors: List[np.ndarray]):
        """
        Huấn luyện mô hình từ lịch sử đo hợp lệ (đã loại trừ điểm is_suppressed, Quy Tắc 8).
        """
        if len(historical_vectors) >= 10:
            X_train = np.array(historical_vectors)
        else:
            # Sinh baseline tham chiếu chuẩn công nghiệp nếu chưa đủ dữ liệu hiện trường (Local RandomState)
            rng = np.random.RandomState(42)
            n_samples = max(30, len(historical_vectors))
            X_train = rng.normal(
                loc=DEFAULT_BASELINE_CENTERS,
                scale=DEFAULT_BASELINE_SCALES,
                size=(n_samples, 4)
            )
            if len(historical_vectors) > 0:
                X_train = np.vstack([X_train, np.array(historical_vectors)])

        self.model = IsolationForest(
            n_estimators=100,
            contamination=self.contamination,
            random_state=42
        ).fit(X_train)

    def evaluate(self, current_vector: np.ndarray) -> Dict[str, Any]:
        """
        Đánh giá điểm số bất thường (anomaly score).
        Nếu score >= 0.65, kích hoạt cảnh báo tương quan đa biến.
        """
        if self.model is None:
            self.train_or_fit([])

        vec_2d = current_vector.reshape(1, -1)
        # Điểm số bất thường Isolation Forest: -score_samples
        raw_score = float(-self.model.score_samples(vec_2d)[0])
        score = round(raw_score, 4)

        has_anomaly = score >= self.threshold
        severity = "CRITICAL" if score >= 0.72 else ("WARNING" if has_anomaly else "NORMAL")

        return {
            "has_anomaly": has_anomaly,
            "anomaly_score": score,
            "threshold": self.threshold,
            "severity": severity,
            "vector": {
                "vibration": float(current_vector[0]),
                "delta_t": float(current_vector[1]),
                "pressure": float(current_vector[2]),
                "current": float(current_vector[3]),
            },
            "message": f"Điểm bất thường tương quan đa biến: {score} (Ngưỡng: {self.threshold})" if has_anomaly else "Tương quan đa biến bình thường."
        }

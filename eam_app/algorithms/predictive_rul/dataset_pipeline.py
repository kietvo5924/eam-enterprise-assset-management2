"""
Industrial Dataset Pipeline & Sliding-Window 4-Feature Sequence Generator (Phase 11.5).
Tích hợp mẫu suy thoái công nghiệp thực tế:
- IEEE PHM 2012 Challenge (FEMTO / PRONOSTIA Bearing Degradation Dataset)
- UCI AI4I 2020 Predictive Maintenance Dataset
"""

import math
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from .constants import (
    WINDOW_SIZE, FEATURE_DIM, FEATURE_BOUNDS, RUL_MAX_CLIP_DAYS,
    IDX_VIBRATION, IDX_DELTA_TEMP, IDX_PRESSURE, IDX_LOAD_FACTOR
)


class DegradationFeaturePipeline:
    """
    Pipeline trích xuất và chuẩn hóa vector 4 chiều phục vụ mạng LSTM:
    X_t = [v_rms, ΔT_bearing, P_pressure, L_load_factor]
    với ΔT_bearing = max(0.0, T_bearing - T_ambient)
    """

    @staticmethod
    def normalize_feature(value: float, feature_name: str) -> float:
        """Min-Max Scaling về đoạn [0, 1] dựa trên giới hạn vật lý công nghiệp."""
        bounds = FEATURE_BOUNDS.get(feature_name, {'min': 0.0, 'max': 100.0})
        v_min = bounds['min']
        v_max = bounds['max']
        if v_max <= v_min:
            return 0.5
        scaled = (value - v_min) / (v_max - v_min)
        return float(np.clip(scaled, 0.0, 1.0))

    @staticmethod
    def denormalize_feature(scaled_value: float, feature_name: str) -> float:
        """Quy đổi ngược giá trị chuẩn hóa [0, 1] về thang đo vật lý công nghiệp."""
        bounds = FEATURE_BOUNDS.get(feature_name, {'min': 0.0, 'max': 100.0})
        v_min = bounds['min']
        v_max = bounds['max']
        return float(scaled_value * (v_max - v_min) + v_min)

    @staticmethod
    def extract_4_feature_vector(
        vibration_rms: float,
        bearing_temp: Optional[float] = None,
        ambient_temp: Optional[float] = None,
        pressure: Optional[float] = None,
        load_factor: Optional[float] = None
    ) -> np.ndarray:
        """
        Trích xuất vector 4 chiều chuẩn hóa tại một thời điểm t.
        """
        # 1. Độ rung RMS
        norm_vib = DegradationFeaturePipeline.normalize_feature(vibration_rms, 'vibration_rms')

        # 2. Nhiệt độ ổ trục vi sai ΔT = T_bearing - T_ambient
        b_temp = bearing_temp if bearing_temp is not None else 45.0
        a_temp = ambient_temp if ambient_temp is not None else 30.0
        delta_t = max(0.0, b_temp - a_temp)
        norm_delta_t = DegradationFeaturePipeline.normalize_feature(delta_t, 'delta_temp')

        # 3. Áp suất thủy lực / áp suất dầu
        p_val = pressure if pressure is not None else 10.0
        norm_press = DegradationFeaturePipeline.normalize_feature(p_val, 'pressure')

        # 4. Hệ số phụ tải (Load Factor)
        l_val = load_factor if load_factor is not None else 1.0
        norm_load = DegradationFeaturePipeline.normalize_feature(l_val, 'load_factor')

        return np.array([norm_vib, norm_delta_t, norm_press, norm_load], dtype=np.float32)

    @classmethod
    def construct_sliding_window(
        cls,
        raw_readings: List[Dict[str, Any]],
        window_size: int = WINDOW_SIZE
    ) -> Optional[np.ndarray]:
        """
        Xây dựng ma trận cửa sổ trượt shape (W=30, F=4).
        Chỉ nhận chuỗi bản ghi đã lọc hợp lệ ở trạng thái RUNNING.
        """
        if len(raw_readings) < window_size:
            return None

        # Lấy đúng W=30 bản ghi gần nhất theo thời gian
        target_readings = raw_readings[-window_size:]
        matrix = np.zeros((window_size, FEATURE_DIM), dtype=np.float32)

        for i, item in enumerate(target_readings):
            vib = float(item.get('vibration', 0.0) or item.get('vibration_rms', 0.0))
            b_temp = item.get('bearing_temperature') or item.get('temperature')
            a_temp = item.get('ambient_temperature')
            press = item.get('pressure')
            load = item.get('load_factor', 1.0)

            vec = cls.extract_4_feature_vector(
                vibration_rms=vib,
                bearing_temp=float(b_temp) if b_temp is not None else None,
                ambient_temp=float(a_temp) if a_temp is not None else None,
                pressure=float(press) if press is not None else None,
                load_factor=float(load) if load is not None else 1.0
            )
            matrix[i] = vec

        return matrix

    @staticmethod
    def calculate_piecewise_linear_target(time_to_failure: float, max_clip: float = RUL_MAX_CLIP_DAYS) -> float:
        """
        Thuật toán gán nhãn kẹp trần Piece-wise Linear RUL Target (Rule 11):
        RUL_target(t) = min(125.0, T_failure - t)
        """
        return float(min(max_clip, max(0.0, time_to_failure)))

    @classmethod
    def generate_synthetic_femto_trajectory(
        cls,
        total_cycles: int = 100,
        load_factor: float = 1.0,
        noise_std: float = 0.05
    ) -> List[Dict[str, Any]]:
        """
        Tạo chuỗi dữ liệu suy thoái tổng hợp mô phỏng quỹ đạo thực nghiệm FEMTO Bearing:
        - Giai đoạn 1 (0 -> 70% vòng đời): Ổn định, mòn rất chậm.
        - Giai đoạn 2 (70% -> 90%): Rỗ bề mặt, rung và nhiệt tăng theo hàm mũ.
        - Giai đoạn 3 (90% -> 100%): Suy thoái đột biến, nứt vỡ rãnh bi, tiến tới hỏng hoàn toàn.
        """
        rng = np.random.RandomState(42)
        readings = []

        for t in range(total_cycles):
            progress = t / float(total_cycles)
            # Baseline lành lặn
            base_vib = 1.5 + rng.normal(0, noise_std)
            base_temp = 42.0 + rng.normal(0, noise_std * 2)

            if progress > 0.70:
                # Giai đoạn rỗ bề mặt: tăng phi tuyến
                exp_factor = math.exp((progress - 0.70) * 8.0) - 1.0
                vib = base_vib + exp_factor * 2.0 * load_factor
                temp = base_temp + exp_factor * 6.0
            else:
                vib = base_vib * load_factor
                temp = base_temp

            readings.append({
                'cycle': t + 1,
                'vibration': max(0.2, vib),
                'bearing_temperature': max(25.0, temp),
                'ambient_temperature': 28.0,
                'pressure': 10.0 + rng.normal(0, 0.2),
                'load_factor': load_factor,
                'machine_state': 'RUNNING',
                'true_rul': max(0.0, total_cycles - (t + 1))
            })

        return readings

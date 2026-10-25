import numpy as np
from typing import List, Optional, Dict, Any

# Ngưỡng kỹ thuật an toàn của nhà sản xuất (OEM Static Limits) cho chế độ Cold-Start
OEM_STATIC_LIMITS = {
    'VIBRATION': {'warning': 2.8, 'critical': 7.1, 'unit': 'mm/s'},
    'TEMPERATURE': {'warning': 75.0, 'critical': 90.0, 'unit': '°C'},
    'PRESSURE': {'warning': 15.0, 'critical': 25.0, 'unit': 'bar'},
    'CURRENT': {'warning': 40.0, 'critical': 60.0, 'unit': 'A'},
    'VOLTAGE': {'warning': 420.0, 'critical': 450.0, 'unit': 'V'},
    'RPM': {'warning': 3200.0, 'critical': 3600.0, 'unit': 'v/p'},
    'FLOW_RATE': {'warning': 120.0, 'critical': 150.0, 'unit': 'm³/h'},
    'RUN_HOURS': {'warning': 5000.0, 'critical': 8000.0, 'unit': 'h'},
    'NOISE': {'warning': 85.0, 'critical': 95.0, 'unit': 'dB'},
}


def detect_z_score_anomaly(
    historical_readings: List[Any],
    current_reading_value: float,
    current_machine_state: str = 'RUNNING',
    metric_code: str = 'VIBRATION',
    custom_oem_limits: Optional[Dict[str, float]] = None,
    window_size: int = 30
) -> Dict[str, Any]:
    """
    Cấp độ 1: Observation-Based Sliding Z-score Detector.
    Tuân thủ:
    - Quy Tắc 1: Lọc trạng thái máy (Bỏ qua WARM_UP và IDLE, tránh báo động giả).
    - Quy Tắc 2: Tái lập cửa sổ trượt sau sửa chữa (Cold-Start OEM limits nếu < 15 mẫu).
    - Quy Tắc 6: Nhận diện cảm biến bị đóng băng (Frozen sensor nếu 7 lần đo liên tiếp không đổi).
    """
    metric = str(metric_code).upper().strip() if metric_code else 'VIBRATION'

    # Quy Tắc 1: Warm-Up / Cold-State Guardrail (TC-ANOM-01)
    if current_machine_state != 'RUNNING':
        return {
            "has_anomaly": False,
            "skipped": True,
            "reason": f"Bỏ qua phân tích bất thường do máy đang ở trạng thái {current_machine_state}",
            "machine_state": current_machine_state,
            "metric": metric,
            "current_value": current_reading_value,
            "z_score": None,
            "severity": "NORMAL",
            "status": "NORMAL"
        }

    # Lọc các lần đo hợp lệ: chỉ lấy RUNNING, không bị pre_repair, không bị suppressed
    valid_historical_values = []
    for r in historical_readings:
        # Hỗ trợ cả ORM object lẫn dict/float
        m_state = getattr(r, 'machine_state', None) or (r.get('machine_state') if isinstance(r, dict) else 'RUNNING')
        is_pre = getattr(r, 'is_pre_repair', False) or (r.get('is_pre_repair', False) if isinstance(r, dict) else False)
        is_sup = getattr(r, 'is_suppressed', False) or (r.get('is_suppressed', False) if isinstance(r, dict) else False)

        if m_state == 'RUNNING' and not is_pre and not is_sup:
            val = getattr(r, 'value', None)
            if val is None:
                val = getattr(r, 'reading_value', None)
            if val is None and isinstance(r, dict):
                val = r.get('value', r.get('reading_value'))
            if val is not None:
                try:
                    valid_historical_values.append(float(val))
                except (ValueError, TypeError):
                    pass

    # Quy Tắc 6: Frozen Sensor Detection (TC-ANOM-06)
    # Lấy 6 mẫu gần nhất + mẫu hiện tại = 7 mẫu đo liên tiếp
    recent_values_for_freeze = valid_historical_values[-6:] + [float(current_reading_value)]
    if len(recent_values_for_freeze) >= 7:
        val_range = max(recent_values_for_freeze) - min(recent_values_for_freeze)
        std_freeze = np.std(recent_values_for_freeze)
        if val_range < 1e-5 or std_freeze < 1e-6:
            return {
                "has_anomaly": True,
                "is_frozen": True,
                "severity": "WARNING",
                "status": "FROZEN_SENSOR",
                "metric": metric,
                "current_value": current_reading_value,
                "z_score": 0.0,
                "message": "Dữ liệu đo bị đóng băng bất thường. Vui lòng kiểm tra lại thiết bị đo hoặc thao tác kiểm tra."
            }

    # Giới hạn OEM limits
    oem_limits = custom_oem_limits or OEM_STATIC_LIMITS.get(metric)

    # Quy Tắc 2: Post-Repair Window Reset (TC-ANOM-02)
    # Nếu chưa tích lũy đủ 15 lần đo mới sau khi sửa chữa: Dùng ngưỡng tĩnh OEM (Cold-Start mode)
    if len(valid_historical_values) < 15:
        if oem_limits:
            warn_lim = oem_limits.get('warning')
            crit_lim = oem_limits.get('critical')
            
            if crit_lim is not None and current_reading_value >= crit_lim:
                return {
                    "has_anomaly": True,
                    "is_cold_start": True,
                    "severity": "CRITICAL",
                    "status": "SPIKE",
                    "metric": metric,
                    "current_value": current_reading_value,
                    "z_score": None,
                    "oem_critical_limit": crit_lim,
                    "message": f"Vượt ngưỡng nguy hiểm của nhà sản xuất OEM ({current_reading_value} >= {crit_lim})"
                }
            elif warn_lim is not None and current_reading_value >= warn_lim:
                return {
                    "has_anomaly": True,
                    "is_cold_start": True,
                    "severity": "WARNING",
                    "status": "ELEVATED",
                    "metric": metric,
                    "current_value": current_reading_value,
                    "z_score": None,
                    "oem_warning_limit": warn_lim,
                    "message": f"Vượt ngưỡng cảnh báo của nhà sản xuất OEM ({current_reading_value} >= {warn_lim})"
                }
            else:
                return {
                    "has_anomaly": False,
                    "is_cold_start": True,
                    "severity": "NORMAL",
                    "status": "NORMAL",
                    "metric": metric,
                    "current_value": current_reading_value,
                    "z_score": None,
                    "message": "Trạng thái ổn định theo ngưỡng tiêu chuẩn OEM."
                }
        else:
            return {
                "has_anomaly": False,
                "is_cold_start": True,
                "severity": "NORMAL",
                "status": "NORMAL",
                "metric": metric,
                "current_value": current_reading_value,
                "z_score": None,
                "message": f"Đang tích lũy dữ liệu cơ sở ({len(valid_historical_values)}/15 mẫu) cho chỉ số tùy biến {metric}."
            }

    # Cửa sổ trượt W = 30 lần đo gần nhất
    window = valid_historical_values[-window_size:]
    mu_w = float(np.mean(window))
    sigma_w = float(np.std(window))

    if sigma_w < 1e-6:
        # Độ lệch chuẩn tiệm cận 0, so sánh ngưỡng OEM
        if oem_limits:
            warn_lim = oem_limits.get('warning')
            crit_lim = oem_limits.get('critical')
            if crit_lim is not None and current_reading_value >= crit_lim:
                return {
                    "has_anomaly": True,
                    "is_cold_start": False,
                    "severity": "CRITICAL",
                    "status": "SPIKE",
                    "metric": metric,
                    "current_value": current_reading_value,
                    "z_score": 99.0,
                    "window_mean": round(mu_w, 2),
                    "window_std": 0.0,
                    "message": f"Đột biến vượt ngưỡng nguy hiểm OEM ({metric}: {current_reading_value} >= {crit_lim})"
                }
            elif warn_lim is not None and current_reading_value >= warn_lim:
                return {
                    "has_anomaly": True,
                    "is_cold_start": False,
                    "severity": "WARNING",
                    "status": "ELEVATED",
                    "metric": metric,
                    "current_value": current_reading_value,
                    "z_score": 99.0,
                    "window_mean": round(mu_w, 2),
                    "window_std": 0.0,
                    "message": f"Cảnh báo vượt ngưỡng OEM ({metric}: {current_reading_value} >= {warn_lim})"
                }
        z = 0.0
    else:
        z = float((current_reading_value - mu_w) / sigma_w)

    # Với rung động và nhiệt độ, giá trị giảm sâu sau sửa chữa là trạng thái tốt, không xem là hư hỏng
    is_unidirectional_high = metric in ('VIBRATION', 'TEMPERATURE')
    is_critical = (z >= 3.0) if is_unidirectional_high else (abs(z) >= 3.0)
    is_warning = (z >= 2.0) if is_unidirectional_high else (abs(z) >= 2.0)

    if is_critical:
        return {
            "has_anomaly": True,
            "is_cold_start": False,
            "severity": "CRITICAL",
            "status": "SPIKE",
            "metric": metric,
            "current_value": current_reading_value,
            "z_score": round(z, 2),
            "window_mean": round(mu_w, 2),
            "window_std": round(sigma_w, 2),
            "message": f"Đột biến nghiêm trọng ({metric}: Z = {round(z, 2)} >= 3.0)"
        }
    elif is_warning:
        return {
            "has_anomaly": True,
            "is_cold_start": False,
            "severity": "WARNING",
            "status": "ELEVATED",
            "metric": metric,
            "current_value": current_reading_value,
            "z_score": round(z, 2),
            "window_mean": round(mu_w, 2),
            "window_std": round(sigma_w, 2),
            "message": f"Cảnh báo độ lệch ({metric}: Z = {round(z, 2)} >= 2.0)"
        }
    else:
        return {
            "has_anomaly": False,
            "is_cold_start": False,
            "severity": "NORMAL",
            "status": "NORMAL",
            "metric": metric,
            "current_value": current_reading_value,
            "z_score": round(z, 2),
            "window_mean": round(mu_w, 2),
            "window_std": round(sigma_w, 2),
            "message": "Chỉ số hoạt động bình thường."
        }

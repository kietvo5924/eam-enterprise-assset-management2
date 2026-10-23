def evaluate_iso_10816(metric_code: str, value: float) -> dict:
    """
    Đánh giá chỉ số độ rung vận tốc RMS (mm/s) theo tiêu chuẩn quốc tế ISO 10816-3 (Quy Tắc 9 & TC-ANOM-11).
    - Vùng A/B (Tốt / Đạt tiêu chuẩn): < 2.8 mm/s
    - Vùng C (Cảnh báo - Cần theo dõi): 2.8 - 7.1 mm/s
    - Vùng D (Nguy hiểm - Dừng máy khẩn cấp): > 7.1 mm/s
    """
    if metric_code is None or str(metric_code).upper() != 'VIBRATION':
        return None

    try:
        val = float(value)
    except (ValueError, TypeError):
        return None

    if val < 2.8:
        return {
            "zone": "ZONE_AB",
            "label": "Tốt / Đạt tiêu chuẩn (Vùng A/B: < 2.8 mm/s)",
            "severity": "NORMAL",
            "color": "green",
            "limit": 7.1
        }
    elif 2.8 <= val <= 7.1:
        return {
            "zone": "ZONE_C",
            "label": "Cảnh báo (Vùng C: 2.8 - 7.1 mm/s)",
            "severity": "WARNING",
            "color": "yellow",
            "limit": 7.1
        }
    else:
        return {
            "zone": "ZONE_D",
            "label": "Nguy hiểm - Dừng máy khẩn cấp (Vùng D: > 7.1 mm/s)",
            "severity": "CRITICAL",
            "color": "red",
            "limit": 7.1
        }

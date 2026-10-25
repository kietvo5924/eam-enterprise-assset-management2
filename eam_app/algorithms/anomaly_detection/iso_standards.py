def get_iso_thresholds_for_asset(asset=None) -> dict:
    """
    Cung cấp cấu hình ngưỡng rung theo tiêu chuẩn ISO 10816-3 thống nhất cho cả Backend và Frontend.
    Mặc định: Nhóm 2 - Bệ móng cứng (Group 2 Rigid - máy động cơ trung bình 15kW - 300kW):
      - Vùng A/B: < 2.8 mm/s (Đạt chuẩn)
      - Vùng C: 2.8 - 7.1 mm/s (Cảnh báo)
      - Vùng D: > 7.1 mm/s (Nguy hiểm)
    """
    # Nếu danh mục tài sản có cấu hình tùy biến riêng thì cho phép ghi đè
    cat = getattr(asset, 'category', None)
    return {
        "standard": "ISO 10816-3 (Group 2 Rigid)",
        "zone_ab_limit": 2.8,
        "zone_c_limit": 7.1,
        "unit": "mm/s",
        "description": "< 2.8 mm/s: Đạt chuẩn (A/B) | 2.8 - 7.1 mm/s: Cảnh báo (C) | > 7.1 mm/s: Nguy hiểm (D)"
    }


def evaluate_iso_10816(metric_code: str, value: float, asset=None) -> dict:
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

    thresholds = get_iso_thresholds_for_asset(asset)
    ab_limit = thresholds["zone_ab_limit"]
    c_limit = thresholds["zone_c_limit"]

    if val < ab_limit:
        return {
            "zone": "ZONE_AB",
            "label": f"Tốt / Đạt tiêu chuẩn (Vùng A/B: < {ab_limit} mm/s)",
            "severity": "NORMAL",
            "color": "green",
            "limit": c_limit
        }
    elif ab_limit <= val <= c_limit:
        return {
            "zone": "ZONE_C",
            "label": f"Cảnh báo (Vùng C: {ab_limit} - {c_limit} mm/s)",
            "severity": "WARNING",
            "color": "yellow",
            "limit": c_limit
        }
    else:
        return {
            "zone": "ZONE_D",
            "label": f"Nguy hiểm - Dừng máy khẩn cấp (Vùng D: > {c_limit} mm/s)",
            "severity": "CRITICAL",
            "color": "red",
            "limit": c_limit
        }

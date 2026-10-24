from rest_framework.exceptions import ValidationError

# Giới hạn vật lý khả thi cho các chỉ số đo đạc công nghiệp (Quy Tắc 10 & TC-ANOM-09)
PHYSICAL_BOUNDS = {
    'TEMPERATURE': (0.0, 180.0),      # °C
    'VIBRATION': (0.01, 50.0),        # mm/s
    'PRESSURE': (0.0, 30.0),          # bar
    'CURRENT': (0.0, 500.0),          # A
    'VOLTAGE': (0.0, 1000.0),         # V
    'RPM': (0.0, 50000.0),            # v/p
    'FLOW_RATE': (0.0, 10000.0),      # m³/h
    'OIL_LEVEL': (0.0, 100.0),        # %
    'LEVEL': (0.0, 100.0),            # %
    'RUN_HOURS': (0.0, 1000000.0),    # h
    'NOISE': (0.0, 160.0),            # dB
}

STATIC_CATEGORY_KEYWORDS = [
    'bàn ghế',
    'giường bệnh',
    'tủ tài liệu',
    'tài sản tĩnh',
    'furniture',
    'static',
    'fixtures',
    'office'
]


def validate_physical_bounds(metric_code: str, value: float) -> None:
    """
    Kiểm tra tính hợp lệ về mặt vật lý của giá trị đo (Quy Tắc 10).
    Nếu vượt quá ngưỡng vật lý khả thi, ném ngoại lệ ValidationError (HTTP 400 Bad Request).
    """
    if metric_code is None:
        return

    code = str(metric_code).strip().upper()
    try:
        val = float(value)
        import math
        if math.isnan(val) or math.isinf(val):
            raise ValidationError(f"Giá trị đo không được là NaN hoặc vô cực.")
    except (ValueError, TypeError):
        raise ValidationError(f"Giá trị đo không hợp lệ: {value}")

    if code in PHYSICAL_BOUNDS:
        min_val, max_val = PHYSICAL_BOUNDS[code]
        if val < min_val or val > max_val:
            raise ValidationError(
                f"Giá trị đo {val} vượt giới hạn vật lý khả thi cho chỉ số {code} [{min_val}, {max_val}]."
            )


def is_static_asset(asset) -> bool:
    """
    Nhận diện tài sản tĩnh (bàn ghế, tủ tài liệu, giường bệnh...) (Quy Tắc 10 & TC-ANOM-10).
    Tài sản tĩnh không chạy các mô hình AI rung nhiệt, mà chuyển sang checklist định tính.
    """
    if asset is None:
        return False

    # Nếu cờ is_trackable bị tắt
    if hasattr(asset, 'is_trackable') and asset.is_trackable is False:
        return True

    # Nếu có thuộc tính is_static trực tiếp
    if getattr(asset, 'is_static', False):
        return True

    # Kiểm tra theo danh mục (AssetCategory)
    category = getattr(asset, 'category', None)
    if category and getattr(category, 'name', None):
        cat_name = category.name.lower().strip()
        for kw in STATIC_CATEGORY_KEYWORDS:
            if kw in cat_name:
                return True

    # Kiểm tra theo tên tài sản
    asset_name = getattr(asset, 'name', '').lower().strip()
    for kw in STATIC_CATEGORY_KEYWORDS:
        if kw in asset_name:
            return True

    return False


def get_static_asset_checklist(asset) -> dict:
    """
    Tạo cấu trúc phiếu kiểm tra định tính (Pass/Fail Checklist) cho tài sản tĩnh.
    """
    return {
        "isStatic": True,
        "assetId": str(asset.id) if asset else None,
        "assetName": asset.name if asset else "",
        "message": "Tài sản tĩnh: Áp dụng phiếu kiểm tra ngoại quan định tính (Pass/Fail). Không kích hoạt mô hình AI rung/nhiệt.",
        "checklist": [
            {"id": "CHK_01", "name": "Kiểm tra ngoại quan, trầy xước, móp méo", "status": "PENDING"},
            {"id": "CHK_02", "name": "Độ vững chắc của kết cấu và chân đế", "status": "PENDING"},
            {"id": "CHK_03", "name": "Vệ sinh công nghiệp và môi trường xung quanh", "status": "PENDING"},
            {"id": "CHK_04", "name": "Tem nhãn tài sản & mã QR nhận diện", "status": "PENDING"},
        ]
    }

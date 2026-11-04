"""
Log-Distance Path Loss RSSI Distance Calculation Engine (From-Scratch).
Căn cứ Đề cương Đồ án Tốt nghiệp & Đặc tả Kỹ thuật Phase 11.7.

Mô hình suy hao sóng vô tuyến logarit trong nhà xưởng công nghiệp:
    RSSI = - (10 * n * log10(d) - A)
    <=> d = 10 ** ((A - RSSI) / (10 * n))

Trong đó:
    - RSSI: Chỉ số cường độ tín hiệu nhận được (dBm).
    - A: Cường độ tín hiệu đo được ở khoảng cách chuẩn 1m (-59 dBm cho ESP32 TxPower +9 dBm).
    - n: Hệ số suy hao môi trường (n = 2.8 cho môi trường phân xưởng công nghiệp nhiều máy móc kim loại).
    - d: Khoảng cách trắc địa ước tính (mét).

Quy tắc ngưỡng 50m:
    Tại d = 50.0m: RSSI_50m = -59 - (10 * 2.8 * log10(50)) = -59 - 47.57 ~= -92 dBm.
    Hợp lệ: RSSI >= -92 dBm và d <= 50.0m.
"""

import math

BLE_UNIVERSAL_BEACON_NAME = "EAM-UNIVERSAL-BEACON"
BLE_UNIVERSAL_BEACON_UUID = "e2c56db5-dffb-48d2-b060-d0f5a71096e0"
DEFAULT_TX_POWER_1M = -59
DEFAULT_PATH_LOSS_EXPONENT = 2.8
MAX_GEOFENCE_RADIUS_METERS = 50.0
RSSI_THRESHOLD_50M = -92


def calculate_ble_log_distance(
    rssi: int,
    tx_power_1m: int = -59,
    path_loss_exponent: float = 2.8,
) -> float:
    """
    Ước tính khoảng cách trắc địa (mét) từ chỉ số RSSI nhận được của ESP32.
    Công thức: d = 10 ** ((A - RSSI) / (10 * n))

    Tuyệt đối không dùng thư viện ngoài; tự tính toán 100% bằng toán học thuần túy.
    """
    if rssi == 0 or rssi is None:
        return 999.0  # Mất sóng / không có tín hiệu

    try:
        f_rssi = float(rssi)
        f_tx = float(tx_power_1m)
        f_n = float(path_loss_exponent)
    except (ValueError, TypeError):
        return 999.0

    if not math.isfinite(f_rssi) or not math.isfinite(f_tx) or not math.isfinite(f_n):
        return 999.0

    if f_n <= 0.0:
        f_n = DEFAULT_PATH_LOSS_EXPONENT

    ratio = (f_tx - f_rssi) / (10.0 * f_n)
    try:
        distance = math.pow(10.0, ratio)
    except OverflowError:
        return 999.0

    if not math.isfinite(distance):
        return 999.0
    return round(float(distance), 2)


def verify_ble_proximity(
    rssi: int,
    max_radius_meters: float = 50.0,
    tx_power_1m: int = -59,
    path_loss_exponent: float = 2.8,
) -> tuple[bool, float]:
    """
    Kiểm tra thiết bị di động có nằm trong bán kính cho phép (mặc định <= 50m)
    của mạch ESP32 Universal Beacon hay không.

    Điều kiện hợp lệ:
        - distance <= max_radius_meters (<= 50.0m)
        - rssi >= -92 dBm (ngưỡng vật lý tương ứng 50m với A=-59, n=2.8)
    """
    if rssi == 0 or rssi is None:
        return False, 999.0

    try:
        f_rssi = float(rssi)
    except (ValueError, TypeError):
        return False, 999.0

    if not math.isfinite(f_rssi):
        return False, 999.0

    distance = calculate_ble_log_distance(
        rssi,
        tx_power_1m=tx_power_1m,
        path_loss_exponent=path_loss_exponent,
    )
    is_valid = (distance <= max_radius_meters) and (f_rssi >= RSSI_THRESHOLD_50M)
    return is_valid, distance


def rssi_for_distance(
    distance: float,
    tx_power_1m: int = -59,
    path_loss_exponent: float = 2.8,
) -> int:
    """
    Hàm tính ngược RSSI lý thuyết tương ứng với một khoảng cách d (mét).
    Công thức: RSSI = A - (10 * n * log10(d))
    """
    try:
        f_dist = float(distance)
        f_tx = float(tx_power_1m)
        f_n = float(path_loss_exponent)
    except (ValueError, TypeError):
        return tx_power_1m

    if not math.isfinite(f_dist) or not math.isfinite(f_tx) or not math.isfinite(f_n):
        return tx_power_1m

    if f_dist <= 0:
        return int(round(f_tx))
    if f_n <= 0:
        f_n = DEFAULT_PATH_LOSS_EXPONENT

    rssi_calc = f_tx - (10.0 * f_n * math.log10(f_dist))
    return int(round(rssi_calc))


def is_beacon_identifier_matched(client_beacon_id: str, asset=None) -> bool:
    """
    Xác thực định danh Beacon nhận được từ ứng dụng di động:
    1. Khớp tên hoặc UUID của Mỏ neo không gian vạn năng (EAM-UNIVERSAL-BEACON).
    2. Khớp UUID mỏ neo riêng của tài sản (asset.ble_beacon_uuid) không phân biệt dấu gạch ngang hoặc hoa thường.
    3. Khớp địa chỉ MAC vật lý của mạch ESP32 (asset.ble_mac_address).
    4. Khớp tên quảng bá ESP32 chuẩn (chứa 'EAM-' hoặc 'BEACON').
    """
    if not client_beacon_id:
        return False

    raw_id = str(client_beacon_id).strip()
    if not raw_id:
        return False

    clean_id = raw_id.upper().replace('-', '').replace(':', '')
    clean_universal_name = BLE_UNIVERSAL_BEACON_NAME.upper().replace('-', '')
    clean_universal_uuid = BLE_UNIVERSAL_BEACON_UUID.upper().replace('-', '')

    # 1. Khớp Universal Beacon (tên hoặc UUID)
    if raw_id.upper() == BLE_UNIVERSAL_BEACON_NAME or clean_id == clean_universal_name or clean_id == clean_universal_uuid:
        return True

    # 2. Khớp UUID cấu hình trên Asset
    if asset and getattr(asset, 'ble_beacon_uuid', None):
        clean_asset_uuid = str(asset.ble_beacon_uuid).strip().upper().replace('-', '')
        if clean_id == clean_asset_uuid:
            return True

    # 3. Khớp MAC address cấu hình trên Asset
    if asset and getattr(asset, 'ble_mac_address', None):
        clean_asset_mac = str(asset.ble_mac_address).strip().upper().replace(':', '').replace('-', '')
        if clean_id == clean_asset_mac:
            return True

    # 4. Hỗ trợ tên quảng bá ESP32 chuẩn theo tài sản
    upper_raw = raw_id.upper()
    if upper_raw.startswith('EAM-') or 'BEACON' in upper_raw:
        if not asset or not getattr(asset, 'ble_beacon_uuid', None):
            return True
        if getattr(asset, 'code', None) and str(asset.code).upper() in upper_raw:
            return True
        if getattr(asset, 'name', None) and str(asset.name).upper() in upper_raw:
            return True

    return False


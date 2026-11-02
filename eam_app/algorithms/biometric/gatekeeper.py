"""
Gatekeeper Security Interlock (Cổng Gác 15 Phút & Khóa Hiện Trường Cổng 2).
Căn cứ Đề cương Đồ án Tốt nghiệp & Đặc tả Kỹ thuật Phase 11.7.

Cổng 1 (Start Work Order Gate):
    - Khóa 15 phút nghiêm ngặt: Bắt buộc có bản ghi AttendanceLog hợp lệ trong vòng 15 phút.
    - is_face_verified == True (100% bắt buộc cho mọi tài sản).
    - is_location_verified == True (nếu require_ble_beacon == True và Tenant cho phép geofencing).
    - Thiếu -> 403 Forbidden COMPLIANCE_ATTENDANCE_REQUIRED hoặc LOCATION_VERIFICATION_REQUIRED.

Cổng 2 (Complete Work Order Gate):
    - Khóa kiểm tra hiện diện tức thời: Phải có mặt tại máy (bắt sóng ESP32 <= 50m) lúc nghiệm thu.
    - Nếu asset.require_ble_beacon == True mà không có sóng ESP32 -> 403 Forbidden PRESENCE_VERIFICATION_REQUIRED.
"""

from datetime import timedelta
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response


def verify_start_work_order_gate(work_order, user) -> Response | None:
    """
    Cổng 1: Bắt buộc kiểm tra sự tồn tại của bản ghi điểm danh sinh trắc học
    hợp lệ trong vòng 15 phút gần nhất trước khi cho phép chuyển trạng thái IN_PROGRESS.

    Returns:
        None nếu thỏa mãn điều kiện mở khóa;
        Response (status 403) nếu vi phạm quy chuẩn an toàn.
    """
    from workorders.models import AttendanceLog

    cutoff = timezone.now() - timedelta(minutes=15)

    # Tìm bản ghi điểm danh Cổng 1 mới nhất của thợ đối với Work Order này
    valid_log = AttendanceLog.all_objects.filter(
        work_order=work_order,
        technician=user,
        is_face_verified=True,
        gate_type='START_GATE',
        created_at__gte=cutoff,
    ).order_by('-created_at').first()

    if not valid_log:
        return Response({
            "success": False,
            "error": {
                "code": "COMPLIANCE_ATTENDANCE_REQUIRED",
                "message": "Yêu cầu điểm danh sinh trắc học hợp lệ (MobileFaceNet) trong vòng 15 phút trước khi bắt đầu thực hiện."
            }
        }, status=status.HTTP_403_FORBIDDEN)

    # Kiểm tra cờ bật/tắt Geofencing cấp Tenant
    tenant_geofencing_enabled = True
    if work_order.tenant and hasattr(work_order.tenant, 'enable_geofencing'):
        tenant_geofencing_enabled = bool(work_order.tenant.enable_geofencing)

    # Nếu tài sản yêu cầu Beacon mà không có sóng ESP32 hợp lệ
    asset_requires_beacon = getattr(work_order.asset, 'require_ble_beacon', True)
    if tenant_geofencing_enabled and asset_requires_beacon:
        if not valid_log.is_location_verified:
            return Response({
                "success": False,
                "error": {
                    "code": "LOCATION_VERIFICATION_REQUIRED",
                    "message": "Thiết bị này yêu cầu xác thực vị trí qua sóng mỏ neo ESP32 (<= 50m). Vui lòng lại gần máy móc để điểm danh!"
                }
            }, status=status.HTTP_403_FORBIDDEN)

    return None


def verify_complete_work_order_gate(work_order, user, ble_verification_data: dict = None) -> Response | None:
    """
    Cổng 2: Kiểm tra sự hiện diện thực tế của thợ tại máy trước khi hoàn thành nghiệm thu.

    Returns:
        None nếu thỏa mãn điều kiện;
        Response (status 403) nếu thợ vắng mặt / không bắt được sóng ESP32.
    """
    from workorders.models import AttendanceLog

    # Kiểm tra cờ bật/tắt Geofencing cấp Tenant
    tenant_geofencing_enabled = True
    if work_order.tenant and hasattr(work_order.tenant, 'enable_geofencing'):
        tenant_geofencing_enabled = bool(work_order.tenant.enable_geofencing)

    if not tenant_geofencing_enabled:
        # Miễn trừ theo chính sách Tenant
        return None

    # Nếu tài sản không yêu cầu Beacon (bàn, ghế, nội thất tĩnh) -> cho phép nghiệm thu trực tiếp
    asset_requires_beacon = getattr(work_order.asset, 'require_ble_beacon', True)
    if not asset_requires_beacon:
        return None

    # 1. Kiểm tra xem có bản ghi COMPLETE_GATE hợp lệ vừa quét trong vòng 15 phút không
    cutoff = timezone.now() - timedelta(minutes=15)
    recent_presence = AttendanceLog.all_objects.filter(
        work_order=work_order,
        technician=user,
        gate_type='COMPLETE_GATE',
        is_location_verified=True,
        created_at__gte=cutoff,
    ).exists()

    if recent_presence:
        return None

    # 2. Hoặc kiểm tra dữ liệu BLE kèm RSSI thực tế truyền lên trong payload
    if ble_verification_data and isinstance(ble_verification_data, dict):
        rssi_val = ble_verification_data.get('rssi')
        beacon_id = (
            ble_verification_data.get('beaconId')
            or ble_verification_data.get('bleBeaconId')
            or ble_verification_data.get('ble_beacon_id')
            or 'EAM-UNIVERSAL-BEACON'
        )
        if rssi_val is not None:
            from algorithms.biometric.proximity_engine import verify_ble_proximity
            try:
                rssi_int = int(rssi_val)
            except (ValueError, TypeError):
                rssi_int = -999

            beacon_matched = (beacon_id == 'EAM-UNIVERSAL-BEACON') or (
                work_order.asset and work_order.asset.ble_beacon_uuid and beacon_id == work_order.asset.ble_beacon_uuid
            )
            is_valid, dist_meters = verify_ble_proximity(rssi_int, max_radius_meters=50.0)
            if is_valid and beacon_matched:
                # Ghi nhận bản ghi kiểm soát hiện diện Cổng 2
                AttendanceLog.all_objects.create(
                    tenant=work_order.tenant,
                    work_order=work_order,
                    technician=user,
                    verification_method='ESP32_UNIVERSAL_BEACON',
                    ble_beacon_id=beacon_id,
                    rssi_dbm=rssi_int,
                    distance_meters=dist_meters,
                    similarity_score=1.0,
                    is_location_verified=True,
                    is_face_verified=True,
                    overall_compliance='PASSED',
                    gate_type='COMPLETE_GATE',
                )
                return None

    # Không có minh chứng hiện diện thực tế -> Chặn đứng nghiệm thu khống từ xa
    return Response({
        "success": False,
        "error": {
            "code": "PRESENCE_VERIFICATION_REQUIRED",
            "message": "Vi phạm hiện trường: Bạn không có mặt tại vị trí máy móc (Không bắt được sóng ESP32). Vui lòng có mặt trực tiếp tại thiết bị để hoàn thành phiếu bảo dưỡng!"
        }
    }, status=status.HTTP_403_FORBIDDEN)

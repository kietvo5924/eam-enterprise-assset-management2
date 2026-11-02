"""
Attendance & Biometric API Views (Phase 11.7).
Endpoints:
    POST /api/v1/biometric/enroll/
    POST /api/v1/attendance/check-in/
    POST /api/v1/attendance/verify-presence/
"""

import math
import logging
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from users.models import User, BiometricProfile
from workorders.models import WorkOrder, AttendanceLog
from algorithms.biometric.proximity_engine import (
    calculate_ble_log_distance,
    verify_ble_proximity,
)
from algorithms.biometric.cosine_similarity import (
    calculate_cosine_similarity_from_scratch,
    verify_face_cosine_similarity,
    normalize_l2_from_scratch,
)
from algorithms.biometric.enrollment import (
    enroll_user_face,
    extract_face_embedding_from_image,
    save_audit_snapshot,
)

logger = logging.getLogger(__name__)


class BiometricEnrollView(APIView):
    """
    POST /api/v1/biometric/enroll/
    Đăng ký khuôn mặt User trên Web Portal (Task 5.2 & Phase 11.7).
    Trích xuất vector 128 số thực chuẩn hóa L2 từ ảnh chân dung và lưu vào biometric_profiles.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user_id = request.data.get('userId') or request.data.get('user_id')
        if not user_id:
            target_user = request.user
        else:
            try:
                target_user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return Response({
                    "success": False,
                    "error": "Không tìm thấy người dùng được chỉ định."
                }, status=status.HTTP_404_NOT_FOUND)

            # Phân quyền: Chỉ Quản đốc/Quản trị viên hoặc chính chủ mới được đăng ký hồ sơ khuôn mặt
            if target_user.id != request.user.id:
                is_admin_or_mgr = (
                    request.user.is_superuser
                    or request.user.roles.filter(permissions__id='system:admin').exists()
                    or request.user.roles.filter(name__in=['ADMIN', 'MANAGER', 'SUPERVISOR']).exists()
                )
                if not is_admin_or_mgr:
                    return Response({
                        "success": False,
                        "error": "Chỉ Quản trị viên hoặc Quản đốc mới có quyền đăng ký khuôn mặt cho nhân viên khác."
                    }, status=status.HTTP_403_FORBIDDEN)

        face_image = request.FILES.get('faceImage') or request.FILES.get('face_image')
        live_embedding = request.data.get('liveEmbedding') or request.data.get('live_embedding')

        if not face_image and not live_embedding:
            return Response({
                "success": False,
                "error": "Vui lòng tải lên tệp ảnh chân dung (faceImage) hoặc vector đặc trưng."
            }, status=status.HTTP_400_BAD_REQUEST)

        image_bytes = None
        if face_image:
            image_bytes = face_image.read()

        precomputed = None
        if live_embedding:
            if isinstance(live_embedding, str):
                import json
                try:
                    precomputed = json.loads(live_embedding)
                except Exception:
                    precomputed = None
            elif isinstance(live_embedding, list):
                precomputed = live_embedding

        try:
            profile, snapshot_path = enroll_user_face(
                user=target_user,
                image_bytes=image_bytes or b'SIMULATED_FACE_IMAGE_BYTES',
                enrolled_by=request.user,
                precomputed_embedding=precomputed,
            )

            return Response({
                "success": True,
                "data": {
                    "profileId": str(profile.id),
                    "userId": str(target_user.id),
                    "embeddingDimension": len(profile.face_embedding),
                    "status": "ENROLLED",
                    "enrolledAt": profile.enrolled_at.isoformat() if profile.enrolled_at else timezone.now().isoformat(),
                    "snapshotPath": snapshot_path,
                }
            }, status=status.HTTP_200_OK)

        except Exception as ex:
            logger.exception("Biometric enrollment error: %s", ex)
            return Response({
                "success": False,
                "error": f"Lỗi khi xử lý trích xuất sinh trắc học: {str(ex)}"
            }, status=status.HTTP_400_BAD_REQUEST)


class AttendanceCheckInView(APIView):
    """
    POST /api/v1/attendance/check-in/
    Gửi dữ liệu điểm danh hiện trường Cổng 1 (ESP32 BLE Beacon + MobileFaceNet)
    để mở khóa Work Order sang trạng thái IN_PROGRESS.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data
        wo_id = data.get('workOrderId') or data.get('work_order_id')
        if not wo_id:
            return Response({
                "success": False,
                "error": "Thiếu workOrderId."
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            wo = WorkOrder.all_objects.select_related('asset', 'tenant').get(id=wo_id)
        except WorkOrder.DoesNotExist:
            return Response({
                "success": False,
                "error": "Không tìm thấy Work Order."
            }, status=status.HTTP_404_NOT_FOUND)

        technician = request.user

        # Phân quyền: Chỉ kỹ thuật viên được giao việc mới có quyền điểm danh thực hiện phiếu
        if wo.assigned_to_id and wo.assigned_to_id != technician.id:
            is_supervisor = (
                request.user.is_superuser
                or request.user.roles.filter(name__in=['ADMIN', 'MANAGER', 'SUPERVISOR']).exists()
            )
            if not is_supervisor:
                return Response({
                    "success": False,
                    "error": "Chỉ kỹ thuật viên được giao việc mới có quyền điểm danh thực hiện phiếu công việc này."
                }, status=status.HTTP_403_FORBIDDEN)

        if wo.status in ('COMPLETED', 'CANCELLED'):
            return Response({
                "success": False,
                "error": f"Không thể điểm danh cho phiếu công việc đã ở trạng thái {wo.status}."
            }, status=status.HTTP_400_BAD_REQUEST)

        ble_beacon_id = data.get('bleBeaconId') or data.get('ble_beacon_id') or 'EAM-UNIVERSAL-BEACON'
        rssi_val = data.get('rssi')
        live_embedding = data.get('liveEmbedding') or data.get('live_embedding')
        face_image_file = request.FILES.get('faceImage') or request.FILES.get('face_image')
        face_image_b64 = data.get('faceImageBase64') or data.get('face_image_base64')

        # Nếu có ảnh khuôn mặt gửi lên (từ Camera thiết bị di động):
        # Giải mã ảnh thực tế và bóc tách đặc trưng 128D qua mô hình nhận diện khuôn mặt
        raw_face_bytes = None
        if face_image_file:
            raw_face_bytes = face_image_file.read()
        elif face_image_b64:
            import base64
            try:
                b64_str = str(face_image_b64)
                if ',' in b64_str:
                    b64_str = b64_str.split(',', 1)[1]
                raw_face_bytes = base64.b64decode(b64_str)
            except Exception as e:
                logger.warning(f"Lỗi giải mã base64 faceImage: {e}")
                raw_face_bytes = None

        if raw_face_bytes:
            try:
                live_embedding = extract_face_embedding_from_image(raw_face_bytes)
                save_audit_snapshot(
                    image_bytes=raw_face_bytes,
                    user_id=str(technician.id),
                    tenant_id=str(wo.tenant_id or 'default'),
                    prefix='field_checkin'
                )
            except ValueError as ex:
                return Response({
                    "success": False,
                    "error": str(ex)
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({
                "success": False,
                "error": "Bắt buộc chụp ảnh trực tiếp từ camera trước để nhận diện sinh trắc học khuôn mặt!"
            }, status=status.HTTP_400_BAD_REQUEST)

        # 1. Kiểm tra không gian vi định vị ESP32 BLE Beacon
        asset = wo.asset
        require_ble_beacon = getattr(asset, 'require_ble_beacon', True)
        tenant_geofencing_enabled = True
        if wo.tenant and hasattr(wo.tenant, 'enable_geofencing'):
            tenant_geofencing_enabled = bool(wo.tenant.enable_geofencing)

        is_location_verified = False
        verification_method = 'ESP32_UNIVERSAL_BEACON'
        dist_meters = 0.0

        if not require_ble_beacon:
            # Miễn quét sóng BLE theo cờ Asset
            verification_method = 'BLE_EXEMPT_BY_ASSET'
            is_location_verified = True
            proximity_info = {
                "method": "BLE_EXEMPT_BY_ASSET",
                "isPassed": True,
                "message": "Thiết bị không yêu cầu Beacon hiện trường (Bàn, ghế, nội thất tĩnh)"
            }
        elif not tenant_geofencing_enabled:
            # Miễn quét sóng theo cấu hình Tenant Fallback
            verification_method = 'BYPASSED_BY_TENANT_POLICY'
            is_location_verified = True
            proximity_info = {
                "method": "BYPASSED_BY_TENANT_POLICY",
                "isPassed": True,
                "message": "Kiểm soát BLE tạm thời được miễn trừ theo chính sách Tenant"
            }
        else:
            # Máy móc kỹ thuật quan trọng: Bắt buộc quét được sóng ESP32 Beacon 50m
            if rssi_val is None:
                is_location_verified = False
                dist_meters = 999.0
            else:
                try:
                    rssi_int = int(rssi_val)
                except (ValueError, TypeError):
                    rssi_int = -999

                # Kiểm tra Beacon identifier
                beacon_matched = (ble_beacon_id == 'EAM-UNIVERSAL-BEACON') or (
                    asset and asset.ble_beacon_uuid and ble_beacon_id == asset.ble_beacon_uuid
                )

                is_valid, dist_meters = verify_ble_proximity(rssi_int, max_radius_meters=50.0)
                is_location_verified = is_valid and beacon_matched

            proximity_info = {
                "method": "ESP32_UNIVERSAL_BEACON",
                "beaconId": ble_beacon_id,
                "rssi": rssi_val,
                "estimatedDistanceMeters": dist_meters,
                "maxAllowedRadius": 50.0,
                "isPassed": is_location_verified
            }

        # 2. Kiểm tra khuôn mặt sinh trắc học MobileFaceNet (BẮT BUỘC 100%)
        is_face_verified = False
        similarity_score = 0.0

        if live_embedding is not None:
            if isinstance(live_embedding, str):
                import json
                try:
                    live_embedding = json.loads(live_embedding)
                except Exception:
                    live_embedding = None

        # Lấy hồ sơ đăng ký của thợ trên Web Portal (bắt buộc phải có)
        profile = BiometricProfile.all_objects.filter(user=technician, is_active=True).first()
        if not profile:
            return Response({
                "success": False,
                "error": "Kỹ thuật viên chưa đăng ký hồ sơ sinh trắc học trên hệ thống. Vui lòng liên hệ Quản đốc hoặc đăng ký ảnh chân dung trên Web Portal trước khi điểm danh!"
            }, status=status.HTTP_400_BAD_REQUEST)

        # Kiểm tra tính hợp lệ của vector 128 chiều
        if not live_embedding or not isinstance(live_embedding, list) or len(live_embedding) != 128:
            return Response({
                "success": False,
                "error": "Dữ liệu sinh trắc học không hợp lệ. Yêu cầu vector đặc trưng 128 chiều từ MobileFaceNet."
            }, status=status.HTTP_400_BAD_REQUEST)

        clean_live_embedding = []
        for val in live_embedding:
            try:
                f_val = float(val)
            except (ValueError, TypeError):
                return Response({
                    "success": False,
                    "error": "Vector sinh trắc học chứa giá trị không phải số thực."
                }, status=status.HTTP_400_BAD_REQUEST)
            if not math.isfinite(f_val):
                return Response({
                    "success": False,
                    "error": "Vector sinh trắc học chứa giá trị không hợp lệ (NaN hoặc vô cực)."
                }, status=status.HTTP_400_BAD_REQUEST)
            clean_live_embedding.append(f_val)

        FACE_THRESHOLD = 0.55
        is_face_verified, similarity_score = verify_face_cosine_similarity(
            clean_live_embedding,
            profile.face_embedding,
            threshold=FACE_THRESHOLD,
        )

        biometric_info = {
            "similarityScore": similarity_score,
            "acceptanceThreshold": FACE_THRESHOLD,
            "isPassed": is_face_verified
        }

        # 3. Đánh giá tính tuân thủ tổng thể
        if is_location_verified and is_face_verified:
            if verification_method == 'BYPASSED_BY_TENANT_POLICY':
                overall_compliance = 'BYPASSED_BY_TENANT_POLICY'
            else:
                overall_compliance = 'PASSED'
        else:
            overall_compliance = 'FAILED'

        # 4. Ghi bản ghi AttendanceLog bất biến
        log = AttendanceLog.all_objects.create(
            tenant=wo.tenant,
            work_order=wo,
            technician=technician,
            verification_method=verification_method,
            ble_beacon_id=ble_beacon_id,
            rssi_dbm=int(rssi_val) if rssi_val is not None else None,
            distance_meters=dist_meters,
            similarity_score=similarity_score,
            is_location_verified=is_location_verified,
            is_face_verified=is_face_verified,
            overall_compliance=overall_compliance,
            gate_type='START_GATE',
        )

        # 5. Nếu đạt yêu cầu, mở khóa chuyển Work Order sang IN_PROGRESS
        if overall_compliance != 'FAILED':
            if wo.status in ('CREATED', 'ASSIGNED', 'ON_HOLD'):
                wo.status = 'IN_PROGRESS'
                if not wo.actual_start_time:
                    wo.actual_start_time = timezone.now()
                wo.save()

        fail_reason = None
        if overall_compliance == 'FAILED':
            if not is_face_verified and not is_location_verified:
                fail_reason = "Không quét được sóng BLE và khuôn mặt không khớp hồ sơ!"
            elif not is_face_verified:
                fail_reason = f"Khuôn mặt không khớp hồ sơ thợ đã đăng ký ({round(similarity_score * 100, 1)}% < 55%)."
            elif not is_location_verified:
                fail_reason = "Không tìm thấy sóng ESP32 Beacon hợp lệ trong bán kính 50m quanh thiết bị!"

        return Response({
            "success": (overall_compliance != 'FAILED'),
            "error": fail_reason,
            "data": {
                "attendanceId": str(log.id),
                "workOrderId": str(wo.id),
                "overallCompliance": overall_compliance,
                "proximity": proximity_info,
                "biometric": biometric_info,
                "workOrderStatus": wo.status,
                "timestamp": log.created_at.isoformat(),
            }
        }, status=status.HTTP_200_OK if overall_compliance != 'FAILED' else status.HTTP_400_BAD_REQUEST)


class AttendanceVerifyPresenceView(APIView):
    """
    POST /api/v1/attendance/verify-presence/
    Xác thực hiện diện nhanh Cổng 2 (Complete Gate) trước khi cho phép nghiệm thu.
    Quét sóng ESP32 trong 3 giây. Nếu bắt được sóng RSSI >= -92 dBm (<= 50m) thì mở khóa form nghiệm thu.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data
        wo_id = data.get('workOrderId') or data.get('work_order_id')
        if not wo_id:
            return Response({
                "success": False,
                "error": "Thiếu workOrderId."
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            wo = WorkOrder.all_objects.select_related('asset', 'tenant').get(id=wo_id)
        except WorkOrder.DoesNotExist:
            return Response({
                "success": False,
                "error": "Không tìm thấy Work Order."
            }, status=status.HTTP_404_NOT_FOUND)

        # Phân quyền: Chỉ kỹ thuật viên được giao việc mới có quyền xác thực hiện diện cho phiếu
        if wo.assigned_to_id and wo.assigned_to_id != request.user.id:
            is_supervisor = (
                request.user.is_superuser
                or request.user.roles.filter(name__in=['ADMIN', 'MANAGER', 'SUPERVISOR']).exists()
            )
            if not is_supervisor:
                return Response({
                    "success": False,
                    "error": "Chỉ kỹ thuật viên được giao việc mới có quyền xác thực hiện diện cho phiếu này."
                }, status=status.HTTP_403_FORBIDDEN)

        if wo.status in ('COMPLETED', 'CANCELLED'):
            return Response({
                "success": False,
                "error": f"Không thể xác thực hiện diện cho phiếu công việc đã ở trạng thái {wo.status}."
            }, status=status.HTTP_400_BAD_REQUEST)

        asset = wo.asset
        require_ble_beacon = getattr(asset, 'require_ble_beacon', True)
        tenant_geofencing_enabled = True
        if wo.tenant and hasattr(wo.tenant, 'enable_geofencing'):
            tenant_geofencing_enabled = bool(wo.tenant.enable_geofencing)

        if not require_ble_beacon:
            return Response({
                "success": True,
                "data": {
                    "isPresenceVerified": True,
                    "method": "BLE_EXEMPT_BY_ASSET",
                    "message": "Thiết bị không yêu cầu Beacon hiện trường"
                }
            }, status=status.HTTP_200_OK)

        if not tenant_geofencing_enabled:
            return Response({
                "success": True,
                "data": {
                    "isPresenceVerified": True,
                    "method": "BYPASSED_BY_TENANT_POLICY",
                    "message": "Miễn trừ định vị BLE theo chính sách Tenant"
                }
            }, status=status.HTTP_200_OK)

        ble_beacon_id = data.get('bleBeaconId') or data.get('ble_beacon_id') or 'EAM-UNIVERSAL-BEACON'
        rssi_val = data.get('rssi')

        if rssi_val is None:
            return Response({
                "success": False,
                "error": {
                    "code": "PRESENCE_VERIFICATION_REQUIRED",
                    "message": "Không nhận được tín hiệu sóng ESP32. Vui lòng lại gần thiết bị trong bán kính <= 50m!"
                }
            }, status=status.HTTP_403_FORBIDDEN)

        try:
            rssi_int = int(rssi_val)
        except (ValueError, TypeError):
            rssi_int = -999

        if not (-120 <= rssi_int <= 0):
            rssi_int = -999

        beacon_matched = (ble_beacon_id == 'EAM-UNIVERSAL-BEACON') or (
            asset and asset.ble_beacon_uuid and ble_beacon_id == asset.ble_beacon_uuid
        )

        is_valid, dist_meters = verify_ble_proximity(rssi_int, max_radius_meters=50.0)
        is_verified = is_valid and beacon_matched

        # Ghi log Cổng 2
        AttendanceLog.all_objects.create(
            tenant=wo.tenant,
            work_order=wo,
            technician=request.user,
            verification_method='ESP32_UNIVERSAL_BEACON',
            ble_beacon_id=ble_beacon_id,
            rssi_dbm=rssi_int,
            distance_meters=dist_meters,
            similarity_score=1.0,
            is_location_verified=is_verified,
            is_face_verified=True,
            overall_compliance='PASSED' if is_verified else 'FAILED',
            gate_type='COMPLETE_GATE',
        )

        if not is_verified:
            return Response({
                "success": False,
                "error": {
                    "code": "PRESENCE_VERIFICATION_REQUIRED",
                    "message": f"Vi phạm hiện trường: Khoảng cách tới máy ({dist_meters}m, RSSI: {rssi_int}dBm) vượt quá bán kính 50m hoặc không khớp mỏ neo ESP32!"
                }
            }, status=status.HTTP_403_FORBIDDEN)

        return Response({
            "success": True,
            "data": {
                "isPresenceVerified": True,
                "method": "ESP32_UNIVERSAL_BEACON",
                "beaconId": ble_beacon_id,
                "rssi": rssi_int,
                "distanceMeters": dist_meters,
                "maxAllowedRadius": 50.0,
                "message": "Xác thực hiện diện thành công. Đã mở khóa biểu mẫu nghiệm thu."
            }
        }, status=status.HTTP_200_OK)

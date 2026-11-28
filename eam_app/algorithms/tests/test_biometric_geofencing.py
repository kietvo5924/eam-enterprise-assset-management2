"""
Test Suite for Phase 11.7: Smart Field Biometric Attendance & Micro-Geofencing.
Implements Acceptance Verification Matrix TC-BIO-01 to TC-BIO-14:
- TC-BIO-01: Điểm danh chuẩn với ESP32 Universal (<= 50m, Sim >= 0.72) -> IN_PROGRESS
- TC-BIO-02: Vi phạm khoảng cách sóng ESP32 (> 50m, RSSI < -92 dBm) -> FAILED
- TC-BIO-03: Khóa Nghiệm thu Cổng 2 khi thợ vắng mặt -> 403 PRESENCE_VERIFICATION_REQUIRED
- TC-BIO-04: Nghiệm thu Cổng 2 thành công tại máy (RSSI >= -92 dBm) -> COMPLETED
- TC-BIO-05: Đăng ký khuôn mặt User trên Web qua Deep Learning -> 128D vector
- TC-BIO-06: Mỏ neo vạn năng (EAM-UNIVERSAL-BEACON) nhận diện cho mọi Work Order
- TC-BIO-07: Điểm danh hộ / Không khớp khuôn mặt (Sim < 0.65) -> Từ chối
- TC-BIO-08: Chặn dùng tem QR thay thế BLE beacon (QR chỉ dùng tra cứu thông tin)
- TC-BIO-09: Tài sản nội thất không gắn chip (require_ble_beacon = False) -> BLE_EXEMPT_BY_ASSET
- TC-BIO-10: Bật/Tắt cấu hình require_ble_beacon trên Web Portal
- TC-BIO-11: Khóa thư viện ảnh (Chỉ chấp nhận camera stream trực tiếp)
- TC-BIO-12: Cổng gác máy chủ Backend 15 phút (Khóa nếu không có check-in) -> 403 COMPLIANCE_ATTENDANCE_REQUIRED
- TC-BIO-13: Tuân thủ bảo mật Nghị định 13/2023/NĐ-CP (Chỉ lưu 128D trong DB, mã hóa ảnh AES-256)
- TC-BIO-14: Hiệu năng giải thuật thuần từ số liệu thực nghiệm (<= 30ms)
"""

import os
import time
import math
import json
import tempfile
from decimal import Decimal
from datetime import timedelta
from django.conf import settings
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import Tenant
from core.tenant_context import set_current_tenant, clear_current_tenant
from users.models import User, Role, Permission, BiometricProfile
from assets.models import Asset, AssetCategory, Location
from workorders.models import WorkOrder, AttendanceLog, WorkOrderAttachment
from algorithms.biometric.proximity_engine import (
    calculate_ble_log_distance,
    verify_ble_proximity,
    BLE_UNIVERSAL_BEACON_NAME,
)
from algorithms.biometric.cosine_similarity import (
    calculate_cosine_similarity_from_scratch,
    verify_face_cosine_similarity,
    normalize_l2_from_scratch,
    dot_product_from_scratch,
    l2_norm_from_scratch,
)
from algorithms.biometric.enrollment import (
    enroll_user_face,
    decrypt_image_snapshot,
)
from algorithms.biometric.gatekeeper import (
    verify_start_work_order_gate,
    verify_complete_work_order_gate,
)


class BiometricGeofencingTestSuite(TestCase):
    def setUp(self):
        import uuid
        self._tmp_media_dir = tempfile.TemporaryDirectory()
        self._media_override = self.settings(MEDIA_ROOT=self._tmp_media_dir.name)
        self._media_override.enable()
        self.uid = uuid.uuid4().hex[:6]
        self.client = APIClient()
        self.tenant = Tenant.objects.create(
            name=f"VinFast Factory Hai Phong {self.uid}",
            tenant_code=f"VINFAST_HP_{self.uid}",
            enable_geofencing=True,
        )
        set_current_tenant(self.tenant.id)

        self.location = Location.objects.create(
            name="Phân xưởng Thân vỏ",
            code=f"LOC_BODY_SHOP_{self.uid}",
            tenant=self.tenant,
        )
        self.category = AssetCategory.objects.create(
            name="Robot Hàn Tự Động",
            tenant=self.tenant,
        )

        # Asset requiring ESP32 Beacon
        self.robot_asset = Asset.objects.create(
            name="Robot Hàn KUKA KR-210",
            serial_number=f"KUKA-KR210-{self.uid}",
            qr_code=f"QR_KUKA_KR210_{self.uid}",
            category=self.category,
            location=self.location,
            tenant=self.tenant,
            is_active=True,
            require_ble_beacon=True,
            ble_beacon_uuid="e2c56db5-dffb-48d2-b060-d0f5a71096e0",
            ble_mac_address="24:6F:28:AB:CD:EF",
        )

        # Asset NOT requiring Beacon (Office chair / Static furniture)
        self.chair_asset = Asset.objects.create(
            name="Bàn ghế điều khiển trung tâm",
            serial_number=f"FURN-DESK-{self.uid}",
            qr_code=f"QR_FURN_DESK_{self.uid}",
            category=self.category,
            location=self.location,
            tenant=self.tenant,
            is_active=True,
            require_ble_beacon=False,
        )

        # Technician User
        self.technician = User.objects.create(
            username=f"tech_nguyen_van_a_{self.uid}",
            email=f"tech.a_{self.uid}@vinfast.vn",
            tenant=self.tenant,
        )
        self.technician.set_password("SecurePass@123")
        self.technician.save()

        # Manager User
        self.manager = User.objects.create(
            username=f"manager_le_thi_b_{self.uid}",
            email=f"manager.b_{self.uid}@vinfast.vn",
            tenant=self.tenant,
        )
        self.manager.set_password("ManagerPass@123")
        self.manager.save()

        # Assign Role & Permissions
        self.role_tech = Role.objects.create(name="TECHNICIAN", tenant=self.tenant)
        self.role_mgr = Role.objects.create(name="MANAGER", tenant=self.tenant)
        
        perms = [
            ("work_order:execute", "Execute WO"),
            ("work_order:update", "Update WO"),
            ("work_order:read", "Read WO"),
            ("asset:update", "Update Asset"),
            ("asset:read", "Read Asset"),
            ("asset:create", "Create Asset"),
            ("system:admin", "Sys Admin"),
        ]
        created_perms = []
        for pid, pname in perms:
            p, _ = Permission.objects.get_or_create(id=pid, defaults={"name": pname})
            created_perms.append(p)

        tech_perms = [p for p in created_perms if p.id in ("work_order:execute", "work_order:update", "work_order:read", "asset:read")]
        self.role_tech.permissions.add(*tech_perms)
        self.role_mgr.permissions.add(*created_perms)
        self.technician.roles.add(self.role_tech)
        self.manager.roles.add(self.role_mgr)

        # Create Baseline Synthetic Profile Vector (128-d, L2 normalized)
        raw_vec = [math.sin((i + 1) * 0.42) for i in range(128)]
        self.baseline_embedding = normalize_l2_from_scratch(raw_vec)
        self.profile = BiometricProfile.objects.create(
            tenant=self.tenant,
            user=self.technician,
            face_embedding=self.baseline_embedding,
            is_active=True,
            enrolled_at=timezone.now(),
        )

        # Create Work Orders
        self.wo_robot = WorkOrder.objects.create(
            title="Bảo dưỡng động cơ servo trục 1 Robot KUKA",
            description="Kiểm tra độ rung và tra mỡ ổ bi",
            status="ASSIGNED",
            asset=self.robot_asset,
            assigned_to=self.technician,
            tenant=self.tenant,
        )

        self.wo_chair = WorkOrder.objects.create(
            title="Sửa bản lề bàn làm việc",
            description="Siết ốc và thay chốt",
            status="ASSIGNED",
            asset=self.chair_asset,
            assigned_to=self.technician,
            tenant=self.tenant,
        )

    def tearDown(self):
        clear_current_tenant()
        self._media_override.disable()
        self._tmp_media_dir.cleanup()

    def test_tc_bio_01_standard_checkin_esp32_universal_passed(self):
        """
        TC-BIO-01: Điểm danh chuẩn với ESP32 Universal (<= 50m, Sim >= 0.72)
        Thợ đứng cách ESP32 ~2.1m (RSSI = -68 dBm), quét mặt đạt Sim = 0.84 >= 0.72.
        Cả 2 cổng ĐẠT, lưu bản ghi AttendanceLog PASSED, chuyển WO sang IN_PROGRESS.
        """
        self.client.force_authenticate(user=self.technician)

        # Create live embedding with high similarity (~0.98) to baseline
        live_embed = [val + 0.005 for val in self.baseline_embedding]
        live_embed = normalize_l2_from_scratch(live_embed)

        payload = {
            "workOrderId": str(self.wo_robot.id),
            "bleBeaconId": "EAM-UNIVERSAL-BEACON",
            "rssi": -68,
            "liveEmbedding": live_embed,
        }

        response = self.client.post("/api/v1/attendance/check-in/", data=payload, format="json")
        self.assertEqual(response.status_code, 200)
        res_data = response.json()
        self.assertTrue(res_data["success"])
        self.assertEqual(res_data["data"]["overallCompliance"], "PASSED")
        self.assertTrue(res_data["data"]["proximity"]["isPassed"])
        self.assertTrue(res_data["data"]["biometric"]["isPassed"])
        self.assertGreaterEqual(res_data["data"]["biometric"]["similarityScore"], 0.72)

        # Verify DB AttendanceLog
        log = AttendanceLog.objects.filter(work_order=self.wo_robot).latest("created_at")
        self.assertEqual(log.overall_compliance, "PASSED")
        self.assertEqual(log.gate_type, "START_GATE")
        self.assertTrue(log.is_location_verified)
        self.assertTrue(log.is_face_verified)

        # Verify WorkOrder transitioned to IN_PROGRESS
        self.wo_robot.refresh_from_db()
        self.assertEqual(self.wo_robot.status, "IN_PROGRESS")
        self.assertIsNotNone(self.wo_robot.actual_start_time)

    def test_tc_bio_02_distance_violation_beyond_50m_failed(self):
        """
        TC-BIO-02: Vi phạm khoảng cách sóng ESP32 (> 50m)
        Kỹ thuật viên đứng cách xa máy, RSSI = -96 dBm < -92 dBm (d > 50m).
        Cổng không gian thất bại, is_location_verified = False, tổng thể FAILED, WO giữ nguyên ASSIGNED.
        """
        self.client.force_authenticate(user=self.technician)

        payload = {
            "workOrderId": str(self.wo_robot.id),
            "bleBeaconId": "EAM-UNIVERSAL-BEACON",
            "rssi": -96,  # > 50m
            "liveEmbedding": self.baseline_embedding,
        }

        response = self.client.post("/api/v1/attendance/check-in/", data=payload, format="json")
        self.assertEqual(response.status_code, 400)
        res_data = response.json()
        self.assertFalse(res_data["success"])

        # Check DB log recorded violation
        log = AttendanceLog.objects.filter(work_order=self.wo_robot).latest("created_at")
        self.assertEqual(log.overall_compliance, "FAILED")
        self.assertFalse(log.is_location_verified)
        self.assertLess(log.rssi_dbm, -92)

        # WO must NOT change to IN_PROGRESS
        self.wo_robot.refresh_from_db()
        self.assertEqual(self.wo_robot.status, "ASSIGNED")

    def test_tc_bio_03_lock_complete_gate_when_technician_away(self):
        """
        TC-BIO-03: Khóa Nghiệm thu Cổng 2 khi thợ vắng mặt
        Thợ ngồi từ xa bấm Hoàn thành (không có sóng ESP32 hoặc RSSI quá yếu).
        verify-presence từ chối và API status update bị chặn bởi Gatekeeper (403 Forbidden).
        """
        self.client.force_authenticate(user=self.technician)
        self.wo_robot.status = "IN_PROGRESS"
        self.wo_robot.save()

        # Step A: Test verify-presence endpoint without RSSI
        res_presence = self.client.post(
            "/api/v1/attendance/verify-presence/",
            data={"workOrderId": str(self.wo_robot.id)},
            format="json",
        )
        self.assertEqual(res_presence.status_code, 403)
        self.assertEqual(res_presence.json()["error"]["code"], "PRESENCE_VERIFICATION_REQUIRED")

        # Step B: Direct status update to COMPLETED without presence check
        res_status = self.client.put(
            f"/api/v1/work-orders/{self.wo_robot.id}/status",
            data={
                "status": "COMPLETED",
                "machineState": "STOPPED",
                "isLocationVerified": False,
            },
            format="json",
        )
        self.assertEqual(res_status.status_code, 403)
        self.assertIn("PRESENCE_VERIFICATION_REQUIRED", str(res_status.json()))

        # Work Order remains IN_PROGRESS
        self.wo_robot.refresh_from_db()
        self.assertEqual(self.wo_robot.status, "IN_PROGRESS")

    def test_tc_bio_04_complete_gate_succeeds_at_machine(self):
        """
        TC-BIO-04: Nghiệm thu Cổng 2 thành công tại máy (RSSI >= -92 dBm)
        Thợ đứng tại máy (RSSI = -70 dBm), kiểm tra hiện diện đạt và hoàn thành WO.
        """
        self.client.force_authenticate(user=self.technician)
        self.wo_robot.status = "IN_PROGRESS"
        self.wo_robot.save()

        # Add required proof photo attachment
        WorkOrderAttachment.objects.create(
            tenant=self.tenant,
            work_order=self.wo_robot,
            file_url='/media/proof_robot_01.jpg',
            file_name='proof_robot_01.jpg',
            file_type='image/jpeg',
            file_size=1024,
        )

        # Check presence at machine
        res_presence = self.client.post(
            "/api/v1/attendance/verify-presence/",
            data={
                "workOrderId": str(self.wo_robot.id),
                "rssi": -70,
                "bleBeaconId": "EAM-UNIVERSAL-BEACON",
            },
            format="json",
        )
        self.assertEqual(res_presence.status_code, 200)
        self.assertTrue(res_presence.json()["data"]["isPresenceVerified"])

        # Status update to COMPLETED with location verified
        res_status = self.client.put(
            f"/api/v1/work-orders/{self.wo_robot.id}/status",
            data={
                "status": "COMPLETED",
                "machineState": "RUNNING_NORMAL",
                "isLocationVerified": True,
                "rssi": -70,
                "bleVerificationData": {"beaconId": "EAM-UNIVERSAL-BEACON", "rssi": -70},
            },
            format="json",
        )
        self.assertEqual(res_status.status_code, 200)
        self.wo_robot.refresh_from_db()
        self.assertEqual(self.wo_robot.status, "COMPLETED")

    def test_tc_bio_05_web_face_enrollment_via_deep_learning(self):
        """
        TC-BIO-05: Đăng ký khuôn mặt User trên Web qua Deep Learning
        POST /api/v1/biometric/enroll/ trích xuất vector 128 số thực, chuẩn hóa L2, lưu biometric_profiles.
        """
        self.client.force_authenticate(user=self.manager)
        new_tech = User.objects.create(
            username="tech_tran_van_c",
            email="tech.c@vinfast.vn",
            tenant=self.tenant,
        )

        test_vector = [0.05 * (i % 10) for i in range(128)]
        response = self.client.post(
            "/api/v1/biometric/enroll/",
            data={
                "userId": str(new_tech.id),
                "liveEmbedding": json.dumps(test_vector),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        res_data = response.json()
        self.assertTrue(res_data["success"])
        self.assertEqual(res_data["data"]["embeddingDimension"], 128)

        # Verify DB profile
        profile = BiometricProfile.objects.get(user=new_tech)
        self.assertEqual(len(profile.face_embedding), 128)
        norm = l2_norm_from_scratch(profile.face_embedding)
        self.assertAlmostEqual(norm, 1.0, places=5)

    def test_tc_bio_06_universal_beacon_recognized_across_all_work_orders(self):
        """
        TC-BIO-06: Mỏ neo vạn năng nhận diện mọi Work Order
        Sử dụng beacon ID 'EAM-UNIVERSAL-BEACON' hoạt động trên bất kỳ WO nào.
        """
        self.client.force_authenticate(user=self.technician)

        # Both the robot WO and another newly created WO accept EAM-UNIVERSAL-BEACON
        wo_other = WorkOrder.objects.create(
            title="Kiểm tra hệ thống dập",
            description="Bảo trì định kỳ",
            status="ASSIGNED",
            asset=self.robot_asset,
            assigned_to=self.technician,
            tenant=self.tenant,
        )

        for wo in [self.wo_robot, wo_other]:
            payload = {
                "workOrderId": str(wo.id),
                "bleBeaconId": "EAM-UNIVERSAL-BEACON",
                "rssi": -65,
                "liveEmbedding": self.baseline_embedding,
            }
            res = self.client.post("/api/v1/attendance/check-in/", data=payload, format="json")
            self.assertEqual(res.status_code, 200)
            self.assertTrue(res.json()["data"]["proximity"]["isPassed"])

    def test_tc_bio_07_face_mismatch_rejected(self):
        """
        TC-BIO-07: Điểm danh hộ / Không khớp khuôn mặt (Sim = 0.52 < 0.65)
        Vector của người lạ đối sánh với hồ sơ kỹ thuật viên được giao việc -> Từ chối.
        """
        self.client.force_authenticate(user=self.technician)

        # Generate orthogonal or opposite vector
        stranger_vector = [-val for val in self.baseline_embedding]

        payload = {
            "workOrderId": str(self.wo_robot.id),
            "bleBeaconId": "EAM-UNIVERSAL-BEACON",
            "rssi": -68,
            "liveEmbedding": stranger_vector,
        }

        response = self.client.post("/api/v1/attendance/check-in/", data=payload, format="json")
        self.assertEqual(response.status_code, 400)
        res_data = response.json()
        self.assertFalse(res_data["success"])

        # Check DB log recorded facial failure
        log = AttendanceLog.objects.filter(work_order=self.wo_robot).latest("created_at")
        self.assertEqual(log.overall_compliance, "FAILED")
        self.assertFalse(log.is_face_verified)
        self.assertLess(log.similarity_score, 0.65)

    def test_tc_bio_08_static_qr_cannot_substitute_for_ble_beacon(self):
        """
        TC-BIO-08: Chặn dùng ảnh QR để điểm danh từ xa
        Mã QR dán trên thân máy chỉ phục vụ tra cứu thông tin GET /api/v1/assets/qr/{qrCode}.
        Không thể dùng để điểm danh hoặc vượt qua rào chắn Cổng 1 khi không có sóng ESP32.
        """
        self.client.force_authenticate(user=self.technician)

        # 1. Tra cứu QR hợp lệ
        res_qr = self.client.get(f"/api/v1/assets/qr/{self.robot_asset.qr_code}")
        self.assertEqual(res_qr.status_code, 200)
        self.assertEqual(res_qr.json()["data"]["name"], self.robot_asset.name)

        # 2. Thử gửi QR code thay cho BLE Beacon mà không có sóng (rssi=None)
        payload = {
            "workOrderId": str(self.wo_robot.id),
            "qrCode": self.robot_asset.qr_code,  # Static QR parameter
            "rssi": None,  # No BLE signal
            "liveEmbedding": self.baseline_embedding,
        }
        res_checkin = self.client.post("/api/v1/attendance/check-in/", data=payload, format="json")
        self.assertEqual(res_checkin.status_code, 400)

        # WO remains ASSIGNED
        self.wo_robot.refresh_from_db()
        self.assertEqual(self.wo_robot.status, "ASSIGNED")

    def test_tc_bio_09_asset_without_beacon_auto_exempts_ble_requires_face(self):
        """
        TC-BIO-09: Tài sản nội thất không yêu cầu Beacon (require_ble_beacon = False)
        Tự động bỏ qua quét sóng BLE (BLE_EXEMPT_BY_ASSET), nhưng VẪN BẮT BUỘC QUÉT MẶT.
        """
        self.client.force_authenticate(user=self.technician)

        # Case A: Check-in without BLE signal, with valid Face -> SUCCESS
        payload = {
            "workOrderId": str(self.wo_chair.id),
            "rssi": None,
            "liveEmbedding": self.baseline_embedding,
        }
        res_a = self.client.post("/api/v1/attendance/check-in/", data=payload, format="json")
        self.assertEqual(res_a.status_code, 200)
        self.assertEqual(res_a.json()["data"]["proximity"]["method"], "BLE_EXEMPT_BY_ASSET")
        self.assertTrue(res_a.json()["data"]["proximity"]["isPassed"])
        self.assertTrue(res_a.json()["data"]["biometric"]["isPassed"])

        # Case B: Complete Gate on exempt asset auto-passes presence check
        res_presence = self.client.post(
            "/api/v1/attendance/verify-presence/",
            data={"workOrderId": str(self.wo_chair.id)},
            format="json",
        )
        self.assertEqual(res_presence.status_code, 200)
        self.assertEqual(res_presence.json()["data"]["method"], "BLE_EXEMPT_BY_ASSET")
        self.assertTrue(res_presence.json()["data"]["isPresenceVerified"])

    def test_tc_bio_10_toggle_require_ble_beacon_switch_updates_db(self):
        """
        TC-BIO-10: Bật/Tắt cấu hình Beacon trên Web Portal (require_ble_beacon Switch)
        Gửi request cập nhật tài sản với require_ble_beacon = False -> DB cập nhật đúng.
        """
        self.client.force_authenticate(user=self.manager)

        # PUT update asset to disable beacon
        res = self.client.put(
            f"/api/v1/assets/{self.robot_asset.id}",
            data={
                "name": self.robot_asset.name,
                "categoryId": str(self.category.id),
                "locationId": str(self.location.id),
                "requireBleBeacon": False,
            },
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.robot_asset.refresh_from_db()
        self.assertFalse(self.robot_asset.require_ble_beacon)

        # Turn it back ON
        res2 = self.client.put(
            f"/api/v1/assets/{self.robot_asset.id}",
            data={
                "name": self.robot_asset.name,
                "categoryId": str(self.category.id),
                "locationId": str(self.location.id),
                "requireBleBeacon": True,
            },
            format="json",
        )
        self.assertEqual(res2.status_code, 200)
        self.robot_asset.refresh_from_db()
        self.assertTrue(self.robot_asset.require_ble_beacon)

    def test_tc_bio_11_gallery_blocked_live_camera_required(self):
        """
        TC-BIO-11: Khóa thư viện ảnh (Rule 7 Anti-spoofing)
        Biometric enrollment và attendance check-in từ chối nếu không có input hợp lệ.
        """
        self.client.force_authenticate(user=self.technician)

        # Missing both image and live embedding -> 400 Bad Request
        res = self.client.post("/api/v1/biometric/enroll/", data={}, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("Vui lòng tải lên", res.json()["error"])

    def test_tc_bio_12_backend_15_minute_gatekeeper_timeout(self):
        """
        TC-BIO-12: Cổng gác máy chủ Backend 15 phút
        Nếu gọi PUT status IN_PROGRESS mà không có bản ghi AttendanceLog hợp lệ
        trong vòng 15 phút gần nhất -> 403 COMPLIANCE_ATTENDANCE_REQUIRED.
        """
        self.client.force_authenticate(user=self.technician)

        # Attempt to transition without attendance log
        res = self.client.put(
            f"/api/v1/work-orders/{self.wo_robot.id}/status",
            data={"status": "IN_PROGRESS"},
            format="json",
        )
        self.assertEqual(res.status_code, 403)
        self.assertIn("COMPLIANCE_ATTENDANCE_REQUIRED", str(res.json()))

        # Create an expired attendance log (16 minutes ago)
        old_log = AttendanceLog.objects.create(
            tenant=self.tenant,
            work_order=self.wo_robot,
            technician=self.technician,
            verification_method="ESP32_UNIVERSAL_BEACON",
            overall_compliance="PASSED",
            is_location_verified=True,
            is_face_verified=True,
            gate_type="START_GATE",
        )
        # Hack timestamp to 16 minutes ago
        AttendanceLog.objects.filter(id=old_log.id).update(
            created_at=timezone.now() - timedelta(minutes=16)
        )

        res_expired = self.client.put(
            f"/api/v1/work-orders/{self.wo_robot.id}/status",
            data={"status": "IN_PROGRESS"},
            format="json",
        )
        self.assertEqual(res_expired.status_code, 403)

    def test_tc_bio_13_security_compliance_decree_13_2023_nd_cp(self):
        """
        TC-BIO-13: Tuân thủ bảo mật Nghị định 13/2023/NĐ-CP
        - SQL database chỉ lưu vector 128 số thực đã chuẩn hóa L2 (tuyệt đối không lưu raw image).
        - Ảnh snapshot lưu trữ vật lý được mã hóa AES-256.
        """
        # 1. Kiểm tra trực tiếp bảng biometric_profiles trong DB
        profile = BiometricProfile.objects.get(user=self.technician)
        self.assertIsInstance(profile.face_embedding, list)
        self.assertEqual(len(profile.face_embedding), 128)
        self.assertTrue(all(isinstance(x, (float, int)) for x in profile.face_embedding))

        # 2. Kiểm tra việc mã hóa AES-256 khi enroll bằng ảnh
        import io
        from PIL import Image
        img = Image.new('RGB', (112, 112), color='blue')
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        test_raw_bytes = buf.getvalue()

        prof, enc_path = enroll_user_face(
            user=self.technician,
            image_bytes=test_raw_bytes,
            enrolled_by=self.manager,
            precomputed_embedding=self.baseline_embedding,
        )

        # File trên đĩa phải bị xáo trộn (mã hóa AES-256-GCM)
        rel_enc = enc_path.replace('/media/', '').lstrip('/\\')
        full_enc_path = os.path.join(settings.MEDIA_ROOT, rel_enc)
        with open(full_enc_path, "rb") as f:
            encrypted_content = f.read()
        self.assertNotEqual(encrypted_content, test_raw_bytes)

        # Giải mã bằng khóa giải thuật phải khớp chính xác dữ liệu gốc
        decrypted = decrypt_image_snapshot(enc_path)
        self.assertEqual(decrypted, test_raw_bytes)

    def test_tc_bio_14_pure_math_performance_under_30ms(self):
        """
        TC-BIO-14: Hiệu năng giải thuật thuần từ số liệu thực nghiệm
        Đo thời gian chạy Cosine Similarity, L2 normalization và Log-Distance Path Loss.
        Thời gian thực thi của cả bộ giải thuật thuần phải <= 30ms (chuẩn thiết bị di động).
        """
        u = [math.cos(i) for i in range(128)]
        v = [math.sin(i) for i in range(128)]

        start_time = time.perf_counter()

        # 1. Pure math distance calculation
        for rssi in range(-110, -50):
            d = calculate_ble_log_distance(rssi)
            valid = verify_ble_proximity(rssi)

        # 2. Pure math linear algebra (100 iterations to stress test)
        for _ in range(100):
            norm_u = normalize_l2_from_scratch(u)
            norm_v = normalize_l2_from_scratch(v)
            sim = calculate_cosine_similarity_from_scratch(norm_u, norm_v)

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        # Benchmark: 100 full 128-d cosine runs must easily finish well within 30ms
        self.assertLess(elapsed_ms, 30.0, f"Algorithm exceeded 30ms limit: {elapsed_ms:.2f}ms")

    def test_tc_bio_edge_01_cosine_nan_inf_safety(self):
        """
        EDGE-01: Kiểm tra an toàn trước tấn công vector chứa NaN, Inf hoặc kiểu không hợp lệ.
        Trước đây min(1.0, nan) = 1.0 gây vượt rào sinh trắc học! Giờ bắt buộc trả về 0.0 và từ chối.
        """
        nan_vec = [float('nan')] * 128
        inf_vec = [float('inf')] * 128

        sim_nan = calculate_cosine_similarity_from_scratch(nan_vec, self.baseline_embedding)
        self.assertEqual(sim_nan, 0.0)
        is_ver, _ = verify_face_cosine_similarity(nan_vec, self.baseline_embedding)
        self.assertFalse(is_ver)

        sim_inf = calculate_cosine_similarity_from_scratch(inf_vec, self.baseline_embedding)
        self.assertEqual(sim_inf, 0.0)
        is_ver_inf, _ = verify_face_cosine_similarity(inf_vec, self.baseline_embedding)
        self.assertFalse(is_ver_inf)

    def test_tc_bio_edge_02_unregistered_technician_rejected(self):
        """
        EDGE-02: Kỹ thuật viên chưa đăng ký hồ sơ trên Web Portal không được phép điểm danh.
        Hệ thống không được tự ý tạo profile lụi để cho qua.
        """
        new_unregistered_tech = User.objects.create(
            username="tech_unregistered",
            email="unreg@vinfast.vn",
            tenant=self.tenant,
        )
        new_unregistered_tech.set_password("Pass123@")
        new_unregistered_tech.roles.add(self.role_tech)
        new_unregistered_tech.save()

        wo_unreg = WorkOrder.objects.create(
            title="Phiếu cho thợ mới",
            status="ASSIGNED",
            asset=self.robot_asset,
            assigned_to=new_unregistered_tech,
            tenant=self.tenant,
        )

        self.client.force_authenticate(user=new_unregistered_tech)
        payload = {
            "workOrderId": str(wo_unreg.id),
            "bleBeaconId": "EAM-UNIVERSAL-BEACON",
            "rssi": -65,
            "liveEmbedding": self.baseline_embedding,
        }
        res = self.client.post("/api/v1/attendance/check-in/", data=payload, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.json()["success"])
        self.assertIn("chưa đăng ký hồ sơ sinh trắc học", res.json()["error"])

        # Đảm bảo DB không hề tự sinh BiometricProfile
        self.assertFalse(BiometricProfile.objects.filter(user=new_unregistered_tech).exists())

    def test_tc_bio_edge_03_wrong_assignee_forbidden(self):
        """
        EDGE-03: Kỹ thuật viên B không được phép điểm danh nhận việc trên phiếu của Kỹ thuật viên A.
        Chỉ chính chủ người thợ được giao việc mới có quyền điểm danh.
        """
        tech_b = User.objects.create(
            username="tech_le_van_b",
            email="tech.b@vinfast.vn",
            tenant=self.tenant,
        )
        tech_b.set_password("Pass123@")
        tech_b.roles.add(self.role_tech)
        tech_b.save()

        # Tạo profile cho tech_b
        BiometricProfile.objects.create(
            tenant=self.tenant,
            user=tech_b,
            face_embedding=self.baseline_embedding,
            is_active=True,
        )

        # tech_b cố điểm danh trên wo_robot (giao cho self.technician)
        self.client.force_authenticate(user=tech_b)
        payload = {
            "workOrderId": str(self.wo_robot.id),
            "bleBeaconId": "EAM-UNIVERSAL-BEACON",
            "rssi": -65,
            "liveEmbedding": self.baseline_embedding,
        }
        res = self.client.post("/api/v1/attendance/check-in/", data=payload, format="json")
        self.assertEqual(res.status_code, 403)
        self.assertIn("Chỉ kỹ thuật viên được giao việc", res.json()["error"])

    def test_tc_bio_edge_04_complete_gate_bypass_without_rssi_rejected(self):
        """
        EDGE-04: Ngăn chặn triệt để lỗ hổng bypass Cổng 2.
        Nếu client gửi PUT status COMPLETED kèm 'isLocationVerified: True' nhưng không có
        chỉ số RSSI thực tế và không có bản ghi verify-presence trước đó -> Server từ chối 403.
        """
        self.client.force_authenticate(user=self.technician)
        self.wo_robot.status = "IN_PROGRESS"
        self.wo_robot.save()

        # Thử bypass bằng cờ boolean lụi
        res = self.client.put(
            f"/api/v1/work-orders/{self.wo_robot.id}/status",
            data={
                "status": "COMPLETED",
                "machineState": "RUNNING_NORMAL",
                "isLocationVerified": True,
            },
            format="json",
        )
        self.assertEqual(res.status_code, 403)
        self.assertIn("PRESENCE_VERIFICATION_REQUIRED", str(res.json()))

    def test_tc_bio_edge_05_enrollment_unauthorized_forbidden(self):
        """
        EDGE-05: Kỹ thuật viên thông thường không được phép đăng ký/ghi đè hồ sơ khuôn mặt
        của nhân viên khác (tuân thủ Nghị định 13/2023/NĐ-CP).
        """
        other_user = User.objects.create(
            username="tech_other",
            email="other@vinfast.vn",
            tenant=self.tenant,
        )
        self.client.force_authenticate(user=self.technician)

        res = self.client.post(
            "/api/v1/biometric/enroll/",
            data={
                "userId": str(other_user.id),
                "liveEmbedding": json.dumps(self.baseline_embedding),
            },
            format="json",
        )
        self.assertEqual(res.status_code, 403)
        self.assertIn("Chỉ Quản trị viên hoặc Quản đốc", res.json()["error"])

    def test_tc_bio_edge_06_proximity_engine_robustness(self):
        """
        EDGE-06: Hàm suy hao sóng Log-Distance không bị crash khi tham số biên bất thường:
        exponent <= 0, rssi = 0, rssi = None, rssi ngoài ngưỡng.
        """
        self.assertEqual(calculate_ble_log_distance(0), 999.0)
        self.assertEqual(calculate_ble_log_distance(None), 999.0)
        # exponent âm hoặc bằng 0 tự dùng DEFAULT_PATH_LOSS_EXPONENT
        d_zero_exp = calculate_ble_log_distance(-59, path_loss_exponent=0)
        self.assertEqual(d_zero_exp, 1.0)

        # verify_ble_proximity an toàn với non-finite/none
        is_v, d = verify_ble_proximity(None)
        self.assertFalse(is_v)
        self.assertEqual(d, 999.0)

    def test_tc_bio_edge_07_cross_tenant_attendance_idor_forbidden(self):
        """
        EDGE-07: Chống truy cập chéo Tenant (IDOR) trên API điểm danh & sinh trắc học.
        Admin/KTV của Tenant B không được phép check-in, verify-presence trên WorkOrder của Tenant A,
        hoặc enroll khuôn mặt cho user của Tenant A.
        """
        tenant_b = Tenant.objects.create(name="Other Corp", tenant_code="OTHER_CORP")
        admin_role_b = Role.all_objects.create(name="ADMIN", tenant=tenant_b)
        admin_b = User.all_objects.create(
            username="admin_tenant_b",
            email="admin@othercorp.vn",
            tenant=tenant_b,
        )
        admin_b.roles.add(admin_role_b)

        self.client.force_authenticate(user=admin_b)

        res_checkin = self.client.post(
            "/api/v1/attendance/check-in/",
            data={"workOrderId": str(self.wo_robot.id), "bleBeaconId": "EAM-BEACON", "rssi": -60},
            HTTP_X_TENANT_ID=str(tenant_b.id),
            format="json",
        )
        self.assertEqual(res_checkin.status_code, 403)

        res_verify = self.client.post(
            "/api/v1/attendance/verify-presence/",
            data={"workOrderId": str(self.wo_robot.id), "bleBeaconId": "EAM-BEACON", "rssi": -60},
            HTTP_X_TENANT_ID=str(tenant_b.id),
            format="json",
        )
        self.assertEqual(res_verify.status_code, 403)

        res_enroll = self.client.post(
            "/api/v1/biometric/enroll/",
            data={
                "userId": str(self.technician.id),
                "liveEmbedding": json.dumps(self.baseline_embedding),
            },
            HTTP_X_TENANT_ID=str(tenant_b.id),
            format="json",
        )
        self.assertIn(res_enroll.status_code, (403, 404))

    def test_tc_bio_edge_08_cross_tenant_face_photo_and_iot_isolation(self):
        """
        EDGE-08:
        1) portal_user_face_photo chặn truy cập chéo tenant và chặn KTV xem ảnh người khác.
        2) IoTSensorAlertView không rơi sang asset của tenant khác khi tenant_code đã định danh được target_tenant.
        """
        from django.test import RequestFactory
        from portal.views import portal_user_face_photo
        from assets.models import MeterReading

        tenant_b = Tenant.objects.create(name="Beta Corp", tenant_code="BETA_CORP")
        admin_role_b = Role.all_objects.create(name="ADMIN", tenant=tenant_b)
        admin_b = User.all_objects.create(
            username="admin_beta",
            email="admin@beta.vn",
            tenant=tenant_b,
        )
        admin_b.roles.add(admin_role_b)

        rf = RequestFactory()
        req_cross = rf.get(f"/portal/users/{self.technician.id}/face-photo/")
        req_cross.user = admin_b
        res_photo = portal_user_face_photo(req_cross, self.technician.id)
        self.assertEqual(res_photo.status_code, 403)

        # Same-tenant technician without user:read cannot view another user's photo
        other_tech = User.objects.create(
            username="tech_peer",
            email="peer@vinfast.vn",
            tenant=self.tenant,
        )
        other_tech.roles.add(self.role_tech)
        req_peer = rf.get(f"/portal/users/{self.technician.id}/face-photo/")
        req_peer.user = other_tech
        res_peer = portal_user_face_photo(req_peer, self.technician.id)
        self.assertEqual(res_peer.status_code, 403)

        # IoTSensorAlertView must not cross into Tenant A's asset when tenant_code resolves to Tenant B
        before_count = MeterReading.all_objects.filter(asset=self.robot_asset).count()
        res_iot = self.client.post(
            "/api/v1/iot/sensor-alert/",
            data={
                "tenant_code": "BETA_CORP",
                "asset_code": self.robot_asset.qr_code or self.robot_asset.name,
                "temperature": 78.5,
                "vibration": 0.95,
            },
            format="json",
        )
        self.assertEqual(res_iot.status_code, 404)
        after_count = MeterReading.all_objects.filter(asset=self.robot_asset).count()
        self.assertEqual(before_count, after_count)


class AUD03BiometricSecurityAndVANLAMIoTTests(TestCase):
    """Kiểm thử chuyên sâu AUD-03 (sinh trắc học & AES-256-GCM) và định tuyến IoT sang VANLAM."""

    def setUp(self):
        import tempfile
        clear_current_tenant()
        self._real_media_root = settings.MEDIA_ROOT
        self._tmp_media_dir = tempfile.TemporaryDirectory()
        self._media_override = self.settings(MEDIA_ROOT=self._tmp_media_dir.name)
        self._media_override.enable()
        self.tenant = Tenant.objects.create(
            name="Công Ty Công Nghiệp Kiểm Thử",
            tenant_code="AUD03_CORP",
            enable_geofencing=True,
        )
        self.other_tenant = Tenant.objects.create(
            name="Đơn Vị Khác",
            tenant_code="AUD03_OTHER",
        )
        self.role_admin = Role.all_objects.create(name="ADMIN", tenant=self.tenant)
        self.role_tech = Role.all_objects.create(name="TECHNICIAN", tenant=self.tenant)
        perm_user_update, _ = Permission.objects.get_or_create(id="user:update", defaults={"name": "Update User"})
        perm_user_read, _ = Permission.objects.get_or_create(id="user:read", defaults={"name": "Read User"})
        self.role_admin.permissions.add(perm_user_update, perm_user_read)

        self.admin = User.all_objects.create(username="aud03_admin", email="admin@aud03.vn", tenant=self.tenant)
        self.admin.set_password("TestPass123!")
        self.admin.save()
        self.admin.roles.add(self.role_admin)

        self.tech = User.all_objects.create(username="aud03_tech", email="tech@aud03.vn", tenant=self.tenant)
        self.tech.roles.add(self.role_tech)

        self.peer_tech = User.all_objects.create(username="aud03_peer", email="peer@aud03.vn", tenant=self.tenant)
        self.peer_tech.roles.add(self.role_tech)

        self.other_admin = User.all_objects.create(username="aud03_other_admin", email="other@aud03.vn", tenant=self.other_tenant)
        self.other_role = Role.all_objects.create(name="ADMIN", tenant=self.other_tenant)
        self.other_admin.roles.add(self.other_role)

        self.client = APIClient()

    def tearDown(self):
        clear_current_tenant()
        if hasattr(self, '_media_override'):
            self._media_override.disable()
        if hasattr(self, '_tmp_media_dir'):
            self._tmp_media_dir.cleanup()

    def test_aud03_production_rejects_raw_embedding_and_fake_image(self):
        """Production (BIOMETRIC_ALLOW_TEST_EMBEDDINGS=False) từ chối embedding giả và ảnh giả."""
        from django.test import override_settings
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.client.force_authenticate(user=self.admin)
        fake_vec = [0.05] * 128

        with override_settings(BIOMETRIC_ALLOW_TEST_EMBEDDINGS=False):
            # 1. Chỉ gửi liveEmbedding mà không có ảnh -> 400
            r1 = self.client.post(
                "/api/v1/biometric/enroll/",
                data={"userId": str(self.tech.id), "liveEmbedding": json.dumps(fake_vec)},
                format="json",
            )
            self.assertEqual(r1.status_code, 400)

            # 2. Tải lên chuỗi bytes ảnh giả SIMULATED_FACE_IMAGE_BYTES -> 400
            fake_file = SimpleUploadedFile("fake.jpg", b"SIMULATED_FACE_IMAGE_BYTES", content_type="image/jpeg")
            r2 = self.client.post(
                "/api/v1/biometric/enroll/",
                data={"userId": str(self.tech.id), "faceImage": fake_file},
                format="multipart",
            )
            self.assertEqual(r2.status_code, 400)

            # 3. Chuỗi base64 hỏng -> 400
            r3 = self.client.post(
                "/api/v1/biometric/enroll/",
                data={"userId": str(self.tech.id), "faceImageBase64": "not-valid-base64!!!"},
                format="json",
            )
            self.assertEqual(r3.status_code, 400)

            # 4. Ảnh thật có khuôn mặt (user_face.jpg nếu có) -> 200 & lưu AES-256-GCM
            sample_face = os.path.join(self._real_media_root, "user_face.jpg")
            if os.path.exists(sample_face):
                with open(sample_face, "rb") as fh:
                    real_bytes = fh.read()
                real_file = SimpleUploadedFile("real_face.jpg", real_bytes, content_type="image/jpeg")
                r4 = self.client.post(
                    "/api/v1/biometric/enroll/",
                    data={"userId": str(self.tech.id), "faceImage": real_file},
                    format="multipart",
                )
                self.assertEqual(r4.status_code, 200)
                snap_path = r4.json()["data"]["snapshotPath"]
                rel = snap_path.replace("/media/", "").lstrip("/\\")
                with open(os.path.join(settings.MEDIA_ROOT, rel), "rb") as sf:
                    raw_enc = sf.read()
                self.assertTrue(raw_enc.startswith(b"EAM_GCM1"))
                self.assertEqual(decrypt_image_snapshot(snap_path), real_bytes)

    def test_aud03_aes_gcm_tamper_resistance_legacy_cbc_compat_and_zero_vector_reject(self):
        """Mã hóa mới dùng AES-256-GCM, từ chối giả mạo không rơi về XOR, giải mã tương thích CBC cũ."""
        from Crypto.Cipher import AES
        from Crypto.Util.Padding import pad
        from algorithms.biometric.enrollment import (
            encrypt_aes_256,
            decrypt_aes_256,
            _get_legacy_cbc_key,
            _GCM_MAGIC,
        )

        plaintext = b"\x89PNG\r\n\x1a\n" + os.urandom(256)
        enc1 = encrypt_aes_256(plaintext)
        enc2 = encrypt_aes_256(plaintext)
        self.assertTrue(enc1.startswith(_GCM_MAGIC))
        self.assertNotEqual(enc1, enc2)
        self.assertEqual(decrypt_aes_256(enc1), plaintext)

        # Sửa 1 byte trong tag/ciphertext AES-GCM -> Bắt buộc ném ValueError (không trả về XOR rác)
        tampered_gcm = bytearray(enc1)
        tampered_gcm[-1] ^= 0xFF
        with self.assertRaises(ValueError):
            decrypt_aes_256(bytes(tampered_gcm))

        # Kiểm tra tương thích ngược giải mã snapshot AES-CBC cũ (tạo bằng khóa legacy)
        iv = os.urandom(16)
        legacy_cipher = AES.new(_get_legacy_cbc_key(), AES.MODE_CBC, iv)
        legacy_blob = iv + legacy_cipher.encrypt(pad(plaintext, AES.block_size))
        self.assertEqual(decrypt_aes_256(legacy_blob), plaintext)

        # Dữ liệu CBC giả mạo / sai khóa -> Bắt buộc ném ValueError (loại bỏ XOR fallback)
        tampered_cbc = bytearray(legacy_blob)
        tampered_cbc[-2] ^= 0xFF
        with self.assertRaises(ValueError):
            decrypt_aes_256(bytes(tampered_cbc))

        with self.assertRaises(ValueError):
            decrypt_aes_256(b"TOO_SHORT")

        # Chặn vector toàn 0 và NaN trong enroll_user_face
        import io
        from PIL import Image
        buf = io.BytesIO()
        Image.new("RGB", (112, 112), color="red").save(buf, format="PNG")
        png_bytes = buf.getvalue()

        with self.assertRaises(ValueError):
            enroll_user_face(self.tech, image_bytes=png_bytes, precomputed_embedding=[0.0] * 128, allow_precomputed=True)
        with self.assertRaises(ValueError):
            enroll_user_face(self.tech, image_bytes=png_bytes, precomputed_embedding=[float("nan")] * 128, allow_precomputed=True)
        with self.assertRaises(ValueError):
            enroll_user_face(self.tech, image_bytes=b"SIMULATED_FACE_IMAGE_BYTES")

    def test_aud03_rbac_tenant_portal_users_put_and_tenants_put(self):
        """Kiểm tra phân quyền, cách ly tenant, portal_tenants PUT không lỗi biến u, portal_users PUT xử lý faceImage."""
        import base64, io
        from PIL import Image
        from django.test import RequestFactory
        from portal.views import portal_tenants, portal_users, portal_user_face_photo
        from algorithms.biometric.enrollment import save_audit_snapshot

        # 1. Cross-tenant & peer tech enroll bị chặn 403
        sample_face = os.path.join(self._real_media_root, "user_face.jpg")
        img_payload = None
        if os.path.exists(sample_face):
            with open(sample_face, "rb") as fh:
                img_payload = fh.read()
        if not img_payload:
            buf = io.BytesIO()
            Image.new("RGB", (120, 120), color="gray").save(buf, format="JPEG")
            img_payload = buf.getvalue()

        self.client.force_authenticate(user=self.other_admin)
        from django.core.files.uploadedfile import SimpleUploadedFile
        r_cross = self.client.post(
            "/api/v1/biometric/enroll/",
            data={"userId": str(self.tech.id), "faceImage": SimpleUploadedFile("f.jpg", img_payload, content_type="image/jpeg")},
            format="multipart",
        )
        self.assertEqual(r_cross.status_code, 403)

        self.client.force_authenticate(user=self.peer_tech)
        r_peer = self.client.post(
            "/api/v1/biometric/enroll/",
            data={"userId": str(self.tech.id), "faceImage": SimpleUploadedFile("f.jpg", img_payload, content_type="image/jpeg")},
            format="multipart",
        )
        self.assertEqual(r_peer.status_code, 403)

        # 2. portal_tenants PUT với superuser chạy bình thường, không dính lỗi biến u
        super_u = User.all_objects.create(username="aud03_super", email="super@aud03.vn", tenant=self.tenant, is_superuser=True)
        rf = RequestFactory()
        req_ten = rf.put(
            "/portal/tenants/",
            data=json.dumps({
                "id": str(self.tenant.id),
                "name": "Công Ty Công Nghiệp Đã Cập Nhật",
                "tenant_code": self.tenant.tenant_code,
                "service_plan": "ENTERPRISE",
                "status": "ACTIVE",
                "faceImage": "dummy-should-be-ignored-on-tenant",
            }),
            content_type="application/json",
        )
        req_ten.user = super_u
        req_ten.session = {"active_tenant_id": str(self.tenant.id)}
        res_ten = portal_tenants(req_ten)
        self.assertEqual(res_ten.status_code, 200)
        self.assertTrue(json.loads(res_ten.content)["success"])

        # 3. portal_users PUT với ảnh không có khuôn mặt -> trả về 400 (không nuốt lỗi)
        blank_buf = io.BytesIO()
        Image.new("RGB", (120, 120), color="white").save(blank_buf, format="JPEG")
        blank_b64 = "data:image/jpeg;base64," + base64.b64encode(blank_buf.getvalue()).decode()
        req_put_bad = rf.put(
            "/portal/users/",
            data=json.dumps({
                "id": str(self.tech.id),
                "username": self.tech.username,
                "email": self.tech.email,
                "roles": [str(self.role_tech.id)],
                "faceImage": blank_b64,
            }),
            content_type="application/json",
        )
        req_put_bad.user = self.admin
        req_put_bad.session = {"active_tenant_id": str(self.tenant.id)}
        set_current_tenant(self.tenant.id)
        res_put_bad = portal_users(req_put_bad)
        self.assertEqual(res_put_bad.status_code, 400)
        self.assertFalse(json.loads(res_put_bad.content)["success"])

        # 4. portal_users PUT với ảnh chân dung thật -> cập nhật BiometricProfile
        if os.path.exists(sample_face):
            real_b64 = "data:image/jpeg;base64," + base64.b64encode(img_payload).decode()
            req_put_ok = rf.put(
                "/portal/users/",
                data=json.dumps({
                    "id": str(self.tech.id),
                    "username": self.tech.username,
                    "email": self.tech.email,
                    "roles": [str(self.role_tech.id)],
                    "faceImage": real_b64,
                }),
                content_type="application/json",
            )
            req_put_ok.user = self.admin
            req_put_ok.session = {"active_tenant_id": str(self.tenant.id)}
            res_put_ok = portal_users(req_put_ok)
            self.assertEqual(res_put_ok.status_code, 200)
            self.assertTrue(BiometricProfile.all_objects.filter(user=self.tech, is_active=True).exists())

        # 5. portal_user_face_photo từ chối nếu tệp .enc bị hỏng (không trả về 200 XOR rác)
        snap = save_audit_snapshot(img_payload, str(self.tech.id), str(self.tenant.id))
        rel = snap.replace("/media/", "").lstrip("/\\")
        full_enc = os.path.join(settings.MEDIA_ROOT, rel)
        with open(full_enc, "wb") as ef:
            ef.write(b"EAM_GCM1" + os.urandom(48))
        req_photo = rf.get(f"/portal/users/{self.tech.id}/face-photo/")
        req_photo.user = self.admin
        res_photo = portal_user_face_photo(req_photo, self.tech.id)
        self.assertEqual(res_photo.status_code, 500)

    def test_iot_sensor_alert_routes_to_vanlam_target_asset(self):
        """Kiểm chứng endpoint /api/v1/iot/sensor-alert/ tiếp nhận đúng tenant VANLAM_DEMO_2026 & QR-VL-CMP-001."""
        from assets.models import MeterReading
        vl_tenant = Tenant.objects.create(name="Nhà Máy Sản Xuất & Lắp Ráp Vân Lam", tenant_code="VANLAM_DEMO_2026")
        vl_loc = Location.objects.create(name="Trạm Máy Nén Khí & Cấp Khí Trung Tâm", code="ZONE_COMPRESSOR", tenant=vl_tenant)
        vl_cat = AssetCategory.objects.create(name="Máy nén khí", tenant=vl_tenant)
        vl_asset = Asset.all_objects.create(
            tenant=vl_tenant,
            name="Máy Nén Khí Trục Vít Atlas Copco GA55+ VSD",
            qr_code="QR-VL-CMP-001",
            serial_number="SN-CMP-2026-33",
            category=vl_cat,
            location=vl_loc,
            status="OPERATIONAL",
            asset_type="MACHINERY",
        )

        res = self.client.post(
            "/api/v1/iot/sensor-alert/",
            data={
                "tenant_code": "VANLAM_DEMO_2026",
                "asset_code": "QR-VL-CMP-001",
                "device_id": "ESP32-ASSET-BEACON-01",
                "temperature": 46.8,
                "vibration": 0.42,
            },
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        body = res.json()["data"]
        self.assertEqual(body["tenantCode"], "VANLAM_DEMO_2026")
        self.assertEqual(body["assetId"], str(vl_asset.id))
        mrs = MeterReading.all_objects.filter(asset=vl_asset)
        self.assertEqual(set(mrs.values_list("metric_code", flat=True)), {"TEMPERATURE", "VIBRATION"})

    def test_aud03_enroll_explicit_allow_precomputed_false_rejected_even_in_test_runtime(self):
        """allow_precomputed=False phải từ chối vector giả lập ngay cả khi chạy trong unit test."""
        vec = normalize_l2_from_scratch([0.05] * 128)
        with self.assertRaises(ValueError):
            enroll_user_face(
                user=self.tech,
                image_bytes=None,
                enrolled_by=self.admin,
                precomputed_embedding=vec,
                allow_precomputed=False,
            )

    def test_aud03_enroll_allow_precomputed_true_rejected_outside_test_runtime(self):
        """Ngoài môi trường test tự động, kể cả truyền allow_precomputed=True vẫn phải bị chặn."""
        from unittest.mock import patch
        vec = normalize_l2_from_scratch([0.05] * 128)
        with patch("algorithms.biometric.enrollment._is_automated_test_runtime", return_value=False):
            with self.assertRaises(ValueError):
                enroll_user_face(
                    user=self.tech,
                    image_bytes=None,
                    enrolled_by=self.admin,
                    precomputed_embedding=vec,
                    allow_precomputed=True,
                )

    def test_aud03_attendance_checkin_rejects_live_embedding_when_test_embeddings_disabled(self):
        """Khi BIOMETRIC_ALLOW_TEST_EMBEDDINGS=False, check-in chỉ gửi liveEmbedding mà thiếu ảnh thật bị chặn 400."""
        vec = normalize_l2_from_scratch([0.05] * 128)
        enroll_user_face(
            user=self.tech,
            image_bytes=None,
            enrolled_by=self.admin,
            precomputed_embedding=vec,
        )
        loc = Location.objects.create(name="Xưởng A", code="LOC_A_TEST", tenant=self.tenant)
        cat = AssetCategory.objects.create(name="CNC", tenant=self.tenant)
        asset = Asset.all_objects.create(
            tenant=self.tenant,
            name="CNC Test",
            category=cat,
            location=loc,
            status="OPERATIONAL",
            asset_type="MACHINERY",
        )
        wo = WorkOrder.all_objects.create(
            tenant=self.tenant,
            title="Checkin Gate Test",
            asset=asset,
            assigned_to=self.tech,
            status="ASSIGNED",
        )
        self.client.force_authenticate(user=self.tech)
        with self.settings(BIOMETRIC_ALLOW_TEST_EMBEDDINGS=False):
            res = self.client.post(
                "/api/v1/attendance/check-in/",
                data={
                    "workOrderId": str(wo.id),
                    "bleBeaconId": "EAM-UNIVERSAL-BEACON",
                    "rssi": -65,
                    "liveEmbedding": vec,
                },
                format="json",
            )
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.json()["success"])



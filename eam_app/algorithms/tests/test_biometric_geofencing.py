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

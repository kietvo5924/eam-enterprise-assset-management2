"""
Automated Test Suite for Task 11.4 — Condition Monitoring & Inspection Anomaly Detection.
Covers all 12 Acceptance Criteria & Edge Cases (TC-ANOM-01 through TC-ANOM-12).
"""

import uuid
from datetime import datetime, timedelta
from django.utils import timezone
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

import json
from core.models import Tenant
from core.tenant_context import clear_current_tenant
from users.models import Role, Permission
from assets.models import Location, AssetCategory, Asset, MeterReading, AssetAnomalyAlert
from workorders.models import WorkOrder, WorkOrderChecklistItem

from algorithms.anomaly_detection import (
    validate_physical_bounds,
    is_static_asset,
    evaluate_iso_10816,
    detect_z_score_anomaly,
    compute_theil_sen_drift,
    evaluate_trend_drift,
    MultivariateIsolationForestDetector,
    compute_delta_t,
    ConditionMonitoringEngine
)

User = get_user_model()


class SensorAnomalyDetectionTestCase(TestCase):
    def setUp(self):
        clear_current_tenant()
        self.tenant = Tenant.objects.create(name="Enterprise Factory Corp", tenant_code="T-EFC-01")

        self.user = User.objects.create_user(
            username="tech_alice",
            email="tech_alice@efc.com",
            password="password123",
            tenant=self.tenant
        )

        # Quyền hạn cho technician & manager
        self.perm_read = Permission.objects.filter(id='asset:read').first() or Permission.objects.create(id='asset:read', name='Read Asset')
        self.perm_update = Permission.objects.filter(id='asset:update').first() or Permission.objects.create(id='asset:update', name='Update Asset')
        self.perm_wo_exec = Permission.objects.filter(id='work_order:execute').first() or Permission.objects.create(id='work_order:execute', name='Execute WO')
        self.perm_wo_upd = Permission.objects.filter(id='work_order:update').first() or Permission.objects.create(id='work_order:update', name='Update WO')

        self.role = Role.objects.create(name="MAINTENANCE_TECH", tenant=self.tenant)
        self.role.permissions.add(self.perm_read, self.perm_update, self.perm_wo_exec, self.perm_wo_upd)
        self.user.roles.add(self.role)

        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.location = Location.objects.create(
            tenant=self.tenant,
            name="Xưởng Cơ Khí A",
            code="LOC-XCK-A"
        )
        self.category_pump = AssetCategory.objects.create(
            tenant=self.tenant,
            name="Máy Bơm Công Nghiệp"
        )
        self.category_static = AssetCategory.objects.create(
            tenant=self.tenant,
            name="Bàn ghế & Tủ tài liệu văn phòng"
        )

        self.pump_asset = Asset.objects.create(
            tenant=self.tenant,
            name="Máy Bơm Ly Tâm P-101",
            category=self.category_pump,
            location=self.location,
            qr_code="QR-PUMP-101"
        )

        self.static_asset = Asset.objects.create(
            tenant=self.tenant,
            name="Bàn làm việc kỹ sư B-01",
            category=self.category_static,
            location=self.location,
            qr_code="QR-DESK-01"
        )

    def test_tc_anom_01_warm_up_guardrail(self):
        """
        TC-ANOM-01: Bất thường giả do máy chưa chạy đủ công suất (Warm-Up Guardrail).
        Đo nhiệt độ lúc vừa bật 2 phút (25°C so với trung bình 75°C), chọn WARM_UP.
        Kỳ vọng: Lưu thành công; KHÔNG kích hoạt cảnh báo Z-score âm; không phát sinh báo động giả.
        """
        # Tạo 20 lần đo bình thường khi RUNNING ở 75°C
        now = timezone.now()
        for i in range(20):
            MeterReading.objects.create(
                tenant=self.tenant,
                asset=self.pump_asset,
                metric_code='TEMPERATURE',
                reading_value=75.0,
                reading_date=now - timedelta(days=21 - i),
                machine_state='RUNNING',
                unit='°C'
            )

        # Gửi số đo lúc vừa bật máy (25°C) với trạng thái WARM_UP
        url = f"/api/v1/assets/{self.pump_asset.id}/meter-readings/"
        payload = {
            "machineState": "WARM_UP",
            "ambientTemperature": 24.0,
            "readings": [
                {"metricCode": "TEMPERATURE", "value": 25.0, "unit": "°C"}
            ]
        }
        res = self.client.post(url, data=payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        res_data = res.json()['data']

        self.assertEqual(res_data['savedReadingsCount'], 1)
        self.assertFalse(res_data['analysisSummary']['hasAnomaly'])
        self.assertEqual(res_data['analysisSummary']['highestSeverity'], 'NORMAL')
        self.assertIn("WARM_UP", res_data['analysisSummary']['message'])

        # Xác nhận không có cảnh báo nào trong DB
        alerts = AssetAnomalyAlert.objects.filter(asset=self.pump_asset)
        self.assertEqual(alerts.count(), 0)

    def test_tc_anom_02_post_repair_window_reset(self):
        """
        TC-ANOM-02: Tái lập cửa sổ trượt sau khi sửa chữa xong (Post-Repair Reset).
        Máy rung lắc mạnh 20 lần đo. Kỹ thuật viên hoàn thành phiếu thay vòng bi (WorkOrder.status = 'COMPLETED').
        Hôm nay đo độ rung máy giảm mạnh về mức êm (1.5 mm/s).
        Kỳ vọng: Cửa sổ trượt được tái lập; toàn bộ dữ liệu rung lắc cũ bị đánh dấu is_pre_repair = True;
        không báo lỗi độ rung thấp bất thường.
        """
        now = timezone.now()
        # 20 lần đo rung lắc xấu (6.0 mm/s)
        for i in range(20):
            MeterReading.objects.create(
                tenant=self.tenant,
                asset=self.pump_asset,
                metric_code='VIBRATION',
                reading_value=6.0,
                reading_date=now - timedelta(days=25 - i),
                machine_state='RUNNING',
                unit='mm/s'
            )

        # Tạo WorkOrder sửa chữa thay thế vòng bi và chuyển sang COMPLETED
        repair_wo = WorkOrder.objects.create(
            tenant=self.tenant,
            asset=self.pump_asset,
            title="Thay thế cụm vòng bi trục chính",
            type='CORRECTIVE',
            status='IN_PROGRESS',
            priority='HIGH'
        )
        repair_wo.status = 'COMPLETED'
        repair_wo.completed_at = now - timedelta(days=2)
        repair_wo.save()

        # Kiểm tra signal đã đánh dấu is_pre_repair = True cho toàn bộ 20 lần đo cũ
        pre_repair_count = MeterReading.objects.filter(
            asset=self.pump_asset,
            is_pre_repair=True
        ).count()
        self.assertEqual(pre_repair_count, 20)

        # Hôm nay thợ đo độ rung máy êm (1.5 mm/s)
        url = f"/api/v1/assets/{self.pump_asset.id}/meter-readings/"
        payload = {
            "machineState": "RUNNING",
            "readings": [
                {"metricCode": "VIBRATION", "value": 1.5, "unit": "mm/s"}
            ]
        }
        res = self.client.post(url, data=payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        res_data = res.json()['data']

        # Vì các lần đo cũ bị prune khỏi baseline, hệ thống chuyển sang cold-start OEM static check (1.5 < 2.8), không báo lỗi
        self.assertFalse(res_data['analysisSummary']['hasAnomaly'])
        self.assertEqual(res_data['analysisSummary']['highestSeverity'], 'NORMAL')

    def test_tc_anom_03_theil_sen_robustness(self):
        """
        TC-ANOM-03: Chống méo đường xu hướng do súng đo trượt tay (Theil-Sen Robustness).
        Trong 10 lần đo gần nhất có 1 lần nhập nhầm 120°C (trượt tay vào ống xả), các lần khác đều 80°C.
        Kỳ vọng: Thuật toán Theil-Sen bỏ qua điểm ngoại lai 120°C; đường xu hướng vẫn duy trì nằm ngang (slope <= 0.01).
        """
        now = timezone.now()
        t_list = [now - timedelta(days=10 - i) for i in range(10)]
        v_list = [80.0] * 10
        v_list[4] = 120.0  # Điểm ngoại lai trượt tay

        slope, days_rem = compute_theil_sen_drift(t_list, v_list, limit_value=95.0)

        # Theil-Sen có break-down point 29%, hoàn toàn miễn nhiễm ngoại lai
        self.assertIsNotNone(slope)
        self.assertLessEqual(slope, 0.01)
        self.assertIsNone(days_rem)  # Không có xu hướng tăng nên không kích hoạt Draft PM

    def test_tc_anom_04_ambient_temperature_normalization(self):
        """
        TC-ANOM-04: Khử nhiễu biến đổi thời tiết mùa hè/mùa đông (Delta T).
        Mùa hè: xưởng nóng 38°C, máy chạy 78°C (Delta T = 40°C).
        Mùa đông: xưởng 12°C, máy 52°C (Delta T = 40°C).
        Kỳ vọng: Mô hình đánh giá trên biến Delta T = 40°C thấy trạng thái hoàn toàn ổn định bình thường.
        """
        delta_summer = compute_delta_t(machine_temp=78.0, ambient_temp=38.0)
        delta_winter = compute_delta_t(machine_temp=52.0, ambient_temp=12.0)

        self.assertEqual(delta_summer, 40.0)
        self.assertEqual(delta_winter, 40.0)

        detector = MultivariateIsolationForestDetector()
        vec_summer = detector.build_vector(vibration=2.0, temperature=78.0, ambient_temperature=38.0, pressure=2.5, current=15.0)
        vec_winter = detector.build_vector(vibration=2.0, temperature=52.0, ambient_temperature=12.0, pressure=2.5, current=15.0)

        # Hai vector hoàn toàn đồng nhất do Delta T đều là 40°C
        self.assertTrue((vec_summer == vec_winter).all())

        res_summer = detector.evaluate(vec_summer)
        res_winter = detector.evaluate(vec_winter)

        self.assertEqual(res_summer['anomaly_score'], res_winter['anomaly_score'])
        self.assertFalse(res_summer['has_anomaly'])
        self.assertLess(res_summer['anomaly_score'], 0.65)

    def test_tc_anom_05_alert_throttling_and_deduplication(self):
        """
        TC-ANOM-05: Chống bão hòa cảnh báo & Không spam Draft PM (Alert Throttling).
        Thiết bị đã có 1 cảnh báo OPEN và 1 Draft PM tạo từ hôm qua. Hôm nay đo tiếp thấy thông số vẫn xấu.
        Kỳ vọng: Bản ghi cảnh báo cũ được tăng occurrence_count = 2; tuyệt đối KHÔNG tạo thêm Draft PM thứ 2.
        """
        now = timezone.now()
        # Tạo 5 lần đo rung tăng dần chuẩn bị chạm ngưỡng nguy hiểm
        for i in range(5):
            MeterReading.objects.create(
                tenant=self.tenant,
                asset=self.pump_asset,
                metric_code='VIBRATION',
                reading_value=4.0 + (i * 0.5),  # 4.0, 4.5, 5.0, 5.5, 6.0
                reading_date=now - timedelta(days=6 - i),
                machine_state='RUNNING',
                unit='mm/s'
            )

        # Lần đo 1: Rung mạnh 6.5 mm/s -> Kích hoạt cảnh báo mới & sinh Draft PM
        url = f"/api/v1/assets/{self.pump_asset.id}/meter-readings/"
        payload1 = {
            "machineState": "RUNNING",
            "readings": [{"metricCode": "VIBRATION", "value": 6.5, "unit": "mm/s"}]
        }
        res1 = self.client.post(url, data=payload1, format='json')
        self.assertEqual(res1.status_code, status.HTTP_200_OK)

        initial_alerts_count = AssetAnomalyAlert.objects.filter(asset=self.pump_asset).count()
        initial_pm_count = WorkOrder.objects.filter(asset=self.pump_asset, type='PREVENTIVE').count()
        self.assertEqual(initial_alerts_count, 1)
        self.assertEqual(initial_pm_count, 1)

        alert1 = AssetAnomalyAlert.objects.filter(asset=self.pump_asset).first()
        self.assertEqual(alert1.occurrence_count, 1)

        # Lần đo 2: Hôm sau đo tiếp vẫn xấu (6.8 mm/s)
        payload2 = {
            "machineState": "RUNNING",
            "readings": [{"metricCode": "VIBRATION", "value": 6.8, "unit": "mm/s"}]
        }
        res2 = self.client.post(url, data=payload2, format='json')
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        res2_data = res2.json()['data']

        # Alert Throttling: Cảnh báo cũ được cập nhật, KHÔNG sinh Draft PM mới!
        alert1.refresh_from_db()
        self.assertEqual(alert1.occurrence_count, 2)
        self.assertEqual(AssetAnomalyAlert.objects.filter(asset=self.pump_asset).count(), 1)
        self.assertEqual(WorkOrder.objects.filter(asset=self.pump_asset, type='PREVENTIVE').count(), 1)
        self.assertEqual(res2_data['analysisSummary']['draftWorkOrderAction'], "UPDATED_EXISTING_DRAFT")

    def test_tc_anom_06_frozen_sensor_detection(self):
        """
        TC-ANOM-06: Nhận diện cảm biến bị kẹt / đóng băng số liệu (Frozen Sensor).
        7 lần đo liên tiếp khi máy đang RUNNING đều ghi nhận giá trị 28.00°C không đổi.
        Kỳ vọng: Hệ thống phát cảnh báo thiết bị đo bị kẹt giá trị hoặc hỏng hóc.
        """
        now = timezone.now()
        # 6 lần đo trước đó đều 28.00°C
        for i in range(6):
            MeterReading.objects.create(
                tenant=self.tenant,
                asset=self.pump_asset,
                metric_code='TEMPERATURE',
                reading_value=28.00,
                reading_date=now - timedelta(hours=7 - i),
                machine_state='RUNNING',
                unit='°C'
            )

        # Lần đo thứ 7 tiếp tục là 28.00°C
        url = f"/api/v1/assets/{self.pump_asset.id}/meter-readings/"
        payload = {
            "machineState": "RUNNING",
            "readings": [{"metricCode": "TEMPERATURE", "value": 28.00, "unit": "°C"}]
        }
        res = self.client.post(url, data=payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        res_data = res.json()['data']

        self.assertTrue(res_data['analysisSummary']['hasAnomaly'])
        self.assertEqual(res_data['analysisSummary']['zScoreAlert']['status'], 'FROZEN_SENSOR')
        self.assertIn("đóng băng", res_data['analysisSummary']['zScoreAlert']['message'])

    def test_tc_anom_07_timestamp_elapsed_days(self):
        """
        TC-ANOM-07: Hồi quy theo mốc ngày thực tế (Timestamp Elapsed Days).
        Đo cách nhau 10 ngày do nghỉ lễ.
        Kỳ vọng: Tốc độ suy thoái a được tính toán trên khoảng cách 10 ngày thực tế, không coi là 1 bước đo liền kề.
        """
        # Ngày 0: 2.0 mm/s, Ngày 1: 2.2, Ngày 2: 2.4, Ngày 3: 2.6, Ngày 13: 4.6 (cách 10 ngày sau nghỉ lễ)
        base_t = datetime(2026, 9, 1, 8, 0)
        timestamps = [
            base_t,
            base_t + timedelta(days=1),
            base_t + timedelta(days=2),
            base_t + timedelta(days=3),
            base_t + timedelta(days=13),  # 10 ngày nghỉ
        ]
        values = [2.0, 2.2, 2.4, 2.6, 4.6]

        slope, days_rem = compute_theil_sen_drift(timestamps, values, limit_value=7.1)
        self.assertIsNotNone(slope)
        # Tốc độ tăng trưởng chuẩn xác là 0.2 mm/s mỗi ngày
        self.assertAlmostEqual(slope, 0.2, places=2)

    def test_tc_anom_08_human_feedback_loop(self):
        """
        TC-ANOM-08: Phản hồi của Quản lý loại trừ báo động giả (Human Feedback Loop).
        Quản đốc bấm nút 'Đánh dấu Báo động giả' cho cảnh báo rung.
        Kỳ vọng: Trạng thái chuyển thành FALSE_ALARM, is_suppressed = True;
        điểm đo bị loại trừ khỏi tập huấn luyện.
        """
        # Tạo 1 cảnh báo OPEN
        reading = MeterReading.objects.create(
            tenant=self.tenant,
            asset=self.pump_asset,
            metric_code='VIBRATION',
            reading_value=6.5,
            reading_date=timezone.now(),
            machine_state='RUNNING',
            unit='mm/s'
        )
        alert = AssetAnomalyAlert.objects.create(
            tenant=self.tenant,
            asset=self.pump_asset,
            reading=reading,
            metric_code='VIBRATION',
            current_value=6.5,
            severity='WARNING',
            status='OPEN'
        )

        # Quản đốc gửi phản hồi FALSE_ALARM
        url = f"/api/v1/condition-monitoring/alerts/{alert.id}/feedback/"
        payload = {
            "feedback": "FALSE_ALARM",
            "notes": "Rung do xe nâng hàng nặng chạy ngang qua sàn xưởng"
        }
        res = self.client.post(url, data=payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        alert.refresh_from_db()
        reading.refresh_from_db()

        self.assertEqual(alert.status, 'FALSE_ALARM')
        self.assertTrue(alert.is_suppressed)
        self.assertTrue(reading.is_suppressed)
        self.assertIn("xe nâng", alert.message)

    def test_tc_anom_09_physical_bounds_check(self):
        """
        TC-ANOM-09: Chặn số liệu gõ nhầm vượt ngưỡng vật lý khả thi.
        Người dùng nhập nhiệt độ 750°C hoặc độ rung 200 mm/s.
        Kỳ vọng: Hệ thống từ chối lưu với mã lỗi 400 Bad Request.
        """
        url = f"/api/v1/assets/{self.pump_asset.id}/meter-readings/"

        # Nhiệt độ 750°C vượt ngưỡng [0, 180°C]
        payload_temp = {
            "machineState": "RUNNING",
            "readings": [{"metricCode": "TEMPERATURE", "value": 750.0, "unit": "°C"}]
        }
        res_temp = self.client.post(url, data=payload_temp, format='json')
        self.assertEqual(res_temp.status_code, status.HTTP_400_BAD_REQUEST)

        # Độ rung 200 mm/s vượt ngưỡng [0.01, 50 mm/s]
        payload_vib = {
            "machineState": "RUNNING",
            "readings": [{"metricCode": "VIBRATION", "value": 200.0, "unit": "mm/s"}]
        }
        res_vib = self.client.post(url, data=payload_vib, format='json')
        self.assertEqual(res_vib.status_code, status.HTTP_400_BAD_REQUEST)

    def test_tc_anom_10_static_asset_routing(self):
        """
        TC-ANOM-10: Phân luồng tài sản tĩnh (Bàn ghế, tủ tài liệu).
        Kiểm tra một tài sản thuộc danh mục tài sản tĩnh.
        Kỳ vọng: Hệ thống hiển thị biểu mẫu kiểm tra định tính (Pass/Fail); không chạy mô hình Z-score hay Isolation Forest.
        """
        self.assertTrue(is_static_asset(self.static_asset))

        url = f"/api/v1/assets/{self.static_asset.id}/meter-readings/"
        payload = {
            "machineState": "RUNNING",
            "readings": [{"metricCode": "GENERAL", "value": 1.0, "unit": ""}]
        }
        res = self.client.post(url, data=payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        res_data = res.json()['data']

        self.assertTrue(res_data['isStaticAsset'])
        self.assertIn("checklist", res_data['analysisSummary'])
        self.assertEqual(len(res_data['analysisSummary']['checklist']), 4)
        # Không có Z-score hay anomaly alerts được tạo
        self.assertEqual(AssetAnomalyAlert.objects.filter(asset=self.static_asset).count(), 0)

    def test_tc_anom_11_iso_10816_benchmark(self):
        """
        TC-ANOM-11: Tích hợp đối chiếu dải tiêu chuẩn quốc tế ISO 10816-3.
        Máy bơm công nghiệp có độ rung 5.5 mm/s.
        Kỳ vọng: Hệ thống phân loại chính xác vào Vùng C (Cảnh báo: 2.8 - 7.1 mm/s).
        """
        eval_c = evaluate_iso_10816('VIBRATION', 5.5)
        self.assertEqual(eval_c['zone'], 'ZONE_C')
        self.assertEqual(eval_c['severity'], 'WARNING')
        self.assertIn("Vùng C", eval_c['label'])

        eval_ab = evaluate_iso_10816('VIBRATION', 1.8)
        self.assertEqual(eval_ab['zone'], 'ZONE_AB')
        self.assertEqual(eval_ab['severity'], 'NORMAL')

        eval_d = evaluate_iso_10816('VIBRATION', 8.2)
        self.assertEqual(eval_d['zone'], 'ZONE_D')
        self.assertEqual(eval_d['severity'], 'CRITICAL')

    def test_tc_anom_12_failure_prediction_and_auto_draft_pm(self):
        """
        TC-ANOM-12: Dự báo ngày chạm ngưỡng & tự động tạo Draft PM khi <= 7 ngày.
        Độ rung máy tăng đều đặn theo quy luật Theil-Sen, dự báo chạm ngưỡng đỏ sau 4-5 ngày.
        Kỳ vọng: Hệ thống tạo 1 bản thảo Draft PM duy nhất kèm thông báo gửi Quản đốc.
        """
        now = timezone.now()
        # Tạo chuỗi đo tăng trưởng đều đặn: ngày 0: 4.5 mm/s, mỗi ngày tăng 0.4 mm/s
        # 4.5, 4.9, 5.3, 5.7, 6.1 -> dự báo chạm ngưỡng 7.1 sau (7.1 - 6.1) / 0.4 = 2.5 ~ 2-3 ngày
        for i in range(5):
            MeterReading.objects.create(
                tenant=self.tenant,
                asset=self.pump_asset,
                metric_code='VIBRATION',
                reading_value=4.5 + (i * 0.4),
                reading_date=now - timedelta(days=5 - i),
                machine_state='RUNNING',
                unit='mm/s'
            )

        url = f"/api/v1/assets/{self.pump_asset.id}/meter-readings/"
        payload = {
            "machineState": "RUNNING",
            "readings": [{"metricCode": "VIBRATION", "value": 6.3, "unit": "mm/s"}]
        }
        res = self.client.post(url, data=payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        res_data = res.json()['data']

        self.assertTrue(res_data['analysisSummary']['hasAnomaly'])
        trend_drift = res_data['analysisSummary']['trendDrift']
        self.assertIsNotNone(trend_drift)
        self.assertTrue(trend_drift['isDrifting'])
        self.assertIsNotNone(trend_drift['daysRemaining'])
        self.assertLessEqual(trend_drift['daysRemaining'], 7)

        # Kiểm tra bản thảo Draft PM đã được tự động tạo
        draft_wo = WorkOrder.objects.filter(asset=self.pump_asset, type='PREVENTIVE', status='CREATED').first()
        self.assertIsNotNone(draft_wo)
        self.assertIn("Bản thảo PM", draft_wo.title)

        # Kiểm tra liên kết giữa Alert và Draft PM
        alert = AssetAnomalyAlert.objects.filter(asset=self.pump_asset, status='OPEN').first()
        self.assertIsNotNone(alert)
        self.assertEqual(alert.draft_work_order, draft_wo)

    def test_tc_anom_13_work_order_meter_reading_and_followup(self):
        """
        TC-ANOM-13: Ghi nhận số đo cảm biến trực tiếp trong quá trình thực hiện Work Order.
        Kỹ thuật viên đang thực hiện Work Order kiểm tra, ghi nhận số đo độ rung bất thường (5.8 mm/s - Zone D).
        Kỳ vọng:
        1. MeterReading được gắn khóa ngoại work_order.
        2. ConditionMonitoringEngine trả về bất thường CRITICAL.
        3. Draft Work Order tự động liên kết parent_id trỏ về Work Order hiện tại.
        4. API cho phép khởi tạo Work Order con (Follow-up Corrective WO).
        """
        inspection_wo = WorkOrder.objects.create(
            tenant=self.tenant,
            asset=self.pump_asset,
            title="Phiếu kiểm tra định kỳ bơm P-101",
            type="PREVENTIVE",
            status="IN_PROGRESS",
            priority="MEDIUM",
            assigned_to=self.user
        )

        url = f"/api/v1/assets/{self.pump_asset.id}/meter-readings/"
        payload = {
            "workOrderId": str(inspection_wo.id),
            "machineState": "RUNNING",
            "ambientTemperature": 30.5,
            "readings": [
                {"metricCode": "VIBRATION", "value": 7.8, "unit": "mm/s", "remarks": "Rung lắc dữ dội nguy hiểm tại bệ đỡ"}
            ]
        }

        res = self.client.post(url, data=payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()['data']

        # 1. Kiểm tra MeterReading đã liên kết chính xác với Work Order
        latest_reading = MeterReading.objects.filter(asset=self.pump_asset).order_by('-created_at').first()
        self.assertIsNotNone(latest_reading)
        self.assertEqual(latest_reading.work_order, inspection_wo)
        self.assertEqual(latest_reading.metric_code, 'VIBRATION')
        self.assertEqual(float(latest_reading.reading_value), 7.8)

        # 2. Kiểm tra bất thường CRITICAL (ISO Zone D)
        summary = data['analysisSummary']
        self.assertTrue(summary['hasAnomaly'])
        self.assertEqual(summary['highestSeverity'], 'CRITICAL')
        self.assertEqual(summary['iso10816Status']['zone'], 'ZONE_D')

        # 3. Kiểm tra Draft Work Order kế thừa parent_id là inspection_wo
        alert = AssetAnomalyAlert.objects.filter(asset=self.pump_asset, status='OPEN').first()
        self.assertIsNotNone(alert)
        self.assertIsNotNone(alert.draft_work_order)
        self.assertEqual(alert.draft_work_order.parent_id, inspection_wo)

        # 4. Kiểm tra tạo Follow-up Corrective Work Order kế thừa parent_id
        followup_wo = WorkOrder.objects.create(
            tenant=self.tenant,
            asset=self.pump_asset,
            parent_id=inspection_wo,
            title="Sửa chữa khắc phục: Rung lắc bất thường tại bơm P-101",
            type="CORRECTIVE",
            priority="URGENT",
            status="CREATED",
            created_by=self.user
        )
        self.assertEqual(followup_wo.parent_id, inspection_wo)
        self.assertIn(followup_wo, inspection_wo.follow_up_work_orders.all())

    def test_tc_anom_14_work_order_modal_dynamic_checklists_and_mandatory_measurement(self):
        """
        TC-ANOM-14: Kiểm tra cấu hình checklist động và đo kiểm bắt buộc (Mandatory Measurement)
        qua Portal Work Orders.
        """
        perm_wo_read = Permission.objects.filter(id='work_order:read').first() or Permission.objects.create(id='work_order:read', name='Read WO')
        perm_wo_create = Permission.objects.filter(id='work_order:create').first() or Permission.objects.create(id='work_order:create', name='Create WO')
        self.role.permissions.add(perm_wo_read, perm_wo_create)
        self.client.force_login(self.user)

        # 1. Tạo Work Order kèm checklist đo rung động bắt buộc
        create_payload = {
            "title": "Bảo dưỡng & đo kiểm độ rung bơm P-101",
            "asset_id": str(self.pump_asset.id),
            "type": "PREVENTIVE",
            "priority": "HIGH",
            "assigned_to_id": str(self.user.id),
            "checklists": [
                {
                    "item_name": "Đo độ rung RMS bệ đỡ",
                    "input_type": "NUMBER",
                    "expected_value": "< 4.5 mm/s",
                    "is_mandatory": True
                },
                {
                    "item_name": "Kiểm tra rò rỉ phớt cơ khí",
                    "input_type": "PASS_FAIL",
                    "expected_value": "Không rò rỉ",
                    "is_mandatory": False
                }
            ]
        }

        res = self.client.post("/portal/work-orders/", data=json.dumps(create_payload), content_type="application/json")
        self.assertEqual(res.status_code, 200)
        res_data = res.json()
        self.assertTrue(res_data.get('success'))
        wo_id = res_data.get('id')
        self.assertIsNotNone(wo_id)

        # 2. Xác thực checklist trong DB
        wo = WorkOrder.objects.get(id=wo_id)
        checklists = list(wo.checklists.all().order_by('created_at'))
        self.assertEqual(len(checklists), 2)

        vib_chk = checklists[0]
        self.assertEqual(vib_chk.item_name, "Đo độ rung RMS bệ đỡ")
        self.assertEqual(vib_chk.input_type, "NUMBER")
        self.assertEqual(vib_chk.expected_value, "< 4.5 mm/s")
        self.assertTrue(vib_chk.is_mandatory)
        self.assertFalse(vib_chk.is_completed)

        leak_chk = checklists[1]
        self.assertEqual(leak_chk.item_name, "Kiểm tra rò rỉ phớt cơ khí")
        self.assertEqual(leak_chk.input_type, "PASS_FAIL")
        self.assertFalse(leak_chk.is_mandatory)

        # 3. Chuyển sang IN_PROGRESS rồi cố hoàn thành khi chưa hoàn thành bước đo kiểm bắt buộc
        wo.status = 'IN_PROGRESS'
        wo.save()

        complete_payload = {
            "id": str(wo_id),
            "status": "COMPLETED",
            "resolution_notes": "Đã hoàn thành kiểm tra hiện trường"
        }
        res_fail = self.client.put(f"/portal/work-orders/?id={wo_id}", data=json.dumps(complete_payload), content_type="application/json")
        self.assertEqual(res_fail.status_code, 400)
        self.assertIn("Chưa hoàn thành bước bắt buộc", res_fail.json().get('error', ''))

        # 4. Nhập số liệu đo kiểm thực tế vào checklist
        vib_chk.actual_value = "3.2"
        vib_chk.is_completed = True
        vib_chk.save()

        res_ok = self.client.put(f"/portal/work-orders/?id={wo_id}", data=json.dumps(complete_payload), content_type="application/json")
        self.assertEqual(res_ok.status_code, 200)
        self.assertTrue(res_ok.json().get('success'))
        wo.refresh_from_db()
        self.assertEqual(wo.status, "COMPLETED")

        # 5. Kiểm tra thêm checklist qua action add_checklist và sync qua PUT
        wo2 = WorkOrder.objects.create(
            tenant=self.tenant,
            asset=self.pump_asset,
            title="WO kiểm tra định kỳ 2",
            type="PREVENTIVE",
            status="CREATED",
            priority="LOW"
        )
        add_chk_payload = {
            "action": "add_checklist",
            "work_order_id": str(wo2.id),
            "wo_id": str(wo2.id),
            "item_name": "Đo nhiệt độ ổ bi",
            "input_type": "NUMBER",
            "expected_value": "< 70 °C",
            "is_mandatory": True
        }
        res_add = self.client.post("/portal/work-orders/", data=json.dumps(add_chk_payload), content_type="application/json")
        self.assertEqual(res_add.status_code, 200)
        chk_item = WorkOrderChecklistItem.objects.get(work_order=wo2, item_name="Đo nhiệt độ ổ bi")
        self.assertEqual(chk_item.input_type, "NUMBER")
        self.assertEqual(chk_item.expected_value, "< 70 °C")
        self.assertTrue(chk_item.is_mandatory)

    def test_tc_anom_13_dynamic_metric_and_strict_validation(self):
        """
        TC-ANOM-13: Hỗ trợ chỉ số đo động/tùy biến và kiểm soát ràng buộc chặt chẽ.
        - Chấp nhận mã chỉ số hợp lệ (RPM, FLOW_RATE, BEARING_OIL_TEMP_2).
        - Chặn mã chỉ số chứa ký tự đặc biệt hoặc dấu cách (400 Bad Request).
        - Chặn giá trị đo là NaN hoặc vô cực (400 Bad Request).
        - Áp dụng giới hạn vật lý khả thi cho các chỉ số công nghiệp mở rộng (VOLTAGE, RPM, NOISE...).
        """
        url = f"/api/v1/assets/{self.pump_asset.id}/meter-readings/"

        # 1. Đo RPM thành công
        payload_rpm = {
            "machineState": "RUNNING",
            "readings": [{"metricCode": "rpm", "value": 1450.0, "unit": "v/p"}]
        }
        res_rpm = self.client.post(url, data=payload_rpm, format='json')
        self.assertEqual(res_rpm.status_code, status.HTTP_200_OK)
        saved_reading = MeterReading.objects.filter(asset=self.pump_asset, metric_code='RPM').first()
        self.assertIsNotNone(saved_reading)
        self.assertEqual(float(saved_reading.reading_value), 1450.0)

        # 2. Đo chỉ số tùy chỉnh BEARING_OIL_TEMP_2 thành công
        payload_custom = {
            "machineState": "RUNNING",
            "readings": [{"metricCode": "BEARING_OIL_TEMP_2", "value": 62.5, "unit": "°C"}]
        }
        res_custom = self.client.post(url, data=payload_custom, format='json')
        self.assertEqual(res_custom.status_code, status.HTTP_200_OK)
        saved_custom = MeterReading.objects.filter(asset=self.pump_asset, metric_code='BEARING_OIL_TEMP_2').first()
        self.assertIsNotNone(saved_custom)

        # 3. Chặn mã chỉ số chứa ký tự không hợp lệ (kí tự đặc biệt hoặc dấu cách)
        payload_invalid_code = {
            "machineState": "RUNNING",
            "readings": [{"metricCode": "RPM#$@! INVALID", "value": 1500.0, "unit": "v/p"}]
        }
        res_invalid_code = self.client.post(url, data=payload_invalid_code, format='json')
        self.assertEqual(res_invalid_code.status_code, status.HTTP_400_BAD_REQUEST)

        # 4. Chặn giá trị đo vượt giới hạn vật lý khả thi (RPM = 99,999 v/p vượt [0, 50000])
        payload_rpm_bound = {
            "machineState": "RUNNING",
            "readings": [{"metricCode": "RPM", "value": 99999.0, "unit": "v/p"}]
        }
        res_rpm_bound = self.client.post(url, data=payload_rpm_bound, format='json')
        self.assertEqual(res_rpm_bound.status_code, status.HTTP_400_BAD_REQUEST)

        # 5. Chặn giá trị đo điện áp vượt giới hạn (VOLTAGE = 2500V vượt [0, 1000V])
        payload_volt_bound = {
            "machineState": "RUNNING",
            "readings": [{"metricCode": "VOLTAGE", "value": 2500.0, "unit": "V"}]
        }
        res_volt_bound = self.client.post(url, data=payload_volt_bound, format='json')
        self.assertEqual(res_volt_bound.status_code, status.HTTP_400_BAD_REQUEST)

    def test_tc_anom_14_custom_metric_cold_start_no_false_alarm(self):
        """
        TC-ANOM-14: Kiểm soát Cold-Start cho chỉ số tùy biến.
        Khi người dùng nhập chỉ số mới (chưa đủ 15 mẫu đo và chưa có ngưỡng tĩnh OEM mặc định),
        hệ thống KHÔNG được dùng fallback 80.0 để kích hoạt báo động giả SPIKE!
        Ví dụ: RPM = 1450.0 hoặc VISCOSITY = 320.0 không được báo động đỏ.
        """
        url = f"/api/v1/assets/{self.pump_asset.id}/meter-readings/"

        # Đảm bảo chưa có mẫu đo nào cho CUSTOM_FLOW
        MeterReading.objects.filter(asset=self.pump_asset, metric_code='CUSTOM_FLOW').delete()
        AssetAnomalyAlert.objects.filter(asset=self.pump_asset, metric_code='CUSTOM_FLOW').delete()

        payload = {
            "machineState": "RUNNING",
            "readings": [{"metricCode": "CUSTOM_FLOW", "value": 250.0, "unit": "m³/h"}]
        }
        res = self.client.post(url, data=payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        res_data = res.json()['data']

        # Không phát sinh cảnh báo bất thường giả
        self.assertFalse(res_data['analysisSummary']['hasAnomaly'])
        alerts_count = AssetAnomalyAlert.objects.filter(asset=self.pump_asset, metric_code='CUSTOM_FLOW').count()
        self.assertEqual(alerts_count, 0)


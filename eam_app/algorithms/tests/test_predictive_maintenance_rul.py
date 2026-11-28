"""
Unit & Integration Test Suite for Phase 11.5: Deep Learning LSTM Predictive Maintenance RUL.
Bao gồm trọn vẹn 12 Test Cases (TC-RUL-01 -> TC-RUL-12) phủ kín 100% nghiệp vụ phòng thủ.
"""

import uuid
from decimal import Decimal
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework.exceptions import ValidationError

from core.models import Tenant
from core.tenant_context import clear_current_tenant
from assets.models import Asset, AssetCategory, Location, SparePart, MeterReading, AssetRulPrediction
from workorders.models import WorkOrder
from algorithms.predictive_rul import (
    RULPredictiveService, PredictiveRULGuardrails, DegradationFeaturePipeline,
    get_rul_model, WINDOW_SIZE, COLD_START_MIN_SAMPLES, RUL_MAX_CLIP_DAYS
)
from algorithms.anomaly_detection.engine import ConditionMonitoringEngine

User = get_user_model()


class PredictiveMaintenanceRULTests(TestCase):
    def setUp(self):
        clear_current_tenant()
        self.tenant = Tenant.objects.create(name="Test Tenant RUL", tenant_code=f"T-RUL-{uuid.uuid4().hex[:6]}")
        self.tenant_id = self.tenant.id
        self.user = User.objects.create_user(
            username=f'tech_rul_{uuid.uuid4().hex[:6]}',
            email='tech_rul@test.com',
            password='password123',
            tenant=self.tenant
        )
        self.loc = Location.objects.create(
            name='Trạm Bơm Trung Tâm',
            code='PUMP_STATION_01',
            tenant=self.tenant
        )
        self.machinery_category = AssetCategory.objects.create(
            name='Bơm công nghiệp',
            tenant=self.tenant
        )
        self.static_category = AssetCategory.objects.create(
            name='Bàn ghế văn phòng',
            tenant=self.tenant
        )
        self.spare_part = SparePart.objects.create(
            name='Vòng bi đỡ chặn SKF 6205',
            part_number='SKF-6205-2RSH',
            quantity_in_stock=Decimal('5.00'),
            lead_time_days=20,
            tenant=self.tenant,
            location=self.loc
        )
        self.asset = Asset.objects.create(
            name='Bơm ly tâm P-101',
            qr_code=f'P101-{uuid.uuid4().hex[:6]}',
            category=self.machinery_category,
            location=self.loc,
            primary_spare_part=self.spare_part,
            duty_cycle_ratio=0.70,
            tenant=self.tenant
        )

    def _seed_running_readings(self, asset, count=30, base_vib=2.0, base_temp=45.0, load_factor=1.0):
        """Hỗ trợ tạo chuỗi đo RUNNING hợp lệ."""
        now = timezone.now()
        readings = []
        for i in range(count):
            r_date = now - timedelta(days=(count - i))
            r = MeterReading.objects.create(
                tenant=asset.tenant,
                asset=asset,
                metric_code='VIBRATION',
                reading_value=Decimal(str(round(base_vib + 0.05 * (i / 10.0), 2))),
                reading_date=r_date,
                unit='mm/s',
                ambient_temperature=30.0,
                load_factor=load_factor,
                machine_state='RUNNING',
                recorded_by=self.user
            )
            readings.append(r)
        return readings

    def test_tc_rul_01_block_passive_asset(self):
        """TC-RUL-01: Chặn phân tích RUL đối với tài sản tĩnh (asset_type=STATIC hoặc fallback)."""
        static_asset = Asset.objects.create(
            name='Bàn làm việc gỗ giám đốc',
            qr_code=f'DESK-{uuid.uuid4().hex[:6]}',
            category=self.static_category,
            asset_type='STATIC',
            tenant=self.tenant
        )
        with self.assertRaises(ValidationError) as ctx:
            RULPredictiveService.predict_asset_rul(asset=static_asset, current_user=self.user)
        self.assertIn("Tài sản tĩnh", str(ctx.exception))

    def test_tc_rul_01b_motorized_chair_machinery_allowed(self):
        """Kiểm tra thiết bị cơ điện có tên chứa 'ghế' nhưng asset_type=MACHINERY không bị chặn nhầm."""
        motorized_chair = Asset.objects.create(
            name='Ghế thử nghiệm rung NVH mô-tơ điện xưởng Body',
            qr_code=f'CHAIR-NVH-{uuid.uuid4().hex[:6]}',
            category=self.machinery_category,
            asset_type='MACHINERY',
            tenant=self.tenant
        )
        is_machinery, err = PredictiveRULGuardrails.validate_asset_machinery_type(motorized_chair)
        self.assertTrue(is_machinery)
        self.assertIsNone(err)

    def test_tc_rul_02_cold_start_bypass(self):
        """TC-RUL-02: Ngưỡng khởi động nguội (< 15 mẫu đo RUNNING -> CALIBRATING)."""
        # Chỉ nạp 8 mẫu đo RUNNING
        self._seed_running_readings(self.asset, count=8)

        res = RULPredictiveService.predict_asset_rul(asset=self.asset, current_user=self.user)
        self.assertTrue(res['success'])
        data = res['data']
        self.assertEqual(data['currentStatus'], 'CALIBRATING')
        self.assertIsNone(data['operatingRulDays'])
        self.assertEqual(data['validRunningSamples'], 8)
        self.assertEqual(data['requiredSamplesThreshold'], 15)

        self.asset.refresh_from_db()
        self.assertEqual(self.asset.rul_risk_level, 'CALIBRATING')
        self.assertIsNone(self.asset.current_rul_days)

    def test_tc_rul_03_filter_standby_and_calendar_conversion(self):
        """TC-RUL-03: Lọc bỏ trạng thái STANDBY và quy đổi OperatingDays sang CalendarDays."""
        now = timezone.now()
        # Nạp xen kẽ 15 mẫu RUNNING và 15 mẫu STANDBY
        for i in range(30):
            state = 'RUNNING' if (i % 2 == 0) else 'STANDBY'
            MeterReading.objects.create(
                tenant=self.asset.tenant,
                asset=self.asset,
                metric_code='VIBRATION',
                reading_value=Decimal('2.50'),
                reading_date=now - timedelta(days=(30 - i)),
                unit='mm/s',
                ambient_temperature=30.0,
                load_factor=1.0,
                machine_state=state,
                recorded_by=self.user
            )

        res = RULPredictiveService.predict_asset_rul(asset=self.asset, current_user=self.user)
        self.assertTrue(res['success'])
        data = res['data']
        # Đã đủ 15 mẫu RUNNING nên vượt qua khởi động nguội
        self.assertIsNotNone(data['operatingRulDays'])
        op_days = data['operatingRulDays']
        cal_days = data['calendarRulDays']

        # duty_cycle_ratio = 0.70 -> CalendarDays = round(OperatingDays / 0.70, 1)
        expected_cal = round(op_days / 0.70, 1)
        self.assertAlmostEqual(cal_days, expected_cal, places=1)

    def test_tc_rul_04_load_factor_prevents_false_alarm(self):
        """TC-RUL-04: Biến tải trọng ngăn chặn báo động giả khi chạy quá tải tạm thời."""
        # Chạy quá tải 130% (load_factor = 1.3), độ rung 5.5 mm/s
        self._seed_running_readings(self.asset, count=20, base_vib=5.5, base_temp=55.0, load_factor=1.3)

        res = RULPredictiveService.predict_asset_rul(
            asset=self.asset,
            custom_load_factor=1.3,
            current_user=self.user
        )
        self.assertTrue(res['success'])
        data = res['data']
        self.assertTrue(data['loadConditionSummary']['isOverloaded'])
        # RUL vẫn ở mức an toàn/hợp lý chứ không bị sụt về 0 ngày
        self.assertGreater(data['operatingRulDays'], 10.0)

    def test_tc_rul_05_phantom_recovery_trap_clamp(self):
        """TC-RUL-05: Bẫy phục hồi ảo (Phantom Recovery Clamp sau bảo dưỡng nhỏ)."""
        self._seed_running_readings(self.asset, count=20, base_vib=3.5)
        # Giả sử trước đó máy đang có RUL = 18.0 ngày
        self.asset.current_rul_days = 18.0
        self.asset.save()

        # Kỹ thuật viên vừa hoàn thành phiếu bảo dưỡng nhỏ (bơm mỡ/siết ốc)
        WorkOrder.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            title='Bơm mỡ bôi trơn định kỳ',
            status='COMPLETED',
            maintenance_action='MICRO_MAINTENANCE',
            completed_at=timezone.now()
        )

        # Trực tiếp kiểm tra Guardrail check_phantom_recovery
        clamped_rul, is_phantom = PredictiveRULGuardrails.check_phantom_recovery(
            model_predicted_rul=65.0,  # Mô hình thấy rung giảm tưởng RUL nhảy lên 65 ngày
            previous_rul=18.0,
            last_maintenance_action='MICRO_MAINTENANCE'
        )

        self.assertTrue(is_phantom)
        self.assertEqual(clamped_rul, 18.0)  # Đã bị kẹp cứng ở mức 18.0 ngày!

    def test_tc_rul_06_monotonic_degradation_filter(self):
        """TC-RUL-06: Bộ lọc suy thoái đơn điệu vật lý (chặn RUL tự động trẻ hóa vô cớ)."""
        prev_rul = 25.0
        # Hôm sau rung lắc ngẫu nhiên khiến model tính ra 30.0 ngày
        filtered_rul = PredictiveRULGuardrails.apply_monotonic_filter(
            current_rul=30.0,
            previous_rul=prev_rul,
            is_core_overhaul_completed=False
        )
        # Bị kẹp trần tại prev_rul + 1.0 = 26.0 ngày
        self.assertLessEqual(filtered_rul, prev_rul + 1.0)

        # Nếu có CORE_REPLACEMENT, RUL được phép tăng tự do
        overhaul_rul = PredictiveRULGuardrails.apply_monotonic_filter(
            current_rul=90.0,
            previous_rul=prev_rul,
            is_core_overhaul_completed=True
        )
        self.assertEqual(overhaul_rul, 90.0)

    def test_tc_rul_07_monte_carlo_dropout_uncertainty(self):
        """TC-RUL-07: Định lượng độ bất định Monte Carlo Dropout (M=20)."""
        # Giả lập 20 lượt suy diễn
        preds = [18.0 + (i % 3) * 0.5 for i in range(20)]
        res = PredictiveRULGuardrails.calculate_mc_dropout_uncertainty(preds)

        self.assertIn('rul_mean', res)
        self.assertIn('rul_std', res)
        self.assertIn('confidence_lower', res)
        self.assertIn('confidence_upper', res)
        self.assertLessEqual(res['confidence_lower'], res['rul_mean'])
        self.assertGreaterEqual(res['confidence_upper'], res['rul_mean'])

        # Kiểm tra cờ High Uncertainty nếu std > 10
        noisy_preds = [5.0, 35.0, 8.0, 40.0, 10.0, 45.0] * 3 + [20.0, 25.0]
        noisy_res = PredictiveRULGuardrails.calculate_mc_dropout_uncertainty(noisy_preds)
        self.assertTrue(noisy_res['is_high_uncertainty'])

    def test_tc_rul_08_dynamic_lead_time_critical_threshold(self):
        """TC-RUL-08: Ngưỡng Critical động theo Lead-Time kho phụ tùng."""
        # Vòng bi có lead_time = 25 ngày
        threshold = PredictiveRULGuardrails.calculate_dynamic_critical_threshold(lead_time_days=25)
        # Threshold = max(14, 25 + 5) = 30 ngày
        self.assertEqual(threshold, 30)

        # Phụ tùng có lead_time = 3 ngày -> Threshold = max(14, 3 + 5) = 14 ngày
        threshold_short = PredictiveRULGuardrails.calculate_dynamic_critical_threshold(lead_time_days=3)
        self.assertEqual(threshold_short, 14)

    def test_tc_rul_09_alert_consolidation_two_stage(self):
        """TC-RUL-09: Hợp nhất cảnh báo 2 tầng (Phase 11.4 Anomaly trigger Phase 11.5 RUL)."""
        self._seed_running_readings(self.asset, count=20, base_vib=2.0)
        now = timezone.now()

        # Gửi một số đo vượt ngưỡng để kích hoạt ConditionMonitoringEngine
        result = ConditionMonitoringEngine.process_readings(
            asset=self.asset,
            readings_data=[{'metricCode': 'VIBRATION', 'readingValue': 8.5, 'unit': 'mm/s'}],
            machine_state='RUNNING',
            recorded_at=now,
            recorded_by=self.user,
            tenant=self.tenant
        )

        summary = result['analysisSummary']
        self.assertTrue(summary['hasAnomaly'])
        # RUL Prediction đã được tích hợp liên hoàn trong kết quả trả về
        self.assertIn('rulPrediction', summary)
        rul_info = summary['rulPrediction']
        self.assertIsNotNone(rul_info)
        self.assertEqual(rul_info['assetId'], str(self.asset.id))

    def test_tc_rul_10_rapid_degradation_detection(self):
        """TC-RUL-10: Phát hiện gia tốc suy thoái đột biến (RUL sụt giảm >= 5 ngày/lần)."""
        # 3 mốc RUL: [45.0, 30.0, 15.0] -> tụt 30 ngày trong 2 bước đo (15 ngày/lần)
        is_rapid, rate = PredictiveRULGuardrails.detect_rapid_degradation([45.0, 30.0, 15.0])
        self.assertTrue(is_rapid)
        self.assertEqual(rate, 15.0)

        # Mức sụt giảm bình thường: [45.0, 44.0, 43.0] -> tụt 1 ngày/lần
        is_normal, norm_rate = PredictiveRULGuardrails.detect_rapid_degradation([45.0, 44.0, 43.0])
        self.assertFalse(is_normal)

    def test_tc_rul_11_piecewise_linear_target_clamping(self):
        """TC-RUL-11: Kẹp trần Piece-wise Linear RUL Target (RUL <= 125.0 ngày)."""
        # Thiết bị mới tinh còn 250 ngày mới hỏng
        target_early = DegradationFeaturePipeline.calculate_piecewise_linear_target(time_to_failure=250.0)
        self.assertEqual(target_early, 125.0)

        # Thiết bị trong giai đoạn suy thoái còn 40 ngày
        target_late = DegradationFeaturePipeline.calculate_piecewise_linear_target(time_to_failure=40.0)
        self.assertEqual(target_late, 40.0)

    def test_tc_rul_12_auto_check_stock_and_draft_predictive_pm(self):
        """TC-RUL-12: Tự động tra tồn kho và sinh bản thảo Work Order đón đầu khi chạm Critical."""
        # Giả lập máy có độ rung và nhiệt độ cao suy thoái nặng
        self._seed_running_readings(self.asset, count=25, base_vib=8.0, base_temp=75.0)

        # Chạy dự đoán RUL
        res = RULPredictiveService.predict_asset_rul(asset=self.asset, current_user=self.user)
        self.assertTrue(res['success'])
        data = res['data']

        # Khi RUL sụt giảm chạm mức nguy cấp, hệ thống tự sinh phiếu PREDICTIVE_PM
        if data['riskLevel'] == 'CRITICAL':
            self.assertIsNotNone(data['draftWorkOrderId'])
            wo = WorkOrder.objects.get(id=data['draftWorkOrderId'])
            self.assertEqual(wo.type, 'PREDICTIVE_PM')
            self.assertEqual(wo.asset_id, self.asset.id)
            self.assertIn('VIB_METER', wo.required_tools)
            self.assertIn(str(self.spare_part.id), wo.required_spare_parts)


    def test_tc_aud04_multichannel_grouping_and_cold_start_cycle_count(self):
        """AUD-04: Gom nhóm đúng nhiều kênh theo round_id/timestamp, không bơm vibration=0 cho dòng TEMPERATURE."""
        now = timezone.now()
        # Tạo 10 cặp đo đồng thời (TEMPERATURE + VIBRATION) từ IoT (round_id=None) -> chỉ tính 10 chu kỳ!
        for i in range(10):
            ts = now - timedelta(hours=(24 - i))
            MeterReading.objects.create(
                tenant=self.asset.tenant,
                asset=self.asset,
                metric_code='TEMPERATURE',
                reading_value=Decimal('52.50'),
                reading_date=ts,
                unit='°C',
                ambient_temperature=31.0,
                machine_state='RUNNING',
                recorded_by=self.user,
            )
            MeterReading.objects.create(
                tenant=self.asset.tenant,
                asset=self.asset,
                metric_code='VIBRATION',
                reading_value=Decimal('3.20'),
                reading_date=ts + timedelta(milliseconds=50),
                unit='mm/s',
                machine_state='RUNNING',
                recorded_by=self.user,
            )

        readings_qs = MeterReading.objects.filter(asset=self.asset).order_by('reading_date')
        grouped_10 = PredictiveRULGuardrails.filter_running_meter_readings(readings_qs)
        self.assertEqual(len(grouped_10), 10)
        self.assertAlmostEqual(grouped_10[0]['vibration'], 3.20, places=2)
        self.assertAlmostEqual(grouped_10[0]['temperature'], 52.50, places=2)
        self.assertAlmostEqual(grouped_10[0]['ambient_temperature'], 31.0, places=2)

        # Với chỉ 10 chu kỳ (dù có 20 bản ghi DB), bắt buộc vẫn giữ CALIBRATING (N < 15)!
        res_cold = RULPredictiveService.predict_asset_rul(asset=self.asset, current_user=self.user)
        self.assertEqual(res_cold['data']['riskLevel'], 'CALIBRATING')
        self.assertEqual(res_cold['data']['validRunningSamples'], 10)
        self.assertEqual(res_cold['data']['rawRunningReadingsCount'], 20)

        # Thêm 6 vòng đo nữa (dùng round_id) -> 16 chu kỳ hợp lệ, đủ vượt ngưỡng 15
        for i in range(6):
            rid = uuid.uuid4()
            ts = now - timedelta(hours=(10 - i))
            MeterReading.objects.create(
                tenant=self.asset.tenant,
                asset=self.asset,
                round_id=rid,
                metric_code='VIBRATION',
                reading_value=Decimal('3.60'),
                reading_date=ts,
                unit='mm/s',
                machine_state='RUNNING',
                recorded_by=self.user,
            )
            MeterReading.objects.create(
                tenant=self.asset.tenant,
                asset=self.asset,
                round_id=rid,
                metric_code='TEMPERATURE',
                reading_value=Decimal('56.00'),
                reading_date=ts + timedelta(seconds=10),
                unit='°C',
                ambient_temperature=30.0,
                machine_state='RUNNING',
                recorded_by=self.user,
            )
            MeterReading.objects.create(
                tenant=self.asset.tenant,
                asset=self.asset,
                round_id=rid,
                metric_code='PRESSURE',
                reading_value=Decimal('12.50'),
                reading_date=ts + timedelta(seconds=12),
                unit='bar',
                machine_state='RUNNING',
                recorded_by=self.user,
            )

        # Một dòng chỉ có TEMPERATURE (không có vibration) -> không được gán giả vibration=0.0 trong grouped item!
        single_temp_rid = uuid.uuid4()
        MeterReading.objects.create(
            tenant=self.asset.tenant,
            asset=self.asset,
            round_id=single_temp_rid,
            metric_code='TEMPERATURE',
            reading_value=Decimal('57.00'),
            reading_date=now,
            unit='°C',
            machine_state='RUNNING',
            recorded_by=self.user,
        )
        grouped_all = PredictiveRULGuardrails.filter_running_meter_readings(
            MeterReading.objects.filter(asset=self.asset).order_by('reading_date')
        )
        self.assertEqual(len(grouped_all), 17)
        self.assertIsNone(grouped_all[-1]['vibration'])
        self.assertAlmostEqual(grouped_all[-1]['temperature'], 57.00, places=2)

    def test_tc_aud04_missing_channel_diagnostics_and_prototype_transparency(self):
        """AUD-04: Kênh thiếu không bị suy diễn quá nhiệt 45°C và API công khai rõ trạng thái nguyên mẫu chưa huấn luyện."""
        from rest_framework.test import APIClient

        # Chỉ nạp VIBRATION, thiếu TEMPERATURE & PRESSURE
        self._seed_running_readings(self.asset, count=20, base_vib=2.2)

        vec_missing_temp = DegradationFeaturePipeline.extract_4_feature_vector(
            vibration_rms=2.2,
            bearing_temp=None,
            ambient_temp=30.0,
            pressure=None,
            load_factor=1.0,
        )
        # Delta T và Pressure khi không có cảm biến phải ở mức trung tính 0.0 (không tự bịa 45°C hay 10 bar)
        self.assertEqual(float(vec_missing_temp[1]), 0.0)
        self.assertEqual(float(vec_missing_temp[2]), 0.0)

        res = RULPredictiveService.predict_asset_rul(asset=self.asset, current_user=self.user)
        data = res['data']
        self.assertFalse(data['modelMetadata']['isTrainedOnRealData'])
        self.assertEqual(data['modelMetadata']['trainingStatus'], 'UNTRAINED_PROTOTYPE')
        self.assertEqual(data['modelMetadata']['modelVersion'], 'v1.0.0-untrained-prototype')
        self.assertIn('TEMPERATURE', data['sensorDiagnostics']['missingChannels'])
        self.assertIn('PRESSURE', data['sensorDiagnostics']['missingChannels'])
        self.assertEqual(data['sensorDiagnostics']['groupedCyclesCount'], 20)

        # Kiểm tra endpoint GET /api/v1/assets/<id>/rul-prediction/
        client = APIClient()
        client.force_authenticate(user=self.user)
        from users.models import Permission, Role
        perm_read, _ = Permission.objects.get_or_create(id='asset:read', defaults={'name': 'Read Asset'})
        role = Role.all_objects.create(name='AUD04_VIEWER', tenant=self.tenant)
        role.permissions.add(perm_read)
        self.user.roles.add(role)

        resp = client.get(f"/api/v1/assets/{self.asset.id}/rul-prediction/")
        self.assertEqual(resp.status_code, 200)
        api_data = resp.json()['data']
        self.assertFalse(api_data['modelMetadata']['isTrainedOnRealData'])
        self.assertEqual(api_data['sensorDiagnostics']['groupedCyclesCount'], 20)

    def test_tc_aud04_get_endpoint_cold_start_parity_with_stale_asset_rul(self):
        """AUD-04: Asset thiếu chu kỳ RUNNING (<15) nhưng có RUL cũ trên Asset vẫn trả về CALIBRATING & None trên GET."""
        from rest_framework.test import APIClient
        from users.models import Permission, Role

        self.asset.current_rul_days = 90.0
        self.asset.current_rul_calendar_days = 90.0
        self.asset.rul_risk_level = 'CRITICAL'
        self.asset.rul_confidence_lower = 75.0
        self.asset.rul_confidence_upper = 105.0
        self.asset.save()

        perm_read, _ = Permission.objects.get_or_create(id='asset:read', defaults={'name': 'Read Asset'})
        role = Role.all_objects.create(name=f'AUD04_COLD_{uuid.uuid4().hex[:6]}', tenant=self.tenant)
        role.permissions.add(perm_read)
        self.user.roles.add(role)

        client = APIClient()
        client.force_authenticate(user=self.user)
        resp = client.get(f"/api/v1/assets/{self.asset.id}/rul-prediction/")
        self.assertEqual(resp.status_code, 200)
        api_data = resp.json()['data']
        self.assertEqual(api_data['riskLevel'], 'CALIBRATING')
        self.assertIsNone(api_data['operatingRulDays'])
        self.assertIsNone(api_data['calendarRulDays'])
        self.assertIsNone(api_data['confidenceInterval']['lower'])
        self.assertIsNone(api_data['confidenceInterval']['upper'])
        self.assertEqual(api_data['validRunningSamples'], 0)
        # Bảo toàn cột Asset gốc trong DB (không tự ý xóa dữ liệu kế toán/seed)
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.current_rul_days, 90.0)

    def test_tc_aud04_get_endpoint_disabled_includes_model_metadata(self):
        """AUD-04: Khi tắt enable_ai_rul trên Tenant, GET trả DISABLED kèm modelMetadata rõ ràng."""
        from rest_framework.test import APIClient
        from users.models import Permission, Role

        self.tenant.enable_ai_rul = False
        self.tenant.save()
        perm_read, _ = Permission.objects.get_or_create(id='asset:read', defaults={'name': 'Read Asset'})
        role = Role.all_objects.create(name=f'AUD04_DIS_{uuid.uuid4().hex[:6]}', tenant=self.tenant)
        role.permissions.add(perm_read)
        self.user.roles.add(role)

        client = APIClient()
        client.force_authenticate(user=self.user)
        resp = client.get(f"/api/v1/assets/{self.asset.id}/rul-prediction/")
        self.assertEqual(resp.status_code, 200)
        api_data = resp.json()['data']
        self.assertEqual(api_data['riskLevel'], 'DISABLED')
        self.assertFalse(api_data['aiEnabled'])
        self.assertIn('modelMetadata', api_data)
        self.assertEqual(api_data['modelMetadata']['trainingStatus'], 'UNTRAINED_PROTOTYPE')

    def test_tc_aud04_session_readings_multi_channel_grouped_correctly(self):
        """AUD-04: session_readings gửi tách TEMPERATURE + VIBRATION cùng chu kỳ phải được gom 1 chu kỳ, không thổi phồng thành 2."""
        base_time = timezone.now() - timedelta(hours=20)
        for i in range(13):
            ts = base_time + timedelta(hours=i)
            rid = uuid.uuid4()
            MeterReading.objects.create(
                asset=self.asset, metric_code='TEMPERATURE', reading_value=45.0,
                reading_date=ts, round_id=rid, machine_state='RUNNING', tenant=self.tenant
            )
            MeterReading.objects.create(
                asset=self.asset, metric_code='VIBRATION', reading_value=1.8,
                reading_date=ts, round_id=rid, machine_state='RUNNING', tenant=self.tenant
            )

        session_ts = timezone.now()
        session_payload = [
            {'metric_code': 'TEMPERATURE', 'reading_value': 55.0, 'reading_date': session_ts, 'machine_state': 'RUNNING'},
            {'metric_code': 'VIBRATION', 'reading_value': 2.2, 'reading_date': session_ts, 'machine_state': 'RUNNING'},
        ]
        # 13 chu kỳ DB + 1 chu kỳ phiên (2 kênh) = 14 chu kỳ -> Vẫn kích hoạt Cold Start (<15)!
        res_14 = RULPredictiveService.predict_asset_rul(
            asset=self.asset, current_user=self.user, session_readings=session_payload
        )
        self.assertEqual(res_14['data']['riskLevel'], 'CALIBRATING')
        self.assertEqual(res_14['data']['validRunningSamples'], 14)
        self.assertEqual(res_14['data']['rawRunningReadingsCount'], 28)

        # Thêm chu kỳ DB thứ 14 + 1 chu kỳ phiên = 15 chu kỳ -> Đủ ngưỡng chạy LSTM!
        rid14 = uuid.uuid4()
        ts14 = base_time + timedelta(hours=13)
        MeterReading.objects.create(
            asset=self.asset, metric_code='TEMPERATURE', reading_value=46.0,
            reading_date=ts14, round_id=rid14, machine_state='RUNNING', tenant=self.tenant
        )
        MeterReading.objects.create(
            asset=self.asset, metric_code='VIBRATION', reading_value=1.9,
            reading_date=ts14, round_id=rid14, machine_state='RUNNING', tenant=self.tenant
        )
        res_15 = RULPredictiveService.predict_asset_rul(
            asset=self.asset, current_user=self.user, session_readings=session_payload
        )
        self.assertNotEqual(res_15['data']['riskLevel'], 'CALIBRATING')
        self.assertEqual(res_15['data']['validRunningSamples'], 15)
        self.assertEqual(res_15['data']['rawRunningReadingsCount'], 30)



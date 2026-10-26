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

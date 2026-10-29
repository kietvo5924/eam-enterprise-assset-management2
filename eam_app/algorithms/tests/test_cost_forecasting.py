"""
Unit & Integration Test Suite cho Task 11.6: Maintenance Cost & Budget Forecasting.
Bao gồm trọn vẹn 12 Test Cases (TC-COST-01 -> TC-COST-12) phủ kín 100% quy tắc nghiệp vụ.
"""
import uuid
import datetime
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model

from core.models import Tenant
from core.tenant_context import clear_current_tenant
from users.models import Role
from assets.models import Asset, AssetCategory, Location, SparePart, StockTransaction
from workorders.models import WorkOrder, WorkOrderCost, LaborLog
from maintenance.models import PmPlan, PmPlanMaterial, PmPlanAssignment
from analytics.models import BudgetForecast
from notifications.models import Notification

from algorithms.cost_forecasting.constants import (
    DEFAULT_INFLATION_RATE,
    DEFAULT_CONTINGENCY_BUFFER_RATE,
    DEFAULT_LABOR_HOURLY_RATE
)
from algorithms.cost_forecasting.feature_pipeline import (
    CostFeaturePipeline,
    get_actual_consumption_net_cost
)
from algorithms.cost_forecasting.qrf_model import QuantileRegressionForestEngine
from algorithms.cost_forecasting.lemon_detector import LemonAssetDetector
from algorithms.cost_forecasting.hybrid_engine import HybridBudgetingEngine
from algorithms.cost_forecasting.service import CostForecastingService

User = get_user_model()


class MaintenanceCostForecastingTests(TestCase):
    def setUp(self):
        clear_current_tenant()
        self.tenant = Tenant.objects.create(
            name="Test Tenant Cost Forecasting",
            tenant_code=f"T-COST-{uuid.uuid4().hex[:6]}",
            enable_ai_cost_forecasting=True,
            theme_color="cyan"
        )
        self.user = User.objects.create_user(
            username=f'fin_mgr_{uuid.uuid4().hex[:6]}',
            email='finance@test.com',
            password='password123',
            tenant=self.tenant
        )
        self.role, _ = Role.objects.get_or_create(
            name="Finance Manager",
            tenant=self.tenant
        )
        self.user.roles.add(self.role)
        self.loc = Location.objects.create(
            name='Phân Xưởng Cơ Điện',
            code='WORKSHOP_MECH_01',
            tenant=self.tenant
        )
        self.cat = AssetCategory.objects.create(
            name='Bơm ly tâm công nghiệp',
            tenant=self.tenant
        )
        self.spare_part = SparePart.objects.create(
            name='Vòng bi SKF 6205',
            part_number='SKF-6205',
            unit_cost=Decimal('1500000.00'),
            quantity_in_stock=Decimal('10.00'),
            tenant=self.tenant
        )
        self.asset = Asset.objects.create(
            name='Bơm hóa chất ly tâm P-101',
            category=self.cat,
            location=self.loc,
            qr_code=f"QR-{uuid.uuid4().hex[:8]}",
            status='OPERATIONAL',
            asset_type='MACHINERY',
            purchase_cost=Decimal('200000000.00'),
            purchase_date=timezone.now().date() - datetime.timedelta(days=730),
            primary_spare_part=self.spare_part,
            tenant=self.tenant
        )

    def test_tc_cost_01_immutable_snapshot_guardrail(self):
        """
        TC-COST-01: Khóa bất biến đơn giá snapshot tại thời điểm chốt chi phí (Rule 1).
        Khi WorkOrder hoàn tất, snapshot giá phụ tùng và lương thợ được khóa vĩnh viễn.
        Thay đổi giá phụ tùng trong kho sau đó tuyệt đối không ảnh hưởng đến đơn hàng cũ.
        """
        wo = WorkOrder.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            title='Sửa chữa đại tu bơm P-101',
            type='CORRECTIVE',
            priority='HIGH',
            status='IN_PROGRESS'
        )

        # Xuất kho 2 vòng bi giá 1,500,000 VNĐ
        StockTransaction.all_objects.create(
            tenant=self.tenant,
            spare_part=self.spare_part,
            work_order=wo,
            transaction_type='ISSUE',
            quantity=Decimal('2.00'),
            unit_price=self.spare_part.unit_cost,
            total_amount=Decimal('3000000.00'),
            issue_date=timezone.now()
        )

        # Ghi nhận 10 giờ công thợ với mức giá 150,000 VNĐ/giờ
        LaborLog.all_objects.create(
            tenant=self.tenant,
            work_order=wo,
            technician=self.user,
            work_date=timezone.now().date(),
            hours_worked=Decimal('10.00'),
            hourly_rate=DEFAULT_LABOR_HOURLY_RATE,
            total_cost=Decimal('1500000.00')
        )

        wo.status = 'COMPLETED'
        wo.completed_at = timezone.now()
        wo.save()

        # Thực hiện đóng băng chi phí
        cost_obj = CostForecastingService.freeze_work_order_cost(wo)

        self.assertTrue(cost_obj.is_cost_frozen)
        self.assertIsNotNone(cost_obj.cost_frozen_at)
        self.assertEqual(cost_obj.material_cost, Decimal('3000000.00'))
        self.assertEqual(cost_obj.labor_cost, Decimal('1500000.00'))
        self.assertEqual(cost_obj.gross_cost, Decimal('4500000.00'))
        self.assertEqual(cost_obj.net_cost, Decimal('4500000.00'))

        # Giả lập: 6 tháng sau, lạm phát làm tăng giá vòng bi từ 1.5M lên 3.0M
        self.spare_part.unit_cost = Decimal('3000000.00')
        self.spare_part.save()

        # Kiểm tra lại: bản ghi chi phí đã đóng băng hoàn toàn bất biến
        cost_obj.refresh_from_db()
        self.assertEqual(cost_obj.material_cost, Decimal('3000000.00'))
        self.assertEqual(cost_obj.net_cost, Decimal('4500000.00'))

    def test_tc_cost_02_deferred_maintenance_trap(self):
        """
        TC-COST-02: Bẫy bảo trì hoãn lại & biến tích lũy nợ kỹ thuật (Rule 3).
        Khi doanh nghiệp hoãn nhiều lệnh bảo trì (Backlog cao), pipeline trích xuất
        đúng số lượng phiếu và giờ hoãn, kích hoạt rủi ro bùng nổ chi phí.
        """
        past_deadline = timezone.now() - datetime.timedelta(days=15)
        for i in range(12):
            WorkOrder.objects.create(
                tenant=self.tenant,
                asset=self.asset,
                title=f'Bảo trì định kỳ hoãn #{i}',
                type='PREVENTIVE',
                priority='MEDIUM',
                status='CREATED',
                deadline=past_deadline,
                estimated_duration_minutes=120 # 2 giờ mỗi phiếu
            )

        features = CostFeaturePipeline.extract_features(self.tenant)
        self.assertGreaterEqual(features["backlog_orders_count"], 12)
        self.assertGreaterEqual(features["deferred_maintenance_hours"], 24.0)

        # Vector đặc trưng nạp cho QRF phải chứa đúng 2 biến nợ kỹ thuật
        vec = features["feature_vector"]
        self.assertEqual(vec[6], float(features["backlog_orders_count"]))
        self.assertEqual(vec[7], float(features["deferred_maintenance_hours"]))

    def test_tc_cost_03_inflation_extrapolation_blindspot(self):
        """
        TC-COST-03: Khắc phục điểm mù ngoại suy lạm phát bằng cơ chế Hai Nhịp (Rule 4).
        Dự báo khối lượng vật lý * đơn giá * (1 + inflation_rate).
        """
        forecast_normal = HybridBudgetingEngine.execute_forecast(
            tenant=self.tenant,
            period_str='2026-Q4',
            inflation_rate=0.0
        )

        forecast_inflated = HybridBudgetingEngine.execute_forecast(
            tenant=self.tenant,
            period_str='2026-Q4',
            inflation_rate=0.30 # Lạm phát 30%
        )

        # Ngân sách sự cố CM khi có lạm phát 30% phải cao hơn kịch bản lạm phát 0%
        self.assertGreater(
            forecast_inflated["predictedCmMedian"],
            forecast_normal["predictedCmMedian"]
        )

    def test_tc_cost_04_inventory_purchasing_vs_actual_consumption(self):
        """
        TC-COST-04: Phân tách mua hàng lưu kho vs tiêu hao thực tế (Rule 5).
        Tuyệt đối loại trừ 100% các hóa đơn nhập kho lưu trữ RECEIPT.
        """
        today = timezone.now().date()
        start_d = today.replace(day=1)
        end_d = today

        # 1. Giao dịch mua hàng nhập kho 200,000,000 VNĐ
        StockTransaction.all_objects.create(
            tenant=self.tenant,
            spare_part=self.spare_part,
            transaction_type='RECEIPT',
            quantity=Decimal('100.00'),
            unit_price=Decimal('2000000.00'),
            total_amount=Decimal('200000000.00'),
            issue_date=timezone.now()
        )

        # 2. Giao dịch tiêu hao thực tế 1 vòng bi (1,500,000 VNĐ) vào WorkOrder hoàn tất
        wo = WorkOrder.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            title='Thay vòng bi thực tế',
            type='CORRECTIVE',
            status='COMPLETED',
            completed_at=timezone.now()
        )
        StockTransaction.all_objects.create(
            tenant=self.tenant,
            spare_part=self.spare_part,
            work_order=wo,
            transaction_type='ISSUE',
            quantity=Decimal('1.00'),
            unit_price=Decimal('1500000.00'),
            total_amount=Decimal('1500000.00'),
            issue_date=timezone.now()
        )

        net_consumption = get_actual_consumption_net_cost(self.tenant, start_d, end_d)
        # Chỉ tính 1.5M tiêu hao thực tế, loại trừ hoàn toàn 200M nhập kho
        self.assertEqual(net_consumption, Decimal('1500000.00'))

    def test_tc_cost_05_warranty_and_insurance_net_cost_slicing(self):
        """
        TC-COST-05: Bóc tách chi phí ròng bảo hành & bảo hiểm (Rule 6).
        Sửa chữa 300M được bảo hành 100% -> Gross = 300M, Net = 0M.
        """
        wo = WorkOrder.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            title='Thay thế cụm trục chính có bảo hành',
            type='CORRECTIVE',
            status='COMPLETED',
            completed_at=timezone.now()
        )
        StockTransaction.all_objects.create(
            tenant=self.tenant,
            spare_part=self.spare_part,
            work_order=wo,
            transaction_type='ISSUE',
            quantity=Decimal('1.00'),
            unit_price=Decimal('300000000.00'),
            total_amount=Decimal('300000000.00'),
            issue_date=timezone.now()
        )

        cost_obj = CostForecastingService.freeze_work_order_cost(
            work_order=wo,
            warranty_covered_amount=Decimal('300000000.00'),
            insurance_covered_amount=Decimal('0.00')
        )

        self.assertEqual(cost_obj.gross_cost, Decimal('300000000.00'))
        self.assertEqual(cost_obj.warranty_covered_amount, Decimal('300000000.00'))
        self.assertEqual(cost_obj.net_cost, Decimal('0.00'))

    def test_tc_cost_06_pareto_lemon_asset_and_rrr_audit(self):
        """
        TC-COST-06: Kiểm định Pareto 80/20 & RRR Bad Actor phát hiện thiết bị Quả chanh (Rule 7).
        """
        # Tạo thêm 9 máy hoạt động bình thường, chi phí = 0
        for i in range(9):
            Asset.objects.create(
                tenant=self.tenant,
                name=f'Máy bơm êm #{i}',
                category=self.cat,
                qr_code=f"QR-NORMAL-{i}-{uuid.uuid4().hex[:6]}",
                status='OPERATIONAL',
                purchase_cost=Decimal('100000000.00')
            )

        # Máy P-101 ngốn 150 triệu VNĐ chi phí (nguyên giá 200M -> RRR = 75% >= 70%)
        wo = WorkOrder.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            title='Sửa chữa liên tục',
            type='CORRECTIVE',
            status='COMPLETED',
            completed_at=timezone.now()
        )
        WorkOrderCost.all_objects.create(
            tenant=self.tenant,
            work_order=wo,
            gross_cost=Decimal('150000000.00'),
            net_cost=Decimal('150000000.00'),
            is_cost_frozen=True
        )

        lemon_result = LemonAssetDetector.audit_lemon_assets(self.tenant)
        self.assertTrue(lemon_result["isConcentrationDetected"])
        self.assertGreaterEqual(lemon_result["totalBadActorsCount"], 1)

        top_lemon = lemon_result["topLemonAsset"]
        self.assertEqual(top_lemon["assetId"], str(self.asset.id))
        self.assertGreaterEqual(top_lemon["rrrPercent"], 70.0)
        self.assertIn("Đề xuất ban giám đốc xem xét phương án thanh lý", top_lemon["recommendation"])

    def test_tc_cost_07_pruning_disposed_asset_history(self):
        """
        TC-COST-07: Khấu trừ toàn bộ lịch sử máy đã thanh lý DISPOSED (Rule 7).
        """
        wo = WorkOrder.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            title='Lệnh sửa của máy cũ',
            type='CORRECTIVE',
            status='COMPLETED',
            completed_at=timezone.now()
        )
        WorkOrderCost.all_objects.create(
            tenant=self.tenant,
            work_order=wo,
            net_cost=Decimal('50000000.00'),
            is_cost_frozen=True
        )

        # Trước khi thanh lý: Chi phí ghi nhận 50M
        today = timezone.now().date()
        cost_before = get_actual_consumption_net_cost(self.tenant, today.replace(day=1), today)
        self.assertEqual(cost_before, Decimal('50000000.00'))

        # Chuyển trạng thái máy sang DISPOSED (Thanh lý)
        self.asset.status = 'DISPOSED'
        self.asset.save()

        # Sau khi thanh lý: Pipeline tự động cắt tỉa sạch 100% chi phí máy này
        cost_after = get_actual_consumption_net_cost(self.tenant, today.replace(day=1), today)
        self.assertEqual(cost_after, Decimal('0.00'))

    def test_tc_cost_08_deterministic_pm_vs_stochastic_cm_decoupling(self):
        """
        TC-COST-08: Cơ chế ngân sách lai ghép: Tách bạch PM xác định vs CM ngẫu nhiên (Rule 8).
        """
        plan = PmPlan.objects.create(
            tenant=self.tenant,
            name='Bảo dưỡng định kỳ 30 ngày',
            trigger_type='TIME',
            interval_value=Decimal('30.0'),
            interval_unit='DAYS',
            is_active=True,
            estimated_duration_minutes=120 # 2 giờ công = 300,000 VNĐ
        )
        PmPlanMaterial.objects.create(
            tenant=self.tenant,
            pm_plan=plan,
            spare_part=self.spare_part,
            quantity=Decimal('2.0') # 2 vòng bi * 1.5M = 3,000,000 VNĐ
        )
        PmPlanAssignment.objects.create(
            tenant=self.tenant,
            pm_plan=plan,
            asset=self.asset,
            status='ACTIVE'
        )

        start_d = datetime.date(2026, 11, 1)
        end_d = datetime.date(2026, 11, 30)

        # Trong 30 ngày: kích hoạt đúng 1 lần
        pm_budget = HybridBudgetingEngine.calculate_deterministic_pm_budget(self.tenant, start_d, end_d)
        # Vật tư 3,000,000 + Nhân công 300,000 = 3,300,000 VNĐ
        self.assertEqual(pm_budget, Decimal('3300000.00'))

    def test_tc_cost_09_quantile_regression_forests_monotonicity(self):
        """
        TC-COST-09: Định lượng rủi ro bằng Quantile Regression Forests (Rule 9).
        Đảm bảo tính đơn điệu toán học P10 <= P50 <= P90.
        """
        features = [
            10000000.0, 12000000.0, 9000000.0, 10333333.0, 11000000.0, 1200000.0,
            2.0, 4.0, 15.0, 3.2, 0.35, 15000000.0, 200000000.0, 0.20, 11.0, 22.0
        ]
        X_train, y_train = CostFeaturePipeline.generate_synthetic_training_data(
            base_features=features,
            base_cost=15000000.0,
            num_samples=32
        )

        qrf = QuantileRegressionForestEngine()
        qrf.fit(X_train, y_train)

        quantiles = qrf.predict_quantiles(features)
        p10 = quantiles["p10"]
        p50 = quantiles["p50"]
        p90 = quantiles["p90"]

        self.assertLessEqual(p10, p50)
        self.assertLessEqual(p50, p90)
        self.assertGreater(p10, 0.0)

        top_drivers = qrf.get_top_cost_drivers(top_n=3)
        self.assertEqual(len(top_drivers), 3)

    def test_tc_cost_10_task_11_5_rul_critical_liability_bridge(self):
        """
        TC-COST-10: Cầu nối nghĩa vụ tài chính từ Task 11.5 RUL (Rule 10).
        Máy rơi vào mức CRITICAL RISK tự động cộng giá linh kiện vào ngân sách.
        """
        self.asset.rul_risk_level = 'CRITICAL'
        self.asset.current_rul_days = 5.0
        self.asset.save()

        features = CostFeaturePipeline.extract_features(self.tenant)
        self.assertEqual(features["rul_critical_liability"], self.spare_part.unit_cost)

        forecast = HybridBudgetingEngine.execute_forecast(self.tenant, period_str='2026-Q4')
        self.assertEqual(forecast["rulCriticalLiability"], self.spare_part.unit_cost)

    def test_tc_cost_11_budget_overrun_early_warning_notifications(self):
        """
        TC-COST-11: Cảnh báo sớm nguy cơ bội chi ngân sách qua Real-time Notification (Rule 11 & Task 10.1).
        """
        # Đặt ngân sách duyệt rất nhỏ để kích hoạt CRITICAL_OVERRUN
        forecast = CostForecastingService.run_forecast(
            tenant=self.tenant,
            period='2026-Q4',
            approved_budget=Decimal('1000000.00') # 1 triệu VNĐ trong khi dự báo hàng chục triệu
        )

        self.assertEqual(forecast.budget_status, 'CRITICAL_OVERRUN')
        self.assertGreater(forecast.budget_usage_ratio, 100.0)

        # Kiểm tra Notification được sinh ra
        notifs = Notification.objects.filter(
            tenant=self.tenant,
            severity='CRITICAL',
            event_type='BUDGET_OVERRUN_ALERT'
        )
        self.assertTrue(notifs.exists())
        self.assertEqual(forecast.get_budget_status_display(), 'Critical Overrun')

    def test_tc_cost_12_ai_governance_toggle_and_cold_start_fallback(self):
        """
        TC-COST-12: Chuyển đổi an toàn khi tắt AI / Khởi động nguội (Rule 12).
        Tắt enable_ai_cost_forecasting = False -> Fallback xác định, is_ai_fallback = True, không ném lỗi.
        """
        self.tenant.enable_ai_cost_forecasting = False
        self.tenant.save()

        forecast = CostForecastingService.run_forecast(
            tenant=self.tenant,
            period='2026-Q4'
        )

        self.assertTrue(forecast.is_ai_fallback)
        self.assertEqual(forecast.forecast_method, 'DETERMINISTIC_FALLBACK')
        self.assertGreater(forecast.total_forecast_median, Decimal('0.00'))
        self.assertLessEqual(forecast.predicted_cm_lower_p10, forecast.predicted_cm_median)
        self.assertLessEqual(forecast.predicted_cm_median, forecast.predicted_cm_upper_p90)

    def test_tc_cost_13_dynamic_tenant_financial_settings(self):
        """
        TC-COST-13: Cấu hình tài chính linh hoạt cấp Tenant (Lương giờ thợ động, lạm phát, dự phòng).
        Loại bỏ hoàn toàn các hằng số gán cứng cho hệ thống đa doanh nghiệp.
        """
        from analytics.models import TenantFinancialSetting, PeriodApprovedBudget

        # Cập nhật cài đặt tài chính cho Tenant
        settings_data = {
            "defaultLaborHourlyRate": 200000.0,
            "defaultInflationRate": 6.0,
            "defaultContingencyRate": 8.0,
            "criticalSparePartRatio": 7.0,
            "approvedBudget": 2500000000.0,
            "period": "2026-Q4"
        }
        res = CostForecastingService.update_financial_settings(self.tenant, settings_data, user=self.user)
        self.assertEqual(res["defaultLaborHourlyRate"], 200000.0)
        self.assertEqual(res["defaultInflationRatePercent"], 6.0)
        self.assertEqual(res["defaultContingencyRatePercent"], 8.0)
        self.assertEqual(res["approvedBudget"], 2500000000.0)
        self.assertTrue(res["isManuallyApproved"])

        # Kiểm tra database
        setting = TenantFinancialSetting.all_objects.get(tenant=self.tenant)
        self.assertEqual(setting.default_labor_hourly_rate, Decimal('200000.00'))
        self.assertEqual(setting.default_inflation_rate, 0.06)

        pab = PeriodApprovedBudget.all_objects.get(tenant=self.tenant, period='2026-Q4')
        self.assertEqual(pab.approved_budget, Decimal('2500000000.00'))
        self.assertTrue(pab.is_manually_approved)

    def test_tc_cost_14_period_approved_budget_influences_forecast_status(self):
        """
        TC-COST-14: Hạn mức ngân sách duyệt thực tế chi phối trực tiếp tỷ lệ áp lực và trạng thái ngân sách.
        """
        from analytics.models import PeriodApprovedBudget

        # Gán ngân sách duyệt lớn -> Trạng thái HEALTHY
        PeriodApprovedBudget.all_objects.create(
            tenant=self.tenant,
            period='2026-Q4',
            approved_budget=Decimal('5000000000.00'), # 5 tỷ
            is_manually_approved=True
        )

        forecast = CostForecastingService.run_forecast(
            tenant=self.tenant,
            period='2026-Q4'
        )

        self.assertTrue(forecast.is_manually_approved)
        self.assertEqual(forecast.approved_budget, Decimal('5000000000.00'))
        self.assertEqual(forecast.budget_status, 'HEALTHY')
        self.assertLess(forecast.budget_usage_ratio, 50.0)

    def test_tc_cost_15_regression_real_data_training_and_no_synthetic_in_production(self):
        """
        TC-COST-15: Xác minh không sử dụng dữ liệu tổng hợp (synthetic) trong luồng dự báo production.
        Khi chưa đủ 12 kỳ quan sát thực tế có nhãn, hệ thống chuyển sang Fallback xác định có ghi rõ lý do.
        """
        with patch.object(CostFeaturePipeline, 'generate_synthetic_training_data') as mock_synth:
            forecast = CostForecastingService.run_forecast(
                tenant=self.tenant,
                period='2026-Q4'
            )
            # generate_synthetic_training_data tuyệt đối không được gọi trong production run_forecast
            mock_synth.assert_not_called()

        self.assertTrue(forecast.is_ai_fallback)
        self.assertEqual(forecast.forecast_method, 'DETERMINISTIC_FALLBACK')
        self.assertEqual(forecast.fallback_reason, 'INSUFFICIENT_HISTORICAL_DATA')

        # Kiểm tra readiness giải thích rõ ràng lý do
        readiness = CostForecastingService.check_readiness(self.tenant)
        self.assertFalse(readiness["isReadyForAiQrf"])
        self.assertEqual(readiness["fallbackReason"], 'INSUFFICIENT_HISTORICAL_DATA')
        self.assertIn("Cần tối thiểu 12 kỳ", readiness["statusLabel"])

    def test_tc_cost_16_regression_time_based_dataset_no_future_leakage(self):
        """
        TC-COST-16: Kiểm định chuỗi thời gian time-series không rò rỉ dữ liệu tương lai (no data leakage).
        Đặc trưng của tháng t được trích xuất nghiêm ngặt tại ngày 1 của tháng t.
        """
        today = timezone.now().date()
        X_real, y_real, meta = CostFeaturePipeline.build_historical_training_dataset(
            tenant=self.tenant,
            reference_date=today,
            months_back=6
        )
        self.assertEqual(len(X_real), 6)
        self.assertEqual(len(y_real), 6)
        # Các mẫu phải có nhãn thời gian giảm dần về quá khứ
        periods = [m["period"] for m in meta]
        self.assertEqual(len(periods), 6)
        # Không có phần tử NaN hay Inf
        import numpy as np
        self.assertFalse(np.isnan(X_real).any())
        self.assertFalse(np.isinf(X_real).any())

    def test_tc_cost_17_regression_mixed_period_snapshot_and_unfrozen_work_orders(self):
        """
        TC-COST-17: Tổng hợp chi phí trong kỳ có cả WorkOrder đã đóng băng và chưa đóng băng:
        Không bỏ sót, không cộng trùng, loại trừ CapEx và tài sản đã thanh lý.
        """
        start_d = datetime.date(2026, 5, 1)
        end_d = datetime.date(2026, 5, 31)

        # WO 1: Đã đóng băng snapshot net_cost = 5M
        wo1 = WorkOrder.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            title='WO 1 Snapshot Chốt',
            type='CORRECTIVE',
            status='COMPLETED',
            completed_at=timezone.make_aware(datetime.datetime(2026, 5, 10, 10, 0))
        )
        WorkOrderCost.all_objects.create(
            tenant=self.tenant,
            work_order=wo1,
            material_cost=Decimal('3000000.00'),
            labor_cost=Decimal('2000000.00'),
            gross_cost=Decimal('5000000.00'),
            net_cost=Decimal('5000000.00'),
            is_cost_frozen=True
        )

        # WO 2: Chưa đóng băng snapshot, có 2M vật tư + 1M công = 3M
        wo2 = WorkOrder.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            title='WO 2 Chưa Snapshot',
            type='CORRECTIVE',
            status='COMPLETED',
            completed_at=timezone.make_aware(datetime.datetime(2026, 5, 15, 14, 0))
        )
        StockTransaction.all_objects.create(
            tenant=self.tenant,
            work_order=wo2,
            spare_part=self.spare_part,
            transaction_type='ISSUE',
            quantity=Decimal('1.0'),
            total_amount=Decimal('2000000.00'),
            issue_date=timezone.make_aware(datetime.datetime(2026, 5, 15, 10, 0))
        )
        LaborLog.all_objects.create(
            tenant=self.tenant,
            work_order=wo2,
            technician=self.user,
            work_date=datetime.date(2026, 5, 15),
            hours_worked=Decimal('5.0'),
            total_cost=Decimal('1000000.00')
        )

        # WO 3: Đại tu CapEx (is_capitalized=True) = 20M -> Phải bị loại trừ khỏi OpEx
        wo3 = WorkOrder.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            title='WO 3 CapEx',
            type='CORRECTIVE',
            status='COMPLETED',
            is_capitalized=True,
            completed_at=timezone.make_aware(datetime.datetime(2026, 5, 20, 10, 0))
        )
        WorkOrderCost.all_objects.create(
            tenant=self.tenant,
            work_order=wo3,
            gross_cost=Decimal('20000000.00'),
            net_cost=Decimal('20000000.00'),
            is_capital_overhaul=True,
            is_cost_frozen=True
        )

        # Tổng chi phí ròng kỳ tháng 5 phải là 5M + 3M = 8,000,000 VNĐ
        net_cost = get_actual_consumption_net_cost(self.tenant, start_d, end_d)
        self.assertEqual(net_cost, Decimal('8000000.00'))

    def test_tc_cost_18_regression_100_percent_warranty_preserves_zero_net_cost(self):
        """
        TC-COST-18: Phiếu bảo hành 100% cho ra chi phí ròng 0 VNĐ, không bao giờ rơi về chi phí thô dương.
        """
        start_d = datetime.date(2026, 6, 1)
        end_d = datetime.date(2026, 6, 30)

        wo = WorkOrder.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            title='Sửa chữa bảo hành toàn bộ',
            type='CORRECTIVE',
            status='COMPLETED',
            completed_at=timezone.make_aware(datetime.datetime(2026, 6, 12, 10, 0))
        )
        # Vật tư 50 triệu
        StockTransaction.all_objects.create(
            tenant=self.tenant,
            work_order=wo,
            spare_part=self.spare_part,
            transaction_type='ISSUE',
            quantity=Decimal('1.0'),
            unit_price=Decimal('50000000.00'),
            total_amount=Decimal('50000000.00'),
            issue_date=timezone.make_aware(datetime.datetime(2026, 6, 12, 9, 0))
        )
        # Khóa snapshot với bảo hành 50M -> Net = 0
        WorkOrderCost.all_objects.create(
            tenant=self.tenant,
            work_order=wo,
            gross_cost=Decimal('50000000.00'),
            warranty_covered_amount=Decimal('50000000.00'),
            net_cost=Decimal('0.00'),
            is_cost_frozen=True
        )

        net_cost = get_actual_consumption_net_cost(self.tenant, start_d, end_d)
        self.assertEqual(net_cost, Decimal('0.00'))

    def test_tc_cost_19_regression_stock_transaction_semantics(self):
        """
        TC-COST-19: Xử lý đúng ISSUE (+), ADJUSTMENT (+), RETURN (-) và loại trừ 100% RECEIPT.
        """
        start_d = datetime.date(2026, 7, 1)
        end_d = datetime.date(2026, 7, 31)

        wo = WorkOrder.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            title='Lệnh sửa chữa phân tách vật tư',
            type='CORRECTIVE',
            status='COMPLETED',
            completed_at=timezone.make_aware(datetime.datetime(2026, 7, 15, 10, 0))
        )
        # 1. ISSUE xuất 10M
        StockTransaction.all_objects.create(
            tenant=self.tenant,
            work_order=wo,
            spare_part=self.spare_part,
            transaction_type='ISSUE',
            quantity=Decimal('10.0'),
            unit_price=Decimal('1000000.00'),
            total_amount=Decimal('10000000.00'),
            issue_date=timezone.make_aware(datetime.datetime(2026, 7, 15, 8, 0))
        )
        # 2. ADJUSTMENT điều chỉnh tăng 2M
        StockTransaction.all_objects.create(
            tenant=self.tenant,
            work_order=wo,
            spare_part=self.spare_part,
            transaction_type='ADJUSTMENT',
            quantity=Decimal('2.0'),
            unit_price=Decimal('1000000.00'),
            total_amount=Decimal('2000000.00'),
            issue_date=timezone.make_aware(datetime.datetime(2026, 7, 15, 9, 0))
        )
        # 3. RETURN trả kho thừa 3M
        StockTransaction.all_objects.create(
            tenant=self.tenant,
            work_order=wo,
            spare_part=self.spare_part,
            transaction_type='RETURN',
            quantity=Decimal('-3.0'),
            unit_price=Decimal('1000000.00'),
            total_amount=Decimal('3000000.00'),
            issue_date=timezone.make_aware(datetime.datetime(2026, 7, 15, 11, 0))
        )
        # 4. RECEIPT nhập kho lưu trữ 200M (không được tính vào tiêu hao)
        StockTransaction.all_objects.create(
            tenant=self.tenant,
            spare_part=self.spare_part,
            transaction_type='RECEIPT',
            quantity=Decimal('200.0'),
            unit_price=Decimal('1000000.00'),
            total_amount=Decimal('200000000.00'),
            issue_date=timezone.make_aware(datetime.datetime(2026, 7, 15, 7, 0))
        )

        net_cost = get_actual_consumption_net_cost(self.tenant, start_d, end_d)
        # 10M + 2M - 3M = 9,000,000 VNĐ
        self.assertEqual(net_cost, Decimal('9000000.00'))

    def test_tc_cost_20_regression_work_order_completion_freezes_snapshot(self):
        """
        TC-COST-20: Đóng băng snapshot chi phí bất biến khi hoàn thành Work Order qua WorkOrderTransitionService.
        Gọi lặp lại bảo toàn tính idempotent, không ghi đè số liệu.
        """
        from workorders.services import WorkOrderTransitionService
        from workorders.models import WorkOrderChecklistItem, WorkOrderAttachment

        wo = WorkOrder.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            title='Lệnh bảo dưỡng nghiệm thu',
            type='CORRECTIVE',
            status='IN_PROGRESS',
            assigned_to=self.user
        )
        # Tạo attachment bắt buộc
        WorkOrderAttachment.objects.create(
            tenant=self.tenant,
            work_order=wo,
            file_url="/media/proof.jpg",
            file_name="proof.jpg",
            file_type="image/jpeg",
            file_size=1024
        )
        # Tạo xuất kho 2 vòng bi
        StockTransaction.all_objects.create(
            tenant=self.tenant,
            work_order=wo,
            spare_part=self.spare_part,
            transaction_type='ISSUE',
            quantity=Decimal('2.0'),
            unit_price=Decimal('1500000.00'),
            total_amount=Decimal('3000000.00'),
            issue_date=timezone.now()
        )

        completed_wo = WorkOrderTransitionService.complete_work_order(
            work_order_id=wo.id,
            user=self.user,
            tenant_id=self.tenant.id
        )
        self.assertEqual(completed_wo.status, 'COMPLETED')

        # Kiểm tra WorkOrderCost snapshot được tạo tự động
        cost_snap = WorkOrderCost.all_objects.filter(work_order=wo).first()
        self.assertIsNotNone(cost_snap)
        self.assertTrue(cost_snap.is_cost_frozen)
        self.assertEqual(cost_snap.material_cost, Decimal('3000000.00'))
        self.assertEqual(cost_snap.net_cost, Decimal('3000000.00'))
        frozen_time = cost_snap.cost_frozen_at

        # Gọi lại freeze_work_order_cost -> Idempotent, không thay đổi thời điểm và giá trị
        cost_snap_again = CostForecastingService.freeze_work_order_cost(wo)
        self.assertEqual(cost_snap_again.id, cost_snap.id)
        self.assertEqual(cost_snap_again.cost_frozen_at, frozen_time)

    def test_tc_cost_21_regression_pm_scheduling_yearly_and_suppression(self):
        """
        TC-COST-21: Lập lịch PM không mặc định kích hoạt nếu chưa đến hạn.
        Kế hoạch chu kỳ năm (365 ngày) không phát sinh chi phí trong tháng nếu chưa đến hạn;
        Tôn trọng quy tắc suppress_if_pending khi có phiếu bảo trì đang tồn đọng.
        """
        start_d = datetime.date(2026, 11, 1)
        end_d = datetime.date(2026, 11, 30)

        # 1. Kế hoạch năm (365 ngày), vừa thực hiện hôm qua -> Trong tháng 11 không được tính
        plan_yearly = PmPlan.objects.create(
            tenant=self.tenant,
            name='Đại tu năm toàn nhà máy',
            interval_value=Decimal('1.0'),
            interval_unit='YEARS',
            is_active=True,
            estimated_duration_minutes=600
        )
        assign_yearly = PmPlanAssignment.objects.create(
            tenant=self.tenant,
            pm_plan=plan_yearly,
            asset=self.asset,
            last_triggered_at=timezone.make_aware(datetime.datetime(2026, 10, 27, 8, 0)),
            status='ACTIVE'
        )

        # 2. Kế hoạch 30 ngày có suppress_if_pending=True, nhưng đang có 1 phiếu PREVENTIVE mở
        plan_suppressed = PmPlan.objects.create(
            tenant=self.tenant,
            name='Bảo dưỡng hàng tháng tránh trùng lặp',
            interval_value=Decimal('30.0'),
            interval_unit='DAYS',
            is_active=True,
            suppress_if_pending=True,
            estimated_duration_minutes=120
        )
        assign_suppressed = PmPlanAssignment.objects.create(
            tenant=self.tenant,
            pm_plan=plan_suppressed,
            asset=self.asset,
            last_triggered_at=timezone.make_aware(datetime.datetime(2026, 10, 1, 8, 0)),
            status='ACTIVE'
        )
        # Phiếu bảo trì định kỳ đang chờ thực hiện
        WorkOrder.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            title='Phiếu PM đang chờ xử lý',
            type='PREVENTIVE',
            status='IN_PROGRESS'
        )

        pm_budget = HybridBudgetingEngine.calculate_deterministic_pm_budget(self.tenant, start_d, end_d)
        # Cả 2 kế hoạch đều không phát sinh trong tháng 11 -> Chi phí = 0 VNĐ
        self.assertEqual(pm_budget, Decimal('0.00'))

    def test_tc_cost_22_regression_custom_financial_settings_persistence_on_rerun(self):
        """
        TC-COST-22: Tỷ lệ tài chính tùy chỉnh cấp Tenant (lương thợ, lạm phát, dự phòng)
        được giữ nguyên vẹn khi người dùng bấm chạy lại dự báo trên API.
        """
        from analytics.models import TenantFinancialSetting
        from rest_framework.test import APIClient

        # Thiết lập cài đặt tùy chỉnh
        TenantFinancialSetting.all_objects.update_or_create(
            tenant=self.tenant,
            defaults={
                'default_inflation_rate': 0.08,    # 8.0%
                'default_contingency_rate': 0.10,  # 10.0%
                'default_labor_hourly_rate': Decimal('250000.00')
            }
        )

        client = APIClient()
        client.force_authenticate(user=self.user)

        # Chạy dự báo mà không truyền tham số override
        res = client.post('/api/v1/cost-forecasting/run-forecast/', {
            'period': '2026-Q4'
        }, format='json')
        self.assertEqual(res.status_code, 200)

        forecast = BudgetForecast.all_objects.filter(tenant=self.tenant, forecast_period='2026-Q4').latest('created_at')
        # Tỷ lệ lạm phát áp dụng phải là 8.0%, không bị gán đè bởi mặc định 4.5%
        self.assertAlmostEqual(forecast.inflation_rate_applied, 0.08)

    def test_tc_cost_23_regression_tenant_isolation_and_permission_denial(self):
        """
        TC-COST-23: Cô lập Tenant A vs Tenant B và từ chối người dùng không có thẩm quyền tài chính.
        """
        from rest_framework.test import APIClient
        from django.core.exceptions import PermissionDenied
        from portal.views import portal_cost_forecasting
        from django.test import RequestFactory

        # Tenant B
        tenant_b = Tenant.objects.create(
            name="Tenant B Competitor",
            tenant_code=f"T-B-{uuid.uuid4().hex[:6]}"
        )
        user_b = User.objects.create_user(
            username=f'user_b_{uuid.uuid4().hex[:6]}',
            email='b@test.com',
            password='password123',
            tenant=tenant_b
        )
        role_b = Role.objects.create(name="Plant Manager", tenant=tenant_b)
        user_b.roles.add(role_b)

        client = APIClient()
        client.force_authenticate(user=user_b)

        # User B truy cập báo cáo của Tenant B thành công
        res = client.get(f'/api/v1/cost-forecasting/current-forecast/?period=2026-Q4')
        self.assertEqual(res.status_code, 200)
        # Forecast trả về phải gắn đúng Tenant B
        self.assertNotEqual(res.data['data']['period'], None)

        # Tạo user Kỹ thuật viên thuần túy trong Tenant A (không có role Finance hay quyền reports:read)
        tech_user = User.objects.create_user(
            username=f'tech_only_{uuid.uuid4().hex[:6]}',
            email='tech@test.com',
            password='password123',
            tenant=self.tenant
        )
        tech_role, _ = Role.objects.get_or_create(name="Junior Field Technician", tenant=self.tenant)
        tech_user.roles.add(tech_role)

        tech_client = APIClient()
        tech_client.force_authenticate(user=tech_user)

        # Bị chặn 403 Forbidden ở mọi API dự báo tài chính
        res1 = tech_client.get('/api/v1/cost-forecasting/current-forecast/')
        self.assertEqual(res1.status_code, 403)

        res2 = tech_client.post('/api/v1/cost-forecasting/run-forecast/', {'period': '2026-Q4'}, format='json')
        self.assertEqual(res2.status_code, 403)

        res3 = tech_client.post('/api/v1/cost-forecasting/settings/', {'defaultInflationRate': 5.0}, format='json')
        self.assertEqual(res3.status_code, 403)

        # Bị chặn ở giao diện portal
        factory = RequestFactory()
        req = factory.get('/portal/cost-forecasting/')
        req.user = tech_user
        with self.assertRaises(PermissionDenied):
            portal_cost_forecasting(req)

    def test_tc_cost_24_regression_notification_deduplication_no_spam(self):
        """
        TC-COST-24: Chống spam thông báo bội chi khi gọi lại hoặc tải trang nhiều lần.
        """
        # Chạy dự báo với hạn mức rất thấp để kích hoạt bội chi
        forecast = CostForecastingService.run_forecast(
            tenant=self.tenant,
            period='2026-Q4',
            approved_budget=Decimal('1000.00')
        )
        self.assertEqual(forecast.budget_status, 'CRITICAL_OVERRUN')

        count_1 = Notification.objects.filter(
            tenant=self.tenant,
            event_type='BUDGET_OVERRUN_ALERT',
            metadata__period='2026-Q4'
        ).count()
        self.assertGreater(count_1, 0)

        # GET request tải lại trang không được sinh thêm thông báo
        _ = CostForecastingService.get_current_forecast(
            tenant=self.tenant,
            period='2026-Q4'
        )
        count_2 = Notification.objects.filter(
            tenant=self.tenant,
            event_type='BUDGET_OVERRUN_ALERT',
            metadata__period='2026-Q4'
        ).count()
        self.assertEqual(count_1, count_2)

        # Chạy lại run_forecast cho cùng kỳ trong vòng 24h không bị nhân đôi
        CostForecastingService.run_forecast(
            tenant=self.tenant,
            period='2026-Q4',
            approved_budget=Decimal('1000.00')
        )
        count_3 = Notification.objects.filter(
            tenant=self.tenant,
            event_type='BUDGET_OVERRUN_ALERT',
            metadata__period='2026-Q4'
        ).count()
        self.assertEqual(count_1, count_3)

    def test_tc_cost_25_work_order_completion_atomicity_and_retry_self_healing(self):
        """
        TC-COST-25 (Fix A): Tính toàn vẹn dữ liệu Work Order Cost - Atomicity & Self-healing retry.
        1. Khi hoàn thành Work Order, freeze_work_order_cost thực hiện nguyên tử.
        2. Nếu freeze lỗi, giao dịch rollback, WO không bị đổi sang COMPLETED.
        3. Idempotency: gọi hoàn thành lại không tạo bản ghi snapshot trùng.
        4. Tự khắc phục (self-healing): nếu WO đã COMPLETED nhưng thiếu snapshot, gọi retry sẽ tự động freeze.
        """
        from workorders.services import WorkOrderTransitionService
        from workorders.models import WorkOrderAttachment

        wo = WorkOrder.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            title='Test Atomicity Work Order',
            type='CORRECTIVE',
            status='IN_PROGRESS'
        )
        WorkOrderAttachment.objects.create(
            tenant=self.tenant,
            work_order=wo,
            file_url='https://minio.local/proof.jpg',
            file_name='proof.jpg',
            file_type='image/jpeg',
            file_size=1024
        )
        StockTransaction.all_objects.create(
            tenant=self.tenant,
            spare_part=self.spare_part,
            work_order=wo,
            transaction_type='ISSUE',
            quantity=Decimal('1.00'),
            unit_price=Decimal('1500000.00'),
            total_amount=Decimal('1500000.00'),
            issue_date=timezone.now()
        )

        # 1. Thử nghiệm rollback nguyên tử khi freeze lỗi
        with patch.object(CostForecastingService, 'freeze_work_order_cost', side_effect=RuntimeError("Simulated Freeze DB Failure")):
            with self.assertRaises(RuntimeError):
                WorkOrderTransitionService.complete_work_order(
                    work_order=wo,
                    performed_by=self.user
                )

        wo.refresh_from_db()
        # Trạng thái WO phải được rollback, không được để lửng lơ ở trạng thái COMPLETED
        self.assertEqual(wo.status, 'IN_PROGRESS')
        self.assertFalse(WorkOrderCost.all_objects.filter(tenant=self.tenant, work_order=wo).exists())

        # 2. Hoàn thành thành công kèm khấu trừ bảo hành và bảo hiểm
        completed_wo = WorkOrderTransitionService.complete_work_order(
            work_order=wo,
            performed_by=self.user,
            warranty_covered_amount=Decimal('500000.00'),
            insurance_covered_amount=Decimal('200000.00'),
            vendor_cost=Decimal('300000.00')
        )
        self.assertEqual(completed_wo.status, 'COMPLETED')
        self.assertIsNotNone(completed_wo.completed_at)

        cost_snapshot = WorkOrderCost.all_objects.filter(tenant=self.tenant, work_order=wo).first()
        self.assertIsNotNone(cost_snapshot)
        self.assertTrue(cost_snapshot.is_cost_frozen)
        self.assertEqual(cost_snapshot.warranty_covered_amount, Decimal('500000.00'))
        self.assertEqual(cost_snapshot.insurance_covered_amount, Decimal('200000.00'))
        self.assertEqual(cost_snapshot.vendor_cost, Decimal('300000.00'))
        # Gross = 1.5M (vật tư) + 0.3M (vendor) = 1.8M
        self.assertEqual(cost_snapshot.gross_cost, Decimal('1800000.00'))
        # Net = Gross - (0.5M + 0.2M) = 1.1M
        self.assertEqual(cost_snapshot.net_cost, Decimal('1100000.00'))
        self.assertEqual(completed_wo.actual_cost, Decimal('1100000.00'))

        # 3. Idempotency: Gọi lại lần 2 không sinh bản ghi duplicate
        retry_wo = WorkOrderTransitionService.complete_work_order(
            work_order=wo,
            performed_by=self.user
        )
        self.assertEqual(retry_wo.status, 'COMPLETED')
        self.assertEqual(WorkOrderCost.all_objects.filter(tenant=self.tenant, work_order=wo).count(), 1)

        # 4. Self-healing: Giả sử bản ghi WorkOrderCost bị xóa ngoài ý muốn, gọi lại sẽ tự động đóng băng lại
        WorkOrderCost.all_objects.filter(tenant=self.tenant, work_order=wo).delete()
        self.assertFalse(WorkOrderCost.all_objects.filter(tenant=self.tenant, work_order=wo).exists())

        healed_wo = WorkOrderTransitionService.complete_work_order(
            work_order=wo,
            performed_by=self.user
        )
        self.assertEqual(healed_wo.status, 'COMPLETED')
        self.assertTrue(WorkOrderCost.all_objects.filter(tenant=self.tenant, work_order=wo, is_cost_frozen=True).exists())

    def test_tc_cost_26_point_in_time_reconstruction_no_future_leakage(self):
        """
        TC-COST-26 (Fix B): Chống rò rỉ dữ liệu tương lai trong mô hình dự báo.
        Đặc trưng backlog và RUL tại mốc lịch sử target_date chỉ phản ánh trạng thái đúng tại mốc đó.
        """
        target_past_date = timezone.now().date() - datetime.timedelta(days=90)
        target_past_dt = timezone.make_aware(datetime.datetime.combine(target_past_date, datetime.time.min))

        # WO quá khứ: tạo trước target_past_date, deadline trước target_past_date, nhưng hoàn thành SAU target_past_date
        past_wo = WorkOrder.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            title='WO Overdue at target_past_date',
            type='CORRECTIVE',
            status='COMPLETED',
            deadline=target_past_dt - datetime.timedelta(days=5),
            completed_at=target_past_dt + datetime.timedelta(days=10)
        )
        # Giả lập created_at trong quá khứ
        WorkOrder.objects.filter(id=past_wo.id).update(created_at=target_past_dt - datetime.timedelta(days=15))

        # Trích xuất đặc trưng tại thời điểm quá khứ target_past_date
        feat_past = CostFeaturePipeline.extract_features(self.tenant, target_date=target_past_date)
        # Tại target_past_date, past_wo chưa hoàn thành và đã quá hạn -> phải được tính vào backlog
        self.assertGreaterEqual(feat_past["backlog_orders_count"], 1)

        # Trích xuất đặc trưng tại ngày hiện tại
        feat_now = CostFeaturePipeline.extract_features(self.tenant, target_date=timezone.now().date())
        # Tại thời điểm hiện tại, past_wo đã hoàn tất từ lâu -> không nằm trong backlog hiện tại
        self.assertEqual(feat_now["backlog_orders_count"], 0)

    def test_tc_cost_27_out_of_sample_timeseries_backtesting(self):
        """
        TC-COST-27 (Fix C): Backtest đánh giá ngoài mẫu (Out-of-sample time-series validation).
        Kiểm định QRF trên tập test riêng biệt, tính toán MAE, WAPE, RMSE, Coverage P10-P90
        và so sánh cải thiện với Baseline SMA-3.
        """
        # Tạo chuỗi 16 tháng lịch sử có chi phí thực tế
        today = timezone.now().date()
        self.asset.purchase_date = today - datetime.timedelta(days=1200)
        self.asset.save()
        for i in range(16, 0, -1):
            m = today.month - i
            y = today.year
            while m <= 0:
                m += 12
                y -= 1
            wo_date = timezone.make_aware(datetime.datetime(y, m, 15, 10, 0))
            wo_hist = WorkOrder.objects.create(
                tenant=self.tenant,
                asset=self.asset,
                title=f'Hist WO {y}-{m}',
                type='CORRECTIVE',
                status='COMPLETED',
                completed_at=wo_date
            )
            WorkOrder.objects.filter(id=wo_hist.id).update(created_at=wo_date - datetime.timedelta(days=2))
            WorkOrderCost.all_objects.create(
                tenant=self.tenant,
                work_order=wo_hist,
                net_cost=Decimal(str(10000000 + i * 500000)),
                is_cost_frozen=True,
                is_capital_overhaul=False,
                cost_frozen_at=wo_date
            )

        res = HybridBudgetingEngine.execute_forecast(self.tenant, period_str='2026-Q4')
        self.assertEqual(res["forecastMethod"], 'HYBRID_QRF')
        self.assertFalse(res["isAiFallback"])

        metrics = res.get("evaluationMetrics", {})
        self.assertTrue(metrics.get("is_evaluated", False))
        self.assertIn("mae", metrics)
        self.assertIn("wape", metrics)
        self.assertIn("rmse", metrics)
        self.assertIn("coverage_p10_p90", metrics)
        self.assertIn("improvement_vs_sma_percent", metrics)
        self.assertGreater(metrics["test_samples_count"], 0)

    def test_tc_cost_28_notification_dedup_cost_center_and_recipient_security(self):
        """
        TC-COST-28 (Fix E): Cảnh báo bội chi phân lập theo Cost Center và không phát tán cho user thiếu thẩm quyền.
        1. Cảnh báo vượt ngân sách ở Xưởng A không làm chặn cảnh báo ở Xưởng B.
        2. Người dùng kỹ thuật viên thông thường tuyệt đối không nhận được thông báo tài chính.
        """
        loc_b = Location.objects.create(name='Phân Xưởng Đúc Mạ', code='WORKSHOP_CAST_02', tenant=self.tenant)
        tech_user = User.objects.create_user(
            username=f'tech_sec_{uuid.uuid4().hex[:6]}',
            email='tech_sec@test.com',
            password='password123',
            tenant=self.tenant,
            status='ACTIVE'
        )

        # 1. Chạy cảnh báo cho Xưởng Cơ Điện
        f_a = CostForecastingService.run_forecast(
            tenant=self.tenant,
            period='2026-Q4',
            cost_center=self.loc.name,
            approved_budget=Decimal('100.00')
        )
        self.assertEqual(f_a.budget_status, 'CRITICAL_OVERRUN')

        # 2. Chạy cảnh báo cho Xưởng Đúc Mạ trong cùng một kỳ
        f_b = CostForecastingService.run_forecast(
            tenant=self.tenant,
            period='2026-Q4',
            cost_center=loc_b.name,
            approved_budget=Decimal('100.00')
        )
        self.assertEqual(f_b.budget_status, 'CRITICAL_OVERRUN')

        # Cả 2 xưởng đều phải có thông báo riêng biệt (không bị deduplication nuốt mất)
        notifs_a = Notification.objects.filter(tenant=self.tenant, metadata__costCenter=self.loc.name)
        notifs_b = Notification.objects.filter(tenant=self.tenant, metadata__costCenter=loc_b.name)
        self.assertTrue(notifs_a.exists())
        self.assertTrue(notifs_b.exists())

        # 3. Kỹ thuật viên không có quyền không được nhận thông báo
        tech_notifs = Notification.objects.filter(tenant=self.tenant, recipient=tech_user)
        self.assertFalse(tech_notifs.exists())

    def test_tc_cost_29_lemon_detector_asset_transfer_between_cost_centers(self):
        """
        TC-COST-29 (Fix F): Điều chuyển tài sản giữa các phân xưởng không làm mất lịch sử chi phí.
        Máy phát sinh chi phí tại Xưởng A, sau đó chuyển sang Xưởng B:
        Kiểm định Bad Actor tại Xưởng A vẫn ghi nhận đúng chi phí phát sinh tại Xưởng A.
        """
        loc_b = Location.objects.create(name='Phân Xưởng Ép Phôi', code='WORKSHOP_PRESS_03', tenant=self.tenant)
        transfer_asset = Asset.objects.create(
            name='Máy nén khí di động AC-200',
            category=self.cat,
            location=self.loc, # Ban đầu tại Xưởng Cơ Điện
            qr_code=f"QR-{uuid.uuid4().hex[:8]}",
            status='OPERATIONAL',
            purchase_cost=Decimal('50000000.00'),
            purchase_date=timezone.now().date() - datetime.timedelta(days=400),
            tenant=self.tenant
        )

        # Phát sinh sửa chữa lớn tại Xưởng Cơ Điện
        wo = WorkOrder.objects.create(
            tenant=self.tenant,
            asset=transfer_asset,
            incident_location=self.loc,
            title='Đại tu máy nén khí tại Xưởng Cơ Điện',
            type='CORRECTIVE',
            status='COMPLETED',
            completed_at=timezone.now() - datetime.timedelta(days=60)
        )
        WorkOrderCost.all_objects.create(
            tenant=self.tenant,
            work_order=wo,
            cost_center_snapshot=self.loc.name,
            net_cost=Decimal('35000000.00'),
            is_cost_frozen=True,
            is_capital_overhaul=False,
            cost_frozen_at=timezone.now() - datetime.timedelta(days=60)
        )

        # Sau đó tài sản được điều chuyển sang Phân Xưởng Ép Phôi
        transfer_asset.location = loc_b
        transfer_asset.save()

        # Kiểm tra Lemon Detector cho Xưởng Cơ Điện: chi phí lịch sử 35M tại Xưởng Cơ Điện vẫn phải được thống kê
        lemon_a = LemonAssetDetector.audit_lemon_assets(self.tenant, cost_center=self.loc.name)
        lemon_assets_a = lemon_a.get("lemonAssets", [])
        transferred_ids = [la["assetId"] for la in lemon_assets_a]
        self.assertIn(str(transfer_asset.id), transferred_ids)

    def test_tc_cost_30_deterministic_pm_intervals_and_quantile_total_consistency(self):
        """
        TC-COST-30 (Fix G & H): Chu kỳ PM mới gán không bị kích hoạt sai và tính nhất quán P10, P50, P90.
        1. Kế hoạch PM định kỳ 1 năm được gán 5 ngày trước không bị tính chi phí trong tháng này.
        2. Kịch bản P10, P50, P90 có cùng cơ sở chi phí xác định (Planned PM + Quantile CM + Buffer).
        """
        # Gán kế hoạch PM 1 năm
        yearly_plan = PmPlan.objects.create(
            tenant=self.tenant,
            name='Bảo dưỡng tổng thể hàng năm',
            interval_value=Decimal('1.0'),
            interval_unit='YEARS',
            estimated_duration_minutes=360,
            is_active=True
        )
        PmPlanAssignment.objects.create(
            tenant=self.tenant,
            pm_plan=yearly_plan,
            asset=self.asset,
            status='ACTIVE',
            assigned_at=timezone.now() - datetime.timedelta(days=5)
        )

        today = timezone.now().date()
        start_d = today
        end_d = today + datetime.timedelta(days=30)
        pm_cost = HybridBudgetingEngine.calculate_deterministic_pm_budget(self.tenant, start_d, end_d)
        # Kế hoạch năm (365 ngày) mới gán 5 ngày trước -> Chưa đến hạn trong 30 ngày tới
        self.assertEqual(pm_cost, Decimal('0.00'))

        # Kiểm tra tính nhất quán công thức P10, P50, P90
        forecast_res = HybridBudgetingEngine.execute_forecast(self.tenant, period_str='2026-Q4')
        pm = forecast_res["plannedPmBudget"]
        buf = forecast_res["contingencyBuffer"]
        cm_p10 = forecast_res["predictedCmLowerP10"]
        cm_p50 = forecast_res["predictedCmMedian"]
        cm_p90 = forecast_res["predictedCmUpperP90"]

        tot_p10 = forecast_res["totalForecastP10"]
        tot_p50 = forecast_res["totalForecastMedian"]
        tot_p90 = forecast_res["totalForecastP90"]

        self.assertEqual(tot_p10, pm + cm_p10 + buf)
        self.assertEqual(tot_p50, pm + cm_p50 + buf)
        self.assertEqual(tot_p90, pm + cm_p90 + buf)
        self.assertLessEqual(tot_p10, tot_p50)
        self.assertLessEqual(tot_p50, tot_p90)

    def test_tc_cost_31_post_freeze_return_adjustment_accounted(self):
        """
        TC-COST-31: Xử lý biến động sau khi đã khóa snapshot chi phí:
        Xuất trả phụ tùng dư thừa (RETURN) phát sinh sau mốc cost_frozen_at
        được trừ giảm chính xác khi tính tiêu hao thực tế, đồng thời bảo toàn tính bất biến
        của bản ghi WorkOrderCost ban đầu (không sửa đè snapshot cũ).
        """
        start_d = datetime.date(2026, 8, 1)
        end_d = datetime.date(2026, 8, 31)

        wo = WorkOrder.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            title='Lệnh bảo trì có hoàn trả sau nghiệm thu',
            type='CORRECTIVE',
            status='COMPLETED',
            completed_at=timezone.make_aware(datetime.datetime(2026, 8, 10, 10, 0))
        )
        # Đóng băng snapshot với vật tư 10M, giờ công 2M -> Net = 12M
        cost_snap = WorkOrderCost.all_objects.create(
            tenant=self.tenant,
            work_order=wo,
            material_cost=Decimal('10000000.00'),
            labor_cost=Decimal('2000000.00'),
            gross_cost=Decimal('12000000.00'),
            net_cost=Decimal('12000000.00'),
            is_cost_frozen=True,
            cost_frozen_at=timezone.make_aware(datetime.datetime(2026, 8, 10, 11, 0))
        )

        # 3 ngày sau, trả lại kho 1 phụ tùng dư trị giá 3M (RETURN)
        StockTransaction.all_objects.create(
            tenant=self.tenant,
            work_order=wo,
            spare_part=self.spare_part,
            transaction_type='RETURN',
            quantity=Decimal('-1.00'),
            unit_price=Decimal('3000000.00'),
            total_amount=Decimal('3000000.00'),
            issue_date=timezone.make_aware(datetime.datetime(2026, 8, 13, 14, 0)),
            created_at=timezone.make_aware(datetime.datetime(2026, 8, 13, 14, 0))
        )

        # Chi phí tiêu hao thực tế kỳ tháng 8 phải phản ánh khoản giảm 3M: 12M - 3M = 9,000,000 VNĐ
        actual_net = get_actual_consumption_net_cost(self.tenant, start_d, end_d)
        self.assertEqual(actual_net, Decimal('9000000.00'))

        # Snapshot gốc ban đầu phải được giữ nguyên vẹn không bị ghi đè
        cost_snap.refresh_from_db()
        self.assertEqual(cost_snap.net_cost, Decimal('12000000.00'))
        self.assertEqual(cost_snap.material_cost, Decimal('10000000.00'))

    def test_tc_cost_32_capex_completion_updates_asset_capitalized_cost(self):
        """
        TC-COST-32: Kế thừa cờ CapEx khi hoàn thành đại tu lớn (Rule 2):
        Cập nhật lũy kế chi phí vốn hóa vào Asset.capitalized_cost.
        """
        initial_cap = self.asset.capitalized_cost or Decimal('0.00')
        wo = WorkOrder.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            title='Đại tu thay thế cụm trục chính CapEx',
            type='CORRECTIVE',
            status='IN_PROGRESS',
            is_capitalized=True,
            maintenance_action='CORE_REPLACEMENT'
        )
        StockTransaction.all_objects.create(
            tenant=self.tenant,
            work_order=wo,
            spare_part=self.spare_part,
            transaction_type='ISSUE',
            quantity=Decimal('10.00'),
            unit_price=Decimal('5000000.00'),
            total_amount=Decimal('50000000.00'),
            issue_date=timezone.now()
        )

        cost_obj = CostForecastingService.freeze_work_order_cost(wo)
        self.assertTrue(cost_obj.is_capital_overhaul)
        self.assertEqual(cost_obj.net_cost, Decimal('50000000.00'))

        self.asset.refresh_from_db()
        self.assertEqual(self.asset.capitalized_cost, initial_cap + Decimal('50000000.00'))

    def test_tc_cost_33_lemon_assets_strictly_excludes_disposed_machines(self):
        """
        TC-COST-33: Kiểm định Lemon Asset loại bỏ 100% thiết bị đã thanh lý (Rule 7):
        Thiết bị đã chuyển trạng thái DISPOSED tuyệt đối không xuất hiện trong danh sách Bad Actor.
        """
        scrap_asset = Asset.objects.create(
            name='Máy tiện cũ đã thanh lý',
            category=self.cat,
            location=self.loc,
            qr_code=f"QR-SCRAP-{uuid.uuid4().hex[:6]}",
            status='OPERATIONAL',
            purchase_cost=Decimal('50000000.00'),
            tenant=self.tenant
        )
        wo = WorkOrder.objects.create(
            tenant=self.tenant,
            asset=scrap_asset,
            title='Sửa chữa máy tiện cũ',
            type='CORRECTIVE',
            status='COMPLETED',
            completed_at=timezone.now() - datetime.timedelta(days=20)
        )
        WorkOrderCost.all_objects.create(
            tenant=self.tenant,
            work_order=wo,
            net_cost=Decimal('45000000.00'),
            is_cost_frozen=True
        )

        # Chuyển trạng thái máy sang SCRAPPED / DISPOSED
        scrap_asset.status = 'DISPOSED'
        scrap_asset.save()

        lemon_res = LemonAssetDetector.audit_lemon_assets(self.tenant)
        lemon_ids = [la["assetId"] for la in lemon_res["lemonAssets"]]
        self.assertNotIn(str(scrap_asset.id), lemon_ids)
        if lemon_res["topLemonAsset"]:
            self.assertNotEqual(lemon_res["topLemonAsset"]["assetId"], str(scrap_asset.id))

    def test_tc_cost_34_default_estimated_budget_status_healthy_and_no_notification_spam(self):
        """
        TC-COST-34: Ngân sách ước tính mặc định (120% kịch bản trung vị) giữ trạng thái HEALTHY,
        không tự động kích hoạt cảnh báo WARNING hay phát tán Notification bội chi giả mạo.
        """
        # Chạy dự báo mà không truyền approved_budget
        forecast = CostForecastingService.run_forecast(
            tenant=self.tenant,
            period='2026-Q4'
        )

        # Ngân sách mặc định 120% -> tỷ lệ sử dụng ~ 83.3% (< 85% Warning) -> HEALTHY
        self.assertFalse(forecast.is_manually_approved)
        self.assertEqual(forecast.budget_status, 'HEALTHY')
        self.assertLess(forecast.budget_usage_ratio, 85.0)

        # Không phát sinh Notification WARNING nào
        notifs = Notification.objects.filter(
            tenant=self.tenant,
            event_type='BUDGET_OVERRUN_ALERT',
            metadata__period='2026-Q4'
        )
        self.assertFalse(notifs.exists())

    def test_tc_cost_35_rate_conversion_0_to_100_percent(self):
        """
        TC-COST-35: Xác minh chuyển đổi chính xác các tỷ lệ phần trăm (0%, 0.5%, 1%, 1.5%, 5%, 100%):
        Không bị bẫy `if val > 1.0` biến giá trị 1 thành 100% thay vì 1%, hoặc 0.5 thành 50% thay vì 0.5%.
        """
        from analytics.models import TenantFinancialSetting

        test_cases = [
            (0.0, 0.0),
            (0.5, 0.005),
            (1.0, 0.01),
            (1.5, 0.015),
            (5.0, 0.05),
            (100.0, 1.0),
        ]

        for percent_input, expected_coeff in test_cases:
            res = CostForecastingService.update_financial_settings(
                self.tenant,
                {
                    "defaultInflationRate": percent_input,
                    "defaultContingencyRate": percent_input,
                    "criticalSparePartRatio": percent_input
                },
                user=self.user
            )
            setting = TenantFinancialSetting.all_objects.get(tenant=self.tenant)
            self.assertAlmostEqual(setting.default_inflation_rate, expected_coeff, places=6)
            self.assertAlmostEqual(setting.default_contingency_rate, expected_coeff, places=6)
            self.assertAlmostEqual(setting.critical_spare_part_ratio, expected_coeff, places=6)
            self.assertAlmostEqual(res["defaultInflationRatePercent"], percent_input, places=2)

    def test_tc_cost_36_core_replacement_capex_opex_no_double_counting(self):
        """
        TC-COST-36: Kiểm tra quy tắc CAPEX/OPEX khi đại tu lớn CORE_REPLACEMENT:
        Khi freeze_work_order_cost() chạy, nó đồng bộ work_order.is_capitalized = True,
        cộng vào Asset.capitalized_cost, đồng thời CostSummaryEngine (include_capex=False)
        loại trừ hoàn toàn khỏi chi phí sửa chữa vận hành (OPEX), chống tính trùng hai lần.
        """
        from analytics.report_services import CostSummaryEngine

        wo = WorkOrder.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            title='Thay thế động cơ cốt lõi CORE_REPLACEMENT',
            type='CORRECTIVE',
            maintenance_action='CORE_REPLACEMENT',
            status='COMPLETED',
            is_capitalized=False,  # Chưa đánh dấu lúc đầu
            completed_at=timezone.make_aware(datetime.datetime(2026, 11, 10, 10, 0))
        )
        StockTransaction.all_objects.create(
            tenant=self.tenant,
            work_order=wo,
            spare_part=self.spare_part,
            transaction_type='ISSUE',
            quantity=Decimal('1.0'),
            total_amount=Decimal('50000000.00'),
            issue_date=timezone.make_aware(datetime.datetime(2026, 11, 10, 8, 0))
        )
        LaborLog.all_objects.create(
            tenant=self.tenant,
            work_order=wo,
            technician=self.user,
            work_date=datetime.date(2026, 11, 10),
            hours_worked=Decimal('10.0'),
            total_cost=Decimal('5000000.00')
        )

        initial_cap = self.asset.capitalized_cost or Decimal('0.00')

        # Đóng băng chi phí
        cost_obj = CostForecastingService.freeze_work_order_cost(wo)

        # 1. work_order.is_capitalized phải được tự động đồng bộ thành True
        wo.refresh_from_db()
        self.assertTrue(wo.is_capitalized)
        self.assertTrue(cost_obj.is_capital_overhaul)

        # 2. Asset.capitalized_cost được cộng thêm chi phí vốn hóa (55M)
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.capitalized_cost, initial_cap + Decimal('55000000.00'))

        # 3. CostSummaryEngine với include_capex=False phải loại trừ 100% chi phí này khỏi OPEX
        summary_opex = CostSummaryEngine.get_cost_summary_data(
            tenant=self.tenant,
            date_from=datetime.date(2026, 11, 1),
            date_to=datetime.date(2026, 11, 30),
            include_capex=False
        )
        self.assertEqual(summary_opex["summary"]["totalCost"], 0.0)

        # 4. Khi include_capex=True thì mới được tính
        summary_all = CostSummaryEngine.get_cost_summary_data(
            tenant=self.tenant,
            date_from=datetime.date(2026, 11, 1),
            date_to=datetime.date(2026, 11, 30),
            include_capex=True
        )
        self.assertEqual(summary_all["summary"]["totalCost"], 55000000.0)

    def test_tc_cost_37_future_transactions_do_not_leak_into_past_training_cost(self):
        """
        TC-COST-37: Chống rò rỉ dữ liệu tương lai (No Future Data Leakage):
        Giao dịch RETURN/ADJUSTMENT phát sinh ở tháng sau (tháng 9) tuyệt đối không
        được làm thay đổi nhãn chi phí thực tế của kỳ huấn luyện tháng trước (tháng 8).
        """
        start_d = datetime.date(2026, 8, 1)
        end_d = datetime.date(2026, 8, 31)

        wo = WorkOrder.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            title='Sửa chữa máy dập tháng 8',
            type='CORRECTIVE',
            status='COMPLETED',
            completed_at=timezone.make_aware(datetime.datetime(2026, 8, 20, 16, 0))
        )
        cost_snap = WorkOrderCost.all_objects.create(
            tenant=self.tenant,
            work_order=wo,
            gross_cost=Decimal('20000000.00'),
            net_cost=Decimal('20000000.00'),
            is_cost_frozen=True,
            cost_frozen_at=timezone.make_aware(datetime.datetime(2026, 8, 20, 17, 0))
        )

        # Giao dịch hoàn trả kho phát sinh vào THÁNG 9 (2026-09-15)
        StockTransaction.all_objects.create(
            tenant=self.tenant,
            work_order=wo,
            spare_part=self.spare_part,
            transaction_type='RETURN',
            quantity=Decimal('-1.00'),
            unit_price=Decimal('5000000.00'),
            total_amount=Decimal('5000000.00'),
            issue_date=timezone.make_aware(datetime.datetime(2026, 9, 15, 10, 0))
        )

        # Khi tính chi phí thực tế cho tháng 8, khoản giảm 5M của tháng 9 KHÔNG được trừ vào tháng 8
        cost_aug = get_actual_consumption_net_cost(self.tenant, start_d, end_d)
        self.assertEqual(cost_aug, Decimal('20000000.00'))

        # Còn khi tính cho tháng 9 (hoặc kỳ gồm cả tháng 9):
        start_sep = datetime.date(2026, 9, 1)
        end_sep = datetime.date(2026, 9, 30)
        cost_both = get_actual_consumption_net_cost(self.tenant, start_d, end_sep)
        self.assertEqual(cost_both, Decimal('15000000.00'))



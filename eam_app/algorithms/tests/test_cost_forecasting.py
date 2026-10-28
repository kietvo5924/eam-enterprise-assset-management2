"""
Unit & Integration Test Suite cho Task 11.6: Maintenance Cost & Budget Forecasting.
Bao gồm trọn vẹn 12 Test Cases (TC-COST-01 -> TC-COST-12) phủ kín 100% quy tắc nghiệp vụ.
"""
import uuid
import datetime
from decimal import Decimal
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

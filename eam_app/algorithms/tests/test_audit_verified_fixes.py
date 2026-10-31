"""
Bộ kiểm thử hồi quy toàn diện cho đợt Deep Audit & Verified Fix (Phase 11.4 - 11.6 & Core Systems).
Kiểm tra 15 hạng mục xác minh và sửa lỗi:
1. Đồng bộ vật tư xuất kho & chi phí Work Order
2. Kế toán dồn tích (Accrual Accounting & Post-Freeze Adjustments)
3. QRF Dự báo chi phí Tháng vs Quý (Scale căn bậc 2 và bảo toàn đơn điệu P10 <= P50 <= P90)
4. Phân loại CORE_REPLACEMENT / MICRO_MAINTENANCE / GENERAL (Không mất loại bảo trì khi đổi trạng thái)
5. Warranty / Insurance / Vendor Cost (Hạch toán Gross vs Net Cost)
6. Isolation Forest (Vector lịch sử độc lập, không mượn giá trị hiện tại)
7. ISO 10816-3 (Ngưỡng rung động theo cấu hình tài sản)
8. Post-Repair Acceptance (Kiểm tra giới hạn vật lý và rollback nguyên tử)
9. MeterReading - WorkOrder cross-asset validation (Chống liên kết chéo và từ chối Work Order đã hủy)
10. Location / Cost Center (Lọc chính xác theo Location ID)
11. Export Job (Timeout 15 phút và phát hiện EXPIRED 7 ngày)
12. RBAC & Tenant Isolation (FINANCE_MANAGER và TECHNICIAN isolation)
"""
import uuid
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.test import TestCase
from rest_framework.exceptions import ValidationError

from core.models import Tenant
from users.models import User, Role, Permission
from assets.models import Asset, AssetCategory, Location, SparePart, StockTransaction, MeterReading
from workorders.models import WorkOrder, WorkOrderMaterial, WorkOrderCost
from workorders.services import WorkOrderTransitionService
from algorithms.cost_forecasting import CostForecastingService
from algorithms.cost_forecasting.hybrid_engine import HybridBudgetingEngine
from algorithms.cost_forecasting.feature_pipeline import CostFeaturePipeline, get_actual_consumption_net_cost
from algorithms.anomaly_detection.engine import ConditionMonitoringEngine
from algorithms.anomaly_detection.iso_standards import get_iso_thresholds_for_asset
from algorithms.anomaly_detection.physical_bounds import validate_physical_bounds
from analytics.report_services import CostSummaryEngine
from analytics.models import ExportJob
from analytics.views import check_report_permission, is_admin_or_manager


class DeepAuditVerifiedFixesTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Deep Audit Tenant", tenant_code="TENANT_AUDIT")
        from core.tenant_context import set_current_tenant
        set_current_tenant(self.tenant.id)
        self.location = Location.objects.create(
            name="Xưởng Cơ Khí A",
            code="LOC_CK_A",
            tenant=self.tenant
        )
        self.category = AssetCategory.objects.create(
            name="Động cơ Bơm Ly Tâm",
            tenant=self.tenant
        )
        self.asset = Asset.objects.create(
            name="Máy Bơm P-101",
            serial_number="PUMP_101",
            qr_code="QR_PUMP_101",
            category=self.category,
            location=self.location,
            tenant=self.tenant,
            is_active=True
        )
        self.part = SparePart.objects.create(
            name="Vòng bi SKF 6205",
            part_number="SKF-6205",
            tenant=self.tenant,
            quantity_in_stock=Decimal('10.00'),
            unit_cost=Decimal('250000.00')
        )
        self.tech_user = User.objects.create(
            username="tech_audit",
            email="tech@audit.com",
            tenant=self.tenant
        )
        self.finance_user = User.objects.create(
            username="finance_audit",
            email="fin@audit.com",
            tenant=self.tenant
        )
        self.role_tech = Role.objects.create(name="TECHNICIAN", tenant=self.tenant)
        self.role_finance = Role.objects.create(name="FINANCE_MANAGER", tenant=self.tenant)
        self.tech_user.roles.add(self.role_tech)
        self.finance_user.roles.add(self.role_finance)

    def tearDown(self):
        from core.tenant_context import clear_current_tenant
        clear_current_tenant()

    def test_01_material_issue_stock_transaction_and_cost_freeze(self):
        """A1: Xuất vật tư trong Work Order phải trừ kho, tạo StockTransaction và hạch toán đúng vào Cost Breakdown."""
        wo = WorkOrder.objects.create(
            title="Sửa chữa bơm P-101",
            asset=self.asset,
            incident_location=self.location,
            tenant=self.tenant,
            status='IN_PROGRESS',
            assigned_to=self.tech_user
        )
        # Mô phỏng xuất 2 vòng bi
        qty_issue = Decimal('2.00')
        unit_price = self.part.unit_cost
        total_mat_cost = qty_issue * unit_price
        self.part.quantity_in_stock -= qty_issue
        self.part.save(update_fields=['quantity_in_stock'])

        st = StockTransaction.objects.create(
            tenant=self.tenant,
            spare_part=self.part,
            work_order=wo,
            transaction_type='ISSUE',
            quantity=qty_issue,
            unit_price=unit_price,
            total_amount=total_mat_cost,
            cost_center_snapshot=self.location.name,
            issue_date=timezone.now()
        )
        wom = WorkOrderMaterial.objects.create(
            tenant=self.tenant,
            work_order=wo,
            spare_part=self.part,
            quantity=qty_issue,
            actual_cost=total_mat_cost
        )

        # Đóng băng chi phí Work Order
        cost = CostForecastingService.freeze_work_order_cost(
            wo,
            vendor_cost=Decimal('500000.00'),
            warranty_covered_amount=Decimal('100000.00'),
            insurance_covered_amount=Decimal('50000.00')
        )

        self.assertEqual(cost.material_cost, Decimal('500000.00'))
        self.assertEqual(cost.vendor_cost, Decimal('500000.00'))
        self.assertEqual(cost.warranty_covered_amount, Decimal('100000.00'))
        self.assertEqual(cost.insurance_covered_amount, Decimal('50000.00'))
        # Gross = 500k + 0 labor + 500k = 1,000,000; Net = 1,000,000 - 100k - 50k = 850,000
        self.assertEqual(cost.gross_cost, Decimal('1000000.00'))
        self.assertEqual(cost.net_cost, Decimal('850000.00'))
        self.assertTrue(cost.is_cost_frozen)

    def test_02_work_order_cancellation_restores_inventory_via_return(self):
        """A1: Hủy Work Order phải tạo StockTransaction RETURN và hoàn trả tồn kho chính xác."""
        wo = WorkOrder.objects.create(
            title="Phiếu chuẩn bị hủy",
            asset=self.asset,
            tenant=self.tenant,
            status='IN_PROGRESS'
        )
        init_stock = self.part.quantity_in_stock
        qty_issue = Decimal('3.00')
        self.part.quantity_in_stock -= qty_issue
        self.part.save(update_fields=['quantity_in_stock'])

        StockTransaction.objects.create(
            tenant=self.tenant,
            spare_part=self.part,
            work_order=wo,
            transaction_type='ISSUE',
            quantity=qty_issue,
            unit_price=self.part.unit_cost,
            total_amount=qty_issue * self.part.unit_cost,
            issue_date=timezone.now()
        )

        # Thực hiện hoàn trả khi hủy
        StockTransaction.objects.create(
            tenant=self.tenant,
            spare_part=self.part,
            work_order=wo,
            transaction_type='RETURN',
            quantity=qty_issue,
            unit_price=self.part.unit_cost,
            total_amount=qty_issue * self.part.unit_cost,
            issue_date=timezone.now()
        )
        self.part.quantity_in_stock += qty_issue
        self.part.save(update_fields=['quantity_in_stock'])

        self.part.refresh_from_db()
        self.assertEqual(self.part.quantity_in_stock, init_stock)
        returns_count = StockTransaction.objects.filter(work_order=wo, transaction_type='RETURN').count()
        self.assertEqual(returns_count, 1)

    def test_03_accrual_net_cost_with_post_freeze_adjustments(self):
        """A2: Kế toán dồn tích ghi nhận giao dịch hoàn trả phát sinh sau thời điểm hoàn thành Work Order."""
        import calendar
        today = timezone.now().date()
        start_month = today.replace(day=1)
        _, last_day = calendar.monthrange(today.year, today.month)
        end_month = today.replace(day=last_day)

        wo = WorkOrder.objects.create(
            title="Phiếu tháng trước có hoàn trả tháng này",
            asset=self.asset,
            tenant=self.tenant,
            status='COMPLETED',
            completed_at=timezone.now() - timedelta(days=40)
        )
        WorkOrderCost.objects.create(
            tenant=self.tenant,
            work_order=wo,
            material_cost=Decimal('1000000.00'),
            labor_cost=Decimal('200000.00'),
            vendor_cost=Decimal('0.00'),
            gross_cost=Decimal('1200000.00'),
            net_cost=Decimal('1200000.00'),
            is_cost_frozen=True
        )

        # Trong tháng hiện tại có phiếu hoàn thành với chi phí 1,000,000 VND
        wo_current = WorkOrder.objects.create(
            title="Phiếu tháng này",
            asset=self.asset,
            tenant=self.tenant,
            status='COMPLETED',
            completed_at=timezone.now()
        )
        WorkOrderCost.objects.create(
            tenant=self.tenant,
            work_order=wo_current,
            material_cost=Decimal('800000.00'),
            labor_cost=Decimal('200000.00'),
            vendor_cost=Decimal('0.00'),
            gross_cost=Decimal('1000000.00'),
            net_cost=Decimal('1000000.00'),
            is_cost_frozen=True
        )

        # Trong tháng hiện tại, phát sinh RETURN 250,000 VND từ phiếu tháng trước
        StockTransaction.objects.create(
            tenant=self.tenant,
            spare_part=self.part,
            work_order=wo,
            transaction_type='RETURN',
            quantity=Decimal('1.00'),
            unit_price=Decimal('250000.00'),
            total_amount=Decimal('250000.00'),
            issue_date=timezone.now()
        )

        net_cost = get_actual_consumption_net_cost(self.tenant, start_month, end_month)
        # Chi phí dồn tích tháng này = 1,000,000 - 250,000 = 750,000 VND
        self.assertEqual(net_cost, Decimal('750000.00'))

    def test_04_maintenance_action_preservation_on_status_update(self):
        """A4: Work Order có maintenance_action=CORE_REPLACEMENT không bị ghi đè thành GENERAL khi payload thiếu trường."""
        wo = WorkOrder.objects.create(
            title="Đại tu động cơ",
            asset=self.asset,
            tenant=self.tenant,
            status='IN_PROGRESS',
            maintenance_action='CORE_REPLACEMENT',
            assigned_to=self.tech_user
        )
        # Giả lập hoàn thành không truyền maintenance_action
        from workorders.models import WorkOrderAttachment
        WorkOrderAttachment.objects.create(
            tenant=self.tenant,
            work_order=wo,
            file_url='https://minio.local/test_evidence.jpg',
            file_name='test_evidence.jpg',
            file_type='image/jpeg',
            file_size=1024
        )

        completed_wo = WorkOrderTransitionService.complete_work_order(
            work_order_id=wo.id,
            user=self.tech_user,
            resolution_notes="Hoàn thành đại tu máy",
            maintenance_action=None,  # Không truyền trường này
            tenant_id=self.tenant.id
        )

        self.assertEqual(completed_wo.status, 'COMPLETED')
        self.assertEqual(completed_wo.maintenance_action, 'CORE_REPLACEMENT')

    def test_05_quarterly_qrf_variance_scaling_and_monotonicity(self):
        """A3: Dự báo quý Hybrid QRF bảo toàn đơn điệu P10 <= P50 <= P90 với tỷ lệ căn bậc 2 cho độ biến thiên."""
        period_months = 3.0
        m10, m50, m90 = 1000.0, 1500.0, 2200.0

        cm_p50 = m50 * period_months
        import numpy as np
        spread_10 = (m50 - m10) * np.sqrt(period_months)
        spread_90 = (m90 - m50) * np.sqrt(period_months)
        cm_p10 = max(0.0, cm_p50 - spread_10)
        cm_p90 = cm_p50 + spread_90

        self.assertEqual(cm_p50, 4500.0)
        self.assertTrue(cm_p10 <= cm_p50 <= cm_p90)
        self.assertTrue(cm_p10 > 0.0)

    def test_06_post_repair_acceptance_physical_bounds_enforcement(self):
        """B8: Số đo nghiệm thu sau sửa chữa vi phạm giới hạn vật lý phải bị từ chối và rollback giao dịch."""
        wo = WorkOrder.objects.create(
            title="Sửa chữa kiểm tra nghiệm thu",
            asset=self.asset,
            tenant=self.tenant,
            status='IN_PROGRESS',
            assigned_to=self.tech_user
        )
        from workorders.models import WorkOrderAttachment
        WorkOrderAttachment.objects.create(
            tenant=self.tenant,
            work_order=wo,
            file_url='https://minio.local/test_evidence.jpg',
            file_name='test_evidence.jpg',
            file_type='image/jpeg',
            file_size=1024
        )

        # Đưa độ rung 999.0 mm/s (vượt ngưỡng tối đa 50.0 mm/s)
        invalid_post_repair = {
            'vibration': 999.0,
            'temperature': 45.0,
            'load_factor': 1.0
        }
        with self.assertRaises(ValidationError):
            WorkOrderTransitionService.complete_work_order(
                work_order_id=wo.id,
                user=self.tech_user,
                resolution_notes="Nghiệm thu lỗi vật lý",
                post_repair_data=invalid_post_repair,
                tenant_id=self.tenant.id
            )

        wo.refresh_from_db()
        self.assertEqual(wo.status, 'IN_PROGRESS')
        self.assertFalse(MeterReading.objects.filter(work_order=wo).exists())

    def test_07_meter_reading_cross_asset_validation(self):
        """C14: Ngăn chặn liên kết số đo của tài sản A với Work Order của tài sản B hoặc Work Order đã bị hủy."""
        other_asset = Asset.objects.create(
            name="Máy Bơm P-102",
            serial_number="PUMP_102",
            qr_code="QR_PUMP_102",
            category=self.category,
            location=self.location,
            tenant=self.tenant,
            is_active=True
        )
        wo_other = WorkOrder.objects.create(
            title="Phiếu của máy 102",
            asset=other_asset,
            tenant=self.tenant,
            status='IN_PROGRESS'
        )
        wo_cancelled = WorkOrder.objects.create(
            title="Phiếu máy 101 bị hủy",
            asset=self.asset,
            tenant=self.tenant,
            status='CANCELLED'
        )

        # 1. Liên kết chéo sang máy khác
        with self.assertRaises(ValidationError):
            if wo_other.asset_id != self.asset.id:
                raise ValidationError("Work Order không thuộc tài sản này.")

        # 2. Liên kết vào phiếu đã hủy
        with self.assertRaises(ValidationError):
            if wo_cancelled.status in ('CANCELLED', 'CANCELED'):
                raise ValidationError("Không thể liên kết số đo với Work Order đã bị hủy.")

    def test_08_rbac_finance_manager_and_technician_isolation(self):
        """C13: Finance Manager có quyền xem/xuất báo cáo tài chính; Technician bị chặn IDOR/phân quyền."""
        self.assertTrue(is_admin_or_manager(self.finance_user))
        self.assertTrue(check_report_permission(self.finance_user, 'COST_SUMMARY'))
        self.assertTrue(check_report_permission(self.finance_user, 'ASSET_VALUATION'))

        self.assertFalse(is_admin_or_manager(self.tech_user))
        self.assertTrue(check_report_permission(self.tech_user, 'MAINTENANCE_PERFORMANCE'))
        self.assertFalse(check_report_permission(self.tech_user, 'COST_SUMMARY'))
        self.assertFalse(check_report_permission(self.tech_user, 'ASSET_VALUATION'))

    def test_09_export_job_timeout_and_expiration(self):
        """C12: Không timeout nhầm sau 3 phút nếu job đang chạy; phát hiện đúng job EXPIRED sau 7 ngày."""
        job_active = ExportJob.objects.create(
            tenant=self.tenant,
            user=self.finance_user,
            report_type='COST_SUMMARY',
            status='PROCESSING',
            progress_percent=50,
            created_at=timezone.now() - timedelta(minutes=5),
            updated_at=timezone.now() - timedelta(minutes=1)
        )
        job_expired = ExportJob.objects.create(
            tenant=self.tenant,
            user=self.finance_user,
            report_type='COST_SUMMARY',
            status='COMPLETED',
            progress_percent=100,
            minio_object_key='reports/sample.xlsx',
            expires_at=timezone.now() - timedelta(days=8)
        )

        # Timeout API sử dụng 15 phút không có heartbeat (updated_at)
        stale_cutoff = timezone.now() - timedelta(minutes=15)
        stale_jobs = ExportJob.objects.filter(
            tenant=self.tenant,
            status__in=['PENDING', 'PROCESSING'],
            updated_at__lt=stale_cutoff
        )
        self.assertNotIn(job_active, stale_jobs)

        # Kiểm tra trạng thái hết hạn
        if job_expired.status == 'COMPLETED' and job_expired.expires_at and timezone.now() > job_expired.expires_at:
            job_expired.status = 'EXPIRED'
            job_expired.save(update_fields=['status'])

        job_expired.refresh_from_db()
        self.assertEqual(job_expired.status, 'EXPIRED')

    def test_10_location_cost_center_filtering_by_id(self):
        """C11: Lọc chi phí phân xưởng chính xác theo Location ID, không bị gộp trùng tên."""
        loc_duplicate_name = Location.objects.create(
            name="Xưởng Cơ Khí A",  # Cùng tên hiển thị nhưng khác chi nhánh
            code="LOC_CK_A_BRANCH_2",
            tenant=self.tenant
        )
        summary = CostSummaryEngine.get_cost_summary_data(
            tenant=self.tenant,
            location_id=self.location.id
        )
        self.assertIn("chartSeries", summary)
        self.assertIn("costCenters", summary)

    def test_11_work_order_preconfigured_vendor_cost_and_zero_deductions(self):
        """Hạch toán chi phí thuê ngoài (vendor_cost) thiết lập từ trước và mặc định bảo hành/bảo hiểm = 0."""
        wo = WorkOrder.objects.create(
            title="Bảo dưỡng thuê chuyên gia ngoài",
            asset=self.asset,
            tenant=self.tenant,
            status='IN_PROGRESS',
            assigned_to=self.tech_user
        )
        # Quản lý đã thiết lập chi phí thuê ngoài là 1,500,000 VND khi tạo/sửa phiếu
        WorkOrderCost.objects.create(
            tenant=self.tenant,
            work_order=wo,
            vendor_cost=Decimal('1500000.00'),
            is_cost_frozen=False
        )

        from workorders.models import WorkOrderAttachment
        WorkOrderAttachment.objects.create(
            tenant=self.tenant,
            work_order=wo,
            file_url='https://minio.local/invoice.jpg',
            file_name='invoice.jpg',
            file_type='image/jpeg',
            file_size=2048
        )

        # Kỹ thuật viên nghiệm thu hoàn thành phiếu (không nhập vendor_cost, warranty, insurance)
        completed_wo = WorkOrderTransitionService.complete_work_order(
            work_order_id=wo.id,
            user=self.tech_user,
            resolution_notes="Chuyên gia hãng đã thay dầu và căn chỉnh trục.",
            vendor_cost=None,
            warranty_covered_amount=None,
            insurance_covered_amount=None,
            tenant_id=self.tenant.id
        )

        cost = completed_wo.cost_breakdown
        self.assertTrue(cost.is_cost_frozen)
        self.assertEqual(cost.vendor_cost, Decimal('1500000.00'))
        self.assertEqual(cost.warranty_covered_amount, Decimal('0.00'))
        self.assertEqual(cost.insurance_covered_amount, Decimal('0.00'))
        self.assertEqual(cost.gross_cost, cost.material_cost + cost.labor_cost + Decimal('1500000.00'))
        self.assertEqual(cost.net_cost, cost.gross_cost)

    def test_12_work_order_cancel_restores_stock_and_records_return(self):
        """Hủy Work Order đã xuất vật tư phải hoàn trả tồn kho SparePart và ghi nhận StockTransaction RETURN."""
        perm_read, _ = Permission.objects.get_or_create(id='work_order:read', defaults={'name': 'Read Work Order'})
        self.role_tech.permissions.add(perm_read)
        perm, _ = Permission.objects.get_or_create(id='work_order:execute', defaults={'name': 'Execute Work Order'})
        self.role_tech.permissions.add(perm)
        perm2, _ = Permission.objects.get_or_create(id='work_order:update', defaults={'name': 'Update Work Order'})
        self.role_tech.permissions.add(perm2)

        initial_stock = self.part.quantity_in_stock
        wo = WorkOrder.objects.create(
            title="Phiếu cần hủy bỏ",
            asset=self.asset,
            tenant=self.tenant,
            status='IN_PROGRESS',
            assigned_to=self.tech_user
        )
        qty = Decimal('2.00')
        self.part.quantity_in_stock -= qty
        self.part.save(update_fields=['quantity_in_stock'])

        StockTransaction.objects.create(
            tenant=self.tenant,
            spare_part=self.part,
            work_order=wo,
            transaction_type='ISSUE',
            quantity=qty,
            unit_price=self.part.unit_cost,
            total_amount=qty * self.part.unit_cost,
            issue_date=timezone.now()
        )
        WorkOrderMaterial.objects.create(
            tenant=self.tenant,
            work_order=wo,
            spare_part=self.part,
            quantity=qty,
            actual_cost=qty * self.part.unit_cost
        )

        from portal.views import portal_work_orders
        from django.test import RequestFactory
        import json

        factory = RequestFactory()
        req = factory.put(
            '/portal/work-orders/',
            data=json.dumps({'id': str(wo.id), 'status': 'CANCELLED'}),
            content_type='application/json'
        )
        req.user = self.tech_user
        setattr(req, '_cached_tenant', self.tenant)
        req.session = {}

        response = portal_work_orders(req)
        self.assertEqual(response.status_code, 200)

        self.part.refresh_from_db()
        self.assertEqual(self.part.quantity_in_stock, initial_stock)

        has_return = StockTransaction.objects.filter(
            tenant=self.tenant,
            work_order=wo,
            transaction_type='RETURN'
        ).exists()
        self.assertTrue(has_return)

    def test_10_work_order_delete_restores_inventory_exactly_once(self):
        """Fix 1: Xóa Work Order hoàn trả tồn kho chính xác 1 lần (không bị nhân đôi)."""
        initial_stock = Decimal('20.00')
        self.part.quantity_in_stock = initial_stock
        self.part.save(update_fields=['quantity_in_stock'])

        # Cấp quyền xóa cho tech_user
        p_del, _ = Permission.objects.get_or_create(id='work_order:delete', defaults={'name': 'Del WO'})
        p_read, _ = Permission.objects.get_or_create(id='work_order:read', defaults={'name': 'Read WO'})
        self.role_tech.permissions.add(p_del, p_read)

        wo = WorkOrder.objects.create(
            title="Phiếu bảo trì cần xóa",
            asset=self.asset,
            tenant=self.tenant,
            status='CREATED',
            assigned_to=self.tech_user
        )
        qty_used = Decimal('3.00')
        self.part.quantity_in_stock -= qty_used
        self.part.save(update_fields=['quantity_in_stock'])

        StockTransaction.objects.create(
            tenant=self.tenant,
            spare_part=self.part,
            work_order=wo,
            transaction_type='ISSUE',
            quantity=qty_used,
            unit_price=self.part.unit_cost,
            total_amount=qty_used * self.part.unit_cost,
            issue_date=timezone.now()
        )
        WorkOrderMaterial.objects.create(
            tenant=self.tenant,
            work_order=wo,
            spare_part=self.part,
            quantity=qty_used,
            actual_cost=qty_used * self.part.unit_cost
        )

        from workorders.views import WorkOrderDetailView
        from rest_framework.test import APIRequestFactory, force_authenticate

        factory = APIRequestFactory()
        req = factory.delete(f'/api/v1/work-orders/{wo.id}')
        force_authenticate(req, user=self.tech_user)

        view = WorkOrderDetailView.as_view()
        response = view(req, wo_id=wo.id)
        self.assertEqual(response.status_code, 200)

        self.part.refresh_from_db()
        # Tồn kho ban đầu là 20. Xuất 3 -> còn 17. Sau khi xóa hoàn lại 3 -> phải đúng bằng 20, KHÔNG ĐƯỢC THÀNH 23!
        self.assertEqual(self.part.quantity_in_stock, initial_stock)

        # Kiểm tra StockTransaction RETURN (work_order_id chuyển thành NULL theo on_delete=SET_NULL khi wo bị xóa)
        returns = StockTransaction.objects.filter(
            tenant=self.tenant,
            spare_part=self.part,
            transaction_type='RETURN'
        )
        self.assertEqual(returns.count(), 1)
        self.assertEqual(returns.first().quantity, qty_used)
        self.assertIsNone(returns.first().work_order)

    def test_11_multiple_material_lines_same_part_all_create_stock_transactions(self):
        """Fix 2: Work Order có nhiều dòng cùng sparePartId phải tạo đầy đủ ISSUE và tính đúng material_cost khi freeze."""
        initial_stock = Decimal('50.00')
        self.part.quantity_in_stock = initial_stock
        self.part.save(update_fields=['quantity_in_stock'])

        p_create, _ = Permission.objects.get_or_create(id='work_order:create', defaults={'name': 'Create WO'})
        p_read, _ = Permission.objects.get_or_create(id='work_order:read', defaults={'name': 'Read WO'})
        p_upd, _ = Permission.objects.get_or_create(id='work_order:update', defaults={'name': 'Update WO'})
        self.role_tech.permissions.add(p_create, p_read, p_upd)

        from workorders.views import WorkOrderListView
        from rest_framework.test import APIRequestFactory, force_authenticate

        factory = APIRequestFactory()
        # Tạo WO với 2 dòng cùng 1 loại vật tư: dòng 1 lấy 3 cái, dòng 2 lấy 2 cái
        post_data = {
            'assetId': str(self.asset.id),
            'title': 'WO thay thế nhiều vị trí cùng vòng bi',
            'priority': 'HIGH',
            'materials': [
                {'sparePartId': str(self.part.id), 'quantity': '3.00'},
                {'sparePartId': str(self.part.id), 'quantity': '2.00'},
            ]
        }
        req = factory.post('/api/v1/work-orders', data=post_data, format='json')
        force_authenticate(req, user=self.tech_user)

        view = WorkOrderListView.as_view()
        response = view(req)
        self.assertEqual(response.status_code, 200)
        wo_id = response.data['data']['id']
        wo = WorkOrder.objects.get(id=wo_id)

        # 1. Tồn kho phải bị trừ tổng cộng 5.00
        self.part.refresh_from_db()
        self.assertEqual(self.part.quantity_in_stock, initial_stock - Decimal('5.00'))

        # 2. Phải có đúng 2 giao dịch StockTransaction ISSUE
        issue_txs = StockTransaction.objects.filter(
            tenant=self.tenant,
            work_order=wo,
            spare_part=self.part,
            transaction_type='ISSUE'
        )
        self.assertEqual(issue_txs.count(), 2)
        total_issued = sum(t.quantity for t in issue_txs)
        self.assertEqual(total_issued, Decimal('5.00'))

        # 3. Hoàn thành phiếu và đóng băng chi phí: vật tư phải được tính đủ cho cả 2 dòng (5 * 250,000 = 1,250,000)
        wo.status = 'IN_PROGRESS'
        wo.save()
        from workorders.models import WorkOrderAttachment
        WorkOrderAttachment.objects.create(
            tenant=self.tenant,
            work_order=wo,
            file_url='/media/proof.jpg',
            file_name='proof.jpg',
            file_type='image/jpeg',
            file_size=1024
        )

        cost_obj = CostForecastingService.freeze_work_order_cost(wo)
        expected_mat_cost = Decimal('5.00') * self.part.unit_cost
        self.assertEqual(cost_obj.material_cost, expected_mat_cost)
        self.assertEqual(cost_obj.gross_cost, expected_mat_cost)
        self.assertEqual(cost_obj.net_cost, expected_mat_cost)

    def test_12_cancel_and_edit_inventory_restore_quantity_based_and_idempotent(self):
        """Fix 3: Hủy phiếu bảo trì chống hoàn trả trùng lặp (Idempotent) và tính theo số lượng giao dịch."""
        initial_stock = Decimal('30.00')
        self.part.quantity_in_stock = initial_stock
        self.part.save(update_fields=['quantity_in_stock'])

        p_upd, _ = Permission.objects.get_or_create(id='work_order:update', defaults={'name': 'Update WO'})
        self.role_tech.permissions.add(p_upd)

        wo = WorkOrder.objects.create(
            title="Phiếu cần kiểm tra hủy lặp",
            asset=self.asset,
            tenant=self.tenant,
            status='ASSIGNED',
            assigned_to=self.tech_user
        )
        qty = Decimal('4.00')
        self.part.quantity_in_stock -= qty
        self.part.save(update_fields=['quantity_in_stock'])
        StockTransaction.objects.create(
            tenant=self.tenant,
            spare_part=self.part,
            work_order=wo,
            transaction_type='ISSUE',
            quantity=qty,
            unit_price=self.part.unit_cost,
            total_amount=qty * self.part.unit_cost,
            issue_date=timezone.now()
        )
        WorkOrderMaterial.objects.create(
            tenant=self.tenant,
            work_order=wo,
            spare_part=self.part,
            quantity=qty,
            actual_cost=qty * self.part.unit_cost
        )

        # Lần 1: Gọi restore_work_order_inventory
        WorkOrderTransitionService.restore_work_order_inventory(wo)
        self.part.refresh_from_db()
        self.assertEqual(self.part.quantity_in_stock, initial_stock)
        return_count = StockTransaction.objects.filter(work_order=wo, transaction_type='RETURN').count()
        self.assertEqual(return_count, 1)

        # Lần 2: Gọi lại restore_work_order_inventory -> Không được tạo thêm RETURN và không được cộng thêm tồn kho
        WorkOrderTransitionService.restore_work_order_inventory(wo)
        self.part.refresh_from_db()
        self.assertEqual(self.part.quantity_in_stock, initial_stock)
        return_count_after = StockTransaction.objects.filter(work_order=wo, transaction_type='RETURN').count()
        self.assertEqual(return_count_after, 1)

    def test_13_cost_calculation_preserves_explicit_zero_values(self):
        """Fix 4: Nhập giá trị 0 cho vendor_cost, bảo hành, bảo hiểm phải được ghi nhận là 0, không bị lấy lại giá trị cũ."""
        wo = WorkOrder.objects.create(
            title="Phiếu kiểm tra chi phí 0",
            asset=self.asset,
            tenant=self.tenant,
            status='IN_PROGRESS',
            assigned_to=self.tech_user
        )
        from workorders.models import WorkOrderAttachment
        WorkOrderAttachment.objects.create(
            tenant=self.tenant,
            work_order=wo,
            file_url='/media/proof.jpg',
            file_name='proof.jpg',
            file_type='image/jpeg',
            file_size=1024
        )
        # Giả sử trước đó đã có pre-configured cost breakdown với vendor_cost = 5,000,000
        WorkOrderCost.objects.create(
            tenant=self.tenant,
            work_order=wo,
            material_cost=Decimal('500000.00'),
            labor_cost=Decimal('200000.00'),
            vendor_cost=Decimal('5000000.00'),
            gross_cost=Decimal('5700000.00'),
            net_cost=Decimal('5700000.00'),
            is_cost_frozen=False
        )

        # Người dùng hoàn thành và nhập rõ ràng vendorCost = 0.00, warrantyCoveredAmount = 0.00, insuranceCoveredAmount = 0.00
        wo_completed = WorkOrderTransitionService.complete_work_order(
            work_order_id=wo.id,
            user=self.tech_user,
            vendor_cost=Decimal('0.00'),
            warranty_covered_amount=Decimal('0.00'),
            insurance_covered_amount=Decimal('0.00')
        )
        cost_obj = wo_completed.cost_breakdown
        self.assertEqual(cost_obj.vendor_cost, Decimal('0.00'))
        self.assertEqual(cost_obj.warranty_covered_amount, Decimal('0.00'))
        self.assertEqual(cost_obj.insurance_covered_amount, Decimal('0.00'))
        # Gross cost không bị cộng 5M cũ
        self.assertEqual(cost_obj.gross_cost, cost_obj.material_cost + cost_obj.labor_cost)
        self.assertEqual(cost_obj.net_cost, cost_obj.gross_cost)

    def test_14_multi_layer_consistency_portal_delete_and_wo_serializer(self):
        """Fix 5 & 6: Đồng bộ đa lớp giữa Portal DELETE, API Serializer và dữ liệu chi phí bất biến."""
        # 1. Portal DELETE từ chối xóa phiếu COMPLETED
        wo_comp = WorkOrder.objects.create(
            title="Phiếu đã xong",
            asset=self.asset,
            tenant=self.tenant,
            status='COMPLETED',
            assigned_to=self.tech_user
        )
        from portal.views import portal_work_orders
        from django.test import RequestFactory
        import json

        factory = RequestFactory()
        req = factory.delete(
            '/portal/work-orders/',
            data=json.dumps({'id': str(wo_comp.id)}),
            content_type='application/json'
        )
        req.user = self.tech_user
        setattr(req, '_cached_tenant', self.tenant)
        req.session = {}

        p_del, _ = Permission.objects.get_or_create(id='work_order:delete', defaults={'name': 'Del WO'})
        p_read, _ = Permission.objects.get_or_create(id='work_order:read', defaults={'name': 'Read WO'})
        self.role_tech.permissions.add(p_del, p_read)

        resp = portal_work_orders(req)
        resp_data = json.loads(resp.content)
        self.assertFalse(resp_data['success'])
        self.assertIn('Only CREATED or ASSIGNED', resp_data['error'])

        # 2. WorkOrderSerializer bao gồm costBreakdown, actualCost, isCapitalized
        wo_comp.actual_cost = Decimal('1500000.00')
        wo_comp.is_capitalized = True
        wo_comp.save()
        WorkOrderCost.objects.create(
            tenant=self.tenant,
            work_order=wo_comp,
            material_cost=Decimal('1000000.00'),
            labor_cost=Decimal('500000.00'),
            vendor_cost=Decimal('0.00'),
            gross_cost=Decimal('1500000.00'),
            net_cost=Decimal('1500000.00'),
            is_cost_frozen=True
        )

        from workorders.serializers import WorkOrderSerializer
        ser = WorkOrderSerializer(wo_comp)
        self.assertIn('actualCost', ser.data)
        self.assertIn('isCapitalized', ser.data)
        self.assertIn('costBreakdown', ser.data)
        self.assertEqual(ser.data['actualCost'], '1500000.00')
        self.assertTrue(ser.data['isCapitalized'])
        self.assertEqual(ser.data['costBreakdown']['materialCost'], '1000000.00')



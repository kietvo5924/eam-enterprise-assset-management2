"""
Kiểm thử hồi quy trọng yếu (Supplemental Acceptance Verification) trên PostgreSQL độc lập:
1. Tồn kho và định giá (Inventory & Valuation Engine)
   - Khởi tạo tồn đầu kỳ (RECEIPT)
   - Tăng/giảm tồn bằng ADJUSTMENT (is_variance_adjustment=True)
   - Giữ nguyên số lượng nhưng đổi đơn giá (không tạo transaction thừa)
   - Nhiều lần ISSUE với đơn giá khác nhau
   - RETURN một phần và RETURN nhiều lần
   - Hủy WO hoàn kho (chống double-return)
   - GRN và moving weighted average (tính bình quân gia quyền & phân bổ variance)
   - Quy ước dấu và tính nhất quán báo cáo định giá
   - Concurrency select_for_update() trong Portal PUT
2. CapEx PostgreSQL concurrency (TransactionTestCase đa luồng)
   - 2 WO CapEx cùng liên kết 1 Asset hoàn thành đồng thời trên PostgreSQL
   - Chống lost update, chống deadlock, nhất quán WorkOrderCost và Asset.capitalized_cost
   - Retry không làm tăng thêm CapEx
   - Transaction rollback đầy đủ khi gặp sự cố
"""
import json
import threading
from decimal import Decimal
from django.db import connection, transaction
from django.db.models import Sum
from django.test import TransactionTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory

from core.models import Tenant
from core.tenant_context import set_current_tenant, clear_current_tenant
from users.models import User, Role, Permission
from assets.models import Asset, AssetCategory, Location, SparePart, StockTransaction
from workorders.models import WorkOrder, WorkOrderMaterial, WorkOrderCost, WorkOrderAttachment
from workorders.services import WorkOrderTransitionService
from algorithms.cost_forecasting import CostForecastingService
from analytics.report_services import SparePartsValuationEngine
from portal.views import portal_inventory


class InventoryAndValuationRegressionTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Inventory Tenant", tenant_code="TENANT_INV")
        set_current_tenant(self.tenant.id)
        self.location = Location.objects.create(name="Kho Phụ Tùng Trung Tâm", code="LOC_KHO_01", tenant=self.tenant)
        self.category = AssetCategory.objects.create(name="Máy Cắt CNC", tenant=self.tenant)
        self.asset = Asset.objects.create(
            name="Máy Cắt CNC-01",
            serial_number="CNC_01_SER",
            qr_code="QR_CNC_01",
            category=self.category,
            location=self.location,
            tenant=self.tenant,
            is_active=True
        )
        self.user = User.objects.create(username="inv_user", email="inv@test.com", tenant=self.tenant)
        self.role_admin = Role.objects.create(name="ADMIN", tenant=self.tenant)
        p_sys_admin, _ = Permission.objects.get_or_create(id="system:admin", defaults={"name": "Sys Admin"})
        p_inv_create, _ = Permission.objects.get_or_create(id="inventory:create", defaults={"name": "Create Inv"})
        p_inv_update, _ = Permission.objects.get_or_create(id="inventory:update", defaults={"name": "Update Inv"})
        p_inv_delete, _ = Permission.objects.get_or_create(id="inventory:delete", defaults={"name": "Delete Inv"})
        self.role_admin.permissions.add(p_sys_admin, p_inv_create, p_inv_update, p_inv_delete)
        self.user.roles.add(self.role_admin)

    def tearDown(self):
        clear_current_tenant()

    def test_01_initial_stock_creates_receipt_transaction(self):
        """Khởi tạo phụ tùng có tồn đầu kỳ qua API tự động tạo StockTransaction RECEIPT trong ledger."""
        from assets.views import SparePartListView
        factory = APIRequestFactory()

        # 1. Thử nghiệm qua portal_inventory POST
        payload_portal = {
            'name': 'Bugi Đánh Lửa NGK',
            'part_number': 'NGK-CR7E',
            'quantity_in_stock': '10.00',
            'unit_cost': '150000.00'
        }
        req_portal = factory.post('/portal/inventory/', data=json.dumps(payload_portal), content_type='application/json')
        req_portal.user = self.user
        resp_portal = portal_inventory(req_portal)
        self.assertEqual(resp_portal.status_code, 200)
        data_portal = json.loads(resp_portal.content)
        self.assertTrue(data_portal['success'])
        part_id = data_portal['id']

        part = SparePart.objects.get(id=part_id)
        self.assertEqual(part.quantity_in_stock, Decimal('10.00'))
        self.assertEqual(part.unit_cost, Decimal('150000.00'))

        tx = StockTransaction.all_objects.filter(spare_part=part, transaction_type='RECEIPT').first()
        self.assertIsNotNone(tx, "StockTransaction RECEIPT phải được tạo tự động bởi endpoint")
        self.assertEqual(tx.quantity, Decimal('10.00'))
        self.assertEqual(tx.unit_price, Decimal('150000.00'))
        self.assertEqual(tx.total_amount, Decimal('1500000.00'))
        self.assertFalse(tx.is_variance_adjustment)

        # 2. Thử nghiệm qua API REST SparePartListView POST
        payload_api = {
            'name': 'Dây curoa Bando',
            'partNumber': 'BD-5PK1000',
            'quantityInStock': 5.0,
            'unitCost': 120000.0
        }
        req_api = factory.post('/api/v1/assets/spare-parts/', data=payload_api, format='json')
        req_api.user = self.user
        set_current_tenant(self.tenant.id)
        view = SparePartListView.as_view()
        resp_api = view(req_api)
        self.assertEqual(resp_api.status_code, 200)

        part2 = SparePart.objects.filter(name='Dây curoa Bando', tenant=self.tenant).first()
        self.assertIsNotNone(part2)
        self.assertEqual(part2.quantity_in_stock, Decimal('5.00'))
        tx2 = StockTransaction.all_objects.filter(spare_part=part2, transaction_type='RECEIPT').first()
        self.assertIsNotNone(tx2)
        self.assertEqual(tx2.quantity, Decimal('5.00'))
        self.assertEqual(tx2.total_amount, Decimal('600000.00'))
        self.assertFalse(tx2.is_variance_adjustment)

    def test_02_adjustment_increase_stock(self):
        """Tăng tồn bằng ADJUSTMENT qua Portal PUT tạo transaction ADJUSTMENT với is_variance_adjustment=True."""
        part = SparePart.objects.create(
            tenant=self.tenant,
            name="Cảm biến quang học",
            part_number="OPT-001",
            quantity_in_stock=Decimal('10.00'),
            unit_cost=Decimal('200000.00')
        )
        factory = APIRequestFactory()
        payload = {
            'id': str(part.id),
            'name': part.name,
            'part_number': part.part_number,
            'quantity_in_stock': '15.00',
            'unit_cost': '200000.00'
        }
        req = factory.put('/portal/inventory/', data=json.dumps(payload), content_type='application/json')
        req.user = self.user
        resp = portal_inventory(req)
        self.assertEqual(resp.status_code, 200)

        part.refresh_from_db()
        self.assertEqual(part.quantity_in_stock, Decimal('15.00'))

        tx = StockTransaction.all_objects.filter(spare_part=part, transaction_type='ADJUSTMENT').first()
        self.assertIsNotNone(tx)
        self.assertEqual(tx.quantity, Decimal('5.00'))  # Delta = +5
        self.assertEqual(tx.unit_price, Decimal('200000.00'))
        self.assertEqual(tx.total_amount, Decimal('1000000.00'))
        self.assertTrue(tx.is_variance_adjustment)

    def test_03_adjustment_decrease_stock(self):
        """Giảm tồn bằng ADJUSTMENT qua Portal PUT tạo transaction ADJUSTMENT với delta dương abs()."""
        part = SparePart.objects.create(
            tenant=self.tenant,
            name="Vòng bi cầu",
            part_number="VB-6001",
            quantity_in_stock=Decimal('15.00'),
            unit_cost=Decimal('50000.00')
        )
        factory = APIRequestFactory()
        payload = {
            'id': str(part.id),
            'name': part.name,
            'part_number': part.part_number,
            'quantity_in_stock': '9.00',
            'unit_cost': '50000.00'
        }
        req = factory.put('/portal/inventory/', data=json.dumps(payload), content_type='application/json')
        req.user = self.user
        resp = portal_inventory(req)
        self.assertEqual(resp.status_code, 200)

        part.refresh_from_db()
        self.assertEqual(part.quantity_in_stock, Decimal('9.00'))

        tx = StockTransaction.all_objects.filter(spare_part=part, transaction_type='ADJUSTMENT').first()
        self.assertIsNotNone(tx)
        self.assertEqual(tx.quantity, Decimal('6.00'))  # Delta = |-6| = 6
        self.assertEqual(tx.total_amount, Decimal('300000.00'))
        self.assertTrue(tx.is_variance_adjustment)

    def test_04_price_change_without_qty_change_does_not_create_tx(self):
        """Giữ nguyên số lượng nhưng đổi đơn giá: chỉ cập nhật đơn giá, không tạo transaction ADJUSTMENT số lượng giả."""
        part = SparePart.objects.create(
            tenant=self.tenant,
            name="Ốc vít titan M6",
            part_number="M6-TI",
            quantity_in_stock=Decimal('50.00'),
            unit_cost=Decimal('10000.00')
        )
        factory = APIRequestFactory()
        payload = {
            'id': str(part.id),
            'name': part.name,
            'part_number': part.part_number,
            'quantity_in_stock': '50.00',  # Số lượng không đổi
            'unit_cost': '12500.00'        # Đơn giá tăng
        }
        req = factory.put('/portal/inventory/', data=json.dumps(payload), content_type='application/json')
        req.user = self.user
        resp = portal_inventory(req)
        self.assertEqual(resp.status_code, 200)

        part.refresh_from_db()
        self.assertEqual(part.quantity_in_stock, Decimal('50.00'))
        self.assertEqual(part.unit_cost, Decimal('12500.00'))
        # Không tạo transaction ADJUSTMENT
        self.assertEqual(StockTransaction.all_objects.filter(spare_part=part).count(), 0)

    def test_04b_qty_change_without_unit_cost_preserves_unit_cost(self):
        """Cập nhật số lượng qua portal PUT mà không truyền unit_cost không làm mất đơn giá hiện có."""
        part = SparePart.objects.create(
            tenant=self.tenant,
            name="Cảm biến quang học chính xác",
            part_number="OPT-PREC-99",
            quantity_in_stock=Decimal('10.00'),
            unit_cost=Decimal('450000.00')
        )
        factory = APIRequestFactory()
        payload = {
            'id': str(part.id),
            'name': part.name,
            'part_number': part.part_number,
            'quantity_in_stock': '18.00'
            # unit_cost không được truyền trong payload
        }
        req = factory.put('/portal/inventory/', data=json.dumps(payload), content_type='application/json')
        req.user = self.user
        resp = portal_inventory(req)
        self.assertEqual(resp.status_code, 200)

        part.refresh_from_db()
        self.assertEqual(part.quantity_in_stock, Decimal('18.00'))
        # Đơn giá 450,000 phải được bảo toàn, KHÔNG bị ghi đè thành None
        self.assertEqual(part.unit_cost, Decimal('450000.00'))
        tx = StockTransaction.all_objects.filter(spare_part=part, transaction_type='ADJUSTMENT').first()
        self.assertIsNotNone(tx)
        self.assertEqual(tx.quantity, Decimal('8.00'))
        self.assertEqual(tx.unit_price, Decimal('450000.00'))
        self.assertEqual(tx.total_amount, Decimal('3600000.00'))

    def test_05_multiple_issues_with_different_prices(self):
        """Nhiều lần ISSUE với đơn giá khác nhau hạch toán chính xác vào tổng chi phí Work Order."""
        part = SparePart.objects.create(
            tenant=self.tenant,
            name="Dầu bôi trơn Shell Tellus 68",
            part_number="SHELL-T68",
            quantity_in_stock=Decimal('100.00'),
            unit_cost=Decimal('80000.00')
        )
        wo = WorkOrder.objects.create(
            title="Bảo trì máy cắt CNC - Thay dầu tuần hoàn",
            asset=self.asset,
            tenant=self.tenant,
            status='IN_PROGRESS',
            assigned_to=self.user
        )
        # Xuất đợt 1: 10 lít @ 80,000 = 800,000
        part.quantity_in_stock -= Decimal('10.00')
        part.save(update_fields=['quantity_in_stock'])
        StockTransaction.all_objects.create(
            tenant=self.tenant,
            spare_part=part,
            work_order=wo,
            transaction_type='ISSUE',
            quantity=Decimal('10.00'),
            unit_price=Decimal('80000.00'),
            total_amount=Decimal('800000.00'),
            issue_date=timezone.now() - timezone.timedelta(days=2),
            is_variance_adjustment=False
        )

        # Đơn giá thị trường thay đổi thành 90,000
        part.unit_cost = Decimal('90000.00')
        part.save(update_fields=['unit_cost'])

        # Xuất đợt 2: 5 lít @ 90,000 = 450,000
        part.quantity_in_stock -= Decimal('5.00')
        part.save(update_fields=['quantity_in_stock'])
        StockTransaction.all_objects.create(
            tenant=self.tenant,
            spare_part=part,
            work_order=wo,
            transaction_type='ISSUE',
            quantity=Decimal('5.00'),
            unit_price=Decimal('90000.00'),
            total_amount=Decimal('450000.00'),
            issue_date=timezone.now() - timezone.timedelta(days=1),
            is_variance_adjustment=False
        )

        part.refresh_from_db()
        self.assertEqual(part.quantity_in_stock, Decimal('85.00'))

        # Đóng băng chi phí Work Order
        cost = CostForecastingService.freeze_work_order_cost(wo)
        # Tổng vật tư = 800k + 450k = 1,250,000
        self.assertEqual(cost.material_cost, Decimal('1250000.00'))
        self.assertEqual(cost.gross_cost, Decimal('1250000.00'))
        self.assertEqual(cost.net_cost, Decimal('1250000.00'))

    def test_06_partial_and_multiple_returns(self):
        """RETURN một phần và RETURN nhiều lần giảm trừ chi phí và khôi phục tồn kho chính xác."""
        part = SparePart.objects.create(
            tenant=self.tenant,
            name="Cầu chì công nghiệp 20A",
            part_number="FUSE-20A",
            quantity_in_stock=Decimal('20.00'),
            unit_cost=Decimal('50000.00')
        )
        wo = WorkOrder.objects.create(
            title="Sửa chữa hệ thống điện CNC",
            asset=self.asset,
            tenant=self.tenant,
            status='IN_PROGRESS',
            assigned_to=self.user
        )
        # Xuất 10 chiếc @ 50,000 = 500,000
        part.quantity_in_stock -= Decimal('10.00')
        part.save(update_fields=['quantity_in_stock'])
        StockTransaction.all_objects.create(
            tenant=self.tenant,
            spare_part=part,
            work_order=wo,
            transaction_type='ISSUE',
            quantity=Decimal('10.00'),
            unit_price=Decimal('50000.00'),
            total_amount=Decimal('500000.00'),
            issue_date=timezone.now() - timezone.timedelta(days=1),
            is_variance_adjustment=False
        )
        WorkOrderMaterial.objects.create(
            tenant=self.tenant,
            work_order=wo,
            spare_part=part,
            quantity=Decimal('10.00'),
            actual_cost=Decimal('500000.00')
        )

        # Lần hoàn 1: hoàn 2 chiếc
        SparePartsValuationEngine.record_surplus_return(
            tenant=self.tenant,
            spare_part=part,
            work_order=wo,
            return_qty=Decimal('2.00'),
            original_unit_cost=Decimal('50000.00'),
            return_date=timezone.now()
        )
        part.refresh_from_db()
        self.assertEqual(part.quantity_in_stock, Decimal('12.00'))

        # Lần hoàn 2: hoàn tiếp 3 chiếc
        SparePartsValuationEngine.record_surplus_return(
            tenant=self.tenant,
            spare_part=part,
            work_order=wo,
            return_qty=Decimal('3.00'),
            original_unit_cost=Decimal('50000.00'),
            return_date=timezone.now()
        )
        part.refresh_from_db()
        self.assertEqual(part.quantity_in_stock, Decimal('15.00'))

        # Đóng băng chi phí: Material = 500k - (2*50k + 3*50k) = 250,000
        cost = CostForecastingService.freeze_work_order_cost(wo)
        self.assertEqual(cost.material_cost, Decimal('250000.00'))
        self.assertEqual(cost.net_cost, Decimal('250000.00'))

    def test_07_cancel_work_order_restores_remaining_stock_idempotent(self):
        """Hủy WO hoàn trả tồn kho còn lại và không hoàn trùng nếu gọi lại."""
        part = SparePart.objects.create(
            tenant=self.tenant,
            name="Van điện từ Festo",
            part_number="FESTO-V1",
            quantity_in_stock=Decimal('10.00'),
            unit_cost=Decimal('300000.00')
        )
        wo = WorkOrder.objects.create(
            title="Phiếu bảo trì chuẩn bị hủy",
            asset=self.asset,
            tenant=self.tenant,
            status='IN_PROGRESS',
            assigned_to=self.user
        )
        # Xuất 4 chiếc (kho còn 6)
        part.quantity_in_stock -= Decimal('4.00')
        part.save(update_fields=['quantity_in_stock'])
        StockTransaction.all_objects.create(
            tenant=self.tenant,
            spare_part=part,
            work_order=wo,
            transaction_type='ISSUE',
            quantity=Decimal('4.00'),
            unit_price=Decimal('300000.00'),
            total_amount=Decimal('1200000.00'),
            issue_date=timezone.now(),
            is_variance_adjustment=False
        )
        # Đã hoàn 1 trước đó
        part.quantity_in_stock += Decimal('1.00')
        part.save(update_fields=['quantity_in_stock'])
        StockTransaction.all_objects.create(
            tenant=self.tenant,
            spare_part=part,
            work_order=wo,
            transaction_type='RETURN',
            quantity=Decimal('1.00'),
            unit_price=Decimal('300000.00'),
            total_amount=Decimal('300000.00'),
            issue_date=timezone.now(),
            is_variance_adjustment=False
        )
        # Hiện tại kho đang có: 10 - 4 + 1 = 7. Còn thiếu 3 chiếc chưa hoàn.
        part.refresh_from_db()
        self.assertEqual(part.quantity_in_stock, Decimal('7.00'))

        # Hủy WO lần 1
        WorkOrderTransitionService.restore_work_order_inventory(wo)
        part.refresh_from_db()
        # Kho phải trở về 7 + 3 = 10
        self.assertEqual(part.quantity_in_stock, Decimal('10.00'))

        # Hủy WO lần 2 (Idempotency) -> Kho vẫn giữ nguyên 10, không cộng thêm
        WorkOrderTransitionService.restore_work_order_inventory(wo)
        part.refresh_from_db()
        self.assertEqual(part.quantity_in_stock, Decimal('10.00'))

    def test_08_grn_moving_weighted_average_and_price_variance_reconciliation(self):
        """GRN tính moving weighted average và phân bổ chênh lệch giá cho các issue âm trước đó."""
        part = SparePart.objects.create(
            tenant=self.tenant,
            name="Cảm biến nhiệt PT100",
            part_number="PT-100",
            quantity_in_stock=Decimal('10.00'),
            unit_cost=Decimal('100000.00')
        )
        # GRN đợt 1: Nhập thêm 10 chiếc @ 140,000
        # Weighted average = (10*100k + 10*140k) / 20 = 120,000
        txs = SparePartsValuationEngine.apply_grn_receipt_and_reconcile_variance(
            tenant=self.tenant,
            spare_part=part,
            receipt_qty=Decimal('10.00'),
            new_unit_cost=Decimal('140000.00'),
            receipt_date=timezone.now()
        )
        part.refresh_from_db()
        self.assertEqual(part.quantity_in_stock, Decimal('20.00'))
        self.assertEqual(part.unit_cost, Decimal('120000.00'))

        # Mô phỏng xuất vượt tồn kho (Negative stock): xuất 22 chiếc (kho trở thành -2)
        wo = WorkOrder.objects.create(
            title="Đại tu hệ thống sấy",
            asset=self.asset,
            tenant=self.tenant,
            status='IN_PROGRESS',
            assigned_to=self.user
        )
        SparePartsValuationEngine.record_negative_issue_and_variance(
            tenant=self.tenant,
            spare_part=part,
            work_order=wo,
            issue_qty=Decimal('22.00'),
            issue_date=timezone.now()
        )
        part.refresh_from_db()
        self.assertEqual(part.quantity_in_stock, Decimal('-2.00'))

        # GRN đợt 2: Nhập 5 chiếc với giá 150,000
        # Reconcile 2 chiếc âm: variance = 2 * (150,000 - 120,000) = +60,000 VNĐ
        txs_grn2 = SparePartsValuationEngine.apply_grn_receipt_and_reconcile_variance(
            tenant=self.tenant,
            spare_part=part,
            receipt_qty=Decimal('5.00'),
            new_unit_cost=Decimal('150000.00'),
            receipt_date=timezone.now()
        )
        part.refresh_from_db()
        # Số lượng mới: -2 + 5 = 3 chiếc
        self.assertEqual(part.quantity_in_stock, Decimal('3.00'))
        # Đơn giá bình quân mới = 150,000 (vì trước đó stock âm)
        self.assertEqual(part.unit_cost, Decimal('150000.00'))

        # Phải sinh ra giao dịch ADJUSTMENT is_variance_adjustment=True với total_amount=60,000
        var_tx = StockTransaction.all_objects.filter(
            spare_part=part,
            transaction_type='ADJUSTMENT',
            is_variance_adjustment=True
        ).first()
        self.assertIsNotNone(var_tx)
        self.assertEqual(var_tx.quantity, Decimal('2.00'))
        self.assertEqual(var_tx.total_amount, Decimal('60000.00'))

    def test_09_valuation_report_consistency(self):
        """Báo cáo SparePartsValuationEngine phản ánh số lượng, giá trị tồn và transaction chính xác."""
        part = SparePart.objects.create(
            tenant=self.tenant,
            name="Bộ nguồn MeanWell 24V",
            part_number="MW-24V",
            quantity_in_stock=Decimal('10.00'),
            unit_cost=Decimal('500000.00')
        )
        # Tổng giá trị tồn = 10 * 500k = 5,000,000
        data = SparePartsValuationEngine.get_spare_parts_data(self.tenant)
        self.assertIn("summary", data)
        self.assertEqual(data["summary"]["totalInventoryValue"], 5000000.00)
        self.assertEqual(data["summary"]["negativeStockItems"], 0)

    def test_10_put_unit_cost_zero_and_null_rules(self):
        """PUT unit_cost=0 phải bảo toàn 0.00, PUT null đặt None, đổi location/quantity không mất giá."""
        part = SparePart.objects.create(
            tenant=self.tenant,
            name="Rơ le nhiệt Chint",
            part_number="NR2-25",
            quantity_in_stock=Decimal('20.00'),
            unit_cost=Decimal('85000.00'),
            location=self.location
        )
        factory = APIRequestFactory()

        # 1. PUT không truyền unit_cost -> giữ nguyên giá 85,000
        payload_no_cost = {
            'id': str(part.id),
            'name': part.name,
            'part_number': part.part_number,
            'quantity_in_stock': '25.00'
        }
        req1 = factory.put('/portal/inventory/', data=json.dumps(payload_no_cost), content_type='application/json')
        req1.user = self.user
        resp1 = portal_inventory(req1)
        self.assertEqual(resp1.status_code, 200)
        part.refresh_from_db()
        self.assertEqual(part.quantity_in_stock, Decimal('25.00'))
        self.assertEqual(part.unit_cost, Decimal('85000.00'))

        # 2. PUT đổi vị trí (location_id) -> không làm mất đơn giá
        new_loc = Location.objects.create(name="Kho Phụ Tùng Số 2", code="LOC_KHO_02", tenant=self.tenant)
        payload_loc = {
            'id': str(part.id),
            'name': part.name,
            'part_number': part.part_number,
            'location_id': str(new_loc.id)
        }
        req2 = factory.put('/portal/inventory/', data=json.dumps(payload_loc), content_type='application/json')
        req2.user = self.user
        resp2 = portal_inventory(req2)
        self.assertEqual(resp2.status_code, 200)
        part.refresh_from_db()
        self.assertEqual(part.location_id, new_loc.id)
        self.assertEqual(part.unit_cost, Decimal('85000.00'))

        # 3. PUT truyền unit_cost = 0 -> bảo toàn giá trị 0.00, không bị gán thành None
        payload_zero = {
            'id': str(part.id),
            'name': part.name,
            'part_number': part.part_number,
            'unit_cost': 0
        }
        req3 = factory.put('/portal/inventory/', data=json.dumps(payload_zero), content_type='application/json')
        req3.user = self.user
        resp3 = portal_inventory(req3)
        self.assertEqual(resp3.status_code, 200)
        part.refresh_from_db()
        self.assertEqual(part.unit_cost, Decimal('0.00'))

        # 4. PUT truyền null -> đặt unit_cost thành None
        payload_null = {
            'id': str(part.id),
            'name': part.name,
            'part_number': part.part_number,
            'unit_cost': None
        }
        req4 = factory.put('/portal/inventory/', data=json.dumps(payload_null), content_type='application/json')
        req4.user = self.user
        resp4 = portal_inventory(req4)
        self.assertEqual(resp4.status_code, 200)
        part.refresh_from_db()
        self.assertIsNone(part.unit_cost)

    def test_10b_rest_api_spare_part_put_unit_cost_zero_and_preserve_quantity(self):
        """REST API SparePartDetailView PUT: unitCost=0 bảo toàn 0.00, không truyền quantityInStock không reset về 0, đổi location giữ nguyên giá."""
        from assets.views import SparePartDetailView
        part = SparePart.objects.create(
            tenant=self.tenant,
            name="Biến tần Schneider ATV310",
            part_number="ATV310-01",
            quantity_in_stock=Decimal('42.00'),
            unit_cost=Decimal('3200000.00'),
            location=self.location
        )
        factory = APIRequestFactory()
        view = SparePartDetailView.as_view()

        # 1. PUT cập nhật unitCost = 0 mà KHÔNG truyền quantityInStock:
        # Số lượng 42.00 phải được BẢO TOÀN, tuyệt đối không bị reset về 0.00!
        req1 = factory.put(f'/api/v1/assets/spare-parts/{part.id}/', data={'name': part.name, 'unitCost': 0.0}, format='json')
        req1.user = self.user
        set_current_tenant(self.tenant.id)
        resp1 = view(req1, part_id=str(part.id))
        self.assertEqual(resp1.status_code, 200)
        part.refresh_from_db()
        self.assertEqual(part.quantity_in_stock, Decimal('42.00'), "Không truyền quantityInStock thì không được reset tồn kho về 0")
        self.assertEqual(part.unit_cost, Decimal('0.00'))

        # 2. PUT cập nhật tên mà KHÔNG truyền unitCost và KHÔNG truyền quantityInStock:
        # Cả đơn giá 0.00 và số lượng 42.00 đều phải giữ nguyên, không tạo transaction rác
        req2 = factory.put(f'/api/v1/assets/spare-parts/{part.id}/', data={'name': 'Biến tần Schneider ATV310 (Đã kiểm tra)'}, format='json')
        req2.user = self.user
        set_current_tenant(self.tenant.id)
        resp2 = view(req2, part_id=str(part.id))
        self.assertEqual(resp2.status_code, 200)
        part.refresh_from_db()
        self.assertEqual(part.name, 'Biến tần Schneider ATV310 (Đã kiểm tra)')
        self.assertEqual(part.quantity_in_stock, Decimal('42.00'))
        self.assertEqual(part.unit_cost, Decimal('0.00'))

        # 3. PUT cập nhật location mà KHÔNG truyền unitCost:
        new_loc = Location.objects.create(name="Kho Thiết Bị Điện", code="LOC_KHO_DIEN", tenant=self.tenant)
        req3 = factory.put(f'/api/v1/assets/spare-parts/{part.id}/', data={'name': part.name, 'locationId': str(new_loc.id)}, format='json')
        req3.user = self.user
        set_current_tenant(self.tenant.id)
        resp3 = view(req3, part_id=str(part.id))
        self.assertEqual(resp3.status_code, 200)
        part.refresh_from_db()
        self.assertEqual(part.location_id, new_loc.id)
        self.assertEqual(part.unit_cost, Decimal('0.00'))
        self.assertEqual(part.quantity_in_stock, Decimal('42.00'))

        # 4. PUT cập nhật unitCost = null -> đặt unit_cost thành None
        req4 = factory.put(f'/api/v1/assets/spare-parts/{part.id}/', data={'name': part.name, 'unitCost': None}, format='json')
        req4.user = self.user
        set_current_tenant(self.tenant.id)
        resp4 = view(req4, part_id=str(part.id))
        self.assertEqual(resp4.status_code, 200)
        part.refresh_from_db()
        self.assertIsNone(part.unit_cost)
        self.assertEqual(part.quantity_in_stock, Decimal('42.00'))

    def test_11_stock_transaction_ledger_direction_and_reconciliation(self):
        """Xác minh thực tế chiều biến động ledger: RECEIPT (+), ISSUE (-), RETURN (+), ADJUSTMENT_INCREASE (+), ADJUSTMENT_DECREASE (-)."""
        # Khởi tạo tồn đầu kỳ 50 cái @ 10,000 = 500,000
        part = SparePart.objects.create(
            tenant=self.tenant,
            name="Cầu dao tự động MCB 1P 16A",
            part_number="MCB-1P-16A",
            quantity_in_stock=Decimal('50.00'),
            unit_cost=Decimal('10000.00')
        )
        StockTransaction.all_objects.create(
            tenant=self.tenant,
            spare_part=part,
            transaction_type='RECEIPT',
            quantity=Decimal('50.00'),
            unit_price=Decimal('10000.00'),
            total_amount=Decimal('500000.00'),
            cost_center_snapshot='INITIAL_STOCK',
            issue_date=timezone.now() - timezone.timedelta(days=10),
            is_variance_adjustment=False
        )

        wo = WorkOrder.objects.create(
            title="Sửa chữa tủ điện",
            asset=self.asset,
            tenant=self.tenant,
            status='IN_PROGRESS',
            assigned_to=self.user
        )

        # 1. ISSUE: Xuất 10 cái -> tồn kho giảm 10 (còn 40)
        part.quantity_in_stock -= Decimal('10.00')
        part.save(update_fields=['quantity_in_stock'])
        StockTransaction.all_objects.create(
            tenant=self.tenant,
            spare_part=part,
            work_order=wo,
            transaction_type='ISSUE',
            quantity=Decimal('10.00'),
            unit_price=Decimal('10000.00'),
            total_amount=Decimal('100000.00'),
            issue_date=timezone.now() - timezone.timedelta(days=5),
            is_variance_adjustment=False
        )

        # 2. RETURN: Hoàn trả 3 cái -> tồn kho tăng 3 (thành 43)
        part.quantity_in_stock += Decimal('3.00')
        part.save(update_fields=['quantity_in_stock'])
        StockTransaction.all_objects.create(
            tenant=self.tenant,
            spare_part=part,
            work_order=wo,
            transaction_type='RETURN',
            quantity=Decimal('3.00'),
            unit_price=Decimal('10000.00'),
            total_amount=Decimal('30000.00'),
            issue_date=timezone.now() - timezone.timedelta(days=4),
            is_variance_adjustment=False
        )

        # 3. ADJUSTMENT Tăng: Điều chỉnh kiểm kê thừa 5 cái qua portal_inventory PUT (thành 48)
        factory = APIRequestFactory()
        payload_inc = {
            'id': str(part.id),
            'name': part.name,
            'part_number': part.part_number,
            'quantity_in_stock': '48.00',
            'unit_cost': '10000.00'
        }
        req_inc = factory.put('/portal/inventory/', data=json.dumps(payload_inc), content_type='application/json')
        req_inc.user = self.user
        resp_inc = portal_inventory(req_inc)
        self.assertEqual(resp_inc.status_code, 200)

        # 4. ADJUSTMENT Giảm: Điều chỉnh kiểm kê thiếu 2 cái qua portal_inventory PUT (thành 46)
        payload_dec = {
            'id': str(part.id),
            'name': part.name,
            'part_number': part.part_number,
            'quantity_in_stock': '46.00',
            'unit_cost': '10000.00'
        }
        req_dec = factory.put('/portal/inventory/', data=json.dumps(payload_dec), content_type='application/json')
        req_dec.user = self.user
        resp_dec = portal_inventory(req_dec)
        self.assertEqual(resp_dec.status_code, 200)

        part.refresh_from_db()
        self.assertEqual(part.quantity_in_stock, Decimal('46.00'))

        # Đối chiếu ledger: Tính toán lại số lượng tồn kho thuần túy từ bảng StockTransaction
        txs = StockTransaction.all_objects.filter(spare_part=part)
        ledger_qty = Decimal('0.00')
        for t in txs:
            if t.transaction_type == 'RECEIPT':
                ledger_qty += t.quantity
            elif t.transaction_type == 'ISSUE':
                ledger_qty -= t.quantity
            elif t.transaction_type == 'RETURN':
                ledger_qty += t.quantity
            elif t.transaction_type == 'ADJUSTMENT':
                # Chiều tăng/giảm xác định bởi trường cost_center_snapshot
                if t.cost_center_snapshot == 'ADJUSTMENT_INCREASE':
                    ledger_qty += t.quantity
                elif t.cost_center_snapshot == 'ADJUSTMENT_DECREASE':
                    ledger_qty -= t.quantity

        # Khớp 100% giữa Ledger tính toán và SparePart.quantity_in_stock
        self.assertEqual(ledger_qty, part.quantity_in_stock)
        self.assertEqual(ledger_qty, Decimal('46.00'))

        # Đối chiếu giá trị tồn kho với báo cáo SparePartsValuationEngine
        val_data = SparePartsValuationEngine.get_spare_parts_data(self.tenant)
        # 46 cái @ 10,000 = 460,000 VNĐ
        self.assertEqual(val_data["summary"]["totalInventoryValue"], 460000.00)

    def test_12_return_valuation_when_unit_cost_changes_after_issue(self):
        """Thay đổi unit_cost sau ISSUE không làm sai lệch giá trị hoàn kho (RETURN Valuation)."""
        part = SparePart.objects.create(
            tenant=self.tenant,
            name="Cảm biến tiệm cận Omron",
            part_number="OMRON-E2E",
            quantity_in_stock=Decimal('30.00'),
            unit_cost=Decimal('100000.00')
        )
        wo = WorkOrder.objects.create(
            title="Bảo trì băng tải đóng gói",
            asset=self.asset,
            tenant=self.tenant,
            status='IN_PROGRESS',
            assigned_to=self.user
        )

        # Xuất 5 cái @ 100,000 = 500,000
        part.quantity_in_stock -= Decimal('5.00')
        part.save(update_fields=['quantity_in_stock'])
        StockTransaction.all_objects.create(
            tenant=self.tenant,
            spare_part=part,
            work_order=wo,
            transaction_type='ISSUE',
            quantity=Decimal('5.00'),
            unit_price=Decimal('100000.00'),
            total_amount=Decimal('500000.00'),
            issue_date=timezone.now() - timezone.timedelta(days=2),
            is_variance_adjustment=False
        )

        # Giá thị trường của phụ tùng tăng vọt lên 250,000
        part.unit_cost = Decimal('250000.00')
        part.save(update_fields=['unit_cost'])

        # Hoàn 2 cái: Phải hoàn theo đúng đơn giá ISSUE gốc (100,000), không hoàn theo giá mới (250,000)
        SparePartsValuationEngine.record_surplus_return(
            tenant=self.tenant,
            spare_part=part,
            work_order=wo,
            return_qty=Decimal('2.00'),
            original_unit_cost=Decimal('100000.00'),
            return_date=timezone.now()
        )
        part.refresh_from_db()
        self.assertEqual(part.quantity_in_stock, Decimal('27.00'))

        # Hủy WO: Hoàn nốt 3 cái còn lại qua restore_work_order_inventory
        WorkOrderTransitionService.restore_work_order_inventory(wo)
        part.refresh_from_db()
        self.assertEqual(part.quantity_in_stock, Decimal('30.00'))

        # Tổng giá trị hoàn từ 2 đợt: 2*100k + 3*100k = 500,000 VNĐ (đúng bằng 100% chi phí xuất ban đầu)
        total_returned_amount = StockTransaction.all_objects.filter(
            work_order=wo,
            transaction_type='RETURN'
        ).aggregate(s=Sum('total_amount'))['s']
        self.assertEqual(total_returned_amount, Decimal('500000.00'))


class PostgresCapexConcurrencyTests(TransactionTestCase):
    """
    Kiểm thử đa luồng Concurrency trên PostgreSQL thực thụ (không dùng SQLite giả lập).
    Sử dụng TransactionTestCase để mỗi thread có kết nối và transaction độc lập.
    """
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Capex Concurrency Tenant", tenant_code="TENANT_CAPEX")
        set_current_tenant(self.tenant.id)
        self.location = Location.objects.create(name="Phân Xưởng Nhiệt Điện", code="LOC_ND_01", tenant=self.tenant)
        self.category = AssetCategory.objects.create(name="Tua bin khí", tenant=self.tenant)
        self.asset = Asset.objects.create(
            name="Tua bin phát điện TB-01",
            serial_number="TB_SER_888",
            qr_code="QR_TB_888",
            category=self.category,
            location=self.location,
            tenant=self.tenant,
            capitalized_cost=Decimal('500000000.00'),  # Vốn hóa ban đầu 500 triệu
            is_active=True
        )
        self.tech_user = User.objects.create(username="tech_concurrency", email="tech_con@test.com", tenant=self.tenant)
        self.role_tech = Role.objects.create(name="TECHNICIAN", tenant=self.tenant)
        self.tech_user.roles.add(self.role_tech)

    def tearDown(self):
        clear_current_tenant()

    def test_01_two_concurrent_capex_wo_completion_no_lost_updates_or_deadlocks(self):
        """2 Work Order CapEx (CORE_REPLACEMENT) cùng Asset hoàn thành đồng thời trên PostgreSQL không mất cập nhật, không deadlock."""
        wo1 = WorkOrder.objects.create(
            title="Đại tu buồng đốt tua bin (CapEx WO 1)",
            asset=self.asset,
            tenant=self.tenant,
            status='IN_PROGRESS',
            maintenance_action='CORE_REPLACEMENT',
            assigned_to=self.tech_user
        )
        wo2 = WorkOrder.objects.create(
            title="Thay thế cánh tua bin cao áp (CapEx WO 2)",
            asset=self.asset,
            tenant=self.tenant,
            status='IN_PROGRESS',
            maintenance_action='CORE_REPLACEMENT',
            assigned_to=self.tech_user
        )
        WorkOrderAttachment.objects.create(
            tenant=self.tenant,
            work_order=wo1,
            file_url='/media/proof_wo1.jpg',
            file_name='proof1.jpg',
            file_type='image/jpeg',
            file_size=2048
        )
        WorkOrderAttachment.objects.create(
            tenant=self.tenant,
            work_order=wo2,
            file_url='/media/proof_wo2.jpg',
            file_name='proof2.jpg',
            file_type='image/jpeg',
            file_size=2048
        )

        results = {}
        errors = []
        barrier = threading.Barrier(2)

        def complete_wo(wo_id, v_cost, thread_name):
            try:
                # Đảm bảo connection riêng biệt cho thread mới
                connection.close()
                barrier.wait()  # Cùng bấm giờ xuất phát đồng thời
                wo_res = WorkOrderTransitionService.complete_work_order(
                    work_order_id=wo_id,
                    user=self.tech_user,
                    vendor_cost=v_cost
                )
                results[thread_name] = wo_res
            except Exception as e:
                errors.append((thread_name, str(e)))
            finally:
                connection.close()

        # Thread 1: WO 1 với chi phí 50,000,000
        t1 = threading.Thread(target=complete_wo, args=(wo1.id, Decimal('50000000.00'), 'T1'))
        # Thread 2: WO 2 với chi phí 70,000,000
        t2 = threading.Thread(target=complete_wo, args=(wo2.id, Decimal('70000000.00'), 'T2'))

        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        # 1. Không có thread nào gặp ngoại lệ hay deadlock
        self.assertEqual(len(errors), 0, f"Lỗi xảy ra trong quá trình concurrency: {errors}")
        self.assertIn('T1', results)
        self.assertIn('T2', results)

        # 2. Cả 2 WO đều chuyển sang COMPLETED
        wo1.refresh_from_db()
        wo2.refresh_from_db()
        self.assertEqual(wo1.status, 'COMPLETED')
        self.assertEqual(wo2.status, 'COMPLETED')
        self.assertTrue(wo1.is_capitalized)
        self.assertTrue(wo2.is_capitalized)

        # 3. WorkOrderCost được tạo chính xác
        self.assertEqual(wo1.cost_breakdown.net_cost, Decimal('50000000.00'))
        self.assertEqual(wo2.cost_breakdown.net_cost, Decimal('70000000.00'))

        # 4. Asset.capitalized_cost không bị Lost Update:
        # 500,000,000 (ban đầu) + 50,000,000 (WO 1) + 70,000,000 (WO 2) = 620,000,000
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.capitalized_cost, Decimal('620000000.00'))

    def test_02_capex_retry_does_not_duplicate_capitalization(self):
        """Thực hiện hoàn thành lại (retry) một WO CapEx đã đóng băng không cộng trùng vào Asset."""
        wo = WorkOrder.objects.create(
            title="Đại tu hệ thống bôi trơn",
            asset=self.asset,
            tenant=self.tenant,
            status='IN_PROGRESS',
            maintenance_action='CORE_REPLACEMENT',
            assigned_to=self.tech_user
        )
        WorkOrderAttachment.objects.create(
            tenant=self.tenant,
            work_order=wo,
            file_url='/media/proof.jpg',
            file_name='proof.jpg',
            file_type='image/jpeg',
            file_size=1024
        )
        init_cap = self.asset.capitalized_cost or Decimal('0.00')

        # Lần 1: Nghiệm thu thành công với 30 triệu CapEx
        WorkOrderTransitionService.complete_work_order(
            work_order_id=wo.id,
            user=self.tech_user,
            vendor_cost=Decimal('30000000.00')
        )
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.capitalized_cost, init_cap + Decimal('30000000.00'))

        # Lần 2 (Retry)
        WorkOrderTransitionService.complete_work_order(
            work_order_id=wo.id,
            user=self.tech_user,
            vendor_cost=Decimal('30000000.00')
        )
        self.asset.refresh_from_db()
        # Giá trị vốn hóa KHÔNG được tăng thêm
        self.assertEqual(self.asset.capitalized_cost, init_cap + Decimal('30000000.00'))

    def test_03_transaction_error_rollbacks_completely(self):
        """Khi xảy ra ngoại lệ giữa transaction, PostgreSQL rollback đầy đủ và không làm tăng Asset.capitalized_cost."""
        wo = WorkOrder.objects.create(
            title="WO CapEx lỗi nghiệm thu",
            asset=self.asset,
            tenant=self.tenant,
            status='IN_PROGRESS',
            maintenance_action='CORE_REPLACEMENT',
            assigned_to=self.tech_user
        )
        # Không tạo WorkOrderAttachment -> sẽ bị chặn bởi quy tắc nghiệm thu
        init_cap = self.asset.capitalized_cost or Decimal('0.00')

        with self.assertRaises(Exception):
            WorkOrderTransitionService.complete_work_order(
                work_order_id=wo.id,
                user=self.tech_user,
                vendor_cost=Decimal('40000000.00')
            )

        # Rollback đầy đủ: WO vẫn IN_PROGRESS, Asset.capitalized_cost giữ nguyên
        wo.refresh_from_db()
        self.assertEqual(wo.status, 'IN_PROGRESS')
        self.assertFalse(wo.is_capitalized)
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.capitalized_cost, init_cap)

    def test_04_concurrent_portal_inventory_put_select_for_update(self):
        """Hai phiên Web cùng điều chỉnh 1 phụ tùng chạy select_for_update() trên PostgreSQL, bảo toàn ledger và không ghi đè mất delta."""
        p_inv, _ = Permission.objects.get_or_create(id="inventory:update", defaults={"name": "Update"})
        p_sys, _ = Permission.objects.get_or_create(id="system:admin", defaults={"name": "Admin"})
        role_inv = Role.objects.create(name="INV_ROLE", tenant=self.tenant)
        role_inv.permissions.add(p_sys, p_inv)
        self.tech_user.roles.add(role_inv)

        part = SparePart.objects.create(
            tenant=self.tenant,
            name="Cảm biến rung Piezo",
            part_number="PIEZO-V1",
            quantity_in_stock=Decimal('10.00'),
            unit_cost=Decimal('500000.00')
        )

        barrier = threading.Barrier(2)
        errors = []
        statuses = []

        def adjust_stock(target_qty, t_name):
            try:
                connection.close()
                set_current_tenant(self.tenant.id)
                factory = APIRequestFactory()
                payload = {
                    'id': str(part.id),
                    'name': part.name,
                    'part_number': part.part_number,
                    'quantity_in_stock': str(target_qty),
                    'unit_cost': '500000.00'
                }
                req = factory.put('/portal/inventory/', data=json.dumps(payload), content_type='application/json')
                req.user = self.tech_user
                barrier.wait()
                resp = portal_inventory(req)
                statuses.append((t_name, resp.status_code))
            except Exception as e:
                errors.append((t_name, str(e)))
            finally:
                connection.close()

        # Thread A đặt tồn về 20 (delta ban đầu +10)
        # Thread B đặt tồn về 35 (delta tiếp theo +15)
        t_a = threading.Thread(target=adjust_stock, args=(Decimal('20.00'), 'TA'))
        t_b = threading.Thread(target=adjust_stock, args=(Decimal('35.00'), 'TB'))

        t_a.start()
        t_b.start()
        t_a.join(timeout=10)
        t_b.join(timeout=10)

        self.assertEqual(len(errors), 0, f"Errors: {errors}")
        for t_name, code in statuses:
            self.assertEqual(code, 200)

        part.refresh_from_db()
        # Số lượng cuối cùng là 20 hoặc 35 tùy thứ tự hoàn tất
        self.assertIn(part.quantity_in_stock, [Decimal('20.00'), Decimal('35.00')])
        # Cả 2 giao dịch đều ghi nhận vào StockTransaction ledger mà không xung đột/lỗi deadlock
        adj_txs = StockTransaction.all_objects.filter(spare_part=part, transaction_type='ADJUSTMENT')
        self.assertEqual(adj_txs.count(), 2, "Cả hai phiên PUT đồng thời phải tạo đúng 2 bản ghi ledger ADJUSTMENT riêng biệt")

    def test_05_photo_attachment_upload_retry_does_not_duplicate(self):
        """Thử lại (retry) tải ảnh minh chứng không tạo WorkOrderAttachment trùng lặp (Idempotency)."""
        from workorders.views import WorkOrderAttachmentView
        from django.core.files.uploadedfile import SimpleUploadedFile

        wo = WorkOrder.objects.create(
            title="Phiếu kiểm tra chống trùng ảnh",
            asset=self.asset,
            tenant=self.tenant,
            status='IN_PROGRESS',
            assigned_to=self.tech_user
        )

        p_exec, _ = Permission.objects.get_or_create(id="work_order:execute", defaults={"name": "Exec"})
        self.role_tech.permissions.add(p_exec)

        factory = APIRequestFactory()
        image_content = b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xFF\xDB\x00C\x00"

        # Lần 1: Upload ảnh lần đầu
        file1 = SimpleUploadedFile("inspection_proof.jpg", image_content, content_type="image/jpeg")
        req1 = factory.post(f"/api/v1/work-orders/{wo.id}/attachments", {'file': file1}, format='multipart')
        req1.user = self.tech_user
        view = WorkOrderAttachmentView.as_view()
        resp1 = view(req1, wo_id=str(wo.id))
        self.assertEqual(resp1.status_code, 200)

        # Lần 2: Client mạng chập chờn thử lại (retry) đúng file đó
        file2 = SimpleUploadedFile("inspection_proof.jpg", image_content, content_type="image/jpeg")
        req2 = factory.post(f"/api/v1/work-orders/{wo.id}/attachments", {'file': file2}, format='multipart')
        req2.user = self.tech_user
        resp2 = view(req2, wo_id=str(wo.id))
        self.assertEqual(resp2.status_code, 200)

        # Số lượng attachment trong database phải duy nhất là 1, không bị nhân đôi
        att_count = WorkOrderAttachment.objects.filter(work_order=wo).count()
        self.assertEqual(att_count, 1, "Retry tải ảnh không được sinh bản ghi WorkOrderAttachment trùng lặp")

    def test_06_photo_attachment_different_content_same_name_and_size_not_dropped(self):
        """Hai ảnh khác nội dung nhưng cùng filename và file_size không bị nuốt nhầm; cùng tên khác nội dung được lưu độc lập."""
        from workorders.views import WorkOrderAttachmentView
        from django.core.files.uploadedfile import SimpleUploadedFile

        wo = WorkOrder.objects.create(
            title="WO Kiểm tra 2 ảnh khác nội dung cùng kích thước",
            asset=self.asset,
            tenant=self.tenant,
            status='IN_PROGRESS',
            assigned_to=self.tech_user
        )
        p_exec, _ = Permission.objects.get_or_create(id="work_order:execute", defaults={"name": "Exec"})
        self.role_tech.permissions.add(p_exec)

        factory = APIRequestFactory()
        view = WorkOrderAttachmentView.as_view()

        # Hai nội dung khác nhau nhưng cùng độ dài 512 bytes và cùng tên "proof.jpg"
        content_1 = b"\xFF\xD8\xFF\xE0" + (b"A" * 508)
        content_2 = b"\xFF\xD8\xFF\xE0" + (b"B" * 508)
        self.assertEqual(len(content_1), len(content_2))

        # Upload ảnh 1
        f1 = SimpleUploadedFile("proof.jpg", content_1, content_type="image/jpeg")
        req1 = factory.post(f"/api/v1/work-orders/{wo.id}/attachments", {'file': f1}, format='multipart')
        req1.user = self.tech_user
        resp1 = view(req1, wo_id=str(wo.id))
        self.assertEqual(resp1.status_code, 200)

        # Upload ảnh 2: Cùng tên "proof.jpg" và cùng size 512 bytes nhưng nội dung khác
        f2 = SimpleUploadedFile("proof.jpg", content_2, content_type="image/jpeg")
        req2 = factory.post(f"/api/v1/work-orders/{wo.id}/attachments", {'file': f2}, format='multipart')
        req2.user = self.tech_user
        resp2 = view(req2, wo_id=str(wo.id))
        self.assertEqual(resp2.status_code, 200)

        # Cả 2 ảnh đều phải được lưu thành 2 attachment độc lập (không bị nuốt mất ảnh 2)
        atts = WorkOrderAttachment.objects.filter(work_order=wo)
        self.assertEqual(atts.count(), 2, "Hệ thống không được dùng riêng filename + file_size để bỏ qua ảnh có nội dung khác nhau")
        self.assertNotEqual(atts[0].file_url, atts[1].file_url)

        # Upload ảnh 3: File có tên giống file cũ "proof.jpg" nhưng nội dung và size khác
        content_3 = b"\xFF\xD8\xFF\xE0" + (b"C" * 700)
        f3 = SimpleUploadedFile("proof.jpg", content_3, content_type="image/jpeg")
        req3 = factory.post(f"/api/v1/work-orders/{wo.id}/attachments", {'file': f3}, format='multipart')
        req3.user = self.tech_user
        resp3 = view(req3, wo_id=str(wo.id))
        self.assertEqual(resp3.status_code, 200)

        self.assertEqual(WorkOrderAttachment.objects.filter(work_order=wo).count(), 3)

    def test_07_photo_attachment_concurrent_uploads_concurrency_safe(self):
        """Hai request upload cùng lúc trên 2 database connection độc lập: không sinh bản ghi trùng lặp và không có file rác mồ côi."""
        from workorders.views import WorkOrderAttachmentView
        from django.core.files.uploadedfile import SimpleUploadedFile

        wo = WorkOrder.objects.create(
            title="WO Upload Concurrency Check",
            asset=self.asset,
            tenant=self.tenant,
            status='IN_PROGRESS',
            assigned_to=self.tech_user
        )
        p_exec, _ = Permission.objects.get_or_create(id="work_order:execute", defaults={"name": "Exec"})
        self.role_tech.permissions.add(p_exec)

        image_bytes = b"\xFF\xD8\xFF\xE0\x00\x10JFIF" + (b"X" * 1024)
        barrier = threading.Barrier(2)
        results = []
        errors = []

        def upload_worker(name):
            try:
                connection.close()
                set_current_tenant(self.tenant.id)
                factory = APIRequestFactory()
                file_obj = SimpleUploadedFile("camera_photo.jpg", image_bytes, content_type="image/jpeg")
                req = factory.post(f"/api/v1/work-orders/{wo.id}/attachments", {'file': file_obj}, format='multipart')
                req.user = self.tech_user
                view = WorkOrderAttachmentView.as_view()
                barrier.wait()
                resp = view(req, wo_id=str(wo.id))
                results.append((name, resp.status_code, resp.data))
            except Exception as e:
                errors.append((name, str(e)))
            finally:
                connection.close()

        t1 = threading.Thread(target=upload_worker, args=('Thread-1',))
        t2 = threading.Thread(target=upload_worker, args=('Thread-2',))
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        self.assertEqual(len(errors), 0, f"Lỗi xảy ra trong upload concurrency: {errors}")
        for name, code, data in results:
            self.assertEqual(code, 200)

        # Concurrency Lock (select_for_update) bảo đảm chỉ tạo DUY NHẤT 1 bản ghi WorkOrderAttachment
        att_qs = WorkOrderAttachment.objects.filter(work_order=wo)
        self.assertEqual(att_qs.count(), 1, "Hai request upload cùng lúc không được tạo trùng attachment")

    def test_08_capex_exception_after_capitalization_rolls_back_asset_and_cost(self):
        """Tạo exception sau khi Asset.capitalized_cost đã được cập nhật nhưng trước khi transaction commit: Asset, WorkOrderCost và WorkOrder rollback đồng bộ."""
        wo = WorkOrder.objects.create(
            title="WO CapEx thử nghiệm Rollback đồng bộ",
            asset=self.asset,
            tenant=self.tenant,
            status='IN_PROGRESS',
            maintenance_action='CORE_REPLACEMENT',
            assigned_to=self.tech_user
        )
        WorkOrderAttachment.objects.create(
            tenant=self.tenant,
            work_order=wo,
            file_url='/media/proof_capex_rollback.jpg',
            file_name='proof.jpg',
            file_type='image/jpeg',
            file_size=2048
        )
        init_cap = self.asset.capitalized_cost or Decimal('0.00')

        # Mô phỏng nghiệp vụ chạy hoàn tất cập nhật Asset.capitalized_cost và WorkOrderCost,
        # nhưng ngay trước khi transaction hoàn tất commit thì gặp lỗi hệ thống (Crash/Exception)
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                wo_completed = WorkOrderTransitionService.complete_work_order(
                    work_order_id=wo.id,
                    user=self.tech_user,
                    vendor_cost=Decimal('45000000.00')
                )
                # Xác nhận bên trong transaction, các bảng tạm thời đã được update
                self.asset.refresh_from_db()
                self.assertEqual(self.asset.capitalized_cost, init_cap + Decimal('45000000.00'))
                self.assertEqual(wo_completed.status, 'COMPLETED')
                self.assertTrue(WorkOrderCost.objects.filter(work_order=wo).exists())

                # Cố tình ném Exception ngay trước khi Transaction commit
                raise RuntimeError("Mô phỏng đứt kết nối mạng hoặc server crash trước khi transaction commit")

        # Sau khi rollback toàn diện:
        # 1. Asset.capitalized_cost khôi phục về đúng giá trị ban đầu, không bị cộng vốn hóa ma
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.capitalized_cost, init_cap)

        # 2. WorkOrderCost không tồn tại trong DB
        self.assertFalse(WorkOrderCost.objects.filter(work_order=wo).exists())

        # 3. WorkOrder vẫn giữ trạng thái IN_PROGRESS và is_capitalized = False
        wo.refresh_from_db()
        self.assertEqual(wo.status, 'IN_PROGRESS')
        self.assertFalse(wo.is_capitalized)



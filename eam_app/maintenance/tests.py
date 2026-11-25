import threading
from decimal import Decimal
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from core.models import Tenant
from core.tenant_context import set_current_tenant, clear_current_tenant
from users.models import User, Role
from assets.models import Asset, AssetCategory, Location, SparePart, StockTransaction
from maintenance.models import PmPlan, PmPlanMaterial, PmPlanAssignment
from maintenance.tasks import evaluate_triggers
from workorders.models import WorkOrder, WorkOrderMaterial, WorkOrderAttachment
from workorders.services import WorkOrderTransitionService


class PmInventoryDeductionTestCase(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="PM Test Tenant", tenant_code="PM_TEST_01")
        set_current_tenant(self.tenant.id)
        self.location = Location.objects.create(name="Workshop 1", code="WS1", tenant=self.tenant)
        self.category = AssetCategory.objects.create(name="CNC", tenant=self.tenant)
        self.asset = Asset.objects.create(
            name="CNC Machine 01",
            serial_number="CNC-001",
            qr_code="QR-CNC-001",
            category=self.category,
            location=self.location,
            tenant=self.tenant,
            is_active=True,
        )
        self.role = Role.objects.create(name="ADMIN", tenant=self.tenant)
        self.user = User.objects.create_user(
            username="pm_admin",
            email="pm_admin@test.local",
            password="pass",
            tenant=self.tenant,
        )
        self.user.roles.add(self.role)

    def tearDown(self):
        clear_current_tenant()

    def _create_due_pm(self, part, req_qty, name="Monthly PM"):
        plan = PmPlan.objects.create(
            tenant=self.tenant,
            name=name,
            trigger_type="TIME",
            interval_unit="DAYS",
            interval_value=7,
            lead_time_days=0,
            suppress_if_pending=True,
        )
        PmPlanMaterial.objects.create(
            tenant=self.tenant,
            pm_plan=plan,
            spare_part=part,
            quantity=req_qty,
        )
        assignment = PmPlanAssignment.objects.create(
            tenant=self.tenant,
            pm_plan=plan,
            asset=self.asset,
            status="ACTIVE",
            last_triggered_at=timezone.now() - timedelta(days=10),
        )
        return plan, assignment

    def test_sufficient_stock_deducts_and_creates_issue_transaction(self):
        part = SparePart.objects.create(
            tenant=self.tenant,
            name="Oil Filter",
            quantity_in_stock=Decimal("10.00"),
            unit_cost=Decimal("50000.00"),
            min_stock_level=Decimal("2.00"),
        )
        plan, _ = self._create_due_pm(part, Decimal("3.00"))

        evaluate_triggers()

        part.refresh_from_db()
        self.assertEqual(part.quantity_in_stock, Decimal("7.00"))

        wo = WorkOrder.objects.get(source_reference=f"PM_{plan.id}_ASSET_{self.asset.id}")
        mat = WorkOrderMaterial.objects.get(work_order=wo, spare_part=part)
        self.assertEqual(mat.quantity, Decimal("3.00"))
        self.assertEqual(mat.actual_cost, Decimal("150000.00"))

        txs = StockTransaction.all_objects.filter(work_order=wo, spare_part=part, transaction_type="ISSUE")
        self.assertEqual(txs.count(), 1)
        self.assertEqual(txs.first().quantity, Decimal("3.00"))

    def test_insufficient_stock_never_goes_negative_and_creates_no_phantom_issue(self):
        part_partial = SparePart.objects.create(
            tenant=self.tenant,
            name="Bearing X",
            quantity_in_stock=Decimal("2.00"),
            unit_cost=Decimal("100000.00"),
            min_stock_level=Decimal("5.00"),
        )
        part_zero = SparePart.objects.create(
            tenant=self.tenant,
            name="Belt Y",
            quantity_in_stock=Decimal("0.00"),
            unit_cost=Decimal("80000.00"),
            min_stock_level=Decimal("2.00"),
        )
        plan, _ = self._create_due_pm(part_partial, Decimal("5.00"), name="Insufficient PM")
        PmPlanMaterial.objects.create(
            tenant=self.tenant,
            pm_plan=plan,
            spare_part=part_zero,
            quantity=Decimal("3.00"),
        )

        evaluate_triggers()

        part_partial.refresh_from_db()
        part_zero.refresh_from_db()
        self.assertEqual(part_partial.quantity_in_stock, Decimal("2.00"))
        self.assertGreaterEqual(part_partial.quantity_in_stock, Decimal("0.00"))
        self.assertEqual(part_zero.quantity_in_stock, Decimal("0.00"))

        wo = WorkOrder.objects.get(source_reference=f"PM_{plan.id}_ASSET_{self.asset.id}")
        self.assertEqual(WorkOrderMaterial.objects.filter(work_order=wo).count(), 0)
        self.assertEqual(StockTransaction.all_objects.filter(work_order=wo, transaction_type="ISSUE").count(), 0)
        self.assertIn(str(part_partial.id), wo.required_spare_parts)
        self.assertIn(str(part_zero.id), wo.required_spare_parts)

        # Restoring/cancelling must NOT mint phantom stock
        WorkOrderTransitionService.restore_work_order_inventory(wo)
        part_partial.refresh_from_db()
        part_zero.refresh_from_db()
        self.assertEqual(part_partial.quantity_in_stock, Decimal("2.00"))
        self.assertEqual(part_zero.quantity_in_stock, Decimal("0.00"))

    def test_transaction_rollback_on_failure_preserves_stock(self):
        part = SparePart.objects.create(
            tenant=self.tenant,
            name="Servo Fuse",
            quantity_in_stock=Decimal("10.00"),
            unit_cost=Decimal("25000.00"),
        )
        plan, _ = self._create_due_pm(part, Decimal("4.00"), name="Rollback PM")

        with patch("assets.models.StockTransaction.all_objects.create", side_effect=RuntimeError("DB failure")):
            with self.assertRaises(RuntimeError):
                evaluate_triggers()

        part.refresh_from_db()
        self.assertEqual(part.quantity_in_stock, Decimal("10.00"))
        self.assertEqual(
            WorkOrder.objects.filter(source_reference=f"PM_{plan.id}_ASSET_{self.asset.id}").count(),
            0,
        )

    def test_complete_pm_work_order_does_not_double_deduct_and_restore_works(self):
        part = SparePart.objects.create(
            tenant=self.tenant,
            name="Hydraulic Seal",
            quantity_in_stock=Decimal("10.00"),
            unit_cost=Decimal("40000.00"),
        )
        plan, _ = self._create_due_pm(part, Decimal("2.00"), name="Complete PM")

        evaluate_triggers()
        part.refresh_from_db()
        self.assertEqual(part.quantity_in_stock, Decimal("8.00"))

        wo = WorkOrder.objects.get(source_reference=f"PM_{plan.id}_ASSET_{self.asset.id}")
        wo.status = "IN_PROGRESS"
        wo.assigned_to = self.user
        wo.save()
        WorkOrderAttachment.objects.create(
            tenant=self.tenant,
            work_order=wo,
            file_url="/media/pm_proof.jpg",
            file_name="pm_proof.jpg",
            file_type="image/jpeg",
            file_size=1024,
        )

        completed_wo = WorkOrderTransitionService.complete_work_order(wo.id, self.user)
        self.assertEqual(completed_wo.status, "COMPLETED")

        # Stock remains 8.00 (no double deduction on completion)
        part.refresh_from_db()
        self.assertEqual(part.quantity_in_stock, Decimal("8.00"))
        self.assertEqual(completed_wo.actual_cost, Decimal("80000.00"))


class PmConcurrencyTestCase(TransactionTestCase):
    def test_concurrent_evaluate_triggers_cannot_create_negative_stock(self):
        tenant = Tenant.objects.create(name="Concurrent PM Tenant", tenant_code="CONC_PM_01")
        loc = Location.objects.create(name="Hall A", code="HA", tenant=tenant)
        cat = AssetCategory.objects.create(name="Press", tenant=tenant)
        asset1 = Asset.objects.create(
            name="Press 1", serial_number="P1", qr_code="QR-P1",
            category=cat, location=loc, tenant=tenant, is_active=True
        )
        asset2 = Asset.objects.create(
            name="Press 2", serial_number="P2", qr_code="QR-P2",
            category=cat, location=loc, tenant=tenant, is_active=True
        )
        part = SparePart.all_objects.create(
            tenant=tenant,
            name="Shared Valve",
            quantity_in_stock=Decimal("5.00"),
            unit_cost=Decimal("10000.00"),
        )

        for idx, asset in enumerate([asset1, asset2], start=1):
            plan = PmPlan.all_objects.create(
                tenant=tenant,
                name=f"Concurrent Plan {idx}",
                trigger_type="TIME",
                interval_unit="DAYS",
                interval_value=7,
                lead_time_days=0,
            )
            PmPlanMaterial.all_objects.create(
                tenant=tenant, pm_plan=plan, spare_part=part, quantity=Decimal("4.00")
            )
            PmPlanAssignment.all_objects.create(
                tenant=tenant,
                pm_plan=plan,
                asset=asset,
                status="ACTIVE",
                last_triggered_at=timezone.now() - timedelta(days=10),
            )

        errors = []

        from django.db import connection
        def run_task():
            try:
                evaluate_triggers()
            except Exception as exc:
                errors.append(exc)
            finally:
                connection.close()

        t1 = threading.Thread(target=run_task)
        t2 = threading.Thread(target=run_task)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        part.refresh_from_db()
        self.assertGreaterEqual(part.quantity_in_stock, Decimal("0.00"))
        self.assertEqual(part.quantity_in_stock, Decimal("1.00"))

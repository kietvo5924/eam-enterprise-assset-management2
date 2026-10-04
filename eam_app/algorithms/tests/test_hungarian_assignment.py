"""
Automated Test Suite for Task 11.1 - Hungarian Assignment Optimization
(Kuhn-Munkres Algorithm with 10 Enterprise Guardrails)

Test Cases:
- TC-HUNGARY-01: Square Matrix (N = M) Optimal Assignment
- TC-HUNGARY-02: Priority Multiplier Effect (URGENT x2.5 vs LOW x1.0)
- TC-HUNGARY-03: Restricted/Cleanroom Zone Transition Penalty (+40)
- TC-HUNGARY-04: Shift Handover Clash Penalty (+40)
- TC-HUNGARY-05: Shared Tool Bottleneck Detection
- TC-HUNGARY-06: Prerequisite Task Dependency Filtering (Rule 4)
- TC-HUNGARY-07: Multi-Technician Crew Slot Decomposition (Rule 6)
- TC-HUNGARY-08: Safety Certification Violation (10^7 Big-M Hard Constraint)
- TC-HUNGARY-09: Deterministic Tie-Breaking by monthly_accumulated_hours (Rule 10)
- TC-HUNGARY-10: Concurrency Conflict Handling (HTTP 409 Conflict)
- TC-HUNGARY-11: Surplus & Shortage Dummy Zero-Cost Padding (N > M and M > N)
- TC-HUNGARY-12: Multi-Tenant Data Isolation
"""
import uuid
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from core.models import Tenant
from core.tenant_context import clear_current_tenant
from users.models import TechnicianProfile, Role, Permission
from assets.models import Asset, Tool
from workorders.models import WorkOrder
from algorithms.hungarian.service import HungarianAssignmentService, ConcurrencyConflictError
from algorithms.hungarian.constants import BIG_M, PRIORITY_MULTIPLIERS

User = get_user_model()


class HungarianAssignmentTestCase(TestCase):
    def setUp(self):
        clear_current_tenant()
        self.tenant_a = Tenant.objects.create(name="Tenant Alpha", tenant_code="T-ALPHA")
        self.tenant_b = Tenant.objects.create(name="Tenant Beta", tenant_code="T-BETA")

        # Admin / Dispatcher User
        self.dispatcher = User.objects.create_user(
            username="dispatcher_alpha",
            email="dispatcher@alpha.com",
            password="password123",
            tenant=self.tenant_a
        )
        self.dispatcher_role = Role.objects.create(name="DISPATCHER", tenant=self.tenant_a)
        perm_read = Permission.objects.get_or_create(id="work_order:read", defaults={'name': 'Read Work Order'})[0]
        perm_update = Permission.objects.get_or_create(id="work_order:update", defaults={'name': 'Update Work Order'})[0]
        self.dispatcher_role.permissions.add(perm_read, perm_update)
        self.dispatcher.roles.add(self.dispatcher_role)

        self.client = APIClient()
        self.client.force_authenticate(user=self.dispatcher)

        # Base Asset for Alpha
        self.asset_main = Asset.objects.create(
            name="Main Air Compressor",
            qr_code="QR-AC-01",
            tenant=self.tenant_a,
            coords_x=10.0,
            coords_y=10.0,
            floor_level=1,
            zone_id="ZONE_MAIN"
        )

    def tearDown(self):
        clear_current_tenant()

    def _create_tech(self, username, tenant=None, x=0.0, y=0.0, floor=1, zone="ZONE_MAIN",
                     skills=None, skill_level=3, certs=None, monthly_hours=10.0,
                     shift_end=None, availability="AVAILABLE", is_on_duty=True):
        t = tenant or self.tenant_a
        user = User.objects.create_user(
            username=username,
            email=f"{username}@{t.tenant_code.lower()}.com",
            password="password123",
            tenant=t
        )
        profile = TechnicianProfile.objects.create(
            user=user,
            tenant=t,
            coords_x=x,
            coords_y=y,
            floor_level=floor,
            zone_id=zone,
            skills=skills or ["MECHANICAL", "ELECTRICAL"],
            skill_level=skill_level,
            certifications=certs or [],
            monthly_accumulated_hours=Decimal(str(monthly_hours)),
            shift_end_time=shift_end,
            availability_status=availability,
            is_on_duty=is_on_duty
        )
        return user, profile

    def _create_wo(self, title, tenant=None, priority="MEDIUM", skill="MECHANICAL", min_level=2,
                   cert=None, tools=None, is_crew=False, depends_on=None,
                   x=10.0, y=10.0, floor=1, zone="ZONE_MAIN", duration_hours=2.0, status="CREATED"):
        t = tenant or self.tenant_a
        wo = WorkOrder.objects.create(
            title=title,
            asset=self.asset_main,
            tenant=t,
            priority=priority,
            status=status,
            required_skill=skill,
            min_skill_level=min_level,
            required_certification=cert,
            required_tools=tools or [],
            is_crew_task=is_crew,
            depends_on_wo=depends_on,
            coords_x=x,
            coords_y=y,
            floor_level=floor,
            zone_id=zone,
            estimated_duration_minutes=int(duration_hours * 60)
        )
        return wo

    # =========================================================================
    # TC-HUNGARY-01: Square Matrix (N = M) Assignment Optimality
    # =========================================================================
    def test_tc_hungary_01_square_matrix_optimal(self):
        # 3 Technicians at different coordinates
        u1, p1 = self._create_tech("tech1", x=0.0, y=0.0, skill_level=3)
        u2, p2 = self._create_tech("tech2", x=50.0, y=50.0, skill_level=3)
        u3, p3 = self._create_tech("tech3", x=100.0, y=100.0, skill_level=3)

        # 3 Work Orders near each technician
        w1 = self._create_wo("Task Near T1", x=1.0, y=1.0)
        w2 = self._create_wo("Task Near T2", x=51.0, y=51.0)
        w3 = self._create_wo("Task Near T3", x=101.0, y=101.0)

        preview = HungarianAssignmentService.preview(tenant=self.tenant_a)
        self.assertEqual(preview["assignmentsCount"], 3)
        self.assertEqual(preview["unassignedCount"], 0)

        # Optimal Kuhn-Munkres should pair tech1->w1, tech2->w2, tech3->w3
        pair_map = {str(a["workOrderId"]): a["technicianId"] for a in preview["assignments"]}
        self.assertEqual(pair_map[str(w1.id)], str(u1.id))
        self.assertEqual(pair_map[str(w2.id)], str(u2.id))
        self.assertEqual(pair_map[str(w3.id)], str(u3.id))

    # =========================================================================
    # TC-HUNGARY-02: Priority Multiplier Effect (URGENT x2.5 vs LOW x1.0)
    # =========================================================================
    def test_tc_hungary_02_priority_multiplier(self):
        u1, p1 = self._create_tech("tech_dist", x=0.0, y=0.0, skill_level=2)

        # WO Urgent vs WO Low at identical distance and skill requirement
        wo_low = self._create_wo("Low Priority", priority="LOW", x=20.0, y=20.0, min_level=3)
        wo_urgent = self._create_wo("Urgent Priority", priority="URGENT", x=20.0, y=20.0, min_level=3)

        preview_low = HungarianAssignmentService.preview(tenant=self.tenant_a, work_order_ids=[wo_low.id])
        preview_urgent = HungarianAssignmentService.preview(tenant=self.tenant_a, work_order_ids=[wo_urgent.id])

        cost_low = preview_low["assignments"][0]["cost"]
        cost_urgent = preview_urgent["assignments"][0]["cost"]

        # Urgent cost must reflect the 2.5 multiplier
        expected_ratio = PRIORITY_MULTIPLIERS["URGENT"] / PRIORITY_MULTIPLIERS["LOW"]
        self.assertAlmostEqual(cost_urgent / cost_low, expected_ratio, delta=0.01)

    # =========================================================================
    # TC-HUNGARY-03: Cleanroom / Restricted Zone Transition Penalty (+40)
    # =========================================================================
    def test_tc_hungary_03_cleanroom_zone_penalty(self):
        # Tech 1 already in Cleanroom
        u1, p1 = self._create_tech("tech_cleanroom", x=10.0, y=10.0, zone="ZONE_CLEANROOM")
        # Tech 2 in Office zone at identical distance
        u2, p2 = self._create_tech("tech_office", x=10.0, y=10.0, zone="ZONE_OFFICE")

        wo = self._create_wo("Cleanroom Maintenance", x=10.0, y=10.0, zone="ZONE_CLEANROOM")

        preview = HungarianAssignmentService.preview(tenant=self.tenant_a, work_order_ids=[wo.id])
        assigned_tech_id = preview["assignments"][0]["technicianId"]

        # Tech in Cleanroom should win assignment without the +40 penalty
        self.assertEqual(assigned_tech_id, str(u1.id))
        self.assertLess(preview["assignments"][0]["cost"], 40.0)

    # =========================================================================
    # TC-HUNGARY-04: Shift Handover Clash Penalty (+40)
    # =========================================================================
    def test_tc_hungary_04_shift_handover_clash_penalty(self):
        now = timezone.now()
        # Tech A shift ends in 30 mins (Task takes 2 hours -> clash!)
        u_ending, p_ending = self._create_tech("tech_ending", shift_end=now + timedelta(minutes=30))
        # Tech B shift ends in 5 hours (no clash)
        u_fresh, p_fresh = self._create_tech("tech_fresh", shift_end=now + timedelta(hours=5))

        wo = self._create_wo("2-Hour Inspection", duration_hours=2.0)

        preview = HungarianAssignmentService.preview(tenant=self.tenant_a, work_order_ids=[wo.id], current_time=now)
        assigned_tech_id = preview["assignments"][0]["technicianId"]

        # Fresh tech should be assigned
        self.assertEqual(assigned_tech_id, str(u_fresh.id))

    # =========================================================================
    # TC-HUNGARY-05: Shared Tool Bottleneck Detection
    # =========================================================================
    def test_tc_hungary_05_shared_tool_bottleneck(self):
        # Create single unique shared calibration tool
        tool = Tool.objects.create(
            name="Precision Torque Sensor",
            code="TOOL-TORQUE-01",
            tenant=self.tenant_a,
            available_quantity=1
        )

        u1, p1 = self._create_tech("tech_a", x=0.0, y=0.0)
        u2, p2 = self._create_tech("tech_b", x=10.0, y=10.0)

        wo1 = self._create_wo("Task requiring tool 1", tools=["TOOL-TORQUE-01"])
        wo2 = self._create_wo("Task requiring tool 2", tools=["TOOL-TORQUE-01"])

        preview = HungarianAssignmentService.preview(tenant=self.tenant_a)
        conflicts = preview.get("sharedToolConflicts", [])

        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["tool_code"], "TOOL-TORQUE-01")
        self.assertEqual(conflicts[0]["total_available"], 1)
        self.assertEqual(conflicts[0]["required_count"], 2)

    # =========================================================================
    # TC-HUNGARY-06: Prerequisite Task Dependency Filtering (Rule 4)
    # =========================================================================
    def test_tc_hungary_06_prerequisite_task_dependency(self):
        u1, p1 = self._create_tech("tech_dep")

        wo_parent = self._create_wo("Parent Task", status="CREATED")
        wo_child = self._create_wo("Child Task", depends_on=wo_parent, status="CREATED")

        # When parent is CREATED, child must be blocked and filtered out of Hungarian solver
        preview = HungarianAssignmentService.preview(tenant=self.tenant_a)
        self.assertEqual(preview["assignmentsCount"], 1)
        self.assertEqual(preview["assignments"][0]["workOrderId"], str(wo_parent.id))
        self.assertEqual(len(preview["blockedWorkOrders"]), 1)
        self.assertEqual(preview["blockedWorkOrders"][0]["workOrderId"], str(wo_child.id))

        # Once parent is COMPLETED, child becomes eligible
        wo_parent.status = "COMPLETED"
        wo_parent.save()

        preview_after = HungarianAssignmentService.preview(tenant=self.tenant_a)
        self.assertEqual(len(preview_after["blockedWorkOrders"]), 0)
        assigned_wos = [str(a["workOrderId"]) for a in preview_after["assignments"]]
        self.assertIn(str(wo_child.id), assigned_wos)

    # =========================================================================
    # TC-HUNGARY-07: Multi-Technician Crew Slot Decomposition (Rule 6)
    # =========================================================================
    def test_tc_hungary_07_crew_slot_decomposition(self):
        u1, p1 = self._create_tech("tech_lead", skill_level=4)
        u2, p2 = self._create_tech("tech_assist", skill_level=2)

        wo_crew = self._create_wo("Heavy Boiler Overhaul", is_crew=True, min_level=3)

        preview = HungarianAssignmentService.preview(tenant=self.tenant_a, work_order_ids=[wo_crew.id])
        self.assertEqual(preview["assignmentsCount"], 2)

        roles = {a["technicianId"]: a["slotRole"] for a in preview["assignments"]}
        self.assertIn("LEAD", roles.values())
        self.assertIn("ASSIST", roles.values())
        # Lead should be given to higher skill tech
        self.assertEqual(roles[str(u1.id)], "LEAD")
        self.assertEqual(roles[str(u2.id)], "ASSIST")

    # =========================================================================
    # TC-HUNGARY-08: Safety Certification Violation (10^7 Big-M Hard Constraint)
    # =========================================================================
    def test_tc_hungary_08_safety_certification_big_m(self):
        # Tech 1 has HIGH_VOLTAGE cert
        u1, p1 = self._create_tech("tech_certified", certs=["HIGH_VOLTAGE"])
        # Tech 2 lacks certification
        u2, p2 = self._create_tech("tech_uncertified", certs=[])

        wo_hv = self._create_wo("HV Switchgear Repair", cert="HIGH_VOLTAGE")

        preview = HungarianAssignmentService.preview(tenant=self.tenant_a, work_order_ids=[wo_hv.id])
        self.assertEqual(preview["assignmentsCount"], 1)
        self.assertEqual(preview["assignments"][0]["technicianId"], str(u1.id))
        self.assertFalse(preview["assignments"][0]["isSafetyViolation"])

        # Cost for uncertified tech in the cost matrix must be >= BIG_M
        matrix = preview["costMatrix"]
        # Matrix rows map to sorted techs; find row for tech2
        tech_order = preview["matrixHeader"]["technicians"]
        t2_idx = tech_order.index(u2.username)
        self.assertGreaterEqual(matrix[t2_idx][0], BIG_M / 2.0)

    # =========================================================================
    # TC-HUNGARY-09: Deterministic Tie-Breaking by monthly_accumulated_hours
    # =========================================================================
    def test_tc_hungary_09_deterministic_tie_breaker(self):
        # Both techs have identical skills, locations, and status
        u_busy, p_busy = self._create_tech("tech_busy_hours", monthly_hours=50.0)
        u_fresh, p_fresh = self._create_tech("tech_fresh_hours", monthly_hours=10.0)

        wo = self._create_wo("General Pump Lubrication")

        preview = HungarianAssignmentService.preview(tenant=self.tenant_a, work_order_ids=[wo.id])
        assigned_tech_id = preview["assignments"][0]["technicianId"]

        # The tech with fewer monthly accumulated hours must be prioritized
        self.assertEqual(assigned_tech_id, str(u_fresh.id))

    # =========================================================================
    # TC-HUNGARY-10: Concurrency Conflict Handling (HTTP 409 Conflict)
    # =========================================================================
    def test_tc_hungary_10_concurrency_conflict(self):
        u1, p1 = self._create_tech("tech_lock")
        wo = self._create_wo("Urgent Motor Replacement")

        # 1. Dispatcher generates preview
        response = self.client.post("/api/v1/work-orders/auto-assign/preview/", {
            "workOrderIds": [str(wo.id)]
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # 2. Simulate concurrent dispatcher altering the technician's status
        p1.availability_status = "BUSY"
        p1.save()

        # 3. Apply assignment plan -> must raise HTTP 409
        apply_payload = {
            "assignments": [
                {
                    "workOrderId": str(wo.id),
                    "technicianId": str(u1.id),
                    "slotRole": "SOLO"
                }
            ]
        }
        apply_resp = self.client.post("/api/v1/work-orders/auto-assign/apply/", apply_payload, format="json")
        self.assertEqual(apply_resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(apply_resp.data["error"]["code"], "CONCURRENT_DISPATCH_CONFLICT")

    # =========================================================================
    # TC-HUNGARY-11: Surplus & Shortage Dummy Zero-Cost Padding
    # =========================================================================
    def test_tc_hungary_11_dummy_zero_cost_padding(self):
        # Case A: Surplus Technicians (N > M) -> 3 Techs, 1 Work Order
        u1, p1 = self._create_tech("t1", x=0.0, y=0.0)
        u2, p2 = self._create_tech("t2", x=20.0, y=20.0)
        u3, p3 = self._create_tech("t3", x=40.0, y=40.0)
        wo1 = self._create_wo("Single Task", x=0.0, y=0.0)

        preview_surplus_tech = HungarianAssignmentService.preview(tenant=self.tenant_a, work_order_ids=[wo1.id])
        self.assertEqual(preview_surplus_tech["assignmentsCount"], 1)
        self.assertEqual(preview_surplus_tech["assignments"][0]["technicianId"], str(u1.id))

        # Case B: Surplus Work Orders (M > N) -> 1 Tech, 3 Work Orders
        wo2 = self._create_wo("Urgent Second Task", priority="URGENT", x=5.0, y=5.0)
        wo3 = self._create_wo("Third Task", priority="LOW", x=10.0, y=10.0)

        # Filter preview to only t1
        TechnicianProfile.objects.filter(id__in=[p2.id, p3.id]).update(availability_status="BUSY")

        preview_surplus_wo = HungarianAssignmentService.preview(tenant=self.tenant_a)
        self.assertEqual(preview_surplus_wo["assignmentsCount"], 1)
        # Urgent task must be selected over low priority tasks
        self.assertEqual(preview_surplus_wo["assignments"][0]["workOrderId"], str(wo2.id))
        # Remainder placed in unassigned queue
        self.assertEqual(preview_surplus_wo["unassignedCount"], 2)

    # =========================================================================
    # TC-HUNGARY-12: Multi-Tenant Data Isolation
    # =========================================================================
    def test_tc_hungary_12_multi_tenant_isolation(self):
        # Alpha data
        u_alpha, p_alpha = self._create_tech("tech_alpha", tenant=self.tenant_a)
        wo_alpha = self._create_wo("Alpha Task", tenant=self.tenant_a)

        # Beta data
        u_beta, p_beta = self._create_tech("tech_beta", tenant=self.tenant_b)
        wo_beta = self._create_wo("Beta Task", tenant=self.tenant_b)

        # Run preview for Tenant Alpha
        preview_a = HungarianAssignmentService.preview(tenant=self.tenant_a)
        assigned_techs_a = [a["technicianId"] for a in preview_a["assignments"]]
        assigned_wos_a = [str(a["workOrderId"]) for a in preview_a["assignments"]]

        self.assertIn(str(u_alpha.id), assigned_techs_a)
        self.assertNotIn(str(u_beta.id), assigned_techs_a)
        self.assertIn(str(wo_alpha.id), assigned_wos_a)
        self.assertNotIn(str(wo_beta.id), assigned_wos_a)

    # =========================================================================
    # TC-HUNGARY-13: Dynamic In-Progress Location Anchoring (No GPS Required)
    # =========================================================================
    def test_tc_hungary_13_dynamic_in_progress_location_anchoring(self):
        """
        When a technician is executing an IN_PROGRESS ticket at an asset,
        their dispatch origin dynamically anchors to that asset's location
        instead of their static base duty station.
        """
        # Tech 1 base station is Zone A (0, 0)
        u1, p1 = self._create_tech("tech_chain", x=0.0, y=0.0, zone="ZONE_A", skill_level=3)

        # Tech 1 is currently physically working on a job in Zone B at (80, 80)
        wo_active = self._create_wo(
            "Ongoing Maintenance",
            x=80.0, y=80.0, zone="ZONE_B",
            status="IN_PROGRESS"
        )
        wo_active.assigned_to = u1
        wo_active.save()

        # A new work order is created right next to Tech 1 in Zone B at (82, 80)
        wo_next = self._create_wo(
            "Next Task Adjacent",
            x=82.0, y=80.0, zone="ZONE_B",
            status="CREATED"
        )

        preview = HungarianAssignmentService.preview(tenant=self.tenant_a, work_order_ids=[wo_next.id])
        self.assertEqual(preview["assignmentsCount"], 1)

        bdown = preview["assignments"][0]["breakdown"]
        # Distance should be 2 meters (|80-82| + |80-80|) * 0.1 = 0.2đ
        # NOT the 162 meters (|0-82| + |0-80|) from static base station!
        self.assertAlmostEqual(bdown["distanceScore"], 0.2, places=2)
        # Zone penalty should be 0.0 because Tech 1 is already inside Zone B
        self.assertEqual(bdown["zonePenalty"], 0.0)


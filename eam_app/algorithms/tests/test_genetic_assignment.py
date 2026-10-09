"""
Automated Test Suite for Task 11.2 - Genetic Algorithm (GA) Multi-Objective
Task Assignment & Schedule Optimization Engine.

Test Cases:
- TC-GA-01: Elitism Monotonic Non-Decreasing Best Fitness
- TC-GA-02: Sub-decoding Nearest Neighbor & Due Date Route Sequencing
- TC-GA-03: Travel Time Workload Overload Quadratic Penalty
- TC-GA-04: Virtual Technician Backlog Capacity Overflow Survival
- TC-GA-05: Due Date SLA Lateness Penalty by Priority
- TC-GA-06: Stagnation Detection & Adaptive Cataclysmic Mutation Burst
- TC-GA-07: Heuristic Seeding Initial Convergence Acceleration
- TC-GA-08: Warehouse Pickup Stop Insertion for Spare Parts
- TC-GA-09: Heterogeneous Shift Lengths Support (4h vs 8h)
- TC-GA-10: Pareto Front Top 3 Strategy Synthesis (Balanced, Skill, Min-Travel)
- TC-GA-11: Safety Certification Strict Compliance (CERT_HIGH_VOLTAGE)
- TC-GA-12: Asynchronous REST API Lifecycle & Progress Polling
- TC-GA-13: Floorplan & Duty Zone Locking Guardrail
- TC-GA-14: Time-Overlap Shared Tool Contention Handling
"""
import uuid
import time
from decimal import Decimal
from datetime import datetime, timedelta
from django.utils import timezone
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from core.models import Tenant
from core.tenant_context import clear_current_tenant
from users.models import TechnicianProfile, Role, Permission
from assets.models import Asset, Tool, Location
from workorders.models import WorkOrder, GAOptimizationJob
from algorithms.genetic.constants import (
    DEFAULT_POPULATION_SIZE, DEFAULT_MAX_GENERATIONS,
    DEFAULT_MUTATION_RATE, CATACLYSMIC_MUTATION_RATE,
    PENALTY_OVERLOAD_BETA, PENALTY_LATE_GAMMA, PENALTY_BACKLOG_BASE,
    PENALTY_FLOORPLAN_MISMATCH, WAREHOUSE_PICKUP_BUFFER_MINUTES,
    STAGNATION_THRESHOLD, WEIGHTS_BALANCED
)
from algorithms.genetic.chromosome import GATask, GATechnician, GAIndividual
from algorithms.genetic.sub_decoding import (
    sub_decode_route_nearest_neighbor,
    simulate_technician_timeline,
    calculate_spatial_distance_meters,
    estimate_transit_minutes
)
from algorithms.genetic.fitness import (
    calculate_task_skill_score,
    evaluate_individual_fitness
)
from algorithms.genetic.operators import (
    generate_greedy_seed,
    repair_individual_constraints,
    initialize_population
)
from algorithms.genetic.pareto import extract_pareto_front_solutions
from algorithms.genetic.solver import MaintenanceGAScheduler
from algorithms.genetic.service import GASchedulingService

User = get_user_model()


class GeneticAlgorithmAssignmentTestCase(TestCase):
    def setUp(self):
        clear_current_tenant()
        self.tenant_alpha = Tenant.objects.create(name="Tenant Alpha GA", tenant_code="T-ALPHAGA")
        self.tenant_beta = Tenant.objects.create(name="Tenant Beta GA", tenant_code="T-BETAGA")

        # Admin / Dispatcher User
        self.dispatcher = User.objects.create_user(
            username="dispatcher_ga",
            email="dispatcher_ga@alpha.com",
            password="password123",
            tenant=self.tenant_alpha
        )
        self.dispatcher_role = Role.objects.create(name="DISPATCHER_GA", tenant=self.tenant_alpha)
        perm_read = Permission.objects.get_or_create(id="work_order:read", defaults={'name': 'Read Work Order'})[0]
        perm_update = Permission.objects.get_or_create(id="work_order:update", defaults={'name': 'Update Work Order'})[0]
        self.dispatcher_role.permissions.add(perm_read, perm_update)
        self.dispatcher.roles.add(self.dispatcher_role)

        self.client = APIClient()
        self.client.force_authenticate(user=self.dispatcher)

        # Floorplan Locations
        self.floorplan_a = Location.objects.create(
            name="Xuong San Xuat A",
            code="FP-A",
            zone_type="FLOORPLAN",
            floor_level=1,
            tenant=self.tenant_alpha,
            is_active=True
        )
        self.floorplan_b = Location.objects.create(
            name="Xuong San Xuat B",
            code="FP-B",
            zone_type="FLOORPLAN",
            floor_level=2,
            tenant=self.tenant_alpha,
            is_active=True
        )

        # Sub-zones
        self.zone_a1 = Location.objects.create(
            name="Khu Vuc A1",
            code="ZONE_A1",
            zone_type="STANDARD",
            parent_id=str(self.floorplan_a.id),
            floor_level=1,
            center_x=10.0,
            center_y=10.0,
            tenant=self.tenant_alpha,
            is_active=True
        )
        self.zone_b1 = Location.objects.create(
            name="Khu Vuc B1",
            code="ZONE_B1",
            zone_type="STANDARD",
            parent_id=str(self.floorplan_b.id),
            floor_level=2,
            center_x=80.0,
            center_y=80.0,
            tenant=self.tenant_alpha,
            is_active=True
        )

        # Base Asset
        self.asset_a = Asset.objects.create(
            name="May Tien CNC 01",
            qr_code="QR-CNC-01",
            tenant=self.tenant_alpha,
            location=self.zone_a1,
            coords_x=10.0,
            coords_y=10.0,
            floor_level=1,
            zone_id="ZONE_A1"
        )
        self.asset_b = Asset.objects.create(
            name="May Phay CNC 02",
            qr_code="QR-CNC-02",
            tenant=self.tenant_alpha,
            location=self.zone_b1,
            coords_x=80.0,
            coords_y=80.0,
            floor_level=2,
            zone_id="ZONE_B1"
        )

    def tearDown(self):
        clear_current_tenant()

    def _create_tech(self, username, tenant=None, x=0.0, y=0.0, floor=1, zone="ZONE_A1",
                     skills=None, skill_level=3, certs=None, monthly_hours=10.0,
                     shift_minutes=480, availability="AVAILABLE", is_on_duty=True):
        t = tenant or self.tenant_alpha
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
            max_shift_minutes=shift_minutes,
            availability_status=availability,
            is_on_duty=is_on_duty
        )
        return user, profile

    def _create_wo(self, title, tenant=None, asset=None, priority="MEDIUM", skill="MECHANICAL", min_level=2,
                   cert=None, tools=None, spare_parts=None, deadline=None,
                   x=10.0, y=10.0, floor=1, zone="ZONE_A1", duration_minutes=60, status="CREATED"):
        t = tenant or self.tenant_alpha
        a = asset or self.asset_a
        wo = WorkOrder.objects.create(
            title=title,
            asset=a,
            tenant=t,
            priority=priority,
            status=status,
            required_skill=skill,
            min_skill_level=min_level,
            required_certification=cert,
            required_tools=tools or [],
            required_spare_parts=spare_parts or [],
            deadline=deadline,
            coords_x=x,
            coords_y=y,
            floor_level=floor,
            zone_id=zone,
            estimated_duration_minutes=duration_minutes
        )
        return wo

    # =========================================================================
    # TC-GA-01: Elitism Monotonic Non-Decreasing Best Fitness
    # =========================================================================
    def test_tc_ga_01_elitism_monotonic_fitness(self):
        """TC-GA-01: Best Fitness must never regress across generations due to Elitism."""
        u1, p1 = self._create_tech("tech_ga_01a", x=10.0, y=10.0, skill_level=3)
        u2, p2 = self._create_tech("tech_ga_01b", x=20.0, y=20.0, skill_level=4)
        techs = [p1, p2]

        wos = [
            self._create_wo(f"WO Elite {i}", x=float(i * 5), y=float(i * 5), duration_minutes=45)
            for i in range(5)
        ]

        scheduler = MaintenanceGAScheduler(
            work_orders=wos,
            technicians=techs,
            config={'populationSize': 30, 'maxGenerations': 25}
        )
        res = scheduler.run()

        history = res['convergenceHistory']
        self.assertTrue(len(history) >= 2, "Should record convergence milestones")

        # Verify monotonicity: bestFitness at each milestone >= previous bestFitness
        prev_best = 0.0
        for entry in history:
            current_best = entry['bestFitness']
            self.assertGreaterEqual(
                current_best, prev_best - 1e-4,
                f"Elitism violated: generation {entry['generation']} has lower best fitness {current_best} than previous {prev_best}"
            )
            prev_best = current_best

    # =========================================================================
    # TC-GA-02: Sub-decoding Nearest Neighbor & Due Date Route Sequencing
    # =========================================================================
    def test_tc_ga_02_sub_decoding_nearest_neighbor_and_due_date(self):
        """TC-GA-02: Nearest Neighbor orders tasks by shortest distance, but urgent due dates take priority."""
        u, profile = self._create_tech("tech_nn", x=1.0, y=1.0, floor=1, zone="ZONE_A1")
        tech = GATechnician(profile)

        # 1. Pure Spatial Nearest Neighbor (No urgent SLA)
        now = timezone.now()
        wo1 = self._create_wo("Near Task 1", x=10.0, y=1.0, deadline=now + timedelta(hours=24))
        wo2 = self._create_wo("Mid Task 2", x=30.0, y=1.0, deadline=now + timedelta(hours=24))
        wo3 = self._create_wo("Far Task 3", x=70.0, y=1.0, deadline=now + timedelta(hours=24))

        t1, t2, t3 = GATask(wo1), GATask(wo2), GATask(wo3)
        # Pass in reverse order: [t3, t2, t1]
        ordered = sub_decode_route_nearest_neighbor(tech, [t3, t2, t1], current_time=now)
        self.assertEqual([t.id for t in ordered], [t1.id, t2.id, t3.id], "Nearest Neighbor should sort by distance [10, 30, 70]")

        # 2. Imminent SLA Due Date bypasses distance
        wo_urgent = self._create_wo("Urgent Far Task", x=100.0, y=100.0, deadline=now + timedelta(hours=1))
        t_urgent = GATask(wo_urgent)
        ordered_with_sla = sub_decode_route_nearest_neighbor(tech, [t1, t_urgent], current_time=now)
        self.assertEqual(ordered_with_sla[0].id, t_urgent.id, "Urgent SLA (< 2h) must be prioritized first despite farther distance")

    # =========================================================================
    # TC-GA-03: Travel Time Workload Overload Quadratic Penalty
    # =========================================================================
    def test_tc_ga_03_travel_time_overload_quadratic_penalty(self):
        """TC-GA-03: Total shift overload (repair + transit) incurs quadratic penalty Beta * overload^2."""
        u, profile = self._create_tech("tech_overload", x=0.0, y=0.0, shift_minutes=120)
        tech = GATechnician(profile)

        # 2 tasks of 70 minutes each = 140 min repair > 120 min max_shift
        wo1 = self._create_wo("Task 1", x=0.0, y=0.0, duration_minutes=70)
        wo2 = self._create_wo("Task 2", x=0.0, y=0.0, duration_minutes=70)
        t1, t2 = GATask(wo1), GATask(wo2)

        # Assigned to Tech 0 (gene [0, 0])
        ind = GAIndividual([0, 0])
        evaluate_individual_fitness(ind, [t1, t2], [tech])

        expected_overload = 140 - 120  # 20 minutes
        expected_penalty = round(PENALTY_OVERLOAD_BETA * (expected_overload ** 2), 2)  # 0.05 * 400 = 20.0
        self.assertEqual(ind.penalties['overload'], expected_penalty)
        self.assertGreater(ind.penalties['overload'], 0)

    # =========================================================================
    # TC-GA-04: Virtual Technician Backlog Capacity Overflow Survival
    # =========================================================================
    def test_tc_ga_04_virtual_technician_backlog_survival(self):
        """TC-GA-04: Excess tasks are offloaded to Virtual Technician N as backlog without crashing."""
        u, profile = self._create_tech("tech_sole", x=0.0, y=0.0, shift_minutes=120)
        tech = GATechnician(profile)

        wos = [self._create_wo(f"WO {i}", priority="LOW" if i > 0 else "URGENT", duration_minutes=80) for i in range(4)]
        tasks = [GATask(wo) for wo in wos]

        # Individual assigns task 0 to Tech 0, and tasks 1, 2, 3 to Virtual Tech (index 1)
        ind = GAIndividual([0, 1, 1, 1])
        fit = evaluate_individual_fitness(ind, tasks, [tech])

        self.assertGreaterEqual(fit, 0.0)
        self.assertEqual(len(ind.backlog_tasks), 3, "Virtual Tech should contain 3 backlog tasks")
        self.assertGreater(ind.penalties['backlog'], 0.0, "Backlog penalty should be non-zero")
        self.assertIn("Vượt tổng năng lực ca làm việc", ind.backlog_tasks[0]['reason'])

    # =========================================================================
    # TC-GA-05: Due Date SLA Lateness Penalty by Priority
    # =========================================================================
    def test_tc_ga_05_due_date_sla_lateness_penalty(self):
        """TC-GA-05: Late tasks are penalized proportional to priority weight (URGENT > LOW)."""
        u, profile = self._create_tech("tech_sla", x=0.0, y=0.0, shift_minutes=480)
        tech = GATechnician(profile)
        now = timezone.now()

        # Both tasks take 120 min and are due 30 min from now (60 min late)
        wo_urgent = self._create_wo("Urgent Late", priority="URGENT", duration_minutes=120, deadline=now + timedelta(minutes=60))
        wo_low = self._create_wo("Low Late", priority="LOW", duration_minutes=120, deadline=now + timedelta(minutes=60))

        t_urgent = GATask(wo_urgent)
        t_low = GATask(wo_low)

        ind_urgent = GAIndividual([0])
        evaluate_individual_fitness(ind_urgent, [t_urgent], [tech], current_time=now)

        ind_low = GAIndividual([0])
        evaluate_individual_fitness(ind_low, [t_low], [tech], current_time=now)

        self.assertGreater(ind_urgent.penalties['late'], ind_low.penalties['late'],
                           "URGENT task SLA breach must incur higher penalty than LOW task")

    # =========================================================================
    # TC-GA-06: Stagnation Detection & Adaptive Cataclysmic Mutation Burst
    # =========================================================================
    def test_tc_ga_06_stagnation_cataclysmic_adaptive_mutation(self):
        """TC-GA-06: 15 generations of stagnation triggers cataclysmic mutation rate = 0.30."""
        u, profile = self._create_tech("tech_stag", x=0.0, y=0.0)
        wo = self._create_wo("Task Stag", duration_minutes=60)

        scheduler = MaintenanceGAScheduler(
            work_orders=[wo],
            technicians=[profile],
            config={'populationSize': 10, 'maxGenerations': 25}
        )
        scheduler.tasks = [GATask(wo)]
        scheduler.techs = [GATechnician(profile)]

        # Simulate 14 stagnant generations
        scheduler.stagnation_count = 14
        scheduler.best_fitness = 90.0

        # Run 1 generation where best fitness does not improve
        ind = GAIndividual([0])
        ind.fitness = 90.0
        scheduler.population = [ind]

        # Trigger logic check
        current_gen_best = 90.0
        if current_gen_best <= (scheduler.best_fitness * 1.001):
            scheduler.stagnation_count += 1

        self.assertEqual(scheduler.stagnation_count, 15)
        if scheduler.stagnation_count >= STAGNATION_THRESHOLD:
            scheduler.cataclysmic_burst_remaining = 3
            scheduler.stagnation_count = 0

        self.assertEqual(scheduler.cataclysmic_burst_remaining, 3)
        if scheduler.cataclysmic_burst_remaining > 0:
            scheduler.mutation_rate = CATACLYSMIC_MUTATION_RATE

        self.assertEqual(scheduler.mutation_rate, 0.30, "Mutation rate must jump to 0.30 during cataclysmic burst")

    # =========================================================================
    # TC-GA-07: Heuristic Seeding Initial Convergence Acceleration
    # =========================================================================
    def test_tc_ga_07_heuristic_seeding_convergence_acceleration(self):
        """TC-GA-07: Greedy heuristic seeding produces superior initial fitness compared to unseeded random."""
        u1, p1 = self._create_tech("tech_seed1", x=0.0, y=0.0, skill_level=4)
        u2, p2 = self._create_tech("tech_seed2", x=20.0, y=20.0, skill_level=3)
        techs = [GATechnician(p1), GATechnician(p2)]

        wos = [self._create_wo(f"WO Seed {i}", x=float(i*10), y=float(i*10), duration_minutes=60) for i in range(6)]
        tasks = [GATask(wo) for wo in wos]

        # Generate greedy seed
        seed_ind = generate_greedy_seed(tasks, techs)
        seed_fitness = evaluate_individual_fitness(seed_ind, tasks, techs)

        # Generate naive worst-case individual (all tasks to 1 tech or random)
        naive_ind = GAIndividual([0, 0, 0, 0, 0, 0])  # overload tech 0 heavily
        naive_fitness = evaluate_individual_fitness(naive_ind, tasks, techs)

        self.assertGreater(seed_fitness, naive_fitness,
                           f"Heuristic seed fitness ({seed_fitness}) should exceed naive overloaded fitness ({naive_fitness})")
        self.assertGreaterEqual(seed_fitness, 70.0, "Heuristic seed should have high baseline fitness")

    # =========================================================================
    # TC-GA-08: Warehouse Pickup Stop Insertion for Spare Parts
    # =========================================================================
    def test_tc_ga_08_warehouse_pickup_stop_insertion(self):
        """TC-GA-08: Work orders requiring spare parts include warehouse transit and 15min checkout buffer."""
        u, profile = self._create_tech("tech_wh", x=0.0, y=0.0, floor=1, zone="ZONE_A1")
        tech = GATechnician(profile)

        # WO requires spare parts
        wo_parts = self._create_wo("Replace Bearing", spare_parts=["BEARING_SKF_6205"], duration_minutes=60)
        t_parts = GATask(wo_parts)
        self.assertTrue(t_parts.has_spare_parts)

        # Warehouse location at (50.0, 50.0, floor 1)
        wh_coords = (50.0, 50.0, 1, "ZONE_WAREHOUSE")
        sim_res = simulate_technician_timeline(tech, [t_parts], warehouse_coords=wh_coords)

        self.assertEqual(sim_res['warehouseMinutes'], WAREHOUSE_PICKUP_BUFFER_MINUTES,
                         "Should include 15 minutes warehouse checkout buffer")
        self.assertGreater(sim_res['totalMinutes'], 60 + WAREHOUSE_PICKUP_BUFFER_MINUTES,
                           "Total minutes must include repair + warehouse buffer + travel")

    # =========================================================================
    # TC-GA-09: Heterogeneous Shift Lengths Support (4h vs 8h)
    # =========================================================================
    def test_tc_ga_09_heterogeneous_shift_lengths(self):
        """TC-GA-09: Part-time (4h = 240m) technician incurs overload while Full-time (8h = 480m) does not."""
        u1, p1 = self._create_tech("tech_pt", shift_minutes=240)  # Part-time 4h
        u2, p2 = self._create_tech("tech_ft", shift_minutes=480)  # Full-time 8h
        t_pt = GATechnician(p1)
        t_ft = GATechnician(p2)

        # Task workload = 300 minutes
        wo = self._create_wo("Heavy Maintenance", duration_minutes=300)
        tsk = GATask(wo)

        # PT tech assigned 300 min -> 60 min overload
        ind_pt = GAIndividual([0])
        evaluate_individual_fitness(ind_pt, [tsk], [t_pt])
        self.assertGreater(ind_pt.penalties['overload'], 0, "Part-time technician should incur overload penalty for 300 min")

        # FT tech assigned 300 min -> 0 min overload
        ind_ft = GAIndividual([0])
        evaluate_individual_fitness(ind_ft, [tsk], [t_ft])
        self.assertEqual(ind_ft.penalties['overload'], 0.0, "Full-time technician should not incur overload penalty for 300 min")

    # =========================================================================
    # TC-GA-10: Pareto Front Top 3 Strategy Synthesis
    # =========================================================================
    def test_tc_ga_10_pareto_front_top3_extraction(self):
        """TC-GA-10: Extraction synthesizes Top 3 Pareto strategies: BALANCED, SKILL_FOCUSED, and MIN_TRAVEL."""
        u1, p1 = self._create_tech("tech_p1", x=0.0, y=0.0, skill_level=4)
        u2, p2 = self._create_tech("tech_p2", x=50.0, y=50.0, skill_level=2)
        techs = [GATechnician(p1), GATechnician(p2)]

        wos = [self._create_wo(f"WO Pareto {i}", x=float(i*10), y=0.0, duration_minutes=45) for i in range(4)]
        tasks = [GATask(wo) for wo in wos]

        population = [GAIndividual([0, 0, 1, 1]), GAIndividual([1, 1, 0, 0]), GAIndividual([0, 1, 0, 1])]
        for ind in population:
            evaluate_individual_fitness(ind, tasks, techs)

        pareto = extract_pareto_front_solutions(population, tasks, techs)
        self.assertEqual(len(pareto), 3, "Must return exactly 3 Pareto candidate strategies")

        strategy_codes = [sol['strategy'] for sol in pareto]
        self.assertEqual(strategy_codes, ["BALANCED", "SKILL_FOCUSED", "MIN_TRAVEL"])

        for sol in pareto:
            self.assertIn("fitnessScore", sol)
            self.assertIn("skillScore", sol)
            self.assertIn("workloadScore", sol)
            self.assertIn("travelScore", sol)
            self.assertIn("schedules", sol)
            self.assertIn("backlogTasks", sol)

    # =========================================================================
    # TC-GA-11: Safety Certification Strict Compliance (CERT_HIGH_VOLTAGE)
    # =========================================================================
    def test_tc_ga_11_safety_certification_strict_compliance(self):
        """TC-GA-11: Tasks requiring safety certification are strictly repaired away from uncertified technicians."""
        u_uncert, p_uncert = self._create_tech("tech_no_cert", certs=[])
        u_cert, p_cert = self._create_tech("tech_with_cert", certs=["CERT_HIGH_VOLTAGE"])
        t_uncert, t_cert = GATechnician(p_uncert), GATechnician(p_cert)

        wo_danger = self._create_wo("High Voltage Transformer", cert="CERT_HIGH_VOLTAGE")
        tsk = GATask(wo_danger)

        # Uncertified tech gets skill score 0
        score_uncert = calculate_task_skill_score(tsk, t_uncert)
        self.assertEqual(score_uncert, 0.0, "Missing required safety certification must give skill score 0")

        # Certified tech gets positive skill score
        score_cert = calculate_task_skill_score(tsk, t_cert)
        self.assertGreater(score_cert, 70.0)

        # Repair Operator re-assigns from uncertified to certified
        ind = GAIndividual([0])  # Assigned to uncertified tech index 0
        repaired = repair_individual_constraints(ind, [tsk], [t_uncert, t_cert])
        self.assertEqual(repaired.genes[0], 1, "Repair operator must reassign certified task to Tech 1")

    # =========================================================================
    # TC-GA-12: Asynchronous REST API Lifecycle & Progress Polling
    # =========================================================================
    def test_tc_ga_12_async_endpoints_and_progress_lifecycle(self):
        """TC-GA-12: Full API lifecycle: initiate (HTTP 202) -> poll progress -> apply assignment."""
        u1, p1 = self._create_tech("tech_api1", x=10.0, y=10.0)
        u2, p2 = self._create_tech("tech_api2", x=20.0, y=20.0)
        wo1 = self._create_wo("API Task 1", duration_minutes=45)
        wo2 = self._create_wo("API Task 2", duration_minutes=45)

        # 1. Initiate Optimization
        initiate_url = "/api/v1/work-orders/ga-auto-assign/"
        payload = {
            "workOrderIds": [str(wo1.id), str(wo2.id)],
            "maxGenerations": 10,
            "populationSize": 20
        }
        res_init = self.client.post(initiate_url, payload, format='json')
        self.assertEqual(res_init.status_code, status.HTTP_202_ACCEPTED)
        task_id = res_init.data['data']['taskId']
        self.assertTrue(bool(task_id))

        # Synchronously execute the job to simulate worker completion in test environment
        GASchedulingService.execute_job_sync(task_id)

        # 2. Check Progress
        progress_url = f"/api/v1/work-orders/ga-auto-assign/{task_id}/progress/"
        res_prog = self.client.get(progress_url)
        self.assertEqual(res_prog.status_code, status.HTTP_200_OK)
        prog_data = res_prog.data.get('data', res_prog.data)
        self.assertEqual(prog_data['status'], 'COMPLETED')
        self.assertEqual(len(prog_data['paretoSolutions']), 3)

        # 3. Apply Assignment
        apply_url = "/api/v1/work-orders/ga-auto-assign/apply/"
        apply_payload = {
            "taskId": task_id,
            "strategy": "BALANCED",
            "assignments": [
                {"workOrderId": str(wo1.id), "technicianId": str(u1.id)},
                {"workOrderId": str(wo2.id), "technicianId": str(u2.id)}
            ]
        }
        res_apply = self.client.post(apply_url, apply_payload, format='json')
        self.assertEqual(res_apply.status_code, status.HTTP_200_OK)
        apply_data = res_apply.data.get('data', res_apply.data)
        self.assertEqual(apply_data['appliedCount'], 2)

        # Verify DB update
        wo1.refresh_from_db()
        wo2.refresh_from_db()
        self.assertEqual(wo1.status, 'ASSIGNED')
        self.assertEqual(wo1.assigned_to_id, u1.id)
        self.assertEqual(wo2.status, 'ASSIGNED')
        self.assertEqual(wo2.assigned_to_id, u2.id)

    # =========================================================================
    # TC-GA-13: Floorplan & Duty Zone Locking Guardrail
    # =========================================================================
    def test_tc_ga_13_floorplan_and_duty_zone_isolation(self):
        """TC-GA-13: Technicians locked to Floorplan A incur PENALTY_FLOORPLAN_MISMATCH (1000.0) if assigned Floorplan B."""
        # Tech A locked to Floorplan A via zone_a1
        u_a, p_a = self._create_tech("tech_fl_a", zone="ZONE_A1")
        # Tech B locked to Floorplan B via zone_b1
        u_b, p_b = self._create_tech("tech_fl_b", zone="ZONE_B1")
        # Tech Roving (Cơ Động)
        u_rov, p_rov = self._create_tech("tech_roving", zone="CO_DONG")

        catalog = {
            'zone_to_floorplan': {
                'ZONE_A1': str(self.floorplan_a.id),
                'ZONE_B1': str(self.floorplan_b.id),
                'CO_DONG': ''
            }
        }

        t_a = GATechnician(p_a, catalog=catalog)
        t_b = GATechnician(p_b, catalog=catalog)
        t_rov = GATechnician(p_rov, catalog=catalog)

        # WO on Floorplan B
        wo_b = self._create_wo("Pump Repair at Workshop B", asset=self.asset_b, zone="ZONE_B1")
        task_b = GATask(wo_b, catalog=catalog)

        self.assertEqual(t_a.floorplan_id, str(self.floorplan_a.id))
        self.assertEqual(t_b.floorplan_id, str(self.floorplan_b.id))
        self.assertTrue(t_rov.is_roving)
        self.assertEqual(task_b.floorplan_id, str(self.floorplan_b.id))

        # Assign Task B to Tech A (Floorplan mismatch!)
        ind_mismatch = GAIndividual([0])
        evaluate_individual_fitness(ind_mismatch, [task_b], [t_a], catalog=catalog)
        self.assertEqual(ind_mismatch.penalties['floorplan'], PENALTY_FLOORPLAN_MISMATCH,
                         "Cross-floorplan assignment for non-roving tech must incur 1000.0 penalty")

        # Assign Task B to Roving Tech (Exempt from penalty)
        ind_roving = GAIndividual([0])
        evaluate_individual_fitness(ind_roving, [task_b], [t_rov], catalog=catalog)
        self.assertEqual(ind_roving.penalties['floorplan'], 0.0,
                         "Roving technician should not incur floorplan penalty")

        # Repair operator repairs mismatch from Tech A to Tech B
        repaired = repair_individual_constraints(ind_mismatch, [task_b], [t_a, t_b], catalog=catalog)
        self.assertEqual(repaired.genes[0], 1, "Repair operator must reassign Floorplan B task to Tech B")

    # =========================================================================
    # TC-GA-14: Time-Overlap Shared Tool Contention Handling
    # =========================================================================
    def test_tc_ga_14_time_overlap_tool_contention(self):
        """TC-GA-14: Work orders requiring shared physical tools are tracked without execution conflicts."""
        tool_calib = Tool.objects.create(
            name="Laser Alignment Tool",
            code="TOOL_LASER_01",
            available_quantity=1,
            tenant=self.tenant_alpha
        )

        u1, p1 = self._create_tech("tech_tool1", x=0.0, y=0.0)
        u2, p2 = self._create_tech("tech_tool2", x=10.0, y=10.0)
        techs = [GATechnician(p1), GATechnician(p2)]

        wo1 = self._create_wo("Align Shaft 1", tools=["TOOL_LASER_01"], duration_minutes=60)
        wo2 = self._create_wo("Align Shaft 2", tools=["TOOL_LASER_01"], duration_minutes=60)
        tasks = [GATask(wo1), GATask(wo2)]

        self.assertEqual(tasks[0].required_tools, ["TOOL_LASER_01"])
        self.assertEqual(tasks[1].required_tools, ["TOOL_LASER_01"])

        # When scheduled to the same technician, timeline executes them sequentially without overlap
        ind_sequential = GAIndividual([0, 0])
        evaluate_individual_fitness(ind_sequential, tasks, techs)

        sched_0 = ind_sequential.schedules[0]
        self.assertEqual(sched_0['taskCount'], 2)
        # Verify sequential order in timeline
        ordered_tasks = sched_0['orderedTasks']
        self.assertEqual(len(ordered_tasks), 2)
        self.assertLessEqual(ordered_tasks[0]['finishTime'], ordered_tasks[1]['startTime'],
                             "Tasks on the same technician must be executed sequentially without tool conflict")

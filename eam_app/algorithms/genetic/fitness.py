"""
Multi-Objective Fitness Evaluation Function with Enterprise Guardrail Penalties.
Implements Rule 2 (Overload Penalty), Rule 3 (Virtual Tech / Backlog Penalty),
Rule 4 (Late SLA Penalty), Rule 8 (Heterogeneous Shifts), Rule 10 (Clustering / Frag Penalty),
and Multi-Floorplan Isolation.
"""
import math
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from .constants import (
    WEIGHTS_BALANCED, PENALTY_OVERLOAD_BETA, PENALTY_LATE_GAMMA,
    PENALTY_BACKLOG_BASE, PENALTY_ZONE_FRAG, PENALTY_FLOORPLAN_MISMATCH,
    MAX_TASKS_PER_TECH_QUOTA
)
from .sub_decoding import sub_decode_route_nearest_neighbor, simulate_technician_timeline
from algorithms.hungarian.cost_matrix import is_skill_satisfied, is_certification_satisfied


def calculate_task_skill_score(task, tech, catalog=None) -> float:
    """Evaluates skill compatibility on a scale of 0 to 100."""
    if not task.required_skill:
        return 100.0

    # Safety Certification Hard Check: Missing required cert incurs 0 score
    if task.required_certification and not is_certification_satisfied(
        task.required_certification, tech.certifications, catalog=catalog
    ):
        return 0.0

    # Skill match check
    if not is_skill_satisfied(task.required_skill, tech.skills, catalog=catalog):
        return 20.0  # Basic effort score for unskilled work

    # Skill level delta: Level_tech - Level_req
    delta = tech.skill_level - task.min_skill_level
    if delta >= 0:
        # Perfectly qualified or overqualified
        return max(80.0, 100.0 - (delta * 5.0))
    else:
        # Underqualified
        gap = abs(delta)
        return max(30.0, 100.0 - (gap * 25.0))


def evaluate_individual_fitness(individual,
                                tasks: List[Any],
                                technicians: List[Any],
                                weights: Dict[str, float] = None,
                                catalog: Dict[str, Any] = None,
                                warehouse_coords: Optional[Tuple[float, float, int, str]] = None,
                                current_time=None) -> float:
    """
    Evaluates multi-objective fitness score F(X) in range [0, 100] for a GA individual.
    Computes Skill, Workload balance, Travel minimization, and applies 5 operational penalties.
    """
    w = weights or WEIGHTS_BALANCED
    w_skill = w.get('skill', 0.35)
    w_workload = w.get('workload', 0.35)
    w_travel = w.get('travel', 0.30)

    n_techs = len(technicians)
    m_tasks = len(tasks)
    genes = individual.genes

    # Group tasks by technician assignment
    tech_assignments = {t_idx: [] for t_idx in range(n_techs)}
    backlog_indices = []

    for task_idx, gene_val in enumerate(genes):
        if gene_val < n_techs:
            tech_assignments[gene_val].append(tasks[task_idx])
        else:
            backlog_indices.append(task_idx)

    # -------------------------------------------------------------
    # 1. Sub-decoding & Timeline Simulation for Real Technicians
    # -------------------------------------------------------------
    tech_schedules = {}
    shift_times = []
    total_travel_meters = 0.0
    total_skill_points = 0.0
    assigned_tasks_count = 0

    pen_overload = 0.0
    pen_late = 0.0
    pen_frag = 0.0
    pen_floorplan = 0.0

    for t_idx, tech in enumerate(technicians):
        assigned_wos = tech_assignments[t_idx]
        if not assigned_wos:
            tech_schedules[t_idx] = {
                "technicianId": tech.user_id,
                "technicianName": tech.name,
                "taskCount": 0,
                "totalMinutes": 0,
                "repairMinutes": 0,
                "travelMinutes": 0.0,
                "warehouseMinutes": 0,
                "totalDistanceMeters": 0.0,
                "overloadMinutes": 0,
                "zoneHops": 0,
                "orderedTasks": []
            }
            shift_times.append(0)
            continue

        # Rule 1: Sub-decoding Nearest Neighbor + Due Date
        ordered = sub_decode_route_nearest_neighbor(tech, assigned_wos, current_time=current_time)

        # Rule 2 & 7: Timeline simulation with transit and warehouse stops
        sim_res = simulate_technician_timeline(tech, ordered, warehouse_coords=warehouse_coords,
                                               shift_start_time=current_time)
        tech_schedules[t_idx] = sim_res
        shift_times.append(sim_res["totalMinutes"])
        total_travel_meters += sim_res["totalDistanceMeters"]

        # Skill Score Evaluation
        for tsk in ordered:
            score = calculate_task_skill_score(tsk, tech, catalog=catalog)
            total_skill_points += score
            assigned_tasks_count += 1

            # Multi-Floorplan Isolation Check (ISA-95)
            if not tech.is_roving and tech.floorplan_id and tsk.floorplan_id:
                if tech.floorplan_id != tsk.floorplan_id:
                    pen_floorplan += PENALTY_FLOORPLAN_MISMATCH

        # Rule 2: Overload Penalty (Nonlinear quadratic)
        ov_mins = sim_res["overloadMinutes"]
        if ov_mins > 0:
            pen_overload += PENALTY_OVERLOAD_BETA * (ov_mins ** 2)

        # Task Quota soft penalty (excessive distinct tickets)
        if len(ordered) > MAX_TASKS_PER_TECH_QUOTA:
            pen_overload += (len(ordered) - MAX_TASKS_PER_TECH_QUOTA) * 10.0

        # Rule 4: Late SLA Penalty
        for ot in sim_res["orderedTasks"]:
            if ot.get("isLate"):
                p_mins = ot.get("latenessPenaltyMinutes", min(60, ot.get("latenessMinutes", 0)))
                pen_late += min(4.0, PENALTY_LATE_GAMMA * ot.get("priorityWeight", 1.0) * (p_mins / 30.0))

        # Rule 10: Anti-fragmentation penalty
        if sim_res["zoneHops"] > 2:
            pen_frag += min(10.0, PENALTY_ZONE_FRAG * (sim_res["zoneHops"] - 2))

    # -------------------------------------------------------------
    # 2. Rule 3: Virtual Technician (Backlog) Penalty
    # -------------------------------------------------------------
    pen_backlog = 0.0
    backlog_tasks_data = []
    for b_idx in backlog_indices:
        b_tsk = tasks[b_idx]
        pen_backlog += min(15.0, b_tsk.priority_weight * 5.0)
        backlog_tasks_data.append({
            "workOrderId": b_tsk.id,
            "code": b_tsk.code,
            "title": b_tsk.title,
            "priority": b_tsk.priority,
            "requiredSkill": b_tsk.required_skill,
            "estimatedMinutes": b_tsk.estimated_duration_minutes,
            "reason": "Vượt tổng năng lực ca làm việc (Chuyển tiếp ca sau)"
        })

    # -------------------------------------------------------------
    # 3. Objective Normalized Scores [0, 100]
    # -------------------------------------------------------------
    # (a) Skill Match Score: Average score across assigned tasks
    if assigned_tasks_count > 0:
        f_skill = round(total_skill_points / assigned_tasks_count, 2)
    else:
        f_skill = 50.0  # Neutral fallback

    # (b) Workload Balance Score: 100 - Coefficient of Variation
    if shift_times and max(shift_times) > 0:
        mean_time = np.mean(shift_times)
        std_time = np.std(shift_times)
        cv = (std_time / (mean_time + 1e-5)) * 100.0
        f_workload = round(max(0.0, min(100.0, 100.0 - cv)), 2)
    else:
        f_workload = 100.0

    # (c) Travel Optimization Score: Inverse distance
    max_possible_dist = max(1000.0, m_tasks * 250.0)
    travel_ratio = min(1.0, total_travel_meters / max_possible_dist)
    f_travel = round(max(0.0, 100.0 * (1.0 - travel_ratio)), 2)

    # -------------------------------------------------------------
    # 4. Total Composite Fitness Calculation
    # -------------------------------------------------------------
    total_penalties = (
        min(40.0, pen_overload) +
        min(30.0, pen_late) +
        min(40.0, pen_backlog) +
        min(20.0, pen_frag) +
        min(1000.0, pen_floorplan)
    )

    base_objectives = (w_skill * f_skill) + (w_workload * f_workload) + (w_travel * f_travel)
    raw_fitness = base_objectives - total_penalties

    final_fitness = round(max(0.0, min(100.0, raw_fitness)), 2)

    # Cache attributes on individual
    individual.fitness = final_fitness
    individual.skill_score = f_skill
    individual.workload_score = f_workload
    individual.travel_score = f_travel
    individual.penalties = {
        'overload': round(pen_overload, 2),
        'late': round(pen_late, 2),
        'backlog': round(pen_backlog, 2),
        'frag': round(pen_frag, 2),
        'floorplan': round(pen_floorplan, 2)
    }
    individual.schedules = tech_schedules
    individual.backlog_tasks = backlog_tasks_data

    return final_fitness

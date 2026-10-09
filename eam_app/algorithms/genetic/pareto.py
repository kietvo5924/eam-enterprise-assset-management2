"""
Pareto Front Extraction & Managerial Strategy Synthesis for Task 11.2 GA.
Implements Rule 9: Extracts Top 3 Multi-Objective Pareto Solutions
(Balanced, Skill-Focused, and Min-Travel).
"""
from typing import List, Dict, Any, Tuple
from .constants import WEIGHTS_BALANCED, WEIGHTS_SKILL_FOCUSED, WEIGHTS_MIN_TRAVEL
from .fitness import evaluate_individual_fitness


def format_solution_response(strategy_code: str, label: str,
                             individual,
                             technicians: List[Any],
                             focus_description: str = "") -> Dict[str, Any]:
    """Formats an individual into the API Pareto solution schema."""
    schedules_list = []
    for t_idx, tech in enumerate(technicians):
        sched_data = individual.schedules.get(t_idx, {
            "technicianId": tech.user_id,
            "technicianName": tech.name,
            "taskCount": 0,
            "repairMinutes": 0,
            "travelMinutes": 0,
            "warehouseMinutes": 0,
            "totalMinutes": 0,
            "orderedTasks": []
        })
        schedules_list.append(sched_data)

    return {
        "strategy": strategy_code,
        "label": label,
        "focusDescription": focus_description,
        "fitnessScore": round(float(individual.fitness), 1),
        "skillScore": round(float(individual.skill_score), 1),
        "workloadScore": round(float(individual.workload_score), 1),
        "travelScore": round(float(individual.travel_score), 1),
        "backlogCount": len(individual.backlog_tasks),
        "backlogTasks": individual.backlog_tasks,
        "schedules": schedules_list
    }


def extract_pareto_front_solutions(population,
                                  tasks: List[Any],
                                  technicians: List[Any],
                                  catalog: Dict[str, Any] = None,
                                  warehouse_coords=None,
                                  current_time=None) -> List[Dict[str, Any]]:
    """
    Extracts Top 3 trade-off solutions representing:
    1. Balanced Strategy (Recommended)
    2. Skill-Focused Strategy
    3. Min-Travel Strategy
    """
    if not population:
        return []

    # 1. Best Balanced Candidate
    best_balanced = max(population, key=lambda ind: ind.fitness)

    # 2. Best Skill-Focused Candidate
    best_skill_ind = None
    best_skill_score = -1.0
    for ind in population:
        test_ind = ind.clone()
        score = evaluate_individual_fitness(
            test_ind, tasks, technicians,
            weights=WEIGHTS_SKILL_FOCUSED,
            catalog=catalog, warehouse_coords=warehouse_coords, current_time=current_time
        )
        if score > best_skill_score:
            best_skill_score = score
            best_skill_ind = test_ind

    # If identical to balanced, pick best distinct individual with highest skill priority
    if best_skill_ind and best_skill_ind.genes == best_balanced.genes:
        for ind in sorted(population, key=lambda x: (x.skill_score, -x.penalties.get('late', 0), x.fitness), reverse=True):
            if ind.genes != best_balanced.genes:
                test_ind = ind.clone()
                evaluate_individual_fitness(
                    test_ind, tasks, technicians,
                    weights=WEIGHTS_SKILL_FOCUSED,
                    catalog=catalog, warehouse_coords=warehouse_coords, current_time=current_time
                )
                best_skill_ind = test_ind
                break

    # 3. Best Min-Travel Candidate
    best_travel_ind = None
    best_travel_score = -1.0
    for ind in population:
        test_ind = ind.clone()
        score = evaluate_individual_fitness(
            test_ind, tasks, technicians,
            weights=WEIGHTS_MIN_TRAVEL,
            catalog=catalog, warehouse_coords=warehouse_coords, current_time=current_time
        )
        if score > best_travel_score:
            best_travel_score = score
            best_travel_ind = test_ind

    # If identical to balanced or skill candidate, pick best distinct individual with highest travel score
    taken_genes = [best_balanced.genes]
    if best_skill_ind and best_skill_ind.genes != best_balanced.genes:
        taken_genes.append(best_skill_ind.genes)

    if best_travel_ind and any(best_travel_ind.genes == tg for tg in taken_genes):
        for ind in sorted(population, key=lambda x: (x.travel_score, x.fitness), reverse=True):
            if not any(ind.genes == tg for tg in taken_genes):
                test_ind = ind.clone()
                evaluate_individual_fitness(
                    test_ind, tasks, technicians,
                    weights=WEIGHTS_MIN_TRAVEL,
                    catalog=catalog, warehouse_coords=warehouse_coords, current_time=current_time
                )
                best_travel_ind = test_ind
                break

    pareto_solutions = [
        format_solution_response(
            "BALANCED",
            "Phương án Cân Bằng (Khuyến nghị)",
            best_balanced,
            technicians,
            focus_description="Hài hòa tối ưu giữa trình độ tay nghề, cân bằng tải ca và lộ trình đi lại."
        ),
        format_solution_response(
            "SKILL_FOCUSED",
            "Phương án Tối Đa Tay Nghề",
            best_skill_ind or best_balanced,
            technicians,
            focus_description="Ưu tiên giao các phiếu quan trọng cho kỹ thuật viên bậc cao nhất."
        ),
        format_solution_response(
            "MIN_TRAVEL",
            "Phương án Quãng Đường Ngắn Nhất",
            best_travel_ind or best_balanced,
            technicians,
            focus_description="Gom cụm thiết bị gần nhau để tiết kiệm tối đa thời gian đi bộ trong ca."
        ),
    ]

    return pareto_solutions

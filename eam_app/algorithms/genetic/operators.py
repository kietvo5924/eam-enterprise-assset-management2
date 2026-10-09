"""
Adaptive Genetic Operators: Tournament Selection, Uniform Crossover,
Adaptive Cataclysmic Mutation, Heuristic Seeding, and Multi-Floorplan Repair Operator.
Implements Rule 5 (Adaptive Mutation) and Rule 6 (Heuristic Seeding).
"""
import random
from typing import List, Any, Dict, Optional, Tuple
from .chromosome import GAIndividual
from .constants import (
    DEFAULT_CROSSOVER_RATE, DEFAULT_MUTATION_RATE,
    CATACLYSMIC_MUTATION_RATE, TOURNAMENT_SIZE, HEURISTIC_SEEDING_RATIO
)
from algorithms.hungarian.cost_matrix import is_certification_satisfied


def repair_individual_constraints(individual: GAIndividual,
                                  tasks: List[Any],
                                  technicians: List[Any],
                                  catalog: Dict[str, Any] = None) -> GAIndividual:
    """
    Repair Operator: Enforces safety certifications and floorplan compatibility.
    If a task requiring a safety cert is assigned to an uncertified tech,
    re-assigns to a qualified tech or Virtual Tech N.
    If non-roving tech is assigned to a different floorplan, re-assigns appropriately.
    """
    n_techs = len(technicians)
    for j, task in enumerate(tasks):
        assigned_tech_idx = individual.genes[j]
        if assigned_tech_idx >= n_techs:
            continue  # Virtual Tech is safe

        tech = technicians[assigned_tech_idx]

        # 1. Certification check
        needs_repair = False
        if task.required_certification and not is_certification_satisfied(
            task.required_certification, tech.certifications, catalog=catalog
        ):
            needs_repair = True

        # 2. Floorplan mismatch check
        if not tech.is_roving and tech.floorplan_id and task.floorplan_id:
            if tech.floorplan_id != task.floorplan_id:
                needs_repair = True

        if needs_repair:
            # Find candidate technicians matching both cert and floorplan
            qualified_indices = []
            for t_idx, cand_tech in enumerate(technicians):
                cand_ok = True
                if task.required_certification and not is_certification_satisfied(
                    task.required_certification, cand_tech.certifications, catalog=catalog
                ):
                    cand_ok = False
                if not cand_tech.is_roving and cand_tech.floorplan_id and task.floorplan_id:
                    if cand_tech.floorplan_id != task.floorplan_id:
                        cand_ok = False
                if cand_ok:
                    qualified_indices.append(t_idx)

            if qualified_indices:
                individual.genes[j] = random.choice(qualified_indices)
            else:
                individual.genes[j] = n_techs  # Push to Backlog

    return individual


def generate_greedy_seed(tasks: List[Any], technicians: List[Any], catalog=None) -> GAIndividual:
    """
    Rule 6: Generates a high-quality heuristic seed individual using Greedy Workload balancing.
    Prioritizes urgent tasks, assigns to highest qualified technician with matching zone and shift headroom.
    """
    n_techs = len(technicians)
    m_tasks = len(tasks)
    genes = [n_techs] * m_tasks  # Default to Virtual Tech

    # Track allocated workload in minutes per tech
    tech_minutes = {i: 0 for i in range(n_techs)}

    # Sort tasks: highest priority first, then longest duration
    sorted_task_indices = sorted(
        range(m_tasks),
        key=lambda idx: (-tasks[idx].priority_weight, -tasks[idx].estimated_duration_minutes)
    )

    for j in sorted_task_indices:
        task = tasks[j]
        best_tech_idx = None
        min_load = float('inf')

        # Find best eligible tech
        for t_idx, tech in enumerate(technicians):
            # Check certification
            if task.required_certification and not is_certification_satisfied(
                task.required_certification, tech.certifications, catalog=catalog
            ):
                continue

            # Check floorplan
            if not tech.is_roving and tech.floorplan_id and task.floorplan_id:
                if tech.floorplan_id != task.floorplan_id:
                    continue

            # Check shift capacity limit
            future_load = tech_minutes[t_idx] + task.estimated_duration_minutes
            if future_load <= tech.max_shift_minutes:
                if future_load < min_load:
                    min_load = future_load
                    best_tech_idx = t_idx

        if best_tech_idx is not None:
            genes[j] = best_tech_idx
            tech_minutes[best_tech_idx] += task.estimated_duration_minutes
        else:
            genes[j] = n_techs  # Exceeds shift capacity -> Backlog

    ind = GAIndividual(genes)
    return repair_individual_constraints(ind, tasks, technicians, catalog=catalog)


def initialize_population(pop_size: int,
                          tasks: List[Any],
                          technicians: List[Any],
                          catalog: Dict[str, Any] = None) -> List[GAIndividual]:
    """
    Initializes population: 20% Heuristic Seeds + 80% Random with Constraint Repair.
    """
    n_techs = len(technicians)
    m_tasks = len(tasks)
    population = []

    # Number of heuristic seeds (20%)
    num_seeds = max(1, int(pop_size * HEURISTIC_SEEDING_RATIO))

    # 1. Generate Heuristic Seeds
    base_seed = generate_greedy_seed(tasks, technicians, catalog=catalog)
    population.append(base_seed)

    for _ in range(num_seeds - 1):
        # Slightly perturbed variants of the greedy seed for gene diversity
        seed_copy = base_seed.clone()
        num_mutations = max(1, int(m_tasks * 0.10))
        for _ in range(num_mutations):
            rand_j = random.randint(0, m_tasks - 1)
            seed_copy.genes[rand_j] = random.randint(0, n_techs)
        repaired_seed = repair_individual_constraints(seed_copy, tasks, technicians, catalog=catalog)
        population.append(repaired_seed)

    # 2. Generate Remaining Individuals (80% Random with Repair)
    while len(population) < pop_size:
        genes = [random.randint(0, n_techs) for _ in range(m_tasks)]
        ind = GAIndividual(genes)
        repaired = repair_individual_constraints(ind, tasks, technicians, catalog=catalog)
        population.append(repaired)

    return population


def tournament_select(population: List[GAIndividual], k: int = TOURNAMENT_SIZE) -> GAIndividual:
    """Tournament Selection: Samples k candidates and returns the one with highest fitness."""
    candidates = random.sample(population, min(k, len(population)))
    return max(candidates, key=lambda ind: ind.fitness)


def uniform_crossover(parent1: GAIndividual, parent2: GAIndividual,
                      crossover_rate: float = DEFAULT_CROSSOVER_RATE) -> Tuple[GAIndividual, GAIndividual]:
    """Uniform Crossover with probability Pc."""
    if random.random() > crossover_rate:
        return parent1.clone(), parent2.clone()

    child1_genes = []
    child2_genes = []
    for g1, g2 in zip(parent1.genes, parent2.genes):
        if random.random() < 0.5:
            child1_genes.append(g1)
            child2_genes.append(g2)
        else:
            child1_genes.append(g2)
            child2_genes.append(g1)

    return GAIndividual(child1_genes), GAIndividual(child2_genes)


def mutate(individual: GAIndividual,
           mutation_rate: float,
           num_techs: int,
           tasks: List[Any],
           technicians: List[Any],
           catalog: Dict[str, Any] = None) -> GAIndividual:
    """
    Mutates individual genes with rate Pm.
    Includes Repair Operator afterwards to guarantee certification and floorplan safety.
    """
    for j in range(len(individual.genes)):
        if random.random() < mutation_rate:
            individual.genes[j] = random.randint(0, num_techs)

    return repair_individual_constraints(individual, tasks, technicians, catalog=catalog)

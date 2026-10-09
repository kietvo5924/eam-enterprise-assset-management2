"""
Core Evolution Loop & Solver for Task 11.2 GA Workload Scheduling.
Implements Rule 5 (Adaptive Stagnation Mutation), Elitism (TC-GA-01),
and Real-time Generation Progress Callbacks.
"""
import numpy as np
from typing import List, Dict, Any, Callable, Optional
from django.utils import timezone
from .constants import (
    DEFAULT_POPULATION_SIZE, DEFAULT_MAX_GENERATIONS,
    DEFAULT_MUTATION_RATE, CATACLYSMIC_MUTATION_RATE,
    DEFAULT_CROSSOVER_RATE, STAGNATION_THRESHOLD,
    CATACLYSMIC_BURST_GENERATIONS, ELITISM_RATIO, WEIGHTS_BALANCED
)
from .chromosome import GATask, GATechnician, GAIndividual
from .operators import initialize_population, tournament_select, uniform_crossover, mutate
from .fitness import evaluate_individual_fitness
from .pareto import extract_pareto_front_solutions


class MaintenanceGAScheduler:
    """
    Genetic Algorithm Engine for Multi-Objective Maintenance Workload Scheduling.
    """
    def __init__(self,
                 work_orders: List[Any],
                 technicians: List[Any],
                 config: Dict[str, Any] = None,
                 catalog: Dict[str, Any] = None,
                 warehouse_coords=None,
                 current_time=None,
                 today_schedules: Optional[Dict[Any, Any]] = None,
                 in_progress_wos: Optional[Dict[Any, Any]] = None,
                 progress_callback: Optional[Callable[[int, int, float, List[Dict]], None]] = None):
        cfg = config or {}
        self.pop_size = int(cfg.get('populationSize', DEFAULT_POPULATION_SIZE))
        self.max_gen = int(cfg.get('maxGenerations', DEFAULT_MAX_GENERATIONS))
        self.catalog = catalog
        self.warehouse_coords = warehouse_coords
        self.current_time = current_time or timezone.now()
        self.progress_callback = progress_callback
        self.today_schedules = today_schedules or {}
        self.in_progress_wos = in_progress_wos or {}

        # Convert to lightweight representations
        self.tasks = [GATask(wo, catalog=catalog) for wo in work_orders]
        self.techs = [
            GATechnician(
                t,
                current_time=self.current_time,
                catalog=catalog,
                today_schedule=self.today_schedules.get(getattr(t, 'user_id', None)),
                active_wo=self.in_progress_wos.get(str(getattr(t, 'user_id', '')))
            )
            if hasattr(t, 'skills') else t
            for t in technicians
        ]

        self.mutation_rate = DEFAULT_MUTATION_RATE
        self.stagnation_count = 0
        self.cataclysmic_burst_remaining = 0
        self.best_fitness = 0.0
        self.convergence_history = []
        self.population: List[GAIndividual] = []

    def run(self) -> Dict[str, Any]:
        """Executes full genetic evolution across generations."""
        if not self.tasks or not self.techs:
            return {
                "bestFitness": 0.0,
                "currentGeneration": 0,
                "maxGenerations": self.max_gen,
                "convergenceHistory": [],
                "paretoSolutions": []
            }

        # 1. Initialize Population (20% Heuristic Seeds + 80% Random Safe)
        self.population = initialize_population(
            pop_size=self.pop_size,
            tasks=self.tasks,
            technicians=self.techs,
            catalog=self.catalog
        )

        n_techs = len(self.techs)
        elitism_k = max(1, int(self.pop_size * ELITISM_RATIO))

        # 2. Evolution Loop
        for gen in range(1, self.max_gen + 1):
            # Evaluate fitness of all individuals
            fitness_values = []
            for ind in self.population:
                f_val = evaluate_individual_fitness(
                    ind,
                    tasks=self.tasks,
                    technicians=self.techs,
                    weights=WEIGHTS_BALANCED,
                    catalog=self.catalog,
                    warehouse_coords=self.warehouse_coords,
                    current_time=self.current_time
                )
                fitness_values.append(f_val)

            current_gen_best = max(fitness_values)
            current_gen_avg = round(float(np.mean(fitness_values)), 1)

            # Rule 5: Stagnation Detection & Adaptive Cataclysmic Mutation
            if current_gen_best <= (self.best_fitness * 1.001):
                self.stagnation_count += 1
            else:
                self.stagnation_count = 0
                self.best_fitness = current_gen_best

            if self.stagnation_count >= STAGNATION_THRESHOLD:
                # Trigger Cataclysmic Mutation Burst
                self.cataclysmic_burst_remaining = CATACLYSMIC_BURST_GENERATIONS
                self.stagnation_count = 0  # Reset counter

            if self.cataclysmic_burst_remaining > 0:
                self.mutation_rate = CATACLYSMIC_MUTATION_RATE
                self.cataclysmic_burst_remaining -= 1
            else:
                self.mutation_rate = DEFAULT_MUTATION_RATE

            # Sort population descending by fitness
            self.population.sort(key=lambda ind: ind.fitness, reverse=True)

            # Record convergence milestone (every 10 generations or first/last)
            if gen == 1 or gen % 10 == 0 or gen == self.max_gen:
                self.convergence_history.append({
                    "generation": gen,
                    "bestFitness": round(current_gen_best, 1),
                    "avgFitness": current_gen_avg
                })
                if self.progress_callback:
                    try:
                        self.progress_callback(gen, self.max_gen, current_gen_best, self.convergence_history)
                    except Exception:
                        pass

            if gen == self.max_gen:
                break

            # -------------------------------------------------------------
            # 3. Next Generation Assembly: Elitism + Crossover + Mutation
            # -------------------------------------------------------------
            new_generation = []

            # TC-GA-01: Elitism Preservation (Top 5% copied verbatim)
            for top_i in range(elitism_k):
                new_generation.append(self.population[top_i].clone())

            # Fill remaining population
            while len(new_generation) < self.pop_size:
                p1 = tournament_select(self.population)
                p2 = tournament_select(self.population)

                c1, c2 = uniform_crossover(p1, p2, crossover_rate=DEFAULT_CROSSOVER_RATE)

                c1_mutated = mutate(
                    c1,
                    mutation_rate=self.mutation_rate,
                    num_techs=n_techs,
                    tasks=self.tasks,
                    technicians=self.techs,
                    catalog=self.catalog
                )
                new_generation.append(c1_mutated)

                if len(new_generation) < self.pop_size:
                    c2_mutated = mutate(
                        c2,
                        mutation_rate=self.mutation_rate,
                        num_techs=n_techs,
                        tasks=self.tasks,
                        technicians=self.techs,
                        catalog=self.catalog
                    )
                    new_generation.append(c2_mutated)

            self.population = new_generation

        # -------------------------------------------------------------
        # 4. Extract Top 3 Pareto Front Solutions (Rule 9)
        # -------------------------------------------------------------
        pareto_solutions = extract_pareto_front_solutions(
            self.population,
            tasks=self.tasks,
            technicians=self.techs,
            catalog=self.catalog,
            warehouse_coords=self.warehouse_coords,
            current_time=self.current_time
        )

        return {
            "bestFitness": round(self.best_fitness, 1),
            "currentGeneration": self.max_gen,
            "maxGenerations": self.max_gen,
            "convergenceHistory": self.convergence_history,
            "paretoSolutions": pareto_solutions
        }

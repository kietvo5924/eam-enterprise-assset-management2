"""
Tiered ATSP & TSPTW Solver for Task 11.3 Technician Routing Optimization.
Implements:
1. Tiered TSP (Rule 3): Solves Urgent cluster first from v0, then normal cluster from last urgent stop.
2. TSP with Time Windows (Rule 4): Evaluates machine downtime windows [e_j, l_j] and penalizes late arrival.
3. Asymmetric TSP with Or-opt Relocate (Rule 5): 1-node and 2-node relocation without sub-path reversal.
4. Pure Business Ordering (Rule 11): Priority + Due Date fallback.
"""

from typing import List, Dict, Tuple, Optional, Any
from datetime import time, datetime

from .constants import (
    WALKING_SPEED_METERS_PER_MIN,
    TIME_WINDOW_LATE_PENALTY_RATE,
    TIME_WINDOW_EARLY_WAIT_RATE,
    DEFAULT_TASK_DURATION_MINUTES,
    BIG_M,
)
from .distance_matrix import RoutingNode


def time_to_minutes(t: Optional[time]) -> Optional[float]:
    """Converts a datetime.time object to minutes from midnight."""
    if t is None:
        return None
    return float(t.hour * 60 + t.minute + (t.second / 60.0))


def minutes_to_time_str(mins: float) -> str:
    """Converts minutes from midnight to HH:MM string."""
    normalized_mins = int(mins) % 1440
    hours = normalized_mins // 60
    minutes = normalized_mins % 60
    return f"{hours:02d}:{minutes:02d}"


class TourEvaluation:
    def __init__(
        self,
        total_distance: float = 0.0,
        total_time_minutes: float = 0.0,
        total_waiting_minutes: float = 0.0,
        total_penalty: float = 0.0,
        schedule: Optional[List[Dict[str, Any]]] = None,
    ):
        self.total_distance = total_distance
        self.total_time_minutes = total_time_minutes
        self.total_waiting_minutes = total_waiting_minutes
        self.total_penalty = total_penalty
        self.schedule = schedule or []

    @property
    def total_cost(self) -> float:
        """Combined objective cost: distance + waiting cost + late penalties."""
        return (
            self.total_distance +
            (self.total_waiting_minutes * TIME_WINDOW_EARLY_WAIT_RATE) +
            self.total_penalty
        )


class TieredATSPSolver:
    """
    Solves multi-tier asymmetric routing with time windows and Or-opt local search.
    """

    def __init__(self, walking_speed: float = WALKING_SPEED_METERS_PER_MIN, default_start_time: float = 480.0):
        # Default start time: 08:00 AM (480 minutes from midnight)
        self.walking_speed = walking_speed or WALKING_SPEED_METERS_PER_MIN
        self.default_start_time = default_start_time

    def evaluate_tour(
        self,
        tour: List[int],
        nodes: List[RoutingNode],
        dist_matrix: List[List[float]],
        start_time_minutes: float,
        return_to_depot: bool = False,
    ) -> TourEvaluation:
        """
        Evaluates a sequence of node indices: computes travel distances, arrival times,
        time-window waiting or violation penalties, and departure times.
        """
        if not tour:
            return TourEvaluation()

        total_dist = 0.0
        current_time = start_time_minutes
        total_waiting = 0.0
        total_penalty = 0.0
        schedule = []

        for idx, node_idx in enumerate(tour):
            node = nodes[node_idx]
            travel_dist = 0.0
            travel_time = 0.0

            if idx > 0:
                prev_idx = tour[idx - 1]
                travel_dist = dist_matrix[prev_idx][node_idx]
                travel_time = travel_dist / self.walking_speed
                total_dist += travel_dist
                current_time += travel_time

            arrival_time = current_time
            wait_time = 0.0
            penalty = 0.0

            # Rule 4: TSPTW Time Windows
            w_start = time_to_minutes(node.time_window_start)
            w_end = time_to_minutes(node.time_window_end)

            if w_start is not None and arrival_time < w_start:
                wait_time = w_start - arrival_time
                total_waiting += wait_time
                current_time = w_start

            if w_end is not None and arrival_time > w_end:
                mins_late = arrival_time - w_end
                penalty = mins_late * TIME_WINDOW_LATE_PENALTY_RATE
                total_penalty += penalty

            service_start = current_time
            duration = node.estimated_duration_minutes if node.work_order else 0.0
            departure_time = service_start + duration
            current_time = departure_time

            schedule.append({
                'nodeIndex': node_idx,
                'node': node,
                'travelDistance': travel_dist,
                'travelTimeMinutes': travel_time,
                'arrivalTimeMinutes': arrival_time,
                'arrivalTimeStr': minutes_to_time_str(arrival_time),
                'waitingMinutes': wait_time,
                'serviceStartMinutes': service_start,
                'departureTimeMinutes': departure_time,
                'departureTimeStr': minutes_to_time_str(departure_time),
                'penalty': penalty,
            })

        # Return to depot if requested
        if return_to_depot and len(tour) > 1 and tour[-1] != tour[0]:
            last_idx = tour[-1]
            first_idx = tour[0]
            return_dist = dist_matrix[last_idx][first_idx]
            return_time = return_dist / self.walking_speed
            total_dist += return_dist
            current_time += return_time

            schedule.append({
                'nodeIndex': first_idx,
                'node': nodes[first_idx],
                'travelDistance': return_dist,
                'travelTimeMinutes': return_time,
                'arrivalTimeMinutes': current_time,
                'arrivalTimeStr': minutes_to_time_str(current_time),
                'waitingMinutes': 0.0,
                'serviceStartMinutes': current_time,
                'departureTimeMinutes': current_time,
                'departureTimeStr': minutes_to_time_str(current_time),
                'penalty': 0.0,
            })

        total_time = current_time - start_time_minutes
        return TourEvaluation(
            total_distance=total_dist,
            total_time_minutes=total_time,
            total_waiting_minutes=total_waiting,
            total_penalty=total_penalty,
            schedule=schedule,
        )

    def _nearest_neighbor_construct(
        self,
        start_idx: int,
        candidates: List[int],
        nodes: List[RoutingNode],
        dist_matrix: List[List[float]],
        start_time_minutes: float,
    ) -> List[int]:
        """
        Greedy Nearest Neighbor with Time-Window awareness to construct an initial tour.
        """
        unvisited = list(candidates)
        tour = [start_idx]
        current_node = start_idx
        current_time = start_time_minutes

        while unvisited:
            best_cand = None
            best_cost = float('inf')

            for cand in unvisited:
                d = dist_matrix[current_node][cand]
                travel_time = d / self.walking_speed
                cand_arr = current_time + travel_time
                cand_node = nodes[cand]

                w_start = time_to_minutes(cand_node.time_window_start)
                w_end = time_to_minutes(cand_node.time_window_end)

                penalty = 0.0
                if w_end is not None and cand_arr > w_end:
                    penalty = (cand_arr - w_end) * TIME_WINDOW_LATE_PENALTY_RATE
                wait = 0.0
                if w_start is not None and cand_arr < w_start:
                    wait = (w_start - cand_arr) * TIME_WINDOW_EARLY_WAIT_RATE

                cost = d + wait + penalty
                if cost < best_cost:
                    best_cost = cost
                    best_cand = cand

            if best_cand is not None:
                unvisited.remove(best_cand)
                tour.append(best_cand)
                # Advance time
                travel_d = dist_matrix[current_node][best_cand]
                current_time += travel_d / self.walking_speed
                node_cand = nodes[best_cand]
                w_start = time_to_minutes(node_cand.time_window_start)
                if w_start and current_time < w_start:
                    current_time = w_start
                current_time += node_cand.estimated_duration_minutes
                current_node = best_cand
            else:
                break

        return tour

    def _or_opt_improve(
        self,
        tour: List[int],
        nodes: List[RoutingNode],
        dist_matrix: List[List[float]],
        start_time_minutes: float,
        max_iterations: int = 100,
    ) -> List[int]:
        """
        Rule 5: Or-opt Relocate Move.
        Moves segments of length 1 or 2 without reversing them.
        Preserves ATSP one-way corridor asymmetry and directional flows.
        """
        if len(tour) <= 3:
            return tour

        best_tour = list(tour)
        best_eval = self.evaluate_tour(best_tour, nodes, dist_matrix, start_time_minutes, return_to_depot=False)
        best_cost = best_eval.total_cost

        improved = True
        iteration = 0

        while improved and iteration < max_iterations:
            improved = False
            iteration += 1

            # Only relocate stops beyond index 0 (keep start position fixed)
            n = len(best_tour)

            # Segment lengths: 1 (single node) and 2 (block of 2 nodes)
            for seg_len in (1, 2):
                for i in range(1, n - seg_len + 1):
                    segment = best_tour[i:i + seg_len]
                    remaining = best_tour[:i] + best_tour[i + seg_len:]

                    # Try inserting segment into every position j >= 1
                    for j in range(1, len(remaining) + 1):
                        new_tour = remaining[:j] + segment + remaining[j:]
                        new_eval = self.evaluate_tour(new_tour, nodes, dist_matrix, start_time_minutes, return_to_depot=False)
                        new_cost = new_eval.total_cost

                        # Epsilon threshold for improvement
                        if new_cost < best_cost - 1e-4:
                            best_tour = new_tour
                            best_cost = new_cost
                            improved = True
                            break
                    if improved:
                        break
                if improved:
                    break

        return best_tour

    def solve_atsp_cluster(
        self,
        start_idx: int,
        candidates: List[int],
        nodes: List[RoutingNode],
        dist_matrix: List[List[float]],
        start_time_minutes: float,
    ) -> List[int]:
        """
        Solves ATSP for a single cluster of stops from start_idx.
        Returns the ordered list of node indices starting with start_idx.
        """
        if not candidates:
            return [start_idx]

        init_tour = self._nearest_neighbor_construct(
            start_idx, candidates, nodes, dist_matrix, start_time_minutes
        )
        optimized_tour = self._or_opt_improve(
            init_tour, nodes, dist_matrix, start_time_minutes
        )
        return optimized_tour

    def solve_tiered_tsp(
        self,
        start_node_idx: int,
        work_order_indices: List[int],
        nodes: List[RoutingNode],
        dist_matrix: List[List[float]],
        start_time_minutes: float = 480.0,
        return_to_depot: bool = False,
    ) -> TourEvaluation:
        """
        Rule 3: Tiered ATSP Solver.
        Tier 1: URGENT & EMERGENCY work orders.
        Tier 2: NORMAL work orders (HIGH, MEDIUM, LOW).
        """
        if not work_order_indices:
            return self.evaluate_tour([start_node_idx], nodes, dist_matrix, start_time_minutes, return_to_depot)

        urgent_indices = []
        normal_indices = []

        for idx in work_order_indices:
            node = nodes[idx]
            if node.priority in ('URGENT', 'EMERGENCY'):
                urgent_indices.append(idx)
            else:
                normal_indices.append(idx)

        current_start_idx = start_node_idx
        current_time = start_time_minutes
        overall_tour = [start_node_idx]

        # 1. Solve Tier 1 (Urgent Cluster)
        if urgent_indices:
            urgent_tour = self.solve_atsp_cluster(
                current_start_idx, urgent_indices, nodes, dist_matrix, current_time
            )
            # urgent_tour starts with current_start_idx, slice [1:]
            overall_tour.extend(urgent_tour[1:])
            current_start_idx = overall_tour[-1]

            # Re-evaluate to get accurate start time for Tier 2
            interim_eval = self.evaluate_tour(overall_tour, nodes, dist_matrix, start_time_minutes, return_to_depot=False)
            if interim_eval.schedule:
                current_time = interim_eval.schedule[-1]['departureTimeMinutes']

        # 2. Solve Tier 2 (Normal Cluster)
        if normal_indices:
            normal_tour = self.solve_atsp_cluster(
                current_start_idx, normal_indices, nodes, dist_matrix, current_time
            )
            overall_tour.extend(normal_tour[1:])

        # Final Evaluation
        final_evaluation = self.evaluate_tour(
            overall_tour, nodes, dist_matrix, start_time_minutes, return_to_depot=return_to_depot
        )
        return final_evaluation

    def solve_pure_business_ordering(
        self,
        start_node_idx: int,
        work_order_indices: List[int],
        nodes: List[RoutingNode],
        dist_matrix: List[List[float]],
        start_time_minutes: float = 480.0,
        return_to_depot: bool = False,
    ) -> TourEvaluation:
        """
        Rule 11: Pure Business Fallback.
        Orders strictly by Priority (URGENT -> HIGH -> MEDIUM -> LOW), then due_date.
        No spatial distance optimization.
        """
        priority_ranks = {
            'EMERGENCY': 0,
            'URGENT': 1,
            'HIGH': 2,
            'MEDIUM': 3,
            'LOW': 4,
        }

        def sort_key(idx: int):
            node = nodes[idx]
            rank = priority_ranks.get(node.priority, 5)
            due_date = getattr(node.work_order, 'due_date', None)
            due_str = due_date.isoformat() if due_date else "9999-12-31"
            return (rank, due_str)

        sorted_wos = sorted(work_order_indices, key=sort_key)
        tour = [start_node_idx] + sorted_wos

        return self.evaluate_tour(tour, nodes, dist_matrix, start_time_minutes, return_to_depot=return_to_depot)

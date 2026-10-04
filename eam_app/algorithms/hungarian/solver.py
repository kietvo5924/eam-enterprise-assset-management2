"""
Kuhn-Munkres (Hungarian) Solver Integration with SciPy
"""
import numpy as np
from scipy.optimize import linear_sum_assignment
from typing import List, Tuple, Dict, Any
from .constants import BIG_M


def solve_kuhn_munkres(raw_cost_matrix: List[List[float]],
                       num_real_techs: int,
                       num_real_slots: int) -> Tuple[List[Tuple[int, int]], float, List[List[float]]]:
    """
    Solves Linear Sum Assignment Problem using scipy.optimize.linear_sum_assignment.
    Pads with Zero-Cost Dummy nodes if matrix is non-square (Rule 7).

    Returns:
      - valid_assignments: List of (row_idx, col_idx) strictly for real technicians and real tasks
      - total_optimal_cost: Sum of costs for valid real pairings
      - padded_matrix: The square K x K matrix used in solver
    """
    n = num_real_techs
    m = num_real_slots

    if n == 0 or m == 0:
        return [], 0.0, []

    k = max(n, m)
    cost_matrix = np.zeros((k, k), dtype=np.float64)

    # Populate real costs
    for i in range(n):
        for j in range(m):
            cost_matrix[i, j] = raw_cost_matrix[i][j]

    # Rule 7: Zero-Cost Dummy Padding
    # Any padded technician row (i >= n) or padded slot column (j >= m) has cost = 0.0 (already initialized to 0)

    # Solve via Kuhn-Munkres
    row_ind, col_ind = linear_sum_assignment(cost_matrix)

    valid_pairs = []
    total_cost = 0.0

    for r, c in zip(row_ind, col_ind):
        # Only keep assignments between real technicians and real task slots
        if r < n and c < m:
            cost_val = float(raw_cost_matrix[r][c])
            valid_pairs.append((int(r), int(c)))
            # If cost is not Big-M penalty, add to total optimal cost
            if cost_val < (BIG_M / 2.0):
                total_cost += cost_val

    total_cost = round(total_cost, 2)
    return valid_pairs, total_cost, cost_matrix.tolist()

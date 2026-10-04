"""
Constants and Mathematical Coefficients for Task 11.1 Hungarian Assignment
"""

# Big-M: Extreme penalty for hard constraint violations (safety certs, missing skill, excessive shift overflow)
BIG_M = 10000000.0  # 10^7

# Rule 1: Priority Multiplier Guardrail
# Multiplying ensures priority amplifies distance & skill gaps, fixing the column-constant flaw.
PRIORITY_MULTIPLIERS = {
    'URGENT': 2.5,
    'HIGH': 1.8,
    'MEDIUM': 1.2,
    'LOW': 1.0,
}

# Cost Normalization Weights (Section 4.1, Item 8)
NORM_WEIGHT_DISTANCE = 0.50   # w_d
NORM_WEIGHT_SKILL = 0.50      # w_s
NORM_WEIGHT_WORKLOAD = 0.20   # w_w

# Rule 2: Zone Transition Penalties
PENALTY_ZONE_SAME = 0.0
PENALTY_ZONE_DIFF = 15.0
PENALTY_ZONE_CONTROLLED = 40.0

# Pre-defined Controlled & Cleanroom Zones requiring decontamination
CONTROLLED_ZONES = {
    'ZONE_CLEANROOM_01',
    'CLEANROOM',
    'ZONE_CLEANROOM',
    'ISOLATION_ZONE',
    'PAINT_SHOP_STERILE',
    'ZONE_CONTROLLED',
    'BIO_SAFETY_LAB',
}

# Rule 3: Shift Handover Penalties
PENALTY_SHIFT_HANDOVER = 40.0       # Soft penalty when duration > remaining_shift
SHIFT_OVERTIME_LIMIT_HOURS = 2.0    # Hard penalty Big-M when duration > remaining_shift + 2.0h

# Disruption Penalty for in-progress tasks
PENALTY_DISRUPTION = 15.0

# Max Normalized Manhattan Distance Score Cap
MAX_DISTANCE_SCORE = 100.0
FLOOR_PENALTY_METERS = 50.0
METERS_TO_SCORE_FACTOR = 0.1

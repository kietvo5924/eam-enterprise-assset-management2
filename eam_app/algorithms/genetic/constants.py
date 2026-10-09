"""
Constants and Configuration Parameters for Task 11.2 Genetic Algorithm (GA)
Multi-Objective Workload Scheduling & Task Assignment Optimization.
"""

# Genetic Algorithm Evolution Parameters
DEFAULT_POPULATION_SIZE = 100
DEFAULT_MAX_GENERATIONS = 150
DEFAULT_CROSSOVER_RATE = 0.85
DEFAULT_MUTATION_RATE = 0.08
CATACLYSMIC_MUTATION_RATE = 0.30
STAGNATION_THRESHOLD = 15
CATACLYSMIC_BURST_GENERATIONS = 3
ELITISM_RATIO = 0.05
HEURISTIC_SEEDING_RATIO = 0.20
TOURNAMENT_SIZE = 3

# Multi-Objective Strategy Weightings [Skill, Workload, Travel]
WEIGHTS_BALANCED = {
    'skill': 0.35,
    'workload': 0.35,
    'travel': 0.30
}

WEIGHTS_SKILL_FOCUSED = {
    'skill': 0.60,
    'workload': 0.20,
    'travel': 0.20
}

WEIGHTS_MIN_TRAVEL = {
    'skill': 0.20,
    'workload': 0.20,
    'travel': 0.60
}

# Penalty Coefficients
PENALTY_OVERLOAD_BETA = 0.05        # Quadratic coefficient: Beta * (overload_minutes)^2
PENALTY_LATE_GAMMA = 0.5           # Linear late penalty per minute * Priority Weight
PENALTY_BACKLOG_BASE = 50.0        # Base backlog multiplier: Priority_Weight * 50
PENALTY_ZONE_FRAG = 15.0           # Penalty per zone hop over 2 transitions
PENALTY_FLOORPLAN_MISMATCH = 1000.0# Massive penalty for non-roving cross-floorplan dispatch
BIG_M = 1000000.0

# Logistics & Spatial Parameters
WALKING_SPEED_METERS_PER_MIN = 60.0  # 1 m/s = 60 m/minute
FLOOR_PENALTY_METERS = 50.0          # 50m walk equivalent per vertical floor
WAREHOUSE_PICKUP_BUFFER_MINUTES = 15 # Detour/checkout time at warehouse
DEFAULT_SHIFT_MINUTES = 480          # 8 hours default shift
SHIFT_LUNCH_BREAK_MINUTES = 60       # 1 hour lunch break (12:00 - 13:00)
MAX_TASKS_PER_TECH_QUOTA = 8         # Soft max tasks per technician per shift

# Priority Multipliers matching Hungarian standards
PRIORITY_WEIGHTS = {
    'URGENT': 2.0,
    'HIGH': 1.5,
    'MEDIUM': 1.0,
    'LOW': 0.7
}

# Roving / General Zone Tokens exempt from Floorplan Hard Isolation
GENERAL_ZONE_TOKENS = {
    'CHUNG', 'ALL', 'ANY', 'DEFAULT', 'TOAN_NHA_MAY', 'TOAN_CONG_TY',
    'CO_DONG', 'COMMON', 'PLANT_WIDE', 'GENERAL', 'NONE', 'ROVING', ''
}

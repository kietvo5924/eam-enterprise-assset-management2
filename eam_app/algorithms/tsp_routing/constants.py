"""
Constants and Mathematical Coefficients for Task 11.3 Technician Routing Optimization (TSP)
"""

# Big-M: Extreme penalty for hard constraints (infeasible routes, broken windows)
BIG_M = 10000000.0

# Walking Speed & Multi-Floor Timing
WALKING_SPEED_METERS_PER_MIN = 60.0    # 1.0 m/s = 60 m/min
FLOOR_PENALTY_METERS = 50.0            # Equivalent horizontal meters per floor climbed
ELEVATOR_WAIT_MINUTES = 3.0            # Fixed elevator/stair transition time
DEFAULT_TASK_DURATION_MINUTES = 45.0   # Default estimated duration per maintenance task

# Rule 1: Topological Ladder Costs (Hierarchical No-Map Facility)
TOPO_COST_SAME_ROOM = 1.0              # Same room: minimal transition
TOPO_COST_SAME_FLOOR = 10.0            # Same floor, different room: hallway walk
TOPO_COST_BASE_FLOOR_DIFF = 10.0       # Base floor transition fee
TOPO_COST_PER_FLOOR_DIFF = 30.0        # Multiplier per floor level difference: 10 + 30 * |delta_floor|
TOPO_COST_DIFF_BUILDING = 150.0        # Different building in same facility/site (campus transit)
TOPO_COST_DIFF_SITE = 1000.0           # Different site / campus (vehicle transit)

# Rule 4: TSPTW Time Window Penalties
TIME_WINDOW_LATE_PENALTY_RATE = 1000.0 # Extreme penalty per minute past window end
TIME_WINDOW_EARLY_WAIT_RATE = 1.0      # Idle penalty per minute arriving before window start

# Rule 5: Asymmetric One-Way / Air-lock / Cleanroom Penalties
ASYMMETRIC_ONE_WAY_PENALTY = 100.0     # Penalty when moving against preferential flow or requiring decon airlock

# Routing Modes
MODE_HIERARCHICAL_TOPOLOGICAL = 'HIERARCHICAL_TOPOLOGICAL'
MODE_MANHATTAN_2D = 'MANHATTAN_2D'
MODE_GPS_HAVERSINE = 'GPS_HAVERSINE'
MODE_PURE_BUSINESS = 'PURE_BUSINESS'

# Stop Types
STOP_DEPOT = 'DEPOT'
STOP_CURRENT_LOCATION = 'CURRENT_LOCATION'
STOP_WORK_ORDER = 'WORK_ORDER'
STOP_WAREHOUSE = 'WAREHOUSE'

"""
Sub-decoding Routing Heuristics and Timeline Simulation Engine for Task 11.2 GA.
Implements Rule 1 (Nearest Neighbor + Due Date), Rule 2 (Travel Time Workload),
Rule 4 (Due Date SLA), Rule 7 (Warehouse Pickup), and Lunch Break windows.
"""
from typing import List, Dict, Tuple, Any, Optional
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from django.utils import timezone
from .constants import (
    WALKING_SPEED_METERS_PER_MIN, FLOOR_PENALTY_METERS,
    WAREHOUSE_PICKUP_BUFFER_MINUTES, SHIFT_LUNCH_BREAK_MINUTES
)
from algorithms.hungarian.cost_matrix import calculate_zone_penalty, normalize_text_token


def to_local_vn_time(dt: Optional[datetime]) -> Optional[datetime]:
    """Converts a timezone-aware or naive datetime to Vietnam local time (UTC+7)."""
    if dt is None:
        return None
    try:
        vn_tz = ZoneInfo("Asia/Ho_Chi_Minh")
        if timezone.is_aware(dt):
            return dt.astimezone(vn_tz)
        return dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(vn_tz)
    except Exception:
        return dt


def calculate_spatial_distance_meters(x1: float, y1: float, f1: int,
                                      x2: float, y2: float, f2: int) -> float:
    """Calculates Multi-Floor Manhattan distance in meters."""
    if (x1 == 0.0 and y1 == 0.0) or (x2 == 0.0 and y2 == 0.0):
        return 0.0
    dx = abs(float(x1) - float(x2))
    dy = abs(float(y1) - float(y2))
    dz = abs(int(f1 or 1) - int(f2 or 1))
    return dx + dy + (FLOOR_PENALTY_METERS * dz)


def estimate_transit_minutes(x1: float, y1: float, f1: int, z1: str,
                             x2: float, y2: float, f2: int, z2: str) -> float:
    """Estimates walking transit minutes including spatial distance and zone transitions."""
    dist_meters = calculate_spatial_distance_meters(x1, y1, f1, x2, y2, f2)
    travel_mins = dist_meters / max(10.0, WALKING_SPEED_METERS_PER_MIN)

    # Zone transition penalty conversion (e.g. Cleanroom gowning = 15-20 min, Standard = 3-5 min)
    zone_pen = calculate_zone_penalty(z1, z2)
    if zone_pen >= 40.0:
        travel_mins += 15.0  # Controlled cleanroom gowning / sterilization
    elif zone_pen >= 15.0:
        travel_mins += 3.0   # Inter-workshop transit

    return round(travel_mins, 2)


def sub_decode_route_nearest_neighbor(tech, assigned_tasks: List[Any],
                                      current_time=None) -> List[Any]:
    """
    Rule 1: Sub-decoding Routing Guardrail.
    Orders assigned tasks using a Hybrid Due-Date & Nearest-Neighbor heuristic.
    Tasks with imminent due dates are prioritized first; ties are broken by shortest distance.
    """
    if not assigned_tasks:
        return []
    if len(assigned_tasks) == 1:
        return list(assigned_tasks)

    now = current_time or timezone.now()
    remaining = list(assigned_tasks)
    ordered = []

    # Current position of the technician (active machine if IN_PROGRESS, else base station)
    curr_x = tech.coords_x
    curr_y = tech.coords_y
    curr_floor = tech.floor_level
    curr_zone = tech.zone_id

    while remaining:
        best_idx = 0
        best_score = float('inf')

        for idx, task in enumerate(remaining):
            # 1. Travel cost from current location
            travel_mins = estimate_transit_minutes(
                curr_x, curr_y, curr_floor, curr_zone,
                task.coords_x, task.coords_y, task.floor_level, task.zone_id
            )

            # 2. Due date urgency score
            due_urgency_penalty = 0.0
            if task.due_date:
                diff_hours = (task.due_date - now).total_seconds() / 3600.0
                if diff_hours <= 2.0:
                    due_urgency_penalty = -500.0  # Highly urgent SLA window
                elif diff_hours <= 4.0:
                    due_urgency_penalty = -200.0

            composite_distance_cost = travel_mins + due_urgency_penalty
            if composite_distance_cost < best_score:
                best_score = composite_distance_cost
                best_idx = idx

        next_task = remaining.pop(best_idx)
        ordered.append(next_task)
        curr_x = next_task.coords_x
        curr_y = next_task.coords_y
        curr_floor = next_task.floor_level
        curr_zone = next_task.zone_id

    return ordered


def simulate_technician_timeline(tech, ordered_tasks: List[Any],
                                 warehouse_coords: Optional[Tuple[float, float, int, str]] = None,
                                 shift_start_time=None) -> Dict[str, Any]:
    """
    Simulates cumulative timeline across ordered tasks for a technician.
    Includes repair duration, travel transit, warehouse pickup stop, and lunch break.
    """
    start_dt = shift_start_time or timezone.now()
    current_dt = start_dt

    curr_x = tech.coords_x
    curr_y = tech.coords_y
    curr_floor = tech.floor_level
    curr_zone = tech.zone_id

    # If tech is actively in progress, account for ongoing work
    if tech.in_progress_remaining_minutes > 0:
        current_dt += timedelta(minutes=tech.in_progress_remaining_minutes)

    total_repair_mins = 0
    total_travel_mins = 0
    total_warehouse_mins = 0
    total_distance_meters = 0.0
    zone_hops = 0
    last_zone = curr_zone

    task_timeline = []
    has_taken_lunch = False

    for task in ordered_tasks:
        task_travel_mins = 0.0

        # Zone hop tracking (Rule 10 Anti-Fragmentation)
        if task.zone_id and last_zone and task.zone_id != last_zone:
            zone_hops += 1
            last_zone = task.zone_id

        # Rule 7: Warehouse Pickup Detour if task requires spare parts
        if task.has_spare_parts:
            w_x, w_y, w_floor, w_zone = warehouse_coords or (curr_x, curr_y, curr_floor, "ZONE_WAREHOUSE")
            to_warehouse_mins = estimate_transit_minutes(curr_x, curr_y, curr_floor, curr_zone,
                                                         w_x, w_y, w_floor, w_zone)
            dist_w = calculate_spatial_distance_meters(curr_x, curr_y, curr_floor, w_x, w_y, w_floor)
            total_distance_meters += dist_w
            task_travel_mins += to_warehouse_mins
            total_warehouse_mins += WAREHOUSE_PICKUP_BUFFER_MINUTES
            
            # Arrive at warehouse and pick up parts
            current_dt += timedelta(minutes=to_warehouse_mins + WAREHOUSE_PICKUP_BUFFER_MINUTES)
            curr_x, curr_y, curr_floor, curr_zone = w_x, w_y, w_floor, w_zone

        # Travel from current location (or warehouse) to task equipment
        direct_travel_mins = estimate_transit_minutes(curr_x, curr_y, curr_floor, curr_zone,
                                                      task.coords_x, task.coords_y, task.floor_level, task.zone_id)
        dist_direct = calculate_spatial_distance_meters(curr_x, curr_y, curr_floor,
                                                        task.coords_x, task.coords_y, task.floor_level)
        total_distance_meters += dist_direct
        task_travel_mins += direct_travel_mins
        total_travel_mins += task_travel_mins
        current_dt += timedelta(minutes=direct_travel_mins)

        # Lunch Break check (12:00 - 13:00 window)
        task_start_dt = current_dt
        if not has_taken_lunch and task_start_dt.hour >= 12:
            current_dt += timedelta(minutes=SHIFT_LUNCH_BREAK_MINUTES)
            task_start_dt = current_dt
            has_taken_lunch = True

        # Repair work execution
        repair_mins = task.estimated_duration_minutes
        total_repair_mins += repair_mins
        current_dt += timedelta(minutes=repair_mins)
        task_finish_dt = current_dt

        # SLA Due Date compliance check (Rule 4)
        is_late = False
        is_backlog_past_due = False
        lateness_minutes = 0
        lateness_penalty_minutes = 0

        if task.due_date:
            if task.due_date < start_dt:
                # Task was already past due BEFORE today's shift started (overdue backlog item)
                is_backlog_past_due = True
                is_late = True
                # Effective shift delay: minutes into the shift until task completes
                mins_into_shift = int(max(0.0, (task_finish_dt - start_dt).total_seconds() / 60.0))
                lateness_penalty_minutes = min(90, mins_into_shift)
                lateness_minutes = mins_into_shift
            elif task_finish_dt > task.due_date:
                # Task due date was scheduled during or after shift start, but finish is after due date
                is_late = True
                delta_mins = int((task_finish_dt - task.due_date).total_seconds() / 60.0)
                lateness_minutes = delta_mins
                lateness_penalty_minutes = min(120, delta_mins)

        local_start = to_local_vn_time(task_start_dt)
        local_finish = to_local_vn_time(task_finish_dt)
        local_due = to_local_vn_time(task.due_date) if task.due_date else None

        task_timeline.append({
            "taskId": task.id,
            "taskCode": task.code,
            "taskTitle": task.title,
            "priority": task.priority,
            "priorityWeight": task.priority_weight,
            "startTime": local_start.strftime("%H:%M") if local_start else "--:--",
            "finishTime": local_finish.strftime("%H:%M") if local_finish else "--:--",
            "dueTime": local_due.strftime("%H:%M") if local_due else "N/A",
            "dueDateDisplay": local_due.strftime("%d/%m") if local_due else "",
            "isLate": is_late,
            "isBacklogPastDue": is_backlog_past_due,
            "latenessMinutes": lateness_minutes,
            "latenessPenaltyMinutes": lateness_penalty_minutes,
            "travelMinutes": round(task_travel_mins, 1),
            "repairMinutes": repair_mins,
            "hasSpareParts": task.has_spare_parts
        })

        # Update position anchor
        curr_x = task.coords_x
        curr_y = task.coords_y
        curr_floor = task.floor_level
        curr_zone = task.zone_id

    total_shift_time_mins = int(round(total_repair_mins + total_travel_mins + total_warehouse_mins))
    overload_mins = max(0, total_shift_time_mins - tech.max_shift_minutes)

    return {
        "technicianId": tech.user_id,
        "technicianName": tech.name,
        "taskCount": len(ordered_tasks),
        "totalMinutes": total_shift_time_mins,
        "repairMinutes": total_repair_mins,
        "travelMinutes": round(total_travel_mins, 1),
        "warehouseMinutes": total_warehouse_mins,
        "totalDistanceMeters": round(total_distance_meters, 1),
        "overloadMinutes": overload_mins,
        "zoneHops": zone_hops,
        "orderedTasks": task_timeline
    }

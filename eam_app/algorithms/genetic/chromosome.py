"""
Chromosome Representation and Individual Abstractions for GA Scheduling.
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from decimal import Decimal
from .constants import PRIORITY_WEIGHTS, DEFAULT_SHIFT_MINUTES, GENERAL_ZONE_TOKENS


class GATask:
    """Lightweight representation of a Work Order for fast GA fitness evaluation."""
    def __init__(self, wo, catalog=None):
        self.id = str(wo.id)
        self.code = getattr(wo, 'code', f"WO-{str(wo.id)[:8].upper()}")
        self.title = wo.title or ""
        self.priority = wo.priority or 'MEDIUM'
        self.priority_weight = PRIORITY_WEIGHTS.get(self.priority, 1.0)
        self.required_skill = wo.required_skill or ""
        self.min_skill_level = int(wo.min_skill_level or 1)
        self.required_certification = wo.required_certification or ""
        self.required_tools = wo.required_tools or []
        
        # Check spare parts: either JSON list or related materials
        has_spare_parts = False
        parts_list = getattr(wo, 'required_spare_parts', None)
        if parts_list and isinstance(parts_list, list) and len(parts_list) > 0:
            has_spare_parts = True
        elif hasattr(wo, 'materials') and wo.materials.exists():
            has_spare_parts = True
        self.has_spare_parts = has_spare_parts
        self.required_spare_parts = parts_list or []

        self.estimated_duration_minutes = int(wo.estimated_duration_minutes or 60)
        self.due_date = getattr(wo, 'due_date', None) or getattr(wo, 'deadline', None)
        
        # 3-Tier Spatial Fallback (WorkOrder -> Asset -> Location)
        coords_x = wo.coords_x
        coords_y = wo.coords_y
        floor_level = wo.floor_level
        zone_id = wo.zone_id

        asset_obj = getattr(wo, 'asset', None)
        loc_obj = getattr(asset_obj, 'location', None) if asset_obj else None

        if coords_x is None and asset_obj and getattr(asset_obj, 'coords_x', None) is not None:
            coords_x = asset_obj.coords_x
            coords_y = getattr(asset_obj, 'coords_y', 0.0)
            floor_level = getattr(asset_obj, 'floor_level', floor_level)
            if not zone_id and getattr(asset_obj, 'zone_id', None):
                zone_id = asset_obj.zone_id

        if coords_x is None and loc_obj and getattr(loc_obj, 'center_x', None) is not None:
            coords_x = loc_obj.center_x
            coords_y = getattr(loc_obj, 'center_y', 0.0)
            floor_level = getattr(loc_obj, 'floor_level', floor_level)
            if not zone_id and getattr(loc_obj, 'code', None):
                zone_id = loc_obj.code

        self.coords_x = float(coords_x if coords_x is not None else 0.0)
        self.coords_y = float(coords_y if coords_y is not None else 0.0)
        self.floor_level = int(floor_level or 1)
        self.zone_id = zone_id or ""
        
        # Resolve Floorplan ID from Asset Location parent or catalog
        self.floorplan_id = ""
        if catalog and self.zone_id:
            zone_to_fp = catalog.get('zone_to_floorplan', {})
            from algorithms.hungarian.cost_matrix import normalize_text_token
            self.floorplan_id = zone_to_fp.get(normalize_text_token(self.zone_id), "")
            
        if not self.floorplan_id and loc_obj:
            if getattr(loc_obj, 'zone_type', '') == 'FLOORPLAN':
                self.floorplan_id = str(loc_obj.id)
            elif getattr(loc_obj, 'parent_id', None):
                self.floorplan_id = str(loc_obj.parent_id)

        self.depends_on_wo_id = str(wo.depends_on_wo_id) if getattr(wo, 'depends_on_wo_id', None) else None
        self.is_crew_task = bool(getattr(wo, 'is_crew_task', False))


class GATechnician:
    """Lightweight representation of an available Technician."""
    def __init__(self, profile, current_time=None, catalog=None, today_schedule=None, active_wo=None):
        self.user_id = str(profile.user_id)
        self.username = getattr(profile.user, 'username', self.user_id)
        if hasattr(profile.user, 'get_full_name') and callable(profile.user.get_full_name):
            self.name = profile.user.get_full_name() or self.username
        else:
            self.name = self.username

        self.skills = profile.skills or []
        self.skill_level = int(profile.skill_level or 1)
        self.certifications = profile.certifications or []
        
        # Determine effective shift duration (Rule 8: Heterogeneous Shift Lengths)
        max_shift = getattr(profile, 'max_shift_minutes', None) or DEFAULT_SHIFT_MINUTES
        if today_schedule and getattr(today_schedule, 'shift_template', None):
            tmpl = today_schedule.shift_template
            st = tmpl.start_time
            et = tmpl.end_time
            dur = (et.hour * 60 + et.minute) - (st.hour * 60 + st.minute)
            if getattr(tmpl, 'is_overnight', False) or dur <= 0:
                dur += 24 * 60
            if dur > 0:
                max_shift = dur
        self.max_shift_minutes = int(max_shift)

        # Base origin position (Priority: Today's schedule duty zone -> Profile zone)
        effective_zone = profile.zone_id or ""
        if today_schedule and getattr(today_schedule, 'duty_zone_id', None):
            effective_zone = today_schedule.duty_zone_id

        self.zone_id = effective_zone
        self.coords_x = float(profile.coords_x if profile.coords_x is not None else 0.0)
        self.coords_y = float(profile.coords_y if profile.coords_y is not None else 0.0)
        self.floor_level = int(profile.floor_level or 1)

        # In-progress dynamic anchoring (active task currently in progress)
        self.in_progress_remaining_minutes = 0
        self.active_machine_coords = None
        if active_wo:
            dur = int(getattr(active_wo, 'estimated_duration_minutes', 60) or 60)
            elapsed = 0
            if current_time and getattr(active_wo, 'actual_start_time', None):
                elapsed = max(0, int((current_time - active_wo.actual_start_time).total_seconds() / 60.0))
            self.in_progress_remaining_minutes = max(10, dur - elapsed)
            # Anchor current technician location to active work order equipment
            if active_wo.coords_x is not None:
                self.coords_x = float(active_wo.coords_x)
                self.coords_y = float(active_wo.coords_y or 0.0)
                self.floor_level = int(active_wo.floor_level or 1)
                self.zone_id = active_wo.zone_id or self.zone_id
                self.active_machine_coords = (self.coords_x, self.coords_y, self.floor_level, self.zone_id)

        # Check if Roving / Plant-wide technician
        from algorithms.hungarian.cost_matrix import normalize_text_token
        tz_tok = normalize_text_token(self.zone_id)
        self.is_roving = (
            tz_tok in GENERAL_ZONE_TOKENS or
            any(g in tz_tok for g in {'TOAN_NHA_MAY', 'TOAN_CONG_TY', 'CO_DONG', 'ROVING'})
        )

        # Floorplan ID
        self.floorplan_id = ""
        if catalog and self.zone_id:
            zone_to_fp = catalog.get('zone_to_floorplan', {})
            self.floorplan_id = zone_to_fp.get(tz_tok, "")

        self.monthly_accumulated_hours = float(profile.monthly_accumulated_hours or Decimal("0.0"))


class GAIndividual:
    """Represents a candidate assignment solution across all M work orders."""
    def __init__(self, genes: List[int]):
        self.genes = list(genes)  # Array of length M, values in [0, N] (N = Virtual Tech)
        self.fitness = 0.0
        self.skill_score = 0.0
        self.workload_score = 0.0
        self.travel_score = 0.0
        self.penalties = {
            'overload': 0.0,
            'late': 0.0,
            'backlog': 0.0,
            'frag': 0.0,
            'floorplan': 0.0
        }
        self.schedules = {}     # tech_idx -> dict of timeline & ordered tasks
        self.backlog_tasks = [] # list of task indices assigned to Virtual Tech N

    def clone(self) -> 'GAIndividual':
        ind = GAIndividual(self.genes)
        ind.fitness = self.fitness
        ind.skill_score = self.skill_score
        ind.workload_score = self.workload_score
        ind.travel_score = self.travel_score
        ind.penalties = dict(self.penalties)
        ind.schedules = self.schedules
        ind.backlog_tasks = list(self.backlog_tasks)
        return ind

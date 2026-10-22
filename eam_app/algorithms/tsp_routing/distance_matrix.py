"""
Multi-Tier Distance Matrix Engine for Task 11.3 Technician Routing Optimization (TSP).
Supports 4 modes:
1. Hierarchical Topological Distance (No-Map Facility: Site -> Building -> Floor -> Room)
2. 2D Manhattan Distance with Floor Penalty (Floorplan coordinates)
3. GPS Haversine Distance (Outdoor coordinates)
4. Pure Business Fallback (No spatial coordinates available)
Also supports Asymmetric ATSP directional penalty for cleanrooms and one-way flows.
"""

import math
from typing import List, Dict, Tuple, Optional, Any
from datetime import time

from assets.models import Location
from .constants import (
    TOPO_COST_SAME_ROOM,
    TOPO_COST_SAME_FLOOR,
    TOPO_COST_BASE_FLOOR_DIFF,
    TOPO_COST_PER_FLOOR_DIFF,
    TOPO_COST_DIFF_BUILDING,
    TOPO_COST_DIFF_SITE,
    FLOOR_PENALTY_METERS,
    WALKING_SPEED_METERS_PER_MIN,
    ELEVATOR_WAIT_MINUTES,
    ASYMMETRIC_ONE_WAY_PENALTY,
    MODE_HIERARCHICAL_TOPOLOGICAL,
    MODE_MANHATTAN_2D,
    MODE_GPS_HAVERSINE,
    MODE_PURE_BUSINESS,
    STOP_DEPOT,
    STOP_CURRENT_LOCATION,
    STOP_WORK_ORDER,
    STOP_WAREHOUSE,
    DEFAULT_TASK_DURATION_MINUTES,
)


class RoutingNode:
    """
    Represents a stop along the technician's journey.
    """
    def __init__(
        self,
        node_id: str,
        node_type: str = STOP_WORK_ORDER,
        name: str = "",
        location: Optional[Location] = None,
        location_id: Optional[str] = None,
        coords_x: Optional[float] = None,
        coords_y: Optional[float] = None,
        gps_lat: Optional[float] = None,
        gps_lon: Optional[float] = None,
        floor_number: int = 1,
        priority: str = 'MEDIUM',
        time_window_start: Optional[time] = None,
        time_window_end: Optional[time] = None,
        estimated_duration_minutes: float = DEFAULT_TASK_DURATION_MINUTES,
        work_order: Optional[Any] = None,
        asset_name: Optional[str] = None,
        work_order_code: Optional[str] = None,
        is_controlled_zone: bool = False,
        one_way_exit_only: bool = False,
        required_for_wo_ids: Optional[List[str]] = None,
    ):
        self.node_id = str(node_id)
        self.node_type = node_type
        self.name = name or (f"Work Order {work_order_code}" if work_order_code else self.node_id)
        self.location = location
        self.location_id = str(location.id) if location else (str(location_id) if location_id else None)
        self.coords_x = coords_x
        self.coords_y = coords_y
        self.gps_lat = gps_lat
        self.gps_lon = gps_lon
        self.floor_number = floor_number
        self.priority = (priority or 'MEDIUM').upper()
        self.time_window_start = time_window_start
        self.time_window_end = time_window_end
        self.estimated_duration_minutes = float(estimated_duration_minutes or DEFAULT_TASK_DURATION_MINUTES)
        self.work_order = work_order
        self.asset_name = asset_name or (work_order.asset.name if work_order and getattr(work_order, 'asset', None) else "")
        self.work_order_code = work_order_code or (getattr(work_order, 'code', '') or str(getattr(work_order, 'id', '')))
        self.is_controlled_zone = is_controlled_zone
        self.one_way_exit_only = one_way_exit_only
        self.required_for_wo_ids = [str(x) for x in required_for_wo_ids] if required_for_wo_ids else []

    @classmethod
    def from_work_order(cls, wo, location_cache: Optional[Dict[str, Location]] = None) -> 'RoutingNode':
        """
        Rule 2: Movable Asset Context.
        Prioritizes work_order.incident_location over asset master location.
        4-Tier Spatial Fallback.
        """
        loc = wo.incident_location
        if not loc and getattr(wo, 'asset', None):
            loc = getattr(wo.asset, 'current_location', None) or getattr(wo.asset, 'location', None)

        if not loc and getattr(wo, 'incident_location_id', None) and location_cache:
            loc = location_cache.get(str(wo.incident_location_id))

        coords_x = getattr(wo, 'coords_x', None)
        coords_y = getattr(wo, 'coords_y', None)
        if (coords_x is None or coords_y is None) and getattr(wo, 'asset', None):
            coords_x = getattr(wo.asset, 'coords_x', None) or getattr(wo.asset, 'center_x', None)
            coords_y = getattr(wo.asset, 'coords_y', None) or getattr(wo.asset, 'center_y', None)
        if (coords_x is None or coords_y is None) and loc:
            coords_x = getattr(loc, 'center_x', None)
            coords_y = getattr(loc, 'center_y', None)

        floor_number = 1
        if loc and (getattr(loc, 'floor_level', None) is not None or getattr(loc, 'floor_number', None) is not None):
            floor_number = getattr(loc, 'floor_level', None) or getattr(loc, 'floor_number', 1) or 1
        elif getattr(wo, 'floor_level', None) is not None:
            floor_number = wo.floor_level or 1
        elif getattr(wo, 'asset', None):
            floor_number = getattr(wo.asset, 'floor_level', None) or getattr(wo.asset, 'floor_number', 1) or 1

        is_controlled = False
        if loc and getattr(loc, 'zone_type', '') in ('CONTROLLED', 'CLEANROOM'):
            is_controlled = True

        name = getattr(wo, 'title', '') or (wo.asset.name if getattr(wo, 'asset', None) else f"WO-{wo.id}")
        duration = float(getattr(wo, 'estimated_duration_hours', 0.75) or 0.75) * 60.0

        return cls(
            node_id=str(wo.id),
            node_type=STOP_WORK_ORDER,
            name=name,
            location=loc,
            location_id=str(loc.id) if loc else None,
            coords_x=coords_x,
            coords_y=coords_y,
            floor_number=floor_number,
            priority=getattr(wo, 'priority', 'MEDIUM'),
            time_window_start=getattr(wo, 'maintenance_window_start', None),
            time_window_end=getattr(wo, 'maintenance_window_end', None),
            estimated_duration_minutes=duration,
            work_order=wo,
            asset_name=wo.asset.name if getattr(wo, 'asset', None) else "",
            work_order_code=getattr(wo, 'code', '') or str(wo.id)[:8],
            is_controlled_zone=is_controlled,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'nodeId': self.node_id,
            'nodeType': self.node_type,
            'name': self.name,
            'locationId': self.location_id,
            'locationName': self.location.name if self.location else "",
            'coords': {'x': self.coords_x, 'y': self.coords_y} if self.coords_x is not None else None,
            'floorNumber': self.floor_number,
            'priority': self.priority,
            'timeWindow': {
                'start': self.time_window_start.strftime('%H:%M') if self.time_window_start else None,
                'end': self.time_window_end.strftime('%H:%M') if self.time_window_end else None,
            } if (self.time_window_start or self.time_window_end) else None,
            'estimatedDurationMinutes': self.estimated_duration_minutes,
            'workOrderId': str(self.work_order.id) if self.work_order else None,
            'workOrderCode': self.work_order_code,
            'assetName': self.asset_name,
        }


class MultiTierDistanceEngine:
    """
    Engine to compute distances between stops with multi-tier spatial fallback:
    - Mode 1: Topological Hierarchical (Campus/Building/Floor/Room)
    - Mode 2: 2D Manhattan with Vertical Floor Penalty
    - Mode 3: GPS Haversine
    - Mode 4: Business ordering
    """

    def __init__(self, tenant=None, default_pixel_ratio: float = 10.0):
        self.tenant = tenant
        self.default_pixel_ratio = default_pixel_ratio or 10.0
        self._location_cache: Dict[str, Location] = {}
        self._ancestor_cache: Dict[str, List[Location]] = {}

    def get_location(self, loc_id: Optional[str]) -> Optional[Location]:
        if not loc_id:
            return None
        loc_str = str(loc_id)
        if loc_str in self._location_cache:
            return self._location_cache[loc_str]
        try:
            qs = Location.objects.all()
            if self.tenant:
                qs = qs.filter(tenant=self.tenant)
            loc = qs.filter(id=loc_str).first()
            if loc:
                self._location_cache[loc_str] = loc
            return loc
        except Exception:
            return None

    def get_ancestors(self, location: Optional[Location]) -> List[Location]:
        """
        Traverse up parent_id hierarchy to root.
        """
        if not location:
            return []
        loc_id = str(location.id)
        if loc_id in self._ancestor_cache:
            return self._ancestor_cache[loc_id]

        ancestors = [location]
        curr = location
        visited_ids = {loc_id}
        depth = 0

        while curr and curr.parent_id and depth < 10:
            p_id = str(curr.parent_id)
            if p_id in visited_ids:
                break
            visited_ids.add(p_id)
            parent = self.get_location(p_id)
            if not parent:
                break
            ancestors.append(parent)
            curr = parent
            depth += 1

        self._ancestor_cache[loc_id] = ancestors
        return ancestors

    def get_building(self, location: Optional[Location]) -> Optional[Location]:
        if not location:
            return None
        ancestors = self.get_ancestors(location)
        for loc in ancestors:
            if getattr(loc, 'location_type', '') == 'BUILDING':
                return loc
        # Fallback: if 2nd or 3rd level ancestor exists
        if len(ancestors) >= 3:
            return ancestors[-2]
        elif len(ancestors) == 2:
            return ancestors[-1]
        return None

    def get_site(self, location: Optional[Location]) -> Optional[Location]:
        if not location:
            return None
        ancestors = self.get_ancestors(location)
        for loc in reversed(ancestors):
            if getattr(loc, 'location_type', '') == 'SITE':
                return loc
        if len(ancestors) >= 3:
            return ancestors[-1]
        return None

    def determine_routing_mode(self, nodes: List[RoutingNode]) -> str:
        """
        Determines the most accurate spatial routing mode available for the set of nodes.
        Prioritizes work orders to determine facility mode.
        """
        wo_nodes = [n for n in nodes if n.node_type == STOP_WORK_ORDER]
        if not wo_nodes:
            wo_nodes = [n for n in nodes if n.node_type != STOP_DEPOT]
        if not wo_nodes:
            return MODE_PURE_BUSINESS

        # Check 2D coordinates: meaningful if any non-zero coordinates exist
        has_real_2d = any((n.coords_x or 0.0) != 0.0 or (n.coords_y or 0.0) != 0.0 for n in wo_nodes)
        has_2d_all = all(n.coords_x is not None and n.coords_y is not None for n in wo_nodes)
        if has_real_2d and has_2d_all:
            return MODE_MANHATTAN_2D

        # Check GPS coordinates
        has_gps = all(n.gps_lat is not None and n.gps_lon is not None for n in wo_nodes)
        if has_gps:
            return MODE_GPS_HAVERSINE

        # Check Hierarchical Location
        has_loc = any(n.location or n.location_id for n in wo_nodes)
        if has_loc:
            return MODE_HIERARCHICAL_TOPOLOGICAL

        return MODE_PURE_BUSINESS

    def compute_hierarchical_topological_distance(self, loc_a: Optional[Location], loc_b: Optional[Location], floor_a: int = 1, floor_b: int = 1) -> float:
        """
        Rule 1: Topological Hierarchical Routing.
        Ladder:
        - Same room: 1.0
        - Same floor: 10.0
        - Same building, diff floor: 10.0 + 30.0 * |floor_a - floor_b|
        - Different building, same site: 150.0
        - Different site: 1000.0
        """
        if not loc_a or not loc_b:
            # If one or both lack location, return neutral floor-adjusted cost
            if floor_a == floor_b:
                return TOPO_COST_SAME_FLOOR
            return TOPO_COST_BASE_FLOOR_DIFF + TOPO_COST_PER_FLOOR_DIFF * abs(floor_a - floor_b)

        if str(loc_a.id) == str(loc_b.id):
            return TOPO_COST_SAME_ROOM

        # Check same parent (e.g. same floor or department)
        if loc_a.parent_id and loc_a.parent_id == loc_b.parent_id:
            fa = getattr(loc_a, 'floor_number', None) or floor_a
            fb = getattr(loc_b, 'floor_number', None) or floor_b
            if fa == fb:
                return TOPO_COST_SAME_FLOOR
            return TOPO_COST_BASE_FLOOR_DIFF + TOPO_COST_PER_FLOOR_DIFF * abs(fa - fb)

        # Check same building
        bldg_a = self.get_building(loc_a)
        bldg_b = self.get_building(loc_b)

        if bldg_a and bldg_b and str(bldg_a.id) == str(bldg_b.id):
            fa = getattr(loc_a, 'floor_number', None) or floor_a
            fb = getattr(loc_b, 'floor_number', None) or floor_b
            floor_diff = abs(fa - fb)
            if floor_diff == 0:
                return TOPO_COST_SAME_FLOOR
            return TOPO_COST_BASE_FLOOR_DIFF + TOPO_COST_PER_FLOOR_DIFF * floor_diff

        # Check same site
        site_a = self.get_site(loc_a)
        site_b = self.get_site(loc_b)
        if site_a and site_b and str(site_a.id) == str(site_b.id):
            return TOPO_COST_DIFF_BUILDING

        # Different building or unlinked
        if bldg_a and bldg_b and str(bldg_a.id) != str(bldg_b.id):
            return TOPO_COST_DIFF_BUILDING

        return TOPO_COST_DIFF_SITE

    def compute_manhattan_distance(
        self,
        x1: float, y1: float, floor1: int,
        x2: float, y2: float, floor2: int,
        pixel_ratio: Optional[float] = None
    ) -> float:
        """
        Rule 8: Multi-floor vertical penalty on 2D coordinates.
        d = horizontal_distance_meters + 50.0 * |floor1 - floor2| + elevator_distance
        """
        ratio = pixel_ratio or self.default_pixel_ratio or 10.0
        # If coordinates are in pixels (e.g., > 100 on 1000x700 canvas), scale by ratio
        dx_meters = abs(x1 - x2) / ratio if ratio > 0 else abs(x1 - x2)
        dy_meters = abs(y1 - y2) / ratio if ratio > 0 else abs(y1 - y2)
        horizontal_dist = dx_meters + dy_meters

        floor_diff = abs(floor1 - floor2)
        vertical_dist = FLOOR_PENALTY_METERS * floor_diff
        elevator_dist = (WALKING_SPEED_METERS_PER_MIN * ELEVATOR_WAIT_MINUTES) if floor_diff > 0 else 0.0

        return horizontal_dist + vertical_dist + elevator_dist

    def compute_haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Great-circle distance in meters.
        """
        r = 6371000.0  # Earth radius in meters
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)

        a = math.sin(delta_phi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0)**2
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        return r * c

    def calculate_distance(self, node_a: RoutingNode, node_b: RoutingNode, mode: Optional[str] = None) -> float:
        """
        Computes transition cost/distance from node_a to node_b.
        Includes Rule 5 ATSP asymmetric penalties (cleanroom decontamination / one-way paths).
        """
        if node_a.node_id == node_b.node_id:
            return 0.0

        resolved_mode = mode or self.determine_routing_mode([node_a, node_b])

        base_distance = 0.0
        if resolved_mode == MODE_MANHATTAN_2D:
            if (node_a.coords_x is not None and node_a.coords_y is not None and
                node_b.coords_x is not None and node_b.coords_y is not None):
                pixel_ratio = getattr(node_a.location, 'pixel_to_meter_ratio', None) or self.default_pixel_ratio
                base_distance = self.compute_manhattan_distance(
                    node_a.coords_x, node_a.coords_y, node_a.floor_number,
                    node_b.coords_x, node_b.coords_y, node_b.floor_number,
                    pixel_ratio=pixel_ratio
                )
            else:
                # Fallback to topological
                base_distance = self.compute_hierarchical_topological_distance(
                    node_a.location, node_b.location, node_a.floor_number, node_b.floor_number
                )

        elif resolved_mode == MODE_GPS_HAVERSINE:
            if (node_a.gps_lat is not None and node_a.gps_lon is not None and
                node_b.gps_lat is not None and node_b.gps_lon is not None):
                base_distance = self.compute_haversine_distance(
                    node_a.gps_lat, node_a.gps_lon, node_b.gps_lat, node_b.gps_lon
                )
            else:
                base_distance = self.compute_hierarchical_topological_distance(
                    node_a.location, node_b.location, node_a.floor_number, node_b.floor_number
                )

        elif resolved_mode == MODE_HIERARCHICAL_TOPOLOGICAL:
            base_distance = self.compute_hierarchical_topological_distance(
                node_a.location, node_b.location, node_a.floor_number, node_b.floor_number
            )

        else:
            # MODE_PURE_BUSINESS fallback
            base_distance = 10.0

        # Rule 5: Asymmetric ATSP penalties (Controlled Cleanroom Zone or One-Way exit)
        asymmetric_penalty = 0.0
        if node_a.one_way_exit_only:
            # Exiting through a one-way security lock or airlock
            asymmetric_penalty += ASYMMETRIC_ONE_WAY_PENALTY
        if node_a.is_controlled_zone != node_b.is_controlled_zone:
            # Entering or exiting cleanroom requires decontamination protocol
            asymmetric_penalty += ASYMMETRIC_ONE_WAY_PENALTY

        return float(base_distance + asymmetric_penalty)

    def build_distance_matrix(self, nodes: List[RoutingNode], forced_mode: Optional[str] = None) -> Tuple[List[List[float]], str]:
        """
        Builds an N x N distance matrix for the given list of nodes.
        Returns: (matrix, routing_mode)
        """
        # Resolve locations if needed
        for node in nodes:
            if not node.location and node.location_id:
                node.location = self.get_location(node.location_id)

        mode = forced_mode or self.determine_routing_mode(nodes)
        n = len(nodes)
        matrix = [[0.0 for _ in range(n)] for _ in range(n)]

        for i in range(n):
            for j in range(n):
                if i == j:
                    matrix[i][j] = 0.0
                else:
                    matrix[i][j] = self.calculate_distance(nodes[i], nodes[j], mode=mode)

        return matrix, mode

"""
Service Layer for Task 11.3 Technician Routing Optimization (TSP).
Coordinates distance matrix computation, tiered ATSP/TSPTW solving,
mid-shift re-routing, pit-stops, and scan-to-relocate operations.
"""

from typing import List, Dict, Tuple, Optional, Any
from datetime import datetime, time
import logging

from django.db import transaction
from django.utils import timezone

from assets.models import Location, Asset
from workorders.models import WorkOrder
from .constants import (
    STOP_DEPOT,
    STOP_CURRENT_LOCATION,
    STOP_WORK_ORDER,
    STOP_WAREHOUSE,
    MODE_PURE_BUSINESS,
    MODE_HIERARCHICAL_TOPOLOGICAL,
    MODE_MANHATTAN_2D,
    DEFAULT_TASK_DURATION_MINUTES,
    WALKING_SPEED_METERS_PER_MIN,
)
from .distance_matrix import MultiTierDistanceEngine, RoutingNode
from .solver import TieredATSPSolver, minutes_to_time_str

logger = logging.getLogger(__name__)


class TSPRoutingService:
    """
    Main orchestrator for Technician Daily Route Optimization.
    """

    def __init__(self, tenant=None):
        self.tenant = tenant
        self.distance_engine = MultiTierDistanceEngine(tenant=tenant)
        self.solver = TieredATSPSolver(walking_speed=WALKING_SPEED_METERS_PER_MIN)

    def _get_warehouse_location(self) -> Optional[Location]:
        """Finds warehouse or depot location for the tenant."""
        if not self.tenant:
            return None
        wh = Location.objects.filter(tenant=self.tenant, location_type='WAREHOUSE', is_active=True).first()
        if not wh:
            wh = Location.objects.filter(
                tenant=self.tenant,
                name__icontains='kho',
                is_active=True
            ).first()
        if not wh:
            wh = Location.objects.filter(
                tenant=self.tenant,
                name__icontains='warehouse',
                is_active=True
            ).first()
        return wh

    def _format_location_name(self, loc: Optional[Location]) -> str:
        if not loc:
            return "Vị trí chưa xác định"
        ancestors = self.distance_engine.get_ancestors(loc)
        if len(ancestors) > 1:
            names = [a.name for a in ancestors]
            return " > ".join(names)
        return loc.name

    def optimize_daily_route(
        self,
        technician: Any,
        work_orders: List[WorkOrder],
        start_coords: Optional[Dict[str, float]] = None,
        start_location_id: Optional[str] = None,
        return_to_depot: bool = True,
        start_time_minutes: float = 480.0,  # 08:00 AM
    ) -> Dict[str, Any]:
        """
        Calculates optimized daily route for a technician across a set of assigned work orders.
        """
        # Rule 11: Feature Toggle Check
        routing_enabled = getattr(self.tenant, 'enable_tsp_routing', True) if self.tenant else True

        if not work_orders:
            return {
                'success': True,
                'data': {
                    'totalEstimatedMinutes': 0,
                    'totalDistanceMeters': 0.0,
                    'routingMode': MODE_PURE_BUSINESS if not routing_enabled else MODE_HIERARCHICAL_TOPOLOGICAL,
                    'routingEnabled': routing_enabled,
                    'orderedStops': [],
                }
            }

        # Resolve Depot / Starting Stop
        start_loc = None
        if start_location_id:
            start_loc = self.distance_engine.get_location(start_location_id)
        if not start_loc:
            start_loc = self._get_warehouse_location()

        sx = start_coords.get('x') if start_coords else (getattr(start_loc, 'center_x', 0.0) if start_loc else 0.0)
        sy = start_coords.get('y') if start_coords else (getattr(start_loc, 'center_y', 0.0) if start_loc else 0.0)
        start_floor = getattr(start_loc, 'floor_number', 1) if start_loc else 1

        depot_node = RoutingNode(
            node_id="depot_start",
            node_type=STOP_DEPOT,
            name=f"Điểm xuất phát: {start_loc.name if start_loc else 'Phòng Điều Phối'}",
            location=start_loc,
            coords_x=sx,
            coords_y=sy,
            floor_number=start_floor,
            priority='LOW',
            estimated_duration_minutes=0.0,
        )

        nodes: List[RoutingNode] = [depot_node]

        # Specialized Tool & Spare Part Pickup Stop injection (automatic resolution)
        pickup_nodes = self._resolve_pickup_nodes(work_orders, exclude_location_id=str(start_loc.id) if start_loc else None)
        nodes.extend(pickup_nodes)

        for wo in work_orders:
            wo_node = RoutingNode.from_work_order(wo, location_cache=self.distance_engine._location_cache)
            nodes.append(wo_node)

        wo_indices = list(range(1, len(nodes)))

        # If TSP Routing disabled on tenant, use Rule 11 pure business fallback
        if not routing_enabled:
            dist_matrix, _ = self.distance_engine.build_distance_matrix(nodes, forced_mode=MODE_PURE_BUSINESS)
            eval_result = self.solver.solve_pure_business_ordering(
                start_node_idx=0,
                work_order_indices=wo_indices,
                nodes=nodes,
                dist_matrix=dist_matrix,
                start_time_minutes=start_time_minutes,
                return_to_depot=return_to_depot,
            )
            return self._build_response(eval_result, nodes, MODE_PURE_BUSINESS, routing_enabled=False)

        # Build Distance Matrix & determine mode
        dist_matrix, resolved_mode = self.distance_engine.build_distance_matrix(nodes)

        # Rule 10: Graceful fallback if completely zero-location
        if resolved_mode == MODE_PURE_BUSINESS:
            eval_result = self.solver.solve_pure_business_ordering(
                start_node_idx=0,
                work_order_indices=wo_indices,
                nodes=nodes,
                dist_matrix=dist_matrix,
                start_time_minutes=start_time_minutes,
                return_to_depot=return_to_depot,
            )
        else:
            # Rule 3, 4, 5: Tiered ATSP with TSPTW Solver
            eval_result = self.solver.solve_tiered_tsp(
                start_node_idx=0,
                work_order_indices=wo_indices,
                nodes=nodes,
                dist_matrix=dist_matrix,
                start_time_minutes=start_time_minutes,
                return_to_depot=return_to_depot,
            )

        return self._build_response(eval_result, nodes, resolved_mode, routing_enabled=True)

    def re_route_mid_shift(
        self,
        technician: Any,
        current_coords: Optional[Dict[str, float]] = None,
        current_location_id: Optional[str] = None,
        completed_work_order_ids: Optional[List[str]] = None,
        remaining_work_orders: Optional[List[WorkOrder]] = None,
        include_warehouse_pitstop: bool = False,
        pitstop_location_id: Optional[str] = None,
        return_to_depot: bool = True,
        start_time_minutes: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Rule 7: Dynamic Mid-shift Re-routing from current location.
        Rule 6: Intermediate Pit-Stop insertion for warehouse replenishment / tool pickup.
        """
        routing_enabled = getattr(self.tenant, 'enable_tsp_routing', True) if self.tenant else True

        completed_set = set(str(cid) for cid in (completed_work_order_ids or []))
        active_wos = [wo for wo in (remaining_work_orders or []) if str(wo.id) not in completed_set]

        # Calculate current time in minutes if not provided
        if start_time_minutes is None:
            now = timezone.localtime()
            start_time_minutes = float(now.hour * 60 + now.minute)

        curr_loc = None
        if current_location_id:
            curr_loc = self.distance_engine.get_location(current_location_id)

        cx = current_coords.get('x') if current_coords else (getattr(curr_loc, 'center_x', 0.0) if curr_loc else 0.0)
        cy = current_coords.get('y') if current_coords else (getattr(curr_loc, 'center_y', 0.0) if curr_loc else 0.0)
        curr_floor = getattr(curr_loc, 'floor_level', None) or getattr(curr_loc, 'floor_number', 1) if curr_loc else 1

        curr_node = RoutingNode(
            node_id="current_position",
            node_type=STOP_CURRENT_LOCATION,
            name=f"Vị trí hiện tại: {curr_loc.name if curr_loc else 'Hiện trường'}",
            location=curr_loc,
            coords_x=cx,
            coords_y=cy,
            floor_number=curr_floor,
            priority='LOW',
            estimated_duration_minutes=0.0,
        )

        nodes: List[RoutingNode] = [curr_node]

        # Rule 6: Intermediate Pit-stop to warehouse / tool storage room
        if include_warehouse_pitstop:
            wh_loc = None
            if pitstop_location_id:
                wh_loc = self.distance_engine.get_location(pitstop_location_id)
            if not wh_loc:
                wh_loc = self._get_warehouse_location()
            wh_x = getattr(wh_loc, 'center_x', 0.0) if wh_loc else 0.0
            wh_y = getattr(wh_loc, 'center_y', 0.0) if wh_loc else 0.0
            wh_floor = getattr(wh_loc, 'floor_level', None) or getattr(wh_loc, 'floor_number', 1) if wh_loc else 1
            wh_name = f"Trạm tiếp vận: {wh_loc.name if wh_loc else 'Kho vật tư'}"
            wh_node = RoutingNode(
                node_id="warehouse_pitstop",
                node_type=STOP_WAREHOUSE,
                name=wh_name,
                location=wh_loc,
                coords_x=wh_x,
                coords_y=wh_y,
                floor_number=wh_floor,
                priority='HIGH',
                estimated_duration_minutes=15.0,  # 15 minutes replenishment time
            )
            nodes.append(wh_node)
        else:
            curr_loc_id = str(curr_node.location.id) if curr_node.location else None
            pickup_nodes = self._resolve_pickup_nodes(active_wos, exclude_location_id=curr_loc_id)
            nodes.extend(pickup_nodes)

        # Append remaining work orders
        for wo in active_wos:
            wo_node = RoutingNode.from_work_order(wo, location_cache=self.distance_engine._location_cache)
            nodes.append(wo_node)

        if len(nodes) == 1:
            # Only current location, no work left
            return {
                'success': True,
                'data': {
                    'totalEstimatedMinutes': 0,
                    'totalDistanceMeters': 0.0,
                    'routingMode': MODE_HIERARCHICAL_TOPOLOGICAL,
                    'routingEnabled': routing_enabled,
                    'orderedStops': [curr_node.to_dict()],
                }
            }

        # Build distance matrix
        dist_matrix, resolved_mode = self.distance_engine.build_distance_matrix(nodes)

        if not routing_enabled:
            wo_indices = list(range(1, len(nodes)))
            eval_result = self.solver.solve_pure_business_ordering(
                start_node_idx=0,
                work_order_indices=wo_indices,
                nodes=nodes,
                dist_matrix=dist_matrix,
                start_time_minutes=start_time_minutes,
                return_to_depot=return_to_depot,
            )
            return self._build_response(eval_result, nodes, MODE_PURE_BUSINESS, routing_enabled=False)

        # If pit-stop requested, force route: curr -> wh -> TSP(remaining)
        if include_warehouse_pitstop and len(nodes) > 2:
            wh_idx = 1
            remaining_indices = list(range(2, len(nodes)))
            # Solve remaining from warehouse stop
            sub_eval = self.solver.solve_tiered_tsp(
                start_node_idx=wh_idx,
                work_order_indices=remaining_indices,
                nodes=nodes,
                dist_matrix=dist_matrix,
                start_time_minutes=start_time_minutes + (dist_matrix[0][wh_idx] / self.solver.walking_speed),
                return_to_depot=return_to_depot,
            )
            # Prepend current position (index 0)
            overall_tour = [0] + [s['nodeIndex'] for s in sub_eval.schedule]
            eval_result = self.solver.evaluate_tour(
                overall_tour, nodes, dist_matrix, start_time_minutes, return_to_depot=False
            )
        else:
            wo_indices = list(range(1, len(nodes)))
            eval_result = self.solver.solve_tiered_tsp(
                start_node_idx=0,
                work_order_indices=wo_indices,
                nodes=nodes,
                dist_matrix=dist_matrix,
                start_time_minutes=start_time_minutes,
                return_to_depot=return_to_depot,
            )

        return self._build_response(eval_result, nodes, resolved_mode, routing_enabled=True)

    def scan_to_relocate(
        self,
        qr_code_or_asset_id: str,
        new_location_id: str,
        user: Any = None,
    ) -> Dict[str, Any]:
        """
        Rule 2 & Rule 11 (TC-TSP-11): Scan-to-Relocate.
        Updates movable asset location upon technician scanning QR code.
        """
        qs = Asset.objects.all()
        if self.tenant:
            qs = qs.filter(tenant=self.tenant)

        asset = qs.filter(qr_code=qr_code_or_asset_id).first()
        if not asset:
            asset = qs.filter(id=qr_code_or_asset_id).first()
        if not asset:
            return {'success': False, 'message': f'Asset not found: {qr_code_or_asset_id}'}

        new_loc = self.distance_engine.get_location(new_location_id)
        if not new_loc:
            return {'success': False, 'message': f'Location not found: {new_location_id}'}

        with transaction.atomic():
            old_loc = asset.location
            asset.location = new_loc
            if hasattr(asset, 'current_location'):
                setattr(asset, 'current_location', new_loc)
            asset.floor_level = new_loc.floor_level
            if user:
                asset.updated_by = user
            asset.save()

        logger.info(
            f"[Scan-to-Relocate] Asset {asset.name} relocated from {old_loc.name if old_loc else 'None'} "
            f"to {new_loc.name} by {user.username if user else 'System'}"
        )

        return {
            'success': True,
            'message': f"Đã cập nhật vị trí thiết bị {asset.name} sang {new_loc.name}",
            'data': {
                'assetId': str(asset.id),
                'assetName': asset.name,
                'qrCode': asset.qr_code,
                'newLocationId': str(new_loc.id),
                'newLocationName': new_loc.name,
                'floorNumber': new_loc.floor_number,
            }
        }

    def _build_response(
        self,
        eval_result: Any,
        nodes: List[RoutingNode],
        routing_mode: str,
        routing_enabled: bool,
    ) -> Dict[str, Any]:
        """Formats solving evaluation into uniform JSON response structure."""
        ordered_stops = []
        for step_idx, item in enumerate(eval_result.schedule):
            node: RoutingNode = item['node']
            loc_name = self._format_location_name(node.location)

            stop_data = {
                'step': step_idx,
                'type': node.node_type,
                'name': node.name,
                'locationId': node.location_id,
                'locationName': loc_name,
                'floorNumber': node.floor_number,
                'coords': {'x': node.coords_x, 'y': node.coords_y} if node.coords_x is not None else None,
                'priority': node.priority,
                'estimatedArrival': item.get('arrivalTimeStr', '08:00'),
                'serviceStartTime': minutes_to_time_str(item.get('serviceStartMinutes', 0.0)),
                'departureTime': item.get('departureTimeStr', '08:00'),
                'travelDistanceMeters': round(item.get('travelDistance', 0.0), 1),
                'travelTimeMinutes': round(item.get('travelTimeMinutes', 0.0), 1),
                'waitingMinutes': round(item.get('waitingMinutes', 0.0), 1),
                'timeWindow': {
                    'start': node.time_window_start.strftime('%H:%M') if node.time_window_start else None,
                    'end': node.time_window_end.strftime('%H:%M') if node.time_window_end else None,
                } if (node.time_window_start or node.time_window_end) else None,
                'workOrderId': str(node.work_order.id) if node.work_order else None,
                'workOrderCode': node.work_order_code or (str(node.work_order.id)[:8] if node.work_order else None),
                'assetName': node.asset_name,
            }

            if node.node_type in (STOP_DEPOT, STOP_CURRENT_LOCATION):
                stop_data['action'] = 'DEPART'
            elif node.node_type == STOP_WAREHOUSE:
                if node.node_id.startswith('tool_pickup_'):
                    stop_data['action'] = 'PICKUP_TOOLS'
                else:
                    stop_data['action'] = 'PICKUP_SUPPLIES'
            else:
                stop_data['action'] = 'SERVICE'

            if step_idx > 0:
                prev_floor = ordered_stops[step_idx - 1].get('floorNumber')
                curr_floor = stop_data.get('floorNumber')
                if prev_floor and curr_floor and prev_floor != curr_floor:
                    is_up = curr_floor > prev_floor
                    stop_data['floorTransition'] = {
                        'fromFloor': prev_floor,
                        'toFloor': curr_floor,
                        'direction': 'UP' if is_up else 'DOWN',
                        'transitionType': 'STAIRS',
                        'actionLabel': f"Chuyển sang Tầng {curr_floor}"
                    }

            ordered_stops.append(stop_data)

        total_distance = round(eval_result.total_distance, 1) if routing_enabled else 0.0
        total_time = int(round(eval_result.total_time_minutes))

        return {
            'success': True,
            'data': {
                'totalEstimatedMinutes': total_time,
                'totalDistanceMeters': total_distance,
                'routingMode': routing_mode,
                'routingEnabled': routing_enabled,
                'totalStops': len(ordered_stops),
                'orderedStops': ordered_stops,
            }
        }

    def _resolve_pickup_nodes(self, work_orders, exclude_location_id=None) -> List[RoutingNode]:
        """
        Automatically resolves tool and spare part storage locations for the given work orders
        and generates high-priority pickup stops.
        """
        from assets.models import Tool, SparePart
        pickup_nodes: List[RoutingNode] = []
        seen_loc_ids = set()
        if exclude_location_id:
            seen_loc_ids.add(str(exclude_location_id))

        # 1. Collect required tool codes and required spare parts across all work orders
        tool_code_to_wos = {}
        part_ref_to_wos = {}
        for wo in work_orders:
            req_tools = getattr(wo, 'required_tools', None) or []
            for t_code in req_tools:
                if t_code:
                    tool_code_to_wos.setdefault(str(t_code).strip(), []).append(wo)

            req_parts = getattr(wo, 'required_spare_parts', None) or []
            for p_ref in req_parts:
                if p_ref:
                    part_ref_to_wos.setdefault(str(p_ref).strip(), []).append(wo)

        # 2. Query Tools and their locations
        if tool_code_to_wos:
            tenant_filter = {'tenant': self.tenant} if self.tenant else {}
            tools_qs = Tool.objects.filter(code__in=list(tool_code_to_wos.keys()), is_active=True, **tenant_filter).select_related('location')
            loc_to_tool_names = {}
            for t in tools_qs:
                if t.location:
                    loc_to_tool_names.setdefault(t.location, []).append(t.name)
            
            for loc, t_names in loc_to_tool_names.items():
                lid = str(loc.id)
                if lid not in seen_loc_ids:
                    seen_loc_ids.add(lid)
                    tx = getattr(loc, 'center_x', 0.0) or 0.0
                    ty = getattr(loc, 'center_y', 0.0) or 0.0
                    t_floor = getattr(loc, 'floor_level', None) or getattr(loc, 'floor_number', 1) or 1
                    t_summary = ", ".join(t_names[:2])
                    pickup_nodes.append(RoutingNode(
                        node_id=f"tool_pickup_{loc.id}",
                        node_type=STOP_WAREHOUSE,
                        name=f"Lấy dụng cụ chuyên dụng ({t_summary}): {loc.name}",
                        location=loc,
                        coords_x=tx,
                        coords_y=ty,
                        floor_number=t_floor,
                        priority='HIGH',
                        estimated_duration_minutes=5.0,
                    ))

        # Fallback for wo.tool_pickup_location if any work orders specified it
        for wo in work_orders:
            req_tools = getattr(wo, 'required_tools', None) or []
            tool_loc = getattr(wo, 'tool_pickup_location', None)
            if req_tools and tool_loc and str(tool_loc.id) not in seen_loc_ids:
                seen_loc_ids.add(str(tool_loc.id))
                tx = getattr(tool_loc, 'center_x', 0.0) or 0.0
                ty = getattr(tool_loc, 'center_y', 0.0) or 0.0
                t_floor = getattr(tool_loc, 'floor_level', None) or getattr(tool_loc, 'floor_number', 1) or 1
                tool_names = ", ".join(str(t) for t in req_tools[:2])
                pickup_nodes.append(RoutingNode(
                    node_id=f"tool_pickup_{tool_loc.id}",
                    node_type=STOP_WAREHOUSE,
                    name=f"Lấy dụng cụ chuyên dụng ({tool_names}): {tool_loc.name}",
                    location=tool_loc,
                    coords_x=tx,
                    coords_y=ty,
                    floor_number=t_floor,
                    priority='HIGH',
                    estimated_duration_minutes=5.0,
                ))

        # 3. Query Spare Parts and their locations
        if part_ref_to_wos:
            from django.db.models import Q
            tenant_filter = {'tenant': self.tenant} if self.tenant else {}
            part_refs = list(part_ref_to_wos.keys())
            valid_uuids = []
            for r in part_refs:
                try:
                    import uuid
                    uuid.UUID(r)
                    valid_uuids.append(r)
                except ValueError:
                    pass

            q_filter = Q(id__in=valid_uuids) | Q(part_number__in=part_refs)
            parts_qs = SparePart.objects.filter(q_filter, **tenant_filter).select_related('location')
            loc_to_part_names = {}
            for p in parts_qs:
                if p.location:
                    loc_to_part_names.setdefault(p.location, []).append(p.name)

            for loc, p_names in loc_to_part_names.items():
                lid = str(loc.id)
                if lid not in seen_loc_ids:
                    seen_loc_ids.add(lid)
                    px = getattr(loc, 'center_x', 0.0) or 0.0
                    py = getattr(loc, 'center_y', 0.0) or 0.0
                    p_floor = getattr(loc, 'floor_level', None) or getattr(loc, 'floor_number', 1) or 1
                    p_summary = ", ".join(p_names[:2])
                    pickup_nodes.append(RoutingNode(
                        node_id=f"part_pickup_{loc.id}",
                        node_type=STOP_WAREHOUSE,
                        name=f"Lấy vật tư/phụ tùng ({p_summary}): {loc.name}",
                        location=loc,
                        coords_x=px,
                        coords_y=py,
                        floor_number=p_floor,
                        priority='HIGH',
                        estimated_duration_minutes=5.0,
                    ))

        return pickup_nodes

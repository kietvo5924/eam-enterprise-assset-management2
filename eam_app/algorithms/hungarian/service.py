"""
Facade Service for Task 11.1 Hungarian Assignment Optimization
"""
from typing import List, Dict, Any, Optional
from django.utils import timezone
from django.db import transaction
from users.models import TechnicianProfile
from workorders.models import WorkOrder
from .constants import BIG_M, PRIORITY_MULTIPLIERS
from .guardrails import (
    filter_task_dependencies,
    decompose_crew_slots,
    sort_technicians_tie_breaker,
    detect_shared_tool_conflicts,
    WorkOrderSlot
)
from .cost_matrix import evaluate_pair_cost
from .solver import solve_kuhn_munkres


def get_user_display_name(user) -> str:
    if not user:
        return ""
    if hasattr(user, 'get_full_name') and callable(user.get_full_name):
        name = user.get_full_name()
        if name:
            return name
    return getattr(user, 'username', str(user))


class HungarianAssignmentService:
    """
    Main Orchestration Service for Linear Sum Assignment Problem (LSAP)
    in Enterprise Asset Management.
    """

    @classmethod
    def preview(cls, tenant, work_order_ids: Optional[List[str]] = None, current_time=None) -> Dict[str, Any]:
        """
        Calculates optimal assignment plan and returns explainable cost matrix,
        breakdown tooltips, and shared tool bottleneck warnings.
        """
        now = current_time or timezone.now()

        # Step 1: Query Work Orders
        wo_qs = WorkOrder.objects.filter(tenant=tenant)
        if work_order_ids:
            wo_qs = wo_qs.filter(id__in=work_order_ids)
        else:
            wo_qs = wo_qs.filter(status='CREATED')

        all_work_orders = list(wo_qs.select_related('asset', 'depends_on_wo').order_by('created_at'))

        # Step 2: Rule 4 - Task Dependency Filtering
        eligible_wos, blocked_wos = filter_task_dependencies(all_work_orders)

        # Step 3: Rule 6 - Crew Task Slot Decomposition
        all_slots: List[WorkOrderSlot] = decompose_crew_slots(eligible_wos)

        # Step 4: Query Available Technicians (Rules 8 & 10 - Filtered strictly by 'work_order:execute' permission)
        from users.models import TechnicianSchedule
        from datetime import timedelta
        from django.db.models import Q
        tech_qs = TechnicianProfile.objects.filter(
            tenant=tenant,
            is_on_duty=True,
            availability_status='AVAILABLE',
            user__status='ACTIVE',
        ).filter(
            Q(user__roles__permissions__id='work_order:execute') | Q(user__roles__isnull=True)
        ).distinct().select_related('user')

        # Rule 8: Exclude technicians scheduled as OFF or LEAVE for today
        try:
            off_tech_ids = set(TechnicianSchedule.objects.filter(
                tenant=tenant,
                work_date=now.date(),
                status__in=['OFF', 'LEAVE']
            ).values_list('user_id', flat=True))
            if off_tech_ids:
                tech_qs = tech_qs.exclude(user_id__in=off_tech_ids)
        except Exception:
            pass

        sorted_techs = sort_technicians_tie_breaker(tech_qs)

        # Rule 8: Update effective shift_end_time from today's schedule if available (overnight support)
        try:
            today_schedules = {
                ts.user_id: ts for ts in TechnicianSchedule.objects.filter(
                    tenant=tenant,
                    work_date=now.date(),
                    status='ON_DUTY',
                    shift_template__isnull=False
                ).select_related('shift_template')
            }
            for t in sorted_techs:
                if t.user_id in today_schedules:
                    sched = today_schedules[t.user_id]
                    sh_tmpl = sched.shift_template
                    end_t = sh_tmpl.end_time
                    end_dt = now.replace(hour=end_t.hour, minute=end_t.minute, second=end_t.second, microsecond=0)
                    if sh_tmpl.is_overnight or end_dt < now:
                        end_dt += timedelta(days=1)
                    t.shift_end_time = end_dt
                    # Shift duty zone: override technician base zone with today's scheduled duty zone
                    if getattr(sched, 'duty_zone_id', None):
                        t.zone_id = sched.duty_zone_id
        except Exception:
            pass

        # Early return if no technicians or no slots
        if not sorted_techs or not all_slots:
            return {
                "totalOptimalCost": 0.0,
                "assignmentsCount": 0,
                "unassignedCount": len(all_slots),
                "assignments": [],
                "unassignedSlots": [
                    {"workOrderId": s.original_id, "title": s.title, "role": s.slot_role}
                    for s in all_slots
                ],
                "blockedWorkOrders": blocked_wos,
                "sharedToolConflicts": [],
                "matrixHeader": {
                    "technicians": [get_user_display_name(t.user) for t in sorted_techs],
                    "workOrders": [s.display_name for s in all_slots] + [f"{b['workOrderTitle']} (Blocked)" for b in blocked_wos]
                },
                "costMatrix": []
            }

        # Step 5: Gather Active Workloads & In-progress Status for Technicians
        tech_user_ids = [t.user_id for t in sorted_techs]
        active_wos = WorkOrder.objects.filter(
            tenant=tenant,
            assigned_to_id__in=tech_user_ids,
            status__in=['ASSIGNED', 'IN_PROGRESS']
        ).values('assigned_to_id', 'status', 'coords_x', 'coords_y', 'floor_level', 'zone_id')

        workload_counts = {uid: 0 for uid in tech_user_ids}
        has_in_progress = {uid: False for uid in tech_user_ids}
        active_job_locations = {}

        for awo in active_wos:
            uid = awo['assigned_to_id']
            workload_counts[uid] = workload_counts.get(uid, 0) + 1
            if awo['status'] == 'IN_PROGRESS':
                has_in_progress[uid] = True
                # Real-world dynamic location anchoring: If tech is actively executing a task,
                # their physical position right now is that asset's location (no continuous GPS required).
                if awo.get('coords_x') is not None or awo.get('zone_id'):
                    active_job_locations[uid] = {
                        'coords_x': awo.get('coords_x'),
                        'coords_y': awo.get('coords_y'),
                        'floor_level': awo.get('floor_level'),
                        'zone_id': awo.get('zone_id')
                    }

        # Step 6: Handle Surplus Work Orders (M > N) - Rule 7
        priority_rank = {'URGENT': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
        active_slots = list(all_slots)
        overflow_unassigned_slots = []

        if len(active_slots) > len(sorted_techs):
            from datetime import datetime, timezone as dt_timezone
            max_dt = datetime.max.replace(tzinfo=dt_timezone.utc)
            # Sort slots by urgency and due date
            active_slots.sort(key=lambda s: (
                priority_rank.get(s.priority, 9),
                s.due_date or max_dt
            ))
            # Take top N slots for immediate dispatch; remainder stay in backlog
            n_techs = len(sorted_techs)
            overflow_unassigned_slots = active_slots[n_techs:]
            active_slots = active_slots[:n_techs]

        # Step 7: Build Multi-Factor Cost Matrix
        from .cost_matrix import build_tenant_competency_catalog
        competency_catalog = build_tenant_competency_catalog(tenant)

        n = len(sorted_techs)
        m = len(active_slots)
        raw_matrix = []
        breakdown_matrix = []
        explanation_matrix = []

        for i, tech in enumerate(sorted_techs):
            row_costs = []
            row_breakdowns = []
            row_explanations = []
            uid = tech.user_id
            wl = workload_counts.get(uid, 0)
            in_prog = has_in_progress.get(uid, False)
            active_loc = active_job_locations.get(uid)

            # Hierarchical Location Resolution:
            # 1. If currently IN_PROGRESS at a machine, dispatch origin dynamically anchors to that machine.
            # 2. If IDLE, dispatch origin anchors to technician's assigned base duty station / workshop.
            effective_tech = tech
            if active_loc:
                class EffectiveTechProxy:
                    def __init__(self, base, loc):
                        self._base = base
                        self.user = base.user
                        self.user_id = base.user_id
                        self.tenant = base.tenant
                        self.skills = base.skills
                        self.skill_level = base.skill_level
                        self.certifications = base.certifications
                        self.shift_end_time = base.shift_end_time
                        self.monthly_accumulated_hours = base.monthly_accumulated_hours
                        self.coords_x = loc['coords_x'] if loc.get('coords_x') is not None else base.coords_x
                        self.coords_y = loc['coords_y'] if loc.get('coords_y') is not None else base.coords_y
                        self.floor_level = loc['floor_level'] if loc.get('floor_level') is not None else base.floor_level
                        self.zone_id = loc['zone_id'] if loc.get('zone_id') else base.zone_id

                    def __getattr__(self, name):
                        return getattr(self._base, name)

                effective_tech = EffectiveTechProxy(tech, active_loc)

            for j, slot in enumerate(active_slots):
                cost, bdown, expl = evaluate_pair_cost(
                    tech_profile=effective_tech,
                    wo_slot=slot,
                    active_workload=wl,
                    has_in_progress=in_prog,
                    current_time=now,
                    catalog=competency_catalog
                )
                # Rule 10: Deterministic tie-breaker epsilon based on monthly_accumulated_hours
                # sorted_techs is ordered by monthly_accumulated_hours ascending.
                # A micro epsilon breaks exact cost ties in favor of lower accumulated hours.
                tie_break_epsilon = float(i) * 0.0001
                effective_cost = round(cost + tie_break_epsilon, 4)
                row_costs.append(effective_cost)
                row_breakdowns.append(bdown)
                row_explanations.append(expl)

            raw_matrix.append(row_costs)
            breakdown_matrix.append(row_breakdowns)
            explanation_matrix.append(row_explanations)

        # Step 8: Solve via Kuhn-Munkres
        valid_pairs, total_optimal_cost, padded_matrix = solve_kuhn_munkres(
            raw_cost_matrix=raw_matrix,
            num_real_techs=n,
            num_real_slots=m
        )

        # Step 9: Assemble Result Assignments
        assignments = []
        assigned_slot_objects = []
        assigned_slot_indices = set()

        for r_idx, c_idx in valid_pairs:
            tech = sorted_techs[r_idx]
            slot = active_slots[c_idx]
            cost_val = raw_matrix[r_idx][c_idx]
            bdown = breakdown_matrix[r_idx][c_idx]
            expl = explanation_matrix[r_idx][c_idx]

            is_safety_violation = (cost_val >= (BIG_M / 2.0))

            assignment_item = {
                "technicianId": str(tech.user_id),
                "technicianName": get_user_display_name(tech.user),
                "workOrderId": slot.original_id,
                "workOrderCode": slot.display_code,
                "workOrderTitle": slot.title,
                "slotRole": slot.slot_role,
                "priority": slot.priority,
                "cost": cost_val,
                "isSafetyViolation": is_safety_violation,
                "breakdown": bdown,
                "explanation": expl
            }
            assignments.append(assignment_item)
            assigned_slot_indices.add(c_idx)
            assigned_slot_objects.append((tech, slot))

        # Identify any unassigned slots
        unassigned_slots_list = [
            {"workOrderId": active_slots[j].original_id, "title": active_slots[j].title, "role": active_slots[j].slot_role}
            for j in range(m) if j not in assigned_slot_indices
        ]
        unassigned_slots_list.extend([
            {"workOrderId": s.original_id, "title": s.title, "role": s.slot_role}
            for s in overflow_unassigned_slots
        ])

        # Step 10: Rule 5 - Shared Tool Bottleneck Detection
        shared_tool_conflicts = detect_shared_tool_conflicts(assigned_slot_objects, tenant=tenant)

        # Step 11: Format Response
        matrix_header = {
            "technicians": [get_user_display_name(t.user) for t in sorted_techs],
            "workOrders": [s.display_name for s in active_slots] + [f"{b['workOrderTitle']} (Blocked)" for b in blocked_wos]
        }

        available_techs = [
            {
                "id": str(t.user_id),
                "name": get_user_display_name(t.user),
                "username": t.user.username,
                "skillLevel": t.skill_level,
                "skills": t.skills or [],
                "zoneId": t.zone_id or ""
            }
            for t in sorted_techs
        ]

        return {
            "totalOptimalCost": total_optimal_cost,
            "assignmentsCount": len(assignments),
            "unassignedCount": len(unassigned_slots_list),
            "assignments": assignments,
            "unassignedSlots": unassigned_slots_list,
            "blockedWorkOrders": blocked_wos,
            "sharedToolConflicts": shared_tool_conflicts,
            "availableTechnicians": available_techs,
            "matrixHeader": matrix_header,
            "costMatrix": raw_matrix
        }

    @classmethod
    @transaction.atomic
    def apply(cls, tenant, assignments_data: List[Dict[str, Any]], current_user=None) -> Dict[str, Any]:
        """
        Applies validated optimal assignments to the database.
        Implements Rule 10 (concurrency locking via select_for_update)
        and dispatches assignment notifications.
        """
        from notifications.services import notify_work_order_assigned
        from django.core.exceptions import ValidationError

        wo_ids = [str(item['workOrderId']) for item in assignments_data]
        tech_ids = [str(item['technicianId']) for item in assignments_data]

        # Concurrency Lock (Rule 10): select_for_update
        wo_qs = WorkOrder.objects.select_for_update()
        if tenant is not None:
            wo_qs = wo_qs.filter(tenant=tenant)
        wos = {str(wo.id): wo for wo in wo_qs.filter(id__in=wo_ids)}

        tech_qs = TechnicianProfile.objects.select_for_update().select_related('user')
        if tenant is not None:
            tech_qs = tech_qs.filter(tenant=tenant)
        techs = {str(t.user_id): t for t in tech_qs.filter(user_id__in=tech_ids)}

        # Validate existence & lock status
        for item in assignments_data:
            wo_id_str = str(item['workOrderId'])
            tech_id_str = str(item['technicianId'])

            if wo_id_str not in wos:
                raise ValidationError(f"Phiếu công việc {wo_id_str} không tồn tại hoặc không thuộc tổ chức hiện tại.")
            if tech_id_str not in techs:
                raise ValidationError(f"Kỹ thuật viên {tech_id_str} không tồn tại hoặc không thuộc tổ chức hiện tại.")

            wo = wos[wo_id_str]
            tech = techs[tech_id_str]

            if wo.status != 'CREATED':
                raise ConcurrencyConflictError(
                    f"Phiếu công việc {wo.code} đã được phân công hoặc chuyển trạng thái ({wo.status}) bởi điều phối viên khác."
                )
            if tech.availability_status != 'AVAILABLE' or not tech.is_on_duty:
                raise ConcurrencyConflictError(
                    f"Kỹ thuật viên {get_user_display_name(tech.user)} hiện không khả dụng (Trạng thái: {tech.availability_status}, Trực: {tech.is_on_duty})."
                )

        # Apply assignments
        now = timezone.now()
        applied_list = []

        for item in assignments_data:
            wo_id_str = str(item['workOrderId'])
            tech_id_str = str(item['technicianId'])
            role = item.get('slotRole', 'SOLO')

            wo = wos[wo_id_str]
            tech = techs[tech_id_str]

            if role == 'ASSIST' and wo.assigned_to:
                # Add crew assist info to notes
                wo.notes = f"{wo.notes or ''}\n[Crew Assist]: {get_user_display_name(tech.user)}".strip()
            else:
                wo.assigned_to = tech.user
            
            wo.assigned_at = now
            wo.status = 'ASSIGNED'
            wo.save()

            # Mark technician as BUSY
            tech.availability_status = 'BUSY'
            tech.save()

            # Tool Reservation Concurrency Handling
            try:
                from assets.models import Tool, ToolReservation, ToolInstance
                if wo.required_tools and isinstance(wo.required_tools, list):
                    for tool_item in wo.required_tools:
                        if isinstance(tool_item, dict):
                            t_code = tool_item.get('code')
                            req_qty = int(tool_item.get('quantity', 1))
                        else:
                            t_code = str(tool_item)
                            req_qty = 1

                        tool_obj = Tool.objects.select_for_update().filter(tenant=tenant, code=t_code, is_active=True).first()
                        if tool_obj:
                            inst = ToolInstance.objects.filter(tool=tool_obj, tenant=tenant, status='AVAILABLE').first()
                            ToolReservation.objects.create(
                                tenant=tenant,
                                tool=tool_obj,
                                tool_instance=inst,
                                work_order=wo,
                                reserved_quantity=req_qty,
                                status='RESERVED'
                            )
                            if tool_obj.available_quantity >= req_qty:
                                tool_obj.available_quantity -= req_qty
                                tool_obj.save()
                            if inst:
                                inst.status = 'IN_USE'
                                inst.save()
            except Exception:
                pass

            # Dispatch notification
            try:
                notify_work_order_assigned(wo, assignee=tech.user, is_reassigned=False, sender=current_user)
            except Exception:
                pass  # Do not block transactional dispatch on non-critical notification failures

            applied_list.append({
                "workOrderId": str(wo.id),
                "workOrderCode": wo.code,
                "technicianId": str(tech.user_id),
                "technicianName": get_user_display_name(tech.user),
                "slotRole": role,
                "status": wo.status
            })

        return {
            "appliedCount": len(applied_list),
            "assignments": applied_list
        }


class ConcurrencyConflictError(Exception):
    """Raised when a concurrent dispatch or state conflict occurs."""
    pass


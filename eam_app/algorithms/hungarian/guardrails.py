"""
Guardrails and Pre/Post-processing Engines for Task 11.1 Hungarian Assignment
"""
from collections import defaultdict
from typing import List, Dict, Tuple, Any


class WorkOrderSlot:
    """
    Represents an assignable task slot in the cost matrix.
    Supports decomposition of Crew Tasks (Rule 6) into Lead and Assistant slots.
    """
    def __init__(self, work_order, slot_role='SOLO', min_skill_level=None):
        self.work_order = work_order
        self.slot_role = slot_role  # 'SOLO', 'LEAD', 'ASSISTANT'
        self.original_id = str(work_order.id)
        self.slot_key = f"{work_order.id}-{slot_role}"
        self.title = work_order.title
        self.display_code = getattr(work_order, 'source_reference', None) or f"WO-{str(work_order.id)[:8].upper()}"
        if slot_role != 'SOLO':
            self.display_name = f"{self.display_code} ({slot_role.capitalize()})"
        else:
            self.display_name = self.display_code

        self.required_skill = work_order.required_skill
        self.min_skill_level = min_skill_level if min_skill_level is not None else (work_order.min_skill_level or 1)
        self.required_certification = work_order.required_certification
        self.required_tools = work_order.required_tools or []
        self.priority = work_order.priority or 'MEDIUM'
        self.estimated_duration_hours = work_order.estimated_duration_hours
        self.coords_x = work_order.coords_x
        self.coords_y = work_order.coords_y
        self.floor_level = work_order.floor_level or 1
        self.zone_id = work_order.zone_id or ''
        self.due_date = work_order.due_date


def filter_task_dependencies(work_orders) -> Tuple[List[Any], List[Dict[str, Any]]]:
    """
    Rule 4: Task Dependency Filtering Guardrail
    If prerequisite task (depends_on_wo) is not 'COMPLETED', exclude work order from matrix.
    Returns: (eligible_work_orders, blocked_work_orders_info)
    """
    eligible = []
    blocked = []

    for wo in work_orders:
        dep = getattr(wo, 'depends_on_wo', None)
        if dep and getattr(dep, 'status', 'COMPLETED') != 'COMPLETED':
            wo_code = getattr(wo, 'source_reference', None) or f"WO-{str(wo.id)[:8].upper()}"
            dep_code = getattr(dep, 'source_reference', None) or f"WO-{str(dep.id)[:8].upper()}"
            blocked.append({
                "workOrderId": str(wo.id),
                "workOrderCode": wo_code,
                "workOrderTitle": wo.title,
                "blockingWorkOrderCode": dep_code,
                "prerequisiteId": str(dep.id),
                "prerequisiteTitle": dep.title,
                "prerequisiteStatus": dep.status,
                "reason": f"Phụ thuộc vào phiếu [{dep_code}] '{dep.title}' đang ở trạng thái {dep.status} (chưa hoàn thành)."
            })
        else:
            eligible.append(wo)

    return eligible, blocked


def decompose_crew_slots(work_orders) -> List[WorkOrderSlot]:
    """
    Rule 6: Multi-Technician Crew Slot Decomposition
    If is_crew_task == True:
      - Slot Lead: min_skill_level = max(4, wo.min_skill_level)
      - Slot Assistant: min_skill_level = max(2, wo.min_skill_level - 1)
    Else:
      - Slot Solo
    """
    slots = []
    for wo in work_orders:
        if getattr(wo, 'is_crew_task', False):
            # Lead Slot (Requires High Level >= 4)
            lead_level = max(4, wo.min_skill_level or 1)
            slots.append(WorkOrderSlot(wo, slot_role='LEAD', min_skill_level=lead_level))

            # Assist Slot (Requires Supporting Level >= 2)
            asst_level = max(2, min(wo.min_skill_level or 2, 2))
            slots.append(WorkOrderSlot(wo, slot_role='ASSIST', min_skill_level=asst_level))
        else:
            slots.append(WorkOrderSlot(wo, slot_role='SOLO'))
    return slots


def sort_technicians_tie_breaker(technicians_qs) -> List[Any]:
    """
    Rule 10: Deterministic Tie-Breaking
    Orders technicians by monthly_accumulated_hours ascending so that in case of identical costs,
    the technician with fewer hours in the month gets row priority in Hungarian solver.
    """
    return list(technicians_qs.order_by('monthly_accumulated_hours', 'created_at', 'id'))


def detect_shared_tool_conflicts(assigned_slots: List[Tuple[Any, WorkOrderSlot]], tenant) -> List[Dict[str, Any]]:
    """
    Rule 5: Shared Tool Bottleneck Detection Guardrail
    Checks if multiple work orders dispatched simultaneously demand more units of a tool
    than currently available in warehouse inventory.
    """
    from assets.models import Tool

    tool_to_wos = defaultdict(list)
    tool_to_techs = defaultdict(list)
    for tech_profile, slot in assigned_slots:
        if not slot or not slot.required_tools:
            continue
        tech_user = getattr(tech_profile, 'user', None)
        tech_name = getattr(tech_user, 'full_name', '') or getattr(tech_user, 'username', 'KTV') if tech_user else 'KTV'
        for tool_code in slot.required_tools:
            tool_to_wos[tool_code].append(slot.display_name)
            tool_to_techs[tool_code].append(tech_name)

    conflicts = []
    for tool_code, wo_names in tool_to_wos.items():
        if len(wo_names) > 1:
            tool = Tool.objects.filter(tenant=tenant, code=tool_code, is_active=True).first()
            avail_qty = tool.available_quantity if tool else 1
            if avail_qty < len(wo_names):
                tool_name = tool.name if tool else tool_code
                tech_names = tool_to_techs[tool_code]
                conflicts.append({
                    "toolCode": tool_code,
                    "tool_code": tool_code,
                    "toolName": tool_name,
                    "tool_name": tool_name,
                    "availableQuantity": avail_qty,
                    "total_available": avail_qty,
                    "requiredQuantity": len(wo_names),
                    "required_count": len(wo_names),
                    "conflictingWorkOrders": wo_names,
                    "assigned_technicians": tech_names,
                    "assignedTechnicians": tech_names,
                    "warningMessage": (
                        f"Xung đột công cụ '{tool_name}' ({tool_code}): "
                        f"Có {len(wo_names)} phiếu yêu cầu đồng thời nhưng chỉ có {avail_qty} chiếc khả dụng. "
                        f"Đề xuất Quản lý lùi giờ hoặc điều phối thủ công."
                    )
                })

    return conflicts

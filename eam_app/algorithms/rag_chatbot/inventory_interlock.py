"""
Live Inventory & Tool Availability Interlock (Rule 7, TC-RAG-07).
Scans response/chunk texts for referenced spare parts and tools,
queries the warehouse inventory in real-time without modifying or deducting stock.
"""

from typing import List, Dict, Any, Optional
import re


def check_live_inventory(text: str, tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Scans the given text for part numbers or names in the SparePart database.
    Returns real-time stock levels and shelf locations.
    GUARANTEE: Purely read-only; absolutely NO stock deduction.
    """
    if not text or not isinstance(text, str):
        return []

    from assets.models import SparePart
    
    # Base queryset isolated by tenant
    qs = SparePart.objects.select_related('location').all()
    if tenant_id:
        qs = qs.filter(tenant_id=tenant_id)

    # Fetch spare parts to check
    spare_parts = list(qs)

    matched_items: List[Dict[str, Any]] = []
    seen_ids = set()

    lower_text = text.lower()

    for part in spare_parts:
        matched = False
        # Match part number if present
        if part.part_number and len(part.part_number.strip()) >= 3:
            pn_clean = part.part_number.strip().lower()
            if pn_clean in lower_text:
                matched = True
        
        # Match name if specific
        if not matched and part.name and len(part.name.strip()) >= 5:
            name_clean = part.name.strip().lower()
            if name_clean in lower_text:
                matched = True

        if matched and str(part.id) not in seen_ids:
            seen_ids.add(str(part.id))
            loc_str = part.location.name if part.location else "Chưa chỉ định kệ"
            matched_items.append({
                'partNumber': part.part_number or '',
                'name': part.name,
                'inStock': float(part.quantity_in_stock),
                'location': loc_str,
                'minStockLevel': float(part.min_stock_level) if hasattr(part, 'min_stock_level') else 1.0,
                'unitCost': float(part.unit_cost) if part.unit_cost else 0.0,
                'isTool': False,
            })

    # 2. Check Tool availability and inspection/calibration status independently of spare parts
    try:
        from django.utils import timezone
        from assets.models import Tool
        tool_qs = Tool.objects.select_related('location').prefetch_related('instances').filter(is_active=True)
        if tenant_id:
            tool_qs = tool_qs.filter(tenant_id=tenant_id)
        
        today = timezone.now().date()

        for tool in tool_qs:
            tool_matched = False
            if tool.code and len(tool.code.strip()) >= 3 and tool.code.strip().lower() in lower_text:
                tool_matched = True
            elif tool.name and len(tool.name.strip()) >= 4 and tool.name.strip().lower() in lower_text:
                tool_matched = True

            if tool_matched and str(tool.id) not in seen_ids:
                seen_ids.add(str(tool.id))
                instances = list(tool.instances.all())
                
                if not instances:
                    status_label = "NO_CALIBRATION_DATA"
                else:
                    has_expired = False
                    has_due_soon = False
                    calibrated_count = 0

                    for inst in instances:
                        is_valid = getattr(inst, 'is_calibration_valid', True)
                        due_date = getattr(inst, 'calibration_due_date', None)
                        cal_date = getattr(inst, 'calibration_date', None)
                        inst_status = getattr(inst, 'inspection_status', 'PASSED')

                        # An instance only has calibration data if a calibration date or due date is recorded
                        has_cal_data = (due_date is not None) or (cal_date is not None)
                        if has_cal_data:
                            calibrated_count += 1

                        if not is_valid or inst_status == 'EXPIRED' or (due_date and due_date < today):
                            has_expired = True
                        elif inst_status == 'DUE_SOON' or (due_date and 0 <= (due_date - today).days <= 30):
                            has_due_soon = True

                    if has_expired:
                        status_label = "EXPIRED"
                    elif has_due_soon:
                        status_label = "DUE_SOON"
                    elif calibrated_count == 0 or calibrated_count < len(instances):
                        # Missing or incomplete calibration data across tool instances
                        status_label = "NO_CALIBRATION_DATA"
                    else:
                        status_label = "PASSED"
                
                tool_loc = tool.location.name if tool.location else "Chưa chỉ định vị trí"
                matched_items.append({
                    'partNumber': tool.code,
                    'name': f"[Dụng cụ] {tool.name}",
                    'inStock': float(tool.available_quantity),
                    'location': tool_loc,
                    'minStockLevel': 1.0,
                    'unitCost': 0.0,
                    'isTool': True,
                    'inspectionStatus': status_label,
                })
    except Exception:
        pass

    return matched_items

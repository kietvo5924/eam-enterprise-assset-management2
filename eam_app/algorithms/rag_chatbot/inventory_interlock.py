"""
Live Inventory & Tool Availability Interlock (Rule 7, TC-RAG-07).
Scans response/chunk texts for referenced spare parts and tools,
queries the warehouse inventory in real-time without modifying or deducting stock.
"""

import logging
import re
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


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
                    has_missing_cal = False
                    all_maintenance = True

                    for inst in instances:
                        inst_status = getattr(inst, 'inspection_status', 'PASSED')
                        inst_maint = getattr(inst, 'status', 'AVAILABLE')
                        due_date = getattr(inst, 'calibration_due_date', None)
                        cal_date = getattr(inst, 'calibration_date', None)

                        if inst_maint != 'MAINTENANCE':
                            all_maintenance = False

                        # 1. Overdue or explicit EXPIRED status -> EXPIRED
                        if (due_date and due_date < today) or inst_status == 'EXPIRED':
                            has_expired = True
                        # 2. Missing due_date or missing calibration_date -> Incomplete calibration data
                        elif cal_date is None or due_date is None:
                            has_missing_cal = True
                        # 3. Due soon within 30 days
                        elif inst_status == 'DUE_SOON' or (due_date and 0 <= (due_date - today).days <= 30):
                            has_due_soon = True

                    if has_expired:
                        status_label = "EXPIRED"
                    elif has_missing_cal:
                        status_label = "NO_CALIBRATION_DATA"
                    elif has_due_soon:
                        status_label = "DUE_SOON"
                    elif all_maintenance:
                        status_label = "MAINTENANCE"
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
    except Exception as e:
        logger.error("Failed to query tool inventory / calibration data: %s", str(e), exc_info=True)
        # Indicate unverified tool inspection state if query text references measurement tools,
        # ensuring the system does not silently swallow tool inspection errors nor produce false expired warnings
        tool_keywords = ['dụng cụ', 'tool', 'đo', 'kiểm định', 'hiệu chuẩn', 'panme', 'thước', 'đồng hồ áp']
        if any(tk in lower_text for tk in tool_keywords):
            matched_items.append({
                'partNumber': 'TOOL_INSPECTION_UNAVAILABLE',
                'name': '[Cảnh báo hệ thống] Không thể xác minh kiểm định dụng cụ đo (Lỗi truy vấn)',
                'inStock': 0.0,
                'location': 'Hệ thống gián đoạn kết nối',
                'minStockLevel': 1.0,
                'unitCost': 0.0,
                'isTool': True,
                'inspectionStatus': 'UNVERIFIED',
            })

    return matched_items

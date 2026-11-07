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
    if not spare_parts:
        return []

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
            loc_str = part.location.name if part.location else "Kệ A1-01"
            matched_items.append({
                'partNumber': part.part_number or '',
                'name': part.name,
                'inStock': float(part.quantity_in_stock),
                'location': loc_str,
                'minStockLevel': float(part.min_stock_level) if hasattr(part, 'min_stock_level') else 1.0,
                'unitCost': float(part.unit_cost) if part.unit_cost else 0.0,
            })

    return matched_items

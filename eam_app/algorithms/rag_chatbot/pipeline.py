"""
Comprehensive RAG Chatbot Pipeline Orchestrator (Rules 1-10, Specs Section 4.1).
Integrates:
1. Context-aware life-safety classifier (stops RAG on real emergencies)
2. Slang & onomatopoeia query expansion
3. Dual-stream PGVector retrieval (Parent-Child, tenant-isolated equipment vs global software guide)
4. Similarity threshold tiers (<0.65 fallback, 0.65-0.75 amber warning, >=0.75 confident)
5. Contradiction guard (preserves safety prohibitions)
6. Real-time live inventory interlock (read-only, no deduction)
7. Actionable Chat-to-WorkOrder draft generation (status='CREATED', draft only)
"""

import logging
from typing import Dict, Any, Optional, List
from .constants import (
    SAFE_FALLBACK_MESSAGE,
    SIMILARITY_THRESHOLD_FALLBACK,
)
from .safety_classifier import classify_safety_context
from .query_expansion import expand_slang_query
from .vector_engine import retrieve_relevant_chunks, classify_similarity_tier
from .contradiction_guard import check_negation_contradiction
from .inventory_interlock import check_live_inventory
from .ollama_client import OllamaClient

logger = logging.getLogger(__name__)

SYSTEM_GUIDE_KEYWORDS = [
    'nút', 'button', 'giao việc', 'bắt đầu sửa chữa', 'tạo phiếu', 
    'vòng đời', 'hướng dẫn sử dụng phần mềm', 'tính năng phần mềm', 
    'menu', 'xuất excel', 'báo cáo kpi', 'quy trình hệ thống',
    'eam', 'cách dùng phần mềm', 'chức năng phần mềm', 'trang tổng quan', 'dashboard',
    'sơ đồ mặt bằng', 'floorplan', 'hướng dẫn hệ thống', 'cây tài sản', 'phiếu bảo trì',
    'kho vật tư', 'kho phụ tùng', 'nhân lực', 'công cụ', 'kế hoạch pm', 'bảo trì định kỳ'
]


STRONG_SOFTWARE_INDICATORS = [
    # Pages & Modules
    'trang tổng quan', 'tổng quan', 'dashboard', 'sơ đồ mặt bằng', 'floorplan',
    'trang cây tài sản', 'cây tài sản', 'cây thiết bị', 'danh mục tài sản', 'quản lý tài sản',
    'trang phiếu bảo trì', 'phiếu bảo trì', 'phiếu sửa chữa', 'phiếu wo', 'vòng đời phiếu',
    'nhân lực & công cụ', 'nhân lực và công cụ', 'nhân lực', 'công cụ', 'ca trực', 'hiệu chuẩn',
    'kế hoạch pm', 'bảo trì định kỳ', 'pm plan',
    'kho vật tư', 'kho phụ tùng', 'tồn kho', 'min-stock',
    'trang báo cáo', 'báo cáo kpi', 'oee', 'mtbf', 'mttr', 'xuất excel', 'xuất pdf',
    'dự báo chi phí', 'chi phí lcc',
    'cấu hình tài sản',
    'cài đặt', 'cấu hình đơn vị',
    'tri thức ai', 'trợ lý ai', 'hàng đợi thẩm định', 'tri thức vàng',
    'nhật ký hệ thống', 'audit logs',
    'người dùng', 'quản lý người dùng',
    'phân quyền', 'vai trò', 'quản lý vai trò',
    'đơn vị', 'tenant',
    # General UI / Software indicators
    'trang web có gì', 'hệ thống có gì', 'phần mềm có gì',
    'nút trên trang', 'nút này', 'nút', 'button', 'giao việc', 'bắt đầu sửa chữa', 
    'phần mềm eam', 'hệ thống eam', 
    'tính năng phần mềm', 'cách dùng phần mềm', 'cách sử dụng phần mềm', 'menu',
    'chức năng hệ thống', 'chức năng phần mềm'
]


def is_system_feature_query(prompt: str, asset_context: Optional[Dict[str, Any]] = None) -> bool:
    """Detects if query is asking about EAM software usage rather than machine repairs."""
    lower = prompt.lower().strip()
    
    # 1. Any direct inquiry about portal pages ("trang ...", "màn hình ...", "giao diện ...")
    if lower.startswith('trang ') or ' trang ' in lower or lower.startswith('màn hình ') or ' màn hình ' in lower:
        return True
        
    # 2. Check strong indicators
    if any(k in lower for k in STRONG_SOFTWARE_INDICATORS):
        # Exclude physical machine troubleshooting like "áp suất tụt", "xì nhớt", "bị hỏng"
        machine_fault_terms = ['xì nhớt', 'xì dầu', 'rò rỉ', 'áp suất tụt', 'áp suất giảm', 'quá nhiệt', 'kêu cọc cọc', 'nóng máy', 'rung lắc', 'hỏng bạc đạn']
        if any(term in lower for term in machine_fault_terms):
            return False
        return True
        
    if asset_context and asset_context.get('model'):
        return False
        
    return any(k in lower for k in SYSTEM_GUIDE_KEYWORDS)


def process_rag_query(
    prompt: str,
    asset_context: Optional[Dict[str, Any]] = None,
    tenant_id: Optional[str] = None,
    stream: bool = False
) -> Dict[str, Any]:
    """
    Main entry point for processing an AI assistant technical query.
    """
    # Step 1: Life-Safety Classification (Rule 1, Rule 6)
    safety_result = classify_safety_context(prompt)
    if safety_result['is_emergency']:
        return {
            "success": True,
            "data": {
                "isEmergency": True,
                "hazardType": safety_result['hazard_type'],
                "emergencyName": safety_result['emergency_name'],
                "actionSummary": safety_result['action_summary'],
                "reply": safety_result['instruction'],
                "semanticRelevance": {
                    "score": 1.0,
                    "tier": "EMERGENCY_OVERRIDE",
                    "tierLabel": "Kích hoạt giao thức an toàn sinh mạng khẩn cấp"
                },
                "diagramAnchors": [],
                "inventoryAvailability": [],
                "actionableWorkOrderDraft": None,
                "citedSources": []
            }
        }

    # Step 2: Query Expansion (Rule 2)
    expansion_res = expand_slang_query(prompt, asset_context)
    expanded_query = expansion_res['expanded_query']

    # Step 3: Determine query branch
    is_sys_guide = is_system_feature_query(prompt, asset_context)

    asset_model = None
    manufacture_year = None
    if asset_context and not is_sys_guide:
        asset_model = asset_context.get('model') or asset_context.get('applicable_model')
        manufacture_year = asset_context.get('manufactureYear') or asset_context.get('manufacture_year')

    # Step 4: Multi-source PGVector Retrieval (Rule 4, Rule 5)
    retrieved_chunks = retrieve_relevant_chunks(
        query_text=expanded_query,
        tenant_id=tenant_id,
        asset_model=asset_model,
        manufacture_year=manufacture_year,
        is_system_query=is_sys_guide,
        limit=4
    )

    # Step 5: Similarity Tier Classification (Rule 10, TC-RAG-12)
    top_score = retrieved_chunks[0]['similarity'] if retrieved_chunks else 0.0
    tier_info = classify_similarity_tier(top_score)

    # Safe Fallback when score < 0.65
    if tier_info['isFallback'] or not retrieved_chunks:
        return {
            "success": True,
            "data": {
                "expandedQuery": expanded_query,
                "reply": SAFE_FALLBACK_MESSAGE,
                "isFallback": True,
                "isSystemGuide": is_sys_guide,
                "semanticRelevance": {
                    "score": tier_info['score'],
                    "tier": tier_info['tier'],
                    "tierLabel": tier_info['tierLabel']
                },
                "diagramAnchors": [],
                "inventoryAvailability": [],
                "actionableWorkOrderDraft": None,
                "citedSources": []
            }
        }

    # Step 6: Parent-Child Context Assembly & Diagram Anchors
    parent_sections = []
    all_diagram_anchors = []
    cited_sources = []
    seen_parent = set()

    oem_texts = []
    tacit_texts = []
    system_texts = []

    for chunk in retrieved_chunks:
        p_content = chunk['parent_content']
        if p_content not in seen_parent:
            seen_parent.add(p_content)
            parent_sections.append(p_content)

            # Categorize text stream
            src_type = chunk['source_type']
            if src_type == 'TACIT_WORK_ORDER':
                prov = chunk.get('provenance_wo_code') or 'Lịch sử xưởng'
                tacit_texts.append(f"Mẹo từ {prov}: {chunk['content']}")
            elif chunk.get('is_system_guide') or src_type == 'SYSTEM_GUIDE':
                system_texts.append(p_content)
            else:
                oem_texts.append(p_content)

        for anchor in chunk.get('image_anchors', []):
            if anchor not in all_diagram_anchors:
                all_diagram_anchors.append(anchor)

        page_num = chunk.get('page_number')
        if not page_num and chunk.get('image_anchors'):
            page_num = chunk['image_anchors'][0].get('pageNumber')
        if not page_num:
            page_num = 1

        cited_sources.append({
            "documentName": chunk.get('document_title', 'Tài liệu kỹ thuật'),
            "pageNumber": page_num,
            "similarityScore": round(chunk['similarity'], 3)
        })

    full_context = "\n\n".join(parent_sections)

    # Step 7: Live Inventory Interlock (Rule 7)
    inventory_items = check_live_inventory(full_context + " " + prompt, tenant_id=tenant_id)

    # Step 8: Build Prompt & Synthesize Response
    system_prompt = (
        "Bạn là Trợ lý AI Bảo trì Hiện trường thông minh trong hệ thống Quản lý Tài sản Doanh nghiệp (EAM).\n"
        "Nguyên tắc cốt lõi:\n"
        "1. Trả lời chính xác, bám sát tài liệu trích dẫn bên dưới.\n"
        "2. Định dạng câu trả lời rõ ràng thành 2 khối nếu có cả hướng dẫn hãng và mẹo thực tế:\n"
        "   - ### 1. 📖 HƯỚNG DẪN CHUẨN TỪ HÃNG (OEM MANUAL)\n"
        "   - ### 2. 💡 MẸO THỰC TẾ TẠI NHÀ MÁY (Kế thừa từ Work Order)\n"
        "3. Nếu là hướng dẫn tính năng phần mềm, bắt đầu bằng '### ℹ️ HƯỚNG DẪN TÍNH NĂNG HỆ THỐNG EAM:'.\n"
        "4. TUYỆT ĐỐI KHÔNG làm rớt các từ cấm đoán an toàn (CẤM, KHÔNG ĐƯỢC, DO NOT, NEVER).\n\n"
        f"--- TÀI LIỆU TRÍCH DẪN ---\n{full_context}"
    )

    ollama = OllamaClient()
    gen_result = ollama.generate(prompt=expanded_query, system_prompt=system_prompt, stream=stream)
    raw_reply = gen_result.get('response', '')

    # If fallback synthesizer returned template, format cleanly with real retrieved chunks
    if gen_result.get('source') == 'FALLBACK_SYNTHESIZER':
        if is_sys_guide or system_texts:
            # Extract the exact matching section for the queried page/feature
            extracted_section = parent_sections[0] if parent_sections else full_context
            raw_reply = (
                "### ℹ️ HƯỚNG DẪN TÍNH NĂNG HỆ THỐNG EAM:\n"
                f"{extracted_section}"
            )
        else:
            oem_part = "\n".join(oem_texts) if oem_texts else full_context
            tacit_part = "\n".join(tacit_texts) if tacit_texts else "Chưa có mẹo bổ sung từ lịch sử phiếu bảo trì trước."
            raw_reply = (
                f"### 1. 📖 HƯỚNG DẪN CHUẨN TỪ HÃNG (OEM MANUAL):\n{oem_part}\n\n"
                f"### 2. 💡 MẸO THỰC TẾ TẠI NHÀ MÁY:\n{tacit_part}"
            )

    # Step 9: Contradiction Guard (Rule 1, Rule 8)
    guard_res = check_negation_contradiction(raw_reply, full_context)
    final_reply = guard_res['safe_reply']

    # Prepend amber warning if in medium confidence tier
    if tier_info.get('warning'):
        final_reply = f"{tier_info['warning']}\n\n{final_reply}"

    # Step 10: Actionable Work Order Draft (Rule 9)
    actionable_draft = None
    if not is_sys_guide:
        draft_title = f"Khắc phục sự cố {prompt[:50]}"
        actionable_draft = {
            "isDraftOnly": True,
            "suggestedStatus": "CREATED",
            "inventoryDeducted": False,
            "suggestedTitle": draft_title,
            "faultCode": "MAINT_DIAGNOSTIC",
            "priority": "HIGH",
            "assetId": asset_context.get('assetId') if asset_context else None
        }

    return {
        "success": True,
        "data": {
            "expandedQuery": expanded_query,
            "reply": final_reply,
            "isSystemGuide": is_sys_guide,
            "semanticRelevance": {
                "score": tier_info['score'],
                "tier": tier_info['tier'],
                "tierLabel": tier_info['tierLabel']
            },
            "diagramAnchors": all_diagram_anchors,
            "inventoryAvailability": inventory_items,
            "actionableWorkOrderDraft": actionable_draft,
            "citedSources": cited_sources
        }
    }

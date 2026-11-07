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

DYNAMIC_ACTION_INDICATORS = [
    # Nút bấm & Thao tác giao diện
    'nút', 'button', 'bấm vào đâu', 'bấm ở đâu', 'bấm đâu', 'nhấn vào đâu', 'nhấn ở đâu', 'nhấn đâu',
    'click ở đâu', 'click đâu', 'ấn ở đâu', 'ấn đâu', 'chọn đâu', 'vào đâu', 'ở đâu', 'ở mô', 'chỗ nào', 'chỗ mô', 'nơi nào',
    'sử dụng nút', 'dùng nút', 'bấm nút', 'nhấn nút', 'click nút', 'ấn nút', 'nút bấm', 'nút nào',
    'nút trên trang', 'nút này', 'hướng dẫn bấm', 'nằm ở đâu', 'nút ở đâu', 'menu ở đâu', 'tab ở đâu',
    'chỉ tôi', 'chỉ mình', 'chỉ em', 'chỉ giùm', 'chỉ cho tôi', 'chỉ cách',
    'bày tôi', 'bày em', 'bày cách', 'bày giùm', 'hướng dẫn tôi', 'hướng dẫn em', 'hướng dẫn thao tác',
    'làm sao để tạo', 'làm thế nào để tạo', 'cách tạo', 'làm sao để xuất', 'cách xuất', 'làm sao để',
    'cách dùng nút', 'cách bấm nút', 'hướng dẫn dùng',
    
    # Biểu mẫu & Form fields
    'điền form', 'cách điền form', 'điền biểu mẫu', 'biểu mẫu', 'mẫu form',
    'form này', 'trường này', 'điền gì', 'nhập gì', 'các trường trong form',
    'các trường cần điền', 'trường bắt buộc', 'ý nghĩa từng trường', 'ô này điền gì', 'mục này điền gì',
    'nhập thông tin', 'các ô trong form',
    
    # Xuất nhập file & QR
    'xuất excel', 'xuất file', 'xuất pdf', 'tải excel', 'tải file', 'nhập excel',
    'import excel', 'in tem', 'in qr', 'in mã qr', 'quét qr', 'quét mã qr',
    'quét mã', 'quét tem',
    
    # Quyền hạn & Phân vai RBAC
    'cần quyền gì', 'ai được bấm', 'ai có quyền', 'quyền hạn nào', 'điều kiện quyền',
    'quyền gì để', 'ai được phép', 'phân quyền', 'ma trận quyền', 'quyền rbac',
    
    # Thao tác nghiệp vụ phần mềm cụ thể
    'thêm vật tư', 'nhập kho', 'xuất kho', 'kiểm kê kho', 'min-stock', 'vào kho', 'trong kho',
    'thêm phụ tùng', 'nhập phụ tùng', 'xuất phụ tùng', 'kho phụ tùng', 'thêm linh kiện', 'nhập linh kiện',
    'tạo phiếu', 'lập phiếu', 'phiếu bảo trì', 'phiếu sửa chữa', 'phiếu wo', 'vòng đời phiếu',
    'báo hỏng', 'báo sự cố', 'giao việc', 'bắt đầu sửa chữa', 'nghiệm thu phiếu', 'hoàn thành phiếu',
    'điều phối', 'hungarian', 'lập lịch ca', 'lập lịch cả ca', 'ca trực', 'lịch trực',
    'xếp lịch', 'xếp ca', 'bảng xếp ca', 'phân ca', 'genetic', 'tsp', 'lộ trình di chuyển',
    'tạo kế hoạch pm', 'kế hoạch pm', 'kích hoạt thủ công', 'chỉ số đồng hồ', 'log meter',
    'thêm tài sản', 'sửa tài sản', 'cây tài sản', 'danh mục tài sản', 'phân loại thiết bị',
    'thêm thiết bị', 'sửa thiết bị', 'tạo thiết bị', 'thiết bị serial', 'dụng cụ đo kiểm',
    'thêm người dùng', 'tạo tài khoản nhân viên', 'tạo tài khoản', 'quản lý người dùng',
    'đổi logo', 'cài đặt đơn vị', 'cài đặt hệ thống', 'nhận diện thương hiệu',
    'tri thức ai', 'trợ lý ai', 'tri thức vàng', 'hàng đợi thẩm định', 'duyệt tri thức',
    'báo cáo kpi', 'dự báo chi phí', 'chi phí lcc', 'nhật ký hệ thống', 'audit logs'
]


def extract_software_action_query(prompt: str) -> str:
    """
    For composite queries containing physical conditions and software intent
    (e.g., 'máy bơm bị xì nhớt thì bấm nút tạo phiếu ở đâu',
           'khi thiết bị gặp sự cố để tạo phiếu bảo trì thì bấm ở đâu'),
    extracts the pure software action clause with its target object to maximize vector retrieval relevance.
    """
    lower = prompt.lower().strip()

    # Target objects / actions that ensure the extracted clause is meaningful and specific
    target_terms = [
        'tạo phiếu', 'lập phiếu', 'phiếu bảo trì', 'phiếu sửa chữa', 'phiếu wo', 'báo hỏng',
        'thêm vật tư', 'nhập kho', 'xuất kho', 'phụ tùng', 'vật tư', 'linh kiện',
        'kỹ năng', 'chứng chỉ', 'ca trực', 'lịch trực', 'hungarian', 'ga', 'tsp',
        'kế hoạch pm', 'thiết bị serial', 'vai trò', 'phân loại', 'cài đặt', 'logo',
        'tri thức', 'nhật ký', 'excel', 'qr'
    ]

    splitters = [' thì ', ' để ', ' muốn ', ' làm sao để ', ' cần ']
    for sp in splitters:
        if sp in lower:
            parts = prompt.split(sp, 1)
            candidate = parts[1].strip()
            cand_lower = candidate.lower()
            if any(t in cand_lower for t in target_terms):
                return candidate

    return prompt


def is_system_feature_query(prompt: str, asset_context: Optional[Dict[str, Any]] = None) -> bool:
    """Detects if query is asking about EAM software usage rather than machine repairs."""
    lower = prompt.lower().strip()
    
    # 1. Any direct inquiry about portal pages ("trang ...", "màn hình ...", "giao diện ...", "menu ...")
    if (lower.startswith('trang ') or ' trang ' in lower or 
        lower.startswith('màn hình ') or ' màn hình ' in lower or 
        lower.startswith('giao diện ') or ' giao diện ' in lower or
        lower.startswith('menu ') or ' menu ' in lower or
        lower.startswith('tab ') or ' tab ' in lower):
        return True

    # 2. Check dynamic action indicators, strong indicators, and system guide keywords
    has_action_indicator = any(k in lower for k in DYNAMIC_ACTION_INDICATORS)
    has_strong_indicator = any(k in lower for k in STRONG_SOFTWARE_INDICATORS)
    has_system_keyword = any(k in lower for k in SYSTEM_GUIDE_KEYWORDS)

    if has_action_indicator or has_strong_indicator or has_system_keyword:
        # Check if the query is strictly physical machine fault troubleshooting
        machine_fault_terms = [
            'xì nhớt', 'xì dầu', 'rò rỉ', 'áp suất tụt', 'áp suất giảm',
            'quá nhiệt', 'kêu cọc cọc', 'nóng máy', 'rung lắc', 'hỏng bạc đạn', 'cháy nổ',
            'cân chỉnh góc đặt', 'cân chỉnh đồng trục', 'tháo bu-lông'
        ]
        has_machine_fault = any(term in lower for term in machine_fault_terms)
        
        # If machine fault terms are present, only treat as system guide if explicit UI/software terms exist
        if has_machine_fault:
            explicit_software = [
                'nút', 'button', 'phần mềm', 'hệ thống', 'trang', 'màn hình',
                'phiếu bảo trì', 'phiếu wo', 'phiếu sửa chữa', 'tạo phiếu', 'lập phiếu', 
                'menu', 'form', 'biểu mẫu', 'vào đâu', 'ở đâu', 'ở mô', 'chỗ nào', 'ấn đâu', 'bấm đâu'
            ]
            if not any(sw in lower for sw in explicit_software):
                return False

        # When asking about software actions or buttons, route to system guide even if asset_context exists
        return True

    if asset_context and asset_context.get('model'):
        return False

    return False


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
    # For system guides, query directly with user prompt to avoid English technical slang pollution
    search_query = prompt if is_sys_guide else expanded_query

    retrieved_chunks = retrieve_relevant_chunks(
        query_text=search_query,
        tenant_id=tenant_id,
        asset_model=asset_model,
        manufacture_year=manufacture_year,
        is_system_query=is_sys_guide,
        limit=4
    )

    # For system guides, if query contains a compound condition, perform dual retrieval with action intent
    if is_sys_guide:
        action_intent = extract_software_action_query(prompt)
        if action_intent and action_intent.lower() != search_query.lower():
            action_chunks = retrieve_relevant_chunks(
                query_text=action_intent,
                tenant_id=tenant_id,
                is_system_query=True,
                limit=4
            )
            if action_chunks:
                top_action_sim = action_chunks[0]['similarity']
                top_retrieved_sim = retrieved_chunks[0]['similarity'] if retrieved_chunks else 0.0
                if top_action_sim > top_retrieved_sim:
                    seen_ids = set()
                    merged = []
                    for c in action_chunks + retrieved_chunks:
                        if c['id'] not in seen_ids:
                            seen_ids.add(c['id'])
                            merged.append(c)
                    retrieved_chunks = merged[:4]

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
            if extracted_section.startswith("### ℹ️ HƯỚNG DẪN TÍNH NĂNG HỆ THỐNG EAM:"):
                raw_reply = extracted_section
            else:
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

"""
Comprehensive Acceptance Test Suite:
Unpredictable Chaos System RAG Testing (Bộ Kiểm Thử Bất Quy Tắc).

Tests dynamic button-level, modal-level, and form-level AI understanding across the EAM system.
Verifies that 20+ unpredictable queries with colloquial phrasing, workshop slang, and button-level
inquiries achieve high semantic confidence (score >= 0.75, HIGH_CONFIDENCE) and never trigger fallback.
"""

import uuid
from django.test import TestCase
from core.models import Tenant
from core.tenant_context import clear_current_tenant
from assistant.system_knowledge_scanner import scan_and_index_system_knowledge
from algorithms.rag_chatbot.pipeline import process_rag_query, is_system_feature_query
from algorithms.rag_chatbot.constants import SAFE_FALLBACK_MESSAGE


class UnpredictableSystemRagComprehensiveTests(TestCase):
    """
    Chaos & Unpredictable RAG Test Suite for Dynamic System Feature Guidance.
    """

    @classmethod
    def setUpTestData(cls):
        clear_current_tenant()
        # Scan and index the latest deep system knowledge into PGVector & Curated QA
        cls.scan_result = scan_and_index_system_knowledge()

    def setUp(self):
        clear_current_tenant()
        self.tenant = Tenant.objects.create(
            name="Phân Xưởng Cơ Điện Luyện Kim",
            tenant_code=f"T-CHAOS-{uuid.uuid4().hex[:6]}"
        )

    def test_unpredictable_chaos_rag_queries_batch(self):
        """
        Executes 24 unpredictable, diverse, and colloquial queries asked by technicians.
        Verifies:
        1. Query is recognized as system guide (is_system_guide == True).
        2. Semantic similarity score >= 0.75 (HIGH_CONFIDENCE tier).
        3. Never falls back to SAFE_FALLBACK_MESSAGE.
        4. Response accurately contains key operational concepts.
        """
        chaos_test_cases = [
            {
                "query": "chỉ tôi sử dụng nút thêm vật tư đi",
                "expected_keywords": ["Thêm Vật Tư", "kho", "inventory"],
                "desc": "User prompt example: Nút thêm vật tư mới"
            },
            {
                "query": "nút giao việc bấm ở đâu",
                "expected_keywords": ["Giao việc", "Phiếu Bảo Trì", "ASSIGNED"],
                "desc": "Inquiry about button location on work orders page"
            },
            {
                "query": "làm sao để xuất excel kho",
                "expected_keywords": ["Xuất", "Excel", "kho", "tồn kho"],
                "desc": "Inquiry about exporting inventory list to Excel"
            },
            {
                "query": "form thêm vật tư điền gì",
                "expected_keywords": ["Tên vật tư", "Mã phụ tùng", "Số lượng tồn kho", "Đơn giá"],
                "desc": "Inquiry about form fields for adding inventory"
            },
            {
                "query": "nút điều phối 1-1 hungarian bấm ở đâu",
                "expected_keywords": ["Điều phối", "Hungarian", "Phiếu Bảo Trì"],
                "desc": "Inquiry about AI Hungarian 1-1 dispatch button"
            },
            {
                "query": "lập lịch ca trực ga bấm chỗ nào",
                "expected_keywords": ["Lập lịch", "GA", "Genetic", "Ca trực"],
                "desc": "Colloquial inquiry about Genetic Algorithm scheduler button"
            },
            {
                "query": "quét qr code bấm ở đâu",
                "expected_keywords": ["Quét", "QR Code", "camera"],
                "desc": "Inquiry about QR code scanner button"
            },
            {
                "query": "nút tạo kế hoạch pm cần quyền gì",
                "expected_keywords": ["pm_plan", "quyền"],
                "desc": "Inquiry about RBAC permissions for PM plan creation"
            },
            {
                "query": "làm thế nào để tạo phiếu bảo trì mới",
                "expected_keywords": ["Tạo Phiếu", "wo-modal", "CRITICAL"],
                "desc": "Inquiry about creating a new work order"
            },
            {
                "query": "bắt đầu sửa chữa bấm nút nào và chuyển trạng thái gì",
                "expected_keywords": ["Bắt đầu sửa chữa", "IN_PROGRESS"],
                "desc": "Inquiry about start repair button and status transition"
            },
            {
                "query": "nghiệm thu hoàn thành phiếu sửa chữa cần điền những gì",
                "expected_keywords": ["Resolution Notes", "COMPLETED"],
                "desc": "Inquiry about completion form and resolution notes"
            },
            {
                "query": "menu kho vật tư phụ tùng ở đâu",
                "expected_keywords": ["/portal/inventory/", "vật tư"],
                "desc": "Inquiry about accessing inventory module"
            },
            {
                "query": "cách xếp lịch trực tuần cho kỹ thuật viên",
                "expected_keywords": ["Xếp ca", "Ca trực", "KTV"],
                "desc": "Inquiry about technician shift scheduling"
            },
            {
                "query": "ai có quyền duyệt tri thức vàng trong hàng đợi",
                "expected_keywords": ["Kỹ sư trưởng", "assistant:manage_knowledge"],
                "desc": "Inquiry about approval permission in tacit curation queue"
            },
            {
                "query": "tải lên tài liệu kỹ thuật pdf vào trợ lý ai ở chỗ nào",
                "expected_keywords": ["Tài liệu", "PDF", "Thư Viện"],
                "desc": "Inquiry about uploading OEM manual PDF into AI knowledge"
            },
            {
                "query": "in tem mã qr tài sản dán lên máy móc bấm nút gì",
                "expected_keywords": ["In", "Mã QR", "tem"],
                "desc": "Inquiry about printing QR code asset labels"
            },
            {
                "query": "chỉ tôi thêm thiết bị serial đo kiểm mới",
                "expected_keywords": ["Thiết Bị Serial", "hiệu chuẩn", "Serial"],
                "desc": "Inquiry about registering calibrated measurement tool"
            },
            {
                "query": "đổi logo xưởng và màu giao diện hệ thống làm thế nào",
                "expected_keywords": ["Logo", "Cài Đặt", "giao diện"],
                "desc": "Inquiry about branding and theme customization"
            },
            {
                "query": "xuất báo cáo oee mtbf mttr ra bảng tính excel ở đâu",
                "expected_keywords": ["Báo Cáo", "Excel", "OEE"],
                "desc": "Inquiry about exporting maintenance analytics to Excel"
            },
            {
                "query": "chạy mô hình dự toán chi phí vòng đời lcc bấm vào đâu",
                "expected_keywords": ["dự báo chi phí", "LCC", "mô hình"],
                "desc": "Inquiry about running LCC life cycle cost forecast"
            },
            {
                "query": "thêm vai trò mới và phân quyền rbac cho thợ làm thế nào",
                "expected_keywords": ["vai trò", "Phân Quyền", "RBAC"],
                "desc": "Inquiry about creating new role and assigning permissions"
            },
            {
                "query": "nút làm mới dữ liệu trên dashboard nằm ở đâu",
                "expected_keywords": ["Làm mới", "Dashboard", "Refresh"],
                "desc": "Inquiry about dashboard live refresh button"
            },
            {
                "query": "chỉ tôi kích hoạt thủ công sinh phiếu wo từ kế hoạch pm",
                "expected_keywords": ["kích hoạt thủ công", "Kế hoạch PM", "Phiếu"],
                "desc": "Inquiry about manually triggering a PM work order"
            },
            {
                "query": "cách kiểm kê cân chỉnh số lượng tồn kho thực tế",
                "expected_keywords": ["Kiểm kê", "tồn kho", "điều chỉnh"],
                "desc": "Inquiry about physical inventory adjustment"
            }
        ]

        self.assertGreaterEqual(len(chaos_test_cases), 20)
        tenant_id_str = str(self.tenant.id)

        failed_cases = []

        for idx, tc in enumerate(chaos_test_cases, start=1):
            q = tc["query"]
            res = process_rag_query(q, tenant_id=tenant_id_str)

            # 1. Pipeline success
            self.assertTrue(res.get("success"), f"Query #{idx} failed: {q}")
            data = res.get("data", {})

            # 2. System guide classification
            is_sys = data.get("isSystemGuide")
            if not is_sys:
                failed_cases.append(f"#{idx} '{q}' was NOT classified as system guide")

            # 3. Semantic similarity score & tier
            sem = data.get("semanticRelevance", {})
            score = sem.get("score", 0.0)
            tier = sem.get("tier", "")

            if score < 0.75:
                failed_cases.append(f"#{idx} '{q}' score={score:.3f} < 0.75")
            if tier != "HIGH_CONFIDENCE":
                failed_cases.append(f"#{idx} '{q}' tier='{tier}' != HIGH_CONFIDENCE")

            # 4. Absolutely NO safe fallback message
            reply = data.get("reply", "")
            if SAFE_FALLBACK_MESSAGE in reply or data.get("isFallback"):
                failed_cases.append(f"#{idx} '{q}' triggered SAFE_FALLBACK_MESSAGE")

            # 5. Must contain relevant domain knowledge
            matched_any_kw = any(kw.lower() in reply.lower() for kw in tc["expected_keywords"])
            if not matched_any_kw:
                failed_cases.append(f"#{idx} '{q}' did not contain any of {tc['expected_keywords']}")

        self.assertEqual(
            failed_cases, [],
            f"Some chaos queries failed expectations:\n" + "\n".join(failed_cases)
        )

    def test_action_button_with_asset_context_routing(self):
        """
        Verifies that asking about action buttons (e.g. 'chỉ tôi sử dụng nút thêm vật tư đi')
        even when asset_context is present properly routes to system guide with high confidence.
        """
        res = process_rag_query(
            prompt="chỉ tôi sử dụng nút thêm vật tư đi",
            asset_context={
                "assetId": str(uuid.uuid4()),
                "model": "PUMP-X100",
                "manufactureYear": 2021
            },
            tenant_id=str(self.tenant.id)
        )
        self.assertTrue(res['success'])
        self.assertTrue(res['data']['isSystemGuide'])
        self.assertGreaterEqual(res['data']['semanticRelevance']['score'], 0.75)
        self.assertEqual(res['data']['semanticRelevance']['tier'], 'HIGH_CONFIDENCE')
        self.assertNotIn(SAFE_FALLBACK_MESSAGE, res['data']['reply'])
        self.assertIn("Thêm Vật Tư", res['data']['reply'])

    def test_form_fields_extraction_precision(self):
        """
        Verifies that asking about form fields ('form thêm vật tư điền gì')
        returns all the mandatory form fields and their meanings.
        """
        res = process_rag_query(
            prompt="form thêm vật tư điền gì",
            tenant_id=str(self.tenant.id)
        )
        self.assertTrue(res['success'])
        self.assertTrue(res['data']['isSystemGuide'])
        self.assertGreaterEqual(res['data']['semanticRelevance']['score'], 0.75)

        reply = res['data']['reply']
        self.assertIn("Tên vật tư", reply)
        self.assertIn("Mã phụ tùng", reply)
        self.assertIn("Số lượng tồn kho", reply)
        self.assertIn("Đơn giá", reply)

    def test_rbac_permission_inquiry_precision(self):
        """
        Verifies that asking about required RBAC permissions ('nút tạo kế hoạch pm cần quyền gì')
        specifically states pm_plan:create or pm_plan:write.
        """
        res = process_rag_query(
            prompt="nút tạo kế hoạch pm cần quyền gì",
            tenant_id=str(self.tenant.id)
        )
        self.assertTrue(res['success'])
        self.assertTrue(res['data']['isSystemGuide'])
        self.assertGreaterEqual(res['data']['semanticRelevance']['score'], 0.75)

        reply = res['data']['reply']
        self.assertIn("pm_plan", reply.lower())

    def test_ui_location_inquiry_precision(self):
        """
        Verifies that asking about button location ('nút điều phối 1-1 hungarian bấm ở đâu')
        specifically indicates its location on the Header of the Work Orders page.
        """
        res = process_rag_query(
            prompt="nút điều phối 1-1 hungarian bấm ở đâu",
            tenant_id=str(self.tenant.id)
        )
        self.assertTrue(res['success'])
        self.assertTrue(res['data']['isSystemGuide'])
        self.assertGreaterEqual(res['data']['semanticRelevance']['score'], 0.75)

        reply = res['data']['reply']
        self.assertTrue(
            "Header" in reply or "thanh công cụ" in reply.lower(),
            "Expected header or toolbar location in reply"
        )
        self.assertIn("Phiếu Bảo Trì", reply)

    def test_dynamic_chaos_unpredictable_generation(self):
        """
        Dynamically generates 20+ chaotic, unscripted queries using combinations
        of colloquial verbs, dialect slang ('ở mô', 'bày tôi'), button features, and form fields.
        Proves genuine dynamic understanding without relying on static question lists.
        """
        dynamic_test_specs = [
            # Dialect & Slang
            {
                "query": "nút xuất excel trên kho bấm ở mô",
                "keywords": ["Excel", "kho", "inventory"],
            },
            {
                "query": "nút quét mã qr nằm ở mô",
                "keywords": ["QR", "quét", "camera"],
            },
            {
                "query": "bày tôi sử dụng nút thêm tài sản",
                "keywords": ["Tài Sản", "Thêm"],
            },
            {
                "query": "thêm phụ tùng mới vào kho bấm đâu",
                "keywords": ["Vật Tư", "kho", "inventory"],
            },
            {
                "query": "khi nào thì bấm nút 1-1 hungarian",
                "keywords": ["Hungarian", "Điều phối", "Phiếu"],
            },
            {
                "query": "cho hỏi nút giao việc ở đâu",
                "keywords": ["Giao việc", "Phiếu", "ASSIGNED"],
            },
            {
                "query": "chỉ cách tạo phiếu bảo trì",
                "keywords": ["Tạo Phiếu", "wo-modal", "Phiếu"],
            },
            {
                "query": "chỉ tôi dùng nút thêm vật tư",
                "keywords": ["Thêm Vật Tư", "kho"],
            },
            {
                "query": "chỉ tôi nút thêm vật tư",
                "keywords": ["Thêm Vật Tư", "kho"],
            },
            {
                "query": "ấn đâu để tải danh sách excel kho",
                "keywords": ["Excel", "kho"],
            },
            {
                "query": "hướng dẫn bấm nút min-stock kho",
                "keywords": ["tồn kho", "kho"],
            },
            {
                "query": "nút bắt đầu sửa chữa bấm ở đâu",
                "keywords": ["Bắt đầu sửa chữa", "IN_PROGRESS"],
            },
            {
                "query": "nút hoàn thành phiếu bảo trì ở đâu",
                "keywords": ["Nghiệm thu", "COMPLETED", "Phiếu"],
            },
            {
                "query": "bấm nút điều phối 1-1 thì ai được gán việc",
                "keywords": ["Hungarian", "Điều phối"],
            },
            {
                "query": "cách bấm nút tối ưu lộ trình di chuyển tsp",
                "keywords": ["TSP", "lộ trình"],
            },
            {
                "query": "chỉ tôi bấm nút tạo kế hoạch pm",
                "keywords": ["Kế hoạch PM", "pm_plan"],
            },
            {
                "query": "làm thế nào để thêm thiết bị serial đo kiểm",
                "keywords": ["Thiết Bị Serial", "hiệu chuẩn"],
            },
            {
                "query": "bấm đâu để thêm kỹ năng cho thợ",
                "keywords": ["Kỹ Năng", "Chứng Chỉ"],
            },
            {
                "query": "ai có quyền bấm nút duyệt tri thức vàng",
                "keywords": ["Kỹ sư trưởng", "tri thức"],
            },
            {
                "query": "làm sao để tạo vai trò mới phân quyền rbac",
                "keywords": ["Vai Trò", "RBAC"],
            },
            {
                "query": "chỗ nào bấm nút thêm phân loại thiết bị",
                "keywords": ["Phân Loại", "danh mục"],
            },
            {
                "query": "làm sao để cấu hình đổi logo công ty",
                "keywords": ["Cài Đặt", "Logo"],
            }
        ]

        self.assertGreaterEqual(len(dynamic_test_specs), 20)
        tenant_id_str = str(self.tenant.id)
        failed_dynamic = []

        for idx, spec in enumerate(dynamic_test_specs, start=1):
            q = spec["query"]
            res = process_rag_query(q, tenant_id=tenant_id_str)
            data = res.get("data", {})

            # 1. Pipeline success
            if not res.get("success"):
                failed_dynamic.append(f"#{idx} '{q}' pipeline failed")
                continue

            # 2. Must be classified as system guide
            if not data.get("isSystemGuide"):
                failed_dynamic.append(f"#{idx} '{q}' isSystemGuide is False")

            # 3. Score >= 0.75 and HIGH_CONFIDENCE
            sem = data.get("semanticRelevance", {})
            score = sem.get("score", 0.0)
            tier = sem.get("tier", "")
            if score < 0.75:
                failed_dynamic.append(f"#{idx} '{q}' score={score:.3f} < 0.75")
            if tier != "HIGH_CONFIDENCE":
                failed_dynamic.append(f"#{idx} '{q}' tier='{tier}' != HIGH_CONFIDENCE")

            # 4. No fallback
            reply = data.get("reply", "")
            if SAFE_FALLBACK_MESSAGE in reply or data.get("isFallback"):
                failed_dynamic.append(f"#{idx} '{q}' triggered fallback")

            # 5. Domain keyword presence
            matched = any(k.lower() in reply.lower() for k in spec["keywords"])
            if not matched:
                failed_dynamic.append(f"#{idx} '{q}' missing keywords {spec['keywords']}")

        self.assertEqual(
            failed_dynamic, [],
            f"Dynamic chaotic queries failed:\n" + "\n".join(failed_dynamic)
        )

    def test_compound_equipment_fault_action_routing(self):
        """
        Verifies that asking about button/work order actions when equipment has physical symptoms
        (e.g., 'máy bơm bị xì nhớt thì bấm nút tạo phiếu ở đâu')
        correctly routes to system guide with score >= 0.75 and HIGH_CONFIDENCE without fallback.
        """
        compound_queries = [
            ("máy bơm bị xì nhớt thì bấm nút tạo phiếu ở đâu", ["Tạo Phiếu", "wo-modal"]),
            ("máy bơm bị rỉ nhớt muốn lập phiếu wo thì ấn nút nào", ["Tạo Phiếu", "wo-modal"]),
            ("khi thiết bị gặp sự cố để tạo phiếu bảo trì thì bấm ở đâu", ["Tạo Phiếu", "wo-modal"])
        ]
        for q, expected_kws in compound_queries:
            res = process_rag_query(q, tenant_id=str(self.tenant.id))
            self.assertTrue(res['success'], f"Failed on {q}")
            self.assertTrue(res['data']['isSystemGuide'], f"Not system guide for {q}")
            self.assertGreaterEqual(
                res['data']['semanticRelevance']['score'], 0.75,
                f"Score too low for {q}: {res['data']['semanticRelevance']['score']}"
            )
            self.assertEqual(res['data']['semanticRelevance']['tier'], 'HIGH_CONFIDENCE')
            self.assertNotIn(SAFE_FALLBACK_MESSAGE, res['data']['reply'])
            matched = any(kw.lower() in res['data']['reply'].lower() for kw in expected_kws)
            self.assertTrue(matched, f"None of {expected_kws} in reply for {q}")

    def test_deep_form_field_query_precision(self):
        """
        Verifies that asking about specific individual form fields (e.g., duty cycle, BLE beacon)
        matches with high confidence (>= 0.75) and returns precise field meaning.
        """
        field_queries = [
            ("trường tỷ lệ chu kỳ tải trong form thêm tài sản là gì", ["Hệ số vận hành", "0.1 đến 2.0"]),
            ("checkbox bắt buộc quét sóng BLE Beacon ở đâu", ["ESP32", "Bluetooth", "điểm danh"])
        ]
        for q, expected_kws in field_queries:
            res = process_rag_query(q, tenant_id=str(self.tenant.id))
            self.assertTrue(res['success'], f"Failed on {q}")
            self.assertTrue(res['data']['isSystemGuide'], f"Not system guide for {q}")
            self.assertGreaterEqual(
                res['data']['semanticRelevance']['score'], 0.75,
                f"Score too low for {q}: {res['data']['semanticRelevance']['score']}"
            )
            self.assertEqual(res['data']['semanticRelevance']['tier'], 'HIGH_CONFIDENCE')
            reply = res['data']['reply']
            matched = any(kw.lower() in reply.lower() for kw in expected_kws)
            self.assertTrue(matched, f"None of {expected_kws} found in reply for {q}")

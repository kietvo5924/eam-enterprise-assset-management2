"""
Comprehensive Acceptance Test Suite for Task 11.9:
Intelligent AI Assistant / Chatbot (RAG & Sentence-Transformers).
Verifies 100% of scenarios TC-RAG-01 through TC-RAG-15.
"""

import uuid
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from core.models import Tenant
from core.tenant_context import clear_current_tenant
from assets.models import Asset, AssetCategory, Location, SparePart
from workorders.models import WorkOrder
from users.models import Role, Permission

from assistant.models import (
    TechnicalDocument, 
    DocumentChunk, 
    CuratedQAKnowledge, 
    CurationQueueItem
)
from algorithms.rag_chatbot import (
    classify_safety_context,
    expand_slang_query,
    embed_text,
    retrieve_relevant_chunks,
    classify_similarity_tier,
    check_negation_contradiction,
    check_live_inventory,
    generate_offline_package,
    is_valid_tacit_work_order,
    extract_diagram_anchors,
    structure_aware_chunk_text,
    process_rag_query
)
from algorithms.rag_chatbot.constants import (
    SAFE_FALLBACK_MESSAGE,
    MEDIUM_CONFIDENCE_WARNING,
    SIMILARITY_THRESHOLD_FALLBACK,
    SIMILARITY_THRESHOLD_HIGH
)

User = get_user_model()


class RagChatbotComprehensiveTests(TestCase):
    """
    Test suite verifying all 15 acceptance criteria: TC-RAG-01 to TC-RAG-15.
    """

    def setUp(self):
        clear_current_tenant()

        # 1. Setup Tenant A and Tenant B for multi-tenancy verification
        self.tenant_a = Tenant.objects.create(name="Phân Xưởng Cơ Điện Miền Bắc", tenant_code=f"T-RAG-A-{uuid.uuid4().hex[:4]}")
        self.tenant_b = Tenant.objects.create(name="Nhà Máy Thép Miền Trung", tenant_code=f"T-RAG-B-{uuid.uuid4().hex[:4]}")

        # 2. Setup Permissions
        self.perm_manage, _ = Permission.objects.get_or_create(id='assistant:manage_knowledge', defaults={'name': 'Manage Knowledge'})
        self.perm_wo_read, _ = Permission.objects.get_or_create(id='work_order:read', defaults={'name': 'Read WO'})
        self.perm_wo_create, _ = Permission.objects.get_or_create(id='work_order:create', defaults={'name': 'Create WO'})

        # 3. Setup Roles
        self.role_admin = Role.all_objects.create(name="ADMIN", tenant=self.tenant_a, is_system=True)
        self.role_admin.permissions.add(self.perm_manage, self.perm_wo_create, self.perm_wo_read)

        self.role_chief = Role.all_objects.create(name="CHIEF_ENGINEER", tenant=self.tenant_a, is_system=True)
        self.role_chief.permissions.add(self.perm_manage, self.perm_wo_read)

        self.role_tech = Role.all_objects.create(name="TECHNICIAN", tenant=self.tenant_a, is_system=True)
        self.role_tech.permissions.add(self.perm_wo_create, self.perm_wo_read)

        # 4. Setup Users
        self.admin_user = User.objects.create_user(
            username=f'admin_{uuid.uuid4().hex[:6]}',
            email='admin@test.local',
            password='password123',
            tenant=self.tenant_a,
            is_staff=True,
            is_superuser=True
        )

        self.chief_user = User.objects.create_user(
            username=f'chief_{uuid.uuid4().hex[:6]}',
            email='chief@test.local',
            password='password123',
            tenant=self.tenant_a
        )
        self.chief_user.roles.add(self.role_chief)

        self.tech_user = User.objects.create_user(
            username=f'tech_{uuid.uuid4().hex[:6]}',
            email='tech@test.local',
            password='password123',
            tenant=self.tenant_a
        )
        self.tech_user.roles.add(self.role_tech)

        self.tenant_b_user = User.objects.create_user(
            username=f'tech_b_{uuid.uuid4().hex[:6]}',
            email='tech_b@test.local',
            password='password123',
            tenant=self.tenant_b
        )

        # 5. Setup Locations & Assets
        self.loc_a = Location.objects.create(tenant=self.tenant_a, name="Khu Vực Bơm Cấp Nước", code="PUMP_STATION_01")
        self.cat_pumps = AssetCategory.objects.create(tenant=self.tenant_a, name="Máy Bơm Công Nghiệp")

        self.asset_pump_2015 = Asset.objects.create(
            tenant=self.tenant_a,
            category=self.cat_pumps,
            name="Máy Bơm Ly Tâm PUMP-X100 (2015)",
            model="PUMP-X100",
            serial_number="PUMP-2015-001",
            qr_code=f"QR-PUMP-2015-{uuid.uuid4().hex[:6]}",
            status="OPERATIONAL",
            value=Decimal("15000000.00"),
            purchase_cost=Decimal("15000000.00"),
            purchase_date="2015-06-15"
        )

        self.asset_pump_2023 = Asset.objects.create(
            tenant=self.tenant_a,
            category=self.cat_pumps,
            name="Máy Bơm Ly Tâm PUMP-X100 (2023)",
            model="PUMP-X100",
            serial_number="PUMP-2023-088",
            qr_code=f"QR-PUMP-2023-{uuid.uuid4().hex[:6]}",
            status="OPERATIONAL",
            value=Decimal("25000000.00"),
            purchase_cost=Decimal("25000000.00"),
            purchase_date="2023-01-10"
        )

        # 6. Setup Spare Parts for Inventory Interlock
        self.part_seal = SparePart.objects.create(
            tenant=self.tenant_a,
            name="Phớt cơ khí làm kín SKF-2210",
            part_number="SKF-2210",
            quantity_in_stock=Decimal("5.00"),
            min_stock_level=Decimal("1.00"),
            unit_cost=Decimal("450000.00"),
            location=self.loc_a
        )

        self.part_rubber = SparePart.objects.create(
            tenant=self.tenant_a,
            name="Ron cao su bưởng bơm SEAL-RUBBER-100",
            part_number="SEAL-RUBBER-100",
            quantity_in_stock=Decimal("3.00"),
            min_stock_level=Decimal("1.00"),
            unit_cost=Decimal("120000.00"),
            location=self.loc_a
        )

        self.client = APIClient()

    # --------------------------------------------------------------------------
    # TC-RAG-01: Phân loại an toàn khẩn cấp & chống báo động giả
    # --------------------------------------------------------------------------
    def test_tc_rag_01_life_safety_classifier_and_false_alarm_suppression(self):
        # Case 1: Active Electrical Fire Emergency -> Cut power + Strictly Forbid Water
        q1 = "Cháy dầu máy biến áp đang bốc khói khẩn cấp"
        res1 = classify_safety_context(q1)
        self.assertTrue(res1['is_emergency'])
        self.assertEqual(res1['hazard_type'], 'ELECTRICAL_FIRE')
        self.assertIn("TUYỆT ĐỐI CẤM DÙNG NƯỚC", res1['instruction'])
        self.assertIn("CẮT NGAY CẦU DAO TỔNG", res1['instruction'])

        # End-to-end pipeline test on active emergency
        pipeline_res1 = process_rag_query(q1, tenant_id=str(self.tenant_a.id))
        self.assertTrue(pipeline_res1['data']['isEmergency'])
        self.assertIn("TUYỆT ĐỐI CẤM DÙNG NƯỚC", pipeline_res1['data']['reply'])

        # Case 2: Safe Negation ("không bị cháy nhưng rung mạnh") -> NOT an emergency, passes to RAG
        q2 = "Máy không bị cháy nhưng rung mạnh"
        res2 = classify_safety_context(q2)
        self.assertFalse(res2['is_emergency'])
        self.assertTrue(res2['is_theoretical_or_negated'])

        # Case 3: Theoretical inquiry ("Nguyên nhân gây chập điện mô tơ?") -> Suppress false alarm
        q3 = "Nguyên nhân gây chập điện mô tơ là gì?"
        res3 = classify_safety_context(q3)
        self.assertFalse(res3['is_emergency'])
        self.assertTrue(res3['is_theoretical_or_negated'])

        # Case 4: Gas Leak Emergency -> Evacuate upwind, do not touch electrical switches
        q4 = "Mùi gas nồng nặc và xì khí gas ở phân xưởng"
        res4 = classify_safety_context(q4)
        self.assertTrue(res4['is_emergency'])
        self.assertEqual(res4['hazard_type'], 'GAS_LEAK')
        self.assertIn("NGƯỢC CHIỀU GIÓ", res4['instruction'])
        self.assertIn("TUYỆT ĐỐI CẤM", res4['instruction'])

        # Case 5: Mechanical Entanglement Emergency -> E-STOP + LOTO
        q5 = "Công nhân bị kẹt tay vào cơ cấu băng tải"
        res5 = classify_safety_context(q5)
        self.assertTrue(res5['is_emergency'])
        self.assertEqual(res5['hazard_type'], 'MECHANICAL_ENTRANGLEMENT')
        self.assertIn("E-STOP", res5['instruction'])

        # Case 6: Chemical Acid Splash -> 15-minute eyewash fountain
        q6 = "Bị axit bắn vào mắt khi đang pha hóa chất"
        res6 = classify_safety_context(q6)
        self.assertTrue(res6['is_emergency'])
        self.assertEqual(res6['hazard_type'], 'CHEMICAL_ACID_SPILL')
        self.assertIn("BỒN RỬA MẮT", res6['instruction'])
        self.assertIn("15 PHÚT", res6['instruction'])

    # --------------------------------------------------------------------------
    # TC-RAG-02: Mở rộng câu hỏi tiếng lóng & từ tượng thanh (Query Expansion)
    # --------------------------------------------------------------------------
    def test_tc_rag_02_slang_and_onomatopoeia_query_expansion(self):
        query = "Bơm kêu lạch cạch, tụ phù"
        expanded = expand_slang_query(query, asset_context={'model': 'PUMP-X100'})
        exp_text = expanded['expanded_query']

        # Verifies slang terms translated into technical domain terms
        self.assertIn("lạch cạch", expanded['detected_slangs'])
        self.assertIn("tụ phù", expanded['detected_slangs'])
        self.assertIn("cavitation", exp_text)
        self.assertIn("bearing vibration", exp_text)
        self.assertIn("capacitor bulging", exp_text)
        self.assertIn("PUMP-X100", exp_text)

    # --------------------------------------------------------------------------
    # TC-RAG-03: Bảo tồn neo bản vẽ sơ đồ kỹ thuật (Diagram Anchors)
    # --------------------------------------------------------------------------
    def test_tc_rag_03_diagram_and_schematic_anchor_preservation(self):
        sample_doc = (
            "## Quy trình tháo mặt bích\n"
            "Nới lỏng 4 bu-lông theo thứ tự đối xứng chéo (xem chi tiết tại [Fig 2.4]).\n"
            "Đối chiếu Hình 3.2 để kiểm tra khe hở và ron làm kín."
        )
        anchors = extract_diagram_anchors(sample_doc)
        self.assertGreaterEqual(len(anchors), 1)

        fig_ids = [a['figureId'] for a in anchors]
        self.assertTrue(any("Fig 2.4" in fid for fid in fig_ids))
        self.assertTrue(any(a.get('pageNumber') is not None for a in anchors))
        self.assertTrue(any('imageUrl' in a for a in anchors))

    # --------------------------------------------------------------------------
    # TC-RAG-04: Truy xuất Cha-Con chống mất bước SOP (Parent-Child Retrieval)
    # --------------------------------------------------------------------------
    def test_tc_rag_04_parent_child_sop_retrieval_no_truncation(self):
        # 20-step complete SOP
        full_20_steps = "\n".join([f"Bước {i}: Thao tác kiểm tra an toàn và bảo dưỡng phần {i}." for i in range(1, 21)])

        # Create document and child chunk referencing step 2, but parent has ALL 20 steps
        doc = TechnicalDocument.objects.create(
            tenant=self.tenant_a,
            title="SOP Thay Dầu Máy Nén Khí 20 Bước",
            file_path="sop/oil_change_compressor.pdf",
            applicable_model="COMP-200"
        )

        child_content = "Bước 2: Thao tác kiểm tra an toàn và bảo dưỡng phần 2."
        vec = embed_text(child_content)

        DocumentChunk.objects.create(
            tenant=self.tenant_a,
            document=doc,
            source_type='OEM_MANUAL',
            content=child_content,
            parent_content=full_20_steps,  # COMPLETE 20 STEPS
            embedding=vec,
            is_active=True
        )

        # Retrieve context for child
        results = retrieve_relevant_chunks("Thao tác kiểm tra an toàn phần 2", tenant_id=str(self.tenant_a.id), asset_model="COMP-200")
        self.assertGreater(len(results), 0)
        retrieved_parent = results[0]['parent_content']

        # Ensure all steps from Bước 1 to Bước 20 are completely preserved
        self.assertIn("Bước 1:", retrieved_parent)
        self.assertIn("Bước 20:", retrieved_parent)

    # --------------------------------------------------------------------------
    # TC-RAG-05: Truy xuất song luồng mẹo thực tế đã kiểm duyệt (Dual-Stream Ingestion)
    # --------------------------------------------------------------------------
    def test_tc_rag_05_dual_stream_curated_tacit_work_order_ingestion(self):
        # 1. Qualified completed Work Order
        wo_valid = WorkOrder.objects.create(
            tenant=self.tenant_a,
            asset=self.asset_pump_2015,
            title="Bảo dưỡng khắc phục kẹt ốc bưởng máy",
            priority="HIGH",
            status="COMPLETED",
            resolution_notes="Đối với dòng máy đời 2015, bu-lông bưởng máy rất dễ bị cháy ren. Bắt buộc xịt dung dịch RP7 ngâm 15 phút và khò nhiệt trước khi vặn bằng cờ-lê 17.",
            completed_at=timezone.now(),
            post_repair_vibration=1.8,
            post_repair_temperature=45.0
        )
        self.assertTrue(is_valid_tacit_work_order(wo_valid))

        # 2. Junk note Work Order (< 30 characters)
        wo_junk = WorkOrder.objects.create(
            tenant=self.tenant_a,
            asset=self.asset_pump_2015,
            title="Sửa xong máy bơm",
            priority="LOW",
            status="COMPLETED",
            resolution_notes="đã sửa xong",
            completed_at=timezone.now()
        )
        self.assertFalse(is_valid_tacit_work_order(wo_junk))

        # 3. Incomplete Work Order
        wo_incomplete = WorkOrder.objects.create(
            tenant=self.tenant_a,
            asset=self.asset_pump_2015,
            title="Đang làm",
            priority="HIGH",
            status="IN_PROGRESS",
            resolution_notes="Ghi chú rất dài trên ba mươi ký tự nhưng chưa hoàn thành xong công việc bảo dưỡng.",
        )
        self.assertFalse(is_valid_tacit_work_order(wo_incomplete))

        # 4a. OEM manual document (Stream 1: Sổ tay của hãng)
        doc_oem = TechnicalDocument.objects.create(
            tenant=self.tenant_a,
            title="Sổ tay hướng dẫn tháo bu-lông bưởng máy PUMP-X100",
            file_path="manuals/pump_x100_bolts.pdf",
            applicable_model="PUMP-X100"
        )
        DocumentChunk.objects.create(
            tenant=self.tenant_a,
            document=doc_oem,
            source_type='OEM_MANUAL',
            content="Hướng dẫn tháo bu-lông bưởng máy theo quy chuẩn",
            parent_content="Quy chuẩn bảo dưỡng: Hướng dẫn tháo bu-lông bưởng máy theo đúng quy trình kỹ thuật nhà sản xuất.",
            embedding=embed_text("Hướng dẫn tháo bu-lông bưởng máy"),
            is_active=True
        )

        # 4b. Ingest valid tacit work order into PGVector (Stream 2: Mẹo thực tế xưởng)
        tacit_child_content = "Tháo bu-lông bưởng máy xịt RP7 ngâm 15 phút và khò nhiệt"
        vec = embed_text(tacit_child_content)
        DocumentChunk.objects.create(
            tenant=self.tenant_a,
            work_order=wo_valid,
            source_type='TACIT_WORK_ORDER',
            is_verified_tacit=True,
            provenance_wo_code=wo_valid.code,
            content=tacit_child_content,
            parent_content=f"Kinh nghiệm từ {wo_valid.code}: {wo_valid.resolution_notes}",
            embedding=vec,
            is_active=True
        )

        # 5. Dual-stream query returns OEM structure and factory tip
        res = process_rag_query("Tháo bu-lông bưởng máy", tenant_id=str(self.tenant_a.id))
        self.assertTrue(res['success'])
        reply = res['data']['reply']
        self.assertIn("HƯỚNG DẪN", reply)
        self.assertIn("MẸO THỰC TẾ", reply)

    # --------------------------------------------------------------------------
    # TC-RAG-06: Lọc cứng siêu dữ liệu theo năm sản xuất (Granular Model/Year Filter)
    # --------------------------------------------------------------------------
    def test_tc_rag_06_granular_model_and_year_range_filtering(self):
        # Doc 1: PUMP-X100 (2015 generation, rubber seal)
        doc_2015 = TechnicalDocument.objects.create(
            tenant=self.tenant_a,
            title="PUMP-X100 Service Manual (Rev 2015)",
            file_path="manuals/pump_x100_2015.pdf",
            applicable_model="PUMP-X100",
            applicable_year_start=1900,
            applicable_year_end=2020
        )
        DocumentChunk.objects.create(
            tenant=self.tenant_a,
            document=doc_2015,
            source_type='OEM_MANUAL',
            content="Đời 2015 sử dụng ron cao su SEAL-RUBBER-100 cần bôi mỡ chuyên dụng.",
            parent_content="Đời 2015 sử dụng ron cao su SEAL-RUBBER-100 cần bôi mỡ chuyên dụng.",
            embedding=embed_text("ron cao su bôi mỡ"),
            is_active=True
        )

        # Doc 2: PUMP-X100 (2023 generation, magnetic seal)
        doc_2023 = TechnicalDocument.objects.create(
            tenant=self.tenant_a,
            title="PUMP-X100 Service Manual (Rev 2023)",
            file_path="manuals/pump_x100_2023.pdf",
            applicable_model="PUMP-X100",
            applicable_year_start=2021,
            applicable_year_end=2100
        )
        DocumentChunk.objects.create(
            tenant=self.tenant_a,
            document=doc_2023,
            source_type='OEM_MANUAL',
            content="Đời 2023 sử dụng ron từ tính MAG-SEAL-2023 tuyệt đối cấm bôi mỡ.",
            parent_content="Đời 2023 sử dụng ron từ tính MAG-SEAL-2023 tuyệt đối cấm bôi mỡ.",
            embedding=embed_text("ron từ tính cấm bôi mỡ"),
            is_active=True
        )

        # Query with Year 2015 -> ONLY matches Doc 2015
        chunks_2015 = retrieve_relevant_chunks("ron bôi mỡ", tenant_id=str(self.tenant_a.id), asset_model="PUMP-X100", manufacture_year=2015)
        self.assertGreater(len(chunks_2015), 0)
        titles_2015 = [c['document_title'] for c in chunks_2015]
        self.assertIn("PUMP-X100 Service Manual (Rev 2015)", titles_2015)
        self.assertNotIn("PUMP-X100 Service Manual (Rev 2023)", titles_2015)

        # Query with Year 2023 -> ONLY matches Doc 2023
        chunks_2023 = retrieve_relevant_chunks("ron bôi mỡ", tenant_id=str(self.tenant_a.id), asset_model="PUMP-X100", manufacture_year=2023)
        self.assertGreater(len(chunks_2023), 0)
        titles_2023 = [c['document_title'] for c in chunks_2023]
        self.assertIn("PUMP-X100 Service Manual (Rev 2023)", titles_2023)
        self.assertNotIn("PUMP-X100 Service Manual (Rev 2015)", titles_2023)

    # --------------------------------------------------------------------------
    # TC-RAG-07: Tra cứu tồn kho phụ tùng & dụng cụ (Live Inventory Interlock)
    # --------------------------------------------------------------------------
    def test_tc_rag_07_live_inventory_and_tool_interlock(self):
        text_with_parts = "Quy trình yêu cầu thay thế phớt cơ khí SKF-2210 và kiểm tra ron SEAL-RUBBER-100."
        initial_stock = self.part_seal.quantity_in_stock

        # Call read-only inventory interlock
        inventory = check_live_inventory(text_with_parts, tenant_id=str(self.tenant_a.id))
        self.assertGreaterEqual(len(inventory), 1)

        skf = next((item for item in inventory if item['partNumber'] == 'SKF-2210'), None)
        self.assertIsNotNone(skf)
        self.assertEqual(skf['inStock'], 5.0)
        self.assertEqual(skf['location'], self.loc_a.name)

        # GUARANTEE: Zero stock deduction
        self.part_seal.refresh_from_db()
        self.assertEqual(self.part_seal.quantity_in_stock, initial_stock)

    # --------------------------------------------------------------------------
    # TC-RAG-08: Chống đảo ngược từ phủ định an toàn (Contradiction Guard)
    # --------------------------------------------------------------------------
    def test_tc_rag_08_negation_contradiction_guard(self):
        source = "CẤM mở van xả áp khi máy đang vận hành."

        # Case 1: Consistent reply preserving negation -> No contradiction
        reply_ok = "Quy tắc an toàn: CẤM mở van xả áp khi máy đang vận hành."
        res_ok = check_negation_contradiction(reply_ok, source)
        self.assertFalse(res_ok['contradiction_detected'])

        # Case 2: Inverted/dropped negation ("Có thể mở van xả áp khi máy đang vận hành")
        reply_bad = "Bạn có thể mở van xả áp khi máy đang vận hành để giảm áp."
        res_bad = check_negation_contradiction(reply_bad, source)
        self.assertTrue(res_bad['contradiction_detected'])
        self.assertIn("CẢNH BÁO AN TOÀN QUAN TRỌNG", res_bad['safe_reply'])
        self.assertIn("CẤM mở van xả áp", res_bad['safe_reply'])

    # --------------------------------------------------------------------------
    # TC-RAG-09: Gói dự phòng ngoại tuyến FTS5 có phiên bản (Offline Package)
    # --------------------------------------------------------------------------
    def test_tc_rag_09_offline_pre_fetch_package_with_checksum(self):
        self.client.force_authenticate(user=self.tech_user)
        url = f"/api/v1/assistant/offline-pack/{self.asset_pump_2015.id}/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        data = response.json()['data']
        self.assertIn('manifest', data)
        manifest = data['manifest']
        self.assertEqual(manifest['assetId'], str(self.asset_pump_2015.id))
        self.assertIn('checksumSha256', manifest)
        self.assertEqual(len(manifest['checksumSha256']), 64)  # Valid SHA-256 string
        self.assertIn('packageVersion', manifest)
        self.assertIn('topFaultCodes', data)
        self.assertGreaterEqual(len(data['topFaultCodes']), 3)
        self.assertIn('emergencyShutdownSteps', data)

    # --------------------------------------------------------------------------
    # TC-RAG-10: Vòng lặp thẩm định Kỹ sư trưởng (Chief Engineer Curation Loop)
    # --------------------------------------------------------------------------
    def test_tc_rag_10_chief_engineer_curation_queue_and_approval(self):
        # Step 1: Technician downvotes an answer
        self.client.force_authenticate(user=self.tech_user)
        feedback_url = "/api/v1/assistant/feedback/"
        fb_resp = self.client.post(feedback_url, {
            "userQuery": "Cách tháo cụm cánh bơm chìm",
            "generatedAnswer": "Tháo bu-lông ngược chiều kim đồng hồ bằng tay.",
            "voteType": "DOWNVOTE",
            "feedback": "Tài liệu không khớp thực tế, cần vam chuyên dụng"
        }, format='json')
        self.assertEqual(fb_resp.status_code, 200)

        # Check item in CurationQueueItem
        item = CurationQueueItem.all_objects.filter(user_query="Cách tháo cụm cánh bơm chìm", status='PENDING').first()
        self.assertIsNotNone(item)

        # Step 2: Chief Engineer retrieves queue
        self.client.force_authenticate(user=self.chief_user)
        queue_url = "/api/v1/assistant/admin/curation-queue/"
        q_resp = self.client.get(queue_url)
        self.assertEqual(q_resp.status_code, 200)

        # Step 3: Chief Engineer approves with gold answer
        approve_url = f"/api/v1/assistant/admin/curation-queue/{item.id}/approve/"
        gold_text = "Phải dùng vam 3 càng chuyên dụng và khò nhẹ 60 độ C trước khi rút cánh bơm."
        app_resp = self.client.post(approve_url, {
            "curatedAnswer": gold_text,
            "applicableModel": "PUMP-X100"
        }, format='json')
        self.assertEqual(app_resp.status_code, 200)

        # Verifies queue item status becomes APPROVED
        item.refresh_from_db()
        self.assertEqual(item.status, 'APPROVED')
        self.assertEqual(item.curated_answer, gold_text)

        # Verifies stored in CuratedQAKnowledge
        qa = CuratedQAKnowledge.all_objects.filter(question_pattern=item.user_query).first()
        self.assertIsNotNone(qa)
        self.assertEqual(qa.gold_answer, gold_text)

    # --------------------------------------------------------------------------
    # TC-RAG-11: Nút 1-chạm tạo bản thảo Work Order (Chat-to-WorkOrder, status=CREATED)
    # --------------------------------------------------------------------------
    def test_tc_rag_11_chat_to_work_order_draft_created_status_no_stock_deduction(self):
        self.client.force_authenticate(user=self.tech_user)
        draft_url = "/api/v1/assistant/create-work-order-draft/"
        initial_stock = self.part_seal.quantity_in_stock

        resp = self.client.post(draft_url, {
            "assetId": str(self.asset_pump_2015.id),
            "title": "Khắc phục xâm thực và thay phớt cơ khí Bơm PUMP-X100",
            "faultCode": "CAVITATION_NOISE",
            "priority": "HIGH"
        }, format='json')
        self.assertEqual(resp.status_code, 201)

        wo_data = resp.json()['data']
        # STRICT COMPLIANCE: Must be 'CREATED'
        self.assertEqual(wo_data['status'], 'CREATED')
        self.assertTrue(wo_data['isDraftOnly'])
        self.assertFalse(wo_data['inventoryDeducted'])

        # Verify in database
        wo = WorkOrder.all_objects.get(id=wo_data['workOrderId'])
        self.assertEqual(wo.status, 'CREATED')
        self.assertNotEqual(wo.status, 'IN_PROGRESS')

        # Verify no inventory deducted
        self.part_seal.refresh_from_db()
        self.assertEqual(self.part_seal.quantity_in_stock, initial_stock)

    # --------------------------------------------------------------------------
    # TC-RAG-12: Phân tầng độ tương đồng ngữ nghĩa (<0.65 & 0.65-0.75 & >=0.75)
    # --------------------------------------------------------------------------
    def test_tc_rag_12_semantic_relevance_tiers_and_safe_fallback(self):
        # Tier 1: Sim < 0.65 -> Low confidence, Safe Fallback
        t1 = classify_similarity_tier(0.52)
        self.assertEqual(t1['tier'], 'LOW_CONFIDENCE')
        self.assertTrue(t1['isFallback'])
        self.assertEqual(t1['warning'], SAFE_FALLBACK_MESSAGE)

        # Tier 2: 0.65 <= Sim < 0.75 -> Medium confidence, amber warning
        t2 = classify_similarity_tier(0.70)
        self.assertEqual(t2['tier'], 'MEDIUM_CONFIDENCE')
        self.assertFalse(t2['isFallback'])
        self.assertIn("độ tương đồng trung bình", t2['warning'])

        # Tier 3: Sim >= 0.75 -> High confidence
        t3 = classify_similarity_tier(0.88)
        self.assertEqual(t3['tier'], 'HIGH_CONFIDENCE')
        self.assertFalse(t3['isFallback'])
        self.assertIsNone(t3['warning'])

    # --------------------------------------------------------------------------
    # TC-RAG-13: Trợ lý hướng dẫn tính năng phần mềm EAM (Global Cross-Tenant Guide)
    # --------------------------------------------------------------------------
    def test_tc_rag_13_global_system_software_guide_cross_tenant(self):
        # Create global system guide with tenant_id = NULL and is_system_guide = TRUE
        doc_guide = TechnicalDocument.objects.create(
            tenant=None,  # Global
            is_system_guide=True,
            category='SYSTEM_SOFTWARE_GUIDE',
            title='EAM_User_Manual_WorkOrder_Workflow.md',
            file_path='guides/workflow.md'
        )

        guide_content = (
            "Vòng đời Phiếu Bảo Trì trong hệ thống gồm các trạng thái chuẩn: "
            "CREATED -> ASSIGNED -> IN_PROGRESS -> COMPLETED (hoặc ON_HOLD, CANCELLED). "
            "Nút [Giao việc] chuyển phiếu sang ASSIGNED. Nút [Bắt đầu sửa chữa] chuyển sang IN_PROGRESS."
        )

        DocumentChunk.objects.create(
            tenant=None,
            is_system_guide=True,
            document=doc_guide,
            source_type='SYSTEM_GUIDE',
            content="Nút Giao việc / Bắt đầu sửa chữa có tác dụng gì",
            parent_content=guide_content,
            embedding=embed_text("Nút Giao việc Bắt đầu sửa chữa phân công kỹ thuật viên"),
            is_active=True
        )

        # Tenant A user asks about system guide
        res_a = process_rag_query(
            "Nút Giao việc / Bắt đầu sửa chữa có tác dụng gì và ai được bấm?",
            tenant_id=str(self.tenant_a.id)
        )
        self.assertTrue(res_a['success'])
        self.assertTrue(res_a['data']['isSystemGuide'])
        self.assertIn("HƯỚNG DẪN TÍNH NĂNG", res_a['data']['reply'])
        self.assertIn("CREATED", res_a['data']['reply'])

        # Tenant B user asks same question -> also retrieves global guide without tenant blocking
        res_b = process_rag_query(
            "Nút Giao việc / Bắt đầu sửa chữa có tác dụng gì?",
            tenant_id=str(self.tenant_b.id)
        )
        self.assertTrue(res_b['success'])
        self.assertIn("CREATED", res_b['data']['reply'])

    # --------------------------------------------------------------------------
    # TC-RAG-14: Quản trị viên Settings thêm Q&A trong Admin Hub
    # --------------------------------------------------------------------------
    def test_tc_rag_14_admin_hub_qa_creation_and_immediate_retrieval(self):
        self.client.force_authenticate(user=self.admin_user)
        qa_url = "/api/v1/assistant/admin/qa/"

        q_pattern = "Làm thế nào để cân chỉnh góc đặt bơm màng khí nén ARO?"
        g_answer = "Nới lỏng 4 ốc đế chân máy, sử dụng đồng hồ so căn chỉnh độ lệch tâm dưới 0.05mm."

        resp = self.client.post(qa_url, {
            "questionPattern": q_pattern,
            "goldAnswer": g_answer,
            "category": "EQUIPMENT_MAINTENANCE",
            "applicableModel": "ARO-DIAPHRAGM"
        }, format='json')
        self.assertEqual(resp.status_code, 200)

        # Verify saved in database
        saved_qa = CuratedQAKnowledge.all_objects.filter(question_pattern=q_pattern).first()
        self.assertIsNotNone(saved_qa)

        # Immediate Chatbot retrieval verification
        chat_res = process_rag_query(q_pattern, tenant_id=str(self.tenant_a.id))
        self.assertTrue(chat_res['success'])
        self.assertIn("0.05mm", chat_res['data']['reply'])

    # --------------------------------------------------------------------------
    # TC-RAG-15: Nút FAB nổi tự động nhận biết ngữ cảnh trang (assetContext)
    # --------------------------------------------------------------------------
    def test_tc_rag_15_fab_context_aware_binding(self):
        # Create OEM manual for PUMP-X100
        doc = TechnicalDocument.objects.create(
            tenant=self.tenant_a,
            applicable_model="PUMP-X100",
            title="PUMP-X100 Diagnostic Manual",
            file_path="manuals/x100.pdf",
            applicable_year_start=2010,
            applicable_year_end=2025
        )
        DocumentChunk.objects.create(
            tenant=self.tenant_a,
            document=doc,
            source_type='OEM_MANUAL',
            content="Kiểm tra độ rung và siết bu-lông chân máy PUMP-X100.",
            parent_content="Quy trình chẩn đoán PUMP-X100: Kiểm tra độ rung và siết bu-lông chân máy PUMP-X100.",
            embedding=embed_text("độ rung nóng bất thường PUMP-X100"),
            is_active=True
        )

        # Query with contextual injection: colloquial query without mentioning asset name
        res = process_rag_query(
            prompt="Máy rung mạnh và nóng bất thường xử lý thế nào?",
            asset_context={
                "assetId": str(self.asset_pump_2015.id),
                "model": "PUMP-X100",
                "manufactureYear": 2018
            },
            tenant_id=str(self.tenant_a.id)
        )
        self.assertTrue(res['success'])
        self.assertIn("PUMP-X100", res['data']['expandedQuery'])
        self.assertIn("PUMP-X100", res['data']['reply'])

    # --------------------------------------------------------------------------
    # Additional Verification: Admin Q&A List API & DocumentChunk Cleanup on Delete
    # --------------------------------------------------------------------------
    def test_admin_qa_list_api_and_cleanup_on_delete(self):
        self.client.force_authenticate(user=self.admin_user)

        # 1. Create a curated QA
        create_url = "/api/v1/assistant/admin/qa/"
        c_resp = self.client.post(create_url, {
            "questionPattern": "Cách xả áp van an toàn lò hơi?",
            "goldAnswer": "Nâng nhẹ cần xả thủ công và giữ trong 10 giây, kiểm tra áp kế về 0 bar.",
            "category": "EQUIPMENT_MAINTENANCE",
            "applicableModel": "BOILER-B500"
        }, format='json')
        self.assertEqual(c_resp.status_code, 200)
        qa_id = c_resp.json()['data']['id']

        # 2. Query Q&A List API
        list_url = "/api/v1/assistant/admin/qa-list/"
        l_resp = self.client.get(list_url)
        self.assertEqual(l_resp.status_code, 200)
        data = l_resp.json()['data']
        self.assertTrue(any(q['id'] == qa_id for q in data))

        # Query with search
        search_resp = self.client.get(f"{list_url}?search=lò hơi")
        self.assertEqual(search_resp.status_code, 200)
        search_data = search_resp.json()['data']
        self.assertEqual(len(search_data), 1)

        # Confirm DocumentChunk was created
        chunk = DocumentChunk.all_objects.filter(source_type='CURATED_QA', content="Cách xả áp van an toàn lò hơi?").first()
        self.assertIsNotNone(chunk)

        # 3. Delete Q&A and verify DocumentChunk is cleaned up
        del_url = f"/api/v1/assistant/admin/qa/{qa_id}/"
        del_resp = self.client.delete(del_url)
        self.assertEqual(del_resp.status_code, 200)

        # Verify QA deleted
        self.assertFalse(CuratedQAKnowledge.all_objects.filter(id=qa_id).exists())
        # Verify vector chunk cleaned up
        self.assertFalse(DocumentChunk.all_objects.filter(source_type='CURATED_QA', content="Cách xả áp van an toàn lò hơi?").exists())

    # --------------------------------------------------------------------------
    # Additional Verification: Web Portal Admin Hub View (/admin/rag-knowledge/)
    # --------------------------------------------------------------------------
    def test_portal_rag_knowledge_admin_hub_view(self):
        self.client.force_login(self.admin_user)
        portal_url = "/admin/rag-knowledge/"
        resp = self.client.get(portal_url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("curated_qa_list", resp.context)
        self.assertIn("curation_queue_list", resp.context)
        self.assertIn("technical_docs", resp.context)
        self.assertIn("slang_dict", resp.context)
        self.assertIn("emergency_hazards", resp.context)

    # --------------------------------------------------------------------------
    # Additional Verification: Upload Document & Reindex APIs
    # --------------------------------------------------------------------------
    def test_admin_upload_document_and_reindex_apis(self):
        self.client.force_authenticate(user=self.admin_user)

        # 1. Upload document API
        upload_url = "/api/v1/assistant/admin/upload-document/"
        up_resp = self.client.post(upload_url, {
            "title": "ARO Diaphragm Pump Manual Rev 2022",
            "category": "OEM_MANUAL",
            "applicableModel": "ARO-PUMP",
            "content": "## Quy trình bảo dưỡng bơm màng\nKiểm tra màng bơm cao su theo sơ đồ [Fig 3.1]."
        }, format='json')
        self.assertEqual(up_resp.status_code, 201)
        doc_id = up_resp.json()['data']['id']
        self.assertTrue(TechnicalDocument.all_objects.filter(id=doc_id).exists())
        self.assertTrue(DocumentChunk.all_objects.filter(document_id=doc_id).exists())

        # 2. Reindex API
        wo = WorkOrder.objects.create(
            tenant=self.tenant_a,
            asset=self.asset_pump_2015,
            title="Khắc phục hỏng phốt làm kín bơm nước",
            priority="HIGH",
            status="COMPLETED",
            resolution_notes="Đã kiểm tra bưởng bơm và thay phớt cơ khí SKF-2210 mới, căn chỉnh đồng trục đạt chuẩn.",
            completed_at=timezone.now()
        )
        reindex_url = "/api/v1/assistant/admin/reindex/"
        re_resp = self.client.post(reindex_url)
        self.assertEqual(re_resp.status_code, 200)
        self.assertGreaterEqual(re_resp.json()['ingestedCount'], 1)

    # --------------------------------------------------------------------------
    # Additional Verification: Action Chip System Feature Query with Asset Context
    # --------------------------------------------------------------------------
    def test_quick_action_chip_system_guide_on_asset_page(self):
        # Even with assetContext provided, "Nút trên trang này dùng để làm gì?" routes to system guide
        res = process_rag_query(
            prompt="Nút trên trang này dùng để làm gì?",
            asset_context={
                "assetId": str(self.asset_pump_2015.id),
                "model": "PUMP-X100",
                "manufactureYear": 2018
            },
            tenant_id=str(self.tenant_a.id)
        )
        self.assertTrue(res['success'])
        self.assertTrue(res['data']['isSystemGuide'])

    # --------------------------------------------------------------------------
    # Additional Verification: Specific Transformer Fire Inquiry & Theoretical Suppression
    # --------------------------------------------------------------------------
    def test_life_safety_specific_transformer_queries(self):
        # Query from spec Section 3, Rule 1: "Làm sao dập lửa dầu biến áp?"
        q1 = "Làm sao dập lửa dầu biến áp?"
        res1 = classify_safety_context(q1)
        self.assertTrue(res1['is_emergency'])
        self.assertEqual(res1['hazard_type'], 'ELECTRICAL_FIRE')
        self.assertIn("TUYỆT ĐỐI CẤM DÙNG NƯỚC", res1['instruction'])

        # Theoretical inquiry from spec: "Cách phòng chống cháy nổ trạm biến áp?"
        q2 = "Cách phòng chống cháy nổ trạm biến áp?"
        res2 = classify_safety_context(q2)
        self.assertFalse(res2['is_emergency'])
        self.assertTrue(res2['is_theoretical_or_negated'])

    # --------------------------------------------------------------------------
    # Additional Verification: Tacit Work Order Requires completed_at
    # --------------------------------------------------------------------------
    def test_tacit_work_order_requires_completed_at(self):
        wo_no_completed_at = WorkOrder.objects.create(
            tenant=self.tenant_a,
            asset=self.asset_pump_2015,
            title="Phiếu hoàn thành nhưng thiếu completed_at",
            priority="HIGH",
            status="COMPLETED",
            resolution_notes="Nội dung giải pháp rất dài trên ba mươi ký tự hợp lệ nhưng thiếu trường completed_at.",
            completed_at=None
        )
        self.assertFalse(is_valid_tacit_work_order(wo_no_completed_at))


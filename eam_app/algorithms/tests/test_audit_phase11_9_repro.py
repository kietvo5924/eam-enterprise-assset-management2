"""
Audit Phase 11.9 Reproduction Test Suite.
Tests the 7 suspected issues identified in the audit:
1. Safety Classifier negation issues ('tránh', 'không có')
2. Contradiction Guard displaying dangerous reply
3. Tenant Isolation & RBAC vulnerabilities
4. RAG Retrieval model/year/serial filtering for OEM, Tacit, Curated QA
5. System Knowledge Scanner category and Work Order change ingestion
6. Offline Pack tenant isolation, Inventory fake location, Tool availability, Diagram fallback
7. Upload file storage and Safety Configuration POST support
"""

import sys
import subprocess
import os
import uuid
from datetime import date, timedelta
from decimal import Decimal
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from core.models import Tenant
from core.tenant_context import clear_current_tenant
from users.models import User, Role, Permission
from assets.models import Asset, AssetCategory, Location, SparePart, Tool, ToolInstance
from workorders.models import WorkOrder
from assistant.models import TechnicalDocument, DocumentChunk, CuratedQAKnowledge, CurationQueueItem
from assistant.system_knowledge_scanner import scan_and_index_system_knowledge
from algorithms.rag_chatbot import (
    classify_safety_context,
    check_negation_contradiction,
    generate_offline_package,
    check_live_inventory,
    retrieve_relevant_chunks,
    process_rag_query,
    embed_text,
    save_persisted_safety_config,
    load_persisted_safety_config,
    ensure_safety_config_loaded,
)
from algorithms.rag_chatbot.constants import SLANG_TECHNICAL_DICTIONARY
from algorithms.rag_chatbot.query_expansion import expand_slang_query
from assistant.auto_ingest import ingest_completed_workorders


class AuditPhase119ReproductionTests(TestCase):
    def setUp(self):
        clear_current_tenant()
        self.client = APIClient()

        # Permissions
        self.perm_manage_knowledge, _ = Permission.objects.get_or_create(
            id='assistant:manage_knowledge',
            defaults={'name': 'Manage Knowledge', 'description': 'Manage AI Knowledge'}
        )
        self.perm_configure_safety, _ = Permission.objects.get_or_create(
            id='assistant:configure_safety',
            defaults={'name': 'Configure Safety', 'description': 'Configure Life Safety Interlocks'}
        )
        # Tenants
        self.tenant_a = Tenant.objects.create(name="Tenant A", tenant_code=f"T-A-{uuid.uuid4().hex[:4]}")
        self.tenant_b = Tenant.objects.create(name="Tenant B", tenant_code=f"T-B-{uuid.uuid4().hex[:4]}")

        self.role_admin_a = Role.objects.create(name='ADMIN', tenant=self.tenant_a)
        self.role_admin_a.permissions.add(self.perm_manage_knowledge, self.perm_configure_safety)

        self.role_admin_b = Role.objects.create(name='ADMIN', tenant=self.tenant_b)
        self.role_admin_b.permissions.add(self.perm_manage_knowledge, self.perm_configure_safety)

        self.role_safety_officer = Role.objects.create(name='SAFETY_OFFICER', tenant=self.tenant_a)
        self.role_safety_officer.permissions.add(self.perm_configure_safety)

        # Users
        self.user_a = User.objects.create_user(
            username=f'user_a_{uuid.uuid4().hex[:6]}',
            email='user_a@test.local',
            password='password123',
            tenant=self.tenant_a
        )
        self.user_a.roles.add(self.role_admin_a)

        self.user_b = User.objects.create_user(
            username=f'user_b_{uuid.uuid4().hex[:6]}',
            email='user_b@test.local',
            password='password123',
            tenant=self.tenant_b
        )
        self.user_b.roles.add(self.role_admin_b)

        self.user_safety = User.objects.create_user(
            username=f'user_safety_{uuid.uuid4().hex[:6]}',
            email='safety@test.local',
            password='password123',
            tenant=self.tenant_a
        )
        self.user_safety.roles.add(self.role_safety_officer)

        self.tenant_system, _ = Tenant.objects.get_or_create(
            id='00000000-0000-0000-0000-000000000000',
            defaults={'name': 'System Administration', 'tenant_code': 'SYSTEM'}
        )
        self.superuser = User.all_objects.create_user(
            username=f'super_{uuid.uuid4().hex[:6]}',
            email='super@test.local',
            password='password123',
            tenant=self.tenant_system,
            is_superuser=True,
            is_staff=True
        )

        # Assets
        self.cat_a = AssetCategory.objects.create(tenant=self.tenant_a, name="Bơm A")
        self.cat_b = AssetCategory.objects.create(tenant=self.tenant_b, name="Bơm B")

        self.asset_a = Asset.objects.create(
            tenant=self.tenant_a,
            category=self.cat_a,
            name="Máy Bơm A PUMP-X100",
            model="PUMP-X100",
            serial_number="SN-A-001",
            status="OPERATIONAL",
            value=Decimal("10000000"),
            purchase_cost=Decimal("10000000"),
            purchase_date="2020-01-01"
        )

        self.asset_b = Asset.objects.create(
            tenant=self.tenant_b,
            category=self.cat_b,
            name="Máy Nén Khí B COMP-Y200",
            model="COMP-Y200",
            serial_number="SN-B-002",
            status="OPERATIONAL",
            value=Decimal("20000000"),
            purchase_cost=Decimal("20000000"),
            purchase_date="2021-01-01"
        )

    # -------------------------------------------------------------------------
    # Issue 1: Safety Classifier Negation
    # -------------------------------------------------------------------------
    def test_repro_issue1_safety_classifier_with_tranh_and_khong_co(self):
        # 1a. User asks how to avoid fire spreading in active transformer oil fire
        q1 = "Máy biến áp đang cháy dầu, làm sao tránh lửa lan rộng?"
        res1 = classify_safety_context(q1)
        self.assertTrue(res1['is_emergency'], "Prompt with active fire and 'tránh' must still be classified as emergency!")
        self.assertEqual(res1['hazard_type'], 'ELECTRICAL_FIRE')

        # 1b. User mentions electrical fire and 'tránh bị giật'
        q2 = "Tủ điện đang chập điện bốc khói, làm sao tránh bị phóng điện?"
        res2 = classify_safety_context(q2)
        self.assertTrue(res2['is_emergency'], "Prompt with active electrical fire and 'tránh' must be classified as emergency!")

        # 1c. User mentions gas leak and 'không có'
        q3 = "Mùi gas nồng nặc và xì khí gas, ở đây không có mặt nạ phòng độc thì làm sao?"
        res3 = classify_safety_context(q3)
        self.assertTrue(res3['is_emergency'], "Prompt with gas leak and 'không có' must be classified as emergency!")

        # 1d. Active fire containment question with 'không cháy lan' must be EMERGENCY
        q_spread1 = "Cháy tủ điện khẩn cấp, làm sao để không cháy lan?"
        res_spread1 = classify_safety_context(q_spread1)
        self.assertTrue(res_spread1['is_emergency'], "Active fire with 'không cháy lan' MUST be classified as emergency!")
        self.assertEqual(res_spread1['hazard_type'], 'ELECTRICAL_FIRE')

        q_spread2 = "Máy biến áp đang cháy dầu, dập ngay kẻo không cháy hết cả xưởng"
        res_spread2 = classify_safety_context(q_spread2)
        self.assertTrue(res_spread2['is_emergency'], "Active fire with spread risk must be classified as emergency!")

        # 1e. Safe negation should STILL work when the hazard itself is negated!
        q4 = "Máy không bị cháy nhưng rung mạnh"
        res4 = classify_safety_context(q4)
        self.assertFalse(res4['is_emergency'], "Safe negation of hazard itself must NOT be classified as emergency")
        self.assertTrue(res4['is_theoretical_or_negated'])

    # -------------------------------------------------------------------------
    # Issue 2: Contradiction Guard Safe Reply
    # -------------------------------------------------------------------------
    def test_repro_issue2_contradiction_guard_must_not_display_dangerous_reply(self):
        source = "Quy tắc an toàn: CẤM mở van xả áp khi máy đang vận hành."
        dangerous_reply = "Bạn có thể mở van xả áp khi máy đang vận hành để giảm áp lực đường ống."
        guard_res = check_negation_contradiction(dangerous_reply, source)
        self.assertTrue(guard_res['contradiction_detected'])
        # Dangerous reply should NOT be contained in safe_reply
        self.assertNotIn(
            dangerous_reply,
            guard_res['safe_reply'],
            "Contradiction Guard must suppress/discard the dangerous reply rather than displaying it to the user!"
        )

    # -------------------------------------------------------------------------
    # Issue 3: Tenant Isolation & RBAC
    # -------------------------------------------------------------------------
    def test_repro_issue3_tenant_isolation_work_order_draft(self):
        # User A attempts to create a work order draft targeting Tenant B's asset
        self.client.force_authenticate(user=self.user_a)
        response = self.client.post('/api/v1/assistant/create-work-order-draft/', {
            'assetId': str(self.asset_b.id),
            'title': 'Sửa chữa trái phép asset B'
        }, format='json')
        # Should NOT succeed with asset_b
        if response.status_code == 201:
            wo_id = response.data['data']['workOrderId']
            wo = WorkOrder.objects.get(id=wo_id)
            self.assertEqual(wo.tenant_id, self.tenant_a.id)
            self.assertNotEqual(wo.asset_id, self.asset_b.id, "User A must not create work order on Tenant B's asset!")
        else:
            self.assertIn(response.status_code, [400, 403, 404])

    def test_repro_issue3_tenant_isolation_offline_pack(self):
        # User A requests offline pack for Tenant B's asset
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(f'/api/v1/assistant/offline-pack/{self.asset_b.id}/')
        # Should NOT return 200 with Tenant B's asset info
        self.assertIn(response.status_code, [403, 404], "User A must not access Tenant B's offline pack!")

    def test_repro_issue3_tenant_isolation_qa_edit_delete(self):
        # Create QA in Tenant B
        qa_b = CuratedQAKnowledge.objects.create(
            tenant_id=self.tenant_b.id,
            category='EQUIPMENT_MAINTENANCE',
            question_pattern='Bảo trì máy B thế nào?',
            gold_answer='Quy trình chuẩn cho máy B.'
        )

        # User A attempts to edit QA of Tenant B
        self.client.force_authenticate(user=self.user_a)
        res_edit = self.client.post('/api/v1/assistant/admin/qa/', {
            'id': str(qa_b.id),
            'questionPattern': 'Bị hack bởi Tenant A',
            'goldAnswer': 'Dữ liệu đã bị phá'
        }, format='json')
        self.assertIn(res_edit.status_code, [403, 404], "Tenant A must not edit Tenant B's Q&A!")
        qa_b.refresh_from_db()
        self.assertEqual(qa_b.question_pattern, 'Bảo trì máy B thế nào?')

        # User A attempts to delete QA of Tenant B
        res_del = self.client.delete(f'/api/v1/assistant/admin/qa/{qa_b.id}/')
        self.assertIn(res_del.status_code, [403, 404], "Tenant A must not delete Tenant B's Q&A!")
        self.assertTrue(CuratedQAKnowledge.objects.filter(id=qa_b.id).exists())

    def test_repro_issue3_rbac_non_superuser_cannot_create_global_guide(self):
        # User A is regular tenant admin, not superuser
        self.client.force_authenticate(user=self.user_a)
        res = self.client.post('/api/v1/assistant/admin/qa/', {
            'questionPattern': 'Toàn cục trái phép',
            'goldAnswer': 'Dữ liệu toàn cục trái phép',
            'isSystemGuide': True
        }, format='json')
        # If created, tenant_id must NOT be None (must be isolated to tenant_a) or return 403
        if res.status_code in [200, 201]:
            created_qa = CuratedQAKnowledge.objects.get(id=res.data['data']['id'])
            self.assertIsNotNone(created_qa.tenant_id, "Non-superuser must not create global knowledge (tenant_id=None)!")
        else:
            self.assertEqual(res.status_code, 403)

    # -------------------------------------------------------------------------
    # Issue 6: Inventory fake location and tool inspection
    # -------------------------------------------------------------------------
    def test_repro_issue6_inventory_location_not_faked(self):
        # Create spare part without location
        part = SparePart.objects.create(
            tenant=self.tenant_a,
            name="Vòng bi test không kệ",
            part_number="BEARING-TEST-99",
            quantity_in_stock=Decimal("10"),
            location=None
        )
        matches = check_live_inventory("Cần thay vòng bi BEARING-TEST-99", tenant_id=str(self.tenant_a.id))
        self.assertEqual(len(matches), 1)
        self.assertNotEqual(matches[0]['location'], "Kệ A1-01", "Should not hallucinate 'Kệ A1-01' when location is None!")

        # Tool without location must not hallucinate fake workshop room
        tool = Tool.objects.create(
            tenant=self.tenant_a,
            code="TOOL-CALIPER-01",
            name="Thước kẹp điện tử Mitutoyo",
            location=None,
            available_quantity=2
        )
        tool_matches = check_live_inventory("Cần dùng thước kẹp TOOL-CALIPER-01", tenant_id=str(self.tenant_a.id))
        self.assertTrue(len(tool_matches) >= 1)
        tool_item = [m for m in tool_matches if m['partNumber'] == 'TOOL-CALIPER-01'][0]
        self.assertNotEqual(tool_item['location'], "Phòng dụng cụ cơ điện", "Tool location must not hallucinate fake room!")
        self.assertTrue(tool_item['isTool'])

    # -------------------------------------------------------------------------
    # Issue 4: RAG Retrieval model and tacit/QA filtering
    # -------------------------------------------------------------------------
    def test_repro_issue4_rag_retrieval_model_filtering(self):
        # Create QA for Model PUMP-X100
        qa_pump = CuratedQAKnowledge.objects.create(
            tenant_id=self.tenant_a.id,
            category='EQUIPMENT_MAINTENANCE',
            question_pattern='Cách xả bọt khí bơm ly tâm PUMP-X100',
            gold_answer='Mở ốc xả gió trên thân bơm PUMP-X100.',
            applicable_model='PUMP-X100',
            applicable_year_start=2005,
            applicable_year_end=2015
        )
        vec = [0.1] * 384
        DocumentChunk.objects.create(
            tenant_id=self.tenant_a.id,
            source_type='CURATED_QA',
            content='Cách xả bọt khí bơm ly tâm PUMP-X100',
            parent_content='Mở ốc xả gió trên thân bơm PUMP-X100.',
            embedding=vec,
            is_active=True
        )

        # 4a. Query for a completely different model: CHILLER-999
        chunks = retrieve_relevant_chunks(
            query_text="Cách xả bọt khí",
            tenant_id=str(self.tenant_a.id),
            asset_model="CHILLER-999",
            limit=5
        )
        # Should NOT return chunk belonging to PUMP-X100 when querying CHILLER-999!
        for c in chunks:
            if c.get('source_type') == 'CURATED_QA':
                self.assertNotIn("PUMP-X100", c['content'], "CURATED_QA for PUMP-X100 should not be returned when asset_model is CHILLER-999!")

        # 4b. Query for PUMP-X100 with manufacture_year=None: MUST NOT default to 2020 and exclude 2005-2015!
        chunks_none_year = retrieve_relevant_chunks(
            query_text="Cách xả bọt khí",
            tenant_id=str(self.tenant_a.id),
            asset_model="PUMP-X100",
            manufacture_year=None,
            limit=5
        )
        found_pump = any("PUMP-X100" in c['content'] for c in chunks_none_year)
        self.assertTrue(found_pump, "Querying with manufacture_year=None must not exclude valid records by hardcoded 2020 year!")

    # -------------------------------------------------------------------------
    # Issue 5: Work Order update in auto-ingest and category choices
    # -------------------------------------------------------------------------
    def test_repro_issue5_workorder_change_and_category_match(self):
        # 5a. Check Category choices match between scanner and models
        from assistant.system_knowledge_scanner import PORTAL_MODULES_METADATA
        valid_cats = [c[0] for c in CuratedQAKnowledge.CATEGORY_CHOICES]
        self.assertIn('SYSTEM_FEATURE_GUIDE', valid_cats)
        # Scanner was using 'SYSTEM_FEATURE' which is NOT in valid_cats
        self.assertNotIn('SYSTEM_FEATURE', valid_cats)

        # 5b. Work Order resolution notes change
        from datetime import datetime, timezone
        wo = WorkOrder.objects.create(
            tenant_id=self.tenant_a.id,
            asset=self.asset_a,
            title="Sửa rò rỉ bưởng bơm",
            description="Mô tả sự cố",
            resolution_notes="Đã siết lại bu lông bưởng số 1 và 2 và thay gioăng đệm.",
            status="COMPLETED",
            completed_at=datetime.now(timezone.utc),
            priority="HIGH",
            type="CORRECTIVE"
        )
        # First ingestion
        ingested = ingest_completed_workorders(tenant_id=str(self.tenant_a.id))
        self.assertEqual(ingested, 1)
        chunk = DocumentChunk.objects.get(work_order=wo)
        self.assertIn("siết lại bu lông", chunk.parent_content)

        # Now engineer updates the resolution notes with deeper findings
        wo.resolution_notes = "Phát hiện vết nứt chân bưởng, đã hàn đắp và tôi cứng lại."
        wo.save()

        # Ingest again
        ingested_again = ingest_completed_workorders(tenant_id=str(self.tenant_a.id))
        chunk.refresh_from_db()
        self.assertIn("vết nứt chân bưởng", chunk.parent_content, "DocumentChunk should update when Work Order notes are modified!")

        # Now work order is CANCELLED or REOPENED
        wo.status = "CANCELLED"
        wo.save()
        ingest_completed_workorders(tenant_id=str(self.tenant_a.id))
        self.assertFalse(DocumentChunk.objects.filter(work_order=wo, is_active=True).exists(), "Cancelled work orders must be deactivated or deleted from knowledge base!")

        # 5c. Real-time post_save & post_delete signals without manual ingestion call
        wo_signal = WorkOrder.objects.create(
            tenant_id=self.tenant_a.id,
            asset=self.asset_a,
            title="Sự cố rung bạc đạn động cơ chính",
            description="Mô tả rung",
            resolution_notes="Đã kiểm tra khe hở và căn chỉnh độ đồng tâm trục chính bằng laser.",
            status="COMPLETED",
            completed_at=datetime.now(timezone.utc),
            priority="HIGH",
            type="CORRECTIVE"
        )
        wo_signal_id = wo_signal.id
        self.assertTrue(
            DocumentChunk.objects.filter(work_order_id=wo_signal_id, is_active=True).exists(),
            "Creating a completed Work Order must automatically ingest via post_save signal in real-time!"
        )
        wo_signal.delete()
        self.assertFalse(
            DocumentChunk.objects.filter(work_order_id=wo_signal_id).exists(),
            "Deleting a Work Order must automatically purge chunk via post_delete signal in real-time!"
        )

    # -------------------------------------------------------------------------
    # Issue 7: File storage in Upload and Safety Config POST
    # -------------------------------------------------------------------------
    def test_repro_issue7_upload_document_saves_file_and_safety_config_post(self):
        self.client.force_authenticate(user=self.user_a)

        # 7a. Safety Config POST support & persistent reloading
        res_post_safety = self.client.post('/api/v1/assistant/admin/safety-config/', {
            'custom_slang': {'cháy biến áp': 'transformer catastrophic failure'}
        }, format='json')
        self.assertNotEqual(res_post_safety.status_code, 405, "Safety config must support POST method!")
        self.assertEqual(res_post_safety.status_code, 200)

        res_get_safety = self.client.get('/api/v1/assistant/admin/safety-config/')
        self.assertEqual(res_get_safety.status_code, 200)
        self.assertIn('cháy biến áp', res_get_safety.data['data']['slangDictionary'], "Custom slang must persist in safety config!")

        # 7b. Upload document saves actual file content
        test_file = SimpleUploadedFile("manual_test.txt", b"Noi dung so tay van hanh may bom")
        res_upload = self.client.post('/api/v1/assistant/admin/upload-document/', {
            'title': 'Sổ tay Vận hành Test',
            'file': test_file,
            'category': 'OEM_MANUAL'
        }, format='multipart')
        self.assertEqual(res_upload.status_code, 201)
        doc_id = res_upload.data['data']['id']
        doc = TechnicalDocument.objects.get(id=doc_id)
        from django.core.files.storage import default_storage
        self.assertTrue(
            default_storage.exists(doc.file_path),
            f"Original file {doc.file_path} must be saved in storage!"
        )

    # =========================================================================
    # PHASE 11.9 CONTROLLED REGRESSION SUITE (12 MANDATORY AUDIT VALIDATIONS)
    # =========================================================================

    def test_regression_1_multi_worker_safety_configuration_sync(self):
        """1. Cấu hình Safety được cập nhật và worker khác nhận được cấu hình."""
        slang_k = f"slang_sync_{uuid.uuid4().hex[:6]}"
        slang_v = "motor bearing failure vibration"
        
        # Worker 1 writes config
        save_persisted_safety_config(custom_slang={slang_k: slang_v})
        
        # Simulate Worker 2 memory state: slang_k is not yet in its memory dictionary
        if slang_k in SLANG_TECHNICAL_DICTIONARY:
            del SLANG_TECHNICAL_DICTIONARY[slang_k]
        
        # Reset mtime tracker to simulate Worker 2 having never loaded or having stale mtime
        import algorithms.rag_chatbot.safety_config as sc
        sc._last_loaded_mtime = None

        # Worker 2 processes query, which automatically calls ensure_safety_config_loaded()
        expansion = expand_slang_query(f"máy bị {slang_k}")
        self.assertIn(slang_k, expansion['detected_slangs'], "Worker 2 must automatically reload updated safety config from storage!")
        self.assertIn("vibration", expansion['technical_additions'])

        # Real independent OS subprocess verification:
        # Spawns a completely independent Python process with fresh memory space
        cmd = [
            sys.executable,
            "-c",
            "import sys, os; sys.path.insert(0, 'eam_app'); os.environ['DJANGO_SETTINGS_MODULE']='config.settings'; "
            "import django; django.setup(); "
            "from algorithms.rag_chatbot.query_expansion import expand_slang_query; "
            "res = expand_slang_query('máy bị ' + sys.argv[1]); "
            "print('detected:' + str(sys.argv[1] in res['detected_slangs']))",
            slang_k
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=os.getcwd())
        self.assertEqual(proc.returncode, 0, f"Independent worker process failed: {proc.stderr}")
        self.assertIn("detected:True", proc.stdout, "Independent worker process must read latest safety configuration from shared storage!")

        # Clean up
        if slang_k in SLANG_TECHNICAL_DICTIONARY:
            del SLANG_TECHNICAL_DICTIONARY[slang_k]

    def test_regression_2_safety_officer_rbac_access_and_boundaries(self):
        """2. SAFETY_OFFICER truy cập được API và Tab Safety nhưng không có quyền quản trị tri thức ngoài phạm vi."""
        self.client.force_authenticate(user=self.user_safety)

        # 2a. Can GET and POST safety config
        res_get_safety = self.client.get('/api/v1/assistant/admin/safety-config/')
        self.assertEqual(res_get_safety.status_code, 200)

        res_post_safety = self.client.post('/api/v1/assistant/admin/safety-config/', {
            'custom_slang': {'cháy biến áp an toàn': 'transformer arc explosion safety'}
        }, format='json')
        self.assertEqual(res_post_safety.status_code, 200)

        # 2b. Can access Web Portal Tab Safety
        self.client.force_login(self.user_safety)
        res_portal = self.client.get('/portal/rag-knowledge/')
        self.assertEqual(res_portal.status_code, 200)
        self.assertTrue(res_portal.context['can_configure_safety'])
        self.assertFalse(res_portal.context['can_manage'])
        self.assertEqual(res_portal.context['active_tab'], 'safety')

        # 2c. CANNOT manage QA knowledge (403 Forbidden)
        res_qa_create = self.client.post('/api/v1/assistant/admin/qa/', {
            'questionPattern': 'Câu hỏi vượt quyền',
            'goldAnswer': 'Trả lời'
        }, format='json')
        self.assertEqual(res_qa_create.status_code, 403, "SAFETY_OFFICER must NOT have permission to create QA!")

        # 2d. CANNOT upload technical documents (403 Forbidden)
        test_file = SimpleUploadedFile("leak.txt", b"secret info")
        res_upload = self.client.post('/api/v1/assistant/admin/upload-document/', {
            'title': 'Tài liệu vượt quyền',
            'file': test_file
        }, format='multipart')
        self.assertEqual(res_upload.status_code, 403, "SAFETY_OFFICER must NOT have permission to upload docs!")

    def test_regression_3_superuser_ghost_chunk_prevention(self):
        """3. Superuser tạo QA non-system phải có Tenant hợp lệ; cấm Ghost Chunk."""
        self.client.force_authenticate(user=self.superuser)

        # 3a. Superuser creating non-system QA without tenant must return 400
        res_no_tenant = self.client.post('/api/v1/assistant/admin/qa/', {
            'questionPattern': 'Lỗi thiếu tenant',
            'goldAnswer': 'Không được lưu ghost chunk',
            'isSystemGuide': False
        }, format='json')
        self.assertEqual(res_no_tenant.status_code, 400, "Superuser creating non-system QA without tenant must be rejected!")
        self.assertIn("Tenant", res_no_tenant.data.get('error', ''))

        # 3b. Superuser creating non-system QA with invalid tenant must return 400
        res_invalid_tenant = self.client.post('/api/v1/assistant/admin/qa/', {
            'questionPattern': 'Lỗi tenant ảo',
            'goldAnswer': 'Không được lưu ghost chunk',
            'isSystemGuide': False,
            'targetTenantId': str(uuid.uuid4())
        }, format='json')
        self.assertEqual(res_invalid_tenant.status_code, 400)

        # 3c. Superuser creating non-system QA with valid tenant must succeed and link chunk to that tenant
        res_valid = self.client.post('/api/v1/assistant/admin/qa/', {
            'questionPattern': 'Bảo trì bơm chuẩn Tenant A',
            'goldAnswer': 'Quy trình kiểm tra áp suất bưởng bơm',
            'isSystemGuide': False,
            'targetTenantId': str(self.tenant_a.id)
        }, format='json')
        self.assertEqual(res_valid.status_code, 200)
        qa_id = res_valid.data['data']['id']
        qa = CuratedQAKnowledge.objects.get(id=qa_id)
        self.assertEqual(str(qa.tenant_id), str(self.tenant_a.id))
        self.assertFalse(qa.is_system_guide)
        
        chunk = DocumentChunk.objects.filter(content='Bảo trì bơm chuẩn Tenant A').first()
        self.assertIsNotNone(chunk)
        self.assertEqual(str(chunk.tenant_id), str(self.tenant_a.id))
        self.assertFalse(chunk.is_system_guide)

        # 3d. Superuser uploading document non-system without tenant must return 400
        test_file = SimpleUploadedFile("doc.txt", b"Noi dung tai lieu")
        res_doc_no_tenant = self.client.post('/api/v1/assistant/admin/upload-document/', {
            'title': 'Tài liệu không tenant',
            'file': test_file,
            'isSystemGuide': False
        }, format='multipart')
        self.assertEqual(res_doc_no_tenant.status_code, 400)

        # 3e. Non-superuser from Tenant A attempting cross-tenant QA injection targeting Tenant B must return 403
        self.client.force_authenticate(user=self.user_a)
        res_cross_qa = self.client.post('/api/v1/assistant/admin/qa/', {
            'questionPattern': 'Injection vào Tenant B',
            'goldAnswer': 'Dữ liệu lậu',
            'isSystemGuide': False,
            'targetTenantId': str(self.tenant_b.id)
        }, format='json')
        self.assertEqual(res_cross_qa.status_code, 403, "Non-superuser MUST NOT be allowed to create QA targeting another tenant!")
        self.assertFalse(CuratedQAKnowledge.all_objects.filter(question_pattern='Injection vào Tenant B').exists())

        # 3f. Non-superuser from Tenant A attempting cross-tenant document upload targeting Tenant B must return 403
        test_file_b = SimpleUploadedFile("cross_doc.txt", b"Cross tenant doc")
        res_cross_doc = self.client.post('/api/v1/assistant/admin/upload-document/', {
            'title': 'Tài liệu cross-tenant',
            'file': test_file_b,
            'isSystemGuide': False,
            'targetTenantId': str(self.tenant_b.id)
        }, format='multipart')
        self.assertEqual(res_cross_doc.status_code, 403, "Non-superuser MUST NOT be allowed to upload documents targeting another tenant!")

    def test_regression_4_cross_tenant_qa_deletion_isolation(self):
        """4. Xóa QA của Tenant A không làm mất chunk Tenant B, kể cả khi nội dung giống nhau."""
        shared_pattern = f"Quy trình cân tâm trục laser {uuid.uuid4().hex[:6]}"
        
        # Create QA and chunk in Tenant A
        qa_a = CuratedQAKnowledge.objects.create(
            tenant_id=self.tenant_a.id,
            is_system_guide=False,
            category='EQUIPMENT_MAINTENANCE',
            question_pattern=shared_pattern,
            gold_answer='Quy trình Tenant A: sai số 0.05mm'
        )
        chunk_a = DocumentChunk.objects.create(
            tenant_id=self.tenant_a.id,
            is_system_guide=False,
            source_type='CURATED_QA',
            content=shared_pattern,
            parent_content=qa_a.gold_answer,
            embedding=[0.05] * 384,
            is_active=True
        )

        # Create QA and chunk in Tenant B with IDENTICAL question pattern
        qa_b = CuratedQAKnowledge.objects.create(
            tenant_id=self.tenant_b.id,
            is_system_guide=False,
            category='EQUIPMENT_MAINTENANCE',
            question_pattern=shared_pattern,
            gold_answer='Quy trình Tenant B: sai số 0.02mm'
        )
        chunk_b = DocumentChunk.objects.create(
            tenant_id=self.tenant_b.id,
            is_system_guide=False,
            source_type='CURATED_QA',
            content=shared_pattern,
            parent_content=qa_b.gold_answer,
            embedding=[0.05] * 384,
            is_active=True
        )

        # Superuser deletes QA A
        self.client.force_authenticate(user=self.superuser)
        res_del = self.client.delete(f'/api/v1/assistant/admin/qa/{qa_a.id}/')
        self.assertEqual(res_del.status_code, 200)

        # Tenant A's chunk should be deleted
        self.assertFalse(DocumentChunk.all_objects.filter(id=chunk_a.id).exists())

        # Tenant B's chunk MUST BE PRESERVED!
        self.assertTrue(DocumentChunk.all_objects.filter(id=chunk_b.id).exists(), "Deleting QA of Tenant A must NEVER delete chunk of Tenant B!")
        self.assertTrue(CuratedQAKnowledge.all_objects.filter(id=qa_b.id).exists())

    def test_regression_5_system_scanner_does_not_delete_tenant_qa(self):
        """5. Scanner không xóa QA do Tenant quản lý dù trùng câu hỏi với mẫu cẩm nang."""
        sample_q = "hướng dẫn tạo phiếu bảo trì"
        
        # Tenant A custom QA
        qa_tenant = CuratedQAKnowledge.objects.create(
            tenant_id=self.tenant_a.id,
            is_system_guide=False,
            category='EQUIPMENT_MAINTENANCE',
            question_pattern=sample_q,
            gold_answer='Tenant A workflow: Gặp Trưởng phòng ký trước khi tạo phiếu.'
        )

        # Run scanner
        scan_and_index_system_knowledge()

        # Tenant A QA must still exist!
        self.assertTrue(
            CuratedQAKnowledge.all_objects.filter(id=qa_tenant.id).exists(),
            "System Knowledge Scanner must NOT delete Tenant-managed Q&As!"
        )

    def test_regression_6_system_scanner_idempotency_no_duplicates(self):
        """6. Scanner chạy nhiều lần không gây duplicate dữ liệu tri thức hệ thống."""
        res1 = scan_and_index_system_knowledge()
        count_chunks_1 = DocumentChunk.all_objects.filter(is_system_guide=True).count()
        count_qa_1 = CuratedQAKnowledge.all_objects.filter(is_system_guide=True).count()

        # Run second time
        res2 = scan_and_index_system_knowledge()
        count_chunks_2 = DocumentChunk.all_objects.filter(is_system_guide=True).count()
        count_qa_2 = CuratedQAKnowledge.all_objects.filter(is_system_guide=True).count()

        self.assertEqual(count_chunks_1, count_chunks_2, "Repeated scanner execution must be idempotent and not create duplicate chunks!")
        self.assertEqual(count_qa_1, count_qa_2, "Repeated scanner execution must not duplicate system QAs!")

    def test_regression_7_no_sparepart_still_checks_tool(self):
        """7. Không có SparePart vẫn kiểm tra Tool bình thường (không bị short-circuit)."""
        # Ensure Tenant B has 0 spare parts
        SparePart.objects.filter(tenant=self.tenant_b).delete()
        self.assertEqual(SparePart.objects.filter(tenant=self.tenant_b).count(), 0)

        # Create Tool in Tenant B
        tool_torque = Tool.objects.create(
            tenant=self.tenant_b,
            code="TOOL-TORQUE-M50",
            name="Cờ lê lực điện tử M50",
            available_quantity=3
        )

        matches = check_live_inventory("Cần dùng cờ lê lực điện tử TOOL-TORQUE-M50", tenant_id=str(self.tenant_b.id))
        self.assertTrue(len(matches) >= 1, "Tool check must execute even when warehouse has 0 SpareParts!")
        tool_item = [m for m in matches if m['partNumber'] == 'TOOL-TORQUE-M50'][0]
        self.assertTrue(tool_item['isTool'])
        self.assertEqual(tool_item['inStock'], 3.0)

    def test_regression_8_tool_without_calibration_reports_no_data(self):
        """8. Tool chưa có dữ liệu kiểm định không được báo PASSED (phải báo NO_CALIBRATION_DATA)."""
        # 8a. Tool without instances
        tool_no_inst = Tool.objects.create(
            tenant=self.tenant_a,
            code=f"TOOL-CALIPER-{uuid.uuid4().hex[:4]}",
            name="Thước kẹp cơ khí chưa có cá thể",
            available_quantity=1
        )
        matches1 = check_live_inventory(f"dùng {tool_no_inst.code}", tenant_id=str(self.tenant_a.id))
        self.assertTrue(len(matches1) >= 1)
        tool_item1 = [m for m in matches1 if m['partNumber'] == tool_no_inst.code][0]
        self.assertEqual(tool_item1['inspectionStatus'], "NO_CALIBRATION_DATA", "Tool without instances must report NO_CALIBRATION_DATA!")

        # 8b. Tool with instance but NO calibration date/due date
        tool_uncal = Tool.objects.create(
            tenant=self.tenant_a,
            code=f"TOOL-MICROMETER-{uuid.uuid4().hex[:4]}",
            name="Panme đo ngoài chưa kiểm định",
            available_quantity=1
        )
        ToolInstance.objects.create(
            tenant=self.tenant_a,
            tool=tool_uncal,
            serial_number="SN-UNCAL-001",
            calibration_due_date=None,
            calibration_date=None,
            inspection_status='PASSED' # default model value must not cause false PASSED
        )
        matches2 = check_live_inventory(f"dùng {tool_uncal.code}", tenant_id=str(self.tenant_a.id))
        self.assertTrue(len(matches2) >= 1)
        tool_item2 = [m for m in matches2 if m['partNumber'] == tool_uncal.code][0]
        self.assertEqual(tool_item2['inspectionStatus'], "NO_CALIBRATION_DATA", "Instance with no calibration dates must NEVER report PASSED!")

        # 8c. Tool with multiple instances: one valid, one missing calibration data
        tool_multi = Tool.objects.create(
            tenant=self.tenant_a,
            code=f"TOOL-LEVEL-{uuid.uuid4().hex[:4]}",
            name="Nivo cân bằng điện tử đa cá thể",
            available_quantity=2
        )
        ToolInstance.objects.create(
            tenant=self.tenant_a,
            tool=tool_multi,
            serial_number="SN-LEVEL-CALIBRATED",
            calibration_due_date=date.today() + timedelta(days=90),
            inspection_status='PASSED'
        )
        ToolInstance.objects.create(
            tenant=self.tenant_a,
            tool=tool_multi,
            serial_number="SN-LEVEL-NOCAL",
            calibration_due_date=None,
            calibration_date=None,
            inspection_status='PASSED'
        )
        matches3 = check_live_inventory(f"dùng {tool_multi.code}", tenant_id=str(self.tenant_a.id))
        self.assertTrue(len(matches3) >= 1)
        tool_item3 = [m for m in matches3 if m['partNumber'] == tool_multi.code][0]
        self.assertEqual(tool_item3['inspectionStatus'], "NO_CALIBRATION_DATA", "Multi-instance tool with incomplete calibration data must report NO_CALIBRATION_DATA!")

    def test_regression_9_tool_overdue_calibration_reports_expired(self):
        """9. Tool quá hạn kiểm định phải bị cảnh báo EXPIRED ngay cả khi DB status còn ghi PASSED."""
        tool_expired = Tool.objects.create(
            tenant=self.tenant_a,
            code=f"TOOL-GAUGE-{uuid.uuid4().hex[:4]}",
            name="Đồng hồ đo áp suất hiệu chuẩn",
            available_quantity=1
        )
        ToolInstance.objects.create(
            tenant=self.tenant_a,
            tool=tool_expired,
            serial_number="SN-INST-OVERDUE",
            calibration_due_date=date.today() - timedelta(days=45),
            inspection_status='PASSED' # Stale DB value
        )

        matches = check_live_inventory(f"dùng {tool_expired.code}", tenant_id=str(self.tenant_a.id))
        self.assertTrue(len(matches) >= 1)
        tool_item = [m for m in matches if m['partNumber'] == tool_expired.code][0]
        self.assertEqual(tool_item['inspectionStatus'], "EXPIRED", "Overdue calibration date must report EXPIRED status!")

    def test_regression_10_sql_top_k_no_duplicate_chunks(self):
        """10. SQL Top-K không chứa nhiều bản sao của cùng chunk (triệt tiêu duplicate qua EXISTS)."""
        shared_answer = "Quy trình kiểm tra áp suất bưởng bơm và xả khí."
        qa_dup_1 = CuratedQAKnowledge.objects.create(
            tenant_id=self.tenant_a.id,
            is_system_guide=False,
            category='EQUIPMENT_MAINTENANCE',
            question_pattern="Bơm ly tâm bị tụt áp",
            gold_answer=shared_answer,
            applicable_model="PUMP-X100"
        )
        qa_dup_2 = CuratedQAKnowledge.objects.create(
            tenant_id=self.tenant_a.id,
            is_system_guide=False,
            category='EQUIPMENT_MAINTENANCE',
            question_pattern="Áp suất bơm không đạt",
            gold_answer=shared_answer,
            applicable_model="PUMP-X100"
        )
        chunk_single = DocumentChunk.objects.create(
            tenant_id=self.tenant_a.id,
            is_system_guide=False,
            source_type='CURATED_QA',
            content="Bơm ly tâm bị tụt áp",
            parent_content=shared_answer,
            embedding=embed_text("Bơm ly tâm bị tụt áp"),
            is_active=True
        )

        chunks = retrieve_relevant_chunks(
            query_text="Bơm ly tâm bị tụt áp",
            tenant_id=str(self.tenant_a.id),
            asset_model="PUMP-X100",
            limit=5
        )
        occurrences = sum(1 for c in chunks if c['id'] == str(chunk_single.id))
        self.assertEqual(occurrences, 1, "Top-K SQL results must contain each DocumentChunk at most ONCE without duplication!")

    def test_regression_11_portal_handles_safety_officer_tab_and_error_handling(self):
        """11. Tab Safety hiển thị đúng thông báo khi gặp HTTP 403 và phân quyền Tab trên Portal."""
        # Authenticate as safety officer
        self.client.force_login(self.user_safety)
        self.client.force_authenticate(user=self.user_safety)
        response = self.client.get('/portal/rag-knowledge/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Rào Chắn An Toàn & Tiếng Lóng')
        # QA Tab button should not be accessible to safety officer
        self.assertNotContains(response, 'id="tab-btn-qa"')
        self.assertEqual(response.context['active_tab'], 'safety')

        # When safety officer accesses with ?tab=qa, active_tab should safely fall back to 'safety'
        res_with_qa_tab = self.client.get('/portal/rag-knowledge/?tab=qa')
        self.assertEqual(res_with_qa_tab.status_code, 200)
        self.assertEqual(res_with_qa_tab.context['active_tab'], 'safety', "Unauthorized active_tab must safely fallback to 'safety' to prevent blank page!")

        # Verify JS error handling for 403 and error/detail fields
        self.assertContains(response, 'res.status === 403')
        self.assertContains(response, 'data.detail')
        self.assertContains(response, 'data.error')

    def test_regression_12_global_and_tenant_knowledge_dual_stream_retrieval(self):
        """12. Các luồng Global Knowledge và Tenant Knowledge vẫn truy xuất đúng."""
        # System Guide chunk
        doc_sys = TechnicalDocument.objects.create(
            tenant_id=None,
            is_system_guide=True,
            category='SYSTEM_FEATURE_GUIDE',
            title='Cẩm Nang Toàn Cục Hệ Thống'
        )
        chunk_sys = DocumentChunk.objects.create(
            tenant_id=None,
            is_system_guide=True,
            document=doc_sys,
            source_type='SYSTEM_GUIDE',
            content='Hướng dẫn đổi mật khẩu và bảo mật hai lớp',
            parent_content='Vào Cài đặt Tài khoản > Bảo mật > Bật 2FA.',
            embedding=embed_text('đổi mật khẩu bảo mật'),
            is_active=True
        )

        # Tenant A query for system guide
        results = retrieve_relevant_chunks(
            query_text='làm sao đổi mật khẩu tài khoản',
            tenant_id=str(self.tenant_a.id),
            is_system_query=True,
            limit=5
        )
        sys_ids = [r['id'] for r in results]
        self.assertIn(str(chunk_sys.id), sys_ids, "Tenant A must be able to retrieve Global System Guide chunks!")


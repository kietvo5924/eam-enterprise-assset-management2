import json
import uuid
from datetime import datetime, timezone
from django.db.models import Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from core.models import Tenant
from users.permissions import HasPermission
from assets.models import Asset, SparePart
from workorders.models import WorkOrder
from .models import TechnicalDocument, DocumentChunk, CuratedQAKnowledge, CurationQueueItem
from .serializers import (
    TechnicalDocumentSerializer, 
    CuratedQAKnowledgeSerializer, 
    CurationQueueItemSerializer
)
from algorithms.rag_chatbot import (
    process_rag_query,
    generate_offline_package,
    embed_text,
    is_valid_tacit_work_order,
    structure_aware_chunk_text,
    extract_diagram_anchors
)
from algorithms.rag_chatbot.constants import (
    SLANG_TECHNICAL_DICTIONARY,
    EMERGENCY_HAZARDS
)


class AssistantChatView(APIView):
    """
    POST /api/v1/assistant/chat/
    Technical field assistant & system feature guide chatbot.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        prompt = request.data.get('prompt', '').strip()
        if not prompt:
            return Response(
                {"success": False, "error": "Câu hỏi không được để trống."},
                status=status.HTTP_400_BAD_REQUEST
            )

        asset_context = request.data.get('assetContext')
        stream = request.data.get('stream', False)
        tenant_id = str(getattr(request.user, 'tenant_id', '')) or None

        result = process_rag_query(
            prompt=prompt,
            asset_context=asset_context,
            tenant_id=tenant_id,
            stream=stream
        )
        return Response(result, status=status.HTTP_200_OK)


class AssistantFeedbackView(APIView):
    """
    POST /api/v1/assistant/feedback/
    Technician feedback: Thumbs up / Thumbs down.
    When downvoted, sends entry into the Chief Engineer Curation Queue.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user_query = request.data.get('userQuery', '').strip()
        generated_answer = request.data.get('generatedAnswer', '').strip()
        vote_type = request.data.get('voteType', 'UPVOTE').upper()
        feedback = request.data.get('feedback', '').strip()

        tenant_id = getattr(request.user, 'tenant_id', None)

        if vote_type == 'DOWNVOTE':
            CurationQueueItem.objects.create(
                tenant_id=tenant_id,
                user=request.user,
                user_query=user_query,
                generated_answer=generated_answer,
                technician_feedback=feedback or "Cần Kỹ sư trưởng hiệu chỉnh",
                vote_type='DOWNVOTE',
                status='PENDING'
            )
            return Response({
                "success": True,
                "message": "Phản hồi chưa hài lòng đã được chuyển vào Hàng đợi Thẩm định của Kỹ sư trưởng."
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                "success": True,
                "message": "Cảm ơn phản hồi hữu ích của bạn!"
            }, status=status.HTTP_200_OK)


class AssistantCreateWorkOrderDraftView(APIView):
    """
    POST /api/v1/assistant/create-work-order-draft/
    Actionable Chat-to-WorkOrder Draft Generator (Rule 3, Rule 9, TC-RAG-11).
    STRICT GUARANTEE:
    - Creates draft with status = 'CREATED'.
    - NEVER auto-progresses status to IN_PROGRESS.
    - NEVER deducts spare parts inventory stock.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        asset_id = request.data.get('assetId') or request.data.get('asset_id')
        title = request.data.get('title', '').strip()
        description = request.data.get('description', '').strip()
        fault_code = request.data.get('faultCode', 'CAVITATION_NOISE')
        priority = request.data.get('priority', 'HIGH').upper()

        if priority not in ['LOW', 'MEDIUM', 'HIGH', 'URGENT']:
            priority = 'HIGH'

        tenant_id = getattr(request.user, 'tenant_id', None)

        asset = None
        if asset_id:
            try:
                qs = Asset.all_objects.filter(id=asset_id)
                if tenant_id:
                    qs = qs.filter(tenant_id=tenant_id)
                asset = qs.first()
            except Exception:
                pass
            if not asset:
                return Response(
                    {"success": False, "error": "Thiết bị không tồn tại hoặc không thuộc quyền quản lý của đơn vị bạn."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        if not asset:
            # Fallback to first available asset in tenant
            asset = Asset.all_objects.filter(tenant_id=tenant_id).first()

        if not asset:
            return Response(
                {"success": False, "error": "Không tìm thấy thiết bị hợp lệ để tạo phiếu bảo trì."},
                status=status.HTTP_400_BAD_REQUEST
            )

        effective_tenant_id = tenant_id or getattr(asset, 'tenant_id', None)

        # STRICT COMPLIANCE: status MUST BE 'CREATED', NO inventory deduction
        wo = WorkOrder.objects.create(
            tenant_id=effective_tenant_id,
            asset=asset,
            title=title or f"Khắc phục sự cố theo chẩn đoán AI: {asset.name}",
            description=description or f"Tạo tự động từ chẩn đoán AI Chatbot (Mã lỗi: {fault_code})",
            priority=priority,
            status='CREATED',  # Only CREATED
            type='CORRECTIVE',
            source_reference=f"RAG_AI_{fault_code}",
            created_by=request.user
        )

        return Response({
            "success": True,
            "message": "Bản thảo Phiếu Bảo Trì đã được tạo thành công ở trạng thái CREATED (chưa trừ kho).",
            "data": {
                "workOrderId": str(wo.id),
                "code": wo.code,
                "status": wo.status,
                "title": wo.title,
                "isDraftOnly": True,
                "inventoryDeducted": False,
                "faultCode": fault_code,
                "priority": wo.priority
            }
        }, status=status.HTTP_201_CREATED)


class AssistantOfflinePackView(APIView):
    """
    GET /api/v1/assistant/offline-pack/<asset_id>/
    Downloads pre-fetched offline package with versioning and SHA-256 checksum for mobile Drift SQLite.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, asset_id):
        tenant_id = getattr(request.user, 'tenant_id', None)
        pack = generate_offline_package(str(asset_id), tenant_id=str(tenant_id) if tenant_id else None)
        if pack is None:
            return Response(
                {"success": False, "error": "Không tìm thấy thiết bị hoặc bạn không có quyền truy cập gói offline của thiết bị này."},
                status=status.HTTP_404_NOT_FOUND
            )
        return Response({
            "success": True,
            "data": pack
        }, status=status.HTTP_200_OK)


class AssistantAdminQAListView(APIView):
    """
    GET /api/v1/assistant/admin/qa-list/
    Lists curated Q&A knowledge (Equipment vs Global Software Guides).
    """
    permission_classes = [IsAuthenticated, HasPermission('assistant:manage_knowledge')]

    def get(self, request):
        category = request.GET.get('category')
        is_system_guide = request.GET.get('is_system_guide')
        search = request.GET.get('search', '').strip()

        qs = CuratedQAKnowledge.all_objects.all()
        tenant_id = getattr(request.user, 'tenant_id', None)
        if tenant_id:
            qs = qs.filter(
                Q(tenant_id=tenant_id) | Q(is_system_guide=True, tenant_id__isnull=True)
            )

        if category:
            qs = qs.filter(category=category)
        if is_system_guide is not None:
            qs = qs.filter(is_system_guide=(is_system_guide.lower() == 'true'))
        if search:
            qs = qs.filter(
                Q(question_pattern__icontains=search) | 
                Q(gold_answer__icontains=search)
            )

        serializer = CuratedQAKnowledgeSerializer(qs.order_by('-created_at'), many=True)
        return Response({
            "success": True,
            "data": serializer.data
        }, status=status.HTTP_200_OK)


class AssistantAdminQACreateUpdateView(APIView):
    """
    POST /api/v1/assistant/admin/qa/
    Adds or updates a Curated Q&A entry and synchronizes into DocumentChunk for immediate retrieval.
    """
    permission_classes = [IsAuthenticated, HasPermission('assistant:manage_knowledge')]

    def post(self, request):
        qa_id = request.data.get('id')
        question = request.data.get('questionPattern', '').strip()
        answer = request.data.get('goldAnswer', '').strip()
        category = request.data.get('category', 'EQUIPMENT_MAINTENANCE')
        is_system_guide = request.data.get('isSystemGuide', False)
        applicable_model = request.data.get('applicableModel')
        app_year_start = request.data.get('applicableYearStart', 1900)
        app_year_end = request.data.get('applicableYearEnd', 2100)

        try:
            app_year_start = int(app_year_start) if app_year_start not in (None, '') else 1900
        except (ValueError, TypeError):
            app_year_start = 1900

        try:
            app_year_end = int(app_year_end) if app_year_end not in (None, '') else 2100
        except (ValueError, TypeError):
            app_year_end = 2100

        if not question or not answer:
            return Response(
                {"success": False, "error": "Câu hỏi và câu trả lời không được để trống."},
                status=status.HTTP_400_BAD_REQUEST
            )

        user_tenant_id = getattr(request.user, 'tenant_id', None)
        is_sys_tenant = (not user_tenant_id) or (str(user_tenant_id) == '00000000-0000-0000-0000-000000000000')

        if is_system_guide:
            if not request.user.is_superuser:
                is_system_guide = False
                tenant_id = user_tenant_id
            else:
                tenant_id = None
        else:
            req_target_tenant = request.data.get('tenant_id') or request.data.get('targetTenantId')
            if request.user.is_superuser:
                if is_sys_tenant:
                    target_tenant_id = req_target_tenant
                else:
                    target_tenant_id = req_target_tenant or user_tenant_id

                if not target_tenant_id or str(target_tenant_id) == '00000000-0000-0000-0000-000000000000':
                    return Response({"success": False, "error": "Vui lòng chọn Tenant hợp lệ khi tạo tri thức thiết bị."}, status=status.HTTP_400_BAD_REQUEST)

                if not Tenant.objects.filter(id=target_tenant_id).exists():
                    return Response({"success": False, "error": "Tenant được chọn không tồn tại trên hệ thống."}, status=status.HTTP_400_BAD_REQUEST)

                tenant_id = target_tenant_id
            else:
                if req_target_tenant and str(req_target_tenant) != str(user_tenant_id):
                    return Response({"success": False, "error": "Bạn không có quyền tạo tri thức cho Tenant khác."}, status=status.HTTP_403_FORBIDDEN)
                
                if not user_tenant_id or str(user_tenant_id) == '00000000-0000-0000-0000-000000000000':
                    return Response({"success": False, "error": "Tài khoản không thuộc Tenant hợp lệ."}, status=status.HTTP_400_BAD_REQUEST)

                tenant_id = user_tenant_id

        if not is_system_guide and not tenant_id:
            return Response({"success": False, "error": "Tri thức thiết bị bắt buộc phải thuộc một Tenant cụ thể."}, status=status.HTTP_400_BAD_REQUEST)

        old_question = None
        if qa_id:
            try:
                qs = CuratedQAKnowledge.all_objects.filter(id=qa_id)
                if not request.user.is_superuser and user_tenant_id:
                    qs = qs.filter(tenant_id=user_tenant_id)
                qa = qs.first()
                if not qa:
                    return Response({"success": False, "error": "Không tìm thấy bản ghi Q&A hoặc bạn không có quyền sửa."}, status=status.HTTP_404_NOT_FOUND)
                old_question = qa.question_pattern
                tenant_id = qa.tenant_id
                is_system_guide = qa.is_system_guide
                qa.question_pattern = question
                qa.gold_answer = answer
                qa.category = category
                qa.applicable_model = applicable_model
                qa.applicable_year_start = app_year_start
                qa.applicable_year_end = app_year_end
                qa.save()
            except Exception:
                return Response({"success": False, "error": "Không tìm thấy bản ghi Q&A."}, status=404)
        else:
            qa = CuratedQAKnowledge.objects.create(
                tenant_id=tenant_id,
                is_system_guide=is_system_guide,
                category=category,
                question_pattern=question,
                gold_answer=answer,
                applicable_model=applicable_model,
                applicable_year_start=app_year_start,
                applicable_year_end=app_year_end,
                approved_by=request.user
            )

        # Remove existing/old chunk to prevent duplicates with strict tenant boundary
        chunk_del_qs = DocumentChunk.all_objects.filter(source_type='CURATED_QA')
        if tenant_id:
            chunk_del_qs = chunk_del_qs.filter(tenant_id=tenant_id)
        elif is_system_guide:
            chunk_del_qs = chunk_del_qs.filter(is_system_guide=True, tenant_id__isnull=True)
        else:
            if user_tenant_id:
                chunk_del_qs = chunk_del_qs.filter(tenant_id=user_tenant_id)
            else:
                chunk_del_qs = chunk_del_qs.none()

        if old_question:
            chunk_del_qs.filter(content=old_question).delete()
        chunk_del_qs.filter(content=question).delete()

        # Vectorize and save as DocumentChunk for immediate PGVector search
        vec = embed_text(f"{question} {answer}")
        anchors = extract_diagram_anchors(answer)

        # Create corresponding DocumentChunk
        DocumentChunk.objects.create(
            tenant_id=tenant_id,
            is_system_guide=is_system_guide,
            source_type='CURATED_QA',
            content=question,
            parent_content=answer,
            embedding=vec,
            section_title=f"Curated QA: {question[:50]}",
            image_anchors=anchors,
            is_active=True
        )

        return Response({
            "success": True,
            "message": "Lưu Tri thức Vàng thành công và đã lập chỉ mục vector PGVector.",
            "data": CuratedQAKnowledgeSerializer(qa).data
        }, status=status.HTTP_200_OK)


class AssistantAdminQADeleteView(APIView):
    """
    DELETE /api/v1/assistant/admin/qa/<id>/
    Deletes a Curated Q&A entry and its corresponding DocumentChunk.
    """
    permission_classes = [IsAuthenticated, HasPermission('assistant:manage_knowledge')]

    def delete(self, request, id):
        user_tenant_id = getattr(request.user, 'tenant_id', None)
        qs = CuratedQAKnowledge.all_objects.filter(id=id)
        if not request.user.is_superuser and user_tenant_id:
            qs = qs.filter(tenant_id=user_tenant_id)
        qa = qs.first()
        if not qa:
            return Response({"success": False, "error": "Không tìm thấy bản ghi hoặc bạn không có quyền xóa."}, status=status.HTTP_404_NOT_FOUND)

        # Clean up vector chunk so it is no longer retrieved
        chunk_qs = DocumentChunk.all_objects.filter(source_type='CURATED_QA', content=qa.question_pattern)
        if qa.tenant_id:
            chunk_qs = chunk_qs.filter(tenant_id=qa.tenant_id)
        elif qa.is_system_guide:
            chunk_qs = chunk_qs.filter(is_system_guide=True, tenant_id__isnull=True)
        else:
            if user_tenant_id:
                chunk_qs = chunk_qs.filter(tenant_id=user_tenant_id)
            else:
                chunk_qs = chunk_qs.none()
        chunk_qs.delete()
        qa.delete()
        return Response({"success": True, "message": "Xóa câu hỏi thành công."}, status=status.HTTP_200_OK)


class AssistantAdminCurationQueueView(APIView):
    """
    GET /api/v1/assistant/admin/curation-queue/
    Chief Engineer curation review queue for downvoted technician queries.
    """
    permission_classes = [IsAuthenticated, HasPermission('assistant:manage_knowledge')]

    def get(self, request):
        status_filter = request.GET.get('status', 'PENDING')
        tenant_id = getattr(request.user, 'tenant_id', None)

        qs = CurationQueueItem.all_objects.all()
        if tenant_id:
            qs = qs.filter(tenant_id=tenant_id)
        if status_filter:
            qs = qs.filter(status=status_filter)

        serializer = CurationQueueItemSerializer(qs.order_by('-created_at'), many=True)
        return Response({
            "success": True,
            "data": serializer.data
        }, status=status.HTTP_200_OK)


class AssistantAdminCurationApproveView(APIView):
    """
    POST /api/v1/assistant/admin/curation-queue/<id>/approve/
    Chief Engineer approves curated answer and stores as Gold Knowledge.
    """
    permission_classes = [IsAuthenticated, HasPermission('assistant:manage_knowledge')]

    def post(self, request, id):
        curated_answer = request.data.get('curatedAnswer', '').strip()
        applicable_model = request.data.get('applicableModel')

        if not curated_answer:
            return Response(
                {"success": False, "error": "Nội dung câu trả lời chuẩn không được để trống."},
                status=status.HTTP_400_BAD_REQUEST
            )

        user_tenant_id = getattr(request.user, 'tenant_id', None)
        qs = CurationQueueItem.all_objects.filter(id=id)
        if not request.user.is_superuser and user_tenant_id:
            qs = qs.filter(tenant_id=user_tenant_id)
        item = qs.first()
        if not item:
            return Response({"success": False, "error": "Không tìm thấy yêu cầu thẩm định hoặc bạn không có quyền thao tác."}, status=status.HTTP_404_NOT_FOUND)

        # Update queue item
        item.status = 'APPROVED'
        item.curated_answer = curated_answer
        item.reviewed_by = request.user
        item.reviewed_at = datetime.now(timezone.utc)
        item.save()

        # Create Curated Gold QA
        qa = CuratedQAKnowledge.objects.create(
            tenant_id=item.tenant_id,
            is_system_guide=False,
            category='EQUIPMENT_MAINTENANCE',
            question_pattern=item.user_query,
            gold_answer=curated_answer,
            applicable_model=applicable_model,
            approved_by=request.user
        )

        # Embed and insert into document_chunks
        vec = embed_text(f"{item.user_query} {curated_answer}")
        anchors = extract_diagram_anchors(curated_answer)
        DocumentChunk.objects.create(
            tenant_id=item.tenant_id,
            is_system_guide=False,
            source_type='CURATED_QA',
            content=item.user_query,
            parent_content=curated_answer,
            embedding=vec,
            section_title=f"Gold QA: {item.user_query[:50]}",
            image_anchors=anchors,
            is_active=True
        )

        return Response({
            "success": True,
            "message": "Phê duyệt thành công và đã lưu thành Tri thức Vàng.",
            "data": CuratedQAKnowledgeSerializer(qa).data
        }, status=status.HTTP_200_OK)


class AssistantAdminUploadDocumentView(APIView):
    """
    POST /api/v1/assistant/admin/upload-document/
    Uploads technical OEM manual or software guide and chunks/embeds it into PGVector.
    Supports file uploads (.pdf, .docx, .md, .txt) as well as direct text input.
    """
    permission_classes = [IsAuthenticated, HasPermission('assistant:manage_knowledge')]

    def post(self, request):
        title = request.data.get('title', '').strip()
        content = request.data.get('content', '').strip()
        category = request.data.get('category', 'OEM_MANUAL')
        is_system_guide = request.data.get('isSystemGuide', False)
        if isinstance(is_system_guide, str):
            is_system_guide = is_system_guide.lower() in ('true', '1', 'yes')
        applicable_model = request.data.get('applicableModel')
        app_year_start = request.data.get('applicableYearStart', 1900)
        app_year_end = request.data.get('applicableYearEnd', 2100)

        uploaded_file = request.FILES.get('file')
        file_size_bytes = 0

        if uploaded_file:
            file_size_bytes = uploaded_file.size
            if not title:
                import os
                title = os.path.splitext(uploaded_file.name)[0].replace('_', ' ').strip()
            
            # Extract content from file if content is not provided
            if not content:
                fname_lower = uploaded_file.name.lower()
                if fname_lower.endswith('.pdf'):
                    try:
                        import pypdf
                        reader = pypdf.PdfReader(uploaded_file)
                        pages_text = []
                        for i, page in enumerate(reader.pages):
                            txt = page.extract_text()
                            if txt:
                                pages_text.append(f"<!-- [Page {i+1}] -->\n" + txt.strip())
                        content = "\n\n".join(pages_text)
                    except Exception as e:
                        return Response(
                            {"success": False, "error": f"Lỗi đọc nội dung file PDF: {str(e)}"},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                elif fname_lower.endswith('.docx'):
                    try:
                        import zipfile, xml.etree.ElementTree as ET
                        with zipfile.ZipFile(uploaded_file) as z:
                            xml_content = z.read('word/document.xml')
                            tree = ET.fromstring(xml_content)
                            paragraphs = []
                            for p in tree.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'):
                                texts = [node.text for node in p.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t') if node.text]
                                if texts:
                                    paragraphs.append(''.join(texts))
                            content = '\n\n'.join(paragraphs)
                    except Exception as e:
                        return Response(
                            {"success": False, "error": f"Lỗi đọc nội dung file Word (.docx): {str(e)}"},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                else:
                    try:
                        content = uploaded_file.read().decode('utf-8', errors='ignore')
                    except Exception as e:
                        return Response(
                            {"success": False, "error": f"Lỗi đọc file văn bản: {str(e)}"},
                            status=status.HTTP_400_BAD_REQUEST
                        )

        try:
            app_year_start = int(app_year_start) if app_year_start not in (None, '') else 1900
        except (ValueError, TypeError):
            app_year_start = 1900

        try:
            app_year_end = int(app_year_end) if app_year_end not in (None, '') else 2100
        except (ValueError, TypeError):
            app_year_end = 2100

        if not title or not content:
            return Response(
                {"success": False, "error": "Vui lòng nhập tiêu đề hoặc tải lên file hợp lệ có nội dung văn bản."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not file_size_bytes:
            file_size_bytes = len(content.encode('utf-8'))

        user_tenant_id = getattr(request.user, 'tenant_id', None)
        is_sys_tenant = (not user_tenant_id) or (str(user_tenant_id) == '00000000-0000-0000-0000-000000000000')

        if is_system_guide:
            if not request.user.is_superuser:
                is_system_guide = False
                tenant_id = user_tenant_id
            else:
                tenant_id = None
        else:
            req_target_tenant = request.data.get('tenant_id') or request.data.get('targetTenantId')
            if request.user.is_superuser:
                if is_sys_tenant:
                    target_tenant_id = req_target_tenant
                else:
                    target_tenant_id = req_target_tenant or user_tenant_id

                if not target_tenant_id or str(target_tenant_id) == '00000000-0000-0000-0000-000000000000':
                    return Response({"success": False, "error": "Vui lòng chọn Tenant hợp lệ khi tải lên tài liệu thiết bị."}, status=status.HTTP_400_BAD_REQUEST)

                if not Tenant.objects.filter(id=target_tenant_id).exists():
                    return Response({"success": False, "error": "Tenant được chọn không tồn tại trên hệ thống."}, status=status.HTTP_400_BAD_REQUEST)

                tenant_id = target_tenant_id
            else:
                if req_target_tenant and str(req_target_tenant) != str(user_tenant_id):
                    return Response({"success": False, "error": "Bạn không có quyền tải lên tài liệu cho Tenant khác."}, status=status.HTTP_403_FORBIDDEN)
                
                if not user_tenant_id or str(user_tenant_id) == '00000000-0000-0000-0000-000000000000':
                    return Response({"success": False, "error": "Tài khoản không thuộc Tenant hợp lệ."}, status=status.HTTP_400_BAD_REQUEST)

                tenant_id = user_tenant_id

        if not is_system_guide and not tenant_id:
            return Response({"success": False, "error": "Tài liệu thiết bị bắt buộc phải thuộc một Tenant cụ thể."}, status=status.HTTP_400_BAD_REQUEST)

        # Persist uploaded file to storage
        from django.core.files.storage import default_storage
        from django.core.files.base import ContentFile
        from django.utils.text import get_valid_filename
        if uploaded_file:
            try:
                uploaded_file.seek(0)
            except Exception:
                pass
            safe_name = get_valid_filename(uploaded_file.name)
            saved_name = default_storage.save(f"manuals/{safe_name}", uploaded_file)
            file_path_val = saved_name
        else:
            safe_fname = get_valid_filename(f"{title.lower().replace(' ', '_')}.md")
            saved_name = default_storage.save(f"manuals/{safe_fname}", ContentFile(content.encode('utf-8')))
            file_path_val = saved_name

        doc = TechnicalDocument.objects.create(
            tenant_id=tenant_id,
            is_system_guide=is_system_guide,
            category=category,
            title=title,
            file_path=file_path_val,
            applicable_model=applicable_model,
            applicable_year_start=app_year_start,
            applicable_year_end=app_year_end,
            file_size_bytes=file_size_bytes
        )

        chunks_data = structure_aware_chunk_text(content)
        created_chunks = 0
        for chunk in chunks_data:
            vec = embed_text(chunk['content'])
            anchors = chunk.get('image_anchors', [])
            page_num = anchors[0].get('pageNumber', 1) if anchors else 1
            DocumentChunk.objects.create(
                tenant_id=tenant_id,
                is_system_guide=is_system_guide,
                document=doc,
                source_type='SYSTEM_GUIDE' if is_system_guide else 'OEM_MANUAL',
                content=chunk['content'],
                parent_content=chunk['parent_content'],
                embedding=vec,
                page_number=page_num,
                image_anchors=anchors,
                is_active=True
            )
            created_chunks += 1

        return Response({
            "success": True,
            "message": f"Tải lên và lập chỉ mục {created_chunks} đoạn tri thức thành công.",
            "data": TechnicalDocumentSerializer(doc).data
        }, status=status.HTTP_201_CREATED)


class AssistantAdminDocumentDetailView(APIView):
    """
    GET /api/v1/assistant/admin/documents/<uuid:doc_id>/
    Retrieves full details and text chunks of a technical document for viewing.
    """
    permission_classes = [IsAuthenticated, HasPermission('assistant:manage_knowledge')]

    def get(self, request, doc_id):
        tenant_id = getattr(request.user, 'tenant_id', None)
        qs = TechnicalDocument.all_objects.filter(id=doc_id)
        if tenant_id:
            qs = qs.filter(Q(tenant_id=tenant_id) | Q(is_system_guide=True, tenant_id__isnull=True))
        doc = qs.first()
        if not doc:
            return Response({"success": False, "error": "Không tìm thấy tài liệu kỹ thuật."}, status=status.HTTP_404_NOT_FOUND)

        chunks_qs = doc.chunks.all().order_by('page_number', 'id')
        chunks_data = [
            {
                "id": str(c.id),
                "pageNumber": c.page_number,
                "content": c.content,
                "parentContent": c.parent_content,
                "imageAnchors": c.image_anchors,
                "sourceType": c.source_type
            }
            for c in chunks_qs
        ]

        return Response({
            "success": True,
            "data": {
                "id": str(doc.id),
                "title": doc.title,
                "category": doc.category,
                "categoryDisplay": doc.get_category_display(),
                "isSystemGuide": doc.is_system_guide,
                "applicableModel": doc.applicable_model or "Tất cả thiết bị",
                "applicableYearStart": doc.applicable_year_start,
                "applicableYearEnd": doc.applicable_year_end,
                "fileSizeBytes": doc.file_size_bytes,
                "filePath": doc.file_path,
                "createdAt": doc.created_at.strftime('%d/%m/%Y %H:%M'),
                "chunksCount": len(chunks_data),
                "chunks": chunks_data
            }
        })


class AssistantAdminReindexView(APIView):
    """
    POST /api/v1/assistant/admin/reindex/
    Scans completed Work Orders and synchronizes tacit maintenance knowledge into PGVector.
    """
    permission_classes = [IsAuthenticated, HasPermission('assistant:manage_knowledge')]

    def post(self, request):
        tenant_id = getattr(request.user, 'tenant_id', None)
        qs = WorkOrder.all_objects.filter(status='COMPLETED')
        if tenant_id:
            qs = qs.filter(tenant_id=tenant_id)

        ingested_count = 0
        for wo in qs:
            if is_valid_tacit_work_order(wo):
                vec = embed_text(f"{wo.title} {wo.resolution_notes}")
                anchors = extract_diagram_anchors(wo.resolution_notes)
                existing = DocumentChunk.objects.filter(work_order=wo).first()
                if existing:
                    existing.content = f"{wo.title}: {wo.resolution_notes[:200]}"
                    existing.parent_content = f"Work Order {wo.code} ({wo.title}):\n{wo.resolution_notes}"
                    existing.embedding = vec
                    existing.image_anchors = anchors
                    existing.is_active = True
                    existing.save()
                else:
                    DocumentChunk.objects.create(
                        tenant_id=wo.tenant_id,
                        is_system_guide=False,
                        source_type='TACIT_WORK_ORDER',
                        work_order=wo,
                        is_verified_tacit=True,
                        provenance_wo_code=wo.code,
                        content=f"{wo.title}: {wo.resolution_notes[:200]}",
                        parent_content=f"Work Order {wo.code} ({wo.title}):\n{wo.resolution_notes}",
                        embedding=vec,
                        image_anchors=anchors,
                        is_active=True
                    )
                ingested_count += 1

        return Response({
            "success": True,
            "message": f"Tái lập chỉ mục hoàn tất. Đã nạp {ingested_count} phiếu bảo trì đạt chuẩn.",
            "ingestedCount": ingested_count
        }, status=status.HTTP_200_OK)


from algorithms.rag_chatbot.safety_config import (
    load_persisted_safety_config,
    save_persisted_safety_config,
    ensure_safety_config_loaded,
    CONFIG_STORAGE_PATH,
)


class AssistantAdminSafetyConfigView(APIView):
    """
    GET / POST /api/v1/assistant/admin/safety-config/
    Safety categories, hazard keywords and slang dictionary viewer and dynamic config manager.
    Persists configuration across application restarts and worker processes.
    Requires permission: assistant:configure_safety (SAFETY_OFFICER, ADMIN, TENANT_ADMIN).
    """
    permission_classes = [IsAuthenticated, HasPermission('assistant:configure_safety')]

    def get(self, request):
        load_persisted_safety_config(force=True)
        return Response({
            "success": True,
            "data": {
                "slangDictionary": SLANG_TECHNICAL_DICTIONARY,
                "emergencyHazards": EMERGENCY_HAZARDS
            }
        }, status=status.HTTP_200_OK)

    def post(self, request):
        custom_slang = request.data.get('custom_slang') or request.data.get('slangDictionary')
        custom_hazards = request.data.get('custom_hazards') or request.data.get('emergencyHazards')

        cleaned_slang = {}
        if custom_slang and isinstance(custom_slang, dict):
            for k, v in custom_slang.items():
                clean_k = str(k).lower().strip()
                clean_v = str(v).strip()
                if clean_k and clean_v:
                    SLANG_TECHNICAL_DICTIONARY[clean_k] = clean_v
                    cleaned_slang[clean_k] = clean_v

        cleaned_hazards = {}
        if custom_hazards and isinstance(custom_hazards, dict):
            for h_code, h_body in custom_hazards.items():
                if isinstance(h_body, dict) and 'keywords' in h_body:
                    EMERGENCY_HAZARDS[h_code] = h_body
                    cleaned_hazards[h_code] = h_body

        save_persisted_safety_config(cleaned_slang, cleaned_hazards)

        return Response({
            "success": True,
            "message": "Cấu hình an toàn và từ điển kỹ thuật đã được cập nhật thành công và lưu trữ lâu dài.",
            "data": {
                "slangDictionary": SLANG_TECHNICAL_DICTIONARY,
                "emergencyHazards": EMERGENCY_HAZARDS
            }
        }, status=status.HTTP_200_OK)

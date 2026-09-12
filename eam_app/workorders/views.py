from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError
from django.db import transaction, models
from workorders.models import WorkOrder
from workorders.serializers import (
    WorkOrderSerializer, WorkOrderCreateSerializer,
    WorkOrderAssignSerializer, WorkOrderStatusUpdateSerializer
)
from users.models import User
from users.permissions import HasPermission
from rest_framework.permissions import IsAuthenticated
from assets.views import success_response

class WorkOrderListView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        if not HasPermission('work_order:read')().has_permission(request, self):
            self.permission_denied(request)
            
        wos = WorkOrder.objects.all().order_by('-created_at')
        
        try:
            page = int(request.query_params.get('page', 0))
            size = int(request.query_params.get('size', 20))
        except ValueError:
            page = 0
            size = 20
            
        start = page * size
        end = start + size
        
        total_elements = wos.count()
        total_pages = (total_elements + size - 1) // size if size > 0 else 1
        is_last = (page + 1) >= total_pages or total_elements == 0

        serializer = WorkOrderSerializer(wos[start:end], many=True)
        return success_response({
            "content": serializer.data,
            "totalElements": total_elements,
            "totalPages": total_pages,
            "page": page,
            "size": size,
            "last": is_last
        })
        
    @transaction.atomic
    def post(self, request):
        if not HasPermission('work_order:create')().has_permission(request, self):
            self.permission_denied(request)
            
        serializer = WorkOrderCreateSerializer(data=request.data)
        if not serializer.is_valid():
            raise ValidationError(serializer.errors)
        data = serializer.validated_data
        
        wo = WorkOrder.objects.create(
            asset_id=data['assetId'],
            title=data['title'],
            description=data.get('description'),
            priority=data['priority'],
            deadline=data.get('deadline'),
            estimated_duration_minutes=data.get('estimatedDurationMinutes'),
            parent_id_id=data.get('parentId'),
            source_reference=data.get('sourceReference'),
            status='CREATED'
        )
        
        # Save Checklists
        from workorders.models import WorkOrderChecklistItem, WorkOrderMaterial
        from assets.models import SparePart
        
        checklists = data.get('checklists', [])
        for pc in checklists:
            WorkOrderChecklistItem.objects.create(
                work_order=wo,
                item_name=pc.get('itemName'),
                input_type=pc.get('inputType', 'PASS_FAIL'),
                expected_value=pc.get('expectedValue'),
                is_mandatory=pc.get('isMandatory', False),
                is_completed=False
            )
            
        # Save Materials and Deduct Inventory
        materials = data.get('materials', [])
        for pm in materials:
            part = get_object_or_404(SparePart, id=pm.get('sparePartId'), tenant_id=wo.tenant_id)
            req_qty = pm.get('quantity')
            if part.quantity_in_stock is not None:
                if part.quantity_in_stock < req_qty:
                    raise ValidationError(f"Không đủ số lượng trong kho cho vật tư: {part.name}")
                part.quantity_in_stock -= req_qty
                part.save()
                
            WorkOrderMaterial.objects.create(
                work_order=wo,
                spare_part=part,
                quantity=req_qty
            )
        
        # Mock Async Event
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[KAFKA MOCK] workorder.events - WorkOrderCreatedEvent: wo_id={wo.id}")
        
        return success_response(WorkOrderSerializer(wo).data)

class WorkOrderDetailView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, wo_id):
        if not HasPermission('work_order:read')().has_permission(request, self):
            self.permission_denied(request)
            
        try:
            wo = WorkOrder.objects.get(id=wo_id)
        except WorkOrder.DoesNotExist:
            raise ValidationError("Work Order not found")
            
        return success_response(WorkOrderSerializer(wo).data)
        
    @transaction.atomic
    def put(self, request, wo_id):
        if not HasPermission('work_order:update')().has_permission(request, self):
            self.permission_denied(request)
            
        try:
            wo = WorkOrder.objects.get(id=wo_id)
        except WorkOrder.DoesNotExist:
            raise ValidationError("Work Order not found")
            
        if wo.status not in ['CREATED', 'ASSIGNED']:
            raise ValidationError('Cannot edit a Work Order that is in progress, completed or canceled')
            
        serializer = WorkOrderCreateSerializer(data=request.data)
        if not serializer.is_valid():
            raise ValidationError(serializer.errors)
        data = serializer.validated_data
        
        wo.asset_id = data['assetId']
        wo.title = data['title']
        wo.description = data.get('description')
        wo.priority = data['priority']
        wo.deadline = data.get('deadline')
        wo.estimated_duration_minutes = data.get('estimatedDurationMinutes')
        wo.save()
        
        from workorders.models import WorkOrderChecklistItem, WorkOrderMaterial
        from assets.models import SparePart
        
        # Update Checklists
        if 'checklists' in data:
            wo.checklists.all().delete()
            for pc in data['checklists']:
                WorkOrderChecklistItem.objects.create(
                    work_order=wo,
                    item_name=pc.get('itemName'),
                    input_type=pc.get('inputType', 'PASS_FAIL'),
                    expected_value=pc.get('expectedValue'),
                    is_mandatory=pc.get('isMandatory', False),
                    is_completed=False
                )
                
        # Update Materials
        if 'materials' in data:
            # Restore old inventory
            old_materials = wo.materials.all()
            for old_wm in old_materials:
                part = old_wm.spare_part
                if part.quantity_in_stock is not None:
                    part.quantity_in_stock += old_wm.quantity
                    part.save()
            old_materials.delete()
            
            # Save new materials
            for pm in data['materials']:
                part = get_object_or_404(SparePart, id=pm.get('sparePartId'), tenant_id=wo.tenant_id)
                req_qty = pm.get('quantity')
                if part.quantity_in_stock is not None:
                    if part.quantity_in_stock < req_qty:
                        raise ValidationError(f"Không đủ số lượng trong kho cho vật tư: {part.name}")
                    part.quantity_in_stock -= req_qty
                    part.save()
                    
                WorkOrderMaterial.objects.create(
                    work_order=wo,
                    spare_part=part,
                    quantity=req_qty
                )
        
        return success_response(WorkOrderSerializer(wo).data)
        
    @transaction.atomic
    def delete(self, request, wo_id):
        if not HasPermission('work_order:delete')().has_permission(request, self):
            self.permission_denied(request)
            
        try:
            wo = WorkOrder.objects.get(id=wo_id)
        except WorkOrder.DoesNotExist:
            raise ValidationError("Work Order not found")
            
        if wo.status not in ['CREATED', 'ASSIGNED']:
            raise ValidationError('Only CREATED or ASSIGNED Work Orders can be deleted')
            
        # Restore inventory
        old_materials = wo.materials.all()
        for old_wm in old_materials:
            part = old_wm.spare_part
            if part.quantity_in_stock is not None:
                part.quantity_in_stock += old_wm.quantity
                part.save()
            
        wo.delete()
        return success_response(None)

class WorkOrderAssignView(APIView):
    permission_classes = [IsAuthenticated]
    
    @transaction.atomic
    def put(self, request, wo_id):
        if not HasPermission('work_order:update')().has_permission(request, self):
            self.permission_denied(request)
            
        try:
            wo = WorkOrder.objects.get(id=wo_id)
        except WorkOrder.DoesNotExist:
            raise ValidationError("Work Order not found")
            
        if wo.status in ['COMPLETED', 'CANCELLED']:
            raise ValidationError('Cannot reassign a completed or canceled work order')
            
        serializer = WorkOrderAssignSerializer(data=request.data)
        if not serializer.is_valid():
            raise ValidationError(serializer.errors)
            
        assignee_id = serializer.validated_data['assignedTo']
        try:
            assignee = User.objects.get(id=assignee_id)
        except User.DoesNotExist:
            raise ValidationError("Assignee not found")
            
        is_reassigned = wo.assigned_to is not None
        wo.assigned_to = assignee
        wo.assigned_at = timezone.now()
        
        if is_reassigned and wo.status == 'IN_PROGRESS':
            wo.status = 'ASSIGNED'
            wo.actual_start_time = None
        elif wo.status == 'CREATED':
            wo.status = 'ASSIGNED'
            
        wo.save()
        
        # Mock Async Event
        import logging
        logger = logging.getLogger(__name__)
        event_type = "work_order.reassigned" if is_reassigned else "work_order.assigned"
        logger.info(f"[KAFKA MOCK] work_orders_topic - {event_type}: wo_id={wo.id}, assignee={assignee_id}")
        
        return success_response(WorkOrderSerializer(wo).data)

class WorkOrderStatusView(APIView):
    permission_classes = [IsAuthenticated]
    
    @transaction.atomic
    def put(self, request, wo_id):
        has_exec = HasPermission('work_order:execute')().has_permission(request, self)
        has_upd = HasPermission('work_order:update')().has_permission(request, self)
        if not (has_exec or has_upd):
            self.permission_denied(request)
            
        try:
            wo = WorkOrder.objects.get(id=wo_id)
        except WorkOrder.DoesNotExist:
            raise ValidationError("Work Order not found")
            
        serializer = WorkOrderStatusUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            raise ValidationError(serializer.errors)
        data = serializer.validated_data
        new_status = data['status']
        
        if wo.status == new_status:
            return success_response(WorkOrderSerializer(wo).data)
            
        if new_status == 'ASSIGNED':
            raise ValidationError('Cannot manually change status to ASSIGNED')
            
        if new_status == 'IN_PROGRESS':
            if wo.status != 'ASSIGNED':
                raise ValidationError('Work Order can only be started from ASSIGNED state')
            if wo.assigned_to_id != request.user.id and not has_upd:
                raise ValidationError('Only the assignee can start the Work Order')
            wo.actual_start_time = timezone.now()
            
        if new_status == 'COMPLETED':
            if wo.status != 'IN_PROGRESS':
                raise ValidationError('Work Order can only be completed from IN_PROGRESS state')
            if wo.assigned_to_id != request.user.id and not has_upd:
                raise ValidationError('Only the assignee can complete the Work Order')
                
            resolution_notes = data.get('resolutionNotes')
            
            has_notes = bool(resolution_notes) or bool(wo.resolution_notes and wo.resolution_notes.strip())
            has_attachments = wo.attachments.exists()
            
            if not has_notes and not has_attachments:
                raise ValidationError('Vui lòng nhập ghi chú sửa chữa hoặc tải lên ít nhất một hình ảnh minh chứng trước khi hoàn thành công việc.')
                
            for item in wo.checklists.all():
                if item.is_mandatory and not item.is_completed:
                    raise ValidationError(f"Không thể hoàn thành: Chưa hoàn thành bước bắt buộc '{item.item_name}'")
                
            if resolution_notes:
                wo.resolution_notes = resolution_notes
            wo.actual_duration_minutes = data.get('actualDurationMinutes')
            wo.completed_at = timezone.now()
            
        if new_status == 'CANCELLED':
            if wo.status == 'COMPLETED':
                raise ValidationError('Cannot cancel a COMPLETED Work Order')
                
        wo.status = new_status
        wo.save()
        
        if new_status == 'COMPLETED':
            # Mock Async Event
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"[KAFKA MOCK] work_orders_topic - work_order.completed: wo_id={wo.id}")
            
        return success_response(WorkOrderSerializer(wo).data)

class WorkOrderChecklistView(APIView):
    permission_classes = [IsAuthenticated]
    
    @transaction.atomic
    def post(self, request, wo_id):
        has_exec = HasPermission('work_order:execute')().has_permission(request, self)
        has_upd = HasPermission('work_order:update')().has_permission(request, self)
        if not (has_exec or has_upd):
            self.permission_denied(request)
            
        try:
            wo = WorkOrder.objects.get(id=wo_id)
        except WorkOrder.DoesNotExist:
            raise ValidationError("Work Order not found")
            
        if wo.assigned_to_id != request.user.id and not has_upd:
            self.permission_denied(request)
            
        from workorders.serializers import WorkOrderChecklistItemRequestSerializer, WorkOrderChecklistItemSerializer
        serializer = WorkOrderChecklistItemRequestSerializer(data=request.data)
        if not serializer.is_valid():
            raise ValidationError(serializer.errors)
        data = serializer.validated_data
        
        from workorders.models import WorkOrderChecklistItem
        item = wo.checklists.filter(item_name=data['itemName']).first()
        if not item:
            item = WorkOrderChecklistItem(
                work_order=wo,
                item_name=data['itemName'],
                is_mandatory=False,
                input_type='PASS_FAIL'
            )
            
        item.is_completed = data['isCompleted']
        if 'actualValue' in data:
            item.actual_value = data['actualValue']
        item.save()
        
        return success_response(WorkOrderChecklistItemSerializer(item).data)

class WorkOrderChecklistDeleteView(APIView):
    permission_classes = [IsAuthenticated]
    
    @transaction.atomic
    def delete(self, request, wo_id, checklist_id):
        has_exec = HasPermission('work_order:execute')().has_permission(request, self)
        has_upd = HasPermission('work_order:update')().has_permission(request, self)
        if not (has_exec or has_upd):
            self.permission_denied(request)
            
        try:
            wo = WorkOrder.objects.get(id=wo_id)
        except WorkOrder.DoesNotExist:
            raise ValidationError("Work Order not found")
            
        if wo.assigned_to_id != request.user.id and not has_upd:
            self.permission_denied(request)
            
        from workorders.models import WorkOrderChecklistItem
        import uuid
        is_uuid = False
        try:
            uuid.UUID(str(checklist_id))
            is_uuid = True
        except ValueError:
            is_uuid = False

        item = None
        if is_uuid:
            item = WorkOrderChecklistItem.objects.filter(id=checklist_id, work_order=wo).first()
        if not item:
            item = WorkOrderChecklistItem.objects.filter(item_name=str(checklist_id), work_order=wo).first()

        if item:
            item.delete()
            return success_response(None)
            
        raise ValidationError("Checklist item not found")

class WorkOrderNoteUpdateView(APIView):
    permission_classes = [IsAuthenticated]
    
    @transaction.atomic
    def put(self, request, wo_id):
        has_exec = HasPermission('work_order:execute')().has_permission(request, self)
        has_upd = HasPermission('work_order:update')().has_permission(request, self)
        if not (has_exec or has_upd):
            self.permission_denied(request)
            
        try:
            wo = WorkOrder.objects.get(id=wo_id)
        except WorkOrder.DoesNotExist:
            raise ValidationError("Work Order not found")
            
        if wo.assigned_to_id != request.user.id and not has_upd:
            self.permission_denied(request)
            
        from workorders.serializers import WorkOrderNoteUpdateRequestSerializer
        serializer = WorkOrderNoteUpdateRequestSerializer(data=request.data)
        if not serializer.is_valid():
            raise ValidationError(serializer.errors)
            
        wo.resolution_notes = serializer.validated_data.get('resolutionNotes') or serializer.validated_data.get('notes', '')
        wo.save()
        return success_response(WorkOrderSerializer(wo).data)

class WorkOrderAttachmentView(APIView):
    permission_classes = [IsAuthenticated]
    
    @transaction.atomic
    def post(self, request, wo_id):
        has_exec = HasPermission('work_order:execute')().has_permission(request, self)
        has_upd = HasPermission('work_order:update')().has_permission(request, self)
        if not (has_exec or has_upd):
            self.permission_denied(request)
            
        try:
            wo = WorkOrder.objects.get(id=wo_id)
        except WorkOrder.DoesNotExist:
            raise ValidationError("Work Order not found")
            
        if wo.assigned_to_id != request.user.id and not has_upd:
            self.permission_denied(request)
            
        file_obj = request.FILES.get('file')
        if not file_obj:
            raise ValidationError("File cannot be empty")
            
        if file_obj.size > 5 * 1024 * 1024:
            raise ValidationError("File size exceeds 5MB limit")
            
        content_type = file_obj.content_type
        if not content_type or not content_type.startswith('image/'):
            raise ValidationError("Only image files are allowed")
            
        import os
        import uuid
        from django.conf import settings
        from minio import Minio

        file_url = None
        bucket_name = getattr(settings, 'MINIO_BUCKET_NAME', 'tenant-assets')
        extension = os.path.splitext(file_obj.name)[1]
        object_name = f"tenant-{wo.tenant_id}/work-orders/{wo.id}/{uuid.uuid4()}{extension}"

        # Upload directly to MinIO
        try:
            client = Minio(
                settings.MINIO_ENDPOINT,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=getattr(settings, 'MINIO_SECURE', False)
            )
            if not client.bucket_exists(bucket_name):
                client.make_bucket(bucket_name)
                import json
                policy = {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": {"AWS": "*"},
                            "Action": ["s3:GetObject"],
                            "Resource": [f"arn:aws:s3:::{bucket_name}/*"]
                        }
                    ]
                }
                client.set_bucket_policy(bucket_name, json.dumps(policy))

            file_obj.seek(0)
            client.put_object(
                bucket_name,
                object_name,
                file_obj,
                length=file_obj.size,
                content_type=content_type
            )
            file_url = f"/{bucket_name}/{object_name}"
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"MinIO upload failed, falling back to default_storage: {e}")
            from django.core.files.storage import default_storage
            file_obj.seek(0)
            file_path = default_storage.save(f"tenant-{wo.tenant_id}/work-orders/{wo.id}/{file_obj.name}", file_obj)
            file_url = default_storage.url(file_path)
            if not file_url.startswith('/') and not file_url.startswith('http'):
                file_url = f"/{file_url}"
        
        from workorders.models import WorkOrderAttachment
        from workorders.serializers import WorkOrderAttachmentSerializer
        
        attachment = WorkOrderAttachment.objects.create(
            work_order=wo,
            file_url=file_url,
            file_name=file_obj.name,
            file_type=content_type,
            file_size=file_obj.size
        )
        
        return success_response(WorkOrderAttachmentSerializer(attachment).data)

class WorkOrderAttachmentDeleteView(APIView):
    permission_classes = [IsAuthenticated]
    
    @transaction.atomic
    def delete(self, request, wo_id, attachment_id):
        has_exec = HasPermission('work_order:execute')().has_permission(request, self)
        has_upd = HasPermission('work_order:update')().has_permission(request, self)
        if not (has_exec or has_upd):
            self.permission_denied(request)
            
        try:
            wo = WorkOrder.objects.get(id=wo_id)
        except WorkOrder.DoesNotExist:
            raise ValidationError("Work Order not found")
            
        if wo.assigned_to_id != request.user.id and not has_upd:
            self.permission_denied(request)
            
        from workorders.models import WorkOrderAttachment
        try:
            attachment = WorkOrderAttachment.objects.get(id=attachment_id, work_order=wo)
            # In a real app we would delete from storage here
            attachment.delete()
        except WorkOrderAttachment.DoesNotExist:
            raise ValidationError("Attachment not found")
            
        return success_response(None)

class WorkOrderKpiView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not HasPermission('work_order:read')().has_permission(request, self):
            self.permission_denied(request)

        tenant = request.user.tenant
        
        total = WorkOrder.objects.filter(tenant=tenant).count()
        in_progress = WorkOrder.objects.filter(tenant=tenant, status='IN_PROGRESS').count()
        completed = WorkOrder.objects.filter(tenant=tenant, status='COMPLETED').count()
        
        overdue = WorkOrder.objects.filter(
            tenant=tenant,
            deadline__lt=timezone.now(),
        ).exclude(status__in=['COMPLETED', 'CANCELLED']).count()

        return success_response({
            "totalWorkOrders": total,
            "inProgressWorkOrders": in_progress,
            "completedWorkOrders": completed,
            "overdueWorkOrders": overdue
        })

class MaintenanceCalendarView(APIView):
    from rest_framework.authentication import SessionAuthentication
    from rest_framework_simplejwt.authentication import JWTAuthentication
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not HasPermission('work_order:read')().has_permission(request, self):
            self.permission_denied(request)

        tenant = request.user.tenant
        start_date_str = request.query_params.get('startDate')
        end_date_str = request.query_params.get('endDate')
        asset_id = request.query_params.get('assetId')
        category_id = request.query_params.get('categoryId')
        status = request.query_params.get('status')

        from django.utils.dateparse import parse_datetime
        
        start_date = parse_datetime(start_date_str) if start_date_str else timezone.now().replace(day=1)
        end_date = parse_datetime(end_date_str) if end_date_str else timezone.now()

        events = []

        wo_qs = WorkOrder.objects.filter(tenant=tenant)
        if asset_id:
            wo_qs = wo_qs.filter(asset_id=asset_id)
        if category_id:
            wo_qs = wo_qs.filter(asset__category_id=category_id)
        
        if status and status != 'SCHEDULED':
            wo_qs = wo_qs.filter(status=status)
            
        wo_qs = wo_qs.filter(
            models.Q(deadline__range=(start_date, end_date)) | 
            models.Q(deadline__isnull=True, created_at__range=(start_date, end_date))
        )

        for wo in wo_qs:
            event_date = wo.deadline if wo.deadline else wo.created_at
            events.append({
                "id": str(wo.id),
                "title": wo.title,
                "eventDate": event_date.isoformat() if event_date else None,
                "eventType": "WORK_ORDER",
                "status": wo.status,
                "priority": wo.priority,
                "assetId": str(wo.asset_id) if wo.asset_id else None,
                "assetName": wo.asset.name if wo.asset else None,
                "originalData": WorkOrderSerializer(wo).data
            })

        if status and status != 'SCHEDULED':
            return success_response(events)

        # Append PM Plans
        from maintenance.models import PmPlanAssignment
        from dateutil.relativedelta import relativedelta
        import time
        
        pm_qs = PmPlanAssignment.objects.filter(tenant=tenant, status='ACTIVE', pm_plan__trigger_type='TIME')
        if asset_id:
            pm_qs = pm_qs.filter(asset_id=asset_id)
        if category_id:
            pm_qs = pm_qs.filter(asset__category_id=category_id)

        for assignment in pm_qs:
            plan = assignment.pm_plan
            interval = plan.interval_value
            unit = plan.interval_unit
            if not interval or interval <= 0 or not unit:
                continue

            ref_date = assignment.last_triggered_at or assignment.created_at
            due_date = ref_date

            while due_date <= end_date:
                if unit == 'DAYS':
                    due_date += relativedelta(days=int(interval))
                elif unit == 'WEEKS':
                    due_date += relativedelta(weeks=int(interval))
                elif unit == 'MONTHS':
                    due_date += relativedelta(months=int(interval))
                elif unit == 'YEARS':
                    due_date += relativedelta(years=int(interval))
                else:
                    break

                if due_date >= start_date and due_date <= end_date:
                    ts = int(time.mktime(due_date.timetuple()) * 1000)
                    
                    # Construct originalData for PM_PLAN
                    materials_list = []
                    for mat in plan.materials.all():
                        materials_list.append({
                            "id": str(mat.id),
                            "sparePartId": str(mat.spare_part.id) if mat.spare_part else None,
                            "sparePartName": mat.spare_part.name if mat.spare_part else None,
                            "quantity": float(mat.quantity)
                        })
                        
                    assignee_data = None
                    if plan.assignee:
                        assignee_data = {
                            "username": plan.assignee.username,
                            "fullName": plan.assignee.get_full_name() if hasattr(plan.assignee, 'get_full_name') else None
                        }
                    
                    original_data = {
                        "estimatedDurationMinutes": plan.estimated_duration_minutes,
                        "assignee": assignee_data,
                        "materials": materials_list
                    }
                    
                    events.append({
                        "id": f"{assignment.id}_proj_{ts}",
                        "title": f"PM: {plan.name}",
                        "eventDate": due_date.isoformat(),
                        "eventType": "PM_PLAN",
                        "status": "SCHEDULED",
                        "priority": "MEDIUM",
                        "assetId": str(assignment.asset_id) if assignment.asset_id else None,
                        "assetName": assignment.asset.name if assignment.asset else None,
                        "originalData": original_data
                    })

        return success_response(events)

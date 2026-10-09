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
    WorkOrderAssignSerializer, WorkOrderStatusUpdateSerializer,
    WorkOrderAutoAssignPreviewRequestSerializer,
    WorkOrderAutoAssignApplyRequestSerializer,
    WorkOrderGAAutoAssignInitiateRequestSerializer,
    WorkOrderGAApplyRequestSerializer,
    WorkOrderAlgorithmReadinessRequestSerializer
)
from algorithms.hungarian.service import HungarianAssignmentService, ConcurrencyConflictError
from algorithms.genetic.service import GASchedulingService
from workorders.models import GAOptimizationJob
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
        
        priority = data['priority']
        deadline = data.get('deadline')
        if not deadline:
            now_dt = timezone.now()
            from datetime import timedelta
            if priority == 'URGENT':
                deadline = now_dt + timedelta(hours=2)
            elif priority == 'HIGH':
                deadline = now_dt + timedelta(hours=4)
            elif priority == 'LOW':
                deadline = now_dt + timedelta(hours=72)
            else:  # MEDIUM
                deadline = now_dt + timedelta(hours=24)

        from assets.models import Asset
        asset_obj = Asset.objects.filter(id=data['assetId']).first()
        coords_x = float(asset_obj.coords_x) if (asset_obj and asset_obj.coords_x is not None) else 0.0
        coords_y = float(asset_obj.coords_y) if (asset_obj and asset_obj.coords_y is not None) else 0.0
        floor_level = int(asset_obj.floor_level) if (asset_obj and asset_obj.floor_level is not None) else 1
        zone_id = asset_obj.zone_id if (asset_obj and asset_obj.zone_id) else ''

        wo = WorkOrder.objects.create(
            asset_id=data['assetId'],
            title=data['title'],
            description=data.get('description'),
            priority=priority,
            deadline=deadline,
            estimated_duration_minutes=data.get('estimatedDurationMinutes'),
            parent_id_id=data.get('parentId'),
            source_reference=data.get('sourceReference'),
            status='CREATED',
            coords_x=coords_x,
            coords_y=coords_y,
            floor_level=floor_level,
            zone_id=zone_id,
            required_skill=data.get('requiredSkill', 'GENERAL') or 'GENERAL'
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
                from notifications.services import notify_spare_part_low_stock
                notify_spare_part_low_stock(part)
                
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
        
        # Dispatch Notification to Assignee
        from notifications.services import notify_work_order_assigned
        notify_work_order_assigned(wo, assignee=assignee, is_reassigned=is_reassigned)

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

            # Event-based technician positioning: snap tech coords & zone to machine
            assigned_user = wo.assigned_to or request.user
            if hasattr(assigned_user, 'technician_profile'):
                tp = assigned_user.technician_profile
                snap_x = wo.coords_x or (wo.asset.coords_x if wo.asset else None)
                snap_y = wo.coords_y or (wo.asset.coords_y if wo.asset else None)
                snap_zone = wo.zone_id or (wo.asset.zone_id if wo.asset else None)
                snap_floor = wo.floor_level or (wo.asset.floor_level if wo.asset else None)
                if snap_x is not None: tp.coords_x = snap_x
                if snap_y is not None: tp.coords_y = snap_y
                if snap_zone: tp.zone_id = snap_zone
                if snap_floor: tp.floor_level = snap_floor
                tp.availability_status = 'BUSY'
                tp.save()

            # Dispatch real-time notification to supervisor / creator
            try:
                from notifications.services import notify_work_order_started
                notify_work_order_started(wo, technician=assigned_user)
            except Exception:
                pass
            
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

            # Event-based technician positioning: return tech to duty zone station
            assigned_user = wo.assigned_to or request.user
            if hasattr(assigned_user, 'technician_profile'):
                tp = assigned_user.technician_profile
                tp.availability_status = 'AVAILABLE'
                from users.models import TechnicianSchedule
                from assets.models import Location
                today_sched = TechnicianSchedule.objects.filter(
                    tenant=wo.tenant,
                    user=assigned_user,
                    work_date=timezone.now().date(),
                    status='ON_DUTY'
                ).first()
                if today_sched and today_sched.duty_zone_id:
                    loc = Location.objects.filter(tenant=wo.tenant, code=today_sched.duty_zone_id).first()
                    if loc:
                        tp.zone_id = loc.code
                        tp.coords_x = loc.center_x or 25.0
                        tp.coords_y = loc.center_y or 20.0
                        tp.floor_level = loc.floor_level or 1
                tp.save()

            # Dispatch real-time notification to supervisor / creator
            try:
                from notifications.services import notify_work_order_completed
                notify_work_order_completed(wo, technician=assigned_user)
            except Exception:
                pass
            
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


class WorkOrderAutoAssignPreviewView(APIView):
    """
    POST /api/v1/work-orders/auto-assign/preview/
    Evaluates optimal Kuhn-Munkres assignment plan with 10 guardrails.
    Returns explainable cost matrix, assignment proposals, and conflict warnings.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not HasPermission('work_order:read')().has_permission(request, self):
            self.permission_denied(request)

        serializer = WorkOrderAutoAssignPreviewRequestSerializer(data=request.data)
        if not serializer.is_valid():
            raise ValidationError(serializer.errors)

        work_order_ids = serializer.validated_data.get('workOrderIds')
        tenant = getattr(request.user, 'tenant', None)

        preview_result = HungarianAssignmentService.preview(
            tenant=tenant,
            work_order_ids=work_order_ids
        )
        return success_response(preview_result)


class WorkOrderAutoAssignApplyView(APIView):
    """
    POST /api/v1/work-orders/auto-assign/apply/
    Atomically locks candidate records and applies approved assignment plan.
    Dispatches Kafka/WebSocket/DB assignment notifications.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not HasPermission('work_order:update')().has_permission(request, self):
            self.permission_denied(request)

        serializer = WorkOrderAutoAssignApplyRequestSerializer(data=request.data)
        if not serializer.is_valid():
            raise ValidationError(serializer.errors)

        assignments_data = serializer.validated_data.get('assignments')
        tenant = getattr(request.user, 'tenant', None)

        try:
            apply_result = HungarianAssignmentService.apply(
                tenant=tenant,
                assignments_data=assignments_data,
                current_user=request.user
            )
            return success_response(apply_result, message="Phân công công việc tối ưu thành công.")
        except ConcurrencyConflictError as e:
            return Response({
                "success": False,
                "error": {
                    "code": "CONCURRENT_DISPATCH_CONFLICT",
                    "message": str(e)
                }
            }, status=status.HTTP_409_CONFLICT)
        except ValidationError as e:
            return Response({
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": str(e)
                }
            }, status=status.HTTP_400_BAD_REQUEST)


class WorkOrderGAAutoAssignInitiateView(APIView):
    """
    POST /api/v1/work-orders/ga-auto-assign/
    Initiates asynchronous multi-objective Genetic Algorithm scheduling task.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not HasPermission('work_order:read')().has_permission(request, self):
            self.permission_denied(request)

        serializer = WorkOrderGAAutoAssignInitiateRequestSerializer(data=request.data)
        if not serializer.is_valid():
            raise ValidationError(serializer.errors)

        tenant = getattr(request.user, 'tenant', None)
        floorplan_id = serializer.validated_data.get('floorplanId')
        work_order_ids = serializer.validated_data.get('workOrderIds')
        max_generations = serializer.validated_data.get('maxGenerations', 150)
        population_size = serializer.validated_data.get('populationSize', 100)

        job = GASchedulingService.initiate_optimization(
            tenant=tenant,
            user=request.user,
            floorplan_id=str(floorplan_id) if floorplan_id else None,
            work_order_ids=work_order_ids,
            max_generations=max_generations,
            population_size=population_size
        )

        return Response({
            "success": True,
            "data": {
                "taskId": str(job.id),
                "status": job.status,
                "message": "Tác vụ tối ưu hóa phân công ca GA đã được khởi tạo và đang xử lý ngầm."
            }
        }, status=status.HTTP_202_ACCEPTED)


class WorkOrderGAAutoAssignProgressView(APIView):
    """
    GET /api/v1/work-orders/ga-auto-assign/<task_id>/progress/
    Polls evolution progress, generation convergence curve, and Pareto front solutions.
    Strictly isolated by tenant (anti-IDOR).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, task_id):
        tenant = getattr(request.user, 'tenant', None)
        try:
            job = GAOptimizationJob.objects.select_related('floorplan').get(id=task_id, tenant=tenant)
        except GAOptimizationJob.DoesNotExist:
            return Response({
                "success": False,
                "error": {
                    "code": "JOB_NOT_FOUND",
                    "message": "Tác vụ GA không tồn tại hoặc bạn không có quyền truy cập."
                }
            }, status=status.HTTP_404_NOT_FOUND)

        floorplan_name = job.floorplan.name if job.floorplan else "Tất cả mặt bằng (Toàn nhà máy)"

        return success_response({
            "taskId": str(job.id),
            "status": job.status,
            "floorplanId": str(job.floorplan_id) if job.floorplan_id else None,
            "floorplanName": floorplan_name,
            "currentGeneration": job.current_generation,
            "maxGenerations": job.max_generations,
            "bestFitness": round(job.best_fitness, 1),
            "convergenceHistory": job.convergence_history or [],
            "paretoSolutions": job.pareto_solutions or [],
            "errorMessage": job.error_message
        })


class WorkOrderGAAutoAssignApplyView(APIView):
    """
    POST /api/v1/work-orders/ga-auto-assign/apply/
    Atomically applies approved Pareto assignment plan to the database.
    Dispatches real-time notification alerts.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not HasPermission('work_order:update')().has_permission(request, self):
            self.permission_denied(request)

        serializer = WorkOrderGAApplyRequestSerializer(data=request.data)
        if not serializer.is_valid():
            raise ValidationError(serializer.errors)

        assignments_data = serializer.validated_data.get('assignments')
        tenant = getattr(request.user, 'tenant', None)

        try:
            apply_result = GASchedulingService.apply_solution(
                tenant=tenant,
                assignments_data=assignments_data,
                current_user=request.user
            )
            return success_response(apply_result, message="Phân công công việc bằng giải thuật GA thành công.")
        except ConcurrencyConflictError as e:
            return Response({
                "success": False,
                "error": {
                    "code": "CONCURRENT_DISPATCH_CONFLICT",
                    "message": str(e)
                }
            }, status=status.HTTP_409_CONFLICT)
        except ValidationError as e:
            return Response({
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": str(e)
                }
            }, status=status.HTTP_400_BAD_REQUEST)


class WorkOrderAlgorithmReadinessView(APIView):
    """
    POST /api/v1/work-orders/algorithm-readiness/
    Pre-checks all prerequisites before executing Hungarian or Genetic Algorithm:
    - Verifies whether technicians exist in the tenant.
    - Verifies whether any technicians are on-duty and available.
    - Verifies whether eligible, unblocked work orders exist.
    - Evaluates floorplan scope constraints if applicable.
    Returns clear, human-readable explanations and action recommendations if conditions fail.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not HasPermission('work_order:read')().has_permission(request, self):
            self.permission_denied(request)

        serializer = WorkOrderAlgorithmReadinessRequestSerializer(data=request.data)
        if not serializer.is_valid():
            raise ValidationError(serializer.errors)

        algorithm = serializer.validated_data.get('algorithm', 'HUNGARIAN')
        work_order_ids = serializer.validated_data.get('workOrderIds', [])
        floorplan_id = serializer.validated_data.get('floorplanId')
        tenant = getattr(request.user, 'tenant', None)
        now = timezone.now()

        from users.models import User, TechnicianProfile, TechnicianSchedule
        from django.db.models import Q
        from algorithms.hungarian.service import filter_task_dependencies

        issues = []

        # 1. Evaluate Technicians
        # A. Total active technicians with work_order:execute permission
        base_tech_users = User.objects.filter(
            tenant=tenant,
            status='ACTIVE'
        ).filter(
            Q(roles__permissions__id='work_order:execute') | Q(roles__isnull=True)
        ).distinct()
        total_techs = base_tech_users.count()

        if total_techs == 0:
            issues.append("Hệ thống chưa có tài khoản kỹ thuật viên nào được phân quyền thực hiện công việc (work_order:execute).")

        # B. Available & On-duty Technicians
        available_tech_profiles = TechnicianProfile.objects.filter(
            tenant=tenant,
            is_on_duty=True,
            availability_status='AVAILABLE',
            user__status='ACTIVE'
        ).filter(
            Q(user__roles__permissions__id='work_order:execute') | Q(user__roles__isnull=True)
        ).distinct().select_related('user')

        # Exclude technicians on OFF or LEAVE today
        try:
            off_tech_ids = set(TechnicianSchedule.objects.filter(
                tenant=tenant,
                work_date=now.date(),
                status__in=['OFF', 'LEAVE']
            ).values_list('user_id', flat=True))
            if off_tech_ids:
                available_tech_profiles = available_tech_profiles.exclude(user_id__in=off_tech_ids)
        except Exception:
            pass

        available_techs_count = available_tech_profiles.count()

        if total_techs > 0 and available_techs_count == 0:
            issues.append(f"Không có kỹ thuật viên nào đang rảnh (AVAILABLE) hoặc đang trực ca (ON DUTY) để tiếp nhận công việc (Tổng số thợ: {total_techs}).")

        # 2. Evaluate Work Orders
        eligible_wos_count = 0
        blocked_wos_count = 0

        if work_order_ids and len(work_order_ids) > 0:
            selected_wos = list(
                WorkOrder.objects.filter(tenant=tenant, id__in=work_order_ids)
                .select_related('depends_on_wo', 'asset')
            )
            # Filter out completed/cancelled
            active_selected = [w for w in selected_wos if w.status not in ['COMPLETED', 'CANCELED', 'CANCELLED']]
            if not active_selected:
                issues.append("Các phiếu công việc bạn tích chọn đều đã hoàn thành hoặc đã bị hủy, không thể phân công.")
            else:
                eligible_wos, blocked_wos = filter_task_dependencies(active_selected)
                eligible_wos_count = len(eligible_wos)
                blocked_wos_count = len(blocked_wos)
                if not eligible_wos:
                    issues.append(f"Tất cả {len(active_selected)} phiếu công việc được chọn đều đang bị khóa do phụ thuộc vào công việc khác chưa hoàn tất.")
        else:
            # Automatic candidate selection
            if algorithm == 'HUNGARIAN':
                created_wos = list(
                    WorkOrder.objects.filter(tenant=tenant, status='CREATED')
                    .select_related('depends_on_wo', 'asset')
                )
                if not created_wos:
                    issues.append("Không có phiếu công việc nào ở trạng thái chờ phân công (CREATED). Hãy tạo phiếu mới hoặc tích chọn cụ thể các phiếu cần gán.")
                else:
                    eligible_wos, blocked_wos = filter_task_dependencies(created_wos)
                    eligible_wos_count = len(eligible_wos)
                    blocked_wos_count = len(blocked_wos)
                    if not eligible_wos:
                        issues.append(f"Tất cả {len(created_wos)} phiếu công việc mới đều đang bị khóa do phụ thuộc vào công việc khác chưa hoàn tất.")
            else:
                # GENETIC
                from datetime import timedelta
                shift_horizon_cutoff = now + timedelta(hours=24)
                time_window_q = Q(deadline__isnull=True) | Q(deadline__lte=shift_horizon_cutoff)

                ga_wo_qs = WorkOrder.objects.filter(tenant=tenant).exclude(status__in=['COMPLETED', 'CANCELED', 'CANCELLED'])
                if floorplan_id:
                    fp_id_str = str(floorplan_id)
                    ga_wo_qs = ga_wo_qs.filter(
                        Q(asset__location__parent_id=fp_id_str) |
                        Q(asset__location_id=fp_id_str)
                    )

                pending_qs = ga_wo_qs.filter(status__in=['CREATED', 'PENDING'])
                pending_in_window = pending_qs.filter(time_window_q)
                if pending_in_window.exists():
                    target_wos = list(pending_in_window.select_related('depends_on_wo'))
                elif pending_qs.exists():
                    target_wos = list(pending_qs.select_related('depends_on_wo'))
                else:
                    assigned_qs = ga_wo_qs.filter(status='ASSIGNED')
                    target_wos = list(assigned_qs.select_related('depends_on_wo'))

                if not target_wos:
                    issues.append("Không có phiếu công việc nào cần lập lịch hoặc phân bổ ca trực trong phạm vi đã chọn.")
                else:
                    eligible_wos, blocked_wos = filter_task_dependencies(target_wos)
                    eligible_wos_count = len(eligible_wos)
                    blocked_wos_count = len(blocked_wos)
                    if not eligible_wos:
                        issues.append(f"Tất cả {len(target_wos)} phiếu công việc đều đang bị khóa do phụ thuộc vào công việc khác chưa hoàn tất.")

        can_run = (len(issues) == 0)
        algo_display_name = "Hungary Kuhn-Munkres" if algorithm == 'HUNGARIAN' else "Di truyền (Genetic Algorithm)"

        return success_response({
            "canRun": can_run,
            "algorithm": algorithm,
            "algorithmName": algo_display_name,
            "issues": issues,
            "summary": {
                "totalTechnicians": total_techs,
                "availableTechnicians": available_techs_count,
                "eligibleWorkOrders": eligible_wos_count,
                "blockedWorkOrders": blocked_wos_count
            }
        })



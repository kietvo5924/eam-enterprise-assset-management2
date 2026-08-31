from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError

from maintenance.models import PmPlan, PmPlanChecklistItem, PmPlanMaterial, PmPlanAssignment
from maintenance.serializers import (
    PmPlanSerializer, PmPlanCreateUpdateSerializer,
    PmPlanAssignmentSerializer, PmPlanAssignRequestSerializer
)
from assets.models import Asset, SparePart
from users.models import User
from users.permissions import HasPermission
from rest_framework.permissions import IsAuthenticated
from assets.views import success_response

class PmPlanListView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        if not HasPermission('pm_plan:read')().has_permission(request, self):
            self.permission_denied(request)
            
        plans = PmPlan.objects.all().order_by('-created_at')
        return success_response({
            "content": PmPlanSerializer(plans, many=True).data,
            "totalElements": plans.count()
        })
        
    @transaction.atomic
    def post(self, request):
        if not HasPermission('pm_plan:create')().has_permission(request, self):
            self.permission_denied(request)
            
        serializer = PmPlanCreateUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            print("PM PLAN VALIDATION ERROR:", serializer.errors)
            raise ValidationError(serializer.errors)
        data = serializer.validated_data
        
        plan = PmPlan.objects.create(
            name=data['name'],
            description=data.get('description'),
            trigger_type=data['triggerType'],
            interval_value=data.get('intervalValue'),
            interval_unit=data.get('intervalUnit'),
            is_active=data.get('isActive', True),
            is_floating_schedule=data.get('isFloatingSchedule', False),
            suppress_if_pending=data.get('suppressIfPending', True),
            lead_time_days=data.get('leadTimeDays', 0),
            estimated_duration_minutes=data.get('estimatedDurationMinutes'),
            assignee_id=data.get('assigneeId')
        )
        
        # Checklists
        checklists = data.get('checklists', [])
        for pc in checklists:
            PmPlanChecklistItem.objects.create(
                pm_plan=plan,
                item_name=pc.get('itemName'),
                input_type=pc.get('inputType', 'PASS_FAIL'),
                expected_value=pc.get('expectedValue'),
                is_mandatory=pc.get('isMandatory', False)
            )
            
        # Materials
        materials = data.get('materials', [])
        for pm in materials:
            part = get_object_or_404(SparePart, id=pm.get('sparePartId'), tenant_id=plan.tenant_id)
            PmPlanMaterial.objects.create(
                pm_plan=plan,
                spare_part=part,
                quantity=pm.get('quantity')
            )
            
        return success_response(PmPlanSerializer(plan).data)

class PmPlanDetailView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, plan_id):
        if not HasPermission('pm_plan:read')().has_permission(request, self):
            self.permission_denied(request)
            
        plan = get_object_or_404(PmPlan, id=plan_id)
        return success_response(PmPlanSerializer(plan).data)
        
    @transaction.atomic
    def put(self, request, plan_id):
        if not HasPermission('pm_plan:update')().has_permission(request, self):
            self.permission_denied(request)
            
        plan = get_object_or_404(PmPlan, id=plan_id)
        serializer = PmPlanCreateUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            raise ValidationError(serializer.errors)
        data = serializer.validated_data
        
        plan.name = data['name']
        plan.description = data.get('description')
        plan.trigger_type = data['triggerType']
        plan.interval_value = data.get('intervalValue')
        plan.interval_unit = data.get('intervalUnit')
        plan.is_active = data.get('isActive', True)
        plan.is_floating_schedule = data.get('isFloatingSchedule', False)
        plan.suppress_if_pending = data.get('suppressIfPending', True)
        plan.lead_time_days = data.get('leadTimeDays', 0)
        plan.estimated_duration_minutes = data.get('estimatedDurationMinutes')
        plan.assignee_id = data.get('assigneeId')
        plan.save()
        
        if 'checklists' in data:
            plan.checklists.all().delete()
            for pc in data['checklists']:
                PmPlanChecklistItem.objects.create(
                    pm_plan=plan,
                    item_name=pc.get('itemName'),
                    input_type=pc.get('inputType', 'PASS_FAIL'),
                    expected_value=pc.get('expectedValue'),
                    is_mandatory=pc.get('isMandatory', False)
                )
                
        if 'materials' in data:
            plan.materials.all().delete()
            for pm in data['materials']:
                part = get_object_or_404(SparePart, id=pm.get('sparePartId'), tenant_id=plan.tenant_id)
                PmPlanMaterial.objects.create(
                    pm_plan=plan,
                    spare_part=part,
                    quantity=pm.get('quantity')
                )
                
        return success_response(PmPlanSerializer(plan).data)
        
    @transaction.atomic
    def delete(self, request, plan_id):
        if not HasPermission('pm_plan:delete')().has_permission(request, self):
            self.permission_denied(request)
            
        plan = get_object_or_404(PmPlan, id=plan_id)
        
        from workorders.models import WorkOrder
        has_wos = WorkOrder.objects.filter(source_reference__startswith=f"PM_{plan.id}_ASSET_").exists()
        if has_wos:
            raise ValidationError("Không thể xóa PM Plan này vì đã có Work Order được sinh ra từ nó. Vui lòng vô hiệu hóa (Deactivate) thay vì xóa.")
            
        plan.assignments.all().delete()
        plan.delete()
        return success_response(None)

class PmPlanKpiView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        if not HasPermission('pm_plan:read')().has_permission(request, self):
            self.permission_denied(request)
            
        tenant = request.user.tenant
        total_plans = PmPlan.objects.filter(tenant=tenant).count()
        
        from workorders.models import WorkOrder
        missed_pms = WorkOrder.objects.filter(
            tenant=tenant,
            source_reference__startswith="PM_",
            deadline__lt=django.utils.timezone.now()
        ).exclude(status__in=['COMPLETED', 'CANCELLED']).count()
        
        total_pm_wos = WorkOrder.objects.filter(tenant=tenant, source_reference__startswith="PM_").count()
        completed_pm_wos = WorkOrder.objects.filter(tenant=tenant, source_reference__startswith="PM_", status='COMPLETED').count()
        
        compliance_rate = 100.0
        if total_pm_wos > 0:
            compliance_rate = (completed_pm_wos / total_pm_wos) * 100.0
            
        return success_response({
            "totalPlans": total_plans,
            "upcomingIn7Days": 0,
            "missedPms": missed_pms,
            "complianceRate": compliance_rate
        })

class PmPlanAssignmentView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, plan_id):
        if not HasPermission('pm_plan:read')().has_permission(request, self):
            self.permission_denied(request)
            
        plan = get_object_or_404(PmPlan, id=plan_id)
        assignments = plan.assignments.all().order_by('-assigned_at')
        return success_response({
            "content": PmPlanAssignmentSerializer(assignments, many=True).data,
            "totalElements": assignments.count()
        })
        
    @transaction.atomic
    def post(self, request, plan_id):
        if not HasPermission('pm_plan:update')().has_permission(request, self):
            self.permission_denied(request)
            
        plan = get_object_or_404(PmPlan, id=plan_id)
        serializer = PmPlanAssignRequestSerializer(data=request.data)
        if not serializer.is_valid():
            raise ValidationError(serializer.errors)
        data = serializer.validated_data
        
        assigned = []
        for asset_id in data['assetIds']:
            asset = get_object_or_404(Asset, id=asset_id, tenant_id=plan.tenant_id)
            
            # Check if already assigned
            if PmPlanAssignment.objects.filter(pm_plan=plan, asset=asset).exists():
                continue
                
            assignment = PmPlanAssignment.objects.create(
                pm_plan=plan,
                asset=asset,
                baseline_meter_reading=data.get('baselineMeterReading')
            )
            assigned.append(assignment)
            
        return success_response(PmPlanAssignmentSerializer(assigned, many=True).data)

class PmPlanAssignmentDetailView(APIView):
    permission_classes = [IsAuthenticated]
    
    @transaction.atomic
    def delete(self, request, assignment_id):
        if not HasPermission('pm_plan:update')().has_permission(request, self):
            self.permission_denied(request)
            
        assignment = get_object_or_404(PmPlanAssignment, id=assignment_id)
        
        from workorders.models import WorkOrder
        source_ref = f"PM_{assignment.pm_plan.id}_ASSET_{assignment.asset.id}"
        if WorkOrder.objects.filter(source_reference=source_ref).exists():
            raise ValidationError("Cannot delete this assignment because Work Orders have already been generated. Please Pause or Deactivate instead.")
            
        assignment.delete()
        return success_response(None)

class PmPlanAssignmentStatusView(APIView):
    permission_classes = [IsAuthenticated]
    
    @transaction.atomic
    def patch(self, request, assignment_id):
        if not HasPermission('pm_plan:update')().has_permission(request, self):
            self.permission_denied(request)
            
        assignment = get_object_or_404(PmPlanAssignment, id=assignment_id)
        
        status_val = request.data.get('status')
        if status_val not in dict(PmPlanAssignment.STATUS_CHOICES):
            raise ValidationError("Invalid status")
            
        assignment.status = status_val
        assignment.save()
        return success_response(PmPlanAssignmentSerializer(assignment).data)

from rest_framework import serializers
from maintenance.models import PmPlan, PmPlanChecklistItem, PmPlanMaterial, PmPlanAssignment
from assets.serializers import AssetSerializer, SparePartSerializer
from users.serializers import UserSerializer

class PmPlanChecklistItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = PmPlanChecklistItem
        fields = ['id', 'itemName', 'inputType', 'expectedValue', 'isMandatory']
        
    itemName = serializers.CharField(source='item_name')
    inputType = serializers.CharField(source='input_type')
    expectedValue = serializers.CharField(source='expected_value', required=False, allow_null=True)
    isMandatory = serializers.BooleanField(source='is_mandatory')


class PmPlanMaterialSerializer(serializers.ModelSerializer):
    sparePart = SparePartSerializer(source='spare_part', read_only=True)
    sparePartId = serializers.UUIDField(source='spare_part_id')
    
    class Meta:
        model = PmPlanMaterial
        fields = ['id', 'sparePartId', 'sparePart', 'quantity']


class PmPlanAssignmentSerializer(serializers.ModelSerializer):
    asset = AssetSerializer(read_only=True)
    assetId = serializers.UUIDField(source='asset_id')
    
    class Meta:
        model = PmPlanAssignment
        fields = [
            'id', 'assetId', 'asset', 'status', 'assignedAt',
            'baselineMeterReading', 'lastTriggeredAt', 'lastTriggeredMeter'
        ]
        
    assignedAt = serializers.DateTimeField(source='assigned_at', read_only=True)
    baselineMeterReading = serializers.DecimalField(source='baseline_meter_reading', max_digits=19, decimal_places=2, required=False, allow_null=True)
    lastTriggeredAt = serializers.DateTimeField(source='last_triggered_at', read_only=True)
    lastTriggeredMeter = serializers.DecimalField(source='last_triggered_meter', max_digits=19, decimal_places=2, read_only=True)


class PmPlanSerializer(serializers.ModelSerializer):
    assignee = UserSerializer(read_only=True)
    assigneeId = serializers.UUIDField(source='assignee_id', required=False, allow_null=True)
    checklists = PmPlanChecklistItemSerializer(many=True, read_only=True)
    materials = PmPlanMaterialSerializer(many=True, read_only=True)
    
    class Meta:
        model = PmPlan
        fields = [
            'id', 'name', 'description', 'triggerType', 'intervalValue',
            'intervalUnit', 'isActive', 'isFloatingSchedule', 'suppressIfPending',
            'leadTimeDays', 'estimatedDurationMinutes', 'assigneeId', 'assignee',
            'checklists', 'materials', 'created_at', 'updated_at'
        ]
        
    triggerType = serializers.CharField(source='trigger_type')
    intervalValue = serializers.DecimalField(source='interval_value', max_digits=19, decimal_places=2, required=False, allow_null=True)
    intervalUnit = serializers.CharField(source='interval_unit', required=False, allow_null=True)
    isActive = serializers.BooleanField(source='is_active')
    isFloatingSchedule = serializers.BooleanField(source='is_floating_schedule')
    suppressIfPending = serializers.BooleanField(source='suppress_if_pending')
    leadTimeDays = serializers.IntegerField(source='lead_time_days')
    estimatedDurationMinutes = serializers.IntegerField(source='estimated_duration_minutes', required=False, allow_null=True)


class PmPlanCreateUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    triggerType = serializers.ChoiceField(choices=PmPlan.TRIGGER_CHOICES)
    intervalValue = serializers.DecimalField(max_digits=19, decimal_places=2, required=False, allow_null=True)
    intervalUnit = serializers.ChoiceField(choices=PmPlan.INTERVAL_UNIT_CHOICES, required=False, allow_null=True)
    isActive = serializers.BooleanField(default=True)
    isFloatingSchedule = serializers.BooleanField(default=False)
    suppressIfPending = serializers.BooleanField(default=True)
    leadTimeDays = serializers.IntegerField(default=0)
    estimatedDurationMinutes = serializers.IntegerField(required=False, allow_null=True)
    assigneeId = serializers.UUIDField(required=False, allow_null=True)
    
    checklists = serializers.ListField(child=serializers.DictField(), required=False)
    materials = serializers.ListField(child=serializers.DictField(), required=False)


class PmPlanAssignRequestSerializer(serializers.Serializer):
    assetIds = serializers.ListField(child=serializers.UUIDField())
    baselineMeterReading = serializers.DecimalField(max_digits=19, decimal_places=2, required=False, allow_null=True)

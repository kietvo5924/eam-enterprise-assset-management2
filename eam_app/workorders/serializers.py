from rest_framework import serializers
from workorders.models import WorkOrder, WorkOrderChecklistItem, WorkOrderAttachment, WorkOrderMaterial
from assets.serializers import AssetSerializer, SparePartSerializer
from users.serializers import UserSerializer

class NullableUUIDField(serializers.UUIDField):
    """
    UUIDField treats empty string or whitespace-only string as None.
    Prevents HTML form selects sending "" for optional UUID from causing validation errors.
    """
    def to_internal_value(self, data):
        if data == '' or data is None or (isinstance(data, str) and not data.strip()):
            return None
        return super().to_internal_value(data)

class WorkOrderChecklistItemSerializer(serializers.ModelSerializer):
    itemName = serializers.CharField(source='item_name')
    isCompleted = serializers.BooleanField(source='is_completed')
    completed = serializers.BooleanField(source='is_completed')
    inputType = serializers.CharField(source='input_type')
    expectedValue = serializers.CharField(source='expected_value', required=False, allow_null=True)
    actualValue = serializers.CharField(source='actual_value', required=False, allow_null=True)
    isMandatory = serializers.BooleanField(source='is_mandatory')
    
    class Meta:
        model = WorkOrderChecklistItem
        fields = ['id', 'itemName', 'isCompleted', 'completed', 'inputType', 'expectedValue', 'actualValue', 'isMandatory']

class WorkOrderAttachmentSerializer(serializers.ModelSerializer):
    fileUrl = serializers.CharField(source='file_url')
    fileName = serializers.CharField(source='file_name')
    fileType = serializers.CharField(source='file_type')
    fileSize = serializers.IntegerField(source='file_size')
    
    class Meta:
        model = WorkOrderAttachment
        fields = ['id', 'fileUrl', 'fileName', 'fileType', 'fileSize']

class WorkOrderMaterialSerializer(serializers.ModelSerializer):
    sparePart = SparePartSerializer(source='spare_part', read_only=True)
    sparePartId = serializers.UUIDField(source='spare_part_id')
    actualCost = serializers.DecimalField(source='actual_cost', max_digits=19, decimal_places=2, required=False, allow_null=True)
    
    class Meta:
        model = WorkOrderMaterial
        fields = ['id', 'sparePartId', 'sparePart', 'quantity', 'actualCost']

class WorkOrderSerializer(serializers.ModelSerializer):
    code = serializers.CharField(read_only=True)
    assetId = serializers.UUIDField(source='asset.id', read_only=True)
    assignedTo = serializers.UUIDField(source='assigned_to.id', read_only=True)
    parentId = serializers.UUIDField(source='parent_id.id', read_only=True)
    estimatedDurationMinutes = serializers.IntegerField(source='estimated_duration_minutes', read_only=True)
    actualDurationMinutes = serializers.IntegerField(source='actual_duration_minutes', read_only=True)
    sourceReference = serializers.CharField(source='source_reference', read_only=True)
    actualStartTime = serializers.DateTimeField(source='actual_start_time', read_only=True)
    assignedAt = serializers.DateTimeField(source='assigned_at', read_only=True)
    completedAt = serializers.DateTimeField(source='completed_at', read_only=True)
    resolutionNotes = serializers.CharField(source='resolution_notes', read_only=True)
    assigneeName = serializers.CharField(source='assigned_to.username', read_only=True, default=None)
    assignee = UserSerializer(source='assigned_to', read_only=True)
    
    coordsX = serializers.FloatField(source='coords_x', read_only=True)
    coordsY = serializers.FloatField(source='coords_y', read_only=True)
    floorLevel = serializers.IntegerField(source='floor_level', read_only=True)
    zoneId = serializers.CharField(source='zone_id', read_only=True)
    incidentLocationId = serializers.UUIDField(source='incident_location.id', read_only=True, default=None)
    maintenanceWindowStart = serializers.TimeField(source='maintenance_window_start', read_only=True, default=None)
    maintenanceWindowEnd = serializers.TimeField(source='maintenance_window_end', read_only=True, default=None)

    asset = AssetSerializer(read_only=True)
    checklists = WorkOrderChecklistItemSerializer(many=True, read_only=True)
    attachments = WorkOrderAttachmentSerializer(many=True, read_only=True)
    materials = WorkOrderMaterialSerializer(many=True, read_only=True)

    maintenanceAction = serializers.CharField(source='maintenance_action', read_only=True)
    completionProcessedAt = serializers.DateTimeField(source='completion_processed_at', read_only=True)
    postRepairVibration = serializers.FloatField(source='post_repair_vibration', read_only=True)
    postRepairTemperature = serializers.FloatField(source='post_repair_temperature', read_only=True)
    postRepairLoadFactor = serializers.FloatField(source='post_repair_load_factor', read_only=True)

    class Meta:
        model = WorkOrder
        fields = [
            'id', 'code', 'assetId', 'parentId', 'title', 'description', 
            'priority', 'status', 'deadline', 'assignedTo', 'assigneeName',
            'assignee',
            'estimatedDurationMinutes', 'actualDurationMinutes',
            'sourceReference', 'actualStartTime', 'assignedAt',
            'completedAt', 'resolutionNotes', 'coordsX', 'coordsY',
            'floorLevel', 'zoneId', 'incidentLocationId',
            'maintenanceWindowStart', 'maintenanceWindowEnd',
            'maintenanceAction', 'completionProcessedAt',
            'postRepairVibration', 'postRepairTemperature', 'postRepairLoadFactor',
            'created_at', 'updated_at',
            'asset', 'checklists', 'attachments', 'materials'
        ]

class WorkOrderCreateSerializer(serializers.Serializer):
    assetId = serializers.UUIDField()
    title = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    priority = serializers.ChoiceField(choices=WorkOrder.PRIORITY_CHOICES)
    deadline = serializers.DateTimeField(required=False, allow_null=True)
    assignedTo = NullableUUIDField(required=False, allow_null=True)
    parentId = NullableUUIDField(required=False, allow_null=True)
    incidentLocationId = NullableUUIDField(required=False, allow_null=True)
    maintenanceWindowStart = serializers.TimeField(required=False, allow_null=True)
    maintenanceWindowEnd = serializers.TimeField(required=False, allow_null=True)
    sourceReference = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)
    estimatedDurationMinutes = serializers.IntegerField(required=False, allow_null=True)
    checklists = serializers.ListField(
        child=serializers.DictField(), required=False
    )
    materials = serializers.ListField(
        child=serializers.DictField(), required=False
    )
    requiredTools = serializers.ListField(
        child=serializers.CharField(), required=False, default=list
    )
    requiredSpareParts = serializers.ListField(
        child=serializers.CharField(), required=False, default=list
    )
    maintenanceAction = serializers.CharField(required=False, default='GENERAL')

class WorkOrderAssignSerializer(serializers.Serializer):
    assignedTo = serializers.UUIDField()

class WorkOrderStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=WorkOrder.STATUS_CHOICES)
    resolutionNotes = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    actualDurationMinutes = serializers.IntegerField(required=False, allow_null=True)
    maintenanceAction = serializers.ChoiceField(
        choices=WorkOrder.MAINTENANCE_ACTION_CHOICES,
        required=False,
        default='GENERAL'
    )
    postRepairVibration = serializers.FloatField(required=False, allow_null=True)
    postRepairTemperature = serializers.FloatField(required=False, allow_null=True)
    postRepairLoadFactor = serializers.FloatField(required=False, allow_null=True, default=1.0)
    
class WorkOrderChecklistItemRequestSerializer(serializers.Serializer):
    id = serializers.UUIDField(required=False, allow_null=True)
    itemId = serializers.UUIDField(required=False, allow_null=True)
    itemName = serializers.CharField(max_length=255, required=False)
    item_name = serializers.CharField(max_length=255, required=False)
    isCompleted = serializers.BooleanField(required=False)
    completed = serializers.BooleanField(required=False)
    actualValue = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    inputType = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    input_type = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    expectedValue = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)
    expected_value = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)
    isMandatory = serializers.BooleanField(required=False, allow_null=True)
    is_mandatory = serializers.BooleanField(required=False, allow_null=True)

    def validate(self, attrs):
        item_id = attrs.get('id') or attrs.get('itemId')
        if item_id:
            attrs['id'] = item_id
        name = attrs.get('itemName') or attrs.get('item_name')
        if not name:
            raise serializers.ValidationError("itemName or item_name is required")
        attrs['itemName'] = name

        comp = attrs.get('isCompleted')
        if comp is None:
            comp = attrs.get('completed')
        if comp is None:
            comp = False
        attrs['isCompleted'] = comp

        input_type = attrs.get('inputType') or attrs.get('input_type')
        if input_type:
            attrs['inputType'] = input_type

        expected_val = attrs.get('expectedValue') or attrs.get('expected_value')
        if expected_val is not None:
            attrs['expectedValue'] = expected_val

        is_mand = attrs.get('isMandatory')
        if is_mand is None:
            is_mand = attrs.get('is_mandatory')
        if is_mand is not None:
            attrs['isMandatory'] = is_mand

        return attrs

class WorkOrderNoteUpdateRequestSerializer(serializers.Serializer):
    resolutionNotes = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        if not attrs.get('resolutionNotes') and not attrs.get('notes'):
            raise serializers.ValidationError("resolutionNotes or notes is required")
        return attrs


class WorkOrderAutoAssignPreviewRequestSerializer(serializers.Serializer):
    workOrderIds = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        default=list
    )


class WorkOrderAssignmentPairSerializer(serializers.Serializer):
    workOrderId = serializers.UUIDField()
    technicianId = serializers.UUIDField()
    slotRole = serializers.CharField(required=False, default='SOLO')


class WorkOrderAutoAssignApplyRequestSerializer(serializers.Serializer):
    assignments = serializers.ListField(
        child=WorkOrderAssignmentPairSerializer(),
        allow_empty=False
    )


class WorkOrderGAAutoAssignInitiateRequestSerializer(serializers.Serializer):
    floorplanId = NullableUUIDField(required=False, allow_null=True)
    workOrderIds = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        default=list
    )
    maxGenerations = serializers.IntegerField(required=False, default=150, min_value=10, max_value=500)
    populationSize = serializers.IntegerField(required=False, default=100, min_value=20, max_value=300)


class WorkOrderGAApplyRequestSerializer(serializers.Serializer):
    assignments = serializers.ListField(
        child=WorkOrderAssignmentPairSerializer(),
        allow_empty=False
    )


class WorkOrderAlgorithmReadinessRequestSerializer(serializers.Serializer):
    algorithm = serializers.ChoiceField(choices=['HUNGARIAN', 'GENETIC'], default='HUNGARIAN')
    workOrderIds = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        default=list
    )
    floorplanId = NullableUUIDField(required=False, allow_null=True)


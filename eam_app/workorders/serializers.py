from rest_framework import serializers
from workorders.models import WorkOrder, WorkOrderChecklistItem, WorkOrderAttachment, WorkOrderMaterial
from assets.serializers import AssetSerializer, SparePartSerializer
from users.serializers import UserSerializer

class WorkOrderChecklistItemSerializer(serializers.ModelSerializer):
    itemName = serializers.CharField(source='item_name')
    isCompleted = serializers.BooleanField(source='is_completed')
    inputType = serializers.CharField(source='input_type')
    expectedValue = serializers.CharField(source='expected_value', required=False, allow_null=True)
    actualValue = serializers.CharField(source='actual_value', required=False, allow_null=True)
    isMandatory = serializers.BooleanField(source='is_mandatory')
    
    class Meta:
        model = WorkOrderChecklistItem
        fields = ['id', 'itemName', 'isCompleted', 'inputType', 'expectedValue', 'actualValue', 'isMandatory']

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
    
    asset = AssetSerializer(read_only=True)
    checklists = WorkOrderChecklistItemSerializer(many=True, read_only=True)
    attachments = WorkOrderAttachmentSerializer(many=True, read_only=True)
    materials = WorkOrderMaterialSerializer(many=True, read_only=True)

    class Meta:
        model = WorkOrder
        fields = [
            'id', 'assetId', 'parentId', 'title', 'description', 
            'priority', 'status', 'deadline', 'assignedTo',
            'estimatedDurationMinutes', 'actualDurationMinutes',
            'sourceReference', 'actualStartTime', 'assignedAt',
            'completedAt', 'resolutionNotes', 'created_at', 'updated_at',
            'asset', 'checklists', 'attachments', 'materials'
        ]

class WorkOrderCreateSerializer(serializers.Serializer):
    assetId = serializers.UUIDField()
    title = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    priority = serializers.ChoiceField(choices=WorkOrder.PRIORITY_CHOICES)
    deadline = serializers.DateTimeField(required=False, allow_null=True)
    assignedTo = serializers.UUIDField(required=False, allow_null=True)
    parentId = serializers.UUIDField(required=False, allow_null=True)
    sourceReference = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)
    estimatedDurationMinutes = serializers.IntegerField(required=False, allow_null=True)
    checklists = serializers.ListField(
        child=serializers.DictField(), required=False
    )
    materials = serializers.ListField(
        child=serializers.DictField(), required=False
    )

class WorkOrderAssignSerializer(serializers.Serializer):
    assignedTo = serializers.UUIDField()

class WorkOrderStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=WorkOrder.STATUS_CHOICES)
    resolutionNotes = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    actualDurationMinutes = serializers.IntegerField(required=False, allow_null=True)
    
class WorkOrderChecklistItemRequestSerializer(serializers.Serializer):
    itemName = serializers.CharField(max_length=255)
    isCompleted = serializers.BooleanField()
    actualValue = serializers.CharField(required=False, allow_blank=True, allow_null=True)

class WorkOrderNoteUpdateRequestSerializer(serializers.Serializer):
    resolutionNotes = serializers.CharField(required=True)

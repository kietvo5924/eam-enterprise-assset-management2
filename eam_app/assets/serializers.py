from rest_framework import serializers
from assets.models import Location, AssetCategory, HierarchyTemplate, SparePart, Asset, MeterReading

class LocationSerializer(serializers.ModelSerializer):
    parentId = serializers.CharField(source='parent_id', read_only=True)
    code = serializers.CharField(read_only=True)
    zoneType = serializers.CharField(source='zone_type', read_only=True)
    floorLevel = serializers.IntegerField(source='floor_level', read_only=True)
    centerX = serializers.FloatField(source='center_x', read_only=True)
    centerY = serializers.FloatField(source='center_y', read_only=True)
    floorplanImage = serializers.CharField(source='floorplan_image', read_only=True)
    hasFloorplan = serializers.SerializerMethodField()
    isActive = serializers.BooleanField(source='is_active', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)

    def get_hasFloorplan(self, obj):
        return bool(obj.floorplan_image)

    class Meta:
        model = Location
        fields = ['id', 'parentId', 'code', 'name', 'zoneType', 'floorLevel', 'centerX', 'centerY', 'floorplanImage', 'hasFloorplan', 'description', 'isActive', 'createdAt', 'updatedAt']

class LocationCreateUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    description = serializers.CharField(max_length=1000, required=False, allow_blank=True, allow_null=True)
    parentId = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)
    isActive = serializers.BooleanField(required=False, default=True)

class AssetCategorySerializer(serializers.ModelSerializer):
    isActive = serializers.BooleanField(source='is_active', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)

    class Meta:
        model = AssetCategory
        fields = ['id', 'name', 'description', 'isActive', 'createdAt', 'updatedAt']

class AssetCategoryCreateUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    description = serializers.CharField(max_length=1000, required=False, allow_blank=True, allow_null=True)
    isActive = serializers.BooleanField(required=False, default=True)

class HierarchyTemplateSerializer(serializers.ModelSerializer):
    isActive = serializers.BooleanField(source='is_active', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)

    class Meta:
        model = HierarchyTemplate
        fields = ['id', 'name', 'path', 'description', 'isActive', 'createdAt', 'updatedAt']

class HierarchyTemplateCreateUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    path = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)
    description = serializers.CharField(max_length=1000, required=False, allow_blank=True, allow_null=True)
    isActive = serializers.BooleanField(required=False, default=True)

class SparePartSerializer(serializers.ModelSerializer):
    partNumber = serializers.CharField(source='part_number', read_only=True)
    quantityInStock = serializers.DecimalField(source='quantity_in_stock', read_only=True, max_digits=19, decimal_places=2)
    unitCost = serializers.DecimalField(source='unit_cost', read_only=True, max_digits=19, decimal_places=2)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)

    class Meta:
        model = SparePart
        fields = ['id', 'name', 'partNumber', 'description', 'quantityInStock', 'unitCost', 'createdAt', 'updatedAt']

class SparePartCreateUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    partNumber = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)
    description = serializers.CharField(max_length=1000, required=False, allow_blank=True, allow_null=True)
    quantityInStock = serializers.DecimalField(max_digits=19, decimal_places=2, required=False, default=0.00)
    unitCost = serializers.DecimalField(max_digits=19, decimal_places=2, required=False, allow_null=True)

class AssetSerializer(serializers.ModelSerializer):
    categoryId = serializers.UUIDField(source='category.id', read_only=True)
    categoryName = serializers.CharField(source='category.name', read_only=True)
    locationId = serializers.UUIDField(source='location.id', read_only=True)
    locationName = serializers.CharField(source='location.name', read_only=True)
    hierarchyTemplateId = serializers.UUIDField(source='hierarchy_template.id', read_only=True)
    hierarchyTemplateName = serializers.CharField(source='hierarchy_template.name', read_only=True)
    parentId = serializers.CharField(source='parent_id', read_only=True)
    serialNumber = serializers.CharField(source='serial_number', read_only=True)
    purchaseDate = serializers.DateField(source='purchase_date', read_only=True)
    qrCode = serializers.CharField(source='qr_code', read_only=True)
    isActive = serializers.BooleanField(source='is_active', read_only=True)
    coordsX = serializers.FloatField(source='coords_x', read_only=True)
    coordsY = serializers.FloatField(source='coords_y', read_only=True)
    floorLevel = serializers.IntegerField(source='floor_level', read_only=True)
    zoneId = serializers.CharField(source='zone_id', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)
    
    class Meta:
        model = Asset
        fields = ['id', 'categoryId', 'categoryName', 'parentId', 'name', 'serialNumber', 'model', 'manufacturer', 
                  'purchaseDate', 'value', 'status', 'locationId', 'locationName', 'hierarchyTemplateId', 
                  'hierarchyTemplateName', 'qrCode', 'isActive', 'coordsX', 'coordsY', 'floorLevel', 'zoneId',
                  'createdAt', 'updatedAt']

class AssetCreateUpdateSerializer(serializers.Serializer):
    categoryId = serializers.UUIDField(required=False, allow_null=True)
    parentId = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)
    name = serializers.CharField(max_length=255)
    serialNumber = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)
    model = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)
    manufacturer = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)
    purchaseDate = serializers.DateField(required=False, allow_null=True)
    value = serializers.DecimalField(max_digits=19, decimal_places=2, required=False, allow_null=True)
    status = serializers.ChoiceField(choices=Asset.STATUS_CHOICES, required=False, default='OPERATIONAL')
    locationId = serializers.UUIDField(required=False, allow_null=True)
    hierarchyTemplateId = serializers.UUIDField(required=False, allow_null=True)
    qrCode = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)
    isActive = serializers.BooleanField(required=False, default=True)

from assets.models import AssetAnomalyAlert

class MeterReadingSerializer(serializers.ModelSerializer):
    assetId = serializers.UUIDField(source='asset.id', read_only=True)
    workOrderId = serializers.UUIDField(source='work_order.id', read_only=True, allow_null=True)
    workOrderCode = serializers.CharField(source='work_order.code', read_only=True, allow_null=True)
    metricCode = serializers.CharField(source='metric_code', read_only=True)
    readingValue = serializers.DecimalField(source='reading_value', read_only=True, max_digits=19, decimal_places=2)
    value = serializers.DecimalField(source='reading_value', read_only=True, max_digits=19, decimal_places=2)
    readingDate = serializers.DateTimeField(source='reading_date', read_only=True)
    recordedAt = serializers.DateTimeField(source='reading_date', read_only=True)
    machineState = serializers.CharField(source='machine_state', read_only=True)
    ambientTemperature = serializers.FloatField(source='ambient_temperature', read_only=True)
    isPreRepair = serializers.BooleanField(source='is_pre_repair', read_only=True)
    isSuppressed = serializers.BooleanField(source='is_suppressed', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    
    class Meta:
        model = MeterReading
        fields = [
            'id', 'assetId', 'workOrderId', 'workOrderCode', 'metricCode', 'value', 'readingValue',
            'readingDate', 'recordedAt', 'unit', 'machineState',
            'ambientTemperature', 'isPreRepair', 'isSuppressed',
            'remarks', 'createdAt'
        ]

class SingleReadingItemSerializer(serializers.Serializer):
    metricCode = serializers.CharField(max_length=64, required=False, default='VIBRATION')
    value = serializers.FloatField(required=False)
    readingValue = serializers.FloatField(required=False)
    unit = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    remarks = serializers.CharField(max_length=1000, required=False, allow_blank=True, allow_null=True)

    def validate_metricCode(self, value):
        if not value or not str(value).strip():
            return 'VIBRATION'
        cleaned = str(value).strip().upper()
        import re
        if not re.match(r'^[A-Z0-9_\-]+$', cleaned):
            raise serializers.ValidationError("Mã chỉ số đo chỉ được chứa chữ cái, số, dấu gạch dưới hoặc gạch nối (VD: RPM, FLOW_RATE).")
        return cleaned

    def validate(self, attrs):
        val = attrs.get('value')
        if val is None:
            val = attrs.get('readingValue')
        if val is None:
            raise serializers.ValidationError("Giá trị đo (value hoặc readingValue) là bắt buộc.")
        import math
        if math.isnan(val) or math.isinf(val):
            raise serializers.ValidationError("Giá trị đo không được là NaN hoặc vô cực.")
        return attrs

class MeterReadingCreateSerializer(serializers.Serializer):
    # Hỗ trợ cả định dạng đa chỉ số (Condition Monitoring Round) lẫn đơn chỉ số
    readings = serializers.ListField(
        child=SingleReadingItemSerializer(),
        required=False,
        allow_empty=False
    )
    # Định dạng đơn chỉ số truyền thống
    readingValue = serializers.FloatField(required=False)
    value = serializers.FloatField(required=False)
    metricCode = serializers.CharField(max_length=64, required=False, default='VIBRATION')
    readingDate = serializers.DateTimeField(required=False, allow_null=True)
    recordedAt = serializers.DateTimeField(required=False, allow_null=True)
    unit = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    remarks = serializers.CharField(max_length=1000, required=False, allow_blank=True, allow_null=True)
    
    # Liên kết với Work Order đang thực thi (nếu có)
    workOrderId = serializers.UUIDField(required=False, allow_null=True)
    work_order_id = serializers.UUIDField(required=False, allow_null=True)

    # Ngữ cảnh kiểm tra hiện trường (Quy Tắc 1 & Quy Tắc 4)
    machineState = serializers.CharField(max_length=20, required=False, default='RUNNING')
    ambientTemperature = serializers.FloatField(required=False, allow_null=True)

    def validate_metricCode(self, value):
        if not value or not str(value).strip():
            return 'VIBRATION'
        cleaned = str(value).strip().upper()
        import re
        if not re.match(r'^[A-Z0-9_\-]+$', cleaned):
            raise serializers.ValidationError("Mã chỉ số đo chỉ được chứa chữ cái, số, dấu gạch dưới hoặc gạch nối (VD: RPM, FLOW_RATE).")
        return cleaned

    def validate(self, attrs):
        readings = attrs.get('readings')
        if not readings:
            val = attrs.get('value')
            if val is None:
                val = attrs.get('readingValue')
            if val is None:
                raise serializers.ValidationError("Giá trị đo (value hoặc readingValue) là bắt buộc khi không có danh sách readings.")
            import math
            if math.isnan(val) or math.isinf(val):
                raise serializers.ValidationError("Giá trị đo không được là NaN hoặc vô cực.")
        return attrs


class AssetAnomalyAlertSerializer(serializers.ModelSerializer):
    assetId = serializers.UUIDField(source='asset.id', read_only=True)
    readingId = serializers.UUIDField(source='reading.id', read_only=True, allow_null=True)
    metricType = serializers.CharField(source='metric_type', read_only=True)
    metricCode = serializers.CharField(source='metric_code', read_only=True)
    currentValue = serializers.FloatField(source='current_value', read_only=True)
    zScore = serializers.FloatField(source='z_score', read_only=True)
    anomalyScore = serializers.FloatField(source='anomaly_score', read_only=True)
    trendSlope = serializers.FloatField(source='trend_slope', read_only=True)
    predictedFailureDate = serializers.DateField(source='predicted_failure_date', read_only=True)
    daysRemaining = serializers.IntegerField(source='days_remaining', read_only=True)
    severity = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    occurrenceCount = serializers.IntegerField(source='occurrence_count', read_only=True)
    isSuppressed = serializers.BooleanField(source='is_suppressed', read_only=True)
    draftWorkOrderId = serializers.UUIDField(source='draft_work_order.id', read_only=True, allow_null=True)
    draftWorkOrderCode = serializers.CharField(source='draft_work_order.code', read_only=True, allow_null=True)
    draftWorkOrderStatus = serializers.CharField(source='draft_work_order.status', read_only=True, allow_null=True)
    assignedTechnicianName = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    lastDetectedAt = serializers.DateTimeField(source='last_detected_at', read_only=True)

    def get_assignedTechnicianName(self, obj):
        if obj.draft_work_order and obj.draft_work_order.assigned_to:
            user = obj.draft_work_order.assigned_to
            return user.get_full_name() or user.username
        return None

    class Meta:
        model = AssetAnomalyAlert
        fields = [
            'id', 'assetId', 'readingId', 'metricType', 'metricCode',
            'currentValue', 'zScore', 'anomalyScore', 'trendSlope',
            'predictedFailureDate', 'daysRemaining', 'severity', 'status',
            'occurrenceCount', 'isSuppressed', 'draftWorkOrderId',
            'draftWorkOrderCode', 'draftWorkOrderStatus', 'assignedTechnicianName',
            'message', 'createdAt', 'lastDetectedAt'
        ]

from rest_framework import serializers
from assets.models import Location, AssetCategory, HierarchyTemplate, SparePart, Asset, MeterReading

class LocationSerializer(serializers.ModelSerializer):
    parentId = serializers.CharField(source='parent_id', read_only=True)
    isActive = serializers.BooleanField(source='is_active', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)

    class Meta:
        model = Location
        fields = ['id', 'parentId', 'name', 'description', 'isActive', 'createdAt', 'updatedAt']

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
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)
    
    class Meta:
        model = Asset
        fields = ['id', 'categoryId', 'categoryName', 'parentId', 'name', 'serialNumber', 'model', 'manufacturer', 
                  'purchaseDate', 'value', 'status', 'locationId', 'locationName', 'hierarchyTemplateId', 
                  'hierarchyTemplateName', 'qrCode', 'isActive', 'createdAt', 'updatedAt']

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
    qrCode = serializers.CharField(max_length=255)

class MeterReadingSerializer(serializers.ModelSerializer):
    assetId = serializers.UUIDField(source='asset.id', read_only=True)
    readingValue = serializers.DecimalField(source='reading_value', read_only=True, max_digits=19, decimal_places=2)
    readingDate = serializers.DateTimeField(source='reading_date', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    
    class Meta:
        model = MeterReading
        fields = ['id', 'assetId', 'readingValue', 'readingDate', 'unit', 'remarks', 'createdAt']

class MeterReadingCreateSerializer(serializers.Serializer):
    readingValue = serializers.DecimalField(max_digits=19, decimal_places=2)
    readingDate = serializers.DateTimeField(required=False, allow_null=True)
    unit = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    remarks = serializers.CharField(max_length=1000, required=False, allow_blank=True, allow_null=True)

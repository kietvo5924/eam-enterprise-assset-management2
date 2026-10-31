import unicodedata
import re
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction, models
from django.core.exceptions import ValidationError
from rest_framework.exceptions import NotFound
from assets.models import (
    Location, AssetCategory, HierarchyTemplate, SparePart, Asset,
    MeterReading, AssetAnomalyAlert, AssetRulPrediction
)
from assets.serializers import (
    LocationSerializer, LocationCreateUpdateSerializer,
    AssetCategorySerializer, AssetCategoryCreateUpdateSerializer,
    HierarchyTemplateSerializer, HierarchyTemplateCreateUpdateSerializer,
    SparePartSerializer, SparePartCreateUpdateSerializer,
    AssetSerializer, AssetCreateUpdateSerializer,
    MeterReadingSerializer, MeterReadingCreateSerializer,
    AssetAnomalyAlertSerializer
)
from users.permissions import HasPermission
from algorithms.anomaly_detection import ConditionMonitoringEngine, is_static_asset, evaluate_trend_drift

def success_response(data=None, message="Success"):
    return Response({
        "success": True,
        "message": message,
        "data": data
    }, status=status.HTTP_200_OK)

def error_response(message="Error", status_code=status.HTTP_400_BAD_REQUEST, errors=None):
    return Response({
        "success": False,
        "message": message,
        "errors": errors
    }, status=status_code)

def format_to_ltree(input_str):
    if not input_str:
        return None
    # Strip diacritics
    normalized = unicodedata.normalize('NFD', input_str)
    no_diacritics = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
    # Replace non-alphanumeric (except dots) with underscore
    ltree = re.sub(r'[^a-zA-Z0-9\.]', '_', no_diacritics)
    # Remove consecutive underscores and dots
    ltree = re.sub(r'_+', '_', ltree)
    ltree = re.sub(r'\.+', '.', ltree)
    # Strip trailing/leading dots or underscores
    ltree = re.sub(r'^[\._]+|[\._]+$', '', ltree)
    return ltree

class LocationListView(APIView):
    def get(self, request):
        has_loc = HasPermission('location:read')().has_permission(request, self)
        has_asset = HasPermission('asset:read')().has_permission(request, self)
        if not (has_loc or has_asset):
            self.permission_denied(request)
            
        locations = Location.objects.all()

        try:
            page = int(request.query_params.get('page', 0))
            size = int(request.query_params.get('size', 20))
        except ValueError:
            page, size = 0, 20

        total_elements = locations.count()
        start = page * size
        end = start + size
        locations_page = locations[start:end]

        serializer = LocationSerializer(locations_page, many=True)
        return success_response({
            "content": serializer.data,
            "totalElements": total_elements,
            "page": page,
            "size": size
        })

    @transaction.atomic
    def post(self, request):
        if not HasPermission('location:create')().has_permission(request, self):
            self.permission_denied(request)

        serializer = LocationCreateUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            raise ValidationError(serializer.errors)
            
        data = serializer.validated_data
        
        parent_id = data.get('parentId')
        if parent_id and not parent_id.strip():
            parent_id = None
        elif parent_id:
            parent_id = format_to_ltree(parent_id)
            
        location = Location.objects.create(
            name=data['name'],
            parent_id=parent_id,
            description=data.get('description'),
            is_active=data.get('isActive', True)
        )
        return success_response(LocationSerializer(location).data, message="Created")

class LocationDetailView(APIView):
    def get(self, request, location_id):
        has_loc = HasPermission('location:read')().has_permission(request, self)
        has_asset = HasPermission('asset:read')().has_permission(request, self)
        if not (has_loc or has_asset):
            self.permission_denied(request)
            
        try:
            location = Location.objects.get(id=location_id)
        except Location.DoesNotExist:
            raise ValidationError("Location not found")
            
        return success_response(LocationSerializer(location).data)

    @transaction.atomic
    def put(self, request, location_id):
        if not HasPermission('location:update')().has_permission(request, self):
            self.permission_denied(request)

        try:
            location = Location.objects.get(id=location_id)
        except Location.DoesNotExist:
            raise ValidationError("Location not found")
            
        serializer = LocationCreateUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            raise ValidationError(serializer.errors)
            
        data = serializer.validated_data
        
        location.name = data['name']
        
        parent_id = data.get('parentId')
        if parent_id and not parent_id.strip():
            parent_id = None
        elif parent_id:
            parent_id = format_to_ltree(parent_id)
            
        location.parent_id = parent_id
        
        if 'description' in data:
            location.description = data['description']
        if 'isActive' in data:
            location.is_active = data['isActive']
            
        location.save()
        return success_response(LocationSerializer(location).data)

    @transaction.atomic
    def delete(self, request, location_id):
        if not HasPermission('location:delete')().has_permission(request, self):
            self.permission_denied(request)

        try:
            location = Location.objects.get(id=location_id)
        except Location.DoesNotExist:
            raise NotFound("Location not found")
            
        location.is_active = False
        location.save()
        return success_response(None)


class LocationFloorplanDetailView(APIView):
    """
    API Mobile & Web: Xem Sơ đồ Mặt bằng Chi tiết của Phân xưởng/Doanh nghiệp kèm danh sách máy móc đã lắp đặt
    """
    def get(self, request, location_id):
        has_loc = HasPermission('location:read')().has_permission(request, self)
        has_asset = HasPermission('asset:read')().has_permission(request, self)
        has_wo = HasPermission('work_order:read')().has_permission(request, self)
        if not (has_loc or has_asset or has_wo):
            self.permission_denied(request)

        import uuid
        location = None
        try:
            loc_uuid = uuid.UUID(str(location_id))
            location = Location.objects.filter(id=loc_uuid).first()
        except (ValueError, TypeError):
            location = None

        if not location:
            # Fallback search by location code within tenant
            tenant = getattr(request.user, 'tenant', None)
            location = Location.objects.filter(code=str(location_id), is_active=True)
            if tenant:
                location = location.filter(tenant=tenant)
            location = location.first()

        if not location:
            raise ValidationError("Location not found")

        # Determine Vector Preset based on code/name if enterprise hasn't uploaded CAD floorplan_image
        code_upper = (location.code or '').upper()
        name_upper = (location.name or '').upper()
        vector_preset = 'STANDARD'
        if any(k in code_upper or k in name_upper for k in ['DAP', 'PRESS', 'DẬP', 'STAMPING']):
            vector_preset = 'PRESS'
        elif any(k in code_upper or k in name_upper for k in ['SACH', 'CLEAN', 'SẠCH', 'CHIP', 'YELLOW']):
            vector_preset = 'CLEANROOM'
        elif any(k in code_upper or k in name_upper for k in ['KHO', 'WAREHOUSE', 'STORAGE', 'PALLET', 'DOCK']):
            vector_preset = 'WAREHOUSE'

        # Query all active assets situated in this location or zone
        from workorders.models import WorkOrder
        from django.db.models import Q

        assets_qs = Asset.objects.filter(
            Q(location=location) | Q(zone_id=location.code),
            is_active=True
        ).select_related('category')
        if location.tenant:
            assets_qs = assets_qs.filter(tenant=location.tenant)

        # Preload active work orders targeting these assets
        active_wo_qs = WorkOrder.objects.filter(
            status__in=['CREATED', 'ASSIGNED', 'IN_PROGRESS']
        )
        if location.tenant:
            active_wo_qs = active_wo_qs.filter(tenant=location.tenant)
        active_wo_qs = active_wo_qs.values('id', 'asset_id')

        active_wo_by_asset = {}
        for w in active_wo_qs:
            aid = str(w['asset_id'])
            if aid not in active_wo_by_asset:
                active_wo_by_asset[aid] = {
                    'id': str(w['id']),
                    'code': f"WO-{str(w['id'])[:8].upper()}"
                }

        equipment_list = []
        for a in assets_qs:
            wo_info = active_wo_by_asset.get(str(a.id))
            equipment_list.append({
                "id": str(a.id),
                "name": a.name,
                "serialNumber": a.serial_number or "",
                "qrCode": a.qr_code,
                "model": a.model or "",
                "manufacturer": a.manufacturer or "",
                "status": a.status,
                "coordsX": float(a.coords_x or 0.0),
                "coordsY": float(a.coords_y or 0.0),
                "floorLevel": a.floor_level or location.floor_level or 1,
                "categoryName": a.category.name if a.category else "",
                "hasActiveWorkOrder": bool(wo_info),
                "activeWorkOrderId": wo_info['id'] if wo_info else None,
                "activeWorkOrderCode": wo_info['code'] if wo_info else None
            })

        data = {
            "locationId": str(location.id),
            "code": location.code or "",
            "name": location.name,
            "zoneType": location.zone_type,
            "floorLevel": location.floor_level or 1,
            "centerX": float(location.center_x or 0.0),
            "centerY": float(location.center_y or 0.0),
            "floorplanImage": location.floorplan_image or "",
            "hasFloorplan": bool(location.floorplan_image),
            "vectorPreset": vector_preset,
            "dimensions": {
                "widthMeters": 100.0,
                "heightMeters": 70.0
            },
            "equipmentList": equipment_list
        }
        return success_response(data)


class AssetCategoryListView(APIView):
    def get(self, request):
        has_cat = HasPermission('asset_category:read')().has_permission(request, self)
        has_asset = HasPermission('asset:read')().has_permission(request, self)
        if not (has_cat or has_asset):
            self.permission_denied(request)
            
        categories = AssetCategory.objects.all()

        try:
            page = int(request.query_params.get('page', 0))
            size = int(request.query_params.get('size', 20))
        except ValueError:
            page, size = 0, 20

        total_elements = categories.count()
        start = page * size
        end = start + size
        categories_page = categories[start:end]

        serializer = AssetCategorySerializer(categories_page, many=True)
        return success_response({
            "content": serializer.data,
            "totalElements": total_elements,
            "page": page,
            "size": size
        })

    @transaction.atomic
    def post(self, request):
        if not HasPermission('asset_category:create')().has_permission(request, self):
            self.permission_denied(request)

        serializer = AssetCategoryCreateUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            raise ValidationError(serializer.errors)
            
        data = serializer.validated_data
        
        if AssetCategory.objects.filter(name=data['name']).exists():
            raise ValidationError("Category name already exists in this tenant")
            
        category = AssetCategory.objects.create(
            name=data['name'],
            description=data.get('description'),
            is_active=data.get('isActive', True)
        )
        
        return success_response(AssetCategorySerializer(category).data, message="Created")

class AssetCategoryDetailView(APIView):
    def get(self, request, category_id):
        has_cat = HasPermission('asset_category:read')().has_permission(request, self)
        has_asset = HasPermission('asset:read')().has_permission(request, self)
        if not (has_cat or has_asset):
            self.permission_denied(request)
            
        try:
            category = AssetCategory.objects.get(id=category_id)
        except AssetCategory.DoesNotExist:
            raise NotFound("Asset category not found")
            
        return success_response(AssetCategorySerializer(category).data)

    @transaction.atomic
    def put(self, request, category_id):
        if not HasPermission('asset_category:update')().has_permission(request, self):
            self.permission_denied(request)

        try:
            category = AssetCategory.objects.get(id=category_id)
        except AssetCategory.DoesNotExist:
            raise NotFound("Asset category not found")
            
        serializer = AssetCategoryCreateUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            raise ValidationError(serializer.errors)
            
        data = serializer.validated_data
        
        if category.name != data['name'] and AssetCategory.objects.filter(name=data['name']).exists():
            raise ValidationError("Category name already exists in this tenant")
            
        category.name = data['name']
        if 'description' in data:
            category.description = data['description']
        if 'isActive' in data:
            category.is_active = data['isActive']
            
        category.save()
        return success_response(AssetCategorySerializer(category).data)

    @transaction.atomic
    def delete(self, request, category_id):
        if not HasPermission('asset_category:delete')().has_permission(request, self):
            self.permission_denied(request)

        try:
            category = AssetCategory.objects.get(id=category_id)
        except AssetCategory.DoesNotExist:
            raise ValidationError("Asset category not found")
            
        category.is_active = False
        category.save()
        return success_response(None)


class HierarchyTemplateListView(APIView):
    def get(self, request):
        has_cat = HasPermission('asset_category:read')().has_permission(request, self)
        has_asset = HasPermission('asset:read')().has_permission(request, self)
        if not (has_cat or has_asset):
            self.permission_denied(request)
            
        templates = HierarchyTemplate.objects.all().order_by('path')

        try:
            page = int(request.query_params.get('page', 0))
            size = int(request.query_params.get('size', 20))
        except ValueError:
            page, size = 0, 20

        total_elements = templates.count()
        start = page * size
        end = start + size
        templates_page = templates[start:end]

        serializer = HierarchyTemplateSerializer(templates_page, many=True)
        return success_response({
            "content": serializer.data,
            "totalElements": total_elements,
            "page": page,
            "size": size
        })

    @transaction.atomic
    def post(self, request):
        if not HasPermission('asset_category:create')().has_permission(request, self):
            self.permission_denied(request)

        serializer = HierarchyTemplateCreateUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            raise ValidationError(serializer.errors)
            
        data = serializer.validated_data
        
        if HierarchyTemplate.objects.filter(name=data['name']).exists():
            raise ValidationError("Hierarchy template name already exists in this tenant")
            
        path = data.get('path')
        if path and not path.strip():
            path = None
        elif path:
            path = format_to_ltree(path)
            
        template = HierarchyTemplate.objects.create(
            name=data['name'],
            path=path,
            description=data.get('description'),
            is_active=data.get('isActive', True)
        )
        
        return success_response(HierarchyTemplateSerializer(template).data, message="Created")

class HierarchyTemplateDetailView(APIView):
    def get(self, request, template_id):
        has_cat = HasPermission('asset_category:read')().has_permission(request, self)
        has_asset = HasPermission('asset:read')().has_permission(request, self)
        if not (has_cat or has_asset):
            self.permission_denied(request)
            
        try:
            template = HierarchyTemplate.objects.get(id=template_id)
        except HierarchyTemplate.DoesNotExist:
            raise ValidationError("Hierarchy template not found")
            
        return success_response(HierarchyTemplateSerializer(template).data)

    @transaction.atomic
    def put(self, request, template_id):
        if not HasPermission('asset_category:update')().has_permission(request, self):
            self.permission_denied(request)

        try:
            template = HierarchyTemplate.objects.get(id=template_id)
        except HierarchyTemplate.DoesNotExist:
            raise NotFound("Hierarchy template not found")
            
        serializer = HierarchyTemplateCreateUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            raise ValidationError(serializer.errors)
            
        data = serializer.validated_data
        
        if template.name != data['name'] and HierarchyTemplate.objects.filter(name=data['name']).exists():
            raise ValidationError("Hierarchy template name already exists in this tenant")
            
        template.name = data['name']
        
        path = data.get('path')
        if path and not path.strip():
            path = None
        elif path:
            path = format_to_ltree(path)
            
        if 'path' in data:
            template.path = path
            
        if 'description' in data:
            template.description = data['description']
            
        if 'isActive' in data:
            template.is_active = data['isActive']
            
        template.save()
        return success_response(HierarchyTemplateSerializer(template).data)

    @transaction.atomic
    def delete(self, request, template_id):
        if not HasPermission('asset_category:delete')().has_permission(request, self):
            self.permission_denied(request)

        try:
            template = HierarchyTemplate.objects.get(id=template_id)
        except HierarchyTemplate.DoesNotExist:
            raise NotFound("Hierarchy template not found")
            
        template.is_active = False
        template.save()
        return success_response(None)

class SparePartListView(APIView):
    def get(self, request):
        is_sys_admin = hasattr(request, '_user_permissions_cache') and 'system:admin' in request._user_permissions_cache
        if not (is_sys_admin or HasPermission('inventory:read')().has_permission(request, self)):
            self.permission_denied(request)
            
        parts = SparePart.objects.all()
        serializer = SparePartSerializer(parts, many=True)
        return success_response(serializer.data)

    @transaction.atomic
    def post(self, request):
        is_sys_admin = hasattr(request, '_user_permissions_cache') and 'system:admin' in request._user_permissions_cache
        if not (is_sys_admin or HasPermission('inventory:create')().has_permission(request, self)):
            self.permission_denied(request)

        serializer = SparePartCreateUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            raise ValidationError(serializer.errors)
            
        data = serializer.validated_data
        
        part = SparePart.objects.create(
            name=data['name'],
            part_number=data.get('partNumber'),
            description=data.get('description'),
            quantity_in_stock=data.get('quantityInStock', 0.0),
            unit_cost=data.get('unitCost')
        )
        
        return success_response(SparePartSerializer(part).data, message="Created")


class SparePartDetailView(APIView):
    @transaction.atomic
    def put(self, request, part_id):
        is_sys_admin = hasattr(request, '_user_permissions_cache') and 'system:admin' in request._user_permissions_cache
        if not (is_sys_admin or HasPermission('inventory:update')().has_permission(request, self)):
            self.permission_denied(request)

        try:
            part = SparePart.objects.get(id=part_id)
        except SparePart.DoesNotExist:
            raise NotFound("Spare part not found")
            
        serializer = SparePartCreateUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            raise ValidationError(serializer.errors)
            
        data = serializer.validated_data
        
        part.name = data['name']
        if 'partNumber' in data:
            part.part_number = data['partNumber']
        if 'description' in data:
            part.description = data['description']
        if 'quantityInStock' in data:
            part.quantity_in_stock = data['quantityInStock']
        if 'unitCost' in data:
            part.unit_cost = data['unitCost']
            
        part.save()

        from notifications.services import notify_spare_part_low_stock
        notify_spare_part_low_stock(part)

        return success_response(SparePartSerializer(part).data)

    @transaction.atomic
    def delete(self, request, part_id):
        is_sys_admin = hasattr(request, '_user_permissions_cache') and 'system:admin' in request._user_permissions_cache
        if not (is_sys_admin or HasPermission('inventory:delete')().has_permission(request, self)):
            self.permission_denied(request)

        try:
            part = SparePart.objects.get(id=part_id)
        except SparePart.DoesNotExist:
            raise ValidationError("Spare part not found")
            
        part.delete()
        return success_response(None)

class AssetListView(APIView):
    def get(self, request):
        if not HasPermission('asset:read')().has_permission(request, self):
            self.permission_denied(request)
            
        assets = Asset.objects.filter(is_active=True)

        try:
            page = int(request.query_params.get('page', 0))
            size = int(request.query_params.get('size', 20))
        except ValueError:
            page, size = 0, 20

        total_elements = assets.count()
        total_pages = (total_elements + size - 1) // size if size > 0 else 1
        is_last = (page + 1) >= total_pages or total_elements == 0

        start = page * size
        end = start + size
        assets_page = assets[start:end]

        serializer = AssetSerializer(assets_page, many=True)
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
        if not HasPermission('asset:create')().has_permission(request, self):
            self.permission_denied(request)

        serializer = AssetCreateUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            raise ValidationError(serializer.errors)
            
        data = serializer.validated_data
        
        qr_code = data.get('qrCode')
        if not qr_code:
            import uuid
            qr_code = "AST-" + str(uuid.uuid4())[:8].upper()
            while Asset.objects.filter(qr_code=qr_code).exists():
                qr_code = "AST-" + str(uuid.uuid4())[:8].upper()

        if Asset.objects.filter(qr_code=qr_code).exists():
            raise ValidationError("QR Code must be unique")
            
        parent_id = data.get('parentId')
        if parent_id:
            parent_id = format_to_ltree(parent_id)
            
        asset = Asset.objects.create(
            name=data['name'],
            category_id=data.get('categoryId'),
            parent_id=parent_id,
            serial_number=data.get('serialNumber'),
            model=data.get('model'),
            manufacturer=data.get('manufacturer'),
            purchase_date=data.get('purchaseDate'),
            value=data.get('value'),
            status=data.get('status', 'OPERATIONAL'),
            asset_type=data.get('assetType', 'MACHINERY'),
            duty_cycle_ratio=data.get('dutyCycleRatio', 1.0),
            location_id=data.get('locationId'),
            hierarchy_template_id=data.get('hierarchyTemplateId'),
            qr_code=qr_code,
            is_active=data.get('isActive', True)
        )
        
        return success_response(AssetSerializer(asset).data, message="Created")


class AssetDetailView(APIView):
    def get(self, request, asset_id):
        if not HasPermission('asset:read')().has_permission(request, self):
            self.permission_denied(request)
            
        try:
            asset = Asset.objects.get(id=asset_id, is_active=True)
        except Asset.DoesNotExist:
            raise NotFound("Asset not found")
            
        return success_response(AssetSerializer(asset).data)

    @transaction.atomic
    def put(self, request, asset_id):
        if not HasPermission('asset:update')().has_permission(request, self):
            self.permission_denied(request)

        try:
            asset = Asset.objects.get(id=asset_id, is_active=True)
        except Asset.DoesNotExist:
            raise NotFound("Asset not found")
            
        serializer = AssetCreateUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            raise ValidationError(serializer.errors)
            
        data = serializer.validated_data
        
        if 'qrCode' in data and data['qrCode'] != asset.qr_code:
            if Asset.objects.filter(qr_code=data['qrCode']).exists():
                raise ValidationError("QR Code must be unique")
            asset.qr_code = data['qrCode']
            
        asset.name = data['name']
        
        if 'categoryId' in data:
            asset.category_id = data['categoryId']
            
        if 'parentId' in data:
            parent_id = data['parentId']
            if parent_id:
                parent_id = format_to_ltree(parent_id)
            asset.parent_id = parent_id
            
        if 'serialNumber' in data:
            asset.serial_number = data['serialNumber']
            
        if 'model' in data:
            asset.model = data['model']
            
        if 'manufacturer' in data:
            asset.manufacturer = data['manufacturer']
            
        if 'purchaseDate' in data:
            asset.purchase_date = data['purchaseDate']
            
        if 'value' in data:
            asset.value = data['value']
            
        if 'status' in data:
            asset.status = data['status']
            
        if 'locationId' in data:
            asset.location_id = data['locationId']
            
        if 'hierarchyTemplateId' in data:
            asset.hierarchy_template_id = data['hierarchyTemplateId']
            
        if 'isActive' in data:
            asset.is_active = data['isActive']
            
        if 'assetType' in data:
            asset.asset_type = data['assetType']

        if 'dutyCycleRatio' in data:
            asset.duty_cycle_ratio = data['dutyCycleRatio']
            
        asset.save()
        return success_response(AssetSerializer(asset).data)

    @transaction.atomic
    def delete(self, request, asset_id):
        if not HasPermission('asset:delete')().has_permission(request, self):
            self.permission_denied(request)

        try:
            asset = Asset.objects.get(id=asset_id, is_active=True)
        except Asset.DoesNotExist:
            raise NotFound("Asset not found")
            
        asset.is_active = False
        asset.save()
        return success_response(None)

class MeterReadingListView(APIView):
    def get(self, request, asset_id):
        if not HasPermission('asset:read')().has_permission(request, self):
            self.permission_denied(request)
            
        try:
            asset = Asset.objects.get(id=asset_id, is_active=True)
        except Asset.DoesNotExist:
            raise NotFound("Asset not found")
            
        readings = MeterReading.objects.filter(asset=asset).order_by('-reading_date')
        serializer = MeterReadingSerializer(readings, many=True)
        return success_response(serializer.data)

    @transaction.atomic
    def post(self, request, asset_id):
        if not (HasPermission('asset:update')().has_permission(request, self) or HasPermission('work_order:execute')().has_permission(request, self)):
            self.permission_denied(request)
            
        try:
            asset = Asset.objects.get(id=asset_id, is_active=True)
        except Asset.DoesNotExist:
            raise NotFound("Asset not found")

        serializer = MeterReadingCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
            
        data = serializer.validated_data
        from django.utils import timezone

        # Chuẩn bị danh sách chỉ số đo kiểm tra
        if data.get('readings'):
            readings_data = data['readings']
        else:
            val = data.get('value')
            if val is None:
                val = data.get('readingValue')
            if val is None:
                raise ValidationError("Thiếu giá trị đo đạc (value hoặc readingValue).")
            readings_data = [{
                'metricCode': data.get('metricCode', 'VIBRATION'),
                'value': val,
                'unit': data.get('unit'),
                'remarks': data.get('remarks')
            }]

        machine_state = data.get('machineState', 'RUNNING')
        ambient_temp = data.get('ambientTemperature')
        load_factor = None
        for _lf_k in ('loadFactor', 'load_factor'):
            if _lf_k in data and data[_lf_k] is not None:
                load_factor = data[_lf_k]
                break
            if _lf_k in request.data and request.data[_lf_k] is not None:
                load_factor = request.data[_lf_k]
                break
        if load_factor is None:
            load_factor = 1.0
        rec_time = data.get('recordedAt') or data.get('readingDate') or timezone.now()

        # Liên kết với Work Order nếu được gửi lên từ quy trình bảo dưỡng
        work_order = None
        work_order_id = data.get('workOrderId') or data.get('work_order_id') or request.data.get('workOrderId') or request.data.get('work_order_id')
        if work_order_id:
            from workorders.models import WorkOrder
            work_order = WorkOrder.objects.filter(id=work_order_id, tenant_id=asset.tenant_id).first()
            if not work_order:
                raise ValidationError("Work Order không tồn tại hoặc không thuộc phân vùng dữ liệu của tài sản.")
            if work_order.asset_id != asset.id:
                raise ValidationError(f"Work Order {work_order.code or work_order_id} không thuộc tài sản này ({asset.code or asset.id}).")
            if work_order.status in ('CANCELLED', 'CANCELED'):
                raise ValidationError(f"Không thể liên kết số đo với Work Order đã bị hủy ({work_order.code or work_order_id}).")

        # Thực thi qua ConditionMonitoringEngine
        result = ConditionMonitoringEngine.process_readings(
            asset=asset,
            readings_data=readings_data,
            machine_state=machine_state,
            ambient_temperature=ambient_temp,
            load_factor=float(load_factor),
            recorded_at=rec_time,
            recorded_by=request.user if request.user and request.user.is_authenticated else None,
            tenant=asset.tenant,
            work_order=work_order
        )

        return success_response(result, message="Created")


class AssetAnomalyHistoryView(APIView):
    def get(self, request, asset_id):
        if not HasPermission('asset:read')().has_permission(request, self):
            self.permission_denied(request)

        try:
            asset = Asset.objects.get(id=asset_id, is_active=True)
        except Asset.DoesNotExist:
            raise NotFound("Asset not found")

        readings = MeterReading.objects.filter(asset=asset).order_by('-reading_date')[:50]
        alerts = AssetAnomalyAlert.objects.filter(asset=asset).order_by('-last_detected_at')[:20]

        # Tính toán đường xu hướng Theil-Sen cho độ rung
        vib_readings = list(MeterReading.objects.filter(
            asset=asset,
            metric_code='VIBRATION',
            machine_state='RUNNING',
            is_pre_repair=False,
            is_suppressed=False
        ).order_by('reading_date'))

        from algorithms.anomaly_detection.iso_standards import get_iso_thresholds_for_asset
        iso_cfg = get_iso_thresholds_for_asset(asset)
        ab_lim = iso_cfg.get("zone_ab_limit", 2.8)
        c_lim = iso_cfg.get("zone_c_limit", 7.1)
        std_name = iso_cfg.get("standard", "ISO 10816-3")

        trend_summary = None
        if len(vib_readings) >= 5:
            trend_summary = evaluate_trend_drift(
                timestamps=[r.reading_date for r in vib_readings],
                values=[float(r.reading_value) for r in vib_readings],
                limit_value=c_lim
            )

        data = {
            "assetId": str(asset.id),
            "assetName": asset.name,
            "isStaticAsset": is_static_asset(asset),
            "readings": MeterReadingSerializer(readings, many=True).data,
            "alerts": AssetAnomalyAlertSerializer(alerts, many=True).data,
            "trendDrift": trend_summary,
            "isoBenchmark": {
                "standard": std_name,
                "metric": "VIBRATION",
                "zones": [
                    {"zone": "ZONE_AB", "range": f"< {ab_lim} mm/s", "label": "Tốt / Đạt chuẩn", "color": "green"},
                    {"zone": "ZONE_C", "range": f"{ab_lim} - {c_lim} mm/s", "label": "Cảnh báo - Cần theo dõi", "color": "yellow"},
                    {"zone": "ZONE_D", "range": f"> {c_lim} mm/s", "label": "Nguy hiểm - Dừng máy khẩn cấp", "color": "red"}
                ]
            }
        }
        return success_response(data)


class ConditionMonitoringAlertFeedbackView(APIView):
    def post(self, request, alert_id):
        if not (HasPermission('asset:update')().has_permission(request, self) or HasPermission('work_order:update')().has_permission(request, self)):
            self.permission_denied(request)

        user_tenant = getattr(request.user, 'tenant', None)
        try:
            if user_tenant and not getattr(request.user, 'is_superuser', False):
                alert = AssetAnomalyAlert.objects.get(id=alert_id, tenant=user_tenant)
            else:
                alert = AssetAnomalyAlert.objects.get(id=alert_id)
        except AssetAnomalyAlert.DoesNotExist:
            raise ValidationError("Alert not found")

        feedback = str(request.data.get('feedback') or request.data.get('status') or '').strip().upper()
        notes = request.data.get('notes', '')

        # Quy Tắc 8 & TC-ANOM-08: Quản đốc đánh dấu Báo động giả
        if feedback in ('FALSE_ALARM', 'FALSE_POSITIVE', 'SPURIOUS'):
            alert.status = 'FALSE_ALARM'
            alert.is_suppressed = True
            if alert.reading:
                alert.reading.is_suppressed = True
                alert.reading.save()
            if notes:
                alert.message = f"{alert.message or ''} [Quản đốc phản hồi: {notes}]".strip()
            alert.save()
        elif feedback in ('CONFIRMED', 'ACKNOWLEDGED'):
            alert.status = 'ACKNOWLEDGED'
            if notes:
                alert.message = f"{alert.message or ''} [Quản đốc xác nhận: {notes}]".strip()
            alert.save()
        elif feedback == 'RESOLVED':
            alert.status = 'RESOLVED'
            alert.save()
        else:
            raise ValidationError(f"Phản hồi không hợp lệ: {feedback}. Hỗ trợ: FALSE_ALARM, CONFIRMED, RESOLVED")

        return success_response(AssetAnomalyAlertSerializer(alert).data, message="Phản hồi đã được ghi nhận")

class AssetTreeView(APIView):
    def get(self, request):
        if not HasPermission('asset:read')().has_permission(request, self):
            self.permission_denied(request)

        all_locations = list(Location.objects.filter(is_active=True))
        loc_map = {loc.id: loc for loc in all_locations}
        
        assets_qs = Asset.objects.filter(is_active=True)
        status_param = request.query_params.get('status')
        if status_param:
            assets_qs = assets_qs.filter(status=status_param.upper())
            
        category_id = request.query_params.get('categoryId')
        if category_id:
            assets_qs = assets_qs.filter(category_id=category_id)
            
        filtered_assets = list(assets_qs)
        search = request.query_params.get('search')
        search_lower = search.lower() if search else None
        
        matching_assets = []
        
        def get_full_path(l):
            if not l: return ""
            if l.parent_id:
                return f"{l.parent_id}.{format_to_ltree(l.name)}"
            return format_to_ltree(l.name)

        for a in filtered_assets:
            matches = True
            if search_lower:
                asset_matches = False
                if a.name and search_lower in a.name.lower(): asset_matches = True
                elif a.serial_number and search_lower in a.serial_number.lower(): asset_matches = True
                elif a.qr_code and search_lower in a.qr_code.lower(): asset_matches = True
                
                if not asset_matches:
                    ancestor_matches = False
                    loc = a.location
                    while loc:
                        if loc.name and search_lower in loc.name.lower():
                            ancestor_matches = True
                            break
                        if loc.parent_id:
                            parent_path = loc.parent_id
                            loc = next((l for l in all_locations if get_full_path(l) == parent_path), None)
                        else:
                            loc = None
                    if not ancestor_matches:
                        matches = False
                        
            if matches:
                matching_assets.append(a)
                
        visible_loc_ids = set()
        
        for a in matching_assets:
            if a.location_id:
                loc = loc_map.get(a.location_id)
                while loc:
                    visible_loc_ids.add(loc.id)
                    if loc.parent_id:
                        parent_path = loc.parent_id
                        loc = next((l for l in all_locations if get_full_path(l) == parent_path), None)
                    else:
                        loc = None
                        
        if search_lower:
            for loc in all_locations:
                if loc.name and search_lower in loc.name.lower():
                    curr = loc
                    while curr:
                        visible_loc_ids.add(curr.id)
                        if curr.parent_id:
                            parent_path = curr.parent_id
                            curr = next((l for l in all_locations if get_full_path(l) == parent_path), None)
                        else:
                            curr = None
        else:
            if not status_param and not category_id:
                for l in all_locations:
                    visible_loc_ids.add(l.id)
                    
        root_nodes = []
        node_map = {}
        
        serialized_assets_cache = {a.id: AssetSerializer(a).data for a in matching_assets}
        
        for loc in all_locations:
            if loc.id not in visible_loc_ids: continue
            
            loc_assets = [serialized_assets_cache[a.id] for a in matching_assets if a.location_id == loc.id]
            
            node = {
                "id": loc.id,
                "name": loc.name,
                "parentId": loc.parent_id,
                "isActive": loc.is_active,
                "assets": loc_assets,
                "children": []
            }
            node_map[loc.id] = node
            
        for loc in all_locations:
            if loc.id not in visible_loc_ids: continue
            
            node = node_map[loc.id]
            if not loc.parent_id:
                root_nodes.append(node)
            else:
                parent_node = None
                parent_path = loc.parent_id
                for p_loc in all_locations:
                    if p_loc.id in visible_loc_ids:
                        if get_full_path(p_loc) == parent_path:
                            parent_node = node_map.get(p_loc.id)
                            break
                if parent_node:
                    parent_node['children'].append(node)
                else:
                    root_nodes.append(node)
                    
        unassigned_assets = [serialized_assets_cache[a.id] for a in matching_assets if not a.location_id]
        
        return success_response({
            "locations": root_nodes,
            "unassignedAssets": unassigned_assets
        })

class AssetQRCodeView(APIView):
    def get(self, request, qr_code):
        if not HasPermission('asset:read')().has_permission(request, self):
            self.permission_denied(request)
            
        try:
            asset = Asset.objects.get(qr_code=qr_code, is_active=True)
        except Asset.DoesNotExist:
            raise ValidationError("Asset not found")
            
        return success_response(AssetSerializer(asset).data)

class AssetImportView(APIView):
    @transaction.atomic
    def post(self, request):
        if not HasPermission('asset:create')().has_permission(request, self):
            self.permission_denied(request)
            
        file_obj = request.FILES.get('file')
        if not file_obj:
            raise ValidationError("No file uploaded")

        import csv
        import io
        from datetime import datetime
        import uuid
        
        success_count = 0
        failure_count = 0
        errors = []
        
        try:
            decoded_file = file_obj.read().decode('utf-8')
            io_string = io.StringIO(decoded_file)
            reader = csv.reader(io_string, delimiter=',', quotechar='"')
            
            is_first = True
            line_number = 0
            
            for line in reader:
                line_number += 1
                if is_first:
                    is_first = False
                    continue
                    
                if not line or (len(line) == 1 and not line[0].strip()):
                    continue
                    
                if len(line) < 1:
                    failure_count += 1
                    errors.append(f"Line {line_number}: Missing asset name")
                    continue
                    
                name = line[0].strip()
                if not name:
                    failure_count += 1
                    errors.append(f"Line {line_number}: Asset name cannot be empty")
                    continue
                    
                asset = Asset(name=name)
                
                if len(line) > 1 and line[1].strip():
                    cat = AssetCategory.objects.filter(name=line[1].strip()).first()
                    if cat: asset.category = cat
                    
                if len(line) > 2 and line[2].strip():
                    tmp = HierarchyTemplate.objects.filter(name=line[2].strip()).first()
                    if tmp: asset.hierarchy_template = tmp
                    
                if len(line) > 3: asset.serial_number = line[3].strip()
                if len(line) > 4: asset.model = line[4].strip()
                if len(line) > 5: asset.manufacturer = line[5].strip()
                
                if len(line) > 6 and line[6].strip():
                    try:
                        asset.purchase_date = datetime.strptime(line[6].strip(), '%Y-%m-%d').date()
                    except ValueError:
                        pass
                        
                if len(line) > 7 and line[7].strip():
                    try:
                        from decimal import Decimal
                        asset.value = Decimal(line[7].strip())
                    except Exception:
                        pass
                        
                if len(line) > 8 and line[8].strip():
                    status_val = line[8].strip().upper()
                    if status_val in dict(Asset.STATUS_CHOICES):
                        asset.status = status_val
                    else:
                        asset.status = 'OPERATIONAL'
                else:
                    asset.status = 'OPERATIONAL'
                    
                if len(line) > 9 and line[9].strip():
                    loc = Location.objects.filter(name=line[9].strip()).first()
                    if loc: asset.location = loc
                    
                is_active = True
                if len(line) > 11 and line[11].strip():
                    is_active_str = line[11].strip().lower()
                    if is_active_str == 'false':
                        is_active = False
                asset.is_active = is_active
                
                asset.qr_code = "AST-" + str(uuid.uuid4())[:8].upper()
                asset.save()
                success_count += 1
                
        except Exception as e:
            failure_count += 1
            errors.append(f"Failed to parse CSV file: {str(e)}")
            
        return success_response({
            "totalProcessed": success_count + failure_count,
            "successCount": success_count,
            "errorCount": failure_count,
            "errors": errors
        })

class AssetExportView(APIView):
    def get(self, request):
        if not HasPermission('asset:read')().has_permission(request, self):
            self.permission_denied(request)
            
        from django.http import HttpResponse
        import csv
        
        response = HttpResponse(content_type='text/csv; charset=UTF-8')
        response['Content-Disposition'] = 'attachment; filename="assets_export.csv"'
        
        writer = csv.writer(response, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        header = [
            "Name", "Category", "Template", "Serial Number", "Model", 
            "Manufacturer", "Purchase Date", "Value", "Status", "Location", 
            "QR Code", "IsActive"
        ]
        writer.writerow(header)
        
        assets = Asset.objects.all()
        for a in assets:
            row = [
                a.name or "",
                a.category.name if a.category else "",
                a.hierarchy_template.name if a.hierarchy_template else "",
                a.serial_number or "",
                a.model or "",
                a.manufacturer or "",
                str(a.purchase_date) if a.purchase_date else "",
                str(a.value) if a.value else "",
                a.status or "",
                a.location.name if a.location else "",
                a.qr_code or "",
                "true" if a.is_active else "false"
            ]
            writer.writerow(row)
            
        return response

class AssetImportTemplateView(APIView):
    def get(self, request):
        if not HasPermission('asset:create')().has_permission(request, self):
            self.permission_denied(request)
            
        from django.http import HttpResponse
        import csv
        
        response = HttpResponse(content_type='text/csv; charset=UTF-8')
        response['Content-Disposition'] = 'attachment; filename="assets_import_template.csv"'
        
        writer = csv.writer(response, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        header = [
            "Name", "Category", "Template", "Serial Number", "Model", 
            "Manufacturer", "Purchase Date", "Value", "Status", "Location", 
            "QR Code", "IsActive"
        ]
        writer.writerow(header)
        
        # Sample row to help user understand the format
        sample_row = [
            "Sample Asset", "Category Name", "Template Name", "SN-12345", "Model-X",
            "Manufacturer Y", "2023-01-01", "1000.50", "OPERATIONAL", "Location Z",
            "", "true"
        ]
        writer.writerow(sample_row)
        
        return response


from algorithms.predictive_rul import RULPredictiveService, PredictiveRULGuardrails
from assets.serializers import AssetRulPredictionSerializer

class AssetRulPredictionDetailView(APIView):
    def get(self, request, asset_id):
        if not HasPermission('asset:read')().has_permission(request, self):
            self.permission_denied(request)

        try:
            asset = Asset.objects.get(id=asset_id, is_active=True)
        except Asset.DoesNotExist:
            raise NotFound("Asset not found")

        tenant = getattr(request.user, 'tenant', None)
        if tenant and not getattr(tenant, 'enable_ai_rul', True):
            return success_response({
                "assetId": str(asset.id),
                "assetName": asset.name,
                "currentStatus": asset.status,
                "aiEnabled": False,
                "operatingRulDays": None,
                "calendarRulDays": None,
                "riskLevel": "DISABLED",
                "message": "Thuật toán AI Dự đoán Tuổi thọ Còn lại (RUL) đang tạm tắt theo cài đặt tổ chức. Hệ thống áp dụng quy trình bảo trì định kỳ truyền thống.",
                "history": []
            })

        # Kiểm tra tài sản tĩnh
        is_machinery, static_err = PredictiveRULGuardrails.validate_asset_machinery_type(asset)
        if not is_machinery:
            return error_response(message=static_err, status_code=400)

        # Lấy bản ghi dự đoán RUL gần nhất (nếu có)
        latest_pred = AssetRulPrediction.objects.filter(asset=asset).order_by('-created_at').first()
        
        # Nếu chưa có bản ghi nào và chưa từng tính RUL
        if not latest_pred and asset.current_rul_days is None and asset.rul_risk_level != 'CALIBRATING':
            try:
                result = RULPredictiveService.predict_asset_rul(asset=asset, trigger_source='MANUAL', current_user=request.user)
                return success_response(result.get('data', {}))
            except Exception:
                pass

        # Lấy lịch sử 10 lần dự đoán gần nhất để vẽ biểu đồ suy thoái
        history = list(AssetRulPrediction.objects.filter(asset=asset).order_by('-created_at')[:10])
        history.reverse()

        spare_part = asset.primary_spare_part
        lead_time = int(spare_part.lead_time_days) if spare_part else 7
        crit_threshold = PredictiveRULGuardrails.calculate_dynamic_critical_threshold(lead_time)
        stock_qty = float(spare_part.quantity_in_stock) if spare_part else 0.0

        data = {
            "assetId": str(asset.id),
            "assetName": asset.name,
            "currentStatus": asset.status,
            "aiEnabled": True,
            "operatingRulDays": asset.current_rul_days,
            "calendarRulDays": asset.current_rul_calendar_days,
            "dutyCycleRatio": asset.duty_cycle_ratio,
            "confidenceInterval": {
                "lower": asset.rul_confidence_lower,
                "upper": asset.rul_confidence_upper,
                "stdDeviation": latest_pred.std_deviation if latest_pred else 0.0,
                "isHighUncertainty": bool(latest_pred.std_deviation > 10.0) if latest_pred else False
            },
            "riskLevel": asset.rul_risk_level,
            "isPhantomRecovery": asset.is_phantom_recovery,
            "rapidDegradationAlert": asset.rapid_degradation_alert,
            "rapidDegradationRate": latest_pred.rapid_degradation_rate if latest_pred else None,
            "lastEvaluatedAt": asset.last_rul_predicted_at.isoformat() if asset.last_rul_predicted_at else None,
            "sparePartStatus": {
                "partId": str(spare_part.id) if spare_part else None,
                "partName": spare_part.name if spare_part else None,
                "availableQuantity": stock_qty,
                "leadTimeDays": lead_time,
                "dynamicCriticalThreshold": crit_threshold,
                "isStockSufficient": bool(stock_qty >= 1.0)
            },
            "history": AssetRulPredictionSerializer(history, many=True).data,
            "activeWorkOrderId": str(latest_pred.work_order_id) if latest_pred and latest_pred.work_order_id else None,
            "activeWorkOrderCode": latest_pred.work_order.code if latest_pred and latest_pred.work_order else None
        }
        return success_response(data)


class AssetRulPredictionRunView(APIView):
    def post(self, request, asset_id):
        if not HasPermission('asset:update')().has_permission(request, self):
            self.permission_denied(request)

        try:
            asset = Asset.objects.get(id=asset_id, is_active=True)
        except Asset.DoesNotExist:
            raise NotFound("Asset not found")

        tenant = getattr(request.user, 'tenant', None)
        if tenant and not getattr(tenant, 'enable_ai_rul', True):
            return error_response(message="Thuật toán Dự đoán Tuổi thọ Còn lại (RUL) đang tạm tắt trong Cài đặt tổ chức.", status_code=400)

        custom_load = request.data.get('loadFactor') or request.data.get('load_factor')
        if custom_load is not None:
            try:
                custom_load = float(custom_load)
            except (ValueError, TypeError):
                custom_load = None

        result = RULPredictiveService.predict_asset_rul(
            asset=asset,
            trigger_source='MANUAL',
            custom_load_factor=custom_load,
            current_user=request.user
        )
        return success_response(result.get('data', {}), message="Dự đoán RUL thành công")


class AssetRulOverridePhantomView(APIView):
    def post(self, request, asset_id):
        if not HasPermission('asset:update')().has_permission(request, self):
            self.permission_denied(request)

        try:
            asset = Asset.objects.get(id=asset_id, is_active=True)
        except Asset.DoesNotExist:
            raise NotFound("Asset not found")

        reason = str(request.data.get('reason') or '').strip()
        if not reason:
            raise ValidationError({"reason": "Bắt buộc phải nhập lý do kỹ thuật để xác thực ghi đè Phantom Recovery."})

        # Ghi đè cờ hồi phục ảo
        asset.is_phantom_recovery = False
        asset.save(update_fields=['is_phantom_recovery', 'updated_at'])

        # Cập nhật bản ghi prediction gần nhất nếu có
        latest_pred = AssetRulPrediction.objects.filter(asset=asset, is_phantom_recovery=True).first()
        if latest_pred:
            latest_pred.is_phantom_recovery = False
            latest_pred.action_taken = f"OVERRIDDEN_BY_MANAGER: {reason}"
            latest_pred.save(update_fields=['is_phantom_recovery', 'action_taken'])

        return success_response({
            "assetId": str(asset.id),
            "isPhantomRecovery": False,
            "overrideReason": reason
        }, message="Đã xác thực bỏ qua cảnh báo Phantom Recovery.")


class CriticalAssetsRulListView(APIView):
    def get(self, request):
        if not HasPermission('asset:read')().has_permission(request, self):
            self.permission_denied(request)

        cur_tenant = getattr(request.user, 'tenant', None)
        qs = Asset.objects.filter(is_active=True)
        if cur_tenant and not getattr(request.user, 'is_superuser', False):
            qs = qs.filter(tenant=cur_tenant)

        # Lọc các thiết bị có nguy cơ cao (HIGH / CRITICAL) hoặc có cảnh báo gia tốc suy thoái đột biến
        critical_assets = qs.filter(
            models.Q(rul_risk_level__in=['HIGH', 'CRITICAL']) |
            models.Q(rapid_degradation_alert=True)
        ).select_related('category', 'location', 'primary_spare_part').order_by('current_rul_days')

        data = AssetSerializer(critical_assets, many=True).data
        return success_response(data)


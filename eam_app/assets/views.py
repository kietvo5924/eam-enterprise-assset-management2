import unicodedata
import re
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.core.exceptions import ValidationError
from assets.models import Location, AssetCategory, HierarchyTemplate, SparePart, Asset, MeterReading
from assets.serializers import (
    LocationSerializer, LocationCreateUpdateSerializer,
    AssetCategorySerializer, AssetCategoryCreateUpdateSerializer,
    HierarchyTemplateSerializer, HierarchyTemplateCreateUpdateSerializer,
    SparePartSerializer, SparePartCreateUpdateSerializer,
    AssetSerializer, AssetCreateUpdateSerializer,
    MeterReadingSerializer, MeterReadingCreateSerializer
)
from users.permissions import HasPermission

def success_response(data=None, message="Success"):
    return Response({
        "success": True,
        "message": message,
        "data": data
    }, status=status.HTTP_200_OK)

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
            raise ValidationError("Location not found")
            
        location.is_active = False
        location.save()
        return success_response(None)


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
            raise ValidationError("Asset category not found")
            
        return success_response(AssetCategorySerializer(category).data)

    @transaction.atomic
    def put(self, request, category_id):
        if not HasPermission('asset_category:update')().has_permission(request, self):
            self.permission_denied(request)

        try:
            category = AssetCategory.objects.get(id=category_id)
        except AssetCategory.DoesNotExist:
            raise ValidationError("Asset category not found")
            
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
            raise ValidationError("Hierarchy template not found")
            
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
            raise ValidationError("Hierarchy template not found")
            
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
            raise ValidationError("Spare part not found")
            
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
            raise ValidationError("Asset not found")
            
        return success_response(AssetSerializer(asset).data)

    @transaction.atomic
    def put(self, request, asset_id):
        if not HasPermission('asset:update')().has_permission(request, self):
            self.permission_denied(request)

        try:
            asset = Asset.objects.get(id=asset_id, is_active=True)
        except Asset.DoesNotExist:
            raise ValidationError("Asset not found")
            
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
            
        asset.save()
        return success_response(AssetSerializer(asset).data)

    @transaction.atomic
    def delete(self, request, asset_id):
        if not HasPermission('asset:delete')().has_permission(request, self):
            self.permission_denied(request)

        try:
            asset = Asset.objects.get(id=asset_id, is_active=True)
        except Asset.DoesNotExist:
            raise ValidationError("Asset not found")
            
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
            raise ValidationError("Asset not found")
            
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
            raise ValidationError("Asset not found")

        serializer = MeterReadingCreateSerializer(data=request.data)
        if not serializer.is_valid():
            raise ValidationError(serializer.errors)
            
        data = serializer.validated_data
        
        from django.utils import timezone
        
        reading = MeterReading.objects.create(
            asset=asset,
            reading_value=data['readingValue'],
            reading_date=data.get('readingDate') or timezone.now(),
            unit=data.get('unit'),
            remarks=data.get('remarks')
        )
        
        return success_response(MeterReadingSerializer(reading).data, message="Created")

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

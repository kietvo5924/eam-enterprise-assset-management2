from django.urls import path
from assets.views import (
    LocationListView, LocationDetailView,
    AssetCategoryListView, AssetCategoryDetailView,
    HierarchyTemplateListView, HierarchyTemplateDetailView,
    SparePartListView, SparePartDetailView,
    AssetListView, AssetDetailView, MeterReadingListView,
    AssetTreeView, AssetQRCodeView, AssetImportView, AssetExportView
)

urlpatterns = [
    path('locations', LocationListView.as_view(), name='location_list'),
    path('locations/<uuid:location_id>', LocationDetailView.as_view(), name='location_detail'),
    
    path('asset-categories', AssetCategoryListView.as_view(), name='asset_category_list'),
    path('asset-categories/<uuid:category_id>', AssetCategoryDetailView.as_view(), name='asset_category_detail'),
    
    path('hierarchy-templates', HierarchyTemplateListView.as_view(), name='hierarchy_template_list'),
    path('hierarchy-templates/<uuid:template_id>', HierarchyTemplateDetailView.as_view(), name='hierarchy_template_detail'),
    
    path('spare-parts', SparePartListView.as_view(), name='spare_part_list'),
    path('spare-parts/<uuid:part_id>', SparePartDetailView.as_view(), name='spare_part_detail'),
    
    path('assets', AssetListView.as_view(), name='asset_list'),
    path('assets/tree', AssetTreeView.as_view(), name='asset_tree'),
    path('assets/qr/<str:qr_code>', AssetQRCodeView.as_view(), name='asset_qr'),
    path('assets/import', AssetImportView.as_view(), name='asset_import'),
    path('assets/export', AssetExportView.as_view(), name='asset_export'),
    path('assets/<uuid:asset_id>', AssetDetailView.as_view(), name='asset_detail'),
    
    path('assets/<uuid:asset_id>/meter-readings', MeterReadingListView.as_view(), name='meter_reading_list'),
]

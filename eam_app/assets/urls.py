from django.urls import path, re_path
from assets.views import (
    LocationListView, LocationDetailView, LocationFloorplanDetailView,
    AssetCategoryListView, AssetCategoryDetailView,
    HierarchyTemplateListView, HierarchyTemplateDetailView,
    SparePartListView, SparePartDetailView,
    AssetListView, AssetDetailView, MeterReadingListView,
    AssetTreeView, AssetQRCodeView, AssetImportView, AssetExportView,
    AssetImportTemplateView, AssetAnomalyHistoryView, ConditionMonitoringAlertFeedbackView,
    AssetRulPredictionDetailView, AssetRulPredictionRunView, AssetRulOverridePhantomView, CriticalAssetsRulListView
)

urlpatterns = [
    re_path(r'^locations/?$', LocationListView.as_view(), name='location_list'),
    re_path(r'^locations/(?P<location_id>[0-9a-zA-Z_ -]+)/floorplan/?$', LocationFloorplanDetailView.as_view(), name='location_floorplan_detail'),
    re_path(r'^locations/(?P<location_id>[0-9a-fA-F-]+)/?$', LocationDetailView.as_view(), name='location_detail'),
    
    re_path(r'^asset-categories/?$', AssetCategoryListView.as_view(), name='asset_category_list'),
    re_path(r'^asset-categories/(?P<category_id>[0-9a-fA-F-]+)/?$', AssetCategoryDetailView.as_view(), name='asset_category_detail'),
    
    re_path(r'^hierarchy-templates/?$', HierarchyTemplateListView.as_view(), name='hierarchy_template_list'),
    re_path(r'^hierarchy-templates/(?P<template_id>[0-9a-fA-F-]+)/?$', HierarchyTemplateDetailView.as_view(), name='hierarchy_template_detail'),
    
    re_path(r'^spare-parts/?$', SparePartListView.as_view(), name='spare_part_list'),
    re_path(r'^spare-parts/(?P<part_id>[0-9a-fA-F-]+)/?$', SparePartDetailView.as_view(), name='spare_part_detail'),
    
    re_path(r'^assets/?$', AssetListView.as_view(), name='asset_list'),
    re_path(r'^assets/tree/?$', AssetTreeView.as_view(), name='asset_tree'),
    re_path(r'^assets/qr/(?P<qr_code>[^/]+)/?$', AssetQRCodeView.as_view(), name='asset_qr'),
    re_path(r'^assets/import/?$', AssetImportView.as_view(), name='asset_import'),
    re_path(r'^assets/import-template/?$', AssetImportTemplateView.as_view(), name='asset_import_template'),
    re_path(r'^assets/export/?$', AssetExportView.as_view(), name='asset_export'),
    re_path(r'^assets/(?P<asset_id>[0-9a-fA-F-]+)/?$', AssetDetailView.as_view(), name='asset_detail'),
    
    re_path(r'^assets/(?P<asset_id>[0-9a-fA-F-]+)/meter-readings/?$', MeterReadingListView.as_view(), name='meter_reading_list'),
    re_path(r'^assets/(?P<asset_id>[0-9a-fA-F-]+)/anomaly-history/?$', AssetAnomalyHistoryView.as_view(), name='asset_anomaly_history'),
    re_path(r'^condition-monitoring/alerts/(?P<alert_id>[0-9a-fA-F-]+)/feedback/?$', ConditionMonitoringAlertFeedbackView.as_view(), name='condition_monitoring_alert_feedback'),

    # Phase 11.5: RUL Predictive Maintenance Endpoints
    re_path(r'^assets/(?P<asset_id>[0-9a-fA-F-]+)/rul-prediction/?$', AssetRulPredictionDetailView.as_view(), name='asset_rul_prediction_detail'),
    re_path(r'^assets/(?P<asset_id>[0-9a-fA-F-]+)/rul-prediction/run/?$', AssetRulPredictionRunView.as_view(), name='asset_rul_prediction_run'),
    re_path(r'^assets/(?P<asset_id>[0-9a-fA-F-]+)/rul-prediction/override-phantom/?$', AssetRulOverridePhantomView.as_view(), name='asset_rul_override_phantom'),
    re_path(r'^predictive-maintenance/critical-assets/?$', CriticalAssetsRulListView.as_view(), name='critical_assets_rul_list'),
]

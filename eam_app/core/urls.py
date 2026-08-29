from django.urls import path
from core.views.system import (
    SystemTenantListView, SystemTenantDetailView, SystemTenantStatusView,
    SystemTenantAdminListView, SystemTenantAdminDetailView, SystemTenantAdminStatusView
)
from core.views.files import FileUploadView
from core.views.tenant import TenantSettingsView
from core.views.audit import AuditLogListView

urlpatterns = [
    path('audit-logs', AuditLogListView.as_view(), name='audit_log_list'),
    path('tenant/settings', TenantSettingsView.as_view(), name='tenant_settings'),
    path('system/tenants', SystemTenantListView.as_view(), name='system_tenant_list'),
    path('system/tenants/<uuid:tenant_id>', SystemTenantDetailView.as_view(), name='system_tenant_detail'),
    path('system/tenants/<uuid:tenant_id>/status', SystemTenantStatusView.as_view(), name='system_tenant_status'),
    path('system/tenants/<uuid:tenant_id>/admins', SystemTenantAdminListView.as_view(), name='system_tenant_admin_list'),
    path('system/tenants/<uuid:tenant_id>/admins/<uuid:admin_id>', SystemTenantAdminDetailView.as_view(), name='system_tenant_admin_detail'),
    path('system/tenants/<uuid:tenant_id>/admins/<uuid:admin_id>/status', SystemTenantAdminStatusView.as_view(), name='system_tenant_admin_status'),
    
    path('files/upload/logo', FileUploadView.as_view(), name='file_upload_logo'),
]

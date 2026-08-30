from django.urls import path
from . import views

urlpatterns = [
    path('', views.portal_dashboard, name='portal_dashboard'),
    path('login/', views.portal_login, name='portal_login'),
    path('logout/', views.portal_logout, name='portal_logout'),
    path('change-password/', views.portal_change_password, name='portal_change_password'),
    path('forgot-password/', views.portal_forgot_password, name='portal_forgot_password'),
    path('reset-password/', views.portal_reset_password, name='portal_reset_password'),
    path('tenants/', views.portal_tenants, name='portal_tenants'),
    path('users/', views.portal_users, name='portal_users'),
    path('roles/', views.portal_roles, name='portal_roles'),
    path('settings/', views.portal_settings, name='portal_settings'),
    path('asset-categories/', views.portal_asset_categories, name='portal_asset_categories'),
    path('hierarchy-templates/', views.portal_hierarchy_templates, name='portal_hierarchy_templates'),
    path('assets/', views.portal_asset_registry, name='portal_asset_registry'),
    path('work-orders/', views.portal_work_orders, name='portal_work_orders'),
    path('inventory/', views.portal_inventory, name='portal_inventory'),
    path('pm-plans/', views.portal_pm_plans, name='portal_pm_plans'),
    path('pm-plans/<uuid:plan_id>/assignments/', views.portal_pm_plan_assignments, name='portal_pm_plan_assignments'),
    path('pm-plans/assignments/<uuid:assignment_id>/', views.portal_pm_plan_assignments, name='portal_pm_plan_assignments_detail'),
    path('audit-logs/', views.portal_audit_logs, name='portal_audit_logs'),
]

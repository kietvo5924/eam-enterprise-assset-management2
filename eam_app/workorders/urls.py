from django.urls import path, re_path
from workorders.views import (
    WorkOrderListView, WorkOrderDetailView,
    WorkOrderAssignView, WorkOrderStatusView,
    WorkOrderChecklistView, WorkOrderChecklistDeleteView,
    WorkOrderNoteUpdateView, WorkOrderAttachmentView,
    WorkOrderAttachmentDeleteView, WorkOrderKpiView,
    MaintenanceCalendarView,
    WorkOrderAutoAssignPreviewView, WorkOrderAutoAssignApplyView,
    WorkOrderGAAutoAssignInitiateView, WorkOrderGAAutoAssignProgressView,
    WorkOrderGAAutoAssignApplyView, WorkOrderAlgorithmReadinessView
)

urlpatterns = [
    re_path(r'^work-orders/?$', WorkOrderListView.as_view(), name='work_order_list'),
    re_path(r'^work-orders/kpis/?$', WorkOrderKpiView.as_view(), name='work_order_kpis'),
    re_path(r'^work-orders/calendar/?$', MaintenanceCalendarView.as_view(), name='work_order_calendar'),
    re_path(r'^work-orders/algorithm-readiness/?$', WorkOrderAlgorithmReadinessView.as_view(), name='work_order_algorithm_readiness'),
    re_path(r'^work-orders/auto-assign/preview/?$', WorkOrderAutoAssignPreviewView.as_view(), name='work_order_auto_assign_preview'),
    re_path(r'^work-orders/auto-assign/apply/?$', WorkOrderAutoAssignApplyView.as_view(), name='work_order_auto_assign_apply'),
    re_path(r'^work-orders/ga-auto-assign/?$', WorkOrderGAAutoAssignInitiateView.as_view(), name='work_order_ga_auto_assign_initiate'),
    re_path(r'^work-orders/ga-auto-assign/(?P<task_id>[0-9a-fA-F-]+)/progress/?$', WorkOrderGAAutoAssignProgressView.as_view(), name='work_order_ga_auto_assign_progress'),
    re_path(r'^work-orders/ga-auto-assign/apply/?$', WorkOrderGAAutoAssignApplyView.as_view(), name='work_order_ga_auto_assign_apply'),
    re_path(r'^work-orders/(?P<wo_id>[0-9a-fA-F-]+)/?$', WorkOrderDetailView.as_view(), name='work_order_detail'),
    re_path(r'^work-orders/(?P<wo_id>[0-9a-fA-F-]+)/assign/?$', WorkOrderAssignView.as_view(), name='work_order_assign'),
    re_path(r'^work-orders/(?P<wo_id>[0-9a-fA-F-]+)/status/?$', WorkOrderStatusView.as_view(), name='work_order_status'),
    re_path(r'^work-orders/(?P<wo_id>[0-9a-fA-F-]+)/checklists/?$', WorkOrderChecklistView.as_view(), name='work_order_checklist'),
    re_path(r'^work-orders/(?P<wo_id>[0-9a-fA-F-]+)/checklists/(?P<checklist_id>[^/]+)/?$', WorkOrderChecklistDeleteView.as_view(), name='work_order_checklist_delete'),
    re_path(r'^work-orders/(?P<wo_id>[0-9a-fA-F-]+)/notes/?$', WorkOrderNoteUpdateView.as_view(), name='work_order_note'),
    re_path(r'^work-orders/(?P<wo_id>[0-9a-fA-F-]+)/attachments/?$', WorkOrderAttachmentView.as_view(), name='work_order_attachment'),
    re_path(r'^work-orders/(?P<wo_id>[0-9a-fA-F-]+)/attachments/(?P<attachment_id>[0-9a-fA-F-]+)/?$', WorkOrderAttachmentDeleteView.as_view(), name='work_order_attachment_delete'),
]

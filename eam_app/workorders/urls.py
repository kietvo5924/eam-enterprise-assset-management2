from django.urls import path
from workorders.views import (
    WorkOrderListView, WorkOrderDetailView,
    WorkOrderAssignView, WorkOrderStatusView,
    WorkOrderChecklistView, WorkOrderChecklistDeleteView,
    WorkOrderNoteUpdateView, WorkOrderAttachmentView,
    WorkOrderAttachmentDeleteView, WorkOrderKpiView,
    MaintenanceCalendarView
)

urlpatterns = [
    path('work-orders', WorkOrderListView.as_view(), name='work_order_list'),
    path('work-orders/kpis', WorkOrderKpiView.as_view(), name='work_order_kpis'),
    path('work-orders/calendar', MaintenanceCalendarView.as_view(), name='work_order_calendar'),
    path('work-orders/<uuid:wo_id>', WorkOrderDetailView.as_view(), name='work_order_detail'),
    path('work-orders/<uuid:wo_id>/assign', WorkOrderAssignView.as_view(), name='work_order_assign'),
    path('work-orders/<uuid:wo_id>/status', WorkOrderStatusView.as_view(), name='work_order_status'),
    path('work-orders/<uuid:wo_id>/checklists', WorkOrderChecklistView.as_view(), name='work_order_checklist'),
    path('work-orders/<uuid:wo_id>/checklists/<uuid:checklist_id>', WorkOrderChecklistDeleteView.as_view(), name='work_order_checklist_delete'),
    path('work-orders/<uuid:wo_id>/notes', WorkOrderNoteUpdateView.as_view(), name='work_order_note'),
    path('work-orders/<uuid:wo_id>/attachments', WorkOrderAttachmentView.as_view(), name='work_order_attachment'),
    path('work-orders/<uuid:wo_id>/attachments/<uuid:attachment_id>', WorkOrderAttachmentDeleteView.as_view(), name='work_order_attachment_delete'),
]

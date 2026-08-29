from django.urls import path
from maintenance.views import (
    PmPlanListView, PmPlanDetailView,
    PmPlanAssignmentView, PmPlanAssignmentDetailView,
    PmPlanKpiView, PmPlanAssignmentStatusView
)

urlpatterns = [
    path('pm-plans', PmPlanListView.as_view(), name='pm_plan_list'),
    path('pm-plans/kpis', PmPlanKpiView.as_view(), name='pm_plan_kpis'),
    path('pm-plans/<uuid:plan_id>', PmPlanDetailView.as_view(), name='pm_plan_detail'),
    path('pm-plans/<uuid:plan_id>/assign', PmPlanAssignmentView.as_view(), name='pm_plan_assign'),
    path('pm-plans/<uuid:plan_id>/assignments', PmPlanAssignmentView.as_view(), name='pm_plan_assignments'),
    path('pm-plans/assignments/<uuid:assignment_id>', PmPlanAssignmentDetailView.as_view(), name='pm_plan_assignment_detail'),
    path('pm-plans/assignments/<uuid:assignment_id>/status', PmPlanAssignmentStatusView.as_view(), name='pm_plan_assignment_status'),
]

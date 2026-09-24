from django.urls import path, re_path
from analytics.views import (
    DashboardSummaryView,
    DashboardTrendsView,
    DashboardActivityFeedView
)

urlpatterns = [
    re_path(r'^summary/?$', DashboardSummaryView.as_view(), name='dashboard_summary'),
    re_path(r'^trends/?$', DashboardTrendsView.as_view(), name='dashboard_trends'),
    re_path(r'^activity-feed/?$', DashboardActivityFeedView.as_view(), name='dashboard_activity_feed'),
]

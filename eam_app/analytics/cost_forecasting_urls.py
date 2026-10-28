"""
URLs cho Phân hệ Quản lý & Dự báo Chi phí Bảo trì (Task 11.6).
"""
from django.urls import re_path
from analytics.cost_forecasting_views import (
    CurrentForecastView,
    RunForecastView,
    LemonAssetsView,
    HistoricalTrendsView,
    CostForecastingReadinessView,
    FinancialSettingsView
)

urlpatterns = [
    re_path(r'^current-forecast/?$', CurrentForecastView.as_view(), name='cost_forecasting_current'),
    re_path(r'^run-forecast/?$', RunForecastView.as_view(), name='cost_forecasting_run'),
    re_path(r'^lemon-assets/?$', LemonAssetsView.as_view(), name='cost_forecasting_lemon_assets'),
    re_path(r'^historical-trends/?$', HistoricalTrendsView.as_view(), name='cost_forecasting_historical_trends'),
    re_path(r'^readiness/?$', CostForecastingReadinessView.as_view(), name='cost_forecasting_readiness'),
    re_path(r'^settings/?$', FinancialSettingsView.as_view(), name='cost_forecasting_settings'),
]


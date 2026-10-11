"""
URL Routing for Task 11.3 Technician Routing Optimization (TSP).
"""

from django.urls import path
from .views import (
    OptimizeRouteView,
    ReRouteMidShiftView,
    MyDailyRouteView,
    ScanToRelocateView,
)

urlpatterns = [
    path('optimize-route/', OptimizeRouteView.as_view(), name='tsp-optimize-route'),
    path('re-route-mid-shift/', ReRouteMidShiftView.as_view(), name='tsp-re-route-mid-shift'),
    path('my-daily-route/', MyDailyRouteView.as_view(), name='tsp-my-daily-route'),
    path('scan-to-relocate/', ScanToRelocateView.as_view(), name='tsp-scan-to-relocate'),
]

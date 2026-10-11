"""
REST API Views for Task 11.3 Technician Routing Optimization (TSP).
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from datetime import datetime

from workorders.models import WorkOrder
from users.models import User
from core.models import Tenant
from .serializers import (
    OptimizeRouteRequestSerializer,
    ReRouteMidShiftRequestSerializer,
    ScanToRelocateRequestSerializer,
)
from .service import TSPRoutingService


def parse_start_time_str(time_str: str) -> float:
    """Parses 'HH:MM' string to minutes from midnight."""
    if not time_str:
        return 480.0  # 08:00
    try:
        parts = time_str.strip().split(':')
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        return float(h * 60 + m)
    except Exception:
        return 480.0


def resolve_tenant(request):
    """Safely resolves active tenant from request or user."""
    if hasattr(request, 'tenant') and request.tenant:
        return request.tenant
    if hasattr(request, 'user') and request.user and getattr(request.user, 'tenant', None):
        return request.user.tenant
    return Tenant.objects.first()


class OptimizeRouteView(APIView):
    """
    POST /api/v1/routing/optimize-route/
    Calculates the optimal technician route honoring hierarchical topological costs,
    Manhattan 2D coordinates, time windows, and multi-urgent clusters.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = OptimizeRouteRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'success': False, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        tenant = resolve_tenant(request)

        technician_id = data.get('technicianId')
        technician = None
        if technician_id:
            technician = User.objects.filter(tenant=tenant, id=technician_id).first()
        elif request.user and request.user.is_authenticated:
            technician = request.user

        work_order_ids = data.get('workOrderIds', [])
        qs = WorkOrder.objects.all()
        if tenant:
            qs = qs.filter(tenant=tenant)

        if work_order_ids:
            work_orders = list(qs.filter(id__in=work_order_ids))
            # Preserve input order or sort
            order_map = {str(wo_id): idx for idx, wo_id in enumerate(work_order_ids)}
            work_orders.sort(key=lambda wo: order_map.get(str(wo.id), 9999))
        elif technician:
            work_orders = list(qs.filter(
                assigned_to=technician,
                status__in=['OPEN', 'IN_PROGRESS', 'ASSIGNED', 'PENDING']
            ))
        else:
            work_orders = []

        start_time_mins = parse_start_time_str(data.get('startTime'))
        service = TSPRoutingService(tenant=tenant)
        result = service.optimize_daily_route(
            technician=technician,
            work_orders=work_orders,
            start_coords=data.get('startCoords'),
            start_location_id=data.get('startLocationId'),
            return_to_depot=data.get('returnToDepot', True),
            start_time_minutes=start_time_mins,
        )

        return Response(result, status=status.HTTP_200_OK)


class ReRouteMidShiftView(APIView):
    """
    POST /api/v1/routing/re-route-mid-shift/
    Dynamic re-routing from current technician position, with optional warehouse pit-stop.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ReRouteMidShiftRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'success': False, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        tenant = resolve_tenant(request)

        technician_id = data.get('technicianId')
        technician = None
        if technician_id:
            technician = User.objects.filter(tenant=tenant, id=technician_id).first()
        elif request.user and request.user.is_authenticated:
            technician = request.user

        rem_ids = data.get('remainingWorkOrderIds', [])
        qs = WorkOrder.objects.all()
        if tenant:
            qs = qs.filter(tenant=tenant)

        if rem_ids:
            rem_wos = list(qs.filter(id__in=rem_ids))
            order_map = {str(wo_id): idx for idx, wo_id in enumerate(rem_ids)}
            rem_wos.sort(key=lambda wo: order_map.get(str(wo.id), 9999))
        elif technician:
            rem_wos = list(qs.filter(
                assigned_to=technician,
                status__in=['OPEN', 'IN_PROGRESS', 'ASSIGNED', 'PENDING']
            ))
        else:
            rem_wos = []

        start_time_mins = None
        if data.get('startTime'):
            start_time_mins = parse_start_time_str(data.get('startTime'))

        service = TSPRoutingService(tenant=tenant)
        result = service.re_route_mid_shift(
            technician=technician,
            current_coords=data.get('currentCoords'),
            current_location_id=data.get('currentLocationId'),
            completed_work_order_ids=data.get('completedWorkOrderIds', []),
            remaining_work_orders=rem_wos,
            include_warehouse_pitstop=data.get('includeWarehousePitstop', False),
            return_to_depot=data.get('returnToDepot', True),
            start_time_minutes=start_time_mins,
        )

        return Response(result, status=status.HTTP_200_OK)


class MyDailyRouteView(APIView):
    """
    GET /api/v1/routing/my-daily-route/
    Returns the optimized daily route for the logged-in technician.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tenant = resolve_tenant(request)
        technician = request.user

        qs = WorkOrder.objects.all()
        if tenant:
            qs = qs.filter(tenant=tenant)

        work_orders = list(qs.filter(
            assigned_to=technician,
            status__in=['OPEN', 'IN_PROGRESS', 'ASSIGNED', 'PENDING']
        ))

        now = timezone.localtime()
        start_time_mins = float(now.hour * 60 + now.minute)

        service = TSPRoutingService(tenant=tenant)
        result = service.optimize_daily_route(
            technician=technician,
            work_orders=work_orders,
            start_time_minutes=start_time_mins,
            return_to_depot=True,
        )

        return Response(result, status=status.HTTP_200_OK)


class ScanToRelocateView(APIView):
    """
    POST /api/v1/routing/scan-to-relocate/
    Updates movable asset current location upon technician QR scan.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ScanToRelocateRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'success': False, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        tenant = resolve_tenant(request)

        service = TSPRoutingService(tenant=tenant)
        result = service.scan_to_relocate(
            qr_code_or_asset_id=data['qrCode'],
            new_location_id=data['newLocationId'],
            user=request.user if request.user.is_authenticated else None,
        )

        http_status = status.HTTP_200_OK if result.get('success') else status.HTTP_400_BAD_REQUEST
        return Response(result, status=http_status)

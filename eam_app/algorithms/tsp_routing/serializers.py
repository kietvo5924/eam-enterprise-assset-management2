"""
Serializers for Task 11.3 Technician Routing Optimization (TSP).
"""

from rest_framework import serializers


class OptimizeRouteRequestSerializer(serializers.Serializer):
    technicianId = serializers.UUIDField(required=False, allow_null=True)
    workOrderIds = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=list
    )
    startCoords = serializers.DictField(required=False, allow_null=True)
    startLocationId = serializers.CharField(required=False, allow_null=True)
    returnToDepot = serializers.BooleanField(required=False, default=True)
    startTime = serializers.CharField(required=False, allow_null=True, default="08:00")


class ReRouteMidShiftRequestSerializer(serializers.Serializer):
    technicianId = serializers.UUIDField(required=False, allow_null=True)
    currentLocationId = serializers.CharField(required=False, allow_null=True)
    currentCoords = serializers.DictField(required=False, allow_null=True)
    actionTrigger = serializers.CharField(required=False, default="MANUAL")
    includeWarehousePitstop = serializers.BooleanField(required=False, default=False)
    completedWorkOrderIds = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=list
    )
    remainingWorkOrderIds = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=list
    )
    returnToDepot = serializers.BooleanField(required=False, default=True)
    startTime = serializers.CharField(required=False, allow_null=True)


class ScanToRelocateRequestSerializer(serializers.Serializer):
    qrCode = serializers.CharField(required=True)
    newLocationId = serializers.CharField(required=True)

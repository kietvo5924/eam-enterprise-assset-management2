from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.core.exceptions import ValidationError
from core.models import Tenant
from users.permissions import HasPermission

def success_response(data=None, message="Success"):
    return Response({
        "success": True,
        "message": message,
        "data": data
    }, status=status.HTTP_200_OK)

class TenantSettingsView(APIView):
    def get(self, request):
        checker = HasPermission('tenant:read')()
        if not checker.has_permission(request, self):
            self.permission_denied(request)

        tenant = request.user.tenant
        
        # Serialize to match TenantSettingsDto
        data = {
            "id": str(tenant.id),
            "name": tenant.name,
            "tenantCode": tenant.tenant_code,
            "servicePlan": tenant.service_plan,
            "timezone": tenant.timezone,
            "logoUrl": getattr(tenant, 'logo_url', None),
            "themeColor": getattr(tenant, 'theme_color', 'cyan'),
            "enableTspRouting": getattr(tenant, 'enable_tsp_routing', True),
            "enableAiHungarian": getattr(tenant, 'enable_ai_hungarian', True),
            "enableAiGenetic": getattr(tenant, 'enable_ai_genetic', True),
            "enableAiRul": getattr(tenant, 'enable_ai_rul', True),
            "enableAiAnomalyDetection": getattr(tenant, 'enable_ai_anomaly_detection', True),
            "enableAiCostForecasting": getattr(tenant, 'enable_ai_cost_forecasting', True),
            "createdAt": tenant.created_at.isoformat() if tenant.created_at else None,
            "updatedAt": tenant.updated_at.isoformat() if tenant.updated_at else None,
        }
        return success_response(data)

    @transaction.atomic
    def put(self, request):
        checker = HasPermission('tenant:update')()
        if not checker.has_permission(request, self):
            self.permission_denied(request)

        tenant = request.user.tenant
        
        # Update settings
        tenant.name = request.data.get('name', tenant.name)
        tenant.timezone = request.data.get('timezone', tenant.timezone)
        if 'logoUrl' in request.data or 'logo_url' in request.data:
            raw_logo = request.data.get('logoUrl', request.data.get('logo_url'))
            tenant.logo_url = str(raw_logo).strip() if raw_logo and str(raw_logo).strip() else None

        # Tùy biến Theme màu
        if 'themeColor' in request.data:
            tenant.theme_color = request.data.get('themeColor')
        elif 'theme_color' in request.data:
            tenant.theme_color = request.data.get('theme_color')

        # Quản trị thuật toán AI (Toggles)
        if 'enableTspRouting' in request.data:
            tenant.enable_tsp_routing = bool(request.data.get('enableTspRouting'))
        elif 'enable_tsp_routing' in request.data:
            tenant.enable_tsp_routing = bool(request.data.get('enable_tsp_routing'))

        if 'enableAiHungarian' in request.data:
            tenant.enable_ai_hungarian = bool(request.data.get('enableAiHungarian'))
        elif 'enable_ai_hungarian' in request.data:
            tenant.enable_ai_hungarian = bool(request.data.get('enable_ai_hungarian'))

        if 'enableAiGenetic' in request.data:
            tenant.enable_ai_genetic = bool(request.data.get('enableAiGenetic'))
        elif 'enable_ai_genetic' in request.data:
            tenant.enable_ai_genetic = bool(request.data.get('enable_ai_genetic'))

        if 'enableAiRul' in request.data:
            tenant.enable_ai_rul = bool(request.data.get('enableAiRul'))
        elif 'enable_ai_rul' in request.data:
            tenant.enable_ai_rul = bool(request.data.get('enable_ai_rul'))

        if 'enableAiAnomalyDetection' in request.data:
            tenant.enable_ai_anomaly_detection = bool(request.data.get('enableAiAnomalyDetection'))
        elif 'enable_ai_anomaly_detection' in request.data:
            tenant.enable_ai_anomaly_detection = bool(request.data.get('enable_ai_anomaly_detection'))

        if 'enableAiCostForecasting' in request.data:
            tenant.enable_ai_cost_forecasting = bool(request.data.get('enableAiCostForecasting'))
        elif 'enable_ai_cost_forecasting' in request.data:
            tenant.enable_ai_cost_forecasting = bool(request.data.get('enable_ai_cost_forecasting'))
            
        tenant.save()
        
        data = {
            "id": str(tenant.id),
            "name": tenant.name,
            "tenantCode": tenant.tenant_code,
            "servicePlan": tenant.service_plan,
            "timezone": tenant.timezone,
            "logoUrl": getattr(tenant, 'logo_url', None),
            "themeColor": getattr(tenant, 'theme_color', 'cyan'),
            "enableTspRouting": getattr(tenant, 'enable_tsp_routing', True),
            "enableAiHungarian": getattr(tenant, 'enable_ai_hungarian', True),
            "enableAiGenetic": getattr(tenant, 'enable_ai_genetic', True),
            "enableAiRul": getattr(tenant, 'enable_ai_rul', True),
            "enableAiAnomalyDetection": getattr(tenant, 'enable_ai_anomaly_detection', True),
            "enableAiCostForecasting": getattr(tenant, 'enable_ai_cost_forecasting', True),
            "createdAt": tenant.created_at.isoformat() if tenant.created_at else None,
            "updatedAt": tenant.updated_at.isoformat() if tenant.updated_at else None,
        }
        return success_response(data)

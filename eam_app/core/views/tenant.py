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
        # Assuming logoUrl is handled here or via FileUploadView, we update it if provided
        if 'logoUrl' in request.data:
            tenant.logo_url = request.data.get('logoUrl')
            
        tenant.save()
        
        data = {
            "id": str(tenant.id),
            "name": tenant.name,
            "tenantCode": tenant.tenant_code,
            "servicePlan": tenant.service_plan,
            "timezone": tenant.timezone,
            "logoUrl": getattr(tenant, 'logo_url', None),
            "createdAt": tenant.created_at.isoformat() if tenant.created_at else None,
            "updatedAt": tenant.updated_at.isoformat() if tenant.updated_at else None,
        }
        return success_response(data)

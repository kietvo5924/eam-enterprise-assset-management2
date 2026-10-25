import re
from django.http import JsonResponse
from core.tenant_context import set_current_tenant, clear_current_tenant

class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.exempt_urls = [
            re.compile(r'^/api/v1/system.*'),
            re.compile(r'^/api/v1/auth/login.*'),
            re.compile(r'^/api/v1/auth/refresh.*'),
            re.compile(r'^/api/v1/auth/forgot-password.*'),
            re.compile(r'^/api/v1/auth/reset-password.*'),
            re.compile(r'^/api/v1/auth/accept-invite.*'),
            re.compile(r'^/admin.*'),
            re.compile(r'^/login/?$'),
            re.compile(r'^/logout/?$'),
        ]

    def __call__(self, request):
        path = request.path_info
        
        is_exempt = any(m.match(path) for m in self.exempt_urls)
        
        if not is_exempt:
            header_tenant_id = request.headers.get('X-Tenant-Id')
            jwt_tenant_id = None
            jwt_is_superuser = False

            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
                try:
                    from rest_framework_simplejwt.tokens import AccessToken
                    access_token = AccessToken(token)
                    jwt_tenant_id = access_token.get('tenantId')
                    jwt_is_superuser = access_token.get('is_superuser', False)
                except Exception:
                    pass

            forced_user = getattr(request, '_force_auth_user', None) or (request.user if hasattr(request, 'user') and request.user.is_authenticated else None)
            auth_tenant_id = jwt_tenant_id or (getattr(forced_user, 'tenant_id', None) if forced_user else None)
            is_super = jwt_is_superuser or (getattr(forced_user, 'is_superuser', False) if forced_user else False)

            # Security check: if user is authenticated and attempts to access another tenant
            if header_tenant_id and auth_tenant_id and not is_super:
                if str(header_tenant_id) != str(auth_tenant_id):
                    return JsonResponse(
                        {'error': 'Forbidden: You do not have access to this tenant.'},
                        status=403
                    )

            tenant_id = header_tenant_id or auth_tenant_id

            if not tenant_id:
                if path.startswith('/api/'):
                    return JsonResponse(
                        {'error': 'Tenant context is missing! A valid tenant_id is required to access data.'},
                        status=400
                    )
                # For non-API routes, let the view/login_required decorator handle it
            else:
                set_current_tenant(tenant_id)
        else:
            clear_current_tenant()

        response = self.get_response(request)
        
        clear_current_tenant()
        return response

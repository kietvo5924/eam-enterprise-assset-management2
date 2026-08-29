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
            # We will read tenant_id from user if authenticated via session
            # For JWT, we parse the token directly
            tenant_id = request.headers.get('X-Tenant-Id')
            
            if not tenant_id:
                auth_header = request.headers.get('Authorization')
                if auth_header and auth_header.startswith('Bearer '):
                    token = auth_header.split(' ')[1]
                    try:
                        from rest_framework_simplejwt.tokens import AccessToken
                        access_token = AccessToken(token)
                        tenant_id = access_token.get('tenantId')
                    except Exception:
                        pass

            if not tenant_id and hasattr(request, 'user') and request.user.is_authenticated:
                if hasattr(request.user, 'tenant_id'):
                    tenant_id = request.user.tenant_id

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

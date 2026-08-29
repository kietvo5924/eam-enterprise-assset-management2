from core.audit_context import set_current_user_id, clear_current_user_id

class AuditMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user_id = 'system'
        
        # If authenticated via session
        if hasattr(request, 'user') and request.user.is_authenticated:
            user_id = str(request.user.id)
        else:
            # Check JWT token
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
                try:
                    from rest_framework_simplejwt.tokens import AccessToken
                    access_token = AccessToken(token)
                    # We configured USER_ID_CLAIM to 'sub' which holds username. 
                    # But if we need user UUID, maybe it's not in the token. 
                    # Wait, in authentication.py we put username in 'username' and 'sub'.
                    # Let's just store the username as user_id for auditing, matching Java which might use user ID string.
                    # Java says: userId = ((CustomUserDetails) auth.getPrincipal()).getId().toString();
                    user_id = access_token.get('userId', 'system')
                except Exception:
                    pass

        set_current_user_id(user_id)
        
        response = self.get_response(request)
        
        clear_current_user_id()
        return response

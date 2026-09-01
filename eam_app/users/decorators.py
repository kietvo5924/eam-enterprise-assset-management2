# pyrefly: ignore [missing-import]
from django.core.exceptions import PermissionDenied
# pyrefly: ignore [missing-import]
from django.http import JsonResponse
from functools import wraps

def permission_required(perm):
    """
    Decorator for views that checks whether a user has a particular permission.
    `perm` can be a single string or an iterable of strings (in which case ANY permission is sufficient).
    Returns a JsonResponse for AJAX requests, otherwise raises PermissionDenied.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept', '') or request.content_type == 'application/json'
            
            if not request.user or not request.user.is_authenticated:
                if is_ajax:
                    return JsonResponse({'success': False, 'error': 'You must be logged in.'}, status=401)
                raise PermissionDenied("You must be logged in.")

            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            # Cache permissions on the request object for the duration of the request
            if not hasattr(request, '_user_permissions_cache'):
                perms = set()
                for role in request.user.roles.prefetch_related('permissions').all():
                    for p in role.permissions.all():
                        perms.add(p.id)
                request._user_permissions_cache = perms
            
            if 'system:admin' in request._user_permissions_cache:
                return view_func(request, *args, **kwargs)
                
            has_perm = False
            if isinstance(perm, (list, tuple)):
                if any(p in request._user_permissions_cache for p in perm):
                    has_perm = True
            else:
                if perm in request._user_permissions_cache:
                    has_perm = True
                    
            if has_perm:
                return view_func(request, *args, **kwargs)

            error_msg = f"You do not have permission to access this resource ({perm} required)."
            if is_ajax:
                return JsonResponse({'success': False, 'error': error_msg}, status=403)
            raise PermissionDenied(error_msg)
            
        return _wrapped_view
    return decorator

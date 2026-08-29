from rest_framework.permissions import BasePermission

class HasPermission:
    """
    Factory function that returns a BasePermission class 
    checking if the user has the specified permission via their roles.
    """
    def __new__(cls, required_permission):
        class _HasPermission(BasePermission):
            def has_permission(self, request, view):
                if not request.user or not request.user.is_authenticated:
                    return False
                
                # Superusers or users with system:admin permission can bypass
                if request.user.is_superuser:
                    return True
                    
                # Cache permissions on the request object for the duration of the request
                if not hasattr(request, '_user_permissions_cache'):
                    perms = set()
                    for role in request.user.roles.prefetch_related('permissions').all():
                        for perm in role.permissions.all():
                            perms.add(perm.id)
                    request._user_permissions_cache = perms
                
                if 'system:admin' in request._user_permissions_cache:
                    return True
                    
                return required_permission in request._user_permissions_cache
                
        return _HasPermission

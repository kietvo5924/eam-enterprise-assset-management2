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
                    
                # Explicit permission grant
                if required_permission in request._user_permissions_cache:
                    return True

                # Assistant RBAC matrix mappings (Section 5 Harmonized RBAC Matrix)
                user_roles = [r.name.upper() for r in request.user.roles.all()]
                if required_permission == 'assistant:chat':
                    # All authenticated users have access to field assistant chat
                    return True
                elif required_permission == 'assistant:manage_knowledge':
                    if 'tenant:update' in request._user_permissions_cache:
                        return True
                    if any(r in user_roles for r in ['ADMIN', 'TENANT_ADMIN', 'MAINTENANCE_MANAGER', 'CHIEF_ENGINEER']):
                        return True
                elif required_permission == 'assistant:curate_qa':
                    if any(r in user_roles for r in ['CHIEF_ENGINEER', 'MAINTENANCE_MANAGER', 'ADMIN', 'TENANT_ADMIN']):
                        return True
                elif required_permission == 'assistant:configure_safety':
                    if any(r in user_roles for r in ['SAFETY_OFFICER', 'ADMIN', 'TENANT_ADMIN']):
                        return True

                return False
                
        return _HasPermission


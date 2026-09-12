from users.models import Permission

def user_permissions(request):
    """
    Context processor providing active user's permissions, roles, and admin status to all templates.
    """
    if not hasattr(request, 'user') or not request.user.is_authenticated:
        return {
            'user_permissions': set(),
            'user_roles': [],
            'user_role_names': 'Guest',
            'is_system_admin': False,
            'current_tenant': None,
        }
    
    if not hasattr(request, '_user_roles_cache') or not hasattr(request, '_is_system_admin_cache') or not hasattr(request, '_user_permissions_cache'):
        roles = list(request.user.roles.prefetch_related('permissions').all())
        perms = set()
        for role in roles:
            for p in role.permissions.all():
                perms.add(p.id)
        
        is_sys_admin = request.user.is_superuser or ('system:admin' in perms) or any(r.name == 'SUPER_ADMIN' for r in roles)
        if is_sys_admin:
            try:
                all_perms = set(Permission.objects.values_list('id', flat=True))
                all_perms.add('system:admin')
                perms = all_perms
            except Exception:
                perms.add('system:admin')

        request._user_permissions_cache = perms
        request._user_roles_cache = [r.name for r in roles]
        request._is_system_admin_cache = is_sys_admin
        
    role_names = getattr(request, '_user_roles_cache', [])
    display_roles = ', '.join(role_names) if role_names else ('Super Admin' if request.user.is_superuser else 'Không có vai trò')
    current_tenant = getattr(request.user, 'tenant', None)
    
    return {
        'user_permissions': getattr(request, '_user_permissions_cache', set()),
        'user_roles': role_names,
        'user_role_names': display_roles,
        'is_system_admin': getattr(request, '_is_system_admin_cache', False),
        'current_tenant': current_tenant,
    }


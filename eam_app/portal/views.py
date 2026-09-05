from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from users.decorators import permission_required
from django.contrib import messages

def check_perm(request, perm):
    if not request.user or not request.user.is_authenticated:
        return False
    if request.user.is_superuser:
        return True
    if not hasattr(request, '_user_permissions_cache'):
        perms = set()
        for role in request.user.roles.prefetch_related('permissions').all():
            for p in role.permissions.all():
                perms.add(p.id)
        request._user_permissions_cache = perms
    if 'system:admin' in request._user_permissions_cache:
        return True
    if isinstance(perm, (list, tuple, set)):
        return any(p in request._user_permissions_cache for p in perm)
    return perm in request._user_permissions_cache

def portal_login(request):
    if request.user.is_authenticated:
        return redirect('portal_dashboard')
        
    if request.method == 'POST':
        u = request.POST.get('username')
        p = request.POST.get('password')
        user = authenticate(request, username=u, password=p)
        if user is None and u and '@' in u:
            from users.models import User
            found_user = User.all_objects.filter(email__iexact=u).first()
            if found_user:
                user = authenticate(request, username=found_user.username, password=p)
        if user is not None:
            login(request, user)
            return redirect('portal_dashboard')
        else:
            messages.error(request, 'Invalid username or password')
            
    return render(request, 'login.html')

def portal_logout(request):
    logout(request)
    return redirect('portal_login')

@login_required(login_url='portal_login')
def portal_dashboard(request):
    from workorders.models import WorkOrder
    from assets.models import Asset
    
    total_assets = Asset.objects.count()
    operational_assets = Asset.objects.filter(status='OPERATIONAL').count()
    active_work_orders = WorkOrder.objects.filter(status__in=['CREATED', 'ASSIGNED', 'IN_PROGRESS']).count()
    completed_work_orders = WorkOrder.objects.filter(status='COMPLETED').count()

    context = {
        'total_assets': total_assets,
        'operational_assets': operational_assets,
        'active_work_orders': active_work_orders,
        'completed_work_orders': completed_work_orders,
    }
    return render(request, 'dashboard.html', context)

@login_required(login_url='portal_login')
@permission_required('system:admin')
def portal_tenants(request):
    from core.models import Tenant
    import json
    from django.http import JsonResponse, HttpResponseForbidden
    
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            t = Tenant.objects.create(
                name=data.get('name'),
                tenant_code=data.get('tenant_code'),
                service_plan=data.get('service_plan', 'FREE'),
                status=data.get('status', 'ACTIVE')
            )
            return JsonResponse({'success': True, 'id': str(t.id)})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
            
    elif request.method == 'PUT':
        try:
            data = json.loads(request.body)
            t = Tenant.objects.get(id=data.get('id'))
            t.name = data.get('name')
            t.tenant_code = data.get('tenant_code')
            t.service_plan = data.get('service_plan', 'FREE')
            t.status = data.get('status', 'ACTIVE')
            t.save()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
            
    elif request.method == 'DELETE':
        try:
            data = json.loads(request.body)
            t = Tenant.objects.get(id=data.get('id'))
            # Don't delete the super admin tenant
            if str(t.id) == '00000000-0000-0000-0000-000000000000':
                return JsonResponse({'success': False, 'error': 'Cannot delete System Tenant'}, status=400)
            t.delete()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
            
    tenants = Tenant.objects.all().order_by('-created_at')
    return render(request, 'tenants.html', {'tenants': tenants})

@login_required(login_url='portal_login')
@permission_required('system:admin')
def portal_tenant_admins(request):
    from users.models import User, Role, Permission
    from core.models import Tenant
    import json
    from django.http import JsonResponse, HttpResponseForbidden
    from django.contrib.auth.hashers import make_password
    
        
    if request.method == 'GET':
        tenant_id = request.GET.get('tenant_id')
        if not tenant_id:
            return JsonResponse({'success': False, 'error': 'tenant_id is required'}, status=400)
            
        admins = User.all_objects.filter(tenant_id=tenant_id, roles__name='TENANT_ADMIN').distinct()
        data = []
        for a in admins:
            data.append({
                'id': str(a.id),
                'username': a.username,
                'status': a.status,
                'created_at': a.created_at.isoformat() if a.created_at else None
            })
        return JsonResponse({'success': True, 'data': data})
        
    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
            tenant_id = data.get('tenant_id')
            username = data.get('username')
            password = data.get('password')
            
            if User.all_objects.filter(tenant_id=tenant_id, username=username).exists():
                return JsonResponse({'success': False, 'error': 'Username already exists in this tenant'}, status=400)
                
            tenant = Tenant.objects.get(id=tenant_id)
            
            admin_role, created = Role.all_objects.get_or_create(
                tenant_id=tenant_id,
                name='TENANT_ADMIN',
                defaults={
                    'description': 'Administrator for Tenant',
                    'is_system': True
                }
            )
            
            if created:
                perms = Permission.objects.exclude(id='system:admin')
                admin_role.permissions.set(perms)
                
            u = User.all_objects.create(
                tenant_id=tenant_id,
                username=username,
                email=username,
                password=make_password(password),
                status='ACTIVE'
            )
            u.roles.add(admin_role)
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
            
    elif request.method == 'PUT':
        try:
            data = json.loads(request.body)
            admin_id = data.get('id')
            u = User.all_objects.get(id=admin_id)
            
            if data.get('status'):
                if str(u.id) == '00000000-0000-0000-0000-000000000000':
                    return JsonResponse({'success': False, 'error': 'Cannot modify the Super Admin'}, status=400)
                u.status = data.get('status')
            
            if data.get('username'):
                u.username = data.get('username')
                u.email = data.get('username')
                
            if data.get('password'):
                u.password = make_password(data.get('password'))
                
            u.save()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

@login_required(login_url='portal_login')
@permission_required('tenant:read')
def portal_settings(request):
    from core.models import Tenant
    import json
    from django.http import JsonResponse, HttpResponseForbidden
    from users.permissions import HasPermission
    
    tenant = request.user.tenant
    
    if request.method == 'POST':
        checker = HasPermission('tenant:update')()
        if not checker.has_permission(request, None):
            return JsonResponse({'success': False, 'error': 'Permission denied: tenant:update required'}, status=403)
            
        try:
            data = json.loads(request.body)
            tenant.name = data.get('name', tenant.name)
            tenant.logo_url = data.get('logoUrl', tenant.logo_url)
            tenant.timezone = data.get('timezone', tenant.timezone)
            tenant.save()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
            
    # GET method
        
    return render(request, 'settings.html', {'tenant': tenant})


@login_required(login_url='portal_login')
def portal_change_password(request):
    import json
    from django.http import JsonResponse
    from django.contrib.auth import update_session_auth_hash
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            old_password = data.get('oldPassword')
            new_password = data.get('newPassword')
            
            if not request.user.check_password(old_password):
                return JsonResponse({'success': False, 'error': 'Invalid current password'}, status=400)
                
            request.user.set_password(new_password)
            request.user.save()
            update_session_auth_hash(request, request.user) # Keep user logged in
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)

def portal_forgot_password(request):
    import json
    from django.http import JsonResponse
    from users.models import User
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            email = data.get('email')
            # Mock sending email. In a real app, generate a 6-digit code, save to DB, and send via Resend/SMTP
            user = User.objects.filter(email=email).first()
            if user:
                # Code generated, normally saved to cache/DB
                pass
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)

def portal_reset_password(request):
    import json
    from django.http import JsonResponse
    from users.models import User
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            code = data.get('code')
            new_password = data.get('newPassword')
            
            # Mock validation. In a real app, verify the code from DB/Cache
            if len(code) < 6:
                return JsonResponse({'success': False, 'error': 'Invalid code'}, status=400)
                
            # For demo, just find any user (or we could pass email) and reset. 
            # We don't have email in the second step according to the web-portal UI.
            # Real app: get email from session/cache using the code
            # Let's just return success for demo purposes if code is '123456'
            if code == '123456':
                return JsonResponse({'success': True})
            else:
                return JsonResponse({'success': False, 'error': 'Invalid code. Use 123456 for demo.'}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)

@login_required(login_url='portal_login')
@permission_required('user:read')
def portal_users(request):
    from users.models import User, Role
    from users.permissions import HasPermission
    import json
    from django.http import JsonResponse, HttpResponseForbidden
    
    tenant_id = request.user.tenant_id
    
    if request.method == 'POST':
        if not HasPermission('user:create')().has_permission(request, None):
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
            
        action = request.GET.get('action')
        if action == 'import':
            file = request.FILES.get('file')
            if not file:
                return JsonResponse({'success': False, 'error': 'No file uploaded'}, status=400)
            return JsonResponse({'success': True, 'data': {'successCount': 0, 'failureCount': 1, 'errors': ['Import functionality is not fully implemented in this demo']}})
        
        try:
            data = json.loads(request.body)
            if action == 'invite':
                # Mock invite behavior
                username = data.get('username')
                if User.objects.filter(username=username).exists():
                    return JsonResponse({'success': False, 'error': 'Username already exists'}, status=400)
                u = User.objects.create(
                    username=username,
                    email=data.get('email'),
                    status='PENDING',
                    tenant_id=tenant_id
                )
                if data.get('password'):
                    u.set_password(data.get('password'))
                    u.save()
                role_ids = data.get('roleIds', [])
                if role_ids:
                    roles = list(Role.objects.filter(id__in=role_ids, tenant_id=tenant_id))
                    for r in roles:
                        is_super = request.user.is_superuser or request.user.roles.filter(name='SUPER_ADMIN').exists()
                        if r.name == 'SUPER_ADMIN' and not is_super:
                            return JsonResponse({'success': False, 'error': 'You do not have permission to assign the SUPER_ADMIN role'}, status=403)
                    u.roles.set(roles)
                return JsonResponse({'success': True})

            username = data.get('username')
            if User.all_objects.filter(tenant_id=tenant_id, username=username).exists():
                return JsonResponse({'success': False, 'error': 'Username already exists in this organization'}, status=400)
            email = data.get('email')
            if email and User.all_objects.filter(tenant_id=tenant_id, email=email).exists():
                return JsonResponse({'success': False, 'error': 'Email already exists in this organization'}, status=400)
                
            u = User.all_objects.create(
                username=username,
                email=email,
                status=data.get('status', 'ACTIVE'),
                tenant_id=tenant_id
            )
            if data.get('password'):
                u.set_password(data.get('password'))
                u.save()
                
            role_ids = data.get('roles', [])
            if role_ids:
                roles = list(Role.objects.filter(id__in=role_ids, tenant_id=tenant_id))
                for r in roles:
                    is_super = request.user.is_superuser or request.user.roles.filter(name='SUPER_ADMIN').exists()
                    if r.name == 'SUPER_ADMIN' and not is_super:
                        return JsonResponse({'success': False, 'error': 'You do not have permission to assign the SUPER_ADMIN role'}, status=403)
                u.roles.set(roles)
            else:
                u.roles.clear()
                
            return JsonResponse({'success': True, 'id': str(u.id)})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
            
    elif request.method == 'PUT':
        if not HasPermission('user:update')().has_permission(request, None):
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
            
        action = request.GET.get('action')
        try:
            if action in ['disable', 'enable']:
                user_id = request.GET.get('id')
                if not user_id:
                    return JsonResponse({'success': False, 'error': 'Missing ID'}, status=400)
                u = User.objects.get(id=user_id, tenant_id=tenant_id)
                if u.id == request.user.id and action == 'disable':
                    return JsonResponse({'success': False, 'error': 'Cannot block yourself'}, status=400)
                if u.is_superuser and action == 'disable':
                    return JsonResponse({'success': False, 'error': 'Cannot block superuser'}, status=400)
                u.status = 'INACTIVE' if action == 'disable' else 'ACTIVE'
                u.save()
                return JsonResponse({'success': True})
                
            data = json.loads(request.body)
            u = User.objects.get(id=data.get('id'), tenant_id=tenant_id)
            
            new_username = data.get('username')
            if new_username != u.username and User.objects.filter(username=new_username).exists():
                return JsonResponse({'success': False, 'error': 'Username already exists'}, status=400)
                
            u.username = new_username
            u.email = data.get('email')
            if 'status' in data:
                u.status = data.get('status')
            
            if data.get('password'):
                u.set_password(data.get('password'))
            u.save()
            
            role_ids = data.get('roles', [])
            roles = list(Role.objects.filter(id__in=role_ids, tenant_id=tenant_id))
            for r in roles:
                is_super = request.user.is_superuser or request.user.roles.filter(name='SUPER_ADMIN').exists()
                if r.name == 'SUPER_ADMIN' and not is_super:
                    return JsonResponse({'success': False, 'error': 'You do not have permission to assign the SUPER_ADMIN role'}, status=403)
            u.roles.set(roles)
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
            
    elif request.method == 'DELETE':
        if not HasPermission('user:update')().has_permission(request, None): # delete is mapped to update block in legacy usually? No legacy has delete? Wait, legacy only has disable/enable.
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        try:
            data = json.loads(request.body)
            u = User.objects.get(id=data.get('id'), tenant_id=tenant_id)
            if u.id == request.user.id:
                return JsonResponse({'success': False, 'error': 'Cannot block your own account'}, status=400)
            if u.is_superuser:
                return JsonResponse({'success': False, 'error': 'Cannot block superuser'}, status=400)
            # Soft delete by marking INACTIVE instead of deleting
            u.status = 'INACTIVE'
            u.save()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)


    if str(tenant_id) == '00000000-0000-0000-0000-000000000000' or request.user.is_superuser:
        users = User.all_objects.exclude(id='00000000-0000-0000-0000-000000000000').order_by('-created_at')
    else:
        users = User.objects.filter(tenant_id=tenant_id).order_by('-created_at')
    
    # Calculate metrics
    total_users = users.count()
    active_users = users.filter(status='ACTIVE').count()
    blocked_users = users.filter(status='INACTIVE').count()
    pending_users = users.filter(status='PENDING').count()
    
    is_super = request.user.is_superuser or request.user.roles.filter(name='SUPER_ADMIN').exists()
    if is_super:
        roles = Role.all_objects.all()
    else:
        roles = Role.objects.filter(tenant_id=tenant_id).exclude(name='SUPER_ADMIN')
    
    return render(request, 'users.html', {
        'users': users, 
        'roles': roles,
        'total_users': total_users,
        'active_users': active_users,
        'blocked_users': blocked_users,
        'pending_users': pending_users
    })

@login_required(login_url='portal_login')
@permission_required('role:read')
def portal_roles(request):
    from users.models import Role, Permission
    import json
    from django.http import JsonResponse, HttpResponseForbidden
    from users.permissions import HasPermission
    
    tenant_id = request.user.tenant_id
    
    if request.method == 'POST':
        if not HasPermission('role:create')().has_permission(request, None):
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        try:
            data = json.loads(request.body)
            name = data.get('name')
            
            if Role.objects.filter(name=name, tenant_id=tenant_id).exists():
                return JsonResponse({'success': False, 'error': f'Role with name {name} already exists in this tenant'}, status=400)
                
            r = Role.objects.create(
                name=name,
                description=data.get('description'),
                is_system=False,
                tenant_id=tenant_id
            )
            
            perm_ids = data.get('permissions', [])
            if perm_ids:
                perms = Permission.objects.filter(id__in=perm_ids)
                r.permissions.set(perms)
                
            return JsonResponse({'success': True, 'id': str(r.id)})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
            
    elif request.method == 'PUT':
        if not HasPermission('role:update')().has_permission(request, None):
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        try:
            data = json.loads(request.body)
            r = Role.objects.get(id=data.get('id'), tenant_id=tenant_id)
            
            if r.is_system:
                return JsonResponse({'success': False, 'error': 'Cannot edit system roles'}, status=400)
                
            new_name = data.get('name')
            if new_name != r.name and Role.objects.filter(name=new_name, tenant_id=tenant_id).exists():
                return JsonResponse({'success': False, 'error': 'Role name already exists'}, status=400)
                
            r.name = new_name
            r.description = data.get('description')
            r.save()
            
            perm_ids = data.get('permissions', [])
            perms = Permission.objects.filter(id__in=perm_ids)
            r.permissions.set(perms)
            
            return JsonResponse({'success': True})
        except Role.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Role not found in this tenant'}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
            
    elif request.method == 'DELETE':
        if not HasPermission('role:delete')().has_permission(request, None):
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        try:
            from users.models import User
            data = json.loads(request.body)
            r = Role.objects.get(id=data.get('id'), tenant_id=tenant_id)
            if r.is_system:
                return JsonResponse({'success': False, 'error': 'Cannot delete system roles'}, status=400)
                
            fallback_role_id = data.get('fallbackRoleId')
            users_with_role = User.objects.filter(roles=r, tenant_id=tenant_id)
            
            if users_with_role.exists():
                if not fallback_role_id:
                    return JsonResponse({'success': False, 'error': 'ROLE_HAS_USERS'}, status=400)
                
                try:
                    fallback_role = Role.objects.get(id=fallback_role_id, tenant_id=tenant_id)
                    for user in users_with_role:
                        user.roles.remove(r)
                        user.roles.add(fallback_role)
                except Role.DoesNotExist:
                    return JsonResponse({'success': False, 'error': 'Fallback role not found in this tenant'}, status=400)
                    
            r.delete()
            return JsonResponse({'success': True})
        except Role.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Role not found in this tenant'}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)


    roles = Role.objects.filter(tenant_id=tenant_id)
    is_super = request.user.is_superuser or request.user.roles.filter(name='SUPER_ADMIN').exists()
    if not is_super:
        roles = roles.exclude(name='SUPER_ADMIN')
    
    roles = roles.order_by('-is_system', 'name')
    permissions = Permission.objects.exclude(id='system:admin').order_by('name')
    return render(request, 'roles.html', {'roles': roles, 'permissions': permissions})

@login_required(login_url='portal_login')
@permission_required(('asset_category:read', 'asset:read'))
def portal_asset_categories(request):
    from assets.models import AssetCategory
    import json
    from django.http import JsonResponse, HttpResponseForbidden
    from users.permissions import HasPermission
    
    tenant_id = request.user.tenant_id
    
    if request.method == 'POST':
        if not HasPermission('asset_category:create')().has_permission(request, None):
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        try:
            data = json.loads(request.body)
            name = data.get('name')
            
            if AssetCategory.objects.filter(tenant_id=tenant_id, name=name).exists():
                return JsonResponse({'success': False, 'error': 'Category name already exists in this tenant'}, status=400)
                
            c = AssetCategory.objects.create(
                tenant_id=tenant_id,
                name=name,
                description=data.get('description'),
                is_active=data.get('is_active', True)
            )
            return JsonResponse({'success': True, 'id': str(c.id)})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
            
    elif request.method == 'PUT':
        if not HasPermission('asset_category:update')().has_permission(request, None):
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        try:
            data = json.loads(request.body)
            c = AssetCategory.objects.get(id=data.get('id'), tenant_id=tenant_id)
            new_name = data.get('name')
            
            if new_name != c.name and AssetCategory.objects.filter(tenant_id=tenant_id, name=new_name).exists():
                return JsonResponse({'success': False, 'error': 'Category name already exists in this tenant'}, status=400)
                
            c.name = new_name
            c.description = data.get('description')
            c.is_active = data.get('is_active', True)
            c.save()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
            
    elif request.method == 'DELETE':
        if not HasPermission('asset_category:delete')().has_permission(request, None):
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        try:
            data = json.loads(request.body)
            c = AssetCategory.objects.get(id=data.get('id'), tenant_id=tenant_id)
            c.is_active = False
            c.save()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)


    categories = AssetCategory.objects.filter(tenant_id=tenant_id)
    from assets.models import HierarchyTemplate, Location
    templates = HierarchyTemplate.objects.filter(tenant_id=tenant_id)
    locations = Location.objects.filter(tenant_id=tenant_id)
    
    # Process locations for template hierarchy
    loc_list = []
    for loc in locations:
        loc_list.append({
            'id': str(loc.id),
            'name': loc.name,
            'description': loc.description or '',
            'parent_id': loc.parent_id or '',
            'is_active': loc.is_active
        })

    return render(request, 'asset_categories.html', {
        'categories': categories,
        'templates': templates,
        'locations': loc_list,
    })

@login_required(login_url='portal_login')
@permission_required(('asset_category:read', 'asset:read'))
def portal_hierarchy_templates(request):
    from assets.models import HierarchyTemplate, AssetCategory
    import json
    from django.http import JsonResponse
    from users.permissions import HasPermission
    
    tenant_id = request.user.tenant_id
    

    if request.method == 'POST':
        if not HasPermission('asset_category:create')().has_permission(request, None):
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        try:
            data = json.loads(request.body)
            name = data.get('name')
            if HierarchyTemplate.objects.filter(tenant_id=tenant_id, name=name).exists():
                return JsonResponse({'success': False, 'error': 'Hierarchy template name already exists in this tenant'}, status=400)
            
            t = HierarchyTemplate.objects.create(
                tenant_id=tenant_id,
                name=name,
                description=data.get('description'),
                path=data.get('path', '/'),
                is_active=data.get('is_active', True)
            )
            return JsonResponse({'success': True, 'id': str(t.id)})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
            
    elif request.method == 'PUT':
        if not HasPermission('asset_category:update')().has_permission(request, None):
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        try:
            data = json.loads(request.body)
            t = HierarchyTemplate.objects.get(id=data.get('id'), tenant_id=tenant_id)
            name = data.get('name')
            if name != t.name and HierarchyTemplate.objects.filter(tenant_id=tenant_id, name=name).exists():
                return JsonResponse({'success': False, 'error': 'Hierarchy template name already exists in this tenant'}, status=400)
                
            t.name = name
            if 'description' in data:
                t.description = data.get('description')
            if 'path' in data:
                t.path = data.get('path', '/')
            if 'is_active' in data:
                t.is_active = data.get('is_active')
            t.save()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
            
    elif request.method == 'DELETE':
        if not HasPermission('asset_category:delete')().has_permission(request, None):
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        try:
            data = json.loads(request.body)
            t = HierarchyTemplate.objects.get(id=data.get('id'), tenant_id=tenant_id)
            t.is_active = False
            t.save()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    templates = HierarchyTemplate.objects.filter(tenant_id=tenant_id)
    category_count = AssetCategory.objects.filter(tenant_id=tenant_id).count()
    return render(request, 'hierarchy_templates.html', {
        'templates': templates,
        'category_count': category_count
    })

@login_required(login_url='portal_login')
@permission_required(('asset_category:read', 'asset:read'))
def portal_locations(request):
    from assets.models import Location
    import json
    from django.http import JsonResponse, HttpResponseForbidden
    from users.permissions import HasPermission
    
    tenant_id = request.user.tenant_id
    

    if request.method == 'POST':
        if not HasPermission('asset_category:create')().has_permission(request, None):
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        try:
            data = json.loads(request.body)
            name = data.get('name')
            parent_id = data.get('parentId')
            
            if Location.objects.filter(tenant_id=tenant_id, name=name, parent_id=parent_id).exists():
                return JsonResponse({'success': False, 'error': 'Location name already exists under this parent'}, status=400)
            
            l = Location.objects.create(
                tenant_id=tenant_id,
                name=name,
                description=data.get('description'),
                parent_id=parent_id,
                is_active=data.get('is_active', True)
            )
            return JsonResponse({'success': True, 'id': str(l.id)})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
            
    elif request.method == 'PUT':
        if not HasPermission('asset_category:update')().has_permission(request, None):
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        try:
            data = json.loads(request.body)
            l = Location.objects.get(id=data.get('id'), tenant_id=tenant_id)
            name = data.get('name')
            parent_id = data.get('parentId')
            
            if (name != l.name or parent_id != l.parent_id) and Location.objects.filter(tenant_id=tenant_id, name=name, parent_id=parent_id).exists():
                return JsonResponse({'success': False, 'error': 'Location name already exists under this parent'}, status=400)
                
            l.name = name
            if 'description' in data:
                l.description = data.get('description')
            if 'parentId' in data:
                l.parent_id = parent_id
            if 'is_active' in data:
                l.is_active = data.get('is_active')
            l.save()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
            
    elif request.method == 'DELETE':
        if not HasPermission('asset_category:delete')().has_permission(request, None):
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        try:
            data = json.loads(request.body)
            l = Location.objects.get(id=data.get('id'), tenant_id=tenant_id)
            l.is_active = False
            l.save()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    locations = Location.objects.filter(tenant_id=tenant_id)
    return JsonResponse({'success': True, 'data': [{'id': str(loc.id), 'name': loc.name, 'description': loc.description, 'parentId': loc.parent_id, 'isActive': loc.is_active} for loc in locations]})

@login_required(login_url='portal_login')
@permission_required('asset:read')
def portal_asset_registry(request):
    from assets.models import Asset, AssetCategory, Location, HierarchyTemplate
    import json
    import uuid
    from django.http import JsonResponse, HttpResponseForbidden
    from users.permissions import HasPermission
    
    tenant_id = request.user.tenant_id
    
    if request.method == 'POST':
        if not HasPermission('asset:create')().has_permission(request, None):
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        try:
            data = json.loads(request.body)
            category_id = data.get('category_id')
            a = Asset.objects.create(
                tenant_id=tenant_id,
                name=data.get('name'),
                model=data.get('model'),
                serial_number=data.get('serial_number'),
                qr_code=data.get('qr_code') or ("AST-" + str(uuid.uuid4())[:8].upper()),
                status=data.get('status', 'OPERATIONAL'),
                category_id=category_id if category_id else None
            )
            return JsonResponse({'success': True, 'id': str(a.id)})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
            
    elif request.method == 'PUT':
        if not HasPermission('asset:update')().has_permission(request, None):
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        try:
            data = json.loads(request.body)
            a = Asset.objects.get(id=data.get('id'), tenant_id=tenant_id, is_active=True)
            
            if 'name' in data: a.name = data.get('name')
            if 'model' in data: a.model = data.get('model')
            if 'serial_number' in data: a.serial_number = data.get('serial_number')
            if data.get('qr_code'): a.qr_code = data.get('qr_code')
            if 'status' in data: a.status = data.get('status')
            
            if 'category_id' in data:
                category_id = data.get('category_id')
                a.category_id = category_id if category_id else None
            
            if 'location_id' in data:
                location_id = data.get('location_id')
                a.location_id = location_id if location_id else None
                
            a.save()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
            
    elif request.method == 'DELETE':
        if not HasPermission('asset:delete')().has_permission(request, None):
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        try:
            data = json.loads(request.body)
            a = Asset.objects.get(id=data.get('id'), tenant_id=tenant_id, is_active=True)
            a.is_active = False # Soft delete to match DRF API
            a.save()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)


    assets = Asset.objects.filter(tenant_id=tenant_id, is_active=True).select_related('category', 'location', 'hierarchy_template')
    categories = AssetCategory.objects.filter(tenant_id=tenant_id)
    locations_list = list(Location.objects.filter(tenant_id=tenant_id, is_active=True))
    
    import unicodedata
    import re
    def format_to_ltree(input_str):
        if not input_str: return ""
        normalized = unicodedata.normalize('NFD', input_str)
        no_diacritics = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
        ltree = re.sub(r'[^a-zA-Z0-9\.]', '_', no_diacritics)
        ltree = re.sub(r'_+', '_', ltree)
        ltree = re.sub(r'\.+', '.', ltree)
        ltree = re.sub(r'^[\._]+|[\._]+$', '', ltree)
        return ltree

    # Build Tree Data
    def build_location_tree(parent_path=None):
        nodes = []
        for loc in locations_list:
            if loc.parent_id == parent_path or (parent_path is None and not loc.parent_id):
                loc_assets = [a for a in assets if str(a.location_id) == str(loc.id)]
                loc_path = f"{loc.parent_id}.{format_to_ltree(loc.name)}" if loc.parent_id else format_to_ltree(loc.name)
                nodes.append({
                    'id': str(loc.id),
                    'name': loc.name,
                    'is_active': loc.is_active,
                    'assets': loc_assets,
                    'children': build_location_tree(loc_path)
                })
        return nodes
        
    tree_locations = build_location_tree(None)
    unassigned_assets = [a for a in assets if not a.location_id]
    
    context = {
        'assets': assets,
        'categories': categories,
        'tree_locations': tree_locations,
        'unassigned_assets': unassigned_assets,
        'locations': locations_list,
        'templates': HierarchyTemplate.objects.filter(tenant_id=tenant_id, is_active=True)
    }
    return render(request, 'asset_registry.html', context)

@login_required(login_url='portal_login')
@permission_required('work_order:read')
def portal_work_orders(request):
    from workorders.models import WorkOrder, WorkOrderChecklistItem
    from assets.models import Asset
    from users.models import User
    import json
    from django.http import JsonResponse
    from django.utils.dateparse import parse_datetime
    
    tenant_id = request.user.tenant_id
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            action = data.get('action')
            
            if action == 'toggle_checklist':
                if not check_perm(request, ('work_order:execute', 'work_order:update')):
                    return JsonResponse({'success': False, 'error': 'Permission denied: work_order:execute required'}, status=403)
                item = WorkOrderChecklistItem.objects.get(id=data.get('item_id'), tenant_id=tenant_id)
                item.is_completed = data.get('is_completed')
                if 'actual_value' in data:
                    item.actual_value = data.get('actual_value')
                item.save()
                return JsonResponse({'success': True})
                
            elif action == 'add_checklist':
                if not check_perm(request, 'work_order:update'):
                    return JsonResponse({'success': False, 'error': 'Permission denied: work_order:update required'}, status=403)
                wo = WorkOrder.objects.get(id=data.get('work_order_id'), tenant_id=tenant_id)
                item = WorkOrderChecklistItem.objects.create(
                    tenant_id=tenant_id,
                    work_order=wo,
                    item_name=data.get('item_name')
                )
                return JsonResponse({'success': True, 'id': str(item.id)})
                
            else:
                if not check_perm(request, 'work_order:create'):
                    return JsonResponse({'success': False, 'error': 'Permission denied: work_order:create required'}, status=403)
                asset_id = data.get('asset_id')
                assigned_to_id = data.get('assigned_to_id')
                
                wo = WorkOrder.objects.create(
                    tenant_id=tenant_id,
                    title=data.get('title'),
                    description=data.get('description'),
                    priority=data.get('priority', 'MEDIUM'),
                    status=data.get('status', 'CREATED'),
                    asset_id=asset_id if asset_id else None,
                    assigned_to_id=assigned_to_id if assigned_to_id else None,
                    deadline=parse_datetime(data.get('deadline')) if data.get('deadline') else None,
                    created_by=request.user
                )
                return JsonResponse({'success': True, 'id': str(wo.id)})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
            
    elif request.method == 'PUT':
        try:
            data = json.loads(request.body)
            wo = WorkOrder.objects.get(id=data.get('id'), tenant_id=tenant_id)
            from django.utils import timezone
            
            # 1. Update Status Action
            if 'status' in data and (len(data) == 2 or ('resolution_notes' in data and len(data) <= 4)):
                if not check_perm(request, ('work_order:execute', 'work_order:update')):
                    return JsonResponse({'success': False, 'error': 'Permission denied: work_order:execute required'}, status=403)
                new_status = data.get('status')
                current_status = wo.status
                if data.get('resolution_notes'):
                    wo.resolution_notes = data.get('resolution_notes')
                
                if current_status != new_status:
                    if new_status == 'ASSIGNED':
                        raise Exception("Cannot manually change status to ASSIGNED")
                    elif new_status == 'IN_PROGRESS':
                        if current_status != 'ASSIGNED':
                            raise Exception("Work Order can only be started from ASSIGNED state")
                        if str(wo.assigned_to_id) != str(request.user.id):
                            raise Exception("Only the assignee can start the Work Order")
                        wo.actual_start_time = timezone.now()
                    elif new_status == 'COMPLETED':
                        if current_status != 'IN_PROGRESS':
                            raise Exception("Work Order can only be completed from IN_PROGRESS state")
                        if str(wo.assigned_to_id) != str(request.user.id):
                            raise Exception("Only the assignee can complete the Work Order")
                            
                        has_notes = wo.resolution_notes and wo.resolution_notes.strip()
                        has_attachments = wo.attachments.exists()
                        if not has_notes and not has_attachments:
                            raise Exception("Vui lòng nhập ghi chú sửa chữa hoặc tải lên ít nhất một hình ảnh minh chứng trước khi hoàn thành công việc.")
                            
                        for item in wo.checklists.all():
                            if item.is_mandatory and not item.is_completed:
                                raise Exception(f"Không thể hoàn thành: Chưa hoàn thành bước bắt buộc '{item.item_name}'")
                                
                        wo.completed_at = timezone.now()
                    elif new_status in ['CANCELED', 'CANCELLED']:
                        if current_status == 'COMPLETED':
                            raise Exception("Cannot cancel a COMPLETED Work Order")
                            
                    wo.status = new_status
                    wo.save()
                return JsonResponse({'success': True})
                
            # 2. Assign Action
            elif len(data) == 2 and 'assigned_to_id' in data:
                if not check_perm(request, ('work_order:reassign', 'work_order:update')):
                    return JsonResponse({'success': False, 'error': 'Permission denied: work_order:reassign required'}, status=403)
                if wo.status in ['COMPLETED', 'CANCELED', 'CANCELLED']:
                    raise Exception("Cannot reassign a completed or canceled work order")
                    
                new_assignee_id = data.get('assigned_to_id')
                if str(wo.assigned_to_id) != str(new_assignee_id):
                    wo.assigned_to_id = new_assignee_id if new_assignee_id else None
                    if new_assignee_id:
                        wo.assigned_at = timezone.now()
                        if wo.status == 'IN_PROGRESS':
                            wo.status = 'ASSIGNED'
                            wo.actual_start_time = None
                        elif wo.status == 'CREATED':
                            wo.status = 'ASSIGNED'
                    wo.save()
                return JsonResponse({'success': True})
                
            # 3. Full Update Action
            else:
                if not check_perm(request, 'work_order:update'):
                    return JsonResponse({'success': False, 'error': 'Permission denied: work_order:update required'}, status=403)
                asset_id = data.get('asset_id')
                assigned_to_id = data.get('assigned_to_id')
                
                wo.title = data.get('title')
                wo.description = data.get('description')
                wo.priority = data.get('priority')
                wo.status = data.get('status')
                wo.asset_id = asset_id if asset_id else None
                wo.assigned_to_id = assigned_to_id if assigned_to_id else None
                
                if data.get('deadline'):
                    wo.deadline = parse_datetime(data.get('deadline'))
                else:
                    wo.deadline = None
                    
                wo.save()
                return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
            
    elif request.method == 'DELETE':
        try:
            data = json.loads(request.body)
            action = data.get('action')
            if action == 'delete_checklist':
                if not check_perm(request, 'work_order:update'):
                    return JsonResponse({'success': False, 'error': 'Permission denied: work_order:update required'}, status=403)
                item = WorkOrderChecklistItem.objects.get(id=data.get('item_id'), tenant_id=tenant_id)
                item.delete()
            else:
                if not check_perm(request, 'work_order:delete'):
                    return JsonResponse({'success': False, 'error': 'Permission denied: work_order:delete required'}, status=403)
                wo = WorkOrder.objects.get(id=data.get('id'), tenant_id=tenant_id)
                wo.delete()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    from django.utils import timezone
    now = timezone.now()

    work_orders = WorkOrder.objects.filter(tenant_id=tenant_id).select_related('asset', 'assigned_to', 'parent_id', 'created_by').prefetch_related('checklists', 'follow_up_work_orders')
    
    total_wos = work_orders.count()
    in_progress = sum(1 for wo in work_orders if wo.status == 'IN_PROGRESS')
    overdue = sum(1 for wo in work_orders if wo.deadline and wo.deadline < now and wo.status not in ['COMPLETED', 'CANCELED'])
    completed = sum(1 for wo in work_orders if wo.status == 'COMPLETED')

    wo_data = []
    for wo in work_orders:
        checklists = list(wo.checklists.all().values('id', 'item_name', 'is_completed', 'input_type', 'expected_value', 'actual_value', 'is_mandatory'))
        # Need to cast UUIDs to strings
        for c in checklists:
            c['id'] = str(c['id'])
        
        follow_ups = list(wo.follow_up_work_orders.all().values('id'))
        
        wo_data.append({
            'wo': wo,
            'checklists_json': json.dumps(checklists),
            'follow_ups_count': len(follow_ups)
        })

    assets = Asset.objects.filter(tenant_id=tenant_id)
    users = User.objects.all() # Assuming cross-tenant or specific users
    
    kpis = {
        'total': total_wos,
        'in_progress': in_progress,
        'overdue': overdue,
        'completed': completed
    }
    
    return render(request, 'work_orders.html', {'work_orders_data': wo_data, 'assets': assets, 'users': users, 'kpis': kpis})

@login_required(login_url='portal_login')
@permission_required('inventory:read')
def portal_inventory(request):
    from assets.models import SparePart
    import json
    from django.http import JsonResponse, HttpResponseForbidden
    
    tenant_id = request.user.tenant_id
    is_admin = request.user.is_superuser or request.user.roles.filter(permissions__id='system:admin').exists()
    
            
    if request.method == 'POST':
        if not (is_admin or request.user.roles.filter(permissions__id='inventory:create').exists()):
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        try:
            data = json.loads(request.body)
            qty = data.get('quantity_in_stock')
            
            sp = SparePart.objects.create(
                tenant_id=tenant_id,
                name=data.get('name'),
                part_number=data.get('part_number'),
                description=data.get('description'),
                quantity_in_stock=qty if qty is not None else 0,
                unit_cost=data.get('unit_cost') or None
            )
            return JsonResponse({'success': True, 'id': str(sp.id)})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
            
    elif request.method == 'PUT':
        if not (is_admin or request.user.roles.filter(permissions__id='inventory:update').exists()):
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        try:
            data = json.loads(request.body)
            sp = SparePart.objects.get(id=data.get('id'), tenant_id=tenant_id)
            sp.name = data.get('name')
            sp.part_number = data.get('part_number')
            sp.description = data.get('description')
            
            if data.get('quantity_in_stock') is not None:
                sp.quantity_in_stock = data['quantity_in_stock']
                
            sp.unit_cost = data.get('unit_cost') or None
            sp.save()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
            
    elif request.method == 'DELETE':
        if not (is_admin or request.user.roles.filter(permissions__id='inventory:delete').exists()):
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        try:
            data = json.loads(request.body)
            sp = SparePart.objects.get(id=data.get('id'), tenant_id=tenant_id)
            sp.delete()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    spare_parts = SparePart.objects.filter(tenant_id=tenant_id)
    return render(request, 'inventory.html', {'spare_parts': spare_parts})

@login_required(login_url='portal_login')
@permission_required('pm_plan:read')
def portal_pm_plans(request):
    from maintenance.models import PmPlan
    import json
    from django.http import JsonResponse
    from django.db import transaction
    
    tenant_id = request.user.tenant_id
    
    if request.method == 'POST':
        if not check_perm(request, 'pm_plan:create'):
            return JsonResponse({'success': False, 'error': 'Permission denied: pm_plan:create required'}, status=403)
        try:
            data = json.loads(request.body)
            with transaction.atomic():
                pm = PmPlan.objects.create(
                    tenant_id=tenant_id,
                    name=data.get('name'),
                    description=data.get('description'),
                    trigger_type=data.get('trigger_type', 'TIME'),
                    interval_value=data.get('interval_value') or None,
                    interval_unit=data.get('interval_unit') or None,
                    is_active=data.get('is_active', True),
                    is_floating_schedule=data.get('is_floating_schedule', False),
                    suppress_if_pending=data.get('suppress_if_pending', True),
                    lead_time_days=data.get('lead_time_days', 0),
                    estimated_duration_minutes=data.get('estimated_duration_minutes') or None,
                    assignee_id=data.get('assignee_id') or None
                )
                
                from maintenance.models import PmPlanChecklistItem, PmPlanMaterial
                from assets.models import SparePart
                
                if 'checklists' in data:
                    for pc in data['checklists']:
                        PmPlanChecklistItem.objects.create(
                            pm_plan=pm,
                            item_name=pc.get('item_name'),
                            input_type=pc.get('input_type', 'PASS_FAIL'),
                            expected_value=pc.get('expected_value') or None,
                            is_mandatory=pc.get('is_mandatory', False)
                        )
                
                if 'materials' in data:
                    for pm_mat in data['materials']:
                        sp = SparePart.objects.get(id=pm_mat.get('spare_part_id'), tenant_id=tenant_id)
                        PmPlanMaterial.objects.create(
                            pm_plan=pm,
                            spare_part=sp,
                            quantity=pm_mat.get('quantity')
                        )
                
            return JsonResponse({'success': True, 'id': str(pm.id)})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
            
    elif request.method == 'PUT':
        if not check_perm(request, 'pm_plan:update'):
            return JsonResponse({'success': False, 'error': 'Permission denied: pm_plan:update required'}, status=403)
        try:
            data = json.loads(request.body)
            with transaction.atomic():
                pm = PmPlan.objects.get(id=data.get('id'), tenant_id=tenant_id)
                pm.name = data.get('name')
                pm.description = data.get('description')
                pm.trigger_type = data.get('trigger_type')
                pm.interval_value = data.get('interval_value') or None
                pm.interval_unit = data.get('interval_unit') or None
                pm.is_active = data.get('is_active', True)
                pm.is_floating_schedule = data.get('is_floating_schedule', False)
                pm.suppress_if_pending = data.get('suppress_if_pending', True)
                pm.lead_time_days = data.get('lead_time_days', 0)
                pm.estimated_duration_minutes = data.get('estimated_duration_minutes') or None
                pm.assignee_id = data.get('assignee_id') or None
                pm.save()
                
                from maintenance.models import PmPlanChecklistItem, PmPlanMaterial
                from assets.models import SparePart
                
                if 'checklists' in data:
                    pm.checklists.all().delete()
                    for pc in data['checklists']:
                        PmPlanChecklistItem.objects.create(
                            pm_plan=pm,
                            item_name=pc.get('item_name'),
                            input_type=pc.get('input_type', 'PASS_FAIL'),
                            expected_value=pc.get('expected_value') or None,
                            is_mandatory=pc.get('is_mandatory', False)
                        )
                
                if 'materials' in data:
                    pm.materials.all().delete()
                    for pm_mat in data['materials']:
                        sp = SparePart.objects.get(id=pm_mat.get('spare_part_id'), tenant_id=tenant_id)
                        PmPlanMaterial.objects.create(
                            pm_plan=pm,
                            spare_part=sp,
                            quantity=pm_mat.get('quantity')
                        )

            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
            
    elif request.method == 'DELETE':
        if not check_perm(request, 'pm_plan:delete'):
            return JsonResponse({'success': False, 'error': 'Permission denied: pm_plan:delete required'}, status=403)
        try:
            data = json.loads(request.body)
            pm = PmPlan.objects.get(id=data.get('id'), tenant_id=tenant_id)
            pm.delete()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    pm_plans = PmPlan.objects.filter(tenant_id=tenant_id)
    
    # Calculate KPIs
    from workorders.models import WorkOrder
    from django.utils import timezone
    total_plans = pm_plans.count()
    missed_pms = WorkOrder.objects.filter(
        tenant_id=tenant_id,
        source_reference__startswith="PM_",
        deadline__lt=timezone.now()
    ).exclude(status__in=['COMPLETED', 'CANCELLED']).count()
    
    total_pm_wos = WorkOrder.objects.filter(tenant_id=tenant_id, source_reference__startswith="PM_").count()
    completed_pm_wos = WorkOrder.objects.filter(tenant_id=tenant_id, source_reference__startswith="PM_", status='COMPLETED').count()
    
    compliance_rate = 100.0
    if total_pm_wos > 0:
        compliance_rate = (completed_pm_wos / total_pm_wos) * 100.0

    upcoming_pms_count = 0
    from maintenance.models import PmPlanAssignment
    from datetime import timedelta
    next_week = timezone.now() + timedelta(days=7)
    upcoming_pms_count = PmPlanAssignment.objects.filter(
        tenant_id=tenant_id,
        status='ACTIVE',
        next_due_date__lte=next_week,
        next_due_date__gte=timezone.now()
    ).count()

    kpis = {
        'totalPlans': total_plans,
        'upcomingIn7Days': upcoming_pms_count,
        'missedPms': missed_pms,
        'complianceRate': round(compliance_rate, 1)
    }

    pm_plans_data = []
    for pm in pm_plans:
        pm_plans_data.append({
            'pm': pm,
            'checklists_json': json.dumps([
                {
                    'id': str(c.id),
                    'item_name': c.item_name,
                    'input_type': c.input_type,
                    'expected_value': c.expected_value,
                    'is_mandatory': c.is_mandatory
                } for c in pm.checklists.all()
            ]),
            'materials_json': json.dumps([
                {
                    'id': str(m.id),
                    'spare_part_id': str(m.spare_part_id),
                    'quantity': float(m.quantity)
                } for m in pm.materials.all()
            ])
        })

    from assets.models import Asset, SparePart
    from users.models import User
    assets = Asset.objects.filter(tenant_id=tenant_id, is_active=True)
    users = User.objects.filter(tenant_id=tenant_id, status='ACTIVE')
    spare_parts = SparePart.objects.filter(tenant_id=tenant_id)

    return render(request, 'pm_plans.html', {
        'pm_plans_data': pm_plans_data,
        'kpis': kpis,
        'assets': assets,
        'users': users,
        'spare_parts': spare_parts,
    })

@login_required(login_url='portal_login')
@permission_required('pm_plan:read')
def portal_pm_plan_assignments(request, plan_id=None, assignment_id=None):
    from maintenance.models import PmPlanAssignment, PmPlan
    from assets.models import Asset
    import json
    from django.http import JsonResponse
    
    tenant_id = request.user.tenant_id
    
    if request.method == 'GET' and plan_id:
        assignments = PmPlanAssignment.objects.filter(pm_plan_id=plan_id, tenant_id=tenant_id).select_related('asset')
        data = []
        for a in assignments:
            data.append({
                'id': str(a.id),
                'assetId': str(a.asset_id),
                'assetName': a.asset.name,
                'status': a.status
            })
        return JsonResponse({'success': True, 'data': data})
        
    elif request.method == 'POST' and plan_id:
        if not check_perm(request, ('pm_plan:create', 'pm_plan:update')):
            return JsonResponse({'success': False, 'error': 'Permission denied: pm_plan:create required'}, status=403)
        try:
            data = json.loads(request.body)
            asset_ids = data.get('asset_ids', [])
            pm = PmPlan.objects.get(id=plan_id, tenant_id=tenant_id)
            for aid in asset_ids:
                asset = Asset.objects.get(id=aid, tenant_id=tenant_id)
                PmPlanAssignment.objects.get_or_create(
                    pm_plan=pm,
                    asset=asset,
                    tenant_id=tenant_id,
                    defaults={'status': 'ACTIVE'}
                )
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
            
    elif request.method == 'PATCH' and assignment_id:
        if not check_perm(request, 'pm_plan:update'):
            return JsonResponse({'success': False, 'error': 'Permission denied: pm_plan:update required'}, status=403)
        try:
            data = json.loads(request.body)
            assignment = PmPlanAssignment.objects.get(id=assignment_id, tenant_id=tenant_id)
            if 'status' in data:
                assignment.status = data['status']
                assignment.save()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
            
    elif request.method == 'DELETE' and assignment_id:
        if not check_perm(request, 'pm_plan:delete'):
            return JsonResponse({'success': False, 'error': 'Permission denied: pm_plan:delete required'}, status=403)
        try:
            assignment = PmPlanAssignment.objects.get(id=assignment_id, tenant_id=tenant_id)
            assignment.delete()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

@login_required(login_url='portal_login')
@permission_required('audit_logs:read')
def portal_audit_logs(request):
    from core.models import AuditLog
    logs = AuditLog.objects.all().order_by('-timestamp')[:500]
    
    creates = sum(1 for log in logs if log.action_type == 'CREATE')
    updates = sum(1 for log in logs if log.action_type == 'UPDATE')
    deletes = sum(1 for log in logs if log.action_type == 'DELETE')
    
    return render(request, 'audit_logs.html', {
        'logs': logs,
        'creates': creates,
        'updates': updates,
        'deletes': deletes
    })

@login_required(login_url='portal_login')
@permission_required('audit_logs:read')
def portal_reports(request):
    return render(request, 'reports.html')

def custom_403_view(request, exception=None):
    import re
    error_msg = str(exception) if exception else "Bạn không có quyền truy cập tài nguyên này."
    match = re.search(r'\((.*?)\s+required\)', error_msg)
    required_perm = match.group(1) if match else None

    perm_names = {
        'user:read': 'Xem danh sách người dùng (Read Users)',
        'user:create': 'Tạo người dùng mới (Create User)',
        'role:read': 'Xem danh sách vai trò (Read Roles)',
        'role:create': 'Tạo & phân quyền vai trò (Manage Roles)',
        'tenant:read': 'Cấu hình hệ thống Tenant (Tenant Settings)',
        'asset:read': 'Xem danh mục tài sản (Read Assets)',
        'work_order:read': 'Xem lệnh làm việc (Read Work Orders)',
        'work_order:execute': 'Thực thi lệnh làm việc (Execute Work Orders)',
        'pm_plan:read': 'Xem kế hoạch bảo trì PM (Read PM Plans)',
        'inventory:read': 'Xem kho & phụ tùng (Read Inventory)',
        'audit_logs:read': 'Xem nhật ký kiểm toán (Read Audit Logs)',
        'system:admin': 'Quản trị viên toàn hệ thống (Super Admin)',
        'asset_category:read': 'Cấu hình phân loại tài sản (Asset Config)',
    }

    context = {
        'error_message': error_msg,
        'required_perm': required_perm,
        'required_perm_title': perm_names.get(required_perm, required_perm),
        'requested_path': request.path,
    }
    return render(request, '403.html', context, status=403)








from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages

def portal_login(request):
    if request.user.is_authenticated:
        return redirect('portal_dashboard')
        
    if request.method == 'POST':
        u = request.POST.get('username')
        p = request.POST.get('password')
        user = authenticate(request, username=u, password=p)
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
def portal_tenants(request):
    from core.models import Tenant
    import json
    from django.http import JsonResponse, HttpResponseForbidden
    
    if not request.user.is_superuser and str(request.user.tenant_id) != '00000000-0000-0000-0000-000000000000':
        return HttpResponseForbidden("Only system admins can manage tenants")
    
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
def portal_settings(request):
    from core.models import Tenant
    import json
    from django.http import JsonResponse
    
    tenant = request.user.tenant
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            tenant.name = data.get('name', tenant.name)
            tenant.logo_url = data.get('logoUrl', tenant.logo_url)
            tenant.timezone = data.get('timezone', tenant.timezone)
            tenant.save()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
            
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
def portal_users(request):
    from users.models import User, Role
    import json
    from django.http import JsonResponse
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            username = data.get('username')
            if User.objects.filter(username=username).exists():
                return JsonResponse({'success': False, 'error': 'Username already exists'}, status=400)
                
            u = User.objects.create(
                username=username,
                email=data.get('email'),
                status=data.get('status', 'ACTIVE')
            )
            if data.get('password'):
                u.set_password(data.get('password'))
                u.save()
                
            role_ids = data.get('roles', [])
            if role_ids:
                roles = Role.objects.filter(id__in=role_ids)
                u.roles.set(roles)
                
            return JsonResponse({'success': True, 'id': str(u.id)})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
            
    elif request.method == 'PUT':
        try:
            data = json.loads(request.body)
            u = User.objects.get(id=data.get('id'))
            
            new_username = data.get('username')
            if new_username != u.username and User.objects.filter(username=new_username).exists():
                return JsonResponse({'success': False, 'error': 'Username already exists'}, status=400)
                
            u.username = new_username
            u.email = data.get('email')
            u.status = data.get('status', 'ACTIVE')
            
            if data.get('password'):
                u.set_password(data.get('password'))
            u.save()
            
            role_ids = data.get('roles', [])
            roles = Role.objects.filter(id__in=role_ids)
            u.roles.set(roles)
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
            
    elif request.method == 'DELETE':
        try:
            data = json.loads(request.body)
            u = User.objects.get(id=data.get('id'))
            if u.id == request.user.id:
                return JsonResponse({'success': False, 'error': 'Cannot delete your own account'}, status=400)
            if u.is_superuser:
                return JsonResponse({'success': False, 'error': 'Cannot delete superuser'}, status=400)
            u.delete()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    users = User.objects.all().order_by('-created_at')
    roles = Role.objects.all()
    return render(request, 'users.html', {'users': users, 'roles': roles})

@login_required(login_url='portal_login')
def portal_roles(request):
    from users.models import Role, Permission
    import json
    from django.http import JsonResponse
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            name = data.get('name')
            
            if Role.objects.filter(name=name).exists():
                return JsonResponse({'success': False, 'error': 'Role name already exists'}, status=400)
                
            r = Role.objects.create(
                name=name,
                description=data.get('description'),
                is_system=False
            )
            
            perm_ids = data.get('permissions', [])
            if perm_ids:
                perms = Permission.objects.filter(id__in=perm_ids)
                r.permissions.set(perms)
                
            return JsonResponse({'success': True, 'id': str(r.id)})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
            
    elif request.method == 'PUT':
        try:
            data = json.loads(request.body)
            r = Role.objects.get(id=data.get('id'))
            
            if r.is_system:
                return JsonResponse({'success': False, 'error': 'Cannot edit system roles'}, status=400)
                
            new_name = data.get('name')
            if new_name != r.name and Role.objects.filter(name=new_name).exists():
                return JsonResponse({'success': False, 'error': 'Role name already exists'}, status=400)
                
            r.name = new_name
            r.description = data.get('description')
            r.save()
            
            perm_ids = data.get('permissions', [])
            perms = Permission.objects.filter(id__in=perm_ids)
            r.permissions.set(perms)
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
            
    elif request.method == 'DELETE':
        try:
            from users.models import User
            data = json.loads(request.body)
            r = Role.objects.get(id=data.get('id'))
            if r.is_system:
                return JsonResponse({'success': False, 'error': 'Cannot delete system roles'}, status=400)
                
            fallback_role_id = data.get('fallbackRoleId')
            users_with_role = User.objects.filter(roles=r)
            
            if users_with_role.exists():
                if not fallback_role_id:
                    return JsonResponse({'success': False, 'error': 'ROLE_HAS_USERS'}, status=400)
                
                try:
                    fallback_role = Role.objects.get(id=fallback_role_id)
                    for user in users_with_role:
                        user.roles.remove(r)
                        user.roles.add(fallback_role)
                except Role.DoesNotExist:
                    return JsonResponse({'success': False, 'error': 'Fallback role not found'}, status=400)
                    
            r.delete()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    roles = Role.objects.all().order_by('-is_system', 'name')
    permissions = Permission.objects.all()
    return render(request, 'roles.html', {'roles': roles, 'permissions': permissions})

@login_required(login_url='portal_login')
def portal_asset_categories(request):
    from assets.models import AssetCategory
    import json
    from django.http import JsonResponse
    
    tenant_id = request.user.tenant_id
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            c = AssetCategory.objects.create(
                tenant_id=tenant_id,
                name=data.get('name'),
                description=data.get('description'),
                is_active=data.get('is_active', True)
            )
            return JsonResponse({'success': True, 'id': str(c.id)})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
            
    elif request.method == 'PUT':
        try:
            data = json.loads(request.body)
            c = AssetCategory.objects.get(id=data.get('id'), tenant_id=tenant_id)
            c.name = data.get('name')
            c.description = data.get('description')
            c.is_active = data.get('is_active', True)
            c.save()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
            
    elif request.method == 'DELETE':
        try:
            data = json.loads(request.body)
            c = AssetCategory.objects.get(id=data.get('id'), tenant_id=tenant_id)
            c.delete()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    categories = AssetCategory.objects.filter(tenant_id=tenant_id)
    return render(request, 'asset_categories.html', {'categories': categories})

@login_required(login_url='portal_login')
def portal_hierarchy_templates(request):
    from assets.models import HierarchyTemplate
    import json
    from django.http import JsonResponse
    
    tenant_id = request.user.tenant_id
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            t = HierarchyTemplate.objects.create(
                tenant_id=tenant_id,
                name=data.get('name'),
                description=data.get('description'),
                path=data.get('path', '/')
            )
            return JsonResponse({'success': True, 'id': str(t.id)})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
            
    elif request.method == 'PUT':
        try:
            data = json.loads(request.body)
            t = HierarchyTemplate.objects.get(id=data.get('id'), tenant_id=tenant_id)
            t.name = data.get('name')
            t.description = data.get('description')
            t.path = data.get('path', '/')
            t.save()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
            
    elif request.method == 'DELETE':
        try:
            data = json.loads(request.body)
            t = HierarchyTemplate.objects.get(id=data.get('id'), tenant_id=tenant_id)
            t.delete()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    templates = HierarchyTemplate.objects.filter(tenant_id=tenant_id)
    return render(request, 'hierarchy_templates.html', {'templates': templates})

@login_required(login_url='portal_login')
def portal_asset_registry(request):
    from assets.models import Asset, AssetCategory, Location
    import json
    import uuid
    from django.http import JsonResponse
    
    tenant_id = request.user.tenant_id
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            category_id = data.get('category_id')
            a = Asset.objects.create(
                tenant_id=tenant_id,
                name=data.get('name'),
                model=data.get('model'),
                serial_number=data.get('serial_number'),
                qr_code=data.get('qr_code') or str(uuid.uuid4())[:8].upper(),
                status=data.get('status', 'OPERATIONAL'),
                category_id=category_id if category_id else None
            )
            return JsonResponse({'success': True, 'id': str(a.id)})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
            
    elif request.method == 'PUT':
        try:
            data = json.loads(request.body)
            a = Asset.objects.get(id=data.get('id'), tenant_id=tenant_id)
            a.name = data.get('name')
            a.model = data.get('model')
            a.serial_number = data.get('serial_number')
            if data.get('qr_code'):
                a.qr_code = data.get('qr_code')
            a.status = data.get('status', 'OPERATIONAL')
            
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
        try:
            data = json.loads(request.body)
            a = Asset.objects.get(id=data.get('id'), tenant_id=tenant_id)
            a.delete()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    assets = Asset.objects.filter(tenant_id=tenant_id).select_related('category', 'location', 'hierarchy_template')
    categories = AssetCategory.objects.filter(tenant_id=tenant_id)
    locations_list = list(Location.objects.filter(tenant_id=tenant_id, is_active=True))
    
    # Build Tree Data
    def build_location_tree(parent_id=None):
        nodes = []
        for loc in locations_list:
            if loc.parent_id == parent_id or (parent_id is None and not loc.parent_id):
                loc_assets = [a for a in assets if str(a.location_id) == str(loc.id)]
                loc_path = f"{loc.parent_id}.{loc.name}" if loc.parent_id else loc.name # simplified
                nodes.append({
                    'id': str(loc.id),
                    'name': loc.name,
                    'is_active': loc.is_active,
                    'assets': loc_assets,
                    'children': build_location_tree(str(loc.id))
                })
        return nodes
        
    tree_locations = build_location_tree(None)
    unassigned_assets = [a for a in assets if not a.location_id]
    
    context = {
        'assets': assets,
        'categories': categories,
        'tree_locations': tree_locations,
        'unassigned_assets': unassigned_assets,
        'locations': locations_list
    }
    return render(request, 'asset_registry.html', context)

@login_required(login_url='portal_login')
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
                item = WorkOrderChecklistItem.objects.get(id=data.get('item_id'), tenant_id=tenant_id)
                item.is_completed = data.get('is_completed')
                item.save()
                return JsonResponse({'success': True})
                
            elif action == 'add_checklist':
                wo = WorkOrder.objects.get(id=data.get('work_order_id'), tenant_id=tenant_id)
                item = WorkOrderChecklistItem.objects.create(
                    tenant_id=tenant_id,
                    work_order=wo,
                    item_name=data.get('item_name')
                )
                return JsonResponse({'success': True, 'id': str(item.id)})
                
            else:
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
                    deadline=parse_datetime(data.get('deadline')) if data.get('deadline') else None
                )
                return JsonResponse({'success': True, 'id': str(wo.id)})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
            
    elif request.method == 'PUT':
        try:
            data = json.loads(request.body)
            wo = WorkOrder.objects.get(id=data.get('id'), tenant_id=tenant_id)
            
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
                item = WorkOrderChecklistItem.objects.get(id=data.get('item_id'), tenant_id=tenant_id)
                item.delete()
            else:
                wo = WorkOrder.objects.get(id=data.get('id'), tenant_id=tenant_id)
                wo.delete()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    from django.utils import timezone
    now = timezone.now()

    work_orders = WorkOrder.objects.filter(tenant_id=tenant_id).select_related('asset', 'assigned_to', 'parent_id').prefetch_related('checklists', 'follow_up_work_orders')
    
    total_wos = work_orders.count()
    in_progress = sum(1 for wo in work_orders if wo.status == 'IN_PROGRESS')
    overdue = sum(1 for wo in work_orders if wo.deadline and wo.deadline < now and wo.status not in ['COMPLETED', 'CANCELED'])
    completed = sum(1 for wo in work_orders if wo.status == 'COMPLETED')

    wo_data = []
    for wo in work_orders:
        checklists = list(wo.checklists.all().values('id', 'item_name', 'is_completed'))
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
def portal_inventory(request):
    from assets.models import SparePart
    import json
    from django.http import JsonResponse
    
    tenant_id = request.user.tenant_id
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            sp = SparePart.objects.create(
                tenant_id=tenant_id,
                name=data.get('name'),
                part_number=data.get('part_number'),
                description=data.get('description'),
                quantity_in_stock=data.get('quantity_in_stock', 0),
                unit_cost=data.get('unit_cost') or None
            )
            return JsonResponse({'success': True, 'id': str(sp.id)})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
            
    elif request.method == 'PUT':
        try:
            data = json.loads(request.body)
            sp = SparePart.objects.get(id=data.get('id'), tenant_id=tenant_id)
            sp.name = data.get('name')
            sp.part_number = data.get('part_number')
            sp.description = data.get('description')
            sp.quantity_in_stock = data.get('quantity_in_stock', 0)
            sp.unit_cost = data.get('unit_cost') or None
            sp.save()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
            
    elif request.method == 'DELETE':
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
def portal_pm_plans(request):
    from maintenance.models import PmPlan
    import json
    from django.http import JsonResponse
    
    tenant_id = request.user.tenant_id
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            pm = PmPlan.objects.create(
                tenant_id=tenant_id,
                name=data.get('name'),
                description=data.get('description'),
                trigger_type=data.get('trigger_type', 'TIME'),
                interval_value=data.get('interval_value') or None,
                interval_unit=data.get('interval_unit') or None,
                is_active=data.get('is_active', True)
            )
            return JsonResponse({'success': True, 'id': str(pm.id)})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
            
    elif request.method == 'PUT':
        try:
            data = json.loads(request.body)
            pm = PmPlan.objects.get(id=data.get('id'), tenant_id=tenant_id)
            pm.name = data.get('name')
            pm.description = data.get('description')
            pm.trigger_type = data.get('trigger_type')
            pm.interval_value = data.get('interval_value') or None
            pm.interval_unit = data.get('interval_unit') or None
            pm.is_active = data.get('is_active', True)
            pm.save()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
            
    elif request.method == 'DELETE':
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

    kpis = {
        'totalPlans': total_plans,
        'upcomingIn7Days': 0, # Since we'd need to project plans, hardcode or leave 0 for now as in the API
        'missedPms': missed_pms,
        'complianceRate': round(compliance_rate, 1)
    }

    return render(request, 'pm_plans.html', {'pm_plans': pm_plans, 'kpis': kpis})

@login_required(login_url='portal_login')
def portal_audit_logs(request):
    from core.models import AuditLog
    logs = AuditLog.objects.all().order_by('-timestamp')[:100]
    return render(request, 'audit_logs.html', {'logs': logs})







from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from users.decorators import permission_required
from django.contrib import messages
import json

def check_perm(request, perm):
    if not request.user or not request.user.is_authenticated:
        return False
    if request.user.is_superuser:
        return True
    if not hasattr(request, '_user_permissions_cache'):
        perms = set()
        roles = list(request.user.roles.prefetch_related('permissions').all())
        for role in roles:
            for p in role.permissions.all():
                perms.add(p.id)
        if any(r.name == 'TENANT_ADMIN' for r in roles) and len(perms) <= 2:
            from users.models import Permission
            tenant_perms = set(Permission.objects.exclude(id='system:admin').values_list('id', flat=True))
            perms.update(tenant_perms)
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
    from analytics.services import DashboardCacheService
    import json
    
    tenant = getattr(request.user, 'tenant', None)
    if tenant:
        summary_data = DashboardCacheService.get_summary(tenant)
        trends_data = DashboardCacheService.get_trends(tenant)
        activities = DashboardCacheService.get_activity_feed(tenant)
    else:
        summary_data = {
            "kpis": {
                "totalAssets": {"value": 0, "delta": "0", "deltaType": "neutral", "deltaLabel": "N/A", "label": "Thiết bị đang quản lý", "drillDownUrl": "/portal/assets/"},
                "activeWorkOrders": {"value": 0, "delta": "0", "deltaType": "neutral", "deltaLabel": "N/A", "label": "Phiếu đang xử lý", "drillDownUrl": "/portal/work-orders/"},
                "completedWorkOrders": {"value": 0, "delta": "0", "deltaType": "neutral", "deltaLabel": "N/A", "label": "Phiếu hoàn tất (30 ngày)", "drillDownUrl": "/portal/work-orders/"},
                "plantAvailability": {"value": "100.0%", "delta": "0", "deltaType": "neutral", "deltaLabel": "N/A", "label": "Độ sẵn sàng vận hành", "drillDownUrl": None},
                "pmComplianceRate": {"value": "100.0%", "delta": "0", "deltaType": "neutral", "deltaLabel": "N/A", "label": "Tuân thủ bảo trì định kỳ", "drillDownUrl": "/portal/work-orders/?type=PREVENTIVE"}
            },
            "assetHealth": {
                "totalActive": 0,
                "operating": {"count": 0, "percentage": 0.0},
                "maintenance": {"count": 0, "percentage": 0.0},
                "down": {"count": 0, "percentage": 0.0},
                "plantStatus": "NORMAL",
                "plantStatusLabel": "Bình thường"
            },
            "reliability": {
                "mtbfHours": None,
                "mtbfDisplay": "100% Khả dụng (0 Sự cố)",
                "isZeroFailure": True,
                "mttrHours": None,
                "mttrDisplay": "N/A",
                "ongoingDownCount": 0
            }
        }
        trends_data = {"timezone": "Asia/Ho_Chi_Minh", "series": []}
        activities = []

    kpis = summary_data.get("kpis", {})
    context = {
        'summary': summary_data,
        'kpis': kpis,
        'asset_health': summary_data.get("assetHealth", {}),
        'reliability': summary_data.get("reliability", {}),
        'trends': trends_data,
        'trends_json': json.dumps(trends_data.get("series", [])),
        'activities': activities,
        # Backward-compatible keys
        'total_assets': kpis.get("totalAssets", {}).get("value", 0),
        'operational_assets': summary_data.get("assetHealth", {}).get("operating", {}).get("count", 0),
        'active_work_orders': kpis.get("activeWorkOrders", {}).get("value", 0),
        'completed_work_orders': kpis.get("completedWorkOrders", {}).get("value", 0),
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
    import random
    import datetime
    from django.utils import timezone
    from django.http import JsonResponse
    from users.models import User
    from django.core.mail import send_mail
    from django.conf import settings
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            email = (data.get('email') or '').strip()
            user = User.all_objects.filter(email__iexact=email).first()
            if not user:
                return JsonResponse({'success': False, 'error': f"User with email '{email}' not found."}, status=404)
            
            # Generate random 6-digit code
            code = f"{random.randint(100000, 999999):06d}"
            user.reset_token = code
            user.reset_token_expiry = timezone.now() + datetime.timedelta(minutes=15)
            user.save(update_fields=['reset_token', 'reset_token_expiry'])
            
            # Attempt to send real email via SMTP
            send_mail(
                subject="[EAM System] Password Reset Code",
                message=(
                    f"Hello {user.username},\n\n"
                    f"You requested a password reset for your EAM account.\n"
                    f"Your 6-digit verification code is: {code}\n\n"
                    f"This code will expire in 15 minutes.\n"
                    f"If you did not request this, please ignore this email.\n\n"
                    f"Best regards,\nEAM Technical Team"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL or 'noreply@eam.local',
                recipient_list=[email],
                fail_silently=False,
            )
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': f"SMTP Error: {str(e)}"}, status=500)
    return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)

def portal_reset_password(request):
    import json
    from django.utils import timezone
    from django.http import JsonResponse
    from users.models import User
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            code = str(data.get('code') or '').strip()
            new_password = data.get('newPassword')
            
            if not code or len(code) != 6:
                return JsonResponse({'success': False, 'error': 'Please enter a valid 6-digit code.'}, status=400)
            if not new_password or len(new_password) < 6:
                return JsonResponse({'success': False, 'error': 'New password must be at least 6 characters long.'}, status=400)
                
            user = User.all_objects.filter(reset_token=code).first()
            if not user:
                return JsonResponse({'success': False, 'error': 'Invalid or incorrect reset code.'}, status=400)
                
            if user.reset_token_expiry and user.reset_token_expiry < timezone.now():
                return JsonResponse({'success': False, 'error': 'Reset code has expired (15 minutes). Please request a new one.'}, status=400)
                
            user.set_password(new_password)
            user.reset_token = None
            user.reset_token_expiry = None
            user.save(update_fields=['password', 'reset_token', 'reset_token_expiry'])
            
            return JsonResponse({'success': True})
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
            roles = []
            if role_ids:
                roles = list(Role.objects.filter(id__in=role_ids, tenant_id=tenant_id).prefetch_related('permissions'))
                for r in roles:
                    is_super = request.user.is_superuser or request.user.roles.filter(name='SUPER_ADMIN').exists()
                    if r.name == 'SUPER_ADMIN' and not is_super:
                        return JsonResponse({'success': False, 'error': 'You do not have permission to assign the SUPER_ADMIN role'}, status=403)
                u.roles.set(roles)
            else:
                u.roles.clear()

            # PERMISSION-BASED TECHNICIAN PROFILE (RBAC)
            # If any assigned role has 'work_order:execute', ensure and update TechnicianProfile
            has_exec_perm = any(r.permissions.filter(id='work_order:execute').exists() for r in roles)
            tech_payload = data.get('technicianProfile')
            if has_exec_perm or tech_payload:
                from users.models import TechnicianProfile
                from datetime import timedelta
                from django.utils import timezone
                
                tech_data = tech_payload or {}
                shift_code = tech_data.get('shift_code', 'SHIFT_1')
                now = timezone.now()
                if shift_code == 'SHIFT_1':
                    shift_end = now.replace(hour=14, minute=0, second=0, microsecond=0)
                    if shift_end < now:
                        shift_end += timedelta(days=1)
                elif shift_code == 'SHIFT_2':
                    shift_end = now.replace(hour=22, minute=0, second=0, microsecond=0)
                    if shift_end < now:
                        shift_end += timedelta(days=1)
                elif shift_code == 'SHIFT_3':
                    shift_end = now.replace(hour=6, minute=0, second=0, microsecond=0) + timedelta(days=1)
                else:
                    shift_end = now + timedelta(hours=8)

                TechnicianProfile.objects.update_or_create(
                    user=u,
                    defaults={
                        'tenant_id': tenant_id,
                        'skill_level': int(tech_data.get('skill_level', 1)),
                        'skills': tech_data.get('skills', ['GENERAL']),
                        'certifications': tech_data.get('certifications', []),
                        'zone_id': tech_data.get('zone_id', '') or '',
                        'floor_level': int(tech_data.get('floor_level', 1)),
                        'coords_x': float(tech_data.get('coords_x', 20.0)),
                        'coords_y': float(tech_data.get('coords_y', 20.0)),
                        'shift_end_time': shift_end,
                        'is_on_duty': True,
                        'availability_status': 'AVAILABLE'
                    }
                )
                
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
            roles = []
            if role_ids:
                roles = list(Role.objects.filter(id__in=role_ids, tenant_id=tenant_id).prefetch_related('permissions'))
                for r in roles:
                    is_super = request.user.is_superuser or request.user.roles.filter(name='SUPER_ADMIN').exists()
                    if r.name == 'SUPER_ADMIN' and not is_super:
                        return JsonResponse({'success': False, 'error': 'You do not have permission to assign the SUPER_ADMIN role'}, status=403)
                u.roles.set(roles)
            else:
                u.roles.clear()

            # PERMISSION-BASED TECHNICIAN PROFILE (RBAC)
            has_exec_perm = any(r.permissions.filter(id='work_order:execute').exists() for r in roles)
            tech_payload = data.get('technicianProfile')
            if has_exec_perm or tech_payload:
                from users.models import TechnicianProfile
                from datetime import timedelta
                from django.utils import timezone
                
                tech_data = tech_payload or {}
                shift_code = tech_data.get('shift_code', 'SHIFT_1')
                now = timezone.now()
                if shift_code == 'SHIFT_1':
                    shift_end = now.replace(hour=14, minute=0, second=0, microsecond=0)
                    if shift_end < now:
                        shift_end += timedelta(days=1)
                elif shift_code == 'SHIFT_2':
                    shift_end = now.replace(hour=22, minute=0, second=0, microsecond=0)
                    if shift_end < now:
                        shift_end += timedelta(days=1)
                elif shift_code == 'SHIFT_3':
                    shift_end = now.replace(hour=6, minute=0, second=0, microsecond=0) + timedelta(days=1)
                else:
                    shift_end = now + timedelta(hours=8)

                TechnicianProfile.objects.update_or_create(
                    user=u,
                    defaults={
                        'tenant_id': tenant_id,
                        'skill_level': int(tech_data.get('skill_level', 1)),
                        'skills': tech_data.get('skills', ['GENERAL']),
                        'certifications': tech_data.get('certifications', []),
                        'zone_id': tech_data.get('zone_id', '') or '',
                        'floor_level': int(tech_data.get('floor_level', 1)),
                        'coords_x': float(tech_data.get('coords_x', 20.0)),
                        'coords_y': float(tech_data.get('coords_y', 20.0)),
                        'shift_end_time': shift_end,
                        'is_on_duty': True,
                        'availability_status': 'AVAILABLE'
                    }
                )
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
            
    elif request.method == 'DELETE':
        if not HasPermission('user:update')().has_permission(request, None):
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        try:
            data = json.loads(request.body)
            u = User.objects.get(id=data.get('id'), tenant_id=tenant_id)
            if u.id == request.user.id:
                return JsonResponse({'success': False, 'error': 'Cannot block your own account'}, status=400)
            if u.is_superuser:
                return JsonResponse({'success': False, 'error': 'Cannot block superuser'}, status=400)
            u.status = 'INACTIVE'
            u.save()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    from assets.models import Asset

    if str(tenant_id) == '00000000-0000-0000-0000-000000000000' or request.user.is_superuser:
        users = User.all_objects.exclude(id='00000000-0000-0000-0000-000000000000').select_related('tenant', 'technician_profile').prefetch_related('roles__permissions').order_by('-created_at')
    else:
        users = User.objects.filter(tenant_id=tenant_id).select_related('tenant', 'technician_profile').prefetch_related('roles__permissions').order_by('-created_at')
    
    # Calculate metrics
    total_users = users.count()
    active_users = users.filter(status='ACTIVE').count()
    blocked_users = users.filter(status='INACTIVE').count()
    pending_users = users.filter(status='PENDING').count()
    
    is_super = request.user.is_superuser or request.user.roles.filter(name='SUPER_ADMIN').exists()
    if is_super:
        roles = Role.all_objects.prefetch_related('permissions').all()
    else:
        roles = Role.objects.filter(tenant_id=tenant_id).prefetch_related('permissions').exclude(name='SUPER_ADMIN')
    
    # RBAC: Compute permission map and user profile data for frontend
    roles_can_execute_map = {}
    for r in roles:
        has_exec = r.permissions.filter(id='work_order:execute').exists()
        r.can_execute_wo = has_exec
        roles_can_execute_map[str(r.id)] = has_exec

    user_profiles_dict = {}
    for u in users:
        tp = getattr(u, 'technician_profile', None)
        u.can_execute_wo = any(r.permissions.filter(id='work_order:execute').exists() for r in u.roles.all()) or (tp is not None)
        if tp:
            user_profiles_dict[str(u.id)] = {
                'skill_level': tp.skill_level,
                'skills': tp.skills or [],
                'certifications': tp.certifications or [],
                'zone_id': tp.zone_id or '',
                'floor_level': tp.floor_level or 1,
                'coords_x': tp.coords_x or 0.0,
                'coords_y': tp.coords_y or 0.0,
            }

    # Available Zones & Locations Master Data
    from assets.models import Location
    locations_list = list(Location.objects.filter(tenant_id=tenant_id, is_active=True).values('id', 'code', 'name', 'zone_type', 'floor_level', 'center_x', 'center_y', 'floorplan_image'))
    loc_codes = [l['code'] for l in locations_list if l['code']]
    asset_zones = list(Asset.objects.filter(tenant_id=tenant_id).exclude(zone_id='').values_list('zone_id', flat=True).distinct())
    available_zones = sorted(list(set(loc_codes + asset_zones)))
    if not available_zones:
        available_zones = ['ZONE_MAIN', 'ZONE_PRESS', 'ZONE_CLEANROOM', 'ZONE_WAREHOUSE']

    from users.models import WorkforceSkill, CertificationType, ShiftTemplate
    workforce_skills = list(WorkforceSkill.objects.filter(tenant_id=tenant_id, is_active=True).values('code', 'name', 'category'))
    certification_types = list(CertificationType.objects.filter(tenant_id=tenant_id, is_active=True).values('code', 'name'))
    shift_templates = list(ShiftTemplate.objects.filter(tenant_id=tenant_id, is_active=True).values('id', 'code', 'name', 'start_time', 'end_time', 'is_overnight'))

    return render(request, 'users.html', {
        'users': users, 
        'roles': roles,
        'roles_can_execute_json': json.dumps(roles_can_execute_map),
        'user_profiles_json': json.dumps(user_profiles_dict),
        'available_zones': available_zones,
        'locations_list': locations_list,
        'locations_json': json.dumps(locations_list, default=str),
        'workforce_skills': workforce_skills,
        'certification_types': certification_types,
        'shift_templates': shift_templates,
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
    from assets.models import HierarchyTemplate, Location, Asset
    templates = HierarchyTemplate.objects.filter(tenant_id=tenant_id)
    locations = Location.objects.filter(tenant_id=tenant_id).exclude(code__startswith='__').order_by('floor_level', 'name', 'id')
    import re
    # Process locations for template hierarchy & visual floorplan
    loc_list = []
    for loc in locations:
        dim_match = re.search(r'\[DIM:([\d\.]+)x([\d\.]+)\]', loc.description or '')
        w_m = float(dim_match.group(1)) if dim_match else 36.0
        h_m = float(dim_match.group(2)) if dim_match else 26.0
        loc_list.append({
            'id': str(loc.id),
            'name': loc.name,
            'code': loc.code or '',
            'zone_type': loc.zone_type,
            'description': loc.description or '',
            'parent_id': loc.parent_id or '',
            'center_x': loc.center_x,
            'center_y': loc.center_y,
            'width_m': w_m,
            'height_m': h_m,
            'floor_level': loc.floor_level or 1,
            'floorplan_image': loc.floorplan_image or '',
            'is_active': loc.is_active
        })

    # Query active assets for drag-and-drop floorplan studio
    assets_qs = Asset.objects.filter(tenant_id=tenant_id, is_active=True).order_by('name', 'id').values(
        'id', 'name', 'qr_code', 'model', 'serial_number', 'status', 'location_id',
        'coords_x', 'coords_y', 'floor_level', 'zone_id'
    )
    assets_list = list(assets_qs)
    for a in assets_list:
        a['id'] = str(a['id'])
        if a.get('location_id'):
            a['location_id'] = str(a['location_id'])

    # Active technicians & roster duty stations today (for Floorplan Worker Simulation)
    from users.models import TechnicianSchedule
    from workorders.models import WorkOrder
    from django.utils import timezone
    today = timezone.now().date()
    
    today_scheds = TechnicianSchedule.objects.filter(
        tenant_id=tenant_id,
        work_date=today,
        status='ON_DUTY'
    ).select_related('user', 'shift_template')
    
    techs_list = []
    for s in today_scheds:
        tp = getattr(s.user, 'technician_profile', None)
        techs_list.append({
            'user_id': str(s.user.id),
            'name': s.user.get_full_name() or s.user.username,
            'duty_zone': s.duty_zone_id or (tp.zone_id if tp else ''),
            'shift_name': s.shift_template.name if s.shift_template else 'Ca trực',
            'coords_x': tp.coords_x if tp else 0.0,
            'coords_y': tp.coords_y if tp else 0.0,
            'floor_level': tp.floor_level if tp else 1,
            'availability': tp.availability_status if tp else 'AVAILABLE'
        })

    # In-progress work orders (for live machine status indicator)
    active_wos = list(WorkOrder.objects.filter(
        tenant_id=tenant_id,
        status='IN_PROGRESS',
        asset_id__isnull=False
    ).values('id', 'title', 'asset_id', 'assigned_to__username'))
    for w in active_wos:
        w['id'] = str(w['id'])
        w['asset_id'] = str(w['asset_id'])

    spatials_loc = Location.objects.filter(tenant_id=tenant_id, code='__SPATIAL_ELEMENTS__').first()
    spatials_json = spatials_loc.description if (spatials_loc and spatials_loc.description) else '[]'

    factory_dim_loc = Location.objects.filter(tenant_id=tenant_id, code='__FACTORY_DIMENSIONS__').first()
    factory_dim_json = factory_dim_loc.description if (factory_dim_loc and factory_dim_loc.description) else '{}'

    return render(request, 'asset_categories.html', {
        'categories': categories,
        'templates': templates,
        'locations': loc_list,
        'locations_json': json.dumps(loc_list, default=str),
        'assets_list': assets_list,
        'assets_json': json.dumps(assets_list, default=str),
        'technicians_list': techs_list,
        'technicians_json': json.dumps(techs_list, default=str),
        'active_wos_list': active_wos,
        'active_wos_json': json.dumps(active_wos, default=str),
        'spatials_json': spatials_json,
        'factory_dim_json': factory_dim_json,
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
    

    action = request.GET.get('action')
    if request.method == 'POST' and action == 'place_asset':
        try:
            data = json.loads(request.body)
            asset_id = data.get('asset_id')
            loc_id = data.get('location_id')
            cx = float(data.get('coords_x') or 0.0)
            cy = float(data.get('coords_y') or 0.0)
            fl = int(data.get('floor_level') or 1)
            
            from assets.models import Asset
            asset_obj = Asset.objects.filter(id=asset_id, tenant_id=tenant_id).first()
            if not asset_obj:
                return JsonResponse({'success': False, 'error': 'Asset not found'}, status=404)
            
            if loc_id:
                loc = Location.objects.filter(id=loc_id, tenant_id=tenant_id).first()
                if loc:
                    asset_obj.location = loc
                    asset_obj.zone_id = loc.code or loc.name
            else:
                asset_obj.location = None
                asset_obj.zone_id = ''
                
            asset_obj.coords_x = cx
            asset_obj.coords_y = cy
            asset_obj.floor_level = fl
            asset_obj.save()
            return JsonResponse({
                'success': True,
                'asset_id': str(asset_obj.id),
                'location_id': str(asset_obj.location_id) if asset_obj.location_id else None,
                'coords_x': asset_obj.coords_x,
                'coords_y': asset_obj.coords_y,
                'zone_id': asset_obj.zone_id
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    if request.method == 'POST':
        if not HasPermission('asset_category:create')().has_permission(request, None):
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        try:
            import uuid
            data = json.loads(request.body)
            name = data.get('name')
            parent_id = data.get('parentId')
            code = (data.get('code') or '').strip().upper()
            zone_type = data.get('zone_type', 'STANDARD')
            floor_level = int(data.get('floor_level') or 1)
            center_x = float(data.get('center_x') or 25.0)
            center_y = float(data.get('center_y') or 20.0)
            floorplan_image = data.get('floorplan_image', '')
            
            if Location.objects.filter(tenant_id=tenant_id, name=name, parent_id=parent_id).exists():
                return JsonResponse({'success': False, 'error': 'Location name already exists under this parent'}, status=400)
            
            l = Location.objects.create(
                tenant_id=tenant_id,
                name=name,
                code=code or ('LOC-' + str(uuid.uuid4())[:6].upper()),
                zone_type=zone_type,
                floor_level=floor_level,
                center_x=center_x,
                center_y=center_y,
                floorplan_image=floorplan_image or '',
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
            if 'code' in data and data.get('code'):
                l.code = data.get('code').strip().upper()
            if 'zone_type' in data:
                l.zone_type = data.get('zone_type')
            if 'floor_level' in data:
                l.floor_level = int(data.get('floor_level') or 1)
            if 'center_x' in data and data.get('center_x') is not None:
                l.center_x = float(data.get('center_x'))
            if 'center_y' in data and data.get('center_y') is not None:
                l.center_y = float(data.get('center_y'))
            if 'floorplan_image' in data:
                l.floorplan_image = data.get('floorplan_image') or ''
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
    return JsonResponse({'success': True, 'data': [{
        'id': str(loc.id),
        'name': loc.name,
        'code': loc.code or '',
        'zone_type': loc.zone_type,
        'center_x': loc.center_x,
        'center_y': loc.center_y,
        'floor_level': loc.floor_level,
        'floorplan_image': loc.floorplan_image or '',
        'description': loc.description,
        'parentId': loc.parent_id,
        'isActive': loc.is_active
    } for loc in locations]})

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
            location_id = data.get('location_id')
            template_id = data.get('hierarchy_template_id')
            a = Asset.objects.create(
                tenant_id=tenant_id,
                name=data.get('name'),
                model=data.get('model'),
                serial_number=data.get('serial_number'),
                qr_code=data.get('qr_code') or ("AST-" + str(uuid.uuid4())[:8].upper()),
                status=data.get('status', 'OPERATIONAL'),
                category_id=category_id if category_id else None,
                location_id=location_id if location_id else None,
                hierarchy_template_id=template_id if template_id else None,
                parent_id=data.get('parent_id') or None,
                manufacturer=data.get('manufacturer') or None,
                purchase_date=data.get('purchase_date') or None,
                value=data.get('value') or None,
                is_active=data.get('is_active', True)
            )
            return JsonResponse({'success': True, 'id': str(a.id)})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
            
    elif request.method == 'PUT':
        if not HasPermission('asset:update')().has_permission(request, None):
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        try:
            data = json.loads(request.body)
            a = Asset.objects.get(id=data.get('id'), tenant_id=tenant_id)
            
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

            if 'hierarchy_template_id' in data:
                template_id = data.get('hierarchy_template_id')
                a.hierarchy_template_id = template_id if template_id else None
                
            if 'parent_id' in data:
                a.parent_id = data.get('parent_id') or None
            if 'manufacturer' in data:
                a.manufacturer = data.get('manufacturer') or None
            if 'purchase_date' in data:
                a.purchase_date = data.get('purchase_date') or None
            if 'is_active' in data:
                a.is_active = data.get('is_active', True)
            if 'coords_x' in data and data.get('coords_x') is not None:
                a.coords_x = float(data.get('coords_x') or 0.0)
            if 'coords_y' in data and data.get('coords_y') is not None:
                a.coords_y = float(data.get('coords_y') or 0.0)
            if 'floor_level' in data and data.get('floor_level') is not None:
                a.floor_level = int(data.get('floor_level') or 1)
            if 'zone_id' in data and data.get('zone_id') is not None:
                a.zone_id = str(data.get('zone_id') or '')
                
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
                
                # Auto-inherit location from asset if not manually supplied
                asset_obj = Asset.objects.filter(id=asset_id, tenant_id=tenant_id).first() if asset_id else None
                zone_id = data.get('zone_id') if data.get('zone_id') else (asset_obj.zone_id if asset_obj else '')
                floor_level = int(data.get('floor_level') if data.get('floor_level') is not None else (asset_obj.floor_level if asset_obj else 1))
                coords_x = float(data.get('coords_x') if data.get('coords_x') is not None else (asset_obj.coords_x if asset_obj else 0.0))
                coords_y = float(data.get('coords_y') if data.get('coords_y') is not None else (asset_obj.coords_y if asset_obj else 0.0))

                wo = WorkOrder.objects.create(
                    tenant_id=tenant_id,
                    title=data.get('title'),
                    description=data.get('description'),
                    priority=data.get('priority', 'MEDIUM'),
                    status=data.get('status', 'CREATED'),
                    asset_id=asset_id if asset_id else None,
                    assigned_to_id=assigned_to_id if assigned_to_id else None,
                    deadline=parse_datetime(data.get('deadline')) if data.get('deadline') else None,
                    created_by=request.user,
                    # Hungarian & Optimization fields
                    required_skill=data.get('required_skill', 'GENERAL') or 'GENERAL',
                    min_skill_level=int(data.get('min_skill_level', 1)),
                    required_certification=data.get('required_certification', '') or '',
                    required_tools=data.get('required_tools', []),
                    is_crew_task=bool(data.get('is_crew_task', False)),
                    depends_on_wo_id=data.get('depends_on_wo_id') if data.get('depends_on_wo_id') else None,
                    zone_id=zone_id or '',
                    floor_level=floor_level,
                    coords_x=coords_x,
                    coords_y=coords_y
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

                        # Event-based technician positioning: snap tech coords & zone to machine
                        if hasattr(request.user, 'technician_profile'):
                            tp = request.user.technician_profile
                            snap_x = wo.coords_x or (wo.asset.coords_x if wo.asset else None)
                            snap_y = wo.coords_y or (wo.asset.coords_y if wo.asset else None)
                            snap_zone = wo.zone_id or (wo.asset.zone_id if wo.asset else None)
                            snap_floor = wo.floor_level or (wo.asset.floor_level if wo.asset else None)
                            if snap_x is not None: tp.coords_x = snap_x
                            if snap_y is not None: tp.coords_y = snap_y
                            if snap_zone: tp.zone_id = snap_zone
                            if snap_floor: tp.floor_level = snap_floor
                            tp.availability_status = 'BUSY'
                            tp.save()

                        # Dispatch real-time notification to supervisor / creator
                        try:
                            from notifications.services import notify_work_order_started
                            notify_work_order_started(wo, technician=request.user)
                        except Exception:
                            pass

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

                        # Event-based technician positioning: return tech to duty zone station
                        if hasattr(request.user, 'technician_profile'):
                            tp = request.user.technician_profile
                            tp.availability_status = 'AVAILABLE'
                            from users.models import TechnicianSchedule
                            from assets.models import Location
                            today_sched = TechnicianSchedule.objects.filter(
                                tenant_id=tenant_id,
                                user=request.user,
                                work_date=timezone.now().date(),
                                status='ON_DUTY'
                            ).first()
                            if today_sched and today_sched.duty_zone_id:
                                loc = Location.objects.filter(tenant_id=tenant_id, code=today_sched.duty_zone_id).first()
                                if loc:
                                    tp.zone_id = loc.code
                                    tp.coords_x = loc.center_x or 25.0
                                    tp.coords_y = loc.center_y or 20.0
                                    tp.floor_level = loc.floor_level or 1
                            tp.save()

                        # Dispatch real-time notification to supervisor / creator
                        try:
                            from notifications.services import notify_work_order_completed
                            notify_work_order_completed(wo, technician=request.user)
                        except Exception:
                            pass

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
                    
                # Hungarian & Optimization fields in PUT
                if 'required_skill' in data:
                    wo.required_skill = data.get('required_skill') or 'GENERAL'
                if 'min_skill_level' in data:
                    wo.min_skill_level = int(data.get('min_skill_level', 1))
                if 'required_certification' in data:
                    wo.required_certification = data.get('required_certification') or ''
                if 'required_tools' in data:
                    wo.required_tools = data.get('required_tools', [])
                if 'is_crew_task' in data:
                    wo.is_crew_task = bool(data.get('is_crew_task', False))
                if 'depends_on_wo_id' in data:
                    wo.depends_on_wo_id = data.get('depends_on_wo_id') if data.get('depends_on_wo_id') else None
                if 'zone_id' in data:
                    wo.zone_id = data.get('zone_id') or ''
                if 'floor_level' in data:
                    wo.floor_level = int(data.get('floor_level', 1))
                if 'coords_x' in data and data.get('coords_x') is not None:
                    wo.coords_x = float(data.get('coords_x'))
                if 'coords_y' in data and data.get('coords_y') is not None:
                    wo.coords_y = float(data.get('coords_y'))

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
    from assets.models import Tool
    now = timezone.now()

    work_orders = WorkOrder.objects.filter(tenant_id=tenant_id).select_related('asset', 'assigned_to', 'parent_id', 'created_by').prefetch_related('checklists', 'follow_up_work_orders')
    
    total_wos = work_orders.count()
    in_progress = sum(1 for wo in work_orders if wo.status == 'IN_PROGRESS')
    overdue = sum(1 for wo in work_orders if wo.deadline and wo.deadline < now and wo.status not in ['COMPLETED', 'CANCELED'])
    completed = sum(1 for wo in work_orders if wo.status == 'COMPLETED')

    wo_data = []
    wo_metadata = {}
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

        wo_metadata[str(wo.id)] = {
            'required_skill': wo.required_skill or 'GENERAL',
            'min_skill_level': wo.min_skill_level or 1,
            'required_certification': wo.required_certification or '',
            'required_tools': wo.required_tools or [],
            'is_crew_task': bool(wo.is_crew_task),
            'depends_on_wo_id': str(wo.depends_on_wo_id) if wo.depends_on_wo_id else '',
            'zone_id': wo.zone_id or '',
            'floor_level': wo.floor_level or 1,
            'coords_x': wo.coords_x if wo.coords_x is not None else 0.0,
            'coords_y': wo.coords_y if wo.coords_y is not None else 0.0,
        }

    assets = Asset.objects.filter(tenant_id=tenant_id)
    assets_dict = {}
    for a in assets:
        assets_dict[str(a.id)] = {
            'name': a.name,
            'zone_id': a.zone_id or '',
            'floor_level': a.floor_level or 1,
            'coords_x': a.coords_x if a.coords_x is not None else 0.0,
            'coords_y': a.coords_y if a.coords_y is not None else 0.0,
        }

    # Strict RBAC: Technicians assignable must have permission 'work_order:execute'
    technicians = User.objects.filter(
        tenant_id=tenant_id,
        roles__permissions__id='work_order:execute'
    ).distinct().select_related('technician_profile')

    tools = list(Tool.objects.filter(tenant_id=tenant_id, is_active=True).values('code', 'name', 'available_quantity'))

    from users.models import WorkforceSkill, CertificationType
    skills = list(WorkforceSkill.objects.filter(tenant_id=tenant_id, is_active=True).values('code', 'name', 'category'))
    cert_types = list(CertificationType.objects.filter(tenant_id=tenant_id, is_active=True).values('code', 'name'))

    # Available Zones & Locations Master Data
    from assets.models import Location
    locations_list = list(Location.objects.filter(tenant_id=tenant_id, is_active=True).values('id', 'code', 'name', 'zone_type', 'floor_level', 'center_x', 'center_y', 'floorplan_image'))
    loc_codes = [l['code'] for l in locations_list if l['code']]
    asset_zones = list(Asset.objects.filter(tenant_id=tenant_id).exclude(zone_id='').values_list('zone_id', flat=True).distinct())
    available_zones = sorted(list(set(loc_codes + asset_zones)))
    if not available_zones:
        available_zones = ['ZONE_MAIN', 'ZONE_PRESS', 'ZONE_CLEANROOM', 'ZONE_WAREHOUSE']

    kpis = {
        'total': total_wos,
        'in_progress': in_progress,
        'overdue': overdue,
        'completed': completed
    }
    
    return render(request, 'work_orders.html', {
        'work_orders_data': wo_data,
        'assets': assets,
        'assets_json': json.dumps(assets_dict),
        'users': technicians,
        'technicians': technicians,
        'tools': tools,
        'skills': skills,
        'cert_types': cert_types,
        'available_zones': available_zones,
        'locations_list': locations_list,
        'locations_json': json.dumps(locations_list, default=str),
        'wo_metadata_json': json.dumps(wo_metadata),
        'kpis': kpis
    })

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
    from dateutil.relativedelta import relativedelta
    now = timezone.now()
    next_week = now + timedelta(days=7)
    
    active_assignments = PmPlanAssignment.objects.filter(
        tenant_id=tenant_id,
        status='ACTIVE',
        pm_plan__trigger_type='TIME'
    ).select_related('pm_plan')
    
    for assignment in active_assignments:
        plan = assignment.pm_plan
        interval = plan.interval_value
        unit = plan.interval_unit
        if not interval or interval <= 0 or not unit:
            continue
            
        ref_date = assignment.last_triggered_at or assignment.created_at
        due_date = ref_date
        if unit == 'DAYS':
            due_date += relativedelta(days=int(interval))
        elif unit == 'WEEKS':
            due_date += relativedelta(weeks=int(interval))
        elif unit == 'MONTHS':
            due_date += relativedelta(months=int(interval))
        elif unit == 'YEARS':
            due_date += relativedelta(years=int(interval))
            
        if now <= due_date <= next_week:
            upcoming_pms_count += 1


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
@permission_required('reports:read')
def portal_reports(request):
    from assets.models import AssetCategory, Location
    from django.utils import timezone
    tenant = getattr(request.user, 'tenant', None)
    categories = AssetCategory.objects.filter(tenant=tenant, is_active=True) if tenant else []
    locations = Location.objects.filter(tenant=tenant, is_active=True) if tenant else []
    
    today = timezone.now().date()
    first_day_of_month = today.replace(day=1)
    
    context = {
        'categories': categories,
        'locations': locations,
        'default_date_from': first_day_of_month.strftime('%Y-%m-%d'),
        'default_date_to': today.strftime('%Y-%m-%d'),
    }
    return render(request, 'reports.html', context)

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
        'reports:read': 'Xem báo cáo doanh nghiệp (Read Enterprise Reports)',
        'reports:export': 'Xuất báo cáo doanh nghiệp (Export Enterprise Reports)',
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


# ==============================================================================
# WORKFORCE & TOOLS (MAINTENANCE RESOURCES MANAGEMENT)
# ==============================================================================

@login_required(login_url='portal_login')
def portal_workforce_tools(request):
    """
    Unified Hub for Maintenance Workforce Competency, Shifts, Specialized Tools & Calibration.
    Accessible with 'workforce:read', 'work_order:read', or 'user:read'.
    """
    if not check_perm(request, ['workforce:read', 'work_order:read', 'user:read']):
        return portal_permission_denied(request, 'workforce:read')

    from users.models import (
        WorkforceSkill, CertificationType, ShiftTemplate,
        TechnicianSchedule, User
    )
    from assets.models import Tool, ToolInstance, ToolReservation
    from datetime import timedelta
    from django.utils import timezone

    tenant_id = request.session.get('tenant_id') or getattr(request.user, 'tenant_id', None)
    now = timezone.now()
    today = now.date()

    # Active Tab
    active_tab = request.GET.get('tab', 'skills')

    # Week calculation for Roster Matrix
    week_offset = int(request.GET.get('week_offset', 0))
    base_monday = (today - timedelta(days=today.weekday())) + timedelta(weeks=week_offset)
    days_of_week = [base_monday + timedelta(days=i) for i in range(7)]

    # 1. Skills & Certifications Data
    skills = list(WorkforceSkill.objects.filter(tenant_id=tenant_id).order_by('category', 'name'))
    cert_types = list(CertificationType.objects.filter(tenant_id=tenant_id).order_by('name'))

    # 2. Shift Templates & Weekly Roster
    shift_templates = list(ShiftTemplate.objects.filter(tenant_id=tenant_id).order_by('start_time'))
    tech_qs = User.all_objects.filter(
        tenant_id=tenant_id,
        status='ACTIVE',
        technician_profile__isnull=False
    ).distinct().select_related('technician_profile').order_by('username')
    technicians = list(tech_qs)

    schedules_qs = TechnicianSchedule.objects.filter(
        tenant_id=tenant_id,
        work_date__in=days_of_week
    ).select_related('shift_template', 'user')

    schedule_lookup = {}
    for sc in schedules_qs:
        schedule_lookup[(str(sc.user_id), sc.work_date.isoformat())] = sc

    roster_rows = []
    for tech in technicians:
        profile = getattr(tech, 'technician_profile', None)
        day_cells = []
        for d in days_of_week:
            d_str = d.isoformat()
            sc = schedule_lookup.get((str(tech.id), d_str))
            day_cells.append({
                'date': d,
                'date_str': d_str,
                'is_today': (d == today),
                'schedule': sc,
                'status': sc.status if sc else 'UNASSIGNED',
                'duty_zone_id': getattr(sc, 'duty_zone_id', '') if sc else '',
                'shift_name': sc.shift_template.name if (sc and sc.shift_template) else ('Nghỉ ca' if (sc and sc.status == 'OFF') else ('Nghỉ phép' if (sc and sc.status == 'LEAVE') else 'Chưa xếp ca')),
                'shift_color': sc.shift_template.color_code if (sc and sc.shift_template) else ('#94a3b8' if (sc and sc.status in ['OFF', 'LEAVE']) else '#cbd5e1'),
                'is_overnight': sc.shift_template.is_overnight if (sc and sc.shift_template) else False,
            })
        roster_rows.append({
            'tech': tech,
            'profile': profile,
            'days': day_cells
        })

    # 3. Specialized Tools & Calibration Instances
    tools = list(Tool.objects.filter(tenant_id=tenant_id).order_by('name'))
    tool_instances = list(
        ToolInstance.objects.filter(tenant_id=tenant_id)
        .select_related('tool')
        .order_by('tool__name', 'serial_number')
    )

    total_instances = len(tool_instances)
    passed_count = sum(1 for ti in tool_instances if ti.inspection_status == 'PASSED' and ti.status == 'AVAILABLE')
    expired_count = sum(1 for ti in tool_instances if ti.inspection_status == 'EXPIRED' or (ti.calibration_due_date and ti.calibration_due_date < today))
    due_soon_count = sum(1 for ti in tool_instances if ti.inspection_status == 'DUE_SOON' or (ti.calibration_due_date and 0 <= (ti.calibration_due_date - today).days <= 30 and ti.inspection_status != 'EXPIRED'))

    # 4. Tool Reservations
    reservations = list(
        ToolReservation.objects.filter(tenant_id=tenant_id)
        .select_related('tool', 'tool_instance', 'work_order')
        .order_by('-reserved_at')[:50]
    )

    # 5. Locations & Zones (Master Data for Spatial & Shift Duty)
    from assets.models import Location
    locations = list(Location.objects.filter(tenant_id=tenant_id, is_active=True).order_by('name'))
    locations_data = [
        {
            'id': str(l.id),
            'code': l.code,
            'name': l.name,
            'zone_type': l.zone_type,
            'zone_type_display': dict(Location.ZONE_TYPE_CHOICES).get(l.zone_type, l.zone_type),
            'floor_level': l.floor_level,
            'center_x': l.center_x,
            'center_y': l.center_y,
            'description': l.description or '',
            'has_floorplan': bool(l.floorplan_image),
            'floorplan_image': l.floorplan_image or '',
        }
        for l in locations
    ]

    # Permission flags
    can_manage_workforce = check_perm(request, ['user:update', 'tenant:update'])
    can_manage_tools = check_perm(request, ['work_order:update', 'inventory:update'])

    context = {
        'active_tab': active_tab,
        'skills': skills,
        'cert_types': cert_types,
        'shift_templates': shift_templates,
        'roster_rows': roster_rows,
        'days_of_week': days_of_week,
        'base_monday': base_monday,
        'week_offset': week_offset,
        'today': today,
        'tools': tools,
        'tool_instances': tool_instances,
        'reservations': reservations,
        'locations': locations,
        'locations_data': locations_data,
        'locations_json': json.dumps(locations_data, default=str),
        'stats': {
            'total_tools': len(tools),
            'total_instances': total_instances,
            'passed_count': passed_count,
            'expired_count': expired_count,
            'due_soon_count': due_soon_count,
            'active_reservations': sum(1 for r in reservations if r.status in ['RESERVED', 'IN_USE']),
        },
        'can_manage_workforce': can_manage_workforce,
        'can_manage_tools': can_manage_tools,
    }
    return render(request, 'workforce_tools.html', context)


@login_required(login_url='portal_login')
def portal_workforce_skills_api(request):
    """API for Managing Skills (Create, Update, Toggle Active)"""
    from django.http import JsonResponse
    import json
    from users.models import WorkforceSkill

    tenant_id = request.session.get('tenant_id') or getattr(request.user, 'tenant_id', None)
    if not check_perm(request, ['user:update', 'tenant:update']):
        return JsonResponse({'success': False, 'error': 'Bạn không có quyền cập nhật danh mục kỹ năng (Yêu cầu: user:update hoặc tenant:update)'}, status=403)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            code = (data.get('code') or '').strip().upper()
            name = (data.get('name') or '').strip()
            category = (data.get('category') or 'GENERAL').strip()
            description = (data.get('description') or '').strip()
            is_active = bool(data.get('is_active', True))
            skill_id = data.get('id')

            if not code or not name:
                return JsonResponse({'success': False, 'error': 'Mã và Tên kỹ năng không được để trống.'}, status=400)

            if skill_id:
                skill = WorkforceSkill.objects.filter(id=skill_id, tenant_id=tenant_id).first()
                if not skill:
                    return JsonResponse({'success': False, 'error': 'Kỹ năng không tồn tại.'}, status=404)
                skill.code = code
                skill.name = name
                skill.category = category
                skill.description = description
                skill.is_active = is_active
                skill.save()
            else:
                if WorkforceSkill.objects.filter(code=code, tenant_id=tenant_id).exists():
                    return JsonResponse({'success': False, 'error': f"Mã kỹ năng '{code}' đã tồn tại trong tổ chức."}, status=400)
                skill = WorkforceSkill.objects.create(
                    tenant_id=tenant_id,
                    code=code,
                    name=name,
                    category=category,
                    description=description,
                    is_active=is_active
                )

            return JsonResponse({'success': True, 'id': str(skill.id), 'code': skill.code, 'name': skill.name})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

    elif request.method == 'DELETE':
        try:
            skill_id = request.GET.get('id')
            skill = WorkforceSkill.objects.filter(id=skill_id, tenant_id=tenant_id).first()
            if skill:
                skill.delete()
                return JsonResponse({'success': True})
            return JsonResponse({'success': False, 'error': 'Kỹ năng không tồn tại.'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

    return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)


@login_required(login_url='portal_login')
def portal_cert_types_api(request):
    """API for Managing Certification Types"""
    from django.http import JsonResponse
    import json
    from users.models import CertificationType

    tenant_id = request.session.get('tenant_id') or getattr(request.user, 'tenant_id', None)
    if not check_perm(request, ['user:update', 'tenant:update']):
        return JsonResponse({'success': False, 'error': 'Bạn không có quyền cập nhật danh mục chứng chỉ.'}, status=403)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            code = (data.get('code') or '').strip().upper()
            name = (data.get('name') or '').strip()
            issuing_body = (data.get('issuing_body') or '').strip()
            validity_months = int(data.get('validity_months') or 12)
            description = (data.get('description') or '').strip()
            is_active = bool(data.get('is_active', True))
            cert_id = data.get('id')

            if not code or not name:
                return JsonResponse({'success': False, 'error': 'Mã và Tên chứng chỉ không được để trống.'}, status=400)

            if cert_id:
                cert = CertificationType.objects.filter(id=cert_id, tenant_id=tenant_id).first()
                if not cert:
                    return JsonResponse({'success': False, 'error': 'Loại chứng chỉ không tồn tại.'}, status=404)
                cert.code = code
                cert.name = name
                cert.issuing_body = issuing_body
                cert.validity_months = validity_months
                cert.description = description
                cert.is_active = is_active
                cert.save()
            else:
                if CertificationType.objects.filter(code=code, tenant_id=tenant_id).exists():
                    return JsonResponse({'success': False, 'error': f"Mã chứng chỉ '{code}' đã tồn tại."}, status=400)
                cert = CertificationType.objects.create(
                    tenant_id=tenant_id,
                    code=code,
                    name=name,
                    issuing_body=issuing_body,
                    validity_months=validity_months,
                    description=description,
                    is_active=is_active
                )
            return JsonResponse({'success': True, 'id': str(cert.id), 'code': cert.code, 'name': cert.name})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

    return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)


@login_required(login_url='portal_login')
def portal_shift_templates_api(request):
    """API for Managing Shift Templates"""
    from django.http import JsonResponse
    import json
    from users.models import ShiftTemplate

    tenant_id = request.session.get('tenant_id') or getattr(request.user, 'tenant_id', None)
    if not check_perm(request, ['tenant:update', 'user:update']):
        return JsonResponse({'success': False, 'error': 'Bạn không có quyền cấu hình mẫu ca trực.'}, status=403)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            code = (data.get('code') or '').strip().upper()
            name = (data.get('name') or '').strip()
            start_time = data.get('start_time')
            end_time = data.get('end_time')
            is_overnight = bool(data.get('is_overnight', False))
            color_code = (data.get('color_code') or '#3b82f6').strip()
            shift_id = data.get('id')

            if not code or not name or not start_time or not end_time:
                return JsonResponse({'success': False, 'error': 'Vui lòng điền đủ Mã, Tên, Giờ bắt đầu và Giờ kết thúc.'}, status=400)

            if shift_id:
                sh = ShiftTemplate.objects.filter(id=shift_id, tenant_id=tenant_id).first()
                if not sh:
                    return JsonResponse({'success': False, 'error': 'Mẫu ca trực không tồn tại.'}, status=404)
                sh.code = code
                sh.name = name
                sh.start_time = start_time
                sh.end_time = end_time
                sh.is_overnight = is_overnight
                sh.color_code = color_code
                sh.save()
            else:
                if ShiftTemplate.objects.filter(code=code, tenant_id=tenant_id).exists():
                    return JsonResponse({'success': False, 'error': f"Mã ca trực '{code}' đã tồn tại."}, status=400)
                sh = ShiftTemplate.objects.create(
                    tenant_id=tenant_id,
                    code=code,
                    name=name,
                    start_time=start_time,
                    end_time=end_time,
                    is_overnight=is_overnight,
                    color_code=color_code,
                    is_active=True
                )
            return JsonResponse({'success': True, 'id': str(sh.id), 'name': sh.name})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

    return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)


@login_required(login_url='portal_login')
def portal_schedules_api(request):
    """API for Updating Technician Schedules on Specific Dates"""
    from django.http import JsonResponse
    import json
    from users.models import TechnicianSchedule, ShiftTemplate, User
    from datetime import datetime

    tenant_id = request.session.get('tenant_id') or getattr(request.user, 'tenant_id', None)
    if not check_perm(request, 'user:update'):
        return JsonResponse({'success': False, 'error': 'Bạn không có quyền xếp lịch trực cho kỹ thuật viên (Yêu cầu: user:update)'}, status=403)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_id = data.get('user_id')
            work_date_str = data.get('work_date')
            shift_template_id = data.get('shift_template_id')
            status = data.get('status', 'ON_DUTY')
            notes = data.get('notes', '')

            if not user_id or not work_date_str:
                return JsonResponse({'success': False, 'error': 'Thiếu user_id hoặc work_date.'}, status=400)

            user = User.all_objects.filter(id=user_id, tenant_id=tenant_id).first()
            if not user:
                return JsonResponse({'success': False, 'error': 'Kỹ thuật viên không tồn tại.'}, status=404)

            work_date = datetime.strptime(work_date_str, '%Y-%m-%d').date()
            shift_template = None
            if shift_template_id and status == 'ON_DUTY':
                shift_template = ShiftTemplate.objects.filter(id=shift_template_id, tenant_id=tenant_id).first()

            duty_zone_id = (data.get('duty_zone_id') or '').strip()

            sched, created = TechnicianSchedule.objects.update_or_create(
                tenant_id=tenant_id,
                user=user,
                work_date=work_date,
                defaults={
                    'shift_template': shift_template,
                    'status': status,
                    'duty_zone_id': duty_zone_id,
                    'notes': notes
                }
            )

            # If today, sync with technician profile
            from django.utils import timezone
            from datetime import timedelta
            now = timezone.now()
            if work_date == now.date():
                profile = getattr(user, 'technician_profile', None)
                if profile:
                    if status == 'OFF':
                        profile.is_on_duty = False
                        profile.availability_status = 'AVAILABLE'
                    elif status == 'LEAVE':
                        profile.is_on_duty = False
                        profile.availability_status = 'ON_LEAVE'
                    elif status == 'ON_DUTY' and shift_template:
                        profile.is_on_duty = True
                        profile.availability_status = 'AVAILABLE'
                        end_t = shift_template.end_time
                        end_dt = now.replace(hour=end_t.hour, minute=end_t.minute, second=end_t.second, microsecond=0)
                        if shift_template.is_overnight or end_dt < now:
                            end_dt += timedelta(days=1)
                        profile.shift_end_time = end_dt
                        if duty_zone_id:
                            profile.zone_id = duty_zone_id
                    profile.save()

            # Trigger real-time & mobile push notification for the technician
            try:
                from notifications.services import notify_technician_shift_assigned
                notify_technician_shift_assigned(sched, actor=request.user, is_update=not created)
            except Exception as notif_ex:
                import logging
                logging.getLogger(__name__).error(f"Failed to dispatch schedule notification: {notif_ex}")

            return JsonResponse({
                'success': True,
                'schedule_id': str(sched.id),
                'status': sched.status,
                'duty_zone_id': sched.duty_zone_id,
                'shift_name': shift_template.name if shift_template else sched.status
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

    return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)


@login_required(login_url='portal_login')
def portal_locations_api(request):
    """API for Managing Locations / Zones with Floorplan & Spatial Coordinates"""
    from django.http import JsonResponse
    import json
    from assets.models import Location

    tenant_id = request.session.get('tenant_id') or getattr(request.user, 'tenant_id', None)
    if not check_perm(request, ['asset:read', 'work_order:read', 'user:read']):
        return JsonResponse({'success': False, 'error': 'Bạn không có quyền truy cập danh mục khu vực.'}, status=403)

    if request.method == 'GET':
        locs = Location.objects.filter(tenant_id=tenant_id, is_active=True).exclude(code__startswith='__').order_by('name')
        data = [
            {
                'id': str(l.id),
                'code': l.code,
                'name': l.name,
                'zone_type': l.zone_type,
                'zone_type_display': dict(Location.ZONE_TYPE_CHOICES).get(l.zone_type, l.zone_type),
                'parent_id': l.parent_id or '',
                'floor_level': l.floor_level,
                'center_x': l.center_x,
                'center_y': l.center_y,
                'description': l.description or '',
                'has_floorplan': bool(l.floorplan_image),
                'floorplan_image': l.floorplan_image or '',
            }
            for l in locs
        ]
        spatials_loc = Location.objects.filter(tenant_id=tenant_id, code='__SPATIAL_ELEMENTS__').first()
        spatials_data = json.loads(spatials_loc.description) if (spatials_loc and spatials_loc.description) else []
        factory_dim_loc = Location.objects.filter(tenant_id=tenant_id, code='__FACTORY_DIMENSIONS__').first()
        factory_dim_data = json.loads(factory_dim_loc.description) if (factory_dim_loc and factory_dim_loc.description) else {}
        return JsonResponse({
            'success': True,
            'data': data,
            'spatials': spatials_data,
            'factory_dim': factory_dim_data
        })

    if not check_perm(request, ['asset:update', 'tenant:update', 'user:update', 'asset_category:update', 'asset_category:delete', 'asset_category:create']):
        return JsonResponse({'success': False, 'error': 'Bạn không có quyền quản lý khu vực.'}, status=403)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            action = request.GET.get('action') or data.get('action')
            if action == 'place_asset':
                asset_id = data.get('asset_id')
                target_loc_id = data.get('location_id')
                cx = float(data.get('coords_x')) if data.get('coords_x') is not None else None
                cy = float(data.get('coords_y')) if data.get('coords_y') is not None else None
                fl = int(data.get('floor_level') or 1)
                
                from assets.models import Asset
                asset_obj = Asset.objects.filter(id=asset_id, tenant_id=tenant_id).first()
                if not asset_obj:
                    return JsonResponse({'success': False, 'error': 'Thiết bị không tồn tại.'}, status=404)
                
                if target_loc_id:
                    target_loc = Location.objects.filter(id=target_loc_id, tenant_id=tenant_id).first()
                    if target_loc:
                        asset_obj.location = target_loc
                        asset_obj.zone_id = target_loc.code or target_loc.name
                # Note: Assets must always belong to a specific location (Asset Register requirement), never set to None
                    
                asset_obj.coords_x = cx
                asset_obj.coords_y = cy
                asset_obj.floor_level = fl
                asset_obj.save()
                return JsonResponse({
                    'success': True,
                    'asset_id': str(asset_obj.id),
                    'location_id': str(asset_obj.location_id) if asset_obj.location_id else None,
                    'coords_x': asset_obj.coords_x,
                    'coords_y': asset_obj.coords_y,
                    'zone_id': asset_obj.zone_id
                })

            if action == 'update_zone_position':
                loc_id = data.get('location_id') or data.get('id')
                cx = float(data.get('center_x') or 0.0)
                cy = float(data.get('center_y') or 0.0)
                fl = int(data.get('floor_level') or 1)
                target_loc = Location.objects.filter(id=loc_id, tenant_id=tenant_id).first()
                if not target_loc:
                    return JsonResponse({'success': False, 'error': 'Phân xưởng không tồn tại.'}, status=404)
                target_loc.center_x = cx
                target_loc.center_y = cy
                target_loc.floor_level = fl
                target_loc.save()
                return JsonResponse({
                    'success': True,
                    'location_id': str(target_loc.id),
                    'center_x': target_loc.center_x,
                    'center_y': target_loc.center_y,
                    'floor_level': target_loc.floor_level
                })

            if action == 'delete_zone':
                loc_id = data.get('location_id') or data.get('id')
                import uuid
                loc = None
                try:
                    uuid_val = uuid.UUID(str(loc_id))
                    loc = Location.objects.filter(id=uuid_val, tenant_id=tenant_id).first()
                except (ValueError, TypeError):
                    loc = None

                if loc:
                    from assets.models import Asset
                    # Nếu yêu cầu chỉ gỡ khỏi sơ đồ (xoá toạ độ X, Y), không xoá hẳn khỏi DB
                    if data.get('only_coords') or data.get('from_studio'):
                        loc.center_x = None
                        loc.center_y = None
                        loc.save()
                        # Đồng thời gỡ toạ độ tất cả tài sản trực thuộc khu vực này khỏi sơ đồ
                        Asset.objects.filter(location=loc, tenant_id=tenant_id).update(coords_x=None, coords_y=None)
                        return JsonResponse({
                            'success': True,
                            'message': f'Đã gỡ phân xưởng "{loc.name}" và các tài sản trực thuộc khỏi sơ đồ.'
                        })

                    # Check if there are active assets directly belonging to this workshop zone
                    assigned_count = Asset.objects.filter(location=loc, tenant_id=tenant_id, is_active=True).count()
                    if assigned_count > 0:
                        return JsonResponse({
                            'success': False,
                            'error': f'Không thể xóa phân xưởng "{loc.name}" vì đang có {assigned_count} tài sản trực thuộc. Theo quy định, mọi tài sản bắt buộc luôn phải thuộc về một kho xưởng cụ thể.'
                        }, status=400)
                    loc.is_active = False
                    loc.save()
                    return JsonResponse({
                        'success': True,
                        'message': f'Đã xóa phân xưởng "{loc.name}".'
                    })
                else:
                    return JsonResponse({
                        'success': True,
                        'message': 'Đã xóa phân xưởng khỏi sơ đồ.'
                    })

            if action == 'delete_asset':
                return JsonResponse({
                    'success': False,
                    'error': 'Không được phép xóa tài sản từ sơ đồ mặt bằng. Vui lòng thực hiện tại trang Danh mục tài sản (Asset Register).'
                }, status=400)

            if action == 'batch_save':
                from assets.models import Asset
                from django.db import transaction
                import uuid
                import re
                saved_assets = 0
                saved_zones = 0
                new_zone_map = {}
                with transaction.atomic():
                    for a_item in data.get('assets', []):
                        a_id = a_item.get('id')
                        if not a_id:
                            continue
                        a_obj = None
                        try:
                            a_uuid = uuid.UUID(str(a_id))
                            a_obj = Asset.objects.filter(id=a_uuid, tenant_id=tenant_id).first()
                        except (ValueError, TypeError, Exception):
                            a_obj = None

                        if a_obj:
                            t_loc_id = a_item.get('location_id')
                            if t_loc_id:
                                try:
                                    t_loc_uuid = uuid.UUID(str(t_loc_id))
                                    t_loc = Location.objects.filter(id=t_loc_uuid, tenant_id=tenant_id).first()
                                except (ValueError, TypeError, Exception):
                                    t_loc = None
                                if t_loc:
                                    a_obj.location = t_loc
                                    a_obj.zone_id = t_loc.code or t_loc.name
                            if 'coords_x' in a_item:
                                a_obj.coords_x = float(a_item['coords_x']) if a_item['coords_x'] is not None else None
                            if 'coords_y' in a_item:
                                a_obj.coords_y = float(a_item['coords_y']) if a_item['coords_y'] is not None else None
                            if 'floor_level' in a_item and a_item['floor_level'] is not None:
                                a_obj.floor_level = int(a_item['floor_level'])
                            a_obj.save()
                            saved_assets += 1

                    for z_item in data.get('zones', []):
                        z_id = z_item.get('id')
                        z_obj = None
                        if z_id:
                            try:
                                z_uuid = uuid.UUID(str(z_id))
                                z_obj = Location.objects.filter(id=z_uuid, tenant_id=tenant_id).first()
                            except (ValueError, TypeError, Exception):
                                z_obj = None

                        if z_obj:
                            if 'name' in z_item and z_item['name']:
                                z_obj.name = z_item['name']
                            if 'code' in z_item and z_item['code']:
                                z_obj.code = z_item['code']
                            if 'parent_id' in z_item:
                                z_obj.parent_id = z_item['parent_id'] if z_item['parent_id'] else None
                            if 'center_x' in z_item:
                                z_obj.center_x = float(z_item['center_x']) if z_item['center_x'] is not None else None
                            if 'center_y' in z_item:
                                z_obj.center_y = float(z_item['center_y']) if z_item['center_y'] is not None else None
                            if 'floor_level' in z_item and z_item['floor_level'] is not None:
                                z_obj.floor_level = int(z_item['floor_level'])
                            poly_pts = z_item.get('polygon_points')
                            if 'width_m' in z_item and 'height_m' in z_item:
                                w_m = float(z_item['width_m'])
                                h_m = float(z_item['height_m'])
                                cur_desc = z_obj.description or ''
                                clean_desc = re.sub(r'\[DIM:[\d\.]+x[\d\.]+\]', '', cur_desc).strip()
                                clean_desc = re.sub(r'\[POLYGON:.*?\]', '', clean_desc).strip()
                                poly_str = f" [POLYGON:{json.dumps(poly_pts)}]" if poly_pts else ""
                                z_obj.description = f"{clean_desc} [DIM:{w_m}x{h_m}]{poly_str}".strip()
                            elif poly_pts:
                                cur_desc = z_obj.description or ''
                                clean_desc = re.sub(r'\[POLYGON:.*?\]', '', cur_desc).strip()
                                z_obj.description = f"{clean_desc} [POLYGON:{json.dumps(poly_pts)}]".strip()
                            z_obj.save()
                            saved_zones += 1
                        elif z_item.get('is_new'):
                            new_name = z_item.get('name') or 'Phòng trống'
                            new_code = z_item.get('code') or ('ROOM-' + str(uuid.uuid4())[:4].upper())
                            w_m = float(z_item.get('width_m') or 36.0)
                            h_m = float(z_item.get('height_m') or 26.0)
                            poly_pts = z_item.get('polygon_points')
                            poly_str = f" [POLYGON:{json.dumps(poly_pts)}]" if poly_pts else ""
                            desc = (z_item.get('description') or 'Khu vực mặt bằng mới') + f" [DIM:{w_m}x{h_m}]{poly_str}"
                            new_loc = Location.objects.create(
                                tenant_id=tenant_id,
                                name=new_name,
                                code=new_code,
                                parent_id=z_item.get('parent_id') or None,
                                zone_type=z_item.get('zone_type', 'STANDARD'),
                                floor_level=int(z_item.get('floor_level', 1)),
                                center_x=float(z_item.get('center_x', 25.0)),
                                center_y=float(z_item.get('center_y', 20.0)),
                                description=desc,
                                is_active=True
                            )
                            if z_id:
                                new_zone_map[str(z_id)] = str(new_loc.id)
                            saved_zones += 1

                    # Lưu các thành phần cấu trúc không gian (Đường đi xe nâng, lối đi bộ, vách ngăn, dock...)
                    spatials = data.get('spatials')
                    if spatials is not None:
                        sp_loc, _ = Location.objects.get_or_create(
                            tenant_id=tenant_id,
                            code='__SPATIAL_ELEMENTS__',
                            defaults={'name': 'Spatial Layout', 'is_active': False, 'floor_level': 1}
                        )
                        sp_loc.description = json.dumps(spatials)
                        sp_loc.save()

                    # Lưu thông số kích thước nhà xưởng
                    factory_dim = data.get('factory_dim')
                    if factory_dim:
                        fd_loc, _ = Location.objects.get_or_create(
                            tenant_id=tenant_id,
                            code='__FACTORY_DIMENSIONS__',
                            defaults={'name': 'Factory Dimensions', 'is_active': False, 'floor_level': 1}
                        )
                        fd_loc.description = json.dumps(factory_dim)
                        fd_loc.save()

                return JsonResponse({
                    'success': True,
                    'saved_assets': saved_assets,
                    'saved_zones': saved_zones,
                    'new_zone_map': new_zone_map,
                    'message': f'Đã lưu thành công {saved_assets} thiết bị và {saved_zones} phân xưởng.'
                })

            loc_id = data.get('id')
            code = (data.get('code') or '').strip().upper()
            name = (data.get('name') or '').strip()
            zone_type = data.get('zone_type', 'STANDARD')
            floor_level = int(data.get('floor_level') or 1)
            center_x = float(data.get('center_x') or 0.0)
            center_y = float(data.get('center_y') or 0.0)
            description = (data.get('description') or '').strip()
            floorplan_image = data.get('floorplan_image', '')

            if not code or not name:
                return JsonResponse({'success': False, 'error': 'Mã và Tên khu vực không được để trống.'}, status=400)

            if loc_id:
                loc = Location.objects.filter(id=loc_id, tenant_id=tenant_id).first()
                if not loc:
                    return JsonResponse({'success': False, 'error': 'Khu vực không tồn tại.'}, status=404)
                loc.code = code
                loc.name = name
                loc.zone_type = zone_type
                loc.floor_level = floor_level
                loc.center_x = center_x
                loc.center_y = center_y
                loc.description = description
                if floorplan_image is not None and floorplan_image != '':
                    loc.floorplan_image = floorplan_image
                loc.is_active = True
                loc.save()
            else:
                existing = Location.objects.filter(code=code, tenant_id=tenant_id, is_active=True).first()
                if existing:
                    return JsonResponse({'success': False, 'error': f"Mã khu vực '{code}' đã tồn tại."}, status=400)
                loc = Location.objects.create(
                    tenant_id=tenant_id,
                    code=code,
                    name=name,
                    zone_type=zone_type,
                    floor_level=floor_level,
                    center_x=center_x,
                    center_y=center_y,
                    description=description,
                    floorplan_image=floorplan_image or '',
                    is_active=True
                )

            return JsonResponse({'success': True, 'id': str(loc.id), 'code': loc.code, 'name': loc.name})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

    elif request.method == 'DELETE':
        try:
            data = json.loads(request.body)
            loc_id = data.get('id') or data.get('location_id')
            loc = Location.objects.filter(id=loc_id, tenant_id=tenant_id).first()
            if loc:
                from assets.models import Asset
                Asset.objects.filter(location=loc, tenant_id=tenant_id).update(
                    location=None,
                    zone_id='',
                    coords_x=0.0,
                    coords_y=0.0
                )
                loc.is_active = False
                loc.save()
            return JsonResponse({'success': True, 'message': 'Đã xóa phân xưởng và giải phóng thiết bị thành công.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

    return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)


@login_required(login_url='portal_login')
def portal_tools_api(request):
    """API for Managing Specialized Tools"""
    from django.http import JsonResponse
    import json
    from assets.models import Tool

    tenant_id = request.session.get('tenant_id') or getattr(request.user, 'tenant_id', None)
    if not check_perm(request, ['work_order:update', 'inventory:update']):
        return JsonResponse({'success': False, 'error': 'Bạn không có quyền quản lý công cụ chuyên dụng.'}, status=403)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            code = (data.get('code') or '').strip().upper()
            name = (data.get('name') or '').strip()
            qty = int(data.get('available_quantity') or 1)
            tool_id = data.get('id')

            if not code or not name:
                return JsonResponse({'success': False, 'error': 'Mã và Tên công cụ không được để trống.'}, status=400)

            if tool_id:
                tool = Tool.objects.filter(id=tool_id, tenant_id=tenant_id).first()
                if not tool:
                    return JsonResponse({'success': False, 'error': 'Công cụ không tồn tại.'}, status=404)
                tool.code = code
                tool.name = name
                tool.available_quantity = qty
                tool.save()
            else:
                if Tool.objects.filter(code=code, tenant_id=tenant_id).exists():
                    return JsonResponse({'success': False, 'error': f"Mã công cụ '{code}' đã tồn tại."}, status=400)
                tool = Tool.objects.create(
                    tenant_id=tenant_id,
                    code=code,
                    name=name,
                    available_quantity=qty,
                    is_active=True
                )
            return JsonResponse({'success': True, 'id': str(tool.id), 'code': tool.code, 'name': tool.name})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

    return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)


@login_required(login_url='portal_login')
def portal_tool_instances_api(request):
    """API for Managing Tool Instances (Serial Numbers & Calibration)"""
    from django.http import JsonResponse
    import json
    from assets.models import Tool, ToolInstance
    from datetime import datetime

    tenant_id = request.session.get('tenant_id') or getattr(request.user, 'tenant_id', None)
    if not check_perm(request, ['work_order:update', 'inventory:update']):
        return JsonResponse({'success': False, 'error': 'Bạn không có quyền cập nhật serial/hiệu chuẩn công cụ.'}, status=403)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            tool_id = data.get('tool_id')
            serial_number = (data.get('serial_number') or '').strip()
            asset_tag = (data.get('asset_tag') or '').strip()
            cal_date_str = data.get('calibration_date')
            due_date_str = data.get('calibration_due_date')
            inspection_status = data.get('inspection_status', 'PASSED')
            status = data.get('status', 'AVAILABLE')
            notes = data.get('notes', '')
            instance_id = data.get('id')

            if not tool_id or not serial_number:
                return JsonResponse({'success': False, 'error': 'Vui lòng chọn công cụ cha và nhập số Serial.'}, status=400)

            tool = Tool.objects.filter(id=tool_id, tenant_id=tenant_id).first()
            if not tool:
                return JsonResponse({'success': False, 'error': 'Công cụ cha không tồn tại.'}, status=404)

            cal_date = datetime.strptime(cal_date_str, '%Y-%m-%d').date() if cal_date_str else None
            due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date() if due_date_str else None

            if instance_id:
                inst = ToolInstance.objects.filter(id=instance_id, tenant_id=tenant_id).first()
                if not inst:
                    return JsonResponse({'success': False, 'error': 'Thiết bị không tồn tại.'}, status=404)
                inst.tool = tool
                inst.serial_number = serial_number
                inst.asset_tag = asset_tag
                inst.calibration_date = cal_date
                inst.calibration_due_date = due_date
                inst.inspection_status = inspection_status
                inst.status = status
                inst.notes = notes
                inst.save()
            else:
                if ToolInstance.objects.filter(tool=tool, serial_number=serial_number, tenant_id=tenant_id).exists():
                    return JsonResponse({'success': False, 'error': f"Serial '{serial_number}' đã tồn tại cho công cụ này."}, status=400)
                inst = ToolInstance.objects.create(
                    tenant_id=tenant_id,
                    tool=tool,
                    serial_number=serial_number,
                    asset_tag=asset_tag,
                    calibration_date=cal_date,
                    calibration_due_date=due_date,
                    inspection_status=inspection_status,
                    status=status,
                    notes=notes
                )
            return JsonResponse({'success': True, 'id': str(inst.id), 'serial': inst.serial_number})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

    return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)


@login_required(login_url='portal_login')
def portal_tool_reservations_api(request):
    """API for Managing Tool Reservations (Mark Returned, Cancel)"""
    from django.http import JsonResponse
    import json
    from assets.models import ToolReservation
    from django.utils import timezone
    from django.db import transaction

    tenant_id = request.session.get('tenant_id') or getattr(request.user, 'tenant_id', None)
    if not check_perm(request, ['work_order:update', 'inventory:update']):
        return JsonResponse({'success': False, 'error': 'Bạn không có quyền quản lý cấp phát công cụ.'}, status=403)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            res_id = data.get('id')
            action = data.get('action', 'RETURN')  # 'RETURN' or 'CANCEL'

            with transaction.atomic():
                res = ToolReservation.objects.select_for_update().filter(id=res_id, tenant_id=tenant_id).first()
                if not res:
                    return JsonResponse({'success': False, 'error': 'Bản ghi giữ chỗ không tồn tại.'}, status=404)

                tool = res.tool
                if action == 'RETURN' and res.status in ['RESERVED', 'IN_USE']:
                    res.status = 'RETURNED'
                    res.returned_at = timezone.now()
                    res.save()
                    # Increment tool available quantity
                    tool.available_quantity = tool.available_quantity + res.reserved_quantity
                    tool.save()
                elif action == 'CANCEL' and res.status == 'RESERVED':
                    res.status = 'CANCELLED'
                    res.returned_at = timezone.now()
                    res.save()
                    tool.available_quantity = tool.available_quantity + res.reserved_quantity
                    tool.save()

            return JsonResponse({'success': True, 'status': res.status})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

    return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)









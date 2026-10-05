from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.db import transaction
from django.core.exceptions import ValidationError
from users.models import Role, Permission, User
from users.serializers import RoleSerializer, PermissionSerializer, RoleCreateUpdateSerializer
from users.permissions import HasPermission

def success_response(data=None, message="Success"):
    return Response({
        "success": True,
        "message": message,
        "data": data
    }, status=status.HTTP_200_OK)

class RoleListView(APIView):
    permission_classes = [HasPermission('role:read')]

    def get(self, request):
        roles = Role.objects.all()
        
        # Check if user is super admin
        is_super_admin = False
        if hasattr(request, '_user_permissions_cache') and 'system:admin' in request._user_permissions_cache:
            is_super_admin = True
            
        if not is_super_admin:
            roles = roles.exclude(name='SUPER_ADMIN')
            
        serializer = RoleSerializer(roles, many=True)
        return success_response(serializer.data)

    @transaction.atomic
    def post(self, request):
        # Check permission manually for POST
        checker = HasPermission('role:create')()
        if not checker.has_permission(request, self):
            self.permission_denied(request)

        serializer = RoleCreateUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            raise ValidationError(serializer.errors)
            
        data = serializer.validated_data
        
        if Role.objects.filter(name=data['name']).exists():
            raise ValidationError(f"Role with name {data['name']} already exists in this tenant")
            
        role = Role.objects.create(
            name=data['name'],
            description=data.get('description', ''),
            is_system=False
        )
        
        perms = Permission.objects.filter(id__in=data['permissionIds'])
        role.permissions.set(perms)
        
        return success_response(RoleSerializer(role).data)

class RoleDetailView(APIView):
    @transaction.atomic
    def put(self, request, role_id):
        checker = HasPermission('role:update')()
        if not checker.has_permission(request, self):
            self.permission_denied(request)

        try:
            role = Role.objects.get(id=role_id)
        except Role.DoesNotExist:
            raise ValidationError("Role not found")
            
        if role.is_system:
            raise ValidationError("Cannot update system role")
            
        serializer = RoleCreateUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            raise ValidationError(serializer.errors)
            
        data = serializer.validated_data
        
        role.name = data['name']
        role.description = data.get('description', '')
        role.save()
        
        perms = Permission.objects.filter(id__in=data['permissionIds'])
        role.permissions.set(perms)
        
        return success_response(RoleSerializer(role).data)

    @transaction.atomic
    def delete(self, request, role_id):
        checker = HasPermission('role:delete')()
        if not checker.has_permission(request, self):
            self.permission_denied(request)

        try:
            role = Role.objects.get(id=role_id)
        except Role.DoesNotExist:
            raise ValidationError("Role not found")
            
        if role.is_system:
            raise ValidationError("Cannot delete system role")
            
        fallback_role_id = request.query_params.get('fallbackRoleId')
        
        users_with_role = User.objects.filter(roles=role)
        if users_with_role.exists():
            if not fallback_role_id:
                raise ValidationError("ROLE_HAS_USERS")
                
            try:
                fallback_role = Role.objects.get(id=fallback_role_id)
            except Role.DoesNotExist:
                raise ValidationError("Fallback role not found")
                
            for user in users_with_role:
                user.roles.remove(role)
                user.roles.add(fallback_role)
                
        role.delete()
        return success_response(None)

class PermissionListView(APIView):
    permission_classes = [HasPermission('role:read')]

    def get(self, request):
        permissions = Permission.objects.exclude(id='system:admin')
        serializer = PermissionSerializer(permissions, many=True)
        return success_response(serializer.data)

class UserListView(APIView):
    permission_classes = [HasPermission('user:read')]

    def get(self, request):
        role_name = request.query_params.get('roleName')
        permission_id = request.query_params.get('permissionId')
        
        # We need to implement pagination if we strictly follow Java (pageable).
        # For simplicity, returning all filtered matching Java logic for filtering.
        users = User.objects.all()
        
        if role_name:
            users = users.filter(roles__name=role_name)
        if permission_id:
            users = users.filter(roles__permissions__id=permission_id)
            
        # Distinct since a user can have multiple roles
        users = users.distinct()
        
        # Determine if super admin
        is_super_admin = False
        if hasattr(request, '_user_permissions_cache') and 'system:admin' in request._user_permissions_cache:
            is_super_admin = True
            
        if not is_super_admin:
            # Exclude super admin users (users that have SUPER_ADMIN role)
            # Actually, `SUPER_ADMIN` is across all tenants if tenant_id = 0...0
            # Java says: findAllExcludingSuperAdmin(UUID systemTenantId)
            users = users.exclude(roles__name='SUPER_ADMIN')
            
        # Pagination
        try:
            page = int(request.query_params.get('page', 0))
            size = int(request.query_params.get('size', 20))
        except ValueError:
            page, size = 0, 20

        total_elements = users.count()
        start = page * size
        end = start + size
        users_page = users[start:end]

        from users.serializers import UserSerializer
        serializer = UserSerializer(users_page, many=True)
        
        return success_response({
            "content": serializer.data,
            "totalElements": total_elements,
            "page": page,
            "size": size
        })

    @transaction.atomic
    def post(self, request):
        checker = HasPermission('user:create')()
        if not checker.has_permission(request, self):
            self.permission_denied(request)

        from users.serializers import UserCreateRequestSerializer, UserSerializer
        serializer = UserCreateRequestSerializer(data=request.data)
        if not serializer.is_valid():
            raise ValidationError(serializer.errors)
            
        data = serializer.validated_data
        
        if User.objects.filter(email=data['email']).exists():
            raise ValidationError("Email already exists in this tenant")
            
        if User.objects.filter(username=data['username']).exists():
            raise ValidationError("Username already exists in this tenant")
            
        user = User.objects.create_user(
            username=data['username'],
            email=data['email'],
            password=data['password'],
            status='ACTIVE'
        )
        
        if 'roleIds' in data and data['roleIds']:
            is_super_admin = False
            if hasattr(request, '_user_permissions_cache') and 'system:admin' in request._user_permissions_cache:
                is_super_admin = True
                
            for role_id in data['roleIds']:
                try:
                    role = Role.objects.get(id=role_id)
                except Role.DoesNotExist:
                    raise ValidationError("Role not found")
                    
                if role.name == 'SUPER_ADMIN' and not is_super_admin:
                    raise ValidationError("You do not have permission to assign the SUPER_ADMIN role")
                    
                user.roles.add(role)
                
        return success_response(UserSerializer(user).data)

class UserDetailView(APIView):
    @transaction.atomic
    def put(self, request, user_id):
        checker = HasPermission('user:update')()
        if not checker.has_permission(request, self):
            self.permission_denied(request)

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise ValidationError("User not found")
            
        from users.serializers import UserUpdateRequestSerializer, UserSerializer
        serializer = UserUpdateRequestSerializer(data=request.data)
        if not serializer.is_valid():
            raise ValidationError(serializer.errors)
            
        data = serializer.validated_data
        
        if 'username' in data and data['username'] != user.username:
            if User.objects.filter(username=data['username']).exists():
                raise ValidationError("Username already exists")
            user.username = data['username']
            
        if 'roleIds' in data:
            is_super_admin = False
            if hasattr(request, '_user_permissions_cache') and 'system:admin' in request._user_permissions_cache:
                is_super_admin = True
                
            user.roles.clear()
            for role_id in data['roleIds']:
                try:
                    role = Role.objects.get(id=role_id)
                except Role.DoesNotExist:
                    raise ValidationError("Role not found")
                    
                if role.name == 'SUPER_ADMIN' and not is_super_admin:
                    raise ValidationError("You do not have permission to assign the SUPER_ADMIN role")
                    
                user.roles.add(role)
                
        user.save()
        return success_response(UserSerializer(user).data)

class UserDisableView(APIView):
    @transaction.atomic
    def put(self, request, user_id):
        checker = HasPermission('user:update')()
        if not checker.has_permission(request, self):
            self.permission_denied(request)

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise ValidationError("User not found")
            
        user.status = 'INACTIVE'
        user.save()
        return success_response(None)

class UserEnableView(APIView):
    @transaction.atomic
    def put(self, request, user_id):
        checker = HasPermission('user:update')()
        if not checker.has_permission(request, self):
            self.permission_denied(request)

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise ValidationError("User not found")
            
        user.status = 'ACTIVE'
        user.save()
        return success_response(None)

class UserInviteView(APIView):
    @transaction.atomic
    def post(self, request):
        checker = HasPermission('user:create')()
        if not checker.has_permission(request, self):
            self.permission_denied(request)

        from users.serializers import UserInviteRequestSerializer
        serializer = UserInviteRequestSerializer(data=request.data)
        if not serializer.is_valid():
            raise ValidationError(serializer.errors)
            
        data = serializer.validated_data
        
        if User.objects.filter(email=data['email']).exists():
            raise ValidationError("Email already exists")
            
        if User.objects.filter(username=data['username']).exists():
            raise ValidationError("Username already exists")
            
        user = User.objects.create_user(
            username=data['username'],
            email=data['email'],
            password=data['password'],
            status='ACTIVE'
        )
        
        if 'roleIds' in data and data['roleIds']:
            is_super_admin = False
            if hasattr(request, '_user_permissions_cache') and 'system:admin' in request._user_permissions_cache:
                is_super_admin = True
                
            for role_id in data['roleIds']:
                try:
                    role = Role.objects.get(id=role_id)
                except Role.DoesNotExist:
                    raise ValidationError("Role not found")
                    
                if role.name == 'SUPER_ADMIN' and not is_super_admin:
                    raise ValidationError("You do not have permission to assign the SUPER_ADMIN role")
                    
                user.roles.add(role)
                
        # Sending email
        from django.core.mail import send_mail
        from django.conf import settings
        
        login_link = "http://localhost:5173/login"
        message = (
            f"You have been invited to join the EAM System.\n\n"
            f"Here are your login credentials:\n"
            f"Username: {data['username']}\n"
            f"Password: {data['password']}\n\n"
            f"Please click the link below to login:\n"
            f"{login_link}\n\n"
            f"We recommend changing your password after your first login."
        )
        
        send_mail(
            subject="EAM System - Invitation & Credentials",
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[data['email']],
            fail_silently=False,
        )
        
        return success_response(None)

class UserImportView(APIView):
    @transaction.atomic
    def post(self, request):
        checker = HasPermission('user:create')()
        if not checker.has_permission(request, self):
            self.permission_denied(request)
            
        # In a real scenario we'd parse the multipart CSV/Excel here.
        # Following Java's behavior, it returns a UserImportResultDto.
        return success_response({
            "totalProcessed": 0,
            "successCount": 0,
            "errorCount": 0,
            "errors": []
        })

class ChangePasswordView(APIView):
    # Only authenticated users can change their password
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        old_password = request.data.get('oldPassword') or request.data.get('currentPassword')
        new_password = request.data.get('newPassword')

        if not old_password or not new_password:
            raise ValidationError("oldPassword (or currentPassword) and newPassword are required")

        user = request.user
        if not user.check_password(old_password):
            return Response({"success": False, "message": "Incorrect old password"}, status=400)

        user.set_password(new_password)
        user.save()
        return success_response(None)

class ForgotPasswordView(APIView):
    permission_classes = []

    @transaction.atomic
    def post(self, request):
        email = request.data.get('email')
        if not email:
            raise ValidationError("Email is required")

        email_clean = email.strip().lower()
        users = User.all_objects.filter(email=email_clean)
        if users.exists():
            user = users.first()
            import secrets
            from django.utils import timezone
            import datetime

            # Cryptographically secure 6-digit OTP code
            code = f"{secrets.randbelow(1000000):06d}"
            user.reset_token = code
            user.reset_token_expiry = timezone.now() + datetime.timedelta(minutes=15)
            user.save(update_fields=['reset_token', 'reset_token_expiry'])

            # Sending email
            from django.core.mail import send_mail
            from django.conf import settings
            
            message = (
                f"You requested a password reset.\n\n"
                f"Your password reset code is: {code}\n\n"
                f"This code will expire in 15 minutes."
            )
            
            send_mail(
                subject="EAM System - Password Reset Code",
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email_clean],
                fail_silently=False,
            )

        # Always return success for security (don't reveal if email exists)
        return success_response(None)

class ResetPasswordView(APIView):
    permission_classes = []

    @transaction.atomic
    def post(self, request):
        code = str(request.data.get('code') or '').strip()
        new_password = request.data.get('newPassword')
        email = request.data.get('email')

        if not code or not new_password:
            raise ValidationError("code and newPassword are required")

        if len(code) != 6:
            return Response({"success": False, "message": "Mã xác thực phải gồm 6 chữ số."}, status=400)

        if len(new_password) < 6:
            return Response({"success": False, "message": "Mật khẩu mới phải có ít nhất 6 ký tự."}, status=400)

        from django.utils import timezone

        # Anti-brute force: Verify against specific email if provided
        if email:
            user = User.all_objects.filter(email=email.strip().lower(), reset_token=code).first()
        else:
            user = User.all_objects.filter(reset_token=code).first()

        if user:
            if user.reset_token_expiry and user.reset_token_expiry > timezone.now():
                user.set_password(new_password)
                user.reset_token = None
                user.reset_token_expiry = None
                user.save(update_fields=['password', 'reset_token', 'reset_token_expiry'])
                return success_response(None, message="Mật khẩu đã được đặt lại thành công.")
            else:
                return Response({"success": False, "message": "Mã xác thực đã hết hạn (15 phút). Vui lòng yêu cầu mã mới."}, status=400)
        
        return Response({"success": False, "message": "Mã xác thực không hợp lệ hoặc không khớp."}, status=400)


class UserMeProfileView(APIView):
    """
    API Mobile & Web: Lấy hồ sơ cá nhân của người dùng hiện tại, bao gồm quyền hạn,
    năng lực thợ (kỹ năng, chứng chỉ, cấp bậc) và chốt trực phân xưởng.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        tenant = getattr(user, 'tenant', None)
        from django.utils import timezone
        today = timezone.now().date()

        # Collect roles and permissions
        roles = list(user.roles.values_list('name', flat=True))
        permissions = set()
        for role in user.roles.prefetch_related('permissions'):
            for perm in role.permissions.all():
                permissions.add(perm.id)

        # Check today's schedule for duty zone
        from users.models import TechnicianSchedule, TechnicianProfile, UserCertification
        schedule_today = TechnicianSchedule.objects.filter(
            tenant=tenant,
            user=user,
            work_date=today
        ).select_related('shift_template').first()

        tp = getattr(user, 'technician_profile', None)

        duty_zone_code = ''
        if schedule_today and schedule_today.duty_zone_id:
            duty_zone_code = schedule_today.duty_zone_id
        elif tp and tp.zone_id:
            duty_zone_code = tp.zone_id

        duty_zone_data = None
        if duty_zone_code:
            from assets.models import Location
            loc_obj = Location.objects.filter(tenant=tenant, code=duty_zone_code, is_active=True).first()
            if not loc_obj:
                try:
                    import uuid
                    loc_obj = Location.objects.filter(tenant=tenant, id=uuid.UUID(duty_zone_code)).first()
                except Exception:
                    loc_obj = None
            if loc_obj:
                duty_zone_data = {
                    "id": str(loc_obj.id),
                    "code": loc_obj.code or duty_zone_code,
                    "name": loc_obj.name,
                    "zoneType": loc_obj.zone_type,
                    "floorLevel": loc_obj.floor_level or 1,
                    "centerX": float(loc_obj.center_x or 0.0),
                    "centerY": float(loc_obj.center_y or 0.0),
                    "floorplanImage": loc_obj.floorplan_image or "",
                    "hasFloorplan": bool(loc_obj.floorplan_image),
                    "description": loc_obj.description or ""
                }
            else:
                duty_zone_data = {
                    "id": None,
                    "code": duty_zone_code,
                    "name": duty_zone_code,
                    "zoneType": "STANDARD",
                    "floorLevel": 1,
                    "centerX": 0.0,
                    "centerY": 0.0,
                    "floorplanImage": "",
                    "hasFloorplan": False,
                    "description": ""
                }

        # User certifications with valid status and countdown days
        certs_data = []
        user_certs = UserCertification.objects.filter(
            tenant=tenant,
            user=user
        ).select_related('certification_type')
        for uc in user_certs:
            days_rem = (uc.expiry_date - today).days if uc.expiry_date else None
            certs_data.append({
                "id": str(uc.id),
                "code": uc.certification_type.code,
                "name": uc.certification_type.name,
                "issuingBody": uc.certification_type.issuing_body,
                "expiryDate": uc.expiry_date.isoformat() if uc.expiry_date else None,
                "isValid": uc.is_valid,
                "daysRemaining": days_rem,
                "status": uc.status
            })

        tech_data = None
        if tp:
            tech_data = {
                "skillLevel": tp.skill_level,
                "skills": tp.skills or [],
                "certifications": certs_data,
                "dutyZone": duty_zone_data,
                "availabilityStatus": tp.availability_status,
                "isOnDuty": tp.is_on_duty and (schedule_today.status == 'ON_DUTY' if schedule_today else True),
                "coordsX": float(tp.coords_x or 0.0),
                "coordsY": float(tp.coords_y or 0.0),
                "floorLevel": tp.floor_level or 1
            }
        elif 'TECHNICIAN' in roles or duty_zone_data or certs_data:
            tech_data = {
                "skillLevel": 1,
                "skills": [],
                "certifications": certs_data,
                "dutyZone": duty_zone_data,
                "availabilityStatus": "AVAILABLE",
                "isOnDuty": True if schedule_today and schedule_today.status == 'ON_DUTY' else False,
                "coordsX": 0.0,
                "coordsY": 0.0,
                "floorLevel": 1
            }

        res_data = {
            "id": str(user.id),
            "username": user.username,
            "fullName": getattr(user, 'full_name', None) or user.username,
            "email": user.email,
            "tenantId": str(user.tenant_id) if user.tenant_id else None,
            "roles": roles,
            "permissions": sorted(list(permissions)),
            "technicianProfile": tech_data
        }
        return success_response(res_data)


class UserMeScheduleView(APIView):
    """
    API Mobile & Web: Lấy danh sách lịch trực ca cá nhân của Kỹ thuật viên
    theo khoảng thời gian start_date - end_date (hoặc mặc định 21 ngày gần nhất).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        tenant = getattr(user, 'tenant', None)
        from django.utils import timezone
        import datetime
        today = timezone.now().date()

        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')

        if start_date_str:
            try:
                start_date = datetime.date.fromisoformat(start_date_str)
            except ValueError:
                start_date = today - datetime.timedelta(days=7)
        else:
            start_date = today - datetime.timedelta(days=7)

        if end_date_str:
            try:
                end_date = datetime.date.fromisoformat(end_date_str)
            except ValueError:
                end_date = today + datetime.timedelta(days=14)
        else:
            end_date = today + datetime.timedelta(days=14)

        from users.models import TechnicianSchedule
        from assets.models import Location

        schedules = TechnicianSchedule.objects.filter(
            tenant=tenant,
            user=user,
            work_date__gte=start_date,
            work_date__lte=end_date
        ).select_related('shift_template').order_by('work_date')

        # Cache location details for duty zones
        locations_by_code = {}
        for loc in Location.objects.filter(tenant=tenant, is_active=True):
            if loc.code:
                locations_by_code[loc.code] = loc
            locations_by_code[str(loc.id)] = loc

        items = []
        for s in schedules:
            duty_zone_code = s.duty_zone_id or ""
            loc_obj = locations_by_code.get(duty_zone_code)
            if loc_obj:
                duty_zone_data = {
                    "id": str(loc_obj.id),
                    "code": loc_obj.code or duty_zone_code,
                    "name": loc_obj.name,
                    "zoneType": loc_obj.zone_type,
                    "floorLevel": loc_obj.floor_level or 1,
                    "centerX": float(loc_obj.center_x or 0.0),
                    "centerY": float(loc_obj.center_y or 0.0),
                    "floorplanImage": loc_obj.floorplan_image or "",
                    "hasFloorplan": bool(loc_obj.floorplan_image),
                    "description": loc_obj.description or ""
                }
            elif duty_zone_code:
                duty_zone_data = {
                    "id": None,
                    "code": duty_zone_code,
                    "name": duty_zone_code,
                    "zoneType": "STANDARD",
                    "floorLevel": 1,
                    "centerX": 0.0,
                    "centerY": 0.0,
                    "floorplanImage": "",
                    "hasFloorplan": False,
                    "description": ""
                }
            else:
                duty_zone_data = None

            shift_tmpl = s.shift_template
            shift_data = {
                "id": str(shift_tmpl.id) if shift_tmpl else None,
                "code": shift_tmpl.code if shift_tmpl else "",
                "name": shift_tmpl.name if shift_tmpl else s.status,
                "startTime": shift_tmpl.start_time.strftime('%H:%M') if shift_tmpl and shift_tmpl.start_time else "",
                "endTime": shift_tmpl.end_time.strftime('%H:%M') if shift_tmpl and shift_tmpl.end_time else "",
                "color": shift_tmpl.color_code if shift_tmpl else "#3b82f6"
            } if shift_tmpl else None

            items.append({
                "id": str(s.id),
                "date": s.work_date.isoformat(),
                "isToday": s.work_date == today,
                "status": s.status,
                "shift": shift_data,
                "dutyZone": duty_zone_data,
                "notes": s.notes or ""
            })

        return success_response(items)

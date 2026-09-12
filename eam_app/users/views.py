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

        # Java logic: Get the first active user across tenants (or all users by email)
        users = User.all_objects.filter(email=email)
        if users.exists():
            user = users.first()
            import random
            from django.utils import timezone
            import datetime

            code = f"{random.randint(0, 999999):06d}"
            user.reset_token = code
            user.reset_token_expiry = timezone.now() + datetime.timedelta(minutes=15)
            user.save()

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
                recipient_list=[email],
                fail_silently=False,
            )

        # Always return success for security (don't reveal if email exists)
        return success_response(None)

class ResetPasswordView(APIView):
    permission_classes = []

    @transaction.atomic
    def post(self, request):
        code = request.data.get('code')
        new_password = request.data.get('newPassword')

        if not code or not new_password:
            raise ValidationError("code and newPassword are required")

        # In Django, our token might not be unique if we didn't enforce it, 
        # but for this logic we just find the user with the valid token.
        from django.utils import timezone
        user = User.all_objects.filter(reset_token=code).first()

        if user:
            if user.reset_token_expiry and user.reset_token_expiry > timezone.now():
                user.set_password(new_password)
                user.reset_token = None
                user.reset_token_expiry = None
                user.save()
                return success_response(None)
            else:
                return Response({"success": False, "message": "Reset code has expired"}, status=400)
        
        return Response({"success": False, "message": "Invalid reset code"}, status=400)

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.db import transaction
from django.core.exceptions import ValidationError
from users.models import User, Role, Permission
from core.models import Tenant
from core.serializers import (
    TenantSerializer, SystemTenantCreateSerializer, 
    SystemTenantAdminRequestSerializer, UserSerializer
)

class SystemAdminPermission(IsAuthenticated):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        # Check if user has 'system:admin' permission
        # The user has roles -> permissions. We need to check all permissions.
        # However, since this is bypassed by TenantMiddleware, request.user might not be evaluated with a tenant correctly if it's outside.
        # But wait, TenantMiddleware EXEMPTS /api/v1/system.* !
        # This means TenantMiddleware clears the tenant context for system endpoints.
        # So User.objects.get() won't work unless we use all_objects!
        # DRF's JWTAuthentication sets request.user by querying the database.
        # If the default authentication rule uses User.objects.get(), and TenantContext is clear, 
        # it will query without tenant filter, which is fine because usernames are unique globally (User.objects without tenant filter would need User.all_objects).
        # Actually, if request.user is retrieved via JWT, we can check permissions.
        # Wait, DRF SimpleJWT gets user via `User.objects.get(id=...)`. Since TenantContext is empty for system endpoints, 
        # `TenantManager` returns `queryset` (all users) when `tenant_id` is None!
        # Let's verify `TenantManager` behavior:
        # def get_queryset(self):
        #     queryset = super().get_queryset()
        #     tenant_id = get_current_tenant()
        #     if tenant_id:
        #         return queryset.filter(tenant_id=tenant_id)
        #     return queryset
        # YES! If tenant_id is None, it returns all records. So `request.user` will be properly populated for system endpoints.
        
        has_system_admin = request.user.roles.filter(permissions__id='system:admin').exists()
        return has_system_admin

def success_response(data=None, message="Success"):
    return Response({
        "success": True,
        "message": message,
        "data": data
    }, status=status.HTTP_200_OK)

class SystemTenantListView(APIView):
    permission_classes = [SystemAdminPermission]

    def get(self, request):
        tenants = Tenant.objects.all()
        serializer = TenantSerializer(tenants, many=True)
        return success_response(serializer.data)

    @transaction.atomic
    def post(self, request):
        serializer = SystemTenantCreateSerializer(data=request.data)
        if not serializer.is_valid():
            raise ValidationError(serializer.errors)
        
        data = serializer.validated_data
        
        if Tenant.objects.filter(tenant_code=data['tenantCode']).exists():
            raise ValidationError("Tenant code already exists")
            
        tenant = Tenant.objects.create(
            name=data['name'],
            tenant_code=data['tenantCode'],
            service_plan=data.get('servicePlan', 'FREE'),
            timezone="UTC"
        )
        return success_response(TenantSerializer(tenant).data)

class SystemTenantDetailView(APIView):
    permission_classes = [SystemAdminPermission]

    @transaction.atomic
    def put(self, request, tenant_id):
        try:
            tenant = Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist:
            raise ValidationError("Tenant not found")
            
        name = request.data.get('name')
        service_plan = request.data.get('servicePlan')
        
        if name:
            tenant.name = name
        if service_plan:
            tenant.service_plan = service_plan
        tenant.save()
        return success_response(TenantSerializer(tenant).data)

class SystemTenantStatusView(APIView):
    permission_classes = [SystemAdminPermission]

    @transaction.atomic
    def put(self, request, tenant_id):
        if str(tenant_id) == "00000000-0000-0000-0000-000000000000":
            raise ValidationError("Cannot block the System Administration tenant")
            
        try:
            tenant = Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist:
            raise ValidationError("Tenant not found")
            
        tenant_status = request.data.get('status')
        if tenant_status:
            tenant.status = tenant_status
            tenant.save()
        return success_response(TenantSerializer(tenant).data)

class SystemTenantAdminListView(APIView):
    permission_classes = [SystemAdminPermission]

    def get(self, request, tenant_id):
        # Admins for the tenant are those users with role TENANT_ADMIN
        # Using all_objects since we are in a system endpoint with no tenant context
        users = User.all_objects.filter(tenant_id=tenant_id, roles__name='TENANT_ADMIN').distinct()
        serializer = UserSerializer(users, many=True)
        return success_response(serializer.data)

    @transaction.atomic
    def post(self, request, tenant_id):
        try:
            tenant = Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist:
            raise ValidationError("Tenant not found")

        serializer = SystemTenantAdminRequestSerializer(data=request.data)
        if not serializer.is_valid():
            raise ValidationError(serializer.errors)

        data = serializer.validated_data
        
        if User.all_objects.filter(username=data['username'], tenant_id=tenant_id).exists():
            raise ValidationError("Username already exists in this tenant")

        # Get or create TENANT_ADMIN role
        admin_role = Role.all_objects.filter(name='TENANT_ADMIN', tenant_id=tenant_id).first()
        if not admin_role:
            admin_role = Role.all_objects.create(
                name='TENANT_ADMIN',
                description='Administrator for Tenant',
                is_system=True,
                tenant_id=tenant_id
            )
            # Fetch all permissions except system:admin
            perms = Permission.objects.exclude(id='system:admin')
            admin_role.permissions.set(perms)

        user = User.all_objects.create_user(
            username=data['username'],
            email=data['username'],
            password=data['password'],
            tenant_id=tenant_id,
            status='ACTIVE'
        )
        user.roles.add(admin_role)

        # Send onboarding email
        from django.core.mail import send_mail
        from django.conf import settings
        
        login_link = "http://localhost:5173/login"
        message = (
            f"Welcome to the EAM System!\n\n"
            f"You have been added as an administrator for the tenant '{tenant.name}'.\n\n"
            f"Here are your login credentials:\n"
            f"Username: {data['username']}\n"
            f"Password: {data['password']}\n\n"
            f"Please click the link below to login:\n"
            f"{login_link}\n\n"
            f"We recommend changing your password after your first login."
        )
        
        send_mail(
            subject=f"EAM System - Admin Invitation for {tenant.name}",
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[data['username']],
            fail_silently=False,
        )

        return success_response(UserSerializer(user).data)

class SystemTenantAdminDetailView(APIView):
    permission_classes = [SystemAdminPermission]

    @transaction.atomic
    def put(self, request, tenant_id, admin_id):
        try:
            user = User.all_objects.get(id=admin_id, tenant_id=tenant_id)
        except User.DoesNotExist:
            raise ValidationError("Admin not found")
            
        username = request.data.get('username')
        password = request.data.get('password')
        
        if username:
            user.username = username
            user.email = username
        if password:
            user.set_password(password)
            
        user.save()
        return success_response(UserSerializer(user).data)

class SystemTenantAdminStatusView(APIView):
    permission_classes = [SystemAdminPermission]

    @transaction.atomic
    def put(self, request, tenant_id, admin_id):
        if str(admin_id) == "00000000-0000-0000-0000-000000000000":
            raise ValidationError("Cannot block the Super Admin")
            
        try:
            user = User.all_objects.get(id=admin_id, tenant_id=tenant_id)
        except User.DoesNotExist:
            raise ValidationError("Admin not found")
            
        user_status = request.data.get('status')
        if user_status:
            user.status = user_status
            user.save()
            
        return success_response(UserSerializer(user).data)

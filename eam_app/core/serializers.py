from rest_framework import serializers
from core.models import Tenant
from users.models import User

class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = ['id', 'name', 'logo_url', 'timezone', 'tenant_code', 'service_plan', 'status', 'created_at', 'updated_at']

class SystemTenantCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    tenantCode = serializers.CharField(max_length=100)
    servicePlan = serializers.CharField(max_length=50, default="FREE")

class SystemTenantAdminRequestSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=255)
    password = serializers.CharField(max_length=255)

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'status', 'created_at', 'updated_at']

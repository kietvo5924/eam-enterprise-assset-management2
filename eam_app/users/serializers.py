from rest_framework import serializers
from users.models import Role, Permission, User

class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ['id', 'name', 'description']

class RoleSerializer(serializers.ModelSerializer):
    permissions = PermissionSerializer(many=True, read_only=True)
    
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)
    isSystem = serializers.BooleanField(source='is_system', read_only=True)

    class Meta:
        model = Role
        fields = ['id', 'name', 'description', 'isSystem', 'permissions', 'createdAt', 'updatedAt']

class RoleCreateUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    description = serializers.CharField(max_length=255, required=False, allow_blank=True)
    permissionIds = serializers.ListField(
        child=serializers.CharField(max_length=100),
        allow_empty=True
    )

class UserSerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField()
    roleIds = serializers.SerializerMethodField()

    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'status', 'roles', 'roleIds', 'createdAt', 'updatedAt']

    def get_roles(self, obj):
        return [role.name for role in obj.roles.all()]

    def get_roleIds(self, obj):
        return [str(role.id) for role in obj.roles.all()]

class UserCreateRequestSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=255)
    email = serializers.EmailField()
    password = serializers.CharField(max_length=255)
    roleIds = serializers.ListField(
        child=serializers.UUIDField(),
        allow_empty=True,
        required=False
    )

class UserUpdateRequestSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=255, required=False)
    roleIds = serializers.ListField(
        child=serializers.UUIDField(),
        allow_empty=True,
        required=False
    )

class UserInviteRequestSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=255)
    email = serializers.EmailField()
    password = serializers.CharField(max_length=255)
    roleIds = serializers.ListField(
        child=serializers.UUIDField(),
        allow_empty=True,
        required=False
    )


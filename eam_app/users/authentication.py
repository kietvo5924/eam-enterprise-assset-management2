from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.response import Response
from rest_framework import status

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        # We override validate to mimic the Java backend's login logic
        username = attrs.get(self.username_field)
        password = attrs.get('password')

        from users.models import User
        
        # In Java, it iterates over all tenants to find the user.
        # In Django, we can just query all_objects to bypass tenant filter
        user = User.all_objects.filter(username=username).first()
        
        if user and user.check_password(password):
            tenant = user.tenant
            if tenant.status == 'INACTIVE':
                return {'error': 'Organization account is currently locked or inactive'}
            if user.status == 'INACTIVE':
                return {'error': 'User account is inactive'}
            
            # Generate token
            refresh = self.get_token(user)
            access_token = refresh.access_token
            
            # Roles and permissions
            roles_str = ",".join(user.roles.values_list('name', flat=True))
            perms_set = set()
            for role in user.roles.prefetch_related('permissions').all():
                for perm in role.permissions.all():
                    perms_set.add(perm.id)
            perms_str = ",".join(perms_set)
            
            return {
                'token': str(access_token),
                'tenantId': str(tenant.id),
                'roles': roles_str,
                'permissions': perms_str
            }
        
        return {'error': 'Account does not exist' if not user else 'Incorrect password'}

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['tenantId'] = str(user.tenant_id)
        token['username'] = user.username
        token['userId'] = str(user.id)
        return token

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=False)
        
        data = serializer.validated_data
        
        if data and 'error' in data:
            return Response({
                "success": False,
                "message": data['error'],
                "data": None
            }, status=status.HTTP_200_OK) # Java usually returns 200 with error message in ApiResponse
            
        if data is None:
             return Response({
                "success": False,
                "message": "Account does not exist",
                "data": None
            }, status=status.HTTP_200_OK)
            
        return Response({
            "success": True,
            "message": "Success",
            "data": data
        }, status=status.HTTP_200_OK)

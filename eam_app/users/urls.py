# pyrefly: ignore [missing-import]
from django.urls import path
from users.authentication import CustomTokenObtainPairView
# pyrefly: ignore [missing-import]
from rest_framework_simplejwt.views import TokenRefreshView
from users.views import (
    RoleListView, RoleDetailView, PermissionListView,
    UserListView, UserDetailView, UserDisableView, UserEnableView,
    UserInviteView, UserImportView,
    ChangePasswordView, ForgotPasswordView, ResetPasswordView
)

urlpatterns = [
    path('auth/login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/change-password/', ChangePasswordView.as_view(), name='auth_change_password'),
    path('auth/forgot-password/', ForgotPasswordView.as_view(), name='auth_forgot_password'),
    path('auth/reset-password/', ResetPasswordView.as_view(), name='auth_reset_password'),
    
    path('roles', RoleListView.as_view(), name='role_list'),
    path('roles/<uuid:role_id>', RoleDetailView.as_view(), name='role_detail'),
    
    path('permissions', PermissionListView.as_view(), name='permission_list'),
    
    path('users', UserListView.as_view(), name='user_list'),
    path('users/<uuid:user_id>', UserDetailView.as_view(), name='user_detail'),
    path('users/<uuid:user_id>/disable', UserDisableView.as_view(), name='user_disable'),
    path('users/<uuid:user_id>/enable', UserEnableView.as_view(), name='user_enable'),
    
    path('users/invite', UserInviteView.as_view(), name='user_invite'),
    path('users/import', UserImportView.as_view(), name='user_import'),
]

from django.urls import path, re_path
from users.authentication import CustomTokenObtainPairView, CustomTokenRefreshView
from users.views import (
    RoleListView, RoleDetailView, PermissionListView,
    UserListView, UserDetailView, UserDisableView, UserEnableView,
    UserInviteView, UserImportView,
    ChangePasswordView, ForgotPasswordView, ResetPasswordView
)

urlpatterns = [
    re_path(r'^auth/login/?$', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    re_path(r'^auth/refresh/?$', CustomTokenRefreshView.as_view(), name='token_refresh'),
    re_path(r'^auth/change-password/?$', ChangePasswordView.as_view(), name='auth_change_password'),
    re_path(r'^auth/forgot-password/?$', ForgotPasswordView.as_view(), name='auth_forgot_password'),
    re_path(r'^auth/reset-password/?$', ResetPasswordView.as_view(), name='auth_reset_password'),
    
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

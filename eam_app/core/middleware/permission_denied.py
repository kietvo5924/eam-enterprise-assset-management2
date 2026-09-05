import re
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import render
from django.utils.deprecation import MiddlewareMixin

class PermissionDeniedMiddleware(MiddlewareMixin):
    """
    Middleware that intercepts PermissionDenied exceptions to return:
    - A polished, branded HTML 403 error page for web browser navigation.
    - A JSON response for API or AJAX fetch requests.
    Works seamlessly in both DEBUG=True and production environments.
    """
    def process_exception(self, request, exception):
        if not isinstance(exception, PermissionDenied):
            return None

        is_ajax = (
            request.headers.get('x-requested-with') == 'XMLHttpRequest' or
            'application/json' in request.headers.get('Accept', '') or
            request.content_type == 'application/json' or
            request.path.startswith('/api/')
        )

        error_msg = str(exception) or "Bạn không có quyền truy cập tài nguyên này."

        if is_ajax:
            return JsonResponse({
                'success': False,
                'error': error_msg,
                'code': 'PERMISSION_DENIED',
            }, status=403)

        # Extract required permission if available (e.g. "... (user:read required).")
        match = re.search(r'\((.*?)\s+required\)', error_msg)
        required_perm = match.group(1) if match else None

        # Friendly permission names mapping
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

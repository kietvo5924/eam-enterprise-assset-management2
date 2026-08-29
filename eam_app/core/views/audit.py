from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.db import models
from django.utils.dateparse import parse_datetime
from django.core.paginator import Paginator
from core.models import AuditLog
from users.permissions import HasPermission

def success_response(data=None, message="Success"):
    return Response({
        "success": True,
        "message": message,
        "data": data
    }, status=status.HTTP_200_OK)

class AuditLogListView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        if not HasPermission('audit_logs:read')().has_permission(request, self):
            self.permission_denied(request)
            
        tenant = request.user.tenant
        
        username = request.query_params.get('username')
        action_type = request.query_params.get('actionType')
        entity_type = request.query_params.get('entityType')
        start_date_str = request.query_params.get('startDate')
        end_date_str = request.query_params.get('endDate')
        
        try:
            page = int(request.query_params.get('page', 0))
            size = int(request.query_params.get('size', 20))
        except ValueError:
            page, size = 0, 20
            
        sort_by = request.query_params.get('sortBy', 'timestamp')
        sort_dir = request.query_params.get('sortDir', 'DESC')
        
        qs = AuditLog.objects.filter(tenant=tenant)
        
        if username:
            # Join with User model (via all_objects just in case)
            from users.models import User
            users = User.objects.filter(username__icontains=username, tenant=tenant)
            user_ids = [str(u.id) for u in users]
            qs = qs.filter(user_id__in=user_ids)
            
        if action_type:
            qs = qs.filter(action_type=action_type)
        if entity_type:
            qs = qs.filter(entity_type=entity_type)
            
        if start_date_str:
            start_date = parse_datetime(start_date_str)
            if start_date:
                qs = qs.filter(timestamp__gte=start_date)
                
        if end_date_str:
            end_date = parse_datetime(end_date_str)
            if end_date:
                qs = qs.filter(timestamp__lte=end_date)
                
        # Handle sorting
        if sort_dir.upper() == 'DESC':
            sort_by = f"-{sort_by}"
            
        qs = qs.order_by(sort_by)
        
        paginator = Paginator(qs, size)
        
        # Django paginator is 1-indexed, our page is 0-indexed
        page_obj = paginator.get_page(page + 1)
        
        content = []
        for log in page_obj.object_list:
            from users.models import User
            # Resolve username safely
            uname = None
            if log.user_id:
                try:
                    u = User.all_objects.get(id=log.user_id)
                    uname = u.username
                except (User.DoesNotExist, ValueError):
                    uname = log.user_id if log.user_id == 'system' else None
                    
            content.append({
                "id": str(log.id),
                "tenantId": str(log.tenant_id) if log.tenant_id else None,
                "userId": log.user_id,
                "username": uname,
                "actionType": log.action_type,
                "entityType": log.entity_type,
                "entityId": log.entity_id,
                "timestamp": log.timestamp.isoformat() if log.timestamp else None
            })
            
        return success_response({
            "content": content,
            "currentPage": page,
            "totalElements": paginator.count,
            "totalPages": paginator.num_pages
        })

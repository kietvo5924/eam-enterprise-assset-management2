from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone

from assets.views import success_response
from notifications.models import Notification, NotificationPreference, DevicePushToken
from notifications.serializers import (
    NotificationSerializer,
    NotificationPreferenceSerializer,
    DevicePushTokenSerializer
)


class NotificationListView(APIView):
    """
    List notifications for authenticated user with multi-tenant isolation,
    filtering by read status, actionable status, category, severity, and pagination.
    Anti-IDOR: Scoped exclusively to request.user within the active tenant.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tenant = getattr(request.user, 'tenant', None)
        qs = Notification.objects.filter(
            recipient=request.user,
            is_deleted=False
        )
        if tenant:
            qs = qs.filter(tenant=tenant)

        # Filter by read status
        unread_only = request.query_params.get('unread_only', '').strip().lower() in ('true', '1')
        is_read_param = request.query_params.get('is_read', '').strip().lower()
        if unread_only or is_read_param in ('false', '0'):
            qs = qs.filter(is_read=False)
        elif is_read_param in ('true', '1'):
            qs = qs.filter(is_read=True)

        # Filter by actionable status (Rule 7)
        is_actionable_param = request.query_params.get('is_actionable', '').strip().lower()
        if is_actionable_param in ('true', '1'):
            qs = qs.filter(is_actionable=True)
        elif is_actionable_param in ('false', '0'):
            qs = qs.filter(is_actionable=False)

        action_status_param = request.query_params.get('action_status', '').strip().upper()
        if action_status_param:
            qs = qs.filter(action_status=action_status_param)

        # Filter by category
        category_param = request.query_params.get('category', '').strip().upper()
        if category_param:
            qs = qs.filter(category=category_param)

        # Filter by severity
        severity_param = request.query_params.get('severity', '').strip().upper()
        if severity_param:
            qs = qs.filter(severity=severity_param)

        # Calculate unread count for badge indicators
        unread_count = Notification.objects.filter(
            recipient=request.user,
            is_read=False,
            is_deleted=False
        ).count()

        # Pagination
        try:
            page = max(0, int(request.query_params.get('page', 0)))
            size = max(1, int(request.query_params.get('size', 20)))
        except (ValueError, TypeError):
            page = 0
            size = 20

        total_elements = qs.count()
        total_pages = (total_elements + size - 1) // size if size > 0 else 1
        is_last = (page + 1) >= total_pages or total_elements == 0

        start = page * size
        end = start + size
        paged_items = qs[start:end]

        serializer = NotificationSerializer(paged_items, many=True)
        return success_response({
            "content": serializer.data,
            "unread_count": unread_count,
            "unreadCount": unread_count,
            "totalElements": total_elements,
            "totalPages": total_pages,
            "page": page,
            "size": size,
            "last": is_last
        })


class NotificationUnreadCountView(APIView):
    """
    Lightweight polling endpoint returning unread count and critical alert indicator.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tenant = getattr(request.user, 'tenant', None)
        base_qs = Notification.objects.filter(
            recipient=request.user,
            is_read=False,
            is_deleted=False
        )
        if tenant:
            base_qs = base_qs.filter(tenant=tenant)

        unread_count = base_qs.count()
        has_critical = base_qs.filter(severity='CRITICAL').exists()

        return success_response({
            "unread_count": unread_count,
            "unreadCount": unread_count,
            "has_critical": has_critical
        })


class NotificationMarkAsReadView(APIView):
    """
    Mark a single notification as read by ID.
    Anti-IDOR: Rejects requests if notification does not belong to request.user (returns 404).
    """
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, notification_id):
        tenant = getattr(request.user, 'tenant', None)
        lookup = {'id': notification_id, 'recipient': request.user}
        if tenant:
            lookup['tenant'] = tenant

        notification = get_object_or_404(Notification, **lookup)
        notification.mark_as_read(save=True)
        serializer = NotificationSerializer(notification)
        return success_response(serializer.data, message="Notification marked as read")


class NotificationMarkAllAsReadView(APIView):
    """
    Mark all unread notifications of the currently authenticated user as read.
    Optionally filters by category in request body.
    """
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        tenant = getattr(request.user, 'tenant', None)
        qs = Notification.objects.filter(
            recipient=request.user,
            is_read=False,
            is_deleted=False
        )
        if tenant:
            qs = qs.filter(tenant=tenant)

        category = request.data.get('category') if isinstance(request.data, dict) else None
        if category:
            qs = qs.filter(category=category.strip().upper())

        updated_count = qs.update(is_read=True, read_at=timezone.now())

        return success_response({
            "updated_count": updated_count,
            "updatedCount": updated_count
        }, message="All notifications marked as read")


class NotificationResolveActionView(APIView):
    """
    Resolve or update actionable notification state (Rule 7).
    """
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, notification_id):
        tenant = getattr(request.user, 'tenant', None)
        lookup = {'id': notification_id, 'recipient': request.user}
        if tenant:
            lookup['tenant'] = tenant

        notification = get_object_or_404(Notification, **lookup)
        status_to_set = request.data.get('action_status', 'RESOLVED').strip().upper()
        if status_to_set not in ('PENDING', 'RESOLVED', 'EXPIRED'):
            status_to_set = 'RESOLVED'

        notification.resolve_action(status=status_to_set, save=True)
        serializer = NotificationSerializer(notification)
        return success_response(serializer.data, message=f"Action marked as {status_to_set}")


class NotificationDeleteView(APIView):
    """
    Soft-delete a notification (Rule 4).
    Anti-IDOR: Rejects requests if notification does not belong to request.user.
    """
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def delete(self, request, notification_id):
        tenant = getattr(request.user, 'tenant', None)
        lookup = {'id': notification_id, 'recipient': request.user}
        if tenant:
            lookup['tenant'] = tenant

        notification = get_object_or_404(Notification, **lookup)
        notification.is_deleted = True
        notification.save(update_fields=['is_deleted'])
        return success_response({"success": True}, message="Notification deleted")


class NotificationPreferenceView(APIView):
    """
    Get or update user delivery channel preferences and OOO delegation (Rule 5).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tenant = getattr(request.user, 'tenant', None)
        pref, _ = NotificationPreference.objects.get_or_create(
            user=request.user,
            tenant=tenant,
            category='ALL'
        )
        serializer = NotificationPreferenceSerializer(pref)
        return success_response(serializer.data)

    @transaction.atomic
    def put(self, request):
        tenant = getattr(request.user, 'tenant', None)
        pref, _ = NotificationPreference.objects.get_or_create(
            user=request.user,
            tenant=tenant,
            category='ALL'
        )

        data = request.data or {}
        if 'in_app_enabled' in data:
            pref.in_app_enabled = bool(data['in_app_enabled'])
        if 'email_enabled' in data:
            pref.email_enabled = bool(data['email_enabled'])
        if 'push_enabled' in data:
            pref.push_enabled = bool(data['push_enabled'])
        if 'quiet_hours_start' in data:
            pref.quiet_hours_start = data['quiet_hours_start'] or None
        if 'quiet_hours_end' in data:
            pref.quiet_hours_end = data['quiet_hours_end'] or None
        if 'is_out_of_office' in data:
            pref.is_out_of_office = bool(data['is_out_of_office'])
        if 'delegated_to_user' in data:
            del_id = data['delegated_to_user']
            if del_id:
                pref.delegated_to_user_id = del_id
            else:
                pref.delegated_to_user = None

        pref.save()
        serializer = NotificationPreferenceSerializer(pref)
        return success_response(serializer.data, message="Notification preferences updated")


class DevicePushTokenView(APIView):
    """
    Register or refresh a mobile FCM / APNs device push token (Section 4.1 C & 4.2).
    """
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        token = request.data.get('device_token', '').strip()
        device_type = request.data.get('device_type', 'ANDROID').strip().upper()

        if not token:
            return success_response({"success": False, "error": "device_token is required"}, message="Missing device token")

        tenant = getattr(request.user, 'tenant', None)
        token_obj, created = DevicePushToken.all_objects.update_or_create(
            user=request.user,
            device_token=token,
            defaults={
                'tenant': tenant,
                'device_type': device_type if device_type in ('ANDROID', 'IOS', 'WEB') else 'ANDROID',
                'is_active': True
            }
        )

        serializer = DevicePushTokenSerializer(token_obj)
        return success_response(serializer.data, message="Device registered successfully")

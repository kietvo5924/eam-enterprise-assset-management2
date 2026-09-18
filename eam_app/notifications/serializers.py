from rest_framework import serializers
from notifications.models import Notification, NotificationPreference, DevicePushToken


class NotificationSerializer(serializers.ModelSerializer):
    recipientId = serializers.UUIDField(source='recipient.id', read_only=True)
    recipientUsername = serializers.CharField(source='recipient.username', read_only=True)
    tenantId = serializers.UUIDField(source='tenant.id', read_only=True)
    isRead = serializers.BooleanField(source='is_read', read_only=True)
    readAt = serializers.DateTimeField(source='read_at', read_only=True)
    isActionable = serializers.BooleanField(source='is_actionable', read_only=True)
    actionStatus = serializers.CharField(source='action_status', read_only=True)
    actionResolvedAt = serializers.DateTimeField(source='action_resolved_at', read_only=True)
    eventType = serializers.CharField(source='event_type', read_only=True)
    occurrenceCount = serializers.IntegerField(source='occurrence_count', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)
    sender = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            'id',
            'title',
            'message',
            'link',
            'category',
            'severity',
            'event_type',
            'metadata',
            'is_read',
            'read_at',
            'is_actionable',
            'action_status',
            'action_resolved_at',
            'escalation_level',
            'occurrence_count',
            'created_at',
            'updated_at',
            # CamelCase parity aliases for Web & Mobile
            'sender',
            'eventType',
            'isRead',
            'readAt',
            'isActionable',
            'actionStatus',
            'actionResolvedAt',
            'occurrenceCount',
            'createdAt',
            'updatedAt',
            'recipientId',
            'recipientUsername',
            'tenantId'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'tenant', 'recipient', 'sender']

    def get_sender(self, obj):
        """Safe sender serialization with snapshot fallback (Rule 8 & TC-SNAPSHOT-01)."""
        if obj.sender:
            role = obj.sender_role_snapshot
            if not role and hasattr(obj.sender, 'roles') and obj.sender.roles.exists():
                role = obj.sender.roles.first().name
            return {
                "id": str(obj.sender.id),
                "name": obj.sender.username,
                "role": role or "USER"
            }
        elif obj.sender_name_snapshot:
            return {
                "id": None,
                "name": obj.sender_name_snapshot,
                "role": obj.sender_role_snapshot or "USER"
            }
        return None


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    delegatedToUsername = serializers.CharField(source='delegated_to_user.username', read_only=True)

    class Meta:
        model = NotificationPreference
        fields = [
            'id',
            'category',
            'in_app_enabled',
            'email_enabled',
            'push_enabled',
            'quiet_hours_start',
            'quiet_hours_end',
            'is_out_of_office',
            'delegated_to_user',
            'delegatedToUsername'
        ]
        read_only_fields = ['id']


class DevicePushTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = DevicePushToken
        fields = [
            'id',
            'device_token',
            'device_type',
            'is_active',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

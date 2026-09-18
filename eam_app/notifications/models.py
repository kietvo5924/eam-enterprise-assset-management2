import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from core.models import BaseTenantModel


class Notification(BaseTenantModel):
    """
    Real-time notification model supporting multi-tenancy scoping,
    recipient tracking, sender snapshots, read/unread states, action workflows,
    and SLA-based escalation.
    """
    SEVERITY_CHOICES = (
        ('INFO', 'Information'),
        ('WARNING', 'Warning'),
        ('URGENT', 'Urgent'),
        ('CRITICAL', 'Critical'),
    )

    ACTION_STATUS_CHOICES = (
        ('NOT_APPLICABLE', 'Not Applicable'),
        ('PENDING', 'Pending Action'),
        ('RESOLVED', 'Resolved'),
        ('EXPIRED', 'Expired'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        db_column='recipient_id'
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sent_notifications',
        db_column='sender_id'
    )
    sender_name_snapshot = models.CharField(max_length=150, blank=True, default='')
    sender_role_snapshot = models.CharField(max_length=64, blank=True, default='')

    event_type = models.CharField(max_length=64, default='GENERAL', db_index=True)
    category = models.CharField(max_length=32, default='SYSTEM', db_index=True)
    severity = models.CharField(max_length=16, choices=SEVERITY_CHOICES, default='INFO', db_index=True)

    title = models.CharField(max_length=255)
    message = models.TextField()
    link = models.CharField(max_length=500, null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    is_actionable = models.BooleanField(default=False, db_index=True)
    action_status = models.CharField(max_length=20, choices=ACTION_STATUS_CHOICES, default='NOT_APPLICABLE', db_index=True)
    action_resolved_at = models.DateTimeField(null=True, blank=True)

    escalation_level = models.SmallIntegerField(default=0)
    escalate_at = models.DateTimeField(null=True, blank=True, db_index=True)
    occurrence_count = models.IntegerField(default=1)
    is_deleted = models.BooleanField(default=False, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['tenant', 'recipient', 'is_read', '-created_at'], name='notif_ten_rec_read_idx'),
            models.Index(fields=['recipient', 'is_actionable', 'action_status'], name='notif_rec_act_idx'),
            models.Index(fields=['severity', 'is_read', 'escalate_at'], name='notif_esc_scan_idx'),
            models.Index(fields=['recipient', '-created_at'], name='notif_recip_created_idx'),
        ]

    def __str__(self):
        status = "Read" if self.is_read else "Unread"
        username = self.recipient.username if self.recipient else "Unknown"
        return f"[{status}][{self.severity}] {self.title} -> {username}"

    def clean(self):
        super().clean()
        if self.recipient_id and self.tenant_id:
            recipient_tenant_id = getattr(self.recipient, 'tenant_id', None)
            if recipient_tenant_id and str(recipient_tenant_id) != str(self.tenant_id):
                raise ValidationError({
                    'recipient': 'Notification recipient must belong to the same tenant.'
                })

    def save(self, *args, **kwargs):
        # Auto-set tenant from recipient if not explicitly set and not in context
        if not self.tenant_id and self.recipient_id:
            recipient_tenant_id = getattr(self.recipient, 'tenant_id', None)
            if recipient_tenant_id:
                self.tenant_id = recipient_tenant_id

        # Sender snapshotting to prevent NULL issues if sender user is deleted
        if self.sender and not self.sender_name_snapshot:
            self.sender_name_snapshot = self.sender.username
        if self.sender and not self.sender_role_snapshot:
            # Pick first role name if user has roles assigned
            first_role = self.sender.roles.first() if hasattr(self.sender, 'roles') else None
            self.sender_role_snapshot = first_role.name if first_role else 'USER'

        self.clean()
        super().save(*args, **kwargs)

    def mark_as_read(self, save=True):
        """Mark this notification as read and record timestamp."""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            if save:
                self.save(update_fields=['is_read', 'read_at', 'updated_at'])

    def resolve_action(self, status='RESOLVED', save=True):
        """Update actionable lifecycle state."""
        self.action_status = status
        self.action_resolved_at = timezone.now()
        if save:
            self.save(update_fields=['action_status', 'action_resolved_at', 'updated_at'])


class NotificationPreference(BaseTenantModel):
    """
    Per-user notification delivery channel preferences and Out-Of-Office (OOO) delegation.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_preferences',
        db_column='user_id'
    )
    category = models.CharField(max_length=32, default='ALL')
    in_app_enabled = models.BooleanField(default=True)
    email_enabled = models.BooleanField(default=True)
    push_enabled = models.BooleanField(default=True)
    quiet_hours_start = models.TimeField(null=True, blank=True)
    quiet_hours_end = models.TimeField(null=True, blank=True)

    is_out_of_office = models.BooleanField(default=False)
    delegated_to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='delegated_preferences',
        db_column='delegated_to_user_id'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'notification_preferences'
        unique_together = (('user', 'tenant', 'category'),)

    def __str__(self):
        username = self.user.username if self.user else "Unknown"
        return f"Preferences({username} - {self.category})"


class DevicePushToken(BaseTenantModel):
    """
    Registers mobile FCM / APNs device tokens for push notifications.
    """
    DEVICE_TYPE_CHOICES = (
        ('ANDROID', 'Android'),
        ('IOS', 'iOS'),
        ('WEB', 'Web'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='device_push_tokens',
        db_column='user_id'
    )
    device_token = models.TextField()
    device_type = models.CharField(max_length=16, choices=DEVICE_TYPE_CHOICES, default='ANDROID')
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'device_push_tokens'
        unique_together = (('user', 'device_token'),)

    def __str__(self):
        username = self.user.username if self.user else "Unknown"
        return f"DeviceToken({username} - {self.device_type} - Active: {self.is_active})"

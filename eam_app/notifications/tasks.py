import os
import logging
from celery import shared_task
from django.conf import settings
from django.utils import timezone
from django.core.mail import send_mail
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()

# Global Firebase initialization helper
_firebase_initialized = False

def get_firebase_app():
    global _firebase_initialized
    if _firebase_initialized:
        return True

    try:
        import firebase_admin
        from firebase_admin import credentials
        if firebase_admin._apps:
            _firebase_initialized = True
            return True

        cred_path = getattr(settings, 'FIREBASE_CREDENTIALS_PATH', None)
        if cred_path and os.path.exists(cred_path):
            cred = credentials.Certificate(str(cred_path))
            firebase_admin.initialize_app(cred)
            _firebase_initialized = True
            logger.info("Firebase Admin SDK initialized successfully in worker.")
            return True
        else:
            logger.warning(f"Firebase credentials file not found at {cred_path}")
            return False
    except Exception as e:
        logger.error(f"Failed to initialize Firebase Admin SDK: {e}", exc_info=True)
        return False


@shared_task(name="notifications.async_send_notification")
def async_send_notification(recipient_id, tenant_id, title, message, link=None):
    """
    Celery asynchronous task to dispatch notifications in background worker (backward compatibility).
    """
    from core.models import Tenant
    from notifications.services import send_notification
    try:
        recipient = User.all_objects.get(id=recipient_id)
        tenant = Tenant.objects.get(id=tenant_id)
        return send_notification(recipient, title, message, link=link, tenant=tenant) is not None
    except Exception as e:
        logger.error(f"Error in async_send_notification task: {e}", exc_info=True)
        return False


@shared_task(
    bind=True,
    max_retries=3,
    name="notifications.async_dispatch_notification_channels"
)
def async_dispatch_notification_channels(self, notification_id):
    """
    Multi-channel background dispatcher (Push Notification via FCM & Email via SMTP).
    Includes Exponential Backoff Retry policy (10s, 60s, 300s) and AuditLog fallback (Section 6.2).
    """
    from notifications.models import Notification, NotificationPreference, DevicePushToken

    try:
        notification = Notification.all_objects.select_related('recipient', 'tenant').get(id=notification_id)
    except Notification.DoesNotExist:
        logger.warning(f"Notification {notification_id} does not exist. Skipping channel dispatch.")
        return False

    recipient = notification.recipient
    tenant = notification.tenant
    severity = notification.severity

    # 1. Fetch recipient preferences
    pref = NotificationPreference.all_objects.filter(
        user=recipient,
        tenant=tenant,
        category__in=[notification.category, 'ALL']
    ).first()

    push_enabled = pref.push_enabled if pref else True
    email_enabled = pref.email_enabled if pref else True

    # 2. Check Quiet Hours (Rule: CRITICAL bypasses quiet hours)
    if pref and pref.quiet_hours_start and pref.quiet_hours_end and severity != 'CRITICAL':
        now_time = timezone.localtime().time()
        start = pref.quiet_hours_start
        end = pref.quiet_hours_end
        in_quiet = (start <= now_time <= end) if start <= end else (now_time >= start or now_time <= end)
        if in_quiet:
            logger.info(f"Skipping Push/Email for notification {notification_id}: Recipient {recipient.username} is in quiet hours.")
            return True

    # 3. Mobile Push Notification via Firebase FCM
    if push_enabled:
        tokens = list(DevicePushToken.all_objects.filter(user=recipient, is_active=True).values_list('device_token', flat=True))
        if tokens:
            firebase_ready = get_firebase_app()
            if firebase_ready:
                try:
                    from firebase_admin import messaging
                    messages = [
                        messaging.Message(
                            notification=messaging.Notification(
                                title=notification.title,
                                body=notification.message[:250],
                            ),
                            data={
                                'notification_id': str(notification.id),
                                'event_type': notification.event_type,
                                'severity': notification.severity,
                                'link': notification.link or '',
                            },
                            token=tok
                        )
                        for tok in tokens
                    ]
                    response = messaging.send_each(messages)
                    logger.info(f"FCM batch sent for notif {notification_id}: {response.success_count} success, {response.failure_count} failures.")
                except Exception as exc:
                    logger.error(f"FCM Push failed for notif {notification_id}: {exc}")
                    # Exponential backoff retry: 10s, 60s, 300s
                    retry_backoffs = [10, 60, 300]
                    retries = self.request.retries
                    countdown = retry_backoffs[min(retries, len(retry_backoffs) - 1)]

                    if retries < self.max_retries:
                        raise self.retry(exc=exc, countdown=countdown)
                    else:
                        # After 3 failures: Record in AuditLog without failing worker
                        try:
                            from core.models import AuditLog
                            AuditLog.all_objects.create(
                                tenant=tenant,
                                user_id='SYSTEM',
                                action_type='PUSH_FAILED',
                                entity_type='Notification',
                                entity_id=str(notification.id)
                            )
                        except Exception as log_ex:
                            logger.error(f"Failed to create AuditLog on push failure: {log_ex}")

    # 4. Email Dispatch for URGENT / CRITICAL
    if email_enabled and severity in ('URGENT', 'CRITICAL') and getattr(recipient, 'email', None):
        try:
            subject = f"[{severity}] {notification.title}"
            body = (
                f"Kính gửi {recipient.username},\n\n"
                f"Hệ thống EAM ghi nhận cảnh báo mức độ {severity}:\n"
                f"Tiêu đề: {notification.title}\n"
                f"Nội dung: {notification.message}\n"
                f"Đường dẫn xử lý: {notification.link or 'N/A'}\n"
                f"Thời điểm phát sinh: {notification.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
                f"Trân trọng,\nĐội ngũ Kỹ thuật EAM"
            )
            send_mail(
                subject=subject,
                message=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient.email],
                fail_silently=True
            )
            logger.info(f"Dispatched alert email for notif {notification_id} to {recipient.email}")
        except Exception as e:
            logger.error(f"Failed to send email alert for notif {notification_id}: {e}")

    return True


@shared_task(name="notifications.periodic_escalation_scan")
def periodic_escalation_scan():
    """
    Celery Beat Periodic Task (Rule 6 & TC-ESCALATE-01).
    Scans for unread CRITICAL/URGENT alerts that passed escalate_at SLA deadline and triggers WO_ESCALATED.
    """
    from notifications.models import Notification
    from notifications.services import notify_escalation_alert

    now = timezone.now()
    overdue_notifs = Notification.all_objects.filter(
        severity__in=['CRITICAL', 'URGENT'],
        is_read=False,
        escalation_level=0,
        escalate_at__isnull=False,
        escalate_at__lte=now,
        is_deleted=False
    ).select_related('tenant', 'recipient')

    count = overdue_notifs.count()
    if count == 0:
        return "No overdue escalations found."

    logger.info(f"Escalation scanner found {count} overdue SLA notifications.")
    escalated_count = 0

    for notif in overdue_notifs:
        try:
            notify_escalation_alert(notif)
            notif.escalation_level = 1
            notif.save(update_fields=['escalation_level', 'updated_at'])
            escalated_count += 1
            logger.info(f"Escalated notification {notif.id} [{notif.event_type}]")
        except Exception as e:
            logger.error(f"Failed to escalate notification {notif.id}: {e}", exc_info=True)

    return f"Escalated {escalated_count} notifications."

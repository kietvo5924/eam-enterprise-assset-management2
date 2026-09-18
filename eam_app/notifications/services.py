import logging
from django.utils import timezone
from django.db import models
from django.core.cache import cache
from django.contrib.auth import get_user_model
from notifications.models import Notification, NotificationPreference

logger = logging.getLogger(__name__)
User = get_user_model()


class NotificationRouter:
    """
    Role-Based Notification Router (Rule 3).
    Collects and filters recipients based on organizational roles and active status.
    """

    @staticmethod
    def filter_active_users(users_qs):
        """Ensure recipient accounts are active (Rule 3 & TC-EDGE-02)."""
        return [u for u in users_qs if getattr(u, 'status', 'ACTIVE') == 'ACTIVE' and getattr(u, 'is_active', True)]

    @staticmethod
    def get_maintenance_managers(tenant_id):
        """Find Maintenance Managers and supervisors in tenant."""
        users = User.all_objects.filter(
            tenant_id=tenant_id,
            status='ACTIVE'
        ).filter(
            models.Q(roles__permissions__id__in=['work_order:approve', 'maintenance:update']) |
            models.Q(roles__name__icontains='manager') |
            models.Q(roles__name__icontains='admin') |
            models.Q(is_superuser=True)
        ).distinct()
        return NotificationRouter.filter_active_users(users)

    @staticmethod
    def get_warehouse_keepers(tenant_id):
        """Find warehouse/inventory keepers in tenant."""
        users = User.all_objects.filter(
            tenant_id=tenant_id,
            status='ACTIVE'
        ).filter(
            models.Q(roles__permissions__id__in=['inventory:update', 'inventory:read']) |
            models.Q(roles__name__icontains='inventory') |
            models.Q(roles__name__icontains='warehouse') |
            models.Q(roles__name__icontains='admin') |
            models.Q(is_superuser=True)
        ).distinct()
        return NotificationRouter.filter_active_users(users)

    @staticmethod
    def get_tenant_admins_and_finance(tenant_id):
        """Find Tenant Administrators and Finance Managers."""
        users = User.all_objects.filter(
            tenant_id=tenant_id,
            status='ACTIVE'
        ).filter(
            models.Q(roles__permissions__id__in=['tenant:admin', 'reports:read', 'finance:read']) |
            models.Q(roles__name__icontains='admin') |
            models.Q(roles__name__icontains='finance') |
            models.Q(is_superuser=True)
        ).distinct()
        return NotificationRouter.filter_active_users(users)


def check_and_apply_deduplication(tenant_id, event_type, entity_id, recipient_id, window_seconds=300):
    """
    Sliding-Window Deduplication (Rule 2).
    Unique key: notif_dedup:{tenant_id}:{event_type}:{entity_id}:{recipient_id}
    """
    if not entity_id or not recipient_id:
        return None, False

    cache_key = f"notif_dedup:{tenant_id}:{event_type}:{entity_id}:{recipient_id}"
    existing_notif_id = cache.get(cache_key)

    if existing_notif_id:
        try:
            existing = Notification.all_objects.filter(id=existing_notif_id).first()
            if existing:
                existing.occurrence_count += 1
                existing.save(update_fields=['occurrence_count', 'updated_at'])
                logger.info(f"Deduplicated event {event_type} for recipient {recipient_id}. Count: {existing.occurrence_count}")
                return existing, True
        except Exception as e:
            logger.warning(f"Error updating deduplicated notification: {e}")

    return cache_key, False


def check_ooo_delegation(recipient, tenant_id):
    """
    Check Out-of-Office delegation status (Rule 5 & TC-OOO-01).
    """
    if not recipient:
        return None

    try:
        pref = NotificationPreference.all_objects.filter(
            user=recipient,
            tenant_id=tenant_id,
            is_out_of_office=True
        ).first()
        if pref and pref.delegated_to_user:
            delegate = pref.delegated_to_user
            if getattr(delegate, 'status', 'ACTIVE') == 'ACTIVE' and getattr(delegate, 'is_active', True):
                return delegate
    except Exception as e:
        logger.warning(f"Error checking OOO preference: {e}")

    return None


def send_notification(
    recipient,
    title,
    message,
    link=None,
    tenant=None,
    sender=None,
    event_type='GENERAL',
    category='SYSTEM',
    severity='INFO',
    is_actionable=False,
    action_status='NOT_APPLICABLE',
    metadata=None,
    sla_minutes=None,
    async_channels=True
):
    """
    Safely creates a notification for a recipient in a multi-tenant environment.
    Supports in-place backward compatibility for all existing callers.
    """
    if not recipient:
        return None

    # Check recipient active status (TC-EDGE-02)
    if getattr(recipient, 'status', 'ACTIVE') != 'ACTIVE' or not getattr(recipient, 'is_active', True):
        logger.warning(f"Skipping notification '{title}' to inactive recipient {recipient}.")
        return None

    resolved_tenant = tenant or getattr(recipient, 'tenant', None)
    if not resolved_tenant:
        logger.warning(f"Cannot dispatch notification '{title}': recipient {recipient} has no tenant.")
        return None

    try:
        meta = metadata.copy() if isinstance(metadata, dict) else {}

        # Sender snapshots
        sender_name = sender.username if sender else ''
        sender_role = ''
        if sender and hasattr(sender, 'roles'):
            first_role = sender.roles.first()
            if first_role:
                sender_role = first_role.name

        # Calculate SLA escalation timestamp for CRITICAL or URGENT
        escalate_at = None
        if severity in ('CRITICAL', 'URGENT'):
            default_sla = sla_minutes if sla_minutes is not None else 20
            escalate_at = timezone.now() + timezone.timedelta(minutes=default_sla)

        notification = Notification.all_objects.create(
            tenant=resolved_tenant,
            recipient=recipient,
            sender=sender,
            sender_name_snapshot=sender_name,
            sender_role_snapshot=sender_role,
            event_type=event_type,
            category=category,
            severity=severity,
            title=title,
            message=message,
            link=link or '',
            metadata=meta,
            is_read=False,
            is_actionable=is_actionable,
            action_status=action_status if is_actionable else 'NOT_APPLICABLE',
            escalate_at=escalate_at
        )

        # Invalidate unread count cache
        cache_key = f"notif_unread_count:{resolved_tenant.id}:{recipient.id}"
        cache.delete(cache_key)

        logger.info(f"Dispatched notification {notification.id} to user {recipient.username}: '{title}' [{event_type}]")

        # Async FCM and Email dispatch via Celery
        if async_channels:
            try:
                from notifications.tasks import async_dispatch_notification_channels
                async_dispatch_notification_channels.delay(str(notification.id))
            except Exception as ex:
                logger.debug(f"Celery dispatch queued inline or skipped in eager mode: {ex}")

        return notification
    except Exception as e:
        logger.error(f"Failed to dispatch notification '{title}' to {recipient}: {e}", exc_info=True)
        return None


def dispatch_event_notification(
    event_type,
    tenant,
    entity_type,
    entity_id,
    recipients,
    title,
    message,
    link='',
    sender=None,
    category='SYSTEM',
    severity='INFO',
    is_actionable=False,
    sla_minutes=None,
    metadata=None,
    async_channels=True
):
    """
    Central Event Dispatcher:
    - Deduplicates sliding-window alerts
    - Dispatches to primary recipients
    - Handles Out-of-Office (OOO) delegation
    """
    if not recipients or not tenant:
        return []

    if not isinstance(recipients, (list, tuple, set)):
        recipients = [recipients]

    dispatched = []
    meta = metadata.copy() if isinstance(metadata, dict) else {}
    meta['entity_type'] = entity_type
    meta['entity_id'] = str(entity_id) if entity_id else ''

    for user in recipients:
        if not user or getattr(user, 'status', 'ACTIVE') != 'ACTIVE' or not getattr(user, 'is_active', True):
            continue

        # 1. Deduplication check (Rule 2)
        dedup_res, is_dup = check_and_apply_deduplication(
            tenant_id=tenant.id,
            event_type=event_type,
            entity_id=entity_id,
            recipient_id=user.id
        )
        if is_dup:
            dispatched.append(dedup_res)
            continue

        # 2. Check OOO delegation (Rule 5)
        delegated_user = check_ooo_delegation(user, tenant.id)

        # 3. Create primary notification
        notif = send_notification(
            recipient=user,
            title=title,
            message=message,
            link=link,
            tenant=tenant,
            sender=sender,
            event_type=event_type,
            category=category,
            severity=severity,
            is_actionable=is_actionable,
            action_status='PENDING' if is_actionable else 'NOT_APPLICABLE',
            metadata=meta,
            sla_minutes=sla_minutes,
            async_channels=async_channels
        )

        if notif:
            dispatched.append(notif)
            # Register deduplication cache key for 5 minutes (300s)
            if isinstance(dedup_res, str):
                cache.set(dedup_res, str(notif.id), timeout=300)

        # 4. If user is OOO, create forwarded notification for delegated user (Rule 5 & TC-OOO-01)
        if delegated_user and delegated_user.id != user.id:
            del_meta = meta.copy()
            del_meta['delegated_from_user_id'] = str(user.id)
            del_meta['delegated_from_username'] = user.username
            del_meta['delegation_reason'] = 'Out of Office'

            del_notif = send_notification(
                recipient=delegated_user,
                title=f"[Ủy quyền] {title}",
                message=f"(Chuyển tiếp từ {user.username} do vắng mặt) {message}",
                link=link,
                tenant=tenant,
                sender=sender,
                event_type='TASK_DELEGATED',
                category=category,
                severity=severity,
                is_actionable=is_actionable,
                action_status='PENDING' if is_actionable else 'NOT_APPLICABLE',
                metadata=del_meta,
                sla_minutes=sla_minutes,
                async_channels=async_channels
            )
            if del_notif:
                dispatched.append(del_notif)

    return dispatched


# -------------------------------------------------------------------------
# 15 Standard Event Triggers (Specification Matrix Section 3)
# -------------------------------------------------------------------------

def notify_work_order_assigned(work_order, assignee=None, is_reassigned=False, sender=None):
    """Event 1: WO_ASSIGNED"""
    recipient = assignee or getattr(work_order, 'assigned_to', None)
    if not recipient:
        return None

    action_text = "tái phân công" if is_reassigned else "phân công"
    priority = getattr(work_order, 'priority', 'MEDIUM')
    title = f"Phân công công việc: {work_order.title}"
    message = f"Bạn đã được {action_text} thực hiện phiếu WO '{work_order.title}' (Độ ưu tiên: {priority})."
    link = f"/portal/work-orders/{work_order.id}/"

    notifs = dispatch_event_notification(
        event_type='WO_ASSIGNED',
        tenant=work_order.tenant,
        entity_type='WorkOrder',
        entity_id=work_order.id,
        recipients=[recipient],
        title=title,
        message=message,
        link=link,
        sender=sender or getattr(work_order, 'created_by', None),
        category='WORK_ORDER',
        severity='INFO',
        is_actionable=True
    )
    return notifs[0] if notifs else None


def notify_work_order_status_changed(work_order, old_status, new_status, actor=None):
    """Event 2: WO_STATUS_CHANGED"""
    recipients = []
    if work_order.assigned_to:
        recipients.append(work_order.assigned_to)
    if work_order.created_by and work_order.created_by not in recipients:
        recipients.append(work_order.created_by)

    title = f"Cập nhật trạng thái WO: {work_order.title}"
    message = f"Phiếu công việc '{work_order.title}' đã chuyển trạng thái từ {old_status} sang {new_status}."
    link = f"/portal/work-orders/{work_order.id}/"

    return dispatch_event_notification(
        event_type='WO_STATUS_CHANGED',
        tenant=work_order.tenant,
        entity_type='WorkOrder',
        entity_id=work_order.id,
        recipients=recipients,
        title=title,
        message=message,
        link=link,
        sender=actor,
        category='WORK_ORDER',
        severity='INFO',
        is_actionable=False
    )


def notify_work_order_overdue(work_order):
    """Event 3: WO_OVERDUE"""
    recipients = []
    if work_order.assigned_to:
        recipients.append(work_order.assigned_to)
    managers = NotificationRouter.get_maintenance_managers(work_order.tenant_id)
    recipients.extend([m for m in managers if m not in recipients])

    title = f"Phiếu công việc quá hạn: {work_order.title}"
    message = f"Work Order '{work_order.title}' đã vượt quá thời hạn cam kết xử lý ({work_order.deadline})."
    link = f"/portal/work-orders/{work_order.id}/"

    return dispatch_event_notification(
        event_type='WO_OVERDUE',
        tenant=work_order.tenant,
        entity_type='WorkOrder',
        entity_id=work_order.id,
        recipients=recipients,
        title=title,
        message=message,
        link=link,
        category='WORK_ORDER',
        severity='URGENT',
        is_actionable=True,
        sla_minutes=15
    )


def notify_work_order_emergency_created(work_order, creator=None):
    """Event 4: WO_EMERGENCY_CREATED"""
    recipients = NotificationRouter.get_maintenance_managers(work_order.tenant_id)

    title = f"Sự cố khẩn cấp: {work_order.title}"
    message = f"Phát sinh phiếu công việc khẩn cấp (Dừng máy/Nguy cơ cao): '{work_order.title}'."
    link = f"/portal/work-orders/{work_order.id}/"

    return dispatch_event_notification(
        event_type='WO_EMERGENCY_CREATED',
        tenant=work_order.tenant,
        entity_type='WorkOrder',
        entity_id=work_order.id,
        recipients=recipients,
        title=title,
        message=message,
        link=link,
        sender=creator or getattr(work_order, 'created_by', None),
        category='WORK_ORDER',
        severity='CRITICAL',
        is_actionable=True,
        sla_minutes=15
    )


def notify_escalation_alert(notification, original_wo=None):
    """Event 5: WO_ESCALATED"""
    managers = NotificationRouter.get_maintenance_managers(notification.tenant_id)
    title = f"Cảnh báo leo thang sự cố: {notification.title}"
    message = f"Sự cố nghiêm trọng '{notification.title}' chưa có kỹ thuật viên tiếp nhận quá thời hạn SLA."
    link = notification.link or (f"/portal/work-orders/{original_wo.id}/" if original_wo else "/portal/work-orders/")

    return dispatch_event_notification(
        event_type='WO_ESCALATED',
        tenant=notification.tenant,
        entity_type='Notification',
        entity_id=notification.id,
        recipients=managers,
        title=title,
        message=message,
        link=link,
        category='WORK_ORDER',
        severity='CRITICAL',
        is_actionable=True
    )


def notify_task_delegated(work_order, original_assignee, delegated_user):
    """Event 6: TASK_DELEGATED (explicit trigger helper)"""
    title = f"Ủy quyền công việc: {work_order.title}"
    message = f"Bạn được ủy quyền thực hiện phiếu công việc '{work_order.title}' do {original_assignee.username} vắng mặt."
    link = f"/portal/work-orders/{work_order.id}/"

    return dispatch_event_notification(
        event_type='TASK_DELEGATED',
        tenant=work_order.tenant,
        entity_type='WorkOrder',
        entity_id=work_order.id,
        recipients=[delegated_user],
        title=title,
        message=message,
        link=link,
        category='WORK_ORDER',
        severity='INFO',
        is_actionable=True,
        metadata={'delegated_from': original_assignee.username}
    )


def notify_pm_work_order_generated(pm_plan, work_order, asset=None):
    """Event 7: PM_SCHEDULE_TRIGGERED (backward-compatible signature)"""
    recipients = []
    if pm_plan.assignee:
        recipients.append(pm_plan.assignee)
    creator = getattr(pm_plan, 'created_by', None)
    if creator and creator not in recipients:
        recipients.append(creator)

    if not recipients:
        recipients = NotificationRouter.get_maintenance_managers(work_order.tenant_id)

    asset_name = asset.name if asset else (getattr(work_order.asset, 'name', 'Thiết bị') if getattr(work_order, 'asset', None) else 'Thiết bị')
    title = f"Phiếu bảo trì định kỳ: {work_order.title}"
    message = f"Phiếu công việc định kỳ '{work_order.title}' cho thiết bị '{asset_name}' đã được hệ thống tự động khởi tạo theo kế hoạch '{pm_plan.name}'."
    link = f"/portal/work-orders/{work_order.id}/"

    return dispatch_event_notification(
        event_type='PM_SCHEDULE_TRIGGERED',
        tenant=work_order.tenant,
        entity_type='PmPlan',
        entity_id=pm_plan.id,
        recipients=recipients,
        title=title,
        message=message,
        link=link,
        category='MAINTENANCE',
        severity='INFO',
        is_actionable=False
    )


def notify_pm_upcoming_reminder(pm_plan, due_date):
    """Event 8: PM_UPCOMING_REMINDER"""
    recipients = []
    if pm_plan.assignee:
        recipients.append(pm_plan.assignee)
    managers = NotificationRouter.get_maintenance_managers(pm_plan.tenant_id)
    recipients.extend([m for m in managers if m not in recipients])

    title = f"Nhắc nhở bảo trì định kỳ sắp đến hạn: {pm_plan.name}"
    message = f"Kế hoạch bảo trì '{pm_plan.name}' dự kiến đến hạn vào {due_date}. Vui lòng chuẩn bị vật tư và nhân sự."
    link = f"/portal/maintenance/pm-plans/{pm_plan.id}/"

    return dispatch_event_notification(
        event_type='PM_UPCOMING_REMINDER',
        tenant=pm_plan.tenant,
        entity_type='PmPlan',
        entity_id=pm_plan.id,
        recipients=recipients,
        title=title,
        message=message,
        link=link,
        category='MAINTENANCE',
        severity='INFO',
        is_actionable=False
    )


def notify_spare_part_low_stock(spare_part, threshold=10):
    """Event 9: SPARE_PART_LOW_STOCK (upgraded with Redis sliding-window dedup)"""
    if spare_part.quantity_in_stock is None:
        return []

    try:
        qty = float(spare_part.quantity_in_stock)
    except (ValueError, TypeError):
        return []

    if qty > threshold:
        return []

    recipients = NotificationRouter.get_warehouse_keepers(spare_part.tenant_id)
    if not recipients:
        recipients = NotificationRouter.get_maintenance_managers(spare_part.tenant_id)

    part_no = f" (Mã: {spare_part.part_number})" if getattr(spare_part, 'part_number', None) else ""
    title = f"Cảnh báo tồn kho thấp: {spare_part.name}"
    message = f"Vật tư '{spare_part.name}'{part_no} hiện chỉ còn {int(qty)} trong kho, chạm ngưỡng tối thiểu ({threshold}). Vui lòng lập kế hoạch nhập hàng."
    link = f"/portal/inventory/parts/{spare_part.id}/"

    dispatched = dispatch_event_notification(
        event_type='SPARE_PART_LOW_STOCK',
        tenant=spare_part.tenant,
        entity_type='SparePart',
        entity_id=spare_part.id,
        recipients=recipients,
        title=title,
        message=message,
        link=link,
        category='INVENTORY',
        severity='WARNING',
        is_actionable=True
    )
    # Deduplication suppression: return only newly created notifications
    return [n for n in dispatched if getattr(n, 'occurrence_count', 1) == 1]


def notify_spare_part_requested(spare_part, work_order, quantity_requested, requester=None):
    """Event 10: SPARE_PART_REQUESTED"""
    keepers = NotificationRouter.get_warehouse_keepers(spare_part.tenant_id)
    title = f"Yêu cầu xuất kho vật tư: {spare_part.name}"
    message = f"Kỹ thuật viên yêu cầu xuất {quantity_requested} {spare_part.name} cho phiếu WO '{work_order.title}'."
    link = f"/portal/inventory/requests/{work_order.id}/"

    return dispatch_event_notification(
        event_type='SPARE_PART_REQUESTED',
        tenant=spare_part.tenant,
        entity_type='SparePart',
        entity_id=spare_part.id,
        recipients=keepers,
        title=title,
        message=message,
        link=link,
        sender=requester,
        category='INVENTORY',
        severity='INFO',
        is_actionable=True
    )


def notify_sensor_anomaly(asset, anomaly_type, metric_value, threshold_value):
    """Event 11: SENSOR_ANOMALY_DETECTED"""
    managers = NotificationRouter.get_maintenance_managers(asset.tenant_id)
    title = f"Cảnh báo bất thường cảm biến: {asset.name}"
    message = f"Cảm biến phát hiện {anomaly_type} bất thường tại thiết bị '{asset.name}': {metric_value} (Ngưỡng: {threshold_value})."
    link = f"/portal/assets/{asset.id}/"

    return dispatch_event_notification(
        event_type='SENSOR_ANOMALY_DETECTED',
        tenant=asset.tenant,
        entity_type='Asset',
        entity_id=asset.id,
        recipients=managers,
        title=title,
        message=message,
        link=link,
        category='ASSET',
        severity='CRITICAL',
        is_actionable=True,
        sla_minutes=15
    )


def notify_asset_status_down(asset, reason=None, reporter=None):
    """Event 12: ASSET_STATUS_DOWN"""
    managers = NotificationRouter.get_maintenance_managers(asset.tenant_id)
    title = f"Thiết bị dừng máy: {asset.name}"
    reason_text = f" (Lý do: {reason})" if reason else ""
    message = f"Thiết bị '{asset.name}' đã chuyển sang trạng thái DỪNG MÁY (DOWN){reason_text}."
    link = f"/portal/assets/{asset.id}/"

    return dispatch_event_notification(
        event_type='ASSET_STATUS_DOWN',
        tenant=asset.tenant,
        entity_type='Asset',
        entity_id=asset.id,
        recipients=managers,
        title=title,
        message=message,
        link=link,
        sender=reporter,
        category='ASSET',
        severity='URGENT',
        is_actionable=True,
        sla_minutes=20
    )


def notify_budget_exceeded(tenant, department_name, current_spend, budget_limit):
    """Event 13: BUDGET_THRESHOLD_EXCEEDED"""
    admins = NotificationRouter.get_tenant_admins_and_finance(tenant.id)
    title = f"Cảnh báo vượt ngưỡng ngân sách: {department_name}"
    message = f"Chi phí bảo trì thực tế ({current_spend:,.0f}) đã vượt ngưỡng định mức ngân sách quy định ({budget_limit:,.0f})."
    link = "/portal/reports/costs/"

    return dispatch_event_notification(
        event_type='BUDGET_THRESHOLD_EXCEEDED',
        tenant=tenant,
        entity_type='Budget',
        entity_id=department_name,
        recipients=admins,
        title=title,
        message=message,
        link=link,
        category='FINANCE',
        severity='WARNING',
        is_actionable=False
    )


def notify_user_invitation_accepted(new_user, invited_by=None):
    """Event 14: USER_INVITATION_ACCEPTED"""
    recipients = []
    if invited_by and getattr(invited_by, 'status', 'ACTIVE') == 'ACTIVE':
        recipients.append(invited_by)
    admins = NotificationRouter.get_tenant_admins_and_finance(new_user.tenant_id)
    recipients.extend([a for a in admins if a not in recipients])

    title = "Thành viên mới gia nhập tổ chức"
    message = f"Người dùng '{new_user.username}' đã chấp nhận lời mời và kích hoạt thành công tài khoản thành viên."
    link = "/portal/admin/users/"

    return dispatch_event_notification(
        event_type='USER_INVITATION_ACCEPTED',
        tenant=new_user.tenant,
        entity_type='User',
        entity_id=new_user.id,
        recipients=recipients,
        title=title,
        message=message,
        link=link,
        category='SYSTEM',
        severity='INFO',
        is_actionable=False
    )


def notify_system_maintenance(title, message, scheduled_time=None):
    """Event 15: SYSTEM_MAINTENANCE_ALERT"""
    from core.models import Tenant
    all_tenants = Tenant.objects.filter(status='ACTIVE')
    dispatched = []

    time_str = f" lúc {scheduled_time}" if scheduled_time else ""
    full_msg = f"Kế hoạch bảo trì hệ thống máy chủ{time_str}: {message}"

    for t in all_tenants:
        admins = NotificationRouter.get_tenant_admins_and_finance(t.id)
        if not admins:
            admins = NotificationRouter.get_maintenance_managers(t.id)
        if not admins:
            admins = NotificationRouter.filter_active_users(User.all_objects.filter(tenant_id=t.id, status='ACTIVE'))

        if admins:
            res = dispatch_event_notification(
                event_type='SYSTEM_MAINTENANCE_ALERT',
                tenant=t,
                entity_type='System',
                entity_id='MAINTENANCE',
                recipients=admins,
                title=f"[Hệ Thống] {title}",
                message=full_msg,
                link="/portal/announcements/",
                category='SYSTEM',
                severity='WARNING',
                is_actionable=False
            )
            dispatched.extend(res)

    return dispatched

import uuid
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.contrib.auth import get_user_model
from core.models import Tenant
from core.tenant_context import set_current_tenant, clear_current_tenant
from notifications.models import Notification

User = get_user_model()


class NotificationModelTestCase(TestCase):
    def setUp(self):
        clear_current_tenant()
        self.tenant_a = Tenant.objects.create(name="Tenant Alpha", tenant_code="ALPHA")
        self.tenant_b = Tenant.objects.create(name="Tenant Beta", tenant_code="BETA")

        self.user_a = User.objects.create_user(
            username="alice",
            email="alice@alpha.com",
            password="password123",
            tenant=self.tenant_a
        )
        self.user_b = User.objects.create_user(
            username="bob",
            email="bob@beta.com",
            password="password123",
            tenant=self.tenant_b
        )

    def tearDown(self):
        clear_current_tenant()

    def test_create_notification_with_all_fields(self):
        """Test successful creation of a Notification with all specified fields."""
        notif = Notification.objects.create(
            recipient=self.user_a,
            tenant=self.tenant_a,
            title="Work Order Assigned",
            message="You have been assigned to WO-1001.",
            link="/portal/work-orders/wo-1001",
            is_read=False
        )

        self.assertIsInstance(notif.id, uuid.UUID)
        self.assertEqual(notif.recipient, self.user_a)
        self.assertEqual(notif.tenant, self.tenant_a)
        self.assertEqual(notif.title, "Work Order Assigned")
        self.assertEqual(notif.message, "You have been assigned to WO-1001.")
        self.assertEqual(notif.link, "/portal/work-orders/wo-1001")
        self.assertFalse(notif.is_read)
        self.assertIsNotNone(notif.created_at)
        self.assertIn("Work Order Assigned", str(notif))
        self.assertIn("alice", str(notif))
        self.assertIn("Unread", str(notif))

    def test_auto_tenant_resolution_from_recipient(self):
        """If tenant is not explicitly provided, it should resolve from recipient."""
        notif = Notification.objects.create(
            recipient=self.user_a,
            title="PM Due",
            message="PM inspection due today."
        )
        self.assertEqual(notif.tenant, self.tenant_a)

    def test_auto_tenant_resolution_from_context(self):
        """If tenant context is active, notification inherits context tenant."""
        set_current_tenant(self.tenant_a.id)
        notif = Notification(
            recipient=self.user_a,
            title="Low Stock Alert",
            message="Filter bearings below minimum."
        )
        notif.save()
        self.assertEqual(notif.tenant_id, self.tenant_a.id)

    def test_tenant_cross_contamination_prevented(self):
        """A notification cannot associate a recipient from Tenant B with Tenant A."""
        notif = Notification(
            recipient=self.user_b,  # Tenant B
            tenant=self.tenant_a,   # Tenant A
            title="Mismatched Notification",
            message="This should fail validation."
        )
        with self.assertRaises(ValidationError) as ctx:
            notif.save()
        self.assertIn('recipient', ctx.exception.message_dict)

    def test_multi_tenant_scoping(self):
        """Test that Notification.objects filters by current tenant while all_objects does not."""
        notif_a = Notification.objects.create(
            recipient=self.user_a,
            tenant=self.tenant_a,
            title="Alpha Note",
            message="Notice for Alpha"
        )
        notif_b = Notification.objects.create(
            recipient=self.user_b,
            tenant=self.tenant_b,
            title="Beta Note",
            message="Notice for Beta"
        )

        # In Tenant Alpha context
        set_current_tenant(self.tenant_a.id)
        scoped_a = list(Notification.objects.all())
        self.assertIn(notif_a, scoped_a)
        self.assertNotIn(notif_b, scoped_a)

        # In Tenant Beta context
        set_current_tenant(self.tenant_b.id)
        scoped_b = list(Notification.objects.all())
        self.assertIn(notif_b, scoped_b)
        self.assertNotIn(notif_a, scoped_b)

        # Without tenant context, Notification.all_objects returns all
        all_notifs = list(Notification.all_objects.all())
        self.assertEqual(len(all_notifs), 2)
        self.assertIn(notif_a, all_notifs)
        self.assertIn(notif_b, all_notifs)

    def test_mark_as_read(self):
        """Test mark_as_read helper marks notification as read and updates DB."""
        notif = Notification.objects.create(
            recipient=self.user_a,
            tenant=self.tenant_a,
            title="Test Read",
            message="Please read me",
            is_read=False
        )
        self.assertFalse(notif.is_read)

        notif.mark_as_read()
        self.assertTrue(notif.is_read)

        # Fetch fresh from database
        refreshed = Notification.objects.get(id=notif.id)
        self.assertTrue(refreshed.is_read)
        self.assertIn("Read", str(refreshed))

    def test_recipient_reverse_relationship(self):
        """Test recipient.notifications reverse relation."""
        notif1 = Notification.objects.create(
            recipient=self.user_a,
            tenant=self.tenant_a,
            title="Note 1",
            message="Msg 1"
        )
        notif2 = Notification.objects.create(
            recipient=self.user_a,
            tenant=self.tenant_a,
            title="Note 2",
            message="Msg 2"
        )

        user_notifications = list(self.user_a.notifications.all())
        self.assertEqual(len(user_notifications), 2)
        self.assertIn(notif1, user_notifications)
        self.assertIn(notif2, user_notifications)

    def test_cascade_deletion_on_user_delete(self):
        """Deleting a user should cascade delete their notifications."""
        notif = Notification.objects.create(
            recipient=self.user_a,
            tenant=self.tenant_a,
            title="Doomed",
            message="Will be deleted"
        )
        notif_id = notif.id
        self.user_a.delete()
        self.assertFalse(Notification.all_objects.filter(id=notif_id).exists())

    def test_cascade_deletion_on_tenant_delete(self):
        """Deleting a tenant should cascade delete all associated notifications."""
        notif = Notification.objects.create(
            recipient=self.user_a,
            tenant=self.tenant_a,
            title="Doomed Tenant",
            message="Will be deleted with tenant"
        )
        notif_id = notif.id
        self.tenant_a.delete()
        self.assertFalse(Notification.all_objects.filter(id=notif_id).exists())

    def test_ordering_by_created_at_descending(self):
        """Notifications should be ordered by created_at descending by default."""
        notif1 = Notification.objects.create(
            recipient=self.user_a,
            tenant=self.tenant_a,
            title="First",
            message="Msg 1"
        )
        notif2 = Notification.objects.create(
            recipient=self.user_a,
            tenant=self.tenant_a,
            title="Second",
            message="Msg 2"
        )
        notif3 = Notification.objects.create(
            recipient=self.user_a,
            tenant=self.tenant_a,
            title="Third",
            message="Msg 3"
        )

        notifs = list(Notification.all_objects.filter(recipient=self.user_a))
        # Newest first
        self.assertEqual(notifs[0].id, notif3.id)
        self.assertEqual(notifs[1].id, notif2.id)
        self.assertEqual(notifs[2].id, notif1.id)


from rest_framework.test import APITestCase
from rest_framework import status


class NotificationAPITestCase(APITestCase):
    def setUp(self):
        clear_current_tenant()
        self.tenant_a = Tenant.objects.create(name="Alpha Corp", tenant_code="ALPHA_API")
        self.tenant_b = Tenant.objects.create(name="Beta Corp", tenant_code="BETA_API")

        self.user_a1 = User.objects.create_user(
            username="alice_api",
            email="alice_api@alpha.com",
            password="password123",
            tenant=self.tenant_a
        )
        self.user_a2 = User.objects.create_user(
            username="alex_api",
            email="alex_api@alpha.com",
            password="password123",
            tenant=self.tenant_a
        )
        self.user_b1 = User.objects.create_user(
            username="bob_api",
            email="bob_api@beta.com",
            password="password123",
            tenant=self.tenant_b
        )

        # Create notifications for user_a1 (2 unread, 1 read)
        self.notif_a1_unread1 = Notification.objects.create(
            recipient=self.user_a1,
            tenant=self.tenant_a,
            title="A1 Unread 1",
            message="Message 1",
            link="/portal/work-orders/1",
            is_read=False
        )
        self.notif_a1_unread2 = Notification.objects.create(
            recipient=self.user_a1,
            tenant=self.tenant_a,
            title="A1 Unread 2",
            message="Message 2",
            link="/portal/work-orders/2",
            is_read=False
        )
        self.notif_a1_read = Notification.objects.create(
            recipient=self.user_a1,
            tenant=self.tenant_a,
            title="A1 Read",
            message="Message 3",
            is_read=True
        )

        # Create notification for user_a2 (same tenant, different user)
        self.notif_a2_unread = Notification.objects.create(
            recipient=self.user_a2,
            tenant=self.tenant_a,
            title="A2 Unread",
            message="Message for Alex",
            is_read=False
        )

        # Create notification for user_b1 (different tenant)
        self.notif_b1_unread = Notification.objects.create(
            recipient=self.user_b1,
            tenant=self.tenant_b,
            title="B1 Unread",
            message="Message for Bob",
            is_read=False
        )

    def tearDown(self):
        clear_current_tenant()

    def test_list_notifications_requires_authentication(self):
        """Unauthenticated requests must be rejected with 401."""
        response = self.client.get(
            '/api/v1/notifications/',
            HTTP_X_TENANT_ID=str(self.tenant_a.id)
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_notifications_user_and_tenant_scoped(self):
        """User A1 should only receive their own notifications, not A2 or B1."""
        self.client.force_authenticate(user=self.user_a1)
        response = self.client.get(
            '/api/v1/notifications/',
            HTTP_X_TENANT_ID=str(self.tenant_a.id)
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        res_data = response.json()
        self.assertTrue(res_data['success'])
        
        content = res_data['data']['content']
        returned_ids = [item['id'] for item in content]

        # Should contain A1's 3 notifications
        self.assertEqual(len(content), 3)
        self.assertIn(str(self.notif_a1_unread1.id), returned_ids)
        self.assertIn(str(self.notif_a1_unread2.id), returned_ids)
        self.assertIn(str(self.notif_a1_read.id), returned_ids)

        # Must NOT contain A2 or B1 notifications (Anti-IDOR)
        self.assertNotIn(str(self.notif_a2_unread.id), returned_ids)
        self.assertNotIn(str(self.notif_b1_unread.id), returned_ids)

        # Check unread count
        self.assertEqual(res_data['data']['unread_count'], 2)

    def test_list_notifications_unread_only_filter(self):
        """Filtering with unread_only=true should only return unread items."""
        self.client.force_authenticate(user=self.user_a1)
        response = self.client.get(
            '/api/v1/notifications/?unread_only=true',
            HTTP_X_TENANT_ID=str(self.tenant_a.id)
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        res_data = response.json()
        content = res_data['data']['content']
        self.assertEqual(len(content), 2)
        returned_ids = [item['id'] for item in content]
        self.assertIn(str(self.notif_a1_unread1.id), returned_ids)
        self.assertIn(str(self.notif_a1_unread2.id), returned_ids)
        self.assertNotIn(str(self.notif_a1_read.id), returned_ids)

    def test_mark_single_notification_as_read(self):
        """User A1 successfully marks their own notification as read."""
        self.client.force_authenticate(user=self.user_a1)
        url = f'/api/v1/notifications/{self.notif_a1_unread1.id}/read/'
        response = self.client.post(url, HTTP_X_TENANT_ID=str(self.tenant_a.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        res_data = response.json()
        self.assertTrue(res_data['success'])
        self.assertTrue(res_data['data']['is_read'])

        # Verify in DB
        self.notif_a1_unread1.refresh_from_db()
        self.assertTrue(self.notif_a1_unread1.is_read)

    def test_mark_notification_as_read_anti_idor_same_tenant(self):
        """User A1 cannot mark User A2's notification as read (returns 404)."""
        self.client.force_authenticate(user=self.user_a1)
        url = f'/api/v1/notifications/{self.notif_a2_unread.id}/read/'
        response = self.client.post(url, HTTP_X_TENANT_ID=str(self.tenant_a.id))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # Verify A2's notification was NOT altered
        self.notif_a2_unread.refresh_from_db()
        self.assertFalse(self.notif_a2_unread.is_read)

    def test_mark_notification_as_read_anti_idor_cross_tenant(self):
        """User A1 cannot mark User B1's notification from another tenant (returns 404)."""
        self.client.force_authenticate(user=self.user_a1)
        url = f'/api/v1/notifications/{self.notif_b1_unread.id}/read/'
        response = self.client.post(url, HTTP_X_TENANT_ID=str(self.tenant_a.id))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # Verify B1's notification was NOT altered
        self.notif_b1_unread.refresh_from_db()
        self.assertFalse(self.notif_b1_unread.is_read)

    def test_mark_all_notifications_as_read(self):
        """Mark all notifications as read for current user only."""
        self.client.force_authenticate(user=self.user_a1)
        response = self.client.post(
            '/api/v1/notifications/read-all/',
            HTTP_X_TENANT_ID=str(self.tenant_a.id)
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        res_data = response.json()
        self.assertTrue(res_data['success'])
        self.assertEqual(res_data['data']['updated_count'], 2)

        # Verify in DB: all A1 are read
        self.notif_a1_unread1.refresh_from_db()
        self.notif_a1_unread2.refresh_from_db()
        self.assertTrue(self.notif_a1_unread1.is_read)
        self.assertTrue(self.notif_a1_unread2.is_read)

        # A2 and B1 must remain unread!
        self.notif_a2_unread.refresh_from_db()
        self.notif_b1_unread.refresh_from_db()
        self.assertFalse(self.notif_a2_unread.is_read)
        self.assertFalse(self.notif_b1_unread.is_read)

    def test_unread_count_endpoint(self):
        """Test the dedicated unread count endpoint."""
        self.client.force_authenticate(user=self.user_a1)
        response = self.client.get(
            '/api/v1/notifications/unread-count/',
            HTTP_X_TENANT_ID=str(self.tenant_a.id)
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        res_data = response.json()
        self.assertTrue(res_data['success'])
        self.assertEqual(res_data['data']['unread_count'], 2)


from django.test import Client


class NotificationTemplateTestCase(TestCase):
    def setUp(self):
        clear_current_tenant()
        self.tenant = Tenant.objects.create(name="Template Corp", tenant_code="TPL")
        self.user = User.objects.create_user(
            username="tpl_user",
            email="tpl@corp.com",
            password="password123",
            tenant=self.tenant
        )
        self.client = Client()

    def tearDown(self):
        clear_current_tenant()

    def test_topbar_bell_rendered_for_authenticated_user(self):
        """Verify the Topbar Bell DOM elements and NotificationBell scripts are present in base template."""
        self.client.force_login(self.user)
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

        html = response.content.decode('utf-8')
        self.assertIn('id="notification-bell-container"', html)
        self.assertIn('id="notification-bell-btn"', html)
        self.assertIn('id="notification-badge"', html)
        self.assertIn('id="notification-dropdown"', html)
        self.assertIn('id="notification-header-badge"', html)
        self.assertIn('id="notification-mark-all-read-btn"', html)
        self.assertIn('id="notification-list"', html)
        self.assertIn('id="notification-loading"', html)
        self.assertIn('id="notification-empty"', html)
        self.assertIn('id="notification-items"', html)
        self.assertIn('id="notification-refresh-btn"', html)
        self.assertIn('window.NotificationBell', html)
        self.assertIn('fetchUnreadCount', html)
        self.assertIn('fetchNotifications', html)
        self.assertIn('markAsRead', html)
        self.assertIn('markAllAsRead', html)

        # Polling Engine assertions (Task 10.1.4)
        self.assertIn('pollInterval: 10000', html)
        self.assertIn('startPolling', html)
        self.assertIn('stopPolling', html)
        self.assertIn('checkUpdates', html)
        self.assertIn('visibilitychange', html)
        self.assertIn('window.addEventListener(\'focus\'', html)


from workorders.models import WorkOrder
from assets.models import Asset, SparePart
from maintenance.models import PmPlan
from users.models import Role
from notifications.services import (
    send_notification,
    notify_work_order_assigned,
    notify_pm_work_order_generated,
    notify_spare_part_low_stock,
)
from decimal import Decimal


class NotificationTriggersTestCase(TestCase):
    """
    Tests for Task 10.1.5: Notification dispatch triggers
    - Work Order assigned / reassigned
    - PM auto-generated by Celery
    - Spare part low-stock warning & deduplication
    """
    def setUp(self):
        clear_current_tenant()
        self.tenant = Tenant.objects.create(name="Apex Industries", tenant_code="APEX")
        self.other_tenant = Tenant.objects.create(name="Other Corp", tenant_code="OTHER")

        self.admin_user = User.objects.create_user(
            username="admin_apex",
            email="admin@apex.com",
            password="password123",
            tenant=self.tenant,
            is_staff=True,
            is_superuser=True
        )
        self.tech_user = User.objects.create_user(
            username="tech_john",
            email="john@apex.com",
            password="password123",
            tenant=self.tenant
        )
        self.tech_user2 = User.objects.create_user(
            username="tech_sarah",
            email="sarah@apex.com",
            password="password123",
            tenant=self.tenant
        )
        self.other_user = User.objects.create_user(
            username="other_bob",
            email="bob@other.com",
            password="password123",
            tenant=self.other_tenant
        )

        self.asset = Asset.objects.create(
            name="Hydraulic Press HP-200",
            qr_code="QR-HP200",
            tenant=self.tenant
        )

    def tearDown(self):
        clear_current_tenant()

    def test_send_notification_service(self):
        """Test the foundational send_notification service."""
        notif = send_notification(
            recipient=self.tech_user,
            title="System Alert",
            message="Test message content",
            link="/portal/dashboard",
            tenant=self.tenant
        )
        self.assertIsNotNone(notif)
        self.assertEqual(notif.recipient, self.tech_user)
        self.assertEqual(notif.tenant, self.tenant)
        self.assertEqual(notif.title, "System Alert")
        self.assertEqual(notif.message, "Test message content")
        self.assertEqual(notif.link, "/portal/dashboard")
        self.assertFalse(notif.is_read)

    def test_work_order_assigned_trigger(self):
        """Test notification dispatch when a Work Order is newly assigned."""
        wo = WorkOrder.objects.create(
            asset=self.asset,
            title="Fix Hydraulic Pressure Leak",
            priority="HIGH",
            tenant=self.tenant
        )

        notif = notify_work_order_assigned(wo, assignee=self.tech_user, is_reassigned=False)
        self.assertIsNotNone(notif)
        self.assertEqual(notif.recipient, self.tech_user)
        self.assertEqual(notif.tenant, self.tenant)
        self.assertIn("Phân công công việc", notif.title)
        self.assertIn("Fix Hydraulic Pressure Leak", notif.message)
        self.assertIn("phân công", notif.message)
        self.assertIn("/work-orders/", notif.link)

    def test_work_order_reassigned_trigger(self):
        """Test notification dispatch when a Work Order is reassigned to another technician."""
        wo = WorkOrder.objects.create(
            asset=self.asset,
            title="Routine Oil Replacement",
            priority="MEDIUM",
            assigned_to=self.tech_user,
            tenant=self.tenant
        )

        notif = notify_work_order_assigned(wo, assignee=self.tech_user2, is_reassigned=True)
        self.assertIsNotNone(notif)
        self.assertEqual(notif.recipient, self.tech_user2)
        self.assertIn("Phân công công việc", notif.title)
        self.assertIn("Routine Oil Replacement", notif.message)
        self.assertIn("tái phân công", notif.message)

    def test_pm_work_order_generated_trigger(self):
        """Test notification dispatch when PM Plan automatically generates a Work Order."""
        pm_plan = PmPlan.objects.create(
            name="Monthly Turbine Overhaul",
            trigger_type="TIME",
            assignee=self.tech_user,
            tenant=self.tenant
        )
        wo = WorkOrder.objects.create(
            asset=self.asset,
            title="Bảo trì định kỳ: Monthly Turbine Overhaul",
            priority="MEDIUM",
            assigned_to=self.tech_user,
            tenant=self.tenant
        )

        notifs = notify_pm_work_order_generated(pm_plan, wo, asset=self.asset)
        self.assertIsInstance(notifs, list)
        self.assertTrue(len(notifs) >= 1)
        notif = notifs[0]
        self.assertEqual(notif.recipient, self.tech_user)
        self.assertIn("Phiếu bảo trì định kỳ", notif.title)
        self.assertIn("Monthly Turbine Overhaul", notif.message)
        self.assertIn("Hydraulic Press HP-200", notif.message)
        self.assertIn("/work-orders/", notif.link)

    def test_spare_part_low_stock_trigger_with_inventory_role(self):
        """Test low stock notification dispatched to inventory managers when stock <= threshold."""
        inv_role = Role.objects.create(name="Inventory Manager", tenant=self.tenant)
        inv_user = User.objects.create_user(
            username="inv_clerk",
            email="clerk@apex.com",
            password="password123",
            tenant=self.tenant
        )
        inv_user.roles.add(inv_role)

        part = SparePart.objects.create(
            name="O-Ring Seal 50mm",
            part_number="OR-50MM",
            quantity_in_stock=Decimal("4.00"),
            tenant=self.tenant
        )

        created_notifs = notify_spare_part_low_stock(part, threshold=10.0)
        self.assertTrue(len(created_notifs) >= 1)

        inv_notif = next((n for n in created_notifs if n.recipient == inv_user), None)
        self.assertIsNotNone(inv_notif)
        self.assertIn("Cảnh báo tồn kho thấp", inv_notif.title)
        self.assertIn("O-Ring Seal 50mm", inv_notif.title)
        self.assertIn("4", inv_notif.message)
        self.assertIn("/inventory/", inv_notif.link)

    def test_spare_part_low_stock_deduplication(self):
        """Test that duplicate low-stock notifications are suppressed within 24 hours."""
        part = SparePart.objects.create(
            name="Ball Bearing BB-100",
            part_number="BB-100",
            quantity_in_stock=Decimal("2.00"),
            tenant=self.tenant
        )

        # First trigger creates notifications
        notifs_1 = notify_spare_part_low_stock(part, threshold=10.0)
        self.assertTrue(len(notifs_1) > 0)
        count_after_first = Notification.all_objects.filter(
            tenant=self.tenant,
            title__icontains="Ball Bearing BB-100"
        ).count()
        self.assertEqual(count_after_first, len(notifs_1))

        # Second trigger immediately after should be deduplicated
        notifs_2 = notify_spare_part_low_stock(part, threshold=10.0)
        self.assertEqual(len(notifs_2), 0)

        # Ensure total in DB did not increase
        count_after_second = Notification.all_objects.filter(
            tenant=self.tenant,
            title__icontains="Ball Bearing BB-100"
        ).count()
        self.assertEqual(count_after_second, count_after_first)

    def test_spare_part_above_threshold_no_notification(self):
        """Test that no notification is dispatched when spare part stock > threshold."""
        part = SparePart.objects.create(
            name="Standard Hex Bolt M8",
            part_number="HEX-M8",
            quantity_in_stock=Decimal("150.00"),
            tenant=self.tenant
        )

        notifs = notify_spare_part_low_stock(part, threshold=10.0)
        self.assertEqual(len(notifs), 0)
        self.assertFalse(
            Notification.all_objects.filter(
                tenant=self.tenant,
                title__icontains="Standard Hex Bolt M8"
            ).exists()
        )

    def test_work_order_assign_view_integration(self):
        """Test that calling WorkOrderAssignView triggers notification in database."""
        wo = WorkOrder.objects.create(
            asset=self.asset,
            title="Emergency Valve Repair",
            priority="URGENT",
            status="CREATED",
            tenant=self.tenant
        )

        from rest_framework.test import APIClient
        client = APIClient()
        client.force_authenticate(user=self.admin_user)

        response = client.put(
            f'/api/v1/work-orders/{wo.id}/assign/',
            data={'assignedTo': str(self.tech_user.id)},
            format='json',
            HTTP_X_TENANT_ID=str(self.tenant.id)
        )
        self.assertEqual(response.status_code, 200)

        # Check notification was created for tech_user
        notifs = Notification.all_objects.filter(
            recipient=self.tech_user,
            tenant=self.tenant,
            title__icontains="Phân công công việc"
        )
        self.assertTrue(notifs.exists())
        self.assertIn("Emergency Valve Repair", notifs.first().message)


class NotificationPhase10EnterpriseAcceptanceTestCase(TestCase):
    """
    Comprehensive Acceptance Tests for Task 10.1 (Specification Section 5).
    Verifies Multi-Tenancy, OOO Delegation, Escalation, Deduplication, Sender Snapshot,
    Actionable Lifecycle, Role Drift, and Device Tokens.
    """

    def setUp(self):
        clear_current_tenant()
        from core.models import Tenant
        from users.models import Role, Permission
        from assets.models import Asset, SparePart
        from workorders.models import WorkOrder
        from notifications.models import Notification, NotificationPreference, DevicePushToken

        self.tenant_a = Tenant.objects.create(name="Tenant Alpha", tenant_code="T-ALPHA")
        self.tenant_b = Tenant.objects.create(name="Tenant Beta", tenant_code="T-BETA")

        # Manager user in Tenant A
        self.mgr_user = User.objects.create_user(
            username="manager_alex",
            email="alex@alpha.com",
            password="password123",
            tenant=self.tenant_a
        )
        self.mgr_role = Role.objects.create(name="MAINTENANCE_MANAGER", tenant=self.tenant_a)
        perm_approve = Permission.objects.get_or_create(id="work_order:approve", defaults={'name': 'Approve Work Order'})[0]
        self.mgr_role.permissions.add(perm_approve)
        self.mgr_user.roles.add(self.mgr_role)

        # Tech A & Tech B in Tenant A
        self.tech_a = User.objects.create_user(
            username="tech_john",
            email="john@alpha.com",
            password="password123",
            tenant=self.tenant_a
        )
        self.tech_b = User.objects.create_user(
            username="tech_bob",
            email="bob@alpha.com",
            password="password123",
            tenant=self.tenant_a
        )

        # User in Tenant B (for cross-tenant checks)
        self.user_beta = User.objects.create_user(
            username="beta_user",
            email="beta@beta.com",
            password="password123",
            tenant=self.tenant_b
        )

        # Asset & Work Order
        self.asset = Asset.objects.create(
            name="Air Compressor AC-101",
            qr_code="AC-101",
            tenant=self.tenant_a
        )
        self.work_order = WorkOrder.objects.create(
            asset=self.asset,
            title="Inspect Motor Bearings",
            priority="HIGH",
            status="CREATED",
            tenant=self.tenant_a
        )

    def tearDown(self):
        clear_current_tenant()

    def test_tc_tenant_01_isolation(self):
        """TC-TENANT-01: Notification created in Tenant A must never be visible to Tenant B."""
        from notifications.services import notify_work_order_assigned
        notif = notify_work_order_assigned(self.work_order, assignee=self.tech_a)
        self.assertIsNotNone(notif)
        self.assertEqual(notif.tenant, self.tenant_a)

        # Query scoped to Tenant B
        set_current_tenant(self.tenant_b.id)
        visible_in_b = Notification.objects.filter(id=notif.id).exists()
        self.assertFalse(visible_in_b)

    def test_tc_tenant_02_anti_idor(self):
        """TC-TENANT-02: Tenant B user cannot read or delete Tenant A notification."""
        from rest_framework.test import APIClient
        notif = Notification.all_objects.create(
            tenant=self.tenant_a,
            recipient=self.tech_a,
            title="Confidential Alpha Alert",
            message="Internal maintenance details."
        )

        client = APIClient()
        client.force_authenticate(user=self.user_beta)

        # Attempt to read
        res_read = client.post(
            f'/api/v1/notifications/{notif.id}/read/',
            HTTP_X_TENANT_ID=str(self.tenant_b.id)
        )
        self.assertEqual(res_read.status_code, 404)

        # Attempt to delete
        res_del = client.delete(
            f'/api/v1/notifications/{notif.id}/',
            HTTP_X_TENANT_ID=str(self.tenant_b.id)
        )
        self.assertEqual(res_del.status_code, 404)

    def test_tc_tenant_03_system_maintenance_alert(self):
        """TC-TENANT-03: System maintenance announcements dispatched to active tenants."""
        from notifications.services import notify_system_maintenance
        notifs = notify_system_maintenance(
            title="Cập nhật bảo trì máy chủ",
            message="Máy chủ sẽ tạm dừng 15 phút lúc 23:00.",
            scheduled_time="23:00"
        )
        self.assertTrue(len(notifs) >= 1)
        for n in notifs:
            self.assertEqual(n.event_type, 'SYSTEM_MAINTENANCE_ALERT')
            self.assertEqual(n.severity, 'WARNING')

    def test_tc_event_01_work_order_assigned(self):
        """TC-EVENT-01: Technician receives assigned work order notification with link and actionable flag."""
        from notifications.services import notify_work_order_assigned
        notif = notify_work_order_assigned(self.work_order, assignee=self.tech_a, sender=self.mgr_user)
        self.assertIsNotNone(notif)
        self.assertEqual(notif.recipient, self.tech_a)
        self.assertEqual(notif.event_type, 'WO_ASSIGNED')
        self.assertTrue(notif.is_actionable)
        self.assertEqual(notif.action_status, 'PENDING')
        self.assertEqual(notif.sender_name_snapshot, 'manager_alex')
        self.assertIn(str(self.work_order.id), notif.link)

    def test_tc_event_02_mark_as_read_updates_timestamp(self):
        """TC-EVENT-02: Clicking read updates is_read=True and records read_at timestamp."""
        from rest_framework.test import APIClient
        notif = Notification.all_objects.create(
            tenant=self.tenant_a,
            recipient=self.tech_a,
            title="Read Check",
            message="Test read timestamp",
            is_read=False
        )
        self.assertIsNone(notif.read_at)

        client = APIClient()
        client.force_authenticate(user=self.tech_a)
        res = client.post(
            f'/api/v1/notifications/{notif.id}/read/',
            HTTP_X_TENANT_ID=str(self.tenant_a.id)
        )
        self.assertEqual(res.status_code, 200)

        notif.refresh_from_db()
        self.assertTrue(notif.is_read)
        self.assertIsNotNone(notif.read_at)

    def test_tc_event_03_mark_all_as_read(self):
        """TC-EVENT-03: Mark all as read clears unread badge and updates matching records."""
        from rest_framework.test import APIClient
        Notification.all_objects.create(
            tenant=self.tenant_a,
            recipient=self.tech_a,
            title="Note 1",
            message="M1",
            category="WORK_ORDER",
            is_read=False
        )
        Notification.all_objects.create(
            tenant=self.tenant_a,
            recipient=self.tech_a,
            title="Note 2",
            message="M2",
            category="WORK_ORDER",
            is_read=False
        )

        client = APIClient()
        client.force_authenticate(user=self.tech_a)
        res = client.post(
            '/api/v1/notifications/mark-all-read/',
            data={'category': 'WORK_ORDER'},
            format='json',
            HTTP_X_TENANT_ID=str(self.tenant_a.id)
        )
        self.assertEqual(res.status_code, 200)

        unread_count = Notification.all_objects.filter(recipient=self.tech_a, is_read=False).count()
        self.assertEqual(unread_count, 0)

    def test_tc_ooo_01_delegation_when_user_out_of_office(self):
        """TC-OOO-01: When primary assignee is OOO, a delegated task notification is created."""
        from notifications.models import NotificationPreference
        from notifications.services import notify_work_order_assigned

        # Tech A is Out-of-Office and delegates to Tech B
        NotificationPreference.all_objects.create(
            tenant=self.tenant_a,
            user=self.tech_a,
            category='ALL',
            is_out_of_office=True,
            delegated_to_user=self.tech_b
        )

        notif_a = notify_work_order_assigned(self.work_order, assignee=self.tech_a)
        self.assertIsNotNone(notif_a)

        # Verify forwarded notification exists for Tech B
        delegated_notif = Notification.all_objects.filter(
            recipient=self.tech_b,
            event_type='TASK_DELEGATED'
        ).first()
        self.assertIsNotNone(delegated_notif)
        self.assertIn("tech_john", delegated_notif.message)
        self.assertEqual(delegated_notif.metadata.get('delegated_from_username'), 'tech_john')

    def test_tc_escalate_01_periodic_escalation_scan(self):
        """TC-ESCALATE-01: Overdue unread CRITICAL notification triggers WO_ESCALATED."""
        from django.utils import timezone
        from notifications.tasks import periodic_escalation_scan

        past_sla = timezone.now() - timezone.timedelta(minutes=30)
        crit_notif = Notification.all_objects.create(
            tenant=self.tenant_a,
            recipient=self.tech_a,
            title="Critical Pressure Spike",
            message="Pressure exceeded 500 PSI.",
            severity="CRITICAL",
            event_type="WO_EMERGENCY_CREATED",
            is_read=False,
            escalation_level=0,
            escalate_at=past_sla
        )

        # Run periodic scan
        result = periodic_escalation_scan()
        self.assertIn("Escalated 1", result)

        crit_notif.refresh_from_db()
        self.assertEqual(crit_notif.escalation_level, 1)

        # Verify WO_ESCALATED alert was created for manager
        escalation_alert = Notification.all_objects.filter(
            recipient=self.mgr_user,
            event_type="WO_ESCALATED"
        ).first()
        self.assertIsNotNone(escalation_alert)
        self.assertEqual(escalation_alert.severity, "CRITICAL")

    def test_tc_action_01_read_vs_actionable_lifecycle(self):
        """TC-ACTION-01: Viewing notification sets is_read=True but keeps action_status=PENDING until resolved."""
        from rest_framework.test import APIClient
        notif = Notification.all_objects.create(
            tenant=self.tenant_a,
            recipient=self.mgr_user,
            title="Approve Spare Parts Request",
            message="Request #902 needs approval.",
            is_read=False,
            is_actionable=True,
            action_status="PENDING"
        )

        client = APIClient()
        client.force_authenticate(user=self.mgr_user)

        # 1. User reads the notification
        client.post(
            f'/api/v1/notifications/{notif.id}/read/',
            HTTP_X_TENANT_ID=str(self.tenant_a.id)
        )
        notif.refresh_from_db()
        self.assertTrue(notif.is_read)
        self.assertEqual(notif.action_status, "PENDING")

        # 2. Querying actionable tab still returns this item
        res_list = client.get(
            '/api/v1/notifications/?is_actionable=true&action_status=PENDING',
            HTTP_X_TENANT_ID=str(self.tenant_a.id)
        )
        self.assertEqual(res_list.data['data']['totalElements'], 1)

        # 3. User resolves action
        res_resolve = client.post(
            f'/api/v1/notifications/{notif.id}/resolve-action/',
            data={'action_status': 'RESOLVED'},
            format='json',
            HTTP_X_TENANT_ID=str(self.tenant_a.id)
        )
        self.assertEqual(res_resolve.status_code, 200)
        notif.refresh_from_db()
        self.assertEqual(notif.action_status, "RESOLVED")
        self.assertIsNotNone(notif.action_resolved_at)

    def test_tc_snapshot_01_sender_snapshot_on_user_deletion(self):
        """TC-SNAPSHOT-01: When sender user is deleted, sender snapshot fields preserve identity."""
        from rest_framework.test import APIClient
        sender_temp = User.objects.create_user(
            username="temp_creator",
            email="temp@alpha.com",
            password="password123",
            tenant=self.tenant_a
        )
        notif = Notification.all_objects.create(
            tenant=self.tenant_a,
            recipient=self.tech_a,
            sender=sender_temp,
            sender_name_snapshot="temp_creator",
            sender_role_snapshot="SUPERVISOR",
            title="Temporary Alert",
            message="Message from temp creator."
        )

        # Delete sender
        sender_temp.delete()

        notif.refresh_from_db()
        self.assertIsNone(notif.sender)
        self.assertEqual(notif.sender_name_snapshot, "temp_creator")
        self.assertEqual(notif.sender_role_snapshot, "SUPERVISOR")

        # Serializer should safely render snapshot
        client = APIClient()
        client.force_authenticate(user=self.tech_a)
        res = client.get(f'/api/v1/notifications/?is_read=false', HTTP_X_TENANT_ID=str(self.tenant_a.id))
        self.assertEqual(res.status_code, 200)
        item = res.data['data']['content'][0]
        self.assertIsNotNone(item['sender'])
        self.assertEqual(item['sender']['name'], "temp_creator")
        self.assertEqual(item['sender']['role'], "SUPERVISOR")

    def test_tc_edge_02_inactive_recipient_skipped(self):
        """TC-EDGE-02: Notification is not created for inactive accounts."""
        from notifications.services import send_notification
        inactive_user = User.objects.create_user(
            username="inactive_tech",
            email="inactive@alpha.com",
            password="password123",
            status="INACTIVE",
            tenant=self.tenant_a
        )
        notif = send_notification(
            recipient=inactive_user,
            title="Skipped Notice",
            message="Should not be saved",
            tenant=self.tenant_a
        )
        self.assertIsNone(notif)
        self.assertFalse(Notification.all_objects.filter(recipient=inactive_user).exists())

    def test_tc_edge_03_deduplication_storm_control(self):
        """TC-EDGE-03: Multiple duplicate events within 5 minutes update occurrence_count instead of creating new records."""
        from notifications.services import dispatch_event_notification
        from django.core.cache import cache
        cache.clear()

        # First alert
        res_1 = dispatch_event_notification(
            event_type='SENSOR_ANOMALY_DETECTED',
            tenant=self.tenant_a,
            entity_type='Asset',
            entity_id=self.asset.id,
            recipients=[self.mgr_user],
            title="High Vibration",
            message="Vibration at 8.5 mm/s"
        )
        self.assertEqual(len(res_1), 1)
        initial_id = res_1[0].id
        self.assertEqual(res_1[0].occurrence_count, 1)

        # Immediate second alert for same asset & recipient
        res_2 = dispatch_event_notification(
            event_type='SENSOR_ANOMALY_DETECTED',
            tenant=self.tenant_a,
            entity_type='Asset',
            entity_id=self.asset.id,
            recipients=[self.mgr_user],
            title="High Vibration",
            message="Vibration at 8.9 mm/s"
        )
        self.assertEqual(len(res_2), 1)
        self.assertEqual(res_2[0].id, initial_id)
        self.assertEqual(res_2[0].occurrence_count, 2)

        # Ensure total in DB did not increase
        total_in_db = Notification.all_objects.filter(
            recipient=self.mgr_user,
            event_type='SENSOR_ANOMALY_DETECTED'
        ).count()
        self.assertEqual(total_in_db, 1)

    def test_device_push_token_api(self):
        """Test registering a mobile FCM push token via API."""
        from rest_framework.test import APIClient
        client = APIClient()
        client.force_authenticate(user=self.tech_a)

        res = client.post(
            '/api/v1/notifications/devices/',
            data={'device_token': 'fcm-sample-device-token-12345', 'device_type': 'ANDROID'},
            format='json',
            HTTP_X_TENANT_ID=str(self.tenant_a.id)
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['data']['device_token'], 'fcm-sample-device-token-12345')

    def test_notification_preference_api(self):
        """Test getting and updating notification preferences via API."""
        from rest_framework.test import APIClient
        client = APIClient()
        client.force_authenticate(user=self.tech_a)

        # GET
        res_get = client.get('/api/v1/notifications/preferences/', HTTP_X_TENANT_ID=str(self.tenant_a.id))
        self.assertEqual(res_get.status_code, 200)

        # PUT
        res_put = client.put(
            '/api/v1/notifications/preferences/',
            data={
                'is_out_of_office': True,
                'delegated_to_user': str(self.tech_b.id),
                'push_enabled': True
            },
            format='json',
            HTTP_X_TENANT_ID=str(self.tenant_a.id)
        )
        self.assertEqual(res_put.status_code, 200)
        self.assertTrue(res_put.data['data']['is_out_of_office'])
        self.assertEqual(res_put.data['data']['delegated_to_user'], str(self.tech_b.id))




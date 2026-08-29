from django.test import TestCase
from django.urls import reverse

class PortalViewsTest(TestCase):
    def test_login_page_renders(self):
        response = self.client.get(reverse('portal_login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Welcome Back')
        
    def test_dashboard_redirects_if_not_logged_in(self):
        response = self.client.get(reverse('portal_dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('portal_login'), response.url)

    def test_tenants_redirects_if_not_logged_in(self):
        response = self.client.get(reverse('portal_tenants'))
        self.assertEqual(response.status_code, 302)

    def test_users_redirects_if_not_logged_in(self):
        response = self.client.get(reverse('portal_users'))
        self.assertEqual(response.status_code, 302)

    def test_roles_redirects_if_not_logged_in(self):
        response = self.client.get(reverse('portal_roles'))
        self.assertEqual(response.status_code, 302)

    def test_asset_categories_redirects_if_not_logged_in(self):
        response = self.client.get(reverse('portal_asset_categories'))
        self.assertEqual(response.status_code, 302)

    def test_hierarchy_templates_redirects_if_not_logged_in(self):
        response = self.client.get(reverse('portal_hierarchy_templates'))
        self.assertEqual(response.status_code, 302)

    def test_asset_registry_redirects_if_not_logged_in(self):
        response = self.client.get(reverse('portal_asset_registry'))
        self.assertEqual(response.status_code, 302)

    def test_work_orders_redirects_if_not_logged_in(self):
        response = self.client.get(reverse('portal_work_orders'))
        self.assertEqual(response.status_code, 302)

    def test_inventory_redirects_if_not_logged_in(self):
        response = self.client.get(reverse('portal_inventory'))
        self.assertEqual(response.status_code, 302)

    def test_pm_plans_redirects_if_not_logged_in(self):
        response = self.client.get(reverse('portal_pm_plans'))
        self.assertEqual(response.status_code, 302)

    def test_audit_logs_redirects_if_not_logged_in(self):
        response = self.client.get(reverse('portal_audit_logs'))
        self.assertEqual(response.status_code, 302)

class PortalAuthenticatedViewsTest(TestCase):
    def setUp(self):
        from users.models import User, Role
        from core.models import Tenant
        self.tenant = Tenant.objects.create(name='Test Tenant', tenant_code='TEST')
        self.user = User.objects.create_user(username='admin', email='admin@test.com', password='password', tenant_id=self.tenant.id)
        self.client.login(username='admin', password='password')

    def test_dashboard_renders(self):
        response = self.client.get(reverse('portal_dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_tenants_renders(self):
        response = self.client.get(reverse('portal_tenants'))
        self.assertEqual(response.status_code, 200)

    def test_users_renders(self):
        response = self.client.get(reverse('portal_users'))
        self.assertEqual(response.status_code, 200)

    def test_roles_renders(self):
        response = self.client.get(reverse('portal_roles'))
        self.assertEqual(response.status_code, 200)

    def test_asset_categories_renders(self):
        response = self.client.get(reverse('portal_asset_categories'))
        self.assertEqual(response.status_code, 200)

    def test_hierarchy_templates_renders(self):
        response = self.client.get(reverse('portal_hierarchy_templates'))
        self.assertEqual(response.status_code, 200)

    def test_asset_registry_renders(self):
        response = self.client.get(reverse('portal_asset_registry'))
        self.assertEqual(response.status_code, 200)

    def test_work_orders_renders(self):
        response = self.client.get(reverse('portal_work_orders'))
        self.assertEqual(response.status_code, 200)

    def test_inventory_renders(self):
        response = self.client.get(reverse('portal_inventory'))
        self.assertEqual(response.status_code, 200)

    def test_pm_plans_renders(self):
        response = self.client.get(reverse('portal_pm_plans'))
        self.assertEqual(response.status_code, 200)

    def test_audit_logs_renders(self):
        response = self.client.get(reverse('portal_audit_logs'))
        self.assertEqual(response.status_code, 200)

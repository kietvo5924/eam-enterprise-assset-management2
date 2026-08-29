from rest_framework.test import APITestCase
from django.urls import reverse
from core.models import Tenant
from users.models import User, Role, Permission

class SystemTenantTestCase(APITestCase):
    def setUp(self):
        # Create system admin
        self.sys_tenant = Tenant.objects.create(name='System', tenant_code='SYS', id="00000000-0000-0000-0000-000000000000")
        self.sys_admin = User.all_objects.create_user(username='sysadmin', password='password', tenant=self.sys_tenant)
        self.sys_role = Role.all_objects.create(name='SYSTEM_ADMIN', is_system=True, tenant=self.sys_tenant)
        self.sys_perm = Permission.objects.create(id='system:admin', name='System Admin')
        self.sys_role.permissions.add(self.sys_perm)
        self.sys_admin.roles.add(self.sys_role)
        
        # Get JWT for sysadmin
        response = self.client.post('/api/v1/auth/login/', {'username': 'sysadmin', 'password': 'password'})
        self.token = response.data['data']['token']
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + self.token)

    def test_create_tenant_and_admin(self):
        # 1. Create Tenant
        response = self.client.post('/api/v1/system/tenants', {
            'name': 'New Tenant',
            'tenantCode': 'NEWTENANT',
            'servicePlan': 'PRO'
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])
        tenant_id = response.data['data']['id']
        
        # 2. Create Tenant Admin
        admin_response = self.client.post(f'/api/v1/system/tenants/{tenant_id}/admins', {
            'username': 'admin@newtenant.com',
            'password': 'password123'
        })
        self.assertEqual(admin_response.status_code, 200)
        self.assertTrue(admin_response.data['success'])
        
        # Verify DB
        tenant = Tenant.objects.get(id=tenant_id)
        self.assertEqual(tenant.tenant_code, 'NEWTENANT')
        self.assertEqual(tenant.service_plan, 'PRO')
        
        admin = User.all_objects.get(username='admin@newtenant.com')
        self.assertEqual(str(admin.tenant_id), tenant_id)
        self.assertTrue(admin.roles.filter(name='TENANT_ADMIN').exists())

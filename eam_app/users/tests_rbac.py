from rest_framework.test import APITestCase
from django.urls import reverse
from core.models import Tenant
from users.models import User, Role, Permission

class RBACTestCase(APITestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Test Tenant', tenant_code='TT')
        
        # Create permissions
        self.perm_read = Permission.objects.create(id='role:read', name='Read Roles')
        self.perm_create = Permission.objects.create(id='role:create', name='Create Roles')
        self.perm_update = Permission.objects.create(id='role:update', name='Update Roles')
        self.perm_delete = Permission.objects.create(id='role:delete', name='Delete Roles')
        
        # Create roles
        self.role_admin = Role.objects.create(name='Admin', tenant=self.tenant)
        self.role_admin.permissions.add(self.perm_read, self.perm_create, self.perm_update, self.perm_delete)
        
        self.role_viewer = Role.objects.create(name='Viewer', tenant=self.tenant)
        self.role_viewer.permissions.add(self.perm_read)
        
        # Create users
        self.admin = User.objects.create_user(username='admin_rbac', password='password', tenant=self.tenant)
        self.admin.roles.add(self.role_admin)
        
        self.viewer = User.objects.create_user(username='viewer', password='password', tenant=self.tenant)
        self.viewer.roles.add(self.role_viewer)
        
    def _login(self, username):
        response = self.client.post('/api/v1/auth/login/', {'username': username, 'password': 'password'})
        token = response.data['data']['token']
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + token)
        
    def test_viewer_permissions(self):
        self._login('viewer')
        
        # Can read roles
        response = self.client.get('/api/v1/roles')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])
        
        # Cannot create roles
        response = self.client.post('/api/v1/roles', {
            'name': 'New Role',
            'permissionIds': ['role:read']
        })
        self.assertEqual(response.status_code, 403)
        self.assertFalse(response.data['success'])
        
    def test_admin_permissions(self):
        self._login('admin_rbac')
        
        # Create role
        response = self.client.post('/api/v1/roles', {
            'name': 'New Role',
            'permissionIds': ['role:read']
        }, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data['success'])
        role_id = response.data['data']['id']
        
        # Update role
        response = self.client.put(f'/api/v1/roles/{role_id}', {
            'name': 'New Role Updated',
            'permissionIds': []
        }, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        
        # Delete role
        response = self.client.delete(f'/api/v1/roles/{role_id}')
        self.assertEqual(response.status_code, 200, response.data)

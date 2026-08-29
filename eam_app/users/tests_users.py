from rest_framework.test import APITestCase
from django.urls import reverse
from core.models import Tenant
from users.models import User, Role, Permission

class UserManagementTestCase(APITestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Test Tenant', tenant_code='TT')
        
        # Create permissions
        self.perm_user_read = Permission.objects.create(id='user:read', name='Read Users')
        self.perm_user_create = Permission.objects.create(id='user:create', name='Create Users')
        self.perm_user_update = Permission.objects.create(id='user:update', name='Update Users')
        
        # Create roles
        self.role_admin = Role.objects.create(name='Admin', tenant=self.tenant)
        self.role_admin.permissions.add(self.perm_user_read, self.perm_user_create, self.perm_user_update)
        
        # Create users
        self.admin = User.objects.create_user(username='admin_users', email='admin@test.com', password='password', tenant=self.tenant)
        self.admin.roles.add(self.role_admin)
        
        # Get JWT for admin
        response = self.client.post('/api/v1/auth/login/', {'username': 'admin_users', 'password': 'password'})
        self.token = response.data['data']['token']
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + self.token)
        
    def test_user_crud(self):
        # 1. Create User
        response = self.client.post('/api/v1/users', {
            'username': 'newuser',
            'email': 'newuser@test.com',
            'password': 'password123',
            'roleIds': [str(self.role_admin.id)]
        }, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        user_id = response.data['data']['id']
        
        # 2. Get Users
        response = self.client.get('/api/v1/users')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(len(response.data['data']['content']) >= 2) # admin + newuser
        
        # 3. Update User
        response = self.client.put(f'/api/v1/users/{user_id}', {
            'username': 'updateduser',
            'roleIds': []
        }, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['data']['username'], 'updateduser')
        
        # 4. Disable User
        response = self.client.put(f'/api/v1/users/{user_id}/disable')
        self.assertEqual(response.status_code, 200, response.data)
        
        disabled_user = User.objects.get(id=user_id)
        self.assertEqual(disabled_user.status, 'INACTIVE')
        
        # 5. Enable User
        response = self.client.put(f'/api/v1/users/{user_id}/enable')
        self.assertEqual(response.status_code, 200, response.data)
        
        enabled_user = User.objects.get(id=user_id)
        self.assertEqual(enabled_user.status, 'ACTIVE')
        
    def test_user_invite(self):
        response = self.client.post('/api/v1/users/invite', {
            'username': 'inviteduser',
            'email': 'invite@test.com',
            'password': 'password123',
            'roleIds': []
        }, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        
        invited_user = User.objects.get(username='inviteduser')
        self.assertIsNotNone(invited_user)
        self.assertEqual(invited_user.email, 'invite@test.com')

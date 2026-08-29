from django.test import TestCase
from django.urls import reverse
from core.models import Tenant
from users.models import User
import uuid

class AuthenticationTestCase(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Test Tenant')
        self.user = User.objects.create_user(
            username='testuser', 
            password='testpassword',
            tenant=self.tenant
        )
        self.login_url = reverse('token_obtain_pair')

    def test_token_obtain(self):
        response = self.client.post(self.login_url, {
            'username': 'testuser',
            'password': 'testpassword'
        })
        
        data = response.json()
        self.assertEqual(response.status_code, 200)
        
        self.assertTrue(data['success'])
        token = data['data']['token']
        from rest_framework_simplejwt.tokens import AccessToken
        access_token = AccessToken(token)
        
        # Java uses sub for username, and tenantId for tenant_id
        self.assertEqual(access_token['sub'], 'testuser')
        self.assertEqual(access_token['tenantId'], str(self.tenant.id))
        self.assertEqual(access_token['username'], 'testuser')

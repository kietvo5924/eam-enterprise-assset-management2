import pytest
from django.urls import reverse
from users.models import User, Role, Permission
from core.models import Tenant
import json

@pytest.mark.django_db
def test_portal_settings_view_get(client):
    tenant = Tenant.objects.create(name='Test Tenant')
    user = User.objects.create(username='admin', tenant=tenant)
    role = Role.objects.create(name='Admin Role', tenant=tenant)
    perm = Permission.objects.get_or_create(id='tenant:read', name='Tenant Read')[0]
    role.permissions.add(perm)
    user.roles.add(role)
    
    client.force_login(user)
    
    url = reverse('portal_settings')
    response = client.get(url)
    assert response.status_code == 200

@pytest.mark.django_db
def test_portal_settings_view_post(client):
    tenant = Tenant.objects.create(name='Test Tenant')
    user = User.objects.create(username='admin', tenant=tenant)
    role = Role.objects.create(name='Admin Role', tenant=tenant)
    perm = Permission.objects.get_or_create(id='tenant:update', name='Tenant Update')[0]
    role.permissions.add(perm)
    user.roles.add(role)
    
    client.force_login(user)
    
    url = reverse('portal_settings')
    data = {'name': 'New Name', 'timezone': 'Asia/Tokyo', 'logoUrl': 'http://logo'}
    response = client.post(url, data=json.dumps(data), content_type='application/json')
    assert response.status_code == 200
    
    tenant.refresh_from_db()
    assert tenant.name == 'New Name'
    assert tenant.timezone == 'Asia/Tokyo'
    assert tenant.logo_url == 'http://logo'

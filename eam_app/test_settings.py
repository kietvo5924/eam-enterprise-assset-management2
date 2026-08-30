import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.test import Client
from users.models import User
from core.models import Tenant

print('Initializing test...')
client = Client()

# Get the first active user or super admin
user = User.objects.filter(is_superuser=True).first()
if not user:
    print('No superuser found')
    exit()

client.force_login(user)

print('Testing GET /settings/...')
response = client.get('/settings/')
print('GET Status:', response.status_code)
if response.status_code == 200:
    print('Success! View renders settings.html')
else:
    print('Failed:', response.content)

print('Testing POST /settings/ (Timezone & Logo Update)...')
payload = {
    'name': 'Test Organization',
    'logoUrl': 'https://example.com/new-logo.png',
    'timezone': 'Asia/Tokyo'
}
response = client.post('/settings/', data=json.dumps(payload), content_type='application/json')
print('POST Status:', response.status_code)
print('POST Content:', response.content.decode())

if response.status_code == 200:
    user.tenant.refresh_from_db()
    print('Tenant Name:', user.tenant.name)
    print('Tenant Logo URL:', user.tenant.logo_url)
    print('Tenant Timezone:', user.tenant.timezone)
    if user.tenant.timezone == 'Asia/Tokyo' and user.tenant.logo_url == 'https://example.com/new-logo.png':
        print('Integration Test Passed!')
    else:
        print('Integration Test Failed - Data not saved')

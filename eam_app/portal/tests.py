import json
import uuid
from unittest.mock import patch

from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.test import Client, TestCase, override_settings

from core.models import Tenant
from portal.contact_service import (
    CONTACT_EMAIL_SUBJECT,
    SYSTEM_SUPER_ADMIN_ID,
    SYSTEM_TENANT_ID,
    _LOCAL_RATE_STORE,
    resolve_system_super_admin_email,
)
from users.models import Role, User


class SeedCoreAndContactSuperAdminTests(TestCase):
    def setUp(self):
        cache.clear()
        _LOCAL_RATE_STORE.clear()
        self.system_tenant, _ = Tenant.objects.get_or_create(
            id=SYSTEM_TENANT_ID,
            defaults={
                'name': 'System Administration',
                'tenant_code': 'SYSTEM',
                'service_plan': 'ENTERPRISE',
                'timezone': 'UTC',
            },
        )
        self.super_role, _ = Role.all_objects.get_or_create(
            id=SYSTEM_SUPER_ADMIN_ID,
            defaults={
                'tenant_id': SYSTEM_TENANT_ID,
                'name': 'SUPER_ADMIN',
                'description': 'Super Administrator for System',
                'is_system': True,
            },
        )
        self.super_admin = User.all_objects.create_user(
            id=SYSTEM_SUPER_ADMIN_ID,
            tenant_id=SYSTEM_TENANT_ID,
            username='superadmin@eam.local',
            email='kietcun100@gmail.com',
            password='admin123',
            status='ACTIVE',
        )
        self.super_admin.roles.add(self.super_role)

    @patch('assistant.system_knowledge_scanner.scan_and_index_system_knowledge', return_value={'indexed_chunks': 0})
    def test_seed_core_updates_existing_super_admin_and_is_idempotent(self, _mock_scan):
        self.super_admin.email = 'old_email@example.com'
        self.super_admin.save(update_fields=['email'])
        original_password_hash = self.super_admin.password

        call_command('seed_core')
        call_command('seed_core')

        super_admins = User.all_objects.filter(
            tenant_id=SYSTEM_TENANT_ID,
            roles__name='SUPER_ADMIN',
        ).distinct()
        self.assertEqual(super_admins.count(), 1)
        refreshed = super_admins.first()
        self.assertEqual(str(refreshed.id), SYSTEM_SUPER_ADMIN_ID)
        self.assertEqual(str(refreshed.tenant_id), SYSTEM_TENANT_ID)
        self.assertEqual(refreshed.username, 'superadmin@eam.local')
        self.assertEqual(refreshed.email, 'kietcun100@gmail.com')
        self.assertEqual(refreshed.password, original_password_hash)

    @patch('assistant.system_knowledge_scanner.scan_and_index_system_knowledge', return_value={'indexed_chunks': 0})
    def test_seed_core_creates_super_admin_with_target_email_when_missing(self, _mock_scan):
        User.all_objects.filter(id=SYSTEM_SUPER_ADMIN_ID).delete()

        call_command('seed_core')

        created = User.all_objects.get(id=SYSTEM_SUPER_ADMIN_ID)
        self.assertEqual(str(created.tenant_id), SYSTEM_TENANT_ID)
        self.assertEqual(created.username, 'superadmin@eam.local')
        self.assertEqual(created.email, 'kietcun100@gmail.com')
        self.assertTrue(created.roles.filter(name='SUPER_ADMIN').exists())

    def test_resolve_recipient_ignores_other_tenants_and_local_emails(self):
        other_tenant = Tenant.objects.create(
            name='Other Factory',
            tenant_code=f'OT-{uuid.uuid4().hex[:6]}',
        )
        other_super_role = Role.all_objects.create(
            tenant_id=other_tenant.id,
            name='SUPER_ADMIN',
        )
        other_admin = User.all_objects.create_user(
            tenant_id=other_tenant.id,
            username='other_sa@factory.vn',
            email='wrong_tenant_admin@factory.vn',
            password='Secret123!',
            status='ACTIVE',
        )
        other_admin.roles.add(other_super_role)

        # Even if canonical super admin had an invalid .local email, it must not pick other tenant's admin
        self.super_admin.email = 'superadmin@eam.local'
        self.super_admin.save(update_fields=['email'])

        with override_settings(SYSTEM_ADMIN_CONTACT_EMAIL='fallback@eam.example.com'):
            resolved = resolve_system_super_admin_email()
        self.assertEqual(resolved, 'fallback@eam.example.com')

        # Active System Super Admin email takes strict precedence over fallback env var
        self.super_admin.email = 'kietcun100@gmail.com'
        self.super_admin.save(update_fields=['email'])
        with override_settings(SYSTEM_ADMIN_CONTACT_EMAIL='fallback@eam.example.com'):
            resolved = resolve_system_super_admin_email()
        self.assertEqual(resolved, 'kietcun100@gmail.com')

    def test_landing_page_public_and_does_not_leak_internal_emails(self):
        res = self.client.get('/')
        self.assertEqual(res.status_code, 200)
        html = res.content.decode('utf-8')
        self.assertIn('landing-contact-form', html)
        self.assertNotIn('kietcun100@gmail.com', html)
        self.assertNotIn('superadmin@eam.local', html)

        # /portal/ remains protected for anonymous users
        portal_res = self.client.get('/portal/')
        self.assertEqual(portal_res.status_code, 302)
        self.assertIn('/login/', portal_res['Location'])

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        DEFAULT_FROM_EMAIL='emailsend9898@gmail.com',
    )
    def test_contact_form_csrf_and_successful_delivery(self):
        csrf_client = Client(enforce_csrf_checks=True)
        get_res = csrf_client.get('/')
        self.assertEqual(get_res.status_code, 200)
        csrf_token = get_res.cookies['csrftoken'].value

        # Missing CSRF token is blocked
        no_csrf_res = csrf_client.post(
            '/contact/',
            data=json.dumps({
                'full_name': 'Nguyen Van Khach',
                'email': 'visitor@enterprise.vn',
                'company': 'Cong ty ABC',
                'subject': 'Tu van trien khai',
                'message': 'Chung toi muon tim hieu ve giai phap EAM cho 500 thiet bi.',
            }),
            content_type='application/json',
        )
        self.assertEqual(no_csrf_res.status_code, 403)

        # Valid CSRF + payload with malicious recipient override ignored
        ok_res = csrf_client.post(
            '/contact/',
            data=json.dumps({
                'full_name': 'Nguyen Van Khach',
                'email': 'visitor@enterprise.vn',
                'company': 'Cong ty ABC',
                'subject': 'Tu van trien khai',
                'message': 'Chung toi muon tim hieu ve giai phap EAM cho 500 thiet bi.',
                'to': 'attacker@evil.com',
                'from_email': 'spoof@evil.com',
            }),
            content_type='application/json',
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(ok_res.status_code, 200)
        self.assertTrue(ok_res.json()['success'])
        self.assertEqual(len(mail.outbox), 1)

        sent = mail.outbox[0]
        self.assertEqual(sent.to, ['kietcun100@gmail.com'])
        self.assertEqual(sent.from_email, 'emailsend9898@gmail.com')
        self.assertEqual(sent.reply_to, ['visitor@enterprise.vn'])
        self.assertEqual(sent.subject, CONTACT_EMAIL_SUBJECT)
        raw_msg = sent.message().as_string()
        self.assertIn('@gmail.com>', raw_msg)
        self.assertNotIn('host.docker.internal', raw_msg)
        self.assertIn('Nguyen Van Khach', sent.body)
        self.assertIn('visitor@enterprise.vn', sent.body)
        self.assertIn('Cong ty ABC', sent.body)
        self.assertIn('Tu van trien khai', sent.body)
        self.assertIn('Chung toi muon tim hieu ve giai phap EAM cho 500 thiet bi.', sent.body)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        DEFAULT_FROM_EMAIL='emailsend9898@gmail.com',
    )
    def test_contact_security_header_injection_honeypot_and_rate_limit(self):
        # Header injection attempt
        inj_res = self.client.post(
            '/contact/',
            data=json.dumps({
                'full_name': 'Bad\r\nBcc: attacker@evil.com',
                'email': 'visitor@enterprise.vn',
                'company': 'ABC',
                'subject': 'Test subject',
                'message': 'Noi dung hop le hon muoi ky tu.',
            }),
            content_type='application/json',
        )
        self.assertEqual(inj_res.status_code, 400)
        self.assertEqual(len(mail.outbox), 0)

        # Honeypot triggered
        hp_res = self.client.post(
            '/contact/',
            data=json.dumps({
                'full_name': 'Bot User',
                'email': 'bot@spam.example',
                'subject': 'Spam subject',
                'message': 'Day la noi dung spam tu bot tu dong.',
                'website': 'https://spam.example',
            }),
            content_type='application/json',
        )
        self.assertEqual(hp_res.status_code, 400)
        self.assertEqual(len(mail.outbox), 0)

        # Message length limit
        long_res = self.client.post(
            '/contact/',
            data=json.dumps({
                'full_name': 'Normal User',
                'email': 'user@enterprise.vn',
                'subject': 'Long message test',
                'message': 'A' * 3001,
            }),
            content_type='application/json',
        )
        self.assertEqual(long_res.status_code, 400)

        # Rate limit (5 requests max in window; 3 already made above -> 2 more allowed, 6th blocked)
        for _ in range(2):
            r = self.client.post(
                '/contact/',
                data=json.dumps({
                    'full_name': 'Normal User',
                    'email': 'user@enterprise.vn',
                    'subject': 'Valid subject',
                    'message': 'Noi dung hop le hon muoi ky tu.',
                }),
                content_type='application/json',
            )
            self.assertEqual(r.status_code, 200)

        blocked = self.client.post(
            '/contact/',
            data=json.dumps({
                'full_name': 'Normal User',
                'email': 'user@enterprise.vn',
                'subject': 'Valid subject',
                'message': 'Noi dung hop le hon muoi ky tu.',
            }),
            content_type='application/json',
        )
        self.assertEqual(blocked.status_code, 429)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend',
        EMAIL_HOST='smtp.gmail.com',
        EMAIL_HOST_USER='',
        EMAIL_HOST_PASSWORD='',
        DEFAULT_FROM_EMAIL='emailsend9898@gmail.com',
    )
    def test_unconfigured_smtp_returns_503(self):
        res = self.client.post(
            '/contact/',
            data=json.dumps({
                'full_name': 'Normal User',
                'email': 'user@enterprise.vn',
                'subject': 'SMTP check',
                'message': 'Noi dung hop le hon muoi ky tu.',
            }),
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 503)
        self.assertFalse(res.json()['success'])

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        DEFAULT_FROM_EMAIL='emailsend9898@gmail.com',
    )
    @patch('portal.contact_service.EmailMessage.send', side_effect=OSError('SMTP connection refused'))
    def test_smtp_delivery_failure_never_reports_success(self, _mock_send):
        res = self.client.post(
            '/contact/',
            data=json.dumps({
                'full_name': 'Normal User',
                'email': 'user@enterprise.vn',
                'subject': 'SMTP failure check',
                'message': 'Noi dung hop le hon muoi ky tu.',
            }),
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 502)
        self.assertFalse(res.json()['success'])

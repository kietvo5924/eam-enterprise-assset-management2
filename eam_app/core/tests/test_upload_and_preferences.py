import uuid
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch

from core.models import Tenant
from users.models import User, Role, Permission


class UserPreferencesAndFileUploadTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant = Tenant.objects.create(
            name="Test Factory",
            tenant_code=f"TC-{uuid.uuid4().hex[:6]}",
            theme_color="cyan"
        )
        self.admin_perm, _ = Permission.objects.get_or_create(id='tenant:update', defaults={'name': 'tenant:update'})
        self.read_perm, _ = Permission.objects.get_or_create(id='tenant:read', defaults={'name': 'tenant:read'})
        self.role = Role.objects.create(name="TENANT_ADMIN", tenant=self.tenant)
        self.role.permissions.add(self.admin_perm, self.read_perm)

        self.user = User.objects.create(
            username="user_pref_test",
            email="pref_test@factory.com",
            tenant=self.tenant
        )
        self.user.set_password("SecurePass123!")
        self.user.roles.add(self.role)
        self.user.save()

    def test_user_model_default_theme_and_language(self):
        """User mới tạo tự động có theme_color='cyan' và preferred_language='vi'."""
        self.assertEqual(self.user.theme_color, 'cyan')
        self.assertEqual(self.user.preferred_language, 'vi')

    def test_user_preferences_api_get_and_post(self):
        """API /api/v1/users/me/preferences/ hỗ trợ GET và POST cập nhật theme & language."""
        self.client.force_authenticate(user=self.user)

        # 1. GET
        get_res = self.client.get('/api/v1/users/me/preferences/')
        self.assertEqual(get_res.status_code, status.HTTP_200_OK)
        self.assertEqual(get_res.data['data']['themeColor'], 'cyan')
        self.assertEqual(get_res.data['data']['preferredLanguage'], 'vi')

        # 2. POST update to emerald and ja
        post_res = self.client.post('/api/v1/users/me/preferences/', {
            'theme_color': 'emerald',
            'preferred_language': 'ja'
        }, format='json')
        self.assertEqual(post_res.status_code, status.HTTP_200_OK)
        self.assertEqual(post_res.data['data']['themeColor'], 'emerald')
        self.assertEqual(post_res.data['data']['preferredLanguage'], 'ja')

        # 3. Reload from DB
        self.user.refresh_from_db()
        self.assertEqual(self.user.theme_color, 'emerald')
        self.assertEqual(self.user.preferred_language, 'ja')

        # 4. Check UserMeProfileView
        profile_res = self.client.get('/api/v1/users/me/profile/')
        self.assertEqual(profile_res.status_code, status.HTTP_200_OK)
        self.assertEqual(profile_res.data['data']['themeColor'], 'emerald')
        self.assertEqual(profile_res.data['data']['preferredLanguage'], 'ja')

    def test_portal_login_logout_cookies(self):
        """Khi user có preferred_language='ja' đăng nhập, cookie googtrans được gán đúng; khi logout thì bị xóa."""
        self.user.preferred_language = 'ja'
        self.user.save()

        # Login
        login_res = self.client.post('/login/', {
            'username': 'user_pref_test',
            'password': 'SecurePass123!'
        })
        self.assertEqual(login_res.status_code, 302)
        self.assertIn('googtrans', login_res.cookies)
        self.assertEqual(login_res.cookies['googtrans'].value, '/vi/ja')

        # Logout
        logout_res = self.client.get('/logout/')
        self.assertEqual(logout_res.status_code, 302)
        # Cookie googtrans should be deleted
        self.assertEqual(logout_res.cookies['googtrans']['expires'], 'Thu, 01 Jan 1970 00:00:00 GMT')

    def test_file_upload_logo_success(self):
        """Upload logo ảnh hợp lệ (.png) thành công và trả về URL."""
        self.client.force_authenticate(user=self.user)
        dummy_png = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
        file_obj = SimpleUploadedFile("brand_logo.png", dummy_png, content_type="image/png")

        res = self.client.post('/api/v1/files/upload/logo', {'file': file_obj}, format='multipart')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data['success'])
        self.assertIn('logos/', res.data['data']['url'])

    def test_file_upload_invalid_extension_rejected(self):
        """Tệp không đúng định dạng ảnh bị chặn với mã lỗi 400."""
        self.client.force_authenticate(user=self.user)
        bad_file = SimpleUploadedFile("malicious.sh", b"echo 'hack'", content_type="text/plain")

        res = self.client.post('/api/v1/files/upload/logo', {'file': bad_file}, format='multipart')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(res.data['success'])

    @patch('core.views.files.Minio')
    def test_file_upload_fallback_storage_on_minio_error(self, mock_minio):
        """Khi MinIO gặp sự cố kết nối, FileUploadView tự động Fallback sang default_storage an toàn."""
        mock_minio.side_effect = Exception("MinIO Connection Timeout")

        self.client.force_authenticate(user=self.user)
        dummy_png = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
        file_obj = SimpleUploadedFile("fallback_logo.png", dummy_png, content_type="image/png")

        res = self.client.post('/api/v1/files/upload/logo', {'file': file_obj}, format='multipart')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data['success'])
        self.assertIn('tenant-assets/logos/', res.data['data']['url'])

    def test_save_settings_with_logo_url(self):
        """Lưu cài đặt tổ chức (portal_settings) với đường dẫn logo không bao giờ bị lỗi URL."""
        self.client.force_login(self.user)
        payload = {
            'name': 'Updated Factory Name',
            'logoUrl': 'http://localhost:9900/tenant-assets/logos/test_logo.png',
            'timezone': 'Asia/Ho_Chi_Minh',
            'themeColor': 'emerald',
            'enableAiHungarian': True
        }
        res = self.client.post('/settings/', payload, content_type='application/json')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()['success'])

        self.tenant.refresh_from_db()
        self.assertEqual(self.tenant.name, 'Updated Factory Name')
        self.assertEqual(self.tenant.logo_url, 'http://localhost:9900/tenant-assets/logos/test_logo.png')

    def test_sync_and_purge_local_fallback_task(self):
        """Celery task sync_and_purge_local_fallback_files tự động đẩy ảnh local lên MinIO và xóa file trên ổ cứng."""
        from django.core.files.base import ContentFile
        from django.core.files.storage import default_storage
        from core.tasks import sync_and_purge_local_fallback_files

        # 1. Tạo file giả lập rơi vào fallback local
        dummy_png = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
        file_path = default_storage.save("tenant-assets/logos/temp_offline_logo.png", ContentFile(dummy_png))
        self.assertTrue(default_storage.exists(file_path))

        # 2. Gán Tenant logo trỏ tới local media này
        self.tenant.logo_url = f"/media/{file_path}"
        self.tenant.save()

        # 3. Chạy task đồng bộ Celery
        result = sync_and_purge_local_fallback_files()
        self.assertEqual(result.get('status'), 'success')
        self.assertGreaterEqual(result.get('synced_logos', 0), 1)

        # 4. Kiểm tra file trên ổ cứng local đã được xóa sạch (Purged)
        self.assertFalse(default_storage.exists(file_path))

        # 5. Kiểm tra URL Tenant đã được cập nhật sang MinIO
        self.tenant.refresh_from_db()
        self.assertTrue(self.tenant.logo_url.startswith('http://localhost:9900/tenant-assets/logos/'))


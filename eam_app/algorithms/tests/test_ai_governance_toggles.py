import uuid
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from core.models import Tenant
from users.models import User, Role, Permission
from assets.models import Asset, AssetCategory, MeterReading
from workorders.models import WorkOrder
from algorithms.anomaly_detection.engine import ConditionMonitoringEngine


class AIGovernanceTogglesTestCase(TestCase):
    def setUp(self):
        # 1. Tạo Tenant kiểm thử
        self.tenant = Tenant.objects.create(
            name="Test Industrial Corp",
            tenant_code="T-IND-01",
            theme_color="cyan",
            enable_tsp_routing=True,
            enable_ai_hungarian=True,
            enable_ai_genetic=True,
            enable_ai_rul=True,
            enable_ai_anomaly_detection=True,
            enable_ai_cost_forecasting=True
        )

        # 2. Tạo Quyền và Role
        perms = [
            'tenant:read', 'tenant:update',
            'work_order:read', 'work_order:update',
            'asset:read', 'asset:update'
        ]
        created_perms = []
        for p in perms:
            perm_obj, _ = Permission.objects.get_or_create(id=p, defaults={'name': p})
            created_perms.append(perm_obj)

        self.admin_role = Role.objects.create(tenant=self.tenant, name="AdminRole")
        self.admin_role.permissions.set(created_perms)

        # 3. Tạo User
        self.user = User.objects.create_user(
            username="testadmin",
            email="admin@test.com",
            password="Password123!",
            tenant=self.tenant
        )
        self.user.roles.add(self.admin_role)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.test_category = AssetCategory.objects.create(tenant=self.tenant, name="Thiết bị quay")
        self.test_asset = Asset.objects.create(
            tenant=self.tenant,
            name="Máy nén khí Atlas Copco",
            category=self.test_category,
            qr_code=f"QR-{uuid.uuid4().hex[:8]}",
            status="OPERATIONAL",
            asset_type="MACHINERY"
        )

    def test_tenant_default_toggles_are_all_true(self):
        """Kiểm tra nguyên tắc mặc định: tất cả setting AI đều BẬT, theme mặc định là cyan."""
        new_tenant = Tenant.objects.create(name="Default Tenant", tenant_code="T-DEF-01")
        self.assertTrue(new_tenant.enable_ai_hungarian)
        self.assertTrue(new_tenant.enable_ai_genetic)
        self.assertTrue(new_tenant.enable_ai_rul)
        self.assertTrue(new_tenant.enable_ai_anomaly_detection)
        self.assertTrue(new_tenant.enable_ai_cost_forecasting)
        self.assertTrue(new_tenant.enable_tsp_routing)
        self.assertEqual(new_tenant.theme_color, 'cyan')

    def test_tenant_settings_api_get_and_put(self):
        """Kiểm tra API TenantSettingsView trả về và cập nhật đầy đủ các cờ AI & themeColor."""
        # GET
        res = self.client.get('/api/v1/tenant/settings')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()['data']
        self.assertEqual(data['themeColor'], 'cyan')
        self.assertTrue(data['enableAiHungarian'])
        self.assertTrue(data['enableAiGenetic'])
        self.assertTrue(data['enableAiRul'])

        # PUT: Tắt một số thuật toán và đổi màu theme sang emerald
        update_payload = {
            'themeColor': 'emerald',
            'enableAiHungarian': False,
            'enableAiRul': False,
            'enableAiAnomalyDetection': False
        }
        res_put = self.client.put('/api/v1/tenant/settings', data=update_payload, format='json')
        self.assertEqual(res_put.status_code, status.HTTP_200_OK)

        self.tenant.refresh_from_db()
        self.assertEqual(self.tenant.theme_color, 'emerald')
        self.assertFalse(self.tenant.enable_ai_hungarian)
        self.assertFalse(self.tenant.enable_ai_rul)
        self.assertFalse(self.tenant.enable_ai_anomaly_detection)
        self.assertTrue(self.tenant.enable_ai_genetic)

    def test_hungarian_guardrail_when_disabled(self):
        """Khi enable_ai_hungarian=False, API preview tự động từ chối và trả về AI_FEATURE_DISABLED."""
        self.tenant.enable_ai_hungarian = False
        self.tenant.save()

        # Tạo 1 phiếu WO
        wo = WorkOrder.objects.create(
            tenant=self.tenant,
            asset=self.test_asset,
            title="Sửa máy nén khí",
            status="CREATED",
            priority="HIGH",
            created_by=self.user
        )

        res = self.client.post('/api/v1/work-orders/auto-assign/preview/', data={
            'workOrderIds': [str(wo.id)]
        }, format='json')

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        err = res.json().get('error', {})
        self.assertEqual(err.get('code'), 'AI_FEATURE_DISABLED')
        self.assertIn('Hungarian', err.get('message', ''))

    def test_genetic_algorithm_guardrail_when_disabled(self):
        """Khi enable_ai_genetic=False, API initiate tự động từ chối và trả về AI_FEATURE_DISABLED."""
        self.tenant.enable_ai_genetic = False
        self.tenant.save()

        wo = WorkOrder.objects.create(
            tenant=self.tenant,
            asset=self.test_asset,
            title="Bảo dưỡng động cơ 3 pha",
            status="CREATED",
            priority="MEDIUM",
            created_by=self.user
        )

        res = self.client.post('/api/v1/work-orders/ga-auto-assign/', data={
            'workOrderIds': [str(wo.id)]
        }, format='json')

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        err = res.json().get('error', {})
        self.assertEqual(err.get('code'), 'AI_FEATURE_DISABLED')
        self.assertIn('di truyền (GA)', err.get('message', ''))

    def test_predictive_rul_guardrail_when_disabled(self):
        """Khi enable_ai_rul=False, API RUL Detail trả về trạng thái fallback DISABLED và Run trả về 400."""
        self.tenant.enable_ai_rul = False
        self.tenant.save()

        cat = AssetCategory.objects.create(tenant=self.tenant, name="Bơm công nghiệp")
        asset = Asset.objects.create(
            tenant=self.tenant,
            name="Máy bơm ly tâm P-01",
            category=cat,
            qr_code=f"QR-{uuid.uuid4().hex[:8]}",
            status="OPERATIONAL",
            asset_type="MACHINERY"
        )

        # GET detail: trả về fallback an toàn (200 OK với aiEnabled=False)
        res_get = self.client.get(f'/api/v1/assets/{asset.id}/rul-prediction/')
        self.assertEqual(res_get.status_code, status.HTTP_200_OK)
        data = res_get.json()['data']
        self.assertFalse(data['aiEnabled'])
        self.assertEqual(data['riskLevel'], 'DISABLED')
        self.assertIsNone(data['operatingRulDays'])

        # POST run: bị từ chối
        res_run = self.client.post(f'/api/v1/assets/{asset.id}/rul-prediction/run/')
        self.assertEqual(res_run.status_code, status.HTTP_400_BAD_REQUEST)

    def test_anomaly_detection_guardrail_when_disabled(self):
        """Khi enable_ai_anomaly_detection=False, Engine ghi nhận đo đạc nhưng bỏ qua tính toán AI và không tự tạo WO."""
        self.tenant.enable_ai_anomaly_detection = False
        self.tenant.save()

        cat = AssetCategory.objects.create(tenant=self.tenant, name="Quạt thông gió")
        asset = Asset.objects.create(
            tenant=self.tenant,
            name="Quạt ly tâm F-101",
            category=cat,
            qr_code=f"QR-{uuid.uuid4().hex[:8]}",
            status="OPERATIONAL",
            asset_type="MACHINERY"
        )

        readings_payload = [{
            "metricCode": "VIBRATION",
            "readingValue": 15.5,
            "unit": "mm/s",
            "operatingState": "RUNNING"
        }]

        result = ConditionMonitoringEngine.process_readings(
            asset=asset,
            readings_data=readings_payload,
            tenant=self.tenant,
            recorded_by=self.user
        )

        self.assertEqual(result['savedReadingsCount'], 1)
        summary = result['analysisSummary']
        self.assertFalse(summary['hasAnomaly'])
        self.assertFalse(summary.get('aiEnabled', True))
        self.assertEqual(summary.get('mode'), 'STANDARD_STATIC_ONLY')
        # Không có Work Order nào bị tự động tạo
        self.assertEqual(WorkOrder.objects.filter(asset=asset).count(), 0)

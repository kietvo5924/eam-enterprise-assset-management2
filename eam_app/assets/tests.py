from django.test import TestCase
from rest_framework.test import APIClient

from core.models import Tenant
from core.tenant_context import set_current_tenant, clear_current_tenant
from users.models import User, Role, Permission
from assets.models import Asset, AssetCategory, Location


class LocationFloorplanIsolationTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant_a = Tenant.objects.create(name="Tenant A Corp", tenant_code="TENANT_A_FP")
        self.tenant_b = Tenant.objects.create(name="Tenant B Corp", tenant_code="TENANT_B_FP")

        self.perm_loc = Permission.objects.create(id="location:read", name="location:read", description="Read Location")
        self.perm_asset = Permission.objects.create(id="asset:read", name="asset:read", description="Read Asset")

        self.role_a = Role.objects.create(name="VIEWER_A", tenant=self.tenant_a)
        self.role_a.permissions.add(self.perm_loc, self.perm_asset)

        self.user_a = User.objects.create_user(
            username="user_a_fp",
            email="user_a@tenanta.local",
            password="password123",
            tenant=self.tenant_a,
        )
        self.user_a.roles.add(self.role_a)

        self.superuser = User.objects.create_superuser(
            username="super_fp",
            email="super@eam.local",
            password="password123",
            tenant=self.tenant_a,
        )

        self.loc_a = Location.all_objects.create(
            name="Factory A",
            code="LOC_A_FP",
            tenant=self.tenant_a,
            is_active=True,
        )
        self.loc_b = Location.all_objects.create(
            name="Secret Factory B",
            code="LOC_B_FP",
            tenant=self.tenant_b,
            is_active=True,
        )
        self.cat_b = AssetCategory.all_objects.create(name="CNC B", tenant=self.tenant_b)
        self.asset_b = Asset.all_objects.create(
            name="Secret Asset B",
            serial_number="SEC-B-001",
            qr_code="QR-SEC-B-001",
            category=self.cat_b,
            location=self.loc_b,
            tenant=self.tenant_b,
            is_active=True,
        )

    def tearDown(self):
        clear_current_tenant()

    def test_cross_tenant_focus_asset_id_idor_blocked(self):
        set_current_tenant(self.tenant_a.id)
        self.client.force_authenticate(user=self.user_a)

        res = self.client.get(f"/api/v1/locations/floorplan/?focusAssetId={self.asset_b.id}")
        self.assertEqual(res.status_code, 404)
        self.assertNotIn("Secret Factory B", str(res.content))
        self.assertNotIn(str(self.loc_b.id), str(res.content))

    def test_same_tenant_focus_asset_id_succeeds(self):
        cat_a = AssetCategory.all_objects.create(name="CNC A", tenant=self.tenant_a)
        asset_a = Asset.all_objects.create(
            name="Asset A",
            serial_number="A-001",
            qr_code="QR-A-001",
            category=cat_a,
            location=self.loc_a,
            tenant=self.tenant_a,
            is_active=True,
        )
        set_current_tenant(self.tenant_a.id)
        self.client.force_authenticate(user=self.user_a)

        res = self.client.get(f"/api/v1/locations/floorplan/?focusAssetId={asset_a.id}")
        self.assertEqual(res.status_code, 200)
        data = res.json().get("data", {})
        self.assertEqual(data["locationId"], str(self.loc_a.id))

    def test_superuser_preserves_cross_tenant_floorplan_lookup(self):
        clear_current_tenant()
        self.client.force_authenticate(user=self.superuser)

        res = self.client.get(f"/api/v1/locations/floorplan/?focusAssetId={self.asset_b.id}")
        self.assertEqual(res.status_code, 200)
        data = res.json().get("data", {})
        self.assertEqual(data["locationId"], str(self.loc_b.id))

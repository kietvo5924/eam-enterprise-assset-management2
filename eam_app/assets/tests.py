from rest_framework.test import APITestCase
from core.models import Tenant
from users.models import User, Role, Permission
from assets.models import Location, AssetCategory, HierarchyTemplate, SparePart, Asset, MeterReading

class AssetsTestCase(APITestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Test Tenant', tenant_code='TT')
        
        # Permissions
        self.perm_loc_read = Permission.objects.create(id='location:read', name='Read Location')
        self.perm_loc_create = Permission.objects.create(id='location:create', name='Create Location')
        self.perm_loc_update = Permission.objects.create(id='location:update', name='Update Location')
        self.perm_loc_delete = Permission.objects.create(id='location:delete', name='Delete Location')
        
        self.perm_cat_read = Permission.objects.create(id='asset_category:read', name='Read Cat')
        self.perm_cat_create = Permission.objects.create(id='asset_category:create', name='Create Cat')
        self.perm_cat_update = Permission.objects.create(id='asset_category:update', name='Update Cat')
        self.perm_cat_delete = Permission.objects.create(id='asset_category:delete', name='Delete Cat')
        
        self.perm_inv_read = Permission.objects.create(id='inventory:read', name='Read Inv')
        self.perm_inv_create = Permission.objects.create(id='inventory:create', name='Create Inv')
        self.perm_inv_update = Permission.objects.create(id='inventory:update', name='Update Inv')
        self.perm_inv_delete = Permission.objects.create(id='inventory:delete', name='Delete Inv')
        
        self.role_admin = Role.objects.create(name='Admin', tenant=self.tenant)
        self.role_admin.permissions.add(
            self.perm_loc_read, self.perm_loc_create, self.perm_loc_update, self.perm_loc_delete,
            self.perm_cat_read, self.perm_cat_create, self.perm_cat_update, self.perm_cat_delete,
            self.perm_inv_read, self.perm_inv_create, self.perm_inv_update, self.perm_inv_delete
        )
        
        self.admin = User.objects.create_user(username='admin_assets', email='admin@assets.com', password='password', tenant=self.tenant)
        self.admin.roles.add(self.role_admin)
        
        response = self.client.post('/api/v1/auth/login/', {'username': 'admin_assets', 'password': 'password'})
        self.token = response.data['data']['token']
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + self.token)
        
    def test_location_crud(self):
        # Create
        response = self.client.post('/api/v1/locations', {
            'name': 'Hanoi HQ',
            'parentId': '  Vietnam! Hanoi? '
        }, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        loc_id = response.data['data']['id']
        self.assertEqual(response.data['data']['parent_id'], 'Vietnam_Hanoi')
        
        # Wait, the ltree normalization will do:
        # Vietnam! Hanoi? -> Vietnam__Hanoi__ -> Vietnam_Hanoi_
        
        # Get
        response = self.client.get('/api/v1/locations')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['totalElements'], 1)
        
        # Update
        response = self.client.put(f'/api/v1/locations/{loc_id}', {
            'name': 'Hanoi Branch',
            'parentId': 'Vietnam.HN',
            'description': 'Updated'
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['name'], 'Hanoi Branch')
        self.assertEqual(response.data['data']['parent_id'], 'Vietnam.HN')
        
        # Delete (soft)
        response = self.client.delete(f'/api/v1/locations/{loc_id}')
        self.assertEqual(response.status_code, 200)
        
        loc = Location.objects.get(id=loc_id)
        self.assertFalse(loc.is_active)
        
    def test_asset_category_crud(self):
        # Create
        response = self.client.post('/api/v1/asset-categories', {
            'name': 'Electronics'
        }, format='json')
        self.assertEqual(response.status_code, 200)
        cat_id = response.data['data']['id']
        
        # Create duplicate name
        response = self.client.post('/api/v1/asset-categories', {
            'name': 'Electronics'
        }, format='json')
        self.assertEqual(response.status_code, 400) # DRF exception
        
        # Get
        response = self.client.get('/api/v1/asset-categories')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['totalElements'], 1)
        
        # Update
        response = self.client.put(f'/api/v1/asset-categories/{cat_id}', {
            'name': 'Computers',
            'description': 'Laptops and PCs'
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['name'], 'Computers')
        
        # Delete (soft)
        response = self.client.delete(f'/api/v1/asset-categories/{cat_id}')
        self.assertEqual(response.status_code, 200)
        
        cat = AssetCategory.objects.get(id=cat_id)
        self.assertFalse(cat.is_active)

    def test_hierarchy_template_crud(self):
        # Create
        response = self.client.post('/api/v1/hierarchy-templates', {
            'name': 'HVAC System',
            'path': ' Facility! HVAC? ',
            'description': 'HVAC Template'
        }, format='json')
        self.assertEqual(response.status_code, 200)
        template_id = response.data['data']['id']
        self.assertEqual(response.data['data']['path'], 'Facility_HVAC')
        
        # Create duplicate name
        response = self.client.post('/api/v1/hierarchy-templates', {
            'name': 'HVAC System'
        }, format='json')
        self.assertEqual(response.status_code, 400)
        
        # Get
        response = self.client.get('/api/v1/hierarchy-templates')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['totalElements'], 1)
        
        # Update
        response = self.client.put(f'/api/v1/hierarchy-templates/{template_id}', {
            'name': 'HVAC Updated',
            'path': 'Building.HVAC'
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['name'], 'HVAC Updated')
        self.assertEqual(response.data['data']['path'], 'Building.HVAC')
        
        # Delete (soft)
        response = self.client.delete(f'/api/v1/hierarchy-templates/{template_id}')
        self.assertEqual(response.status_code, 200)
        
        template = HierarchyTemplate.objects.get(id=template_id)
        self.assertFalse(template.is_active)

    def test_spare_part_crud(self):
        # Create
        response = self.client.post('/api/v1/spare-parts', {
            'name': 'Filter AC',
            'partNumber': 'AC-100',
            'description': 'AC filter',
            'quantityInStock': 10,
            'unitCost': 15.50
        }, format='json')
        self.assertEqual(response.status_code, 200)
        part_id = response.data['data']['id']
        self.assertEqual(float(response.data['data']['quantity_in_stock']), 10.0)
        
        # Get
        response = self.client.get('/api/v1/spare-parts')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['data']), 1)
        
        # Update
        response = self.client.put(f'/api/v1/spare-parts/{part_id}', {
            'name': 'Filter AC Pro',
            'quantityInStock': 5
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['name'], 'Filter AC Pro')
        self.assertEqual(float(response.data['data']['quantity_in_stock']), 5.0)
        
        # Delete
        response = self.client.delete(f'/api/v1/spare-parts/{part_id}')
        self.assertEqual(response.status_code, 200)
        
        with self.assertRaises(SparePart.DoesNotExist):
            SparePart.objects.get(id=part_id)

class AssetTestCase(APITestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Asset Tenant', tenant_code='AST')
        
        # Permissions
        self.perm_asset_read = Permission.objects.create(id='asset:read', name='Read Asset')
        self.perm_asset_create = Permission.objects.create(id='asset:create', name='Create Asset')
        self.perm_asset_update = Permission.objects.create(id='asset:update', name='Update Asset')
        self.perm_asset_delete = Permission.objects.create(id='asset:delete', name='Delete Asset')
        
        self.role_admin = Role.objects.create(name='Admin', tenant=self.tenant)
        self.role_admin.permissions.add(
            self.perm_asset_read, self.perm_asset_create, self.perm_asset_update, self.perm_asset_delete
        )
        
        self.admin = User.objects.create_user(username='admin_ast', email='ast@ast.com', password='password', tenant=self.tenant)
        self.admin.roles.add(self.role_admin)
        
        response = self.client.post('/api/v1/auth/login/', {'username': 'admin_ast', 'password': 'password'})
        self.token = response.data['data']['token']
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + self.token)
        
    def test_asset_crud(self):
        # Create
        response = self.client.post('/api/v1/assets', {
            'name': 'Machine A',
            'qrCode': 'QR-12345',
            'status': 'OPERATIONAL'
        }, format='json')
        self.assertEqual(response.status_code, 200)
        asset_id = response.data['data']['id']
        
        # Read
        response = self.client.get(f'/api/v1/assets/{asset_id}')
        self.assertEqual(response.status_code, 200)
        
        # Update
        response = self.client.put(f'/api/v1/assets/{asset_id}', {
            'name': 'Machine A Updated',
            'qrCode': 'QR-12345',
            'status': 'DOWN'
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['status'], 'DOWN')
        
        # Add Meter Reading
        response = self.client.post(f'/api/v1/assets/{asset_id}/meter-readings', {
            'readingValue': 100.5,
            'unit': 'Hours',
            'remarks': 'Initial reading'
        }, format='json')
        self.assertEqual(response.status_code, 200)
        
        # List Meter Readings
        response = self.client.get(f'/api/v1/assets/{asset_id}/meter-readings')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['data']), 1)
        
        # Tree
        response = self.client.get('/api/v1/assets/tree')
        self.assertEqual(response.status_code, 200)
        
        # QR
        response = self.client.get('/api/v1/assets/qr/QR-12345')
        self.assertEqual(response.status_code, 200)
        
        # Delete
        response = self.client.delete(f'/api/v1/assets/{asset_id}')
        self.assertEqual(response.status_code, 200)
        asset = Asset.objects.get(id=asset_id)
        self.assertFalse(asset.is_active)

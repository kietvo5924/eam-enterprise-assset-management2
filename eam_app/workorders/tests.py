from rest_framework.test import APITestCase
from core.models import Tenant
from users.models import User, Role, Permission
from assets.models import Asset
from workorders.models import WorkOrder

class WorkOrderTestCase(APITestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='WO Tenant', tenant_code='WOT')
        
        self.perm_read = Permission.objects.create(id='work_order:read', name='Read WO')
        self.perm_create = Permission.objects.create(id='work_order:create', name='Create WO')
        self.perm_update = Permission.objects.create(id='work_order:update', name='Update WO')
        self.perm_execute = Permission.objects.create(id='work_order:execute', name='Execute WO')
        self.perm_delete = Permission.objects.create(id='work_order:delete', name='Delete WO')
        
        self.role_admin = Role.objects.create(name='Admin', tenant=self.tenant)
        self.role_admin.permissions.add(
            self.perm_read, self.perm_create, self.perm_update, self.perm_execute, self.perm_delete
        )
        
        self.user = User.objects.create_user(username='wo_user', email='wo@w.com', password='pw', tenant=self.tenant)
        self.user.roles.add(self.role_admin)
        
        self.tech = User.objects.create_user(username='tech', email='tech@w.com', password='pw', tenant=self.tenant)
        self.tech.roles.add(self.role_admin)
        
        self.asset = Asset.objects.create(name='AC Unit', tenant=self.tenant, is_active=True, qr_code='AC001')
        
        response = self.client.post('/api/v1/auth/login/', {'username': 'wo_user', 'password': 'pw'})
        self.token = response.data['data']['token']
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + self.token)
        
        response = self.client.post('/api/v1/auth/login/', {'username': 'tech', 'password': 'pw'})
        self.tech_token = response.data['data']['token']
        
    def test_work_order_flow(self):
        # Create
        response = self.client.post('/api/v1/work-orders', {
            'assetId': str(self.asset.id),
            'title': 'Fix AC',
            'priority': 'HIGH'
        }, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        wo_id = response.data['data']['id']
        self.assertEqual(response.data['data']['status'], 'CREATED')
        
        # Read
        response = self.client.get(f'/api/v1/work-orders/{wo_id}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['title'], 'Fix AC')
        
        # Invalid state transition: CREATED -> IN_PROGRESS directly
        response = self.client.put(f'/api/v1/work-orders/{wo_id}/status', {
            'status': 'IN_PROGRESS'
        }, format='json')
        self.assertEqual(response.status_code, 400)
        
        # Assign
        response = self.client.put(f'/api/v1/work-orders/{wo_id}/assign', {
            'assignedTo': str(self.tech.id)
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['status'], 'ASSIGNED')
        
        # Switch to tech user
        response = self.client.post('/api/v1/auth/login/', {'username': 'tech', 'password': 'pw'})
        tech_token = response.data['data']['token']
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + tech_token)
        
        # Valid state transition: ASSIGNED -> IN_PROGRESS
        response = self.client.put(f'/api/v1/work-orders/{wo_id}/status', {
            'status': 'IN_PROGRESS'
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['status'], 'IN_PROGRESS')
        
        # Valid state transition: IN_PROGRESS -> COMPLETED (without notes -> error)
        response = self.client.put(f'/api/v1/work-orders/{wo_id}/status', {
            'status': 'COMPLETED'
        }, format='json')
        self.assertEqual(response.status_code, 400)
        
        # Valid state transition: IN_PROGRESS -> COMPLETED (with notes)
        response = self.client.put(f'/api/v1/work-orders/{wo_id}/status', {
            'status': 'COMPLETED',
            'resolutionNotes': 'Fixed the AC compressor',
            'actualDurationMinutes': 120
        }, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['data']['status'], 'COMPLETED')
        self.assertEqual(response.data['data']['actualDurationMinutes'], 120)

    def test_checklists_and_attachments(self):
        # Create
        response = self.client.post('/api/v1/work-orders', {
            'assetId': str(self.asset.id),
            'title': 'Fix AC',
            'priority': 'HIGH'
        }, format='json')
        wo_id = response.data['data']['id']
        
        # Add mandatory checklist directly (simulating PM plan generation)
        from workorders.models import WorkOrderChecklistItem
        WorkOrderChecklistItem.objects.create(
            work_order_id=wo_id,
            item_name='Safety check',
            is_mandatory=True,
            is_completed=False,
            tenant=self.tenant
        )
        
        # Assign & In Progress
        self.client.put(f'/api/v1/work-orders/{wo_id}/assign', {'assignedTo': str(self.tech.id)}, format='json')
        
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + self.tech_token)
        self.client.put(f'/api/v1/work-orders/{wo_id}/status', {'status': 'IN_PROGRESS'}, format='json')
        
        # Try to complete (missing notes/attachments)
        response = self.client.put(f'/api/v1/work-orders/{wo_id}/status', {'status': 'COMPLETED'}, format='json')
        self.assertEqual(response.status_code, 400)
        
        # Add notes
        response = self.client.put(f'/api/v1/work-orders/{wo_id}/notes', {'resolutionNotes': 'All done'}, format='json')
        self.assertEqual(response.status_code, 200)
        
        # Try to complete (has notes, but mandatory checklist incomplete)
        response = self.client.put(f'/api/v1/work-orders/{wo_id}/status', {'status': 'COMPLETED'}, format='json')
        self.assertEqual(response.status_code, 400)
        
        # Complete checklist
        response = self.client.post(f'/api/v1/work-orders/{wo_id}/checklists', {
            'itemName': 'Safety check',
            'isCompleted': True,
            'actualValue': 'Passed'
        }, format='json')
        self.assertEqual(response.status_code, 200)
        
        # Try to complete (should succeed now)
        response = self.client.put(f'/api/v1/work-orders/{wo_id}/status', {'status': 'COMPLETED'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['status'], 'COMPLETED')
        
    def test_inventory_and_materials(self):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + self.token)
        from assets.models import SparePart
        part = SparePart.objects.create(name='Filter', tenant=self.tenant, quantity_in_stock=10)
        
        # Create with materials
        response = self.client.post('/api/v1/work-orders', {
            'assetId': str(self.asset.id),
            'title': 'Replace filter',
            'priority': 'MEDIUM',
            'materials': [{'sparePartId': str(part.id), 'quantity': 2}]
        }, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        wo_id = response.data['data']['id']
        
        # Check stock deduction
        part.refresh_from_db()
        self.assertEqual(part.quantity_in_stock, 8)
        
        # Update materials
        response = self.client.put(f'/api/v1/work-orders/{wo_id}', {
            'assetId': str(self.asset.id),
            'title': 'Replace filter',
            'priority': 'MEDIUM',
            'materials': [{'sparePartId': str(part.id), 'quantity': 3}]
        }, format='json')
        self.assertEqual(response.status_code, 200)
        
        # Check stock deduction (restored 2, deducted 3)
        part.refresh_from_db()
        self.assertEqual(part.quantity_in_stock, 7)
        
        # Delete WO, should restore stock
        response = self.client.delete(f'/api/v1/work-orders/{wo_id}')
        self.assertEqual(response.status_code, 200)
        
        part.refresh_from_db()
        self.assertEqual(part.quantity_in_stock, 10)

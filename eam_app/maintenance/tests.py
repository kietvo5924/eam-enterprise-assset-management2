from rest_framework.test import APITestCase
from core.models import Tenant
from users.models import User, Role, Permission
from assets.models import Asset, SparePart
from maintenance.models import PmPlan, PmPlanChecklistItem, PmPlanMaterial, PmPlanAssignment

class PmPlanTestCase(APITestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='PM Tenant', tenant_code='PMT')
        
        self.perm_read = Permission.objects.create(id='pm_plan:read', name='Read PM')
        self.perm_create = Permission.objects.create(id='pm_plan:create', name='Create PM')
        self.perm_update = Permission.objects.create(id='pm_plan:update', name='Update PM')
        self.perm_delete = Permission.objects.create(id='pm_plan:delete', name='Delete PM')
        
        self.role_admin = Role.objects.create(name='Admin', tenant=self.tenant)
        self.role_admin.permissions.add(
            self.perm_read, self.perm_create, self.perm_update, self.perm_delete
        )
        
        self.user = User.objects.create_user(username='pm_user', email='pm@p.com', password='pw', tenant=self.tenant)
        self.user.roles.add(self.role_admin)
        
        self.asset = Asset.objects.create(name='Generator', tenant=self.tenant, is_active=True, qr_code='GEN001')
        self.part = SparePart.objects.create(name='Filter', tenant=self.tenant, quantity_in_stock=100)
        
        response = self.client.post('/api/v1/auth/login/', {'username': 'pm_user', 'password': 'pw'})
        self.token = response.data['data']['token']
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + self.token)
        
    def test_pm_plan_crud(self):
        # Create
        response = self.client.post('/api/v1/pm-plans', {
            'name': 'Monthly Generator Check',
            'triggerType': 'TIME',
            'intervalValue': 1.0,
            'intervalUnit': 'MONTHS',
            'checklists': [{'itemName': 'Check oil level', 'isMandatory': True}],
            'materials': [{'sparePartId': str(self.part.id), 'quantity': 1}]
        }, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        plan_id = response.data['data']['id']
        self.assertEqual(response.data['data']['name'], 'Monthly Generator Check')
        self.assertEqual(len(response.data['data']['checklists']), 1)
        self.assertEqual(len(response.data['data']['materials']), 1)
        
        # Read
        response = self.client.get(f'/api/v1/pm-plans/{plan_id}')
        self.assertEqual(response.status_code, 200)
        
        # List
        response = self.client.get('/api/v1/pm-plans')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['totalElements'], 1)
        
        # Update
        response = self.client.put(f'/api/v1/pm-plans/{plan_id}', {
            'name': 'Monthly Generator Check (Updated)',
            'triggerType': 'TIME',
            'intervalValue': 2.0,
            'intervalUnit': 'MONTHS',
            'checklists': [{'itemName': 'Check oil level', 'isMandatory': False}],
            'materials': []
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['name'], 'Monthly Generator Check (Updated)')
        self.assertEqual(len(response.data['data']['materials']), 0)
        
        # Delete
        response = self.client.delete(f'/api/v1/pm-plans/{plan_id}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(PmPlan.objects.count(), 0)
        
    def test_pm_plan_assignments(self):
        # Create plan
        plan = PmPlan.objects.create(name='Plan A', trigger_type='USAGE', tenant=self.tenant)
        
        # Assign
        response = self.client.post(f'/api/v1/pm-plans/{plan.id}/assign', {
            'assetIds': [str(self.asset.id)],
            'baselineMeterReading': 100.5
        }, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(len(response.data['data']), 1)
        assignment_id = response.data['data'][0]['id']
        
        # List assignments
        response = self.client.get(f'/api/v1/pm-plans/{plan.id}/assignments')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['totalElements'], 1)
        
        # Delete assignment
        response = self.client.delete(f'/api/v1/pm-plans/assignments/{assignment_id}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(PmPlanAssignment.objects.count(), 0)

    def test_evaluate_triggers(self):
        from maintenance.tasks import evaluate_triggers
        from workorders.models import WorkOrder
        from django.utils import timezone
        
        # Create a time-based PM Plan
        plan = PmPlan.objects.create(
            name='Daily Check', 
            trigger_type='TIME', 
            interval_value=1, 
            interval_unit='DAYS',
            tenant=self.tenant
        )
        
        # Assign to asset, make it due now by setting last_triggered_at to yesterday
        assignment = PmPlanAssignment.objects.create(
            pm_plan=plan,
            asset=self.asset,
            tenant=self.tenant,
            last_triggered_at=timezone.now() - timezone.timedelta(days=2)
        )
        
        evaluate_triggers()
        
        # Check if Work Order was created
        wo = WorkOrder.objects.filter(source_reference=f"PM_{plan.id}_ASSET_{self.asset.id}").first()
        self.assertIsNotNone(wo)
        self.assertEqual(wo.title, f"PM: Daily Check for {self.asset.name}")
        self.assertEqual(wo.status, 'CREATED')


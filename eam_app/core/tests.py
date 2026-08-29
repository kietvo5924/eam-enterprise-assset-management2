from django.test import TestCase, RequestFactory
from rest_framework.test import APITestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from unittest.mock import patch
from users.models import User, Permission
from core.models import Tenant
from django.urls import path
from django.http import JsonResponse
from core.models import Tenant, BaseTenantModel, DummyTenantModel, AuditLog
from core.middleware.tenant import TenantMiddleware
from core.tenant_context import get_current_tenant
from core.exceptions import global_exception_handler
from rest_framework.exceptions import ValidationError
import uuid

def dummy_view(request):
    return JsonResponse({'status': 'ok'})

class TenantTestCase(TestCase):
    def setUp(self):
        self.tenant1 = Tenant.objects.create(name='Tenant 1', tenant_code='T1')
        self.tenant2 = Tenant.objects.create(name='Tenant 2', tenant_code='T2')
        self.factory = RequestFactory()
        
    def test_tenant_context(self):
        # Create objects with bypassing tenant manager
        obj1 = DummyTenantModel.all_objects.create(name='Obj1', tenant=self.tenant1)
        obj2 = DummyTenantModel.all_objects.create(name='Obj2', tenant=self.tenant2)

        # Test middleware bypassing for system endpoints
        request = self.factory.get('/api/v1/system/test')
        middleware = TenantMiddleware(dummy_view)
        response = middleware(request)
        self.assertEqual(response.status_code, 200)

        # Test missing tenant
        request = self.factory.get('/api/v1/assets')
        response = middleware(request)
        self.assertEqual(response.status_code, 400)

        # Test valid tenant via header
        request = self.factory.get('/api/v1/assets', HTTP_X_TENANT_ID=str(self.tenant1.id))
        
        # Test middleware sets context
        def assert_tenant_view(req):
            self.assertEqual(get_current_tenant(), str(self.tenant1.id))
            # Test model filtering
            self.assertEqual(DummyTenantModel.objects.count(), 1)
            self.assertEqual(DummyTenantModel.objects.first().name, 'Obj1')
            return JsonResponse({'status': 'ok'})
            
        middleware = TenantMiddleware(assert_tenant_view)
        response = middleware(request)
        self.assertEqual(response.status_code, 200)

    def test_audit_logging(self):
        # Test creation audit
        obj = DummyTenantModel.all_objects.create(name='AuditTest', tenant=self.tenant1)
        audit_log = AuditLog.all_objects.filter(entity_type='DummyTenantModel', entity_id=str(obj.pk)).first()
        self.assertIsNotNone(audit_log)
        self.assertEqual(audit_log.action_type, 'CREATE')
        
        # Test update audit
        obj.name = 'AuditTestUpdated'
        obj.save()
        update_log = AuditLog.all_objects.filter(entity_type='DummyTenantModel', entity_id=str(obj.pk), action_type='UPDATE').first()
        self.assertIsNotNone(update_log)
        
        # Test delete audit
        obj_pk = str(obj.pk)
        obj.delete()
        delete_log = AuditLog.all_objects.filter(entity_type='DummyTenantModel', entity_id=obj_pk, action_type='DELETE').first()
        self.assertIsNotNone(delete_log)

    def test_global_exception_handler(self):
        exc = ValidationError("Invalid field")
        response = global_exception_handler(exc, None)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data['success'])
        self.assertEqual(response.data['message'], "Invalid field")

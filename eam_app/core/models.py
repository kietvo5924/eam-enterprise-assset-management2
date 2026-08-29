import uuid
from django.db import models
from core.tenant_context import get_current_tenant

class Tenant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    logo_url = models.URLField(max_length=1024, null=True, blank=True)
    timezone = models.CharField(max_length=100, default='UTC')
    tenant_code = models.CharField(max_length=100, unique=True, null=True, blank=True)
    service_plan = models.CharField(max_length=50, default='FREE')
    status = models.CharField(max_length=50, default='ACTIVE')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tenants'

    def __str__(self):
        return self.name

class TenantManager(models.Manager):
    def get_queryset(self):
        queryset = super().get_queryset()
        tenant_id = get_current_tenant()
        if tenant_id:
            return queryset.filter(tenant_id=tenant_id)
        return queryset

class BaseTenantModel(models.Model):
    # Using a string to refer to 'core.Tenant' prevents circular imports
    # In Java, this is just a raw tenant_id string converted to UUID. We map it nicely using Django ORM.
    tenant = models.ForeignKey(
        'core.Tenant', 
        on_delete=models.CASCADE, 
        db_column='tenant_id',
        related_name='%(class)s_set'
    )

    objects = TenantManager()
    all_objects = models.Manager() # useful for bypassing tenant filter (e.g. background tasks or admin)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        if not self.tenant_id:
            current_tenant_id = get_current_tenant()
            if current_tenant_id:
                self.tenant_id = current_tenant_id
        super().save(*args, **kwargs)

        if self.__class__.__name__ != 'AuditLog':
            from core.models import AuditLog
            from core.audit_context import get_current_user_id
            user_id = get_current_user_id() or 'system'
            action = 'CREATE' if is_new else 'UPDATE'
            # Use all_objects to bypass tenant check when creating audit logs internally
            AuditLog.all_objects.create(
                tenant_id=self.tenant_id,
                user_id=user_id,
                action_type=action,
                entity_type=self.__class__.__name__,
                entity_id=str(self.pk)
            )

    def delete(self, *args, **kwargs):
        tenant_id = self.tenant_id
        pk = str(self.pk)
        class_name = self.__class__.__name__
        
        super().delete(*args, **kwargs)
        
        if class_name != 'AuditLog':
            from core.models import AuditLog
            from core.audit_context import get_current_user_id
            user_id = get_current_user_id() or 'system'
            AuditLog.all_objects.create(
                tenant_id=tenant_id,
                user_id=user_id,
                action_type='DELETE',
                entity_type=class_name,
                entity_id=pk
            )

class DummyTenantModel(BaseTenantModel):
    name = models.CharField(max_length=50)

    class Meta:
        db_table = 'dummy_tenant_models'

class AuditLog(BaseTenantModel):
    ACTION_CHOICES = (
        ('CREATE', 'Create'),
        ('UPDATE', 'Update'),
        ('DELETE', 'Delete'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.CharField(max_length=255, null=True, blank=True)
    action_type = models.CharField(max_length=10, choices=ACTION_CHOICES)
    entity_type = models.CharField(max_length=255)
    entity_id = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'audit_logs'

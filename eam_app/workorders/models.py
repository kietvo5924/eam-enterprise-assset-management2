from django.db import models
from core.models import BaseTenantModel
from assets.models import Asset
from users.models import User
import uuid

class WorkOrder(BaseTenantModel):
    STATUS_CHOICES = (
        ('CREATED', 'Created'),
        ('ASSIGNED', 'Assigned'),
        ('IN_PROGRESS', 'In Progress'),
        ('ON_HOLD', 'On Hold'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled')
    )

    PRIORITY_CHOICES = (
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('URGENT', 'Urgent')
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='work_orders')
    title = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    priority = models.CharField(max_length=50, choices=PRIORITY_CHOICES)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='CREATED')
    
    deadline = models.DateTimeField(null=True, blank=True)
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_work_orders')
    assigned_at = models.DateTimeField(null=True, blank=True)
    actual_start_time = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(null=True, blank=True)
    
    parent_id = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='follow_up_work_orders')
    source_reference = models.CharField(max_length=255, null=True, blank=True)
    estimated_duration_minutes = models.IntegerField(null=True, blank=True)
    actual_duration_minutes = models.IntegerField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='+', db_column='created_by', db_constraint=False)
    updated_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='+', db_column='updated_by', db_constraint=False)
    
    class Meta:
        db_table = 'work_orders'
        
    def __str__(self):
        return self.title

class WorkOrderChecklistItem(BaseTenantModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    work_order = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name='checklists')
    item_name = models.CharField(max_length=255)
    is_completed = models.BooleanField(default=False)
    input_type = models.CharField(max_length=50, default='PASS_FAIL')
    expected_value = models.CharField(max_length=255, null=True, blank=True)
    actual_value = models.CharField(max_length=255, null=True, blank=True)
    is_mandatory = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='+', db_column='created_by', db_constraint=False)
    updated_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='+', db_column='updated_by', db_constraint=False)
    
    class Meta:
        db_table = 'work_order_checklists'
        
class WorkOrderAttachment(BaseTenantModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    work_order = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name='attachments')
    file_url = models.CharField(max_length=1024)
    file_name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=100)
    file_size = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='+', db_column='created_by', db_constraint=False)
    updated_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='+', db_column='updated_by', db_constraint=False)
    
    class Meta:
        db_table = 'work_order_attachments'

class WorkOrderMaterial(BaseTenantModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    work_order = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name='materials')
    spare_part = models.ForeignKey('assets.SparePart', on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=19, decimal_places=2)
    actual_cost = models.DecimalField(max_digits=19, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='+', db_column='created_by', db_constraint=False)
    updated_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='+', db_column='updated_by', db_constraint=False)
    
    class Meta:
        db_table = 'work_order_materials'

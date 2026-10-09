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

    TYPE_CHOICES = (
        ('CORRECTIVE', 'Corrective'),
        ('PREVENTIVE', 'Preventive'),
        ('EMERGENCY', 'Emergency'),
        ('BREAKDOWN', 'Breakdown'),
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
    type = models.CharField(max_length=50, choices=TYPE_CHOICES, default='CORRECTIVE', db_index=True)
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
    
    # Phase 10.3: Capitalization (CAPEX vs OPEX) & PM Overlap Suppression
    is_capitalized = models.BooleanField(default=False)
    actual_cost = models.DecimalField(max_digits=19, decimal_places=2, null=True, blank=True)
    skipped_reason = models.CharField(max_length=50, null=True, blank=True)
    skipped_reference_wo = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='suppressed_pm_orders')
    
    # Phase 11.1: Hungarian Assignment Optimization Fields
    required_skill = models.CharField(max_length=64, null=True, blank=True)
    min_skill_level = models.SmallIntegerField(default=1)
    required_certification = models.CharField(max_length=100, null=True, blank=True)
    required_tools = models.JSONField(default=list, blank=True)
    depends_on_wo = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='dependent_work_orders'
    )
    is_crew_task = models.BooleanField(default=False)
    coords_x = models.FloatField(null=True, blank=True)
    coords_y = models.FloatField(null=True, blank=True)
    floor_level = models.SmallIntegerField(default=1, null=True, blank=True)
    zone_id = models.CharField(max_length=64, blank=True, default='')
    # Phase 11.2: Genetic Algorithm Optimization Fields
    required_spare_parts = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='+', db_column='created_by', db_constraint=False)
    updated_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='+', db_column='updated_by', db_constraint=False)
    
    @property
    def code(self):
        return f"WO-{str(self.id)[:8].upper()}"

    @property
    def due_date(self):
        return self.deadline

    @due_date.setter
    def due_date(self, value):
        self.deadline = value

    @property
    def estimated_duration_hours(self):
        if self.estimated_duration_minutes is not None:
            return round(float(self.estimated_duration_minutes) / 60.0, 2)
        return 0.0

    @estimated_duration_hours.setter
    def estimated_duration_hours(self, value):
        if value is not None:
            self.estimated_duration_minutes = int(float(value) * 60)
        else:
            self.estimated_duration_minutes = None

    @property
    def actual_duration_hours(self):
        if self.actual_duration_minutes is not None:
            return round(float(self.actual_duration_minutes) / 60.0, 2)
        if self.actual_start_time and self.completed_at:
            delta = (self.completed_at - self.actual_start_time).total_seconds() / 3600.0
            return round(delta, 2)
        return None

    class Meta:
        db_table = 'work_orders'
        indexes = [
            models.Index(fields=['tenant', 'status', 'type', 'created_at']),
            models.Index(fields=['tenant', 'completed_at']),
            models.Index(fields=['tenant', 'status', 'priority'], name='work_orders_tenant__cdbaca_idx'),
            models.Index(fields=['tenant', 'depends_on_wo'], name='work_orders_tenant__a59ed9_idx'),
        ]
        
    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.tenant_id:
            try:
                from analytics.services import DashboardCacheService
                DashboardCacheService.invalidate_all(self.tenant_id)
            except Exception:
                pass

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

class LaborLog(BaseTenantModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    work_order = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name='labor_logs')
    technician = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='labor_logs')
    work_date = models.DateField()
    hours_worked = models.DecimalField(max_digits=8, decimal_places=2)
    hourly_rate = models.DecimalField(max_digits=19, decimal_places=2, default=0.00)
    cost_center_snapshot = models.CharField(max_length=255, null=True, blank=True)
    total_cost = models.DecimalField(max_digits=19, decimal_places=2, default=0.00)
    is_overtime = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'labor_logs'
        indexes = [
            models.Index(fields=['tenant', 'work_order', 'work_date']),
            models.Index(fields=['tenant', 'technician', 'work_date']),
        ]

    def save(self, *args, **kwargs):
        if self.hours_worked and self.hourly_rate:
            self.total_cost = self.hours_worked * self.hourly_rate
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.work_order.title} - {self.hours_worked}h - {self.work_date}"


class GAOptimizationJob(BaseTenantModel):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_by = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='ga_jobs')
    floorplan = models.ForeignKey('assets.Location', on_delete=models.SET_NULL, null=True, blank=True, related_name='ga_jobs')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', db_index=True)
    current_generation = models.IntegerField(default=0)
    max_generations = models.IntegerField(default=150)
    best_fitness = models.FloatField(default=0.0)
    convergence_history = models.JSONField(default=list, blank=True)
    pareto_solutions = models.JSONField(default=list, blank=True)
    work_order_ids = models.JSONField(default=list, blank=True)
    error_message = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'ga_optimization_jobs'
        indexes = [
            models.Index(fields=['tenant', 'status', '-created_at']),
        ]

    def __str__(self):
        return f"GA Job {self.id} [{self.status}] Gen: {self.current_generation}/{self.max_generations}"

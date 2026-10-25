import uuid
from django.db import models
from core.models import BaseTenantModel
from users.models import User
from assets.models import Asset, SparePart

class PmPlan(BaseTenantModel):
    TRIGGER_CHOICES = (
        ('TIME', 'Time'),
        ('USAGE', 'Usage'),
        ('METER', 'Meter'),
    )
    
    INTERVAL_UNIT_CHOICES = (
        ('DAYS', 'Days'),
        ('WEEKS', 'Weeks'),
        ('MONTHS', 'Months'),
        ('YEARS', 'Years'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    trigger_type = models.CharField(max_length=50, choices=TRIGGER_CHOICES)
    interval_value = models.DecimalField(max_digits=19, decimal_places=2, null=True, blank=True)
    interval_unit = models.CharField(max_length=50, choices=INTERVAL_UNIT_CHOICES, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_floating_schedule = models.BooleanField(default=False)
    suppress_if_pending = models.BooleanField(default=True)
    MAINTENANCE_ACTION_CHOICES = (
        ('GENERAL', 'General Maintenance / Bảo dưỡng thông thường'),
        ('MICRO_MAINTENANCE', 'Micro Maintenance / Bôi trơn, siết ốc, hiệu chỉnh nhỏ'),
        ('CORE_REPLACEMENT', 'Core Replacement / Đại tu thay thế phụ tùng cốt lõi'),
    )

    lead_time_days = models.IntegerField(default=0)
    estimated_duration_minutes = models.IntegerField(null=True, blank=True)
    assignee = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_pm_plans')
    maintenance_action = models.CharField(
        max_length=32,
        choices=MAINTENANCE_ACTION_CHOICES,
        default='GENERAL',
        db_index=True,
        help_text='Cấp độ can thiệp bảo trì mặc định áp dụng cho các Work Order tự động sinh ra'
    )
    required_tools = models.JSONField(default=list, blank=True, help_text='Danh mục mã dụng cụ chuyên dụng cần thiết')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='+', db_column='created_by', db_constraint=False)
    updated_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='+', db_column='updated_by', db_constraint=False)
    
    class Meta:
        db_table = 'pm_plans'


class PmPlanChecklistItem(BaseTenantModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pm_plan = models.ForeignKey(PmPlan, on_delete=models.CASCADE, related_name='checklists')
    item_name = models.CharField(max_length=255)
    input_type = models.CharField(max_length=50, default='PASS_FAIL')
    expected_value = models.CharField(max_length=255, null=True, blank=True)
    is_mandatory = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='+', db_column='created_by', db_constraint=False)
    updated_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='+', db_column='updated_by', db_constraint=False)

    class Meta:
        db_table = 'pm_plan_checklists'


class PmPlanMaterial(BaseTenantModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pm_plan = models.ForeignKey(PmPlan, on_delete=models.CASCADE, related_name='materials')
    spare_part = models.ForeignKey(SparePart, on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=19, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='+', db_column='created_by', db_constraint=False)
    updated_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='+', db_column='updated_by', db_constraint=False)

    class Meta:
        db_table = 'pm_plan_materials'


class PmPlanAssignment(BaseTenantModel):
    STATUS_CHOICES = (
        ('ACTIVE', 'Active'),
        ('PAUSED', 'Paused'),
        ('DEACTIVATED', 'Deactivated'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pm_plan = models.ForeignKey(PmPlan, on_delete=models.CASCADE, related_name='assignments')
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE)
    assigned_at = models.DateTimeField(auto_now_add=True)
    baseline_meter_reading = models.DecimalField(max_digits=19, decimal_places=2, null=True, blank=True)
    last_triggered_at = models.DateTimeField(null=True, blank=True)
    last_triggered_meter = models.DecimalField(max_digits=19, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='ACTIVE')
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='+', db_column='created_by', db_constraint=False)

    class Meta:
        db_table = 'pm_plan_assignments'
        unique_together = ('tenant', 'pm_plan', 'asset')

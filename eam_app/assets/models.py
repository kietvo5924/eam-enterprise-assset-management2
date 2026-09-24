from django.db import models
from core.models import BaseTenantModel
import uuid

class Location(BaseTenantModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    parent_id = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='+', db_column='created_by', db_constraint=False)
    updated_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='+', db_column='updated_by', db_constraint=False)
    
    class Meta:
        db_table = 'locations'

    def __str__(self):
        return self.name

class AssetCategory(BaseTenantModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='+', db_column='created_by', db_constraint=False)
    updated_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='+', db_column='updated_by', db_constraint=False)
    
    class Meta:
        db_table = 'asset_categories'
        unique_together = (('name', 'tenant'),)

    def __str__(self):
        return self.name

class HierarchyTemplate(BaseTenantModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    path = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='+', db_column='created_by', db_constraint=False)
    updated_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='+', db_column='updated_by', db_constraint=False)
    
    class Meta:
        db_table = 'hierarchy_templates'
        unique_together = (('name', 'tenant'),)

    def __str__(self):
        return self.name

class SparePart(BaseTenantModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    part_number = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    quantity_in_stock = models.DecimalField(max_digits=19, decimal_places=2, default=0.00)
    unit_cost = models.DecimalField(max_digits=19, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'spare_parts'

    def __str__(self):
        return self.name

class Asset(BaseTenantModel):
    STATUS_CHOICES = (
        ('OPERATIONAL', 'Operational'),
        ('OPERATING', 'Operating'),
        ('DOWN', 'Down'),
        ('MAINTENANCE', 'Maintenance'),
        ('RETIRED', 'Retired'),
        ('SCRAPPED', 'Scrapped'),
        ('DISPOSED', 'Disposed'),
        ('DECOMMISSIONED', 'Decommissioned'),
        ('DRAFT', 'Draft'),
        ('LOST', 'Lost'),
        ('SOLD', 'Sold'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.ForeignKey(AssetCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='assets')
    parent_id = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255)
    serial_number = models.CharField(max_length=100, null=True, blank=True)
    model = models.CharField(max_length=100, null=True, blank=True)
    manufacturer = models.CharField(max_length=100, null=True, blank=True)
    purchase_date = models.DateField(null=True, blank=True)
    value = models.DecimalField(max_digits=19, decimal_places=2, null=True, blank=True)
    purchase_cost = models.DecimalField(max_digits=19, decimal_places=2, null=True, blank=True)
    salvage_value = models.DecimalField(max_digits=19, decimal_places=2, default=0.00)
    useful_life_years = models.IntegerField(default=5)
    capitalized_cost = models.DecimalField(max_digits=19, decimal_places=2, default=0.00)
    capitalized_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='OPERATIONAL')
    location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True, related_name='assets')
    hierarchy_template = models.ForeignKey(HierarchyTemplate, on_delete=models.SET_NULL, null=True, blank=True, related_name='assets')
    qr_code = models.CharField(max_length=100)
    is_trackable = models.BooleanField(default=True, db_index=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='+', db_column='created_by', db_constraint=False)
    updated_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='+', db_column='updated_by', db_constraint=False)

    @property
    def effective_purchase_cost(self):
        if self.purchase_cost is not None:
            return self.purchase_cost
        return self.value or 0

    class Meta:
        db_table = 'assets'
        unique_together = (('qr_code', 'tenant'),)
        indexes = [
            models.Index(fields=['tenant', 'is_trackable', 'status']),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.tenant_id:
            try:
                from analytics.services import DashboardCacheService
                DashboardCacheService.invalidate_all(self.tenant_id)
            except Exception:
                pass

class MeterReading(BaseTenantModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='meter_readings')
    reading_value = models.DecimalField(max_digits=19, decimal_places=2)
    reading_date = models.DateTimeField()
    unit = models.CharField(max_length=50, null=True, blank=True)
    remarks = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'meter_readings'

    def __str__(self):
        return f"{self.asset.name} - {self.reading_value} {self.unit}"

class StockTransaction(BaseTenantModel):
    TRANSACTION_TYPE_CHOICES = (
        ('ISSUE', 'Issue / Xuất kho'),
        ('RECEIPT', 'Receipt / Nhập kho GRN'),
        ('RETURN', 'Return / Hoàn trả'),
        ('ADJUSTMENT', 'Adjustment / Điều chỉnh'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    spare_part = models.ForeignKey(SparePart, on_delete=models.CASCADE, related_name='stock_transactions')
    work_order = models.ForeignKey('workorders.WorkOrder', on_delete=models.SET_NULL, null=True, blank=True, related_name='stock_transactions')
    transaction_type = models.CharField(max_length=50, choices=TRANSACTION_TYPE_CHOICES, default='ISSUE')
    quantity = models.DecimalField(max_digits=19, decimal_places=2)
    unit_price = models.DecimalField(max_digits=19, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=19, decimal_places=2, default=0.00)
    cost_center_snapshot = models.CharField(max_length=255, null=True, blank=True)
    issue_date = models.DateTimeField()
    is_variance_adjustment = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'stock_transactions'
        indexes = [
            models.Index(fields=['tenant', 'transaction_type', 'issue_date']),
            models.Index(fields=['tenant', 'work_order']),
        ]

    def __str__(self):
        return f"{self.transaction_type} - {self.spare_part.name} - Qty: {self.quantity}"


from django.db import models
from core.models import BaseTenantModel
import uuid

class Location(BaseTenantModel):
    ZONE_TYPE_CHOICES = (
        ('FLOORPLAN', 'Mặt bằng tổng thể'),
        ('STANDARD', 'Tiêu chuẩn'),
        ('CONTROLLED', 'Kiểm soát đặc thù / Phòng sạch'),
        ('GENERAL', 'Chung / Toàn nhà máy'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    parent_id = models.CharField(max_length=255, null=True, blank=True)
    code = models.CharField(max_length=64, blank=True, default='')
    name = models.CharField(max_length=255)
    zone_type = models.CharField(max_length=32, choices=ZONE_TYPE_CHOICES, default='STANDARD')
    description = models.TextField(null=True, blank=True)
    floorplan_image = models.TextField(blank=True, default='', help_text='URL hoặc Data URI ảnh sơ đồ mặt bằng')
    center_x = models.FloatField(default=0.0, null=True, blank=True)
    center_y = models.FloatField(default=0.0, null=True, blank=True)
    floor_level = models.SmallIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='+', db_column='created_by', db_constraint=False)
    updated_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='+', db_column='updated_by', db_constraint=False)
    
    class Meta:
        db_table = 'locations'
        indexes = [
            models.Index(fields=['tenant', 'code']),
            models.Index(fields=['tenant', 'zone_type']),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})" if self.code else self.name

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
    coords_x = models.FloatField(default=0.0, null=True, blank=True)
    coords_y = models.FloatField(default=0.0, null=True, blank=True)
    floor_level = models.SmallIntegerField(default=1)
    zone_id = models.CharField(max_length=64, blank=True, default='')
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


class Tool(BaseTenantModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=64)
    name = models.CharField(max_length=255)
    available_quantity = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tools'
        unique_together = (('code', 'tenant'),)
        indexes = [
            models.Index(fields=['tenant', 'code']),
        ]

    def __str__(self):
        return f"{self.name} ({self.code}) - Avail: {self.available_quantity}"


class ToolInstance(BaseTenantModel):
    INSPECTION_CHOICES = (
        ('PASSED', 'Đạt chuẩn'),
        ('DUE_SOON', 'Sắp đến hạn'),
        ('EXPIRED', 'Quá hạn kiểm định'),
    )
    STATUS_CHOICES = (
        ('AVAILABLE', 'Khả dụng'),
        ('IN_USE', 'Đang sử dụng'),
        ('MAINTENANCE', 'Đang bảo dưỡng'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tool = models.ForeignKey(Tool, on_delete=models.CASCADE, related_name='instances')
    serial_number = models.CharField(max_length=100)
    asset_tag = models.CharField(max_length=100, blank=True, default='')
    calibration_date = models.DateField(null=True, blank=True, help_text='Ngày kiểm định/hiệu chuẩn gần nhất')
    calibration_due_date = models.DateField(null=True, blank=True, help_text='Ngày đến hạn hiệu chuẩn tiếp theo')
    inspection_status = models.CharField(max_length=20, choices=INSPECTION_CHOICES, default='PASSED')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='AVAILABLE')
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tool_instances'
        unique_together = (('tenant', 'tool', 'serial_number'),)
        indexes = [
            models.Index(fields=['tenant', 'inspection_status']),
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['tenant', 'calibration_due_date']),
        ]

    def __str__(self):
        return f"{self.tool.name} - SN: {self.serial_number} ({self.status})"

    @property
    def is_calibration_valid(self):
        from django.utils import timezone
        if self.inspection_status == 'EXPIRED':
            return False
        if self.calibration_due_date and self.calibration_due_date < timezone.now().date():
            return False
        return True


class ToolReservation(BaseTenantModel):
    STATUS_CHOICES = (
        ('RESERVED', 'Reserved / Đã giữ chỗ'),
        ('IN_USE', 'In Use / Đang xuất dùng'),
        ('RETURNED', 'Returned / Đã hoàn trả'),
        ('CANCELLED', 'Cancelled / Đã hủy'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tool = models.ForeignKey(Tool, on_delete=models.CASCADE, related_name='reservations')
    tool_instance = models.ForeignKey(ToolInstance, on_delete=models.SET_NULL, null=True, blank=True, related_name='reservations')
    work_order = models.ForeignKey('workorders.WorkOrder', on_delete=models.CASCADE, related_name='tool_reservations')
    reserved_quantity = models.IntegerField(default=1)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='RESERVED')
    reserved_at = models.DateTimeField(auto_now_add=True)
    returned_at = models.DateTimeField(null=True, blank=True)
    notes = models.CharField(max_length=255, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tool_reservations'
        indexes = [
            models.Index(fields=['tenant', 'work_order', 'status']),
            models.Index(fields=['tenant', 'tool', 'status']),
        ]

    def __str__(self):
        return f"Reservation of {self.tool.code} (x{self.reserved_quantity}) for WO-{str(self.work_order_id)[:8]} [{self.status}]"



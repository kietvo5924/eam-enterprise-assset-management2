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
        ('PREDICTIVE_PM', 'Predictive PM'),
    )

    MAINTENANCE_ACTION_CHOICES = (
        ('GENERAL', 'General Maintenance / Bảo dưỡng thông thường'),
        ('MICRO_MAINTENANCE', 'Micro Maintenance / Bôi trơn, siết ốc, hiệu chỉnh nhỏ'),
        ('CORE_REPLACEMENT', 'Core Replacement / Đại tu thay thế phụ tùng cốt lõi'),
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
    maintenance_action = models.CharField(max_length=32, choices=MAINTENANCE_ACTION_CHOICES, default='GENERAL', db_index=True)
    completion_processed_at = models.DateTimeField(null=True, blank=True, help_text='Thời điểm hoàn tất xử lý chuyển trạng thái và hậu kỳ Work Order')
    post_repair_vibration = models.FloatField(null=True, blank=True, help_text='Độ rung nghiệm thu sau sửa chữa (mm/s RMS)')
    post_repair_temperature = models.FloatField(null=True, blank=True, help_text='Nhiệt độ ổ trục nghiệm thu sau sửa chữa (°C)')
    post_repair_load_factor = models.FloatField(null=True, blank=True, default=1.0, help_text='Hệ số phụ tải lúc đo nghiệm thu')
    
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
    # Phase 11.3: Technician Routing Optimization (TSP) Fields
    incident_location = models.ForeignKey(
        'assets.Location',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='incident_work_orders',
        help_text='Vị trí thực tế nơi phát sinh sự cố (ưu tiên trên lộ trình TSP)'
    )
    tool_pickup_location = models.ForeignKey(
        'assets.Location',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tool_pickup_work_orders',
        help_text='Khu vực/Vị trí nơi cất giữ thiết bị, dụng cụ chuyên dụng cần lấy cho công việc'
    )
    maintenance_window_start = models.TimeField(
        null=True,
        blank=True,
        help_text='Khung giờ bắt đầu cho phép dừng máy để bảo trì'
    )
    maintenance_window_end = models.TimeField(
        null=True,
        blank=True,
        help_text='Khung giờ kết thúc cho phép dừng máy để bảo trì'
    )

    # Phase 11.8: Complex Maintenance Workflow & Facility Management (Decision Tree & HSM)
    SEVERITY_CHOICES = (
        ('NORMAL_MAINTENANCE', 'Normal Maintenance / Bảo dưỡng thông thường'),
        ('CRITICAL_OVERHAUL', 'Critical Overhaul / Đại tu thay thế cốt lõi'),
    )
    HOLD_REASON_CHOICES = (
        ('WAITING_PARTS', 'Chờ phụ tùng'),
        ('WAITING_VENDOR', 'Chờ nhà thầu / chuyên gia'),
        ('BUDGET_APPROVAL', 'Chờ duyệt ngân sách'),
    )
    severity_level = models.CharField(max_length=32, choices=SEVERITY_CHOICES, null=True, blank=True, db_index=True)
    marginal_boundary_warning = models.BooleanField(default=False, help_text='Cảnh báo chỉ số mấp mé ngưỡng quyết định (±5%)')
    decision_path_explanation = models.TextField(null=True, blank=True, help_text='Giải thích IF-THEN minh bạch từ Cây quyết định')
    override_reason = models.TextField(null=True, blank=True, help_text='Lý do người dùng can thiệp đè phán quyết AI')
    is_on_hold = models.BooleanField(default=False, help_text='Trạng thái tạm hoãn công việc do nguyên nhân khách quan')
    hold_reason = models.CharField(max_length=64, choices=HOLD_REASON_CHOICES, null=True, blank=True)
    hold_started_at = models.DateTimeField(null=True, blank=True)
    hold_accumulated_seconds = models.IntegerField(default=0, help_text='Tổng thời gian tạm hoãn (giây) được đóng băng khỏi SLA')

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
            net_sec = max(0.0, (self.completed_at - self.actual_start_time).total_seconds() - float(self.hold_accumulated_seconds or 0))
            return round(net_sec / 3600.0, 2)
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
        if not self.deadline:
            from django.utils import timezone
            from datetime import timedelta
            self.deadline = timezone.now() + timedelta(days=2)
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
    STAGE_CHOICES = (
        ('DIAGNOSIS', 'Giai đoạn 1: Khảo sát hiện trạng'),
        ('STAGING_PARTS', 'Giai đoạn 2: Vật tư sẵn sàng'),
        ('OVERHAUL_EXECUTION', 'Giai đoạn 3: Thực hiện đại tu'),
        ('TRIAL_ACCEPTANCE', 'Giai đoạn 4: Nghiệm thu chạy thử'),
    )
    stage = models.CharField(max_length=32, choices=STAGE_CHOICES, null=True, blank=True, db_index=True)
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


class WorkOrderCost(BaseTenantModel):
    """
    Task 11.6: Lưu trữ snapshot chi phí bất biến, phân tách Gross vs Net Cost
    và cờ vốn hóa CapEx khi Work Order nghiệm thu hoàn tất.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    work_order = models.OneToOneField(WorkOrder, on_delete=models.CASCADE, related_name='cost_breakdown')
    cost_center_snapshot = models.CharField(max_length=255, null=True, blank=True)
    material_cost = models.DecimalField(max_digits=19, decimal_places=2, default=0.00)
    labor_cost = models.DecimalField(max_digits=19, decimal_places=2, default=0.00)
    vendor_cost = models.DecimalField(max_digits=19, decimal_places=2, default=0.00)
    gross_cost = models.DecimalField(max_digits=19, decimal_places=2, default=0.00)
    warranty_covered_amount = models.DecimalField(max_digits=19, decimal_places=2, default=0.00)
    insurance_covered_amount = models.DecimalField(max_digits=19, decimal_places=2, default=0.00)
    net_cost = models.DecimalField(max_digits=19, decimal_places=2, default=0.00)
    is_capital_overhaul = models.BooleanField(default=False)
    is_cost_frozen = models.BooleanField(default=False)
    cost_frozen_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'work_order_costs'
        indexes = [
            models.Index(fields=['tenant', 'is_cost_frozen', 'created_at']),
            models.Index(fields=['tenant', 'cost_center_snapshot']),
        ]

    def __str__(self):
        return f"Cost of {self.work_order.title} (Gross: {self.gross_cost}, Net: {self.net_cost})"


class AttendanceLog(BaseTenantModel):
    """
    Task 11.7: Smart Field Biometric Attendance & Micro-Geofencing Log
    Lưu trữ lịch sử điểm danh hiện trường bất biến (Cổng Kép: Bắt đầu & Nghiệm thu).
    """
    VERIFICATION_METHOD_CHOICES = (
        ('ESP32_UNIVERSAL_BEACON', 'ESP32 Universal Beacon'),
        ('BLE_EXEMPT_BY_ASSET', 'BLE Exempt by Asset'),
        ('BYPASSED_BY_TENANT_POLICY', 'Bypassed by Tenant Policy'),
    )
    GATE_TYPE_CHOICES = (
        ('START_GATE', 'Start Work Gate (Cổng 1)'),
        ('COMPLETE_GATE', 'Complete Work Gate (Cổng 2)'),
    )
    COMPLIANCE_CHOICES = (
        ('PASSED', 'Passed'),
        ('FAILED', 'Failed'),
        ('BYPASSED_BY_TENANT_POLICY', 'Bypassed by Tenant Policy'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    work_order = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name='attendance_logs')
    technician = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='attendance_logs')
    verification_method = models.CharField(max_length=32, choices=VERIFICATION_METHOD_CHOICES)
    ble_beacon_id = models.CharField(max_length=64, null=True, blank=True)
    rssi_dbm = models.IntegerField(null=True, blank=True)
    distance_meters = models.FloatField(null=True, blank=True)
    similarity_score = models.FloatField(default=0.0)
    is_location_verified = models.BooleanField(default=False)
    is_face_verified = models.BooleanField(default=False)
    overall_compliance = models.CharField(max_length=32, choices=COMPLIANCE_CHOICES)
    gate_type = models.CharField(max_length=20, choices=GATE_TYPE_CHOICES, default='START_GATE')
    snapshot_minio_path = models.CharField(max_length=512, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'attendance_logs'
        indexes = [
            models.Index(fields=['tenant', 'work_order', 'technician', 'created_at']),
        ]

    def __str__(self):
        return f"Attendance {self.gate_type} for WO {self.work_order_id} by {self.technician.username} [{self.overall_compliance}]"


class HsmStageTransition(BaseTenantModel):
    """
    Task 11.8: Lịch sử đánh giá AI, lùi bước kỹ thuật (Rollback) & tạm hoãn (Hold)
    """
    ACTION_CHOICES = (
        ('AI_EVALUATE', 'AI Evaluate'),
        ('OVERRIDE', 'Override'),
        ('ROLLBACK', 'Rollback'),
        ('HOLD', 'Hold'),
        ('RESUME', 'Resume'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    work_order = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name='hsm_transitions')
    action_type = models.CharField(max_length=32, choices=ACTION_CHOICES)
    severity_assigned = models.CharField(max_length=32, null=True, blank=True)
    reason = models.TextField(null=True, blank=True)
    performed_by = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='+')
    vibration_reading = models.FloatField(null=True, blank=True)
    temperature_reading = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    from_stage = models.CharField(max_length=32, null=True, blank=True, help_text='Giai đoạn trước khi chuyển đổi')
    to_stage = models.CharField(max_length=32, null=True, blank=True, help_text='Giai đoạn sau khi chuyển đổi')

    @property
    def action(self):
        return self.action_type

    @property
    def recheck_vibration(self):
        return self.vibration_reading

    @property
    def recheck_temperature(self):
        return self.temperature_reading

    class Meta:
        db_table = 'hsm_stage_transitions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'work_order', 'created_at']),
        ]

    def __str__(self):
        return f"HSM {self.action_type} for WO-{str(self.work_order_id)[:8]} by {self.performed_by_id} [{self.created_at}]"



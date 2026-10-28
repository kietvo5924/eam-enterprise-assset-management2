import uuid
from decimal import Decimal
from django.db import models
from core.models import BaseTenantModel
from users.models import User

class ExportJob(BaseTenantModel):
    REPORT_TYPE_CHOICES = (
        ('ASSET_VALUATION', 'Asset Valuation & Depreciation'),
        ('MAINTENANCE_PERFORMANCE', 'Maintenance Performance & SLA'),
        ('SPARE_PARTS', 'Spare Parts Consumption & Cost'),
        ('COST_SUMMARY', 'Cost Summary (Accrual & Cost Center)'),
    )

    FILE_FORMAT_CHOICES = (
        ('XLSX', 'Excel Spreadsheet (.xlsx)'),
        ('PDF', 'PDF Document (.pdf)'),
        ('CSV', 'Comma Separated Values (.csv)'),
    )

    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('EXPIRED', 'Expired'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='export_jobs')
    report_type = models.CharField(max_length=64, choices=REPORT_TYPE_CHOICES)
    file_format = models.CharField(max_length=16, choices=FILE_FORMAT_CHOICES, default='XLSX')
    filter_params = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='PENDING', db_index=True)
    progress_percent = models.IntegerField(default=0)
    file_name = models.CharField(max_length=255, blank=True)
    minio_object_key = models.CharField(max_length=500, null=True, blank=True)
    file_size_bytes = models.BigIntegerField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'export_jobs'
        indexes = [
            models.Index(fields=['tenant', 'status', '-created_at']),
            models.Index(fields=['tenant', 'user', 'status']),
        ]

    def __str__(self):
        return f"{self.report_type} - {self.file_format} - {self.status} ({self.id})"


class BudgetForecast(BaseTenantModel):
    """
    Task 11.6: Lưu trữ kết quả dự báo ngân sách bảo trì lai ghép (Deterministic PM + QRF CM).
    """
    FORECAST_METHOD_CHOICES = (
        ('HYBRID_QRF', 'Hybrid Quantile Regression Forest'),
        ('DETERMINISTIC_FALLBACK', 'Deterministic Heuristic Fallback'),
    )
    BUDGET_STATUS_CHOICES = (
        ('HEALTHY', 'Healthy'),
        ('WARNING', 'Warning'),
        ('CRITICAL_OVERRUN', 'Critical Overrun'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cost_center_snapshot = models.CharField(max_length=255, null=True, blank=True, help_text='NULL là Macro toàn công ty, chuỗi là phân xưởng cụ thể')
    forecast_period = models.CharField(max_length=16, db_index=True)
    forecast_method = models.CharField(max_length=32, choices=FORECAST_METHOD_CHOICES, default='HYBRID_QRF')
    approved_budget = models.DecimalField(max_digits=19, decimal_places=2, default=0.00)
    planned_pm_budget = models.DecimalField(max_digits=19, decimal_places=2, default=0.00)
    predicted_cm_median = models.DecimalField(max_digits=19, decimal_places=2, default=0.00)
    predicted_cm_lower_p10 = models.DecimalField(max_digits=19, decimal_places=2, default=0.00)
    predicted_cm_upper_p90 = models.DecimalField(max_digits=19, decimal_places=2, default=0.00)
    contingency_buffer = models.DecimalField(max_digits=19, decimal_places=2, default=0.00)
    total_forecast_median = models.DecimalField(max_digits=19, decimal_places=2, default=0.00)
    total_forecast_p90 = models.DecimalField(max_digits=19, decimal_places=2, default=0.00)
    budget_usage_ratio = models.FloatField(default=0.0)
    budget_status = models.CharField(max_length=16, choices=BUDGET_STATUS_CHOICES, default='HEALTHY', db_index=True)
    inflation_rate_applied = models.FloatField(default=0.045)
    backlog_work_orders_count = models.IntegerField(default=0)
    deferred_maintenance_hours = models.FloatField(default=0.0)
    rul_critical_liability = models.DecimalField(max_digits=19, decimal_places=2, default=0.00)
    lemon_assets_detected = models.JSONField(default=list, blank=True)
    top_cost_drivers = models.JSONField(default=list, blank=True)
    is_ai_fallback = models.BooleanField(default=False)
    is_manually_approved = models.BooleanField(default=False, help_text='True nếu hạn mức ngân sách được người dùng nhập tay phê duyệt')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'budget_forecasts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'forecast_period']),
            models.Index(fields=['tenant', 'cost_center_snapshot', '-created_at']),
        ]

    def __str__(self):
        return f"BudgetForecast {self.forecast_period} ({self.total_forecast_median} VND - {self.budget_status})"


class TenantFinancialSetting(BaseTenantModel):
    """
    Task 11.6: Cấu hình chính sách tài chính, lương thợ và tỷ lệ dự phòng cấp Tenant.
    Loại trừ việc gán cứng (hardcoded) cho toàn bộ hệ thống đa doanh nghiệp.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    default_labor_hourly_rate = models.DecimalField(
        max_digits=19, decimal_places=2, default=Decimal('150000.00'),
        help_text="Đơn giá giờ công tiêu chuẩn của kỹ thuật viên (VNĐ/giờ)"
    )
    default_inflation_rate = models.FloatField(
        default=0.045,
        help_text="Tỷ lệ trượt giá lạm phát vật tư hàng năm (0.045 = 4.5%)"
    )
    default_contingency_rate = models.FloatField(
        default=0.05,
        help_text="Tỷ lệ quỹ dự phòng rủi ro khẩn cấp (0.05 = 5.0%)"
    )
    critical_spare_part_ratio = models.FloatField(
        default=0.05,
        help_text="Tỷ lệ ước tính chi phí phụ tùng chính khi chưa có BOM (mặc định 5% nguyên giá máy)"
    )
    currency = models.CharField(max_length=10, default='VND')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tenant_financial_settings'

    def __str__(self):
        return f"FinancialSetting [{self.tenant.name}] Rate: {self.default_labor_hourly_rate} VND/h"


class PeriodApprovedBudget(BaseTenantModel):
    """
    Task 11.6: Hạn mức ngân sách thực tế do Ban Giám đốc / Kế toán trưởng phê duyệt cho từng kỳ và phân xưởng.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    period = models.CharField(max_length=16, db_index=True, help_text="Kỳ ngân sách, e.g. 2026-Q4, 2026-11")
    cost_center = models.CharField(max_length=255, null=True, blank=True, help_text="NULL là toàn nhà máy, hoặc tên phân xưởng")
    approved_budget = models.DecimalField(max_digits=19, decimal_places=2)
    is_manually_approved = models.BooleanField(default=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_budgets')
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'period_approved_budgets'
        indexes = [
            models.Index(fields=['tenant', 'period']),
            models.Index(fields=['tenant', 'period', 'cost_center']),
        ]

    def __str__(self):
        return f"ApprovedBudget {self.period} [{self.cost_center or 'Macro'}]: {self.approved_budget} VND"


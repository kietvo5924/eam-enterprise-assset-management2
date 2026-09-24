import uuid
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

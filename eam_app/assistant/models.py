import uuid
from django.db import models

try:
    from pgvector.django import VectorField, HnswIndex
except ImportError:
    class VectorField(models.Field):
        def __init__(self, *args, **kwargs):
            kwargs.pop('dimensions', None)
            super().__init__(*args, **kwargs)

        def db_type(self, connection):
            return 'vector'

    class HnswIndex(models.Index):
        def __init__(self, *args, **kwargs):
            kwargs.pop('m', None)
            kwargs.pop('ef_construction', None)
            kwargs.pop('opclasses', None)
            super().__init__(*args, **kwargs)

from core.tenant_context import get_current_tenant


class HybridTenantManager(models.Manager):
    """
    Manager that allows access to both tenant-specific records and
    global records (tenant_id IS NULL and is_system_guide = TRUE).
    """
    def get_queryset(self):
        qs = super().get_queryset()
        tenant_id = get_current_tenant()
        if tenant_id:
            has_system_guide = any(f.name == 'is_system_guide' for f in self.model._meta.fields)
            if has_system_guide:
                return qs.filter(
                    models.Q(tenant_id=tenant_id) | 
                    models.Q(tenant_id__isnull=True, is_system_guide=True)
                )
            return qs.filter(tenant_id=tenant_id)
        return qs


class TechnicalDocument(models.Model):
    """
    Technical documents (OEM manuals and Global System Software Guides).
    """
    CATEGORY_CHOICES = (
        ('OEM_MANUAL', 'OEM Manual / Sách hướng dẫn của hãng'),
        ('SYSTEM_SOFTWARE_GUIDE', 'System Software Guide / Cẩm nang sử dụng phần mềm'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'core.Tenant',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        db_column='tenant_id',
        related_name='technical_documents'
    )
    is_system_guide = models.BooleanField(
        default=False,
        help_text='TRUE nếu là tài liệu hướng dẫn phần mềm dùng chung toàn hệ thống'
    )
    category = models.CharField(max_length=32, choices=CATEGORY_CHOICES, default='OEM_MANUAL')
    title = models.CharField(max_length=255)
    file_path = models.CharField(max_length=500)
    applicable_model = models.CharField(max_length=100, null=True, blank=True)
    applicable_year_start = models.IntegerField(default=1900)
    applicable_year_end = models.IntegerField(default=2100)
    serial_number_prefix = models.CharField(max_length=50, null=True, blank=True)
    file_size_bytes = models.BigIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = HybridTenantManager()
    all_objects = models.Manager()

    class Meta:
        db_table = 'technical_documents'
        indexes = [
            models.Index(fields=['tenant', 'applicable_model', 'is_active'], name='idx_doc_tenant_model'),
            models.Index(fields=['is_system_guide', 'is_active'], name='idx_doc_system_guide'),
        ]

    def __str__(self):
        return f"{self.title} ({self.applicable_model or 'GLOBAL'})"


class DocumentChunk(models.Model):
    """
    Chunks of documents, with 384-dimensional dense semantic embedding and image anchors.
    Supports Parent-Child retrieval where content is Child Chunk and parent_content is full section.
    """
    SOURCE_TYPE_CHOICES = (
        ('OEM_MANUAL', 'OEM Manual'),
        ('TACIT_WORK_ORDER', 'Tacit Work Order'),
        ('CURATED_QA', 'Curated QA'),
        ('SYSTEM_GUIDE', 'System Software Guide'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'core.Tenant',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        db_column='tenant_id',
        related_name='document_chunks'
    )
    is_system_guide = models.BooleanField(default=False)
    document = models.ForeignKey(
        TechnicalDocument,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='chunks',
        db_column='document_id'
    )
    source_type = models.CharField(max_length=32, choices=SOURCE_TYPE_CHOICES, default='OEM_MANUAL')
    work_order = models.ForeignKey(
        'workorders.WorkOrder',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='document_chunks',
        db_column='work_order_id'
    )
    is_verified_tacit = models.BooleanField(
        default=False,
        help_text='Đánh dấu tri thức từ Work Order đã hoàn thành đạt chuẩn kiểm định'
    )
    provenance_wo_code = models.CharField(max_length=32, null=True, blank=True)
    content = models.TextField(help_text='Child Chunk (300 ký tự)')
    parent_content = models.TextField(help_text='Parent Section hoàn chỉnh')
    embedding = VectorField(dimensions=384, help_text='Vector 384 chiều từ paraphrase-multilingual-MiniLM-L12-v2')
    page_number = models.IntegerField(null=True, blank=True)
    section_title = models.CharField(max_length=255, null=True, blank=True)
    image_anchors = models.JSONField(null=True, blank=True, default=list)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = HybridTenantManager()
    all_objects = models.Manager()

    class Meta:
        db_table = 'document_chunks'
        indexes = [
            HnswIndex(
                name='idx_chunk_embedding_hnsw',
                fields=['embedding'],
                m=16,
                ef_construction=64,
                opclasses=['vector_cosine_ops']
            ),
            models.Index(fields=['tenant', 'source_type', 'is_active'], name='idx_chunk_tenant_source'),
            models.Index(fields=['is_system_guide', 'is_active'], name='idx_chunk_system_guide'),
        ]

    def __str__(self):
        return f"Chunk {str(self.id)[:8]} ({self.source_type})"


class CuratedQAKnowledge(models.Model):
    """
    Curated Gold QA Knowledge approved by Chief Engineer.
    """
    CATEGORY_CHOICES = (
        ('EQUIPMENT_MAINTENANCE', 'Equipment Maintenance / Bảo trì thiết bị'),
        ('SYSTEM_FEATURE_GUIDE', 'System Feature Guide / Hướng dẫn tính năng phần mềm'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'core.Tenant',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        db_column='tenant_id',
        related_name='curated_qa_knowledge'
    )
    is_system_guide = models.BooleanField(default=False)
    category = models.CharField(max_length=32, choices=CATEGORY_CHOICES, default='EQUIPMENT_MAINTENANCE')
    question_pattern = models.TextField()
    gold_answer = models.TextField()
    applicable_model = models.CharField(max_length=100, null=True, blank=True)
    applicable_year_start = models.IntegerField(default=1900)
    applicable_year_end = models.IntegerField(default=2100)
    approved_by = models.ForeignKey(
        'users.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='approved_curated_qa',
        db_column='approved_by'
    )
    upvote_count = models.IntegerField(default=0)
    downvote_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = HybridTenantManager()
    all_objects = models.Manager()

    class Meta:
        db_table = 'curated_qa_knowledge'
        indexes = [
            models.Index(fields=['tenant', 'category', 'is_system_guide'], name='idx_curated_tenant_cat'),
        ]

    def __str__(self):
        return f"Curated QA: {self.question_pattern[:50]}"


class CurationQueueItem(models.Model):
    """
    Chief Engineer Curation Queue for downvoted answers (Rule 10, TC-RAG-10).
    """
    STATUS_CHOICES = (
        ('PENDING', 'Pending Review / Chờ Kỹ sư trưởng phê duyệt'),
        ('APPROVED', 'Approved / Đã duyệt thành Tri thức Vàng'),
        ('REJECTED', 'Rejected / Bỏ qua'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'core.Tenant',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        db_column='tenant_id',
        related_name='curation_queue_items'
    )
    user = models.ForeignKey(
        'users.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='assistant_feedback_queue'
    )
    user_query = models.TextField()
    generated_answer = models.TextField()
    technician_feedback = models.TextField(null=True, blank=True)
    vote_type = models.CharField(max_length=10, default='DOWNVOTE')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    reviewed_by = models.ForeignKey(
        'users.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='reviewed_curation_items'
    )
    curated_answer = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    objects = HybridTenantManager()
    all_objects = models.Manager()

    class Meta:
        db_table = 'assistant_curation_queue'
        ordering = ['-created_at']

    def __str__(self):
        return f"Queue Item ({self.status}): {self.user_query[:50]}"

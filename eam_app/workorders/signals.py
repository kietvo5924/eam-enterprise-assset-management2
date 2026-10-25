from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from workorders.models import WorkOrder
from assets.models import MeterReading


@receiver(post_save, sender=WorkOrder)
def on_work_order_completed(sender, instance, **kwargs):
    """
    Post-Repair Window Reset Guardrail.
    Chỉ khi WorkOrder hoàn thành là loại CORE_REPLACEMENT (đại tu / thay thế cụm cốt lõi)
    mới kích hoạt đóng băng các lần đo cũ để tái lập cửa sổ trượt.
    Tuyệt đối KHÔNG đóng băng số đo nghiệm thu (POST_REPAIR_ACCEPTANCE) và KHÔNG đóng băng
    khi bảo trì nhỏ (MICRO_MAINTENANCE / GENERAL).
    """
    if instance.status == 'COMPLETED' and instance.asset_id:
        completed_time = instance.completed_at or timezone.now()

        # CHỈ đóng băng dữ liệu cũ khi người dùng xác nhận là CORE_REPLACEMENT
        if instance.maintenance_action == 'CORE_REPLACEMENT':
            MeterReading.objects.filter(
                asset_id=instance.asset_id,
                reading_date__lte=completed_time
            ).exclude(
                measurement_phase='POST_REPAIR_ACCEPTANCE'
            ).update(is_pre_repair=True)

        # Đóng vòng đời AssetAnomalyAlert sang RESOLVED khi phiếu sửa chữa hoàn thành
        from assets.models import AssetAnomalyAlert
        from django.db.models import Q
        AssetAnomalyAlert.objects.filter(
            asset_id=instance.asset_id,
            status__in=['OPEN', 'ACKNOWLEDGED'],
            created_at__lte=completed_time
        ).filter(
            Q(draft_work_order=instance) | Q(draft_work_order__isnull=True)
        ).update(status='RESOLVED')

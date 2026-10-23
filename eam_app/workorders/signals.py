from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from workorders.models import WorkOrder
from assets.models import MeterReading


@receiver(post_save, sender=WorkOrder)
def on_work_order_completed(sender, instance, **kwargs):
    """
    Quy Tắc 2 & Mục 11.2: Post-Repair Window Reset Guardrail.
    Khi một Work Order loại CORRECTIVE hoặc PREVENTIVE trên thiết bị chuyển sang trạng thái COMPLETED,
    hệ thống tự động kích hoạt Cắt tỉa & Tái lập cửa sổ trượt (Sliding Window Reset / Pruning).
    Toàn bộ các lần đo trước thời điểm hoàn thành sửa chữa bị đánh dấu đóng băng (is_pre_repair = True).
    """
    if instance.status == 'COMPLETED' and instance.type in ('CORRECTIVE', 'PREVENTIVE') and instance.asset_id:
        completed_time = instance.completed_at or timezone.now()
        MeterReading.objects.filter(
            asset_id=instance.asset_id,
            reading_date__lte=completed_time
        ).update(is_pre_repair=True)

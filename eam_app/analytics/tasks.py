import logging
from datetime import timedelta
from celery import shared_task
from django.utils import timezone

from analytics.models import ExportJob
from analytics.export_engine import ExportEngineService, MinIOStorageService

logger = logging.getLogger(__name__)


@shared_task(name='analytics.tasks.generate_export_report', queue='reports_export')
def generate_export_report(job_id: str):
    """
    Celery worker task to asynchronously generate reports, stream to disk,
    upload to MinIO, and notify users upon completion.
    """
    try:
        job = ExportJob.all_objects.select_related('tenant', 'user').get(id=job_id)
    except ExportJob.DoesNotExist:
        logger.error(f"ExportJob {job_id} does not exist.")
        return

    job.status = 'PROCESSING'
    job.progress_percent = 10
    job.save(update_fields=['status', 'progress_percent', 'updated_at'])

    def update_progress(percent: int):
        job.progress_percent = percent
        job.save(update_fields=['progress_percent', 'updated_at'])

    try:
        object_key, file_size, presigned_url = ExportEngineService.generate_and_upload(
            job=job,
            progress_callback=update_progress
        )

        now = timezone.now()
        job.status = 'COMPLETED'
        job.progress_percent = 100
        job.minio_object_key = object_key
        job.file_size_bytes = file_size
        job.completed_at = now
        job.expires_at = now + timedelta(days=7)
        job.save(update_fields=[
            'status',
            'progress_percent',
            'minio_object_key',
            'file_size_bytes',
            'file_name',
            'completed_at',
            'expires_at',
            'updated_at'
        ])

        # Send Real-Time Notification (Phase 10.1 integration)
        try:
            from notifications.models import Notification
            Notification.all_objects.create(
                tenant=job.tenant,
                recipient=job.user,
                title="Báo cáo đã hoàn tất",
                message=f"Báo cáo '{job.get_report_type_display()}' đã được xuất thành công.",
                link=f"/portal/reports/?jobId={job.id}"
            )
        except Exception as notify_err:
            logger.warning(f"Could not send completion notification: {notify_err}")

        return {"status": "SUCCESS", "job_id": str(job.id), "object_key": object_key}

    except Exception as e:
        logger.exception(f"Export job {job_id} failed: {e}")
        job.status = 'FAILED'
        job.error_message = str(e)
        job.save(update_fields=['status', 'error_message', 'updated_at'])

        try:
            from notifications.models import Notification
            Notification.all_objects.create(
                tenant=job.tenant,
                recipient=job.user,
                title="Xuất báo cáo thất bại",
                message=f"Tác vụ xuất '{job.get_report_type_display()}' gặp lỗi: {str(e)[:100]}",
                link="/portal/reports/"
            )
        except Exception:
            pass

        return {"status": "FAILED", "job_id": str(job.id), "error": str(e)}


@shared_task(name='analytics.tasks.cleanup_zombie_export_jobs', queue='periodic')
def cleanup_zombie_export_jobs():
    """
    Rule 7 & 10.3: Zombie Job Recovery.
    Celery Beat task scanning for jobs stuck in 'PROCESSING' without progress
    updates for > 15 minutes, marking them as FAILED.
    """
    cutoff = timezone.now() - timedelta(minutes=15)
    zombie_jobs = ExportJob.all_objects.filter(status__in=['PENDING', 'PROCESSING'], updated_at__lt=cutoff)
    count = zombie_jobs.count()
    if count > 0:
        zombie_jobs.update(
            status='FAILED',
            error_message="Tác vụ bị gián đoạn do hệ thống bảo trì. Vui lòng nhấn xuất lại."
        )
        logger.info(f"Cleaned up {count} zombie export jobs.")
    return {"cleaned_count": count}


@shared_task(name='analytics.tasks.purge_expired_export_files', queue='periodic')
def purge_expired_export_files():
    """
    Rule 8: Storage Retention & Auto-Purge.
    Celery Beat task running daily to purge MinIO files older than 7 days
    and update ExportJob status to 'EXPIRED'.
    """
    now = timezone.now()
    expired_jobs = ExportJob.all_objects.filter(
        status='COMPLETED',
        expires_at__isnull=False,
        expires_at__lt=now
    )

    purged_count = 0
    for job in expired_jobs:
        if job.minio_object_key:
            MinIOStorageService.delete_file(job.minio_object_key)
        job.status = 'EXPIRED'
        job.save(update_fields=['status', 'updated_at'])
        purged_count += 1

    logger.info(f"Purged {purged_count} expired export jobs from MinIO.")
    return {"purged_count": purged_count}

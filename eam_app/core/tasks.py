import os
import uuid
import logging
from django.conf import settings
from django.core.files.storage import default_storage
from celery import shared_task
from minio import Minio

logger = logging.getLogger(__name__)


@shared_task(name='core.tasks.sync_and_purge_local_fallback_files', queue='periodic')
def sync_and_purge_local_fallback_files():
    """
    Tác vụ Celery định kỳ (Auto Sync & Local Purge):
    1. Kiểm tra kết nối MinIO. Nếu MinIO không khả dụng (mất mạng/chưa chạy) -> bỏ qua an toàn.
    2. Nếu MinIO khả dụng:
       - Tìm các Tenant có logo_url đang lưu tạm cục bộ (/media/ hoặc relative path).
         Upload lên MinIO, cập nhật lại Tenant.logo_url sang MinIO public URL, xóa file cục bộ.
       - Tìm các WorkOrderAttachment có file_url đang lưu tạm cục bộ (/media/).
         Upload lên MinIO, cập nhật lại WorkOrderAttachment.file_url sang MinIO URL, xóa file cục bộ.
    3. Dọn dẹp các thư mục rỗng và file mồ côi trong media/tenant-assets/logos/.
    """
    try:
        client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=getattr(settings, 'MINIO_SECURE', False)
        )
        bucket_name = getattr(settings, 'MINIO_BUCKET_NAME', 'tenant-assets')
        if not client.bucket_exists(bucket_name):
            client.make_bucket(bucket_name)
            import json
            policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"AWS": "*"},
                        "Action": ["s3:GetObject"],
                        "Resource": [f"arn:aws:s3:::{bucket_name}/*"]
                    }
                ]
            }
            client.set_bucket_policy(bucket_name, json.dumps(policy))
    except Exception as e:
        logger.warning(f"MinIO currently unavailable for sync task: {e}")
        return {"status": "skipped", "reason": f"MinIO unreachable: {e}"}

    synced_logos = 0
    synced_attachments = 0

    # 1. Sync Tenant logos from local storage to MinIO
    from core.models import Tenant
    from mimetypes import guess_type
    import io

    tenants = Tenant.objects.filter(logo_url__isnull=False)
    for tenant in tenants:
        url = tenant.logo_url or ''
        if ('/tenant-assets/logos/' in url or '/media/' in url) and not url.startswith(settings.MINIO_PUBLIC_URL):
            if '/media/' in url:
                rel_path = url.split('/media/', 1)[1]
            elif url.startswith('/'):
                rel_path = url.lstrip('/')
            else:
                rel_path = url

            fname = os.path.basename(url)
            object_name = f"logos/{fname}"
            
            already_in_minio = False
            try:
                client.stat_object(bucket_name, object_name)
                already_in_minio = True
            except Exception:
                already_in_minio = False

            if default_storage.exists(rel_path):
                try:
                    with default_storage.open(rel_path, 'rb') as f:
                        file_bytes = f.read()
                        content_type, _ = guess_type(rel_path)
                        client.put_object(
                            bucket_name,
                            object_name,
                            io.BytesIO(file_bytes),
                            length=len(file_bytes),
                            content_type=content_type or 'image/png'
                        )
                    default_storage.delete(rel_path)
                    minio_url = f"{settings.MINIO_PUBLIC_URL}/{bucket_name}/{object_name}"
                    tenant.logo_url = minio_url
                    tenant.save(update_fields=['logo_url'])
                    synced_logos += 1
                    logger.info(f"Synced & purged tenant logo from {rel_path} to {minio_url}")
                except Exception as sync_err:
                    logger.error(f"Failed to sync tenant logo {rel_path} to MinIO: {sync_err}")
            elif already_in_minio:
                minio_url = f"{settings.MINIO_PUBLIC_URL}/{bucket_name}/{object_name}"
                tenant.logo_url = minio_url
                tenant.save(update_fields=['logo_url'])
                synced_logos += 1
                logger.info(f"Updated tenant logo URL to existing MinIO object: {minio_url}")

    # 2. Sync WorkOrderAttachments from local storage to MinIO
    try:
        from workorders.models import WorkOrderAttachment
        attachments = WorkOrderAttachment.objects.filter(file_url__contains='/media/')
        for att in attachments:
            url = att.file_url or ''
            rel_path = url.split('/media/', 1)[1] if '/media/' in url else url.lstrip('/')
            fname = os.path.basename(att.file_name or url)
            object_name = f"tenant-{att.tenant_id}/work-orders/{att.work_order_id}/{fname}"

            already_in_minio = False
            try:
                client.stat_object(bucket_name, object_name)
                already_in_minio = True
            except Exception:
                already_in_minio = False

            if default_storage.exists(rel_path):
                try:
                    with default_storage.open(rel_path, 'rb') as f:
                        file_bytes = f.read()
                        client.put_object(
                            bucket_name,
                            object_name,
                            io.BytesIO(file_bytes),
                            length=len(file_bytes),
                            content_type=att.file_type or 'application/octet-stream'
                        )
                    default_storage.delete(rel_path)
                    minio_url = f"/{bucket_name}/{object_name}"
                    att.file_url = minio_url
                    att.save(update_fields=['file_url'])
                    synced_attachments += 1
                    logger.info(f"Synced & purged WO attachment from {rel_path} to {minio_url}")
                except Exception as att_err:
                    logger.error(f"Failed to sync WO attachment {rel_path} to MinIO: {att_err}")
            elif already_in_minio:
                att.file_url = f"/{bucket_name}/{object_name}"
                att.save(update_fields=['file_url'])
                synced_attachments += 1

    except Exception as e:
        logger.warning(f"Error querying WorkOrderAttachments for sync: {e}")

    # 3. Purge or sync any leftover orphan files in default_storage tenant-assets/logos/
    try:
        dirs, files = default_storage.listdir("tenant-assets/logos")
        for fname in files:
            orphan_rel = f"tenant-assets/logos/{fname}"
            object_name = f"logos/{fname}"
            try:
                with default_storage.open(orphan_rel, 'rb') as f:
                    file_bytes = f.read()
                    content_type, _ = guess_type(orphan_rel)
                    client.put_object(
                        bucket_name,
                        object_name,
                        io.BytesIO(file_bytes),
                        length=len(file_bytes),
                        content_type=content_type or 'image/png'
                    )
                default_storage.delete(orphan_rel)
                # Ensure any Tenant matching this fname gets updated
                for mt in Tenant.objects.filter(logo_url__contains=fname):
                    mt.logo_url = f"{settings.MINIO_PUBLIC_URL}/{bucket_name}/{object_name}"
                    mt.save(update_fields=['logo_url'])
                logger.info(f"Synced & purged orphan logo {orphan_rel} to MinIO")
            except Exception as orphan_err:
                logger.error(f"Failed to sync orphan logo {orphan_rel}: {orphan_err}")
    except Exception:
        pass

    logger.info(f"Auto-sync completed: {synced_logos} logos, {synced_attachments} attachments migrated to MinIO.")
    return {
        "status": "success",
        "synced_logos": synced_logos,
        "synced_attachments": synced_attachments
    }

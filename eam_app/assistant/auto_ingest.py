"""
Auto Ingestion Service & Background Periodic Worker for Tacit Work Order Knowledge.
Continuously and automatically indexes COMPLETED Work Orders meeting quality criteria:
- Status == 'COMPLETED'
- Resolution notes length >= 30 characters
- Non-trivial notes
- Preserves provenance (wo code, asset, tenant)
"""

import sys
import time
import logging
import threading
from typing import Optional
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

logger = logging.getLogger(__name__)

_loop_started = False
_loop_lock = threading.Lock()


def sync_work_order_tacit_chunk(wo):
    """
    Synchronizes or purges tacit knowledge chunk for an individual WorkOrder instance.
    Called directly by post_save/post_delete signals for real-time responsiveness.
    """
    from assistant.models import DocumentChunk
    from algorithms.rag_chatbot.tacit_ingestion import is_valid_tacit_work_order, extract_diagram_anchors
    from algorithms.rag_chatbot.vector_engine import embed_text

    try:
        if is_valid_tacit_work_order(wo):
            expected_parent = f"Work Order {wo.code} ({wo.title}):\n{wo.resolution_notes}"
            expected_content = f"{wo.title}: {wo.resolution_notes[:200]}"
            chunk = DocumentChunk.objects.filter(work_order=wo).first()
            if chunk:
                if chunk.parent_content != expected_parent or chunk.content != expected_content:
                    vec = embed_text(f"{wo.title} {wo.resolution_notes}")
                    anchors = extract_diagram_anchors(wo.resolution_notes)
                    chunk.content = expected_content
                    chunk.parent_content = expected_parent
                    chunk.embedding = vec
                    chunk.image_anchors = anchors
                    chunk.is_active = True
                    chunk.save()
                    logger.info(f"[AutoIngest] Realtime updated tacit chunk for Work Order {wo.code}")
            else:
                vec = embed_text(f"{wo.title} {wo.resolution_notes}")
                anchors = extract_diagram_anchors(wo.resolution_notes)
                DocumentChunk.objects.create(
                    tenant_id=wo.tenant_id,
                    is_system_guide=False,
                    source_type='TACIT_WORK_ORDER',
                    work_order=wo,
                    is_verified_tacit=True,
                    provenance_wo_code=wo.code,
                    content=expected_content,
                    parent_content=expected_parent,
                    embedding=vec,
                    image_anchors=anchors,
                    is_active=True
                )
                logger.info(f"[AutoIngest] Realtime created tacit chunk for Work Order {wo.code}")
        else:
            DocumentChunk.objects.filter(work_order=wo).delete()
    except Exception as e:
        logger.error(f"[AutoIngest] Error syncing tacit chunk for WO {getattr(wo, 'code', '')}: {e}")


@receiver(post_save, sender='workorders.WorkOrder')
def work_order_post_save_sync(sender, instance, **kwargs):
    sync_work_order_tacit_chunk(instance)


@receiver(post_delete, sender='workorders.WorkOrder')
def work_order_post_delete_sync(sender, instance, **kwargs):
    from assistant.models import DocumentChunk
    try:
        DocumentChunk.objects.filter(work_order_id=instance.id).delete()
    except Exception:
        pass


def ingest_completed_workorders(tenant_id: Optional[str] = None) -> int:
    """
    Scans completed Work Orders and synchronizes tacit maintenance knowledge into PGVector.
    Can be called directly, periodically by background thread, or via signal.
    """
    from workorders.models import WorkOrder
    from assistant.models import DocumentChunk
    from algorithms.rag_chatbot.tacit_ingestion import is_valid_tacit_work_order, extract_diagram_anchors
    from algorithms.rag_chatbot.vector_engine import embed_text

    try:
        # 1. Cleanup chunks for Work Orders that are no longer COMPLETED
        invalid_qs = WorkOrder.all_objects.exclude(status='COMPLETED')
        if tenant_id:
            invalid_qs = invalid_qs.filter(tenant_id=tenant_id)
        DocumentChunk.objects.filter(work_order__in=invalid_qs).delete()

        # 2. Ingest or update COMPLETED Work Orders
        qs = WorkOrder.all_objects.filter(status='COMPLETED')
        if tenant_id:
            qs = qs.filter(tenant_id=tenant_id)

        ingested_count = 0
        for wo in qs:
            if is_valid_tacit_work_order(wo):
                expected_parent = f"Work Order {wo.code} ({wo.title}):\n{wo.resolution_notes}"
                expected_content = f"{wo.title}: {wo.resolution_notes[:200]}"
                
                existing_chunk = DocumentChunk.objects.filter(work_order=wo).first()
                if existing_chunk:
                    # Check if notes or title changed
                    if existing_chunk.parent_content != expected_parent or existing_chunk.content != expected_content:
                        vec = embed_text(f"{wo.title} {wo.resolution_notes}")
                        anchors = extract_diagram_anchors(wo.resolution_notes)
                        existing_chunk.content = expected_content
                        existing_chunk.parent_content = expected_parent
                        existing_chunk.embedding = vec
                        existing_chunk.image_anchors = anchors
                        existing_chunk.is_active = True
                        existing_chunk.save()
                        logger.info(f"[AutoIngest] Successfully updated vector chunk for Work Order {wo.code} ({wo.title})")
                    ingested_count += 1
                else:
                    vec = embed_text(f"{wo.title} {wo.resolution_notes}")
                    anchors = extract_diagram_anchors(wo.resolution_notes)
                    DocumentChunk.objects.create(
                        tenant_id=wo.tenant_id,
                        is_system_guide=False,
                        source_type='TACIT_WORK_ORDER',
                        work_order=wo,
                        is_verified_tacit=True,
                        provenance_wo_code=wo.code,
                        content=expected_content,
                        parent_content=expected_parent,
                        embedding=vec,
                        image_anchors=anchors,
                        is_active=True
                    )
                    ingested_count += 1
                    logger.info(f"[AutoIngest] Successfully vectorized Work Order {wo.code} ({wo.title})")
            else:
                DocumentChunk.objects.filter(work_order=wo).delete()

        return ingested_count
    except Exception as e:
        logger.error(f"[AutoIngest] Error during Work Order ingestion: {e}")
        return 0


def _periodic_worker(interval_seconds: int = 60):
    """Infinite loop daemon worker scanning completed Work Orders."""
    time.sleep(5)  # Wait for Django server startup & imports to settle
    logger.info(f"[AutoIngest] Starting background infinite loop daemon (interval: {interval_seconds}s)...")
    while True:
        try:
            ingest_completed_workorders()
        except Exception as e:
            logger.error(f"[AutoIngest] Daemon error: {e}")
        time.sleep(interval_seconds)


def start_auto_ingestion_loop(interval_seconds: int = 60):
    """Spawns the background infinite daemon loop thread exactly once."""
    global _loop_started
    with _loop_lock:
        if _loop_started:
            return
        
        # Only run background infinite daemon when running the dev/prod server
        cmd_str = " ".join(sys.argv).lower()
        if 'runserver' not in cmd_str:
            return

        thread = threading.Thread(
            target=_periodic_worker,
            args=(interval_seconds,),
            name="TacitWorkOrderAutoIngestDaemon",
            daemon=True
        )
        thread.start()
        _loop_started = True
        logger.info(f"[AutoIngest] Tacit Work Order background infinite loop daemon spawned (interval: {interval_seconds}s).")

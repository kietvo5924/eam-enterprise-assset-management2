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
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)

_loop_started = False
_loop_lock = threading.Lock()


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
        qs = WorkOrder.all_objects.filter(status='COMPLETED')
        if tenant_id:
            qs = qs.filter(tenant_id=tenant_id)

        ingested_count = 0
        for wo in qs:
            if is_valid_tacit_work_order(wo):
                # Check if already vectorized
                if not DocumentChunk.objects.filter(work_order=wo).exists():
                    vec = embed_text(f"{wo.title} {wo.resolution_notes}")
                    anchors = extract_diagram_anchors(wo.resolution_notes)
                    DocumentChunk.objects.create(
                        tenant_id=wo.tenant_id,
                        is_system_guide=False,
                        source_type='TACIT_WORK_ORDER',
                        work_order=wo,
                        is_verified_tacit=True,
                        provenance_wo_code=wo.code,
                        content=f"{wo.title}: {wo.resolution_notes[:200]}",
                        parent_content=f"Work Order {wo.code} ({wo.title}):\n{wo.resolution_notes}",
                        embedding=vec,
                        image_anchors=anchors,
                        is_active=True
                    )
                    ingested_count += 1
                    logger.info(f"[AutoIngest] Successfully vectorized Work Order {wo.code} ({wo.title})")

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

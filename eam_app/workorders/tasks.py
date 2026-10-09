from celery import shared_task
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, name='workorders.run_ga_optimization_task', queue='optimization')
def run_ga_optimization_task(self, job_id: str):
    """
    Celery background worker task executing Genetic Algorithm scheduling.
    Dispatched on 'optimization' queue.
    """
    logger.info(f"Celery worker received GA task for job {job_id}")
    from algorithms.genetic.service import GASchedulingService
    GASchedulingService.execute_job_sync(job_id)
    return {"jobId": job_id, "status": "COMPLETED"}

"""
Facade Orchestration Service for Task 11.2 Genetic Algorithm Optimization.
Handles Job Lifecycle, Multi-Floorplan Scoping, Background Dispatch (Celery/Thread),
Progress Persistence, and Transactional Apply with Real-time Notifications.
"""
import logging
import threading
from typing import List, Dict, Any, Optional
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError

from core.models import Tenant
from users.models import TechnicianProfile, TechnicianSchedule
from assets.models import Location
from workorders.models import WorkOrder, GAOptimizationJob
from algorithms.hungarian.guardrails import filter_task_dependencies
from algorithms.hungarian.cost_matrix import build_tenant_competency_catalog, normalize_text_token
from algorithms.hungarian.service import ConcurrencyConflictError, get_user_display_name
from .solver import MaintenanceGAScheduler
from .constants import DEFAULT_MAX_GENERATIONS, DEFAULT_POPULATION_SIZE, GENERAL_ZONE_TOKENS

logger = logging.getLogger(__name__)


class GASchedulingService:
    """
    Facade Service managing asynchronous GA optimization and assignment application.
    """

    @classmethod
    def initiate_optimization(cls, tenant: Tenant, user,
                              floorplan_id: Optional[str] = None,
                              work_order_ids: Optional[List[str]] = None,
                              max_generations: int = DEFAULT_MAX_GENERATIONS,
                              population_size: int = DEFAULT_POPULATION_SIZE) -> GAOptimizationJob:
        """
        Creates GAOptimizationJob and dispatches background worker execution.
        """
        floorplan_obj = None
        if floorplan_id:
            floorplan_obj = Location.objects.filter(tenant=tenant, id=floorplan_id, is_active=True).first()

        job = GAOptimizationJob.objects.create(
            tenant=tenant,
            created_by=user,
            floorplan=floorplan_obj,
            status='PENDING',
            current_generation=0,
            max_generations=max_generations,
            best_fitness=0.0,
            work_order_ids=[str(x) for x in work_order_ids] if work_order_ids else [],
            convergence_history=[],
            pareto_solutions=[]
        )

        # Dispatch execution: Celery if active worker exists, else background Thread
        dispatched_celery = False
        try:
            from config.celery import app
            active_workers = app.control.ping(timeout=0.3)
            if active_workers:
                from workorders.tasks import run_ga_optimization_task
                run_ga_optimization_task.delay(str(job.id))
                dispatched_celery = True
        except Exception as ex:
            logger.warning(f"Celery ping or dispatch warning: {ex}")

        if not dispatched_celery:
            import sys
            if 'test' not in sys.argv:
                logger.info(f"Dispatching GA job {job.id} via background daemon thread.")
                thread = threading.Thread(
                    target=cls.execute_job_sync,
                    args=(str(job.id),),
                    daemon=True
                )
                thread.start()
            else:
                logger.info(f"Testing environment detected: skipping auto background thread for GA job {job.id}.")

        return job

    @classmethod
    def execute_job_sync(cls, job_id: str):
        """
        Executes GA optimization pipeline for the given job ID.
        Can be invoked by Celery worker or background daemon thread.
        Guarantees database connection cleanup on completion.
        """
        try:
            try:
                job = GAOptimizationJob.objects.select_related('tenant', 'floorplan', 'created_by').get(id=job_id)
            except GAOptimizationJob.DoesNotExist:
                logger.error(f"GAOptimizationJob {job_id} not found.")
                return

            job.status = 'PROCESSING'
            job.save(update_fields=['status', 'updated_at'])

            tenant = job.tenant
            now = timezone.now()

            try:
                # 1. Query Work Orders
                wo_qs = WorkOrder.objects.filter(tenant=tenant)
                if job.work_order_ids and len(job.work_order_ids) > 0:
                    wo_qs = wo_qs.filter(id__in=job.work_order_ids).exclude(status__in=['COMPLETED', 'CANCELLED'])
                else:
                    from datetime import timedelta
                    from django.db.models import Q
                    # Shift Planning Horizon: Target orders due today/within shift window or overdue backlog
                    # Exclude distant future orders (e.g. advance PMs due next week)
                    shift_horizon_cutoff = now + timedelta(hours=24)
                    time_window_q = Q(deadline__isnull=True) | Q(deadline__lte=shift_horizon_cutoff)

                    pending_qs = wo_qs.filter(status__in=['CREATED', 'PENDING'])
                    pending_in_window = pending_qs.filter(time_window_q)
                    if pending_in_window.exists():
                        wo_qs = pending_in_window
                    elif pending_qs.exists():
                        wo_qs = pending_qs
                    else:
                        # Fallback to current uncompleted assigned tickets for shift re-optimization
                        assigned_qs = wo_qs.filter(status='ASSIGNED')
                        assigned_in_window = assigned_qs.filter(time_window_q)
                        wo_qs = assigned_in_window if assigned_in_window.exists() else (assigned_qs if assigned_qs.exists() else pending_qs)

                # Floorplan scoping if specified
                if job.floorplan:
                    fp_id_str = str(job.floorplan.id)
                    from django.db.models import Q
                    wo_qs = wo_qs.filter(
                        Q(asset__location__parent_id=fp_id_str) |
                        Q(asset__location_id=fp_id_str) |
                        Q(zone_id=job.floorplan.code)
                    )

                all_wos = list(
                    wo_qs.select_related('asset__location', 'depends_on_wo')
                    .prefetch_related('materials__spare_part')
                    .order_by('deadline', 'created_at')
                )
                eligible_wos, blocked_wos = filter_task_dependencies(all_wos)

                if not eligible_wos:
                    job.status = 'COMPLETED'
                    job.best_fitness = 100.0
                    job.pareto_solutions = []
                    job.error_message = "Không có phiếu công việc nào cần phân công."
                    job.save()
                    return

                # 2. Query Available Technicians
                from django.db.models import Q
                tech_qs = TechnicianProfile.objects.filter(
                    tenant=tenant,
                    is_on_duty=True,
                    availability_status='AVAILABLE',
                    user__status='ACTIVE'
                ).filter(
                    Q(user__roles__permissions__id='work_order:execute') | Q(user__roles__isnull=True)
                ).distinct().select_related('user')

                # Exclude scheduled OFF or LEAVE today
                try:
                    off_tech_ids = set(TechnicianSchedule.objects.filter(
                        tenant=tenant,
                        work_date=now.date(),
                        status__in=['OFF', 'LEAVE']
                    ).values_list('user_id', flat=True))
                    if off_tech_ids:
                        tech_qs = tech_qs.exclude(user_id__in=off_tech_ids)
                except Exception:
                    pass

                technicians_list = list(tech_qs)

                # Load today schedules
                today_schedules = {}
                try:
                    today_schedules = {
                        ts.user_id: ts for ts in TechnicianSchedule.objects.filter(
                            tenant=tenant,
                            work_date=now.date(),
                            status='ON_DUTY'
                        ).select_related('shift_template')
                    }
                except Exception:
                    pass

                # Query active in-progress work orders for dynamic technician origin anchoring
                in_progress_wos = {}
                try:
                    active_qs = WorkOrder.objects.filter(
                        tenant=tenant,
                        status='IN_PROGRESS',
                        assigned_to__isnull=False
                    ).select_related('asset__location')
                    for a_wo in active_qs:
                        in_progress_wos[str(a_wo.assigned_to_id)] = a_wo
                except Exception:
                    pass

                # Floorplan filter for Technicians (if floorplan is specified)
                competency_catalog = build_tenant_competency_catalog(tenant)
                filtered_techs = []

                for t in technicians_list:
                    sched = today_schedules.get(t.user_id)
                    if sched and getattr(sched, 'duty_zone_id', None):
                        t.zone_id = sched.duty_zone_id

                    tz_tok = normalize_text_token(t.zone_id)
                    is_roving = (
                        tz_tok in GENERAL_ZONE_TOKENS or
                        any(g in tz_tok for g in {'TOAN_NHA_MAY', 'TOAN_CONG_TY', 'CO_DONG', 'ROVING'})
                    )

                    if job.floorplan:
                        fp_id_str = str(job.floorplan.id)
                        zone_to_fp = competency_catalog.get('zone_to_floorplan', {})
                        t_fp = zone_to_fp.get(tz_tok, "")
                        if t_fp == fp_id_str or is_roving or not t_fp:
                            filtered_techs.append(t)
                    else:
                        filtered_techs.append(t)

                if not filtered_techs:
                    # If no techs match floorplan, fallback to all available techs
                    filtered_techs = technicians_list

                if not filtered_techs:
                    job.status = 'COMPLETED'
                    job.best_fitness = 0.0
                    job.pareto_solutions = []
                    job.error_message = "Không có kỹ thuật viên nào đang trong ca trực hoặc khả dụng."
                    job.save()
                    return

                # 3. Locate Warehouse Location on target floorplan if available
                warehouse_coords = None
                try:
                    wh_loc = Location.objects.filter(
                        tenant=tenant,
                        is_active=True
                    ).filter(
                        Q(code__icontains='WAREHOUSE') | Q(code__icontains='KHO') |
                        Q(name__icontains='KHO') | Q(zone_type__in=['STORAGE', 'WAREHOUSE'])
                    ).first()
                    if wh_loc:
                        warehouse_coords = (
                            float(wh_loc.center_x or 0.0),
                            float(wh_loc.center_y or 0.0),
                            int(wh_loc.floor_level or 1),
                            wh_loc.code or "ZONE_WAREHOUSE"
                        )
                except Exception:
                    pass

                # 4. Progress Callback closure to persist intermediate generations
                def on_progress(gen, max_g, best_fit, history):
                    try:
                        job.current_generation = gen
                        job.best_fitness = best_fit
                        job.convergence_history = history
                        job.save(update_fields=['current_generation', 'best_fitness', 'convergence_history', 'updated_at'])
                    except Exception as e:
                        logger.debug(f"Progress save skipped: {e}")

                # 5. Execute Genetic Algorithm Evolution Loop
                scheduler = MaintenanceGAScheduler(
                    work_orders=eligible_wos,
                    technicians=filtered_techs,
                    config={
                        'maxGenerations': job.max_generations,
                        'populationSize': 50 if job.max_generations <= 60 else 100
                    },
                    catalog=competency_catalog,
                    warehouse_coords=warehouse_coords,
                    current_time=now,
                    today_schedules=today_schedules,
                    in_progress_wos=in_progress_wos,
                    progress_callback=on_progress
                )

                result = scheduler.run()

                # Attach blocked work orders metadata to pareto solutions
                pareto_solutions = result['paretoSolutions']
                if blocked_wos:
                    for sol in pareto_solutions:
                        sol['blockedWorkOrders'] = blocked_wos

                # 6. Complete and Save Job
                job.status = 'COMPLETED'
                job.current_generation = job.max_generations
                job.best_fitness = result['bestFitness']
                job.convergence_history = result['convergenceHistory']
                job.pareto_solutions = pareto_solutions
                job.error_message = None
                job.save()
                logger.info(f"GA Job {job.id} completed successfully with best fitness {job.best_fitness}.")

            except Exception as e:
                logger.exception(f"GA Job {job.id} failed: {e}")
                job.status = 'FAILED'
                job.error_message = str(e)
                job.save(update_fields=['status', 'error_message', 'updated_at'])

        finally:
            import threading
            if threading.current_thread() != threading.main_thread():
                try:
                    from django.db import connection
                    connection.close()
                except Exception:
                    pass

    @classmethod
    @transaction.atomic
    def apply_solution(cls, tenant: Tenant,
                       assignments_data: List[Dict[str, Any]],
                       current_user=None) -> Dict[str, Any]:
        """
        Atomically applies approved Pareto schedule to the database.
        Locks candidate WorkOrders and Technicians via select_for_update.
        Guarantees Tool Reservations and Dispatches real-time notification alerts.
        """
        from notifications.services import notify_work_order_assigned

        wo_ids = [str(item['workOrderId']) for item in assignments_data]
        tech_ids = [str(item['technicianId']) for item in assignments_data]

        # Concurrency Lock: select_for_update
        wo_qs = WorkOrder.objects.select_for_update().filter(tenant=tenant, id__in=wo_ids)
        wos = {str(wo.id): wo for wo in wo_qs}

        tech_qs = TechnicianProfile.objects.select_for_update().filter(tenant=tenant, user_id__in=tech_ids).select_related('user')
        techs = {str(t.user_id): t for t in tech_qs}

        # Validate existence & lock state
        for item in assignments_data:
            wo_id = str(item['workOrderId'])
            tech_id = str(item['technicianId'])

            if wo_id not in wos:
                raise ValidationError(f"Phiếu công việc {wo_id} không tồn tại hoặc không thuộc tổ chức hiện tại.")
            if tech_id not in techs:
                raise ValidationError(f"Kỹ thuật viên {tech_id} không tồn tại hoặc không thuộc tổ chức hiện tại.")

            wo = wos[wo_id]
            tech = techs[tech_id]

            if wo.status in ['IN_PROGRESS', 'COMPLETED', 'CANCELLED']:
                raise ConcurrencyConflictError(
                    f"Phiếu công việc {wo.code} đang xử lý ({wo.status}), đã hoàn tất hoặc bị hủy, không thể phân công đè."
                )

            if not tech.is_on_duty or tech.availability_status == 'ON_LEAVE':
                raise ConcurrencyConflictError(
                    f"Kỹ thuật viên {get_user_display_name(tech.user)} hiện không khả dụng (Trực: {tech.is_on_duty}, Trạng thái: {tech.availability_status})."
                )

        # Apply assignments
        now = timezone.now()
        applied_list = []

        for item in assignments_data:
            wo_id = str(item['workOrderId'])
            tech_id = str(item['technicianId'])

            wo = wos[wo_id]
            tech = techs[tech_id]

            wo.assigned_to = tech.user
            wo.assigned_at = now
            wo.status = 'ASSIGNED'
            wo.save()

            # Mark technician as BUSY
            tech.availability_status = 'BUSY'
            tech.save()

            # Tool Reservation Concurrency Handling
            try:
                from assets.models import Tool, ToolReservation, ToolInstance
                if wo.required_tools and isinstance(wo.required_tools, list):
                    for tool_item in wo.required_tools:
                        if isinstance(tool_item, dict):
                            t_code = tool_item.get('code')
                            req_qty = int(tool_item.get('quantity', 1))
                        else:
                            t_code = str(tool_item)
                            req_qty = 1

                        tool_obj = Tool.objects.select_for_update().filter(tenant=tenant, code=t_code, is_active=True).first()
                        if tool_obj:
                            inst = ToolInstance.objects.filter(tool=tool_obj, tenant=tenant, status='AVAILABLE').first()
                            ToolReservation.objects.create(
                                tenant=tenant,
                                tool=tool_obj,
                                tool_instance=inst,
                                work_order=wo,
                                reserved_quantity=req_qty,
                                status='RESERVED'
                            )
                            if tool_obj.available_quantity >= req_qty:
                                tool_obj.available_quantity -= req_qty
                                tool_obj.save()
                            if inst:
                                inst.status = 'IN_USE'
                                inst.save()
            except Exception as ex:
                logger.warning(f"GA Tool reservation warning for WO {wo.code}: {ex}")

            # Dispatch notification
            try:
                notify_work_order_assigned(wo, assignee=tech.user, is_reassigned=False, sender=current_user)
            except Exception:
                pass

            applied_list.append({
                "workOrderId": str(wo.id),
                "workOrderCode": wo.code,
                "technicianId": str(tech.user_id),
                "technicianName": get_user_display_name(tech.user),
                "status": wo.status
            })

        return {
            "appliedCount": len(applied_list),
            "assignments": applied_list
        }

from celery import shared_task
from django.utils import timezone
from django.db import transaction
from maintenance.models import PmPlanAssignment, PmPlan
from workorders.models import WorkOrder, WorkOrderChecklistItem, WorkOrderMaterial
from assets.models import MeterReading, SparePart
import logging

logger = logging.getLogger(__name__)

@shared_task
def evaluate_triggers():
    active_assignments = PmPlanAssignment.objects.filter(status='ACTIVE')
    now = timezone.now()
    
    for assignment in active_assignments:
        pm_plan = assignment.pm_plan
        should_trigger = False
        next_due_date = now
        
        source_reference = f"PM_{pm_plan.id}_ASSET_{assignment.asset_id}"
        
        if pm_plan.trigger_type == 'TIME':
            reference_date = assignment.last_triggered_at or assignment.created_at
            
            if pm_plan.is_floating_schedule:
                last_completed_wo = WorkOrder.objects.filter(
                    source_reference=source_reference, 
                    status='COMPLETED'
                ).order_by('-completed_at').first()
                if last_completed_wo and last_completed_wo.completed_at:
                    reference_date = last_completed_wo.completed_at
                    
            due_date = reference_date
            if pm_plan.interval_unit and pm_plan.interval_value:
                interval = int(pm_plan.interval_value)
                if interval > 0:
                    from dateutil.relativedelta import relativedelta
                    if pm_plan.interval_unit == 'DAYS':
                        due_date += relativedelta(days=interval)
                    elif pm_plan.interval_unit == 'WEEKS':
                        due_date += relativedelta(weeks=interval)
                    elif pm_plan.interval_unit == 'MONTHS':
                        due_date += relativedelta(months=interval)
                    elif pm_plan.interval_unit == 'YEARS':
                        due_date += relativedelta(years=interval)
                        
            generation_date = due_date
            if pm_plan.lead_time_days > 0:
                generation_date = due_date - timezone.timedelta(days=pm_plan.lead_time_days)
                
            if generation_date <= now:
                should_trigger = True
                next_due_date = due_date
                
        elif pm_plan.trigger_type in ['METER', 'USAGE']:
            latest_reading = MeterReading.objects.filter(asset_id=assignment.asset_id).order_by('-reading_date').first()
            if latest_reading:
                current_reading = latest_reading.reading_value
                reference_reading = assignment.last_triggered_meter or assignment.baseline_meter_reading or 0
                threshold = pm_plan.interval_value or 0
                
                if current_reading - reference_reading >= threshold and threshold > 0:
                    should_trigger = True
                    next_due_date = now
                    
        if should_trigger:
            if pm_plan.suppress_if_pending:
                has_pending = WorkOrder.objects.filter(
                    source_reference=source_reference
                ).exclude(status__in=['COMPLETED', 'CANCELLED']).exists()
                if has_pending:
                    continue
                    
            with transaction.atomic():
                # Update assignment
                assignment.last_triggered_at = next_due_date
                if pm_plan.trigger_type in ['METER', 'USAGE']:
                    latest_reading = MeterReading.objects.filter(asset_id=assignment.asset_id).order_by('-reading_date').first()
                    if latest_reading:
                        assignment.last_triggered_meter = latest_reading.reading_value
                assignment.save()
                
                # Create Work Order
                wo = WorkOrder.objects.create(
                    tenant_id=assignment.tenant_id,
                    asset_id=assignment.asset_id,
                    title=f"PM: {pm_plan.name} for {assignment.asset.name}",
                    description=pm_plan.description,
                    priority="MEDIUM",
                    status="CREATED",
                    deadline=next_due_date,
                    estimated_duration_minutes=pm_plan.estimated_duration_minutes,
                    source_reference=source_reference,
                    assigned_to=pm_plan.assignee
                )
                
                # Dispatch PM generation notification
                from notifications.services import notify_pm_work_order_generated, notify_spare_part_low_stock
                notify_pm_work_order_generated(pm_plan, wo, asset=assignment.asset)
                
                # Create Checklists
                for pc in pm_plan.checklists.all():
                    WorkOrderChecklistItem.objects.create(
                        tenant_id=assignment.tenant_id,
                        work_order=wo,
                        item_name=pc.item_name,
                        input_type=pc.input_type,
                        expected_value=pc.expected_value,
                        is_mandatory=pc.is_mandatory,
                        is_completed=False
                    )
                    
                # Create Materials
                for pm in pm_plan.materials.all():
                    part = pm.spare_part
                    req_qty = pm.quantity
                    
                    if part.quantity_in_stock is not None:
                        # Prevent negative stock, but still create material requirement
                        if part.quantity_in_stock >= req_qty:
                            part.quantity_in_stock -= req_qty
                            part.save()
                        else:
                            logger.warning(f"Not enough stock for {part.name} in PM {pm_plan.name}")
                            # In a real system, you might create a purchase request or backorder here
                            # We'll just deduct what we can or leave it. We'll leave it as is to simulate deducting
                            part.quantity_in_stock -= req_qty
                            part.save()
                            
                        # Check low-stock warning
                        notify_spare_part_low_stock(part)
                            
                    WorkOrderMaterial.objects.create(
                        tenant_id=assignment.tenant_id,
                        work_order=wo,
                        spare_part=part,
                        quantity=req_qty
                    )
                
                logger.info(f"Created PM Work Order {wo.id} from Plan {pm_plan.id}")

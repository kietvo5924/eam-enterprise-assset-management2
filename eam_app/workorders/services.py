import uuid
import logging
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError, NotFound

from workorders.models import WorkOrder
from assets.models import Asset, MeterReading, ToolReservation, AssetAnomalyAlert
from users.models import TechnicianSchedule
from assets.models import Location

logger = logging.getLogger(__name__)


class WorkOrderTransitionService:
    """
    Canonical State Transition Service for WorkOrder.
    Đảm bảo tính Idempotent, chống race-condition qua select_for_update,
    phân loại chính xác bảo dưỡng vi mô (MICRO_MAINTENANCE) và đại tu (CORE_REPLACEMENT),
    bảo toàn số đo nghiệm thu sau sửa chữa (POST_REPAIR_ACCEPTANCE).
    """

    @classmethod
    @transaction.atomic
    def complete_work_order(
        cls,
        work_order_id,
        user=None,
        resolution_notes='',
        maintenance_action=None,
        actual_duration_minutes=None,
        post_repair_data=None,
        tenant_id=None
    ):
        query = WorkOrder.objects.select_for_update()
        if tenant_id:
            query = query.filter(tenant_id=tenant_id)

        wo = query.filter(id=work_order_id).first()
        if not wo:
            raise NotFound("Work Order not found")

        # 1. Idempotency Check: Nếu đã COMPLETED trước đó, trả về luôn không thực hiện lại
        if wo.status == 'COMPLETED':
            return wo

        # 2. State Validation: Chỉ có thể hoàn thành từ IN_PROGRESS
        if wo.status != 'IN_PROGRESS':
            raise ValidationError("Work Order can only be completed from IN_PROGRESS state")

        # 3. Check mandatory checklist items & number validation
        for item in wo.checklists.all():
            if item.is_mandatory:
                if not item.is_completed:
                    raise ValidationError(f"Không thể hoàn thành: Chưa hoàn thành bước bắt buộc '{item.item_name}'")
                if item.input_type == 'NUMBER':
                    val_str = str(item.actual_value or '').strip().replace(',', '.')
                    if not val_str:
                        raise ValidationError(f"Không thể hoàn thành: Mục bắt buộc '{item.item_name}' chưa có số liệu đo kiểm.")
                    try:
                        float(val_str)
                    except ValueError:
                        raise ValidationError(f"Không thể hoàn thành: Số liệu đo kiểm của mục '{item.item_name}' phải là một số hợp lệ.")

        # 4. Check attachment requirement
        if not wo.attachments.exists():
            raise ValidationError("Bắt buộc phải tải lên ít nhất một hình ảnh minh chứng trước khi hoàn thành công việc.")

        now = timezone.now()
        wo.completed_at = now
        wo.completion_processed_at = now
        wo.status = 'COMPLETED'
        if resolution_notes:
            wo.resolution_notes = resolution_notes.strip()
        if actual_duration_minutes is not None:
            wo.actual_duration_minutes = actual_duration_minutes
        
        # Validate & set maintenance action: preserve existing wo.maintenance_action if not provided
        if maintenance_action in ('GENERAL', 'MICRO_MAINTENANCE', 'CORE_REPLACEMENT'):
            wo.maintenance_action = maintenance_action
        elif not wo.maintenance_action:
            wo.maintenance_action = 'GENERAL'

        # Set post repair telemetry if supplied
        if post_repair_data and isinstance(post_repair_data, dict):
            if 'vibration' in post_repair_data and post_repair_data['vibration'] is not None:
                wo.post_repair_vibration = float(post_repair_data['vibration'])
            if 'temperature' in post_repair_data and post_repair_data['temperature'] is not None:
                wo.post_repair_temperature = float(post_repair_data['temperature'])
            if 'load_factor' in post_repair_data and post_repair_data['load_factor'] is not None:
                wo.post_repair_load_factor = float(post_repair_data['load_factor'])

        wo.save()

        # 5. Ghi nhận số đo nghiệm thu sau sửa chữa (POST_REPAIR_ACCEPTANCE) nếu có
        if post_repair_data and isinstance(post_repair_data, dict) and wo.asset:
            cls._record_post_repair_acceptance(wo, post_repair_data, user, now)

        # 6. Post-Repair Window Reset Guardrail:
        # CHỈ KHI CORE_REPLACEMENT mới đóng băng dữ liệu cũ và reset baseline RUL!
        if wo.maintenance_action == 'CORE_REPLACEMENT' and wo.asset_id:
            # Đóng băng các số đo cũ trước thời điểm hoàn thành (loại trừ nghiệm thu)
            MeterReading.objects.filter(
                asset_id=wo.asset_id,
                reading_date__lte=now
            ).exclude(
                measurement_phase='POST_REPAIR_ACCEPTANCE'
            ).update(is_pre_repair=True)

            # Cập nhật mốc đại tu và đưa RUL về chế độ hiệu chuẩn lại
            Asset.objects.filter(id=wo.asset_id).update(
                last_core_overhaul_at=now,
                is_phantom_recovery=False,
                rul_risk_level='CALIBRATING'
            )

        # 7. Tự động hoàn trả dụng cụ (Auto-return ToolReservations)
        cls._release_tool_reservations(wo, now)

        # 8. Technician positioning logic
        assigned_user = wo.assigned_to or user
        if assigned_user:
            cls._position_technician_on_complete(wo, assigned_user, now)

        # 9. Gửi thông báo hoàn thành
        try:
            from notifications.services import notify_work_order_completed
            notify_work_order_completed(wo, technician=assigned_user)
        except Exception as ex:
            logger.warning(f"Error dispatching work order completion notification: {ex}")

        # 10. Đóng vòng đời AssetAnomalyAlert
        if wo.asset_id:
            AssetAnomalyAlert.objects.filter(
                asset_id=wo.asset_id,
                status__in=['OPEN', 'ACKNOWLEDGED'],
                created_at__lte=now
            ).filter(
                Q(draft_work_order=wo) | Q(draft_work_order__isnull=True)
            ).update(status='RESOLVED')

        logger.info(f"[KAFKA MOCK] work_orders_topic - work_order.completed: wo_id={wo.id}, action={wo.maintenance_action}")
        return wo

    @classmethod
    def _record_post_repair_acceptance(cls, wo, post_repair_data, user, recorded_at):
        round_uuid = uuid.uuid4()
        load_f = float(post_repair_data.get('load_factor') or 1.0)
        amb_t = post_repair_data.get('ambient_temperature')
        amb_t_val = float(amb_t) if amb_t is not None else None

        # Rung sau sửa chữa
        vib_val = post_repair_data.get('vibration')
        if vib_val is not None:
            try:
                MeterReading.objects.create(
                    tenant=wo.tenant,
                    asset=wo.asset,
                    work_order=wo,
                    metric_code='VIBRATION',
                    reading_value=float(vib_val),
                    reading_date=recorded_at,
                    unit='mm/s',
                    ambient_temperature=amb_t_val,
                    load_factor=load_f,
                    machine_state='RUNNING',
                    measurement_phase='POST_REPAIR_ACCEPTANCE',
                    is_pre_repair=False,
                    recorded_by=user if (user and user.is_authenticated) else None,
                    round_id=round_uuid,
                    remarks=f"Nghiệm thu sau sửa chữa cho phiếu {wo.code or wo.title}"
                )
            except Exception as ex:
                logger.warning(f"Lỗi lưu số đo nghiệm thu rung: {ex}")

        # Nhiệt độ sau sửa chữa
        temp_val = post_repair_data.get('temperature')
        if temp_val is not None:
            try:
                MeterReading.objects.create(
                    tenant=wo.tenant,
                    asset=wo.asset,
                    work_order=wo,
                    metric_code='TEMPERATURE',
                    reading_value=float(temp_val),
                    reading_date=recorded_at,
                    unit='°C',
                    ambient_temperature=amb_t_val,
                    load_factor=load_f,
                    machine_state='RUNNING',
                    measurement_phase='POST_REPAIR_ACCEPTANCE',
                    is_pre_repair=False,
                    recorded_by=user if (user and user.is_authenticated) else None,
                    round_id=round_uuid,
                    remarks=f"Nghiệm thu sau sửa chữa cho phiếu {wo.code or wo.title}"
                )
            except Exception as ex:
                logger.warning(f"Lỗi lưu số đo nghiệm thu nhiệt: {ex}")

    @classmethod
    def _release_tool_reservations(cls, wo, returned_at):
        try:
            active_res = ToolReservation.objects.filter(
                tenant=wo.tenant,
                work_order=wo,
                status__in=['RESERVED', 'IN_USE']
            )
            for r in active_res:
                r.status = 'RETURNED'
                r.returned_at = returned_at
                r.save(update_fields=['status', 'returned_at', 'updated_at'])
                if r.tool:
                    r.tool.available_quantity = r.tool.available_quantity + r.reserved_quantity
                    r.tool.save(update_fields=['available_quantity', 'updated_at'])
                if r.tool_instance:
                    r.tool_instance.status = 'AVAILABLE'
                    r.tool_instance.save(update_fields=['status', 'updated_at'])
        except Exception as ex:
            logger.warning(f"Lỗi hoàn trả dụng cụ cho WO {wo.id}: {ex}")

    @classmethod
    def _position_technician_on_complete(cls, wo, technician_user, now):
        try:
            if hasattr(technician_user, 'technician_profile'):
                tp = technician_user.technician_profile
                tp.availability_status = 'AVAILABLE'
                today_sched = TechnicianSchedule.objects.filter(
                    tenant=wo.tenant,
                    user=technician_user,
                    work_date=now.date(),
                    status='ON_DUTY'
                ).first()
                if today_sched and today_sched.duty_zone_id:
                    loc = Location.objects.filter(tenant=wo.tenant, code=today_sched.duty_zone_id).first()
                    if loc:
                        tp.zone_id = loc.code
                        tp.coords_x = loc.center_x or 25.0
                        tp.coords_y = loc.center_y or 20.0
                        tp.floor_level = loc.floor_level or 1
                tp.save()
        except Exception as ex:
            logger.warning(f"Lỗi định vị kỹ thuật viên sau hoàn thành WO {wo.id}: {ex}")

"""
RUL Predictive Service (Phase 11.5 Orchestrator).
Nhạc trưởng điều phối: Nạp chuỗi thời gian, gọi Guardrails, suy diễn PyTorch/NumPy LSTM,
kiểm tra tồn kho SparePart, tự động sinh bản thảo Work Order đón đầu và điều phối Hungarian.
"""

import uuid
import logging
import numpy as np
from datetime import timedelta
from typing import List, Dict, Any, Optional
from django.utils import timezone
from django.db import transaction
from rest_framework.exceptions import ValidationError

from assets.models import Asset, MeterReading, SparePart, AssetRulPrediction
from workorders.models import WorkOrder
from notifications.services import dispatch_event_notification, NotificationRouter

from .constants import (
    WINDOW_SIZE, FEATURE_DIM, MC_DROPOUT_PASSES, MODEL_VERSION
)
from .model import get_rul_model
from .dataset_pipeline import DegradationFeaturePipeline
from .guardrails import PredictiveRULGuardrails

logger = logging.getLogger(__name__)


class RULPredictiveService:
    """
    Enterprise Deep Learning RUL Predictive Service.
    Tích hợp toàn diện 10 quy tắc nghiệp vụ phòng thủ.
    """

    @classmethod
    @transaction.atomic
    def predict_asset_rul(
        cls,
        asset: Asset,
        trigger_source: str = 'MANUAL',
        custom_load_factor: Optional[float] = None,
        current_user = None,
        session_readings: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        now = timezone.now()
        cur_tenant = getattr(asset, 'tenant', None)

        # -------------------------------------------------------------
        # Bước 1: Quy Tắc 10 - Chặn tài sản tĩnh (Machinery vs Passive Asset)
        # -------------------------------------------------------------
        is_machinery, static_err = PredictiveRULGuardrails.validate_asset_machinery_type(asset)
        if not is_machinery:
            raise ValidationError({"error": static_err, "code": "PASSIVE_ASSET_REJECTED"})

        # -------------------------------------------------------------
        # Bước 2: Thu thập và lọc sạch chuỗi dữ liệu (Quy Tắc 3)
        # -------------------------------------------------------------
        readings_qs = MeterReading.objects.filter(
            asset=asset,
            is_suppressed=False
        ).order_by('reading_date')

        # Lọc trạng thái RUNNING và loại bỏ số đo trước đại tu cũ (is_pre_repair == False)
        valid_readings = PredictiveRULGuardrails.filter_running_meter_readings(readings_qs)

        # Nếu có số đo gửi kèm trong phiên hiện tại
        if session_readings:
            for s in session_readings:
                state = str(s.get('machine_state', 'RUNNING') or 'RUNNING').upper()
                if state == 'RUNNING':
                    valid_readings.append(s)

        running_count = len(valid_readings)

        # -------------------------------------------------------------
        # Bước 3: Quy Tắc 2 - Ngưỡng Khởi Động Nguội (Bypass Threshold N < 15)
        # -------------------------------------------------------------
        is_cold_start, cold_msg = PredictiveRULGuardrails.check_cold_start_bypass(running_count)
        if is_cold_start:
            # Cập nhật trạng thái CALIBRATING trên Asset
            asset.current_rul_days = None
            asset.current_rul_calendar_days = None
            asset.rul_confidence_lower = None
            asset.rul_confidence_upper = None
            asset.rul_risk_level = 'CALIBRATING'
            asset.last_rul_predicted_at = now
            asset.save(update_fields=[
                'current_rul_days', 'current_rul_calendar_days',
                'rul_confidence_lower', 'rul_confidence_upper',
                'rul_risk_level', 'last_rul_predicted_at', 'updated_at'
            ])

            return {
                "success": True,
                "data": {
                    "assetId": str(asset.id),
                    "assetName": asset.name,
                    "currentStatus": "CALIBRATING",
                    "validRunningSamples": running_count,
                    "requiredSamplesThreshold": 15,
                    "operatingRulDays": None,
                    "calendarRulDays": None,
                    "riskLevel": "CALIBRATING",
                    "message": cold_msg
                }
            }

        # -------------------------------------------------------------
        # Bước 4: Xây dựng ma trận cửa sổ trượt (W=30, F=4) - Quy Tắc 1
        # -------------------------------------------------------------
        # Nếu 15 <= running_count < 30: Pad nhân bản các mẫu gần nhất để đủ 30 bước
        padded_readings = list(valid_readings)
        while len(padded_readings) < WINDOW_SIZE:
            padded_readings.insert(0, valid_readings[0])

        input_sequence = DegradationFeaturePipeline.construct_sliding_window(
            raw_readings=padded_readings,
            window_size=WINDOW_SIZE
        )

        # Nếu có custom_load_factor ghi đè tạm thời
        if custom_load_factor is not None:
            norm_load = DegradationFeaturePipeline.normalize_feature(custom_load_factor, 'load_factor')
            input_sequence[:, 3] = norm_load

        # -------------------------------------------------------------
        # Bước 5: Suy diễn Monte Carlo Dropout M=20 lần (Quy Tắc 6)
        # -------------------------------------------------------------
        model = get_rul_model()
        mc_predictions = []
        for _ in range(MC_DROPOUT_PASSES):
            pred_pass = model.forward_one_pass(input_sequence, apply_dropout=True)
            mc_predictions.append(pred_pass)

        uncertainty_info = PredictiveRULGuardrails.calculate_mc_dropout_uncertainty(mc_predictions)
        rul_mean = uncertainty_info['rul_mean']
        previous_rul = asset.current_rul_days

        # -------------------------------------------------------------
        # Bước 6: Kiểm tra Bẫy Hồi Phục Ảo Phantom Recovery (Quy Tắc 4)
        # -------------------------------------------------------------
        # Tìm hành động bảo trì hoàn thành gần nhất
        last_completed_wo = WorkOrder.objects.filter(
            asset=asset,
            status='COMPLETED'
        ).order_by('-completed_at').first()

        last_action = getattr(last_completed_wo, 'maintenance_action', None)
        is_core_overhaul = (last_action == 'CORE_REPLACEMENT')

        rul_after_phantom, is_phantom = PredictiveRULGuardrails.check_phantom_recovery(
            model_predicted_rul=rul_mean,
            previous_rul=previous_rul,
            last_maintenance_action=last_action
        )

        # -------------------------------------------------------------
        # Bước 7: Bộ lọc suy thoái đơn điệu vật lý (Quy Tắc 5)
        # -------------------------------------------------------------
        if not is_phantom:
            final_rul_op = PredictiveRULGuardrails.apply_monotonic_filter(
                current_rul=rul_after_phantom,
                previous_rul=previous_rul,
                is_core_overhaul_completed=is_core_overhaul
            )
        else:
            final_rul_op = rul_after_phantom

        # Quy đổi sang Ngày Dương Lịch (CalendarDays - Quy Tắc 3)
        cal_days = PredictiveRULGuardrails.evaluate_duty_cycle_calendar_days(
            operating_rul_days=final_rul_op,
            duty_cycle_ratio=asset.duty_cycle_ratio
        )

        # -------------------------------------------------------------
        # Bước 8: Kiểm tra Ngưỡng Động theo Lead Time Kho Phụ Tùng (Quy Tắc 7)
        # -------------------------------------------------------------
        spare_part = getattr(asset, 'primary_spare_part', None)
        lead_time = int(spare_part.lead_time_days) if spare_part else 7
        crit_threshold = PredictiveRULGuardrails.calculate_dynamic_critical_threshold(lead_time)

        # Kiểm tra tồn kho khả dụng
        stock_qty = float(spare_part.quantity_in_stock) if spare_part else 0.0
        is_stock_sufficient = bool(stock_qty >= 1.0)

        # -------------------------------------------------------------
        # Bước 9: Phát hiện gia tốc suy thoái đột biến (Quy Tắc 9)
        # -------------------------------------------------------------
        recent_preds = list(AssetRulPrediction.objects.filter(
            asset=asset
        ).order_by('-created_at')[:2].values_list('predicted_rul_op_days', flat=True))
        recent_preds.reverse()
        recent_preds.append(final_rul_op)

        is_rapid, rapid_rate = PredictiveRULGuardrails.detect_rapid_degradation(recent_preds)

        # Đánh giá cấp độ rủi ro (CRITICAL, HIGH, MEDIUM, LOW)
        risk_level = PredictiveRULGuardrails.evaluate_risk_level(
            rul_op_days=final_rul_op,
            critical_threshold=crit_threshold,
            rapid_alert=is_rapid
        )

        # -------------------------------------------------------------
        # Bước 10: Xử lý hành động bảo trì đón đầu (Draft PM Work Order)
        # -------------------------------------------------------------
        created_wo = None
        action_taken = 'NORMAL_MONITORING'

        if risk_level == 'CRITICAL' or is_rapid:
            # Kiểm tra xem đã có phiếu WO nào đang mở (CREATED / ASSIGNED / IN_PROGRESS) cho asset này chưa
            existing_active_wo = WorkOrder.objects.filter(
                asset=asset,
                status__in=['CREATED', 'ASSIGNED', 'IN_PROGRESS'],
                type__in=['PREDICTIVE_PM', 'CORRECTIVE', 'EMERGENCY']
            ).first()

            if not existing_active_wo:
                wo_priority = 'URGENT' if is_rapid else 'HIGH'
                wo_title = f"Bảo trì dự đoán đón đầu: {asset.name} (RUL còn {final_rul_op} ngày)"
                wo_desc = (
                    f"Phiếu bảo trì tự động khởi tạo bởi AI Predictive Maintenance (Phase 11.5).\n"
                    f"- RUL vận hành còn lại: {final_rul_op} ngày (Khoảng tin cậy 90%: {uncertainty_info['confidence_lower']} - {uncertainty_info['confidence_upper']} ngày).\n"
                    f"- Quy đổi ngày dương lịch: {cal_days} ngày (Hệ số tải chu kỳ: {asset.duty_cycle_ratio}).\n"
                    f"- Ngưỡng Critical động: {crit_threshold} ngày (Thời gian nhập vật tư: {lead_time} ngày).\n"
                    f"- Phụ tùng cốt lõi: {spare_part.name if spare_part else 'Chưa gán'} (Tồn kho: {stock_qty})."
                )
                if not is_stock_sufficient:
                    wo_desc += "\n[CẢNH BÁO TỒN KHO]: Phụ tùng trong kho không đủ. Kích hoạt dự thảo yêu cầu mua sắm khẩn cấp."
                if is_rapid:
                    wo_desc += f"\n[BÁO ĐỘNG SỤT GIẢM ĐỘT BIẾN]: Tốc độ suy thoái sụt {rapid_rate} ngày/lần đo. Cần can thiệp gấp!"

                # Gợi ý dụng cụ chuyên dụng
                suggested_tools = ['VIB_METER', 'BEARING_PULLER', 'INDUCTION_HEATER']
                suggested_parts = [str(spare_part.id)] if spare_part else []

                created_wo = WorkOrder.objects.create(
                    tenant=cur_tenant,
                    asset=asset,
                    title=wo_title,
                    description=wo_desc,
                    type='PREDICTIVE_PM',
                    priority=wo_priority,
                    status='CREATED',
                    deadline=now + timedelta(days=max(1, int(cal_days))),
                    required_skill='Cơ khí',
                    min_skill_level=2,
                    required_tools=suggested_tools,
                    required_spare_parts=suggested_parts,
                    coords_x=getattr(asset, 'coords_x', None),
                    coords_y=getattr(asset, 'coords_y', None),
                    floor_level=getattr(asset, 'floor_level', 1) or 1,
                    zone_id=getattr(asset, 'zone_id', '') or '',
                    created_by=current_user
                )

                # Điều phối tức thời bằng giải thuật Hungarian (nếu có kỹ thuật viên khả dụng)
                try:
                    from algorithms.hungarian.service import HungarianAssignmentService
                    preview = HungarianAssignmentService.preview(tenant=cur_tenant, work_order_ids=[str(created_wo.id)])
                    assignments = preview.get('assignments', [])
                    if assignments:
                        top_assign = assignments[0]
                        HungarianAssignmentService.apply(
                            tenant=cur_tenant,
                            assignments_data=[{
                                'workOrderId': str(created_wo.id),
                                'technicianId': str(top_assign['technicianId']),
                                'slotRole': 'SOLO'
                            }],
                            current_user=current_user
                        )
                        created_wo.refresh_from_db()
                except Exception as e:
                    logger.warning(f"Hungarian auto-assignment for Predictive PM {created_wo.id} skipped: {e}")

                action_taken = 'URGENT_PM_CREATED' if is_rapid else 'DRAFT_PM_CREATED'
            else:
                created_wo = existing_active_wo
                action_taken = 'ACTIVE_WO_ALREADY_EXISTS'
        elif risk_level == 'HIGH':
            action_taken = 'CHECK_INVENTORY' if not is_stock_sufficient else 'NORMAL_MONITORING'

        # -------------------------------------------------------------
        # Bước 11: Lưu lịch sử vào bảng AssetRulPrediction & Cập nhật Asset
        # -------------------------------------------------------------
        norm_avg_load = float(np.mean(input_sequence[:, 3]))
        avg_load = DegradationFeaturePipeline.denormalize_feature(norm_avg_load, 'load_factor')

        prediction_record = AssetRulPrediction.objects.create(
            tenant=cur_tenant,
            asset=asset,
            predicted_rul_op_days=final_rul_op,
            predicted_rul_cal_days=cal_days,
            confidence_lower=uncertainty_info['confidence_lower'],
            confidence_upper=uncertainty_info['confidence_upper'],
            std_deviation=uncertainty_info['rul_std'],
            risk_level=risk_level,
            trigger_source=trigger_source,
            load_factor_average=round(avg_load, 2),
            input_window_samples_count=WINDOW_SIZE,
            is_phantom_recovery=is_phantom,
            rapid_degradation_rate=rapid_rate,
            action_taken=action_taken,
            work_order=created_wo,
            model_version=MODEL_VERSION
        )

        # Cập nhật Asset
        asset.current_rul_days = final_rul_op
        asset.current_rul_calendar_days = cal_days
        asset.rul_confidence_lower = uncertainty_info['confidence_lower']
        asset.rul_confidence_upper = uncertainty_info['confidence_upper']
        asset.rul_risk_level = risk_level
        asset.is_phantom_recovery = is_phantom
        asset.rapid_degradation_alert = is_rapid
        asset.last_rul_predicted_at = now
        asset.save(update_fields=[
            'current_rul_days', 'current_rul_calendar_days',
            'rul_confidence_lower', 'rul_confidence_upper',
            'rul_risk_level', 'is_phantom_recovery',
            'rapid_degradation_alert', 'last_rul_predicted_at', 'updated_at'
        ])

        # -------------------------------------------------------------
        # Bước 12: Quy Tắc 8 - Phát thông báo hợp nhất (Alert Consolidation)
        # -------------------------------------------------------------
        if risk_level == 'CRITICAL' or is_rapid:
            cls._dispatch_predictive_alert(asset, final_rul_op, uncertainty_info, created_wo, is_rapid, spare_part)

        # Khuyến nghị hành động
        rec_action = cls._build_recommended_action(
            asset, final_rul_op, cal_days, spare_part, lead_time, crit_threshold, is_stock_sufficient, is_phantom, is_rapid
        )

        return {
            "success": True,
            "data": {
                "assetId": str(asset.id),
                "assetName": asset.name,
                "currentStatus": asset.status,
                "operatingRulDays": final_rul_op,
                "calendarRulDays": cal_days,
                "dutyCycleRatio": asset.duty_cycle_ratio,
                "confidenceInterval": {
                    "lower": uncertainty_info['confidence_lower'],
                    "upper": uncertainty_info['confidence_upper'],
                    "stdDeviation": uncertainty_info['rul_std'],
                    "isHighUncertainty": uncertainty_info['is_high_uncertainty']
                },
                "riskLevel": risk_level,
                "isPhantomRecovery": is_phantom,
                "rapidDegradationRate": rapid_rate,
                "rapidDegradationAlert": is_rapid,
                "lastEvaluatedAt": now.isoformat(),
                "loadConditionSummary": {
                    "averageLoadFactor": round(avg_load, 2),
                    "isOverloaded": (avg_load > 1.2)
                },
                "sparePartStatus": {
                    "partId": str(spare_part.id) if spare_part else None,
                    "partName": spare_part.name if spare_part else None,
                    "availableQuantity": stock_qty,
                    "leadTimeDays": lead_time,
                    "dynamicCriticalThreshold": crit_threshold,
                    "isStockSufficient": is_stock_sufficient
                },
                "actionTaken": action_taken,
                "draftWorkOrderId": str(created_wo.id) if created_wo else None,
                "draftWorkOrderCode": created_wo.code if created_wo else None,
                "recommendedAction": rec_action,
                "predictionRecordId": str(prediction_record.id)
            }
        }

    @staticmethod
    def _dispatch_predictive_alert(asset, rul_op, uncertainty, work_order, is_rapid, spare_part):
        """Bắn thông báo cảnh báo đón đầu tới Quản đốc bảo trì qua Notification Hub."""
        try:
            managers = NotificationRouter.get_maintenance_managers(asset.tenant_id)
            if not managers:
                return

            severity = 'URGENT' if is_rapid else 'CRITICAL'
            alert_prefix = "[BÁO ĐỘNG GIA TỐC NỨT VỠ]" if is_rapid else "[CẢNH BÁO BẢO TRÌ DỰ ĐOÁN]"
            title = f"{alert_prefix} {asset.name} - RUL còn {rul_op} ngày vận hành"
            
            message = (
                f"Mô hình LSTM dự báo RUL thiết bị '{asset.name}' chỉ còn {rul_op} ngày "
                f"(Khoảng tin cậy 90%: {uncertainty['confidence_lower']} - {uncertainty['confidence_upper']} ngày)."
            )
            if work_order:
                message += f" Đã tự động tạo bản thảo phiếu {work_order.code}."

            link = f"/portal/work-orders/?wo_id={work_order.id}" if work_order else f"/portal/assets/{asset.id}/"

            dispatch_event_notification(
                event_type='RUL_CRITICAL_ALERT',
                tenant=asset.tenant,
                entity_type='WorkOrder' if work_order else 'Asset',
                entity_id=str(work_order.id if work_order else asset.id),
                recipients=managers,
                title=title,
                message=message,
                link=link,
                category='WORK_ORDER' if work_order else 'ASSET',
                severity=severity,
                is_actionable=True,
                sla_minutes=60 if is_rapid else 180
            )
        except Exception as e:
            logger.warning(f"Failed to dispatch predictive alert notification: {e}")

    @staticmethod
    def _build_recommended_action(
        asset, rul_op, cal_days, spare_part, lead_time, crit_threshold, is_stock_sufficient, is_phantom, is_rapid
    ) -> str:
        if is_phantom:
            return (
                f"CẢNH BÁO HỒI PHỤC ẢO: Chỉ số rung/nhiệt giảm tạm thời sau bảo dưỡng nhỏ (bôi trơn/siết ốc). "
                f"Hệ thống khóa giữ nguyên RUL = {rul_op} ngày để phòng ngừa vỡ vòng bi."
            )
        if is_rapid:
            return (
                f"BÁO ĐỘNG GIA TỐC: RUL sụt giảm đột biến do nứt rỗ ổ trục. "
                f"Dừng máy kiểm tra khẩn cấp và chuẩn bị thay thế phụ tùng trong vòng 48h."
            )
        if rul_op <= crit_threshold:
            part_str = f"Thời gian đặt hàng vật tư là {lead_time} ngày. "
            stock_str = "Kho còn hàng khả dụng." if is_stock_sufficient else "Kho HẾT HÀNG, cần đặt mua khẩn cấp."
            return (
                f"{part_str}RUL còn {rul_op} ngày vận hành (~{cal_days} ngày lịch), đã chạm ngưỡng nguy cấp động ({crit_threshold} ngày). "
                f"{stock_str} Lên lịch dừng máy bảo dưỡng đón đầu."
            )
        if rul_op <= 60.0:
            return f"Thiết bị ở mức nguy cơ trung bình (RUL {rul_op} ngày). Tiếp tục tuần tra định kỳ và theo dõi xu hướng rung."
        return f"Thiết bị hoạt động ổn định (RUL {rul_op} ngày vận hành). Chưa cần can thiệp bảo trì."

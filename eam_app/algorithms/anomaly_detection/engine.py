from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from django.utils import timezone
from django.db import transaction

from assets.models import Asset, MeterReading, AssetAnomalyAlert
from workorders.models import WorkOrder
from notifications.services import notify_sensor_anomaly

from .physical_bounds import validate_physical_bounds, is_static_asset, get_static_asset_checklist
from .iso_standards import evaluate_iso_10816
from .z_score_detector import detect_z_score_anomaly
from .theil_sen_drift import evaluate_trend_drift
from .isolation_forest_detector import MultivariateIsolationForestDetector


class ConditionMonitoringEngine:
    """
    Condition Monitoring & Inspection Anomaly Engine.
    Tích hợp toàn diện 10 quy tắc nghiệp vụ phòng thủ:
    - Quy Tắc 1: Lọc trạng thái WARM_UP / IDLE
    - Quy Tắc 2: Tái lập cửa sổ trượt sau sửa chữa
    - Quy Tắc 3: Theil-Sen hồi quy mạnh mẽ chống ngoại lai
    - Quy Tắc 4: Chuẩn hóa Delta T theo nhiệt độ môi trường
    - Quy Tắc 5: Giảm âm cảnh báo & chống trùng lặp Draft PM
    - Quy Tắc 6: Nhận diện cảm biến bị đóng băng (Frozen Sensor)
    - Quy Tắc 7: Hồi quy theo mốc ngày thực tế (Elapsed Days)
    - Quy Tắc 8: Vòng lặp phản hồi của con người (Human Feedback)
    - Quy Tắc 9: Đối chiếu chuẩn rung ISO 10816-3
    - Quy Tắc 10: Giới hạn vật lý khả thi & phân luồng tài sản tĩnh
    """

    @classmethod
    @transaction.atomic
    def process_readings(
        cls,
        asset: Asset,
        readings_data: List[Dict[str, Any]],
        machine_state: str = 'RUNNING',
        ambient_temperature: Optional[float] = None,
        recorded_at: Optional[datetime] = None,
        recorded_by = None,
        tenant = None,
        work_order = None
    ) -> Dict[str, Any]:
        rec_time = recorded_at or timezone.now()
        cur_tenant = tenant or getattr(asset, 'tenant', None)
        norm_machine_state = str(machine_state or 'RUNNING').upper().strip()

        # Bước 1: Kiểm tra giới hạn vật lý (Sanity Bounds Check - Quy Tắc 10 & TC-ANOM-09)
        for item in readings_data:
            metric = item.get('metricCode') or item.get('metric_code') or 'VIBRATION'
            val = item.get('value')
            if val is None:
                val = item.get('readingValue') or item.get('reading_value')
            validate_physical_bounds(metric, val)

        # Bước 2: Phân luồng tài sản tĩnh (Quy Tắc 10 & TC-ANOM-10)
        if is_static_asset(asset):
            # Lưu các chỉ số (nếu có) nhưng không chạy AI rung nhiệt
            saved_records = []
            for item in readings_data:
                metric = item.get('metricCode') or item.get('metric_code') or 'GENERAL'
                val = item.get('value', item.get('readingValue', 0.0))
                unit = item.get('unit', '')
                remarks = item.get('remarks', '')
                rec = MeterReading.objects.create(
                    tenant=cur_tenant,
                    asset=asset,
                    work_order=work_order,
                    metric_code=metric,
                    reading_value=val,
                    reading_date=rec_time,
                    unit=unit,
                    ambient_temperature=ambient_temperature,
                    machine_state=norm_machine_state,
                    recorded_by=recorded_by,
                    remarks=remarks
                )
                saved_records.append(rec)

            checklist_data = get_static_asset_checklist(asset)
            return {
                "savedReadingsCount": len(saved_records),
                "isStaticAsset": True,
                "analysisSummary": checklist_data,
                "workOrderId": str(work_order.id) if work_order else None
            }

        # Bước 3: Lưu các bản ghi MeterReading vào cơ sở dữ liệu
        saved_records = []
        for item in readings_data:
            metric = str(item.get('metricCode') or item.get('metric_code') or 'VIBRATION').upper().strip()
            val = float(item.get('value', item.get('readingValue', 0.0)))
            unit = item.get('unit', '')
            remarks = item.get('remarks', '')
            rec = MeterReading.objects.create(
                tenant=cur_tenant,
                asset=asset,
                work_order=work_order,
                metric_code=metric,
                reading_value=val,
                reading_date=rec_time,
                unit=unit,
                ambient_temperature=ambient_temperature,
                machine_state=norm_machine_state,
                recorded_by=recorded_by,
                remarks=remarks
            )
            saved_records.append(rec)

        # Bước 4: Lọc ngữ cảnh trạng thái máy (Quy Tắc 1 & TC-ANOM-01)
        # Nếu máy ở trạng thái WARM_UP hoặc IDLE: Bỏ qua toàn bộ AI, không sinh cảnh báo
        if norm_machine_state != 'RUNNING':
            return {
                "savedReadingsCount": len(saved_records),
                "isStaticAsset": False,
                "analysisSummary": {
                    "machineState": norm_machine_state,
                    "hasAnomaly": False,
                    "highestSeverity": "NORMAL",
                    "message": f"Dữ liệu được lưu thành công. Không kích hoạt phân tích AI do máy đang ở trạng thái {norm_machine_state}."
                }
            }

        # Bước 5: Tiến hành phân tích AI Condition Monitoring trên các mẫu đo
        analysis_summary = cls._run_ai_analysis(
            asset=asset,
            saved_records=saved_records,
            cur_tenant=cur_tenant,
            ambient_temperature=ambient_temperature,
            rec_time=rec_time,
            work_order=work_order,
            recorded_by=recorded_by
        )

        return {
            "savedReadingsCount": len(saved_records),
            "isStaticAsset": False,
            "analysisSummary": analysis_summary
        }

    @classmethod
    def _run_ai_analysis(
        cls,
        asset: Asset,
        saved_records: List[MeterReading],
        cur_tenant,
        ambient_temperature: Optional[float],
        rec_time: datetime,
        work_order = None,
        recorded_by = None
    ) -> Dict[str, Any]:
        has_anomaly = False
        highest_severity = 'NORMAL'
        z_score_alert_info = None
        iso_status_info = None
        trend_drift_info = None
        created_or_updated_alert = None
        draft_pm_action = None

        # Đánh giá từng chỉ số đơn lẻ
        for rec in saved_records:
            metric = rec.metric_code
            val = float(rec.reading_value)

            # Lấy lịch sử đo hợp lệ (chỉ lấy RUNNING, không pre_repair, không suppressed)
            historical_readings = list(
                MeterReading.objects.filter(
                    asset=asset,
                    metric_code=metric,
                    machine_state='RUNNING',
                    is_pre_repair=False,
                    is_suppressed=False,
                    reading_date__lt=rec_time
                ).order_by('reading_date')
            )

            # 1. Sliding Z-Score & Frozen Sensor (Cấp độ 1, Quy Tắc 2, Quy Tắc 6)
            z_res = detect_z_score_anomaly(
                historical_readings=historical_readings,
                current_reading_value=val,
                current_machine_state=rec.machine_state,
                metric_code=metric
            )

            if z_res.get('has_anomaly'):
                has_anomaly = True
                if z_res.get('severity') == 'CRITICAL' or highest_severity != 'CRITICAL':
                    highest_severity = z_res.get('severity', 'WARNING')
                z_score_alert_info = {
                    "metric": metric,
                    "zScore": z_res.get('z_score'),
                    "status": z_res.get('status'),
                    "message": z_res.get('message')
                }

            # 2. ISO 10816-3 (Quy Tắc 9, TC-ANOM-11)
            if metric == 'VIBRATION':
                iso_status_info = evaluate_iso_10816('VIBRATION', val)
                if iso_status_info and iso_status_info.get('severity') == 'CRITICAL':
                    has_anomaly = True
                    highest_severity = 'CRITICAL'
                elif iso_status_info and iso_status_info.get('severity') == 'WARNING' and highest_severity == 'NORMAL':
                    has_anomaly = True
                    highest_severity = 'WARNING'

            # 3. Theil-Sen Robust Drift (Cấp độ 3, Quy Tắc 3, Quy Tắc 7, TC-ANOM-03, TC-ANOM-07)
            # Thu thập timestamp và giá trị cho hồi quy
            all_for_trend = historical_readings + [rec]
            if len(all_for_trend) >= 5:
                t_list = [r.reading_date for r in all_for_trend]
                v_list = [float(r.reading_value) for r in all_for_trend]
                limit_v = 7.1 if metric == 'VIBRATION' else (90.0 if metric == 'TEMPERATURE' else 25.0)
                
                drift_res = evaluate_trend_drift(
                    timestamps=t_list,
                    values=v_list,
                    limit_value=limit_v,
                    current_time=rec_time
                )
                if drift_res.get('isDrifting'):
                    trend_drift_info = drift_res
                    if drift_res.get('shouldTriggerDraftPM'):
                        has_anomaly = True
                        if highest_severity == 'NORMAL':
                            highest_severity = 'WARNING'

        # 4. Multivariate Isolation Forest (Cấp độ 2, Quy Tắc 4, TC-ANOM-04)
        multi_detector = MultivariateIsolationForestDetector()
        vib_val = 2.0
        temp_val = 65.0
        press_val = 2.5
        curr_val = 15.0

        for r in saved_records:
            if r.metric_code == 'VIBRATION':
                vib_val = float(r.reading_value)
            elif r.metric_code == 'TEMPERATURE':
                temp_val = float(r.reading_value)
            elif r.metric_code == 'PRESSURE':
                press_val = float(r.reading_value)
            elif r.metric_code == 'CURRENT':
                curr_val = float(r.reading_value)

        current_vec = multi_detector.build_vector(
            vibration=vib_val,
            temperature=temp_val,
            ambient_temperature=ambient_temperature,
            pressure=press_val,
            current=curr_val
        )
        multi_res = multi_detector.evaluate(current_vec)
        if multi_res.get('has_anomaly'):
            has_anomaly = True
            if multi_res.get('severity') == 'CRITICAL' or highest_severity != 'CRITICAL':
                highest_severity = multi_res.get('severity', 'WARNING')

        # 5. Alert Throttling & De-duplication (Quy Tắc 5, TC-ANOM-05, TC-ANOM-12)
        if has_anomaly:
            existing_open_alert = AssetAnomalyAlert.objects.filter(
                asset=asset,
                status='OPEN'
            ).order_by('-last_detected_at').first()

            # Kiểm tra xem có Draft Work Order nào đang tồn tại chưa hoàn thành
            existing_draft_wo = None
            if existing_open_alert and existing_open_alert.draft_work_order:
                if existing_open_alert.draft_work_order.status not in ('COMPLETED', 'CANCELLED'):
                    existing_draft_wo = existing_open_alert.draft_work_order
            else:
                existing_draft_wo = WorkOrder.objects.filter(
                    asset=asset,
                    type='PREVENTIVE',
                    status='CREATED'
                ).first()

            primary_rec = saved_records[0]
            primary_metric = primary_rec.metric_code
            primary_val = float(primary_rec.reading_value)

            if existing_open_alert or existing_draft_wo:
                # Đã có cảnh báo mở hoặc Draft PM: Chỉ tăng occurrence_count, KHÔNG tạo Draft PM mới!
                target_alert = existing_open_alert
                if not target_alert:
                    # Tạo alert gắn với existing_draft_wo
                    target_alert = AssetAnomalyAlert.objects.create(
                        tenant=cur_tenant,
                        asset=asset,
                        reading=primary_rec,
                        metric_type='SINGLE_METRIC',
                        metric_code=primary_metric,
                        current_value=primary_val,
                        severity=highest_severity,
                        status='OPEN',
                        occurrence_count=1,
                        draft_work_order=existing_draft_wo
                    )
                else:
                    target_alert.occurrence_count += 1
                    target_alert.current_value = primary_val
                    target_alert.severity = highest_severity
                    target_alert.last_detected_at = timezone.now()
                    target_alert.save()

                draft_pm_action = "UPDATED_EXISTING_DRAFT"
                created_or_updated_alert = target_alert

            else:
                # Chưa có cảnh báo: Tạo mới AssetAnomalyAlert
                z_val = z_score_alert_info.get('zScore') if z_score_alert_info else None
                anom_score = multi_res.get('anomaly_score')
                slope = trend_drift_info.get('slopePerDay') if trend_drift_info else None
                days_rem = trend_drift_info.get('daysRemaining') if trend_drift_info else None
                pred_date = trend_drift_info.get('predictedFailureDate') if trend_drift_info else None

                new_alert = AssetAnomalyAlert.objects.create(
                    tenant=cur_tenant,
                    asset=asset,
                    reading=primary_rec,
                    metric_type='SINGLE_METRIC',
                    metric_code=primary_metric,
                    current_value=primary_val,
                    z_score=z_val,
                    anomaly_score=anom_score,
                    trend_slope=slope,
                    predicted_failure_date=pred_date,
                    days_remaining=days_rem,
                    severity=highest_severity,
                    status='OPEN',
                    occurrence_count=1,
                    message=z_score_alert_info.get('message') if z_score_alert_info else (multi_res.get('message') if multi_res.get('has_anomaly') else None)
                )

                created_or_updated_alert = new_alert

                # === CƠ CHẾ ĐIỀU PHỐI PHÂN CẤP HYBRID (CRITICAL vs WARNING) ===
                if highest_severity == 'CRITICAL':
                    # 1. TRƯỜNG HỢP NẶNG (Sự cố Đỏ / CRITICAL / ISO Zone D / Z-Score >= 3.0):
                    # Tự động tạo Work Order khẩn cấp (CORRECTIVE/URGENT) và điều phối tức thời qua Hungarian
                    crit_deadline = timezone.now() + timedelta(hours=4)
                    critical_wo = WorkOrder.objects.create(
                        tenant=cur_tenant,
                        asset=asset,
                        parent_id=work_order,
                        title=f"Sự cố khẩn cấp: {asset.name} ({primary_metric} vượt ngưỡng)",
                        description=(
                            f"Tự động tạo bởi AI Condition Monitoring khi phát hiện chỉ số {primary_metric} "
                            f"({primary_val} {primary_rec.unit or ''}) chạm ngưỡng nguy hiểm CRITICAL.\n"
                            f"Chi tiết: {new_alert.message or 'Vượt ngưỡng an toàn OEM / ISO 10816 Zone D.'}"
                        ),
                        type='CORRECTIVE',
                        priority='URGENT',
                        status='CREATED',
                        deadline=crit_deadline,
                        required_skill='Cơ khí' if primary_metric == 'VIBRATION' else ('Điện' if primary_metric in ('CURRENT', 'VOLTAGE') else None),
                        min_skill_level=2,
                        coords_x=getattr(asset, 'coords_x', None),
                        coords_y=getattr(asset, 'coords_y', None),
                        floor_level=getattr(asset, 'floor_level', 1) or 1,
                        zone_id=getattr(asset, 'zone_id', '') or ''
                    )
                    new_alert.draft_work_order = critical_wo
                    new_alert.save(update_fields=['draft_work_order'])
                    draft_pm_action = "CREATED_CRITICAL_WO"

                    # Điều phối tức thời bằng giải thuật Hungarian (Auto-dispatch)
                    assigned_tech_name = None
                    try:
                        from algorithms.hungarian.service import HungarianAssignmentService
                        preview = HungarianAssignmentService.preview(tenant=cur_tenant, work_order_ids=[str(critical_wo.id)])
                        assignments = preview.get('assignments', [])
                        if assignments:
                            top_assignment = assignments[0]
                            tech_id = top_assignment['technicianId']
                            assigned_tech_name = top_assignment.get('technicianName')
                            HungarianAssignmentService.apply(
                                tenant=cur_tenant,
                                assignments_data=[{
                                    'workOrderId': str(critical_wo.id),
                                    'technicianId': str(tech_id),
                                    'slotRole': 'SOLO'
                                }],
                                current_user=recorded_by
                            )
                            critical_wo.refresh_from_db()
                            draft_pm_action = "CREATED_AND_DISPATCHED_CRITICAL_WO"
                        else:
                            critical_wo.description = (critical_wo.description or '') + "\n\n[Tự động điều phối Hungarian]: Không có kỹ thuật viên khả dụng đang trực trong ca. Chờ Quản đốc phân công khẩn cấp."
                            critical_wo.save(update_fields=['description'])
                    except Exception as e:
                        critical_wo.description = (critical_wo.description or '') + f"\n\n[Tự động điều phối Hungarian]: Lỗi giải thuật: {str(e)}"
                        critical_wo.save(update_fields=['description'])

                    # Bắn thông báo CRITICAL tới Quản lý bảo trì
                    try:
                        notify_sensor_anomaly(
                            asset=asset,
                            anomaly_type=f"{primary_metric} (CRITICAL)",
                            metric_value=f"{primary_val} {primary_rec.unit or ''}",
                            threshold_value="Ngưỡng nguy hiểm OEM / ISO 10816 Zone D",
                            severity='CRITICAL',
                            work_order=critical_wo
                        )
                    except Exception:
                        pass

                elif (days_rem is not None and days_rem <= 7) or highest_severity == 'WARNING':
                    # 2. TRƯỜNG HỢP NHẸ (Cảnh báo sớm / WARNING / Trend Drift / ISO Zone C):
                    # Tự động tạo Bản thảo PM Work Order + Chạy Hungarian ở chế độ PREVIEW gợi ý thợ + Gửi thông báo
                    draft_deadline = timezone.now() + timedelta(days=days_rem if days_rem is not None else 7)
                    draft_wo = WorkOrder.objects.create(
                        tenant=cur_tenant,
                        asset=asset,
                        parent_id=work_order,
                        title=f"Bản thảo PM: Dự phòng sự cố {asset.name} ({primary_metric})",
                        description=(
                            f"Tự động tạo bởi AI Condition Monitoring. "
                            f"{f'Tốc độ suy thoái: {slope}/ngày. Dự kiến sự cố sau {days_rem} ngày.' if slope else 'Phát hiện bất thường cảnh báo sớm.'}"
                        ),
                        type='PREVENTIVE',
                        priority='HIGH',
                        status='CREATED',
                        deadline=draft_deadline,
                        required_skill='Cơ khí' if primary_metric == 'VIBRATION' else ('Điện' if primary_metric in ('CURRENT', 'VOLTAGE') else None),
                        min_skill_level=1,
                        coords_x=getattr(asset, 'coords_x', None),
                        coords_y=getattr(asset, 'coords_y', None),
                        floor_level=getattr(asset, 'floor_level', 1) or 1,
                        zone_id=getattr(asset, 'zone_id', '') or ''
                    )
                    new_alert.draft_work_order = draft_wo
                    new_alert.save(update_fields=['draft_work_order'])
                    draft_pm_action = "CREATED_NEW_DRAFT"

                    # Chạy Hungarian PREVIEW để gợi ý kỹ thuật viên tối ưu
                    suggested_tech_name = None
                    try:
                        from algorithms.hungarian.service import HungarianAssignmentService
                        preview = HungarianAssignmentService.preview(tenant=cur_tenant, work_order_ids=[str(draft_wo.id)])
                        assignments = preview.get('assignments', [])
                        if assignments:
                            top_assignment = assignments[0]
                            suggested_tech_name = top_assignment.get('technicianName')
                            cost = top_assignment.get('cost')
                            draft_wo.description = (draft_wo.description or '') + f"\n\n[Gợi ý Hungarian]: Đề xuất phân công cho thợ {suggested_tech_name} (Chi phí tối ưu: {cost}). Quản đốc có thể phê duyệt 1-click."
                            draft_wo.save(update_fields=['description'])
                    except Exception:
                        pass

                    # Bắn thông báo WARNING tới Quản lý bảo trì
                    try:
                        notify_sensor_anomaly(
                            asset=asset,
                            anomaly_type=f"{primary_metric} (WARNING)",
                            metric_value=f"{primary_val} {primary_rec.unit or ''}",
                            threshold_value="Ngưỡng cảnh báo OEM / ISO 10816 Zone C",
                            severity='WARNING',
                            work_order=draft_wo,
                            suggested_technician=suggested_tech_name
                        )
                    except Exception:
                        pass

        # Gắn draftWorkOrderAction vào trend_drift_info nếu có
        if trend_drift_info:
            trend_drift_info["draftWorkOrderAction"] = draft_pm_action or "NONE"

        assigned_tech_display = None
        if created_or_updated_alert and created_or_updated_alert.draft_work_order:
            wo = created_or_updated_alert.draft_work_order
            if wo.assigned_to:
                assigned_tech_display = wo.assigned_to.get_full_name() or wo.assigned_to.username

        return {
            "machineState": saved_records[0].machine_state if saved_records else "RUNNING",
            "hasAnomaly": has_anomaly,
            "highestSeverity": highest_severity,
            "zScoreAlert": z_score_alert_info,
            "iso10816Status": iso_status_info,
            "trendDrift": trend_drift_info,
            "multivariateStatus": multi_res if multi_res.get('has_anomaly') else None,
            "alertId": str(created_or_updated_alert.id) if created_or_updated_alert else None,
            "alertMessage": created_or_updated_alert.message if created_or_updated_alert else None,
            "occurrenceCount": created_or_updated_alert.occurrence_count if created_or_updated_alert else 0,
            "draftWorkOrderAction": draft_pm_action,
            "draftWorkOrderId": str(created_or_updated_alert.draft_work_order.id) if (created_or_updated_alert and created_or_updated_alert.draft_work_order) else None,
            "draftWorkOrderCode": created_or_updated_alert.draft_work_order.code if (created_or_updated_alert and created_or_updated_alert.draft_work_order) else None,
            "draftWorkOrderStatus": created_or_updated_alert.draft_work_order.status if (created_or_updated_alert and created_or_updated_alert.draft_work_order) else None,
            "assignedTechnicianName": assigned_tech_display,
            "workOrderId": str(work_order.id) if work_order else None
        }

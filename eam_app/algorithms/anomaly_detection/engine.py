from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from django.utils import timezone
from django.db import transaction

from assets.models import Asset, MeterReading, AssetAnomalyAlert
from workorders.models import WorkOrder
from notifications.services import notify_sensor_anomaly

from .physical_bounds import validate_physical_bounds, is_static_asset, get_static_asset_checklist
from .iso_standards import evaluate_iso_10816
from .z_score_detector import detect_z_score_anomaly, OEM_STATIC_LIMITS
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
        work_order = None,
        round_id = None,
        checklist_item = None,
        measurement_phase = 'ROUTINE',
        load_factor = None,
        motor_current_amp = None,
        shaft_rpm = None
    ) -> Dict[str, Any]:
        import uuid
        rec_time = recorded_at or timezone.now()
        cur_tenant = tenant or getattr(asset, 'tenant', None)
        norm_machine_state = str(machine_state or 'RUNNING').upper().strip()
        cur_round_id = round_id or uuid.uuid4()

        # Bước 1: Kiểm tra giới hạn vật lý (Sanity Bounds Check - Quy Tắc 10 & TC-ANOM-09)
        for item in readings_data:
            metric = item.get('metricCode') or item.get('metric_code') or 'VIBRATION'
            val = item.get('value')
            if val is None:
                val = item.get('readingValue') or item.get('reading_value')
            validate_physical_bounds(metric, val)

        # Bước 2: Phân luồng tài sản tĩnh (Quy Tắc 10 & TC-ANOM-10)
        if is_static_asset(asset):
            # Lưu hoặc cập nhật các chỉ số (nếu có) nhưng không chạy AI rung nhiệt
            saved_records = []
            for item in readings_data:
                metric = item.get('metricCode') or item.get('metric_code') or 'GENERAL'
                val = item.get('value')
                if val is None:
                    val = item.get('readingValue')
                if val is None:
                    val = item.get('reading_value', 0.0)
                val = float(val) if val is not None else 0.0
                unit = item.get('unit', '')
                remarks = item.get('remarks', '')
                chk_item = item.get('checklistItem') or item.get('checklist_item') or checklist_item
                r_id = item.get('roundId') or item.get('round_id') or cur_round_id

                rec = None
                if chk_item:
                    rec = MeterReading.objects.filter(
                        checklist_item=chk_item,
                        metric_code=metric,
                        asset=asset,
                        tenant=cur_tenant
                    ).first()

                if rec:
                    rec.reading_value = val
                    rec.reading_date = rec_time
                    if unit: rec.unit = unit
                    if remarks: rec.remarks = remarks
                    rec.save()
                else:
                    rec = MeterReading.objects.create(
                        tenant=cur_tenant,
                        asset=asset,
                        work_order=work_order,
                        checklist_item=chk_item,
                        round_id=r_id,
                        measurement_phase='ROUTINE',
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

        # Bước 3: Lưu hoặc cập nhật các bản ghi MeterReading vào cơ sở dữ liệu
        saved_records = []
        for item in readings_data:
            metric = str(item.get('metricCode') or item.get('metric_code') or 'VIBRATION').upper().strip()
            val = item.get('value')
            if val is None:
                val = item.get('readingValue')
            if val is None:
                val = item.get('reading_value', 0.0)
            val = float(val) if val is not None else 0.0
            unit = item.get('unit', '')
            remarks = item.get('remarks', '')
            chk_item = item.get('checklistItem') or item.get('checklist_item') or checklist_item
            phase = item.get('measurementPhase') or item.get('measurement_phase') or measurement_phase or 'ROUTINE'
            lf = item.get('loadFactor') or item.get('load_factor') or load_factor or 1.0
            cur_amp = item.get('motorCurrentAmp') or item.get('motor_current_amp') or motor_current_amp
            rpm_val = item.get('shaftRpm') or item.get('shaft_rpm') or shaft_rpm
            r_id = item.get('roundId') or item.get('round_id') or cur_round_id

            rec = None
            if chk_item:
                rec = MeterReading.objects.filter(
                    checklist_item=chk_item,
                    metric_code=metric,
                    asset=asset,
                    tenant=cur_tenant
                ).first()

            if rec:
                rec.reading_value = val
                rec.reading_date = rec_time
                if unit: rec.unit = unit
                if ambient_temperature is not None: rec.ambient_temperature = ambient_temperature
                if lf is not None: rec.load_factor = float(lf)
                if cur_amp is not None: rec.motor_current_amp = float(cur_amp)
                if rpm_val is not None: rec.shaft_rpm = float(rpm_val)
                rec.machine_state = norm_machine_state
                rec.measurement_phase = phase
                rec.round_id = r_id
                if remarks: rec.remarks = remarks
                rec.save()
            else:
                rec = MeterReading.objects.create(
                    tenant=cur_tenant,
                    asset=asset,
                    work_order=work_order,
                    checklist_item=chk_item,
                    round_id=r_id,
                    measurement_phase=phase,
                    load_factor=float(lf) if lf is not None else 1.0,
                    motor_current_amp=float(cur_amp) if cur_amp is not None else None,
                    shaft_rpm=float(rpm_val) if rpm_val is not None else None,
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

        # Bước 5: Kiểm tra cờ bật/tắt AI Anomaly Detection của Tenant
        if cur_tenant and not getattr(cur_tenant, 'enable_ai_anomaly_detection', True):
            return {
                "savedReadingsCount": len(saved_records),
                "isStaticAsset": False,
                "analysisSummary": {
                    "hasAnomaly": False,
                    "highestSeverity": "NORMAL",
                    "mode": "STANDARD_STATIC_ONLY",
                    "aiEnabled": False,
                    "message": "Thuật toán Phân tích Dị thường AI đang tắt theo cài đặt của tổ chức. Dữ liệu cảm biến được ghi nhận an toàn."
                }
            }

        # Tiến hành phân tích AI Condition Monitoring trên các mẫu đo
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
        anomalous_records = []
        for rec in saved_records:
            metric = rec.metric_code
            val = float(rec.reading_value)
            rec_has_anomaly = False
            rec_severity = 'NORMAL'

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
                rec_has_anomaly = True
                rec_severity = z_res.get('severity', 'WARNING')
                if rec_severity == 'CRITICAL' or highest_severity != 'CRITICAL':
                    highest_severity = rec_severity
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
                    rec_has_anomaly = True
                    rec_severity = 'CRITICAL'
                    highest_severity = 'CRITICAL'
                elif iso_status_info and iso_status_info.get('severity') == 'WARNING' and highest_severity == 'NORMAL':
                    has_anomaly = True
                    rec_has_anomaly = True
                    if rec_severity != 'CRITICAL':
                        rec_severity = 'WARNING'
                    highest_severity = 'WARNING'

            # 3. Theil-Sen Robust Drift (Cấp độ 3, Quy Tắc 3, Quy Tắc 7, TC-ANOM-03, TC-ANOM-07)
            # Thu thập timestamp và giá trị cho hồi quy
            all_for_trend = historical_readings + [rec]
            if len(all_for_trend) >= 5:
                t_list = [r.reading_date for r in all_for_trend]
                v_list = [float(r.reading_value) for r in all_for_trend]
                oem_entry = OEM_STATIC_LIMITS.get(metric)
                if oem_entry and 'critical' in oem_entry:
                    limit_v = float(oem_entry['critical'])
                elif metric == 'VIBRATION':
                    limit_v = 7.1
                elif metric == 'TEMPERATURE':
                    limit_v = 90.0
                else:
                    limit_v = 25.0
                
                drift_res = evaluate_trend_drift(
                    timestamps=t_list,
                    values=v_list,
                    limit_value=limit_v,
                    current_time=rec_time,
                    metric_code=metric
                )
                if drift_res.get('isDrifting'):
                    trend_drift_info = drift_res
                    if drift_res.get('shouldTriggerDraftPM'):
                        has_anomaly = True
                        rec_has_anomaly = True
                        if rec_severity != 'CRITICAL':
                            rec_severity = 'WARNING'
                        if highest_severity == 'NORMAL':
                            highest_severity = 'WARNING'

            if rec_has_anomaly:
                anomalous_records.append((rec, rec_severity))

        # 4. Multivariate Isolation Forest (Cấp độ 2, Quy Tắc 4, TC-ANOM-04, Audit #7)
        multi_detector = MultivariateIsolationForestDetector()
        channel_vals = {}
        for r in saved_records:
            channel_vals[r.metric_code] = float(r.reading_value)

        # Fallback to latest historical reading if channel not in current batch
        for ch, default_val in [('VIBRATION', 2.0), ('TEMPERATURE', 65.0), ('PRESSURE', 2.5), ('CURRENT', 15.0)]:
            if ch not in channel_vals:
                hist_ch = MeterReading.objects.filter(
                    tenant=cur_tenant,
                    asset=asset,
                    metric_code=ch,
                    machine_state='RUNNING',
                    is_pre_repair=False,
                    is_suppressed=False,
                    reading_date__lt=rec_time
                ).order_by('-reading_date').first()
                if hist_ch and hist_ch.reading_value is not None:
                    channel_vals[ch] = float(hist_ch.reading_value)
                else:
                    channel_vals[ch] = default_val

        # Huấn luyện Isolation Forest bằng dữ liệu vector đa biến thực tế nếu có
        hist_records = list(
            MeterReading.objects.filter(
                tenant=cur_tenant,
                asset=asset,
                machine_state='RUNNING',
                is_pre_repair=False,
                is_suppressed=False,
                reading_date__lt=rec_time
            ).order_by('-reading_date')[:120]
        )
        hist_by_round = {}
        for hr in hist_records:
            rk = hr.round_id or hr.reading_date.strftime('%Y-%m-%d %H')
            if rk not in hist_by_round:
                hist_by_round[rk] = {}
            hist_by_round[rk][hr.metric_code] = float(hr.reading_value)

        historical_vectors = []
        for rk, vals in hist_by_round.items():
            if 'VIBRATION' in vals and 'TEMPERATURE' in vals:
                h_v = vals.get('VIBRATION', 2.0)
                h_t = vals.get('TEMPERATURE', 65.0)
                h_p = vals.get('PRESSURE', channel_vals.get('PRESSURE', 2.5))
                h_c = vals.get('CURRENT', channel_vals.get('CURRENT', 15.0))
                historical_vectors.append(multi_detector.build_vector(
                    vibration=h_v,
                    temperature=h_t,
                    ambient_temperature=ambient_temperature,
                    pressure=h_p,
                    current=h_c
                ))

        if len(historical_vectors) >= 5:
            multi_detector.train_or_fit(historical_vectors)

        current_vec = multi_detector.build_vector(
            vibration=channel_vals['VIBRATION'],
            temperature=channel_vals['TEMPERATURE'],
            ambient_temperature=ambient_temperature,
            pressure=channel_vals['PRESSURE'],
            current=channel_vals['CURRENT']
        )
        multi_res = multi_detector.evaluate(current_vec)
        if multi_res.get('has_anomaly'):
            has_anomaly = True
            if multi_res.get('severity') == 'CRITICAL' or highest_severity != 'CRITICAL':
                highest_severity = multi_res.get('severity', 'WARNING')

        # 5. Alert Throttling & De-duplication (Quy Tắc 5, TC-ANOM-05, TC-ANOM-12)
        if has_anomaly:
            # Audit #9: Attribute alert to the actual failing metric, or MULTIVARIATE
            crit_recs = [r for r, s in anomalous_records if s == 'CRITICAL']
            if crit_recs:
                primary_rec = crit_recs[0]
            elif anomalous_records:
                primary_rec = anomalous_records[0][0]
            else:
                primary_rec = saved_records[0]

            is_multivariate_only = multi_res.get('has_anomaly') and not anomalous_records
            primary_metric = 'MULTIVARIATE' if is_multivariate_only else primary_rec.metric_code
            metric_type = 'MULTIVARIATE' if is_multivariate_only else 'SINGLE_METRIC'
            primary_val = float(primary_rec.reading_value)

            # Khóa dòng và lọc chính xác theo tenant, tài sản, chỉ số và trạng thái OPEN
            existing_open_alert = AssetAnomalyAlert.objects.select_for_update().filter(
                tenant=cur_tenant,
                asset=asset,
                metric_code=primary_metric,
                status='OPEN'
            ).order_by('-last_detected_at').first()

            # Kiểm tra xem có Draft Work Order nào đang tồn tại chưa hoàn thành gắn với alert hiện tại
            existing_draft_wo = None
            if existing_open_alert and existing_open_alert.draft_work_order:
                if existing_open_alert.draft_work_order.status not in ('COMPLETED', 'CANCELLED'):
                    existing_draft_wo = existing_open_alert.draft_work_order

            if existing_open_alert:
                # Đã có cảnh báo mở cho cùng chỉ số: Cập nhật thông số cảnh báo hiện tại
                target_alert = existing_open_alert
                target_alert.occurrence_count += 1
                target_alert.current_value = primary_val
                target_alert.reading = primary_rec
                if highest_severity == 'CRITICAL':
                    target_alert.severity = 'CRITICAL'
                if z_score_alert_info and z_score_alert_info.get('message'):
                    target_alert.message = z_score_alert_info.get('message')
                elif multi_res.get('has_anomaly') and multi_res.get('message'):
                    target_alert.message = multi_res.get('message')
                target_alert.last_detected_at = timezone.now()

                # Đồng bộ toàn diện các trường số liệu và dự phóng mới nhất (Audit #6)
                if z_score_alert_info and z_score_alert_info.get('zScore') is not None:
                    target_alert.z_score = z_score_alert_info.get('zScore')
                if multi_res and multi_res.get('anomaly_score') is not None:
                    target_alert.anomaly_score = multi_res.get('anomaly_score')
                if trend_drift_info:
                    if trend_drift_info.get('slopePerDay') is not None:
                        target_alert.trend_slope = trend_drift_info.get('slopePerDay')
                    if trend_drift_info.get('daysRemaining') is not None:
                        target_alert.days_remaining = trend_drift_info.get('daysRemaining')
                    if trend_drift_info.get('predictedFailureDate') is not None:
                        target_alert.predicted_failure_date = trend_drift_info.get('predictedFailureDate')

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
                    metric_type=metric_type,
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
            active_alert = created_or_updated_alert
            slope = trend_drift_info.get('slopePerDay') if trend_drift_info else None
            days_rem = trend_drift_info.get('daysRemaining') if trend_drift_info else None

            if highest_severity == 'CRITICAL':
                # 1. TRƯỜNG HỢP NẶNG (Sự cố Đỏ / CRITICAL / ISO Zone D / Z-Score >= 3.0):
                # Kiểm tra xem tài sản đã có Work Order khắc phục (CORRECTIVE) nào đang mở chưa (Audit #3)
                active_corrective_wo = WorkOrder.objects.filter(
                    tenant=cur_tenant,
                    asset=asset,
                    type='CORRECTIVE',
                    status__in=['CREATED', 'ASSIGNED', 'IN_PROGRESS', 'ON_HOLD', 'PENDING']
                ).order_by('-created_at').first()

                if active_corrective_wo:
                    # Đã có phiếu khắc phục đang mở: Không tạo thêm phiếu trùng lặp, liên kết alert với phiếu hiện có
                    needs_critical_wo = False
                    if not active_alert.draft_work_order:
                        active_alert.draft_work_order = active_corrective_wo
                        active_alert.save(update_fields=['draft_work_order'])
                else:
                    needs_critical_wo = not active_alert.draft_work_order or active_alert.draft_work_order.priority != 'URGENT'
                if needs_critical_wo:
                    crit_deadline = timezone.now() + timedelta(hours=4)

                    # Gợi ý dụng cụ hợp lệ từ kho của tenant
                    suggested_tools = []
                    try:
                        from assets.models import Tool
                        tool_codes_needed = ['VIB_METER', 'TORQUE_WRENCH'] if primary_metric == 'VIBRATION' else ['MULTIMETER']
                        valid_tools = Tool.objects.filter(
                            tenant=cur_tenant,
                            code__in=tool_codes_needed,
                            is_active=True,
                            available_quantity__gt=0
                        )
                        suggested_tools = list(valid_tools.values_list('code', flat=True))
                    except Exception:
                        suggested_tools = []

                    # Gợi ý phụ tùng vào required_spare_parts (dạng ID metadata tham khảo, TUYỆT ĐỐI KHÔNG tự tạo WorkOrderMaterial làm trừ kho)
                    suggested_parts = []
                    if getattr(asset, 'primary_spare_part_id', None):
                        suggested_parts.append(str(asset.primary_spare_part_id))

                    critical_wo = WorkOrder.objects.create(
                        tenant=cur_tenant,
                        asset=asset,
                        parent_id=work_order,
                        title=f"Sự cố khẩn cấp: {asset.name} - {primary_metric} vượt ngưỡng",
                        description=(
                            f"Tự động tạo bởi AI Condition Monitoring khi phát hiện chỉ số {primary_metric} "
                            f"({primary_val} {primary_rec.unit or ''}) chạm ngưỡng nguy hiểm CRITICAL.\n"
                            f"Chi tiết: {active_alert.message or 'Vượt ngưỡng an toàn OEM / ISO 10816 Zone D.'}"
                        ),
                        type='CORRECTIVE',
                        priority='URGENT',
                        status='CREATED',
                        deadline=crit_deadline,
                        required_skill='Cơ khí' if primary_metric == 'VIBRATION' else ('Điện' if primary_metric in ('CURRENT', 'VOLTAGE') else None),
                        min_skill_level=2,
                        required_tools=suggested_tools,
                        required_spare_parts=suggested_parts,
                        coords_x=getattr(asset, 'coords_x', None),
                        coords_y=getattr(asset, 'coords_y', None),
                        floor_level=getattr(asset, 'floor_level', 1) or 1,
                        zone_id=getattr(asset, 'zone_id', '') or ''
                    )
                    active_alert.draft_work_order = critical_wo
                    active_alert.save(update_fields=['draft_work_order'])
                    draft_pm_action = "CREATED_CRITICAL_WO"

                    # Điều phối tức thời bằng giải thuật Hungarian (Auto-dispatch)
                    try:
                        from algorithms.hungarian.service import HungarianAssignmentService
                        preview = HungarianAssignmentService.preview(tenant=cur_tenant, work_order_ids=[str(critical_wo.id)])
                        assignments = preview.get('assignments', [])
                        if assignments:
                            top_assignment = assignments[0]
                            tech_id = top_assignment['technicianId']
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
                        import logging
                        logging.getLogger(__name__).error(f"Hungarian dispatch error for WO {critical_wo.id}: {e}", exc_info=True)
                        critical_wo.description = (critical_wo.description or '') + "\n\n[Tự động điều phối Hungarian]: Chưa thể phân công tự động do xung đột ca trực hoặc lịch làm việc. Chờ Quản đốc phân công thủ công."
                        critical_wo.save(update_fields=['description'])

                    # Bắn thông báo CRITICAL tới Quản lý bảo trì
                    try:
                        notify_sensor_anomaly(
                            asset=asset,
                            anomaly_type=f"{primary_metric} - Khẩn cấp",
                            metric_value=f"{primary_val} {primary_rec.unit or ''}",
                            threshold_value="Ngưỡng nguy hiểm OEM / ISO 10816 Zone D",
                            severity='CRITICAL',
                            work_order=critical_wo
                        )
                    except Exception:
                        pass

            elif (days_rem is not None and days_rem <= 7) or highest_severity == 'WARNING':
                # 2. TRƯỜNG HỢP CẢNH BÁO SỚM / WARNING / HIGH (Trend Drift / ISO Zone C):
                # Không tự động tạo phiếu trong DB; AI tạo AssetAnomalyAlert và bắn thông báo tới Quản đốc
                # kèm đường dẫn điền sẵn toàn bộ thông tin để Quản đốc mở form và tạo phiếu trực tiếp.
                suggested_tech_name = None
                try:
                    from users.models import User
                    req_skill = 'Cơ khí' if primary_metric == 'VIBRATION' else ('Điện' if primary_metric in ('CURRENT', 'VOLTAGE') else None)
                    tech_qs = User.objects.filter(tenant=cur_tenant, is_active=True, status='ACTIVE')
                    if req_skill:
                        tech_qs = tech_qs.filter(skill_records__skill__name__icontains=req_skill)
                    tech_cand = tech_qs.first()
                    if tech_cand:
                        suggested_tech_name = tech_cand.get_full_name() or tech_cand.username
                except Exception:
                    pass

                draft_pm_action = "ALERT_LOGGED_AWAITING_MANAGER"

                # Nếu chưa có phiếu nào được tạo cho alert này, gửi notification kèm link pre-fill
                if not active_alert.draft_work_order:
                    try:
                        notify_sensor_anomaly(
                            asset=asset,
                            anomaly_type=f"{primary_metric} - Cảnh báo sớm",
                            metric_value=f"{primary_val} {primary_rec.unit or ''}",
                            threshold_value="Ngưỡng cảnh báo OEM / ISO 10816 Zone C",
                            severity='WARNING',
                            work_order=None,
                            suggested_technician=suggested_tech_name,
                            alert_id=active_alert.id if active_alert else None,
                            days_remaining=days_rem,
                            slope=slope
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

        # Phase 11.5: Tuyến Chiến Lược RUL (Kích hoạt liên hoàn 11.4 -> 11.5 & Alert Consolidation)
        rul_prediction_result = None
        cur_machine_state = saved_records[0].machine_state if saved_records else 'RUNNING'
        if cur_machine_state == 'RUNNING':
            try:
                from algorithms.predictive_rul import RULPredictiveService
                trigger_src = 'ANOMALY_TRIGGER_11_4' if has_anomaly else 'METER_LOG'
                rul_prediction_result = RULPredictiveService.predict_asset_rul(
                    asset=asset,
                    trigger_source=trigger_src,
                    current_user=recorded_by
                )
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"RUL auto-trigger error for asset {asset.id}: {e}")

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
            "workOrderId": str(work_order.id) if work_order else None,
            "rulPrediction": rul_prediction_result.get('data') if rul_prediction_result else None
        }

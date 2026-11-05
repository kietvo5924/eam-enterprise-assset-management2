import logging
import numpy as np
from datetime import timedelta
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from sklearn.tree import DecisionTreeClassifier

from .constants import (
    SEVERITY_NORMAL,
    SEVERITY_CRITICAL,
    ACTION_GENERAL,
    ACTION_MICRO,
    ACTION_CORE_REPLACEMENT,
    STAGE_DIAGNOSIS,
    STAGE_STAGING_PARTS,
    STAGE_OVERHAUL_EXECUTION,
    STAGE_TRIAL_ACCEPTANCE,
    RUL_CRITICAL_THRESHOLD_DAYS,
    Z_SCORE_CRITICAL_THRESHOLD,
    Z_SCORE_NORMAL_THRESHOLD,
    RUL_MARGIN_LOWER,
    RUL_MARGIN_UPPER,
    Z_SCORE_CRIT_MARGIN_LOWER,
    Z_SCORE_CRIT_MARGIN_UPPER,
    Z_SCORE_NORM_MARGIN_LOWER,
    Z_SCORE_NORM_MARGIN_UPPER,
    MAX_ACCEPTABLE_POST_REPAIR_VIBRATION,
    MAX_ACCEPTABLE_POST_REPAIR_TEMPERATURE,
)

logger = logging.getLogger(__name__)


class DecisionTreeChecklistEngine:
    """
    Task 11.8: Explainable Decision Tree Classifier & HSM Checklist Engine.
    Điều phối quy trình bảo trì chuyên sâu, tự động chuyển hóa cảnh báo dị biệt (11.4)
    và dự báo tuổi thọ cạn kiệt (11.5) thành Work Order có bộ Checklist 4 giai đoạn bắt buộc.
    """

    _classifier = None

    @classmethod
    def _init_classifier(cls):
        """
        Khởi tạo và huấn luyện cây quyết định max_depth=4 trên miền dữ liệu tri thức chuyên gia.
        Features vector: [z_score, rul_days, cost_ratio, recurrence_count]
        Class label: 0 -> NORMAL_MAINTENANCE, 1 -> CRITICAL_OVERHAUL
        """
        X = np.array([
            # [z_score, rul_days, cost_ratio, recurrence]
            # Nhánh 1: Bảo dưỡng thông thường (Z < 2.0, RUL > 30, chi phí thấp, ít hỏng lặp lại)
            [0.5, 90.0, 0.02, 0],
            [1.0, 60.0, 0.05, 1],
            [1.2, 45.0, 0.08, 0],
            [1.5, 50.0, 0.10, 1],
            [1.8, 35.0, 0.12, 1],
            [0.8, 80.0, 0.03, 0],
            [1.4, 40.0, 0.07, 2],
            [1.9, 32.0, 0.15, 1],
            
            # Nhánh 2: Đại tu cốt lõi (Z >= 2.5 hoặc RUL <= 15 hoặc chi phí/tần suất cao)
            [2.8, 6.0, 0.45, 3],
            [3.2, 12.0, 0.35, 2],
            [2.6, 25.0, 0.25, 2],
            [1.8, 8.0, 0.30, 2],
            [1.2, 10.0, 0.20, 1],
            [2.5, 14.0, 0.40, 3],
            [3.5, 4.0, 0.60, 4],
            [2.9, 15.0, 0.50, 3],
            [2.2, 13.0, 0.38, 3],
            [1.6, 12.0, 0.25, 2],
            [2.7, 50.0, 0.30, 1],
            [1.9, 28.0, 0.55, 4],
        ], dtype=float)

        y = np.array([
            0, 0, 0, 0, 0, 0, 0, 0,
            1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1
        ], dtype=int)

        clf = DecisionTreeClassifier(max_depth=4, criterion='gini', random_state=42)
        clf.fit(X, y)
        cls._classifier = clf
        return clf

    @classmethod
    def get_classifier(cls):
        if cls._classifier is None:
            cls._init_classifier()
        return cls._classifier

    @classmethod
    def check_marginal_boundary(cls, z_score: float, rul_days: float) -> bool:
        """
        Kiểm tra xem các chỉ số có nằm trong vùng đệm giáp ranh ±5% của ngưỡng quyết định hay không.
        - Ngưỡng RUL = 15.0 ngày -> [14.25, 15.75]
        - Ngưỡng Z-score = 2.50 -> [2.375, 2.625]
        - Ngưỡng Z-score = 2.00 -> [1.90, 2.10]
        """
        if rul_days is not None and (RUL_MARGIN_LOWER <= rul_days <= RUL_MARGIN_UPPER):
            return True
        if z_score is not None:
            if Z_SCORE_CRIT_MARGIN_LOWER <= z_score <= Z_SCORE_CRIT_MARGIN_UPPER:
                return True
            if Z_SCORE_NORM_MARGIN_LOWER <= z_score <= Z_SCORE_NORM_MARGIN_UPPER:
                return True
        return False

    @classmethod
    def generate_decision_explanation(
        cls,
        severity: str,
        z_score: float,
        rul_days: float,
        cost_ratio: float = 0.0,
        recurrence: int = 0,
        has_rapid_degradation: bool = False,
        marginal_warning: bool = False
    ) -> str:
        """
        Tạo lời giải thích IF-THEN minh bạch (Explainable AI) theo chuẩn đặc tả.
        """
        if severity == SEVERITY_CRITICAL:
            if has_rapid_degradation:
                msg = (
                    f"Cảnh báo gia tốc suy thoái đột biến (Rapid Degradation) "
                    f"➔ RUL còn lại ({rul_days:.1f} ngày) "
                    f"➔ Phân loại: ĐẠI TU BỔ MÁY BẮT BUỘC (CORE_REPLACEMENT)"
                )
            elif rul_days is not None and rul_days <= RUL_CRITICAL_THRESHOLD_DAYS and z_score is not None and z_score >= Z_SCORE_CRITICAL_THRESHOLD:
                msg = (
                    f"RUL còn lại ({rul_days:.1f} ngày) <= {RUL_CRITICAL_THRESHOLD_DAYS:.1f} ngày "
                    f"➔ Z-score rung chấn ({z_score:.2f}) >= {Z_SCORE_CRITICAL_THRESHOLD:.2f} "
                    f"➔ Phân loại: ĐẠI TU BỔ MÁY BẮT BUỘC (CORE_REPLACEMENT)"
                )
            elif rul_days is not None and rul_days <= RUL_CRITICAL_THRESHOLD_DAYS:
                msg = (
                    f"RUL còn lại ({rul_days:.1f} ngày) <= {RUL_CRITICAL_THRESHOLD_DAYS:.1f} ngày "
                    f"➔ Nguy cơ cạn kiệt tuổi thọ hữu ích máy móc "
                    f"➔ Phân loại: ĐẠI TU BỔ MÁY BẮT BUỘC (CORE_REPLACEMENT)"
                )
            elif z_score is not None and z_score >= Z_SCORE_CRITICAL_THRESHOLD:
                msg = (
                    f"Z-score rung chấn ({z_score:.2f}) >= {Z_SCORE_CRITICAL_THRESHOLD:.2f} (Vượt ngưỡng ISO 10816 Zone C/D) "
                    f"➔ Phân loại: ĐẠI TU BỔ MÁY BẮT BUỘC (CORE_REPLACEMENT)"
                )
            elif recurrence >= 3 or cost_ratio >= 0.4:
                msg = (
                    f"Tần suất hỏng hóc lặp lại ({recurrence} lần/90 ngày) "
                    f"➔ Tỷ lệ chi phí ước tính ({cost_ratio:.1%}) "
                    f"➔ Phân loại: ĐẠI TU BỔ MÁY BẮT BUỘC (CORE_REPLACEMENT)"
                )
            else:
                msg = (
                    f"Cây quyết định phân loại sự cố nguy cấp (max_depth=4) "
                    f"➔ Phân loại: ĐẠI TU BỔ MÁY BẮT BUỘC (CORE_REPLACEMENT)"
                )
        else:
            z_str = f"Z-score rung chấn ({z_score:.2f}) < {Z_SCORE_NORMAL_THRESHOLD:.2f}" if z_score is not None else "Chỉ số cảm biến ổn định"
            rul_str = f"RUL còn lại ({rul_days:.1f} ngày) > 30.0 ngày" if rul_days is not None else "Tuổi thọ RUL an toàn"
            msg = (
                f"{z_str} ➔ {rul_str} "
                f"➔ Phân loại: BẢO DƯỠNG THÔNG THƯỜNG (NORMAL_MAINTENANCE)"
            )

        if marginal_warning:
            msg += " | CẢNH BÁO VÙNG ĐỆM GIÁP RANH (±5%): Chỉ số tiệm cận ngưỡng chuyển đổi. Yêu cầu Quản đốc thẩm định kỹ phương án trước khi triển khai."
        return msg

    @classmethod
    def get_overhaul_checklist_templates(cls, asset=None) -> list:
        """
        Kho mẫu Checklist chuẩn 4 Giai đoạn bắt buộc cho các ca Đại tu bổ máy cốt lõi (CORE_REPLACEMENT).
        """
        part_name = "vòng bi SKF 6205"
        if asset and hasattr(asset, 'primary_spare_part') and asset.primary_spare_part:
            part_name = asset.primary_spare_part.name

        return [
            # Giai đoạn 1: Khảo sát & Đánh giá hiện trạng (Bắt buộc)
            {
                "stage": STAGE_DIAGNOSIS,
                "itemName": "Khảo sát độ rơ trục & xác nhận phương án bổ máy",
                "inputType": "PASS_FAIL",
                "expectedValue": "PASS",
                "isMandatory": True
            },
            {
                "stage": STAGE_DIAGNOSIS,
                "itemName": "Đính kèm ít nhất 1 ảnh chụp hiện trạng máy trước khi tháo",
                "inputType": "PASS_FAIL",
                "expectedValue": "PASS",
                "isMandatory": True
            },
            # Giai đoạn 2: Kiểm đếm vật tư sẵn sàng (Bắt buộc)
            {
                "stage": STAGE_STAGING_PARTS,
                "itemName": f"Xác nhận phụ tùng cốt lõi ({part_name}) đã sẵn sàng trong kho",
                "inputType": "PASS_FAIL",
                "expectedValue": "PASS",
                "isMandatory": True
            },
            # Giai đoạn 3: Thực hiện đại tu & Thay thế cốt lõi (Bắt buộc)
            {
                "stage": STAGE_OVERHAUL_EXECUTION,
                "itemName": "Tháo rã cụm nắp, vệ sinh cổ trục & gia nhiệt lắp vòng bi mới",
                "inputType": "PASS_FAIL",
                "expectedValue": "PASS",
                "isMandatory": True
            },
            # Giai đoạn 4: Chạy thử & Đo nghiệm thu (Bắt buộc số liệu)
            {
                "stage": STAGE_TRIAL_ACCEPTANCE,
                "itemName": "Đo lại độ rung hiệu dụng sau 30 phút chạy thử không tải (mm/s RMS)",
                "inputType": "NUMBER",
                "expectedValue": f"< {MAX_ACCEPTABLE_POST_REPAIR_VIBRATION}",
                "isMandatory": True
            },
            {
                "stage": STAGE_TRIAL_ACCEPTANCE,
                "itemName": "Đo lại nhiệt độ gối đỡ sau chạy thử (°C)",
                "inputType": "NUMBER",
                "expectedValue": f"< {MAX_ACCEPTABLE_POST_REPAIR_TEMPERATURE}",
                "isMandatory": True
            }
        ]

    @classmethod
    def get_normal_checklist_templates(cls, asset=None) -> list:
        """
        Kho mẫu Checklist bảo dưỡng thông thường / nhẹ (NORMAL_MAINTENANCE).
        """
        return [
            {
                "stage": STAGE_DIAGNOSIS,
                "itemName": "Kiểm tra và bôi trơn dầu mỡ các khớp động",
                "inputType": "PASS_FAIL",
                "expectedValue": "PASS",
                "isMandatory": True
            },
            {
                "stage": STAGE_OVERHAUL_EXECUTION,
                "itemName": "Siết chặt bu lông bệ máy và kiểm tra khớp nối",
                "inputType": "PASS_FAIL",
                "expectedValue": "PASS",
                "isMandatory": True
            },
            {
                "stage": STAGE_OVERHAUL_EXECUTION,
                "itemName": "Vệ sinh công nghiệp và lau chùi bề mặt thiết bị",
                "inputType": "PASS_FAIL",
                "expectedValue": "PASS",
                "isMandatory": False
            },
            {
                "stage": STAGE_TRIAL_ACCEPTANCE,
                "itemName": "Đo kiểm tra độ rung sau bảo dưỡng (mm/s RMS)",
                "inputType": "NUMBER",
                "expectedValue": f"< {MAX_ACCEPTABLE_POST_REPAIR_VIBRATION}",
                "isMandatory": False
            }
        ]

    @classmethod
    def evaluate(
        cls,
        asset=None,
        alert=None,
        z_score=None,
        rul_days=None,
        estimated_cost=None,
        recurrence_count=None,
        tenant=None,
        **kwargs
    ) -> dict:
        """
        Phân tích đa biến bằng Decision Tree và sinh bộ gợi ý đầy đủ cho Work Order.
        """
        from assets.models import Asset
        from workorders.models import WorkOrder

        # Handle aliases from kwargs
        if z_score is None:
            z_score = kwargs.get('anomaly_zscore') or kwargs.get('anomalyZscore')
        if rul_days is None:
            rul_days = kwargs.get('current_rul_days') or kwargs.get('currentRulDays')
        if recurrence_count is None:
            recurrence_count = kwargs.get('failure_recurrence') or kwargs.get('failureRecurrence')

        # 1. Trích xuất Z-score từ alert hoặc tham số
        eff_z_score = 0.0
        if z_score is not None:
            eff_z_score = float(z_score)
        elif alert and hasattr(alert, 'metric_value') and alert.metric_value is not None:
            eff_z_score = float(alert.metric_value)

        # 2. Trích xuất RUL days
        eff_rul_days = 60.0
        has_rapid_alert = False
        if rul_days is not None:
            eff_rul_days = float(rul_days)
        elif asset:
            if asset.current_rul_days is not None:
                eff_rul_days = float(asset.current_rul_days)
            has_rapid_alert = bool(getattr(asset, 'rapid_degradation_alert', False))

        # 3. Trích xuất Chi phí ước tính & Tỷ lệ chi phí so với nguyên giá máy
        purchase_cost = 100_000_000.0
        if asset:
            eff_cost = getattr(asset, 'effective_purchase_cost', None)
            if eff_cost and float(eff_cost) > 0:
                purchase_cost = float(eff_cost)

        if 'estimated_cost_ratio' in kwargs and kwargs['estimated_cost_ratio'] is not None:
            cost_ratio = float(kwargs['estimated_cost_ratio'])
        else:
            eff_est_cost = 5_000_000.0
            if estimated_cost is not None:
                eff_est_cost = float(estimated_cost)
            cost_ratio = float(eff_est_cost) / purchase_cost

        # 4. Trích xuất Số lần hỏng hóc lặp lại trong 90 ngày
        eff_recurrence = 0
        if recurrence_count is not None:
            eff_recurrence = int(recurrence_count)
        elif asset:
            ninety_days_ago = timezone.now() - timedelta(days=90)
            eff_recurrence = WorkOrder.objects.filter(
                asset=asset,
                created_at__gte=ninety_days_ago
            ).count()

        # 5. Phân loại qua Cây quyết định
        features = np.array([[eff_z_score, eff_rul_days, cost_ratio, eff_recurrence]], dtype=float)
        clf = cls.get_classifier()
        prediction = clf.predict(features)[0]

        # Override an toàn: nếu RUL <= 15 ngày hoặc Z-score >= 2.5 hoặc có cảnh báo gia tốc suy thoái
        if eff_rul_days <= RUL_CRITICAL_THRESHOLD_DAYS or eff_z_score >= Z_SCORE_CRITICAL_THRESHOLD or has_rapid_alert:
            prediction = 1

        is_critical = (prediction == 1)
        suggested_severity = SEVERITY_CRITICAL if is_critical else SEVERITY_NORMAL
        suggested_action = ACTION_CORE_REPLACEMENT if is_critical else ACTION_GENERAL
        suggested_priority = "CRITICAL" if is_critical else ("MEDIUM" if eff_z_score < 1.5 else "HIGH")

        # 6. Kiểm tra cảnh báo vùng đệm giáp ranh (±5%)
        marginal_warning = cls.check_marginal_boundary(eff_z_score, eff_rul_days)

        # 7. Soạn thảo chuỗi giải thích IF-THEN
        decision_path = cls.generate_decision_explanation(
            severity=suggested_severity,
            z_score=eff_z_score,
            rul_days=eff_rul_days,
            cost_ratio=cost_ratio,
            recurrence=eff_recurrence,
            has_rapid_degradation=has_rapid_alert,
            marginal_warning=marginal_warning
        )

        # 8. Sinh bộ Checklist tương ứng
        if is_critical:
            checklists = cls.get_overhaul_checklist_templates(asset)
            asset_title = asset.name if asset else "Thiết bị"
            suggested_title = f"Đại tu bổ máy cốt lõi: Thay thế cụm chi tiết máy {asset_title}"
        else:
            checklists = cls.get_normal_checklist_templates(asset)
            asset_title = asset.name if asset else "Thiết bị"
            suggested_title = f"Bảo dưỡng định kỳ: {asset_title}"

        normalized_checklists = [
            {
                "item_name": c.get("itemName") or c.get("item_name"),
                "itemName": c.get("itemName") or c.get("item_name"),
                "input_type": c.get("inputType") or c.get("input_type"),
                "inputType": c.get("inputType") or c.get("input_type"),
                "expected_value": c.get("expectedValue") or c.get("expected_value"),
                "expectedValue": c.get("expectedValue") or c.get("expected_value"),
                "is_mandatory": c.get("isMandatory") if "isMandatory" in c else c.get("is_mandatory", False),
                "isMandatory": c.get("isMandatory") if "isMandatory" in c else c.get("is_mandatory", False),
                "stage": c.get("stage", ""),
            }
            for c in checklists
        ]

        return {
            "suggestedSeverity": suggested_severity,
            "severity_level": suggested_severity,
            "severityLevel": suggested_severity,
            "suggestedMaintenanceAction": suggested_action,
            "recommended_action": suggested_action,
            "recommendedMaintenanceAction": suggested_action,
            "marginalBoundaryWarning": marginal_warning,
            "marginal_boundary_warning": marginal_warning,
            "decisionPathExplanation": decision_path,
            "decision_path_explanation": decision_path,
            "suggestedPriority": suggested_priority,
            "recommended_priority": suggested_priority,
            "suggestedTitle": suggested_title,
            "suggestedChecklists": normalized_checklists,
            "suggested_checklists": normalized_checklists,
        }

    @classmethod
    def apply_overhaul_checklist(cls, work_order) -> list:
        """
        Nạp bộ 4 giai đoạn Checklist bắt buộc vào một Work Order cụ thể (dành cho Task 11.5 hoặc Lập phiếu).
        """
        from workorders.models import WorkOrderChecklistItem

        templates = cls.get_overhaul_checklist_templates(work_order.asset)
        created_items = []

        # Xóa checklist rỗng trước nếu có
        from django.db.models import Q
        work_order.checklists.filter(is_completed=False).filter(Q(actual_value__isnull=True) | Q(actual_value='')).delete()

        for t in templates:
            item = WorkOrderChecklistItem.objects.create(
                tenant=work_order.tenant,
                work_order=work_order,
                item_name=t["itemName"],
                input_type=t["inputType"],
                expected_value=t["expectedValue"],
                is_mandatory=t["isMandatory"],
                stage=t["stage"],
                is_completed=False
            )
            created_items.append(item)

        work_order.maintenance_action = ACTION_CORE_REPLACEMENT
        work_order.severity_level = SEVERITY_CRITICAL
        work_order.save(update_fields=['maintenance_action', 'severity_level', 'updated_at'])

        logger.info(f"Đã nạp {len(created_items)} checklist đại tu bổ máy cho WO {work_order.id}")
        return created_items

    @classmethod
    def rollback_work_order(
        cls,
        work_order,
        user,
        reason: str,
        vibration_reading: float = None,
        temperature_reading: float = None,
        **kwargs
    ):
        """
        Lùi bước kỹ thuật (HSM Rollback):
        Khi chạy thử phát hiện rung lắc hoặc không đạt, Quản đốc yêu cầu làm lại:
        - Bắt buộc lý do kỹ thuật >= 20 ký tự
        - Chuyển toàn bộ Checklist giai đoạn 3 (OVERHAUL_EXECUTION) & 4 (TRIAL_ACCEPTANCE) về False
        - Đưa trạng thái Work Order về IN_PROGRESS
        - Ghi log HsmStageTransition (action_type='ROLLBACK')
        """
        from workorders.models import HsmStageTransition

        if vibration_reading is None:
            vibration_reading = kwargs.get('recheck_vibration') or kwargs.get('recheckVibration')
        if temperature_reading is None:
            temperature_reading = kwargs.get('recheck_temperature') or kwargs.get('recheckTemperature')

        clean_reason = str(reason or '').strip()
        if len(clean_reason) < 20:
            raise ValidationError("Lý do lùi bước kỹ thuật phải có ít nhất 20 ký tự mô tả chi tiết nguyên nhân.")

        # Revert Stage 3 & 4 checklists
        target_stages = [STAGE_OVERHAUL_EXECUTION, STAGE_TRIAL_ACCEPTANCE]
        reverted_count = 0

        # Query all checklists of the work order
        for chk in work_order.checklists.all():
            should_revert = False
            if chk.stage in target_stages:
                should_revert = True
            elif chk.input_type == 'NUMBER':
                should_revert = True
            elif any(w in chk.item_name.lower() for w in ['chạy thử', 'nghiệm thu', 'đo lại', 'thay thế', 'tháo rã']):
                should_revert = True

            if should_revert:
                chk.is_completed = False
                chk.actual_value = None
                chk.save(update_fields=['is_completed', 'actual_value', 'updated_at'])
                reverted_count += 1

        work_order.status = 'IN_PROGRESS'
        work_order.save(update_fields=['status', 'updated_at'])

        # Record audit transition
        transition = HsmStageTransition.objects.create(
            tenant=work_order.tenant,
            work_order=work_order,
            action_type='ROLLBACK',
            severity_assigned=work_order.severity_level,
            reason=clean_reason,
            performed_by=user,
            vibration_reading=float(vibration_reading) if vibration_reading is not None else None,
            temperature_reading=float(temperature_reading) if temperature_reading is not None else None
        )

        logger.info(f"Rollback thành công cho WO {work_order.id}: {reverted_count} checklists được chuyển về False")

        class RollbackResult(tuple):
            def __new__(cls, trans, count):
                return super().__new__(cls, (trans, count))
            @property
            def transition(self):
                return self[0]
            @property
            def reverted_count(self):
                return self[1]
            def __getattr__(self, name):
                return getattr(self[0], name)

        return RollbackResult(transition, reverted_count)

    @classmethod
    def hold_work_order(cls, work_order, user, hold_reason: str = None, notes: str = '', **kwargs):
        """
        Tạm hoãn ngoại cảnh (ON_HOLD):
        Khi chờ phụ tùng hoặc chuyên gia, đóng băng đồng hồ tính SLA/MTTR.
        """
        from workorders.models import HsmStageTransition

        if hold_reason is None:
            hold_reason = kwargs.get('reason') or kwargs.get('holdReason') or 'WAITING_PARTS'

        now = timezone.now()
        work_order.is_on_hold = True
        work_order.hold_reason = (hold_reason or 'WAITING_PARTS')[:64]
        work_order.hold_started_at = now
        work_order.status = 'ON_HOLD'
        work_order.save(update_fields=['is_on_hold', 'hold_reason', 'hold_started_at', 'status', 'updated_at'])

        transition = HsmStageTransition.objects.create(
            tenant=work_order.tenant,
            work_order=work_order,
            action_type='HOLD',
            severity_assigned=work_order.severity_level,
            reason=f"Tạm hoãn phiếu: {work_order.hold_reason}. {notes}".strip(),
            performed_by=user
        )
        return transition

    @classmethod
    def resume_work_order(cls, work_order, user, notes: str = ''):
        """
        Tiếp tục công việc sau tạm hoãn (RESUME):
        Tích lũy thời gian tạm hoãn vào hold_accumulated_seconds và đưa trạng thái về IN_PROGRESS.
        """
        from workorders.models import HsmStageTransition

        now = timezone.now()
        if work_order.hold_started_at:
            delta_sec = int((now - work_order.hold_started_at).total_seconds())
            work_order.hold_accumulated_seconds = (work_order.hold_accumulated_seconds or 0) + max(0, delta_sec)
            work_order.hold_started_at = None

        work_order.is_on_hold = False
        work_order.hold_reason = None
        work_order.status = 'IN_PROGRESS'
        work_order.save(update_fields=['hold_accumulated_seconds', 'hold_started_at', 'is_on_hold', 'hold_reason', 'status', 'updated_at'])

        transition = HsmStageTransition.objects.create(
            tenant=work_order.tenant,
            work_order=work_order,
            action_type='RESUME',
            severity_assigned=work_order.severity_level,
            reason=f"Tiếp tục thực hiện phiếu sau tạm hoãn. {notes}".strip(),
            performed_by=user
        )
        return transition

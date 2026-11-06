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
        Đảm bảo cả 4 đặc trưng đều tham gia vào các nút rẽ nhánh quyết định của cây.
        """
        X = np.array([
            # [z_score, rul_days, cost_ratio, recurrence]
            # Nhánh 1: Bảo dưỡng thông thường (RUL > 15, Z < 2.5, Cost <= 0.25, Recurrence <= 2)
            [0.5, 90.0, 0.05, 0],
            [0.8, 80.0, 0.08, 0],
            [1.0, 60.0, 0.10, 1],
            [1.2, 45.0, 0.12, 0],
            [1.4, 40.0, 0.15, 1],
            [1.6, 50.0, 0.18, 0],
            [1.8, 35.0, 0.22, 1],
            [2.0, 30.0, 0.15, 0],
            [2.1, 45.0, 0.10, 1],
            [2.2, 35.0, 0.20, 0],
            [2.3, 40.0, 0.12, 1],
            [2.45, 30.0, 0.15, 0],  # Điểm cận biên Z < 2.50 thuộc Zone C cảnh báo nhưng chưa bổ máy
            [0.6, 80.0, 0.05, 2],  # Máy có 2 lần bảo dưỡng định kỳ trước đó nhưng còn rất tốt -> NORMAL
            [1.1, 55.0, 0.18, 2],  # Recurrence 2, độ rung thấp, RUL dài -> NORMAL
            [1.5, 38.0, 0.22, 2],  # Recurrence 2, chi phí hợp lý -> NORMAL
            [1.0, 25.0, 0.10, 0],  # RUL 25 ngày (> 15), độ rung êm -> NORMAL
            [1.3, 20.0, 0.15, 1],  # RUL 20 ngày (> 15) -> NORMAL
            [1.6, 22.0, 0.20, 0],  # RUL 22 ngày (> 15) -> NORMAL
            [1.7, 18.0, 0.25, 1],  # RUL 18 ngày (> 15) -> NORMAL

            # Nhánh 2: Đại tu cốt lõi - Rung động nguy hiểm Zone D (Z >= 2.5)
            [2.55, 30.0, 0.15, 0],  # Điểm cận biên Z >= 2.50 bắt đầu Zone D
            [2.6, 45.0, 0.10, 0],
            [2.8, 30.0, 0.15, 1],
            [3.0, 50.0, 0.12, 0],
            [3.2, 25.0, 0.20, 2],
            [3.5, 60.0, 0.08, 1],

            # Nhánh 3: Đại tu cốt lõi - Tuổi thọ cạn kiệt (RUL <= 15)
            [0.8, 8.0,  0.10, 0],
            [1.0, 12.0, 0.15, 1],
            [1.4, 10.0, 0.12, 0],
            [1.8, 14.0, 0.18, 1],
            [2.2, 7.0,  0.20, 2],

            # Nhánh 4: Đại tu cốt lõi - Tỷ lệ chi phí vượt ngưỡng nghiêm trọng (Cost >= 0.35)
            [1.5, 35.0, 0.45, 0],
            [1.8, 30.0, 0.40, 1],
            [2.0, 40.0, 0.38, 0],

            # Nhánh 5: Đại tu cốt lõi - Hỏng hóc lặp lại mãn tính (Recurrence >= 3)
            [1.8, 30.0, 0.20, 3],
            [2.0, 35.0, 0.18, 4],
            [2.1, 40.0, 0.22, 3],
        ], dtype=float)

        y = np.array([
            0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,  # 19 normal
            1, 1, 1, 1, 1, 1,                                          # 6 critical Z
            1, 1, 1, 1, 1,                                             # 5 critical RUL
            1, 1, 1,                                                   # 3 high cost
            1, 1, 1                                                    # 3 chronic recurrence
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
            if z_score is not None and z_score < Z_SCORE_NORMAL_THRESHOLD:
                z_str = f"Z-score rung chấn ({z_score:.2f}) < {Z_SCORE_NORMAL_THRESHOLD:.2f}"
            elif z_score is not None:
                z_str = f"Z-score rung chấn ({z_score:.2f}) < {Z_SCORE_CRITICAL_THRESHOLD:.2f} (Ngưỡng cảnh báo nhẹ)"
            else:
                z_str = "Chỉ số cảm biến ổn định"

            if rul_days is not None and rul_days > 30.0:
                rul_str = f"RUL còn lại ({rul_days:.1f} ngày) > 30.0 ngày"
            elif rul_days is not None:
                rul_str = f"RUL còn lại ({rul_days:.1f} ngày) > {RUL_CRITICAL_THRESHOLD_DAYS:.1f} ngày (Tuổi thọ khả dụng)"
            else:
                rul_str = "Tuổi thọ RUL an toàn"

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

        # 1. Trích xuất Z-score từ alert hoặc tham số (Tuyệt đối không dùng current_value cảm biến thô hoặc anomaly_score Isolation Forest)
        eff_z_score = 0.0
        if z_score is not None:
            eff_z_score = float(z_score)
        elif alert and getattr(alert, 'z_score', None) is not None:
            eff_z_score = float(alert.z_score)

        # 2. Trích xuất RUL days (ưu tiên RUL mô hình LSTM Task 11.5)
        eff_rul_days = 60.0
        has_rapid_alert = False
        target_asset = asset or (alert.asset if alert and hasattr(alert, 'asset') else None)
        if rul_days is not None:
            eff_rul_days = float(rul_days)
        elif target_asset and target_asset.current_rul_days is not None:
            eff_rul_days = float(target_asset.current_rul_days)
            has_rapid_alert = bool(getattr(target_asset, 'rapid_degradation_alert', False))
        elif alert and getattr(alert, 'days_remaining', None) is not None:
            # Fallback sang ước tính suy thoái của Alert nếu máy chưa có dự báo RUL LSTM
            eff_rul_days = float(alert.days_remaining)

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
        # Nghiệp vụ chuẩn: Chỉ đếm các sự cố kỹ thuật gốc (CORRECTIVE, EMERGENCY, BREAKDOWN),
        # loại trừ bảo dưỡng định kỳ (PREVENTIVE, PREDICTIVE_PM), phiếu hủy (CANCELLED) và phiếu phụ theo dõi (parent_id)
        eff_recurrence = 0
        if recurrence_count is not None:
            eff_recurrence = int(recurrence_count)
        elif asset:
            ninety_days_ago = timezone.now() - timedelta(days=90)
            eff_recurrence = WorkOrder.objects.filter(
                asset=asset,
                type__in=['CORRECTIVE', 'EMERGENCY', 'BREAKDOWN'],
                created_at__gte=ninety_days_ago
            ).exclude(
                status='CANCELLED'
            ).filter(
                parent_id__isnull=True
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
    def apply_overhaul_checklist(cls, work_order, user=None) -> list:
        """
        Nạp bộ 4 giai đoạn Checklist bắt buộc vào một Work Order cụ thể (dành cho Task 11.5 hoặc Lập phiếu).
        """
        from workorders.models import WorkOrderChecklistItem, HsmStageTransition

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

        # Audit AI_EVALUATE transition if not already recorded
        if user and not work_order.hsm_transitions.filter(action_type='AI_EVALUATE').exists():
            HsmStageTransition.objects.create(
                tenant=work_order.tenant,
                work_order=work_order,
                action_type='AI_EVALUATE',
                severity_assigned=SEVERITY_CRITICAL,
                from_stage=None,
                to_stage=STAGE_DIAGNOSIS,
                reason="AI Cây quyết định tự động nạp quy trình đại tu 4 giai đoạn bắt buộc (CORE_REPLACEMENT)",
                performed_by=user
            )

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
        - Bắt buộc phiếu đang ở trạng thái IN_PROGRESS (chặn tuyệt đối nếu đã COMPLETED hoặc CANCELLED)
        - Bắt buộc lý do kỹ thuật >= 20 ký tự
        - Chuyển toàn bộ Checklist giai đoạn 3 (OVERHAUL_EXECUTION) & 4 (TRIAL_ACCEPTANCE) về False
        - Tuyệt đối giữ nguyên kết quả Checklist giai đoạn 1 (DIAGNOSIS) & giai đoạn 2 (STAGING_PARTS)
        - Đưa trạng thái Work Order về IN_PROGRESS
        - Ghi log HsmStageTransition (action_type='ROLLBACK', from_stage='TRIAL_ACCEPTANCE', to_stage='OVERHAUL_EXECUTION')
        """
        from workorders.models import HsmStageTransition

        if work_order.status == 'COMPLETED':
            raise ValidationError("Không thể Rollback phiếu đã hoàn thành (COMPLETED). Chi phí và mốc đại tu đã được đóng băng.")
        if work_order.status == 'CANCELLED':
            raise ValidationError("Không thể Rollback phiếu đã hủy (CANCELLED).")

        clean_reason = str(reason or '').strip()
        if len(clean_reason) < 20:
            raise ValidationError("Lý do lùi bước kỹ thuật phải có ít nhất 20 ký tự mô tả chi tiết nguyên nhân.")

        if vibration_reading is None:
            vibration_reading = kwargs.get('recheck_vibration') or kwargs.get('recheckVibration')
        if temperature_reading is None:
            temperature_reading = kwargs.get('recheck_temperature') or kwargs.get('recheckTemperature')

        # Revert ONLY Stage 3 & 4 checklists
        target_stages = [STAGE_OVERHAUL_EXECUTION, STAGE_TRIAL_ACCEPTANCE]
        reverted_count = 0

        # Query all checklists of the work order
        for chk in work_order.checklists.all():
            should_revert = False
            if chk.stage:
                should_revert = (chk.stage in target_stages)
            else:
                # Fallback nếu checklist không có stage: chỉ revert mục chạy thử/nghiệm thu/thay thế
                # và TUYỆT ĐỐI không revert nếu là mục khảo sát hay vật tư
                name_l = chk.item_name.lower()
                is_stage_1_or_2 = any(w in name_l for w in ['khảo sát', 'chụp ảnh', 'vật tư', 'phụ tùng', 'sẵn sàng'])
                is_stage_3_or_4 = any(w in name_l for w in ['chạy thử', 'nghiệm thu', 'đo lại', 'thay thế', 'tháo rã', 'lắp'])
                should_revert = is_stage_3_or_4 and not is_stage_1_or_2

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
            from_stage=STAGE_TRIAL_ACCEPTANCE,
            to_stage=STAGE_OVERHAUL_EXECUTION,
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
        Đồng bộ an toàn: chỉ chuyển thợ sang AVAILABLE nếu thợ đang BUSY và không có việc IN_PROGRESS nào khác.
        """
        from django.db import transaction
        from workorders.models import HsmStageTransition, WorkOrder
        from users.models import TechnicianProfile

        with transaction.atomic():
            # Lock work order row
            wo = WorkOrder.objects.select_for_update().get(id=work_order.id)
            if wo.status == 'COMPLETED':
                raise ValidationError("Không thể tạm hoãn phiếu đã hoàn thành.")

            if hold_reason is None:
                hold_reason = kwargs.get('reason') or kwargs.get('holdReason') or 'WAITING_PARTS'

            now = timezone.now()
            wo.is_on_hold = True
            wo.hold_reason = (hold_reason or 'WAITING_PARTS')[:64]
            wo.hold_started_at = now
            wo.status = 'ON_HOLD'
            wo.save(update_fields=['is_on_hold', 'hold_reason', 'hold_started_at', 'status', 'updated_at'])

            # Đồng bộ giải phóng trạng thái kỹ thuật viên
            assigned_user = wo.assigned_to
            if assigned_user and hasattr(assigned_user, 'technician_profile'):
                tp = TechnicianProfile.objects.select_for_update().filter(user=assigned_user).first()
                if tp:
                    other_active = WorkOrder.objects.filter(
                        assigned_to=assigned_user,
                        status__in=['ASSIGNED', 'IN_PROGRESS']
                    ).exclude(id=wo.id).exists()
                    # Chỉ chuyển về AVAILABLE nếu hiện tại đang BUSY và không có phiếu ASSIGNED hoặc IN_PROGRESS nào khác
                    if not other_active and tp.availability_status == 'BUSY':
                        tp.availability_status = 'AVAILABLE'
                        tp.save(update_fields=['availability_status', 'updated_at'])

            # Xác định stage hiện tại để lưu audit trail
            current_stage = STAGE_OVERHAUL_EXECUTION
            incomplete_items = wo.checklists.filter(is_completed=False).order_by('id')
            if incomplete_items.exists():
                first_incomplete = incomplete_items.first()
                if first_incomplete.stage:
                    current_stage = first_incomplete.stage

            transition = HsmStageTransition.objects.create(
                tenant=wo.tenant,
                work_order=wo,
                action_type='HOLD',
                severity_assigned=wo.severity_level,
                from_stage=current_stage,
                to_stage='ON_HOLD',
                reason=f"Tạm hoãn phiếu: {wo.hold_reason}. {notes}".strip(),
                performed_by=user
            )
            return transition

    @classmethod
    def resume_work_order(cls, work_order, user, notes: str = ''):
        """
        Tiếp tục công việc sau tạm hoãn (RESUME):
        Tích lũy thời gian tạm hoãn vào hold_accumulated_seconds và đưa trạng thái về IN_PROGRESS.
        Rào chắn an toàn: kiểm tra kỹ thuật viên không bị phân công chồng lấn và không trong thời gian nghỉ phép.
        """
        from django.db import transaction
        from workorders.models import HsmStageTransition, WorkOrder
        from users.models import TechnicianProfile

        with transaction.atomic():
            # Lock work order row
            wo = WorkOrder.objects.select_for_update().get(id=work_order.id)
            if wo.status != 'ON_HOLD':
                raise ValidationError(f"Không thể tiếp tục (Resume) phiếu đang ở trạng thái {wo.status}. Chỉ có thể Resume từ trạng thái ON_HOLD.")

            now = timezone.now()
            if wo.hold_started_at:
                delta_sec = int((now - wo.hold_started_at).total_seconds())
                wo.hold_accumulated_seconds = (wo.hold_accumulated_seconds or 0) + max(0, delta_sec)
                wo.hold_started_at = None

            # Kiểm tra an toàn phân công kỹ thuật viên
            assigned_user = wo.assigned_to
            if assigned_user and hasattr(assigned_user, 'technician_profile'):
                tp = TechnicianProfile.objects.select_for_update().filter(user=assigned_user).first()
                if tp:
                    # 1. Kiểm tra kỹ thuật viên có đang nghỉ phép hoặc không trong ca trực
                    if tp.availability_status == 'ON_LEAVE' or not tp.is_on_duty:
                        raise ValidationError(
                            f"Không thể tiếp tục phiếu: Kỹ thuật viên {assigned_user.get_full_name() or assigned_user.username} "
                            f"hiện không trong ca trực hoặc đang nghỉ phép (Trạng thái: {tp.availability_status}, Trực: {tp.is_on_duty}). "
                            f"Vui lòng phân công kỹ thuật viên khác trước khi tiếp tục."
                        )

                    # 2. Kiểm tra kỹ thuật viên có đang giữ hoặc thực hiện phiếu khác (ASSIGNED hoặc IN_PROGRESS)
                    other_active = WorkOrder.objects.filter(
                        assigned_to=assigned_user,
                        status__in=['ASSIGNED', 'IN_PROGRESS']
                    ).exclude(id=wo.id)
                    if other_active.exists():
                        other_wo = other_active.first()
                        status_str = "đang thực hiện" if other_wo.status == 'IN_PROGRESS' else "đã được phân công"
                        raise ValidationError(
                            f"Không thể tiếp tục phiếu: Kỹ thuật viên {assigned_user.get_full_name() or assigned_user.username} "
                            f"hiện {status_str} phiếu công việc khác ({other_wo.code or other_wo.title} - Trạng thái: {other_wo.status}). "
                            f"Vui lòng hoàn thành/tái phân công phiếu đó trước khi tiếp tục."
                        )

                    # Nếu hợp lệ, đưa trạng thái kỹ thuật viên sang BUSY
                    tp.availability_status = 'BUSY'
                    tp.save(update_fields=['availability_status', 'updated_at'])

            wo.is_on_hold = False
            wo.hold_reason = None
            wo.status = 'IN_PROGRESS'
            wo.save(update_fields=['hold_accumulated_seconds', 'hold_started_at', 'is_on_hold', 'hold_reason', 'status', 'updated_at'])

            resume_stage = STAGE_OVERHAUL_EXECUTION
            incomplete_items = wo.checklists.filter(is_completed=False).order_by('id')
            if incomplete_items.exists():
                first_incomplete = incomplete_items.first()
                if first_incomplete.stage:
                    resume_stage = first_incomplete.stage

            transition = HsmStageTransition.objects.create(
                tenant=wo.tenant,
                work_order=wo,
                action_type='RESUME',
                severity_assigned=wo.severity_level,
                from_stage='ON_HOLD',
                to_stage=resume_stage,
                reason=f"Tiếp tục thực hiện phiếu sau tạm hoãn. {notes}".strip(),
                performed_by=user
            )
            return transition

    @classmethod
    def record_override(cls, work_order, user, original_severity: str, assigned_severity: str, override_reason: str):
        """
        Lưu vết can thiệp đè phán quyết AI của Quản đốc (HsmStageTransition action_type='OVERRIDE').
        """
        from workorders.models import HsmStageTransition
        return HsmStageTransition.objects.create(
            tenant=work_order.tenant,
            work_order=work_order,
            action_type='OVERRIDE',
            severity_assigned=assigned_severity,
            from_stage=original_severity,
            to_stage=assigned_severity,
            reason=f"Quản đốc can thiệp điều chỉnh phán quyết AI: {override_reason}".strip(),
            performed_by=user
        )

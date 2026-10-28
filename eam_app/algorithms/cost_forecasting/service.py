"""
Orchestrator Service cho Phân hệ Quản lý & Dự báo Chi phí Bảo trì (Task 11.6).
Tích hợp ORM, đóng băng chi phí bất biến, liên kết cảnh báo bội chi và thông báo Real-time.
"""
import calendar
import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Any

from django.utils import timezone
from django.db import transaction
from django.db.models import Sum, Q

from analytics.models import BudgetForecast
from workorders.models import WorkOrder, WorkOrderCost, LaborLog
from assets.models import Asset, StockTransaction
from users.models import User
from maintenance.models import PmPlan
from notifications.models import Notification
from algorithms.cost_forecasting.constants import (
    DEFAULT_INFLATION_RATE,
    DEFAULT_CONTINGENCY_BUFFER_RATE,
    MIN_MONTHS_TRAINING_DATA,
    MIN_HISTORICAL_PERIODS_FOR_ML
)
from algorithms.cost_forecasting.feature_pipeline import CostFeaturePipeline, get_actual_consumption_net_cost
from algorithms.cost_forecasting.lemon_detector import LemonAssetDetector
from algorithms.cost_forecasting.hybrid_engine import HybridBudgetingEngine, round_vnd


class CostForecastingService:
    """
    Dịch vụ điều phối cấp cao cho bài toán Quản lý & Dự báo Chi phí Doanh nghiệp.
    """

    @classmethod
    @transaction.atomic
    def freeze_work_order_cost(
        cls,
        work_order: WorkOrder,
        warranty_covered_amount: Optional[Decimal] = None,
        insurance_covered_amount: Optional[Decimal] = None,
        vendor_cost: Optional[Decimal] = None
    ) -> WorkOrderCost:
        """
        Quy tắc 1: Khóa bất biến đơn giá snapshot tại thời điểm hoàn tất nghiệm thu Work Order.
        Quy tắc 2: Tách bạch CapEx vs OpEx.
        Quy tắc 6: Bóc tách Gross vs Net Cost (trừ bảo hành & bảo hiểm).
        Đảm bảo tính Idempotent: nếu đã khóa (is_cost_frozen=True), không bao giờ ghi đè.
        """
        tenant = work_order.tenant

        # 0. Idempotency Check: Nếu đã có snapshot và đã chốt khóa, trả về ngay lập tức
        existing = WorkOrderCost.all_objects.select_for_update().filter(
            tenant=tenant,
            work_order=work_order
        ).first()
        if existing and existing.is_cost_frozen:
            return existing

        # 1. Tính toán chi phí vật tư từ các giao dịch StockTransaction liên kết
        # Chỉ lấy ISSUE (+), ADJUSTMENT (+), trừ RETURN (-)
        mat_txs = StockTransaction.all_objects.filter(
            tenant=tenant,
            work_order=work_order,
            transaction_type__in=['ISSUE', 'ADJUSTMENT', 'RETURN']
        )
        material_cost = Decimal('0')
        cost_center_snapshot = None

        for tx in mat_txs:
            amt = tx.total_amount or Decimal('0')
            if tx.transaction_type == 'RETURN':
                material_cost -= amt
            else:
                material_cost += amt

            if tx.cost_center_snapshot and not cost_center_snapshot:
                cost_center_snapshot = tx.cost_center_snapshot

        # 2. Tính toán chi phí giờ công thợ từ LaborLog
        labor_logs = LaborLog.all_objects.filter(
            tenant=tenant,
            work_order=work_order
        )
        labor_cost = labor_logs.aggregate(s=Sum('total_cost'))['s'] or Decimal('0')
        if not cost_center_snapshot:
            first_ll = labor_logs.filter(cost_center_snapshot__isnull=False).first()
            if first_ll:
                cost_center_snapshot = first_ll.cost_center_snapshot

        if not cost_center_snapshot:
            if work_order.incident_location and work_order.incident_location.name:
                cost_center_snapshot = work_order.incident_location.name
            elif work_order.asset and work_order.asset.location:
                cost_center_snapshot = work_order.asset.location.name

        # 3. Chi phí thuê ngoài dịch vụ
        if vendor_cost is not None:
            v_cost = Decimal(str(vendor_cost))
        elif existing and existing.vendor_cost:
            v_cost = existing.vendor_cost
        else:
            v_cost = Decimal('0.00')

        # 4. Chi phí gộp Gross Cost
        gross_cost = max(Decimal('0'), material_cost + labor_cost + v_cost)

        # 5. Chi phí bảo hành & bảo hiểm
        if warranty_covered_amount is not None:
            w_cost = Decimal(str(warranty_covered_amount))
        elif existing and existing.warranty_covered_amount:
            w_cost = existing.warranty_covered_amount
        elif hasattr(work_order, 'warranty_covered_amount') and getattr(work_order, 'warranty_covered_amount', None):
            w_cost = Decimal(str(work_order.warranty_covered_amount))
        else:
            w_cost = Decimal('0.00')

        if insurance_covered_amount is not None:
            i_cost = Decimal(str(insurance_covered_amount))
        elif existing and existing.insurance_covered_amount:
            i_cost = existing.insurance_covered_amount
        elif hasattr(work_order, 'insurance_covered_amount') and getattr(work_order, 'insurance_covered_amount', None):
            i_cost = Decimal(str(work_order.insurance_covered_amount))
        else:
            i_cost = Decimal('0.00')

        # 6. Chi phí ròng Net Cost (có thể = 0 nếu bảo hành/bảo hiểm 100%)
        net_cost = max(Decimal('0'), gross_cost - (w_cost + i_cost))

        # 7. Cờ đại tu lớn CapEx
        is_cap = bool(
            work_order.is_capitalized
            or work_order.maintenance_action == 'CORE_REPLACEMENT'
        )

        cost_obj, _ = WorkOrderCost.all_objects.update_or_create(
            tenant=tenant,
            work_order=work_order,
            defaults={
                "cost_center_snapshot": cost_center_snapshot,
                "material_cost": round_vnd(material_cost),
                "labor_cost": round_vnd(labor_cost),
                "vendor_cost": round_vnd(v_cost),
                "gross_cost": round_vnd(gross_cost),
                "warranty_covered_amount": round_vnd(w_cost),
                "insurance_covered_amount": round_vnd(i_cost),
                "net_cost": round_vnd(net_cost),
                "is_capital_overhaul": is_cap,
                "is_cost_frozen": True,
                "cost_frozen_at": timezone.now()
            }
        )

        # Đồng bộ ngược vào WorkOrder.actual_cost
        work_order.actual_cost = cost_obj.net_cost
        work_order.save(update_fields=['actual_cost'])

        return cost_obj

    @classmethod
    def run_forecast(
        cls,
        tenant,
        period: Optional[str] = None,
        cost_center: Optional[str] = None,
        approved_budget: Optional[Decimal] = None,
        inflation_rate: float = DEFAULT_INFLATION_RATE,
        contingency_rate: float = DEFAULT_CONTINGENCY_BUFFER_RATE
    ) -> BudgetForecast:
        """
        Kích hoạt tác vụ tính toán dự báo ngân sách mới và lưu trữ vào database.
        Phát cảnh báo sớm Real-time nếu ngân sách vượt ngưỡng.
        """
        if not period:
            today = timezone.now().date()
            quarter = (today.month - 1) // 3 + 1
            period = f"{today.year}-Q{quarter}"

        # 1. Chạy động cơ dự báo lai ghép
        forecast_result = HybridBudgetingEngine.execute_forecast(
            tenant=tenant,
            period_str=period,
            cost_center=cost_center,
            approved_budget=approved_budget,
            inflation_rate=inflation_rate,
            contingency_rate=contingency_rate
        )

        # 2. Kiểm định tài sản chanh chua Lemon Assets
        lemon_data = LemonAssetDetector.audit_lemon_assets(
            tenant=tenant,
            cost_center=cost_center
        )
        lemon_assets_list = lemon_data.get("lemonAssets", [])

        # Nếu người dùng có nhập approved_budget > 0, cập nhật vào PeriodApprovedBudget
        if approved_budget is not None and approved_budget > Decimal('0'):
            from analytics.models import PeriodApprovedBudget
            PeriodApprovedBudget.all_objects.update_or_create(
                tenant=tenant,
                period=period,
                cost_center=cost_center,
                defaults={
                    'approved_budget': approved_budget,
                    'is_manually_approved': True
                }
            )

        # 3. Lưu vào cơ sở dữ liệu bảng budget_forecasts
        budget_forecast = BudgetForecast.all_objects.create(
            tenant=tenant,
            cost_center_snapshot=cost_center,
            forecast_period=period,
            forecast_method=forecast_result["forecastMethod"],
            approved_budget=forecast_result["approvedBudget"],
            planned_pm_budget=forecast_result["plannedPmBudget"],
            predicted_cm_median=forecast_result["predictedCmMedian"],
            predicted_cm_lower_p10=forecast_result["predictedCmLowerP10"],
            predicted_cm_upper_p90=forecast_result["predictedCmUpperP90"],
            contingency_buffer=forecast_result["contingencyBuffer"],
            total_forecast_median=forecast_result["totalForecastMedian"],
            total_forecast_p90=forecast_result["totalForecastP90"],
            budget_usage_ratio=forecast_result["budgetUsageRatio"],
            budget_status=forecast_result["budgetStatus"],
            inflation_rate_applied=forecast_result["inflationRateApplied"],
            backlog_work_orders_count=forecast_result["backlogOrdersCount"],
            deferred_maintenance_hours=forecast_result["deferredMaintenanceHours"],
            rul_critical_liability=forecast_result["rulCriticalLiability"],
            lemon_assets_detected=lemon_assets_list,
            top_cost_drivers=forecast_result["topCostDrivers"],
            evaluation_metrics=forecast_result.get("evaluationMetrics", {}),
            is_ai_fallback=forecast_result["isAiFallback"],
            fallback_reason=forecast_result.get("fallbackReason"),
            is_manually_approved=forecast_result.get("isManuallyApproved", False)
        )

        # 4. Kích hoạt cảnh báo Real-time (Task 10.1) nếu vượt ngưỡng
        if budget_forecast.budget_status in ['WARNING', 'CRITICAL_OVERRUN']:
            cls._dispatch_overrun_notifications(tenant, budget_forecast)

        return budget_forecast

    @classmethod
    def _dispatch_overrun_notifications(cls, tenant, forecast: BudgetForecast) -> None:
        """
        Gửi thông báo Real-time cho Admin và Kế toán trưởng khi ngân sách chạm ngưỡng nguy hiểm.
        Kiểm tra chống spam thông báo trùng lặp cho cùng một kỳ và trạng thái trong 24 giờ.
        """
        # Deduplication check: Kiểm tra theo Tenant, Kỳ, Trạng thái VÀ Cost Center trong 24 giờ
        recent_threshold = timezone.now() - datetime.timedelta(hours=24)
        cc_val = forecast.cost_center_snapshot or ""
        dedup_qs = Notification.objects.filter(
            tenant=tenant,
            event_type='BUDGET_OVERRUN_ALERT',
            created_at__gte=recent_threshold,
            metadata__period=forecast.forecast_period,
            metadata__budgetStatus=forecast.budget_status
        )
        if cc_val:
            dedup_qs = dedup_qs.filter(metadata__costCenter=cc_val)
        else:
            dedup_qs = dedup_qs.filter(Q(metadata__costCenter__isnull=True) | Q(metadata__costCenter=""))

        if dedup_qs.exists():
            return

        severity = 'CRITICAL' if forecast.budget_status == 'CRITICAL_OVERRUN' else 'WARNING'
        status_text = "Bội chi nghiêm trọng" if severity == 'CRITICAL' else "Tiệm cận hạn mức"

        title = f"Cảnh báo Ngân sách {forecast.forecast_period}: {status_text} ({forecast.budget_usage_ratio}%)"
        message = (
            f"Tổng ngân sách bảo trì dự báo ({int(forecast.total_forecast_median):,} VNĐ) "
            f"đã đạt {forecast.budget_usage_ratio}% hạn mức được duyệt ({int(forecast.approved_budget):,} VNĐ)."
        )

        # Tìm các user có quyền quản lý tài chính hoặc admin chính tắc
        # Tuyệt đối không fallback sang toàn bộ nhân sự trong tenant để tránh rò rỉ thông tin tài chính
        recipients = User.objects.filter(
            tenant=tenant,
            status='ACTIVE'
        ).filter(
            Q(is_superuser=True)
            | Q(roles__permissions__id__in=['tenant:update', 'reports:read', 'system:admin'])
            | Q(roles__name__in=['TENANT_ADMIN', 'SUPER_ADMIN', 'Finance Manager', 'Finance Director', 'CFO'])
        ).distinct()

        if not recipients.exists():
            return

        for recipient in recipients[:10]:
            Notification.objects.create(
                tenant=tenant,
                recipient=recipient,
                event_type='BUDGET_OVERRUN_ALERT',
                category='FINANCE',
                severity=severity,
                title=title,
                message=message,
                link='/portal/cost-forecasting/',
                metadata={
                    "forecastId": str(forecast.id),
                    "period": forecast.forecast_period,
                    "costCenter": cc_val,
                    "budgetUsageRatio": forecast.budget_usage_ratio,
                    "budgetStatus": forecast.budget_status
                }
            )

    @classmethod
    def get_current_forecast(
        cls,
        tenant,
        period: Optional[str] = None,
        cost_center: Optional[str] = None
    ) -> BudgetForecast:
        """
        Lấy bản ghi dự báo ngân sách hiện hành gần nhất, hoặc tự động tính toán nếu chưa có.
        Yêu cầu GET chỉ đọc dữ liệu, không phát notification rác khi tải trang.
        """
        if not period:
            today = timezone.now().date()
            quarter = (today.month - 1) // 3 + 1
            period = f"{today.year}-Q{quarter}"

        qs = BudgetForecast.all_objects.filter(
            tenant=tenant,
            forecast_period=period
        )
        if cost_center:
            qs = qs.filter(cost_center_snapshot=cost_center)
        else:
            qs = qs.filter(cost_center_snapshot__isnull=True)

        latest = qs.order_by('-created_at').first()
        ai_enabled = getattr(tenant, 'enable_ai_cost_forecasting', True)
        if latest:
            # Đồng bộ lại dự báo nếu cấu hình AI Governance của Tenant thay đổi
            if not ai_enabled and latest.fallback_reason != 'AI_DISABLED':
                return cls.run_forecast(tenant=tenant, period=period, cost_center=cost_center)
            elif ai_enabled and latest.fallback_reason == 'AI_DISABLED':
                return cls.run_forecast(tenant=tenant, period=period, cost_center=cost_center)
            return latest

        # Nếu chưa có, chạy tính toán tức thời mà KHÔNG phát notification rác
        forecast_result = HybridBudgetingEngine.execute_forecast(
            tenant=tenant,
            period_str=period,
            cost_center=cost_center
        )
        lemon_data = LemonAssetDetector.audit_lemon_assets(
            tenant=tenant,
            cost_center=cost_center
        )
        lemon_assets_list = lemon_data.get("lemonAssets", [])

        budget_forecast = BudgetForecast.all_objects.create(
            tenant=tenant,
            cost_center_snapshot=cost_center,
            forecast_period=period,
            forecast_method=forecast_result["forecastMethod"],
            approved_budget=forecast_result["approvedBudget"],
            planned_pm_budget=forecast_result["plannedPmBudget"],
            predicted_cm_median=forecast_result["predictedCmMedian"],
            predicted_cm_lower_p10=forecast_result["predictedCmLowerP10"],
            predicted_cm_upper_p90=forecast_result["predictedCmUpperP90"],
            contingency_buffer=forecast_result["contingencyBuffer"],
            total_forecast_median=forecast_result["totalForecastMedian"],
            total_forecast_p90=forecast_result["totalForecastP90"],
            budget_usage_ratio=forecast_result["budgetUsageRatio"],
            budget_status=forecast_result["budgetStatus"],
            inflation_rate_applied=forecast_result["inflationRateApplied"],
            backlog_work_orders_count=forecast_result["backlogOrdersCount"],
            deferred_maintenance_hours=forecast_result["deferredMaintenanceHours"],
            rul_critical_liability=forecast_result["rulCriticalLiability"],
            lemon_assets_detected=lemon_assets_list,
            top_cost_drivers=forecast_result["topCostDrivers"],
            evaluation_metrics=forecast_result.get("evaluationMetrics", {}),
            is_ai_fallback=forecast_result["isAiFallback"],
            fallback_reason=forecast_result.get("fallbackReason"),
            is_manually_approved=forecast_result.get("isManuallyApproved", False)
        )
        return budget_forecast

    @classmethod
    def get_lemon_assets(cls, tenant, cost_center: Optional[str] = None) -> Dict[str, Any]:
        """Lấy danh sách thiết bị quả chanh & Bad Actors theo kiểm định Pareto 80/20 & RRR."""
        return LemonAssetDetector.audit_lemon_assets(tenant=tenant, cost_center=cost_center)

    @classmethod
    def get_historical_trends(
        cls,
        tenant,
        period: Optional[str] = None,
        cost_center: Optional[str] = None,
        months: int = 12
    ) -> Dict[str, Any]:
        """
        Lấy chuỗi lịch sử chi phí thực tế đối sánh với kịch bản dự báo P10, P50, P90 của kỳ được chọn.
        """
        today = timezone.now().date()
        reference_date = today
        if period:
            if '-Q' in period:
                try:
                    parts = period.split('-Q')
                    y = int(parts[0])
                    q = int(parts[1])
                    start_month = (q - 1) * 3 + 1
                    reference_date = datetime.date(y, start_month, 1)
                except Exception:
                    reference_date = today
            elif '-' in period:
                try:
                    parts = period.split('-')
                    y = int(parts[0])
                    m = int(parts[1])
                    reference_date = datetime.date(y, m, 1)
                except Exception:
                    reference_date = today

        hist_costs = CostFeaturePipeline.get_monthly_historical_costs(
            tenant, reference_date=reference_date, months_back=months, cost_center=cost_center
        )

        labels = [item[0] for item in hist_costs]
        actual_values = [float(item[1]) for item in hist_costs]

        # Lấy dự báo đúng kỳ được yêu cầu
        cur_forecast = cls.get_current_forecast(tenant, period=period, cost_center=cost_center)
        p10_val = float(cur_forecast.planned_pm_budget + cur_forecast.predicted_cm_lower_p10 + cur_forecast.contingency_buffer)
        p50_val = float(cur_forecast.total_forecast_median)
        p90_val = float(cur_forecast.total_forecast_p90)

        return {
            "labels": labels,
            "actualSeries": actual_values,
            "forecastProjections": {
                "period": cur_forecast.forecast_period,
                "p10": p10_val,
                "p50": p50_val,
                "p90": p90_val,
                "status": cur_forecast.budget_status
            }
        }

    @classmethod
    def check_readiness(cls, tenant) -> Dict[str, Any]:
        """
        Kiểm tra tính sẵn sàng của dữ liệu thực tế và trạng thái quản trị AI của Tenant.
        """
        ai_enabled = getattr(tenant, 'enable_ai_cost_forecasting', True)
        today = timezone.now().date()

        hist_costs = CostFeaturePipeline.get_monthly_historical_costs(
            tenant, reference_date=today, months_back=12
        )
        months_with_data = sum(1 for _, cost in hist_costs if cost > Decimal('0'))

        X_real, y_real, _ = CostFeaturePipeline.build_historical_training_dataset(
            tenant=tenant,
            reference_date=today,
            months_back=24
        )
        usable_samples = len(y_real)
        positive_samples = sum(1 for y in y_real if y > 0)
        is_ready = bool(ai_enabled and usable_samples >= MIN_HISTORICAL_PERIODS_FOR_ML and positive_samples >= 3)

        active_assets_count = Asset.all_objects.filter(
            tenant=tenant,
            status__in=['OPERATIONAL', 'OPERATING']
        ).count()

        if not ai_enabled:
            status_label = "AI Tắt theo cấu hình Quản trị viên"
            fallback_reason = "AI_DISABLED"
        elif not is_ready:
            status_label = f"Chế độ Fallback Heuristic (Cần tối thiểu {MIN_HISTORICAL_PERIODS_FOR_ML} kỳ lịch sử có nhãn để học 16 đặc trưng; hiện có {usable_samples} kỳ)"
            fallback_reason = "INSUFFICIENT_HISTORICAL_DATA"
        else:
            status_label = "Sẵn sàng chạy Rừng hồi quy phân vị (QRF) trên dữ liệu thực tế"
            fallback_reason = None

        return {
            "aiEnabled": ai_enabled,
            "monthsWithData": months_with_data,
            "usableHistoricalPeriods": usable_samples,
            "minMonthsRequired": MIN_HISTORICAL_PERIODS_FOR_ML,
            "isReadyForAiQrf": is_ready,
            "fallbackReason": fallback_reason,
            "activeAssetsCount": active_assets_count,
            "activePmPlansCount": PmPlan.all_objects.filter(tenant=tenant, is_active=True).count(),
            "statusLabel": status_label
        }

    @classmethod
    def get_financial_settings(cls, tenant, period: Optional[str] = None, cost_center: Optional[str] = None) -> Dict[str, Any]:
        """
        Lấy thiết lập chính sách tài chính của Tenant và hạn mức ngân sách đã duyệt theo kỳ/phân xưởng.
        """
        from analytics.models import TenantFinancialSetting, PeriodApprovedBudget
        setting = TenantFinancialSetting.all_objects.filter(tenant=tenant).first()

        default_rate = float(setting.default_labor_hourly_rate) if setting else 150000.0
        default_inflation = setting.default_inflation_rate if setting else 0.045
        default_contingency = setting.default_contingency_rate if setting else 0.05
        spare_ratio = setting.critical_spare_part_ratio if setting else 0.05

        pab_val = None
        is_manual = False
        if period:
            pab_qs = PeriodApprovedBudget.all_objects.filter(tenant=tenant, period=period)
            if cost_center:
                pab_qs = pab_qs.filter(cost_center=cost_center)
            else:
                pab_qs = pab_qs.filter(cost_center__isnull=True)
            pab = pab_qs.first()
            if pab:
                pab_val = float(pab.approved_budget)
                is_manual = pab.is_manually_approved

        return {
            "defaultLaborHourlyRate": default_rate,
            "defaultInflationRatePercent": round(default_inflation * 100.0, 1),
            "defaultContingencyRatePercent": round(default_contingency * 100.0, 1),
            "criticalSparePartRatioPercent": round(spare_ratio * 100.0, 1),
            "approvedBudget": pab_val,
            "isManuallyApproved": is_manual,
            "currency": setting.currency if setting else "VND"
        }

    @classmethod
    @transaction.atomic
    def update_financial_settings(cls, tenant, data: Dict[str, Any], user=None) -> Dict[str, Any]:
        """
        Cập nhật cấu hình tài chính linh hoạt cấp Tenant và lưu hạn mức ngân sách được duyệt thực tế.
        Xác thực chặt chẽ, không tự ý gán đè số 0 hợp lệ thành mặc định.
        """
        from analytics.models import TenantFinancialSetting, PeriodApprovedBudget
        setting, _ = TenantFinancialSetting.all_objects.get_or_create(tenant=tenant)

        if "defaultLaborHourlyRate" in data and data["defaultLaborHourlyRate"] is not None:
            raw_rate = str(data["defaultLaborHourlyRate"]).replace(',', '').replace(' ', '')
            try:
                dec_rate = Decimal(raw_rate)
                if dec_rate < 0:
                    raise ValueError("Đơn giá giờ công không được là số âm.")
                setting.default_labor_hourly_rate = dec_rate
            except Exception as e:
                raise ValueError(f"Đơn giá giờ công không hợp lệ: {e}")

        if "defaultInflationRate" in data and data["defaultInflationRate"] is not None:
            try:
                val = float(data["defaultInflationRate"])
                if val < 0 or val > 100:
                    raise ValueError("Tỷ lệ lạm phát phải từ 0% đến 100%.")
                setting.default_inflation_rate = val / 100.0 if val > 1.0 else val
            except Exception as e:
                raise ValueError(f"Tỷ lệ lạm phát không hợp lệ: {e}")

        if "defaultContingencyRate" in data and data["defaultContingencyRate"] is not None:
            try:
                val = float(data["defaultContingencyRate"])
                if val < 0 or val > 100:
                    raise ValueError("Tỷ lệ dự phòng rủi ro phải từ 0% đến 100%.")
                setting.default_contingency_rate = val / 100.0 if val > 1.0 else val
            except Exception as e:
                raise ValueError(f"Tỷ lệ dự phòng không hợp lệ: {e}")

        if "criticalSparePartRatio" in data and data["criticalSparePartRatio"] is not None:
            try:
                val = float(data["criticalSparePartRatio"])
                if val < 0 or val > 100:
                    raise ValueError("Tỷ lệ linh kiện cốt lõi phải từ 0% đến 100%.")
                setting.critical_spare_part_ratio = val / 100.0 if val > 1.0 else val
            except Exception as e:
                raise ValueError(f"Tỷ lệ linh kiện cốt lõi không hợp lệ: {e}")

        setting.save()

        period = data.get("period")
        cost_center = data.get("costCenter") or data.get("cost_center") or None
        approved_budget_raw = data.get("approvedBudget") or data.get("approved_budget")

        if period and approved_budget_raw is not None and str(approved_budget_raw).strip() != '':
            raw_app = str(approved_budget_raw).replace(',', '').replace(' ', '')
            if raw_app.count('.') > 1:
                raw_app = raw_app.replace('.', '')
            try:
                dec_app = Decimal(raw_app)
                if dec_app < 0:
                    raise ValueError("Hạn mức ngân sách duyệt không được là số âm.")
                PeriodApprovedBudget.all_objects.update_or_create(
                    tenant=tenant,
                    period=period,
                    cost_center=cost_center,
                    defaults={
                        "approved_budget": dec_app,
                        "is_manually_approved": True,
                        "approved_by": user if user and user.is_authenticated else None,
                        "notes": data.get("notes")
                    }
                )
            except Exception as e:
                raise ValueError(f"Hạn mức ngân sách duyệt không hợp lệ: {e}")

        return cls.get_financial_settings(tenant, period=period, cost_center=cost_center)

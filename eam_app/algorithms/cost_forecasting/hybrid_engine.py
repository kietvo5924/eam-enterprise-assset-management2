"""
Động cơ Lập Ngân Sách Lai Ghép Hai Nhịp (Two-Step Hybrid Budgeting Engine) (Task 11.6).
Tách bạch ngân sách bảo trì định kỳ xác định (Deterministic PM) và ngân sách sự cố (Stochastic CM QRF),
kết hợp chỉ số trượt giá lạm phát, quỹ dự phòng rủi ro và cơ chế Fallback an toàn.
"""
import calendar
import datetime
import math
import numpy as np
from decimal import Decimal
from typing import Dict, List, Optional, Any, Tuple

from django.utils import timezone
from django.db.models import Sum, Q

from maintenance.models import PmPlan, PmPlanAssignment, PmPlanMaterial
from assets.models import Asset
from algorithms.cost_forecasting.constants import (
    DEFAULT_INFLATION_RATE,
    DEFAULT_CONTINGENCY_BUFFER_RATE,
    DEFAULT_LABOR_HOURLY_RATE,
    WARNING_BUDGET_USAGE_RATIO,
    CRITICAL_BUDGET_USAGE_RATIO,
    MIN_MONTHS_TRAINING_DATA,
    MIN_HISTORICAL_PERIODS_FOR_ML
)
from algorithms.cost_forecasting.feature_pipeline import CostFeaturePipeline
from algorithms.cost_forecasting.qrf_model import QuantileRegressionForestEngine
from workorders.models import WorkOrder


def round_vnd(val: Decimal | float | int) -> Decimal:
    """Làm tròn tiền tệ VNĐ không có phần thập phân theo chuẩn ROUND_HALF_UP."""
    if val is None:
        return Decimal('0')
    d = Decimal(str(val)) if not isinstance(d := val, Decimal) else d
    return d.quantize(Decimal('1'), rounding='ROUND_HALF_UP')


class HybridBudgetingEngine:
    """
    Engine thực hiện quy trình dự báo tài chính hai nhịp kết hợp PM và CM.
    """

    @classmethod
    def calculate_deterministic_pm_budget(
        cls,
        tenant,
        start_date: datetime.date,
        end_date: datetime.date,
        cost_center: Optional[str] = None,
        hourly_rate: Optional[Decimal] = None
    ) -> Decimal:
        """
        Nhịp 1: Tính toán chính xác 100% ngân sách bảo trì định kỳ PM trong kỳ tới.
        Dựa trên các PmPlanAssignment đang ACTIVE, định mức linh kiện PmPlanMaterial
        và đơn giá giờ công thợ cấu hình động cấp Tenant.
        """
        if hourly_rate is None:
            from analytics.models import TenantFinancialSetting
            setting = TenantFinancialSetting.all_objects.filter(tenant=tenant).first()
            hourly_rate = setting.default_labor_hourly_rate if setting else DEFAULT_LABOR_HOURLY_RATE

        disposed_asset_ids = set(Asset.all_objects.filter(
            tenant=tenant,
            status__in=['DISPOSED', 'RETIRED', 'SCRAPPED', 'SOLD']
        ).values_list('id', flat=True))

        assignments_qs = PmPlanAssignment.all_objects.filter(
            tenant=tenant,
            status='ACTIVE'
        ).exclude(asset_id__in=disposed_asset_ids).select_related('pm_plan', 'asset').prefetch_related('pm_plan__materials__spare_part')

        if cost_center:
            assignments_qs = assignments_qs.filter(asset__location__name=cost_center)

        total_pm_cost = Decimal('0')

        for assign in assignments_qs:
            plan = assign.pm_plan
            if not plan.is_active:
                continue

            # Miễn trừ kích hoạt nếu có lệnh bảo trì đang tồn đọng
            if plan.suppress_if_pending:
                pending_pm = WorkOrder.all_objects.filter(
                    tenant=tenant,
                    asset=assign.asset,
                    type='PREVENTIVE',
                    status__in=['CREATED', 'ASSIGNED', 'IN_PROGRESS', 'ON_HOLD']
                ).exists()
                if pending_pm:
                    continue

            val = float(plan.interval_value or 30.0)
            unit = (plan.interval_unit or 'DAYS').upper()

            if unit == 'DAYS':
                cycle_days = max(1.0, val)
            elif unit == 'WEEKS':
                cycle_days = max(1.0, val * 7.0)
            elif unit == 'MONTHS':
                cycle_days = max(1.0, val * 30.0)
            elif unit == 'YEARS':
                cycle_days = max(1.0, val * 365.0)
            else:
                cycle_days = 30.0

            # Xác định mốc thời gian cơ sở
            if assign.last_triggered_at:
                ref_date = assign.last_triggered_at.date()
            elif assign.assigned_at:
                ref_date = assign.assigned_at.date()
            else:
                ref_date = plan.created_at.date() if hasattr(plan, 'created_at') and plan.created_at else start_date

            # Tính các lần kích hoạt đến hạn thực tế trong kỳ [start_date, end_date]
            next_due = ref_date + datetime.timedelta(days=int(cycle_days))
            while next_due < start_date:
                next_due += datetime.timedelta(days=int(cycle_days))

            occurrences = 0
            while start_date <= next_due <= end_date:
                occurrences += 1
                next_due += datetime.timedelta(days=int(cycle_days))

            if occurrences <= 0:
                continue

            # Chi phí vật tư định mức tiêu chuẩn
            materials_cost = Decimal('0')
            for mat in plan.materials.all().select_related('spare_part'):
                qty = mat.quantity or Decimal('1.0')
                u_cost = mat.spare_part.unit_cost or Decimal('0')
                materials_cost += (qty * u_cost)

            # Chi phí giờ công tiêu chuẩn theo đơn giá động của Tenant
            duration_mins = plan.estimated_duration_minutes or 120
            labor_hours = Decimal(str(duration_mins / 60.0))
            labor_cost = labor_hours * hourly_rate

            one_time_cost = materials_cost + labor_cost
            total_pm_cost += (one_time_cost * Decimal(str(occurrences)))

        return round_vnd(total_pm_cost)

    @classmethod
    def execute_forecast(
        cls,
        tenant,
        period_str: str,
        cost_center: Optional[str] = None,
        approved_budget: Optional[Decimal] = None,
        inflation_rate: Optional[float] = None,
        contingency_rate: Optional[float] = None,
        hourly_rate: Optional[Decimal] = None
    ) -> Dict[str, Any]:
        """
        Chạy toàn bộ quy trình dự báo lai ghép cho kỳ được chỉ định (e.g. '2026-Q4' hoặc '2026-11').
        Tự động nạp tham số tài chính cấu hình động cấp Tenant và hạn mức ngân sách phê duyệt thực tế.
        """
        today = timezone.now().date()

        # 0. Nạp cấu hình tài chính cấp Tenant (nếu chưa truyền tham số ghi đè)
        from analytics.models import TenantFinancialSetting, PeriodApprovedBudget
        setting = TenantFinancialSetting.all_objects.filter(tenant=tenant).first()

        if hourly_rate is None:
            hourly_rate = setting.default_labor_hourly_rate if setting else DEFAULT_LABOR_HOURLY_RATE
        if inflation_rate is None:
            inflation_rate = setting.default_inflation_rate if setting else DEFAULT_INFLATION_RATE
        if contingency_rate is None:
            contingency_rate = setting.default_contingency_rate if setting else DEFAULT_CONTINGENCY_BUFFER_RATE

        # 1. Xác định khung thời gian start_date, end_date của kỳ dự báo
        if '-Q' in period_str:
            # Ví dụ: 2026-Q4
            parts = period_str.split('-Q')
            y = int(parts[0])
            q = int(parts[1])
            start_month = (q - 1) * 3 + 1
            end_month = start_month + 2
            start_date = datetime.date(y, start_month, 1)
            _, last_day = calendar.monthrange(y, end_month)
            end_date = datetime.date(y, end_month, last_day)
        elif '-' in period_str:
            # Ví dụ: 2026-11
            parts = period_str.split('-')
            y = int(parts[0])
            m = int(parts[1])
            start_date = datetime.date(y, m, 1)
            _, last_day = calendar.monthrange(y, m)
            end_date = datetime.date(y, m, last_day)
        else:
            start_date = today
            end_date = today + datetime.timedelta(days=90)

        # 2. Nhịp 1: Tính toán chi phí bảo trì định kỳ PM xác định 100% theo đơn giá giờ công của Tenant
        planned_pm_cost = cls.calculate_deterministic_pm_budget(
            tenant, start_date=start_date, end_date=end_date, cost_center=cost_center, hourly_rate=hourly_rate
        )

        # 3. Trích xuất đặc trưng chuỗi thời gian đa biến (nếu kỳ hiện tại, lấy mốc thời gian cập nhật nhất)
        target_feature_date = max(today, start_date)
        feature_data = CostFeaturePipeline.extract_features(
            tenant, target_date=target_feature_date, cost_center=cost_center
        )
        feature_vector = feature_data["feature_vector"]
        historical_costs = feature_data["historical_costs"]
        backlog_count = feature_data["backlog_orders_count"]
        deferred_hours = feature_data["deferred_maintenance_hours"]
        rul_liability = feature_data["rul_critical_liability"]
        total_rav = feature_data["total_fleet_rav"]

        # Kiểm tra cờ AI Governance của Tenant và dữ liệu huấn luyện thực tế
        ai_enabled = getattr(tenant, 'enable_ai_cost_forecasting', True)

        X_real, y_real, history_records = CostFeaturePipeline.build_historical_training_dataset(
            tenant=tenant,
            reference_date=start_date,
            months_back=24,
            cost_center=cost_center
        )

        usable_samples = len(y_real)
        positive_cost_samples = sum(1 for y in y_real if y > 0)
        has_sufficient_data = (usable_samples >= MIN_HISTORICAL_PERIODS_FOR_ML and positive_cost_samples >= 3)

        top_cost_drivers = []
        is_ai_fallback = False
        fallback_reason = None
        eval_metrics = {}

        if not ai_enabled:
            is_ai_fallback = True
            forecast_method = 'DETERMINISTIC_FALLBACK'
            fallback_reason = 'AI_DISABLED'
        elif not has_sufficient_data:
            is_ai_fallback = True
            forecast_method = 'DETERMINISTIC_FALLBACK'
            fallback_reason = 'INSUFFICIENT_HISTORICAL_DATA'
        else:
            forecast_method = 'HYBRID_QRF'
            fallback_reason = None

        if not is_ai_fallback:
            # Đánh giá Backtest độc lập theo thời gian (Out-of-sample Time-Series Validation):
            # Huấn luyện trên các kỳ trước, kiểm định sai số trên các kỳ sau chưa tham gia fit
            k_test = max(3, int(len(y_real) * 0.25))
            if len(y_real) > k_test:
                X_train_split = X_real[:-k_test]
                y_train_split = y_real[:-k_test]
                X_test_split = X_real[-k_test:]
                y_test_split = y_real[-k_test:]

                backtest_engine = QuantileRegressionForestEngine()
                backtest_engine.fit(X_train_split, y_train_split)
                eval_metrics = backtest_engine.evaluate_backtest_performance(X_test_split, y_test_split)
            else:
                eval_metrics = {}

            # Huấn luyện mô hình sản xuất trên toàn bộ dữ liệu lịch sử hợp lệ
            qrf_engine = QuantileRegressionForestEngine()
            qrf_engine.fit(X_real, y_real)

            quantiles = qrf_engine.predict_quantiles(feature_vector)
            cm_p10_base = quantiles["p10"]
            cm_p50_base = quantiles["p50"]
            cm_p90_base = quantiles["p90"]

            # Nhịp 2 (Hậu xử lý tài chính - Rule 4): Tách bạch dòng vật tư (chịu lạm phát) và dòng giờ công (theo đơn giá giờ công hiện hành của Tenant)
            inflation_factor = 1.0 + float(inflation_rate)
            labor_rate_ratio = float(hourly_rate / DEFAULT_LABOR_HOURLY_RATE) if DEFAULT_LABOR_HOURLY_RATE > 0 else 1.0

            mat_weight = 0.65
            lab_weight = 0.35

            def price_cm(base_val):
                mat_cost = (base_val * mat_weight) * inflation_factor
                lab_cost = (base_val * lab_weight) * labor_rate_ratio
                return mat_cost + lab_cost

            # Quy đổi chuỗi tháng sang độ dài kỳ dự báo (Tháng vs Quý)
            period_months = 3.0 if '-Q' in period_str else 1.0
            m10 = price_cm(cm_p10_base)
            m50 = price_cm(cm_p50_base)
            m90 = price_cm(cm_p90_base)

            if period_months > 1.0:
                cm_p50 = m50 * float(period_months)
                spread_10 = (m50 - m10) * np.sqrt(float(period_months))
                spread_90 = (m90 - m50) * np.sqrt(float(period_months))
                cm_p10 = max(0.0, cm_p50 - spread_10)
                cm_p90 = cm_p50 + spread_90
            else:
                cm_p10 = m10
                cm_p50 = m50
                cm_p90 = m90

            # Cộng thêm nghĩa vụ tài chính vật tư từ Task 11.5 nếu có (nhất quán P10, P50, P90)
            if rul_liability > Decimal('0'):
                rul_liability_float = float(rul_liability)
                cm_p10 += rul_liability_float
                cm_p50 += rul_liability_float
                cm_p90 += rul_liability_float

            top_cost_drivers = qrf_engine.get_top_cost_drivers(top_n=5)
        else:
            # Cơ chế Fallback xác định an toàn (Rule 12 & Governance)
            forecast_method = 'DETERMINISTIC_FALLBACK'
            is_ai_fallback = True

            # Xác định số tháng trong kỳ dự báo để quy đổi chính xác
            period_months = 3.0 if '-Q' in period_str else 1.0

            # Lấy trung bình trượt SMA3 quy đổi theo độ dài kỳ, hoặc định mức kinh nghiệm 3.5% RAV / năm
            base_cm = Decimal('0')
            if feature_vector[3] > 0:
                base_cm = Decimal(str(feature_vector[3])) * Decimal(str(period_months))
            elif total_rav > Decimal('0'):
                base_cm = round_vnd((total_rav * Decimal('0.035') * Decimal(str(period_months))) / Decimal('12.0'))
            else:
                if planned_pm_cost > Decimal('0'):
                    base_cm = round_vnd(planned_pm_cost * Decimal('0.60'))
                else:
                    active_count = max(1, int(feature_vector[8]))
                    base_cm = Decimal(str(active_count * 2000000 * int(period_months)))

            inflation_factor = Decimal(str(1.0 + float(inflation_rate)))
            labor_rate_ratio = Decimal(str(hourly_rate / DEFAULT_LABOR_HOURLY_RATE)) if DEFAULT_LABOR_HOURLY_RATE > 0 else Decimal('1.0')
            base_mat = base_cm * Decimal('0.65') * inflation_factor
            base_lab = base_cm * Decimal('0.35') * labor_rate_ratio
            base_cm_adjusted = base_mat + base_lab

            cm_p50 = float(base_cm_adjusted)
            cm_p10 = cm_p50 * 0.85
            cm_p90 = cm_p50 * 1.25

            # Nhất quán nghĩa vụ RUL cho P10, P50, P90
            if rul_liability > Decimal('0'):
                rul_liability_float = float(rul_liability)
                cm_p10 += rul_liability_float
                cm_p50 += rul_liability_float
                cm_p90 += rul_liability_float

            top_cost_drivers = [
                {"feature": "Kế hoạch bảo trì định kỳ xác định (Deterministic PM)", "raw_key": "planned_pm", "importance": 0.45},
                {"feature": "Định mức bảo trì theo giá trị thay thế (RAV Benchmark)", "raw_key": "total_fleet_rav", "importance": 0.35},
                {"feature": "Chỉ số trượt giá lạm phát kỳ vọng", "raw_key": "inflation", "importance": 0.20}
            ]

        # 4. Quỹ dự phòng khẩn cấp & Tổng hợp ngân sách
        cm_p10_dec = round_vnd(cm_p10)
        cm_p50_dec = round_vnd(cm_p50)
        cm_p90_dec = round_vnd(cm_p90)

        contingency_buffer = round_vnd((planned_pm_cost + cm_p50_dec) * Decimal(str(contingency_rate)))

        total_forecast_p10 = round_vnd(planned_pm_cost + cm_p10_dec + contingency_buffer)
        total_forecast_median = round_vnd(planned_pm_cost + cm_p50_dec + contingency_buffer)
        total_forecast_p90 = round_vnd(planned_pm_cost + cm_p90_dec + contingency_buffer)

        # 5. So sánh hạn mức ngân sách và đánh giá cảnh báo sớm bội chi (Rule 11)
        is_manually_approved = False
        if approved_budget is not None and approved_budget > Decimal('0'):
            is_manually_approved = True
        else:
            # Tra cứu bảng PeriodApprovedBudget xem ban giám đốc đã duyệt ngân sách cho kỳ/xưởng này chưa
            pab_qs = PeriodApprovedBudget.all_objects.filter(tenant=tenant, period=period_str)
            if cost_center:
                pab_qs = pab_qs.filter(cost_center=cost_center)
            else:
                pab_qs = pab_qs.filter(cost_center__isnull=True)
            pab = pab_qs.first()

            if pab and pab.approved_budget > Decimal('0'):
                approved_budget = pab.approved_budget
                is_manually_approved = True
            else:
                # Ngân sách mặc định ước tính bằng 120% kịch bản trung vị nếu chưa cấu hình để giữ an toàn (Usage ~ 83.3% < 85% Warning)
                # Tránh việc hệ thống tự phát cảnh báo Warning mặc định khi ban giám đốc chưa thiết lập hạn mức
                approved_budget = round_vnd(total_forecast_median * Decimal('1.20'))
                is_manually_approved = False

        usage_ratio = 0.0
        if approved_budget > Decimal('0'):
            usage_ratio = round(float((total_forecast_median / approved_budget) * Decimal('100.0')), 1)

        if usage_ratio >= CRITICAL_BUDGET_USAGE_RATIO:
            budget_status = 'CRITICAL_OVERRUN'
        elif usage_ratio >= WARNING_BUDGET_USAGE_RATIO:
            budget_status = 'WARNING'
        else:
            budget_status = 'HEALTHY'

        return {
            "period": period_str,
            "costCenter": cost_center,
            "forecastMethod": forecast_method,
            "isAiFallback": is_ai_fallback,
            "fallbackReason": fallback_reason,
            "evaluationMetrics": eval_metrics,
            "isManuallyApproved": is_manually_approved,
            "approvedBudget": approved_budget,
            "plannedPmBudget": planned_pm_cost,
            "predictedCmMedian": cm_p50_dec,
            "predictedCmLowerP10": cm_p10_dec,
            "predictedCmUpperP90": cm_p90_dec,
            "contingencyBuffer": contingency_buffer,
            "totalForecastP10": total_forecast_p10,
            "totalForecastMedian": total_forecast_median,
            "totalForecastP90": total_forecast_p90,
            "budgetUsageRatio": usage_ratio,
            "budgetStatus": budget_status,
            "inflationRateApplied": inflation_rate,
            "hourlyRateApplied": float(hourly_rate),
            "backlogOrdersCount": backlog_count,
            "deferredMaintenanceHours": deferred_hours,
            "rulCriticalLiability": rul_liability,
            "topCostDrivers": top_cost_drivers,
            "totalFleetRav": total_rav
        }


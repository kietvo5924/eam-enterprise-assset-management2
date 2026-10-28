"""
Feature Engineering Pipeline cho Dự báo Chi phí & Ngân sách Bảo trì (Task 11.6).
Trích xuất 16 đặc trưng chuỗi thời gian đa biến, bóc tách nợ kỹ thuật tồn đọng,
nghĩa vụ tài chính RUL 11.5, loại trừ CapEx và cắt tỉa tài sản đã thanh lý.
"""
import calendar
import datetime
import math
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any

import numpy as np
from django.db.models import Sum, Q, Count, F
from django.utils import timezone

from assets.models import Asset, SparePart, StockTransaction
from workorders.models import WorkOrder, WorkOrderCost, LaborLog
from algorithms.cost_forecasting.constants import (
    FEATURE_NAMES,
    MIN_MONTHS_TRAINING_DATA,
    DEFAULT_LABOR_HOURLY_RATE
)


def get_actual_consumption_net_cost(tenant, start_date: datetime.date, end_date: datetime.date, cost_center: Optional[str] = None) -> Decimal:
    """
    Quy tắc 5 & 6: Tính chi phí tiêu hao thực tế (loại bỏ 100% nhập kho lưu trữ RECEIPT).
    Chỉ lấy phụ tùng đã xuất vào WorkOrder completed trừ đi nhập trả thừa,
    cộng giờ công thợ theo kế toán dồn tích, bóc tách CapEx và khấu trừ tài sản đã thanh lý.
    """
    # 1. Danh sách ID tài sản đã thanh lý cần cắt tỉa (Rule 7)
    disposed_asset_ids = Asset.all_objects.filter(
        tenant=tenant,
        status__in=['DISPOSED', 'RETIRED', 'SCRAPPED', 'SOLD']
    ).values_list('id', flat=True)

    # 2. Chi phí từ WorkOrderCost nếu đã khóa snapshot (Rule 1)
    frozen_wo_costs = WorkOrderCost.all_objects.filter(
        tenant=tenant,
        is_cost_frozen=True,
        work_order__status='COMPLETED',
        work_order__completed_at__date__gte=start_date,
        work_order__completed_at__date__lte=end_date,
        is_capital_overhaul=False
    ).exclude(work_order__asset_id__in=disposed_asset_ids)

    if cost_center:
        frozen_wo_costs = frozen_wo_costs.filter(cost_center_snapshot=cost_center)

    frozen_total = frozen_wo_costs.aggregate(s=Sum('net_cost'))['s']
    if frozen_total is not None and frozen_total > 0:
        return frozen_total

    # 3. Tính toán dồn tích trực tiếp từ StockTransaction & LaborLog (cho các WO hoàn tất)
    # Lọc giao dịch vật tư: chỉ lấy ISSUE, ADJUSTMENT, trừ RETURN gắn với WorkOrder completed
    material_qs = StockTransaction.all_objects.filter(
        tenant=tenant,
        work_order__status='COMPLETED',
        work_order__is_capitalized=False,
        issue_date__date__gte=start_date,
        issue_date__date__lte=end_date,
        transaction_type__in=['ISSUE', 'ADJUSTMENT', 'RETURN']
    ).exclude(work_order__asset_id__in=disposed_asset_ids)

    if cost_center:
        material_qs = material_qs.filter(cost_center_snapshot=cost_center)

    material_total = Decimal('0')
    for tx in material_qs:
        amt = tx.total_amount or Decimal('0')
        if tx.transaction_type == 'RETURN':
            material_total -= amt
        else:
            material_total += amt

    # Lọc giờ công thợ
    labor_qs = LaborLog.all_objects.filter(
        tenant=tenant,
        work_order__status='COMPLETED',
        work_order__is_capitalized=False,
        work_date__gte=start_date,
        work_date__lte=end_date
    ).exclude(work_order__asset_id__in=disposed_asset_ids)

    if cost_center:
        labor_qs = labor_qs.filter(cost_center_snapshot=cost_center)

    labor_total = labor_qs.aggregate(s=Sum('total_cost'))['s'] or Decimal('0')

    # Bóc tách bảo hành & bảo hiểm từ WorkOrder (nếu có)
    # Nếu chưa có bản ghi work_order_costs thì lấy gross = material + labor
    total_net = max(Decimal('0'), material_total + labor_total)
    return total_net


def count_working_days(year: int, month: int) -> int:
    """Tính số ngày làm việc thực tế trong tháng (loại trừ Thứ 7 và Chủ nhật)."""
    _, num_days = calendar.monthrange(year, month)
    working_days = 0
    for day in range(1, num_days + 1):
        dt = datetime.date(year, month, day)
        if dt.weekday() < 5:  # 0: Thứ 2, ..., 4: Thứ 6
            working_days += 1
    return working_days


class CostFeaturePipeline:
    """
    Pipeline trích xuất 16 đặc trưng chuỗi thời gian đa biến phục vụ mô hình QRF.
    """

    @classmethod
    def get_monthly_historical_costs(
        cls,
        tenant,
        reference_date: datetime.date,
        months_back: int = 12,
        cost_center: Optional[str] = None
    ) -> List[Tuple[str, Decimal]]:
        """
        Lấy danh sách (chuỗi thời gian) chi phí ròng OpEx thực tế theo từng tháng trong quá khứ.
        """
        results = []
        cur_year = reference_date.year
        cur_month = reference_date.month

        for i in range(months_back, 0, -1):
            # Tính lùi tháng
            m = cur_month - i
            y = cur_year
            while m <= 0:
                m += 12
                y -= 1

            start_d = datetime.date(y, m, 1)
            _, last_day = calendar.monthrange(y, m)
            end_d = datetime.date(y, m, last_day)

            period_label = f"{y}-{m:02d}"
            cost = get_actual_consumption_net_cost(tenant, start_d, end_d, cost_center)
            results.append((period_label, cost))

        return results

    @classmethod
    def extract_features(
        cls,
        tenant,
        target_date: Optional[datetime.date] = None,
        cost_center: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Trích xuất đầy đủ 16 đặc trưng cho kỳ dự báo tiếp theo.
        """
        if not target_date:
            target_date = timezone.now().date()

        # 1. Lấy chuỗi lịch sử 6 tháng gần nhất để tính độ trễ và trung bình trượt
        monthly_costs = cls.get_monthly_historical_costs(
            tenant, reference_date=target_date, months_back=6, cost_center=cost_center
        )
        costs_float = [float(cost) for _, cost in monthly_costs]
        while len(costs_float) < 6:
            costs_float.insert(0, 0.0)

        # 1 - 3: Lags
        net_cost_lag_1 = costs_float[-1]
        net_cost_lag_2 = costs_float[-2]
        net_cost_lag_3 = costs_float[-3]

        # 4 - 5: SMA 3 & 6
        sma_3_cost = float(np.mean(costs_float[-3:])) if len(costs_float) >= 3 else net_cost_lag_1
        sma_6_cost = float(np.mean(costs_float[-6:])) if len(costs_float) >= 6 else sma_3_cost

        # 6: Rolling Std Dev 3
        rolling_std_3 = float(np.std(costs_float[-3:])) if len(costs_float) >= 3 else 0.0

        # 7 - 8: Bẫy bảo trì hoãn lại (Deferred Maintenance Trap - Rule 3)
        # WO quá hạn chưa hoàn thành
        overdue_wo_qs = WorkOrder.all_objects.filter(
            tenant=tenant,
            deadline__lt=timezone.now(),
            status__in=['CREATED', 'ASSIGNED', 'IN_PROGRESS', 'ON_HOLD']
        )
        if cost_center:
            overdue_wo_qs = overdue_wo_qs.filter(
                Q(incident_location__name=cost_center) | Q(asset__location__name=cost_center)
            )

        backlog_orders_count = overdue_wo_qs.count()
        deferred_hours_val = overdue_wo_qs.aggregate(
            s=Sum('estimated_duration_minutes')
        )['s'] or 0
        deferred_maintenance_hours = round(float(deferred_hours_val) / 60.0, 1)

        # 9: Tổng số lượng thiết bị đang hoạt động
        active_assets_qs = Asset.all_objects.filter(
            tenant=tenant,
            status__in=['OPERATIONAL', 'OPERATING']
        )
        if cost_center:
            active_assets_qs = active_assets_qs.filter(location__name=cost_center)
        active_assets_count = active_assets_qs.count()

        # 10: Độ tuổi trung bình dàn máy móc (năm)
        assets_with_date = active_assets_qs.exclude(purchase_date__isnull=True)
        total_age_days = 0
        valid_assets_count = 0
        for ast in assets_with_date:
            age = (target_date - ast.purchase_date).days
            if age > 0:
                total_age_days += age
                valid_assets_count += 1
        avg_asset_age_years = round((total_age_days / (valid_assets_count * 365.25)), 1) if valid_assets_count > 0 else 3.5

        # 11: Tỷ lệ sự cố đột xuất 3 tháng gần nhất (Rule 8)
        recent_90d = target_date - datetime.timedelta(days=90)
        recent_wos = WorkOrder.all_objects.filter(
            tenant=tenant,
            created_at__date__gte=recent_90d
        )
        if cost_center:
            recent_wos = recent_wos.filter(
                Q(incident_location__name=cost_center) | Q(asset__location__name=cost_center)
            )
        total_recent_wos = recent_wos.count()
        cm_wos = recent_wos.filter(type__in=['CORRECTIVE', 'EMERGENCY', 'BREAKDOWN']).count()
        breakdown_cm_ratio = round(float(cm_wos) / total_recent_wos, 2) if total_recent_wos > 0 else 0.40

        # 12: Nghĩa vụ tài chính vật tư từ máy RUL Critical Task 11.5 (Rule 10)
        critical_assets = Asset.all_objects.filter(
            tenant=tenant,
            status__in=['OPERATIONAL', 'OPERATING']
        ).filter(
            Q(rul_risk_level='CRITICAL') | Q(rapid_degradation_alert=True)
        ).select_related('primary_spare_part')

        if cost_center:
            critical_assets = critical_assets.filter(location__name=cost_center)

        # Nạp cấu hình tỷ lệ linh kiện cốt lõi cấp Tenant
        from analytics.models import TenantFinancialSetting
        fin_setting = TenantFinancialSetting.all_objects.filter(tenant=tenant).first()
        spare_ratio = fin_setting.critical_spare_part_ratio if fin_setting else 0.05

        rul_critical_liability = Decimal('0')
        for ca in critical_assets:
            if ca.primary_spare_part and ca.primary_spare_part.unit_cost:
                rul_critical_liability += ca.primary_spare_part.unit_cost
            else:
                # Ước tính theo tỷ lệ nguyên giá máy thay cho số cứng 15 triệu
                base_c = ca.effective_purchase_cost or Decimal('0')
                if not isinstance(base_c, Decimal):
                    base_c = Decimal(str(base_c))
                if base_c > Decimal('0'):
                    rul_critical_liability += (base_c * Decimal(str(spare_ratio))).quantize(Decimal('1'))
                else:
                    rul_critical_liability += Decimal('5000000.00')

        # 13: Tổng giá trị thay thế toàn bộ dàn máy (Total Fleet RAV)
        total_rav_decimal = Decimal('0')
        for ast in active_assets_qs:
            base_val = ast.effective_purchase_cost
            if not isinstance(base_val, Decimal):
                base_val = Decimal(str(base_val or 0))
            cap_val = ast.capitalized_cost or Decimal('0')
            if not isinstance(cap_val, Decimal):
                cap_val = Decimal(str(cap_val or 0))
            total_rav_decimal += (base_val + cap_val)
        total_fleet_rav = float(total_rav_decimal)

        # 14: Tỷ trọng chi phí thuộc nhóm thiết bị Class A / Bad Actors (%)
        class_a_cost_ratio = 0.25 # Baseline 25% nếu chưa có sự lệch pha nghiêm trọng
        # Kiểm tra nhanh nồng độ chi phí
        if total_recent_wos > 0:
            top_asset_wos = recent_wos.values('asset_id').annotate(c=Count('id')).order_by('-c')
            if top_asset_wos.exists():
                top_1_orders = top_asset_wos.first()['c']
                class_a_cost_ratio = round(float(top_1_orders) / total_recent_wos, 2)

        # 15: Hệ số mùa vụ (Tháng 1 - 12)
        seasonality_month = float(target_date.month)

        # 16: Số ngày làm việc thực tế trong tháng
        working_days_in_month = float(count_working_days(target_date.year, target_date.month))

        feature_vector = [
            net_cost_lag_1,
            net_cost_lag_2,
            net_cost_lag_3,
            sma_3_cost,
            sma_6_cost,
            rolling_std_3,
            float(backlog_orders_count),
            deferred_maintenance_hours,
            float(active_assets_count),
            avg_asset_age_years,
            breakdown_cm_ratio,
            float(rul_critical_liability),
            total_fleet_rav,
            class_a_cost_ratio,
            seasonality_month,
            working_days_in_month
        ]

        feature_dict = dict(zip(FEATURE_NAMES, feature_vector))

        return {
            "feature_vector": feature_vector,
            "feature_dict": feature_dict,
            "backlog_orders_count": backlog_orders_count,
            "deferred_maintenance_hours": deferred_maintenance_hours,
            "rul_critical_liability": rul_critical_liability,
            "total_fleet_rav": total_rav_decimal,
            "historical_costs": monthly_costs
        }

    @classmethod
    def generate_synthetic_training_data(
        cls,
        base_features: List[float],
        base_cost: float,
        num_samples: int = 48
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Sinh tập mẫu huấn luyện tăng cường (augmented dataset) quanh vector đặc trưng hiện tại
        kết hợp tính mùa vụ và nợ kỹ thuật để huấn luyện mô hình QRF.
        """
        np.random.seed(42)
        X_samples = []
        y_samples = []

        base_f = np.array(base_features, dtype=float)
        base_c = max(1000000.0, base_cost if base_cost > 0 else 50000000.0)

        for i in range(num_samples):
            # Tạo biến thiên ngẫu nhiên có kiểm soát
            noise_scale = np.random.uniform(0.85, 1.18)
            sample_x = base_f.copy()

            # Nhiễu nợ kỹ thuật và độ trễ
            sample_x[0] = sample_x[0] * np.random.uniform(0.8, 1.2)  # lag 1
            sample_x[6] = max(0.0, sample_x[6] + np.random.randint(-4, 5)) # backlog count
            sample_x[7] = max(0.0, sample_x[7] + np.random.uniform(-15.0, 20.0)) # deferred hours
            sample_x[14] = float((i % 12) + 1) # Seasonality month

            # Chi phí thực tế tương ứng có tương quan dương với nợ kỹ thuật
            surge_multiplier = 1.0 + (sample_x[6] * 0.035) + (sample_x[7] * 0.002)
            sample_y = base_c * noise_scale * surge_multiplier

            X_samples.append(sample_x)
            y_samples.append(sample_y)

        return np.array(X_samples), np.array(y_samples)


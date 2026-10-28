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
    Tổng hợp cả Work Order đã chốt snapshot lẫn chưa chốt snapshot trong kỳ mà không cộng trùng,
    bảo toàn chi phí ròng net_cost = 0 khi được bảo hành/bảo hiểm 100%.
    """
    # 1. Danh sách ID tài sản đã thanh lý cần cắt tỉa (Rule 7)
    disposed_asset_ids = set(Asset.all_objects.filter(
        tenant=tenant,
        status__in=['DISPOSED', 'RETIRED', 'SCRAPPED', 'SOLD']
    ).values_list('id', flat=True))

    # 2. Toàn bộ Work Order hoàn tất trong kỳ (loại trừ tài sản đã thanh lý)
    completed_wos = WorkOrder.all_objects.filter(
        tenant=tenant,
        status='COMPLETED',
        completed_at__date__gte=start_date,
        completed_at__date__lte=end_date
    ).exclude(asset_id__in=disposed_asset_ids).select_related('asset', 'incident_location', 'asset__location')

    if not completed_wos.exists():
        return Decimal('0.00')

    # Bản đồ snapshot chi phí đã khóa
    frozen_costs_map = {
        fc.work_order_id: fc
        for fc in WorkOrderCost.all_objects.filter(
            tenant=tenant,
            work_order__in=completed_wos,
            is_cost_frozen=True
        )
    }

    total_net = Decimal('0.00')

    for wo in completed_wos:
        # Trường hợp 1: Đã khóa snapshot
        if wo.id in frozen_costs_map:
            fc = frozen_costs_map[wo.id]
            # Loại trừ CapEx
            if fc.is_capital_overhaul:
                continue
            # Lọc theo Cost Center snapshot
            if cost_center and fc.cost_center_snapshot != cost_center:
                continue
            total_net += (fc.net_cost or Decimal('0.00'))

        # Trường hợp 2: Chưa khóa snapshot
        else:
            # Loại trừ CapEx
            if wo.is_capitalized or wo.maintenance_action == 'CORE_REPLACEMENT':
                continue

            # Xác định Cost Center của WO
            wo_cc = getattr(wo, 'cost_center_snapshot', None)
            if not wo_cc:
                if wo.incident_location and wo.incident_location.name:
                    wo_cc = wo.incident_location.name
                elif wo.asset and wo.asset.location and wo.asset.location.name:
                    wo_cc = wo.asset.location.name

            if cost_center and wo_cc != cost_center:
                continue

            # Tính vật tư: Chỉ ISSUE, ADJUSTMENT (+), trừ RETURN (-) gắn với WO
            mat_qs = StockTransaction.all_objects.filter(
                tenant=tenant,
                work_order=wo,
                transaction_type__in=['ISSUE', 'ADJUSTMENT', 'RETURN']
            )
            mat_total = Decimal('0.00')
            for tx in mat_qs:
                amt = tx.total_amount or Decimal('0.00')
                if tx.transaction_type == 'RETURN':
                    mat_total -= amt
                else:
                    mat_total += amt

            # Tính giờ công thợ
            lab_total = LaborLog.all_objects.filter(
                tenant=tenant,
                work_order=wo
            ).aggregate(s=Sum('total_cost'))['s'] or Decimal('0.00')

            gross = max(Decimal('0.00'), mat_total + lab_total)
            w_cov = getattr(wo, 'warranty_covered_amount', None) or Decimal('0.00')
            i_cov = getattr(wo, 'insurance_covered_amount', None) or Decimal('0.00')
            net = max(Decimal('0.00'), gross - (w_cov + i_cov))

            total_net += net

    return total_net.quantize(Decimal('0.01'))


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
        # Tính toán Backlog chuẩn xác tại mốc target_date (chống rò rỉ dữ liệu tương lai)
        target_dt = timezone.make_aware(
            datetime.datetime.combine(target_date, datetime.time.max)
        ) if timezone.is_naive(datetime.datetime.combine(target_date, datetime.time.max)) else datetime.datetime.combine(target_date, datetime.time.max)

        overdue_wo_qs = WorkOrder.all_objects.filter(
            tenant=tenant,
            created_at__lte=target_dt,
            deadline__lt=target_dt
        ).filter(
            Q(completed_at__isnull=True) | Q(completed_at__gt=target_dt)
        ).exclude(
            Q(status__in=['CANCELLED', 'CANCELED']) & Q(updated_at__lte=target_dt)
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

        # 9: Tổng số lượng thiết bị đang hoạt động tại thời điểm target_date
        active_assets_qs = Asset.all_objects.filter(
            tenant=tenant
        ).filter(
            Q(purchase_date__lte=target_date) | Q(created_at__date__lte=target_date)
        ).exclude(
            Q(status__in=['DISPOSED', 'RETIRED', 'SCRAPPED', 'SOLD']) & Q(updated_at__date__lte=target_date)
        )
        if cost_center:
            active_assets_qs = active_assets_qs.filter(location__name=cost_center)
        active_assets_count = active_assets_qs.count()

        # 10: Độ tuổi trung bình dàn máy móc (năm) tính tại target_date
        assets_with_date = active_assets_qs.exclude(purchase_date__isnull=True)
        total_age_days = 0
        valid_assets_count = 0
        for ast in assets_with_date:
            age = (target_date - ast.purchase_date).days
            if age > 0:
                total_age_days += age
                valid_assets_count += 1
        if valid_assets_count > 0:
            avg_asset_age_years = round((total_age_days / (valid_assets_count * 365.25)), 1)
        else:
            # Fallback: Tính theo ngày tạo hồ sơ tài sản (created_at) tại mốc target_date
            created_age_days = 0
            created_count = 0
            for ast in active_assets_qs:
                c_date = ast.created_at.date() if hasattr(ast, 'created_at') and ast.created_at else None
                if c_date:
                    age = (target_date - c_date).days
                    if age > 0:
                        created_age_days += age
                        created_count += 1
            avg_asset_age_years = round((created_age_days / (created_count * 365.25)), 1) if created_count > 0 else 0.0

        # 11: Tỷ lệ sự cố đột xuất 3 tháng gần nhất tính ngược từ target_date (Rule 8)
        recent_90d = target_date - datetime.timedelta(days=90)
        recent_wos = WorkOrder.all_objects.filter(
            tenant=tenant,
            created_at__date__gte=recent_90d,
            created_at__date__lte=target_date
        )
        if cost_center:
            recent_wos = recent_wos.filter(
                Q(incident_location__name=cost_center) | Q(asset__location__name=cost_center)
            )
        total_recent_wos = recent_wos.count()
        cm_wos = recent_wos.filter(type__in=['CORRECTIVE', 'EMERGENCY', 'BREAKDOWN']).count()
        breakdown_cm_ratio = round(float(cm_wos) / total_recent_wos, 2) if total_recent_wos > 0 else 0.0

        # 12: Nghĩa vụ tài chính vật tư từ máy RUL Critical Task 11.5 (Rule 10)
        # Sử dụng lịch sử dự đoán RUL tại thời điểm target_date để chống rò rỉ tương lai
        from analytics.models import TenantFinancialSetting
        fin_setting = TenantFinancialSetting.all_objects.filter(tenant=tenant).first()
        spare_ratio = fin_setting.critical_spare_part_ratio if fin_setting else 0.05

        today = timezone.now().date()
        is_current_or_future = (target_date >= today.replace(day=1))
        critical_assets_list = []

        if is_current_or_future:
            critical_assets_qs = active_assets_qs.filter(
                Q(rul_risk_level='CRITICAL') | Q(rapid_degradation_alert=True)
            ).select_related('primary_spare_part')
            critical_assets_list = list(critical_assets_qs)
        else:
            # Tra cứu từ bảng AssetRulPrediction tính đến mốc target_dt
            from assets.models import AssetRulPrediction
            for ast in active_assets_qs.select_related('primary_spare_part'):
                latest_pred = AssetRulPrediction.all_objects.filter(
                    tenant=tenant,
                    asset=ast,
                    created_at__lte=target_dt
                ).order_by('-created_at').first()
                if latest_pred and latest_pred.risk_level == 'CRITICAL':
                    critical_assets_list.append(ast)

        rul_critical_liability = Decimal('0')
        for ca in critical_assets_list:
            if ca.primary_spare_part and ca.primary_spare_part.unit_cost:
                rul_critical_liability += ca.primary_spare_part.unit_cost
            else:
                base_c = ca.effective_purchase_cost or Decimal('0')
                if not isinstance(base_c, Decimal):
                    base_c = Decimal(str(base_c))
                if base_c > Decimal('0'):
                    rul_critical_liability += (base_c * Decimal(str(spare_ratio))).quantize(Decimal('1'))
                else:
                    rul_critical_liability += Decimal('0.00')

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
        # Tính theo tỷ trọng chi phí thực tế của nhóm thiết bị rủi ro nguy cấp (RUL Critical / Rapid Degradation)
        class_a_cost_ratio = 0.0
        if total_recent_wos > 0:
            bad_actor_ids = active_assets_qs.filter(
                Q(rul_risk_level='CRITICAL') | Q(rapid_degradation_alert=True)
            ).values_list('id', flat=True)

            recent_costs_all = WorkOrderCost.all_objects.filter(
                tenant=tenant,
                work_order__in=recent_wos,
                is_capital_overhaul=False
            ).aggregate(s=Sum('net_cost'))['s'] or Decimal('0')

            recent_costs_bad = WorkOrderCost.all_objects.filter(
                tenant=tenant,
                work_order__in=recent_wos,
                work_order__asset_id__in=bad_actor_ids,
                is_capital_overhaul=False
            ).aggregate(s=Sum('net_cost'))['s'] or Decimal('0')

            if recent_costs_all > Decimal('0'):
                class_a_cost_ratio = round(float(recent_costs_bad / recent_costs_all), 2)
            else:
                class_a_wos = recent_wos.filter(asset_id__in=bad_actor_ids).count()
                class_a_cost_ratio = round(float(class_a_wos) / total_recent_wos, 2)

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
    def build_historical_training_dataset(
        cls,
        tenant,
        reference_date: Optional[datetime.date] = None,
        months_back: int = 24,
        cost_center: Optional[str] = None
    ) -> Tuple[np.ndarray, np.ndarray, List[Dict[str, Any]]]:
        """
        Xây dựng tập dữ liệu huấn luyện ML thực sự từ chuỗi thời gian lịch sử:
        Mỗi mẫu (X_t, y_t):
        - Target y_t: Chi phí tiêu hao thực tế của tháng t.
        - Features X_t: 16 đặc trưng tính toán nghiêm ngặt tại thời điểm bắt đầu tháng t
          (chỉ dùng thông tin trước ngày 1 của tháng t, không data leakage tương lai).
        Chỉ trả về các mẫu có dữ liệu lịch sử hợp lệ.
        """
        if not reference_date:
            reference_date = timezone.now().date()

        X_samples = []
        y_samples = []
        metadata = []

        cur_year = reference_date.year
        cur_month = reference_date.month
        tenant_created_date = tenant.created_at.date() if hasattr(tenant, 'created_at') and tenant.created_at else None

        for i in range(months_back, 0, -1):
            m = cur_month - i
            y = cur_year
            while m <= 0:
                m += 12
                y -= 1

            start_t = datetime.date(y, m, 1)
            _, last_day = calendar.monthrange(y, m)
            end_t = datetime.date(y, m, last_day)

            # Kiểm tra xem trong kỳ này có tài sản nào thuộc đối tượng bảo trì hay không (chống coi kỳ chưa có thiết bị là nhãn 0)
            assets_existed = Asset.all_objects.filter(
                tenant=tenant
            ).filter(
                Q(purchase_date__lte=end_t) | (Q(purchase_date__isnull=True) & Q(created_at__date__lte=end_t))
            ).exists()
            if not assets_existed:
                continue

            # Target y_t: Chi phí thực tế tháng t
            target_cost = get_actual_consumption_net_cost(tenant, start_t, end_t, cost_center)

            # Feature vector X_t trích xuất tại ngày đầu tháng t (start_t)
            feat_data = cls.extract_features(
                tenant=tenant,
                target_date=start_t,
                cost_center=cost_center
            )
            vec = feat_data["feature_vector"]

            X_samples.append(vec)
            y_samples.append(float(target_cost))
            metadata.append({
                "period": f"{y}-{m:02d}",
                "target_cost": float(target_cost),
                "features": feat_data["feature_dict"]
            })

        X_arr = np.array(X_samples, dtype=float) if X_samples else np.empty((0, len(FEATURE_NAMES)))
        y_arr = np.array(y_samples, dtype=float) if y_samples else np.empty((0,))

        return X_arr, y_arr, metadata

    @classmethod
    def generate_synthetic_training_data(
        cls,
        base_features: List[float],
        base_cost: float,
        num_samples: int = 48
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        [CHỈ DÙNG TRONG UNIT TEST / BENCHMARK]:
        Sinh dữ liệu mô phỏng tăng cường quanh một vector đặc trưng để kiểm thử thuật toán.
        Tuyệt đối không sử dụng trong luồng chạy dự báo thực tế (production forecasting).
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


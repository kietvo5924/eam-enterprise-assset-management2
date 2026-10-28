"""
Kiểm định Phân bổ Chi phí Pareto (80/20 Test) & Nhận diện Thiết bị "Quả chanh" (Lemon Assets) (Task 11.6).
Tích hợp chỉ số Tỷ lệ Sửa chữa trên Giá trị Thay thế (RRR Bad Actor >= 70%)
và sinh khuyến nghị XAI đề xuất thanh lý cắt giảm ngân sách.
"""
from decimal import Decimal
from typing import Dict, List, Optional, Any
from datetime import timedelta
from django.utils import timezone
from django.db.models import Sum, Q

from assets.models import Asset, StockTransaction
from workorders.models import WorkOrder, WorkOrderCost, LaborLog
from algorithms.cost_forecasting.constants import (
    LEMON_ASSET_COST_CONCENTRATION_THRESHOLD,
    LEMON_ASSET_PERCENT_THRESHOLD,
    RRR_BAD_ACTOR_THRESHOLD
)


class LemonAssetDetector:
    """
    Bộ kiểm toán Pareto phát hiện thiết bị "Quả chanh" (Lemon Assets / Bad Actors).
    """

    @classmethod
    def audit_lemon_assets(
        cls,
        tenant,
        cost_center: Optional[str] = None,
        days_window: int = 365
    ) -> Dict[str, Any]:
        """
        Kiểm định phân bổ chi phí trên toàn bộ danh mục tài sản trong khoảng thời gian xác định.
        """
        cutoff_date = timezone.now().date() - timedelta(days=days_window)

        # 1. Danh sách tài sản đang vận hành (loại trừ đã thanh lý)
        assets_qs = Asset.all_objects.filter(
            tenant=tenant
        ).exclude(status__in=['DISPOSED', 'RETIRED', 'SCRAPPED', 'SOLD'])

        if cost_center:
            assets_qs = assets_qs.filter(location__name=cost_center)

        total_assets_count = assets_qs.count()
        if total_assets_count == 0:
            return {
                "isConcentrationDetected": False,
                "totalBadActorsCount": 0,
                "lemonAssets": [],
                "topLemonAsset": None
            }

        # 2. Tổng hợp chi phí OpEx theo từng tài sản
        asset_costs: Dict[str, Dict[str, Any]] = {}
        for ast in assets_qs:
            asset_costs[str(ast.id)] = {
                "asset": ast,
                "cost": Decimal('0')
            }

        # Truy vấn từ WorkOrderCost nếu có
        frozen_costs = WorkOrderCost.all_objects.filter(
            tenant=tenant,
            is_cost_frozen=True,
            is_capital_overhaul=False,
            work_order__status='COMPLETED',
            work_order__completed_at__date__gte=cutoff_date,
            work_order__asset_id__in=asset_costs.keys()
        ).select_related('work_order')

        if cost_center:
            frozen_costs = frozen_costs.filter(cost_center_snapshot=cost_center)

        for fc in frozen_costs:
            ast_id = str(fc.work_order.asset_id)
            if ast_id in asset_costs:
                asset_costs[ast_id]["cost"] += (fc.net_cost or Decimal('0'))

        # Đồng thời kiểm tra các WorkOrder chưa có WorkOrderCost
        processed_wo_ids = set(frozen_costs.values_list('work_order_id', flat=True))
        other_wos = WorkOrder.all_objects.filter(
            tenant=tenant,
            status='COMPLETED',
            is_capitalized=False,
            completed_at__date__gte=cutoff_date,
            asset_id__in=asset_costs.keys()
        ).exclude(id__in=processed_wo_ids)

        if cost_center:
            other_wos = other_wos.filter(
                Q(incident_location__name=cost_center) | Q(asset__location__name=cost_center)
            )

        for wo in other_wos:
            ast_id = str(wo.asset_id)
            wo_cost = wo.actual_cost or Decimal('0')
            if ast_id in asset_costs:
                asset_costs[ast_id]["cost"] += wo_cost

        # 3. Tính tổng chi phí toàn xưởng / toàn công ty
        total_maintenance_cost = sum((item["cost"] for item in asset_costs.values()), Decimal('0'))

        if total_maintenance_cost <= Decimal('0'):
            return {
                "isConcentrationDetected": False,
                "totalBadActorsCount": 0,
                "lemonAssets": [],
                "topLemonAsset": None
            }

        # 4. Sắp xếp tài sản theo chi phí giảm dần
        sorted_assets = sorted(asset_costs.values(), key=lambda x: x["cost"], reverse=True)

        lemon_list = []
        is_concentration_detected = False
        top_lemon_dict = None

        running_cost = Decimal('0')
        for rank, item in enumerate(sorted_assets, start=1):
            ast: Asset = item["asset"]
            cost: Decimal = item["cost"]
            if cost <= Decimal('0'):
                continue

            running_cost += cost
            cost_pct = round(float((cost / total_maintenance_cost) * Decimal('100.0')), 1)
            cumulative_cost_pct = round(float((running_cost / total_maintenance_cost) * Decimal('100.0')), 1)
            asset_rank_pct = round((rank / total_assets_count), 3)

            # Tính RRR (Repair-to-Replacement Ratio)
            base_cost = ast.effective_purchase_cost
            if not isinstance(base_cost, Decimal):
                base_cost = Decimal(str(base_cost or 0))

            rrr_pct = 0.0
            if base_cost > Decimal('0'):
                rrr_pct = round(float((cost / base_cost) * Decimal('100.0')), 1)

            # Điều kiện nhận diện Lemon Asset / Bad Actor:
            # 1. RRR >= 70%
            # 2. Hoặc tài sản đơn lẻ chiếm >= 30% tổng chi phí
            # 3. Hoặc top <= 5% tài sản chiếm >= 50% chi phí
            is_bad_actor = (rrr_pct >= RRR_BAD_ACTOR_THRESHOLD)
            is_pareto_skew = (asset_rank_pct <= LEMON_ASSET_PERCENT_THRESHOLD and cumulative_cost_pct >= (LEMON_ASSET_COST_CONCENTRATION_THRESHOLD * 100)) or (cost_pct >= 35.0)

            if is_bad_actor or is_pareto_skew:
                is_concentration_detected = True
                recommendation = (
                    f"Thiết bị chiếm {cost_pct}% chi phí sửa chữa toàn danh mục"
                    + (f" (RRR = {rrr_pct}% nguyên giá)." if rrr_pct > 0 else ".")
                    + f" Đề xuất ban giám đốc xem xét phương án thanh lý/thay mới để giảm ngay {int(cost):,} VNĐ dự báo ngân sách."
                )

                lemon_entry = {
                    "assetId": str(ast.id),
                    "assetName": ast.name,
                    "costCenter": ast.location.name if ast.location else "Chung",
                    "totalMaintenanceCost": float(cost),
                    "historicalCostContributionPercent": cost_pct,
                    "rrrPercent": rrr_pct,
                    "isBadActor": is_bad_actor,
                    "isParetoSkew": is_pareto_skew,
                    "recommendation": recommendation
                }
                lemon_list.append(lemon_entry)

                if top_lemon_dict is None:
                    top_lemon_dict = lemon_entry

        return {
            "isConcentrationDetected": is_concentration_detected,
            "totalBadActorsCount": len(lemon_list),
            "lemonAssets": lemon_list,
            "topLemonAsset": top_lemon_dict,
            "totalAnalyzedAssets": total_assets_count,
            "totalFleetCost": float(total_maintenance_cost)
        }


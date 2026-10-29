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

        # 1. Danh sách tài sản đã thanh lý cần cắt tỉa triệt để (Rule 7)
        disposed_asset_ids = set(Asset.all_objects.filter(
            tenant=tenant,
            status__in=['DISPOSED', 'RETIRED', 'SCRAPPED', 'SOLD']
        ).values_list('id', flat=True))

        assets_base_qs = Asset.all_objects.filter(
            tenant=tenant
        ).exclude(id__in=disposed_asset_ids)

        if cost_center:
            current_location_assets = assets_base_qs.filter(location__name=cost_center)
        else:
            current_location_assets = assets_base_qs

        # 2. Thu thập chi phí theo đúng snapshot trung tâm chi phí phát sinh
        # Tránh lỗi tài sản điều chuyển khiến chi phí biến mất khỏi cả hai trung tâm chi phí
        frozen_costs = WorkOrderCost.all_objects.filter(
            tenant=tenant,
            is_cost_frozen=True,
            is_capital_overhaul=False,
            work_order__status='COMPLETED',
            work_order__completed_at__date__gte=cutoff_date
        ).exclude(
            work_order__asset_id__in=disposed_asset_ids
        ).select_related('work_order', 'work_order__asset')

        if cost_center:
            frozen_costs = frozen_costs.filter(cost_center_snapshot=cost_center)

        processed_wo_ids = set(frozen_costs.values_list('work_order_id', flat=True))

        other_wos = WorkOrder.all_objects.filter(
            tenant=tenant,
            status='COMPLETED',
            is_capitalized=False,
            completed_at__date__gte=cutoff_date
        ).exclude(
            id__in=processed_wo_ids
        ).exclude(
            asset_id__in=disposed_asset_ids
        ).select_related('asset', 'incident_location', 'asset__location')

        if cost_center:
            # Ưu tiên incident_location tại thời điểm phát sinh sự cố, chỉ fallback sang asset.location khi incident_location là NULL
            # Tránh lỗi tính trùng chi phí khi tài sản đã điều chuyển sang xưởng mới
            other_wos = other_wos.filter(
                Q(incident_location__name=cost_center) |
                (Q(incident_location__isnull=True) & Q(asset__location__name=cost_center))
            )

        # Tập hợp tất cả các tài sản liên quan (loại trừ tài sản đã thanh lý)
        relevant_asset_ids = set(current_location_assets.values_list('id', flat=True))
        for fc in frozen_costs:
            if fc.work_order and fc.work_order.asset_id and fc.work_order.asset_id not in disposed_asset_ids:
                relevant_asset_ids.add(fc.work_order.asset_id)
        for wo in other_wos:
            if wo.asset_id and wo.asset_id not in disposed_asset_ids:
                relevant_asset_ids.add(wo.asset_id)

        all_relevant_assets = {
            str(ast.id): ast for ast in Asset.all_objects.filter(
                id__in=relevant_asset_ids
            ).exclude(id__in=disposed_asset_ids)
        }

        total_assets_count = len(all_relevant_assets)
        if total_assets_count == 0:
            return {
                "isConcentrationDetected": False,
                "totalBadActorsCount": 0,
                "lemonAssets": [],
                "topLemonAsset": None
            }

        asset_costs: Dict[str, Dict[str, Any]] = {
            ast_id: {"asset": ast_obj, "cost": Decimal('0')}
            for ast_id, ast_obj in all_relevant_assets.items()
        }

        for fc in frozen_costs:
            if fc.work_order and fc.work_order.asset_id:
                ast_id = str(fc.work_order.asset_id)
                if ast_id in asset_costs:
                    asset_costs[ast_id]["cost"] += (fc.net_cost or Decimal('0'))

        for wo in other_wos:
            if wo.asset_id:
                ast_id = str(wo.asset_id)
                if ast_id in asset_costs:
                    asset_costs[ast_id]["cost"] += (wo.actual_cost or Decimal('0'))

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

            # Tính RRR (Repair-to-Replacement Ratio - Rule 7):
            # Tỷ lệ giữa chi phí sửa chữa lũy kế trên giá trị thay thế/nguyên giá
            base_cost = ast.effective_purchase_cost
            if not isinstance(base_cost, Decimal):
                base_cost = Decimal(str(base_cost or 0))

            rrr_pct = 0.0
            if base_cost > Decimal('0'):
                lifecycle_frozen = WorkOrderCost.all_objects.filter(
                    tenant=tenant,
                    work_order__asset=ast,
                    work_order__status='COMPLETED',
                    is_capital_overhaul=False
                ).aggregate(s=Sum('net_cost'))['s'] or Decimal('0')
                effective_repair_cost = max(cost, lifecycle_frozen)
                rrr_pct = round(float((effective_repair_cost / base_cost) * Decimal('100.0')), 1)

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
                    + (f" (Tỷ lệ sửa chữa/nguyên giá RRR = {rrr_pct}%)." if rrr_pct > 0 else ".")
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


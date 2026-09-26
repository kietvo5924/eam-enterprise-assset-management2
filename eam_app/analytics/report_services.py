import logging
from datetime import datetime, date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Any, Optional

from django.db import models
from django.db.models import Sum, Count, Q, F, Avg
from django.utils import timezone

from assets.models import Asset, SparePart, StockTransaction, Location
from workorders.models import WorkOrder, WorkOrderMaterial, LaborLog

logger = logging.getLogger(__name__)

def round_vnd(val: Decimal | float | int) -> Decimal:
    """
    Rounds monetary amounts in VNĐ using ROUND_HALF_UP without decimals.
    """
    if val is None:
        return Decimal('0')
    if not isinstance(val, Decimal):
        val = Decimal(str(val))
    return val.quantize(Decimal('1'), rounding=ROUND_HALF_UP)


def parse_date_safe(val: Any) -> Optional[date]:
    """
    Safely parses input to a datetime.date object.
    Supports datetime.date, datetime.datetime, ISO strings (with or without time/Z),
    and common date formats (YYYY-MM-DD, DD/MM/YYYY).
    """
    if val is None or val == "":
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val

    val_str = str(val).strip()
    if len(val_str) >= 10 and val_str[4] == '-' and val_str[7] == '-':
        try:
            return datetime.strptime(val_str[:10], '%Y-%m-%d').date()
        except ValueError:
            pass

    if len(val_str) >= 10 and val_str[2] == '/' and val_str[5] == '/':
        try:
            return datetime.strptime(val_str[:10], '%d/%m/%Y').date()
        except ValueError:
            pass

    try:
        from django.utils.dateparse import parse_date, parse_datetime
        parsed = parse_date(val_str)
        if parsed:
            return parsed
        parsed_dt = parse_datetime(val_str)
        if parsed_dt:
            return parsed_dt.date()
    except Exception:
        pass

    return None


class AssetValuationEngine:
    """
    Engine for Asset Valuation, Straight-Line Depreciation (VAS 03 Floor Guardrail),
    and RRR >= 70% Capitalization Audit.
    """

    @classmethod
    def get_asset_valuation_data(
        cls,
        tenant,
        category_id: Optional[str] = None,
        location_id: Optional[str] = None,
        as_of_date: Optional[date] = None,
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        if as_of_date is None:
            as_of_date = timezone.now().date()

        queryset = Asset.all_objects.filter(tenant=tenant)
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        if location_id:
            queryset = queryset.filter(location_id=location_id)
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(serial_number__icontains=search) | Q(qr_code__icontains=search))

        total_original_cost = Decimal('0')
        total_capex = Decimal('0')
        total_accumulated_depreciation = Decimal('0')
        total_net_book_value = Decimal('0')
        bad_actor_count = 0

        rows = []
        chart_categories = {}

        for asset in queryset.select_related('category', 'location').iterator(chunk_size=1000):
            # Rule 1 & Rule 2: Cost basis = purchase_cost + capitalized_cost
            base_cost = asset.effective_purchase_cost
            if not isinstance(base_cost, Decimal):
                base_cost = Decimal(str(base_cost or 0))

            capex_cost = asset.capitalized_cost or Decimal('0')
            if not isinstance(capex_cost, Decimal):
                capex_cost = Decimal(str(capex_cost))

            salvage_val = asset.salvage_value or Decimal('0')
            if not isinstance(salvage_val, Decimal):
                salvage_val = Decimal(str(salvage_val))

            total_cost_basis = base_cost + capex_cost
            depreciable_amount = max(Decimal('0'), total_cost_basis - salvage_val)

            useful_years = max(1, asset.useful_life_years or 5)
            useful_months = useful_years * 12

            # Determine start date for depreciation
            start_date = asset.capitalized_date if (asset.capitalized_date and capex_cost > 0) else asset.purchase_date
            if not start_date:
                start_date = asset.created_at.date() if asset.created_at else as_of_date

            # Calculate months in service
            months_in_service = max(0, (as_of_date.year - start_date.year) * 12 + (as_of_date.month - start_date.month))
            if as_of_date.day < start_date.day:
                months_in_service = max(0, months_in_service - 1)

            # Straight line monthly rate
            monthly_deprec = depreciable_amount / Decimal(str(useful_months)) if useful_months > 0 else Decimal('0')
            
            # Rule 1: Floor guardrail - Accumulated depreciation cannot exceed depreciable_amount
            accumulated_deprec = min(depreciable_amount, monthly_deprec * Decimal(str(months_in_service)))
            accumulated_deprec = round_vnd(accumulated_deprec)

            # Net Book Value = max(Cost basis - Accumulated deprec, Salvage Value)
            net_book_value = max(salvage_val, total_cost_basis - accumulated_deprec)
            net_book_value = round_vnd(net_book_value)

            is_fully_depreciated = months_in_service >= useful_months
            financial_status = "Đã khấu hao hết - Đang vận hành" if is_fully_depreciated else "Đang trích khấu hao"

            # Rule 2: RRR calculation excluding CAPEX work orders
            # Fetch all completed or in-progress work orders for this asset that are NOT capitalized
            opex_orders = WorkOrder.all_objects.filter(
                tenant=tenant,
                asset=asset,
                is_capitalized=False
            ).exclude(status='CANCELLED')

            total_opex = Decimal('0')
            for wo in opex_orders:
                if wo.actual_cost is not None:
                    total_opex += Decimal(str(wo.actual_cost))
                else:
                    mat_cost = wo.materials.aggregate(s=Sum('actual_cost'))['s'] or Decimal('0')
                    labor_cost = wo.labor_logs.aggregate(s=Sum('total_cost'))['s'] or Decimal('0')
                    total_opex += (Decimal(str(mat_cost)) + Decimal(str(labor_cost)))

            total_opex = round_vnd(total_opex)

            # Replacement value comparison: use base_cost if available
            if base_cost > 0:
                rrr_percent = round(float((total_opex / base_cost) * Decimal('100')), 2)
                is_bad_actor = (rrr_percent >= 70.0)
                if is_bad_actor:
                    bad_actor_count += 1
                    recommendation = "CẢNH BÁO: Đề xuất thanh lý / Thay thế mới (RRR >= 70%)"
                else:
                    recommendation = "Bình thường"
            else:
                rrr_percent = 0.0
                is_bad_actor = False
                recommendation = "Chưa có thông tin nguyên giá để tính RRR" if total_opex > 0 else "Bình thường"

            total_original_cost += base_cost
            total_capex += capex_cost
            total_accumulated_depreciation += accumulated_deprec
            total_net_book_value += net_book_value

            cat_name = asset.category.name if asset.category else "Chưa phân loại"
            chart_categories[cat_name] = chart_categories.get(cat_name, Decimal('0')) + net_book_value

            rows.append({
                "id": str(asset.id),
                "name": asset.name,
                "serialNumber": asset.serial_number or "N/A",
                "categoryName": cat_name,
                "locationName": asset.location.name if asset.location else "N/A",
                "purchaseDate": str(asset.purchase_date) if asset.purchase_date else "N/A",
                "originalCost": float(base_cost),
                "capexCost": float(capex_cost),
                "totalCostBasis": float(total_cost_basis),
                "salvageValue": float(salvage_val),
                "usefulLifeYears": useful_years,
                "monthsInService": months_in_service,
                "accumulatedDepreciation": float(accumulated_deprec),
                "netBookValue": float(net_book_value),
                "financialStatus": financial_status,
                "accumulatedOpex": float(total_opex),
                "rrrPercent": rrr_percent,
                "isBadActor": is_bad_actor,
                "recommendation": recommendation
            })

        chart_series = [
            {"name": k, "value": float(v)} for k, v in sorted(chart_categories.items(), key=lambda x: x[1], reverse=True)[:6]
        ]

        return {
            "summary": {
                "totalAssets": len(rows),
                "totalOriginalCost": float(round_vnd(total_original_cost)),
                "totalCapex": float(round_vnd(total_capex)),
                "totalAccumulatedDepreciation": float(round_vnd(total_accumulated_depreciation)),
                "totalNetBookValue": float(round_vnd(total_net_book_value)),
                "badActorCount": bad_actor_count
            },
            "chartSeries": chart_series,
            "items": rows
        }


class MaintenancePerformanceEngine:
    """
    Engine for Maintenance Performance, SLA on-time rate, MTTR,
    and PM Compliance Rate adhering to the 10% tolerance rule & overlap suppression.
    """

    @classmethod
    def get_performance_data(
        cls,
        tenant,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        location_id: Optional[str] = None
    ) -> Dict[str, Any]:
        now = timezone.now().date()
        if not date_from:
            date_from = now.replace(day=1)
        if not date_to:
            date_to = now

        wo_qs = WorkOrder.all_objects.filter(tenant=tenant).select_related('asset', 'assigned_to')
        if date_from and date_to:
            wo_qs = wo_qs.filter(
                Q(created_at__date__gte=date_from, created_at__date__lte=date_to) |
                Q(deadline__date__gte=date_from, deadline__date__lte=date_to) |
                Q(completed_at__date__gte=date_from, completed_at__date__lte=date_to)
            )

        if location_id:
            wo_qs = wo_qs.filter(asset__location_id=location_id)

        total_orders = wo_qs.count()
        completed_orders = wo_qs.filter(status='COMPLETED').count()

        # Rule 4 & 8: PM Compliance with 10% rule and Overlap suppression
        pm_orders = wo_qs.filter(type='PREVENTIVE')
        total_pm_due = pm_orders.count()
        skipped_overlap = pm_orders.filter(
            Q(skipped_reason='SKIPPED_DUE_TO_OVERLAP') | Q(status='CANCELLED', resolution_notes__icontains='OVERLAP')
        ).count()

        # Effective denominator excludes skipped due to overlap
        effective_pm_denominator = max(0, total_pm_due - skipped_overlap)

        on_time_pm_count = 0
        late_pm_count = 0

        for pm in pm_orders:
            # Skip overlap orders from numerator evaluation
            if pm.skipped_reason == 'SKIPPED_DUE_TO_OVERLAP' or (pm.status == 'CANCELLED' and pm.resolution_notes and 'OVERLAP' in pm.resolution_notes.upper()):
                continue

            target_deadline = pm.due_date or pm.deadline
            if pm.status == 'COMPLETED' and pm.completed_at:
                if target_deadline:
                    # 10% Rule: 30 days cycle has 3 days tolerance
                    tolerance_days = 3
                    deadline = target_deadline + timedelta(days=tolerance_days)
                    if pm.completed_at <= deadline:
                        on_time_pm_count += 1
                    else:
                        late_pm_count += 1
                else:
                    on_time_pm_count += 1
            elif target_deadline and timezone.now() > (target_deadline + timedelta(days=3)):
                late_pm_count += 1

        pm_compliance_rate = 100.0
        if effective_pm_denominator > 0:
            pm_compliance_rate = min(100.0, round((on_time_pm_count / effective_pm_denominator) * 100.0, 2))

        # MTTR Calculation for corrective / breakdown orders
        repair_orders = wo_qs.filter(
            type__in=['CORRECTIVE', 'BREAKDOWN', 'EMERGENCY'],
            status='COMPLETED'
        )
        durations = []
        for ro in repair_orders:
            dur = ro.actual_duration_hours
            if dur is not None and 0 < dur <= 168.0:
                durations.append(dur)

        avg_mttr_hours = round(sum(durations) / len(durations), 2) if durations else 0.0

        # Labor log breakdown
        labor_qs = LaborLog.all_objects.filter(
            tenant=tenant,
            work_date__gte=date_from,
            work_date__lte=date_to
        ).select_related('technician', 'work_order')

        total_labor_hours = labor_qs.aggregate(s=Sum('hours_worked'))['s'] or Decimal('0')
        regular_hours = labor_qs.filter(is_overtime=False).aggregate(s=Sum('hours_worked'))['s'] or Decimal('0')
        overtime_hours = labor_qs.filter(is_overtime=True).aggregate(s=Sum('hours_worked'))['s'] or Decimal('0')
        total_labor_cost = labor_qs.aggregate(s=Sum('total_cost'))['s'] or Decimal('0')

        rows = []
        for wo in wo_qs.order_by('-created_at')[:100]:
            rows.append({
                "id": str(wo.id),
                "title": wo.title,
                "assetName": wo.asset.name if wo.asset else "N/A",
                "type": wo.type,
                "priority": wo.priority,
                "status": wo.status,
                "assignedTo": (wo.assigned_to.username or wo.assigned_to.email) if wo.assigned_to else "Chưa gán",
                "dueDate": wo.due_date.strftime('%d/%m/%Y %H:%M') if wo.due_date else "N/A",
                "completedAt": wo.completed_at.strftime('%d/%m/%Y %H:%M') if wo.completed_at else "N/A",
                "durationHours": wo.actual_duration_hours or 0.0,
                "skippedReason": wo.skipped_reason or "N/A"
            })

        return {
            "summary": {
                "totalOrders": total_orders,
                "completedOrders": completed_orders,
                "totalPmDue": total_pm_due,
                "skippedDueToOverlap": skipped_overlap,
                "effectivePmDenominator": effective_pm_denominator,
                "onTimePmCount": on_time_pm_count,
                "latePmCount": late_pm_count,
                "pmComplianceRate": pm_compliance_rate,
                "avgMttrHours": avg_mttr_hours,
                "totalLaborHours": float(total_labor_hours),
                "regularLaborHours": float(regular_hours),
                "overtimeLaborHours": float(overtime_hours),
                "totalLaborCost": float(round_vnd(total_labor_cost))
            },
            "chartSeries": [
                {"name": "Đúng hạn (On-time)", "value": on_time_pm_count},
                {"name": "Trễ hạn (Late)", "value": late_pm_count},
                {"name": "Miễn trừ trùng lặp (Overlap)", "value": skipped_overlap}
            ],
            "items": rows
        }


class SparePartsValuationEngine:
    """
    Engine for Spare Parts Consumption, Moving Average Valuation,
    Negative Inventory Interim Costing & Price Variance Adjustment.
    """

    @classmethod
    def get_spare_parts_data(
        cls,
        tenant,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        parts_qs = SparePart.all_objects.filter(tenant=tenant)
        if search:
            parts_qs = parts_qs.filter(Q(name__icontains=search) | Q(part_number__icontains=search))

        total_inventory_value = Decimal('0')
        negative_stock_items = 0
        rows = []

        for p in parts_qs.iterator(chunk_size=1000):
            qty = p.quantity_in_stock or Decimal('0')
            cost = p.unit_cost or Decimal('0')
            val = round_vnd(qty * cost)

            if qty < 0:
                negative_stock_items += 1

            total_inventory_value += val
            rows.append({
                "id": str(p.id),
                "name": p.name,
                "partNumber": p.part_number or "N/A",
                "quantityInStock": float(qty),
                "unitCost": float(cost),
                "totalValue": float(val),
                "isNegative": qty < 0
            })

        # Transactions audit
        tx_qs = StockTransaction.all_objects.filter(tenant=tenant).select_related('spare_part', 'work_order')
        if date_from:
            tx_qs = tx_qs.filter(issue_date__date__gte=date_from)
        if date_to:
            tx_qs = tx_qs.filter(issue_date__date__lte=date_to)

        price_variance_total = Decimal('0')
        surplus_returned_total = Decimal('0')
        transaction_rows = []

        for tx in tx_qs.order_by('-issue_date')[:100]:
            if tx.is_variance_adjustment:
                price_variance_total += tx.total_amount
            if tx.transaction_type == 'RETURN':
                surplus_returned_total += tx.total_amount

            transaction_rows.append({
                "id": str(tx.id),
                "partName": tx.spare_part.name if tx.spare_part else "N/A",
                "workOrderTitle": tx.work_order.title if tx.work_order else "N/A",
                "transactionType": tx.transaction_type,
                "quantity": float(tx.quantity),
                "unitPrice": float(tx.unit_price),
                "totalAmount": float(tx.total_amount),
                "issueDate": tx.issue_date.strftime('%d/%m/%Y %H:%M') if tx.issue_date else "N/A",
                "isVarianceAdjustment": tx.is_variance_adjustment
            })

        chart_series = [
            {"name": p["name"], "value": p["totalValue"]}
            for p in sorted(rows, key=lambda x: x["totalValue"], reverse=True)[:6]
        ]

        return {
            "summary": {
                "totalParts": len(rows),
                "totalInventoryValue": float(round_vnd(total_inventory_value)),
                "negativeStockItems": negative_stock_items,
                "priceVarianceTotal": float(round_vnd(price_variance_total)),
                "surplusReturnedTotal": float(round_vnd(surplus_returned_total))
            },
            "chartSeries": chart_series,
            "parts": rows,
            "transactions": transaction_rows
        }

    @classmethod
    def record_negative_issue_and_variance(
        cls,
        tenant,
        spare_part: SparePart,
        work_order: WorkOrder,
        issue_qty: Decimal,
        issue_date: datetime,
        cost_center: str = ""
    ) -> StockTransaction:
        """
        Rule 5: When issuing stock with 0 or negative balance, borrow last known moving average unit cost.
        """
        interim_unit_cost = spare_part.unit_cost or Decimal('0')
        total_interim_cost = round_vnd(issue_qty * interim_unit_cost)

        spare_part.quantity_in_stock = (spare_part.quantity_in_stock or Decimal('0')) - issue_qty
        spare_part.save(update_fields=['quantity_in_stock'])

        tx = StockTransaction.all_objects.create(
            tenant=tenant,
            spare_part=spare_part,
            work_order=work_order,
            transaction_type='ISSUE',
            quantity=issue_qty,
            unit_price=interim_unit_cost,
            total_amount=total_interim_cost,
            cost_center_snapshot=cost_center,
            issue_date=issue_date,
            is_variance_adjustment=False
        )

        # Update Work Order interim cost
        if work_order.actual_cost is None:
            work_order.actual_cost = Decimal('0')
        work_order.actual_cost += total_interim_cost
        work_order.save(update_fields=['actual_cost'])

        return tx

    @classmethod
    def apply_grn_receipt_and_reconcile_variance(
        cls,
        tenant,
        spare_part: SparePart,
        receipt_qty: Decimal,
        new_unit_cost: Decimal,
        receipt_date: datetime
    ) -> List[StockTransaction]:
        """
        Rule 5: When GRN receipt arrives with new purchase price,
        adjust moving average cost and generate Price Variance Adjustment
        for prior negative issues.
        """
        old_qty = spare_part.quantity_in_stock or Decimal('0')
        old_cost = spare_part.unit_cost or Decimal('0')

        # Record receipt
        receipt_tx = StockTransaction.all_objects.create(
            tenant=tenant,
            spare_part=spare_part,
            transaction_type='RECEIPT',
            quantity=receipt_qty,
            unit_price=new_unit_cost,
            total_amount=round_vnd(receipt_qty * new_unit_cost),
            issue_date=receipt_date,
            is_variance_adjustment=False
        )

        variances_created = [receipt_tx]

        # Check if stock was negative before receipt
        if old_qty < 0:
            negative_qty = abs(old_qty)
            reconcile_qty = min(negative_qty, receipt_qty)
            unit_variance = new_unit_cost - old_cost

            if unit_variance != 0 and reconcile_qty > 0:
                variance_amount = round_vnd(reconcile_qty * unit_variance)
                
                # Find past negative issue transactions to associate
                recent_issues = StockTransaction.all_objects.filter(
                    tenant=tenant,
                    spare_part=spare_part,
                    transaction_type='ISSUE',
                    is_variance_adjustment=False
                ).order_by('-issue_date')

                target_wo = recent_issues.first().work_order if recent_issues.exists() else None

                var_tx = StockTransaction.all_objects.create(
                    tenant=tenant,
                    spare_part=spare_part,
                    work_order=target_wo,
                    transaction_type='ADJUSTMENT',
                    quantity=reconcile_qty,
                    unit_price=unit_variance,
                    total_amount=variance_amount,
                    issue_date=receipt_date,
                    is_variance_adjustment=True
                )
                variances_created.append(var_tx)

                if target_wo:
                    target_wo.actual_cost = max(Decimal('0'), (target_wo.actual_cost or Decimal('0')) + variance_amount)
                    target_wo.save(update_fields=['actual_cost'])

        # Update spare part quantity and moving average
        new_total_qty = old_qty + receipt_qty
        if new_total_qty > 0:
            if old_qty > 0:
                weighted_cost = ((old_qty * old_cost) + (receipt_qty * new_unit_cost)) / new_total_qty
            else:
                weighted_cost = new_unit_cost
        else:
            weighted_cost = new_unit_cost

        spare_part.quantity_in_stock = new_total_qty
        spare_part.unit_cost = round_vnd(weighted_cost)
        spare_part.save(update_fields=['quantity_in_stock', 'unit_cost'])

        return variances_created

    @classmethod
    def record_surplus_return(
        cls,
        tenant,
        spare_part: SparePart,
        work_order: WorkOrder,
        return_qty: Decimal,
        original_unit_cost: Decimal,
        return_date: datetime
    ) -> StockTransaction:
        """
        Rule 5: Surplus return restocks at original issue price and deducts from WorkOrder cost.
        """
        refund_amount = round_vnd(return_qty * original_unit_cost)

        spare_part.quantity_in_stock = (spare_part.quantity_in_stock or Decimal('0')) + return_qty
        spare_part.save(update_fields=['quantity_in_stock'])

        tx = StockTransaction.all_objects.create(
            tenant=tenant,
            spare_part=spare_part,
            work_order=work_order,
            transaction_type='RETURN',
            quantity=return_qty,
            unit_price=original_unit_cost,
            total_amount=refund_amount,
            issue_date=return_date,
            is_variance_adjustment=False
        )

        if work_order.actual_cost is not None:
            work_order.actual_cost = max(Decimal('0'), work_order.actual_cost - refund_amount)
            work_order.save(update_fields=['actual_cost'])

        return tx


class CostSummaryEngine:
    """
    Engine for Cross-Period Accrual Accounting (Rule 3) and Temporal Cost Center Slicing (Rule 6).
    """

    @classmethod
    def get_cost_summary_data(
        cls,
        tenant,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        cost_center: Optional[str] = None,
        include_capex: bool = False
    ) -> Dict[str, Any]:
        now = timezone.now().date()
        if not date_from:
            date_from = now.replace(day=1)
        if not date_to:
            date_to = now

        # Rule 3: Accrual Accounting
        # Materials cost based on StockTransaction.issue_date
        material_qs = StockTransaction.all_objects.filter(
            tenant=tenant,
            issue_date__date__gte=date_from,
            issue_date__date__lte=date_to,
            transaction_type__in=['ISSUE', 'ADJUSTMENT', 'RETURN']
        ).select_related('spare_part', 'work_order')

        if cost_center:
            material_qs = material_qs.filter(cost_center_snapshot=cost_center)

        if not include_capex:
            # Rule 2 & Rule 3: Exclude CAPEX work orders if specified
            material_qs = material_qs.exclude(work_order__is_capitalized=True)

        # Labor cost based on LaborLog.work_date
        labor_qs = LaborLog.all_objects.filter(
            tenant=tenant,
            work_date__gte=date_from,
            work_date__lte=date_to
        ).select_related('technician', 'work_order')

        if cost_center:
            labor_qs = labor_qs.filter(cost_center_snapshot=cost_center)

        if not include_capex:
            labor_qs = labor_qs.exclude(work_order__is_capitalized=True)

        # Group by cost center snapshot (Rule 6: Temporal Slicing)
        cost_center_aggregates = {}

        total_material_cost = Decimal('0')
        for m in material_qs:
            cc = m.cost_center_snapshot or "Phân xưởng mặc định"
            m_amount = m.total_amount or Decimal('0')
            amt = m_amount if m.transaction_type != 'RETURN' else -m_amount
            total_material_cost += amt

            if cc not in cost_center_aggregates:
                cost_center_aggregates[cc] = {"material": Decimal('0'), "labor": Decimal('0')}
            cost_center_aggregates[cc]["material"] += amt

        total_labor_cost = Decimal('0')
        for l in labor_qs:
            cc = l.cost_center_snapshot or "Phân xưởng mặc định"
            l_cost = l.total_cost or Decimal('0')
            total_labor_cost += l_cost

            if cc not in cost_center_aggregates:
                cost_center_aggregates[cc] = {"material": Decimal('0'), "labor": Decimal('0')}
            cost_center_aggregates[cc]["labor"] += l_cost

        cost_center_rows = []
        for cc, vals in cost_center_aggregates.items():
            mat = round_vnd(vals["material"])
            lab = round_vnd(vals["labor"])
            tot = mat + lab
            cost_center_rows.append({
                "costCenter": cc,
                "materialCost": float(mat),
                "laborCost": float(lab),
                "totalCost": float(tot)
            })

        cost_center_rows.sort(key=lambda x: x["totalCost"], reverse=True)

        total_combined = round_vnd(total_material_cost + total_labor_cost)

        chart_series = [
            {"name": r["costCenter"], "value": r["totalCost"]} for r in cost_center_rows[:6]
        ]

        return {
            "summary": {
                "period": f"{date_from.strftime('%d/%m/%Y')} - {date_to.strftime('%d/%m/%Y')}",
                "totalMaterialCost": float(round_vnd(total_material_cost)),
                "totalLaborCost": float(round_vnd(total_labor_cost)),
                "totalCost": float(total_combined),
                "costCenterCount": len(cost_center_rows)
            },
            "chartSeries": chart_series,
            "costCenters": cost_center_rows
        }

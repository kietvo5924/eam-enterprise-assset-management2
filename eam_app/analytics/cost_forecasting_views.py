"""
REST API Views cho Phân hệ Quản lý & Dự báo Chi phí Bảo trì (Task 11.6).
"""
from decimal import Decimal
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from assets.models import Asset
from algorithms.cost_forecasting import CostForecastingService


def check_technician_blocked(user):
    """Quy tắc 5: Kỹ thuật viên không có quyền truy cập thông tin dự báo tài chính."""
    if user.is_superuser:
        return False
    role_names = [r.name.lower() for r in user.roles.all()]
    if any('technician' in rn for rn in role_names) and not any(k in ' '.join(role_names) for k in ('admin', 'finance', 'manager')):
        return True
    return False


def parse_numeric_input(raw_val):
    """Chuyển đổi an toàn chuỗi tiền tệ (có dấu phẩy/chấm phân cách hàng nghìn) sang Decimal."""
    if raw_val is None or raw_val == '':
        return None
    s = str(raw_val).strip().replace(',', '').replace(' ', '')
    if s.count('.') > 1:
        s = s.replace('.', '')
    try:
        d = Decimal(s)
        return d if d > 0 else None
    except Exception:
        return None


class CurrentForecastView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if check_technician_blocked(request.user):
            return Response({'success': False, 'error': 'Quyền truy cập bị từ chối đối với vai trò Kỹ thuật viên.'}, status=status.HTTP_403_FORBIDDEN)

        tenant = request.user.tenant
        cost_center = request.query_params.get('cost_center') or request.query_params.get('costCenter')
        period = request.query_params.get('period')

        forecast = CostForecastingService.get_current_forecast(
            tenant=tenant,
            period=period,
            cost_center=cost_center
        )

        lemon_data = CostForecastingService.get_lemon_assets(tenant=tenant, cost_center=cost_center)
        top_lemon = lemon_data.get("topLemonAsset")

        # Tính toán nhãn trạng thái trực quan
        usage_pct = forecast.budget_usage_ratio
        if forecast.budget_status == 'CRITICAL_OVERRUN':
            status_label = f"Báo động: Nguy cơ vượt ngân sách {round(usage_pct - 100.0, 1)}% ở kịch bản trung vị P50"
        elif forecast.budget_status == 'WARNING':
            status_label = f"Cảnh báo: Đã tiệm cận {round(usage_pct, 1)}% hạn mức ngân sách được duyệt"
        else:
            status_label = f"Ngân sách an toàn ({round(usage_pct, 1)}% hạn mức được duyệt)"

        # Tỷ lệ chi phí bảo trì trên RAV (Rule 10)
        active_assets = Asset.all_objects.filter(tenant=tenant, status__in=['OPERATIONAL', 'OPERATING'])
        if cost_center:
            active_assets = active_assets.filter(location__name=cost_center)
        fleet_rav = sum(float(a.effective_purchase_cost or 0) + float(a.capitalized_cost or 0) for a in active_assets)
        if fleet_rav > 0:
            annual_multiplier = 4.0 if '-Q' in (forecast.forecast_period or '') else 12.0
            rav_ratio = round(((float(forecast.total_forecast_median) * annual_multiplier) / fleet_rav) * 100.0, 1)
        else:
            rav_ratio = 3.5

        surge_risk = "HIGH" if forecast.backlog_work_orders_count > 10 else ("MEDIUM" if forecast.backlog_work_orders_count > 3 else "LOW")

        data = {
            "period": forecast.forecast_period,
            "costCenter": forecast.cost_center_snapshot,
            "forecastMethod": forecast.forecast_method,
            "isAiFallback": forecast.is_ai_fallback,
            "currency": "VND",
            "budgetOverview": {
                "approvedBudget": float(forecast.approved_budget),
                "isManuallyApproved": getattr(forecast, 'is_manually_approved', False),
                "plannedPmDeterministic": float(forecast.planned_pm_budget),
                "predictedCmMedianP50": float(forecast.predicted_cm_median),
                "predictedCmRiskP90": float(forecast.predicted_cm_upper_p90),
                "contingencyBuffer": float(forecast.contingency_buffer),
                "totalForecastMedian": float(forecast.total_forecast_median),
                "totalForecastP90": float(forecast.total_forecast_p90),
                "usageRatioPercent": forecast.budget_usage_ratio,
                "budgetStatus": forecast.budget_status,
                "statusLabel": status_label
            },
            "riskFactors": {
                "backlogOrdersCount": forecast.backlog_work_orders_count,
                "deferredMaintenanceHours": forecast.deferred_maintenance_hours,
                "postDeferralSurgeRisk": surge_risk,
                "rulCriticalLiabilityAmount": float(forecast.rul_critical_liability),
                "inflationRateAppliedPercent": round(forecast.inflation_rate_applied * 100.0, 1),
                "fleetRavCostRatioPercent": rav_ratio
            },
            "lemonAssetsAlert": {
                "isConcentrationDetected": lemon_data.get("isConcentrationDetected", False),
                "totalBadActorsCount": lemon_data.get("totalBadActorsCount", 0),
                "topLemonAsset": top_lemon
            },
            "topCostDrivers": forecast.top_cost_drivers
        }

        return Response({'success': True, 'data': data})


class RunForecastView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if check_technician_blocked(request.user):
            return Response({'success': False, 'error': 'Quyền truy cập bị từ chối đối với vai trò Kỹ thuật viên.'}, status=status.HTTP_403_FORBIDDEN)

        tenant = request.user.tenant
        payload = request.data or {}

        period = payload.get('period')
        cost_center = payload.get('costCenter') or payload.get('cost_center')
        approved_budget_raw = payload.get('approvedBudget') or payload.get('approved_budget')
        approved_budget = parse_numeric_input(approved_budget_raw)
        inflation_rate = float(payload.get('inflationRate', 0.045))
        contingency_rate = float(payload.get('contingencyBufferPercent', payload.get('contingency_rate', 0.05)))

        forecast = CostForecastingService.run_forecast(
            tenant=tenant,
            period=period,
            cost_center=cost_center,
            approved_budget=approved_budget,
            inflation_rate=inflation_rate,
            contingency_rate=contingency_rate
        )

        return Response({
            'success': True,
            'message': 'Tính toán dự báo ngân sách lai ghép thành công.',
            'data': {
                'forecastId': str(forecast.id),
                'budgetStatus': forecast.budget_status,
                'totalForecastMedian': float(forecast.total_forecast_median),
                'totalForecastP90': float(forecast.total_forecast_p90),
                'usageRatioPercent': forecast.budget_usage_ratio,
                'isAiFallback': forecast.is_ai_fallback
            }
        })


class LemonAssetsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if check_technician_blocked(request.user):
            return Response({'success': False, 'error': 'Quyền truy cập bị từ chối.'}, status=status.HTTP_403_FORBIDDEN)

        tenant = request.user.tenant
        cost_center = request.query_params.get('cost_center') or request.query_params.get('costCenter')
        lemon_data = CostForecastingService.get_lemon_assets(tenant=tenant, cost_center=cost_center)
        return Response({'success': True, 'data': lemon_data})


class HistoricalTrendsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if check_technician_blocked(request.user):
            return Response({'success': False, 'error': 'Quyền truy cập bị từ chối.'}, status=status.HTTP_403_FORBIDDEN)

        tenant = request.user.tenant
        cost_center = request.query_params.get('cost_center') or request.query_params.get('costCenter')
        months = int(request.query_params.get('months', 12))
        trend_data = CostForecastingService.get_historical_trends(tenant=tenant, cost_center=cost_center, months=months)
        return Response({'success': True, 'data': trend_data})


class CostForecastingReadinessView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tenant = request.user.tenant
        readiness = CostForecastingService.check_readiness(tenant=tenant)
        return Response({'success': True, 'data': readiness})


class FinancialSettingsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if check_technician_blocked(request.user):
            return Response({'success': False, 'error': 'Quyền truy cập bị từ chối.'}, status=status.HTTP_403_FORBIDDEN)

        tenant = request.user.tenant
        period = request.query_params.get('period')
        cost_center = request.query_params.get('cost_center') or request.query_params.get('costCenter')
        settings_data = CostForecastingService.get_financial_settings(tenant, period=period, cost_center=cost_center)
        return Response({'success': True, 'data': settings_data})

    def post(self, request):
        if check_technician_blocked(request.user):
            return Response({'success': False, 'error': 'Quyền truy cập bị từ chối.'}, status=status.HTTP_403_FORBIDDEN)

        tenant = request.user.tenant
        payload = request.data or {}
        updated = CostForecastingService.update_financial_settings(tenant, payload, user=request.user)

        # Tự động tính toán lại dự báo nếu có period
        period = payload.get('period')
        cost_center = payload.get('costCenter') or payload.get('cost_center')
        if period:
            app_b = parse_numeric_input(payload.get('approvedBudget'))
            inf_r = float(payload['defaultInflationRate']) if payload.get('defaultInflationRate') is not None else None
            if inf_r is not None and inf_r > 1.0:
                inf_r /= 100.0
            ctg_r = float(payload['defaultContingencyRate']) if payload.get('defaultContingencyRate') is not None else None
            if ctg_r is not None and ctg_r > 1.0:
                ctg_r /= 100.0

            CostForecastingService.run_forecast(
                tenant=tenant,
                period=period,
                cost_center=cost_center,
                approved_budget=app_b,
                inflation_rate=inf_r if inf_r is not None else 0.045,
                contingency_rate=ctg_r if ctg_r is not None else 0.05
            )

        return Response({
            'success': True,
            'message': 'Cập nhật cấu hình tài chính và ngân sách thành công.',
            'data': updated
        })


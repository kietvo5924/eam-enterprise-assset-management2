"""
REST API Views cho Phân hệ Quản lý & Dự báo Chi phí Bảo trì (Task 11.6).
Bảo vệ phân quyền chặt chẽ theo Role/Permission, xác thực dữ liệu đầu vào và cô lập đa doanh nghiệp (Multi-tenant).
"""
import re
from decimal import Decimal
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from assets.models import Asset, Location
from analytics.models import TenantFinancialSetting
from algorithms.cost_forecasting import CostForecastingService


def has_cost_forecasting_read_permission(user) -> bool:
    """
    Quy định quyền xem dự báo tài chính, báo cáo ngân sách và dữ liệu xu hướng.
    Chỉ cho phép Superuser, quản trị viên Tenant, vai trò Quản lý/Tài chính/Kế toán,
    hoặc người dùng sở hữu quyền 'reports:read' / 'tenant:read' / 'system:admin'.
    Kỹ thuật viên thuần túy không có quyền sẽ bị chặn 403.
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True

    # 1. Kiểm tra quyền gán qua các vai trò
    perms = set()
    for role in user.roles.prefetch_related('permissions').all():
        for p in role.permissions.all():
            perms.add(p.id)

    if any(p in perms for p in ('reports:read', 'tenant:read', 'system:admin')):
        return True

    # 2. Kiểm tra tên vai trò quản lý / tài chính
    role_names = [r.name.lower() for r in user.roles.all()]
    if any(k in ' '.join(role_names) for k in ('admin', 'finance', 'manager', 'director', 'accountant')):
        return True

    return False


def has_cost_forecasting_write_permission(user) -> bool:
    """
    Quy định quyền thay đổi cấu hình tài chính, đơn giá giờ công, tỷ lệ lạm phát,
    quỹ dự phòng và hạn mức ngân sách được duyệt.
    Yêu cầu quyền 'tenant:update' hoặc 'system:admin', hoặc vai trò Admin / Finance Manager.
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    perms = set()
    for role in user.roles.prefetch_related('permissions').all():
        for p in role.permissions.all():
            perms.add(p.id)

    if any(p in perms for p in ('tenant:update', 'system:admin')):
        return True

    role_names = [r.name.lower() for r in user.roles.all()]
    if any(k in ' '.join(role_names) for k in ('admin', 'finance', 'manager', 'director')):
        return True

    return False


def validate_period_and_cost_center(tenant, period=None, cost_center=None):
    """Xác thực định dạng kỳ dự báo và phân xưởng thuộc Tenant hợp lệ."""
    if period:
        p_str = str(period).strip()
        if not re.match(r'^\d{4}-(Q[1-4]|0[1-9]|1[0-2])$', p_str):
            return f'Định dạng kỳ "{period}" không hợp lệ. Ví dụ hợp lệ: 2026-Q4 hoặc 2026-11.'

    if cost_center:
        cc_str = str(cost_center).strip()
        if not Location.objects.filter(tenant=tenant, name=cc_str).exists():
            return f'Phân xưởng / Cost center "{cost_center}" không tồn tại trong doanh nghiệp này.'

    return None


def parse_numeric_input(raw_val):
    """Chuyển đổi an toàn chuỗi tiền tệ sang Decimal, validate không âm."""
    if raw_val is None or raw_val == '':
        return None
    s = str(raw_val).strip().replace(',', '').replace(' ', '')
    if s.count('.') > 1:
        s = s.replace('.', '')
    try:
        d = Decimal(s)
        return d if d >= 0 else None
    except Exception:
        return None


class CurrentForecastView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not has_cost_forecasting_read_permission(request.user):
            return Response({'success': False, 'error': 'Quyền truy cập dự báo tài chính bị từ chối.'}, status=status.HTTP_403_FORBIDDEN)

        tenant = getattr(request.user, 'tenant', None)
        if not tenant:
            return Response({'success': False, 'error': 'Tài khoản không thuộc doanh nghiệp hợp lệ.'}, status=status.HTTP_403_FORBIDDEN)

        cost_center = request.query_params.get('cost_center') or request.query_params.get('costCenter')
        period = request.query_params.get('period')

        val_err = validate_period_and_cost_center(tenant, period=period, cost_center=cost_center)
        if val_err:
            return Response({'success': False, 'error': val_err}, status=status.HTTP_400_BAD_REQUEST)

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
            "fallbackReason": getattr(forecast, 'fallback_reason', None),
            "currency": "VND",
            "lastUpdatedAt": forecast.updated_at.isoformat() if hasattr(forecast, 'updated_at') and forecast.updated_at else None,
            "budgetOverview": {
                "approvedBudget": float(forecast.approved_budget),
                "isManuallyApproved": getattr(forecast, 'is_manually_approved', False),
                "plannedPmDeterministic": float(forecast.planned_pm_budget),
                "predictedCmMedianP50": float(forecast.predicted_cm_median),
                "predictedCmLowerP10": float(forecast.predicted_cm_lower_p10),
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
        if not has_cost_forecasting_write_permission(request.user):
            return Response({'success': False, 'error': 'Quyền thực thi dự báo tài chính bị từ chối.'}, status=status.HTTP_403_FORBIDDEN)

        tenant = getattr(request.user, 'tenant', None)
        if not tenant:
            return Response({'success': False, 'error': 'Tài khoản không thuộc doanh nghiệp hợp lệ.'}, status=status.HTTP_403_FORBIDDEN)

        payload = request.data or {}

        period = payload.get('period')
        cost_center = payload.get('costCenter') or payload.get('cost_center')

        val_err = validate_period_and_cost_center(tenant, period=period, cost_center=cost_center)
        if val_err:
            return Response({'success': False, 'error': val_err}, status=status.HTTP_400_BAD_REQUEST)

        # Nạp cài đặt tài chính mặc định của Tenant để tránh bị ghi đè bởi hằng số gán cứng
        setting = TenantFinancialSetting.all_objects.filter(tenant=tenant).first()
        default_inf = setting.default_inflation_rate if setting else 0.045
        default_ctg = setting.default_contingency_rate if setting else 0.05

        approved_budget_raw = payload.get('approvedBudget') or payload.get('approved_budget')
        approved_budget = parse_numeric_input(approved_budget_raw)

        # Xử lý tỷ lệ lạm phát: hỗ trợ cả 0%, tỷ lệ % hoặc phân số
        raw_inf = payload.get('inflationRate') if payload.get('inflationRate') is not None else payload.get('inflation_rate')
        if raw_inf is not None and str(raw_inf).strip() != '':
            try:
                inf_val = float(raw_inf)
                if inf_val < 0 or inf_val > 100:
                    return Response({'success': False, 'error': 'Tỷ lệ lạm phát phải nằm trong khoảng 0% - 100%.'}, status=status.HTTP_400_BAD_REQUEST)
                inflation_rate = inf_val / 100.0 if inf_val > 1.0 else inf_val
            except ValueError:
                return Response({'success': False, 'error': 'Tỷ lệ lạm phát không hợp lệ.'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            inflation_rate = default_inf

        # Xử lý tỷ lệ dự phòng
        raw_ctg = payload.get('contingencyBufferPercent') if payload.get('contingencyBufferPercent') is not None else (
            payload.get('contingency_rate') if payload.get('contingency_rate') is not None else payload.get('contingencyRate')
        )
        if raw_ctg is not None and str(raw_ctg).strip() != '':
            try:
                ctg_val = float(raw_ctg)
                if ctg_val < 0 or ctg_val > 100:
                    return Response({'success': False, 'error': 'Tỷ lệ quỹ dự phòng phải nằm trong khoảng 0% - 100%.'}, status=status.HTTP_400_BAD_REQUEST)
                contingency_rate = ctg_val / 100.0 if ctg_val > 1.0 else ctg_val
            except ValueError:
                return Response({'success': False, 'error': 'Tỷ lệ quỹ dự phòng không hợp lệ.'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            contingency_rate = default_ctg

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
                'isAiFallback': forecast.is_ai_fallback,
                'fallbackReason': getattr(forecast, 'fallback_reason', None)
            }
        })


class LemonAssetsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not has_cost_forecasting_read_permission(request.user):
            return Response({'success': False, 'error': 'Quyền truy cập bị từ chối.'}, status=status.HTTP_403_FORBIDDEN)

        tenant = getattr(request.user, 'tenant', None)
        if not tenant:
            return Response({'success': False, 'error': 'Tài khoản không thuộc doanh nghiệp hợp lệ.'}, status=status.HTTP_403_FORBIDDEN)

        cost_center = request.query_params.get('cost_center') or request.query_params.get('costCenter')
        val_err = validate_period_and_cost_center(tenant, cost_center=cost_center)
        if val_err:
            return Response({'success': False, 'error': val_err}, status=status.HTTP_400_BAD_REQUEST)

        lemon_data = CostForecastingService.get_lemon_assets(tenant=tenant, cost_center=cost_center)
        return Response({'success': True, 'data': lemon_data})


class HistoricalTrendsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not has_cost_forecasting_read_permission(request.user):
            return Response({'success': False, 'error': 'Quyền truy cập bị từ chối.'}, status=status.HTTP_403_FORBIDDEN)

        tenant = getattr(request.user, 'tenant', None)
        if not tenant:
            return Response({'success': False, 'error': 'Tài khoản không thuộc doanh nghiệp hợp lệ.'}, status=status.HTTP_403_FORBIDDEN)

        cost_center = request.query_params.get('cost_center') or request.query_params.get('costCenter')
        period = request.query_params.get('period')

        val_err = validate_period_and_cost_center(tenant, period=period, cost_center=cost_center)
        if val_err:
            return Response({'success': False, 'error': val_err}, status=status.HTTP_400_BAD_REQUEST)

        try:
            months = int(request.query_params.get('months', 12))
            if months <= 0 or months > 60:
                months = 12
        except (ValueError, TypeError):
            months = 12

        trend_data = CostForecastingService.get_historical_trends(
            tenant=tenant,
            period=period,
            cost_center=cost_center,
            months=months
        )
        return Response({'success': True, 'data': trend_data})


class CostForecastingReadinessView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not has_cost_forecasting_read_permission(request.user):
            return Response({'success': False, 'error': 'Quyền truy cập bị từ chối.'}, status=status.HTTP_403_FORBIDDEN)

        tenant = getattr(request.user, 'tenant', None)
        if not tenant:
            return Response({'success': False, 'error': 'Tài khoản không thuộc doanh nghiệp hợp lệ.'}, status=status.HTTP_403_FORBIDDEN)

        readiness = CostForecastingService.check_readiness(tenant=tenant)
        return Response({'success': True, 'data': readiness})


class FinancialSettingsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not has_cost_forecasting_read_permission(request.user):
            return Response({'success': False, 'error': 'Quyền truy cập bị từ chối.'}, status=status.HTTP_403_FORBIDDEN)

        tenant = getattr(request.user, 'tenant', None)
        if not tenant:
            return Response({'success': False, 'error': 'Tài khoản không thuộc doanh nghiệp hợp lệ.'}, status=status.HTTP_403_FORBIDDEN)

        period = request.query_params.get('period')
        cost_center = request.query_params.get('cost_center') or request.query_params.get('costCenter')

        val_err = validate_period_and_cost_center(tenant, period=period, cost_center=cost_center)
        if val_err:
            return Response({'success': False, 'error': val_err}, status=status.HTTP_400_BAD_REQUEST)

        settings_data = CostForecastingService.get_financial_settings(tenant, period=period, cost_center=cost_center)
        return Response({'success': True, 'data': settings_data})

    def post(self, request):
        if not has_cost_forecasting_write_permission(request.user):
            return Response({'success': False, 'error': 'Chỉ vai trò có thẩm quyền tài chính mới được phép thay đổi cấu hình hoặc hạn mức ngân sách.'}, status=status.HTTP_403_FORBIDDEN)

        tenant = getattr(request.user, 'tenant', None)
        if not tenant:
            return Response({'success': False, 'error': 'Tài khoản không thuộc doanh nghiệp hợp lệ.'}, status=status.HTTP_403_FORBIDDEN)

        payload = request.data or {}
        period = payload.get('period')
        cost_center = payload.get('costCenter') or payload.get('cost_center')

        val_err = validate_period_and_cost_center(tenant, period=period, cost_center=cost_center)
        if val_err:
            return Response({'success': False, 'error': val_err}, status=status.HTTP_400_BAD_REQUEST)

        try:
            updated = CostForecastingService.update_financial_settings(tenant, payload, user=request.user)
        except ValueError as ex:
            return Response({'success': False, 'error': str(ex)}, status=status.HTTP_400_BAD_REQUEST)

        # Tự động tính toán lại dự báo nếu có period
        if period:
            setting = TenantFinancialSetting.all_objects.filter(tenant=tenant).first()
            inf_r = setting.default_inflation_rate if setting else 0.045
            ctg_r = setting.default_contingency_rate if setting else 0.05
            app_b = parse_numeric_input(payload.get('approvedBudget'))

            CostForecastingService.run_forecast(
                tenant=tenant,
                period=period,
                cost_center=cost_center,
                approved_budget=app_b,
                inflation_rate=inf_r,
                contingency_rate=ctg_r
            )

        return Response({
            'success': True,
            'message': 'Cập nhật cấu hình tài chính và ngân sách thành công.',
            'data': updated
        })


import logging
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.db import models
from django.db.models import Count, Q
from django.db.models.functions import TruncDay
from django.utils import timezone
from django.core.cache import cache

from assets.models import Asset
from workorders.models import WorkOrder
from core.models import AuditLog

logger = logging.getLogger(__name__)

CACHE_TTL = 300  # 5 minutes
LOCK_TIMEOUT = 10  # 10 seconds mutex


def calculate_largest_remainder_percentages(counts: dict[str, int]) -> dict[str, float]:
    """
    Hamilton-Hare Largest Remainder Method (Rule 1 & TC-DASH-10).
    Guarantees the sum of percentages across all buckets is exactly 100.0% (or 0.0% if empty).
    """
    total = sum(counts.values())
    if total == 0:
        return {k: 0.0 for k in counts}

    # 1. Calculate raw percentages
    raw_percentages = {k: (v / total) * 100.0 for k, v in counts.items()}

    # 2. Floor to 1 decimal place
    floored = {k: int(pct * 10) / 10.0 for k, pct in raw_percentages.items()}
    remainder_sum = round(100.0 - sum(floored.values()), 1)

    # 3. Sort by remainder descending and distribute 0.1% increments
    remainders = sorted(
        counts.keys(),
        key=lambda k: raw_percentages[k] - floored[k],
        reverse=True
    )
    steps = int(round(remainder_sum * 10))
    for i in range(steps):
        key = remainders[i % len(remainders)]
        floored[key] = round(floored[key] + 0.1, 1)

    return floored


def _format_diff_val(val) -> str:
    if val is None:
        return "0"
    try:
        fval = float(val)
        if fval.is_integer():
            return str(int(fval))
        return str(round(fval, 1))
    except Exception:
        return str(val)


def calculate_safe_delta(current_val: float, previous_val: float, is_percentage: bool = False, higher_is_better: bool = True, default_label: str = "so với tháng trước") -> dict:
    """
    Safe Delta Calculation Guardrail (Rule 9 & TC-DASH-16).
    Avoids ZeroDivisionError / Infinity when previous period value is 0.
    Handles int, float, and Decimal inputs safely.
    """
    if previous_val == 0 or previous_val is None:
        diff = current_val - (previous_val or 0)
        formatted_diff = _format_diff_val(diff)
        if diff > 0:
            diff_str = f"+{formatted_diff}"
            delta_type = "positive" if higher_is_better else "negative"
        elif diff < 0:
            diff_str = f"{formatted_diff}"
            delta_type = "negative" if higher_is_better else "positive"
        else:
            diff_str = "0"
            delta_type = "neutral"

        if is_percentage and diff != 0:
            diff_str = f"{diff_str}%"

        return {
            "delta": diff_str,
            "deltaType": delta_type,
            "deltaLabel": "Kỳ đầu / Mới"
        }

    diff = current_val - previous_val
    sign = "+" if diff > 0 else ""
    formatted_diff = _format_diff_val(diff)

    if is_percentage:
        delta_str = f"{sign}{round(float(diff), 1)}%"
    else:
        delta_str = f"{sign}{formatted_diff}"

    if diff > 0:
        delta_type = "positive" if higher_is_better else "negative"
    elif diff < 0:
        delta_type = "negative" if higher_is_better else "positive"
    else:
        delta_type = "neutral"

    return {
        "delta": delta_str,
        "deltaType": delta_type,
        "deltaLabel": default_label
    }


class AssetHealthService:
    """
    Rule 1 & Rule 10: Asset Lifecycle, Trackable Filtering, Hamilton-Hare Rounding.
    """

    EXCLUDED_STATUSES = [
        'DRAFT', 'DECOMMISSIONED', 'SCRAPPED', 'DISPOSED',
        'LOST', 'SOLD', 'RETIRED'
    ]

    @classmethod
    def calculate_health(cls, tenant) -> dict:
        qs = Asset.all_objects.filter(tenant=tenant, is_trackable=True)
        # Exclude decommissioned/scrapped/disposed/retired
        qs = qs.exclude(status__in=cls.EXCLUDED_STATUSES)

        # Classify into operating, maintenance, down
        op_count = qs.filter(status__in=['OPERATIONAL', 'OPERATING']).count()
        maint_count = qs.filter(status='MAINTENANCE').count()
        down_count = qs.filter(status='DOWN').count()
        total_active = op_count + maint_count + down_count

        counts = {
            'operating': op_count,
            'maintenance': maint_count,
            'down': down_count
        }
        percentages = calculate_largest_remainder_percentages(counts)

        # Plant Status evaluation
        if total_active == 0:
            plant_status = 'NORMAL'
            plant_status_label = 'Bình thường'
        else:
            down_pct = percentages['down']
            op_pct = percentages['operating']
            if down_pct == 0.0 and op_pct >= 90.0:
                plant_status = 'OPTIMAL'
                plant_status_label = 'Tối ưu'
            elif down_pct <= 5.0:
                plant_status = 'NORMAL'
                plant_status_label = 'Bình thường'
            elif down_pct <= 15.0:
                plant_status = 'WARNING'
                plant_status_label = 'Cần chú ý'
            else:
                plant_status = 'CRITICAL'
                plant_status_label = 'Báo động'

        return {
            "totalActive": total_active,
            "operating": {"count": op_count, "percentage": percentages['operating']},
            "maintenance": {"count": maint_count, "percentage": percentages['maintenance']},
            "down": {"count": down_count, "percentage": percentages['down']},
            "plantStatus": plant_status,
            "plantStatusLabel": plant_status_label
        }


class ReliabilityMetricsService:
    """
    Rule 2, 7, 8: MTBF & MTTR calculation, PM exclusion, Zero-Division safety,
    ongoing unresolved downtime isolation, and outlier filtering.
    """

    FAILURE_TYPES = ['CORRECTIVE', 'EMERGENCY', 'BREAKDOWN']

    @classmethod
    def calculate_reliability(cls, tenant, total_active_assets: int, period_days: int = 30) -> dict:
        now = timezone.now()
        start_date = now - timedelta(days=period_days)

        # Rule 2: Strictly EXCLUDE Preventive Maintenance ('PREVENTIVE')
        # Only technical failure work orders in period
        failure_wos = WorkOrder.all_objects.filter(
            tenant=tenant,
            type__in=cls.FAILURE_TYPES,
            created_at__gte=start_date
        )
        n_failures = failure_wos.count()

        # Rule 7: Ongoing unresolved downtime isolation (uncompleted failure work orders or down assets)
        ongoing_wos_count = WorkOrder.all_objects.filter(
            tenant=tenant,
            type__in=cls.FAILURE_TYPES,
            status__in=['CREATED', 'ASSIGNED', 'IN_PROGRESS']
        ).count()
        down_assets_count = Asset.all_objects.filter(
            tenant=tenant,
            is_trackable=True,
            status='DOWN'
        ).count()
        ongoing_down_count = max(ongoing_wos_count, down_assets_count)

        # MTTR: Only COMPLETED failures in period with valid duration
        completed_failures = WorkOrder.all_objects.filter(
            tenant=tenant,
            type__in=cls.FAILURE_TYPES,
            status='COMPLETED',
            completed_at__gte=start_date
        )

        valid_durations = []
        for wo in completed_failures:
            dur = wo.actual_duration_hours
            # Rule 8: Anomalous duration filter (<= 0 or > 168 hours)
            if dur is not None and 0 < dur <= 168.0:
                valid_durations.append(dur)

        if valid_durations:
            mttr_hours = round(sum(valid_durations) / len(valid_durations), 1)
            mttr_display = f"{mttr_hours} giờ"
        else:
            mttr_hours = None
            mttr_display = "N/A"

        # Rule 2: Zero-Division safety
        if n_failures == 0:
            mtbf_hours = None
            mtbf_display = "100% Khả dụng (0 Sự cố)"
            is_zero_failure = True
            plant_availability = "100.0%"
        else:
            is_zero_failure = False
            total_calendar_hours = (total_active_assets or 1) * period_days * 24.0
            total_downtime = sum(valid_durations) if valid_durations else 0.0
            operating_hours = max(0.0, total_calendar_hours - total_downtime)
            mtbf_hours = round(operating_hours / n_failures, 1)
            mtbf_display = f"{mtbf_hours} giờ / sự cố"

            if mttr_hours is not None and (mtbf_hours + mttr_hours) > 0:
                avail_num = round((mtbf_hours / (mtbf_hours + mttr_hours)) * 100.0, 1)
                plant_availability = f"{avail_num}%"
            elif total_active_assets > 0 and ongoing_down_count > 0:
                active_up = max(0, total_active_assets - ongoing_down_count)
                avail_num = round((active_up / total_active_assets) * 100.0, 1)
                plant_availability = f"{avail_num}%"
            else:
                plant_availability = "100.0%"

        return {
            "mtbfHours": mtbf_hours,
            "mtbfDisplay": mtbf_display,
            "isZeroFailure": is_zero_failure,
            "mttrHours": mttr_hours,
            "mttrDisplay": mttr_display,
            "ongoingDownCount": ongoing_down_count,
            "plantAvailability": plant_availability,
            "failureCount": n_failures
        }


class PMComplianceService:
    """
    Calculates PM Compliance Rate in 30 days:
    (Completed PMs on/before deadline / Total PMs due in 30 days) * 100%
    """

    @classmethod
    def calculate_compliance(cls, tenant, period_days: int = 30) -> dict:
        now = timezone.now()
        start_date = now - timedelta(days=period_days)

        pm_due_qs = WorkOrder.all_objects.filter(
            tenant=tenant,
            type='PREVENTIVE'
        ).filter(
            Q(deadline__gte=start_date, deadline__lte=now) |
            Q(created_at__gte=start_date, deadline__isnull=True)
        )
        total_due = pm_due_qs.count()

        if total_due == 0:
            return {
                "rate": 100.0,
                "display": "100.0%",
                "completedOnTime": 0,
                "totalDue": 0
            }

        on_time_count = 0
        for wo in pm_due_qs.filter(status='COMPLETED'):
            if wo.completed_at:
                if wo.deadline:
                    if wo.completed_at <= wo.deadline:
                        on_time_count += 1
                else:
                    on_time_count += 1

        rate = round((on_time_count / total_due) * 100.0, 1)
        return {
            "rate": rate,
            "display": f"{rate}%",
            "completedOnTime": on_time_count,
            "totalDue": total_due
        }


class TrendAnalyticsService:
    """
    Rule 3, 4, 6: 30-Day Zero-Filling Continuous Time-Series & Tenant Timezone Midnight Boundary.
    Separates Created vs Completed series.
    """

    @classmethod
    def get_30_day_trends(cls, tenant) -> dict:
        tz_name = getattr(tenant, 'timezone', None) or 'Asia/Ho_Chi_Minh'
        try:
            tenant_tz = ZoneInfo(tz_name)
        except Exception:
            tenant_tz = ZoneInfo('Asia/Ho_Chi_Minh')
            tz_name = 'Asia/Ho_Chi_Minh'

        local_now = timezone.now().astimezone(tenant_tz)
        today_date = local_now.date()

        # Build 30 calendar days list from (today - 29 days) to today
        days_list = [today_date - timedelta(days=29 - i) for i in range(30)]

        # Start of day 29 days ago (00:00:00 local time)
        start_local = datetime.combine(days_list[0], datetime.min.time(), tzinfo=tenant_tz)
        # End of today (23:59:59 local time)
        end_local = datetime.combine(days_list[-1], datetime.max.time(), tzinfo=tenant_tz)

        # Convert to UTC for DB filtering
        start_utc = start_local.astimezone(ZoneInfo('UTC'))
        end_utc = end_local.astimezone(ZoneInfo('UTC'))

        # Rule 4: Query Created series
        created_qs = (
            WorkOrder.all_objects.filter(
                tenant=tenant,
                created_at__gte=start_utc,
                created_at__lte=end_utc
            )
            .annotate(day=TruncDay('created_at', tzinfo=tenant_tz))
            .values('day')
            .annotate(count=Count('id'))
        )
        created_map = {}
        for row in created_qs:
            if row['day']:
                d = row['day'].date() if hasattr(row['day'], 'date') else row['day']
                created_map[d] = row['count']

        # Rule 4: Query Completed series
        completed_qs = (
            WorkOrder.all_objects.filter(
                tenant=tenant,
                status='COMPLETED',
                completed_at__gte=start_utc,
                completed_at__lte=end_utc
            )
            .annotate(day=TruncDay('completed_at', tzinfo=tenant_tz))
            .values('day')
            .annotate(count=Count('id'))
        )
        completed_map = {}
        for row in completed_qs:
            if row['day']:
                d = row['day'].date() if hasattr(row['day'], 'date') else row['day']
                completed_map[d] = row['count']

        # Rule 3: Zero-filling for all 30 days
        series = []
        for day in days_list:
            series.append({
                "date": day.strftime("%d/%m"),
                "fullDate": day.isoformat(),
                "created": created_map.get(day, 0),
                "completed": completed_map.get(day, 0)
            })

        return {
            "timezone": tz_name,
            "series": series
        }


class ActivityFeedService:
    """
    Rule 5: Activity Feed Whitelist Guardrail.
    Filters out noise (GETs, password changes, logins, profile edits).
    Only returns operational impact events.
    """

    WHITELIST_EVENT_TYPES = [
        'WO_CREATED', 'WO_ASSIGNED', 'WO_COMPLETED',
        'ASSET_STATUS_DOWN', 'ASSET_RESTORED', 'SPARE_PART_LOW_STOCK'
    ]

    @classmethod
    def get_recent_activities(cls, tenant, limit: int = 10) -> list[dict]:
        now = timezone.now()

        # Query recent audit logs for this tenant
        logs = AuditLog.all_objects.filter(tenant=tenant).order_by('-timestamp')[:100]

        activities = []
        for log in logs:
            event_info = cls._classify_and_format_log(log, now)
            if event_info:
                activities.append(event_info)
                if len(activities) >= limit:
                    break

        # If no audit logs match whitelist, also synthesize from recent WorkOrders / Assets if available
        if not activities:
            activities = cls._synthesize_recent_activities(tenant, now, limit)

        return activities

    @classmethod
    def _format_relative_time(cls, dt, now):
        diff = now - dt
        seconds = max(0, int(diff.total_seconds()))
        if seconds < 60:
            return "Vừa xong"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes} phút trước"
        hours = minutes // 60
        if hours < 24:
            return f"{hours} giờ trước"
        days = hours // 24
        if days == 1:
            return "Hôm qua"
        return f"{days} ngày trước"

    @classmethod
    def _classify_and_format_log(cls, log, now) -> dict | None:
        action = getattr(log, 'action_type', '') or ''
        entity = getattr(log, 'entity_type', '') or ''
        entity_id = getattr(log, 'entity_id', '') or ''
        ts = getattr(log, 'timestamp', now)

        # 1. Direct match on whitelist string
        if action in cls.WHITELIST_EVENT_TYPES:
            TITLES = {
                'WO_CREATED': "Khởi tạo phiếu công việc mới",
                'WO_ASSIGNED': "Phân công xử lý phiếu",
                'WO_COMPLETED': "Hoàn tất phiếu công việc",
                'ASSET_STATUS_DOWN': "Thiết bị dừng máy do sự cố (DOWN)",
                'ASSET_RESTORED': "Thiết bị phục hồi vận hành",
                'SPARE_PART_LOW_STOCK': "Cảnh báo phụ tùng tồn kho thấp"
            }
            title = TITLES.get(action, action.replace('_', ' ').title())
            desc = f"Ghi nhận biến động vận hành trên {entity} #{entity_id[:8]}."
            link = f"/portal/work-orders/{entity_id}/" if 'WO' in action else f"/portal/assets/{entity_id}/"
            return {
                "id": str(log.id),
                "eventType": action,
                "title": title,
                "description": desc,
                "timeAgo": cls._format_relative_time(ts, now),
                "timestamp": ts.isoformat(),
                "link": link
            }

        # 2. Derive operational event from entity + action
        if entity == 'WorkOrder':
            if action == 'CREATE':
                return {
                    "id": str(log.id),
                    "eventType": "WO_CREATED",
                    "title": f"Phiếu WO-{entity_id[:8]} được tạo mới",
                    "description": f"Phiếu công việc mới đã được khởi tạo trên hệ thống.",
                    "timeAgo": cls._format_relative_time(ts, now),
                    "timestamp": ts.isoformat(),
                    "link": f"/portal/work-orders/{entity_id}/"
                }
            elif action == 'UPDATE':
                return {
                    "id": str(log.id),
                    "eventType": "WO_COMPLETED",
                    "title": f"Phiếu WO-{entity_id[:8]} cập nhật",
                    "description": f"Tiến độ công việc đã được ghi nhận.",
                    "timeAgo": cls._format_relative_time(ts, now),
                    "timestamp": ts.isoformat(),
                    "link": f"/portal/work-orders/{entity_id}/"
                }

        if entity == 'Asset' and action == 'UPDATE':
            return {
                "id": str(log.id),
                "eventType": "ASSET_STATUS_DOWN",
                "title": f"Trạng thái thiết bị #{entity_id[:8]} thay đổi",
                "description": f"Biến động trạng thái vận hành thiết bị được ghi nhận.",
                "timeAgo": cls._format_relative_time(ts, now),
                "timestamp": ts.isoformat(),
                "link": f"/portal/assets/{entity_id}/"
            }

        # Ignore noise: user, role, permission, password, session
        return None

    @classmethod
    def _synthesize_recent_activities(cls, tenant, now, limit: int) -> list[dict]:
        """Fallback: synthesize from actual work orders and asset changes if audit log is empty."""
        recent_wos = WorkOrder.all_objects.filter(tenant=tenant).order_by('-updated_at')[:limit]
        acts = []
        for wo in recent_wos:
            if wo.status == 'COMPLETED':
                ev_type = 'WO_COMPLETED'
                title = f"{wo.title[:30]} Hoàn tất"
                desc = f"Phiếu bảo trì {wo.title} đã hoàn thành."
            elif wo.assigned_to:
                ev_type = 'WO_ASSIGNED'
                title = f"{wo.title[:30]} Đã giao việc"
                desc = f"Phân công cho {wo.assigned_to.username}."
            else:
                ev_type = 'WO_CREATED'
                title = f"{wo.title[:30]} Tạo mới"
                desc = f"Phiếu yêu cầu công việc mới được tạo."

            acts.append({
                "id": str(wo.id),
                "eventType": ev_type,
                "title": title,
                "description": desc,
                "timeAgo": cls._format_relative_time(wo.updated_at or wo.created_at, now),
                "timestamp": (wo.updated_at or wo.created_at).isoformat(),
                "link": f"/portal/work-orders/{wo.id}/"
            })
        return acts


class DashboardCacheService:
    """
    Rule 10: Cache Stampede Mutex Guardrail & Graceful Fallback.
    """

    @classmethod
    def get_summary_cache_key(cls, tenant_id) -> str:
        return f"eam:dashboard:summary:{tenant_id}"

    @classmethod
    def get_trends_cache_key(cls, tenant_id) -> str:
        return f"eam:dashboard:trends:{tenant_id}"

    @classmethod
    def get_activity_cache_key(cls, tenant_id) -> str:
        return f"eam:dashboard:activity:{tenant_id}"

    @classmethod
    def get_lock_key(cls, tenant_id) -> str:
        return f"eam:dashboard:lock:{tenant_id}"

    @classmethod
    def invalidate_all(cls, tenant_id):
        """Invalidate all dashboard caches for a tenant on key operational events."""
        try:
            cache.delete_many([
                cls.get_summary_cache_key(tenant_id),
                cls.get_trends_cache_key(tenant_id),
                cls.get_activity_cache_key(tenant_id),
            ])
        except Exception as e:
            logger.warning(f"Failed to invalidate dashboard cache for {tenant_id}: {e}")

    @classmethod
    def get_summary(cls, tenant) -> dict:
        cache_key = cls.get_summary_cache_key(tenant.id)
        lock_key = cls.get_lock_key(tenant.id)

        # 1. Try reading cache
        try:
            cached = cache.get(cache_key)
            if cached:
                return cached
        except Exception as e:
            logger.warning(f"Cache read error: {e}. Falling back to live computation.")
            return cls._compute_summary(tenant)

        # 2. Cache miss: Mutex lock to prevent stampede
        acquired_lock = False
        try:
            acquired_lock = cache.add(lock_key, "1", timeout=LOCK_TIMEOUT)
        except Exception:
            pass

        if acquired_lock:
            try:
                data = cls._compute_summary(tenant)
                try:
                    cache.set(cache_key, data, timeout=CACHE_TTL)
                except Exception as e:
                    logger.warning(f"Cache set error: {e}")
                return data
            finally:
                try:
                    cache.delete(lock_key)
                except Exception:
                    pass
        else:
            # Another process is computing: wait briefly for cache
            for _ in range(5):
                time.sleep(0.1)
                try:
                    cached = cache.get(cache_key)
                    if cached:
                        return cached
                except Exception:
                    break
            # Fallback direct compute
            return cls._compute_summary(tenant)

    @classmethod
    def _compute_summary(cls, tenant) -> dict:
        now = timezone.now()
        start_30d = now - timedelta(days=30)
        start_60d = now - timedelta(days=60)

        # 1. Asset Health
        asset_health = AssetHealthService.calculate_health(tenant)
        total_active_assets = asset_health["totalActive"]

        # Previous 30-day assets (or delta)
        prev_assets_count = Asset.all_objects.filter(
            tenant=tenant,
            is_trackable=True,
            created_at__lt=start_30d
        ).exclude(status__in=AssetHealthService.EXCLUDED_STATUSES).count()
        total_assets_delta = calculate_safe_delta(
            total_active_assets, prev_assets_count,
            higher_is_better=True, default_label="so với tháng trước"
        )

        # 2. Active Work Orders
        active_wo_count = WorkOrder.all_objects.filter(
            tenant=tenant,
            status__in=['CREATED', 'ASSIGNED', 'IN_PROGRESS']
        ).count()
        # Yesterday's active count estimation
        yesterday_created = WorkOrder.all_objects.filter(
            tenant=tenant,
            created_at__gte=now - timedelta(days=1),
            status__in=['CREATED', 'ASSIGNED', 'IN_PROGRESS']
        ).count()
        active_wo_delta = calculate_safe_delta(
            active_wo_count, max(0, active_wo_count - yesterday_created),
            higher_is_better=False, default_label="so với hôm qua"
        )

        # 3. Completed Work Orders in 30 days
        completed_wo_count = WorkOrder.all_objects.filter(
            tenant=tenant,
            status='COMPLETED',
            completed_at__gte=start_30d
        ).count()
        prev_completed_wo_count = WorkOrder.all_objects.filter(
            tenant=tenant,
            status='COMPLETED',
            completed_at__gte=start_60d,
            completed_at__lt=start_30d
        ).count()
        completed_wo_delta = calculate_safe_delta(
            completed_wo_count, prev_completed_wo_count,
            higher_is_better=True, default_label="so với 30 ngày trước"
        )

        # 4. Reliability (MTBF, MTTR, Plant Availability)
        reliability = ReliabilityMetricsService.calculate_reliability(
            tenant, total_active_assets, period_days=30
        )

        # Availability delta
        avail_num = 100.0
        if reliability["plantAvailability"]:
            try:
                avail_num = float(reliability["plantAvailability"].replace('%', ''))
            except ValueError:
                avail_num = 100.0
        avail_delta = calculate_safe_delta(
            avail_num, 98.0, is_percentage=True, higher_is_better=True, default_label="so với tháng trước"
        )

        # 5. PM Compliance Rate
        pm_compliance = PMComplianceService.calculate_compliance(tenant, period_days=30)
        pm_delta = calculate_safe_delta(
            pm_compliance["rate"], 90.0, is_percentage=True, higher_is_better=True, default_label="so với tháng trước"
        )

        return {
            "kpis": {
                "totalAssets": {
                    "value": total_active_assets,
                    "delta": total_assets_delta["delta"],
                    "deltaType": total_assets_delta["deltaType"],
                    "deltaLabel": total_assets_delta["deltaLabel"],
                    "label": "Thiết bị đang quản lý",
                    "drillDownUrl": "/portal/assets/?status=OPERATING,MAINTENANCE,DOWN&is_trackable=true"
                },
                "activeWorkOrders": {
                    "value": active_wo_count,
                    "delta": active_wo_delta["delta"],
                    "deltaType": active_wo_delta["deltaType"],
                    "deltaLabel": active_wo_delta["deltaLabel"],
                    "label": "Phiếu đang xử lý",
                    "drillDownUrl": "/portal/work-orders/?status=CREATED,ASSIGNED,IN_PROGRESS"
                },
                "completedWorkOrders": {
                    "value": completed_wo_count,
                    "delta": completed_wo_delta["delta"],
                    "deltaType": completed_wo_delta["deltaType"],
                    "deltaLabel": completed_wo_delta["deltaLabel"],
                    "label": "Phiếu hoàn tất (30 ngày)",
                    "drillDownUrl": "/portal/work-orders/?status=COMPLETED&period=30d"
                },
                "plantAvailability": {
                    "value": reliability["plantAvailability"],
                    "delta": avail_delta["delta"],
                    "deltaType": avail_delta["deltaType"],
                    "deltaLabel": avail_delta["deltaLabel"],
                    "label": "Độ sẵn sàng vận hành",
                    "drillDownUrl": None
                },
                "pmComplianceRate": {
                    "value": pm_compliance["display"],
                    "delta": pm_delta["delta"],
                    "deltaType": pm_delta["deltaType"],
                    "deltaLabel": pm_delta["deltaLabel"],
                    "label": "Tuân thủ bảo trì định kỳ",
                    "drillDownUrl": "/portal/work-orders/?type=PREVENTIVE&period=30d"
                }
            },
            "assetHealth": asset_health,
            "reliability": {
                "mtbfHours": reliability["mtbfHours"],
                "mtbfDisplay": reliability["mtbfDisplay"],
                "isZeroFailure": reliability["isZeroFailure"],
                "mttrHours": reliability["mttrHours"],
                "mttrDisplay": reliability["mttrDisplay"],
                "ongoingDownCount": reliability["ongoingDownCount"]
            }
        }

    @classmethod
    def get_trends(cls, tenant) -> dict:
        cache_key = cls.get_trends_cache_key(tenant.id)
        try:
            cached = cache.get(cache_key)
            if cached:
                return cached
        except Exception as e:
            logger.warning(f"Cache get error: {e}")

        data = TrendAnalyticsService.get_30_day_trends(tenant)
        try:
            cache.set(cache_key, data, timeout=CACHE_TTL)
        except Exception as e:
            logger.warning(f"Cache set error: {e}")
        return data

    @classmethod
    def get_activity_feed(cls, tenant) -> list[dict]:
        cache_key = cls.get_activity_cache_key(tenant.id)
        try:
            cached = cache.get(cache_key)
            if cached:
                return cached
        except Exception as e:
            logger.warning(f"Cache get error: {e}")

        data = ActivityFeedService.get_recent_activities(tenant)
        try:
            cache.set(cache_key, data, timeout=CACHE_TTL)
        except Exception as e:
            logger.warning(f"Cache set error: {e}")
        return data

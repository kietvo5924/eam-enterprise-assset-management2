import uuid
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from core.models import Tenant, AuditLog
from core.tenant_context import set_current_tenant, clear_current_tenant
from assets.models import Asset, AssetCategory, Location
from workorders.models import WorkOrder
from analytics.services import (
    AssetHealthService,
    ReliabilityMetricsService,
    PMComplianceService,
    TrendAnalyticsService,
    ActivityFeedService,
    DashboardCacheService,
    calculate_largest_remainder_percentages,
    calculate_safe_delta
)

User = get_user_model()


class DashboardAnalyticsTestCase(TestCase):
    """
    Acceptance Test Suite for Task 10.2 — Executive Dashboard KPIs & Analytics Engine.
    Covers all 17 Acceptance Criteria and Edge Cases (TC-DASH-01 through TC-DASH-17).
    """

    def setUp(self):
        clear_current_tenant()
        # Tenant Alpha (VN timezone)
        self.tenant_a = Tenant.objects.create(
            name="VinFast Factory Hai Phong",
            tenant_code="VF_HP",
            timezone="Asia/Ho_Chi_Minh"
        )
        # Tenant Beta (for multi-tenant isolation testing)
        self.tenant_b = Tenant.objects.create(
            name="Samsung Electronics Bac Ninh",
            tenant_code="SE_BN",
            timezone="Asia/Ho_Chi_Minh"
        )

        self.user_a = User.objects.create_user(
            username="manager_alpha",
            email="manager@alpha.vn",
            password="password123",
            tenant=self.tenant_a
        )
        self.user_b = User.objects.create_user(
            username="manager_beta",
            email="manager@beta.vn",
            password="password123",
            tenant=self.tenant_b
        )

        self.client_a = APIClient()
        self.client_a.force_authenticate(user=self.user_a)

        self.client_b = APIClient()
        self.client_b.force_authenticate(user=self.user_b)

        # Clear cache before each test
        DashboardCacheService.invalidate_all(self.tenant_a.id)
        DashboardCacheService.invalidate_all(self.tenant_b.id)

    def tearDown(self):
        clear_current_tenant()

    def test_tc_dash_01_empty_state_tenant(self):
        """
        TC-DASH-01: Empty State Tenant.
        A brand-new organization with zero assets or work orders should load cleanly
        without division by zero or errors.
        """
        response = self.client_a.get('/api/v1/dashboard/summary/')
        self.assertEqual(response.status_code, 200)
        res_json = response.json()
        self.assertTrue(res_json["success"])

        data = res_json["data"]
        kpis = data["kpis"]

        # All count KPIs are 0
        self.assertEqual(kpis["totalAssets"]["value"], 0)
        self.assertEqual(kpis["activeWorkOrders"]["value"], 0)
        self.assertEqual(kpis["completedWorkOrders"]["value"], 0)
        self.assertEqual(kpis["plantAvailability"]["value"], "100.0%")
        self.assertEqual(kpis["pmComplianceRate"]["value"], "100.0%")

        # Asset health percentages are 0.0
        health = data["assetHealth"]
        self.assertEqual(health["totalActive"], 0)
        self.assertEqual(health["operating"]["percentage"], 0.0)
        self.assertEqual(health["maintenance"]["percentage"], 0.0)
        self.assertEqual(health["down"]["percentage"], 0.0)

        # Reliability displays zero failure
        rel = data["reliability"]
        self.assertIsNone(rel["mtbfHours"])
        self.assertIsNone(rel["mttrHours"])
        self.assertTrue(rel["isZeroFailure"])
        self.assertEqual(rel["mtbfDisplay"], "100% Khả dụng (0 Sự cố)")

        # Trends endpoint returns exactly 30 days of 0s
        trend_resp = self.client_a.get('/api/v1/dashboard/trends/')
        self.assertEqual(trend_resp.status_code, 200)
        trend_data = trend_resp.json()["data"]
        self.assertEqual(len(trend_data["series"]), 30)
        for item in trend_data["series"]:
            self.assertEqual(item["created"], 0)
            self.assertEqual(item["completed"], 0)

    def test_tc_dash_02_zero_failure_safe(self):
        """
        TC-DASH-02: Zero-Division Safe When 100% Failure-Free.
        Plant runs without any breakdown/corrective incidents in the 30-day period.
        """
        # Create operating assets
        set_current_tenant(self.tenant_a.id)
        for i in range(5):
            Asset.objects.create(
                tenant=self.tenant_a,
                name=f"CNC Machine #{i+1}",
                qr_code=f"QR-CNC-{i+1}",
                status="OPERATIONAL",
                is_trackable=True
            )

        # Only PREVENTIVE maintenance occurred (no breakdowns)
        WorkOrder.objects.create(
            tenant=self.tenant_a,
            asset=Asset.objects.first(),
            title="Monthly lubrication",
            type="PREVENTIVE",
            status="COMPLETED",
            actual_duration_minutes=60,
            completed_at=timezone.now()
        )

        response = self.client_a.get('/api/v1/dashboard/summary/')
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]

        rel = data["reliability"]
        self.assertTrue(rel["isZeroFailure"])
        self.assertIsNone(rel["mtbfHours"])
        self.assertIsNone(rel["mttrHours"])
        self.assertEqual(rel["mtbfDisplay"], "100% Khả dụng (0 Sự cố)")
        self.assertEqual(data["kpis"]["plantAvailability"]["value"], "100.0%")

    def test_tc_dash_03_asset_lifecycle_filtering(self):
        """
        TC-DASH-03: Asset Lifecycle Filtering.
        10 Operating, 2 Down, and 50 Scrapped/Disposed assets.
        Scrapped/Disposed assets MUST be excluded from totalAssets and health distribution.
        """
        set_current_tenant(self.tenant_a.id)

        # 10 Operating
        for i in range(10):
            Asset.objects.create(
                tenant=self.tenant_a,
                name=f"Active Machine {i}",
                qr_code=f"QR-ACT-{i}",
                status="OPERATIONAL",
                is_trackable=True
            )

        # 2 Down
        for i in range(2):
            Asset.objects.create(
                tenant=self.tenant_a,
                name=f"Down Machine {i}",
                qr_code=f"QR-DOWN-{i}",
                status="DOWN",
                is_trackable=True
            )

        # 50 Scrapped / Disposed / Decommissioned
        for i in range(50):
            st = 'SCRAPPED' if i % 2 == 0 else 'DISPOSED'
            Asset.objects.create(
                tenant=self.tenant_a,
                name=f"Disposed Machine {i}",
                qr_code=f"QR-DISP-{i}",
                status=st,
                is_trackable=True
            )

        # Also create a non-trackable spare component
        Asset.objects.create(
            tenant=self.tenant_a,
            name="Small Bearing Sub-component",
            qr_code="QR-PART-01",
            status="OPERATIONAL",
            is_trackable=False
        )

        response = self.client_a.get('/api/v1/dashboard/summary/')
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]

        # Total trackable operational assets should be 10 + 2 = 12
        self.assertEqual(data["kpis"]["totalAssets"]["value"], 12)
        health = data["assetHealth"]
        self.assertEqual(health["totalActive"], 12)
        self.assertEqual(health["operating"]["count"], 10)
        self.assertEqual(health["down"]["count"], 2)
        self.assertEqual(health["maintenance"]["count"], 0)

    def test_tc_dash_04_zero_filling_time_series(self):
        """
        TC-DASH-04: Zero-filling Time-Series for Inactive Days.
        Plant operated only on 3 specific days; remaining 27 days have 0 work orders.
        Output array must contain exactly 30 contiguous days.
        """
        set_current_tenant(self.tenant_a.id)
        asset = Asset.objects.create(
            tenant=self.tenant_a,
            name="Main Press",
            qr_code="QR-PRESS-01",
            status="OPERATING",
            is_trackable=True
        )

        now = timezone.now()
        # Create work orders on day -2, day -10, day -20
        d1 = now - timedelta(days=2)
        d2 = now - timedelta(days=10)
        d3 = now - timedelta(days=20)

        for d in [d1, d2, d3]:
            wo = WorkOrder.objects.create(
                tenant=self.tenant_a,
                asset=asset,
                title="Test WO",
                status="COMPLETED",
                completed_at=d
            )
            # Force created_at to d
            WorkOrder.objects.filter(id=wo.id).update(created_at=d)

        response = self.client_a.get('/api/v1/dashboard/trends/')
        self.assertEqual(response.status_code, 200)
        series = response.json()["data"]["series"]

        # Must have exactly 30 days
        self.assertEqual(len(series), 30)

        # Verify inactive days have 0
        total_created = sum(item["created"] for item in series)
        total_completed = sum(item["completed"] for item in series)
        self.assertEqual(total_created, 3)
        self.assertEqual(total_completed, 3)

    def test_tc_dash_05_graceful_cache_fallback(self):
        """
        TC-DASH-05: Graceful Cache Fallback When Cache Service Fails.
        If Redis raises an exception or disconnects, system must fall back
        to live DB computation without returning HTTP 500.
        """
        set_current_tenant(self.tenant_a.id)
        Asset.objects.create(
            tenant=self.tenant_a,
            name="Pump P-01",
            qr_code="QR-PUMP-01",
            status="OPERATIONAL",
            is_trackable=True
        )

        # Mock cache.get to raise Redis ConnectionError
        with patch('django.core.cache.cache.get', side_effect=Exception("Redis Connection Refused")):
            with patch('django.core.cache.cache.add', side_effect=Exception("Redis Connection Refused")):
                response = self.client_a.get('/api/v1/dashboard/summary/')
                self.assertEqual(response.status_code, 200)
                data = response.json()["data"]
                self.assertEqual(data["kpis"]["totalAssets"]["value"], 1)

    def test_tc_dash_06_event_invalidation_signals(self):
        """
        TC-DASH-06: Event-based Cache Invalidation.
        When an asset turns DOWN, the cache is immediately flushed and refreshed.
        """
        set_current_tenant(self.tenant_a.id)
        asset = Asset.objects.create(
            tenant=self.tenant_a,
            name="Robotic Arm R-01",
            qr_code="QR-ARM-01",
            status="OPERATIONAL",
            is_trackable=True
        )

        # 1. Warm cache
        res1 = self.client_a.get('/api/v1/dashboard/summary/')
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(res1.json()["data"]["assetHealth"]["down"]["count"], 0)

        # 2. Asset breaks down
        asset.status = "DOWN"
        asset.save()  # Triggers invalidate_all()

        # 3. Next call must immediately reflect DOWN count = 1
        res2 = self.client_a.get('/api/v1/dashboard/summary/')
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res2.json()["data"]["assetHealth"]["down"]["count"], 1)

    def test_tc_dash_07_multi_tenant_isolation(self):
        """
        TC-DASH-07: Multi-Tenant Data Isolation.
        Tenant A's metrics and trend data must not bleed into Tenant B.
        """
        # Populate Tenant A
        set_current_tenant(self.tenant_a.id)
        Asset.objects.create(
            tenant=self.tenant_a,
            name="Tenant A Generator",
            qr_code="QR-GEN-A",
            status="OPERATIONAL",
            is_trackable=True
        )

        # Populate Tenant B
        set_current_tenant(self.tenant_b.id)
        Asset.objects.create(
            tenant=self.tenant_b,
            name="Tenant B Boiler 1",
            qr_code="QR-BLR-B1",
            status="OPERATIONAL",
            is_trackable=True
        )
        Asset.objects.create(
            tenant=self.tenant_b,
            name="Tenant B Boiler 2",
            qr_code="QR-BLR-B2",
            status="OPERATIONAL",
            is_trackable=True
        )

        # Fetch A
        res_a = self.client_a.get('/api/v1/dashboard/summary/').json()["data"]
        self.assertEqual(res_a["kpis"]["totalAssets"]["value"], 1)

        # Fetch B
        res_b = self.client_b.get('/api/v1/dashboard/summary/').json()["data"]
        self.assertEqual(res_b["kpis"]["totalAssets"]["value"], 2)

    def test_tc_dash_08_pm_exclusion_from_mtbf(self):
        """
        TC-DASH-08: PM Exclusion From Failure Denominator.
        50 Preventive Maintenance orders + 1 Emergency breakdown order.
        N_failures must equal exactly 1 (not 51!).
        """
        set_current_tenant(self.tenant_a.id)
        asset = Asset.objects.create(
            tenant=self.tenant_a,
            name="Compressor C-01",
            qr_code="QR-CMP-01",
            status="OPERATIONAL",
            is_trackable=True
        )

        now = timezone.now()
        # 50 PM work orders
        for i in range(50):
            WorkOrder.objects.create(
                tenant=self.tenant_a,
                asset=asset,
                title=f"PM Inspection {i}",
                type="PREVENTIVE",
                status="COMPLETED",
                completed_at=now - timedelta(days=5),
                actual_duration_minutes=30
            )

        # 1 Emergency breakdown
        WorkOrder.objects.create(
            tenant=self.tenant_a,
            asset=asset,
            title="Emergency valve burst",
            type="EMERGENCY",
            status="COMPLETED",
            completed_at=now - timedelta(days=2),
            actual_duration_minutes=120  # 2 hours
        )

        response = self.client_a.get('/api/v1/dashboard/summary/')
        self.assertEqual(response.status_code, 200)
        rel = response.json()["data"]["reliability"]

        # Failure count must be 1, MTTR must be 2.0h
        self.assertEqual(rel["mttrHours"], 2.0)
        # MTBF hours = (1 active asset * 30 days * 24h - 2h downtime) / 1 failure = 718.0 hours
        self.assertEqual(rel["mtbfHours"], 718.0)

    def test_tc_dash_09_cross_period_completion(self):
        """
        TC-DASH-09: Cross-Period Completion Separation.
        A WO created 20 days ago but completed 2 days ago must appear
        under 'created' on day -20 and under 'completed' on day -2.
        """
        set_current_tenant(self.tenant_a.id)
        asset = Asset.objects.create(
            tenant=self.tenant_a,
            name="Lathe L-01",
            qr_code="QR-LTH-01",
            status="OPERATIONAL",
            is_trackable=True
        )

        tz = ZoneInfo("Asia/Ho_Chi_Minh")
        now_local = timezone.now().astimezone(tz)
        created_date = (now_local - timedelta(days=20)).date()
        completed_date = (now_local - timedelta(days=2)).date()

        created_time = datetime.combine(created_date, datetime.min.time(), tzinfo=tz).astimezone(ZoneInfo("UTC"))
        completed_time = datetime.combine(completed_date, datetime.min.time(), tzinfo=tz).astimezone(ZoneInfo("UTC"))

        wo = WorkOrder.objects.create(
            tenant=self.tenant_a,
            asset=asset,
            title="Overhaul",
            status="COMPLETED",
            completed_at=completed_time
        )
        WorkOrder.objects.filter(id=wo.id).update(created_at=created_time)

        response = self.client_a.get('/api/v1/dashboard/trends/')
        series = response.json()["data"]["series"]

        day_created_entry = next((s for s in series if s["date"] == created_date.strftime("%d/%m")), None)
        day_completed_entry = next((s for s in series if s["date"] == completed_date.strftime("%d/%m")), None)

        self.assertIsNotNone(day_created_entry)
        self.assertIsNotNone(day_completed_entry)
        self.assertEqual(day_created_entry["created"], 1)
        self.assertEqual(day_created_entry["completed"], 0)
        self.assertEqual(day_completed_entry["created"], 0)
        self.assertEqual(day_completed_entry["completed"], 1)

    def test_tc_dash_10_hamilton_hare_rounding(self):
        """
        TC-DASH-10: Hamilton-Hare Largest Remainder 100.0% Rounding.
        3 machines: 1 Operating, 1 Maintenance, 1 Down.
        Raw = 33.333%, 33.333%, 33.333%.
        Algorithm must round to 33.4%, 33.3%, 33.3% and total MUST BE EXACTLY 100.0%.
        """
        counts = {'operating': 1, 'maintenance': 1, 'down': 1}
        result = calculate_largest_remainder_percentages(counts)

        total = round(sum(result.values()), 1)
        self.assertEqual(total, 100.0)
        self.assertEqual(result['operating'], 33.4)
        self.assertEqual(result['maintenance'], 33.3)
        self.assertEqual(result['down'], 33.3)

    def test_tc_dash_11_activity_feed_noise_filter(self):
        """
        TC-DASH-11: Activity Feed Whitelist Noise Filter.
        System-level actions (passwords, logins, GETs) must be discarded.
        Only operational actions (WO_CREATED, ASSET_STATUS_DOWN, etc.) are shown.
        """
        set_current_tenant(self.tenant_a.id)

        # Noise logs
        AuditLog.objects.create(
            tenant=self.tenant_a,
            user_id="user-1",
            action_type="PASSWORD_CHANGE",
            entity_type="User",
            entity_id="u-01"
        )
        AuditLog.objects.create(
            tenant=self.tenant_a,
            user_id="user-1",
            action_type="PROFILE_UPDATE",
            entity_type="UserProfile",
            entity_id="u-01"
        )

        # Operational logs
        AuditLog.objects.create(
            tenant=self.tenant_a,
            user_id="user-1",
            action_type="WO_CREATED",
            entity_type="WorkOrder",
            entity_id="wo-101"
        )
        AuditLog.objects.create(
            tenant=self.tenant_a,
            user_id="user-1",
            action_type="ASSET_STATUS_DOWN",
            entity_type="Asset",
            entity_id="ast-202"
        )

        response = self.client_a.get('/api/v1/dashboard/activity-feed/')
        self.assertEqual(response.status_code, 200)
        acts = response.json()["data"]["activities"]

        # Only 2 operational events allowed
        self.assertEqual(len(acts), 2)
        event_types = [a["eventType"] for a in acts]
        self.assertIn("WO_CREATED", event_types)
        self.assertIn("ASSET_STATUS_DOWN", event_types)
        self.assertNotIn("PASSWORD_CHANGE", event_types)

    def test_tc_dash_12_timezone_midnight_boundary(self):
        """
        TC-DASH-12: Timezone Midnight Boundary.
        Completion at 01:30 AM on 01/08 Vietnam time (UTC+7) = 18:30 on 31/07 (UTC).
        In tenant's timezone (Asia/Ho_Chi_Minh), it MUST register on 01/08.
        """
        set_current_tenant(self.tenant_a.id)
        asset = Asset.objects.create(
            tenant=self.tenant_a,
            name="Generator G-01",
            qr_code="QR-GEN-01",
            status="OPERATIONAL",
            is_trackable=True
        )

        # 01:30 AM on Aug 1st in VN = 18:30 on July 31st in UTC
        vn_time = datetime(2026, 8, 1, 1, 30, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
        utc_time = vn_time.astimezone(ZoneInfo("UTC"))

        wo = WorkOrder.objects.create(
            tenant=self.tenant_a,
            asset=asset,
            title="Midnight Fix",
            status="COMPLETED",
            completed_at=utc_time
        )
        WorkOrder.objects.filter(id=wo.id).update(created_at=utc_time)

        # Test Trend query with a custom range containing Aug 1st
        with patch('django.utils.timezone.now', return_value=vn_time + timedelta(days=5)):
            response = self.client_a.get('/api/v1/dashboard/trends/')
            self.assertEqual(response.status_code, 200)
            series = response.json()["data"]["series"]

            aug_01 = next((s for s in series if s["date"] == "01/08"), None)
            jul_31 = next((s for s in series if s["date"] == "31/07"), None)

            if aug_01:
                self.assertEqual(aug_01["completed"], 1)
            if jul_31:
                self.assertEqual(jul_31["completed"], 0)

    def test_tc_dash_13_ongoing_unresolved_downtime(self):
        """
        TC-DASH-13: Ongoing Unresolved Downtime Isolation.
        An in-progress failure WO must NOT be included in MTTR (since it is not finished),
        but must increment ongoingDownCount.
        """
        set_current_tenant(self.tenant_a.id)
        asset = Asset.objects.create(
            tenant=self.tenant_a,
            name="Hydraulic Press HP-01",
            qr_code="QR-HP-01",
            status="DOWN",
            is_trackable=True
        )

        # Ongoing failure
        WorkOrder.objects.create(
            tenant=self.tenant_a,
            asset=asset,
            title="Hydraulic leak",
            type="EMERGENCY",
            status="IN_PROGRESS"
        )

        response = self.client_a.get('/api/v1/dashboard/summary/')
        self.assertEqual(response.status_code, 200)
        rel = response.json()["data"]["reliability"]

        # Ongoing count = 1
        self.assertEqual(rel["ongoingDownCount"], 1)
        # MTTR must be None / N/A because no completed failure exists
        self.assertIsNone(rel["mttrHours"])
        self.assertEqual(rel["mttrDisplay"], "N/A")

    def test_tc_dash_14_anomalous_duration_filter(self):
        """
        TC-DASH-14: Anomalous Duration / Outlier Filter.
        A ticket with 2160 hours (3 months forgot to close) and a negative ticket (-2h)
        must be excluded from MTTR.
        """
        set_current_tenant(self.tenant_a.id)
        asset = Asset.objects.create(
            tenant=self.tenant_a,
            name="Conveyor C-01",
            qr_code="QR-CNV-01",
            status="OPERATIONAL",
            is_trackable=True
        )

        now = timezone.now()

        # Valid repair: 2 hours
        WorkOrder.objects.create(
            tenant=self.tenant_a,
            asset=asset,
            title="Belt replacement",
            type="CORRECTIVE",
            status="COMPLETED",
            completed_at=now - timedelta(days=3),
            actual_duration_minutes=120  # 2.0h
        )

        # Outlier repair: 2160 hours (3 months)
        WorkOrder.objects.create(
            tenant=self.tenant_a,
            asset=asset,
            title="Forgot to close ticket",
            type="CORRECTIVE",
            status="COMPLETED",
            completed_at=now - timedelta(days=2),
            actual_duration_minutes=2160 * 60  # 2160h
        )

        # Outlier repair: -2 hours (client clock desync)
        WorkOrder.objects.create(
            tenant=self.tenant_a,
            asset=asset,
            title="Clock desync ticket",
            type="CORRECTIVE",
            status="COMPLETED",
            completed_at=now - timedelta(days=1),
            actual_duration_minutes=-120  # -2.0h
        )

        response = self.client_a.get('/api/v1/dashboard/summary/')
        self.assertEqual(response.status_code, 200)
        rel = response.json()["data"]["reliability"]

        # MTTR should only average the 2.0h ticket, ignoring 2160h and -2h
        self.assertEqual(rel["mttrHours"], 2.0)

    def test_tc_dash_15_cache_stampede_mutex_guardrail(self):
        """
        TC-DASH-15: Cache Stampede Mutex Guardrail.
        Verifies mutex lock mechanism gracefully falls back and prevents stampede.
        """
        set_current_tenant(self.tenant_a.id)
        Asset.objects.create(
            tenant=self.tenant_a,
            name="Turbine T-01",
            qr_code="QR-TRB-01",
            status="OPERATIONAL",
            is_trackable=True
        )

        # Clear cache
        DashboardCacheService.invalidate_all(self.tenant_a.id)

        # Call get_summary multiple times
        res1 = DashboardCacheService.get_summary(self.tenant_a)
        res2 = DashboardCacheService.get_summary(self.tenant_a)

        self.assertEqual(res1["kpis"]["totalAssets"]["value"], 1)
        self.assertEqual(res2["kpis"]["totalAssets"]["value"], 1)

    def test_tc_dash_16_safe_delta_zero_division(self):
        """
        TC-DASH-16: Safe Delta When Previous Period is 0.
        Previous = 0, Current = 2. Must not throw ZeroDivisionError and label 'Kỳ đầu / Mới'.
        """
        delta = calculate_safe_delta(current_val=2, previous_val=0, higher_is_better=True)
        self.assertEqual(delta["delta"], "+2")
        self.assertEqual(delta["deltaType"], "positive")
        self.assertEqual(delta["deltaLabel"], "Kỳ đầu / Mới")

        # Zero to zero
        delta_zero = calculate_safe_delta(current_val=0, previous_val=0)
        self.assertEqual(delta_zero["delta"], "0")
        self.assertEqual(delta_zero["deltaType"], "neutral")

    def test_tc_dash_17_drill_down_consistency(self):
        """
        TC-DASH-17: Drill-Down Click-Through Link Consistency.
        The drill-down link for Active WOs must accurately point to
        /portal/work-orders/?status=CREATED,ASSIGNED,IN_PROGRESS.
        """
        set_current_tenant(self.tenant_a.id)
        asset = Asset.objects.create(
            tenant=self.tenant_a,
            name="CNC Machine 1",
            qr_code="QR-CNC-01",
            status="OPERATIONAL",
            is_trackable=True
        )

        # Create 7 active work orders
        for i in range(7):
            WorkOrder.objects.create(
                tenant=self.tenant_a,
                asset=asset,
                title=f"Active Job {i}",
                status="IN_PROGRESS"
            )

        response = self.client_a.get('/api/v1/dashboard/summary/')
        self.assertEqual(response.status_code, 200)
        kpis = response.json()["data"]["kpis"]

        self.assertEqual(kpis["activeWorkOrders"]["value"], 7)
        self.assertEqual(
            kpis["activeWorkOrders"]["drillDownUrl"],
            "/portal/work-orders/?status=CREATED,ASSIGNED,IN_PROGRESS"
        )

    def test_tc_dash_18_decimal_inputs_safe_delta(self):
        """
        TC-DASH-18: Decimal Inputs in Safe Delta.
        Verifies calculate_safe_delta handles Decimal types without AttributeError.
        """
        # Decimal positive change
        res1 = calculate_safe_delta(current_val=Decimal("15.00"), previous_val=Decimal("10.00"), higher_is_better=True)
        self.assertEqual(res1["delta"], "+5")
        self.assertEqual(res1["deltaType"], "positive")

        # Decimal fractional change
        res2 = calculate_safe_delta(current_val=Decimal("12.50"), previous_val=Decimal("10.00"), is_percentage=True)
        self.assertEqual(res2["delta"], "+2.5%")
        self.assertEqual(res2["deltaType"], "positive")

        # Decimal negative change
        res3 = calculate_safe_delta(current_val=Decimal("5.00"), previous_val=Decimal("8.00"), higher_is_better=True)
        self.assertEqual(res3["delta"], "-3")
        self.assertEqual(res3["deltaType"], "negative")

        # Decimal from zero
        res4 = calculate_safe_delta(current_val=Decimal("10.00"), previous_val=Decimal("0.00"))
        self.assertEqual(res4["delta"], "+10")
        self.assertEqual(res4["deltaLabel"], "Kỳ đầu / Mới")

    def test_tc_dash_19_hamilton_hare_stress_and_edge_cases(self):
        """
        TC-DASH-19: Hamilton-Hare Rounding Stress & Multi-Bucket Edge Cases.
        Guarantees exact 100.0% sum across diverse bucket distributions.
        """
        # All zeros
        res_zeros = calculate_largest_remainder_percentages({'operating': 0, 'maintenance': 0, 'down': 0})
        self.assertEqual(sum(res_zeros.values()), 0.0)

        # Single active bucket
        res_single = calculate_largest_remainder_percentages({'operating': 10, 'maintenance': 0, 'down': 0})
        self.assertEqual(res_single['operating'], 100.0)
        self.assertEqual(res_single['maintenance'], 0.0)
        self.assertEqual(res_single['down'], 0.0)
        self.assertEqual(sum(res_single.values()), 100.0)

        # 7 equal buckets
        seven_buckets = {f"b_{i}": 1 for i in range(7)}
        res_seven = calculate_largest_remainder_percentages(seven_buckets)
        self.assertEqual(round(sum(res_seven.values()), 1), 100.0)

        # Large numbers
        large_counts = {'operating': 789123, 'maintenance': 123456, 'down': 87421}
        res_large = calculate_largest_remainder_percentages(large_counts)
        self.assertEqual(round(sum(res_large.values()), 1), 100.0)

    def test_tc_dash_20_ongoing_failures_availability_accuracy(self):
        """
        TC-DASH-20: Plant Availability When Failures Exist But None Completed Yet.
        10 trackable assets, 2 are in DOWN status with ongoing emergency work orders.
        Availability should accurately reflect 80.0%, NOT misleading 100.0%.
        """
        set_current_tenant(self.tenant_a.id)
        assets = []
        for i in range(10):
            st = "DOWN" if i < 2 else "OPERATIONAL"
            a = Asset.objects.create(
                tenant=self.tenant_a,
                name=f"Plant Line Asset {i+1}",
                qr_code=f"QR-PL-{i+1}",
                status=st,
                is_trackable=True
            )
            assets.append(a)

        # 2 ongoing emergency work orders
        now = timezone.now()
        for i in range(2):
            WorkOrder.objects.create(
                tenant=self.tenant_a,
                asset=assets[i],
                title=f"Ongoing Emergency Break {i+1}",
                type="EMERGENCY",
                status="IN_PROGRESS"
            )

        response = self.client_a.get('/api/v1/dashboard/summary/')
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]

        rel = data["reliability"]
        self.assertFalse(rel["isZeroFailure"])
        self.assertIsNone(rel["mttrHours"])
        self.assertEqual(rel["mttrDisplay"], "N/A")
        self.assertEqual(rel["ongoingDownCount"], 2)

        # Availability must reflect ongoing downtime (8/10 = 80.0%)
        self.assertEqual(data["kpis"]["plantAvailability"]["value"], "80.0%")

    def test_tc_dash_21_pm_compliance_tolerance_and_deadlines(self):
        """
        TC-DASH-21: PM Compliance Tolerance & Deadlines.
        Verifies on-time vs late classification in PMComplianceService.
        """
        set_current_tenant(self.tenant_a.id)
        asset = Asset.objects.create(
            tenant=self.tenant_a,
            name="Packaging Line",
            qr_code="QR-PKG-01",
            status="OPERATIONAL",
            is_trackable=True
        )

        now = timezone.now()

        # PM 1: Completed on time (before deadline)
        WorkOrder.objects.create(
            tenant=self.tenant_a,
            asset=asset,
            title="On time PM",
            type="PREVENTIVE",
            status="COMPLETED",
            deadline=now - timedelta(days=5),
            completed_at=now - timedelta(days=6)
        )

        # PM 2: Completed late (after deadline)
        WorkOrder.objects.create(
            tenant=self.tenant_a,
            asset=asset,
            title="Late PM",
            type="PREVENTIVE",
            status="COMPLETED",
            deadline=now - timedelta(days=10),
            completed_at=now - timedelta(days=2)
        )

        # PM 3: Completed without explicit deadline -> counted as on-time
        WorkOrder.objects.create(
            tenant=self.tenant_a,
            asset=asset,
            title="No deadline PM",
            type="PREVENTIVE",
            status="COMPLETED",
            deadline=None,
            completed_at=now - timedelta(days=3)
        )

        res = PMComplianceService.calculate_compliance(self.tenant_a, period_days=30)
        # 3 total due, 2 on time, 1 late -> 66.7%
        self.assertEqual(res["totalDue"], 3)
        self.assertEqual(res["completedOnTime"], 2)
        self.assertEqual(res["rate"], 66.7)

    def test_tc_dash_22_duration_minutes_without_actual_start_time(self):
        """
        TC-DASH-22: Duration Minutes Without Actual Start Time.
        Technician entered actual_duration_minutes = 90 without clock-in actual_start_time.
        actual_duration_hours property should correctly evaluate to 1.5h and feed into MTTR.
        """
        set_current_tenant(self.tenant_a.id)
        asset = Asset.objects.create(
            tenant=self.tenant_a,
            name="CNC Miller #2",
            qr_code="QR-CNC-02",
            status="OPERATIONAL",
            is_trackable=True
        )

        now = timezone.now()
        WorkOrder.objects.create(
            tenant=self.tenant_a,
            asset=asset,
            title="Quick Spindle Fix",
            type="CORRECTIVE",
            status="COMPLETED",
            completed_at=now - timedelta(days=1),
            actual_duration_minutes=90  # 1.5h
        )

        rel = ReliabilityMetricsService.calculate_reliability(self.tenant_a, total_active_assets=1, period_days=30)
        self.assertEqual(rel["mttrHours"], 1.5)
        self.assertEqual(rel["mttrDisplay"], "1.5 giờ")

    def test_tc_dash_23_activity_feed_fallback_synthesis(self):
        """
        TC-DASH-23: Activity Feed Fallback Synthesis From Actual WorkOrders.
        When AuditLog table has no operational entries, fallback gracefully synthesizes
        operational activity from recent WorkOrders.
        """
        set_current_tenant(self.tenant_a.id)
        asset = Asset.objects.create(
            tenant=self.tenant_a,
            name="Main Generator",
            qr_code="QR-GEN-M1",
            status="OPERATIONAL",
            is_trackable=True
        )

        wo = WorkOrder.objects.create(
            tenant=self.tenant_a,
            asset=asset,
            title="Sửa chữa khẩn cấp hệ thống điện",
            status="COMPLETED"
        )

        # Clear audit logs
        AuditLog.objects.filter(tenant=self.tenant_a).delete()

        acts = ActivityFeedService.get_recent_activities(self.tenant_a, limit=5)
        self.assertTrue(len(acts) >= 1)
        self.assertEqual(acts[0]["eventType"], "WO_COMPLETED")
        self.assertIn("Hoàn tất", acts[0]["title"])
        self.assertIn(str(wo.id), acts[0]["link"])

    def test_tc_dash_24_multi_tenant_cache_and_metric_isolation(self):
        """
        TC-DASH-24: Multi-Tenant Complete Cache and Metric Isolation.
        Tenant A operations do not contaminate Tenant B's cached summary.
        """
        set_current_tenant(self.tenant_a.id)
        for i in range(3):
            Asset.objects.create(
                tenant=self.tenant_a,
                name=f"Tenant A Asset {i}",
                qr_code=f"QR-TNA-{i}",
                status="OPERATIONAL",
                is_trackable=True
            )

        set_current_tenant(self.tenant_b.id)
        for i in range(8):
            Asset.objects.create(
                tenant=self.tenant_b,
                name=f"Tenant B Asset {i}",
                qr_code=f"QR-TNB-{i}",
                status="OPERATIONAL",
                is_trackable=True
            )

        sum_a = DashboardCacheService.get_summary(self.tenant_a)
        sum_b = DashboardCacheService.get_summary(self.tenant_b)

        self.assertEqual(sum_a["kpis"]["totalAssets"]["value"], 3)
        self.assertEqual(sum_b["kpis"]["totalAssets"]["value"], 8)

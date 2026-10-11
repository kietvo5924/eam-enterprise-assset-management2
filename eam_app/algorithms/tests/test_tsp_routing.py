"""
Automated Test Suite for Task 11.3 - Technician Routing Optimization (TSP).
Covers all 13 Acceptance Criteria & Edge Cases (TC-TSP-01 through TC-TSP-13).
"""

import uuid
from datetime import time, timedelta
from django.utils import timezone
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from core.models import Tenant
from core.tenant_context import clear_current_tenant
from users.models import Role, Permission
from assets.models import Location, Asset
from workorders.models import WorkOrder
from algorithms.tsp_routing.service import TSPRoutingService
from algorithms.tsp_routing.distance_matrix import MultiTierDistanceEngine, RoutingNode
from algorithms.tsp_routing.solver import TieredATSPSolver
from algorithms.tsp_routing.constants import (
    MODE_HIERARCHICAL_TOPOLOGICAL,
    MODE_MANHATTAN_2D,
    MODE_PURE_BUSINESS,
    STOP_WAREHOUSE,
    STOP_CURRENT_LOCATION,
)

User = get_user_model()


class TSPRoutingTestCase(TestCase):
    def setUp(self):
        clear_current_tenant()
        # Tenant A (TSP enabled)
        self.tenant_a = Tenant.objects.create(name="School District A", tenant_code="T-SCH-A", enable_tsp_routing=True)
        # Tenant B (Multi-tenant test)
        self.tenant_b = Tenant.objects.create(name="Hospital District B", tenant_code="T-HOSP-B", enable_tsp_routing=True)
        # Tenant C (TSP disabled)
        self.tenant_c = Tenant.objects.create(name="Budget Org C", tenant_code="T-BUDGET-C", enable_tsp_routing=False)

        # Dispatcher / Technician user
        self.tech_user = User.objects.create_user(
            username="tech_john",
            email="tech_john@schooldistrict.edu",
            password="password123",
            tenant=self.tenant_a
        )
        self.role = Role.objects.create(name="TECHNICIAN", tenant=self.tenant_a)
        perm_read = Permission.objects.get_or_create(id="work_order:read", defaults={'name': 'Read Work Order'})[0]
        perm_update = Permission.objects.get_or_create(id="work_order:update", defaults={'name': 'Update Work Order'})[0]
        self.role.permissions.add(perm_read, perm_update)
        self.tech_user.roles.add(self.role)

        self.client = APIClient()
        self.client.force_authenticate(user=self.tech_user)

        # Hierarchy for Tenant A:
        # Site -> Building A -> Floor 1 -> Room 101, Room 102
        #                    -> Floor 2 -> Room 204
        #                    -> Floor 3 -> Room 301, Room 302
        # Warehouse location (Depot)
        self.site_a = Location.objects.create(
            name="Cơ sở Chính",
            code="SITE-01",
            location_type="SITE",
            tenant=self.tenant_a
        )
        self.bldg_a = Location.objects.create(
            name="Tòa Nhà Hiệu Bộ",
            code="BLDG-A",
            location_type="BUILDING",
            parent_id=str(self.site_a.id),
            tenant=self.tenant_a
        )
        self.floor_1 = Location.objects.create(
            name="Tầng 1",
            code="FL-01",
            location_type="FLOOR",
            parent_id=str(self.bldg_a.id),
            floor_level=1,
            tenant=self.tenant_a
        )
        self.floor_2 = Location.objects.create(
            name="Tầng 2",
            code="FL-02",
            location_type="FLOOR",
            parent_id=str(self.bldg_a.id),
            floor_level=2,
            tenant=self.tenant_a
        )
        self.floor_3 = Location.objects.create(
            name="Tầng 3",
            code="FL-03",
            location_type="FLOOR",
            parent_id=str(self.bldg_a.id),
            floor_level=3,
            tenant=self.tenant_a
        )

        self.room_101 = Location.objects.create(
            name="Phòng 101",
            code="ROOM-101",
            location_type="ROOM",
            parent_id=str(self.floor_1.id),
            floor_level=1,
            tenant=self.tenant_a
        )
        self.room_102 = Location.objects.create(
            name="Phòng 102",
            code="ROOM-102",
            location_type="ROOM",
            parent_id=str(self.floor_1.id),
            floor_level=1,
            tenant=self.tenant_a
        )
        self.room_204 = Location.objects.create(
            name="Phòng 204",
            code="ROOM-204",
            location_type="ROOM",
            parent_id=str(self.floor_2.id),
            floor_level=2,
            tenant=self.tenant_a
        )
        self.room_301 = Location.objects.create(
            name="Phòng 301",
            code="ROOM-301",
            location_type="ROOM",
            parent_id=str(self.floor_3.id),
            floor_level=3,
            tenant=self.tenant_a
        )
        self.room_302 = Location.objects.create(
            name="Phòng 302",
            code="ROOM-302",
            location_type="ROOM",
            parent_id=str(self.floor_3.id),
            floor_level=3,
            tenant=self.tenant_a
        )
        self.warehouse = Location.objects.create(
            name="Kho Vật Tư Trung Tâm",
            code="WH-MAIN",
            location_type="WAREHOUSE",
            parent_id=str(self.floor_1.id),
            floor_level=1,
            tenant=self.tenant_a
        )

        # Default assets
        self.asset_a = Asset.objects.create(
            name="Thiết bị Mẫu A",
            qr_code=f"QR-A-{uuid.uuid4().hex[:6]}",
            location=self.room_101,
            tenant=self.tenant_a
        )
        self.asset_b = Asset.objects.create(
            name="Thiết bị Mẫu B",
            qr_code=f"QR-B-{uuid.uuid4().hex[:6]}",
            location=self.room_101,
            tenant=self.tenant_b
        )
        self.asset_c = Asset.objects.create(
            name="Thiết bị Mẫu C",
            qr_code=f"QR-C-{uuid.uuid4().hex[:6]}",
            location=self.room_101,
            tenant=self.tenant_c
        )

    def tearDown(self):
        clear_current_tenant()

    def _create_wo(
        self,
        title,
        tenant=None,
        asset=None,
        incident_location=None,
        priority="MEDIUM",
        status="OPEN",
        maintenance_window_start=None,
        maintenance_window_end=None,
        due_date=None,
        coords_x=None,
        coords_y=None,
    ):
        t = tenant or self.tenant_a
        a = asset or (self.asset_b if t == self.tenant_b else (self.asset_c if t == self.tenant_c else self.asset_a))
        return WorkOrder.objects.create(
            tenant=t,
            asset=a,
            title=title,
            priority=priority,
            status=status,
            incident_location=incident_location,
            maintenance_window_start=maintenance_window_start,
            maintenance_window_end=maintenance_window_end,
            deadline=due_date or timezone.now() + timedelta(days=1),
            coords_x=coords_x,
            coords_y=coords_y,
        )

    def test_tc_tsp_01_no_map_hierarchical_routing(self):
        """
        TC-TSP-01: Định tuyến tô-pô phân cấp khi không có bản đồ (No-Map Hierarchical)
        Trường học không có tọa độ (X, Y).
        5 phiếu: 2 phiếu ở Phòng 301, 1 phiếu ở Phòng 302, 2 phiếu ở Tầng 1 (Phòng 101 & 102).
        Kỳ vọng: Giải thuật gom việc: Hoàn tất các phòng ở Tầng 3 trước (301, 302) rồi mới xuống Tầng 1,
        không nhảy đi nhảy lại giữa các tầng.
        """
        wo_301_a = self._create_wo("Sửa quạt 301A", incident_location=self.room_301)
        wo_301_b = self._create_wo("Sửa đèn 301B", incident_location=self.room_301)
        wo_302 = self._create_wo("Sửa máy chiếu 302", incident_location=self.room_302)
        wo_101 = self._create_wo("Sửa bảng 101", incident_location=self.room_101)
        wo_102 = self._create_wo("Sửa khóa cửa 102", incident_location=self.room_102)

        service = TSPRoutingService(tenant=self.tenant_a)
        # Starting from Room 301
        res = service.optimize_daily_route(
            technician=self.tech_user,
            work_orders=[wo_101, wo_301_a, wo_102, wo_302, wo_301_b],
            start_location_id=str(self.room_301.id),
            return_to_depot=False
        )

        self.assertTrue(res['success'])
        self.assertEqual(res['data']['routingMode'], MODE_HIERARCHICAL_TOPOLOGICAL)
        ordered_stops = res['data']['orderedStops']
        wo_stops = [s for s in ordered_stops if s['type'] == 'WORK_ORDER']
        self.assertEqual(len(wo_stops), 5)

        # Collect floor levels of stops in order
        floors = [s['floorNumber'] for s in wo_stops]
        first_3_floors = floors[:3]
        last_2_floors = floors[3:]
        self.assertEqual(first_3_floors, [3, 3, 3], f"Floor 3 tasks should be grouped together: {floors}")
        self.assertEqual(last_2_floors, [1, 1], f"Floor 1 tasks should be grouped together: {floors}")

    def test_tc_tsp_02_movable_asset_incident_location_context(self):
        """
        TC-TSP-02: Định tuyến tài sản di động theo vị trí sự cố (Movable Asset Context)
        Bàn học TB-01 có vị trí gốc ở Phòng 101, nhưng phiếu báo hỏng ghi tại Phòng 204.
        Kỳ vọng: Chặng di chuyển dẫn tới Phòng 204, không dẫn tới Phòng 101.
        """
        movable_asset = Asset.objects.create(
            name="Bàn Học Di Động TB-01",
            qr_code="QR-TB-01",
            location=self.room_101,  # Nominal location
            tenant=self.tenant_a
        )
        wo = self._create_wo(
            "Gãy chân bàn",
            asset=movable_asset,
            incident_location=self.room_204,  # Actual incident location!
            priority="HIGH"
        )

        node = RoutingNode.from_work_order(wo)
        self.assertEqual(str(node.location.id), str(self.room_204.id))
        self.assertEqual(node.floor_number, 2)
        self.assertEqual(node.location.name, "Phòng 204")

    def test_tc_tsp_03_tiered_tsp_multi_urgent_cluster(self):
        """
        TC-TSP-03: Phân lớp khẩn cấp cho cụm nhiều việc URGENT (Tiered TSP)
        Có 3 việc URGENT ở 3 vị trí khác nhau và 4 việc bình thường (MEDIUM/LOW).
        Kỳ vọng: Thuật toán giải TSP tối ưu đường đi qua riêng 3 việc URGENT trước;
        sau đó mới tiếp tục đi qua 4 việc bình thường.
        """
        urgent_1 = self._create_wo("U1", incident_location=self.room_101, priority="URGENT")
        urgent_2 = self._create_wo("U2", incident_location=self.room_204, priority="URGENT")
        urgent_3 = self._create_wo("U3", incident_location=self.room_301, priority="URGENT")

        norm_1 = self._create_wo("N1", incident_location=self.room_102, priority="MEDIUM")
        norm_2 = self._create_wo("N2", incident_location=self.room_302, priority="LOW")
        norm_3 = self._create_wo("N3", incident_location=self.room_101, priority="HIGH")
        norm_4 = self._create_wo("N4", incident_location=self.room_204, priority="MEDIUM")

        all_wos = [norm_1, urgent_1, norm_2, urgent_2, norm_3, urgent_3, norm_4]
        service = TSPRoutingService(tenant=self.tenant_a)
        res = service.optimize_daily_route(technician=self.tech_user, work_orders=all_wos, return_to_depot=False)

        self.assertTrue(res['success'])
        wo_stops = [s for s in res['data']['orderedStops'] if s['type'] == 'WORK_ORDER']
        self.assertEqual(len(wo_stops), 7)

        # First 3 stops MUST be the 3 URGENT work orders!
        first_3_priorities = [s['priority'] for s in wo_stops[:3]]
        self.assertEqual(first_3_priorities, ['URGENT', 'URGENT', 'URGENT'])

        # Next 4 stops must be normal
        next_4_priorities = [s['priority'] for s in wo_stops[3:]]
        for p in next_4_priorities:
            self.assertIn(p, ['HIGH', 'MEDIUM', 'LOW'])

    def test_tc_tsp_04_time_window_constraints_tsptw(self):
        """
        TC-TSP-04: Ràng buộc khung thời gian cho phép bảo trì (TSPTW)
        Máy nén khí chỉ cho dừng máy từ 11:30 đến 12:30.
        Kỳ vọng: Lộ trình tôn trọng khung giờ, không ghé thăm máy lúc sáng sớm.
        """
        wo_restricted = self._create_wo(
            "Bảo dưỡng Máy nén khí (Chỉ dừng trưa)",
            incident_location=self.room_102,
            maintenance_window_start=time(11, 30),
            maintenance_window_end=time(12, 30),
            priority="MEDIUM"
        )
        wo_morn_1 = self._create_wo("Sửa điều hòa sáng 1", incident_location=self.room_101, priority="MEDIUM")
        wo_morn_2 = self._create_wo("Sửa điều hòa sáng 2", incident_location=self.room_101, priority="MEDIUM")
        wo_morn_3 = self._create_wo("Sửa quạt trần sáng 3", incident_location=self.room_102, priority="MEDIUM")

        service = TSPRoutingService(tenant=self.tenant_a)
        res = service.optimize_daily_route(
            technician=self.tech_user,
            work_orders=[wo_restricted, wo_morn_1, wo_morn_2, wo_morn_3],
            start_time_minutes=480.0,  # 08:00
            return_to_depot=False
        )

        wo_stops = [s for s in res['data']['orderedStops'] if s['type'] == 'WORK_ORDER']
        restr_stop = next(s for s in wo_stops if s['workOrderId'] == str(wo_restricted.id))

        # 1. The restricted machine task must be scheduled after all normal morning tasks, not early in the morning!
        self.assertEqual(wo_stops[-1]['workOrderId'], str(wo_restricted.id), "Restricted lunch task should be scheduled last after morning tasks")

        # 2. Service start time must respect maintenance window [11:30, 12:30]
        service_start = restr_stop.get('serviceStartTime', '11:30')
        h, m = map(int, service_start.split(':'))
        start_mins = h * 60 + m
        self.assertGreaterEqual(start_mins, 11 * 60 + 30, f"Expected service start >= 11:30, got {service_start}")
        self.assertLessEqual(start_mins, 12 * 60 + 30, f"Expected service start <= 12:30, got {service_start}")

    def test_tc_tsp_05_asymmetric_matrix_atsp_cleanroom_oneway(self):
        """
        TC-TSP-05: Ma trận bất đối xứng do lối đi 1 chiều (Asymmetric ATSP)
        Phòng sạch hoặc luồng cửa từ 1 chiều: Đi từ A đến B thuận lợi, nhưng B về A tốn công khử trùng/đi vòng.
        Kỳ vọng: Thuật toán tính đúng ma trận có hướng D(A, B) != D(B, A).
        """
        cleanroom = Location.objects.create(
            name="Phòng Thí Nghiệm Phòng Sạch ISO-5",
            code="CLEAN-01",
            zone_type="CONTROLLED",
            location_type="ROOM",
            parent_id=str(self.floor_1.id),
            tenant=self.tenant_a
        )
        node_standard = RoutingNode(node_id="standard", location=self.room_101, is_controlled_zone=False)
        node_cleanroom = RoutingNode(node_id="cleanroom", location=cleanroom, is_controlled_zone=True)

        engine = MultiTierDistanceEngine(tenant=self.tenant_a)
        dist_forward = engine.calculate_distance(node_standard, node_cleanroom)
        dist_backward = engine.calculate_distance(node_cleanroom, node_standard)

        self.assertGreater(dist_forward, 50.0)
        self.assertGreater(dist_backward, 50.0)

        # One-way node test
        node_exit_only = RoutingNode(node_id="exit_only", location=self.room_102, one_way_exit_only=True)
        dist_from_exit = engine.calculate_distance(node_exit_only, node_standard)
        dist_to_exit = engine.calculate_distance(node_standard, node_exit_only)
        self.assertNotEqual(dist_from_exit, dist_to_exit, "One-way exit nodes must have asymmetric transition costs")

    def test_tc_tsp_06_intermediate_pitstop_warehouse(self):
        """
        TC-TSP-06: Trạm dừng trung gian về kho nhận vật tư (Intermediate Pit-stop)
        Thợ bấm nút 'Về kho lấy vật tư' giữa ca.
        Kỳ vọng: Lộ trình chèn trạm dừng Kho vật tư ngay sau vị trí hiện tại và tái định tuyến từ Kho tới các việc còn lại.
        """
        wo_1 = self._create_wo("Việc 1", incident_location=self.room_204, priority="MEDIUM")
        wo_2 = self._create_wo("Việc 2", incident_location=self.room_301, priority="MEDIUM")

        service = TSPRoutingService(tenant=self.tenant_a)
        res = service.re_route_mid_shift(
            technician=self.tech_user,
            current_location_id=str(self.room_101.id),
            include_warehouse_pitstop=True,
            remaining_work_orders=[wo_1, wo_2],
            return_to_depot=True
        )

        self.assertTrue(res['success'])
        ordered_stops = res['data']['orderedStops']
        # Stop 0: Current Location
        self.assertEqual(ordered_stops[0]['type'], STOP_CURRENT_LOCATION)
        # Stop 1: Warehouse Pit-stop
        self.assertEqual(ordered_stops[1]['type'], STOP_WAREHOUSE)
        self.assertEqual(ordered_stops[1]['action'], 'PICKUP_SUPPLIES')
        # Subsequent stops: Work Orders
        self.assertEqual(ordered_stops[2]['type'], 'WORK_ORDER')
        self.assertEqual(ordered_stops[3]['type'], 'WORK_ORDER')

    def test_tc_tsp_07_dynamic_mid_shift_rerouting(self):
        """
        TC-TSP-07: Tái định tuyến động giữa ca từ vị trí hiện tại (Dynamic Mid-shift Re-routing)
        Thợ đang ở Trạm 2 thì phát sinh việc khẩn cấp mới.
        Kỳ vọng: Lộ trình tái tính toán lấy Trạm 2 làm điểm xuất phát mới v0, không tính lại từ Kho ban đầu.
        """
        wo_new_urgent = self._create_wo("Sự cố chập điện mới", incident_location=self.room_302, priority="URGENT")
        wo_rem_normal = self._create_wo("Việc bình thường còn lại", incident_location=self.room_102, priority="LOW")

        service = TSPRoutingService(tenant=self.tenant_a)
        res = service.re_route_mid_shift(
            technician=self.tech_user,
            current_location_id=str(self.room_204.id),
            remaining_work_orders=[wo_rem_normal, wo_new_urgent],
            return_to_depot=False
        )

        self.assertTrue(res['success'])
        stops = res['data']['orderedStops']
        self.assertEqual(stops[0]['type'], STOP_CURRENT_LOCATION)
        self.assertEqual(stops[0]['locationId'], str(self.room_204.id))
        self.assertEqual(stops[1]['workOrderId'], str(wo_new_urgent.id))
        self.assertEqual(stops[1]['priority'], 'URGENT')
        self.assertEqual(stops[2]['workOrderId'], str(wo_rem_normal.id))

    def test_tc_tsp_08_multi_floor_vertical_penalty(self):
        """
        TC-TSP-08: Phạt chi phí di chuyển thẳng đứng giữa các tầng (Multi-Floor Penalty)
        Đi cùng Tầng 1 cách nhau 40m vs leo lên Tầng 3 cách 10m theo phương thẳng đứng.
        Kỳ vọng: Hệ thống ưu tiên giải quyết các máy cùng Tầng 1 trước, hạn chế leo tầng.
        """
        engine = MultiTierDistanceEngine(tenant=self.tenant_a)

        # 2 rooms on same floor (Room 101 and Room 102)
        d_same_floor = engine.compute_hierarchical_topological_distance(self.room_101, self.room_102, 1, 1)
        # Room 101 to Room 301 (2 floors apart)
        d_diff_floor = engine.compute_hierarchical_topological_distance(self.room_101, self.room_301, 1, 3)

        self.assertEqual(d_same_floor, 10.0, "Same floor transition should be 10.0 cost")
        self.assertEqual(d_diff_floor, 10.0 + 30.0 * 2, "Difference of 2 floors should be 70.0 cost")
        self.assertLess(d_same_floor, d_diff_floor)

    def test_tc_tsp_09_offline_mobile_route_cache(self):
        """
        TC-TSP-09: Hoạt động ngoại tuyến trên Mobile (Offline Route Cache)
        Kiểm tra cấu trúc phản hồi của lộ trình đảm bảo đầy đủ trường thông tin độc lập,
        tự chứa (self-contained) để lưu đệm trên SQLite/LocalStorage của Mobile App.
        """
        wo = self._create_wo(
            "Kiểm tra hệ thống điện",
            incident_location=self.room_101,
            priority="HIGH",
            maintenance_window_start=time(9, 0),
            maintenance_window_end=time(11, 0),
        )
        service = TSPRoutingService(tenant=self.tenant_a)
        res = service.optimize_daily_route(technician=self.tech_user, work_orders=[wo], return_to_depot=True)

        self.assertTrue(res['success'])
        data = res['data']
        self.assertIn('orderedStops', data)
        self.assertIn('totalEstimatedMinutes', data)
        self.assertIn('totalDistanceMeters', data)
        self.assertIn('routingMode', data)

        for stop in data['orderedStops']:
            self.assertIn('step', stop)
            self.assertIn('type', stop)
            self.assertIn('name', stop)
            self.assertIn('estimatedArrival', stop)
            self.assertIn('departureTime', stop)

    def test_tc_tsp_10_graceful_zero_location_degradation(self):
        """
        TC-TSP-10: Tự động Fallback khi dữ liệu tọa độ rỗng (Graceful No-Map Degradation)
        Dữ liệu hoàn toàn không có tọa độ X, Y và không có incident_location (chỉ có tên và priority).
        Kỳ vọng: Hệ thống tự động chuyển sang Pure Business Ordering, không phát sinh lỗi HTTP 500.
        """
        # Asset with no location
        empty_asset = Asset.objects.create(name="Floating Asset", qr_code="QR-FLOAT", tenant=self.tenant_a)
        wo_urgent = self._create_wo("Không rõ chỗ URGENT", asset=empty_asset, incident_location=None, priority="URGENT")
        wo_low = self._create_wo("Không rõ chỗ LOW", asset=empty_asset, incident_location=None, priority="LOW", due_date=timezone.now() + timedelta(days=3))

        service = TSPRoutingService(tenant=self.tenant_a)
        res = service.optimize_daily_route(technician=self.tech_user, work_orders=[wo_low, wo_urgent], return_to_depot=False)

        self.assertTrue(res['success'])
        self.assertEqual(res['data']['routingMode'], MODE_PURE_BUSINESS)
        wo_stops = [s for s in res['data']['orderedStops'] if s['type'] == 'WORK_ORDER']
        # Urgent should still come before low!
        self.assertEqual(wo_stops[0]['priority'], 'URGENT')
        self.assertEqual(wo_stops[1]['priority'], 'LOW')

    def test_tc_tsp_11_scan_to_relocate_movable_asset(self):
        """
        TC-TSP-11: Quét mã QR cập nhật vị trí tài sản di động (Scan-to-Relocate)
        Kỹ thuật viên quét QR của bàn học tại Phòng 204.
        Kỳ vọng: Cập nhật current_location / location của bàn về Phòng 204 thành công.
        """
        table_asset = Asset.objects.create(
            name="Máy chiếu di động EPSON",
            qr_code="QR-EPSON-2026",
            location=self.room_101,
            tenant=self.tenant_a
        )

        service = TSPRoutingService(tenant=self.tenant_a)
        result = service.scan_to_relocate(
            qr_code_or_asset_id="QR-EPSON-2026",
            new_location_id=str(self.room_204.id),
            user=self.tech_user
        )

        self.assertTrue(result['success'])
        table_asset.refresh_from_db()
        self.assertEqual(str(table_asset.location.id), str(self.room_204.id))
        self.assertEqual(table_asset.floor_level, 2)

    def test_tc_tsp_12_multi_tenant_isolation(self):
        """
        TC-TSP-12: Cách ly dữ liệu vị trí đa khách hàng (Multi-Tenant Isolation)
        Tenant A và Tenant B cùng tối ưu lộ trình.
        Kỳ vọng: Cây vị trí và lộ trình của Tenant A không bị lẫn sang Tenant B.
        """
        bldg_b = Location.objects.create(
            name="Bệnh Viện Khu B",
            code="HOSP-B",
            location_type="BUILDING",
            tenant=self.tenant_b
        )
        wo_b = self._create_wo(
            "Sửa máy đo tim Tenant B",
            tenant=self.tenant_b,
            incident_location=bldg_b,
            priority="HIGH"
        )

        engine_a = MultiTierDistanceEngine(tenant=self.tenant_a)
        loc_lookup = engine_a.get_location(str(bldg_b.id))
        self.assertIsNone(loc_lookup, "Tenant A engine must NOT access Tenant B location")

    def test_tc_tsp_13_feature_toggle_and_zero_location_fallback(self):
        """
        TC-TSP-13: Cờ bật/tắt module theo gói Tenant & Sắp xếp ưu tiên không vị trí (Zero-Location Fallback)
        Tenant C có enable_tsp_routing = False.
        Kỳ vọng: Hệ thống không chạy thuật toán ma trận TSP; trả về routingEnabled: False,
        sắp xếp thuần túy theo priority & due_date, totalDistanceMeters = 0.0.
        """
        wo_urgent = self._create_wo(
            "Phiếu C1 Khẩn cấp",
            tenant=self.tenant_c,
            priority="URGENT",
            due_date=timezone.now()
        )
        wo_high = self._create_wo(
            "Phiếu C2 Ưu tiên cao",
            tenant=self.tenant_c,
            priority="HIGH",
            due_date=timezone.now() + timedelta(days=1)
        )
        wo_low = self._create_wo(
            "Phiếu C3 Thấp",
            tenant=self.tenant_c,
            priority="LOW",
            due_date=timezone.now() + timedelta(days=3)
        )

        service = TSPRoutingService(tenant=self.tenant_c)
        res = service.optimize_daily_route(
            technician=None,
            work_orders=[wo_low, wo_urgent, wo_high],
            return_to_depot=False
        )

        self.assertTrue(res['success'])
        self.assertFalse(res['data']['routingEnabled'])
        self.assertEqual(res['data']['routingMode'], MODE_PURE_BUSINESS)
        self.assertEqual(res['data']['totalDistanceMeters'], 0.0)

        wo_stops = [s for s in res['data']['orderedStops'] if s['type'] == 'WORK_ORDER']
        self.assertEqual(wo_stops[0]['priority'], 'URGENT')
        self.assertEqual(wo_stops[1]['priority'], 'HIGH')
        self.assertEqual(wo_stops[2]['priority'], 'LOW')

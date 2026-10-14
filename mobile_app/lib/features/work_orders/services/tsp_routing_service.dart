import 'dart:convert';
import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../../core/network/dio_client.dart';
import '../models/technician_route_model.dart';

class TSPRoutingService {
  static const String offlineCacheKey = 'eam_technician_offline_tsp_route';
  final Dio _dio = DioClient().dio;

  /// 1. Tối ưu hóa lộ trình làm việc đầu ca
  /// POST /api/v1/routing/optimize-route/
  Future<TechnicianRouteData> optimizeRoute({
    List<String>? workOrderIds,
    String startTime = '08:00',
    bool returnToDepot = true,
    String? startLocationId,
    Map<String, dynamic>? startCoords,
  }) async {
    try {
      final payload = {
        'workOrderIds': workOrderIds ?? [],
        'startTime': startTime,
        'returnToDepot': returnToDepot,
        if (startLocationId != null) 'startLocationId': startLocationId,
        if (startCoords != null) 'startCoords': startCoords,
      };

      final response = await _dio.post(
        '/api/v1/routing/optimize-route/',
        data: payload,
      );

      if (response.statusCode == 200 && response.data['success'] == true) {
        final dataJson = response.data['data'] as Map<String, dynamic>;
        final routeData = TechnicianRouteData.fromJson(dataJson);
        // Tự động lưu cache cho chế độ ngoại tuyến
        await saveRouteToCache(routeData);
        return routeData;
      } else {
        final msg = response.data['message'] ?? 'Không thể tính toán lộ trình tối ưu.';
        throw Exception(msg);
      }
    } catch (e) {
      debugPrint('[TSPRoutingService] optimizeRoute error: $e');
      rethrow;
    }
  }

  /// 2. Ghé kho tiếp vận giữa ca (Pit-stop) / Tái định tuyến động
  /// POST /api/v1/routing/re-route-mid-shift/
  Future<TechnicianRouteData> reRouteMidShift({
    String? currentLocationId,
    Map<String, dynamic>? currentCoords,
    String actionTrigger = 'PIT_STOP',
    bool includeWarehousePitstop = true,
    String? pitstopLocationId,
    List<String>? remainingWorkOrderIds,
    List<String>? completedWorkOrderIds,
    bool returnToDepot = true,
    String? startTime,
  }) async {
    try {
      final payload = {
        if (currentLocationId != null) 'currentLocationId': currentLocationId,
        if (currentCoords != null) 'currentCoords': currentCoords,
        'actionTrigger': actionTrigger,
        'includeWarehousePitstop': includeWarehousePitstop,
        if (pitstopLocationId != null) 'pitstopLocationId': pitstopLocationId,
        'remainingWorkOrderIds': remainingWorkOrderIds ?? [],
        'completedWorkOrderIds': completedWorkOrderIds ?? [],
        'returnToDepot': returnToDepot,
        if (startTime != null) 'startTime': startTime,
      };

      final response = await _dio.post(
        '/api/v1/routing/re-route-mid-shift/',
        data: payload,
      );

      if (response.statusCode == 200 && response.data['success'] == true) {
        final dataJson = response.data['data'] as Map<String, dynamic>;
        final routeData = TechnicianRouteData.fromJson(dataJson);
        await saveRouteToCache(routeData);
        return routeData;
      } else {
        final msg = response.data['message'] ?? 'Không thể tái định tuyến giữa ca.';
        throw Exception(msg);
      }
    } catch (e) {
      debugPrint('[TSPRoutingService] reRouteMidShift error: $e');
      rethrow;
    }
  }

  /// 3. Lấy lộ trình trong ngày của KTV
  /// GET /api/v1/routing/my-daily-route/
  Future<TechnicianRouteData?> getMyDailyRoute() async {
    try {
      final response = await _dio.get('/api/v1/routing/my-daily-route/');
      if (response.statusCode == 200 && response.data['success'] == true) {
        final dataJson = response.data['data'] as Map<String, dynamic>;
        final routeData = TechnicianRouteData.fromJson(dataJson);
        await saveRouteToCache(routeData);
        return routeData;
      }
      return null;
    } catch (e) {
      debugPrint('[TSPRoutingService] getMyDailyRoute error: $e');
      return null;
    }
  }

  /// 4. Lấy danh sách kho tiếp vận có sẵn cho dropdown Pitstop
  Future<List<Map<String, dynamic>>> getAvailableWarehouses() async {
    try {
      final response = await _dio.get('/api/v1/locations/?size=50');
      if (response.statusCode == 200) {
        final List<dynamic> results = response.data['data'] ?? response.data['results'] ?? [];
        return results
            .where((loc) =>
                loc['zone_type'] == 'WAREHOUSE' ||
                loc['type'] == 'WAREHOUSE' ||
                (loc['name'] != null && (loc['name'] as String).toLowerCase().contains('kho')))
            .map((loc) => {
                  'id': loc['id'].toString(),
                  'name': loc['name'].toString(),
                  'code': (loc['code'] ?? '').toString(),
                  'floorLevel': (loc['floor_level'] ?? loc['floor_number'] ?? 1) as int,
                })
            .toList();
      }
      return [];
    } catch (e) {
      debugPrint('[TSPRoutingService] getAvailableWarehouses error: $e');
      return [];
    }
  }

  /// 5. Lưu lộ trình vào bộ đệm ngoại tuyến SharedPreferences
  Future<bool> saveRouteToCache(TechnicianRouteData routeData) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final updatedData = routeData.copyWith(cachedAt: DateTime.now());
      final jsonString = jsonEncode(updatedData.toJson());
      return await prefs.setString(offlineCacheKey, jsonString);
    } catch (e) {
      debugPrint('[TSPRoutingService] saveRouteToCache error: $e');
      return false;
    }
  }

  /// 6. Đọc lộ trình đã lưu từ bộ đệm ngoại tuyến
  Future<TechnicianRouteData?> getCachedRoute() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final jsonString = prefs.getString(offlineCacheKey);
      if (jsonString == null || jsonString.isEmpty) {
        return null;
      }
      final map = jsonDecode(jsonString) as Map<String, dynamic>;
      return TechnicianRouteData.fromJson(map);
    } catch (e) {
      debugPrint('[TSPRoutingService] getCachedRoute error: $e');
      return null;
    }
  }

  /// 7. Xóa bộ đệm ngoại tuyến
  Future<bool> clearCachedRoute() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      return await prefs.remove(offlineCacheKey);
    } catch (e) {
      debugPrint('[TSPRoutingService] clearCachedRoute error: $e');
      return false;
    }
  }

  /// 8. Dữ liệu mẫu chuẩn nghiệp vụ mô phỏng phân xưởng EAM
  TechnicianRouteData getFallbackDemoRoute() {
    return TechnicianRouteData(
      totalEstimatedMinutes: 185,
      totalDistanceMeters: 420.0,
      routingMode: 'MANHATTAN_2D',
      routingEnabled: true,
      totalStops: 6,
      detectedFloorplanId: 'fp-prod-01',
      detectedFloorplanName: 'Phân Xưởng Sản Xuất & Chế Tạo Số 1',
      detectedFloorLevel: 1,
      technicianName: 'Nguyễn Văn Minh (KTV-08)',
      technicianUsername: 'ktv.minhnv',
      orderedStops: [
        const RouteStop(
          step: 0,
          type: 'DEPOT',
          name: 'Điểm xuất phát: Phòng Điều Phối Bảo Trì',
          locationName: 'Phòng Kỹ thuật & Điều phối (Tầng 1)',
          floorNumber: 1,
          coords: RouteCoordinate(x: 180.0, y: 190.0),
          travelDistanceMeters: 0.0,
          travelTimeMinutes: 0.0,
          estimatedArrival: '08:00',
          departureTime: '08:05',
          priority: 'LOW',
          action: 'DEPART',
        ),
        const RouteStop(
          step: 1,
          type: 'WORK_ORDER',
          name: 'Thay dầu xilanh thủy lực máy dập 500 tấn',
          workOrderId: 'wo-2026-088',
          workOrderCode: 'WO-2026-088',
          assetName: 'Máy dập cơ khí A01 (STAMP-01)',
          locationName: 'Phân xưởng Dập Thân vỏ (Tầng 1)',
          floorNumber: 1,
          coords: RouteCoordinate(x: 200.0, y: 190.0),
          travelDistanceMeters: 45.0,
          travelTimeMinutes: 2.5,
          estimatedArrival: '08:08',
          departureTime: '08:50',
          priority: 'HIGH',
          action: 'SERVICE',
          timeWindow: TimeWindow(start: '08:00', end: '09:30'),
        ),
        const RouteStop(
          step: 2,
          type: 'WORK_ORDER',
          name: 'Xử lý khẩn cấp cảm biến an toàn robot hàn',
          workOrderId: 'wo-2026-092',
          workOrderCode: 'WO-2026-092',
          assetName: 'Robot hàn tự động FANUC-02',
          locationName: 'Phân xưởng Hàn & Sơn (Tầng 1)',
          floorNumber: 1,
          coords: RouteCoordinate(x: 480.0, y: 200.0),
          travelDistanceMeters: 75.0,
          travelTimeMinutes: 4.2,
          estimatedArrival: '08:55',
          departureTime: '09:40',
          priority: 'URGENT',
          action: 'SERVICE',
          timeWindow: TimeWindow(start: '08:30', end: '10:00'),
        ),
        const RouteStop(
          step: 3,
          type: 'WAREHOUSE',
          name: 'Trạm tiếp vận: Ghé Kho CKD lấy module điều khiển',
          locationName: 'Kho Vật tư & CKD Trung tâm (Tầng 1)',
          floorNumber: 1,
          coords: RouteCoordinate(x: 250.0, y: 510.0),
          travelDistanceMeters: 110.0,
          travelTimeMinutes: 6.0,
          estimatedArrival: '09:48',
          departureTime: '10:05',
          priority: 'HIGH',
          action: 'PICKUP_SUPPLIES',
        ),
        const RouteStop(
          step: 4,
          type: 'WORK_ORDER',
          name: 'Kiểm tra cân chỉnh servo hệ thống băng tải Tầng 2',
          workOrderId: 'wo-2026-095',
          workOrderCode: 'WO-2026-095',
          assetName: 'Băng tải đóng gói tự động CV-03',
          locationName: 'Phân xưởng Lắp ráp & Đóng gói (Tầng 2)',
          floorNumber: 2,
          coords: RouteCoordinate(x: 750.0, y: 210.0),
          travelDistanceMeters: 130.0,
          travelTimeMinutes: 7.8,
          estimatedArrival: '10:15',
          departureTime: '11:10',
          priority: 'MEDIUM',
          action: 'SERVICE',
          timeWindow: TimeWindow(start: '10:00', end: '11:30'),
          floorTransition: FloorTransition(
            fromFloor: 1,
            toFloor: 2,
            direction: 'UP',
            transitionType: 'STAIRS',
            actionLabel: 'Chuyển sang Tầng 2',
          ),
        ),
        const RouteStop(
          step: 5,
          type: 'DEPOT',
          name: 'Hoàn thành ca - Quay về Phòng Kỹ thuật',
          locationName: 'Phòng Kỹ thuật & Điều phối (Tầng 1)',
          floorNumber: 1,
          coords: RouteCoordinate(x: 180.0, y: 190.0),
          travelDistanceMeters: 60.0,
          travelTimeMinutes: 3.5,
          estimatedArrival: '11:25',
          departureTime: '11:30',
          priority: 'LOW',
          action: 'DEPART',
          floorTransition: FloorTransition(
            fromFloor: 2,
            toFloor: 1,
            direction: 'DOWN',
            transitionType: 'STAIRS',
            actionLabel: 'Trở lại Tầng 1',
          ),
        ),
      ],
    );
  }
}

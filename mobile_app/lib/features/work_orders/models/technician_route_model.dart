import 'package:flutter/material.dart';

/// Tọa độ 2D của trạm dừng trên sơ đồ mặt bằng
class RouteCoordinate {
  final double x;
  final double y;

  const RouteCoordinate({
    required this.x,
    required this.y,
  });

  factory RouteCoordinate.fromJson(Map<String, dynamic> json) {
    return RouteCoordinate(
      x: (json['x'] as num?)?.toDouble() ?? 0.0,
      y: (json['y'] as num?)?.toDouble() ?? 0.0,
    );
  }

  Map<String, dynamic> toJson() => {
    'x': x,
    'y': y,
  };
}

/// Khung giờ cho phép dừng máy / bảo trì (Time Window)
class TimeWindow {
  final String? start;
  final String? end;

  const TimeWindow({
    this.start,
    this.end,
  });

  factory TimeWindow.fromJson(Map<String, dynamic> json) {
    return TimeWindow(
      start: json['start'] as String?,
      end: json['end'] as String?,
    );
  }

  Map<String, dynamic> toJson() => {
    'start': start,
    'end': end,
  };

  String get displayString {
    if (start != null && end != null) {
      return '$start - $end';
    }
    return start ?? end ?? '';
  }
}

/// Thông tin chuyển tầng qua cầu thang bộ / thang máy
class FloorTransition {
  final int fromFloor;
  final int toFloor;
  final String direction;
  final String transitionType;
  final String actionLabel;

  const FloorTransition({
    required this.fromFloor,
    required this.toFloor,
    this.direction = 'UP',
    this.transitionType = 'STAIRS',
    required this.actionLabel,
  });

  factory FloorTransition.fromJson(Map<String, dynamic> json) {
    return FloorTransition(
      fromFloor: (json['fromFloor'] as num?)?.toInt() ?? 1,
      toFloor: (json['toFloor'] as num?)?.toInt() ?? 1,
      direction: json['direction'] as String? ?? 'UP',
      transitionType: json['transitionType'] as String? ?? 'STAIRS',
      actionLabel: json['actionLabel'] as String? ?? 'Chuyển tầng',
    );
  }

  Map<String, dynamic> toJson() => {
    'fromFloor': fromFloor,
    'toFloor': toFloor,
    'direction': direction,
    'transitionType': transitionType,
    'actionLabel': actionLabel,
  };
}

/// Một trạm dừng trong lộ trình tối ưu của kỹ thuật viên
class RouteStop {
  final int step;
  final String type; // DEPOT, WORK_ORDER, WAREHOUSE, CURRENT_LOCATION
  final String name;
  final String? locationId;
  final String? locationName;
  final int floorNumber;
  final RouteCoordinate? coords;
  final double travelDistanceMeters;
  final double travelTimeMinutes;
  final double waitingMinutes;
  final String estimatedArrival;
  final String? serviceStartTime;
  final String? departureTime;
  final String? priority; // URGENT, HIGH, MEDIUM, LOW
  final String? workOrderId;
  final String? workOrderCode;
  final String? assetName;
  final String? action; // DEPART, SERVICE, PICKUP_SUPPLIES, PICKUP_TOOLS
  final TimeWindow? timeWindow;
  final FloorTransition? floorTransition;

  const RouteStop({
    required this.step,
    required this.type,
    required this.name,
    this.locationId,
    this.locationName,
    this.floorNumber = 1,
    this.coords,
    this.travelDistanceMeters = 0.0,
    this.travelTimeMinutes = 0.0,
    this.waitingMinutes = 0.0,
    this.estimatedArrival = '08:00',
    this.serviceStartTime,
    this.departureTime,
    this.priority,
    this.workOrderId,
    this.workOrderCode,
    this.assetName,
    this.action,
    this.timeWindow,
    this.floorTransition,
  });

  factory RouteStop.fromJson(Map<String, dynamic> json) {
    RouteCoordinate? parsedCoords;
    if (json['coords'] != null && json['coords'] is Map<String, dynamic>) {
      parsedCoords = RouteCoordinate.fromJson(json['coords'] as Map<String, dynamic>);
    }

    TimeWindow? parsedTimeWindow;
    if (json['timeWindow'] != null && json['timeWindow'] is Map<String, dynamic>) {
      parsedTimeWindow = TimeWindow.fromJson(json['timeWindow'] as Map<String, dynamic>);
    }

    FloorTransition? parsedTransition;
    if (json['floorTransition'] != null && json['floorTransition'] is Map<String, dynamic>) {
      parsedTransition = FloorTransition.fromJson(json['floorTransition'] as Map<String, dynamic>);
    }

    return RouteStop(
      step: (json['step'] ?? json['stepIndex'] as num?)?.toInt() ?? 0,
      type: json['type'] as String? ?? 'WORK_ORDER',
      name: json['name'] as String? ?? '',
      locationId: json['locationId'] as String?,
      locationName: json['locationName'] as String?,
      floorNumber: (json['floorNumber'] as num?)?.toInt() ?? 1,
      coords: parsedCoords,
      travelDistanceMeters: (json['travelDistanceMeters'] as num?)?.toDouble() ?? 0.0,
      travelTimeMinutes: (json['travelTimeMinutes'] as num?)?.toDouble() ?? 0.0,
      waitingMinutes: (json['waitingMinutes'] as num?)?.toDouble() ?? 0.0,
      estimatedArrival: json['estimatedArrival'] as String? ?? '08:00',
      serviceStartTime: json['serviceStartTime'] as String?,
      departureTime: json['departureTime'] as String?,
      priority: json['priority'] as String?,
      workOrderId: json['workOrderId'] as String?,
      workOrderCode: json['workOrderCode'] as String?,
      assetName: json['assetName'] as String?,
      action: json['action'] as String?,
      timeWindow: parsedTimeWindow,
      floorTransition: parsedTransition,
    );
  }

  Map<String, dynamic> toJson() => {
    'step': step,
    'type': type,
    'name': name,
    'locationId': locationId,
    'locationName': locationName,
    'floorNumber': floorNumber,
    'coords': coords?.toJson(),
    'travelDistanceMeters': travelDistanceMeters,
    'travelTimeMinutes': travelTimeMinutes,
    'waitingMinutes': waitingMinutes,
    'estimatedArrival': estimatedArrival,
    'serviceStartTime': serviceStartTime,
    'departureTime': departureTime,
    'priority': priority,
    'workOrderId': workOrderId,
    'workOrderCode': workOrderCode,
    'assetName': assetName,
    'action': action,
    'timeWindow': timeWindow?.toJson(),
    'floorTransition': floorTransition?.toJson(),
  };

  bool get isUrgent => priority == 'URGENT' || priority == 'EMERGENCY';
  bool get isDepot => type == 'DEPOT';
  bool get isCurrentLocation => type == 'CURRENT_LOCATION';
  bool get isWarehouse => type == 'WAREHOUSE';
  bool get isToolPickup => action == 'PICKUP_TOOLS' || name.toLowerCase().contains('dụng cụ');
  bool get isWorkOrder => type == 'WORK_ORDER';

  Color get pinColor {
    if (isUrgent) return const Color(0xFFef4444); // Đỏ khẩn cấp
    if (isToolPickup) return const Color(0xFF8b5cf6); // Tím lấy dụng cụ
    if (isDepot || isCurrentLocation) return const Color(0xFF10b981); // Xanh lục xuất phát
    if (isWarehouse) return const Color(0xFFf97316); // Cam kho vật tư
    return const Color(0xFFf59e0b); // Vàng/Hổ phách công việc thường
  }

  String get typeLabel {
    if (isDepot) return 'Kho xuất phát';
    if (isCurrentLocation) return 'Vị trí hiện tại';
    if (isWarehouse) return 'Kho vật tư';
    if (isToolPickup) return 'Lấy dụng cụ';
    return 'Bảo trì máy';
  }
}

/// Dữ liệu tổng thể của lộ trình tối ưu KTV từ thuật toán TSP
class TechnicianRouteData {
  final int totalEstimatedMinutes;
  final double totalDistanceMeters;
  final String routingMode;
  final bool routingEnabled;
  final int totalStops;
  final String? detectedFloorplanId;
  final String? detectedFloorplanName;
  final int? detectedFloorLevel;
  final String? technicianName;
  final String? technicianUsername;
  final List<RouteStop> orderedStops;
  final DateTime? cachedAt;
  final bool isAdaptiveStart;
  final String? lastKnownMachine;
  final String? lastKnownTime;
  final String? lastKnownWorkOrder;

  const TechnicianRouteData({
    required this.totalEstimatedMinutes,
    required this.totalDistanceMeters,
    required this.routingMode,
    this.routingEnabled = true,
    required this.totalStops,
    this.detectedFloorplanId,
    this.detectedFloorplanName,
    this.detectedFloorLevel,
    this.technicianName,
    this.technicianUsername,
    required this.orderedStops,
    this.cachedAt,
    this.isAdaptiveStart = false,
    this.lastKnownMachine,
    this.lastKnownTime,
    this.lastKnownWorkOrder,
  });

  factory TechnicianRouteData.fromJson(Map<String, dynamic> json) {
    final stopsList = <RouteStop>[];
    if (json['orderedStops'] != null && json['orderedStops'] is List) {
      for (final s in (json['orderedStops'] as List)) {
        if (s is Map<String, dynamic>) {
          stopsList.add(RouteStop.fromJson(s));
        }
      }
    }

    return TechnicianRouteData(
      totalEstimatedMinutes: (json['totalEstimatedMinutes'] as num?)?.toInt() ?? 0,
      totalDistanceMeters: (json['totalDistanceMeters'] as num?)?.toDouble() ?? 0.0,
      routingMode: json['routingMode'] as String? ?? 'MANHATTAN_2D',
      routingEnabled: json['routingEnabled'] as bool? ?? true,
      totalStops: (json['totalStops'] as num?)?.toInt() ?? stopsList.length,
      detectedFloorplanId: json['detectedFloorplanId'] as String?,
      detectedFloorplanName: json['detectedFloorplanName'] as String?,
      detectedFloorLevel: (json['detectedFloorLevel'] as num?)?.toInt(),
      technicianName: json['technicianName'] as String?,
      technicianUsername: json['technicianUsername'] as String?,
      orderedStops: stopsList,
      cachedAt: json['cachedAt'] != null ? DateTime.tryParse(json['cachedAt'] as String) : null,
      isAdaptiveStart: json['isAdaptiveStart'] as bool? ?? false,
      lastKnownMachine: json['lastKnownMachine'] as String?,
      lastKnownTime: json['lastKnownTime'] as String?,
      lastKnownWorkOrder: json['lastKnownWorkOrder'] as String?,
    );
  }

  Map<String, dynamic> toJson() => {
    'totalEstimatedMinutes': totalEstimatedMinutes,
    'totalDistanceMeters': totalDistanceMeters,
    'routingMode': routingMode,
    'routingEnabled': routingEnabled,
    'totalStops': totalStops,
    'detectedFloorplanId': detectedFloorplanId,
    'detectedFloorplanName': detectedFloorplanName,
    'detectedFloorLevel': detectedFloorLevel,
    'technicianName': technicianName,
    'technicianUsername': technicianUsername,
    'orderedStops': orderedStops.map((s) => s.toJson()).toList(),
    'cachedAt': cachedAt?.toIso8601String(),
    'isAdaptiveStart': isAdaptiveStart,
    'lastKnownMachine': lastKnownMachine,
    'lastKnownTime': lastKnownTime,
    'lastKnownWorkOrder': lastKnownWorkOrder,
  };

  TechnicianRouteData copyWith({
    DateTime? cachedAt,
    bool? isAdaptiveStart,
    String? lastKnownMachine,
    String? lastKnownTime,
    String? lastKnownWorkOrder,
  }) {
    return TechnicianRouteData(
      totalEstimatedMinutes: totalEstimatedMinutes,
      totalDistanceMeters: totalDistanceMeters,
      routingMode: routingMode,
      routingEnabled: routingEnabled,
      totalStops: totalStops,
      detectedFloorplanId: detectedFloorplanId,
      detectedFloorplanName: detectedFloorplanName,
      detectedFloorLevel: detectedFloorLevel,
      technicianName: technicianName,
      technicianUsername: technicianUsername,
      orderedStops: orderedStops,
      cachedAt: cachedAt ?? this.cachedAt,
      isAdaptiveStart: isAdaptiveStart ?? this.isAdaptiveStart,
      lastKnownMachine: lastKnownMachine ?? this.lastKnownMachine,
      lastKnownTime: lastKnownTime ?? this.lastKnownTime,
      lastKnownWorkOrder: lastKnownWorkOrder ?? this.lastKnownWorkOrder,
    );
  }
}

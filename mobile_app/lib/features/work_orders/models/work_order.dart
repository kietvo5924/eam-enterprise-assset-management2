import 'package:flutter/material.dart';

class WorkOrder {
  final String id;
  final String title;
  final String description;
  final String status;
  final String? priority;
  final String? assetId;
  final String? assetName;
  final String? assetLocation;
  final DateTime? deadline;
  final String? assigneeUsername;
  final String? resolutionNotes;

  final String? code;
  final String? maintenanceAction;
  final double? coordsX;
  final double? coordsY;
  final int? floorLevel;
  final String? zoneId;
  final String? locationId;
  final String? assetType;

  final bool requireBleBeacon;
  final String? bleBeaconUuid;
  final String? bleMacAddress;

  final String? severityLevel;
  final bool? marginalBoundaryWarning;
  final bool? isOnHold;
  final String? holdReason;
  final int? holdAccumulatedSeconds;

  final List<WorkOrderChecklist> checklists;
  final List<WorkOrderAttachment> attachments;

  WorkOrder({
    required this.id,
    required this.title,
    required this.description,
    required this.status,
    this.code,
    this.priority,
    this.maintenanceAction,
    this.assetId,
    this.assetName,
    this.assetLocation,
    this.deadline,
    this.assigneeUsername,
    this.resolutionNotes,
    this.coordsX,
    this.coordsY,
    this.floorLevel,
    this.zoneId,
    this.locationId,
    this.assetType,
    this.requireBleBeacon = true,
    this.bleBeaconUuid,
    this.bleMacAddress,
    this.severityLevel,
    this.marginalBoundaryWarning,
    this.isOnHold,
    this.holdReason,
    this.holdAccumulatedSeconds,
    this.checklists = const [],
    this.attachments = const [],
  });

  bool get isMachinery {
    // Chỉ dựa hoàn toàn vào đúng phân loại bản chất tài sản (asset_type)
    if (assetType == null || assetType!.trim().isEmpty) return true;
    return assetType!.toUpperCase() != 'STATIC';
  }

  Map<String, dynamic> getStatusUI() {
    switch (status) {
      case 'IN_PROGRESS':
        return {
          'label': 'Đang làm',
          'color': const Color(0xFFf97316),
          'bgColor': const Color(0xFFfff7ed),
          'textColor': const Color(0xFFc2410c),
        };
      case 'ON_HOLD':
      case 'PAUSED':
        return {
          'label': 'Tạm dừng',
          'color': const Color(0xFF0284c7),
          'bgColor': const Color(0xFFe0f2fe),
          'textColor': const Color(0xFF0369a1),
        };
      case 'CREATED':
        return {
          'label': 'Mới',
          'color': const Color(0xFF3b82f6),
          'bgColor': const Color(0xFFeff6ff),
          'textColor': const Color(0xFF1d4ed8),
        };
      case 'ASSIGNED':
        return {
          'label': 'Được giao',
          'color': const Color(0xFF8b5cf6),
          'bgColor': const Color(0xFFf5f3ff),
          'textColor': const Color(0xFF6d28d9),
        };
      case 'COMPLETED':
        return {
          'label': 'Hoàn thành',
          'color': const Color(0xFF22c55e),
          'bgColor': const Color(0xFFf0fdf4),
          'textColor': const Color(0xFF15803d),
        };
      case 'CANCELLED':
      case 'CANCELED':
        return {
          'label': 'Đã hủy',
          'color': const Color(0xFFef4444),
          'bgColor': const Color(0xFFfef2f2),
          'textColor': const Color(0xFFb91c1c),
        };
      default:
        return {
          'label': status,
          'color': const Color(0xFF9ca3af),
          'bgColor': const Color(0xFFf3f4f6),
          'textColor': const Color(0xFF4b5563),
        };
    }
  }

  String getFormattedTime() {
    if (deadline == null) return 'Không có hạn';
    final localTime = deadline!.toLocal();
    final String d = localTime.day.toString().padLeft(2, '0');
    final String m = localTime.month.toString().padLeft(2, '0');
    final String h = localTime.hour.toString().padLeft(2, '0');
    final String min = localTime.minute.toString().padLeft(2, '0');
    return '$h:$min - $d/$m';
  }

  String getMaintenanceActionLabel() {
    switch (maintenanceAction) {
      case 'MICRO_MAINTENANCE':
        return 'Bảo trì vi mô';
      case 'CORE_REPLACEMENT':
        return 'Đại tu cốt lõi';
      default:
        return 'Bảo dưỡng định kỳ';
    }
  }

  factory WorkOrder.fromJson(Map<String, dynamic> json) {
    final String rawId = (json['id'] ?? '').toString();
    final String defaultCode = rawId.length >= 8 ? 'WO-${rawId.substring(0, 8).toUpperCase()}' : 'WO';
    return WorkOrder(
      id: rawId,
      code: json['code'] ?? defaultCode,
      title: json['title'] ?? 'Công việc không tên',
      description: json['description'] ?? '',
      status: json['status'] ?? 'UNKNOWN',
      priority: json['priority'],
      maintenanceAction: json['maintenanceAction'] ?? json['maintenance_action'] ?? 'GENERAL',
      assetId: json['asset']?['id'] ?? json['assetId'],
      assetName: json['asset']?['name'] ?? 'Chưa gán thiết bị',
      assetLocation: json['asset']?['locationName'] ?? 'Không rõ vị trí',
      coordsX: ((json['coordsX'] as num?)?.toDouble() ?? 0.0) > 0
          ? (json['coordsX'] as num).toDouble()
          : (json['asset']?['coordsX'] as num?)?.toDouble(),
      coordsY: ((json['coordsY'] as num?)?.toDouble() ?? 0.0) > 0
          ? (json['coordsY'] as num).toDouble()
          : (json['asset']?['coordsY'] as num?)?.toDouble(),
      floorLevel: json['floorLevel'] as int? ?? json['asset']?['floorLevel'] as int?,
      zoneId: json['zoneId'] as String? ?? json['asset']?['zoneId'] as String?,
      locationId: json['locationId'] as String? ??
          json['incidentLocationId'] as String? ??
          json['asset']?['locationId'] as String? ??
          json['asset']?['location']?['id'] as String?,
      assetType: json['asset']?['assetType'] as String? ??
          json['asset']?['asset_type'] as String? ??
          json['assetType'] as String?,

      requireBleBeacon: json['asset']?['requireBleBeacon'] ??
          json['asset']?['require_ble_beacon'] ??
          json['requireBleBeacon'] ??
          json['require_ble_beacon'] ??
          true,
      bleBeaconUuid: json['asset']?['bleBeaconUuid'] ??
          json['asset']?['ble_beacon_uuid'] ??
          json['bleBeaconUuid'] ??
          json['ble_beacon_uuid'],
      bleMacAddress: json['asset']?['bleMacAddress'] ??
          json['asset']?['ble_mac_address'] ??
          json['bleMacAddress'] ??
          json['ble_mac_address'],
      deadline: json['deadline'] != null ? DateTime.tryParse(json['deadline']) : null,
      assigneeUsername: json['assignee']?['username'] ?? json['assigneeName'],
      resolutionNotes: json['resolutionNotes'],
      severityLevel: json['severityLevel'] ?? json['severity_level'],
      marginalBoundaryWarning: json['marginalBoundaryWarning'] ?? json['marginal_boundary_warning'],
      isOnHold: json['isOnHold'] ?? json['is_on_hold'] ?? (json['status'] == 'ON_HOLD'),
      holdReason: json['holdReason'] ?? json['hold_reason'],
      holdAccumulatedSeconds: json['holdAccumulatedSeconds'] as int? ?? json['hold_accumulated_seconds'] as int?,
      checklists: (json['checklists'] as List<dynamic>?)?.map((c) => WorkOrderChecklist.fromJson(c)).toList() ?? [],
      attachments: (json['attachments'] as List<dynamic>?)?.map((a) => WorkOrderAttachment.fromJson(a)).toList() ?? [],
    );
  }
}

class WorkOrderChecklist {
  final String id;
  final String itemName;
  bool isCompleted;
  final String inputType;
  final String? expectedValue;
  String? actualValue;
  final bool isMandatory;
  final String? stage;

  WorkOrderChecklist({
    required this.id,
    required this.itemName,
    this.isCompleted = false,
    this.inputType = 'PASS_FAIL',
    this.expectedValue,
    this.actualValue,
    this.isMandatory = false,
    this.stage,
  });

  factory WorkOrderChecklist.fromJson(Map<String, dynamic> json) {
    return WorkOrderChecklist(
      id: json['id'] ?? '',
      itemName: json['itemName'] ?? '',
      isCompleted: json['isCompleted'] ?? json['completed'] ?? false,
      inputType: json['inputType'] ?? 'PASS_FAIL',
      expectedValue: json['expectedValue'],
      actualValue: json['actualValue'],
      isMandatory: json['isMandatory'] ?? json['is_mandatory'] ?? false,
      stage: json['stage'],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'itemName': itemName,
      'completed': isCompleted,
      'inputType': inputType,
      'expectedValue': expectedValue,
      'actualValue': actualValue,
      'isMandatory': isMandatory,
      'stage': stage,
    };
  }
}

class WorkOrderAttachment {
  final String id;
  final String fileUrl;
  final String fileName;
  final bool isLocal;

  WorkOrderAttachment({
    required this.id,
    required this.fileUrl,
    required this.fileName,
    this.isLocal = false,
  });

  factory WorkOrderAttachment.fromJson(Map<String, dynamic> json) {
    return WorkOrderAttachment(
      id: json['id'] ?? '',
      fileUrl: json['fileUrl'] ?? '',
      fileName: json['fileName'] ?? '',
      isLocal: json['isLocal'] ?? false,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'fileUrl': fileUrl,
      'fileName': fileName,
      'isLocal': isLocal,
    };
  }
}

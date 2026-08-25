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

  final List<WorkOrderChecklist> checklists;
  final List<WorkOrderAttachment> attachments;

  WorkOrder({
    required this.id,
    required this.title,
    required this.description,
    required this.status,
    this.priority,
    this.assetId,
    this.assetName,
    this.assetLocation,
    this.deadline,
    this.assigneeUsername,
    this.resolutionNotes,
    this.checklists = const [],
    this.attachments = const [],
  });

  Map<String, dynamic> getStatusUI() {
    switch (status) {
      case 'IN_PROGRESS':
        return {
          'label': 'Đang làm',
          'color': const Color(0xFFf97316),
          'bgColor': const Color(0xFFfff7ed),
          'textColor': const Color(0xFFc2410c),
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

  factory WorkOrder.fromJson(Map<String, dynamic> json) {
    return WorkOrder(
      id: json['id'] ?? '',
      title: json['title'] ?? 'Công việc không tên',
      description: json['description'] ?? '',
      status: json['status'] ?? 'UNKNOWN',
      priority: json['priority'],
      assetId: json['asset']?['id'],
      assetName: json['asset']?['name'] ?? 'Chưa gán thiết bị',
      assetLocation: json['asset']?['locationName'] ?? 'Không rõ vị trí',
      deadline: json['deadline'] != null ? DateTime.tryParse(json['deadline']) : null,
      assigneeUsername: json['assignee']?['username'],
      resolutionNotes: json['resolutionNotes'],
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

  WorkOrderChecklist({
    required this.id,
    required this.itemName,
    this.isCompleted = false,
    this.inputType = 'PASS_FAIL',
    this.expectedValue,
    this.actualValue,
    this.isMandatory = false,
  });

  factory WorkOrderChecklist.fromJson(Map<String, dynamic> json) {
    return WorkOrderChecklist(
      id: json['id'] ?? '',
      itemName: json['itemName'] ?? '',
      isCompleted: json['completed'] ?? false,
      inputType: json['inputType'] ?? 'PASS_FAIL',
      expectedValue: json['expectedValue'],
      actualValue: json['actualValue'],
      isMandatory: json['isMandatory'] ?? false,
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

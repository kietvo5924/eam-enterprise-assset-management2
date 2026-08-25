import 'dart:convert';
import '../../features/work_orders/models/work_order.dart';
import 'app_database.dart';

class DatabaseMapper {
  static WorkOrder fromWorkOrderEntity(WorkOrderEntity entity) {
    return WorkOrder(
      id: entity.id,
      title: entity.title,
      description: entity.description,
      status: entity.status,
      priority: entity.priority,
      assetId: entity.assetId,
      assetName: entity.assetName,
      assetLocation: entity.assetLocation,
      deadline: entity.deadline,
      assigneeUsername: entity.assigneeUsername,
      resolutionNotes: entity.resolutionNotes,
      checklists: (entity.checklists as List<dynamic>?)?.map((c) => WorkOrderChecklist.fromJson(c as Map<String, dynamic>)).toList() ?? [],
      attachments: (entity.attachments as List<dynamic>?)?.map((a) => WorkOrderAttachment.fromJson(a as Map<String, dynamic>)).toList() ?? [],
    );
  }

  static WorkOrderEntity toWorkOrderEntity(WorkOrder wo, String tenantId) {
    return WorkOrderEntity(
      id: wo.id,
      title: wo.title,
      description: wo.description,
      status: wo.status,
      priority: wo.priority,
      assetId: wo.assetId,
      assetName: wo.assetName,
      assetLocation: wo.assetLocation,
      deadline: wo.deadline,
      updatedAt: DateTime.now(), // Use current time for eviction logic
      assigneeUsername: wo.assigneeUsername,
      resolutionNotes: wo.resolutionNotes,
      checklists: wo.checklists.map((c) => c.toJson()).toList(),
      attachments: wo.attachments.map((a) => a.toJson()).toList(),
      tenantId: tenantId,
    );
  }

  static Map<String, dynamic> fromAssetEntity(AssetEntity entity) {
    if (entity.rawJson != null) {
      try {
        return json.decode(entity.rawJson!) as Map<String, dynamic>;
      } catch (e) {
        // Fallback
      }
    }
    return {
      'id': entity.id,
      'name': entity.name,
      'qrCode': entity.qrCode,
      'locationName': entity.locationName,
      'status': 'UNKNOWN',
    };
  }

  static AssetEntity? toAssetEntity(Map<String, dynamic> jsonMap, String tenantId) {
    final id = jsonMap['id']?.toString() ?? '';
    if (id.isEmpty) return null; // Prevent Null ID Fallback Risk

    return AssetEntity(
      id: id,
      name: jsonMap['name'] ?? '',
      qrCode: jsonMap['qrCode'],
      locationName: jsonMap['locationName'],
      tenantId: tenantId,
      isActive: jsonMap['isActive'] ?? true,
      lastUpdated: DateTime.now(),
      rawJson: json.encode(jsonMap),
    );
  }
}

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../../core/network/dio_client.dart';
import '../models/assistant_message.dart';

class AssistantService {
  final Dio _dio = DioClient().dio;

  /// Send prompt to AI Assistant backend
  Future<Map<String, dynamic>> sendChatPrompt({
    required String prompt,
    Map<String, dynamic>? assetContext,
  }) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final tenantId = prefs.getString('tenantId');

      final payload = <String, dynamic>{
        'prompt': prompt.trim(),
        'stream': false,
        if (tenantId != null && tenantId.isNotEmpty) 'tenant_id': tenantId,
        if (tenantId != null && tenantId.isNotEmpty) 'tenantId': tenantId,
      };

      if (assetContext != null && assetContext.isNotEmpty) {
        payload['assetContext'] = assetContext;
        payload['asset_context'] = assetContext;
      }

      final response = await _dio.post(
        '/api/v1/assistant/chat/',
        data: payload,
      );

      if (response.statusCode == 200 && response.data != null) {
        final resData = response.data;
        if (resData is Map<String, dynamic>) {
          return resData;
        }
      }
      return {
        'success': false,
        'error': 'Máy chủ trả về phản hồi không hợp lệ.',
      };
    } on DioException catch (e) {
      debugPrint('AssistantService.sendChatPrompt DioError: ${e.message}');
      String errorMessage = 'Không thể kết nối đến máy chủ Trợ lý AI.';
      if (e.response?.data is Map && e.response?.data['error'] != null) {
        errorMessage = e.response?.data['error'].toString() ?? errorMessage;
      } else if (e.type == DioExceptionType.connectionTimeout ||
          e.type == DioExceptionType.receiveTimeout) {
        errorMessage = 'Hết thời gian chờ phản hồi từ mô hình AI.';
      } else if (e.type == DioExceptionType.connectionError) {
        errorMessage = 'Mất kết nối mạng. Vui lòng kiểm tra lại Wifi/4G.';
      }

      return {
        'success': false,
        'error': errorMessage,
      };
    } catch (e) {
      debugPrint('AssistantService.sendChatPrompt error: $e');
      return {
        'success': false,
        'error': 'Đã xảy ra lỗi không xác định: $e',
      };
    }
  }

  /// Send technician feedback (thumbs up / thumbs down)
  Future<bool> sendFeedback({
    required String userQuery,
    required String generatedAnswer,
    required String voteType, // 'UPVOTE' or 'DOWNVOTE'
    String? feedback,
  }) async {
    try {
      final response = await _dio.post(
        '/api/v1/assistant/feedback/',
        data: {
          'userQuery': userQuery,
          'generatedAnswer': generatedAnswer,
          'voteType': voteType,
          'feedback': feedback ?? '',
        },
      );
      return response.statusCode == 200;
    } catch (e) {
      debugPrint('AssistantService.sendFeedback error: $e');
      return false;
    }
  }

  /// Create actionable work order draft from conversation
  /// STRICT: Creates draft with status 'CREATED', NO inventory deduction
  Future<Map<String, dynamic>?> createWorkOrderDraft({
    String? assetId,
    required String title,
    String? description,
    String? faultCode,
    String? priority,
  }) async {
    try {
      final response = await _dio.post(
        '/api/v1/assistant/create-work-order-draft/',
        data: {
          if (assetId != null && assetId.isNotEmpty) 'assetId': assetId,
          'title': title,
          if (description != null && description.isNotEmpty)
            'description': description,
          'faultCode': faultCode ?? 'MAINT_DIAGNOSTIC',
          'priority': priority ?? 'HIGH',
        },
      );

      if ((response.statusCode == 200 || response.statusCode == 201) &&
          response.data != null) {
        final body = response.data;
        if (body is Map<String, dynamic> && body['data'] != null) {
          return body['data'] as Map<String, dynamic>;
        }
      }
      return null;
    } catch (e) {
      debugPrint('AssistantService.createWorkOrderDraft error: $e');
      return null;
    }
  }

  /// Parse response data from backend into AssistantMessage
  AssistantMessage parseResponseToMessage({
    required String messageId,
    required Map<String, dynamic> responseData,
  }) {
    final data = responseData['data'] as Map<String, dynamic>? ?? {};

    final isEmergency = data['isEmergency'] == true;
    final hazardType = data['hazardType']?.toString();
    final emergencyName = data['emergencyName']?.toString();
    final actionSummary = data['actionSummary']?.toString();
    final reply = data['reply']?.toString() ?? 'Không nhận được câu trả lời từ hệ thống.';

    // Semantic relevance
    SemanticRelevance? semanticRelevance;
    if (data['semanticRelevance'] is Map<String, dynamic>) {
      semanticRelevance = SemanticRelevance.fromJson(
        data['semanticRelevance'] as Map<String, dynamic>,
      );
    }

    // Diagram anchors
    final diagramAnchors = <DiagramAnchor>[];
    if (data['diagramAnchors'] is List) {
      for (final item in data['diagramAnchors'] as List) {
        if (item is Map<String, dynamic>) {
          diagramAnchors.add(DiagramAnchor.fromJson(item));
        }
      }
    }

    // Inventory items
    final inventoryAvailability = <InventoryItem>[];
    if (data['inventoryAvailability'] is List) {
      for (final item in data['inventoryAvailability'] as List) {
        if (item is Map<String, dynamic>) {
          inventoryAvailability.add(InventoryItem.fromJson(item));
        }
      }
    }

    // Actionable work order draft
    WorkOrderDraft? actionableWorkOrderDraft;
    if (data['actionableWorkOrderDraft'] is Map<String, dynamic>) {
      actionableWorkOrderDraft = WorkOrderDraft.fromJson(
        data['actionableWorkOrderDraft'] as Map<String, dynamic>,
      );
    }

    // Cited sources
    final citedSources = <CitedSource>[];
    if (data['citedSources'] is List) {
      for (final item in data['citedSources'] as List) {
        if (item is Map<String, dynamic>) {
          citedSources.add(CitedSource.fromJson(item));
        }
      }
    }

    return AssistantMessage(
      id: messageId,
      sender: MessageSender.assistant,
      content: reply,
      timestamp: DateTime.now(),
      isLoading: false,
      isEmergency: isEmergency,
      hazardType: hazardType,
      emergencyName: emergencyName,
      actionSummary: actionSummary,
      semanticRelevance: semanticRelevance,
      diagramAnchors: diagramAnchors,
      inventoryAvailability: inventoryAvailability,
      actionableWorkOrderDraft: actionableWorkOrderDraft,
      citedSources: citedSources,
    );
  }
}

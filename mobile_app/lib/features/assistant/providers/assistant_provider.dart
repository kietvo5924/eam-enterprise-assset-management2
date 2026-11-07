import 'package:flutter/foundation.dart';
import 'package:uuid/uuid.dart';
import '../models/assistant_message.dart';
import '../services/assistant_service.dart';

class AssistantProvider extends ChangeNotifier {
  final AssistantService _service = AssistantService();
  final List<AssistantMessage> _messages = [];
  bool _isGenerating = false;
  Map<String, dynamic>? _currentAssetContext;

  List<AssistantMessage> get messages => List.unmodifiable(_messages);
  bool get isGenerating => _isGenerating;
  Map<String, dynamic>? get currentAssetContext => _currentAssetContext;

  AssistantProvider() {
    _initWelcomeMessage();
  }

  void _initWelcomeMessage() {
    _messages.clear();
    _messages.add(
      AssistantMessage(
        id: const Uuid().v4(),
        sender: MessageSender.assistant,
        content:
            'Xin chào Kỹ thuật viên! Tôi là Trợ lý Kỹ thuật AI EAM hỗ trợ hiện trường.\n\n'
            'Tôi có thể đồng hành cùng bạn:\n'
            '• Chẩn đoán sự cố theo tiếng lóng & từ tượng thanh (lạch cạch, phù tụ, xì khói)\n'
            '• Tra cứu sổ tay hướng dẫn chuẩn của hãng (OEM Manual) & mẹo thực tế xưởng\n'
            '• Kích hoạt giao thức an toàn sinh mạng khẩn cấp (Điện giật, Khí gas, E-Stop)\n'
            '• Kiểm tra tức thời tồn kho phụ tùng thay thế & vị trí kệ chứa\n'
            '• Khởi tạo 1-chạm bản thảo Phiếu bảo trì (Work Order Draft)\n\n'
            'Hãy nhập câu hỏi bên dưới hoặc chọn gợi ý nhanh!',
        timestamp: DateTime.now(),
        semanticRelevance: const SemanticRelevance(
          score: 1.0,
          tier: 'HIGH',
          tierLabel: 'Hệ thống sẵn sàng',
        ),
      ),
    );
  }

  void setAssetContext(Map<String, dynamic>? context) {
    _currentAssetContext = context;
    notifyListeners();
  }

  void clearAssetContext() {
    _currentAssetContext = null;
    notifyListeners();
  }

  void clearConversation() {
    _initWelcomeMessage();
    notifyListeners();
  }

  List<String> get quickSuggestions {
    if (_currentAssetContext != null) {
      final model = _currentAssetContext!['model'] ?? _currentAssetContext!['name'] ?? 'thiết bị';
      return [
        'Máy $model kêu lạch cạch và rung lắc',
        'Quy trình dừng an toàn khẩn cấp cho $model',
        'Phụ tùng thay thế và tồn kho cho $model',
        'Quy trình bảo dưỡng tiêu chuẩn định kỳ',
      ];
    }
    return [
      'Máy bơm kêu lạch cạch và rung mạnh',
      'Chập điện bốc khói tại tủ điều khiển',
      'Quy trình dừng khẩn cấp máy nén khí',
      'Kiểm tra tồn kho bạc đạn SKF',
      'Cách tạo phiếu bảo trì đột xuất',
    ];
  }

  Future<void> sendPrompt(String promptText) async {
    final trimmed = promptText.trim();
    if (trimmed.isEmpty || _isGenerating) return;

    final userMsgId = const Uuid().v4();
    final assistantMsgId = const Uuid().v4();

    // 1. Add User Message
    _messages.add(
      AssistantMessage(
        id: userMsgId,
        sender: MessageSender.user,
        content: trimmed,
        timestamp: DateTime.now(),
      ),
    );

    // 2. Add Loading Message Placeholder
    _isGenerating = true;
    _messages.add(
      AssistantMessage(
        id: assistantMsgId,
        sender: MessageSender.assistant,
        content: '',
        timestamp: DateTime.now(),
        isLoading: true,
      ),
    );
    notifyListeners();

    try {
      final responseData = await _service.sendChatPrompt(
        prompt: trimmed,
        assetContext: _currentAssetContext,
      );

      final index = _messages.indexWhere((m) => m.id == assistantMsgId);
      if (index != -1) {
        if (responseData['success'] == true && responseData['data'] != null) {
          final assistantMessage = _service.parseResponseToMessage(
            messageId: assistantMsgId,
            responseData: responseData,
          );
          _messages[index] = assistantMessage;
        } else {
          final errorText = responseData['error']?.toString() ??
              'Không thể nhận diện câu trả lời. Vui lòng thử lại.';
          _messages[index] = AssistantMessage(
            id: assistantMsgId,
            sender: MessageSender.assistant,
            content: '⚠️ $errorText',
            timestamp: DateTime.now(),
            isLoading: false,
            semanticRelevance: const SemanticRelevance(
              score: 0.0,
              tier: 'FALLBACK',
              tierLabel: 'Lỗi kết nối',
            ),
          );
        }
      }
    } catch (e) {
      final index = _messages.indexWhere((m) => m.id == assistantMsgId);
      if (index != -1) {
        _messages[index] = AssistantMessage(
          id: assistantMsgId,
          sender: MessageSender.assistant,
          content: '⚠️ Đã xảy ra lỗi khi trao đổi với Trợ lý AI: $e',
          timestamp: DateTime.now(),
          isLoading: false,
        );
      }
    } finally {
      _isGenerating = false;
      notifyListeners();
    }
  }

  /// Create Work Order Draft from conversation
  Future<Map<String, dynamic>?> createWorkOrderFromDraft(
    AssistantMessage message,
  ) async {
    final draft = message.actionableWorkOrderDraft;
    if (draft == null) return null;

    // Idempotency guard: prevent duplicate work orders if already created
    if (message.createdWorkOrderId != null) {
      return {
        'workOrderId': message.createdWorkOrderId,
        'code': message.createdWorkOrderCode,
        'status': 'CREATED',
        'alreadyCreated': true,
      };
    }

    final assetId = draft.assetId ?? _currentAssetContext?['assetId']?.toString();
    final result = await _service.createWorkOrderDraft(
      assetId: assetId,
      title: draft.suggestedTitle,
      description: 'Chẩn đoán AI:\n${message.content.substring(0, message.content.length.clamp(0, 500))}',
      faultCode: draft.faultCode,
      priority: draft.priority,
    );

    if (result != null) {
      final woId = result['workOrderId']?.toString() ?? result['id']?.toString();
      final woCode = result['code']?.toString() ?? 'WO-DRAFT';
      message.createdWorkOrderId = woId;
      message.createdWorkOrderCode = woCode;
      notifyListeners();
    }

    return result;
  }

  /// Send feedback vote
  Future<bool> submitFeedback(
    AssistantMessage message,
    String voteType, {
    String? feedbackNotes,
  }) async {
    // Find preceding user query
    final msgIndex = _messages.indexOf(message);
    String userQuery = 'Câu hỏi kỹ thuật';
    if (msgIndex > 0) {
      for (int i = msgIndex - 1; i >= 0; i--) {
        if (_messages[i].sender == MessageSender.user) {
          userQuery = _messages[i].content;
          break;
        }
      }
    }

    final success = await _service.sendFeedback(
      userQuery: userQuery,
      generatedAnswer: message.content,
      voteType: voteType,
      feedback: feedbackNotes,
    );

    if (success) {
      message.feedbackVote = voteType;
      notifyListeners();
    }
    return success;
  }
}

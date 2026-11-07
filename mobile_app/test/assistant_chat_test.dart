import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:mobile_app/features/assistant/models/assistant_message.dart';
import 'package:mobile_app/features/assistant/providers/assistant_provider.dart';
import 'package:mobile_app/features/assistant/widgets/semantic_relevance_badge.dart';
import 'package:mobile_app/features/assistant/widgets/life_safety_banner.dart';
import 'package:mobile_app/features/assistant/widgets/oem_tacit_content_card.dart';
import 'package:mobile_app/features/assistant/widgets/inventory_interlock_card.dart';
import 'package:mobile_app/features/assistant/widgets/work_order_draft_card.dart';
import 'package:mobile_app/features/assistant/widgets/diagram_anchor_card.dart';
import 'package:mobile_app/features/assistant/widgets/chat_bubble.dart';
import 'package:mobile_app/features/assistant/screens/assistant_chat_screen.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('Phase 11.9: AI Assistant Data Models Unit Tests', () {
    test('TC-ASSISTANT-MODEL-01: SemanticRelevance correctly parses and categorizes tiers', () {
      final highJson = {
        'score': 0.88,
        'tier': 'HIGH',
        'tierLabel': 'Độ tin cậy cao - Khớp chính xác tài liệu',
      };
      final highRel = SemanticRelevance.fromJson(highJson);
      expect(highRel.score, 0.88);
      expect(highRel.isHighConfidence, isTrue);
      expect(highRel.isMediumConfidence, isFalse);
      expect(highRel.isFallback, isFalse);
      expect(highRel.isEmergency, isFalse);

      final medJson = {
        'score': 0.70,
        'tier': 'MEDIUM',
        'tierLabel': 'Độ tin cậy trung bình',
      };
      final medRel = SemanticRelevance.fromJson(medJson);
      expect(medRel.isHighConfidence, isFalse);
      expect(medRel.isMediumConfidence, isTrue);

      final fallbackJson = {
        'score': 0.52,
        'tier': 'FALLBACK',
        'tierLabel': 'Ngưỡng an toàn',
      };
      final fallbackRel = SemanticRelevance.fromJson(fallbackJson);
      expect(fallbackRel.isFallback, isTrue);

      final emerJson = {
        'score': 1.0,
        'tier': 'EMERGENCY_OVERRIDE',
        'tierLabel': 'Khẩn cấp',
      };
      final emerRel = SemanticRelevance.fromJson(emerJson);
      expect(emerRel.isEmergency, isTrue);

      // Backend tier naming convention: HIGH_CONFIDENCE, MEDIUM_CONFIDENCE, LOW_CONFIDENCE
      final backendHigh = SemanticRelevance.fromJson({
        'score': 0.85,
        'tier': 'HIGH_CONFIDENCE',
        'tierLabel': 'Độ tương đồng cao (85%)',
      });
      expect(backendHigh.isHighConfidence, isTrue);
      expect(backendHigh.isMediumConfidence, isFalse);

      final backendMed = SemanticRelevance.fromJson({
        'score': 0.70,
        'tier': 'MEDIUM_CONFIDENCE',
        'tierLabel': 'Độ tương đồng trung bình (70%)',
      });
      expect(backendMed.isMediumConfidence, isTrue);
      expect(backendMed.isHighConfidence, isFalse);

      final backendLow = SemanticRelevance.fromJson({
        'score': 0.45,
        'tier': 'LOW_CONFIDENCE',
        'tierLabel': 'Độ tương đồng thấp (45%)',
      });
      expect(backendLow.isFallback, isTrue);
    });

    test('TC-ASSISTANT-MODEL-02: InventoryItem correctly parses stock and location from backend check_live_inventory', () {
      // 1. Real backend keys from inventory_interlock.py: partNumber, name, inStock (float), minStockLevel (float)
      final backendRealJson = {
        'partNumber': 'SKF-6205',
        'name': 'Vòng bi đỡ chặn SKF',
        'inStock': 8.0,
        'location': 'Kệ B3-12',
        'minStockLevel': 2.0,
        'unitCost': 150000.0,
      };
      final realItem = InventoryItem.fromJson(backendRealJson);
      expect(realItem.partCode, 'SKF-6205');
      expect(realItem.partName, 'Vòng bi đỡ chặn SKF');
      expect(realItem.currentStock, 8);
      expect(realItem.location, 'Kệ B3-12');
      expect(realItem.minStock, 2);
      expect(realItem.isInStock, isTrue);

      // 2. Fallback snake_case keys with int
      final json = {
        'part_code': 'SEAL-200',
        'part_name': 'Phớt làm kín',
        'current_stock': 3,
        'location': 'Kho tổng',
        'status': 'IN_STOCK',
      };
      final item = InventoryItem.fromJson(json);
      expect(item.partCode, 'SEAL-200');
      expect(item.partName, 'Phớt làm kín');
      expect(item.currentStock, 3);
      expect(item.location, 'Kho tổng');
      expect(item.isInStock, isTrue);

      // 3. Out of stock item with 0.0 float
      final outStockItem = InventoryItem.fromJson({
        'partNumber': 'BELT-V10',
        'name': 'Dây đai truyền động',
        'inStock': 0.0,
      });
      expect(outStockItem.currentStock, 0);
      expect(outStockItem.isInStock, isFalse);
      expect(outStockItem.status, 'OUT_OF_STOCK');
    });

    test('TC-ASSISTANT-MODEL-03: WorkOrderDraft strictly maintains CREATED status and non-deduction', () {
      final json = {
        'isDraftOnly': true,
        'suggestedStatus': 'CREATED',
        'inventoryDeducted': false,
        'suggestedTitle': 'Khắc phục sự cố máy bơm rung lắc',
        'faultCode': 'VIBRATION_HIGH',
        'priority': 'HIGH',
        'assetId': 'asset-uuid-1234',
      };
      final draft = WorkOrderDraft.fromJson(json);
      expect(draft.isDraftOnly, isTrue);
      expect(draft.suggestedStatus, 'CREATED');
      expect(draft.inventoryDeducted, isFalse);
      expect(draft.suggestedTitle, 'Khắc phục sự cố máy bơm rung lắc');
      expect(draft.priority, 'HIGH');
      expect(draft.assetId, 'asset-uuid-1234');
    });

    test('TC-ASSISTANT-MODEL-04: DiagramAnchor and CitedSource parse accurately', () {
      final anchorJson = {
        'figureId': 'Fig 4.1',
        'pageNumber': 28,
        'caption': 'Sơ đồ mặt cắt cụm phớt cơ khí',
      };
      final anchor = DiagramAnchor.fromJson(anchorJson);
      expect(anchor.figureId, 'Fig 4.1');
      expect(anchor.pageNumber, 28);
      expect(anchor.caption, 'Sơ đồ mặt cắt cụm phớt cơ khí');

      final sourceJson = {
        'documentName': 'OEM_Pump_Manual.pdf',
        'pageNumber': 15,
        'similarityScore': 0.892,
      };
      final source = CitedSource.fromJson(sourceJson);
      expect(source.documentName, 'OEM_Pump_Manual.pdf');
      expect(source.pageNumber, 15);
      expect(source.similarityScore, 0.892);
    });

    test('TC-ASSISTANT-MODEL-05: Non-int numeric types and string numbers do not throw TypeError', () {
      final anchor = DiagramAnchor.fromJson({
        'figure_id': 'Fig 2',
        'page': 12.0, // float page
        'title': 'Sơ đồ mạch',
      });
      expect(anchor.figureId, 'Fig 2');
      expect(anchor.pageNumber, 12);

      final source = CitedSource.fromJson({
        'document_name': 'Manual.pdf',
        'page_number': '7', // string page
        'similarity_score': 0.95,
      });
      expect(source.pageNumber, 7);
      expect(source.similarityScore, 0.95);
    });
  });

  group('Phase 11.9: AssistantProvider Unit Tests', () {
    test('TC-ASSISTANT-PROV-01: Provider initializes with welcoming message and readiness', () {
      final provider = AssistantProvider();
      expect(provider.messages, isNotEmpty);
      expect(provider.messages.first.sender, MessageSender.assistant);
      expect(provider.isGenerating, isFalse);
      expect(provider.currentAssetContext, isNull);
    });

    test('TC-ASSISTANT-PROV-02: Asset context updates quick suggestions appropriately', () {
      final provider = AssistantProvider();
      expect(provider.quickSuggestions.any((s) => s.contains('Máy bơm')), isTrue);

      provider.setAssetContext({
        'assetId': 'ast-99',
        'name': 'Máy Nén Khí Trục Vít',
        'model': 'COMP-V200',
      });
      expect(provider.currentAssetContext?['model'], 'COMP-V200');
      expect(provider.quickSuggestions.any((s) => s.contains('COMP-V200')), isTrue);

      provider.clearAssetContext();
      expect(provider.currentAssetContext, isNull);
    });

    test('TC-ASSISTANT-PROV-03: createWorkOrderFromDraft is idempotent when already created', () async {
      final provider = AssistantProvider();
      final message = AssistantMessage(
        id: 'msg-draft-1',
        sender: MessageSender.assistant,
        content: 'Chẩn đoán',
        timestamp: DateTime.now(),
        actionableWorkOrderDraft: const WorkOrderDraft(
          suggestedTitle: 'Phiếu kiểm tra',
        ),
        createdWorkOrderId: 'wo-existing-123',
        createdWorkOrderCode: 'WO-2026-0099',
      );

      final result = await provider.createWorkOrderFromDraft(message);
      expect(result?['alreadyCreated'], isTrue);
      expect(result?['workOrderId'], 'wo-existing-123');
      expect(result?['code'], 'WO-2026-0099');
    });
  });

  group('Phase 11.9: AI Assistant Widget Components Tests', () {
    testWidgets('TC-ASSISTANT-WIDGET-01: SemanticRelevanceBadge renders accurate confidence levels', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: Column(
              children: [
                SemanticRelevanceBadge(
                  relevance: SemanticRelevance(
                    score: 0.85,
                    tier: 'HIGH',
                    tierLabel: 'Độ tin cậy cao',
                  ),
                ),
                SemanticRelevanceBadge(
                  relevance: SemanticRelevance(
                    score: 0.68,
                    tier: 'MEDIUM',
                    tierLabel: 'Độ tin cậy trung bình',
                  ),
                ),
                SemanticRelevanceBadge(
                  relevance: SemanticRelevance(
                    score: 0.50,
                    tier: 'FALLBACK',
                    tierLabel: 'Ngưỡng an toàn',
                  ),
                ),
                SemanticRelevanceBadge(
                  relevance: SemanticRelevance(
                    score: 1.0,
                    tier: 'EMERGENCY_OVERRIDE',
                    tierLabel: 'Khẩn cấp',
                  ),
                ),
              ],
            ),
          ),
        ),
      );

      expect(find.textContaining('85% khớp ngữ nghĩa'), findsOneWidget);
      expect(find.textContaining('68% - Cần đối chiếu'), findsOneWidget);
      expect(find.textContaining('50% - Ngưỡng an toàn'), findsOneWidget);
      expect(find.textContaining('KHẨN CẤP'), findsOneWidget);
    });

    testWidgets('TC-ASSISTANT-WIDGET-02: LifeSafetyBanner renders emergency alert and instructions', (tester) async {
      final emergencyMessage = AssistantMessage(
        id: 'msg-emer-01',
        sender: MessageSender.assistant,
        content: 'Cắt cầu dao tổng ngay lập tức. TUYỆT ĐỐI CẤM DÙNG NƯỚC DẬP LỬA DẦU BIẾN ÁP.',
        timestamp: DateTime.now(),
        isEmergency: true,
        hazardType: 'ELECTRICAL_FIRE',
        emergencyName: 'Chập Điện / Cháy Trạm Biến Áp',
        actionSummary: 'CẮT CẦU DAO TỔNG - DÙNG BÌNH KHÍ CO2 HOẶC BỘT KHÔ',
      );

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: LifeSafetyBanner(message: emergencyMessage),
          ),
        ),
      );

      expect(find.text('CẢNH BÁO AN TOÀN SINH MẠNG KHẨN CẤP'), findsOneWidget);
      expect(find.text('Chập Điện / Cháy Trạm Biến Áp'), findsOneWidget);
      expect(find.text('CẮT CẦU DAO TỔNG - DÙNG BÌNH KHÍ CO2 HOẶC BỘT KHÔ'), findsOneWidget);
      expect(find.textContaining('TUYỆT ĐỐI CẤM DÙNG NƯỚC'), findsOneWidget);
    });

    testWidgets('TC-ASSISTANT-WIDGET-03: OemTacitContentCard renders dual streams and safety highlights', (tester) async {
      const dualText = '''
### 1. 📖 HƯỚNG DẪN CHUẨN TỪ HÃNG (OEM MANUAL):
Bước 1: Nới lỏng 4 bu lông cố định trục.
Bước 2: CẤM DÙNG BÚA GÕ TRỰC TIẾP LÊN VỎ BƠM.

### 2. 💡 MẸO THỰC TẾ TẠI NHÀ MÁY (Kế thừa từ WO-2023-0112):
Xịt RP7 ngâm 15 phút trước khi vặn bu-lông gỉ sét.
''';

      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: OemTacitContentCard(content: dualText),
            ),
          ),
        ),
      );

      expect(find.textContaining('HƯỚNG DẪN CHUẨN TỪ HÃNG'), findsOneWidget);
      expect(find.textContaining('MẸO THỰC TẾ TẠI NHÀ MÁY'), findsOneWidget);
      expect(find.textContaining('Xịt RP7 ngâm 15 phút'), findsOneWidget);
      expect(find.textContaining('CẤM DÙNG BÚA GÕ TRỰC TIẾP'), findsOneWidget);
    });

    testWidgets('TC-ASSISTANT-WIDGET-04: InventoryInterlockCard displays parts availability', (tester) async {
      final items = [
        const InventoryItem(
          partCode: 'SEAL-200',
          partName: 'Phớt cơ khí chịu nhiệt',
          currentStock: 4,
          location: 'Kệ A1-02',
          status: 'IN_STOCK',
        ),
        const InventoryItem(
          partCode: 'PUMP-IMPELLER',
          partName: 'Cánh bơm ly tâm',
          currentStock: 0,
          location: 'Kho tổng',
          status: 'OUT_OF_STOCK',
        ),
      ];

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: InventoryInterlockCard(items: items),
          ),
        ),
      );

      expect(find.text('TRA CỨU TỒN KHO PHỤ TÙNG (LIVE INTERLOCK)'), findsOneWidget);
      expect(find.text('Phớt cơ khí chịu nhiệt'), findsOneWidget);
      expect(find.text('CÒN HÀNG (4)'), findsOneWidget);
      expect(find.text('HẾT HÀNG (0)'), findsOneWidget);
      expect(find.textContaining('Kệ A1-02'), findsOneWidget);
    });

    testWidgets('TC-ASSISTANT-WIDGET-05: WorkOrderDraftCard displays draft information and action button', (tester) async {
      final message = AssistantMessage(
        id: 'msg-wo-01',
        sender: MessageSender.assistant,
        content: 'Chẩn đoán: Hỏng vòng bi đỡ chặn do quá nhiệt.',
        timestamp: DateTime.now(),
        actionableWorkOrderDraft: const WorkOrderDraft(
          isDraftOnly: true,
          suggestedStatus: 'CREATED',
          inventoryDeducted: false,
          suggestedTitle: 'Sửa chữa thay thế vòng bi máy bơm ly tâm',
          faultCode: 'BEARING_OVERHEAT',
          priority: 'HIGH',
        ),
      );

      await tester.pumpWidget(
        MaterialApp(
          home: ChangeNotifierProvider(
            create: (_) => AssistantProvider(),
            child: Scaffold(
              body: WorkOrderDraftCard(message: message),
            ),
          ),
        ),
      );

      expect(find.text('ĐỀ XUẤT PHIẾU BẢO TRÌ (WORK ORDER DRAFT)'), findsOneWidget);
      expect(find.text('Sửa chữa thay thế vòng bi máy bơm ly tâm'), findsOneWidget);
      expect(find.text('TRẠNG THÁI: CREATED'), findsOneWidget);
      expect(find.text('ƯU TIÊN: HIGH'), findsOneWidget);
      expect(find.text('Tạo phiếu sửa chữa ngay'), findsOneWidget);
    });

    testWidgets('TC-ASSISTANT-WIDGET-06: DiagramAnchorCard renders schematic references', (tester) async {
      final anchors = [
        const DiagramAnchor(
          figureId: 'Fig 3.2',
          pageNumber: 42,
          caption: 'Sơ đồ lắp ráp mặt bích và gioăng làm kín',
        ),
      ];

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: DiagramAnchorCard(anchors: anchors),
          ),
        ),
      );

      expect(find.text('BẢN VẼ SƠ ĐỒ KỸ THUẬT (DIAGRAM ANCHORS)'), findsOneWidget);
      expect(find.text('Fig 3.2 (Trang 42)'), findsOneWidget);
      expect(find.text('Sơ đồ lắp ráp mặt bích và gioăng làm kín'), findsOneWidget);
    });

    testWidgets('TC-ASSISTANT-WIDGET-07: ChatBubble renders user bubble and assistant bubble', (tester) async {
      final userMessage = AssistantMessage(
        id: 'msg-u1',
        sender: MessageSender.user,
        content: 'Bơm nước giải nhiệt kêu rít mạnh',
        timestamp: DateTime.now(),
      );

      final assistantMessage = AssistantMessage(
        id: 'msg-a1',
        sender: MessageSender.assistant,
        content: 'Kiểm tra độ chùng dây đai hoặc bạc đạn.',
        timestamp: DateTime.now(),
        semanticRelevance: const SemanticRelevance(
          score: 0.82,
          tier: 'HIGH',
          tierLabel: 'Khớp cao',
        ),
      );

      await tester.pumpWidget(
        MaterialApp(
          home: ChangeNotifierProvider(
            create: (_) => AssistantProvider(),
            child: Scaffold(
              body: Column(
                children: [
                  ChatBubble(message: userMessage),
                  ChatBubble(message: assistantMessage),
                ],
              ),
            ),
          ),
        ),
      );

      expect(find.text('Bơm nước giải nhiệt kêu rít mạnh'), findsOneWidget);
      expect(find.textContaining('Kiểm tra độ chùng dây đai'), findsOneWidget);
      expect(find.textContaining('82% khớp ngữ nghĩa'), findsOneWidget);
    });

    testWidgets('TC-ASSISTANT-SCREEN-07: AssistantChatScreen renders full UI and input controls', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: ChangeNotifierProvider(
            create: (_) => AssistantProvider(),
            child: const AssistantChatScreen(),
          ),
        ),
      );

      expect(find.text('Trợ lý Kỹ thuật AI'), findsOneWidget);
      expect(find.text('RAG On-Premises • Sẵn sàng'), findsOneWidget);
      expect(find.byType(TextField), findsOneWidget);
      expect(find.text('Hỏi mã lỗi, an toàn, sơ đồ máy...'), findsOneWidget);
      expect(find.byType(ActionChip), findsWidgets);
    });
  });
}

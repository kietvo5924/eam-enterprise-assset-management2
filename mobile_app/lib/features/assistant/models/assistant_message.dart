enum MessageSender {
  user,
  assistant,
}

class SemanticRelevance {
  final double score;
  final String tier;
  final String tierLabel;

  const SemanticRelevance({
    required this.score,
    required this.tier,
    required this.tierLabel,
  });

  factory SemanticRelevance.fromJson(Map<String, dynamic> json) {
    return SemanticRelevance(
      score: (json['score'] as num?)?.toDouble() ?? 0.0,
      tier: (json['tier'] as String?) ?? 'FALLBACK',
      tierLabel: (json['tierLabel'] as String?) ??
          (json['tier_label'] as String?) ??
          'Độ tin cậy tài liệu',
    );
  }

  bool get isEmergency => tier == 'EMERGENCY_OVERRIDE';

  bool get isHighConfidence =>
      !isEmergency &&
      (tier == 'HIGH' ||
          tier == 'HIGH_CONFIDENCE' ||
          (score >= 0.75 &&
              tier != 'MEDIUM' &&
              tier != 'MEDIUM_CONFIDENCE' &&
              tier != 'LOW_CONFIDENCE' &&
              tier != 'FALLBACK'));

  bool get isMediumConfidence =>
      !isEmergency &&
      (tier == 'MEDIUM' ||
          tier == 'MEDIUM_CONFIDENCE' ||
          (score >= 0.65 &&
              score < 0.75 &&
              tier != 'HIGH' &&
              tier != 'HIGH_CONFIDENCE' &&
              tier != 'LOW_CONFIDENCE' &&
              tier != 'FALLBACK'));

  bool get isFallback =>
      !isEmergency &&
      (tier == 'FALLBACK' ||
          tier == 'LOW_CONFIDENCE' ||
          (!isHighConfidence && !isMediumConfidence));
}

class DiagramAnchor {
  final String? figureId;
  final int? pageNumber;
  final String? caption;
  final String? imageUrl;

  const DiagramAnchor({
    this.figureId,
    this.pageNumber,
    this.caption,
    this.imageUrl,
  });

  factory DiagramAnchor.fromJson(Map<String, dynamic> json) {
    final rawPage = json['pageNumber'] ?? json['page_number'] ?? json['page'];
    final int? page = rawPage != null
        ? ((rawPage is num) ? rawPage.toInt() : int.tryParse(rawPage.toString()))
        : null;

    return DiagramAnchor(
      figureId: json['figureId']?.toString() ?? json['figure_id']?.toString(),
      pageNumber: page,
      caption: json['caption']?.toString() ?? json['title']?.toString(),
      imageUrl: json['imageUrl']?.toString() ?? json['image_url']?.toString(),
    );
  }
}

class InventoryItem {
  final String partCode;
  final String partName;
  final int currentStock;
  final String location;
  final String status;
  final int? minStock;

  const InventoryItem({
    required this.partCode,
    required this.partName,
    required this.currentStock,
    required this.location,
    required this.status,
    this.minStock,
  });

  factory InventoryItem.fromJson(Map<String, dynamic> json) {
    final rawStock = json['inStock'] ??
        json['current_stock'] ??
        json['currentStock'] ??
        json['quantity'] ??
        0;
    final int stock = (rawStock is num)
        ? rawStock.round()
        : (int.tryParse(rawStock.toString()) ?? 0);

    final rawMin = json['minStockLevel'] ?? json['min_stock'] ?? json['minStock'];
    final int? minStock = rawMin != null
        ? ((rawMin is num) ? rawMin.round() : int.tryParse(rawMin.toString()))
        : null;

    final code = json['partNumber']?.toString() ??
        json['part_code']?.toString() ??
        json['partCode']?.toString() ??
        '';

    final name = json['name']?.toString() ??
        json['part_name']?.toString() ??
        json['partName']?.toString() ??
        'Phụ tùng';

    final loc = json['location']?.toString() ?? 'Kho tổng';
    final rawStatus = json['status']?.toString();
    final status = rawStatus != null && rawStatus.isNotEmpty
        ? rawStatus
        : (stock > 0 ? 'IN_STOCK' : 'OUT_OF_STOCK');

    return InventoryItem(
      partCode: code,
      partName: name,
      currentStock: stock,
      location: loc,
      status: status,
      minStock: minStock,
    );
  }

  bool get isInStock => currentStock > 0;
}

class WorkOrderDraft {
  final bool isDraftOnly;
  final String suggestedStatus;
  final bool inventoryDeducted;
  final String suggestedTitle;
  final String faultCode;
  final String priority;
  final String? assetId;

  const WorkOrderDraft({
    this.isDraftOnly = true,
    this.suggestedStatus = 'CREATED',
    this.inventoryDeducted = false,
    required this.suggestedTitle,
    this.faultCode = 'MAINT_DIAGNOSTIC',
    this.priority = 'HIGH',
    this.assetId,
  });

  factory WorkOrderDraft.fromJson(Map<String, dynamic> json) {
    return WorkOrderDraft(
      isDraftOnly: json['isDraftOnly'] as bool? ?? true,
      suggestedStatus: json['suggestedStatus']?.toString() ?? 'CREATED',
      inventoryDeducted: json['inventoryDeducted'] as bool? ?? false,
      suggestedTitle: json['suggestedTitle']?.toString() ??
          json['title']?.toString() ??
          'Phiếu bảo trì chẩn đoán AI',
      faultCode: json['faultCode']?.toString() ??
          json['fault_code']?.toString() ??
          'MAINT_DIAGNOSTIC',
      priority: json['priority']?.toString() ?? 'HIGH',
      assetId: json['assetId']?.toString() ?? json['asset_id']?.toString(),
    );
  }
}

class CitedSource {
  final String documentName;
  final int pageNumber;
  final double similarityScore;

  const CitedSource({
    required this.documentName,
    required this.pageNumber,
    required this.similarityScore,
  });

  factory CitedSource.fromJson(Map<String, dynamic> json) {
    final rawPage = json['pageNumber'] ?? json['page_number'] ?? 1;
    final int page = (rawPage is num)
        ? rawPage.toInt()
        : (int.tryParse(rawPage.toString()) ?? 1);

    final rawScore = json['similarityScore'] ??
        json['similarity_score'] ??
        json['similarity'] ??
        0.0;
    final double score = (rawScore is num)
        ? rawScore.toDouble()
        : (double.tryParse(rawScore.toString()) ?? 0.0);

    return CitedSource(
      documentName: json['documentName']?.toString() ??
          json['document_name']?.toString() ??
          'Tài liệu kỹ thuật',
      pageNumber: page,
      similarityScore: score,
    );
  }
}

class AssistantMessage {
  final String id;
  final MessageSender sender;
  final String content;
  final DateTime timestamp;
  final bool isLoading;
  final bool isEmergency;
  final String? hazardType;
  final String? emergencyName;
  final String? actionSummary;
  final SemanticRelevance? semanticRelevance;
  final List<DiagramAnchor> diagramAnchors;
  final List<InventoryItem> inventoryAvailability;
  final WorkOrderDraft? actionableWorkOrderDraft;
  final List<CitedSource> citedSources;
  String? feedbackVote;
  String? createdWorkOrderId;
  String? createdWorkOrderCode;

  AssistantMessage({
    required this.id,
    required this.sender,
    required this.content,
    required this.timestamp,
    this.isLoading = false,
    this.isEmergency = false,
    this.hazardType,
    this.emergencyName,
    this.actionSummary,
    this.semanticRelevance,
    this.diagramAnchors = const [],
    this.inventoryAvailability = const [],
    this.actionableWorkOrderDraft,
    this.citedSources = const [],
    this.feedbackVote,
    this.createdWorkOrderId,
    this.createdWorkOrderCode,
  });

  AssistantMessage copyWith({
    String? id,
    MessageSender? sender,
    String? content,
    DateTime? timestamp,
    bool? isLoading,
    bool? isEmergency,
    String? hazardType,
    String? emergencyName,
    String? actionSummary,
    SemanticRelevance? semanticRelevance,
    List<DiagramAnchor>? diagramAnchors,
    List<InventoryItem>? inventoryAvailability,
    WorkOrderDraft? actionableWorkOrderDraft,
    List<CitedSource>? citedSources,
    String? feedbackVote,
    String? createdWorkOrderId,
    String? createdWorkOrderCode,
  }) {
    return AssistantMessage(
      id: id ?? this.id,
      sender: sender ?? this.sender,
      content: content ?? this.content,
      timestamp: timestamp ?? this.timestamp,
      isLoading: isLoading ?? this.isLoading,
      isEmergency: isEmergency ?? this.isEmergency,
      hazardType: hazardType ?? this.hazardType,
      emergencyName: emergencyName ?? this.emergencyName,
      actionSummary: actionSummary ?? this.actionSummary,
      semanticRelevance: semanticRelevance ?? this.semanticRelevance,
      diagramAnchors: diagramAnchors ?? this.diagramAnchors,
      inventoryAvailability: inventoryAvailability ?? this.inventoryAvailability,
      actionableWorkOrderDraft: actionableWorkOrderDraft ?? this.actionableWorkOrderDraft,
      citedSources: citedSources ?? this.citedSources,
      feedbackVote: feedbackVote ?? this.feedbackVote,
      createdWorkOrderId: createdWorkOrderId ?? this.createdWorkOrderId,
      createdWorkOrderCode: createdWorkOrderCode ?? this.createdWorkOrderCode,
    );
  }
}

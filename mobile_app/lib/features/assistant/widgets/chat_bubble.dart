import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';
import 'package:provider/provider.dart';
import '../../../core/theme/app_theme.dart';
import '../models/assistant_message.dart';
import '../providers/assistant_provider.dart';
import 'semantic_relevance_badge.dart';
import 'life_safety_banner.dart';
import 'oem_tacit_content_card.dart';
import 'inventory_interlock_card.dart';
import 'work_order_draft_card.dart';
import 'diagram_anchor_card.dart';

class ChatBubble extends StatelessWidget {
  final AssistantMessage message;

  const ChatBubble({
    super.key,
    required this.message,
  });

  @override
  Widget build(BuildContext context) {
    final isUser = message.sender == MessageSender.user;

    if (isUser) {
      return _buildUserBubble(context);
    } else {
      return _buildAssistantBubble(context);
    }
  }

  Widget _buildUserBubble(BuildContext context) {
    final timeStr = DateFormat('HH:mm').format(message.timestamp);

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6, horizontal: 12),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.end,
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Text(
            timeStr,
            style: const TextStyle(fontSize: 10, color: AppTheme.neutral400),
          ),
          const SizedBox(width: 8),
          Flexible(
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              decoration: BoxDecoration(
                color: AppTheme.primaryColor,
                borderRadius: const BorderRadius.only(
                  topLeft: Radius.circular(16),
                  topRight: Radius.circular(16),
                  bottomLeft: Radius.circular(16),
                  bottomRight: Radius.circular(4),
                ),
                boxShadow: [
                  BoxShadow(
                    color: AppTheme.primaryColor.withValues(alpha: 0.2),
                    blurRadius: 8,
                    offset: const Offset(0, 2),
                  ),
                ],
              ),
              child: Text(
                message.content,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 14,
                  height: 1.4,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ),
          ),
          const SizedBox(width: 8),
          CircleAvatar(
            radius: 14,
            backgroundColor: AppTheme.neutral200,
            child: const Icon(PhosphorIconsRegular.user, size: 16, color: AppTheme.neutral700),
          ),
        ],
      ),
    );
  }

  Widget _buildAssistantBubble(BuildContext context) {
    final timeStr = DateFormat('HH:mm').format(message.timestamp);

    if (message.isLoading) {
      return _buildLoadingBubble();
    }

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6, horizontal: 12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // AI Robot Avatar
          Container(
            width: 32,
            height: 32,
            decoration: const BoxDecoration(
              shape: BoxShape.circle,
              gradient: LinearGradient(
                colors: [Color(0xFF0284C7), Color(0xFF0F172A)],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
            ),
            child: Center(
              child: Icon(
                PhosphorIcons.robot(PhosphorIconsStyle.fill),
                color: Colors.white,
                size: 18,
              ),
            ),
          ),
          const SizedBox(width: 10),

          // Message Card Content
          Expanded(
            child: Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: const BorderRadius.only(
                  topLeft: Radius.circular(4),
                  topRight: Radius.circular(16),
                  bottomLeft: Radius.circular(16),
                  bottomRight: Radius.circular(16),
                ),
                border: Border.all(color: const Color(0xFFE2E8F0)),
                boxShadow: const [
                  BoxShadow(
                    color: Color(0x06000000),
                    blurRadius: 10,
                    offset: Offset(0, 3),
                  ),
                ],
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // 1. Semantic Relevance Badge
                  if (message.semanticRelevance != null) ...[
                    SemanticRelevanceBadge(relevance: message.semanticRelevance!),
                    const SizedBox(height: 8),
                  ],

                  // 2. Life-Safety Override Banner or Structured OEM Content
                  if (message.isEmergency) ...[
                    LifeSafetyBanner(message: message),
                  ] else ...[
                    OemTacitContentCard(content: message.content),
                  ],

                  // 3. Diagram Anchors
                  if (message.diagramAnchors.isNotEmpty) ...[
                    DiagramAnchorCard(anchors: message.diagramAnchors),
                  ],

                  // 4. Live Inventory Interlock Card
                  if (message.inventoryAvailability.isNotEmpty) ...[
                    InventoryInterlockCard(items: message.inventoryAvailability),
                  ],

                  // 5. Actionable Work Order Draft Card
                  if (message.actionableWorkOrderDraft != null) ...[
                    WorkOrderDraftCard(message: message),
                  ],

                  // 6. Cited Sources
                  if (message.citedSources.isNotEmpty) ...[
                    _buildCitedSources(message.citedSources),
                  ],

                  const SizedBox(height: 8),

                  // Bottom bar: Timestamp & Thumbs feedback
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        timeStr,
                        style: const TextStyle(fontSize: 10, color: AppTheme.neutral400),
                      ),
                      _buildFeedbackRow(context),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildLoadingBubble() {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 32,
            height: 32,
            decoration: const BoxDecoration(
              shape: BoxShape.circle,
              color: AppTheme.neutral800,
            ),
            child: const Center(
              child: Icon(
                PhosphorIconsRegular.robot,
                color: Colors.white,
                size: 18,
              ),
            ),
          ),
          const SizedBox(width: 10),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: const Color(0xFFE2E8F0)),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                const SizedBox(
                  width: 14,
                  height: 14,
                  child: CircularProgressIndicator(strokeWidth: 2, color: AppTheme.primaryColor),
                ),
                const SizedBox(width: 10),
                const Text(
                  'Đang tra cứu tài liệu & kiểm tra tồn kho...',
                  style: TextStyle(
                    fontSize: 12,
                    color: AppTheme.neutral600,
                    fontStyle: FontStyle.italic,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildCitedSources(List<CitedSource> sources) {
    return Container(
      margin: const EdgeInsets.only(top: 8),
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: const Color(0xFFF8FAFC),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: const Color(0xFFE2E8F0)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(PhosphorIconsRegular.fileText, size: 12, color: AppTheme.neutral500),
              SizedBox(width: 4),
              Text(
                'TÀI LIỆU TRÍCH DẪN (PROVENANCE):',
                style: TextStyle(
                  fontSize: 9,
                  fontWeight: FontWeight.bold,
                  color: AppTheme.neutral500,
                  letterSpacing: 0.3,
                ),
              ),
            ],
          ),
          const SizedBox(height: 4),
          ...sources.map(
            (s) => Padding(
              padding: const EdgeInsets.only(bottom: 2),
              child: Text(
                '• ${s.documentName} (Trang ${s.pageNumber}) - ${(s.similarityScore * 100).toInt()}% khớp',
                style: const TextStyle(fontSize: 10, color: AppTheme.neutral700),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFeedbackRow(BuildContext context) {
    final voted = message.feedbackVote;

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        InkWell(
          borderRadius: BorderRadius.circular(12),
          onTap: voted != null
              ? null
              : () async {
                  final provider = context.read<AssistantProvider>();
                  final ok = await provider.submitFeedback(message, 'UPVOTE');
                  if (ok && context.mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(
                        content: Text('Cảm ơn phản hồi hữu ích của bạn!'),
                        backgroundColor: AppTheme.successColor,
                        duration: Duration(seconds: 2),
                      ),
                    );
                  }
                },
          child: Padding(
            padding: const EdgeInsets.all(4.0),
            child: Icon(
              PhosphorIcons.thumbsUp(voted == 'UPVOTE' ? PhosphorIconsStyle.fill : PhosphorIconsStyle.regular),
              size: 16,
              color: voted == 'UPVOTE' ? AppTheme.successColor : AppTheme.neutral400,
            ),
          ),
        ),
        const SizedBox(width: 8),
        InkWell(
          borderRadius: BorderRadius.circular(12),
          onTap: voted != null
              ? null
              : () => _showDownvoteDialog(context),
          child: Padding(
            padding: const EdgeInsets.all(4.0),
            child: Icon(
              PhosphorIcons.thumbsDown(voted == 'DOWNVOTE' ? PhosphorIconsStyle.fill : PhosphorIconsStyle.regular),
              size: 16,
              color: voted == 'DOWNVOTE' ? AppTheme.dangerColor : AppTheme.neutral400,
            ),
          ),
        ),
      ],
    );
  }

  void _showDownvoteDialog(BuildContext context) {
    final textController = TextEditingController();

    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Row(
          children: [
            Icon(PhosphorIconsRegular.thumbsDown, color: AppTheme.warningColor, size: 22),
            SizedBox(width: 8),
            Text('Góp Ý Cho Kỹ Sư Trưởng', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Câu trả lời sẽ được chuyển vào Hàng đợi Thẩm định (Curation Queue) của Kỹ sư trưởng để cập nhật tri thức vàng.',
              style: TextStyle(fontSize: 12, color: AppTheme.neutral600),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: textController,
              maxLines: 3,
              decoration: InputDecoration(
                hintText: 'Nhập nội dung chưa hài lòng hoặc cách xử lý thực tế...',
                hintStyle: const TextStyle(fontSize: 12),
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                contentPadding: const EdgeInsets.all(10),
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Hủy'),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: AppTheme.primaryColor,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
            ),
            onPressed: () async {
              Navigator.pop(ctx);
              final provider = context.read<AssistantProvider>();
              final ok = await provider.submitFeedback(
                message,
                'DOWNVOTE',
                feedbackNotes: textController.text.trim(),
              );
              if (ok && context.mounted) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text('Đã gửi phản hồi vào Hàng đợi Thẩm định của Kỹ sư trưởng.'),
                    backgroundColor: AppTheme.primaryColor,
                  ),
                );
              }
            },
            child: const Text('Gửi phản hồi', style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );
  }
}

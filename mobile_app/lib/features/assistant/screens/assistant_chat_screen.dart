import 'package:flutter/material.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';
import 'package:provider/provider.dart';
import 'package:go_router/go_router.dart';
import '../../../core/theme/app_theme.dart';
import '../providers/assistant_provider.dart';
import '../widgets/chat_bubble.dart';

class AssistantChatScreen extends StatefulWidget {
  final Map<String, dynamic>? initialAssetContext;

  const AssistantChatScreen({
    super.key,
    this.initialAssetContext,
  });

  @override
  State<AssistantChatScreen> createState() => _AssistantChatScreenState();
}

class _AssistantChatScreenState extends State<AssistantChatScreen> {
  final TextEditingController _textController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final FocusNode _focusNode = FocusNode();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (widget.initialAssetContext != null) {
        context.read<AssistantProvider>().setAssetContext(widget.initialAssetContext);
      }
      _scrollToBottom();
    });
  }

  @override
  void dispose() {
    _textController.dispose();
    _scrollController.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  void _handleSend([String? presetText]) {
    final text = presetText ?? _textController.text;
    if (text.trim().isEmpty) return;

    final provider = context.read<AssistantProvider>();
    if (provider.isGenerating) return;

    _textController.clear();
    provider.sendPrompt(text);
    _scrollToBottom();
  }

  void _showClearConfirmation(BuildContext context) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Text('Xóa lịch sử hội thoại?', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
        content: const Text(
          'Toàn bộ câu hỏi và chẩn đoán sự cố hiện tại sẽ được làm mới về trạng thái ban đầu.',
          style: TextStyle(fontSize: 13, color: AppTheme.neutral600),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Hủy'),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: AppTheme.dangerColor,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
            ),
            onPressed: () {
              Navigator.pop(ctx);
              context.read<AssistantProvider>().clearConversation();
            },
            child: const Text('Xóa hội thoại', style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<AssistantProvider>();
    final messages = provider.messages;
    final isGenerating = provider.isGenerating;
    final assetContext = provider.currentAssetContext;

    // Auto-scroll when new messages arrive
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients &&
          _scrollController.position.extentAfter < 200) {
        _scrollToBottom();
      }
    });

    return Scaffold(
      backgroundColor: const Color(0xFFF8FAFC),
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        titleSpacing: 0,
        leading: IconButton(
          icon: Icon(PhosphorIcons.arrowLeft(), color: AppTheme.neutral900),
          onPressed: () => context.pop(),
        ),
        title: Row(
          children: [
            Container(
              width: 38,
              height: 38,
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
                  PhosphorIcons.sparkle(PhosphorIconsStyle.fill),
                  color: const Color(0xFF38BDF8),
                  size: 20,
                ),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Row(
                    children: [
                      Text(
                        'Trợ lý Kỹ thuật AI',
                        style: TextStyle(
                          color: AppTheme.neutral900,
                          fontSize: 15,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      SizedBox(width: 6),
                      Icon(PhosphorIconsFill.sealCheck, size: 14, color: AppTheme.primaryColor),
                    ],
                  ),
                  Row(
                    children: [
                      Container(
                        width: 6,
                        height: 6,
                        decoration: const BoxDecoration(
                          shape: BoxShape.circle,
                          color: AppTheme.successColor,
                        ),
                      ),
                      const SizedBox(width: 4),
                      const Text(
                        'RAG On-Premises • Sẵn sàng',
                        style: TextStyle(
                          fontSize: 10,
                          color: AppTheme.neutral500,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
        actions: [
          IconButton(
            tooltip: 'Xóa hội thoại',
            icon: Icon(PhosphorIcons.trash(), color: AppTheme.neutral600, size: 20),
            onPressed: () => _showClearConfirmation(context),
          ),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: [
            // Active Equipment Context Banner (if set)
            if (assetContext != null) _buildAssetContextBanner(assetContext, provider),

            // Chat Message List
            Expanded(
              child: ListView.builder(
                controller: _scrollController,
                padding: const EdgeInsets.only(top: 10, bottom: 10),
                itemCount: messages.length,
                itemBuilder: (context, index) {
                  return ChatBubble(message: messages[index]);
                },
              ),
            ),

            // Quick Prompt Suggestion Chips
            if (!isGenerating) _buildSuggestionChips(provider),

            // Input Bar
            _buildInputBar(isGenerating),
          ],
        ),
      ),
    );
  }

  Widget _buildAssetContextBanner(
    Map<String, dynamic> assetContext,
    AssistantProvider provider,
  ) {
    final assetName = assetContext['name'] ?? assetContext['assetName'] ?? 'Thiết bị';
    final assetModel = assetContext['model'] ?? assetContext['serialNumber'] ?? '';

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
      decoration: const BoxDecoration(
        color: Color(0xFFEFF6FF),
        border: Border(bottom: BorderSide(color: Color(0xFFDBEAFE))),
      ),
      child: Row(
        children: [
          const Icon(PhosphorIconsRegular.wrench, size: 16, color: Color(0xFF2563EB)),
          const SizedBox(width: 8),
          Expanded(
            child: RichText(
              text: TextSpan(
                style: const TextStyle(fontSize: 11, color: Color(0xFF1E40AF)),
                children: [
                  const TextSpan(text: 'Ngữ cảnh thiết bị: '),
                  TextSpan(
                    text: '$assetName ${assetModel.isNotEmpty ? "($assetModel)" : ""}',
                    style: const TextStyle(fontWeight: FontWeight.bold),
                  ),
                ],
              ),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          ),
          InkWell(
            onTap: () => provider.clearAssetContext(),
            borderRadius: BorderRadius.circular(12),
            child: const Padding(
              padding: EdgeInsets.all(4.0),
              child: Icon(PhosphorIconsRegular.x, size: 14, color: Color(0xFF3B82F6)),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSuggestionChips(AssistantProvider provider) {
    final suggestions = provider.quickSuggestions;

    return Container(
      height: 38,
      margin: const EdgeInsets.only(bottom: 6),
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 12),
        itemCount: suggestions.length,
        separatorBuilder: (_, __) => const SizedBox(width: 8),
        itemBuilder: (context, index) {
          final prompt = suggestions[index];
          return ActionChip(
            backgroundColor: Colors.white,
            side: const BorderSide(color: Color(0xFFE2E8F0)),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 0),
            avatar: Icon(
              PhosphorIcons.sparkle(PhosphorIconsStyle.fill),
              size: 12,
              color: AppTheme.primaryColor,
            ),
            label: Text(
              prompt,
              style: const TextStyle(
                fontSize: 11,
                color: AppTheme.neutral700,
                fontWeight: FontWeight.w600,
              ),
            ),
            onPressed: () => _handleSend(prompt),
          );
        },
      ),
    );
  }

  Widget _buildInputBar(bool isGenerating) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: const BoxDecoration(
        color: Colors.white,
        border: Border(top: BorderSide(color: AppTheme.neutral200)),
      ),
      child: Row(
        children: [
          Expanded(
            child: Container(
              decoration: BoxDecoration(
                color: const Color(0xFFF8FAFC),
                borderRadius: BorderRadius.circular(24),
                border: Border.all(color: const Color(0xFFE2E8F0)),
              ),
              child: Row(
                children: [
                  const SizedBox(width: 14),
                  Expanded(
                    child: TextField(
                      controller: _textController,
                      focusNode: _focusNode,
                      textInputAction: TextInputAction.send,
                      onSubmitted: (_) => _handleSend(),
                      onChanged: (_) => setState(() {}),
                      minLines: 1,
                      maxLines: 4,
                      style: const TextStyle(fontSize: 14, color: AppTheme.neutral900),
                      decoration: const InputDecoration(
                        hintText: 'Hỏi mã lỗi, an toàn, sơ đồ máy...',
                        hintStyle: TextStyle(fontSize: 13, color: AppTheme.neutral400),
                        border: InputBorder.none,
                        isDense: true,
                        contentPadding: EdgeInsets.symmetric(vertical: 10),
                      ),
                    ),
                  ),
                  if (_textController.text.isNotEmpty)
                    IconButton(
                      icon: const Icon(PhosphorIconsRegular.xCircle, size: 18, color: AppTheme.neutral400),
                      onPressed: () {
                        setState(() {
                          _textController.clear();
                        });
                      },
                    ),
                ],
              ),
            ),
          ),
          const SizedBox(width: 8),
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: isGenerating ? AppTheme.neutral300 : AppTheme.primaryColor,
              boxShadow: isGenerating
                  ? null
                  : [
                      BoxShadow(
                        color: AppTheme.primaryColor.withValues(alpha: 0.3),
                        blurRadius: 8,
                        offset: const Offset(0, 3),
                      ),
                    ],
            ),
            child: Material(
              color: Colors.transparent,
              child: InkWell(
                customBorder: const CircleBorder(),
                onTap: isGenerating ? null : () => _handleSend(),
                child: Center(
                  child: isGenerating
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                        )
                      : const Icon(
                          PhosphorIconsFill.paperPlaneRight,
                          color: Colors.white,
                          size: 20,
                        ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

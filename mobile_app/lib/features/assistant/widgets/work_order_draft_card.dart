import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';
import 'package:provider/provider.dart';
import '../../../core/theme/app_theme.dart';
import '../models/assistant_message.dart';
import '../providers/assistant_provider.dart';

class WorkOrderDraftCard extends StatefulWidget {
  final AssistantMessage message;

  const WorkOrderDraftCard({
    super.key,
    required this.message,
  });

  @override
  State<WorkOrderDraftCard> createState() => _WorkOrderDraftCardState();
}

class _WorkOrderDraftCardState extends State<WorkOrderDraftCard> {
  bool _isCreating = false;

  Future<void> _handleCreateWorkOrder() async {
    if (_isCreating || widget.message.createdWorkOrderId != null) return;
    setState(() => _isCreating = true);
    final provider = context.read<AssistantProvider>();
    final result = await provider.createWorkOrderFromDraft(widget.message);
    if (!mounted) return;
    setState(() => _isCreating = false);

    if (result != null) {
      final code = result['code'] ?? 'WO-DRAFT';
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Đã tạo bản thảo Phiếu Bảo Trì ($code) ở trạng thái CREATED.'),
          backgroundColor: AppTheme.successColor,
          duration: const Duration(seconds: 4),
        ),
      );
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Không thể tạo phiếu bảo trì. Vui lòng kiểm tra lại thiết bị.'),
          backgroundColor: AppTheme.dangerColor,
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final draft = widget.message.actionableWorkOrderDraft;
    if (draft == null) return const SizedBox.shrink();

    final isAlreadyCreated = widget.message.createdWorkOrderId != null;
    final createdCode = widget.message.createdWorkOrderCode ?? 'WO-DRAFT';

    return Container(
      margin: const EdgeInsets.only(top: 10),
      decoration: BoxDecoration(
        color: const Color(0xFFF0FDF4),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(
          color: isAlreadyCreated ? AppTheme.successColor : const Color(0xFF86EFAC),
          width: 1.5,
        ),
        boxShadow: const [
          BoxShadow(
            color: Color(0x0A000000),
            blurRadius: 8,
            offset: Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Header
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: BoxDecoration(
              color: isAlreadyCreated ? const Color(0xFFDCFCE7) : const Color(0xFFDCFCE7),
              borderRadius: const BorderRadius.vertical(top: Radius.circular(12)),
            ),
            child: Row(
              children: [
                Icon(
                  PhosphorIcons.wrench(PhosphorIconsStyle.fill),
                  size: 16,
                  color: const Color(0xFF166534),
                ),
                const SizedBox(width: 8),
                const Expanded(
                  child: Text(
                    'ĐỀ XUẤT PHIẾU BẢO TRÌ (WORK ORDER DRAFT)',
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w800,
                      color: Color(0xFF166534),
                      letterSpacing: 0.3,
                    ),
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(4),
                    border: Border.all(color: const Color(0xFF86EFAC)),
                  ),
                  child: const Text(
                    'CHƯA TRỪ KHO',
                    style: TextStyle(
                      fontSize: 9,
                      fontWeight: FontWeight.w900,
                      color: Color(0xFF166534),
                    ),
                  ),
                ),
              ],
            ),
          ),

          Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Title
                Text(
                  draft.suggestedTitle,
                  style: const TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.bold,
                    color: AppTheme.neutral900,
                  ),
                ),
                const SizedBox(height: 6),

                // Meta row: Status CREATED + Priority + Fault code
                Wrap(
                  spacing: 6,
                  runSpacing: 4,
                  children: [
                    _buildMetaTag('TRẠNG THÁI: CREATED', const Color(0xFF0284C7), const Color(0xFFE0F2FE)),
                    _buildMetaTag('ƯU TIÊN: ${draft.priority}', AppTheme.dangerColor, const Color(0xFFFEE2E2)),
                    _buildMetaTag('MÃ LỖI: ${draft.faultCode}', AppTheme.neutral600, const Color(0xFFF1F5F9)),
                  ],
                ),
                const SizedBox(height: 10),

                // Guarantee Notice
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: const Color(0xFFE2E8F0)),
                  ),
                  child: const Row(
                    children: [
                      Icon(PhosphorIconsRegular.shieldCheck, size: 14, color: Color(0xFF166534)),
                      SizedBox(width: 6),
                      Expanded(
                        child: Text(
                          'Bản thảo chỉ lưu nháp (CREATED), không tự ý phát hành và không trừ vật tư kho.',
                          style: TextStyle(fontSize: 10, color: Color(0xFF15803D), fontWeight: FontWeight.w500),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 12),

                // Action Buttons
                if (isAlreadyCreated) ...[
                  Row(
                    children: [
                      Expanded(
                        child: Container(
                          padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 12),
                          decoration: BoxDecoration(
                            color: const Color(0xFFDCFCE7),
                            borderRadius: BorderRadius.circular(10),
                            border: Border.all(color: AppTheme.successColor),
                          ),
                          child: Row(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              const Icon(PhosphorIconsRegular.checkCircle, color: AppTheme.successColor, size: 18),
                              const SizedBox(width: 6),
                              Text(
                                'Đã tạo: $createdCode',
                                style: const TextStyle(
                                  color: Color(0xFF14532D),
                                  fontWeight: FontWeight.bold,
                                  fontSize: 12,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      ElevatedButton.icon(
                        style: ElevatedButton.styleFrom(
                          backgroundColor: AppTheme.primaryColor,
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                        ),
                        onPressed: () {
                          final id = widget.message.createdWorkOrderId!;
                          context.push('/work-order-detail/$id', extra: createdCode);
                        },
                        icon: const Icon(PhosphorIconsRegular.arrowSquareOut, size: 16),
                        label: const Text('Xem phiếu', style: TextStyle(fontSize: 12)),
                      ),
                    ],
                  ),
                ] else ...[
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton.icon(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFF0F766E),
                        foregroundColor: Colors.white,
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                        padding: const EdgeInsets.symmetric(vertical: 11),
                      ),
                      onPressed: _isCreating ? null : _handleCreateWorkOrder,
                      icon: _isCreating
                          ? const SizedBox(
                              width: 16,
                              height: 16,
                              child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                            )
                          : const Icon(PhosphorIconsRegular.plusCircle, size: 18),
                      label: Text(
                        _isCreating ? 'Đang tạo bản thảo...' : 'Tạo phiếu sửa chữa ngay',
                        style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                      ),
                    ),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildMetaTag(String label, Color textColor, Color bgColor) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(
        label,
        style: TextStyle(
          fontSize: 10,
          fontWeight: FontWeight.w800,
          color: textColor,
          letterSpacing: 0.2,
        ),
      ),
    );
  }
}

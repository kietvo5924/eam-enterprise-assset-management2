import 'package:flutter/material.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';
import '../models/assistant_message.dart';

class DiagramAnchorCard extends StatelessWidget {
  final List<DiagramAnchor> anchors;

  const DiagramAnchorCard({
    super.key,
    required this.anchors,
  });

  @override
  Widget build(BuildContext context) {
    if (anchors.isEmpty) return const SizedBox.shrink();

    return Container(
      margin: const EdgeInsets.only(top: 10),
      decoration: BoxDecoration(
        color: const Color(0xFFEFF6FF),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFFBFDBFE), width: 1.2),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: const BoxDecoration(
              color: Color(0xFFDBEAFE),
              borderRadius: BorderRadius.vertical(top: Radius.circular(12)),
            ),
            child: Row(
              children: [
                Icon(
                  PhosphorIcons.blueprint(PhosphorIconsStyle.fill),
                  size: 16,
                  color: const Color(0xFF1E40AF),
                ),
                const SizedBox(width: 8),
                const Text(
                  'BẢN VẼ SƠ ĐỒ KỸ THUẬT (DIAGRAM ANCHORS)',
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w800,
                    color: Color(0xFF1E40AF),
                    letterSpacing: 0.3,
                  ),
                ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(10),
            child: Column(
              children: anchors.map((anchor) => _buildAnchorTile(context, anchor)).toList(),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildAnchorTile(BuildContext context, DiagramAnchor anchor) {
    final fig = anchor.figureId ?? 'Bản vẽ';
    final page = anchor.pageNumber != null ? 'Trang ${anchor.pageNumber}' : '';
    final caption = anchor.caption ?? 'Sơ đồ cụm chi tiết máy';

    return Container(
      margin: const EdgeInsets.only(bottom: 6),
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: const Color(0xFFE2E8F0)),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(6),
            decoration: BoxDecoration(
              color: const Color(0xFFEFF6FF),
              borderRadius: BorderRadius.circular(6),
            ),
            child: const Icon(PhosphorIconsRegular.image, size: 16, color: Color(0xFF2563EB)),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '$fig ${page.isNotEmpty ? "($page)" : ""}',
                  style: const TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.bold,
                    color: Color(0xFF1E293B),
                  ),
                ),
                Text(
                  caption,
                  style: const TextStyle(
                    fontSize: 11,
                    color: Color(0xFF64748B),
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

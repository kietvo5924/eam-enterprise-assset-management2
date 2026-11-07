import 'package:flutter/material.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';
import '../models/assistant_message.dart';

class SemanticRelevanceBadge extends StatelessWidget {
  final SemanticRelevance relevance;

  const SemanticRelevanceBadge({
    super.key,
    required this.relevance,
  });

  @override
  Widget build(BuildContext context) {
    final percent = (relevance.score * 100).clamp(0, 100).round();

    Color bgColor;
    Color textColor;
    Color borderColor;
    IconData iconData;
    String label;

    if (relevance.isEmergency) {
      bgColor = const Color(0xFFFEE2E2);
      textColor = const Color(0xFFDC2626);
      borderColor = const Color(0xFFFCA5A5);
      iconData = PhosphorIcons.warningOctagon(PhosphorIconsStyle.fill);
      label = 'KHẨN CẤP: Giao thức an toàn sinh mạng';
    } else if (relevance.isHighConfidence) {
      bgColor = const Color(0xFFECFDF5);
      textColor = const Color(0xFF059669);
      borderColor = const Color(0xFFA7F3D0);
      iconData = PhosphorIcons.sealCheck(PhosphorIconsStyle.fill);
      label = 'Độ tin cậy cao ($percent% khớp ngữ nghĩa)';
    } else if (relevance.isMediumConfidence) {
      bgColor = const Color(0xFFFFFBEB);
      textColor = const Color(0xFFD97706);
      borderColor = const Color(0xFFFDE68A);
      iconData = PhosphorIcons.warning(PhosphorIconsStyle.fill);
      label = 'Độ tin cậy trung bình ($percent% - Cần đối chiếu)';
    } else {
      bgColor = const Color(0xFFF1F5F9);
      textColor = const Color(0xFF64748B);
      borderColor = const Color(0xFFCBD5E1);
      iconData = PhosphorIcons.info(PhosphorIconsStyle.fill);
      label = 'Độ tin cậy thấp ($percent% - Ngưỡng an toàn)';
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: borderColor, width: 1),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(iconData, size: 14, color: textColor),
          const SizedBox(width: 6),
          Flexible(
            child: Text(
              label,
              style: TextStyle(
                color: textColor,
                fontSize: 11,
                fontWeight: FontWeight.w700,
              ),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          ),
        ],
      ),
    );
  }
}

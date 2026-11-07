import 'package:flutter/material.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';
import '../../../core/theme/app_theme.dart';

class OemTacitContentCard extends StatelessWidget {
  final String content;

  const OemTacitContentCard({
    super.key,
    required this.content,
  });

  @override
  Widget build(BuildContext context) {
    // Check if content has dual-stream sections or system guide
    final hasOemSection = content.contains('HƯỚNG DẪN CHUẨN TỪ HÃNG') || content.contains('OEM MANUAL');
    final hasTacitSection = content.contains('MẸO THỰC TẾ TẠI') || content.contains('TACIT');
    final hasSystemGuide = content.contains('HƯỚNG DẪN TÍNH NĂNG HỆ THỐNG');

    if (hasOemSection || hasTacitSection) {
      return _buildDualStreamView();
    } else if (hasSystemGuide) {
      return _buildSystemGuideView();
    } else {
      return _buildGeneralFormattedView(content);
    }
  }

  Widget _buildDualStreamView() {
    String oemText = '';
    String tacitText = '';

    // Split text into OEM and Tacit
    if (content.contains('### 2.')) {
      final parts = content.split('### 2.');
      oemText = parts[0].replaceAll('### 1.', '').trim();
      tacitText = parts[1].trim();
    } else if (content.contains('MẸO THỰC TẾ TẠI')) {
      final splitIndex = content.indexOf('MẸO THỰC TẾ TẠI');
      oemText = content.substring(0, splitIndex).trim();
      tacitText = content.substring(splitIndex).trim();
    } else {
      oemText = content;
    }

    // Clean up header lines
    oemText = oemText.replaceFirst(RegExp(r'^[#\s\d\.📖]*(HƯỚNG DẪN CHUẨN TỪ HÃNG \(OEM MANUAL\)|OEM MANUAL)[:\s]*', caseSensitive: false), '').trim();
    tacitText = tacitText.replaceFirst(RegExp(r'^[#\s\d\.💡]*(MẸO THỰC TẾ TẠI NHÀ MÁY|MẸO THỰC TẾ TẠI XƯỞNG|TACIT KNOWLEDGE)[^:\n]*[:\s]*', caseSensitive: false), '').trim();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        // 1. OEM Manual Card
        if (oemText.isNotEmpty) ...[
          Container(
            decoration: BoxDecoration(
              color: const Color(0xFFF8FAFC),
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: const Color(0xFFCBD5E1), width: 1.2),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  decoration: const BoxDecoration(
                    color: Color(0xFFE2E8F0),
                    borderRadius: BorderRadius.vertical(top: Radius.circular(12)),
                  ),
                  child: Row(
                    children: [
                      Icon(PhosphorIcons.bookOpen(PhosphorIconsStyle.fill), size: 16, color: const Color(0xFF0F172A)),
                      const SizedBox(width: 8),
                      const Text(
                        '1. HƯỚNG DẪN CHUẨN TỪ HÃNG (OEM MANUAL)',
                        style: TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.w800,
                          color: Color(0xFF0F172A),
                          letterSpacing: 0.3,
                        ),
                      ),
                    ],
                  ),
                ),
                Padding(
                  padding: const EdgeInsets.all(12),
                  child: _buildRichText(oemText),
                ),
              ],
            ),
          ),
          const SizedBox(height: 10),
        ],

        // 2. Tacit Knowledge Card
        if (tacitText.isNotEmpty) ...[
          Container(
            decoration: BoxDecoration(
              color: const Color(0xFFFFFBEB),
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: const Color(0xFFFDE68A), width: 1.2),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  decoration: const BoxDecoration(
                    color: Color(0xFFFEF3C7),
                    borderRadius: BorderRadius.vertical(top: Radius.circular(12)),
                  ),
                  child: Row(
                    children: [
                      Icon(PhosphorIcons.lightbulb(PhosphorIconsStyle.fill), size: 16, color: const Color(0xFFB45309)),
                      const SizedBox(width: 8),
                      const Expanded(
                        child: Text(
                          '2. MẸO THỰC TẾ TẠI NHÀ MÁY (KẾ THỪA WORK ORDER)',
                          style: TextStyle(
                            fontSize: 11,
                            fontWeight: FontWeight.w800,
                            color: Color(0xFF92400E),
                            letterSpacing: 0.3,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                Padding(
                  padding: const EdgeInsets.all(12),
                  child: _buildRichText(tacitText, baseColor: const Color(0xFF78350F)),
                ),
              ],
            ),
          ),
        ],
      ],
    );
  }

  Widget _buildSystemGuideView() {
    String cleanContent = content.replaceAll(RegExp(r'###\s*ℹ️?\s*HƯỚNG DẪN TÍNH NĂNG HỆ THỐNG EAM:?'), '').trim();

    return Container(
      decoration: BoxDecoration(
        color: const Color(0xFFF0FDF4),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFFBBF7D0), width: 1.2),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: const BoxDecoration(
              color: Color(0xFFDCFCE7),
              borderRadius: BorderRadius.vertical(top: Radius.circular(12)),
            ),
            child: Row(
              children: [
                Icon(PhosphorIcons.appWindow(PhosphorIconsStyle.fill), size: 16, color: const Color(0xFF166534)),
                const SizedBox(width: 8),
                const Text(
                  'HƯỚNG DẪN TÍNH NĂNG HỆ THỐNG EAM',
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w800,
                    color: Color(0xFF166534),
                    letterSpacing: 0.3,
                  ),
                ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(12),
            child: _buildRichText(cleanContent, baseColor: const Color(0xFF14532D)),
          ),
        ],
      ),
    );
  }

  Widget _buildGeneralFormattedView(String rawText) {
    return _buildRichText(rawText);
  }

  Widget _buildRichText(String text, {Color baseColor = AppTheme.neutral800}) {
    final lines = text.split('\n');
    final widgets = <Widget>[];

    for (var line in lines) {
      final trimmed = line.trim();
      if (trimmed.isEmpty) {
        widgets.add(const SizedBox(height: 6));
        continue;
      }

      // Check for safety prohibition words
      final isSafetyAlert = trimmed.toUpperCase().contains('CẤM') ||
          trimmed.toUpperCase().contains('KHÔNG ĐƯỢC') ||
          trimmed.toUpperCase().contains('TUYỆT ĐỐI') ||
          trimmed.toUpperCase().contains('DO NOT') ||
          trimmed.toUpperCase().contains('NEVER');

      if (isSafetyAlert) {
        widgets.add(
          Container(
            margin: const EdgeInsets.symmetric(vertical: 4),
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
            decoration: BoxDecoration(
              color: const Color(0xFFFEE2E2),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: const Color(0xFFFCA5A5)),
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Icon(PhosphorIconsRegular.warning, size: 16, color: Color(0xFFDC2626)),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    trimmed,
                    style: const TextStyle(
                      color: Color(0xFF991B1B),
                      fontSize: 13,
                      fontWeight: FontWeight.bold,
                      height: 1.4,
                    ),
                  ),
                ),
              ],
            ),
          ),
        );
        continue;
      }

      // Bullet points or numbered items
      if (trimmed.startsWith('•') || trimmed.startsWith('-') || RegExp(r'^\d+\.').hasMatch(trimmed)) {
        widgets.add(
          Padding(
            padding: const EdgeInsets.only(bottom: 4),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  trimmed.startsWith('•') || trimmed.startsWith('-') ? '• ' : '',
                  style: TextStyle(color: baseColor, fontWeight: FontWeight.bold, fontSize: 13),
                ),
                Expanded(
                  child: Text(
                    trimmed.startsWith('•') || trimmed.startsWith('-') ? trimmed.substring(1).trim() : trimmed,
                    style: TextStyle(
                      color: baseColor,
                      fontSize: 13,
                      height: 1.4,
                    ),
                  ),
                ),
              ],
            ),
          ),
        );
      } else {
        widgets.add(
          Padding(
            padding: const EdgeInsets.only(bottom: 4),
            child: Text(
              trimmed,
              style: TextStyle(
                color: baseColor,
                fontSize: 13,
                height: 1.45,
              ),
            ),
          ),
        );
      }
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: widgets,
    );
  }
}

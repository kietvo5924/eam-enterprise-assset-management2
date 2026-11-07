import 'package:flutter/material.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';
import '../../../core/theme/app_theme.dart';
import '../models/assistant_message.dart';

class LifeSafetyBanner extends StatelessWidget {
  final AssistantMessage message;

  const LifeSafetyBanner({
    super.key,
    required this.message,
  });

  @override
  Widget build(BuildContext context) {
    final hazard = message.hazardType ?? 'EMERGENCY';
    final emergencyName = message.emergencyName ?? 'Sự Cố Nguy Cấp Hiện Trường';
    final actionSummary = message.actionSummary ?? 'NGỪNG THAO TÁC NGAY LẬP TỨC';

    IconData hazardIcon = PhosphorIcons.siren(PhosphorIconsStyle.fill);
    if (hazard.contains('ELECTRICAL') || hazard.contains('DIEN')) {
      hazardIcon = PhosphorIcons.lightning(PhosphorIconsStyle.fill);
    } else if (hazard.contains('GAS') || hazard.contains('TOXIC') || hazard.contains('KHI')) {
      hazardIcon = PhosphorIcons.biohazard(PhosphorIconsStyle.fill);
    } else if (hazard.contains('MECHANICAL') || hazard.contains('CRUSH') || hazard.contains('KET')) {
      hazardIcon = PhosphorIcons.handPalm(PhosphorIconsStyle.fill);
    } else if (hazard.contains('CHEMICAL') || hazard.contains('ACID') || hazard.contains('HOA_CHAT')) {
      hazardIcon = PhosphorIcons.flask(PhosphorIconsStyle.fill);
    } else if (hazard.contains('FIRE') || hazard.contains('CHAY')) {
      hazardIcon = PhosphorIcons.fire(PhosphorIconsStyle.fill);
    }

    return Container(
      margin: const EdgeInsets.symmetric(vertical: 8),
      decoration: BoxDecoration(
        color: const Color(0xFFFEF2F2),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.dangerColor, width: 2),
        boxShadow: [
          BoxShadow(
            color: AppTheme.dangerColor.withValues(alpha: 0.2),
            blurRadius: 16,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Top Red Header
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            decoration: const BoxDecoration(
              color: AppTheme.dangerColor,
              borderRadius: BorderRadius.vertical(top: Radius.circular(14)),
            ),
            child: Row(
              children: [
                Icon(hazardIcon, color: Colors.white, size: 22),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'CẢNH BÁO AN TOÀN SINH MẠNG KHẨN CẤP',
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 12,
                      fontWeight: FontWeight.w900,
                      letterSpacing: 0.5,
                    ),
                  ),
                ),
              ],
            ),
          ),

          Padding(
            padding: const EdgeInsets.all(14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Emergency Hazard Title
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      padding: const EdgeInsets.all(6),
                      decoration: BoxDecoration(
                        color: const Color(0xFFFEE2E2),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Icon(
                        PhosphorIcons.warningCircle(PhosphorIconsStyle.bold),
                        color: AppTheme.dangerColor,
                        size: 20,
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            emergencyName,
                            style: const TextStyle(
                              fontSize: 14,
                              fontWeight: FontWeight.w800,
                              color: Color(0xFF991B1B),
                            ),
                          ),
                          const SizedBox(height: 2),
                          const Text(
                            'Phát hiện tình huống đe dọa tính mạng con người. RAG tự động ngắt để bảo vệ kỹ thuật viên.',
                            style: TextStyle(
                              fontSize: 11,
                              color: Color(0xFF7F1D1D),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),

                // High Contrast Action Summary Box
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                  decoration: BoxDecoration(
                    color: const Color(0xFF7F1D1D),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Row(
                    children: [
                      const Icon(
                        PhosphorIconsRegular.shieldWarning,
                        color: Colors.yellowAccent,
                        size: 20,
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          actionSummary,
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 12,
                            fontWeight: FontWeight.w900,
                            letterSpacing: 0.3,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 12),

                // Step-by-step instructions
                Text(
                  message.content,
                  style: const TextStyle(
                    fontSize: 13,
                    height: 1.5,
                    color: Color(0xFF450A0A),
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

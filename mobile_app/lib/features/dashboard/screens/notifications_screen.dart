import 'package:flutter/material.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';
import '../../../core/theme/app_theme.dart';

class NotificationsScreen extends StatelessWidget {
  const NotificationsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.neutral50,
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        centerTitle: true,
        title: const Text(
          'Thông báo',
          style: TextStyle(
            color: AppTheme.neutral900,
            fontWeight: FontWeight.bold,
            fontSize: 18,
          ),
        ),
        iconTheme: const IconThemeData(color: AppTheme.neutral900),
        actions: [
          TextButton(
            onPressed: () {},
            child: const Text(
              'Đánh dấu đã đọc',
              style: TextStyle(
                color: AppTheme.primaryColor,
                fontWeight: FontWeight.bold,
                fontSize: 13,
              ),
            ),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 20),
        children: [
          _buildDateHeader('Hôm nay'),
          _buildNotificationItem(
            context,
            icon: PhosphorIcons.wrench(PhosphorIconsStyle.fill),
            iconColor: AppTheme.primaryColor,
            iconBgColor: AppTheme.primaryColor.withValues(alpha: 0.15),
            title: 'Công việc mới được giao',
            description: 'Bạn vừa được phân công Work Order WO-5892: Kiểm tra định kỳ máy bơm P-102.',
            time: '10 phút trước',
            isUnread: true,
          ),
          _buildNotificationItem(
            context,
            icon: PhosphorIcons.checkCircle(PhosphorIconsStyle.fill),
            iconColor: AppTheme.successColor,
            iconBgColor: AppTheme.successColor.withValues(alpha: 0.15),
            title: 'Công việc hoàn tất',
            description: 'Quản lý đã duyệt Work Order WO-5810 của bạn. Xin cảm ơn!',
            time: '2 giờ trước',
            isUnread: true,
          ),
          const SizedBox(height: 16),
          _buildDateHeader('Hôm qua'),
          _buildNotificationItem(
            context,
            icon: PhosphorIcons.warning(PhosphorIconsStyle.fill),
            iconColor: AppTheme.warningColor,
            iconBgColor: AppTheme.warningColor.withValues(alpha: 0.15),
            title: 'Thiết bị báo lỗi',
            description: 'Hệ thống ghi nhận Máy nén khí C-201 có nhiệt độ cao bất thường. Cần kiểm tra ngay.',
            time: '09:30',
            isUnread: false,
          ),
          _buildNotificationItem(
            context,
            icon: PhosphorIcons.chatTeardropText(PhosphorIconsStyle.fill),
            iconColor: AppTheme.infoColor,
            iconBgColor: AppTheme.infoColor.withValues(alpha: 0.15),
            title: 'Bình luận mới',
            description: 'Nguyễn Văn A đã thêm bình luận vào Work Order WO-5799: "Đã thay thế linh kiện".',
            time: '14:45',
            isUnread: false,
          ),
          const SizedBox(height: 16),
          _buildDateHeader('Tuần trước'),
          _buildNotificationItem(
            context,
            icon: PhosphorIcons.calendar(PhosphorIconsStyle.fill),
            iconColor: const Color(0xFF8b5cf6),
            iconBgColor: const Color(0xFF8b5cf6).withValues(alpha: 0.15),
            title: 'Lịch bảo trì sắp tới',
            description: 'Bạn có 3 công việc bảo trì dự phòng dự kiến vào tuần sau.',
            time: '05/06/2026',
            isUnread: false,
          ),
        ],
      ),
    );
  }

  Widget _buildDateHeader(String title) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12, left: 4),
      child: Text(
        title,
        style: const TextStyle(
          fontSize: 15,
          fontWeight: FontWeight.w800,
          color: AppTheme.neutral900,
        ),
      ),
    );
  }

  Widget _buildNotificationItem(
    BuildContext context, {
    required IconData icon,
    required Color iconColor,
    required Color iconBgColor,
    required String title,
    required String description,
    required String time,
    required bool isUnread,
  }) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: isUnread ? Colors.white : const Color(0xFFF8FAFC),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: isUnread ? AppTheme.primaryColor.withValues(alpha: 0.3) : Colors.transparent,
          width: 1.5,
        ),
        boxShadow: isUnread
            ? [
                BoxShadow(
                  color: AppTheme.primaryColor.withValues(alpha: 0.08),
                  blurRadius: 16,
                  offset: const Offset(0, 8),
                )
              ]
            : [],
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 48,
            height: 48,
            decoration: BoxDecoration(
              color: iconBgColor,
              shape: BoxShape.circle,
            ),
            child: Icon(icon, color: iconColor, size: 24),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Expanded(
                      child: Text(
                        title,
                        style: TextStyle(
                          fontSize: 15,
                          fontWeight: isUnread ? FontWeight.w800 : FontWeight.bold,
                          color: AppTheme.neutral900,
                        ),
                      ),
                    ),
                    if (isUnread)
                      Container(
                        width: 8,
                        height: 8,
                        decoration: const BoxDecoration(
                          color: AppTheme.primaryColor,
                          shape: BoxShape.circle,
                        ),
                      ),
                  ],
                ),
                const SizedBox(height: 6),
                Text(
                  description,
                  style: TextStyle(
                    fontSize: 13,
                    color: isUnread ? AppTheme.neutral700 : AppTheme.neutral500,
                    height: 1.4,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  time,
                  style: const TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.neutral400,
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

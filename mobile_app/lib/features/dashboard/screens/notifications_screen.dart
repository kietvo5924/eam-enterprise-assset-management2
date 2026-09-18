import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';
import '../../../core/theme/app_theme.dart';
import '../models/notification_model.dart';
import '../services/notification_service.dart';

class NotificationsScreen extends StatefulWidget {
  const NotificationsScreen({super.key});

  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen> {
  final NotificationService _notificationService = NotificationService();
  
  String _selectedTab = 'all'; // 'all', 'unread', 'actionable'
  bool _isLoading = true;
  List<NotificationItem> _notifications = [];
  int _unreadCount = 0;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _loadNotifications();
    // Register device token in background
    _notificationService.registerDeviceToken();
  }

  Future<void> _loadNotifications() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    final result = await _notificationService.getNotifications(tab: _selectedTab);
    
    if (mounted) {
      setState(() {
        _isLoading = false;
        if (result.containsKey('error') && (result['items'] as List).isEmpty) {
          _errorMessage = 'Không thể kết nối đến máy chủ. Vui lòng kiểm tra lại.';
        } else {
          _notifications = result['items'] as List<NotificationItem>;
          _unreadCount = result['unreadCount'] as int? ?? 0;
        }
      });
    }
  }

  Future<void> _handleMarkAllAsRead() async {
    final success = await _notificationService.markAllAsRead();
    if (success && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Đã đánh dấu tất cả thông báo là đã đọc'),
          backgroundColor: AppTheme.successColor,
          behavior: SnackBarBehavior.floating,
        ),
      );
      _loadNotifications();
    }
  }

  Future<void> _handleItemTap(NotificationItem item) async {
    // If unread, mark read immediately
    if (!item.isRead) {
      await _notificationService.markAsRead(item.id);
      setState(() {
        final index = _notifications.indexWhere((n) => n.id == item.id);
        if (index != -1) {
          _notifications[index] = _notifications[index].copyWith(isRead: true);
          if (_unreadCount > 0) _unreadCount--;
        }
      });
    }

    if (!mounted) return;
    _showDetailBottomSheet(item);
  }

  Future<void> _handleResolveAction(NotificationItem item) async {
    final success = await _notificationService.resolveAction(item.id);
    if (success && mounted) {
      Navigator.of(context).pop(); // Close bottom sheet
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Xác nhận xử lý hành động thành công!'),
          backgroundColor: AppTheme.successColor,
          behavior: SnackBarBehavior.floating,
        ),
      );
      setState(() {
        final index = _notifications.indexWhere((n) => n.id == item.id);
        if (index != -1) {
          _notifications[index] = _notifications[index].copyWith(
            actionStatus: 'RESOLVED',
            actionResolvedAt: DateTime.now(),
          );
        }
      });
    } else if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Không thể xử lý hành động lúc này.'),
          backgroundColor: AppTheme.dangerColor,
          behavior: SnackBarBehavior.floating,
        ),
      );
    }
  }

  void _showDetailBottomSheet(NotificationItem item) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) {
        final severityConfig = _getSeverityConfig(item.severity);
        final actionConfig = _getActionConfig(item.actionStatus);

        return Container(
          decoration: const BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
          ),
          padding: EdgeInsets.only(
            top: 16,
            left: 20,
            right: 20,
            bottom: MediaQuery.of(ctx).padding.bottom + 20,
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Center(
                child: Container(
                  width: 40,
                  height: 4,
                  decoration: BoxDecoration(
                    color: AppTheme.neutral300,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),
              const SizedBox(height: 16),
              // Category & Severity row
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: AppTheme.neutral100,
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Text(
                      _getCategoryLabel(item.category),
                      style: const TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                        color: AppTheme.neutral700,
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: severityConfig.bgColor,
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Text(
                      severityConfig.label,
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.bold,
                        color: severityConfig.textColor,
                      ),
                    ),
                  ),
                  if (item.isActionable) ...[
                    const SizedBox(width: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      decoration: BoxDecoration(
                        color: actionConfig.bgColor,
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(color: actionConfig.borderColor),
                      ),
                      child: Text(
                        actionConfig.label,
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.bold,
                          color: actionConfig.textColor,
                        ),
                      ),
                    ),
                  ],
                ],
              ),
              const SizedBox(height: 14),
              // Title
              Text(
                item.title,
                style: const TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                  color: AppTheme.neutral900,
                  height: 1.3,
                ),
              ),
              const SizedBox(height: 8),
              // Timestamp
              Text(
                DateFormat('dd/MM/yyyy HH:mm').format(item.createdAt),
                style: const TextStyle(
                  fontSize: 13,
                  color: AppTheme.neutral500,
                ),
              ),
              const SizedBox(height: 16),
              // Message Box
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: const Color(0xFFF8FAFC),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: const Color(0xFFE2E8F0)),
                ),
                child: Text(
                  item.message,
                  style: const TextStyle(
                    fontSize: 14,
                    color: AppTheme.neutral800,
                    height: 1.5,
                  ),
                ),
              ),
              if (item.sender != null) ...[
                const SizedBox(height: 12),
                Row(
                  children: [
                    const Icon(PhosphorIconsRegular.userCircle, size: 16, color: AppTheme.neutral500),
                    const SizedBox(width: 6),
                    Text(
                      'Người gửi: ${item.sender!['name'] ?? 'Hệ thống'} (${item.sender!['role'] ?? 'SYSTEM'})',
                      style: const TextStyle(
                        fontSize: 12,
                        color: AppTheme.neutral600,
                      ),
                    ),
                  ],
                ),
              ],
              const SizedBox(height: 20),
              // Action Buttons
              if (item.isActionable && item.actionStatus == 'PENDING')
                Padding(
                  padding: const EdgeInsets.only(bottom: 10),
                  child: SizedBox(
                    width: double.infinity,
                    height: 48,
                    child: ElevatedButton.icon(
                      onPressed: () => _handleResolveAction(item),
                      icon: const Icon(PhosphorIconsBold.checkCircle, size: 20),
                      label: const Text(
                        'Xác nhận đã xử lý',
                        style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
                      ),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppTheme.successColor,
                        foregroundColor: Colors.white,
                        elevation: 0,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12),
                        ),
                      ),
                    ),
                  ),
                ),
              SizedBox(
                width: double.infinity,
                height: 46,
                child: OutlinedButton(
                  onPressed: () => Navigator.of(ctx).pop(),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: AppTheme.neutral700,
                    side: const BorderSide(color: AppTheme.neutral300),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                  ),
                  child: const Text('Đóng', style: TextStyle(fontWeight: FontWeight.w600)),
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.neutral50,
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        centerTitle: true,
        title: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text(
              'Thông báo',
              style: TextStyle(
                color: AppTheme.neutral900,
                fontWeight: FontWeight.bold,
                fontSize: 18,
              ),
            ),
            if (_unreadCount > 0) ...[
              const SizedBox(width: 8),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                  color: AppTheme.dangerColor,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  '$_unreadCount',
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 11,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ],
          ],
        ),
        iconTheme: const IconThemeData(color: AppTheme.neutral900),
        actions: [
          TextButton(
            onPressed: _handleMarkAllAsRead,
            child: const Text(
              'Đọc tất cả',
              style: TextStyle(
                color: AppTheme.primaryColor,
                fontWeight: FontWeight.bold,
                fontSize: 13,
              ),
            ),
          ),
        ],
      ),
      body: Column(
        children: [
          // Filter Tabs
          Container(
            color: Colors.white,
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
            child: Row(
              children: [
                _buildFilterTab('Tất cả', 'all'),
                const SizedBox(width: 8),
                _buildFilterTab('Chưa đọc', 'unread'),
                const SizedBox(width: 8),
                _buildFilterTab('Cần xử lý', 'actionable'),
              ],
            ),
          ),
          const Divider(height: 1, color: AppTheme.neutral200),

          // Main List
          Expanded(
            child: _isLoading
                ? const Center(
                    child: CircularProgressIndicator(
                      color: AppTheme.primaryColor,
                    ),
                  )
                : _errorMessage != null
                    ? Center(
                        child: Padding(
                          padding: const EdgeInsets.all(24.0),
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              const Icon(
                                PhosphorIconsRegular.cloudX,
                                size: 56,
                                color: AppTheme.neutral400,
                              ),
                              const SizedBox(height: 12),
                              Text(
                                _errorMessage!,
                                textAlign: TextAlign.center,
                                style: const TextStyle(
                                  color: AppTheme.neutral600,
                                  fontSize: 14,
                                ),
                              ),
                              const SizedBox(height: 16),
                              ElevatedButton(
                                onPressed: _loadNotifications,
                                style: ElevatedButton.styleFrom(
                                  backgroundColor: AppTheme.primaryColor,
                                ),
                                child: const Text('Thử lại'),
                              ),
                            ],
                          ),
                        ),
                      )
                    : _notifications.isEmpty
                        ? RefreshIndicator(
                            onRefresh: _loadNotifications,
                            color: AppTheme.primaryColor,
                            child: ListView(
                              physics: const AlwaysScrollableScrollPhysics(),
                              children: [
                                SizedBox(
                                  height: MediaQuery.of(context).size.height * 0.5,
                                  child: const Center(
                                    child: Column(
                                      mainAxisAlignment: MainAxisAlignment.center,
                                      children: [
                                        Icon(
                                          PhosphorIconsRegular.bellSlash,
                                          size: 56,
                                          color: AppTheme.neutral400,
                                        ),
                                        SizedBox(height: 12),
                                        Text(
                                          'Không có thông báo nào',
                                          style: TextStyle(
                                            color: AppTheme.neutral600,
                                            fontSize: 15,
                                            fontWeight: FontWeight.w600,
                                          ),
                                        ),
                                      ],
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          )
                        : RefreshIndicator(
                            onRefresh: _loadNotifications,
                            color: AppTheme.primaryColor,
                            child: ListView.builder(
                              physics: const AlwaysScrollableScrollPhysics(),
                              padding: const EdgeInsets.symmetric(
                                horizontal: 16,
                                vertical: 16,
                              ),
                              itemCount: _notifications.length,
                              itemBuilder: (context, index) {
                                final item = _notifications[index];
                                return _buildNotificationCard(item);
                              },
                            ),
                          ),
          ),
        ],
      ),
    );
  }

  Widget _buildFilterTab(String label, String tabKey) {
    final isSelected = _selectedTab == tabKey;
    return Expanded(
      child: GestureDetector(
        onTap: () {
          if (_selectedTab != tabKey) {
            setState(() {
              _selectedTab = tabKey;
            });
            _loadNotifications();
          }
        },
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 200),
          padding: const EdgeInsets.symmetric(vertical: 8),
          decoration: BoxDecoration(
            color: isSelected ? AppTheme.primaryColor : const Color(0xFFF1F5F9),
            borderRadius: BorderRadius.circular(10),
          ),
          child: Center(
            child: Text(
              label,
              style: TextStyle(
                fontSize: 13,
                fontWeight: isSelected ? FontWeight.bold : FontWeight.w600,
                color: isSelected ? Colors.white : AppTheme.neutral700,
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildNotificationCard(NotificationItem item) {
    final catConfig = _getCategoryIconConfig(item.category);
    final severityConfig = _getSeverityConfig(item.severity);
    final actionConfig = _getActionConfig(item.actionStatus);

    return GestureDetector(
      onTap: () => _handleItemTap(item),
      child: Container(
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: item.isRead ? Colors.white : const Color(0xFFF0FDF4).withValues(alpha: 0.7),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: item.isRead
                ? const Color(0xFFE2E8F0)
                : AppTheme.primaryColor.withValues(alpha: 0.35),
            width: item.isRead ? 1.0 : 1.5,
          ),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: item.isRead ? 0.03 : 0.06),
              blurRadius: 10,
              offset: const Offset(0, 4),
            ),
          ],
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Category Icon
            Container(
              width: 44,
              height: 44,
              decoration: BoxDecoration(
                color: catConfig.bgColor,
                shape: BoxShape.circle,
              ),
              child: Icon(
                catConfig.icon,
                color: catConfig.iconColor,
                size: 22,
              ),
            ),
            const SizedBox(width: 12),
            // Body
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Title + Unread dot
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(
                        child: Text(
                          item.title,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(
                            fontSize: 14,
                            fontWeight: item.isRead ? FontWeight.w600 : FontWeight.w800,
                            color: AppTheme.neutral900,
                            height: 1.3,
                          ),
                        ),
                      ),
                      if (!item.isRead) ...[
                        const SizedBox(width: 6),
                        Container(
                          width: 8,
                          height: 8,
                          margin: const EdgeInsets.only(top: 4),
                          decoration: const BoxDecoration(
                            color: AppTheme.primaryColor,
                            shape: BoxShape.circle,
                          ),
                        ),
                      ],
                    ],
                  ),
                  const SizedBox(height: 5),
                  // Short Message preview
                  Text(
                    item.message,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      fontSize: 12.5,
                      color: AppTheme.neutral600,
                      height: 1.35,
                    ),
                  ),
                  const SizedBox(height: 10),
                  // Bottom Row: Badges and Timestamp
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Wrap(
                        spacing: 6,
                        crossAxisAlignment: WrapCrossAlignment.center,
                        children: [
                          // Severity badge
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                            decoration: BoxDecoration(
                              color: severityConfig.bgColor,
                              borderRadius: BorderRadius.circular(6),
                            ),
                            child: Text(
                              severityConfig.label,
                              style: TextStyle(
                                fontSize: 10.5,
                                fontWeight: FontWeight.bold,
                                color: severityConfig.textColor,
                              ),
                            ),
                          ),
                          // Action badge
                          if (item.isActionable)
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                              decoration: BoxDecoration(
                                color: actionConfig.bgColor,
                                borderRadius: BorderRadius.circular(6),
                                border: Border.all(color: actionConfig.borderColor, width: 0.8),
                              ),
                              child: Text(
                                actionConfig.label,
                                style: TextStyle(
                                  fontSize: 10.5,
                                  fontWeight: FontWeight.bold,
                                  color: actionConfig.textColor,
                                ),
                              ),
                            ),
                        ],
                      ),
                      // Time
                      Text(
                        _formatTime(item.createdAt),
                        style: const TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.w500,
                          color: AppTheme.neutral400,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  String _formatTime(DateTime dt) {
    final now = DateTime.now();
    final diff = now.difference(dt);
    if (diff.inMinutes < 1) return 'Vừa xong';
    if (diff.inMinutes < 60) return '${diff.inMinutes} phút trước';
    if (diff.inHours < 24 && dt.day == now.day) return '${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';
    return DateFormat('dd/MM').format(dt);
  }

  String _getCategoryLabel(String category) {
    switch (category) {
      case 'WORK_ORDER':
        return 'Phiếu công việc';
      case 'ASSET_FAILURE':
        return 'Sự cố thiết bị';
      case 'PM_SCHEDULE':
        return 'Bảo trì định kỳ';
      case 'INVENTORY':
        return 'Kho & Vật tư';
      case 'SECURITY':
        return 'Bảo mật & An toàn';
      default:
        return 'Hệ thống';
    }
  }

  _IconConfig _getCategoryIconConfig(String category) {
    switch (category) {
      case 'WORK_ORDER':
        return _IconConfig(
          icon: PhosphorIconsFill.wrench,
          iconColor: const Color(0xFF0284c7),
          bgColor: const Color(0xFFE0F2FE),
        );
      case 'ASSET_FAILURE':
        return _IconConfig(
          icon: PhosphorIconsFill.warning,
          iconColor: const Color(0xFFDC2626),
          bgColor: const Color(0xFFFEE2E2),
        );
      case 'PM_SCHEDULE':
        return _IconConfig(
          icon: PhosphorIconsFill.calendar,
          iconColor: const Color(0xFF7C3AED),
          bgColor: const Color(0xFFEDE9FE),
        );
      case 'INVENTORY':
        return _IconConfig(
          icon: PhosphorIconsFill.package,
          iconColor: const Color(0xFFD97706),
          bgColor: const Color(0xFFFEF3C7),
        );
      default:
        return _IconConfig(
          icon: PhosphorIconsFill.bell,
          iconColor: AppTheme.primaryColor,
          bgColor: AppTheme.primaryColor.withValues(alpha: 0.15),
        );
    }
  }

  _BadgeConfig _getSeverityConfig(String severity) {
    switch (severity) {
      case 'CRITICAL':
        return _BadgeConfig(
          label: 'KHẨN CẤP',
          textColor: const Color(0xFFDC2626),
          bgColor: const Color(0xFFFEE2E2),
        );
      case 'HIGH':
        return _BadgeConfig(
          label: 'CẢNH BÁO',
          textColor: const Color(0xFFEA580C),
          bgColor: const Color(0xFFFFEDD5),
        );
      case 'MEDIUM':
        return _BadgeConfig(
          label: 'CẤP BÁCH',
          textColor: const Color(0xFFD97706),
          bgColor: const Color(0xFFFEF3C7),
        );
      default:
        return _BadgeConfig(
          label: 'THÔNG TIN',
          textColor: const Color(0xFF0284C7),
          bgColor: const Color(0xFFE0F2FE),
        );
    }
  }

  _BadgeConfig _getActionConfig(String status) {
    switch (status) {
      case 'PENDING':
        return _BadgeConfig(
          label: 'Chờ duyệt',
          textColor: const Color(0xFFB45309),
          bgColor: const Color(0xFFFEF3C7),
          borderColor: const Color(0xFFFDE68A),
        );
      case 'RESOLVED':
        return _BadgeConfig(
          label: 'Đã xử lý',
          textColor: const Color(0xFF15803D),
          bgColor: const Color(0xFFDCFCE7),
          borderColor: const Color(0xFFBBF7D0),
        );
      default:
        return _BadgeConfig(
          label: status,
          textColor: AppTheme.neutral600,
          bgColor: AppTheme.neutral100,
          borderColor: AppTheme.neutral300,
        );
    }
  }
}

class _IconConfig {
  final IconData icon;
  final Color iconColor;
  final Color bgColor;

  _IconConfig({
    required this.icon,
    required this.iconColor,
    required this.bgColor,
  });
}

class _BadgeConfig {
  final String label;
  final Color textColor;
  final Color bgColor;
  final Color borderColor;

  _BadgeConfig({
    required this.label,
    required this.textColor,
    required this.bgColor,
    this.borderColor = Colors.transparent,
  });
}

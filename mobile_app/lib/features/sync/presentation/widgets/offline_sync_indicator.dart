import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../../../core/network/network_service.dart';
import '../../../../core/database/app_database.dart';
import '../../../../core/providers/user_provider.dart';
import '../../services/sync_engine.dart';

class OfflineSyncIndicator extends StatelessWidget {
  const OfflineSyncIndicator({super.key});

  @override
  Widget build(BuildContext context) {
    final networkService = context.watch<NetworkService>();
    final userProvider = context.watch<UserProvider>();
    final tenantId = userProvider.tenantId;

    return StreamBuilder<List<SyncQueueEntity>>(
      stream: AppDatabase.instance.syncQueueDao.watchPendingSyncs(tenantId.isNotEmpty ? tenantId : null),
      builder: (context, snapshot) {
        final tasks = snapshot.data ?? [];
        final isOnline = networkService.isOnline;

        final conflictCount = tasks.where((t) => t.status == 'CONFLICT').length;
        final failedCount = tasks.where((t) => t.status == 'FAILED' && t.retryCount >= 3).length;
        final pendingCount = tasks.where((t) => t.status == 'PENDING' || t.status == 'IN_PROGRESS' || (t.status == 'FAILED' && t.retryCount < 3)).length;

        if (!isOnline) {
          final totalOffline = tasks.length;
          return _buildBanner(
            bgColor: Colors.red.shade700,
            text: totalOffline > 0
                ? 'Ngoại tuyến - Đang chờ đồng bộ $totalOffline mục'
                : 'Ngoại tuyến',
            icon: Icons.wifi_off,
          );
        }

        if (conflictCount > 0) {
          return _buildBanner(
            bgColor: Colors.purple.shade700,
            text: 'Xung đột đồng bộ $conflictCount mục - Dữ liệu máy chủ đã thay đổi',
            icon: Icons.warning_amber_rounded,
          );
        }

        if (failedCount > 0) {
          return _buildBanner(
            bgColor: Colors.red.shade600,
            text: 'Đồng bộ thất bại $failedCount mục - Nhấn để thử lại',
            icon: Icons.refresh,
            onTap: () {
              SyncEngine().retryFailedTasks();
            },
          );
        }

        if (pendingCount > 0) {
          return _buildBanner(
            bgColor: Colors.orange.shade700,
            text: 'Đang đồng bộ $pendingCount mục...',
            icon: Icons.sync,
          );
        }

        return const SizedBox.shrink();
      },
    );
  }

  Widget _buildBanner({
    required Color bgColor,
    required String text,
    required IconData icon,
    VoidCallback? onTap,
  }) {
    return SafeArea(
      bottom: false,
      child: Material(
        color: bgColor,
        child: InkWell(
          onTap: onTap,
          child: Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(vertical: 5.0, horizontal: 16.0),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(icon, color: Colors.white, size: 14),
                const SizedBox(width: 8),
                Flexible(
                  child: Text(
                    text,
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 12,
                      fontWeight: FontWeight.bold,
                    ),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

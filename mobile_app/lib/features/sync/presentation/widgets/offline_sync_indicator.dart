import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../../../core/network/network_service.dart';
import '../../../../core/database/app_database.dart';

class OfflineSyncIndicator extends StatelessWidget {
  const OfflineSyncIndicator({super.key});

  @override
  Widget build(BuildContext context) {
    final networkService = context.watch<NetworkService>();
    
    return StreamBuilder<List<SyncQueueEntity>>(
      stream: AppDatabase.instance.syncQueueDao.watchPendingSyncs(),
      builder: (context, snapshot) {
        final pendingSyncs = snapshot.data ?? [];
        final hasPending = pendingSyncs.isNotEmpty;
        final isOnline = networkService.isOnline;

        Color bgColor;
        String text;
        IconData icon;

        if (!isOnline) {
          bgColor = Colors.red.shade600;
          text = hasPending ? 'Offline - ${pendingSyncs.length} pending' : 'Offline';
          icon = Icons.wifi_off;
        } else if (hasPending) {
          bgColor = Colors.orange.shade600;
          text = 'Syncing ${pendingSyncs.length} items...';
          icon = Icons.sync;
        } else {
          return const SizedBox.shrink();
        }

        return SafeArea(
          bottom: false,
          child: Container(
            width: double.infinity,
            color: bgColor,
            padding: const EdgeInsets.symmetric(vertical: 4.0, horizontal: 16.0),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(icon, color: Colors.white, size: 14),
                const SizedBox(width: 8),
                Text(
                  text,
                  style: const TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.bold),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}

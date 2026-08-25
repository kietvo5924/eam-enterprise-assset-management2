import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'core/theme/app_theme.dart';
import 'core/providers/user_provider.dart';
import 'core/routes/app_router.dart';
import 'features/work_orders/providers/work_order_provider.dart';
import 'core/network/network_service.dart';
import 'features/sync/presentation/widgets/offline_sync_indicator.dart';

import 'features/sync/services/sync_engine.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  SyncEngine().init();
  
  runApp(
    MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => UserProvider()..loadUser()),
        ChangeNotifierProvider(create: (_) => WorkOrderProvider()),
        ChangeNotifierProvider.value(value: NetworkService()),
      ],
      child: const MyApp(),
    ),
  );
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'EAM Mobile',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.lightTheme,
      routerConfig: AppRouter.router,
      builder: (context, child) {
        return Material(
          type: MaterialType.transparency,
          child: Column(
            children: [
              const OfflineSyncIndicator(),
              Expanded(child: child ?? const SizedBox()),
            ],
          ),
        );
      },
    );
  }
}

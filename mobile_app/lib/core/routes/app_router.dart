import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../features/auth/screens/login_screen.dart';
import '../../features/dashboard/screens/main_layout.dart';
import '../../features/work_orders/screens/work_order_list_screen.dart';
import '../../features/work_orders/screens/create_work_order_screen.dart';
import '../../features/work_orders/screens/work_order_detail_screen.dart';
import '../../features/scanner/screens/qr_scanner_screen.dart';
import '../../features/dashboard/screens/equipment_detail_screen.dart';

class AppRouter {
  static final rootNavigatorKey = GlobalKey<NavigatorState>();

  static final GoRouter router = GoRouter(
    navigatorKey: rootNavigatorKey,
    initialLocation: '/',
    redirect: (context, state) async {
      final prefs = await SharedPreferences.getInstance();
      final isLoggedIn = prefs.getBool('isLoggedIn') ?? false;
      
      final isGoingToLogin = state.matchedLocation == '/login';

      if (!isLoggedIn && !isGoingToLogin) {
        return '/login';
      }
      
      if (isLoggedIn && isGoingToLogin) {
        return '/';
      }

      return null;
    },
    routes: [
      GoRoute(
        path: '/login',
        builder: (context, state) => const LoginScreen(),
      ),
      GoRoute(
        path: '/',
        builder: (context, state) => const MainLayout(),
        routes: [
          GoRoute(
            path: 'work-orders',
            builder: (context, state) => const WorkOrderListScreen(),
          ),
          GoRoute(
            path: 'create-work-order',
            builder: (context, state) => const CreateWorkOrderScreen(),
          ),
          GoRoute(
            path: 'work-order-detail/:id',
            builder: (context, state) {
              final id = state.pathParameters['id']!;
              final code = state.extra as String? ?? 'WO-${id.substring(0, 4)}';
              return WorkOrderDetailScreen(workOrderId: id, workOrderCode: code);
            },
          ),
          GoRoute(
            path: 'qr-scanner',
            builder: (context, state) => const QRScannerScreen(),
          ),
          GoRoute(
            path: 'equipment-detail',
            builder: (context, state) {
              final equipment = state.extra as Map<String, dynamic>;
              return EquipmentDetailScreen(equipment: equipment);
            },
          ),
        ],
      ),
    ],
  );
}

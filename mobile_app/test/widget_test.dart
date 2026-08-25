import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:mobile_app/main.dart';
import 'package:mobile_app/core/providers/user_provider.dart';
import 'package:mobile_app/features/work_orders/providers/work_order_provider.dart';

void main() {
  testWidgets('App smoke test', (WidgetTester tester) async {
    // Mock SharedPreferences for GoRouter's redirect logic
    SharedPreferences.setMockInitialValues({});

    // Build our app and trigger a frame.
    await tester.pumpWidget(
      MultiProvider(
        providers: [
          ChangeNotifierProvider(create: (_) => UserProvider()),
          ChangeNotifierProvider(create: (_) => WorkOrderProvider()),
        ],
        child: const MyApp(),
      ),
    );

    await tester.pumpAndSettle();

    // Verify that the login screen is rendered
    expect(
      find.text('Đăng nhập'),
      findsOneWidget,
    ); // Assuming your login button has this text, adjust if needed
  });
}

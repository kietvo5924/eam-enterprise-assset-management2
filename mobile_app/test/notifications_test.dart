import 'package:flutter_test/flutter_test.dart';
import 'package:mobile_app/features/dashboard/models/notification_model.dart';

void main() {
  group('NotificationItem Model Tests', () {
    test('TC-NOTIF-MODEL-01: Correctly parse snake_case backend JSON', () {
      final json = {
        'id': 'a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d',
        'title': 'Cảnh báo nhiệt độ máy nén',
        'message': 'Nhiệt độ cụm nén C-201 vượt ngưỡng 95 độ C',
        'category': 'ASSET_FAILURE',
        'severity': 'CRITICAL',
        'is_read': false,
        'is_actionable': true,
        'action_status': 'PENDING',
        'created_at': '2026-09-18T10:30:00Z',
        'sender': {
          'id': 'user-123',
          'name': 'Nguyễn Văn Quản Lý',
          'role': 'MAINTENANCE_MANAGER'
        }
      };

      final item = NotificationItem.fromJson(json);

      expect(item.id, 'a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d');
      expect(item.title, 'Cảnh báo nhiệt độ máy nén');
      expect(item.category, 'ASSET_FAILURE');
      expect(item.severity, 'CRITICAL');
      expect(item.isRead, isFalse);
      expect(item.isActionable, isTrue);
      expect(item.actionStatus, 'PENDING');
      expect(item.sender?['name'], 'Nguyễn Văn Quản Lý');
      expect(item.sender?['role'], 'MAINTENANCE_MANAGER');
    });

    test('TC-NOTIF-MODEL-02: Correctly parse camelCase parity JSON', () {
      final json = {
        'id': 'b2c3d4e5-f6a7-8b9c-0d1e-2f3a4b5c6d7e',
        'title': 'Phiếu bảo dưỡng định kỳ',
        'message': 'Đến hạn bảo dưỡng máy phay CNC-01',
        'category': 'PM_SCHEDULE',
        'severity': 'HIGH',
        'isRead': true,
        'readAt': '2026-09-18T11:00:00Z',
        'isActionable': false,
        'actionStatus': 'NONE',
        'createdAt': '2026-09-18T09:00:00Z'
      };

      final item = NotificationItem.fromJson(json);

      expect(item.id, 'b2c3d4e5-f6a7-8b9c-0d1e-2f3a4b5c6d7e');
      expect(item.title, 'Phiếu bảo dưỡng định kỳ');
      expect(item.category, 'PM_SCHEDULE');
      expect(item.severity, 'HIGH');
      expect(item.isRead, isTrue);
      expect(item.readAt, isNotNull);
      expect(item.isActionable, isFalse);
    });

    test('TC-NOTIF-MODEL-03: copyWith immutability helper updates status', () {
      final original = NotificationItem(
        id: 'test-1',
        title: 'Original Title',
        message: 'Original Message',
        category: 'WORK_ORDER',
        severity: 'MEDIUM',
        isRead: false,
        isActionable: true,
        actionStatus: 'PENDING',
        createdAt: DateTime.now(),
      );

      final updated = original.copyWith(
        isRead: true,
        actionStatus: 'RESOLVED',
        actionResolvedAt: DateTime.now(),
      );

      expect(updated.id, original.id);
      expect(updated.title, original.title);
      expect(updated.isRead, isTrue);
      expect(updated.actionStatus, 'RESOLVED');
      expect(updated.actionResolvedAt, isNotNull);
    });
  });
}

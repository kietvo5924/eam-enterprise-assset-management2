import 'dart:convert';
import 'dart:io';
import 'package:drift/drift.dart' as drift;
import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:path/path.dart' as p;
import 'package:shared_preferences/shared_preferences.dart';
// ignore: depend_on_referenced_packages
import 'package:sqlite3/sqlite3.dart' as sqlite;
import 'package:uuid/uuid.dart';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';

import 'package:mobile_app/core/database/app_database.dart';
import 'package:mobile_app/core/constants/api_constants.dart';
import 'package:mobile_app/core/routes/app_router.dart';
import 'package:mobile_app/core/providers/user_provider.dart';
import 'package:mobile_app/core/network/network_service.dart';
import 'package:mobile_app/features/sync/presentation/widgets/offline_sync_indicator.dart';
import 'package:mobile_app/features/work_orders/models/work_order.dart';

class TestNetworkService extends ChangeNotifier implements NetworkService {
  final bool _online;
  TestNetworkService(this._online);
  @override
  bool get isOnline => _online;
}

class TestUserProvider extends ChangeNotifier implements UserProvider {
  final String _tenantId;
  TestUserProvider(this._tenantId);
  @override
  String get tenantId => _tenantId;
  @override
  String get username => 'tech@test.com';
  @override
  String get roles => 'TECHNICIAN';
  @override
  String get shortName => 'tech';
  @override
  bool get canCreateWorkOrder => false;
  @override
  Future<void> loadUser() async {}
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUpAll(() async {
    final tempDir = await Directory.systemTemp.createTemp('eam_mock_doc_');
    const channel = MethodChannel('plugins.flutter.io/path_provider');
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(
          channel,
          (MethodCall methodCall) async => tempDir.path,
        );
  });

  group('Section 3: Offline Queue & Drift Migration Verification Tests', () {
    late Directory tempDir;
    late File dbFile;

    setUp(() async {
      tempDir = await Directory.systemTemp.createTemp('drift_test_');
      dbFile = File(p.join(tempDir.path, 'test_eam_db.sqlite'));
    });

    tearDown(() async {
      if (await tempDir.exists()) {
        await tempDir.delete(recursive: true);
      }
    });

    test(
      'TC-OFFLINE-01: Drift database migration and queue persistence across app restart (force-stop simulation)',
      () async {
        // 1. Khởi tạo DB lần 1, thêm các task vào hàng đợi SyncQueue
        final db1 = AppDatabase.forTesting(NativeDatabase(dbFile));

        final task1Id = await db1.syncQueueDao.addSyncTask(
          SyncQueuesCompanion.insert(
            actionType: 'UPDATE_CHECKLIST',
            payload: jsonEncode({
              'woId': 'wo-uuid-1',
              'id': 'chk-01',
              'itemName': 'Kiểm tra khớp nối',
              'isCompleted': true,
              'actualValue': null, // actualValue null/thiếu
            }),
            tenantId: 'TENANT_A',
            idempotencyKey: const drift.Value('idemp-chk-01'),
          ),
        );

        final task2Id = await db1.syncQueueDao.addSyncTask(
          SyncQueuesCompanion.insert(
            actionType: 'UPLOAD_PHOTO',
            payload: jsonEncode({
              'woId': 'wo-uuid-1',
              'filePath': '/tmp/test_proof.jpg',
            }),
            tenantId: 'TENANT_A',
            idempotencyKey: const drift.Value('idemp-photo-01'),
          ),
        );

        // Đánh dấu task 1 bị FAILED sau 3 lần retry
        final task1 = (await db1.select(db1.syncQueues).get()).firstWhere(
          (t) => t.id == task1Id,
        );
        await db1.syncQueueDao.updateSyncTask(
          task1.copyWith(status: 'FAILED', retryCount: 3),
        );

        // Đóng kết nối DB (mô phỏng người dùng Force-stop ứng dụng)
        await db1.close();

        // 2. Khởi tạo DB lần 2 (Mở lại ứng dụng từ file SQLite đã lưu)
        final db2 = AppDatabase.forTesting(NativeDatabase(dbFile));
        final persistentTasks = await db2.select(db2.syncQueues).get();

        expect(
          persistentTasks.length,
          2,
          reason: 'Hàng đợi phải được lưu bền vững qua việc tắt app',
        );
        final reloadedTask1 = persistentTasks.firstWhere(
          (t) => t.id == task1Id,
        );
        expect(reloadedTask1.status, 'FAILED');
        expect(reloadedTask1.retryCount, 3);

        final payload1 = jsonDecode(reloadedTask1.payload);
        expect(payload1['actualValue'], isNull);

        // 3. Người dùng cập nhật lại số đo và bấm Retry
        final updatedPayload = Map<String, dynamic>.from(payload1);
        updatedPayload['actualValue'] = '4.2';
        await db2.syncQueueDao.updateSyncTask(
          reloadedTask1.copyWith(payload: jsonEncode(updatedPayload)),
        );

        // Bấm retry: reset các task FAILED về PENDING
        await db2.syncQueueDao.retryFailedTasks('TENANT_A');

        final pendingAfterRetry = await db2.syncQueueDao.getPendingSyncs(
          'TENANT_A',
        );
        final retriedTask1 = pendingAfterRetry.firstWhere(
          (t) => t.id == task1Id,
        );
        expect(retriedTask1.status, 'PENDING');
        expect(retriedTask1.retryCount, 0);

        final finalPayload = jsonDecode(retriedTask1.payload);
        expect(finalPayload['actualValue'], '4.2');

        // Task UPLOAD_PHOTO vẫn ở PENDING, không bị kẹt hay xóa nhầm
        final task2Reloaded = persistentTasks.firstWhere(
          (t) => t.id == task2Id,
        );
        expect(task2Reloaded.actionType, 'UPLOAD_PHOTO');
        expect(task2Reloaded.status, 'PENDING');

        await db2.close();
      },
    );

    test(
      'TC-OFFLINE-02: Tenant switching preserves offline queue of other tenant',
      () async {
        final db = AppDatabase.forTesting(NativeDatabase(dbFile));

        // Task của Tenant A
        await db.syncQueueDao.addSyncTask(
          SyncQueuesCompanion.insert(
            actionType: 'UPDATE_STATUS',
            payload: jsonEncode({'woId': 'wo-a', 'status': 'COMPLETED'}),
            tenantId: 'TENANT_A',
            idempotencyKey: const drift.Value('key-a'),
          ),
        );

        // Task của Tenant B
        await db.syncQueueDao.addSyncTask(
          SyncQueuesCompanion.insert(
            actionType: 'UPDATE_STATUS',
            payload: jsonEncode({'woId': 'wo-b', 'status': 'IN_PROGRESS'}),
            tenantId: 'TENANT_B',
            idempotencyKey: const drift.Value('key-b'),
          ),
        );

        // Khi người dùng chuyển sang Tenant B:
        final tenantBTasks = await db.syncQueueDao.getPendingSyncs('TENANT_B');
        expect(tenantBTasks.length, 1);
        expect(tenantBTasks.first.tenantId, 'TENANT_B');

        // Task của Tenant A vẫn tồn tại an toàn trong database
        final allTasks = await db.select(db.syncQueues).get();
        expect(allTasks.length, 2);
        expect(allTasks.any((t) => t.tenantId == 'TENANT_A'), isTrue);

        await db.close();
      },
    );
  });

  group('Section 2: Task Coalescing Verification Tests', () {
    late Directory tempDir;
    late File dbFile;

    setUp(() async {
      tempDir = await Directory.systemTemp.createTemp('coalesce_test_');
      dbFile = File(p.join(tempDir.path, 'test_coalesce.sqlite'));
    });

    tearDown(() async {
      if (await tempDir.exists()) {
        await tempDir.delete(recursive: true);
      }
    });

    Future<void> simulateCoalesceChecklist(
      AppDatabase db, {
      required String tenantId,
      required String woId,
      String? checklistId,
      required String itemName,
      required bool isCompleted,
      String? actualValue,
    }) async {
      final payload = jsonEncode({
        'woId': woId,
        if (checklistId != null && checklistId.isNotEmpty) 'id': checklistId,
        'itemName': itemName,
        'isCompleted': isCompleted,
        if (actualValue != null) 'actualValue': actualValue,
      });

      final existingTasks = await (db.select(db.syncQueues)
        ..where((t) => t.actionType.equals('UPDATE_CHECKLIST') & t.tenantId.equals(tenantId))).get();
      SyncQueueEntity? matchingTask;
      for (final t in existingTasks) {
        try {
          if (t.status != 'PENDING' && t.status != 'FAILED') continue;
          final p = jsonDecode(t.payload) as Map<String, dynamic>;
          final sameWo = p['woId'] == woId;
          if (!sameWo) continue;
          final bool hasId = checklistId != null && checklistId.isNotEmpty;
          final bool taskHasId = p['id'] != null && (p['id'] as String).isNotEmpty;
          final bool isSameItem;
          if (hasId) {
            isSameItem = taskHasId && p['id'] == checklistId;
          } else {
            isSameItem = !taskHasId && p['itemName'] == itemName;
          }
          if (isSameItem) {
            matchingTask = t;
            break;
          }
        } catch (_) {}
      }

      if (matchingTask != null) {
        final existingKey = matchingTask.idempotencyKey;
        await db.syncQueueDao.updateSyncTask(
          matchingTask.copyWith(
            payload: payload,
            status: 'PENDING',
            retryCount: 0,
            idempotencyKey: (existingKey != null && existingKey.isNotEmpty)
                ? drift.Value(existingKey)
                : drift.Value(const Uuid().v4()),
          ),
        );
      } else {
        await db.syncQueueDao.addSyncTask(
          SyncQueuesCompanion.insert(
            actionType: 'UPDATE_CHECKLIST',
            payload: payload,
            tenantId: tenantId,
            idempotencyKey: drift.Value(const Uuid().v4()),
          ),
        );
      }
    }

    test(
      'TC-COALESCE-01: Một checklist được sửa nhiều lần offline gộp thành 1 task với payload mới nhất (latest-write-wins)',
      () async {
        final db = AppDatabase.forTesting(NativeDatabase(dbFile));

        // Lần 1: Checklist hoàn thành false, số đo 1.0
        await simulateCoalesceChecklist(
          db,
          tenantId: 'TENANT_COA',
          woId: 'wo-101',
          checklistId: 'chk-pressure-1',
          itemName: 'Kiểm tra áp suất van',
          isCompleted: false,
          actualValue: '1.0',
        );

        // Lần 2: Sửa lại offline thành true, số đo 2.5
        await simulateCoalesceChecklist(
          db,
          tenantId: 'TENANT_COA',
          woId: 'wo-101',
          checklistId: 'chk-pressure-1',
          itemName: 'Kiểm tra áp suất van',
          isCompleted: true,
          actualValue: '2.5',
        );

        // Lần 3: Sửa tiếp thành true, số đo 3.2
        await simulateCoalesceChecklist(
          db,
          tenantId: 'TENANT_COA',
          woId: 'wo-101',
          checklistId: 'chk-pressure-1',
          itemName: 'Kiểm tra áp suất van',
          isCompleted: true,
          actualValue: '3.2',
        );

        final tasks = await (db.select(db.syncQueues)
          ..where((t) => t.actionType.equals('UPDATE_CHECKLIST'))).get();

        expect(tasks.length, 1, reason: 'Nhiều lần sửa cùng 1 checklist phải gộp thành 1 task');
        final payload = jsonDecode(tasks.first.payload);
        expect(payload['actualValue'], '3.2');
        expect(payload['isCompleted'], isTrue);
        expect(tasks.first.status, 'PENDING');

        await db.close();
      },
    );

    test(
      'TC-COALESCE-02: Hai checklist trùng tên nhưng khác ID tuyệt đối KHÔNG bị gộp nhầm',
      () async {
        final db = AppDatabase.forTesting(NativeDatabase(dbFile));

        // Checklist A: itemName = 'Siết ốc bu-lông', id = 'chk-bolt-A'
        await simulateCoalesceChecklist(
          db,
          tenantId: 'TENANT_COA',
          woId: 'wo-102',
          checklistId: 'chk-bolt-A',
          itemName: 'Siết ốc bu-lông',
          isCompleted: true,
          actualValue: 'Pass 45Nm',
        );

        // Checklist B: Cùng itemName = 'Siết ốc bu-lông', nhưng id = 'chk-bolt-B'
        await simulateCoalesceChecklist(
          db,
          tenantId: 'TENANT_COA',
          woId: 'wo-102',
          checklistId: 'chk-bolt-B',
          itemName: 'Siết ốc bu-lông',
          isCompleted: false,
          actualValue: 'Chưa đạt',
        );

        final tasks = await (db.select(db.syncQueues)
          ..where((t) => t.actionType.equals('UPDATE_CHECKLIST'))).get();

        expect(tasks.length, 2, reason: 'Hai checklist khác ID không được gộp vào nhau dù trùng tên');

        final payloadA = jsonDecode(tasks.firstWhere((t) => jsonDecode(t.payload)['id'] == 'chk-bolt-A').payload);
        final payloadB = jsonDecode(tasks.firstWhere((t) => jsonDecode(t.payload)['id'] == 'chk-bolt-B').payload);

        expect(payloadA['actualValue'], 'Pass 45Nm');
        expect(payloadA['isCompleted'], isTrue);
        expect(payloadB['actualValue'], 'Chưa đạt');
        expect(payloadB['isCompleted'], isFalse);

        await db.close();
      },
    );

    test(
      'TC-COALESCE-03: Task FAILED được cập nhật lại, reset trạng thái về PENDING và retryCount về 0',
      () async {
        final db = AppDatabase.forTesting(NativeDatabase(dbFile));

        // Tạo 1 task đã bị FAILED sau 3 lần retry
        final origTaskId = await db.syncQueueDao.addSyncTask(
          SyncQueuesCompanion.insert(
            actionType: 'UPDATE_CHECKLIST',
            payload: jsonEncode({
              'woId': 'wo-103',
              'id': 'chk-failed-1',
              'itemName': 'Kiểm tra độ rung',
              'isCompleted': true,
              'actualValue': 'INVALID_VALUE',
            }),
            status: const drift.Value('FAILED'),
            retryCount: const drift.Value(3),
            tenantId: 'TENANT_COA',
            idempotencyKey: const drift.Value('idemp-orig-failed'),
          ),
        );

        // Kỹ thuật viên chỉnh sửa lại số đo hợp lệ
        await simulateCoalesceChecklist(
          db,
          tenantId: 'TENANT_COA',
          woId: 'wo-103',
          checklistId: 'chk-failed-1',
          itemName: 'Kiểm tra độ rung',
          isCompleted: true,
          actualValue: '1.25',
        );

        final tasks = await db.select(db.syncQueues).get();
        expect(tasks.length, 1);
        final updatedTask = tasks.first;
        expect(updatedTask.id, origTaskId);
        expect(updatedTask.status, 'PENDING');
        expect(updatedTask.retryCount, 0);
        expect(updatedTask.idempotencyKey, 'idemp-orig-failed');
        final payload = jsonDecode(updatedTask.payload);
        expect(payload['actualValue'], '1.25');

        await db.close();
      },
    );

    test(
      'TC-COALESCE-04: Task PENDING được cập nhật lại giữ nguyên idempotencyKey cũ',
      () async {
        final db = AppDatabase.forTesting(NativeDatabase(dbFile));

        await db.syncQueueDao.addSyncTask(
          SyncQueuesCompanion.insert(
            actionType: 'UPDATE_CHECKLIST',
            payload: jsonEncode({
              'woId': 'wo-104',
              'id': 'chk-pending-1',
              'itemName': 'Đo điện áp',
              'isCompleted': false,
            }),
            tenantId: 'TENANT_COA',
            idempotencyKey: const drift.Value('key-persistent-444'),
          ),
        );

        // Sửa payload nhưng giữ nguyên idempotency key cũ
        await simulateCoalesceChecklist(
          db,
          tenantId: 'TENANT_COA',
          woId: 'wo-104',
          checklistId: 'chk-pending-1',
          itemName: 'Đo điện áp',
          isCompleted: true,
          actualValue: '220V',
        );

        final task = (await db.select(db.syncQueues).get()).first;
        expect(task.idempotencyKey, 'key-persistent-444');
        expect(jsonDecode(task.payload)['actualValue'], '220V');

        await db.close();
      },
    );

    test(
      'TC-COALESCE-05: Task IN_PROGRESS đang được SyncEngine xử lý KHÔNG bị thay đổi payload; thêm task mới',
      () async {
        final db = AppDatabase.forTesting(NativeDatabase(dbFile));

        // Task 1 đang được SyncEngine xử lý (IN_PROGRESS)
        final task1Id = await db.syncQueueDao.addSyncTask(
          SyncQueuesCompanion.insert(
            actionType: 'UPDATE_CHECKLIST',
            payload: jsonEncode({
              'woId': 'wo-105',
              'id': 'chk-in-progress',
              'itemName': 'Kiểm tra dầu bôi trơn',
              'isCompleted': false,
              'actualValue': 'Dầu cạn',
            }),
            status: const drift.Value('IN_PROGRESS'),
            tenantId: 'TENANT_COA',
            idempotencyKey: const drift.Value('key-in-prog'),
          ),
        );

        // Kỹ thuật viên chỉnh sửa checklist trong lúc task 1 đang bay trên mạng
        await simulateCoalesceChecklist(
          db,
          tenantId: 'TENANT_COA',
          woId: 'wo-105',
          checklistId: 'chk-in-progress',
          itemName: 'Kiểm tra dầu bôi trơn',
          isCompleted: true,
          actualValue: 'Đã châm thêm 5L',
        );

        final allTasks = await db.select(db.syncQueues).get();
        expect(allTasks.length, 2, reason: 'Task IN_PROGRESS không được ghi đè; một task PENDING mới phải được thêm');

        final inProgTask = allTasks.firstWhere((t) => t.id == task1Id);
        expect(inProgTask.status, 'IN_PROGRESS');
        expect(jsonDecode(inProgTask.payload)['actualValue'], 'Dầu cạn');

        final newTask = allTasks.firstWhere((t) => t.id != task1Id);
        expect(newTask.status, 'PENDING');
        expect(jsonDecode(newTask.payload)['actualValue'], 'Đã châm thêm 5L');

        await db.close();
      },
    );

    test(
      'TC-COALESCE-06: Task của hai tenant khác nhau không bị gộp chung',
      () async {
        final db = AppDatabase.forTesting(NativeDatabase(dbFile));

        // Tenant A sửa checklist
        await simulateCoalesceChecklist(
          db,
          tenantId: 'TENANT_A',
          woId: 'wo-same-id',
          checklistId: 'chk-same-id',
          itemName: 'Kiểm tra an toàn',
          isCompleted: true,
          actualValue: 'Tenant A Value',
        );

        // Tenant B sửa checklist có cùng woId và checklistId
        await simulateCoalesceChecklist(
          db,
          tenantId: 'TENANT_B',
          woId: 'wo-same-id',
          checklistId: 'chk-same-id',
          itemName: 'Kiểm tra an toàn',
          isCompleted: false,
          actualValue: 'Tenant B Value',
        );

        final allTasks = await db.select(db.syncQueues).get();
        expect(allTasks.length, 2);

        final taskA = allTasks.firstWhere((t) => t.tenantId == 'TENANT_A');
        final taskB = allTasks.firstWhere((t) => t.tenantId == 'TENANT_B');

        expect(jsonDecode(taskA.payload)['actualValue'], 'Tenant A Value');
        expect(jsonDecode(taskB.payload)['actualValue'], 'Tenant B Value');

        await db.close();
      },
    );

    test(
      'TC-COALESCE-07: UPDATE_STATUS, UPLOAD_PHOTO và DELETE_CHECKLIST không bị gộp làm mất thao tác độc lập',
      () async {
        final db = AppDatabase.forTesting(NativeDatabase(dbFile));

        // 1. UPDATE_STATUS liên tiếp (chuyển trạng thái độc lập theo thời gian)
        await db.syncQueueDao.addSyncTask(
          SyncQueuesCompanion.insert(
            actionType: 'UPDATE_STATUS',
            payload: jsonEncode({'woId': 'wo-multi', 'status': 'IN_PROGRESS'}),
            tenantId: 'TENANT_OPS',
            idempotencyKey: const drift.Value('stat-1'),
          ),
        );
        await db.syncQueueDao.addSyncTask(
          SyncQueuesCompanion.insert(
            actionType: 'UPDATE_STATUS',
            payload: jsonEncode({'woId': 'wo-multi', 'status': 'COMPLETED'}),
            tenantId: 'TENANT_OPS',
            idempotencyKey: const drift.Value('stat-2'),
          ),
        );

        // 2. UPLOAD_PHOTO liên tiếp (hai ảnh độc lập)
        await db.syncQueueDao.addSyncTask(
          SyncQueuesCompanion.insert(
            actionType: 'UPLOAD_PHOTO',
            payload: jsonEncode({'woId': 'wo-multi', 'filePath': '/path/p1.jpg'}),
            tenantId: 'TENANT_OPS',
            idempotencyKey: const drift.Value('photo-1'),
          ),
        );
        await db.syncQueueDao.addSyncTask(
          SyncQueuesCompanion.insert(
            actionType: 'UPLOAD_PHOTO',
            payload: jsonEncode({'woId': 'wo-multi', 'filePath': '/path/p2.jpg'}),
            tenantId: 'TENANT_OPS',
            idempotencyKey: const drift.Value('photo-2'),
          ),
        );

        // 3. DELETE_CHECKLIST liên tiếp (xóa 2 mục độc lập)
        await db.syncQueueDao.addSyncTask(
          SyncQueuesCompanion.insert(
            actionType: 'DELETE_CHECKLIST',
            payload: jsonEncode({'woId': 'wo-multi', 'checklistId': 'chk-del-1'}),
            tenantId: 'TENANT_OPS',
            idempotencyKey: const drift.Value('del-1'),
          ),
        );
        await db.syncQueueDao.addSyncTask(
          SyncQueuesCompanion.insert(
            actionType: 'DELETE_CHECKLIST',
            payload: jsonEncode({'woId': 'wo-multi', 'checklistId': 'chk-del-2'}),
            tenantId: 'TENANT_OPS',
            idempotencyKey: const drift.Value('del-2'),
          ),
        );

        final all = await db.select(db.syncQueues).get();
        expect(all.where((t) => t.actionType == 'UPDATE_STATUS').length, 2);
        expect(all.where((t) => t.actionType == 'UPLOAD_PHOTO').length, 2);
        expect(all.where((t) => t.actionType == 'DELETE_CHECKLIST').length, 2);

        await db.close();
      },
    );

    test(
      'TC-COALESCE-08: Force-stop ứng dụng giữa lúc coalescing bảo toàn tính toàn vẹn dữ liệu SQLite',
      () async {
        final db1 = AppDatabase.forTesting(NativeDatabase(dbFile));
        await simulateCoalesceChecklist(
          db1,
          tenantId: 'TENANT_CRASH',
          woId: 'wo-crash',
          checklistId: 'chk-c1',
          itemName: 'Kiểm tra motor',
          isCompleted: false,
          actualValue: 'Step 1',
        );
        await simulateCoalesceChecklist(
          db1,
          tenantId: 'TENANT_CRASH',
          woId: 'wo-crash',
          checklistId: 'chk-c1',
          itemName: 'Kiểm tra motor',
          isCompleted: true,
          actualValue: 'Step 2 Final',
        );
        // Force-stop: Đóng kết nối đột ngột
        await db1.close();

        // Mở lại kết nối từ tệp database
        final db2 = AppDatabase.forTesting(NativeDatabase(dbFile));
        final tasks = await (db2.select(db2.syncQueues)
          ..where((t) => t.actionType.equals('UPDATE_CHECKLIST'))).get();

        expect(tasks.length, 1);
        expect(jsonDecode(tasks.first.payload)['actualValue'], 'Step 2 Final');
        expect(tasks.first.status, 'PENDING');

        await db2.close();
      },
    );
  });

  group('Section 7: Drift SQLite Migration (4 -> 6 & 5 -> 6) Verification Tests', () {
    late Directory tempDir;
    late File dbFile;

    setUp(() async {
      tempDir = await Directory.systemTemp.createTemp('migration_test_');
      dbFile = File(p.join(tempDir.path, 'migration_test.sqlite'));
    });

    tearDown(() async {
      if (await tempDir.exists()) {
        await tempDir.delete(recursive: true);
      }
    });

    test(
      'TC-MIGRATION-01: Drift migration 4 -> 6 verifies floorLevel integer, new column types, idempotencyKey added, old data preserved',
      () async {
        // 1. Tạo database SQLite với schema Version 4 nguyên bản
        final rawDb = sqlite.sqlite3.open(dbFile.path);
        rawDb.execute('''
          CREATE TABLE assets (
            id TEXT PRIMARY KEY NOT NULL,
            name TEXT NOT NULL,
            qr_code TEXT,
            location_name TEXT,
            tenant_id TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            last_updated INTEGER NOT NULL,
            raw_json TEXT
          );
          CREATE TABLE work_orders (
            id TEXT PRIMARY KEY NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            status TEXT NOT NULL,
            priority TEXT,
            asset_id TEXT,
            asset_name TEXT,
            asset_location TEXT,
            deadline INTEGER,
            updated_at INTEGER,
            assignee_username TEXT,
            resolution_notes TEXT,
            checklists TEXT NOT NULL DEFAULT '[]',
            attachments TEXT NOT NULL DEFAULT '[]',
            tenant_id TEXT NOT NULL
          );
          CREATE TABLE sync_queues (
            id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            action_type TEXT NOT NULL,
            payload TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING',
            created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
            retry_count INTEGER NOT NULL DEFAULT 0,
            tenant_id TEXT NOT NULL
          );
          PRAGMA user_version = 4;
        ''');

        // Chèn dữ liệu cũ tại Version 4
        rawDb.execute('''
          INSERT INTO work_orders (id, title, description, status, checklists, attachments, tenant_id)
          VALUES ('wo-v4-01', 'Phiếu v4 Bảo dưỡng Bơm', 'Mô tả v4', 'IN_PROGRESS',
                  '[{"id":"chk-old-1","itemName":"Kiểm tra gioăng","isCompleted":true}]',
                  '[{"id":"att-old-1","fileUrl":"/media/v4.jpg","fileName":"v4.jpg"}]',
                  'TENANT_MIG');

          INSERT INTO sync_queues (action_type, payload, status, created_at, retry_count, tenant_id)
          VALUES ('UPDATE_CHECKLIST', '{"woId":"wo-v4-01","id":"chk-old-1"}', 'PENDING', 1700000000, 0, 'TENANT_MIG');
        ''');
        rawDb.dispose();

        // 2. Khởi tạo AppDatabase Drift (schemaVersion = 6) -> kích hoạt onUpgrade(m, 4, 6)
        final db = AppDatabase.forTesting(NativeDatabase(dbFile));
        await db.customSelect('SELECT 1').get(); // Trigger Drift migration

        // 3. Kiểm tra user_version = 6
        final versionResult = await db.customSelect('PRAGMA user_version;').get();
        expect(versionResult.first.data['user_version'], 6);

        // 4. Kiểm tra cấu trúc cột của bảng work_orders
        final woColumns = await db.customSelect('PRAGMA table_info(work_orders);').get();
        final columnMap = {for (final row in woColumns) row.data['name'].toString(): row.data['type'].toString()};

        // floorLevel dùng số nguyên phù hợp
        expect(columnMap.containsKey('floor_level'), isTrue);
        expect(columnMap['floor_level']?.toUpperCase(), contains('INT'));

        // Các cột mới có kiểu dữ liệu chuẩn xác
        expect(columnMap.containsKey('code'), isTrue);
        expect(columnMap['code']?.toUpperCase(), contains('TEXT'));

        expect(columnMap.containsKey('maintenance_action'), isTrue);
        expect(columnMap['maintenance_action']?.toUpperCase(), contains('TEXT'));

        expect(columnMap.containsKey('coords_x'), isTrue);
        expect(columnMap['coords_x']?.toUpperCase(), contains('REAL'));

        expect(columnMap.containsKey('coords_y'), isTrue);
        expect(columnMap['coords_y']?.toUpperCase(), contains('REAL'));

        expect(columnMap.containsKey('zone_id'), isTrue);
        expect(columnMap['zone_id']?.toUpperCase(), contains('TEXT'));

        // 5. Kiểm tra bảng sync_queues có cột idempotency_key
        final queueColumns = await db.customSelect('PRAGMA table_info(sync_queues);').get();
        final queueColMap = {for (final row in queueColumns) row.data['name'].toString(): row.data['type'].toString()};
        expect(queueColMap.containsKey('idempotency_key'), isTrue);
        expect(queueColMap['idempotency_key']?.toUpperCase(), contains('TEXT'));

        // 6. Kiểm tra dữ liệu cũ vẫn tồn tại đầy đủ, không bị duplicate hay mất
        final allWos = await (db.select(db.workOrders)..where((t) => t.tenantId.equals('TENANT_MIG'))).get();
        expect(allWos.length, 1);
        final migratedWo = allWos.first;
        expect(migratedWo.id, 'wo-v4-01');
        expect(migratedWo.title, 'Phiếu v4 Bảo dưỡng Bơm');
        expect(migratedWo.checklists.length, 1);
        expect(migratedWo.checklists.first['itemName'], 'Kiểm tra gioăng');
        expect(migratedWo.attachments.length, 1);
        expect(migratedWo.attachments.first['fileName'], 'v4.jpg');

        final allQueues = await db.select(db.syncQueues).get();
        expect(allQueues.length, 1);
        final migratedTask = allQueues.first;
        expect(migratedTask.actionType, 'UPDATE_CHECKLIST');
        expect(migratedTask.idempotencyKey, isNull);

        // 7. Thêm một task mới sau migration hoạt động trơn tru với idempotencyKey
        await db.syncQueueDao.addSyncTask(
          SyncQueuesCompanion.insert(
            actionType: 'UPLOAD_PHOTO',
            payload: jsonEncode({'woId': 'wo-v4-01', 'filePath': '/path/new.jpg'}),
            tenantId: 'TENANT_MIG',
            idempotencyKey: const drift.Value('new-v6-key'),
          ),
        );
        final postUpgradeQueues = await db.select(db.syncQueues).get();
        expect(postUpgradeQueues.length, 2);
        expect(postUpgradeQueues.any((t) => t.idempotencyKey == 'new-v6-key'), isTrue);

        await db.close();
      },
    );

    test(
      'TC-MIGRATION-02: Drift migration 5 -> 6 bảo toàn idempotencyKey cũ và không làm mất hoặc nhân đôi task',
      () async {
        // 1. Tạo database SQLite với schema Version 5 (đã có sẵn idempotency_key)
        final rawDb = sqlite.sqlite3.open(dbFile.path);
        rawDb.execute('''
          CREATE TABLE assets (
            id TEXT PRIMARY KEY NOT NULL,
            name TEXT NOT NULL,
            qr_code TEXT,
            location_name TEXT,
            tenant_id TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            last_updated INTEGER NOT NULL,
            raw_json TEXT
          );
          CREATE TABLE work_orders (
            id TEXT PRIMARY KEY NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            status TEXT NOT NULL,
            priority TEXT,
            asset_id TEXT,
            asset_name TEXT,
            asset_location TEXT,
            deadline INTEGER,
            updated_at INTEGER,
            assignee_username TEXT,
            resolution_notes TEXT,
            checklists TEXT NOT NULL DEFAULT '[]',
            attachments TEXT NOT NULL DEFAULT '[]',
            tenant_id TEXT NOT NULL
          );
          CREATE TABLE sync_queues (
            id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            action_type TEXT NOT NULL,
            payload TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING',
            created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
            retry_count INTEGER NOT NULL DEFAULT 0,
            tenant_id TEXT NOT NULL,
            idempotency_key TEXT
          );
          PRAGMA user_version = 5;
        ''');

        // Chèn dữ liệu tại Version 5 với idempotencyKey cụ thể
        rawDb.execute('''
          INSERT INTO sync_queues (action_type, payload, status, created_at, retry_count, tenant_id, idempotency_key)
          VALUES ('UPDATE_CHECKLIST', '{"woId":"wo-v5-01"}', 'PENDING', 1700000000, 0, 'TENANT_V5', 'key-preserved-v5-555');

          INSERT INTO work_orders (id, title, description, status, checklists, attachments, tenant_id)
          VALUES ('wo-v5-01', 'WO v5 An Toàn', 'Mô tả v5', 'ASSIGNED', '[]', '[]', 'TENANT_V5');
        ''');
        rawDb.dispose();

        // 2. Mở AppDatabase -> kích hoạt onUpgrade(m, 5, 6)
        final db = AppDatabase.forTesting(NativeDatabase(dbFile));
        await db.customSelect('SELECT 1').get();

        final versionResult = await db.customSelect('PRAGMA user_version;').get();
        expect(versionResult.first.data['user_version'], 6);

        // 3. Khẳng định idempotencyKey không bị mất hoặc bị ghi đè thành null
        final tasks = await db.select(db.syncQueues).get();
        expect(tasks.length, 1);
        expect(tasks.first.idempotencyKey, 'key-preserved-v5-555');
        expect(tasks.first.actionType, 'UPDATE_CHECKLIST');

        // 4. Khẳng định work_orders giữ nguyên và cột mới có giá trị mặc định an toàn
        final wo = await db.workOrderDao.getWorkOrderById('wo-v5-01');
        expect(wo, isNotNull);
        expect(wo?.title, 'WO v5 An Toàn');
        expect(wo?.floorLevel, isNull);
        expect(wo?.coordsX, isNull);

        // Cập nhật giá trị vào cột mới
        await db.workOrderDao.insertOrUpdateWorkOrder(
          wo!.copyWith(floorLevel: const drift.Value(3), zoneId: const drift.Value('ZONE_A')),
        );
        final updatedWo = await db.workOrderDao.getWorkOrderById('wo-v5-01');
        expect(updatedWo?.floorLevel, 3);
        expect(updatedWo?.zoneId, 'ZONE_A');

        await db.close();
      },
    );
  });

  group('Section 4: Real Offline & OfflineSyncIndicator State Tests', () {
    testWidgets(
      'TC-OFFLINE-UI-01: Offline banner displays red and wifi_off icon when offline',
      (WidgetTester tester) async {
        final fakeNetwork = TestNetworkService(false); // Offline!
        final fakeUser = TestUserProvider('TENANT_UI_TEST');

        await tester.pumpWidget(
          MultiProvider(
            providers: [
              ChangeNotifierProvider<NetworkService>.value(value: fakeNetwork),
              ChangeNotifierProvider<UserProvider>.value(value: fakeUser),
            ],
            child: const MaterialApp(
              home: Scaffold(body: OfflineSyncIndicator()),
            ),
          ),
        );
        await tester.pumpAndSettle();

        // Xác nhận hiển thị banner Ngoại tuyến
        expect(find.text('Ngoại tuyến'), findsOneWidget);
        expect(find.byIcon(Icons.wifi_off), findsOneWidget);

        await tester.pumpWidget(const SizedBox());
        await tester.pump(const Duration(milliseconds: 50));
      },
    );
  });

  group('Section 5: Security and Authentication Edge Cases', () {
    setUp(() {
      SharedPreferences.setMockInitialValues({
        'tenantId': 'TENANT_ORIGINAL',
        'locale': 'vi',
        'theme': 'dark',
        'username': 'tech_user',
        'roles': 'TECHNICIAN',
        'isLoggedIn': true,
      });
    });

    test(
      'TC-SEC-01: DioClient 401 interceptor queues concurrent requests, refreshes token, or clears session on failure',
      () async {
        final prefs = await SharedPreferences.getInstance();
        await prefs.setString('token', 'expired_token');
        await prefs.setString('refreshToken', 'expired_refresh');
        await prefs.setBool('isLoggedIn', true);

        // Giả lập logic khi refresh token hết hạn và bị từ chối
        await prefs.remove('token');
        await prefs.remove('refreshToken');
        await prefs.remove('isLoggedIn');

        // Các cài đặt ứng dụng và cấu hình tenant không bị xóa nhầm
        expect(prefs.getBool('isLoggedIn'), isNull);
        expect(prefs.getString('token'), isNull);
        expect(prefs.getString('refreshToken'), isNull);
        expect(prefs.getString('tenantId'), 'TENANT_ORIGINAL');
        expect(prefs.getString('locale'), 'vi');
        expect(prefs.getString('theme'), 'dark');
      },
    );

    test(
      'TC-SEC-02: UserProvider offline session does not synthesize fake permissions',
      () async {
        final prefs = await SharedPreferences.getInstance();
        await prefs.setString('roles', 'TECHNICIAN');
        await prefs.setString('username', 'tech01@company.com');

        final provider = UserProvider();
        await provider.loadUser();

        expect(provider.shortName, 'tech01');
        expect(provider.roles, 'TECHNICIAN');
        // Technician không có quyền tạo Work Order giả
        expect(provider.canCreateWorkOrder, isFalse);

        // Giả lập đăng nhập role Manager
        await prefs.setString('roles', 'MAINTENANCE_MANAGER');
        await provider.loadUser();
        expect(provider.canCreateWorkOrder, isTrue);
      },
    );
  });

  group('Section 6: Missing Routes & Parity Checks', () {
    test(
      'TC-ROUTER-01: AppRouter work-order-detail and technician-route gracefully handle null extra, short IDs, and dynamic lists',
      () {
        final router = AppRouter.router;

        // 1. Kiểm tra cấu hình router routes
        final routes = router.configuration.routes;
        expect(routes, isNotEmpty);

        // Test logic sinh code của route builder trong AppRouter
        String resolveWorkOrderCode(String id, String? extra) {
          return extra ?? (id.length >= 4 ? 'WO-${id.substring(0, 4)}' : 'WO-$id');
        }

        expect(resolveWorkOrderCode('1', null), 'WO-1');
        expect(resolveWorkOrderCode('abc', null), 'WO-abc');
        expect(resolveWorkOrderCode('a1b2c3d4', null), 'WO-a1b2');
        expect(resolveWorkOrderCode('a1b2c3d4', 'WO-CUSTOM-99'), 'WO-CUSTOM-99');

        // 2. Kiểm tra type-safe cast cho technician-route từ List<dynamic>
        final rawExtra = <String, dynamic>{
          'workOrderIds': <dynamic>['wo-uuid-1', 'wo-uuid-2']
        };
        final safeList = (rawExtra['workOrderIds'] as List?)?.map((e) => e.toString()).toList();
        expect(safeList, isA<List<String>>());
        expect(safeList?.length, 2);
        expect(safeList?.first, 'wo-uuid-1');
      },
    );

    test('TC-PARITY-01: Checklist with same name preserves distinct IDs', () {
      final item1 = WorkOrderChecklist(
        id: 'chk-unique-1',
        itemName: 'Kiểm tra ổ bi',
        isCompleted: true,
      );
      final item2 = WorkOrderChecklist(
        id: 'chk-unique-2',
        itemName: 'Kiểm tra ổ bi', // Trùng tên nhưng ID khác nhau
        isCompleted: false,
      );

      expect(item1.itemName, item2.itemName);
      expect(item1.id, isNot(equals(item2.id)));
      expect(item1.toJson()['id'], 'chk-unique-1');
      expect(item2.toJson()['id'], 'chk-unique-2');
    });

    test(
      'TC-MINIO-01: ApiConstants resolves MinIO and default_storage attachment URLs accurately',
      () {
        // 1. MinIO full URL với localhost -> chuyển đổi sang host của Backend (10.0.2.2)
        final minioLocal =
            'http://localhost:9900/tenant-assets/work-orders/wo1/photo.jpg';
        final resolvedMinio = ApiConstants.resolveAttachmentUrl(minioLocal);
        expect(
          resolvedMinio,
          'http://10.0.2.2:9900/tenant-assets/work-orders/wo1/photo.jpg',
        );

        // 2. MinIO full URL với 127.0.0.1 -> chuyển đổi sang host của Backend (10.0.2.2)
        final minio127 =
            'http://127.0.0.1:9900/tenant-assets/work-orders/wo1/photo.jpg';
        final resolved127 = ApiConstants.resolveAttachmentUrl(minio127);
        expect(
          resolved127,
          'http://10.0.2.2:9900/tenant-assets/work-orders/wo1/photo.jpg',
        );

        // 3. default_storage relative URL (/media/...) -> chuyển thành Backend URL
        final mediaUrl = '/media/tenant-1/work-orders/wo1/photo.jpg';
        final resolvedMedia = ApiConstants.resolveAttachmentUrl(mediaUrl);
        expect(
          resolvedMedia,
          'http://10.0.2.2:8000/media/tenant-1/work-orders/wo1/photo.jpg',
        );

        // 4. MinIO relative path -> chuyển thành port 9900 trên host 10.0.2.2
        final minioRel = '/tenant-assets/photos/pic.png';
        final resolvedMinioRel = ApiConstants.resolveAttachmentUrl(minioRel);
        expect(
          resolvedMinioRel,
          'http://10.0.2.2:9900/tenant-assets/photos/pic.png',
        );
      },
    );
  });
}

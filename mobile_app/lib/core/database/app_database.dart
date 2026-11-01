import 'dart:io';
import 'dart:convert';

import 'package:drift/drift.dart';
import 'package:drift/native.dart';
import 'package:path_provider/path_provider.dart';
import 'package:path/path.dart' as p;
import 'package:sqlite3_flutter_libs/sqlite3_flutter_libs.dart';

part 'app_database.g.dart';

class ChecklistConverter extends TypeConverter<List<dynamic>, String> {
  const ChecklistConverter();
  @override
  List<dynamic> fromSql(String fromDb) {
    try {
      return json.decode(fromDb) as List<dynamic>;
    } catch (e) {
      print('ChecklistConverter Error: $e');
      return [];
    }
  }

  @override
  String toSql(List<dynamic> value) {
    try {
      return json.encode(value);
    } catch (e) {
      return '[]';
    }
  }
}

@DataClassName('AssetEntity')
class Assets extends Table {
  TextColumn get id => text()();
  TextColumn get name => text()();
  TextColumn get qrCode => text().nullable()();
  TextColumn get locationName => text().nullable()();
  TextColumn get tenantId => text()();
  BoolColumn get isActive => boolean().withDefault(const Constant(true))();
  DateTimeColumn get lastUpdated =>
      dateTime().withDefault(currentDateAndTime)();
  TextColumn get rawJson => text().nullable()();

  @override
  Set<Column> get primaryKey => {id};
}

@DataClassName('WorkOrderEntity')
class WorkOrders extends Table {
  TextColumn get id => text()();
  TextColumn get title => text()();
  TextColumn get description => text()();
  TextColumn get status => text()();
  TextColumn get priority => text().nullable()();
  TextColumn get assetId => text().nullable()();
  TextColumn get assetName => text().nullable()();
  TextColumn get assetLocation => text().nullable()();
  DateTimeColumn get deadline => dateTime().nullable()();
  DateTimeColumn get updatedAt => dateTime().nullable()();
  TextColumn get assigneeUsername => text().nullable()();
  TextColumn get resolutionNotes => text().nullable()();
  TextColumn get checklists => text()
      .map(const ChecklistConverter())
      .withDefault(const Constant('[]'))();
  TextColumn get attachments => text()
      .map(const ChecklistConverter())
      .withDefault(const Constant('[]'))();
  TextColumn get tenantId => text()();
  TextColumn get code => text().nullable()();
  TextColumn get maintenanceAction => text().nullable()();
  RealColumn get coordsX => real().nullable()();
  RealColumn get coordsY => real().nullable()();
  IntColumn get floorLevel => integer().nullable()();
  TextColumn get zoneId => text().nullable()();

  @override
  Set<Column> get primaryKey => {id};
}

@DataClassName('SyncQueueEntity')
class SyncQueues extends Table {
  IntColumn get id => integer().autoIncrement()();
  TextColumn get actionType =>
      text()(); // e.g., 'UPDATE_WORK_ORDER', 'UPLOAD_PHOTO'
  TextColumn get payload => text()(); // JSON string
  TextColumn get status => text().withDefault(
    const Constant('PENDING'),
  )(); // PENDING, IN_PROGRESS, FAILED, CONFLICT
  DateTimeColumn get createdAt => dateTime().withDefault(currentDateAndTime)();
  IntColumn get retryCount => integer().withDefault(const Constant(0))();
  TextColumn get tenantId => text()(); // Tenant isolation
  TextColumn get idempotencyKey => text().nullable()(); // Anti-duplicate
}

// DAO for Assets
@DriftAccessor(tables: [Assets])
class AssetDao extends DatabaseAccessor<AppDatabase> with _$AssetDaoMixin {
  AssetDao(AppDatabase db) : super(db);

  Future<List<AssetEntity>> getAllAssets(String tenantId) =>
      (select(assets)..where((t) => t.tenantId.equals(tenantId))).get();

  Stream<List<AssetEntity>> watchAllAssets(String tenantId) =>
      (select(assets)..where((t) => t.tenantId.equals(tenantId))).watch();

  Future<AssetEntity?> getAssetById(String id, [String? tenantId]) =>
      (select(assets)..where((t) {
            final cond = t.id.equals(id);
            if (tenantId != null && tenantId.isNotEmpty) {
              return cond & t.tenantId.equals(tenantId);
            }
            return cond;
          }))
          .getSingleOrNull();

  Future<AssetEntity?> getAssetByQrCode(String qrCode, String tenantId) =>
      (select(assets)..where(
            (t) =>
                t.qrCode.equals(qrCode) &
                t.tenantId.equals(tenantId) &
                t.isActive.equals(true),
          ))
          .getSingleOrNull();

  Future<void> insertOrUpdateAsset(AssetEntity asset) =>
      into(assets).insertOnConflictUpdate(asset);

  Future<void> insertAllAssets(List<AssetEntity> assetList) async {
    await batch((batch) {
      batch.insertAllOnConflictUpdate(assets, assetList);
    });
  }

  Future<int> deleteOrphanedAssets([String? tenantId]) async {
    final cutoff = DateTime.now().subtract(const Duration(days: 30));
    final referencedAssetIds = db.selectOnly(db.workOrders)
      ..addColumns([db.workOrders.assetId])
      ..where(db.workOrders.assetId.isNotNull());

    final query = delete(assets)
      ..where((a) {
        final cond =
            a.id.isNotInQuery(referencedAssetIds) &
            a.lastUpdated.isSmallerThanValue(cutoff);
        if (tenantId != null && tenantId.isNotEmpty) {
          return cond & a.tenantId.equals(tenantId);
        }
        return cond;
      });

    return await query.go();
  }
}

// DAO for WorkOrders
@DriftAccessor(tables: [WorkOrders])
class WorkOrderDao extends DatabaseAccessor<AppDatabase>
    with _$WorkOrderDaoMixin {
  WorkOrderDao(AppDatabase db) : super(db);

  Stream<List<WorkOrderEntity>> watchMyWorkOrders(
    String username,
    String tenantId,
  ) {
    return (select(workOrders)..where(
          (t) =>
              t.assigneeUsername.equals(username) & t.tenantId.equals(tenantId),
        ))
        .watch();
  }

  Future<List<WorkOrderEntity>> getMyWorkOrders(
    String username,
    String tenantId,
  ) {
    return (select(workOrders)..where(
          (t) =>
              t.assigneeUsername.equals(username) & t.tenantId.equals(tenantId),
        ))
        .get();
  }

  Future<WorkOrderEntity?> getWorkOrderById(String id, [String? tenantId]) =>
      (select(workOrders)..where((t) {
            final cond = t.id.equals(id);
            if (tenantId != null && tenantId.isNotEmpty) {
              return cond & t.tenantId.equals(tenantId);
            }
            return cond;
          }))
          .getSingleOrNull();

  Future<void> insertOrUpdateWorkOrder(WorkOrderEntity wo) =>
      into(workOrders).insertOnConflictUpdate(wo);

  Future<void> insertAllWorkOrders(List<WorkOrderEntity> woList) async {
    await batch((batch) {
      batch.insertAllOnConflictUpdate(workOrders, woList);
    });
  }

  Future<int> deleteStaleWorkOrders(
    List<String> validIds,
    String myUsername,
    String tenantId,
  ) {
    if (validIds.isEmpty) {
      return (delete(workOrders)..where(
            (t) =>
                t.assigneeUsername.equals(myUsername) &
                t.tenantId.equals(tenantId),
          ))
          .go();
    }
    return (delete(workOrders)..where(
          (t) =>
              t.id.isNotIn(validIds) &
              t.assigneeUsername.equals(myUsername) &
              t.tenantId.equals(tenantId),
        ))
        .go();
  }

  Future<int> deleteOldCompletedWorkOrders([String? tenantId]) async {
    final cutoff = DateTime.now().subtract(const Duration(days: 7));
    final query = delete(workOrders)
      ..where((wo) {
        final cond =
            wo.status.equals('COMPLETED') &
            wo.updatedAt.isSmallerThanValue(cutoff);
        if (tenantId != null && tenantId.isNotEmpty) {
          return cond & wo.tenantId.equals(tenantId);
        }
        return cond;
      });

    return await query.go();
  }
}

// DAO for SyncQueue
@DriftAccessor(tables: [SyncQueues])
class SyncQueueDao extends DatabaseAccessor<AppDatabase>
    with _$SyncQueueDaoMixin {
  SyncQueueDao(AppDatabase db) : super(db);

  Stream<List<SyncQueueEntity>> watchPendingSyncs([String? tenantId]) {
    return (select(syncQueues)..where((t) {
          final statusCond =
              t.status.equals('PENDING') |
              t.status.equals('FAILED') |
              t.status.equals('IN_PROGRESS') |
              t.status.equals('CONFLICT');
          if (tenantId != null && tenantId.isNotEmpty) {
            return statusCond & t.tenantId.equals(tenantId);
          }
          return statusCond;
        }))
        .watch();
  }

  Future<List<SyncQueueEntity>> getPendingSyncs([String? tenantId]) {
    return (select(syncQueues)
          ..where((t) {
            final cond =
                (t.status.equals('PENDING') | t.status.equals('IN_PROGRESS')) &
                t.retryCount.isSmallerThanValue(3);
            if (tenantId != null && tenantId.isNotEmpty) {
              return cond & t.tenantId.equals(tenantId);
            }
            return cond;
          })
          ..orderBy([(t) => OrderingTerm(expression: t.createdAt)]))
        .get();
  }

  Future<int> retryFailedTasks([String? tenantId]) {
    return (update(syncQueues)..where((t) {
          final cond = t.status.equals('FAILED');
          if (tenantId != null && tenantId.isNotEmpty) {
            return cond & t.tenantId.equals(tenantId);
          }
          return cond;
        }))
        .write(
          const SyncQueuesCompanion(
            status: Value('PENDING'),
            retryCount: Value(0),
          ),
        );
  }

  Future<int> addSyncTask(SyncQueuesCompanion entry) {
    return into(syncQueues).insert(entry);
  }

  Future<bool> updateSyncTask(SyncQueueEntity entry) {
    return update(syncQueues).replace(entry);
  }

  Future<int> deleteSyncTask(int id) {
    return (delete(syncQueues)..where((t) => t.id.equals(id))).go();
  }
}

@DriftDatabase(
  tables: [Assets, WorkOrders, SyncQueues],
  daos: [AssetDao, WorkOrderDao, SyncQueueDao],
)
class AppDatabase extends _$AppDatabase {
  static final AppDatabase instance = AppDatabase._internal();

  AppDatabase._internal() : super(_openConnection());
  AppDatabase.forTesting(super.e);

  @override
  int get schemaVersion => 6; // Incremented to 6 for code, maintenanceAction, coords, floor, zone

  @override
  MigrationStrategy get migration {
    return MigrationStrategy(
      onCreate: (Migrator m) async {
        await m.createAll();
      },
      onUpgrade: (Migrator m, int from, int to) async {
        if (from < 5) {
          // Add idempotencyKey to SyncQueues
          await m.addColumn(syncQueues, syncQueues.idempotencyKey);
        }
        if (from < 6) {
          await m.addColumn(workOrders, workOrders.code);
          await m.addColumn(workOrders, workOrders.maintenanceAction);
          await m.addColumn(workOrders, workOrders.coordsX);
          await m.addColumn(workOrders, workOrders.coordsY);
          await m.addColumn(workOrders, workOrders.floorLevel);
          await m.addColumn(workOrders, workOrders.zoneId);
        }
      },
    );
  }
}

LazyDatabase _openConnection() {
  return LazyDatabase(() async {
    final dbFolder = await getApplicationDocumentsDirectory();
    final file = File(p.join(dbFolder.path, 'eam_db.sqlite'));

    applyWorkaroundToOpenSqlite3OnOldAndroidVersions();

    return NativeDatabase.createInBackground(file);
  });
}

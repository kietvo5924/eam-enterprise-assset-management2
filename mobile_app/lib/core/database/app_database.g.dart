// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'app_database.dart';

// ignore_for_file: type=lint
mixin _$AssetDaoMixin on DatabaseAccessor<AppDatabase> {
  $AssetsTable get assets => attachedDatabase.assets;
  AssetDaoManager get managers => AssetDaoManager(this);
}

class AssetDaoManager {
  final _$AssetDaoMixin _db;
  AssetDaoManager(this._db);
  $$AssetsTableTableManager get assets =>
      $$AssetsTableTableManager(_db.attachedDatabase, _db.assets);
}

mixin _$WorkOrderDaoMixin on DatabaseAccessor<AppDatabase> {
  $WorkOrdersTable get workOrders => attachedDatabase.workOrders;
  WorkOrderDaoManager get managers => WorkOrderDaoManager(this);
}

class WorkOrderDaoManager {
  final _$WorkOrderDaoMixin _db;
  WorkOrderDaoManager(this._db);
  $$WorkOrdersTableTableManager get workOrders =>
      $$WorkOrdersTableTableManager(_db.attachedDatabase, _db.workOrders);
}

mixin _$SyncQueueDaoMixin on DatabaseAccessor<AppDatabase> {
  $SyncQueuesTable get syncQueues => attachedDatabase.syncQueues;
  SyncQueueDaoManager get managers => SyncQueueDaoManager(this);
}

class SyncQueueDaoManager {
  final _$SyncQueueDaoMixin _db;
  SyncQueueDaoManager(this._db);
  $$SyncQueuesTableTableManager get syncQueues =>
      $$SyncQueuesTableTableManager(_db.attachedDatabase, _db.syncQueues);
}

class $AssetsTable extends Assets with TableInfo<$AssetsTable, AssetEntity> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $AssetsTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _idMeta = const VerificationMeta('id');
  @override
  late final GeneratedColumn<String> id = GeneratedColumn<String>(
    'id',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _nameMeta = const VerificationMeta('name');
  @override
  late final GeneratedColumn<String> name = GeneratedColumn<String>(
    'name',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _qrCodeMeta = const VerificationMeta('qrCode');
  @override
  late final GeneratedColumn<String> qrCode = GeneratedColumn<String>(
    'qr_code',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _locationNameMeta = const VerificationMeta(
    'locationName',
  );
  @override
  late final GeneratedColumn<String> locationName = GeneratedColumn<String>(
    'location_name',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _tenantIdMeta = const VerificationMeta(
    'tenantId',
  );
  @override
  late final GeneratedColumn<String> tenantId = GeneratedColumn<String>(
    'tenant_id',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _isActiveMeta = const VerificationMeta(
    'isActive',
  );
  @override
  late final GeneratedColumn<bool> isActive = GeneratedColumn<bool>(
    'is_active',
    aliasedName,
    false,
    type: DriftSqlType.bool,
    requiredDuringInsert: false,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'CHECK ("is_active" IN (0, 1))',
    ),
    defaultValue: const Constant(true),
  );
  static const VerificationMeta _lastUpdatedMeta = const VerificationMeta(
    'lastUpdated',
  );
  @override
  late final GeneratedColumn<DateTime> lastUpdated = GeneratedColumn<DateTime>(
    'last_updated',
    aliasedName,
    false,
    type: DriftSqlType.dateTime,
    requiredDuringInsert: false,
    defaultValue: currentDateAndTime,
  );
  static const VerificationMeta _rawJsonMeta = const VerificationMeta(
    'rawJson',
  );
  @override
  late final GeneratedColumn<String> rawJson = GeneratedColumn<String>(
    'raw_json',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  @override
  List<GeneratedColumn> get $columns => [
    id,
    name,
    qrCode,
    locationName,
    tenantId,
    isActive,
    lastUpdated,
    rawJson,
  ];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'assets';
  @override
  VerificationContext validateIntegrity(
    Insertable<AssetEntity> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('id')) {
      context.handle(_idMeta, id.isAcceptableOrUnknown(data['id']!, _idMeta));
    } else if (isInserting) {
      context.missing(_idMeta);
    }
    if (data.containsKey('name')) {
      context.handle(
        _nameMeta,
        name.isAcceptableOrUnknown(data['name']!, _nameMeta),
      );
    } else if (isInserting) {
      context.missing(_nameMeta);
    }
    if (data.containsKey('qr_code')) {
      context.handle(
        _qrCodeMeta,
        qrCode.isAcceptableOrUnknown(data['qr_code']!, _qrCodeMeta),
      );
    }
    if (data.containsKey('location_name')) {
      context.handle(
        _locationNameMeta,
        locationName.isAcceptableOrUnknown(
          data['location_name']!,
          _locationNameMeta,
        ),
      );
    }
    if (data.containsKey('tenant_id')) {
      context.handle(
        _tenantIdMeta,
        tenantId.isAcceptableOrUnknown(data['tenant_id']!, _tenantIdMeta),
      );
    } else if (isInserting) {
      context.missing(_tenantIdMeta);
    }
    if (data.containsKey('is_active')) {
      context.handle(
        _isActiveMeta,
        isActive.isAcceptableOrUnknown(data['is_active']!, _isActiveMeta),
      );
    }
    if (data.containsKey('last_updated')) {
      context.handle(
        _lastUpdatedMeta,
        lastUpdated.isAcceptableOrUnknown(
          data['last_updated']!,
          _lastUpdatedMeta,
        ),
      );
    }
    if (data.containsKey('raw_json')) {
      context.handle(
        _rawJsonMeta,
        rawJson.isAcceptableOrUnknown(data['raw_json']!, _rawJsonMeta),
      );
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {id};
  @override
  AssetEntity map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return AssetEntity(
      id: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}id'],
      )!,
      name: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}name'],
      )!,
      qrCode: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}qr_code'],
      ),
      locationName: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}location_name'],
      ),
      tenantId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}tenant_id'],
      )!,
      isActive: attachedDatabase.typeMapping.read(
        DriftSqlType.bool,
        data['${effectivePrefix}is_active'],
      )!,
      lastUpdated: attachedDatabase.typeMapping.read(
        DriftSqlType.dateTime,
        data['${effectivePrefix}last_updated'],
      )!,
      rawJson: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}raw_json'],
      ),
    );
  }

  @override
  $AssetsTable createAlias(String alias) {
    return $AssetsTable(attachedDatabase, alias);
  }
}

class AssetEntity extends DataClass implements Insertable<AssetEntity> {
  final String id;
  final String name;
  final String? qrCode;
  final String? locationName;
  final String tenantId;
  final bool isActive;
  final DateTime lastUpdated;
  final String? rawJson;
  const AssetEntity({
    required this.id,
    required this.name,
    this.qrCode,
    this.locationName,
    required this.tenantId,
    required this.isActive,
    required this.lastUpdated,
    this.rawJson,
  });
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['id'] = Variable<String>(id);
    map['name'] = Variable<String>(name);
    if (!nullToAbsent || qrCode != null) {
      map['qr_code'] = Variable<String>(qrCode);
    }
    if (!nullToAbsent || locationName != null) {
      map['location_name'] = Variable<String>(locationName);
    }
    map['tenant_id'] = Variable<String>(tenantId);
    map['is_active'] = Variable<bool>(isActive);
    map['last_updated'] = Variable<DateTime>(lastUpdated);
    if (!nullToAbsent || rawJson != null) {
      map['raw_json'] = Variable<String>(rawJson);
    }
    return map;
  }

  AssetsCompanion toCompanion(bool nullToAbsent) {
    return AssetsCompanion(
      id: Value(id),
      name: Value(name),
      qrCode: qrCode == null && nullToAbsent
          ? const Value.absent()
          : Value(qrCode),
      locationName: locationName == null && nullToAbsent
          ? const Value.absent()
          : Value(locationName),
      tenantId: Value(tenantId),
      isActive: Value(isActive),
      lastUpdated: Value(lastUpdated),
      rawJson: rawJson == null && nullToAbsent
          ? const Value.absent()
          : Value(rawJson),
    );
  }

  factory AssetEntity.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return AssetEntity(
      id: serializer.fromJson<String>(json['id']),
      name: serializer.fromJson<String>(json['name']),
      qrCode: serializer.fromJson<String?>(json['qrCode']),
      locationName: serializer.fromJson<String?>(json['locationName']),
      tenantId: serializer.fromJson<String>(json['tenantId']),
      isActive: serializer.fromJson<bool>(json['isActive']),
      lastUpdated: serializer.fromJson<DateTime>(json['lastUpdated']),
      rawJson: serializer.fromJson<String?>(json['rawJson']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'id': serializer.toJson<String>(id),
      'name': serializer.toJson<String>(name),
      'qrCode': serializer.toJson<String?>(qrCode),
      'locationName': serializer.toJson<String?>(locationName),
      'tenantId': serializer.toJson<String>(tenantId),
      'isActive': serializer.toJson<bool>(isActive),
      'lastUpdated': serializer.toJson<DateTime>(lastUpdated),
      'rawJson': serializer.toJson<String?>(rawJson),
    };
  }

  AssetEntity copyWith({
    String? id,
    String? name,
    Value<String?> qrCode = const Value.absent(),
    Value<String?> locationName = const Value.absent(),
    String? tenantId,
    bool? isActive,
    DateTime? lastUpdated,
    Value<String?> rawJson = const Value.absent(),
  }) => AssetEntity(
    id: id ?? this.id,
    name: name ?? this.name,
    qrCode: qrCode.present ? qrCode.value : this.qrCode,
    locationName: locationName.present ? locationName.value : this.locationName,
    tenantId: tenantId ?? this.tenantId,
    isActive: isActive ?? this.isActive,
    lastUpdated: lastUpdated ?? this.lastUpdated,
    rawJson: rawJson.present ? rawJson.value : this.rawJson,
  );
  AssetEntity copyWithCompanion(AssetsCompanion data) {
    return AssetEntity(
      id: data.id.present ? data.id.value : this.id,
      name: data.name.present ? data.name.value : this.name,
      qrCode: data.qrCode.present ? data.qrCode.value : this.qrCode,
      locationName: data.locationName.present
          ? data.locationName.value
          : this.locationName,
      tenantId: data.tenantId.present ? data.tenantId.value : this.tenantId,
      isActive: data.isActive.present ? data.isActive.value : this.isActive,
      lastUpdated: data.lastUpdated.present
          ? data.lastUpdated.value
          : this.lastUpdated,
      rawJson: data.rawJson.present ? data.rawJson.value : this.rawJson,
    );
  }

  @override
  String toString() {
    return (StringBuffer('AssetEntity(')
          ..write('id: $id, ')
          ..write('name: $name, ')
          ..write('qrCode: $qrCode, ')
          ..write('locationName: $locationName, ')
          ..write('tenantId: $tenantId, ')
          ..write('isActive: $isActive, ')
          ..write('lastUpdated: $lastUpdated, ')
          ..write('rawJson: $rawJson')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(
    id,
    name,
    qrCode,
    locationName,
    tenantId,
    isActive,
    lastUpdated,
    rawJson,
  );
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is AssetEntity &&
          other.id == this.id &&
          other.name == this.name &&
          other.qrCode == this.qrCode &&
          other.locationName == this.locationName &&
          other.tenantId == this.tenantId &&
          other.isActive == this.isActive &&
          other.lastUpdated == this.lastUpdated &&
          other.rawJson == this.rawJson);
}

class AssetsCompanion extends UpdateCompanion<AssetEntity> {
  final Value<String> id;
  final Value<String> name;
  final Value<String?> qrCode;
  final Value<String?> locationName;
  final Value<String> tenantId;
  final Value<bool> isActive;
  final Value<DateTime> lastUpdated;
  final Value<String?> rawJson;
  final Value<int> rowid;
  const AssetsCompanion({
    this.id = const Value.absent(),
    this.name = const Value.absent(),
    this.qrCode = const Value.absent(),
    this.locationName = const Value.absent(),
    this.tenantId = const Value.absent(),
    this.isActive = const Value.absent(),
    this.lastUpdated = const Value.absent(),
    this.rawJson = const Value.absent(),
    this.rowid = const Value.absent(),
  });
  AssetsCompanion.insert({
    required String id,
    required String name,
    this.qrCode = const Value.absent(),
    this.locationName = const Value.absent(),
    required String tenantId,
    this.isActive = const Value.absent(),
    this.lastUpdated = const Value.absent(),
    this.rawJson = const Value.absent(),
    this.rowid = const Value.absent(),
  }) : id = Value(id),
       name = Value(name),
       tenantId = Value(tenantId);
  static Insertable<AssetEntity> custom({
    Expression<String>? id,
    Expression<String>? name,
    Expression<String>? qrCode,
    Expression<String>? locationName,
    Expression<String>? tenantId,
    Expression<bool>? isActive,
    Expression<DateTime>? lastUpdated,
    Expression<String>? rawJson,
    Expression<int>? rowid,
  }) {
    return RawValuesInsertable({
      if (id != null) 'id': id,
      if (name != null) 'name': name,
      if (qrCode != null) 'qr_code': qrCode,
      if (locationName != null) 'location_name': locationName,
      if (tenantId != null) 'tenant_id': tenantId,
      if (isActive != null) 'is_active': isActive,
      if (lastUpdated != null) 'last_updated': lastUpdated,
      if (rawJson != null) 'raw_json': rawJson,
      if (rowid != null) 'rowid': rowid,
    });
  }

  AssetsCompanion copyWith({
    Value<String>? id,
    Value<String>? name,
    Value<String?>? qrCode,
    Value<String?>? locationName,
    Value<String>? tenantId,
    Value<bool>? isActive,
    Value<DateTime>? lastUpdated,
    Value<String?>? rawJson,
    Value<int>? rowid,
  }) {
    return AssetsCompanion(
      id: id ?? this.id,
      name: name ?? this.name,
      qrCode: qrCode ?? this.qrCode,
      locationName: locationName ?? this.locationName,
      tenantId: tenantId ?? this.tenantId,
      isActive: isActive ?? this.isActive,
      lastUpdated: lastUpdated ?? this.lastUpdated,
      rawJson: rawJson ?? this.rawJson,
      rowid: rowid ?? this.rowid,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (id.present) {
      map['id'] = Variable<String>(id.value);
    }
    if (name.present) {
      map['name'] = Variable<String>(name.value);
    }
    if (qrCode.present) {
      map['qr_code'] = Variable<String>(qrCode.value);
    }
    if (locationName.present) {
      map['location_name'] = Variable<String>(locationName.value);
    }
    if (tenantId.present) {
      map['tenant_id'] = Variable<String>(tenantId.value);
    }
    if (isActive.present) {
      map['is_active'] = Variable<bool>(isActive.value);
    }
    if (lastUpdated.present) {
      map['last_updated'] = Variable<DateTime>(lastUpdated.value);
    }
    if (rawJson.present) {
      map['raw_json'] = Variable<String>(rawJson.value);
    }
    if (rowid.present) {
      map['rowid'] = Variable<int>(rowid.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('AssetsCompanion(')
          ..write('id: $id, ')
          ..write('name: $name, ')
          ..write('qrCode: $qrCode, ')
          ..write('locationName: $locationName, ')
          ..write('tenantId: $tenantId, ')
          ..write('isActive: $isActive, ')
          ..write('lastUpdated: $lastUpdated, ')
          ..write('rawJson: $rawJson, ')
          ..write('rowid: $rowid')
          ..write(')'))
        .toString();
  }
}

class $WorkOrdersTable extends WorkOrders
    with TableInfo<$WorkOrdersTable, WorkOrderEntity> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $WorkOrdersTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _idMeta = const VerificationMeta('id');
  @override
  late final GeneratedColumn<String> id = GeneratedColumn<String>(
    'id',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _titleMeta = const VerificationMeta('title');
  @override
  late final GeneratedColumn<String> title = GeneratedColumn<String>(
    'title',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _descriptionMeta = const VerificationMeta(
    'description',
  );
  @override
  late final GeneratedColumn<String> description = GeneratedColumn<String>(
    'description',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _statusMeta = const VerificationMeta('status');
  @override
  late final GeneratedColumn<String> status = GeneratedColumn<String>(
    'status',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _priorityMeta = const VerificationMeta(
    'priority',
  );
  @override
  late final GeneratedColumn<String> priority = GeneratedColumn<String>(
    'priority',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _assetIdMeta = const VerificationMeta(
    'assetId',
  );
  @override
  late final GeneratedColumn<String> assetId = GeneratedColumn<String>(
    'asset_id',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _assetNameMeta = const VerificationMeta(
    'assetName',
  );
  @override
  late final GeneratedColumn<String> assetName = GeneratedColumn<String>(
    'asset_name',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _assetLocationMeta = const VerificationMeta(
    'assetLocation',
  );
  @override
  late final GeneratedColumn<String> assetLocation = GeneratedColumn<String>(
    'asset_location',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _deadlineMeta = const VerificationMeta(
    'deadline',
  );
  @override
  late final GeneratedColumn<DateTime> deadline = GeneratedColumn<DateTime>(
    'deadline',
    aliasedName,
    true,
    type: DriftSqlType.dateTime,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _updatedAtMeta = const VerificationMeta(
    'updatedAt',
  );
  @override
  late final GeneratedColumn<DateTime> updatedAt = GeneratedColumn<DateTime>(
    'updated_at',
    aliasedName,
    true,
    type: DriftSqlType.dateTime,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _assigneeUsernameMeta = const VerificationMeta(
    'assigneeUsername',
  );
  @override
  late final GeneratedColumn<String> assigneeUsername = GeneratedColumn<String>(
    'assignee_username',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _resolutionNotesMeta = const VerificationMeta(
    'resolutionNotes',
  );
  @override
  late final GeneratedColumn<String> resolutionNotes = GeneratedColumn<String>(
    'resolution_notes',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  @override
  late final GeneratedColumnWithTypeConverter<List<dynamic>, String>
  checklists = GeneratedColumn<String>(
    'checklists',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
    defaultValue: const Constant('[]'),
  ).withConverter<List<dynamic>>($WorkOrdersTable.$converterchecklists);
  @override
  late final GeneratedColumnWithTypeConverter<List<dynamic>, String>
  attachments = GeneratedColumn<String>(
    'attachments',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
    defaultValue: const Constant('[]'),
  ).withConverter<List<dynamic>>($WorkOrdersTable.$converterattachments);
  static const VerificationMeta _tenantIdMeta = const VerificationMeta(
    'tenantId',
  );
  @override
  late final GeneratedColumn<String> tenantId = GeneratedColumn<String>(
    'tenant_id',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  @override
  List<GeneratedColumn> get $columns => [
    id,
    title,
    description,
    status,
    priority,
    assetId,
    assetName,
    assetLocation,
    deadline,
    updatedAt,
    assigneeUsername,
    resolutionNotes,
    checklists,
    attachments,
    tenantId,
  ];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'work_orders';
  @override
  VerificationContext validateIntegrity(
    Insertable<WorkOrderEntity> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('id')) {
      context.handle(_idMeta, id.isAcceptableOrUnknown(data['id']!, _idMeta));
    } else if (isInserting) {
      context.missing(_idMeta);
    }
    if (data.containsKey('title')) {
      context.handle(
        _titleMeta,
        title.isAcceptableOrUnknown(data['title']!, _titleMeta),
      );
    } else if (isInserting) {
      context.missing(_titleMeta);
    }
    if (data.containsKey('description')) {
      context.handle(
        _descriptionMeta,
        description.isAcceptableOrUnknown(
          data['description']!,
          _descriptionMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_descriptionMeta);
    }
    if (data.containsKey('status')) {
      context.handle(
        _statusMeta,
        status.isAcceptableOrUnknown(data['status']!, _statusMeta),
      );
    } else if (isInserting) {
      context.missing(_statusMeta);
    }
    if (data.containsKey('priority')) {
      context.handle(
        _priorityMeta,
        priority.isAcceptableOrUnknown(data['priority']!, _priorityMeta),
      );
    }
    if (data.containsKey('asset_id')) {
      context.handle(
        _assetIdMeta,
        assetId.isAcceptableOrUnknown(data['asset_id']!, _assetIdMeta),
      );
    }
    if (data.containsKey('asset_name')) {
      context.handle(
        _assetNameMeta,
        assetName.isAcceptableOrUnknown(data['asset_name']!, _assetNameMeta),
      );
    }
    if (data.containsKey('asset_location')) {
      context.handle(
        _assetLocationMeta,
        assetLocation.isAcceptableOrUnknown(
          data['asset_location']!,
          _assetLocationMeta,
        ),
      );
    }
    if (data.containsKey('deadline')) {
      context.handle(
        _deadlineMeta,
        deadline.isAcceptableOrUnknown(data['deadline']!, _deadlineMeta),
      );
    }
    if (data.containsKey('updated_at')) {
      context.handle(
        _updatedAtMeta,
        updatedAt.isAcceptableOrUnknown(data['updated_at']!, _updatedAtMeta),
      );
    }
    if (data.containsKey('assignee_username')) {
      context.handle(
        _assigneeUsernameMeta,
        assigneeUsername.isAcceptableOrUnknown(
          data['assignee_username']!,
          _assigneeUsernameMeta,
        ),
      );
    }
    if (data.containsKey('resolution_notes')) {
      context.handle(
        _resolutionNotesMeta,
        resolutionNotes.isAcceptableOrUnknown(
          data['resolution_notes']!,
          _resolutionNotesMeta,
        ),
      );
    }
    if (data.containsKey('tenant_id')) {
      context.handle(
        _tenantIdMeta,
        tenantId.isAcceptableOrUnknown(data['tenant_id']!, _tenantIdMeta),
      );
    } else if (isInserting) {
      context.missing(_tenantIdMeta);
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {id};
  @override
  WorkOrderEntity map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return WorkOrderEntity(
      id: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}id'],
      )!,
      title: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}title'],
      )!,
      description: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}description'],
      )!,
      status: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}status'],
      )!,
      priority: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}priority'],
      ),
      assetId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}asset_id'],
      ),
      assetName: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}asset_name'],
      ),
      assetLocation: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}asset_location'],
      ),
      deadline: attachedDatabase.typeMapping.read(
        DriftSqlType.dateTime,
        data['${effectivePrefix}deadline'],
      ),
      updatedAt: attachedDatabase.typeMapping.read(
        DriftSqlType.dateTime,
        data['${effectivePrefix}updated_at'],
      ),
      assigneeUsername: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}assignee_username'],
      ),
      resolutionNotes: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}resolution_notes'],
      ),
      checklists: $WorkOrdersTable.$converterchecklists.fromSql(
        attachedDatabase.typeMapping.read(
          DriftSqlType.string,
          data['${effectivePrefix}checklists'],
        )!,
      ),
      attachments: $WorkOrdersTable.$converterattachments.fromSql(
        attachedDatabase.typeMapping.read(
          DriftSqlType.string,
          data['${effectivePrefix}attachments'],
        )!,
      ),
      tenantId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}tenant_id'],
      )!,
    );
  }

  @override
  $WorkOrdersTable createAlias(String alias) {
    return $WorkOrdersTable(attachedDatabase, alias);
  }

  static TypeConverter<List<dynamic>, String> $converterchecklists =
      const ChecklistConverter();
  static TypeConverter<List<dynamic>, String> $converterattachments =
      const ChecklistConverter();
}

class WorkOrderEntity extends DataClass implements Insertable<WorkOrderEntity> {
  final String id;
  final String title;
  final String description;
  final String status;
  final String? priority;
  final String? assetId;
  final String? assetName;
  final String? assetLocation;
  final DateTime? deadline;
  final DateTime? updatedAt;
  final String? assigneeUsername;
  final String? resolutionNotes;
  final List<dynamic> checklists;
  final List<dynamic> attachments;
  final String tenantId;
  const WorkOrderEntity({
    required this.id,
    required this.title,
    required this.description,
    required this.status,
    this.priority,
    this.assetId,
    this.assetName,
    this.assetLocation,
    this.deadline,
    this.updatedAt,
    this.assigneeUsername,
    this.resolutionNotes,
    required this.checklists,
    required this.attachments,
    required this.tenantId,
  });
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['id'] = Variable<String>(id);
    map['title'] = Variable<String>(title);
    map['description'] = Variable<String>(description);
    map['status'] = Variable<String>(status);
    if (!nullToAbsent || priority != null) {
      map['priority'] = Variable<String>(priority);
    }
    if (!nullToAbsent || assetId != null) {
      map['asset_id'] = Variable<String>(assetId);
    }
    if (!nullToAbsent || assetName != null) {
      map['asset_name'] = Variable<String>(assetName);
    }
    if (!nullToAbsent || assetLocation != null) {
      map['asset_location'] = Variable<String>(assetLocation);
    }
    if (!nullToAbsent || deadline != null) {
      map['deadline'] = Variable<DateTime>(deadline);
    }
    if (!nullToAbsent || updatedAt != null) {
      map['updated_at'] = Variable<DateTime>(updatedAt);
    }
    if (!nullToAbsent || assigneeUsername != null) {
      map['assignee_username'] = Variable<String>(assigneeUsername);
    }
    if (!nullToAbsent || resolutionNotes != null) {
      map['resolution_notes'] = Variable<String>(resolutionNotes);
    }
    {
      map['checklists'] = Variable<String>(
        $WorkOrdersTable.$converterchecklists.toSql(checklists),
      );
    }
    {
      map['attachments'] = Variable<String>(
        $WorkOrdersTable.$converterattachments.toSql(attachments),
      );
    }
    map['tenant_id'] = Variable<String>(tenantId);
    return map;
  }

  WorkOrdersCompanion toCompanion(bool nullToAbsent) {
    return WorkOrdersCompanion(
      id: Value(id),
      title: Value(title),
      description: Value(description),
      status: Value(status),
      priority: priority == null && nullToAbsent
          ? const Value.absent()
          : Value(priority),
      assetId: assetId == null && nullToAbsent
          ? const Value.absent()
          : Value(assetId),
      assetName: assetName == null && nullToAbsent
          ? const Value.absent()
          : Value(assetName),
      assetLocation: assetLocation == null && nullToAbsent
          ? const Value.absent()
          : Value(assetLocation),
      deadline: deadline == null && nullToAbsent
          ? const Value.absent()
          : Value(deadline),
      updatedAt: updatedAt == null && nullToAbsent
          ? const Value.absent()
          : Value(updatedAt),
      assigneeUsername: assigneeUsername == null && nullToAbsent
          ? const Value.absent()
          : Value(assigneeUsername),
      resolutionNotes: resolutionNotes == null && nullToAbsent
          ? const Value.absent()
          : Value(resolutionNotes),
      checklists: Value(checklists),
      attachments: Value(attachments),
      tenantId: Value(tenantId),
    );
  }

  factory WorkOrderEntity.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return WorkOrderEntity(
      id: serializer.fromJson<String>(json['id']),
      title: serializer.fromJson<String>(json['title']),
      description: serializer.fromJson<String>(json['description']),
      status: serializer.fromJson<String>(json['status']),
      priority: serializer.fromJson<String?>(json['priority']),
      assetId: serializer.fromJson<String?>(json['assetId']),
      assetName: serializer.fromJson<String?>(json['assetName']),
      assetLocation: serializer.fromJson<String?>(json['assetLocation']),
      deadline: serializer.fromJson<DateTime?>(json['deadline']),
      updatedAt: serializer.fromJson<DateTime?>(json['updatedAt']),
      assigneeUsername: serializer.fromJson<String?>(json['assigneeUsername']),
      resolutionNotes: serializer.fromJson<String?>(json['resolutionNotes']),
      checklists: serializer.fromJson<List<dynamic>>(json['checklists']),
      attachments: serializer.fromJson<List<dynamic>>(json['attachments']),
      tenantId: serializer.fromJson<String>(json['tenantId']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'id': serializer.toJson<String>(id),
      'title': serializer.toJson<String>(title),
      'description': serializer.toJson<String>(description),
      'status': serializer.toJson<String>(status),
      'priority': serializer.toJson<String?>(priority),
      'assetId': serializer.toJson<String?>(assetId),
      'assetName': serializer.toJson<String?>(assetName),
      'assetLocation': serializer.toJson<String?>(assetLocation),
      'deadline': serializer.toJson<DateTime?>(deadline),
      'updatedAt': serializer.toJson<DateTime?>(updatedAt),
      'assigneeUsername': serializer.toJson<String?>(assigneeUsername),
      'resolutionNotes': serializer.toJson<String?>(resolutionNotes),
      'checklists': serializer.toJson<List<dynamic>>(checklists),
      'attachments': serializer.toJson<List<dynamic>>(attachments),
      'tenantId': serializer.toJson<String>(tenantId),
    };
  }

  WorkOrderEntity copyWith({
    String? id,
    String? title,
    String? description,
    String? status,
    Value<String?> priority = const Value.absent(),
    Value<String?> assetId = const Value.absent(),
    Value<String?> assetName = const Value.absent(),
    Value<String?> assetLocation = const Value.absent(),
    Value<DateTime?> deadline = const Value.absent(),
    Value<DateTime?> updatedAt = const Value.absent(),
    Value<String?> assigneeUsername = const Value.absent(),
    Value<String?> resolutionNotes = const Value.absent(),
    List<dynamic>? checklists,
    List<dynamic>? attachments,
    String? tenantId,
  }) => WorkOrderEntity(
    id: id ?? this.id,
    title: title ?? this.title,
    description: description ?? this.description,
    status: status ?? this.status,
    priority: priority.present ? priority.value : this.priority,
    assetId: assetId.present ? assetId.value : this.assetId,
    assetName: assetName.present ? assetName.value : this.assetName,
    assetLocation: assetLocation.present
        ? assetLocation.value
        : this.assetLocation,
    deadline: deadline.present ? deadline.value : this.deadline,
    updatedAt: updatedAt.present ? updatedAt.value : this.updatedAt,
    assigneeUsername: assigneeUsername.present
        ? assigneeUsername.value
        : this.assigneeUsername,
    resolutionNotes: resolutionNotes.present
        ? resolutionNotes.value
        : this.resolutionNotes,
    checklists: checklists ?? this.checklists,
    attachments: attachments ?? this.attachments,
    tenantId: tenantId ?? this.tenantId,
  );
  WorkOrderEntity copyWithCompanion(WorkOrdersCompanion data) {
    return WorkOrderEntity(
      id: data.id.present ? data.id.value : this.id,
      title: data.title.present ? data.title.value : this.title,
      description: data.description.present
          ? data.description.value
          : this.description,
      status: data.status.present ? data.status.value : this.status,
      priority: data.priority.present ? data.priority.value : this.priority,
      assetId: data.assetId.present ? data.assetId.value : this.assetId,
      assetName: data.assetName.present ? data.assetName.value : this.assetName,
      assetLocation: data.assetLocation.present
          ? data.assetLocation.value
          : this.assetLocation,
      deadline: data.deadline.present ? data.deadline.value : this.deadline,
      updatedAt: data.updatedAt.present ? data.updatedAt.value : this.updatedAt,
      assigneeUsername: data.assigneeUsername.present
          ? data.assigneeUsername.value
          : this.assigneeUsername,
      resolutionNotes: data.resolutionNotes.present
          ? data.resolutionNotes.value
          : this.resolutionNotes,
      checklists: data.checklists.present
          ? data.checklists.value
          : this.checklists,
      attachments: data.attachments.present
          ? data.attachments.value
          : this.attachments,
      tenantId: data.tenantId.present ? data.tenantId.value : this.tenantId,
    );
  }

  @override
  String toString() {
    return (StringBuffer('WorkOrderEntity(')
          ..write('id: $id, ')
          ..write('title: $title, ')
          ..write('description: $description, ')
          ..write('status: $status, ')
          ..write('priority: $priority, ')
          ..write('assetId: $assetId, ')
          ..write('assetName: $assetName, ')
          ..write('assetLocation: $assetLocation, ')
          ..write('deadline: $deadline, ')
          ..write('updatedAt: $updatedAt, ')
          ..write('assigneeUsername: $assigneeUsername, ')
          ..write('resolutionNotes: $resolutionNotes, ')
          ..write('checklists: $checklists, ')
          ..write('attachments: $attachments, ')
          ..write('tenantId: $tenantId')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(
    id,
    title,
    description,
    status,
    priority,
    assetId,
    assetName,
    assetLocation,
    deadline,
    updatedAt,
    assigneeUsername,
    resolutionNotes,
    checklists,
    attachments,
    tenantId,
  );
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is WorkOrderEntity &&
          other.id == this.id &&
          other.title == this.title &&
          other.description == this.description &&
          other.status == this.status &&
          other.priority == this.priority &&
          other.assetId == this.assetId &&
          other.assetName == this.assetName &&
          other.assetLocation == this.assetLocation &&
          other.deadline == this.deadline &&
          other.updatedAt == this.updatedAt &&
          other.assigneeUsername == this.assigneeUsername &&
          other.resolutionNotes == this.resolutionNotes &&
          other.checklists == this.checklists &&
          other.attachments == this.attachments &&
          other.tenantId == this.tenantId);
}

class WorkOrdersCompanion extends UpdateCompanion<WorkOrderEntity> {
  final Value<String> id;
  final Value<String> title;
  final Value<String> description;
  final Value<String> status;
  final Value<String?> priority;
  final Value<String?> assetId;
  final Value<String?> assetName;
  final Value<String?> assetLocation;
  final Value<DateTime?> deadline;
  final Value<DateTime?> updatedAt;
  final Value<String?> assigneeUsername;
  final Value<String?> resolutionNotes;
  final Value<List<dynamic>> checklists;
  final Value<List<dynamic>> attachments;
  final Value<String> tenantId;
  final Value<int> rowid;
  const WorkOrdersCompanion({
    this.id = const Value.absent(),
    this.title = const Value.absent(),
    this.description = const Value.absent(),
    this.status = const Value.absent(),
    this.priority = const Value.absent(),
    this.assetId = const Value.absent(),
    this.assetName = const Value.absent(),
    this.assetLocation = const Value.absent(),
    this.deadline = const Value.absent(),
    this.updatedAt = const Value.absent(),
    this.assigneeUsername = const Value.absent(),
    this.resolutionNotes = const Value.absent(),
    this.checklists = const Value.absent(),
    this.attachments = const Value.absent(),
    this.tenantId = const Value.absent(),
    this.rowid = const Value.absent(),
  });
  WorkOrdersCompanion.insert({
    required String id,
    required String title,
    required String description,
    required String status,
    this.priority = const Value.absent(),
    this.assetId = const Value.absent(),
    this.assetName = const Value.absent(),
    this.assetLocation = const Value.absent(),
    this.deadline = const Value.absent(),
    this.updatedAt = const Value.absent(),
    this.assigneeUsername = const Value.absent(),
    this.resolutionNotes = const Value.absent(),
    this.checklists = const Value.absent(),
    this.attachments = const Value.absent(),
    required String tenantId,
    this.rowid = const Value.absent(),
  }) : id = Value(id),
       title = Value(title),
       description = Value(description),
       status = Value(status),
       tenantId = Value(tenantId);
  static Insertable<WorkOrderEntity> custom({
    Expression<String>? id,
    Expression<String>? title,
    Expression<String>? description,
    Expression<String>? status,
    Expression<String>? priority,
    Expression<String>? assetId,
    Expression<String>? assetName,
    Expression<String>? assetLocation,
    Expression<DateTime>? deadline,
    Expression<DateTime>? updatedAt,
    Expression<String>? assigneeUsername,
    Expression<String>? resolutionNotes,
    Expression<String>? checklists,
    Expression<String>? attachments,
    Expression<String>? tenantId,
    Expression<int>? rowid,
  }) {
    return RawValuesInsertable({
      if (id != null) 'id': id,
      if (title != null) 'title': title,
      if (description != null) 'description': description,
      if (status != null) 'status': status,
      if (priority != null) 'priority': priority,
      if (assetId != null) 'asset_id': assetId,
      if (assetName != null) 'asset_name': assetName,
      if (assetLocation != null) 'asset_location': assetLocation,
      if (deadline != null) 'deadline': deadline,
      if (updatedAt != null) 'updated_at': updatedAt,
      if (assigneeUsername != null) 'assignee_username': assigneeUsername,
      if (resolutionNotes != null) 'resolution_notes': resolutionNotes,
      if (checklists != null) 'checklists': checklists,
      if (attachments != null) 'attachments': attachments,
      if (tenantId != null) 'tenant_id': tenantId,
      if (rowid != null) 'rowid': rowid,
    });
  }

  WorkOrdersCompanion copyWith({
    Value<String>? id,
    Value<String>? title,
    Value<String>? description,
    Value<String>? status,
    Value<String?>? priority,
    Value<String?>? assetId,
    Value<String?>? assetName,
    Value<String?>? assetLocation,
    Value<DateTime?>? deadline,
    Value<DateTime?>? updatedAt,
    Value<String?>? assigneeUsername,
    Value<String?>? resolutionNotes,
    Value<List<dynamic>>? checklists,
    Value<List<dynamic>>? attachments,
    Value<String>? tenantId,
    Value<int>? rowid,
  }) {
    return WorkOrdersCompanion(
      id: id ?? this.id,
      title: title ?? this.title,
      description: description ?? this.description,
      status: status ?? this.status,
      priority: priority ?? this.priority,
      assetId: assetId ?? this.assetId,
      assetName: assetName ?? this.assetName,
      assetLocation: assetLocation ?? this.assetLocation,
      deadline: deadline ?? this.deadline,
      updatedAt: updatedAt ?? this.updatedAt,
      assigneeUsername: assigneeUsername ?? this.assigneeUsername,
      resolutionNotes: resolutionNotes ?? this.resolutionNotes,
      checklists: checklists ?? this.checklists,
      attachments: attachments ?? this.attachments,
      tenantId: tenantId ?? this.tenantId,
      rowid: rowid ?? this.rowid,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (id.present) {
      map['id'] = Variable<String>(id.value);
    }
    if (title.present) {
      map['title'] = Variable<String>(title.value);
    }
    if (description.present) {
      map['description'] = Variable<String>(description.value);
    }
    if (status.present) {
      map['status'] = Variable<String>(status.value);
    }
    if (priority.present) {
      map['priority'] = Variable<String>(priority.value);
    }
    if (assetId.present) {
      map['asset_id'] = Variable<String>(assetId.value);
    }
    if (assetName.present) {
      map['asset_name'] = Variable<String>(assetName.value);
    }
    if (assetLocation.present) {
      map['asset_location'] = Variable<String>(assetLocation.value);
    }
    if (deadline.present) {
      map['deadline'] = Variable<DateTime>(deadline.value);
    }
    if (updatedAt.present) {
      map['updated_at'] = Variable<DateTime>(updatedAt.value);
    }
    if (assigneeUsername.present) {
      map['assignee_username'] = Variable<String>(assigneeUsername.value);
    }
    if (resolutionNotes.present) {
      map['resolution_notes'] = Variable<String>(resolutionNotes.value);
    }
    if (checklists.present) {
      map['checklists'] = Variable<String>(
        $WorkOrdersTable.$converterchecklists.toSql(checklists.value),
      );
    }
    if (attachments.present) {
      map['attachments'] = Variable<String>(
        $WorkOrdersTable.$converterattachments.toSql(attachments.value),
      );
    }
    if (tenantId.present) {
      map['tenant_id'] = Variable<String>(tenantId.value);
    }
    if (rowid.present) {
      map['rowid'] = Variable<int>(rowid.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('WorkOrdersCompanion(')
          ..write('id: $id, ')
          ..write('title: $title, ')
          ..write('description: $description, ')
          ..write('status: $status, ')
          ..write('priority: $priority, ')
          ..write('assetId: $assetId, ')
          ..write('assetName: $assetName, ')
          ..write('assetLocation: $assetLocation, ')
          ..write('deadline: $deadline, ')
          ..write('updatedAt: $updatedAt, ')
          ..write('assigneeUsername: $assigneeUsername, ')
          ..write('resolutionNotes: $resolutionNotes, ')
          ..write('checklists: $checklists, ')
          ..write('attachments: $attachments, ')
          ..write('tenantId: $tenantId, ')
          ..write('rowid: $rowid')
          ..write(')'))
        .toString();
  }
}

class $SyncQueuesTable extends SyncQueues
    with TableInfo<$SyncQueuesTable, SyncQueueEntity> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $SyncQueuesTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _idMeta = const VerificationMeta('id');
  @override
  late final GeneratedColumn<int> id = GeneratedColumn<int>(
    'id',
    aliasedName,
    false,
    hasAutoIncrement: true,
    type: DriftSqlType.int,
    requiredDuringInsert: false,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'PRIMARY KEY AUTOINCREMENT',
    ),
  );
  static const VerificationMeta _actionTypeMeta = const VerificationMeta(
    'actionType',
  );
  @override
  late final GeneratedColumn<String> actionType = GeneratedColumn<String>(
    'action_type',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _payloadMeta = const VerificationMeta(
    'payload',
  );
  @override
  late final GeneratedColumn<String> payload = GeneratedColumn<String>(
    'payload',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _statusMeta = const VerificationMeta('status');
  @override
  late final GeneratedColumn<String> status = GeneratedColumn<String>(
    'status',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
    defaultValue: const Constant('PENDING'),
  );
  static const VerificationMeta _createdAtMeta = const VerificationMeta(
    'createdAt',
  );
  @override
  late final GeneratedColumn<DateTime> createdAt = GeneratedColumn<DateTime>(
    'created_at',
    aliasedName,
    false,
    type: DriftSqlType.dateTime,
    requiredDuringInsert: false,
    defaultValue: currentDateAndTime,
  );
  static const VerificationMeta _retryCountMeta = const VerificationMeta(
    'retryCount',
  );
  @override
  late final GeneratedColumn<int> retryCount = GeneratedColumn<int>(
    'retry_count',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: false,
    defaultValue: const Constant(0),
  );
  static const VerificationMeta _tenantIdMeta = const VerificationMeta(
    'tenantId',
  );
  @override
  late final GeneratedColumn<String> tenantId = GeneratedColumn<String>(
    'tenant_id',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _idempotencyKeyMeta = const VerificationMeta(
    'idempotencyKey',
  );
  @override
  late final GeneratedColumn<String> idempotencyKey = GeneratedColumn<String>(
    'idempotency_key',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  @override
  List<GeneratedColumn> get $columns => [
    id,
    actionType,
    payload,
    status,
    createdAt,
    retryCount,
    tenantId,
    idempotencyKey,
  ];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'sync_queues';
  @override
  VerificationContext validateIntegrity(
    Insertable<SyncQueueEntity> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('id')) {
      context.handle(_idMeta, id.isAcceptableOrUnknown(data['id']!, _idMeta));
    }
    if (data.containsKey('action_type')) {
      context.handle(
        _actionTypeMeta,
        actionType.isAcceptableOrUnknown(data['action_type']!, _actionTypeMeta),
      );
    } else if (isInserting) {
      context.missing(_actionTypeMeta);
    }
    if (data.containsKey('payload')) {
      context.handle(
        _payloadMeta,
        payload.isAcceptableOrUnknown(data['payload']!, _payloadMeta),
      );
    } else if (isInserting) {
      context.missing(_payloadMeta);
    }
    if (data.containsKey('status')) {
      context.handle(
        _statusMeta,
        status.isAcceptableOrUnknown(data['status']!, _statusMeta),
      );
    }
    if (data.containsKey('created_at')) {
      context.handle(
        _createdAtMeta,
        createdAt.isAcceptableOrUnknown(data['created_at']!, _createdAtMeta),
      );
    }
    if (data.containsKey('retry_count')) {
      context.handle(
        _retryCountMeta,
        retryCount.isAcceptableOrUnknown(data['retry_count']!, _retryCountMeta),
      );
    }
    if (data.containsKey('tenant_id')) {
      context.handle(
        _tenantIdMeta,
        tenantId.isAcceptableOrUnknown(data['tenant_id']!, _tenantIdMeta),
      );
    } else if (isInserting) {
      context.missing(_tenantIdMeta);
    }
    if (data.containsKey('idempotency_key')) {
      context.handle(
        _idempotencyKeyMeta,
        idempotencyKey.isAcceptableOrUnknown(
          data['idempotency_key']!,
          _idempotencyKeyMeta,
        ),
      );
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {id};
  @override
  SyncQueueEntity map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return SyncQueueEntity(
      id: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}id'],
      )!,
      actionType: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}action_type'],
      )!,
      payload: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}payload'],
      )!,
      status: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}status'],
      )!,
      createdAt: attachedDatabase.typeMapping.read(
        DriftSqlType.dateTime,
        data['${effectivePrefix}created_at'],
      )!,
      retryCount: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}retry_count'],
      )!,
      tenantId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}tenant_id'],
      )!,
      idempotencyKey: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}idempotency_key'],
      ),
    );
  }

  @override
  $SyncQueuesTable createAlias(String alias) {
    return $SyncQueuesTable(attachedDatabase, alias);
  }
}

class SyncQueueEntity extends DataClass implements Insertable<SyncQueueEntity> {
  final int id;
  final String actionType;
  final String payload;
  final String status;
  final DateTime createdAt;
  final int retryCount;
  final String tenantId;
  final String? idempotencyKey;
  const SyncQueueEntity({
    required this.id,
    required this.actionType,
    required this.payload,
    required this.status,
    required this.createdAt,
    required this.retryCount,
    required this.tenantId,
    this.idempotencyKey,
  });
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['id'] = Variable<int>(id);
    map['action_type'] = Variable<String>(actionType);
    map['payload'] = Variable<String>(payload);
    map['status'] = Variable<String>(status);
    map['created_at'] = Variable<DateTime>(createdAt);
    map['retry_count'] = Variable<int>(retryCount);
    map['tenant_id'] = Variable<String>(tenantId);
    if (!nullToAbsent || idempotencyKey != null) {
      map['idempotency_key'] = Variable<String>(idempotencyKey);
    }
    return map;
  }

  SyncQueuesCompanion toCompanion(bool nullToAbsent) {
    return SyncQueuesCompanion(
      id: Value(id),
      actionType: Value(actionType),
      payload: Value(payload),
      status: Value(status),
      createdAt: Value(createdAt),
      retryCount: Value(retryCount),
      tenantId: Value(tenantId),
      idempotencyKey: idempotencyKey == null && nullToAbsent
          ? const Value.absent()
          : Value(idempotencyKey),
    );
  }

  factory SyncQueueEntity.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return SyncQueueEntity(
      id: serializer.fromJson<int>(json['id']),
      actionType: serializer.fromJson<String>(json['actionType']),
      payload: serializer.fromJson<String>(json['payload']),
      status: serializer.fromJson<String>(json['status']),
      createdAt: serializer.fromJson<DateTime>(json['createdAt']),
      retryCount: serializer.fromJson<int>(json['retryCount']),
      tenantId: serializer.fromJson<String>(json['tenantId']),
      idempotencyKey: serializer.fromJson<String?>(json['idempotencyKey']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'id': serializer.toJson<int>(id),
      'actionType': serializer.toJson<String>(actionType),
      'payload': serializer.toJson<String>(payload),
      'status': serializer.toJson<String>(status),
      'createdAt': serializer.toJson<DateTime>(createdAt),
      'retryCount': serializer.toJson<int>(retryCount),
      'tenantId': serializer.toJson<String>(tenantId),
      'idempotencyKey': serializer.toJson<String?>(idempotencyKey),
    };
  }

  SyncQueueEntity copyWith({
    int? id,
    String? actionType,
    String? payload,
    String? status,
    DateTime? createdAt,
    int? retryCount,
    String? tenantId,
    Value<String?> idempotencyKey = const Value.absent(),
  }) => SyncQueueEntity(
    id: id ?? this.id,
    actionType: actionType ?? this.actionType,
    payload: payload ?? this.payload,
    status: status ?? this.status,
    createdAt: createdAt ?? this.createdAt,
    retryCount: retryCount ?? this.retryCount,
    tenantId: tenantId ?? this.tenantId,
    idempotencyKey: idempotencyKey.present
        ? idempotencyKey.value
        : this.idempotencyKey,
  );
  SyncQueueEntity copyWithCompanion(SyncQueuesCompanion data) {
    return SyncQueueEntity(
      id: data.id.present ? data.id.value : this.id,
      actionType: data.actionType.present
          ? data.actionType.value
          : this.actionType,
      payload: data.payload.present ? data.payload.value : this.payload,
      status: data.status.present ? data.status.value : this.status,
      createdAt: data.createdAt.present ? data.createdAt.value : this.createdAt,
      retryCount: data.retryCount.present
          ? data.retryCount.value
          : this.retryCount,
      tenantId: data.tenantId.present ? data.tenantId.value : this.tenantId,
      idempotencyKey: data.idempotencyKey.present
          ? data.idempotencyKey.value
          : this.idempotencyKey,
    );
  }

  @override
  String toString() {
    return (StringBuffer('SyncQueueEntity(')
          ..write('id: $id, ')
          ..write('actionType: $actionType, ')
          ..write('payload: $payload, ')
          ..write('status: $status, ')
          ..write('createdAt: $createdAt, ')
          ..write('retryCount: $retryCount, ')
          ..write('tenantId: $tenantId, ')
          ..write('idempotencyKey: $idempotencyKey')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(
    id,
    actionType,
    payload,
    status,
    createdAt,
    retryCount,
    tenantId,
    idempotencyKey,
  );
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is SyncQueueEntity &&
          other.id == this.id &&
          other.actionType == this.actionType &&
          other.payload == this.payload &&
          other.status == this.status &&
          other.createdAt == this.createdAt &&
          other.retryCount == this.retryCount &&
          other.tenantId == this.tenantId &&
          other.idempotencyKey == this.idempotencyKey);
}

class SyncQueuesCompanion extends UpdateCompanion<SyncQueueEntity> {
  final Value<int> id;
  final Value<String> actionType;
  final Value<String> payload;
  final Value<String> status;
  final Value<DateTime> createdAt;
  final Value<int> retryCount;
  final Value<String> tenantId;
  final Value<String?> idempotencyKey;
  const SyncQueuesCompanion({
    this.id = const Value.absent(),
    this.actionType = const Value.absent(),
    this.payload = const Value.absent(),
    this.status = const Value.absent(),
    this.createdAt = const Value.absent(),
    this.retryCount = const Value.absent(),
    this.tenantId = const Value.absent(),
    this.idempotencyKey = const Value.absent(),
  });
  SyncQueuesCompanion.insert({
    this.id = const Value.absent(),
    required String actionType,
    required String payload,
    this.status = const Value.absent(),
    this.createdAt = const Value.absent(),
    this.retryCount = const Value.absent(),
    required String tenantId,
    this.idempotencyKey = const Value.absent(),
  }) : actionType = Value(actionType),
       payload = Value(payload),
       tenantId = Value(tenantId);
  static Insertable<SyncQueueEntity> custom({
    Expression<int>? id,
    Expression<String>? actionType,
    Expression<String>? payload,
    Expression<String>? status,
    Expression<DateTime>? createdAt,
    Expression<int>? retryCount,
    Expression<String>? tenantId,
    Expression<String>? idempotencyKey,
  }) {
    return RawValuesInsertable({
      if (id != null) 'id': id,
      if (actionType != null) 'action_type': actionType,
      if (payload != null) 'payload': payload,
      if (status != null) 'status': status,
      if (createdAt != null) 'created_at': createdAt,
      if (retryCount != null) 'retry_count': retryCount,
      if (tenantId != null) 'tenant_id': tenantId,
      if (idempotencyKey != null) 'idempotency_key': idempotencyKey,
    });
  }

  SyncQueuesCompanion copyWith({
    Value<int>? id,
    Value<String>? actionType,
    Value<String>? payload,
    Value<String>? status,
    Value<DateTime>? createdAt,
    Value<int>? retryCount,
    Value<String>? tenantId,
    Value<String?>? idempotencyKey,
  }) {
    return SyncQueuesCompanion(
      id: id ?? this.id,
      actionType: actionType ?? this.actionType,
      payload: payload ?? this.payload,
      status: status ?? this.status,
      createdAt: createdAt ?? this.createdAt,
      retryCount: retryCount ?? this.retryCount,
      tenantId: tenantId ?? this.tenantId,
      idempotencyKey: idempotencyKey ?? this.idempotencyKey,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (id.present) {
      map['id'] = Variable<int>(id.value);
    }
    if (actionType.present) {
      map['action_type'] = Variable<String>(actionType.value);
    }
    if (payload.present) {
      map['payload'] = Variable<String>(payload.value);
    }
    if (status.present) {
      map['status'] = Variable<String>(status.value);
    }
    if (createdAt.present) {
      map['created_at'] = Variable<DateTime>(createdAt.value);
    }
    if (retryCount.present) {
      map['retry_count'] = Variable<int>(retryCount.value);
    }
    if (tenantId.present) {
      map['tenant_id'] = Variable<String>(tenantId.value);
    }
    if (idempotencyKey.present) {
      map['idempotency_key'] = Variable<String>(idempotencyKey.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('SyncQueuesCompanion(')
          ..write('id: $id, ')
          ..write('actionType: $actionType, ')
          ..write('payload: $payload, ')
          ..write('status: $status, ')
          ..write('createdAt: $createdAt, ')
          ..write('retryCount: $retryCount, ')
          ..write('tenantId: $tenantId, ')
          ..write('idempotencyKey: $idempotencyKey')
          ..write(')'))
        .toString();
  }
}

abstract class _$AppDatabase extends GeneratedDatabase {
  _$AppDatabase(QueryExecutor e) : super(e);
  $AppDatabaseManager get managers => $AppDatabaseManager(this);
  late final $AssetsTable assets = $AssetsTable(this);
  late final $WorkOrdersTable workOrders = $WorkOrdersTable(this);
  late final $SyncQueuesTable syncQueues = $SyncQueuesTable(this);
  late final AssetDao assetDao = AssetDao(this as AppDatabase);
  late final WorkOrderDao workOrderDao = WorkOrderDao(this as AppDatabase);
  late final SyncQueueDao syncQueueDao = SyncQueueDao(this as AppDatabase);
  @override
  Iterable<TableInfo<Table, Object?>> get allTables =>
      allSchemaEntities.whereType<TableInfo<Table, Object?>>();
  @override
  List<DatabaseSchemaEntity> get allSchemaEntities => [
    assets,
    workOrders,
    syncQueues,
  ];
}

typedef $$AssetsTableCreateCompanionBuilder =
    AssetsCompanion Function({
      required String id,
      required String name,
      Value<String?> qrCode,
      Value<String?> locationName,
      required String tenantId,
      Value<bool> isActive,
      Value<DateTime> lastUpdated,
      Value<String?> rawJson,
      Value<int> rowid,
    });
typedef $$AssetsTableUpdateCompanionBuilder =
    AssetsCompanion Function({
      Value<String> id,
      Value<String> name,
      Value<String?> qrCode,
      Value<String?> locationName,
      Value<String> tenantId,
      Value<bool> isActive,
      Value<DateTime> lastUpdated,
      Value<String?> rawJson,
      Value<int> rowid,
    });

class $$AssetsTableFilterComposer
    extends Composer<_$AppDatabase, $AssetsTable> {
  $$AssetsTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<String> get id => $composableBuilder(
    column: $table.id,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get name => $composableBuilder(
    column: $table.name,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get qrCode => $composableBuilder(
    column: $table.qrCode,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get locationName => $composableBuilder(
    column: $table.locationName,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get tenantId => $composableBuilder(
    column: $table.tenantId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<bool> get isActive => $composableBuilder(
    column: $table.isActive,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<DateTime> get lastUpdated => $composableBuilder(
    column: $table.lastUpdated,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get rawJson => $composableBuilder(
    column: $table.rawJson,
    builder: (column) => ColumnFilters(column),
  );
}

class $$AssetsTableOrderingComposer
    extends Composer<_$AppDatabase, $AssetsTable> {
  $$AssetsTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<String> get id => $composableBuilder(
    column: $table.id,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get name => $composableBuilder(
    column: $table.name,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get qrCode => $composableBuilder(
    column: $table.qrCode,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get locationName => $composableBuilder(
    column: $table.locationName,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get tenantId => $composableBuilder(
    column: $table.tenantId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<bool> get isActive => $composableBuilder(
    column: $table.isActive,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<DateTime> get lastUpdated => $composableBuilder(
    column: $table.lastUpdated,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get rawJson => $composableBuilder(
    column: $table.rawJson,
    builder: (column) => ColumnOrderings(column),
  );
}

class $$AssetsTableAnnotationComposer
    extends Composer<_$AppDatabase, $AssetsTable> {
  $$AssetsTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<String> get id =>
      $composableBuilder(column: $table.id, builder: (column) => column);

  GeneratedColumn<String> get name =>
      $composableBuilder(column: $table.name, builder: (column) => column);

  GeneratedColumn<String> get qrCode =>
      $composableBuilder(column: $table.qrCode, builder: (column) => column);

  GeneratedColumn<String> get locationName => $composableBuilder(
    column: $table.locationName,
    builder: (column) => column,
  );

  GeneratedColumn<String> get tenantId =>
      $composableBuilder(column: $table.tenantId, builder: (column) => column);

  GeneratedColumn<bool> get isActive =>
      $composableBuilder(column: $table.isActive, builder: (column) => column);

  GeneratedColumn<DateTime> get lastUpdated => $composableBuilder(
    column: $table.lastUpdated,
    builder: (column) => column,
  );

  GeneratedColumn<String> get rawJson =>
      $composableBuilder(column: $table.rawJson, builder: (column) => column);
}

class $$AssetsTableTableManager
    extends
        RootTableManager<
          _$AppDatabase,
          $AssetsTable,
          AssetEntity,
          $$AssetsTableFilterComposer,
          $$AssetsTableOrderingComposer,
          $$AssetsTableAnnotationComposer,
          $$AssetsTableCreateCompanionBuilder,
          $$AssetsTableUpdateCompanionBuilder,
          (
            AssetEntity,
            BaseReferences<_$AppDatabase, $AssetsTable, AssetEntity>,
          ),
          AssetEntity,
          PrefetchHooks Function()
        > {
  $$AssetsTableTableManager(_$AppDatabase db, $AssetsTable table)
    : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$AssetsTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$AssetsTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$AssetsTableAnnotationComposer($db: db, $table: table),
          updateCompanionCallback:
              ({
                Value<String> id = const Value.absent(),
                Value<String> name = const Value.absent(),
                Value<String?> qrCode = const Value.absent(),
                Value<String?> locationName = const Value.absent(),
                Value<String> tenantId = const Value.absent(),
                Value<bool> isActive = const Value.absent(),
                Value<DateTime> lastUpdated = const Value.absent(),
                Value<String?> rawJson = const Value.absent(),
                Value<int> rowid = const Value.absent(),
              }) => AssetsCompanion(
                id: id,
                name: name,
                qrCode: qrCode,
                locationName: locationName,
                tenantId: tenantId,
                isActive: isActive,
                lastUpdated: lastUpdated,
                rawJson: rawJson,
                rowid: rowid,
              ),
          createCompanionCallback:
              ({
                required String id,
                required String name,
                Value<String?> qrCode = const Value.absent(),
                Value<String?> locationName = const Value.absent(),
                required String tenantId,
                Value<bool> isActive = const Value.absent(),
                Value<DateTime> lastUpdated = const Value.absent(),
                Value<String?> rawJson = const Value.absent(),
                Value<int> rowid = const Value.absent(),
              }) => AssetsCompanion.insert(
                id: id,
                name: name,
                qrCode: qrCode,
                locationName: locationName,
                tenantId: tenantId,
                isActive: isActive,
                lastUpdated: lastUpdated,
                rawJson: rawJson,
                rowid: rowid,
              ),
          withReferenceMapper: (p0) => p0
              .map((e) => (e.readTable(table), BaseReferences(db, table, e)))
              .toList(),
          prefetchHooksCallback: null,
        ),
      );
}

typedef $$AssetsTableProcessedTableManager =
    ProcessedTableManager<
      _$AppDatabase,
      $AssetsTable,
      AssetEntity,
      $$AssetsTableFilterComposer,
      $$AssetsTableOrderingComposer,
      $$AssetsTableAnnotationComposer,
      $$AssetsTableCreateCompanionBuilder,
      $$AssetsTableUpdateCompanionBuilder,
      (AssetEntity, BaseReferences<_$AppDatabase, $AssetsTable, AssetEntity>),
      AssetEntity,
      PrefetchHooks Function()
    >;
typedef $$WorkOrdersTableCreateCompanionBuilder =
    WorkOrdersCompanion Function({
      required String id,
      required String title,
      required String description,
      required String status,
      Value<String?> priority,
      Value<String?> assetId,
      Value<String?> assetName,
      Value<String?> assetLocation,
      Value<DateTime?> deadline,
      Value<DateTime?> updatedAt,
      Value<String?> assigneeUsername,
      Value<String?> resolutionNotes,
      Value<List<dynamic>> checklists,
      Value<List<dynamic>> attachments,
      required String tenantId,
      Value<int> rowid,
    });
typedef $$WorkOrdersTableUpdateCompanionBuilder =
    WorkOrdersCompanion Function({
      Value<String> id,
      Value<String> title,
      Value<String> description,
      Value<String> status,
      Value<String?> priority,
      Value<String?> assetId,
      Value<String?> assetName,
      Value<String?> assetLocation,
      Value<DateTime?> deadline,
      Value<DateTime?> updatedAt,
      Value<String?> assigneeUsername,
      Value<String?> resolutionNotes,
      Value<List<dynamic>> checklists,
      Value<List<dynamic>> attachments,
      Value<String> tenantId,
      Value<int> rowid,
    });

class $$WorkOrdersTableFilterComposer
    extends Composer<_$AppDatabase, $WorkOrdersTable> {
  $$WorkOrdersTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<String> get id => $composableBuilder(
    column: $table.id,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get title => $composableBuilder(
    column: $table.title,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get description => $composableBuilder(
    column: $table.description,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get status => $composableBuilder(
    column: $table.status,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get priority => $composableBuilder(
    column: $table.priority,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get assetId => $composableBuilder(
    column: $table.assetId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get assetName => $composableBuilder(
    column: $table.assetName,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get assetLocation => $composableBuilder(
    column: $table.assetLocation,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<DateTime> get deadline => $composableBuilder(
    column: $table.deadline,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<DateTime> get updatedAt => $composableBuilder(
    column: $table.updatedAt,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get assigneeUsername => $composableBuilder(
    column: $table.assigneeUsername,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get resolutionNotes => $composableBuilder(
    column: $table.resolutionNotes,
    builder: (column) => ColumnFilters(column),
  );

  ColumnWithTypeConverterFilters<List<dynamic>, List<dynamic>, String>
  get checklists => $composableBuilder(
    column: $table.checklists,
    builder: (column) => ColumnWithTypeConverterFilters(column),
  );

  ColumnWithTypeConverterFilters<List<dynamic>, List<dynamic>, String>
  get attachments => $composableBuilder(
    column: $table.attachments,
    builder: (column) => ColumnWithTypeConverterFilters(column),
  );

  ColumnFilters<String> get tenantId => $composableBuilder(
    column: $table.tenantId,
    builder: (column) => ColumnFilters(column),
  );
}

class $$WorkOrdersTableOrderingComposer
    extends Composer<_$AppDatabase, $WorkOrdersTable> {
  $$WorkOrdersTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<String> get id => $composableBuilder(
    column: $table.id,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get title => $composableBuilder(
    column: $table.title,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get description => $composableBuilder(
    column: $table.description,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get status => $composableBuilder(
    column: $table.status,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get priority => $composableBuilder(
    column: $table.priority,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get assetId => $composableBuilder(
    column: $table.assetId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get assetName => $composableBuilder(
    column: $table.assetName,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get assetLocation => $composableBuilder(
    column: $table.assetLocation,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<DateTime> get deadline => $composableBuilder(
    column: $table.deadline,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<DateTime> get updatedAt => $composableBuilder(
    column: $table.updatedAt,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get assigneeUsername => $composableBuilder(
    column: $table.assigneeUsername,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get resolutionNotes => $composableBuilder(
    column: $table.resolutionNotes,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get checklists => $composableBuilder(
    column: $table.checklists,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get attachments => $composableBuilder(
    column: $table.attachments,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get tenantId => $composableBuilder(
    column: $table.tenantId,
    builder: (column) => ColumnOrderings(column),
  );
}

class $$WorkOrdersTableAnnotationComposer
    extends Composer<_$AppDatabase, $WorkOrdersTable> {
  $$WorkOrdersTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<String> get id =>
      $composableBuilder(column: $table.id, builder: (column) => column);

  GeneratedColumn<String> get title =>
      $composableBuilder(column: $table.title, builder: (column) => column);

  GeneratedColumn<String> get description => $composableBuilder(
    column: $table.description,
    builder: (column) => column,
  );

  GeneratedColumn<String> get status =>
      $composableBuilder(column: $table.status, builder: (column) => column);

  GeneratedColumn<String> get priority =>
      $composableBuilder(column: $table.priority, builder: (column) => column);

  GeneratedColumn<String> get assetId =>
      $composableBuilder(column: $table.assetId, builder: (column) => column);

  GeneratedColumn<String> get assetName =>
      $composableBuilder(column: $table.assetName, builder: (column) => column);

  GeneratedColumn<String> get assetLocation => $composableBuilder(
    column: $table.assetLocation,
    builder: (column) => column,
  );

  GeneratedColumn<DateTime> get deadline =>
      $composableBuilder(column: $table.deadline, builder: (column) => column);

  GeneratedColumn<DateTime> get updatedAt =>
      $composableBuilder(column: $table.updatedAt, builder: (column) => column);

  GeneratedColumn<String> get assigneeUsername => $composableBuilder(
    column: $table.assigneeUsername,
    builder: (column) => column,
  );

  GeneratedColumn<String> get resolutionNotes => $composableBuilder(
    column: $table.resolutionNotes,
    builder: (column) => column,
  );

  GeneratedColumnWithTypeConverter<List<dynamic>, String> get checklists =>
      $composableBuilder(
        column: $table.checklists,
        builder: (column) => column,
      );

  GeneratedColumnWithTypeConverter<List<dynamic>, String> get attachments =>
      $composableBuilder(
        column: $table.attachments,
        builder: (column) => column,
      );

  GeneratedColumn<String> get tenantId =>
      $composableBuilder(column: $table.tenantId, builder: (column) => column);
}

class $$WorkOrdersTableTableManager
    extends
        RootTableManager<
          _$AppDatabase,
          $WorkOrdersTable,
          WorkOrderEntity,
          $$WorkOrdersTableFilterComposer,
          $$WorkOrdersTableOrderingComposer,
          $$WorkOrdersTableAnnotationComposer,
          $$WorkOrdersTableCreateCompanionBuilder,
          $$WorkOrdersTableUpdateCompanionBuilder,
          (
            WorkOrderEntity,
            BaseReferences<_$AppDatabase, $WorkOrdersTable, WorkOrderEntity>,
          ),
          WorkOrderEntity,
          PrefetchHooks Function()
        > {
  $$WorkOrdersTableTableManager(_$AppDatabase db, $WorkOrdersTable table)
    : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$WorkOrdersTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$WorkOrdersTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$WorkOrdersTableAnnotationComposer($db: db, $table: table),
          updateCompanionCallback:
              ({
                Value<String> id = const Value.absent(),
                Value<String> title = const Value.absent(),
                Value<String> description = const Value.absent(),
                Value<String> status = const Value.absent(),
                Value<String?> priority = const Value.absent(),
                Value<String?> assetId = const Value.absent(),
                Value<String?> assetName = const Value.absent(),
                Value<String?> assetLocation = const Value.absent(),
                Value<DateTime?> deadline = const Value.absent(),
                Value<DateTime?> updatedAt = const Value.absent(),
                Value<String?> assigneeUsername = const Value.absent(),
                Value<String?> resolutionNotes = const Value.absent(),
                Value<List<dynamic>> checklists = const Value.absent(),
                Value<List<dynamic>> attachments = const Value.absent(),
                Value<String> tenantId = const Value.absent(),
                Value<int> rowid = const Value.absent(),
              }) => WorkOrdersCompanion(
                id: id,
                title: title,
                description: description,
                status: status,
                priority: priority,
                assetId: assetId,
                assetName: assetName,
                assetLocation: assetLocation,
                deadline: deadline,
                updatedAt: updatedAt,
                assigneeUsername: assigneeUsername,
                resolutionNotes: resolutionNotes,
                checklists: checklists,
                attachments: attachments,
                tenantId: tenantId,
                rowid: rowid,
              ),
          createCompanionCallback:
              ({
                required String id,
                required String title,
                required String description,
                required String status,
                Value<String?> priority = const Value.absent(),
                Value<String?> assetId = const Value.absent(),
                Value<String?> assetName = const Value.absent(),
                Value<String?> assetLocation = const Value.absent(),
                Value<DateTime?> deadline = const Value.absent(),
                Value<DateTime?> updatedAt = const Value.absent(),
                Value<String?> assigneeUsername = const Value.absent(),
                Value<String?> resolutionNotes = const Value.absent(),
                Value<List<dynamic>> checklists = const Value.absent(),
                Value<List<dynamic>> attachments = const Value.absent(),
                required String tenantId,
                Value<int> rowid = const Value.absent(),
              }) => WorkOrdersCompanion.insert(
                id: id,
                title: title,
                description: description,
                status: status,
                priority: priority,
                assetId: assetId,
                assetName: assetName,
                assetLocation: assetLocation,
                deadline: deadline,
                updatedAt: updatedAt,
                assigneeUsername: assigneeUsername,
                resolutionNotes: resolutionNotes,
                checklists: checklists,
                attachments: attachments,
                tenantId: tenantId,
                rowid: rowid,
              ),
          withReferenceMapper: (p0) => p0
              .map((e) => (e.readTable(table), BaseReferences(db, table, e)))
              .toList(),
          prefetchHooksCallback: null,
        ),
      );
}

typedef $$WorkOrdersTableProcessedTableManager =
    ProcessedTableManager<
      _$AppDatabase,
      $WorkOrdersTable,
      WorkOrderEntity,
      $$WorkOrdersTableFilterComposer,
      $$WorkOrdersTableOrderingComposer,
      $$WorkOrdersTableAnnotationComposer,
      $$WorkOrdersTableCreateCompanionBuilder,
      $$WorkOrdersTableUpdateCompanionBuilder,
      (
        WorkOrderEntity,
        BaseReferences<_$AppDatabase, $WorkOrdersTable, WorkOrderEntity>,
      ),
      WorkOrderEntity,
      PrefetchHooks Function()
    >;
typedef $$SyncQueuesTableCreateCompanionBuilder =
    SyncQueuesCompanion Function({
      Value<int> id,
      required String actionType,
      required String payload,
      Value<String> status,
      Value<DateTime> createdAt,
      Value<int> retryCount,
      required String tenantId,
      Value<String?> idempotencyKey,
    });
typedef $$SyncQueuesTableUpdateCompanionBuilder =
    SyncQueuesCompanion Function({
      Value<int> id,
      Value<String> actionType,
      Value<String> payload,
      Value<String> status,
      Value<DateTime> createdAt,
      Value<int> retryCount,
      Value<String> tenantId,
      Value<String?> idempotencyKey,
    });

class $$SyncQueuesTableFilterComposer
    extends Composer<_$AppDatabase, $SyncQueuesTable> {
  $$SyncQueuesTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<int> get id => $composableBuilder(
    column: $table.id,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get actionType => $composableBuilder(
    column: $table.actionType,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get payload => $composableBuilder(
    column: $table.payload,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get status => $composableBuilder(
    column: $table.status,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<DateTime> get createdAt => $composableBuilder(
    column: $table.createdAt,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get retryCount => $composableBuilder(
    column: $table.retryCount,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get tenantId => $composableBuilder(
    column: $table.tenantId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get idempotencyKey => $composableBuilder(
    column: $table.idempotencyKey,
    builder: (column) => ColumnFilters(column),
  );
}

class $$SyncQueuesTableOrderingComposer
    extends Composer<_$AppDatabase, $SyncQueuesTable> {
  $$SyncQueuesTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<int> get id => $composableBuilder(
    column: $table.id,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get actionType => $composableBuilder(
    column: $table.actionType,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get payload => $composableBuilder(
    column: $table.payload,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get status => $composableBuilder(
    column: $table.status,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<DateTime> get createdAt => $composableBuilder(
    column: $table.createdAt,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get retryCount => $composableBuilder(
    column: $table.retryCount,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get tenantId => $composableBuilder(
    column: $table.tenantId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get idempotencyKey => $composableBuilder(
    column: $table.idempotencyKey,
    builder: (column) => ColumnOrderings(column),
  );
}

class $$SyncQueuesTableAnnotationComposer
    extends Composer<_$AppDatabase, $SyncQueuesTable> {
  $$SyncQueuesTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<int> get id =>
      $composableBuilder(column: $table.id, builder: (column) => column);

  GeneratedColumn<String> get actionType => $composableBuilder(
    column: $table.actionType,
    builder: (column) => column,
  );

  GeneratedColumn<String> get payload =>
      $composableBuilder(column: $table.payload, builder: (column) => column);

  GeneratedColumn<String> get status =>
      $composableBuilder(column: $table.status, builder: (column) => column);

  GeneratedColumn<DateTime> get createdAt =>
      $composableBuilder(column: $table.createdAt, builder: (column) => column);

  GeneratedColumn<int> get retryCount => $composableBuilder(
    column: $table.retryCount,
    builder: (column) => column,
  );

  GeneratedColumn<String> get tenantId =>
      $composableBuilder(column: $table.tenantId, builder: (column) => column);

  GeneratedColumn<String> get idempotencyKey => $composableBuilder(
    column: $table.idempotencyKey,
    builder: (column) => column,
  );
}

class $$SyncQueuesTableTableManager
    extends
        RootTableManager<
          _$AppDatabase,
          $SyncQueuesTable,
          SyncQueueEntity,
          $$SyncQueuesTableFilterComposer,
          $$SyncQueuesTableOrderingComposer,
          $$SyncQueuesTableAnnotationComposer,
          $$SyncQueuesTableCreateCompanionBuilder,
          $$SyncQueuesTableUpdateCompanionBuilder,
          (
            SyncQueueEntity,
            BaseReferences<_$AppDatabase, $SyncQueuesTable, SyncQueueEntity>,
          ),
          SyncQueueEntity,
          PrefetchHooks Function()
        > {
  $$SyncQueuesTableTableManager(_$AppDatabase db, $SyncQueuesTable table)
    : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$SyncQueuesTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$SyncQueuesTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$SyncQueuesTableAnnotationComposer($db: db, $table: table),
          updateCompanionCallback:
              ({
                Value<int> id = const Value.absent(),
                Value<String> actionType = const Value.absent(),
                Value<String> payload = const Value.absent(),
                Value<String> status = const Value.absent(),
                Value<DateTime> createdAt = const Value.absent(),
                Value<int> retryCount = const Value.absent(),
                Value<String> tenantId = const Value.absent(),
                Value<String?> idempotencyKey = const Value.absent(),
              }) => SyncQueuesCompanion(
                id: id,
                actionType: actionType,
                payload: payload,
                status: status,
                createdAt: createdAt,
                retryCount: retryCount,
                tenantId: tenantId,
                idempotencyKey: idempotencyKey,
              ),
          createCompanionCallback:
              ({
                Value<int> id = const Value.absent(),
                required String actionType,
                required String payload,
                Value<String> status = const Value.absent(),
                Value<DateTime> createdAt = const Value.absent(),
                Value<int> retryCount = const Value.absent(),
                required String tenantId,
                Value<String?> idempotencyKey = const Value.absent(),
              }) => SyncQueuesCompanion.insert(
                id: id,
                actionType: actionType,
                payload: payload,
                status: status,
                createdAt: createdAt,
                retryCount: retryCount,
                tenantId: tenantId,
                idempotencyKey: idempotencyKey,
              ),
          withReferenceMapper: (p0) => p0
              .map((e) => (e.readTable(table), BaseReferences(db, table, e)))
              .toList(),
          prefetchHooksCallback: null,
        ),
      );
}

typedef $$SyncQueuesTableProcessedTableManager =
    ProcessedTableManager<
      _$AppDatabase,
      $SyncQueuesTable,
      SyncQueueEntity,
      $$SyncQueuesTableFilterComposer,
      $$SyncQueuesTableOrderingComposer,
      $$SyncQueuesTableAnnotationComposer,
      $$SyncQueuesTableCreateCompanionBuilder,
      $$SyncQueuesTableUpdateCompanionBuilder,
      (
        SyncQueueEntity,
        BaseReferences<_$AppDatabase, $SyncQueuesTable, SyncQueueEntity>,
      ),
      SyncQueueEntity,
      PrefetchHooks Function()
    >;

class $AppDatabaseManager {
  final _$AppDatabase _db;
  $AppDatabaseManager(this._db);
  $$AssetsTableTableManager get assets =>
      $$AssetsTableTableManager(_db, _db.assets);
  $$WorkOrdersTableTableManager get workOrders =>
      $$WorkOrdersTableTableManager(_db, _db.workOrders);
  $$SyncQueuesTableTableManager get syncQueues =>
      $$SyncQueuesTableTableManager(_db, _db.syncQueues);
}

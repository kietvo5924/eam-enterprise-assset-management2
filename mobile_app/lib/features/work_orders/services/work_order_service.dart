import 'package:dio/dio.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:uuid/uuid.dart';
import '../../../core/network/dio_client.dart';
import '../models/work_order.dart';
import '../../../core/database/app_database.dart';
import '../../../core/database/database_mapper.dart';
import 'dart:io';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:drift/drift.dart' as drift;
import 'package:path_provider/path_provider.dart';
import '../../../core/network/network_service.dart';
import 'package:flutter_cache_manager/flutter_cache_manager.dart';
import '../../../core/constants/api_constants.dart';

class WorkOrderService {
  final Dio _dio = DioClient().dio;
  bool _isSyncingAssets = false;
  bool _isSyncingWos = false;

  bool _isDeterministicError(dynamic e) {
    if (e is DioException) {
      return e.response?.statusCode == 400 ||
          e.response?.statusCode == 403 ||
          e.response?.statusCode == 404;
    }
    return false;
  }

  Future<void> syncAssetsInBackground() async {
    if (_isSyncingAssets) return;
    _isSyncingAssets = true;
    try {
      final prefs = await SharedPreferences.getInstance();
      final tenantId = prefs.getString('tenantId') ?? '';
      if (tenantId.isEmpty) return;

      int page = 0;
      bool hasNext = true;
      while (hasNext) {
        if (page > 50) break; // Defensive max limit
        final response = await _dio.get(
          '/api/v1/assets',
          queryParameters: {
            'page': page,
            'size': 100, // chunking
          },
        );
        if (response.statusCode == 200 && response.data['success'] == true) {
          final data = response.data['data'];
          if (data == null) break;
          final List<dynamic> content = data['content'] ?? [];
          final isLast = data['last'] as bool? ?? true;

          final entities = content
              .map(
                (e) => DatabaseMapper.toAssetEntity(
                  e as Map<String, dynamic>,
                  tenantId,
                ),
              )
              .whereType<AssetEntity>()
              .toList();
          if (entities.isNotEmpty) {
            await AppDatabase.instance.assetDao.insertAllAssets(entities);
          }

          hasNext = !isLast;
          page++;
        } else {
          hasNext = false;
        }
      }
    } catch (e) {
      debugPrint('syncAssetsInBackground error: $e');
    } finally {
      _isSyncingAssets = false;
    }
  }

  Future<List<Map<String, dynamic>>> getAssets() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final tenantId = prefs.getString('tenantId') ?? '';

      var assets = await AppDatabase.instance.assetDao.getAllAssets(tenantId);

      // If empty, force sync and wait
      if (assets.isEmpty) {
        await syncAssetsInBackground();
        assets = await AppDatabase.instance.assetDao.getAllAssets(tenantId);
      } else {
        // Otherwise sync in background without awaiting
        syncAssetsInBackground();
      }

      return assets.map((e) => DatabaseMapper.fromAssetEntity(e)).toList();
    } catch (e) {
      // Fallback
    }
    return [];
  }

  Future<Map<String, dynamic>?> getAssetByQrCode(String qrCode) async {
    if (qrCode.trim().isEmpty) return null;
    try {
      final prefs = await SharedPreferences.getInstance();
      final tenantId = prefs.getString('tenantId') ?? '';

      // Try local cache first
      if (tenantId.isNotEmpty) {
        final localAsset = await AppDatabase.instance.assetDao.getAssetByQrCode(
          qrCode,
          tenantId,
        );
        if (localAsset != null) {
          // Trigger async update but return fast cache
          final encodedQr = Uri.encodeComponent(qrCode);
          _dio
              .get('/api/v1/assets/qr/$encodedQr')
              .then((res) {
                if (res.statusCode == 200 && res.data['success'] == true) {
                  final entity = DatabaseMapper.toAssetEntity(
                    res.data['data'],
                    tenantId,
                  );
                  if (entity != null)
                    AppDatabase.instance.assetDao.insertOrUpdateAsset(entity);
                }
              })
              .catchError((_) {});
          return DatabaseMapper.fromAssetEntity(localAsset);
        }
      }

      // Fallback API
      final encodedQr = Uri.encodeComponent(qrCode);
      final response = await _dio.get('/api/v1/assets/qr/$encodedQr');
      if (response.statusCode == 200 && response.data['success'] == true) {
        final assetData = response.data['data'] as Map<String, dynamic>?;
        if (assetData == null) return null;

        // Cache it
        if (tenantId.isNotEmpty && assetData.isNotEmpty) {
          final entity = DatabaseMapper.toAssetEntity(assetData, tenantId);
          if (entity != null) {
            await AppDatabase.instance.assetDao.insertOrUpdateAsset(entity);
          }
        }
        return assetData;
      }
    } catch (e) {
      if (e is DioException) {
        if (e.response?.statusCode == 404 || e.response?.statusCode == 400) {
          return null;
        }
        // Fallthrough
      }
      // Fallthrough
    }
    return null;
  }

  Future<bool> createWorkOrder(Map<String, dynamic> data) async {
    try {
      final response = await _dio.post('/api/v1/work-orders', data: data);
      return response.statusCode == 201 || response.statusCode == 200;
    } catch (e) {
      return false;
    }
  }

  Future<void> syncWorkOrdersInBackground() async {
    if (_isSyncingWos) return;
    _isSyncingWos = true;
    try {
      final prefs = await SharedPreferences.getInstance();
      final myUsername = prefs.getString('username') ?? '';
      final tenantId = prefs.getString('tenantId') ?? '';
      if (myUsername.isEmpty || tenantId.isEmpty) return;

      int page = 0;
      bool hasNext = true;
      List<String> remoteIds = [];

      bool isTruncated = false;

      while (hasNext) {
        if (page > 50) {
          isTruncated = true;
          break;
        }
        final response = await _dio.get(
          '/api/v1/work-orders',
          queryParameters: {'page': page, 'size': 100},
        );

        if (response.statusCode == 200 && response.data['success'] == true) {
          final data = response.data['data'];
          if (data == null) break;
          final List<dynamic> content = data['content'] ?? [];
          final isLast = data['last'] as bool? ?? true;

          final allWos = content
              .map((json) => WorkOrder.fromJson(json as Map<String, dynamic>))
              .toList();
          final filteredWos = allWos
              .where((wo) => wo.assigneeUsername == myUsername)
              .toList();

          if (filteredWos.isNotEmpty) {
            remoteIds.addAll(filteredWos.map((e) => e.id));

            // Do NOT overwrite local DB if there are pending sync tasks for a WO
            final pendingTasks = await AppDatabase.instance.syncQueueDao
                .getPendingSyncs();
            final pendingWoIds = pendingTasks
                .map((t) {
                  try {
                    final payload = jsonDecode(t.payload);
                    return payload['woId'] as String?;
                  } catch (_) {
                    return null;
                  }
                })
                .where((id) => id != null)
                .toSet();

            final safeToUpdateWos = filteredWos
                .where((wo) => !pendingWoIds.contains(wo.id))
                .toList();

            final entities = safeToUpdateWos
                .map((wo) => DatabaseMapper.toWorkOrderEntity(wo, tenantId))
                .toList();
            await AppDatabase.instance.workOrderDao.insertAllWorkOrders(
              entities,
            );

            // Precache attachments for offline viewing
            for (var wo in safeToUpdateWos) {
              for (var att in wo.attachments) {
                if (!att.isLocal) {
                  final apiUri = Uri.parse(ApiConstants.baseUrl);
                  String imageUrl = att.fileUrl.startsWith('http')
                      ? att.fileUrl
                      : 'http://${apiUri.host}:9000${att.fileUrl}';
                  if (imageUrl.contains('localhost')) {
                    imageUrl = imageUrl.replaceAll('localhost', apiUri.host);
                  }
                  // Silent download without awaiting so it doesn't block sync
                  // ignore: invalid_return_type_for_catch_error
                  DefaultCacheManager()
                      .downloadFile(imageUrl)
                      .catchError(
                        // ignore: invalid_return_type_for_catch_error
                        (_) => DefaultCacheManager().getFileFromCache(imageUrl),
                      );
                }
              }
            }
          }

          hasNext = !isLast;
          page++;
        } else {
          hasNext = false;
        }
      }

      // Cleanup stale WOs
      if (!isTruncated) {
        await AppDatabase.instance.workOrderDao.deleteStaleWorkOrders(
          remoteIds,
          myUsername,
          tenantId,
        );
      }
    } catch (e) {
      debugPrint('syncWorkOrdersInBackground error: $e');
    } finally {
      _isSyncingWos = false;
    }
  }

  Future<Map<String, dynamic>> getMyWorkOrders({
    int page = 0,
    int size = 20,
  }) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final myUsername = prefs.getString('username') ?? '';
      final tenantId = prefs.getString('tenantId') ?? '';

      final response = await _dio.get(
        '/api/v1/work-orders',
        queryParameters: {'page': page, 'size': size},
      );

      if (response.statusCode == 200 && response.data['success'] == true) {
        final data = response.data['data'];
        final content = data?['content'] as List<dynamic>? ?? [];
        final last = data?['last'] as bool? ?? true;

        final allWos = content
            .map((json) => WorkOrder.fromJson(json as Map<String, dynamic>))
            .toList();
        final filteredWos = allWos
            .where((wo) => wo.assigneeUsername == myUsername)
            .toList();

        // Caching is handled by syncWorkOrdersInBackground for full sync
        // But we can also insert these just in case
        if (tenantId.isNotEmpty && filteredWos.isNotEmpty) {
          final entities = filteredWos
              .map((wo) => DatabaseMapper.toWorkOrderEntity(wo, tenantId))
              .toList();
          await AppDatabase.instance.workOrderDao.insertAllWorkOrders(entities);
        }

        return {'data': filteredWos, 'last': last};
      }
      return {'data': <WorkOrder>[], 'last': true};
    } catch (e) {
      // Fallback to local DB if network error
      try {
        final prefs = await SharedPreferences.getInstance();
        final myUsername = prefs.getString('username') ?? '';
        final tenantId = prefs.getString('tenantId') ?? '';
        if (myUsername.isNotEmpty && tenantId.isNotEmpty) {
          final entities = await AppDatabase.instance.workOrderDao
              .getMyWorkOrders(myUsername, tenantId);
          var wos = entities
              .map((e) => DatabaseMapper.fromWorkOrderEntity(e))
              .toList();

          // Apply pagination locally
          int start = page * size;
          int end = start + size;
          if (start >= wos.length) return {'data': <WorkOrder>[], 'last': true};
          if (end > wos.length) end = wos.length;

          return {'data': wos.sublist(start, end), 'last': end >= wos.length};
        }
      } catch (dbError) {
        // Ignore DB error
      }
      return {'data': <WorkOrder>[], 'last': true};
    }
  }

  // Hàm dành riêng cho Mobile (Lọc theo user và bỏ qua CANCELED/COMPLETED)
  Future<List<WorkOrder>> getMobileHomeWorkOrders() async {
    try {
      // Trigger background sync to chunk all pages into local DB
      syncWorkOrdersInBackground();

      // Since UI uses Stream from Local DB, we just return empty list here
      // or return the first page directly.
      // The Stream in WorkOrderProvider will automatically yield the full updated list.
      return [];
    } catch (e) {
      return [];
    }
  }

  Future<WorkOrder?> getWorkOrderById(String id) async {
    try {
      // Priority 1: If there are pending sync tasks for this WO, the local DB has the latest un-synced state.
      // We must NOT fetch from the server, otherwise we will overwrite the UI with stale data.
      final pendingTasks = await AppDatabase.instance.syncQueueDao
          .getPendingSyncs();
      final hasPendingForThisWO = pendingTasks.any((t) {
        try {
          final payload = jsonDecode(t.payload);
          return payload['woId'] == id;
        } catch (_) {
          return false;
        }
      });

      if (hasPendingForThisWO) {
        debugPrint('WO $id has pending sync tasks. Serving from local DB.');
        final entity = await AppDatabase.instance.workOrderDao.getWorkOrderById(
          id,
        );
        if (entity != null) return DatabaseMapper.fromWorkOrderEntity(entity);
      }

      // Priority 2: Fetch from server
      final response = await _dio.get('/api/v1/work-orders/$id');
      if (response.statusCode == 200 && response.data['success'] == true) {
        final wo = WorkOrder.fromJson(response.data['data']);
        // Cache the latest server version if no pending mutations
        final prefs = await SharedPreferences.getInstance();
        final tenantId = prefs.getString('tenantId') ?? '';
        await AppDatabase.instance.workOrderDao.insertOrUpdateWorkOrder(
          DatabaseMapper.toWorkOrderEntity(wo, tenantId),
        );
        return wo;
      }
      return null;
    } catch (e) {
      // Priority 3: Offline fallback
      try {
        final entity = await AppDatabase.instance.workOrderDao.getWorkOrderById(
          id,
        );
        if (entity != null) {
          return DatabaseMapper.fromWorkOrderEntity(entity);
        }
      } catch (dbError) {
        // Ignore DB error
      }
      return null;
    }
  }

  Future<void> _updateLocalWorkOrder(String woId) async {
    try {
      final wo = await getWorkOrderById(woId);
      if (wo != null) {
        final prefs = await SharedPreferences.getInstance();
        final tenantId = prefs.getString('tenantId') ?? '';
        if (tenantId.isNotEmpty) {
          final entity = DatabaseMapper.toWorkOrderEntity(wo, tenantId);
          await AppDatabase.instance.workOrderDao.insertOrUpdateWorkOrder(
            entity,
          );
        }
      }
    } catch (e) {
      // Ignore
    }
  }

  Future<bool> updateChecklist(
    String woId,
    String itemName,
    bool isCompleted, [
    String? actualValue,
  ]) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final tenantId = prefs.getString('tenantId') ?? '';
      bool apiSuccess = false;

      if (NetworkService().isOnline) {
        try {
          final response = await _dio.post(
            '/api/v1/work-orders/$woId/checklists',
            data: {
              'itemName': itemName,
              'isCompleted': isCompleted,
              if (actualValue != null) 'actualValue': actualValue,
            },
          );
          if (response.statusCode == 200 && response.data['success'] == true) {
            apiSuccess = true;
          }
        } catch (e) {
          if (_isDeterministicError(e)) return false;
          debugPrint('updateChecklist API failed: $e, falling back to offline');
        }
      }

      if (apiSuccess) {
        _updateLocalWorkOrder(woId);
        return true;
      } else {
        final payload = jsonEncode({
          'woId': woId,
          'itemName': itemName,
          'isCompleted': isCompleted,
          if (actualValue != null) 'actualValue': actualValue,
        });
        await AppDatabase.instance.syncQueueDao.addSyncTask(
          SyncQueuesCompanion.insert(
            actionType: 'UPDATE_CHECKLIST',
            payload: payload,
            tenantId: tenantId,
            idempotencyKey: drift.Value(const Uuid().v4()),
          ),
        );
        final wo = await AppDatabase.instance.workOrderDao.getWorkOrderById(
          woId,
        );
        if (wo != null) {
          List<dynamic> checklists = List.from(wo.checklists);
          bool found = false;
          for (var i = 0; i < checklists.length; i++) {
            var item = checklists[i];
            if (item['itemName'] == itemName) {
              item = Map<String, dynamic>.from(item);
              item['completed'] = isCompleted; // Fixed key
              if (actualValue != null) item['actualValue'] = actualValue;
              checklists[i] = item;
              found = true;
              break;
            }
          }
          if (!found) {
            checklists.add({
              'itemName': itemName,
              'completed': isCompleted,
              if (actualValue != null) 'actualValue': actualValue,
            }); // Fixed key
          }
          await AppDatabase.instance.workOrderDao.insertOrUpdateWorkOrder(
            wo.copyWith(checklists: checklists),
          );
          return true;
        }
        return false;
      }
    } catch (e) {
      return false;
    }
  }

  Future<bool> uploadAttachment(String woId, String filePath) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final tenantId = prefs.getString('tenantId') ?? '';
      bool apiSuccess = false;

      if (NetworkService().isOnline) {
        try {
          final formData = FormData.fromMap({
            'file': await MultipartFile.fromFile(filePath),
          });
          final response = await _dio.post(
            '/api/v1/work-orders/$woId/attachments',
            data: formData,
          );
          if (response.statusCode == 200 && response.data['success'] == true) {
            apiSuccess = true;
          }
        } catch (e) {
          if (_isDeterministicError(e)) return false;
          debugPrint(
            'uploadAttachment API failed: $e, falling back to offline',
          );
        }
      }

      if (apiSuccess) {
        _updateLocalWorkOrder(woId);
        return true;
      } else {
        // Safe File Caching
        final appDir = await getApplicationDocumentsDirectory();
        final fileName = '${const Uuid().v4()}_${filePath.split('/').last}';
        final localFile = File(filePath);
        final savedImage = await localFile.copy('${appDir.path}/$fileName');
        final safePath = savedImage.path;

        final payload = jsonEncode({'woId': woId, 'filePath': safePath});
        await AppDatabase.instance.syncQueueDao.addSyncTask(
          SyncQueuesCompanion.insert(
            actionType: 'UPLOAD_PHOTO',
            payload: payload,
            tenantId: tenantId,
            idempotencyKey: drift.Value(const Uuid().v4()),
          ),
        );

        final wo = await AppDatabase.instance.workOrderDao.getWorkOrderById(
          woId,
        );
        if (wo != null) {
          List<dynamic> attachments = List.from(wo.attachments);
          attachments.add({
            'fileUrl': safePath,
            'fileName': fileName,
            'isLocal': true,
          });
          await AppDatabase.instance.workOrderDao.insertOrUpdateWorkOrder(
            wo.copyWith(attachments: attachments),
          );
          return true;
        }
        return false;
      }
    } catch (e) {
      return false;
    }
  }

  Future<bool> updateStatus(String woId, String status) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final tenantId = prefs.getString('tenantId') ?? '';
      bool apiSuccess = false;

      // Local Validation for COMPLETED status
      if (status == 'COMPLETED') {
        final wo = await AppDatabase.instance.workOrderDao.getWorkOrderById(
          woId,
        );
        if (wo != null) {
          bool allChecked = true;
          for (var item in wo.checklists) {
            if (item['completed'] != true) {
              allChecked = false;
              break;
            }
          }
          if (!allChecked || (wo.resolutionNotes?.isEmpty ?? true)) {
            debugPrint(
              'Local validation failed: Missing notes or incomplete checklists.',
            );
            return false;
          }
        }
      }

      if (NetworkService().isOnline) {
        try {
          final response = await _dio.put(
            '/api/v1/work-orders/$woId/status',
            data: {'status': status},
          );
          if (response.statusCode == 200 && response.data['success'] == true) {
            apiSuccess = true;
          }
        } catch (e) {
          if (_isDeterministicError(e)) return false;
          debugPrint('updateStatus API failed: $e, falling back to offline');
        }
      }

      if (apiSuccess) {
        _updateLocalWorkOrder(woId);
        return true;
      } else {
        final payload = jsonEncode({'woId': woId, 'status': status});
        await AppDatabase.instance.syncQueueDao.addSyncTask(
          SyncQueuesCompanion.insert(
            actionType: 'UPDATE_STATUS',
            payload: payload,
            tenantId: tenantId,
            idempotencyKey: drift.Value(const Uuid().v4()),
          ),
        );
        final wo = await AppDatabase.instance.workOrderDao.getWorkOrderById(
          woId,
        );
        if (wo != null) {
          await AppDatabase.instance.workOrderDao.insertOrUpdateWorkOrder(
            wo.copyWith(status: status),
          );
          return true;
        }
        return false;
      }
    } catch (e) {
      return false;
    }
  }

  Future<bool> updateNotes(String woId, String notes) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final tenantId = prefs.getString('tenantId') ?? '';
      bool apiSuccess = false;

      if (NetworkService().isOnline) {
        try {
          final response = await _dio.put(
            '/api/v1/work-orders/$woId/notes',
            data: {'resolutionNotes': notes},
          );
          if (response.statusCode == 200 && response.data['success'] == true) {
            apiSuccess = true;
          }
        } catch (e) {
          if (_isDeterministicError(e)) return false;
          debugPrint('updateNotes API failed: $e, falling back to offline');
        }
      }

      if (apiSuccess) {
        _updateLocalWorkOrder(woId);
        return true;
      } else {
        final payload = jsonEncode({'woId': woId, 'notes': notes});
        await AppDatabase.instance.syncQueueDao.addSyncTask(
          SyncQueuesCompanion.insert(
            actionType: 'UPDATE_NOTES',
            payload: payload,
            tenantId: tenantId,
            idempotencyKey: drift.Value(const Uuid().v4()),
          ),
        );
        final wo = await AppDatabase.instance.workOrderDao.getWorkOrderById(
          woId,
        );
        if (wo != null) {
          await AppDatabase.instance.workOrderDao.insertOrUpdateWorkOrder(
            wo.copyWith(resolutionNotes: drift.Value(notes)),
          );
          return true;
        }
        return false;
      }
    } catch (e) {
      return false;
    }
  }

  Future<bool> deleteChecklist(String woId, String checklistId) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final tenantId = prefs.getString('tenantId') ?? '';
      bool apiSuccess = false;

      if (NetworkService().isOnline) {
        try {
          final response = await _dio.delete(
            '/api/v1/work-orders/$woId/checklists/$checklistId',
          );
          if (response.statusCode == 200 && response.data['success'] == true) {
            apiSuccess = true;
          }
        } catch (e) {
          if (_isDeterministicError(e)) return false;
          debugPrint('deleteChecklist API failed: $e, falling back to offline');
        }
      }

      if (apiSuccess) {
        _updateLocalWorkOrder(woId);
        return true;
      } else {
        final payload = jsonEncode({'woId': woId, 'checklistId': checklistId});
        await AppDatabase.instance.syncQueueDao.addSyncTask(
          SyncQueuesCompanion.insert(
            actionType: 'DELETE_CHECKLIST',
            payload: payload,
            tenantId: tenantId,
            idempotencyKey: drift.Value(const Uuid().v4()),
          ),
        );

        final wo = await AppDatabase.instance.workOrderDao.getWorkOrderById(
          woId,
        );
        if (wo != null) {
          List<dynamic> checklists = List.from(wo.checklists);
          checklists.removeWhere(
            (item) =>
                item['id'] == checklistId || item['itemName'] == checklistId,
          ); // Fallback to itemName if id is missing locally
          await AppDatabase.instance.workOrderDao.insertOrUpdateWorkOrder(
            wo.copyWith(checklists: checklists),
          );
          return true;
        }
        return false;
      }
    } catch (e) {
      return false;
    }
  }

  Future<bool> logMeterReading(
    String assetId,
    Map<String, dynamic> data,
  ) async {
    try {
      if (NetworkService().isOnline) {
        final response = await _dio.post(
          '/api/v1/assets/$assetId/meter-readings',
          data: data,
        );
        return response.statusCode == 201 || response.statusCode == 200;
      }
      return false; // For now, we don't support offline meter reading logging
    } catch (e) {
      debugPrint('logMeterReading API failed: $e');
      return false;
    }
  }
}

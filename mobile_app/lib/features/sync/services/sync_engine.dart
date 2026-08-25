import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../../core/database/app_database.dart';
import '../../../core/network/dio_client.dart';
import '../../../core/network/network_service.dart';

class SyncEngine {
  static final SyncEngine _instance = SyncEngine._internal();
  factory SyncEngine() => _instance;

  final Dio _dio = DioClient().dio;
  bool _isSyncing = false;

  SyncEngine._internal();
  void _onNetworkChange() {
    if (NetworkService().isOnline) {
      triggerSync();
    }
  }

  void init() {
    NetworkService().addListener(_onNetworkChange);
    if (NetworkService().isOnline) {
      triggerSync();
    }
  }

  void dispose() {
    NetworkService().removeListener(_onNetworkChange);
  }

  Future<void> triggerSync() async {
    if (_isSyncing || !NetworkService().isOnline) return;
    _isSyncing = true;

    try {
      final prefs = await SharedPreferences.getInstance();
      final tenantId = prefs.getString('tenantId') ?? '';
      if (tenantId.isEmpty) {
        _isSyncing = false;
        return;
      }

      final pendingTasks = await AppDatabase.instance.syncQueueDao.getPendingSyncs();
      
      for (final task in pendingTasks) {
        if (task.tenantId != tenantId) continue;
        if (task.status == 'CONFLICT') continue; // Skip conflicted records

        // Ensure we are not retrying too fast.
        // Actually, we process them sequentially.
        await _processTask(task);
      }
    } catch (e) {
      debugPrint('SyncEngine error: $e');
    } finally {
      _isSyncing = false;
    }
  }

  Future<void> _processTask(SyncQueueEntity task) async {
    try {
      if (task.retryCount >= 3) {
        await _updateTaskStatus(task, 'FAILED');
        return;
      }

      // Exponential backoff if it's a retry
      if (task.retryCount > 0) {
        final delaySeconds = pow(2, task.retryCount).toInt();
        await Future.delayed(Duration(seconds: delaySeconds));
      }

      await _updateTaskStatus(task, 'IN_PROGRESS');

      final payload = jsonDecode(task.payload) as Map<String, dynamic>;
      final idempotencyKey = task.idempotencyKey ?? '';

      final options = Options(headers: {
        if (idempotencyKey.isNotEmpty) 'Idempotency-Key': idempotencyKey,
      });

      bool success = false;

      switch (task.actionType) {
        case 'UPDATE_CHECKLIST':
          success = await _syncChecklist(payload, options);
          break;
        case 'UPLOAD_PHOTO':
          success = await _syncPhoto(payload, options);
          break;
        case 'UPDATE_STATUS':
          success = await _syncStatus(payload, options);
          break;
        case 'UPDATE_NOTES':
          success = await _syncNotes(payload, options);
          break;
        default:
          success = true; // Unknown task, mark as success to clear it
      }

      if (success) {
        // Success: Remove from queue
        await AppDatabase.instance.syncQueueDao.deleteSyncTask(task.id);
      }
    } on DioException catch (e) {
      if (e.response?.statusCode == 409) {
        // Conflict
        await _updateTaskStatus(task, 'CONFLICT');
      } else if (e.response?.statusCode == 400 || e.response?.statusCode == 403 || e.response?.statusCode == 404) {
        // Deterministic error (e.g. invalid status transition, missing notes)
        // No point in retrying
        debugPrint('Sync task failed deterministically: ${e.response?.data}');
        await _updateTaskStatus(task, 'FAILED');
      } else {
        // Network or other server error
        await _handleFailure(task);
      }
    } catch (e) {
      debugPrint('Sync task failed: $e');
      await _handleFailure(task);
    }
  }

  Future<void> _handleFailure(SyncQueueEntity task) async {
    final newRetryCount = task.retryCount + 1;
    final newStatus = newRetryCount >= 3 ? 'FAILED' : 'PENDING';
    await AppDatabase.instance.syncQueueDao.updateSyncTask(
      task.copyWith(status: newStatus, retryCount: newRetryCount),
    );
  }

  Future<void> _updateTaskStatus(SyncQueueEntity task, String status) async {
    await AppDatabase.instance.syncQueueDao.updateSyncTask(
      task.copyWith(status: status),
    );
  }

  Future<bool> _syncChecklist(Map<String, dynamic> payload, Options options) async {
    final String woId = payload['woId'];
    final response = await _dio.post(
      '/api/v1/work-orders/$woId/checklists',
      data: {
        'itemName': payload['itemName'],
        'isCompleted': payload['isCompleted'],
      },
      options: options,
    );
    return response.statusCode == 200 && response.data['success'] == true;
  }

  Future<bool> _syncPhoto(Map<String, dynamic> payload, Options options) async {
    final String woId = payload['woId'];
    final String filePath = payload['filePath'];
    
    final file = File(filePath);
    if (!await file.exists()) {
      return true; // File not found, skip
    }

    final formData = FormData.fromMap({
      'file': await MultipartFile.fromFile(filePath),
    });

    final response = await _dio.post(
      '/api/v1/work-orders/$woId/attachments',
      data: formData,
      options: options,
    );
    return response.statusCode == 200 && response.data['success'] == true;
  }

  Future<bool> _syncStatus(Map<String, dynamic> payload, Options options) async {
    final String woId = payload['woId'];
    final response = await _dio.put(
      '/api/v1/work-orders/$woId/status',
      data: {
        'status': payload['status'],
      },
      options: options,
    );
    return response.statusCode == 200 && response.data['success'] == true;
  }

  Future<bool> _syncNotes(Map<String, dynamic> payload, Options options) async {
    final String woId = payload['woId'];
    final response = await _dio.put(
      '/api/v1/work-orders/$woId/notes',
      data: {
        'resolutionNotes': payload['notes'],
      },
      options: options,
    );
    return response.statusCode == 200 && response.data['success'] == true;
  }
}

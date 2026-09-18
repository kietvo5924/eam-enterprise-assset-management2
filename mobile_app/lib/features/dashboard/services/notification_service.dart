import 'package:flutter/foundation.dart';
import 'package:dio/dio.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:uuid/uuid.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import '../../../core/network/dio_client.dart';
import '../models/notification_model.dart';

class NotificationService {
  final Dio _dio = DioClient().dio;

  /// Fetch paginated notifications with optional filter tabs ('all', 'unread', 'actionable')
  Future<Map<String, dynamic>> getNotifications({
    String tab = 'all',
    int page = 0,
    int size = 20,
  }) async {
    try {
      final Map<String, dynamic> queryParams = {
        'page': page,
        'size': size,
      };

      if (tab == 'unread') {
        queryParams['unread_only'] = 'true';
      } else if (tab == 'actionable') {
        queryParams['is_actionable'] = 'true';
      }

      final response = await _dio.get(
        '/api/v1/notifications/',
        queryParameters: queryParams,
      );

      if (response.statusCode == 200 && response.data != null) {
        final data = response.data['data'] ?? response.data;
        final rawList = (data['content'] as List?) ?? [];
        final items = rawList
            .map((item) => NotificationItem.fromJson(item as Map<String, dynamic>))
            .toList();

        final unreadCount = data['unread_count'] ?? data['unreadCount'] ?? 0;
        final totalElements = data['totalElements'] ?? items.length;
        final isLast = data['last'] ?? true;

        return {
          'items': items,
          'unreadCount': unreadCount,
          'totalElements': totalElements,
          'isLast': isLast,
        };
      }
      return {
        'items': <NotificationItem>[],
        'unreadCount': 0,
        'totalElements': 0,
        'isLast': true,
      };
    } catch (e) {
      return {
        'items': <NotificationItem>[],
        'unreadCount': 0,
        'totalElements': 0,
        'isLast': true,
        'error': e.toString(),
      };
    }
  }

  /// Get real-time unread count
  Future<int> getUnreadCount() async {
    try {
      final response = await _dio.get('/api/v1/notifications/unread-count/');
      if (response.statusCode == 200 && response.data != null) {
        final data = response.data['data'] ?? response.data;
        return data['unread_count'] ?? data['unreadCount'] ?? 0;
      }
    } catch (_) {}
    return 0;
  }

  /// Mark single notification as read
  Future<bool> markAsRead(String id) async {
    try {
      final response = await _dio.post('/api/v1/notifications/$id/read/');
      return response.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  /// Mark all notifications as read
  Future<bool> markAllAsRead() async {
    try {
      final response = await _dio.post('/api/v1/notifications/read-all/');
      return response.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  /// Resolve actionable notification
  Future<bool> resolveAction(String id) async {
    try {
      final response = await _dio.post('/api/v1/notifications/$id/resolve-action/');
      return response.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  /// Initialize FCM listeners and request permissions
  Future<void> initFCM({
    void Function(RemoteMessage)? onMessageReceived,
    void Function(RemoteMessage)? onNotificationOpened,
  }) async {
    try {
      final messaging = FirebaseMessaging.instance;

      // Request push notification permissions (required for iOS and Android 13+)
      final settings = await messaging.requestPermission(
        alert: true,
        badge: true,
        sound: true,
        provisional: false,
      );
      debugPrint('User notification permission status: ${settings.authorizationStatus}');

      // Register device token
      await registerDeviceToken();

      // Listen to token refresh
      messaging.onTokenRefresh.listen((newToken) {
        debugPrint('FCM Token refreshed: $newToken');
        _syncDeviceToken(newToken);
      });

      // Listen for foreground messages
      FirebaseMessaging.onMessage.listen((RemoteMessage message) {
        debugPrint('Foreground FCM notification: ${message.notification?.title}');
        if (onMessageReceived != null) {
          onMessageReceived(message);
        }
      });

      // Listen for notification tap when app is in background
      FirebaseMessaging.onMessageOpenedApp.listen((RemoteMessage message) {
        debugPrint('FCM notification opened app: ${message.messageId}');
        if (onNotificationOpened != null) {
          onNotificationOpened(message);
        }
      });

      // Check if app opened from terminated state by a notification
      final initialMessage = await messaging.getInitialMessage();
      if (initialMessage != null && onNotificationOpened != null) {
        onNotificationOpened(initialMessage);
      }
    } catch (e) {
      debugPrint('initFCM bypassed or error: $e');
      // Still ensure a device token is registered (e.g. fallback UUID)
      await registerDeviceToken();
    }
  }

  /// Helper to send device token to backend
  Future<bool> _syncDeviceToken(String token) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('push_device_token', token);

      final response = await _dio.post('/api/v1/notifications/devices/', data: {
        'device_token': token,
        'device_type': 'ANDROID',
      });
      return response.statusCode == 200 || response.statusCode == 201;
    } catch (e) {
      debugPrint('Failed to sync device token to backend: $e');
      return false;
    }
  }

  /// Register device push token to backend for push notifications
  Future<bool> registerDeviceToken() async {
    String? deviceToken;

    try {
      // 1. Try to get native FCM token
      deviceToken = await FirebaseMessaging.instance.getToken();
      if (deviceToken != null && deviceToken.isNotEmpty) {
        debugPrint('Retrieved native FCM Token: $deviceToken');
      }
    } catch (e) {
      debugPrint('Could not retrieve FCM token (using cached or fallback): $e');
    }

    // 2. Fall back to cached token or UUID
    if (deviceToken == null || deviceToken.isEmpty) {
      final prefs = await SharedPreferences.getInstance();
      deviceToken = prefs.getString('push_device_token');
      if (deviceToken == null || deviceToken.isEmpty) {
        deviceToken = const Uuid().v4();
      }
    }

    return await _syncDeviceToken(deviceToken);
  }
}

import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:flutter/foundation.dart';
import '../constants/api_constants.dart';

class DioClient {
  static final DioClient _instance = DioClient._internal();
  late Dio dio;
  final _secureStorage = const FlutterSecureStorage();
  
  // Variables for Refresh Token Queue
  bool _isRefreshing = false;
  final List<Map<String, dynamic>> _failedRequestsQueue = [];

  factory DioClient() {
    return _instance;
  }

  DioClient._internal() {
    dio = Dio(BaseOptions(
      baseUrl: ApiConstants.baseUrl,
      connectTimeout: ApiConstants.connectTimeout,
      receiveTimeout: ApiConstants.receiveTimeout,
      headers: {
        'Content-Type': 'application/json',
      },
    ));

    // Chỉ log an toàn trong kDebugMode, không in Authorization token hay mật khẩu
    if (kDebugMode) {
      dio.interceptors.add(LogInterceptor(
        request: true,
        requestHeader: false, // Redact Authorization headers
        requestBody: false,   // Redact sensitive credentials in request bodies
        responseHeader: false,
        responseBody: false,
        error: true,
        logPrint: (obj) => debugPrint(obj.toString()),
      ));
    }

    dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) async {
        final token = await _secureStorage.read(key: 'token');
        if (token != null) {
          options.headers['Authorization'] = 'Bearer $token';
        }
        final prefs = await SharedPreferences.getInstance();
        final tenantId = prefs.getString('tenantId');
        if (tenantId != null && tenantId.isNotEmpty) {
          options.headers['X-Tenant-Id'] = tenantId;
        }
        return handler.next(options);
      },
      onError: (DioException e, handler) async {
        if (e.response?.statusCode == 401) {
          // Guard against refresh recursion: if this request was already a retry attempt or is the refresh call itself, do not retry
          if (e.requestOptions.extra['isRetry'] == true || e.requestOptions.path.contains('/auth/refresh')) {
            return handler.next(e);
          }
          debugPrint('Caught 401: Token might be expired.');
          
          // Add the failed request to the queue to retry after refreshing
          _failedRequestsQueue.add({
            'options': e.requestOptions,
            'handler': handler,
          });

          if (!_isRefreshing) {
            _isRefreshing = true;
            String? newToken;
            try {
              final refreshToken = await _secureStorage.read(key: 'refreshToken');
              
              if (refreshToken == null || refreshToken.isEmpty) {
                throw Exception('No refresh token available');
              }

              // Create a new Dio instance to avoid circular interceptor triggers
              final refreshDio = Dio(BaseOptions(baseUrl: ApiConstants.baseUrl));
              final response = await refreshDio.post(
                '/api/v1/auth/refresh',
                data: {'refreshToken': refreshToken},
              );
              
              if (response.statusCode == 200 && response.data['token'] != null) {
                newToken = response.data['token'];
                await _secureStorage.write(key: 'token', value: newToken);
                
                // If there's a new refresh token (rotation), save it too
                if (response.data['refreshToken'] != null) {
                  await _secureStorage.write(key: 'refreshToken', value: response.data['refreshToken']);
                }
              } else {
                throw Exception('Failed to refresh token');
              }
            } catch (refreshError) {
              debugPrint('Refresh token failed: $refreshError');
              // If refresh genuinely fails -> Invalidate auth session but preserve app settings
              await _secureStorage.deleteAll();
              final prefs = await SharedPreferences.getInstance();
              await prefs.remove('token');
              await prefs.remove('refreshToken');
              await prefs.remove('isLoggedIn');
            } finally {
              _isRefreshing = false;
            }

            final pendingRequests = List<Map<String, dynamic>>.from(_failedRequestsQueue);
            _failedRequestsQueue.clear();

            if (newToken != null) {
              // Refresh succeeded: retry queued requests individually
              for (var req in pendingRequests) {
                final options = req['options'] as RequestOptions;
                final reqHandler = req['handler'] as ErrorInterceptorHandler;
                options.headers['Authorization'] = 'Bearer $newToken';
                options.extra['isRetry'] = true;
                try {
                  final retryResponse = await dio.fetch(options);
                  reqHandler.resolve(retryResponse);
                } catch (retryErr) {
                  if (retryErr is DioException) {
                    reqHandler.next(retryErr);
                  } else {
                    reqHandler.next(DioException(requestOptions: options, error: retryErr));
                  }
                }
              }
            } else {
              // Refresh failed: reject all queued requests
              for (var req in pendingRequests) {
                final reqHandler = req['handler'] as ErrorInterceptorHandler;
                reqHandler.next(e);
              }
            }
            return;
          }
          return; // Hold the connection in pending state until refresh is resolved
        }
        return handler.next(e);
      },
    ));
  }
}

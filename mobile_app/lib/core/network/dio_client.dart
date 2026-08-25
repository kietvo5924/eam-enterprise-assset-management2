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

    // Thêm LogInterceptor để in log request/response
    dio.interceptors.add(LogInterceptor(
      request: true,
      requestHeader: true,
      requestBody: true,
      responseHeader: true,
      responseBody: true,
      error: true,
      logPrint: (obj) => debugPrint(obj.toString()),
    ));

    dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) async {
        final token = await _secureStorage.read(key: 'token');
        if (token != null) {
          options.headers['Authorization'] = 'Bearer $token';
        }
        return handler.next(options);
      },
      onError: (DioException e, handler) async {
        if (e.response?.statusCode == 401) {
          // Handle 401 Unauthorized - Token Expired
          debugPrint('Caught 401: Token might be expired.');
          
          // Add the failed request to the queue to retry after refreshing
          _failedRequestsQueue.add({
            'options': e.requestOptions,
            'handler': handler,
          });

          if (!_isRefreshing) {
            _isRefreshing = true;
            try {
              final refreshToken = await _secureStorage.read(key: 'refreshToken');
              
              if (refreshToken == null) {
                throw Exception('No refresh token available');
              }

              // Create a new Dio instance to avoid circular interceptor triggers
              final refreshDio = Dio(BaseOptions(baseUrl: ApiConstants.baseUrl));
              final response = await refreshDio.post(
                '/api/v1/auth/refresh',
                data: {'refreshToken': refreshToken},
              );
              
              if (response.statusCode == 200 && response.data['token'] != null) {
                final newToken = response.data['token'];
                await _secureStorage.write(key: 'token', value: newToken);
                
                // If there's a new refresh token, save it too
                if (response.data['refreshToken'] != null) {
                   await _secureStorage.write(key: 'refreshToken', value: response.data['refreshToken']);
                }

                // Retry all requests in the queue
                for (var req in _failedRequestsQueue) {
                  final options = req['options'] as RequestOptions;
                  final reqHandler = req['handler'] as ErrorInterceptorHandler;
                  
                  // Attach the new token
                  options.headers['Authorization'] = 'Bearer $newToken';
                  
                  // Re-fetch the original API call
                  final retryResponse = await dio.fetch(options);
                  reqHandler.resolve(retryResponse);
                }
                _failedRequestsQueue.clear();
                return; // Return so we don't call handler.next(e)
              } else {
                throw Exception('Failed to refresh token');
              }
            } catch (refreshError) {
              debugPrint('Refresh token failed: $refreshError');
              // If refresh fails -> Force logout
              await _secureStorage.deleteAll();
              final prefs = await SharedPreferences.getInstance();
              await prefs.clear();
              // In a real app, dispatch an event or use a global router key to navigate to Login
            } finally {
              _isRefreshing = false;
              // If there are still items in the queue (meaning refresh failed), reject them
              for (var req in _failedRequestsQueue) {
                final reqHandler = req['handler'] as ErrorInterceptorHandler;
                reqHandler.next(e);
              }
              _failedRequestsQueue.clear();
            }
          }
          return; // Hold the connection in pending state until refresh is resolved
        }
        return handler.next(e);
      },
    ));
  }
}

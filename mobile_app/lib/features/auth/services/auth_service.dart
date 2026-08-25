import 'package:dio/dio.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import '../../../core/network/dio_client.dart';

class AuthService {
  final Dio _dio = DioClient().dio;
  final _secureStorage = const FlutterSecureStorage();

  Future<String?> login(String username, String password) async {
    try {
      final response = await _dio.post('/api/v1/auth/login', data: {
        'username': username,
        'password': password,
      });

      if (response.statusCode == 200) {
        final data = response.data;
        if (data['success'] == true) {
          final payload = data['data'];
          final token = payload['token'];
          final roles = payload['roles'];
          final tenantId = payload['tenantId'];

          final prefs = await SharedPreferences.getInstance();
          
          // Securely store token
          await _secureStorage.write(key: 'token', value: token);
          
          // Store other non-sensitive preferences
          await prefs.setString('username', username);
          await prefs.setString('roles', roles ?? '');
          await prefs.setString('tenantId', tenantId ?? '');
          await prefs.setBool('isLoggedIn', true);
          
          return null; // Return null on success
        } else {
          return data['message'] ?? 'Đăng nhập thất bại';
        }
      }
      return 'Lỗi máy chủ (${response.statusCode})';
    } on DioException catch (e) {
      if (e.response != null) {
        return e.response?.data?['message'] ?? 'Sai tài khoản hoặc mật khẩu';
      }
      return 'Lỗi mạng: ${e.message}';
    } catch (e) {
      return 'Lỗi không xác định: $e';
    }
  }
  Future<String?> changePassword(String oldPassword, String newPassword) async {
    try {
      final response = await _dio.post('/api/v1/auth/change-password', data: {
        'oldPassword': oldPassword,
        'newPassword': newPassword,
      });

      if (response.statusCode == 200) {
        final data = response.data;
        if (data['success'] == true) {
          return null;
        } else {
          return data['message'] ?? 'Đổi mật khẩu thất bại';
        }
      }
      return 'Lỗi máy chủ (${response.statusCode})';
    } on DioException catch (e) {
      if (e.response != null) {
        return e.response?.data?['message'] ?? 'Lỗi khi đổi mật khẩu';
      }
      return 'Lỗi mạng: ${e.message}';
    } catch (e) {
      return 'Lỗi không xác định: $e';
    }
  }

  Future<void> logout() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.clear();
    await _secureStorage.deleteAll();
  }
}

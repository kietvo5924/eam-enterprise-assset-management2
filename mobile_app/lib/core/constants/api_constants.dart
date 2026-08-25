class ApiConstants {
  // Sửa IP ở đây nếu mạng đổi IP
  static const String baseUrl = 'http://10.209.193.197:8080';

  // Standard Network Timeouts
  static const Duration connectTimeout = Duration(seconds: 15);
  static const Duration receiveTimeout = Duration(seconds: 15);
}

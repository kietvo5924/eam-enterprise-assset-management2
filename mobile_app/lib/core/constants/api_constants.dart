class ApiConstants {
  // Django Backend Server URL (http://10.0.2.2:8000 for Android Emulator, http://127.0.0.1:8000 for Desktop)
  static const String baseUrl = 'http://10.0.2.2:8000';

  // Standard Network Timeouts
  static const Duration connectTimeout = Duration(seconds: 15);
  static const Duration receiveTimeout = Duration(seconds: 15);
}

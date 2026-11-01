class ApiConstants {
  // Django Backend Server URL (http://10.0.2.2:8000 for Android Emulator, http://127.0.0.1:8000 for Desktop)
  static const String baseUrl = 'http://10.0.2.2:8000';

  // Standard Network Timeouts
  static const Duration connectTimeout = Duration(seconds: 15);
  static const Duration receiveTimeout = Duration(seconds: 15);

  static String resolveAttachmentUrl(String rawUrl) {
    if (rawUrl.isEmpty) return '';
    final apiUri = Uri.parse(baseUrl);
    String resolved = rawUrl;
    if (rawUrl.startsWith('http://') || rawUrl.startsWith('https://')) {
      resolved = rawUrl;
    } else if (rawUrl.startsWith('/media/') || rawUrl.startsWith('media/')) {
      final path = rawUrl.startsWith('/') ? rawUrl : '/$rawUrl';
      resolved = '$baseUrl$path';
    } else {
      final path = rawUrl.startsWith('/') ? rawUrl : '/$rawUrl';
      resolved = 'http://${apiUri.host}:9900$path';
    }
    if (resolved.contains('localhost')) {
      resolved = resolved.replaceAll('localhost', apiUri.host);
    }
    if (resolved.contains('127.0.0.1')) {
      resolved = resolved.replaceAll('127.0.0.1', apiUri.host);
    }
    return resolved;
  }
}

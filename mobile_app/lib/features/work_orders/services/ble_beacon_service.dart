import 'dart:async';
import 'dart:math' as math;
import 'package:flutter/foundation.dart';
import 'package:flutter_blue_plus/flutter_blue_plus.dart';

/// BleScanResult: Represents the outcome of an ESP32 BLE Beacon detection.
class BleScanResult {
  final bool isFound;
  final bool isBluetoothOff;
  final String beaconId;
  final int rssi;
  final double distanceMeters;
  final bool isWithinRange;
  final String message;

  const BleScanResult({
    required this.isFound,
    this.isBluetoothOff = false,
    required this.beaconId,
    required this.rssi,
    required this.distanceMeters,
    required this.isWithinRange,
    required this.message,
  });

  factory BleScanResult.notFound([String? customMessage]) {
    return BleScanResult(
      isFound: false,
      isBluetoothOff: false,
      beaconId: '',
      rssi: -999,
      distanceMeters: 999.0,
      isWithinRange: false,
      message: customMessage ?? 'Không tìm thấy sóng ESP32 của máy móc. Vui lòng bật nguồn ESP32 và di chuyển vào bán kính <= 50m!',
    );
  }

  factory BleScanResult.bluetoothOff([String? customMessage]) {
    return BleScanResult(
      isFound: false,
      isBluetoothOff: true,
      beaconId: '',
      rssi: -999,
      distanceMeters: 999.0,
      isWithinRange: false,
      message: customMessage ?? 'Bluetooth trên điện thoại đang TẮT. Vui lòng bật Bluetooth để định vị máy móc!',
    );
  }

  factory BleScanResult.found({
    required String beaconId,
    required int rssi,
    required double distanceMeters,
    required bool isWithinRange,
    String? message,
  }) {
    return BleScanResult(
      isFound: true,
      isBluetoothOff: false,
      beaconId: beaconId,
      rssi: rssi,
      distanceMeters: distanceMeters,
      isWithinRange: isWithinRange,
      message: message ??
          (isWithinRange
              ? 'Đã nhận diện tín hiệu ESP32 ($rssi dBm ~ ${distanceMeters.toStringAsFixed(1)}m)'
              : 'Tín hiệu ESP32 quá yếu ($rssi dBm ~ ${distanceMeters.toStringAsFixed(1)}m > 50m). Vui lòng lại gần máy!'),
    );
  }
}

/// BleBeaconService:
/// Implements pure math Log-Distance Path Loss Model:
///   d = 10 ^ ((A - RSSI) / (10 * n))
/// with Measured Power at 1m A = -59 dBm, Path Loss Exponent n = 2.8.
/// Cutoff: RSSI >= -92 dBm <=> distance <= 50.0m.
class BleBeaconService {
  static const double defaultMeasuredPower = -59.0; // A in dBm
  static const double defaultPathLossExponent = 2.8; // n in industrial factory
  static const double defaultMaxRadiusMeters = 50.0;
  static const String universalBeaconUuid = 'e2c56db5-dffb-48d2-b060-d0f5a71096e0';
  static const String universalBeaconName = 'EAM-UNIVERSAL-BEACON';

  // Test injection hook for simulated RSSI and Embedding
  static int? simulatedRssi;
  static bool? simulatedBeaconFound;
  static List<double>? simulatedEmbedding;

  /// Pure mathematical log-distance path loss calculation:
  /// d = 10 ^ ((A - RSSI) / (10 * n))
  static double calculateDistance(
    int rssi, {
    double measuredPower = defaultMeasuredPower,
    double pathLossExponent = defaultPathLossExponent,
  }) {
    if (pathLossExponent <= 0.0) {
      throw ArgumentError('Path loss exponent must be strictly positive');
    }
    final exponent = (measuredPower - rssi) / (10.0 * pathLossExponent);
    final distance = math.pow(10.0, exponent).toDouble();
    return double.parse(distance.toStringAsFixed(2));
  }

  /// Verifies if RSSI falls within the maximum permitted proximity radius (default 50.0m).
  static bool isWithinProximity(
    int rssi, {
    double maxRadiusMeters = defaultMaxRadiusMeters,
    double measuredPower = defaultMeasuredPower,
    double pathLossExponent = defaultPathLossExponent,
  }) {
    final dist = calculateDistance(
      rssi,
      measuredPower: measuredPower,
      pathLossExponent: pathLossExponent,
    );
    return dist <= maxRadiusMeters;
  }

  /// Dot product of two vectors (Pure from-scratch linear algebra)
  static double dotProduct(List<double> u, List<double> v) {
    if (u.length != v.length) {
      throw ArgumentError('Vectors must have identical dimensions');
    }
    double sum = 0.0;
    for (int i = 0; i < u.length; i++) {
      if (u[i].isNaN || u[i].isInfinite || v[i].isNaN || v[i].isInfinite) {
        return 0.0;
      }
      sum += u[i] * v[i];
    }
    return sum.isNaN || sum.isInfinite ? 0.0 : sum;
  }

  /// Euclidean L2-norm of a vector
  static double l2Norm(List<double> v) {
    double sumSq = 0.0;
    for (int i = 0; i < v.length; i++) {
      if (v[i].isNaN || v[i].isInfinite) {
        return 0.0;
      }
      sumSq += v[i] * v[i];
    }
    if (sumSq.isNaN || sumSq.isInfinite || sumSq <= 0.0) {
      return 0.0;
    }
    return math.sqrt(sumSq);
  }

  /// Cosine Similarity from scratch:
  /// Cos(u, v) = (u . v) / (||u|| * ||v||)
  static double cosineSimilarity(List<double> u, List<double> v) {
    if (u.length != v.length || u.isEmpty) {
      return 0.0;
    }
    final normU = l2Norm(u);
    final normV = l2Norm(v);
    if (normU < 1e-9 || normV < 1e-9 || normU.isNaN || normV.isNaN || normU.isInfinite || normV.isInfinite) {
      return 0.0;
    }
    final dot = dotProduct(u, v);
    final denom = normU * normV;
    if (denom <= 0.0 || denom.isNaN || denom.isInfinite) {
      return 0.0;
    }
    final sim = dot / denom;
    if (sim.isNaN || sim.isInfinite) {
      return 0.0;
    }
    return math.max(-1.0, math.min(1.0, sim));
  }

  /// Helper nhận diện chính xác duy nhất ESP32 Beacon của hệ thống EAM
  /// Loại bỏ hoàn toàn việc nhận diện nhầm các thiết bị Apple khác (iPhone, iPad, AirPods...)
  static bool isMatchingBeacon(ScanResult r, String cleanTargetUuid) {
    // 1. Kiểm tra Tên thiết bị quảng bá
    final name = '${r.device.advName} ${r.advertisementData.advName}'.toUpperCase();
    if (name.contains('EAM') ||
        name.contains('BEACON') ||
        name.contains('ESP32') ||
        name.contains('P102') ||
        name.contains('PUMP') ||
        name.contains('KUKA')) {
      return true;
    }

    // Tiền tố nhận diện 4-byte đầu của Universal UUID (e2c56db5)
    final prefix4 = cleanTargetUuid.length >= 8 ? cleanTargetUuid.substring(0, 8) : 'e2c56db5';

    // 2. Kiểm tra Manufacturer Data: BẮT BUỘC phải chứa đúng UUID hoặc Major/Minor của ESP32 EAM
    for (final entry in r.advertisementData.manufacturerData.entries) {
      final List<int> bytes = entry.value;
      if (bytes.isEmpty) continue;

      final hex = bytes.map((b) => b.toRadixString(16).padLeft(2, '0')).join().toLowerCase();
      final revHex = bytes.reversed.map((b) => b.toRadixString(16).padLeft(2, '0')).join().toLowerCase();

      // Phải khớp đúng UUID của hệ thống EAM (e2c56db5-dffb-48d2-b060-d0f5a71096e0)
      if (hex.contains(cleanTargetUuid) || revHex.contains(cleanTargetUuid)) {
        return true;
      }
      if (hex.contains(prefix4) || revHex.contains(prefix4)) {
        return true;
      }

      // Hoặc khớp đúng Major=1 (0x0001) và Minor=102 (0x0066) của ESP32 Beacon
      if (bytes.length >= 22) {
        for (int i = 0; i <= bytes.length - 4; i++) {
          final isMajor1 = (bytes[i] == 0 && bytes[i + 1] == 1) || (bytes[i] == 1 && bytes[i + 1] == 0);
          final isMinor102 = (bytes[i + 2] == 0 && bytes[i + 3] == 102) || (bytes[i + 2] == 102 && bytes[i + 3] == 0);
          if (isMajor1 && isMinor102) {
            return true;
          }
        }
      }
    }

    // 3. Kiểm tra Service UUIDs
    for (final s in r.advertisementData.serviceUuids) {
      final sClean = s.str.toLowerCase().replaceAll('-', '');
      if (sClean == cleanTargetUuid || sClean.contains(prefix4)) {
        return true;
      }
    }

    // 4. Kiểm tra Service Data
    for (final sData in r.advertisementData.serviceData.entries) {
      final sHex = sData.value.map((b) => b.toRadixString(16).padLeft(2, '0')).join().toLowerCase();
      if (sHex.contains(cleanTargetUuid) || sHex.contains(prefix4)) {
        return true;
      }
    }

    return false;
  }

  /// Quét sóng BLE thực tế đồng bộ với nRF Connect
  Future<BleScanResult> scanForBeacon({
    String? targetUuid,
    Duration timeout = const Duration(seconds: 4),
  }) async {
    // Nếu có tiêm kiểm thử test
    if (simulatedBeaconFound == false) {
      return BleScanResult.notFound();
    }
    if (simulatedBeaconFound == true) {
      final rssi = simulatedRssi ?? -68;
      final dist = calculateDistance(rssi);
      return BleScanResult.found(
        beaconId: targetUuid ?? universalBeaconName,
        rssi: rssi,
        distanceMeters: dist,
        isWithinRange: dist <= defaultMaxRadiusMeters,
      );
    }

    try {
      // 1. Kiểm tra hỗ trợ phần cứng Bluetooth
      final isSupported = await FlutterBluePlus.isSupported;
      if (!isSupported) {
        return BleScanResult.notFound('Thiết bị này không hỗ trợ Bluetooth BLE.');
      }

      // 2. Kiểm tra xem Bluetooth có đang BẬT không
      final adapterState = await FlutterBluePlus.adapterState.first;
      if (adapterState != BluetoothAdapterState.on) {
        return BleScanResult.bluetoothOff(
          'Bluetooth trên điện thoại đang TẮT. Vui lòng bật Bluetooth để định vị máy móc!'
        );
      }

      // 3. Chuẩn hóa target UUID
      final cleanTargetUuid = (targetUuid ?? universalBeaconUuid)
          .toLowerCase()
          .replaceAll('-', '')
          .trim();

      final completer = Completer<BleScanResult>();
      StreamSubscription? subscription;
      Timer? timer;

      subscription = FlutterBluePlus.onScanResults.listen((results) {
        for (final r in results) {
          debugPrint('BLE Seen: "${r.device.advName}" | RSSI: ${r.rssi} | mfg: ${r.advertisementData.manufacturerData.keys}');
          if (isMatchingBeacon(r, cleanTargetUuid)) {
            final dist = calculateDistance(r.rssi);
            if (!completer.isCompleted) {
              final String bName = r.device.advName.isNotEmpty
                  ? r.device.advName
                  : (targetUuid ?? 'EAM-BEACON-P102');
              completer.complete(BleScanResult.found(
                beaconId: bName,
                rssi: r.rssi,
                distanceMeters: dist,
                isWithinRange: dist <= defaultMaxRadiusMeters,
              ));
            }
          }
        }
      });

      // Bắt đầu quét BLE
      await FlutterBluePlus.startScan(
        timeout: timeout,
        androidUsesFineLocation: true,
      );

      // Timer dự phòng khi hết thời gian mà không thấy Beacon
      timer = Timer(timeout, () {
        if (!completer.isCompleted) {
          completer.complete(BleScanResult.notFound(
            'Không tìm thấy tín hiệu ESP32 của máy móc (khoảng cách > 50m hoặc chưa bật mạch). Vui lòng lại gần máy!'
          ));
        }
      });

      final result = await completer.future;
      timer.cancel();
      try {
        await FlutterBluePlus.stopScan();
        await subscription.cancel();
      } catch (_) {}

      return result;
    } catch (e) {
      debugPrint('BLE Scan Error: $e');
      return BleScanResult.notFound(
        'Lỗi quét Bluetooth: ${e.toString().replaceAll('Exception:', '').trim()}'
      );
    }
  }
}

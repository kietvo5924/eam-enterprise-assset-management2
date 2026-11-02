import 'package:flutter_test/flutter_test.dart';
import 'package:mobile_app/features/work_orders/services/ble_beacon_service.dart';
import 'package:mobile_app/features/work_orders/models/work_order.dart';

void main() {
  group('Phase 11.7: BLE Beacon & Micro-Geofencing Unit Tests', () {
    test('TC-BLE-01: Calculate log-distance at standard 1-meter RSSI (-59 dBm)', () {
      final distance = BleBeaconService.calculateDistance(-59);
      expect(distance, 1.0);
    });

    test('TC-BLE-02: Calculate distance at typical factory RSSI (-68 dBm)', () {
      final distance = BleBeaconService.calculateDistance(-68);
      expect(distance, greaterThan(1.5));
      expect(distance, lessThan(3.0));
      expect(BleBeaconService.isWithinProximity(-68, maxRadiusMeters: 50.0), isTrue);
    });

    test('TC-BLE-03: Edge cutoff verification RSSI -92 dBm is within 50m radius', () {
      expect(BleBeaconService.isWithinProximity(-92, maxRadiusMeters: 50.0), isTrue);
    });

    test('TC-BLE-04: Far signal RSSI -115 dBm exceeds 50m boundary', () {
      final distance = BleBeaconService.calculateDistance(-115);
      expect(distance, greaterThan(50.0));
      expect(BleBeaconService.isWithinProximity(-115, maxRadiusMeters: 50.0), isFalse);
    });

    test('TC-BLE-05: From-scratch Cosine Similarity and L2-Norm linear algebra', () {
      final u = [1.0, 0.0, 0.0];
      final v = [1.0, 0.0, 0.0];
      final w = [0.0, 1.0, 0.0];
      final opp = [-1.0, 0.0, 0.0];

      expect(BleBeaconService.cosineSimilarity(u, v), closeTo(1.0, 1e-5));
      expect(BleBeaconService.cosineSimilarity(u, w), closeTo(0.0, 1e-5));
      expect(BleBeaconService.cosineSimilarity(u, opp), closeTo(-1.0, 1e-5));
    });

    test('TC-BLE-06: 128-d vector Cosine threshold >= 0.72 acceptance', () {
      // Create two highly correlated 128-d vectors
      final List<double> u = List.generate(128, (i) => (i + 1) * 0.01);
      final List<double> v = List.generate(128, (i) => (i + 1) * 0.0105);

      final sim = BleBeaconService.cosineSimilarity(u, v);
      expect(sim, greaterThanOrEqualTo(0.72));
    });

    test('TC-BLE-07: Scan simulation detects beacon in range and handles missing', () async {
      final service = BleBeaconService();

      // In-range scan
      BleBeaconService.simulatedBeaconFound = true;
      BleBeaconService.simulatedRssi = -65;
      final res1 = await service.scanForBeacon(timeout: const Duration(milliseconds: 10));
      expect(res1.isFound, isTrue);
      expect(res1.isWithinRange, isTrue);
      expect(res1.rssi, -65);

      // Out-of-range scan (> 50m)
      BleBeaconService.simulatedRssi = -118;
      final res2 = await service.scanForBeacon(timeout: const Duration(milliseconds: 10));
      expect(res2.isFound, isTrue);
      expect(res2.isWithinRange, isFalse);

      // Not found scan
      BleBeaconService.simulatedBeaconFound = false;
      final res3 = await service.scanForBeacon(timeout: const Duration(milliseconds: 10));
      expect(res3.isFound, isFalse);
      expect(res3.isWithinRange, isFalse);

      // Reset test hooks
      BleBeaconService.simulatedBeaconFound = null;
      BleBeaconService.simulatedRssi = null;
    });

    test('TC-BLE-08: WorkOrder model parses requireBleBeacon flag and defaults to true', () {
      final jsonDefault = {
        'id': 'wo-1',
        'title': 'Test Machine WO',
        'status': 'ASSIGNED',
      };
      final wo1 = WorkOrder.fromJson(jsonDefault);
      expect(wo1.requireBleBeacon, isTrue);

      final jsonExempt = {
        'id': 'wo-2',
        'title': 'Chair Repair WO',
        'status': 'ASSIGNED',
        'asset': {
          'id': 'asset-chair',
          'name': 'Office Chair',
          'requireBleBeacon': false,
        }
      };
      final wo2 = WorkOrder.fromJson(jsonExempt);
      expect(wo2.requireBleBeacon, isFalse);
    });

    test('TC-BLE-09: Cosine similarity protects against NaN and Inf values', () {
      final nanVec = [double.nan, 0.0, 1.0];
      final validVec = [1.0, 0.0, 0.0];
      final infVec = [double.infinity, 0.0, 1.0];

      expect(BleBeaconService.cosineSimilarity(nanVec, validVec), 0.0);
      expect(BleBeaconService.cosineSimilarity(infVec, validVec), 0.0);
    });

    test('TC-BLE-10: Path loss exponent validation throws on non-positive input', () {
      expect(() => BleBeaconService.calculateDistance(-68, pathLossExponent: 0.0), throwsArgumentError);
      expect(() => BleBeaconService.calculateDistance(-68, pathLossExponent: -1.5), throwsArgumentError);
    });
  });
}

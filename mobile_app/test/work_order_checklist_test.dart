import 'package:flutter_test/flutter_test.dart';
import 'package:mobile_app/features/work_orders/models/work_order.dart';

void main() {
  group('WorkOrderChecklist and Measurement Tests', () {
    test('TC-WO-CHK-01: Correctly parse WorkOrderChecklist with measurement fields', () {
      final json = {
        'id': 'chk-001',
        'itemName': 'Đo kiểm độ rung RMS',
        'completed': true,
        'inputType': 'NUMBER',
        'expectedValue': '<= 4.5 mm/s (ISO 10816-3)',
        'actualValue': '1.25',
        'isMandatory': true,
      };

      final checklist = WorkOrderChecklist.fromJson(json);

      expect(checklist.id, 'chk-001');
      expect(checklist.itemName, 'Đo kiểm độ rung RMS');
      expect(checklist.isCompleted, isTrue);
      expect(checklist.inputType, 'NUMBER');
      expect(checklist.expectedValue, '<= 4.5 mm/s (ISO 10816-3)');
      expect(checklist.actualValue, '1.25');
      expect(checklist.isMandatory, isTrue);
    });

    test('TC-WO-CHK-02: toJson produces matching payload for backend API and sync queue', () {
      final checklist = WorkOrderChecklist(
        id: 'chk-002',
        itemName: 'Đo nhiệt độ ổ trục động cơ',
        isCompleted: false,
        inputType: 'NUMBER',
        expectedValue: '< 70°C',
        actualValue: '62.5',
        isMandatory: true,
      );

      final json = checklist.toJson();

      expect(json['id'], 'chk-002');
      expect(json['itemName'], 'Đo nhiệt độ ổ trục động cơ');
      expect(json['completed'], isFalse);
      expect(json['inputType'], 'NUMBER');
      expect(json['expectedValue'], '< 70°C');
      expect(json['actualValue'], '62.5');
      expect(json['isMandatory'], isTrue);
    });

    test('TC-WO-CHK-03: WorkOrder.fromJson parses nested checklists and measurement items', () {
      final woJson = {
        'id': 'wo-uuid-12345678',
        'code': 'WO-2026-0001',
        'title': 'Bảo trì phòng ngừa Băng tải',
        'description': 'Đo kiểm số liệu rung và nhiệt độ',
        'status': 'IN_PROGRESS',
        'priority': 'HIGH',
        'checklists': [
          {
            'id': 'c1',
            'itemName': 'Kiểm tra khớp nối cơ khí',
            'completed': true,
            'inputType': 'PASS_FAIL',
            'isMandatory': false,
          },
          {
            'id': 'c2',
            'itemName': 'Đo độ rung RMS',
            'completed': false,
            'inputType': 'NUMBER',
            'expectedValue': '<= 4.5 mm/s',
            'actualValue': null,
            'isMandatory': true,
          }
        ],
        'attachments': [],
      };

      final wo = WorkOrder.fromJson(woJson);

      expect(wo.id, 'wo-uuid-12345678');
      expect(wo.code, 'WO-2026-0001');
      expect(wo.checklists.length, 2);

      final standardItem = wo.checklists[0];
      expect(standardItem.inputType, 'PASS_FAIL');
      expect(standardItem.isMandatory, isFalse);
      expect(standardItem.isCompleted, isTrue);

      final measurementItem = wo.checklists[1];
      expect(measurementItem.inputType, 'NUMBER');
      expect(measurementItem.isMandatory, isTrue);
      expect(measurementItem.isCompleted, isFalse);
      expect(measurementItem.expectedValue, '<= 4.5 mm/s');
    });

    test('TC-WO-CHK-04: Mandatory checklist validation correctly detects uncompleted mandatory items', () {
      final checklists = [
        WorkOrderChecklist(
          id: '1',
          itemName: 'Bước tùy chọn',
          isCompleted: false,
          isMandatory: false,
        ),
        WorkOrderChecklist(
          id: '2',
          itemName: 'Đo độ rung bắt buộc',
          isCompleted: false,
          isMandatory: true,
          inputType: 'NUMBER',
        ),
      ];

      // Any uncompleted mandatory item blocks completion
      final hasMissingMandatory = checklists.any((c) => c.isMandatory && !c.isCompleted);
      expect(hasMissingMandatory, isTrue);

      // Once the mandatory item is completed, validation passes even if optional is incomplete
      checklists[1].isCompleted = true;
      final hasMissingMandatoryAfter = checklists.any((c) => c.isMandatory && !c.isCompleted);
      expect(hasMissingMandatoryAfter, isFalse);
    });
  });
}

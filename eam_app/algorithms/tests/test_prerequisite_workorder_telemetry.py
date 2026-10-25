import uuid
from decimal import Decimal
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model

from core.models import Tenant
from core.tenant_context import clear_current_tenant
from assets.models import Asset, AssetCategory, Location, SparePart, Tool, MeterReading, AssetAnomalyAlert
from workorders.models import WorkOrder, WorkOrderChecklistItem, WorkOrderAttachment
from workorders.services import WorkOrderTransitionService
from workorders.serializers import WorkOrderStatusUpdateSerializer, WorkOrderSerializer
from assets.serializers import MeterReadingCreateSerializer, MeterReadingSerializer
from algorithms.anomaly_detection.engine import ConditionMonitoringEngine
from algorithms.anomaly_detection.iso_standards import get_iso_thresholds_for_asset, evaluate_iso_10816

User = get_user_model()


class PrerequisiteWorkOrderTelemetryTests(TestCase):
    def setUp(self):
        clear_current_tenant()
        self.tenant = Tenant.objects.create(name="Test Tenant Telemetry", tenant_code=f"T-TEL-{uuid.uuid4().hex[:6]}")
        self.tenant_id = self.tenant.id
        self.user = User.objects.create_user(
            username=f'tech_tester_{uuid.uuid4().hex[:6]}',
            email='tech@test.com',
            password='password123',
            tenant=self.tenant
        )
        self.loc = Location.objects.create(
            name='Xưởng Cơ Điện',
            code='ZONE_CD_01',
            tenant=self.tenant
        )
        self.category = AssetCategory.objects.create(
            name='Động cơ điện công nghiệp',
            tenant=self.tenant
        )
        self.spare_part = SparePart.objects.create(
            name='Vòng bi SKF 6205-2RSH',
            part_number='SKF-6205',
            quantity_in_stock=Decimal('10.00'),
            tenant=self.tenant,
            location=self.loc
        )
        self.asset = Asset.objects.create(
            name='Bơm ly tâm P-101',
            qr_code='P101-TEST',
            category=self.category,
            location=self.loc,
            primary_spare_part=self.spare_part,
            tenant=self.tenant
        )
        self.tool = Tool.objects.create(
            code='VIB_METER',
            name='Máy đo rung Fluke 805',
            available_quantity=2,
            is_active=True,
            tenant=self.tenant,
            location=self.loc
        )

    def test_1_transition_service_concurrency_lock_and_idempotency(self):
        """TC-1: WorkOrderTransitionService khóa select_for_update và đảm bảo idempotency khi gọi lặp lại."""
        wo = WorkOrder.objects.create(
            title='Bảo trì định kỳ máy bơm',
            status='IN_PROGRESS',
            asset=self.asset,
            assigned_to=self.user,
            tenant_id=self.tenant_id
        )
        WorkOrderAttachment.objects.create(
            work_order=wo,
            file_url='/uploads/proof.jpg',
            file_name='proof.jpg',
            file_type='image/jpeg',
            file_size=1024,
            tenant_id=self.tenant_id
        )

        completed_wo_1 = WorkOrderTransitionService.complete_work_order(
            work_order_id=wo.id,
            user=self.user,
            resolution_notes='Đã kiểm tra và bôi trơn hoàn tất.',
            maintenance_action='GENERAL',
            tenant_id=self.tenant_id
        )
        self.assertEqual(completed_wo_1.status, 'COMPLETED')
        self.assertIsNotNone(completed_wo_1.completion_processed_at)

        # Gọi lại lần 2: phải idempotent trả về nguyên trạng, không báo lỗi
        completed_wo_2 = WorkOrderTransitionService.complete_work_order(
            work_order_id=wo.id,
            user=self.user,
            resolution_notes='Lặp lại thao tác',
            maintenance_action='GENERAL',
            tenant_id=self.tenant_id
        )
        self.assertEqual(completed_wo_2.id, completed_wo_1.id)
        self.assertEqual(completed_wo_2.status, 'COMPLETED')

    def test_2_signal_idempotency_with_legacy_completed_wo(self):
        """TC-2: WorkOrder đã hoàn thành trong quá khứ không quét đóng băng dữ liệu mới khi được lưu lại."""
        now = timezone.now()
        legacy_wo = WorkOrder.objects.create(
            title='Phiếu cũ hoàn thành năm ngoái',
            status='COMPLETED',
            asset=self.asset,
            completed_at=now - timedelta(days=30),
            completion_processed_at=now - timedelta(days=30),
            maintenance_action='GENERAL',
            tenant_id=self.tenant_id
        )

        # Số đo mới sau khi phiếu cũ đã hoàn thành
        fresh_reading = MeterReading.objects.create(
            asset=self.asset,
            reading_value=1.5,
            reading_date=now - timedelta(days=5),
            is_pre_repair=False,
            tenant_id=self.tenant_id
        )

        # Save lại WorkOrder cũ
        legacy_wo.resolution_notes = 'Cập nhật ghi chú lưu trữ'
        legacy_wo.save()

        fresh_reading.refresh_from_db()
        self.assertFalse(fresh_reading.is_pre_repair, "Số đo mới không được bị signal đóng băng nhầm khi save lại WO cũ.")

    def test_3_micro_maintenance_preserves_reading_window(self):
        """TC-3: Bảo trì vi mô (bơm mỡ/siết ốc) không đánh dấu is_pre_repair=True cho các số đo trước đó."""
        now = timezone.now()
        r1 = MeterReading.objects.create(
            asset=self.asset,
            reading_value=2.1,
            reading_date=now - timedelta(hours=2),
            is_pre_repair=False,
            measurement_phase='ROUTINE',
            tenant_id=self.tenant_id
        )
        wo = WorkOrder.objects.create(
            title='Bơm mỡ bôi trơn ổ trục',
            status='IN_PROGRESS',
            asset=self.asset,
            assigned_to=self.user,
            tenant_id=self.tenant_id
        )
        WorkOrderAttachment.objects.create(
            work_order=wo,
            file_url='/uploads/grease.jpg',
            file_name='grease.jpg',
            file_type='image/jpeg',
            file_size=2048,
            tenant_id=self.tenant_id
        )

        WorkOrderTransitionService.complete_work_order(
            work_order_id=wo.id,
            user=self.user,
            resolution_notes='Đã bơm mỡ lithium chịu nhiệt.',
            maintenance_action='MICRO_MAINTENANCE',
            tenant_id=self.tenant_id
        )

        r1.refresh_from_db()
        self.assertFalse(r1.is_pre_repair, "Bảo trì vi mô không được xóa chuỗi đo hoặc đánh dấu is_pre_repair=True.")

    def test_4_core_replacement_triggers_window_reset(self):
        """TC-4: Đại tu thay thế cụm cốt lõi (CORE_REPLACEMENT) đóng băng chuỗi cũ và đưa RUL về CALIBRATING."""
        now = timezone.now()
        old_reading = MeterReading.objects.create(
            asset=self.asset,
            reading_value=6.8,
            reading_date=now - timedelta(hours=5),
            is_pre_repair=False,
            measurement_phase='ROUTINE',
            tenant_id=self.tenant_id
        )
        wo = WorkOrder.objects.create(
            title='Thay mới vòng bi SKF cốt lõi',
            status='IN_PROGRESS',
            asset=self.asset,
            assigned_to=self.user,
            tenant_id=self.tenant_id
        )
        WorkOrderAttachment.objects.create(
            work_order=wo,
            file_url='/uploads/bearing_swap.jpg',
            file_name='bearing_swap.jpg',
            file_type='image/jpeg',
            file_size=4096,
            tenant_id=self.tenant_id
        )

        WorkOrderTransitionService.complete_work_order(
            work_order_id=wo.id,
            user=self.user,
            resolution_notes='Đã thay mới vòng bi SKF 6205.',
            maintenance_action='CORE_REPLACEMENT',
            post_repair_data={'vibration': 0.95, 'temperature': 42.0, 'load_factor': 1.0},
            tenant_id=self.tenant_id
        )

        old_reading.refresh_from_db()
        self.assertTrue(old_reading.is_pre_repair, "Số đo cũ phải được đóng băng khi đại tu cụm cốt lõi.")
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.rul_risk_level, 'CALIBRATING')
        self.assertIsNotNone(self.asset.last_core_overhaul_at)

    def test_5_diagnostic_and_acceptance_phases_preserved(self):
        """TC-5: Số đo nghiệm thu POST_REPAIR_ACCEPTANCE không bao giờ bị đánh dấu is_pre_repair=True."""
        now = timezone.now()
        wo = WorkOrder.objects.create(
            title='Sửa chữa đại tu',
            status='IN_PROGRESS',
            asset=self.asset,
            assigned_to=self.user,
            tenant_id=self.tenant_id
        )
        WorkOrderAttachment.objects.create(
            work_order=wo,
            file_url='/uploads/acceptance.jpg',
            file_name='acceptance.jpg',
            file_type='image/jpeg',
            file_size=1024,
            tenant_id=self.tenant_id
        )

        WorkOrderTransitionService.complete_work_order(
            work_order_id=wo.id,
            user=self.user,
            resolution_notes='Đại tu hoàn tất và nghiệm thu êm ái.',
            maintenance_action='CORE_REPLACEMENT',
            post_repair_data={'vibration': 0.85, 'temperature': 38.5, 'load_factor': 1.0},
            tenant_id=self.tenant_id
        )

        acceptance_reading = MeterReading.objects.filter(
            asset=self.asset,
            measurement_phase='POST_REPAIR_ACCEPTANCE'
        ).first()
        self.assertIsNotNone(acceptance_reading)
        self.assertFalse(acceptance_reading.is_pre_repair, "Số đo nghiệm thu POST_REPAIR_ACCEPTANCE phải luôn có is_pre_repair=False.")

    def test_6_checklist_edit_updates_existing_telemetry_not_duplicates(self):
        """TC-6: Sửa checklist kiểu NUMBER nhiều lần chỉ cập nhật bản ghi MeterReading hiện có, không tạo dòng mới."""
        wo = WorkOrder.objects.create(
            title='Kiểm tra định kỳ',
            status='IN_PROGRESS',
            asset=self.asset,
            tenant_id=self.tenant_id
        )
        chk_item = WorkOrderChecklistItem.objects.create(
            work_order=wo,
            item_name='Đo vận tốc rung RMS',
            input_type='NUMBER',
            tenant_id=self.tenant_id
        )

        # Lần nhập 1: 2.5 mm/s
        ConditionMonitoringEngine.process_readings(
            asset=self.asset,
            readings_data=[{'metricCode': 'VIBRATION', 'value': 2.5, 'unit': 'mm/s'}],
            tenant=self.asset.tenant,
            work_order=wo,
            checklist_item=chk_item
        )
        count_1 = MeterReading.objects.filter(checklist_item=chk_item).count()
        self.assertEqual(count_1, 1)

        # Lần sửa 2: 2.7 mm/s (kỹ thuật viên chỉnh lại)
        ConditionMonitoringEngine.process_readings(
            asset=self.asset,
            readings_data=[{'metricCode': 'VIBRATION', 'value': 2.7, 'unit': 'mm/s'}],
            tenant=self.asset.tenant,
            work_order=wo,
            checklist_item=chk_item
        )
        count_2 = MeterReading.objects.filter(checklist_item=chk_item).count()
        self.assertEqual(count_2, 1, "Sửa checklist không được tạo thêm bản ghi MeterReading mới.")
        updated_reading = MeterReading.objects.filter(checklist_item=chk_item).first()
        self.assertEqual(float(updated_reading.reading_value), 2.7)

    def test_7_inspection_round_id_groups_synchronized_vector(self):
        """TC-7: Các kênh đo trong cùng một phiên đo chia sẻ chung round_id."""
        round_uuid = uuid.uuid4()
        res = ConditionMonitoringEngine.process_readings(
            asset=self.asset,
            readings_data=[
                {'metricCode': 'VIBRATION', 'value': 1.8, 'unit': 'mm/s'},
                {'metricCode': 'TEMPERATURE', 'value': 52.0, 'unit': '°C'},
            ],
            round_id=round_uuid,
            tenant=self.asset.tenant
        )
        readings = MeterReading.objects.filter(round_id=round_uuid)
        self.assertEqual(readings.count(), 2)
        metrics = set(readings.values_list('metric_code', flat=True))
        self.assertEqual(metrics, {'VIBRATION', 'TEMPERATURE'})

    def test_8_anomaly_detection_does_not_deduct_inventory(self):
        """TC-8: AI phát hiện bất thường nghiêm trọng chỉ gợi ý required_spare_parts mà không trừ kho."""
        stock_before = self.spare_part.quantity_in_stock
        # Ghi nhận chỉ số rung 15.0 mm/s (rất nguy hiểm, vượt OEM và ISO Zone D)
        ConditionMonitoringEngine.process_readings(
            asset=self.asset,
            readings_data=[{'metricCode': 'VIBRATION', 'value': 15.0, 'unit': 'mm/s'}],
            tenant=self.asset.tenant
        )
        self.spare_part.refresh_from_db()
        self.assertEqual(self.spare_part.quantity_in_stock, stock_before, "AI anomaly detection TUYỆT ĐỐI KHÔNG được tự ý trừ kho vật tư.")

        # Kiểm tra phiếu khẩn cấp được sinh ra chứa required_spare_parts gợi ý
        alert = AssetAnomalyAlert.objects.filter(asset=self.asset, severity='CRITICAL').first()
        self.assertIsNotNone(alert)
        if alert and alert.draft_work_order:
            self.assertIn(str(self.spare_part.id), alert.draft_work_order.required_spare_parts)

    def test_9_tool_assignment_validates_tenant_inventory(self):
        """TC-9: AI chỉ gợi ý các dụng cụ đang có sẵn và khả dụng trong kho của tenant."""
        # Tạo thêm 1 tool không khả dụng
        Tool.objects.create(
            code='TORQUE_WRENCH',
            name='Cờ lê lực',
            available_quantity=0,  # Hết hàng
            is_active=True,
            tenant_id=self.tenant_id
        )

        ConditionMonitoringEngine.process_readings(
            asset=self.asset,
            readings_data=[{'metricCode': 'VIBRATION', 'value': 18.0, 'unit': 'mm/s'}],
            tenant=self.asset.tenant
        )
        alert = AssetAnomalyAlert.objects.filter(asset=self.asset, severity='CRITICAL').first()
        if alert and alert.draft_work_order:
            wo = alert.draft_work_order
            # VIB_METER còn hàng nên có thể xuất hiện, TORQUE_WRENCH available_quantity=0 không được xuất hiện
            self.assertNotIn('TORQUE_WRENCH', wo.required_tools)

    def test_10_mobile_api_backward_compatibility_and_serializers(self):
        """TC-10: Serializers xử lý mượt mà các trường mới mà không làm gãy Mobile App."""
        # WorkOrderStatusUpdateSerializer
        s1 = WorkOrderStatusUpdateSerializer(data={
            'status': 'COMPLETED',
            'resolutionNotes': 'Kiểm tra xong',
            'maintenanceAction': 'MICRO_MAINTENANCE',
            'postRepairVibration': 1.1,
            'postRepairTemperature': 48.0
        })
        self.assertTrue(s1.is_valid(), s1.errors)

        # Hỗ trợ backward-compatible payload không có trường mới
        s2 = WorkOrderStatusUpdateSerializer(data={
            'status': 'COMPLETED',
            'resolutionNotes': 'Phiếu từ Mobile cũ'
        })
        self.assertTrue(s2.is_valid(), s2.errors)
        self.assertEqual(s2.validated_data.get('maintenanceAction'), 'GENERAL')

        # Kiểm tra ISO thresholds
        thresholds = get_iso_thresholds_for_asset(self.asset)
        self.assertEqual(thresholds['zone_ab_limit'], 2.8)
        self.assertEqual(thresholds['zone_c_limit'], 7.1)
        eval_res = evaluate_iso_10816('VIBRATION', 2.0, self.asset)
        self.assertEqual(eval_res['zone'], 'ZONE_AB')

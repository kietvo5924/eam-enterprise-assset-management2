"""
Unit & Integration Test Suite for Phase 11.8:
Complex Maintenance Workflow & Facility Management - Decision Tree & HSM Checklist.
Covering 100% of scenarios TC-HSM-01 through TC-HSM-10.
"""

import uuid
from decimal import Decimal
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework.exceptions import ValidationError

from core.models import Tenant
from core.tenant_context import clear_current_tenant
from assets.models import (
    Asset, AssetCategory, Location, SparePart, MeterReading,
    AssetRulPrediction, AssetAnomalyAlert
)
from workorders.models import (
    WorkOrder, WorkOrderChecklistItem, WorkOrderAttachment,
    HsmStageTransition
)
from workorders.services import WorkOrderTransitionService
from algorithms.decision_tree_hsm import (
    DecisionTreeChecklistEngine,
    SEVERITY_CRITICAL_OVERHAUL,
    SEVERITY_SERIOUS_MONITOR,
    SEVERITY_NORMAL,
    ACTION_CORE_REPLACEMENT,
    ACTION_MICRO_MAINTENANCE,
    ACTION_GENERAL,
    STAGE_DIAGNOSIS,
    STAGE_PARTS_PREP,
    STAGE_OVERHAUL_EXECUTION,
    STAGE_TRIAL_ACCEPTANCE
)

User = get_user_model()


class DecisionTreeHsmWorkflowTests(TestCase):
    def setUp(self):
        clear_current_tenant()
        self.tenant = Tenant.objects.create(name="Test Tenant HSM", tenant_code=f"T-HSM-{uuid.uuid4().hex[:6]}")
        self.tenant_id = self.tenant.id

        self.user = User.objects.create_user(
            username=f'tech_hsm_{uuid.uuid4().hex[:6]}',
            email='tech_hsm@test.com',
            password='password123',
            tenant=self.tenant,
            is_superuser=True
        )

        self.loc = Location.objects.create(
            name='Phân Xưởng Cơ Điện 1',
            code=f'PLANT_01_{uuid.uuid4().hex[:4]}',
            tenant=self.tenant
        )

        self.category = AssetCategory.objects.create(
            name='Máy Bơm Công Nghiệp',
            tenant=self.tenant
        )

        self.asset = Asset.objects.create(
            name='Máy Bơm Cao Áp Booster-01',
            qr_code=f'PMP-{uuid.uuid4().hex[:6]}',
            category=self.category,
            location=self.loc,
            purchase_cost=Decimal('100000000.00'),  # 100M VND
            tenant=self.tenant
        )



        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def _create_attachment(self, wo):
        """Helper to fulfill mandatory attachment requirement before completing WO."""
        return WorkOrderAttachment.objects.create(
            work_order=wo,
            tenant=wo.tenant,
            file_name='overhaul_acceptance_photo.jpg',
            file_url='https://storage.example.com/wo/photo1.jpg',
            file_type='image/jpeg',
            file_size=204800,
            created_by=self.user
        )

    # ------------------------------------------------------------------
    # TC-HSM-01: Phân loại Bảo dưỡng thông thường (Normal Maintenance)
    # ------------------------------------------------------------------
    def test_tc_hsm_01_normal_maintenance_classification(self):
        """TC-HSM-01: Z=1.2, RUL=45 -> NORMAL_MAINTENANCE with lightweight checklist."""
        engine = DecisionTreeChecklistEngine()
        result = engine.evaluate(
            anomaly_zscore=1.2,
            current_rul_days=45.0,
            estimated_cost_ratio=0.05,
            failure_recurrence=0
        )

        self.assertEqual(result['severity_level'], SEVERITY_NORMAL)
        self.assertEqual(result['recommended_action'], ACTION_GENERAL)
        self.assertFalse(result['marginal_boundary_warning'])
        self.assertIn('Z-score rung chấn (1.20) < 2.00', result['decision_path_explanation'])

        # Templates generated for NORMAL severity
        checklists = result['suggested_checklists']
        self.assertGreaterEqual(len(checklists), 2)
        item_names = [c['item_name'] for c in checklists]
        self.assertTrue(any('bôi trơn' in n.lower() or 'kiểm tra' in n.lower() for n in item_names))

    # ------------------------------------------------------------------
    # TC-HSM-02: Phân loại Đại tu bổ máy (Critical Overhaul)
    # ------------------------------------------------------------------
    def test_tc_hsm_02_critical_overhaul_classification(self):
        """TC-HSM-02: Z=2.8, RUL=6 -> CRITICAL_OVERHAUL, 6 checklist items across 4 stages."""
        engine = DecisionTreeChecklistEngine()
        result = engine.evaluate(
            anomaly_zscore=2.8,
            current_rul_days=6.0,
            estimated_cost_ratio=0.35,
            failure_recurrence=2
        )

        self.assertEqual(result['severity_level'], SEVERITY_CRITICAL_OVERHAUL)
        self.assertEqual(result['recommended_action'], ACTION_CORE_REPLACEMENT)
        self.assertEqual(result['recommended_priority'], 'CRITICAL')

        checklists = result['suggested_checklists']
        self.assertEqual(len(checklists), 6)

        # Check coverage across all 4 mandatory stages
        stages_present = {c['stage'] for c in checklists}
        self.assertEqual(stages_present, {
            STAGE_DIAGNOSIS,
            STAGE_PARTS_PREP,
            STAGE_OVERHAUL_EXECUTION,
            STAGE_TRIAL_ACCEPTANCE
        })

        # Stage 4 must contain ISO 10816-3 RMS vibration requirement
        stage_4_items = [c for c in checklists if c['stage'] == STAGE_TRIAL_ACCEPTANCE]
        self.assertTrue(any('rung' in c['item_name'].lower() and c['input_type'] == 'NUMBER' for c in stage_4_items))

    # ------------------------------------------------------------------
    # TC-HSM-03: Cảnh báo vùng đệm giáp ranh (Marginal Boundary Warning)
    # ------------------------------------------------------------------
    def test_tc_hsm_03_marginal_boundary_warning(self):
        """TC-HSM-03: RUL=15.2 days (near threshold 15.0 days within +-5% buffer)."""
        engine = DecisionTreeChecklistEngine()

        # 15.0 * 1.05 = 15.75 -> 15.2 is in [14.25, 15.75]
        result = engine.evaluate(
            anomaly_zscore=2.2,
            current_rul_days=15.2,
            estimated_cost_ratio=0.15,
            failure_recurrence=0
        )

        self.assertTrue(result['marginal_boundary_warning'])
        self.assertIn('CẢNH BÁO VÙNG ĐỆM GIÁP RANH', result['decision_path_explanation'])
        self.assertIn('Quản đốc', result['decision_path_explanation'])

    # ------------------------------------------------------------------
    # TC-HSM-04: Tự động điền form từ thông báo qua API REST
    # ------------------------------------------------------------------
    def test_tc_hsm_04_evaluate_alert_api_endpoint(self):
        """TC-HSM-04: Call /api/v1/work-orders/evaluate-alert/ with alert & asset data."""
        # Create an anomaly alert
        alert = AssetAnomalyAlert.objects.create(
            asset=self.asset,
            metric_type='SINGLE_METRIC',
            metric_code='VIBRATION',
            severity='CRITICAL',
            current_value=4.8,
            anomaly_score=3.2,
            message='Khuyến nghị bổ máy đại tu bạc đạn',
            tenant=self.tenant
        )

        url = '/api/v1/work-orders/evaluate-alert/'
        payload = {
            'assetId': str(self.asset.id),
            'alertId': str(alert.id),
            'anomalyZscore': 3.1,
            'currentRulDays': 5.0
        }

        response = self.client.post(url, data=payload, format='json')
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertTrue(data['success'])
        res_data = data['data']
        self.assertEqual(res_data['severityLevel'], SEVERITY_CRITICAL_OVERHAUL)
        self.assertEqual(res_data['recommendedMaintenanceAction'], ACTION_CORE_REPLACEMENT)
        self.assertIsInstance(res_data['suggestedChecklists'], list)
        self.assertEqual(len(res_data['suggestedChecklists']), 6)



    # ------------------------------------------------------------------
    # TC-HSM-05: Chặn hoàn thành khi thiếu checklist bắt buộc
    # ------------------------------------------------------------------
    def test_tc_hsm_05_block_completion_when_mandatory_checklist_incomplete(self):
        """TC-HSM-05: Complete WO fails when mandatory checklist item is incomplete."""
        wo = WorkOrder.objects.create(
            tenant=self.tenant,
            title='Đại tu máy bơm Booster-01',
            status='IN_PROGRESS',
            priority='HIGH',
            maintenance_action=ACTION_CORE_REPLACEMENT,
            severity_level=SEVERITY_CRITICAL_OVERHAUL,
            asset=self.asset,
            assigned_to=self.user,
        )
        self._create_attachment(wo)

        # Create mandatory checklist item, not completed
        WorkOrderChecklistItem.objects.create(
            tenant=self.tenant,
            work_order=wo,
            item_name='Khảo sát hiện trường và đo khe hở bạc đạn',
            stage=STAGE_DIAGNOSIS,
            input_type='PASS_FAIL',
            is_mandatory=True,
            is_completed=False
        )

        with self.assertRaises(ValidationError) as ctx:
            WorkOrderTransitionService.transition(wo, 'COMPLETED', self.user)

        self.assertIn("Chưa hoàn thành bước bắt buộc", str(ctx.exception))
        wo.refresh_from_db()
        self.assertEqual(wo.status, 'IN_PROGRESS')

    # ------------------------------------------------------------------
    # TC-HSM-06: Chặn hoàn thành khi thiếu số đo bắt buộc (NUMBER blank)
    # ------------------------------------------------------------------
    def test_tc_hsm_06_block_completion_when_number_measurement_missing(self):
        """TC-HSM-06: Complete WO fails when mandatory NUMBER item has no actual value."""
        wo = WorkOrder.objects.create(
            tenant=self.tenant,
            title='Đại tu máy bơm Booster-01',
            status='IN_PROGRESS',
            priority='HIGH',
            maintenance_action=ACTION_CORE_REPLACEMENT,
            severity_level=SEVERITY_CRITICAL_OVERHAUL,
            asset=self.asset,
            assigned_to=self.user
        )
        self._create_attachment(wo)

        WorkOrderChecklistItem.objects.create(
            tenant=self.tenant,
            work_order=wo,
            item_name='Đo rung động sau đại tu (mm/s RMS)',
            stage=STAGE_TRIAL_ACCEPTANCE,
            input_type='NUMBER',
            expected_value='< 4.5',
            is_mandatory=True,
            is_completed=True,
            actual_value=''  # Blank value
        )

        with self.assertRaises(ValidationError) as ctx:
            WorkOrderTransitionService.transition(wo, 'COMPLETED', self.user)

        self.assertIn("chưa có số liệu đo kiểm", str(ctx.exception))

    # ------------------------------------------------------------------
    # TC-HSM-07: Chấp nhận hoàn thành khi đủ số đo hợp lệ
    # ------------------------------------------------------------------
    def test_tc_hsm_07_allow_completion_when_measurements_valid(self):
        """TC-HSM-07: Transition to COMPLETED succeeds when all mandatory items & measurements are valid."""
        wo = WorkOrder.objects.create(
            tenant=self.tenant,
            title='Đại tu máy bơm Booster-01',
            status='IN_PROGRESS',
            priority='HIGH',
            maintenance_action=ACTION_CORE_REPLACEMENT,
            severity_level=SEVERITY_CRITICAL_OVERHAUL,
            asset=self.asset,
            assigned_to=self.user
        )
        self._create_attachment(wo)

        WorkOrderChecklistItem.objects.create(
            tenant=self.tenant,
            work_order=wo,
            item_name='Khảo sát bệ bơm',
            stage=STAGE_DIAGNOSIS,
            input_type='PASS_FAIL',
            is_mandatory=True,
            is_completed=True
        )

        WorkOrderChecklistItem.objects.create(
            tenant=self.tenant,
            work_order=wo,
            item_name='Đo vận tốc rung hiệu dụng RMS (mm/s)',
            stage=STAGE_TRIAL_ACCEPTANCE,
            input_type='NUMBER',
            expected_value='< 4.5',
            actual_value='2.1',  # Valid measurement: 2.1 < 4.5
            is_mandatory=True,
            is_completed=True
        )

        updated_wo = WorkOrderTransitionService.transition(wo, 'COMPLETED', self.user)
        self.assertEqual(updated_wo.status, 'COMPLETED')
        self.assertIsNotNone(updated_wo.completed_at)

    # ------------------------------------------------------------------
    # TC-HSM-08: Lùi bước kỹ thuật (Rollback) & Audit Trail
    # ------------------------------------------------------------------
    def test_tc_hsm_08_hsm_rollback_workflow_and_audit(self):
        """TC-HSM-08: Rollback rewinds stage 3 & 4 checklists, records transition, validates reason >= 20 chars."""
        wo = WorkOrder.objects.create(
            tenant=self.tenant,
            title='Đại tu máy bơm Booster-01',
            status='IN_PROGRESS',
            priority='HIGH',
            maintenance_action=ACTION_CORE_REPLACEMENT,
            severity_level=SEVERITY_CRITICAL_OVERHAUL,
            asset=self.asset,
            assigned_to=self.user
        )

        chk1 = WorkOrderChecklistItem.objects.create(
            tenant=self.tenant, work_order=wo, item_name='Khảo sát',
            stage=STAGE_DIAGNOSIS, is_completed=True, is_mandatory=True
        )
        chk2 = WorkOrderChecklistItem.objects.create(
            tenant=self.tenant, work_order=wo, item_name='Phụ tùng',
            stage=STAGE_PARTS_PREP, is_completed=True, is_mandatory=True
        )
        chk3 = WorkOrderChecklistItem.objects.create(
            tenant=self.tenant, work_order=wo, item_name='Tháo lắp thay bi',
            stage=STAGE_OVERHAUL_EXECUTION, is_completed=True, is_mandatory=True
        )
        chk4 = WorkOrderChecklistItem.objects.create(
            tenant=self.tenant, work_order=wo, item_name='Đo rung chạy thử',
            stage=STAGE_TRIAL_ACCEPTANCE, is_completed=True, is_mandatory=True,
            input_type='NUMBER', expected_value='< 4.5', actual_value='5.8'
        )

        # 1. Validation: reason < 20 characters must fail
        with self.assertRaises(ValidationError) as ctx:
            DecisionTreeChecklistEngine.rollback_work_order(
                wo, self.user, reason="Rung cao", recheck_vibration=5.8
            )
        self.assertIn("ít nhất 20 ký tự", str(ctx.exception))

        # 2. Valid rollback (reason >= 20 chars)
        valid_reason = "Vận tốc rung hiệu dụng đo được 5.8 mm/s vượt ngưỡng cho phép 4.5 mm/s, cần cân chỉnh lại trục"
        transition = DecisionTreeChecklistEngine.rollback_work_order(
            wo, self.user, reason=valid_reason, recheck_vibration=5.8, recheck_temperature=72.0
        )

        self.assertIsNotNone(transition)
        self.assertEqual(transition.action, 'ROLLBACK')
        self.assertEqual(transition.from_stage, STAGE_TRIAL_ACCEPTANCE)
        self.assertEqual(transition.to_stage, STAGE_OVERHAUL_EXECUTION)
        self.assertEqual(transition.recheck_vibration, 5.8)

        # 3. Verify checklist rewound: Stages 1 & 2 remain completed, 3 & 4 rewound to False
        chk1.refresh_from_db()
        chk2.refresh_from_db()
        chk3.refresh_from_db()
        chk4.refresh_from_db()

        self.assertTrue(chk1.is_completed)
        self.assertTrue(chk2.is_completed)
        self.assertFalse(chk3.is_completed)
        self.assertFalse(chk4.is_completed)

        # 4. Verify API endpoint /api/v1/work-orders/{id}/hsm-rollback/
        url = f'/api/v1/work-orders/{wo.id}/hsm-rollback/'
        res = self.client.post(url, data={
            'reason': "Yêu cầu tháo ra căn chỉnh lại khớp nối và bu lông bệ máy lần 2",
            'recheckVibration': 5.2
        }, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()['success'])

    # ------------------------------------------------------------------
    # TC-HSM-09: Tạm hoãn ngoại cảnh đóng băng SLA (On-Hold Clock Freezing)
    # ------------------------------------------------------------------
    def test_tc_hsm_09_external_hold_freezes_sla_clock(self):
        """TC-HSM-09: ON_HOLD sets is_on_hold=True, RESUME accumulates hold_accumulated_seconds."""
        wo = WorkOrder.objects.create(
            tenant=self.tenant,
            title='Bảo dưỡng quạt thông gió F-02',
            status='IN_PROGRESS',
            priority='MEDIUM',
            asset=self.asset,
            assigned_to=self.user
        )

        # Hold the work order
        hold_reason = "WAITING_PARTS: Chờ nhà cung cấp chuyển phốt chặn dầu từ kho tổng"
        t_hold = DecisionTreeChecklistEngine.hold_work_order(wo, self.user, reason=hold_reason)

        wo.refresh_from_db()
        self.assertTrue(wo.is_on_hold)
        self.assertEqual(wo.status, 'ON_HOLD')
        self.assertEqual(wo.hold_reason, hold_reason)
        self.assertIsNotNone(wo.hold_started_at)
        self.assertEqual(t_hold.action, 'HOLD')

        # Simulate 2 hours of clock paused
        two_hours_ago = timezone.now() - timedelta(hours=2)
        WorkOrder.objects.filter(id=wo.id).update(hold_started_at=two_hours_ago)
        wo.refresh_from_db()

        # Resume the work order
        t_resume = DecisionTreeChecklistEngine.resume_work_order(wo, self.user, notes="Phụ tùng đã về kho")
        wo.refresh_from_db()

        self.assertFalse(wo.is_on_hold)
        self.assertEqual(wo.status, 'IN_PROGRESS')
        self.assertIsNone(wo.hold_started_at)
        # Should have accumulated approximately 7200 seconds (at least 7000s)
        self.assertGreaterEqual(wo.hold_accumulated_seconds, 7000)
        self.assertEqual(t_resume.action, 'RESUME')

        # Test API endpoint /api/v1/work-orders/{id}/hsm-hold/
        url = f'/api/v1/work-orders/{wo.id}/hsm-hold/'
        res_hold = self.client.post(url, data={
            'action': 'HOLD',
            'reason': 'WAITING_VENDOR: Chờ chuyên gia của hãng Siemens hỗ trợ firmware'
        }, format='json')
        self.assertEqual(res_hold.status_code, 200)

        wo.refresh_from_db()
        self.assertTrue(wo.is_on_hold)
        self.assertEqual(wo.status, 'ON_HOLD')

        res_resume = self.client.post(url, data={'action': 'RESUME'}, format='json')
        self.assertEqual(res_resume.status_code, 200)
        wo.refresh_from_db()
        self.assertFalse(wo.is_on_hold)
        self.assertEqual(wo.status, 'IN_PROGRESS')

    # ------------------------------------------------------------------
    # TC-HSM-10: Tái đồng bộ Baseline sau đại tu (Post-repair Reset)
    # ------------------------------------------------------------------
    def test_tc_hsm_10_baseline_reset_after_core_replacement(self):
        """TC-HSM-10: CORE_REPLACEMENT completion resets RUL, freezes pre-repair readings, resolves alerts."""
        now = timezone.now()

        # 1. Historical readings before overhaul
        r1 = MeterReading.objects.create(
            asset=self.asset,
            reading_date=now - timedelta(days=2),
            reading_value=Decimal('4.80'),
            metric_code='VIBRATION',
            ambient_temperature=78.0,
            load_factor=1.0,
            tenant=self.tenant
        )
        r2 = MeterReading.objects.create(
            asset=self.asset,
            reading_date=now - timedelta(days=1),
            reading_value=Decimal('5.20'),
            metric_code='VIBRATION',
            ambient_temperature=82.0,
            load_factor=1.0,
            tenant=self.tenant
        )

        # 2. Active anomaly alert
        alert = AssetAnomalyAlert.objects.create(
            asset=self.asset,
            metric_type='SINGLE_METRIC',
            metric_code='VIBRATION',
            severity='CRITICAL',
            current_value=5.2,
            status='OPEN',
            tenant=self.tenant
        )

        # 3. Active RUL prediction
        pred = AssetRulPrediction.objects.create(
            asset=self.asset,
            predicted_rul_op_days=4.5,
            predicted_rul_cal_days=4.5,
            confidence_lower=3.0,
            confidence_upper=6.0,
            risk_level='CRITICAL',
            action_taken='CHECK_INVENTORY',
            is_phantom_recovery=True,
            tenant=self.tenant
        )

        # 4. WorkOrder with CORE_REPLACEMENT
        wo = WorkOrder.objects.create(
            tenant=self.tenant,
            title='Đại tu toàn diện cụm ổ bi và trục máy bơm',
            status='IN_PROGRESS',
            priority='HIGH',
            maintenance_action=ACTION_CORE_REPLACEMENT,
            severity_level=SEVERITY_CRITICAL_OVERHAUL,
            asset=self.asset,
            assigned_to=self.user
        )
        self._create_attachment(wo)

        WorkOrderChecklistItem.objects.create(
            tenant=self.tenant,
            work_order=wo,
            item_name='Đo kiểm rung động sau chạy thử nghiệm thu',
            stage=STAGE_TRIAL_ACCEPTANCE,
            input_type='NUMBER',
            expected_value='< 4.5',
            actual_value='1.8',  # pristine post-repair measurement
            is_mandatory=True,
            is_completed=True
        )

        # Complete the work order
        updated_wo = WorkOrderTransitionService.transition(wo, 'COMPLETED', self.user)
        self.assertEqual(updated_wo.status, 'COMPLETED')

        # Verify historical readings are flagged as pre-repair
        r1.refresh_from_db()
        r2.refresh_from_db()
        self.assertTrue(r1.is_pre_repair)
        self.assertTrue(r2.is_pre_repair)

        # Verify active anomaly alert was resolved
        alert.refresh_from_db()
        self.assertEqual(alert.status, 'RESOLVED')
        self.assertIn('Đã tự động giải quyết sau khi hoàn thành đại tu bổ máy', alert.message)

        # Verify Asset's last_core_overhaul_at was updated
        self.asset.refresh_from_db()
        self.assertIsNotNone(self.asset.last_core_overhaul_at)

        # Verify AssetRulPrediction was reset to CALIBRATING
        pred.refresh_from_db()
        self.assertEqual(pred.risk_level, 'CALIBRATING')
        self.assertEqual(pred.action_taken, 'CALIBRATING')
        self.assertFalse(pred.is_phantom_recovery)

    # ------------------------------------------------------------------
    # TC-HSM-11: Từ chối hoàn thành khi độ rung nghiệm thu vượt ngưỡng (ISO 10816 > 4.5 mm/s)
    # ------------------------------------------------------------------
    def test_tc_hsm_11_post_repair_vibration_exceeding_limit_rejection(self):
        """TC-HSM-11: Completion of CORE_REPLACEMENT rejected when vibration > 4.5 mm/s."""
        wo = WorkOrder.objects.create(
            tenant=self.tenant,
            title='Đại tu máy bơm Booster-01',
            status='IN_PROGRESS',
            priority='HIGH',
            maintenance_action=ACTION_CORE_REPLACEMENT,
            severity_level=SEVERITY_CRITICAL_OVERHAUL,
            asset=self.asset,
            assigned_to=self.user
        )
        self._create_attachment(wo)

        WorkOrderChecklistItem.objects.create(
            tenant=self.tenant,
            work_order=wo,
            item_name='Đo kiểm rung động sau chạy thử nghiệm thu',
            stage=STAGE_TRIAL_ACCEPTANCE,
            input_type='NUMBER',
            expected_value='< 4.5',
            actual_value='5.8',  # Exceeds 4.5 mm/s limit
            is_mandatory=True,
            is_completed=True
        )

        with self.assertRaises(ValidationError) as ctx:
            WorkOrderTransitionService.transition(wo, 'COMPLETED', self.user)
        self.assertIn("vượt ngưỡng an toàn cho phép", str(ctx.exception))
        self.assertIn("Rollback", str(ctx.exception))

        # Also test post_repair_data rejection
        with self.assertRaises(ValidationError) as ctx2:
            WorkOrderTransitionService.complete_work_order(
                work_order_id=wo.id,
                user=self.user,
                maintenance_action=ACTION_CORE_REPLACEMENT,
                post_repair_data={'vibration': 5.2}
            )
        self.assertIn("vượt ngưỡng an toàn cho phép", str(ctx2.exception))



    # ------------------------------------------------------------------
    # TC-HSM-13: Chuyển trạng thái ON_HOLD qua API PUT /status với đầy đủ holdReason & notes
    # ------------------------------------------------------------------
    def test_tc_hsm_13_work_order_status_api_hold_and_resume_with_fields(self):
        """TC-HSM-13: PUT /api/v1/work-orders/{id}/status preserves holdReason and notes in serializer."""
        wo = WorkOrder.objects.create(
            tenant=self.tenant,
            title='Bảo dưỡng máy bơm P-102',
            status='IN_PROGRESS',
            priority='HIGH',
            asset=self.asset,
            assigned_to=self.user
        )

        status_url = f'/api/v1/work-orders/{wo.id}/status'
        res_hold = self.client.put(status_url, data={
            'status': 'ON_HOLD',
            'holdReason': 'BUDGET_APPROVAL',
            'notes': 'Chờ Giám đốc kỹ thuật duyệt ngân sách thay thế cánh bơm'
        }, format='json')
        self.assertEqual(res_hold.status_code, 200)

        wo.refresh_from_db()
        self.assertTrue(wo.is_on_hold)
        self.assertEqual(wo.status, 'ON_HOLD')
        self.assertEqual(wo.hold_reason, 'BUDGET_APPROVAL')

        # Check HsmStageTransition record
        transition = HsmStageTransition.objects.filter(work_order=wo, action_type='HOLD').first()
        self.assertIsNotNone(transition)
        self.assertIn('BUDGET_APPROVAL', transition.reason)
        self.assertIn('duyệt ngân sách', transition.reason)

        # Resume via status API
        res_resume = self.client.put(status_url, data={
            'status': 'IN_PROGRESS',
            'notes': 'Ngân sách đã được phê duyệt, tiếp tục gia công'
        }, format='json')
        self.assertEqual(res_resume.status_code, 200)

        wo.refresh_from_db()
        self.assertFalse(wo.is_on_hold)
        self.assertEqual(wo.status, 'IN_PROGRESS')
        self.assertIsNone(wo.hold_reason)

    # ------------------------------------------------------------------
    # TC-HSM-14: Rollback API nhận và lưu đúng recheckVibration và recheckTemperature
    # ------------------------------------------------------------------
    def test_tc_hsm_14_rollback_api_records_recheck_vibration_and_temperature(self):
        """TC-HSM-14: POST /api/v1/work-orders/{id}/hsm-rollback/ extracts frontend recheck parameters."""
        wo = WorkOrder.objects.create(
            tenant=self.tenant,
            title='Đại tu máy bơm Booster-01',
            status='IN_PROGRESS',
            priority='HIGH',
            maintenance_action=ACTION_CORE_REPLACEMENT,
            severity_level=SEVERITY_CRITICAL_OVERHAUL,
            asset=self.asset,
            assigned_to=self.user
        )

        WorkOrderChecklistItem.objects.create(
            tenant=self.tenant, work_order=wo, item_name='Chạy thử nghiệm thu',
            stage=STAGE_TRIAL_ACCEPTANCE, is_completed=True, is_mandatory=True,
            input_type='NUMBER', expected_value='< 4.5', actual_value='5.4'
        )

        url = f'/api/v1/work-orders/{wo.id}/hsm-rollback/'
        payload = {
            'reason': 'Vận tốc rung sau chạy thử đạt 5.4 mm/s, vượt ngưỡng an toàn yêu cầu căn chỉnh lại',
            'recheckVibration': 5.4,
            'recheckTemperature': 76.5
        }
        res = self.client.post(url, data=payload, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()['success'])

        # Verify the transition captured the recheck measurements
        transition = HsmStageTransition.objects.filter(work_order=wo, action_type='ROLLBACK').first()
        self.assertIsNotNone(transition)
        self.assertEqual(transition.vibration_reading, 5.4)
        self.assertEqual(transition.recheck_vibration, 5.4)
        self.assertEqual(transition.temperature_reading, 76.5)
        self.assertEqual(transition.recheck_temperature, 76.5)

    # ------------------------------------------------------------------
    # TC-HSM-15: Chỉ số MTTR / actual_duration_hours tự động trừ thời gian đóng băng SLA
    # ------------------------------------------------------------------
    def test_tc_hsm_15_sla_mttr_actual_duration_hours_deducts_hold_time(self):
        """TC-HSM-15: actual_duration_hours subtracts hold_accumulated_seconds for precise SLA."""
        now = timezone.now()
        start = now - timedelta(hours=5)  # Total elapsed: 5 hours

        wo = WorkOrder.objects.create(
            tenant=self.tenant,
            title='Bảo trì máy bơm có tạm hoãn phụ tùng',
            status='IN_PROGRESS',
            priority='HIGH',
            asset=self.asset,
            assigned_to=self.user,
            actual_start_time=start,
            hold_accumulated_seconds=7200  # 2 hours paused
        )
        self._create_attachment(wo)

        WorkOrderChecklistItem.objects.create(
            tenant=self.tenant,
            work_order=wo,
            item_name='Kiểm tra cuối',
            stage=STAGE_TRIAL_ACCEPTANCE,
            input_type='PASS_FAIL',
            is_mandatory=True,
            is_completed=True
        )

        updated_wo = WorkOrderTransitionService.transition(wo, 'COMPLETED', self.user)
        self.assertEqual(updated_wo.status, 'COMPLETED')

        # Total elapsed is 5 hours, hold is 2 hours -> net duration should be 3.0 hours
        self.assertAlmostEqual(updated_wo.actual_duration_hours, 3.0, places=1)
        self.assertAlmostEqual(updated_wo.actual_duration_minutes, 180, delta=2)

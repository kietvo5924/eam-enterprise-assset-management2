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

    # ------------------------------------------------------------------
    # TC-HSM-16: Đánh giá khả năng phân loại đa chiều của Cây Quyết Định Chuyên Gia
    # ------------------------------------------------------------------
    def test_tc_hsm_16_expert_decision_tree_operational_modes(self):
        """TC-HSM-16: Decision tree accurately classifies all expert maintenance modes without artificial bias."""
        clf = DecisionTreeChecklistEngine.get_classifier()

        # 1. Máy chạy êm, RUL dài nhưng có 2 lần bảo dưỡng định kỳ trước đó -> KHÔNG được báo đại tu giả tạo
        pred_normal_routine = clf.predict([[0.5, 90.0, 0.05, 2]])[0]
        self.assertEqual(pred_normal_routine, 0, "Thiết bị hoạt động êm ái không được phân loại nhầm thành CRITICAL_OVERHAUL")

        # 2. Cảnh báo rung chấn nguy cấp Zone D (Z=2.85 >= 2.5) -> BẮT BUỘC ĐẠI TU
        pred_crit_vib = clf.predict([[2.85, 45.0, 0.10, 0]])[0]
        self.assertEqual(pred_crit_vib, 1, "Rung chấn Zone D (Z >= 2.5) phải phân loại CRITICAL_OVERHAUL")

        # 3. Tuổi thọ cạn kiệt (RUL=7 ngày <= 15) -> BẮT BUỘC ĐẠI TU
        pred_crit_rul = clf.predict([[1.0, 7.0, 0.10, 0]])[0]
        self.assertEqual(pred_crit_rul, 1, "Tuổi thọ cạn kiệt (RUL <= 15) phải phân loại CRITICAL_OVERHAUL")

        # 4. Tỷ lệ chi phí sửa chữa vượt ngưỡng nghiêm trọng (Cost ratio = 45% >= 35%) -> ĐẠI TU
        pred_crit_cost = clf.predict([[1.5, 40.0, 0.45, 0]])[0]
        self.assertEqual(pred_crit_cost, 1, "Chi phí sửa chữa vượt ngưỡng nghiêm trọng phải phân loại CRITICAL_OVERHAUL")

        # 5. Các đặc trưng chủ đạo z_score, rul_days, cost_ratio đều có trọng số đóng góp
        importances = dict(zip(['z_score', 'rul_days', 'cost_ratio', 'recurrence'], clf.feature_importances_))
        self.assertGreater(importances['z_score'], 0.10)
        self.assertGreater(importances['rul_days'], 0.10)
        self.assertGreater(importances['cost_ratio'], 0.10)

    # ------------------------------------------------------------------
    # TC-HSM-17: Trích xuất đúng alert.z_score và asset.current_rul_days
    # ------------------------------------------------------------------
    def test_tc_hsm_17_alert_z_score_and_rul_extraction(self):
        """TC-HSM-17: Engine extracts real alert.z_score and asset.current_rul_days (not non-existent metric_value)."""
        self.asset.current_rul_days = 8.0
        self.asset.save(update_fields=['current_rul_days'])

        alert = AssetAnomalyAlert.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            metric_code='VIBRATION',
            current_value=6.5,
            z_score=3.4,
            severity='CRITICAL'
        )

        res = DecisionTreeChecklistEngine.evaluate(alert=alert)
        self.assertEqual(res['severity_level'], SEVERITY_CRITICAL_OVERHAUL)
        self.assertEqual(res['recommended_action'], ACTION_CORE_REPLACEMENT)
        self.assertIn('3.40', res['decision_path_explanation'])
        self.assertIn('8.0', res['decision_path_explanation'])

    # ------------------------------------------------------------------
    # TC-HSM-18: Tính nhất quán của chuỗi giải thích IF-THEN
    # ------------------------------------------------------------------
    def test_tc_hsm_18_explanation_consistency(self):
        """TC-HSM-18: Verify decision path explanation has no contradictory comparisons."""
        exp = DecisionTreeChecklistEngine.generate_decision_explanation(
            severity=SEVERITY_NORMAL,
            z_score=2.1,
            rul_days=25.0,
            cost_ratio=0.10,
            recurrence=0
        )
        self.assertNotIn("2.10 < 2.00", exp)
        self.assertNotIn("25.0 > 30.0", exp)
        self.assertIn("2.10", exp)
        self.assertIn("25.0", exp)

    # ------------------------------------------------------------------
    # TC-HSM-19: Chặn số đo NaN, Infinity, số âm và đúng bằng ngưỡng 4.5
    # ------------------------------------------------------------------
    def test_tc_hsm_19_measurement_validation_nan_infinity_negative_boundary(self):
        """TC-HSM-19: Reject NaN, Infinity, negative values, and equal to threshold (>= 4.5)."""
        wo = WorkOrder.objects.create(
            tenant=self.tenant,
            title='Kiểm thử số đo bất thường',
            status='IN_PROGRESS',
            priority='HIGH',
            maintenance_action=ACTION_CORE_REPLACEMENT,
            severity_level=SEVERITY_CRITICAL_OVERHAUL,
            asset=self.asset,
            assigned_to=self.user
        )
        self._create_attachment(wo)

        chk = WorkOrderChecklistItem.objects.create(
            tenant=self.tenant,
            work_order=wo,
            item_name='Đo vận tốc rung hiệu dụng RMS (mm/s)',
            stage=STAGE_TRIAL_ACCEPTANCE,
            input_type='NUMBER',
            expected_value='< 4.5',
            actual_value='NaN',
            is_mandatory=True,
            is_completed=True
        )

        # 1. NaN rejected
        with self.assertRaises(ValidationError) as ctx:
            WorkOrderTransitionService.transition(wo, 'COMPLETED', self.user)
        self.assertIn("NaN", str(ctx.exception))

        # 2. Infinity rejected
        chk.actual_value = 'Infinity'
        chk.save()
        with self.assertRaises(ValidationError) as ctx:
            WorkOrderTransitionService.transition(wo, 'COMPLETED', self.user)
        self.assertIn("Infinity", str(ctx.exception))

        # 3. Negative rejected
        chk.actual_value = '-2.5'
        chk.save()
        with self.assertRaises(ValidationError) as ctx:
            WorkOrderTransitionService.transition(wo, 'COMPLETED', self.user)
        self.assertIn("số âm", str(ctx.exception))

        # 4. Exactly 4.5 rejected (< 4.5 strictly requires smaller)
        chk.actual_value = '4.5'
        chk.save()
        with self.assertRaises(ValidationError) as ctx:
            WorkOrderTransitionService.transition(wo, 'COMPLETED', self.user)
        self.assertIn("vượt ngưỡng an toàn cho phép", str(ctx.exception))

        # 5. Non-vibration sensor (e.g. cold storage temperature) CAN have valid negative values
        chk.item_name = 'Nhiệt độ buồng lạnh kho bảo quản'
        chk.expected_value = '< 0'
        chk.actual_value = '-18.5'
        chk.save()
        # Should not raise "số âm" error for valid negative cold storage temperature
        try:
            WorkOrderTransitionService.complete_work_order(
                work_order_id=wo.id,
                user=self.user,
                post_repair_data={'vibration': 2.1, 'temperature': -18.5}
            )
        except ValidationError as ex:
            self.assertNotIn("số âm", str(ex))

    # ------------------------------------------------------------------
    # TC-HSM-20: Chặn hoàn thành CORE_REPLACEMENT khi không có checklist
    # ------------------------------------------------------------------
    def test_tc_hsm_20_cannot_complete_core_replacement_without_checklists(self):
        """TC-HSM-20: complete_work_order fails if CORE_REPLACEMENT has 0 checklist items."""
        wo = WorkOrder.objects.create(
            tenant=self.tenant,
            title='Đại tu thiếu checklist',
            status='IN_PROGRESS',
            priority='HIGH',
            maintenance_action=ACTION_CORE_REPLACEMENT,
            severity_level=SEVERITY_CRITICAL_OVERHAUL,
            asset=self.asset,
            assigned_to=self.user
        )
        self._create_attachment(wo)

        with self.assertRaises(ValidationError) as ctx:
            WorkOrderTransitionService.transition(wo, 'COMPLETED', self.user)
        self.assertIn("chưa có danh mục kiểm tra", str(ctx.exception))

    # ------------------------------------------------------------------
    # TC-HSM-21: Chặn xóa hoặc hạ cờ bắt buộc của checklist đại tu
    # ------------------------------------------------------------------
    def test_tc_hsm_21_prevent_deleting_or_demoting_mandatory_checklist(self):
        """TC-HSM-21: Mandatory overhaul checklists cannot be deleted or set to non-mandatory."""
        wo = WorkOrder.objects.create(
            tenant=self.tenant,
            title='Đại tu bảo vệ checklist',
            status='IN_PROGRESS',
            priority='HIGH',
            maintenance_action=ACTION_CORE_REPLACEMENT,
            severity_level=SEVERITY_CRITICAL_OVERHAUL,
            asset=self.asset,
            assigned_to=self.user
        )
        chk = WorkOrderChecklistItem.objects.create(
            tenant=self.tenant,
            work_order=wo,
            item_name='Đo kiểm rung động nghiệm thu',
            stage=STAGE_TRIAL_ACCEPTANCE,
            input_type='NUMBER',
            expected_value='< 4.5',
            is_mandatory=True,
            is_completed=False
        )

        # 1. Attempt to demote isMandatory to False via API
        url = f'/api/v1/work-orders/{wo.id}/checklists'
        res = self.client.post(url, data={'id': str(chk.id), 'itemName': chk.item_name, 'isMandatory': False}, format='json')
        self.assertEqual(res.status_code, 400)
        chk.refresh_from_db()
        self.assertTrue(chk.is_mandatory)

        # 2. Attempt to delete mandatory overhaul checklist via API
        del_url = f'/api/v1/work-orders/{wo.id}/checklists/{chk.id}'
        del_res = self.client.delete(del_url)
        self.assertEqual(del_res.status_code, 400)
        self.assertTrue(WorkOrderChecklistItem.objects.filter(id=chk.id).exists())

    # ------------------------------------------------------------------
    # TC-HSM-22: Rollback từ chối tác động lên phiếu đã COMPLETED hoặc CANCELLED
    # ------------------------------------------------------------------
    def test_tc_hsm_22_rollback_rejects_completed_or_cancelled_wo(self):
        """TC-HSM-22: Rollback must reject COMPLETED or CANCELLED work orders to protect immutable data."""
        wo = WorkOrder.objects.create(
            tenant=self.tenant,
            title='Phiếu đã hoàn thành',
            status='COMPLETED',
            maintenance_action=ACTION_CORE_REPLACEMENT,
            asset=self.asset,
            assigned_to=self.user
        )
        with self.assertRaises(ValidationError) as ctx:
            DecisionTreeChecklistEngine.rollback_work_order(
                wo, self.user, reason="Yêu cầu làm lại sau khi đã đóng phiếu bảo trì"
            )
        self.assertIn("Không thể Rollback phiếu đã hoàn thành", str(ctx.exception))

        wo.status = 'CANCELLED'
        wo.save(update_fields=['status'])
        with self.assertRaises(ValidationError) as ctx2:
            DecisionTreeChecklistEngine.rollback_work_order(
                wo, self.user, reason="Yêu cầu làm lại sau khi đã hủy phiếu bảo trì"
            )
        self.assertIn("Không thể Rollback phiếu đã hủy", str(ctx2.exception))

    # ------------------------------------------------------------------
    # TC-HSM-23: Rollback chỉ revert Stage 3 & 4, bảo vệ Stage 1 & 2
    # ------------------------------------------------------------------
    def test_tc_hsm_23_rollback_preserves_stage_1_and_2_even_with_number_type(self):
        """TC-HSM-23: Stage 1 & 2 checklists are never reverted by Rollback even if input_type='NUMBER'."""
        wo = WorkOrder.objects.create(
            tenant=self.tenant,
            title='Đại tu máy bơm',
            status='IN_PROGRESS',
            maintenance_action=ACTION_CORE_REPLACEMENT,
            asset=self.asset,
            assigned_to=self.user
        )
        # Stage 1 with NUMBER type (e.g. initial clearance measurement)
        chk_diag = WorkOrderChecklistItem.objects.create(
            tenant=self.tenant,
            work_order=wo,
            item_name='Đo độ rơ ban đầu trước khi tháo rã (mm)',
            stage=STAGE_DIAGNOSIS,
            input_type='NUMBER',
            actual_value='0.15',
            is_completed=True,
            is_mandatory=True
        )
        # Stage 3
        chk_exec = WorkOrderChecklistItem.objects.create(
            tenant=self.tenant,
            work_order=wo,
            item_name='Thay thế cụm vòng bi',
            stage=STAGE_OVERHAUL_EXECUTION,
            is_completed=True,
            is_mandatory=True
        )
        # Stage 4
        chk_trial = WorkOrderChecklistItem.objects.create(
            tenant=self.tenant,
            work_order=wo,
            item_name='Đo rung chạy thử',
            stage=STAGE_TRIAL_ACCEPTANCE,
            input_type='NUMBER',
            actual_value='5.5',
            is_completed=True,
            is_mandatory=True
        )

        DecisionTreeChecklistEngine.rollback_work_order(
            wo, self.user,
            reason="Vận tốc rung hiệu dụng đo được 5.5 mm/s vượt ngưỡng cho phép 4.5 mm/s"
        )

        chk_diag.refresh_from_db()
        chk_exec.refresh_from_db()
        chk_trial.refresh_from_db()

        # Stage 1 MUST stay True
        self.assertTrue(chk_diag.is_completed)
        self.assertEqual(chk_diag.actual_value, '0.15')
        # Stage 3 and 4 reverted to False
        self.assertFalse(chk_exec.is_completed)
        self.assertFalse(chk_trial.is_completed)

    # ------------------------------------------------------------------
    # TC-HSM-24: Hold và Resume đồng bộ trạng thái kỹ thuật viên
    # ------------------------------------------------------------------
    def test_tc_hsm_24_hold_and_resume_technician_sync(self):
        """TC-HSM-24: HOLD releases technician to AVAILABLE; RESUME restores technician to BUSY."""
        from users.models import TechnicianProfile
        tech_profile, _ = TechnicianProfile.objects.get_or_create(
            user=self.user,
            tenant=self.tenant,
            defaults={'availability_status': 'BUSY'}
        )
        tech_profile.availability_status = 'BUSY'
        tech_profile.save()

        wo = WorkOrder.objects.create(
            tenant=self.tenant,
            title='Phiếu đồng bộ thợ',
            status='IN_PROGRESS',
            asset=self.asset,
            assigned_to=self.user
        )

        # Hold -> Tech becomes AVAILABLE
        t_hold = DecisionTreeChecklistEngine.hold_work_order(wo, self.user, hold_reason='WAITING_PARTS')
        tech_profile.refresh_from_db()
        self.assertEqual(tech_profile.availability_status, 'AVAILABLE')
        self.assertEqual(t_hold.from_stage, STAGE_OVERHAUL_EXECUTION)
        self.assertEqual(t_hold.to_stage, 'ON_HOLD')

        # Resume -> Tech becomes BUSY
        t_resume = DecisionTreeChecklistEngine.resume_work_order(wo, self.user)
        tech_profile.refresh_from_db()
        self.assertEqual(tech_profile.availability_status, 'BUSY')
        self.assertEqual(t_resume.from_stage, 'ON_HOLD')
        self.assertEqual(t_resume.to_stage, STAGE_OVERHAUL_EXECUTION)

    # ------------------------------------------------------------------
    # TC-HSM-25: Phiếu bảo trì GENERAL không đóng nhầm cảnh báo khác của thiết bị
    # ------------------------------------------------------------------
    def test_tc_hsm_25_general_wo_does_not_close_unrelated_alerts(self):
        """TC-HSM-25: Completing a GENERAL maintenance WO does not resolve unlinked open alerts on asset."""
        unrelated_alert = AssetAnomalyAlert.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            metric_code='TEMPERATURE',
            current_value=88.0,
            status='OPEN',
            severity='CRITICAL'
        )

        general_wo = WorkOrder.objects.create(
            tenant=self.tenant,
            title='Bảo dưỡng thông thường (quét dọn bệ máy)',
            status='IN_PROGRESS',
            maintenance_action=ACTION_GENERAL,
            asset=self.asset,
            assigned_to=self.user
        )
        self._create_attachment(general_wo)

        WorkOrderChecklistItem.objects.create(
            tenant=self.tenant,
            work_order=general_wo,
            item_name='Vệ sinh lau chùi',
            is_mandatory=True,
            is_completed=True
        )

        WorkOrderTransitionService.transition(general_wo, 'COMPLETED', self.user)

        unrelated_alert.refresh_from_db()
        # Must still be OPEN!
        self.assertEqual(unrelated_alert.status, 'OPEN')

    # ------------------------------------------------------------------
    # TC-HSM-26: Chặn Resume khi kỹ thuật viên đang bận làm phiếu IN_PROGRESS khác
    # ------------------------------------------------------------------
    def test_tc_hsm_26_resume_fails_when_technician_is_busy_on_another_wo(self):
        """TC-HSM-26: Reject Resume if assigned technician is busy on another IN_PROGRESS work order."""
        from users.models import TechnicianProfile
        tech_profile, _ = TechnicianProfile.objects.get_or_create(
            user=self.user,
            tenant=self.tenant,
            defaults={'availability_status': 'AVAILABLE', 'is_on_duty': True}
        )
        tech_profile.availability_status = 'AVAILABLE'
        tech_profile.is_on_duty = True
        tech_profile.save()

        # WO1 bị tạm hoãn
        wo1 = WorkOrder.objects.create(
            tenant=self.tenant,
            title='Phiếu đại tu tạm hoãn WO1',
            status='IN_PROGRESS',
            asset=self.asset,
            assigned_to=self.user
        )
        DecisionTreeChecklistEngine.hold_work_order(wo1, self.user, hold_reason='WAITING_PARTS')

        # Trong lúc đó thợ được gán và đang làm WO2
        wo2 = WorkOrder.objects.create(
            tenant=self.tenant,
            title='Phiếu sửa chữa đột xuất WO2',
            status='IN_PROGRESS',
            asset=self.asset,
            assigned_to=self.user
        )
        tech_profile.availability_status = 'BUSY'
        tech_profile.save()

        # Thử Resume WO1 -> Phải từ chối vì thợ đang bận làm WO2 (chống double-assignment)
        with self.assertRaises(ValidationError) as ctx:
            DecisionTreeChecklistEngine.resume_work_order(wo1, self.user)
        self.assertIn("đang thực hiện phiếu công việc khác", str(ctx.exception))

    # ------------------------------------------------------------------
    # TC-HSM-27: Chặn Resume khi kỹ thuật viên đang nghỉ phép hoặc ngoài ca trực
    # ------------------------------------------------------------------
    def test_tc_hsm_27_resume_fails_when_technician_is_on_leave(self):
        """TC-HSM-27: Reject Resume if assigned technician is ON_LEAVE or off-duty."""
        from users.models import TechnicianProfile
        tech_profile, _ = TechnicianProfile.objects.get_or_create(
            user=self.user,
            tenant=self.tenant,
            defaults={'availability_status': 'AVAILABLE', 'is_on_duty': True}
        )

        wo = WorkOrder.objects.create(
            tenant=self.tenant,
            title='Phiếu tạm hoãn chờ thợ hết phép',
            status='IN_PROGRESS',
            asset=self.asset,
            assigned_to=self.user
        )
        DecisionTreeChecklistEngine.hold_work_order(wo, self.user, hold_reason='WAITING_PARTS')

        # Thợ xin nghỉ phép
        tech_profile.availability_status = 'ON_LEAVE'
        tech_profile.save()

        with self.assertRaises(ValidationError) as ctx:
            DecisionTreeChecklistEngine.resume_work_order(wo, self.user)
        self.assertIn("đang nghỉ phép", str(ctx.exception))

import os
import sys
import json
import gzip
import uuid
import hashlib
from datetime import datetime

from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone
from django.core import serializers

from core.models import Tenant
from users.models import (
    User, Role, Permission, TechnicianProfile,
    WorkforceSkill, CertificationType, UserCertification,
    ShiftTemplate, TechnicianSchedule, BiometricProfile
)
from assets.models import (
    Location, AssetCategory, HierarchyTemplate, SparePart,
    Asset, MeterReading, AssetAnomalyAlert, StockTransaction,
    Tool, ToolInstance, ToolReservation, AssetRulPrediction
)
from maintenance.models import (
    PmPlan, PmPlanChecklistItem, PmPlanMaterial, PmPlanAssignment
)
from workorders.models import (
    WorkOrder, WorkOrderChecklistItem, WorkOrderMaterial,
    LaborLog, WorkOrderCost, AttendanceLog, HsmStageTransition,
    GAOptimizationJob, WorkOrderAttachment
)
from notifications.models import Notification, NotificationPreference, DevicePushToken
from analytics.models import TenantFinancialSetting, BudgetForecast, PeriodApprovedBudget

try:
    from assistant.models import TechnicalDocument, DocumentChunk, CuratedQAKnowledge
except ImportError:
    TechnicalDocument = DocumentChunk = CuratedQAKnowledge = None


EXPECTED_TENANT_CODE = "VANLAM_DEMO_2026"
EXPECTED_TENANT_ID = uuid.UUID("ba11a3d0-2026-4000-8000-000000000001")


class Command(BaseCommand):
    help = "Create an isolated, verified baseline backup for Van Lam Demo Tenant (VANLAM_DEMO_2026)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--create-baseline',
            action='store_true',
            help='Create official baseline backup (e.g. VANLAM_DEMO_BASELINE_<DATE>.dump)'
        )
        parser.add_argument(
            '--output-dir',
            type=str,
            default=None,
            help='Directory to store backup files (default: project root / backups)'
        )
        parser.add_argument(
            '--filename',
            type=str,
            default=None,
            help='Custom filename for backup'
        )

    def handle(self, *args, **options):
        create_baseline = options.get('create_baseline', False)
        output_dir = options.get('output_dir')
        custom_filename = options.get('filename')

        self.stdout.write("=" * 70)
        self.stdout.write("[*] INITIATING VAN LAM DEMO TENANT BACKUP")
        self.stdout.write("=" * 70)

        # 1. Strict Safety Verification
        current_db = settings.DATABASES['default']['NAME']
        self.stdout.write(f"-> Target Database: {current_db}")

        tenant = Tenant.objects.filter(tenant_code=EXPECTED_TENANT_CODE).first()
        if not tenant:
            self.stdout.write(self.style.ERROR(f"[FAIL] Tenant code '{EXPECTED_TENANT_CODE}' does not exist!"))
            return

        if tenant.id != EXPECTED_TENANT_ID:
            self.stdout.write(self.style.ERROR(f"[FAIL] Tenant ID mismatch! Expected {EXPECTED_TENANT_ID}, got {tenant.id}"))
            return

        if str(tenant.id).startswith("00000000") or tenant.tenant_code in ["SYSTEM", "VF_MFG", "VF_HP"]:
            self.stdout.write(self.style.ERROR(f"[FATAL] Safety breach: Refusing to touch non-demo tenant {tenant.name}!"))
            return

        # Determine Backup Directory
        if not output_dir:
            output_dir = os.path.abspath(os.path.join(settings.BASE_DIR, '..', 'backups'))
        os.makedirs(output_dir, exist_ok=True)

        date_str = timezone.now().strftime("%Y%m%d")
        if custom_filename:
            base_name = custom_filename
        elif create_baseline:
            base_name = f"VANLAM_DEMO_BASELINE_{date_str}"
        else:
            base_name = f"VANLAM_DEMO_BACKUP_{timezone.now().strftime('%Y%m%d_%H%M%S')}"

        dump_path = os.path.join(output_dir, f"{base_name}.dump")
        json_path = os.path.join(output_dir, f"{base_name}.json")
        latest_dump_path = os.path.join(output_dir, "VANLAM_DEMO_BASELINE_LATEST.dump")
        latest_json_path = os.path.join(output_dir, "VANLAM_DEMO_BASELINE_LATEST.json")

        self.stdout.write(f"-> Destination Dump File: {dump_path}")
        self.stdout.write(f"-> Destination JSON File: {json_path}")

        # 2. Gather All Tenant Objects in Dependency Order
        tenant_qs = Tenant.objects.filter(id=tenant.id)
        roles_qs = Role.all_objects.filter(tenant=tenant)
        users_qs = User.all_objects.filter(tenant=tenant)
        skills_qs = WorkforceSkill.all_objects.filter(tenant=tenant)
        cert_types_qs = CertificationType.all_objects.filter(tenant=tenant)
        user_certs_qs = UserCertification.all_objects.filter(tenant=tenant)
        shifts_qs = ShiftTemplate.all_objects.filter(tenant=tenant)
        schedules_qs = TechnicianSchedule.all_objects.filter(tenant=tenant)
        biometrics_qs = BiometricProfile.all_objects.filter(tenant=tenant)
        tech_profiles_qs = TechnicianProfile.all_objects.filter(tenant=tenant)
        locations_qs = Location.all_objects.filter(tenant=tenant)
        categories_qs = AssetCategory.all_objects.filter(tenant=tenant)
        hier_qs = HierarchyTemplate.all_objects.filter(tenant=tenant)
        tools_qs = Tool.all_objects.filter(tenant=tenant)
        tool_instances_qs = ToolInstance.all_objects.filter(tenant=tenant)
        tool_res_qs = ToolReservation.all_objects.filter(tenant=tenant)
        spare_parts_qs = SparePart.all_objects.filter(tenant=tenant)
        stock_trans_qs = StockTransaction.all_objects.filter(tenant=tenant)
        assets_qs = Asset.all_objects.filter(tenant=tenant)
        meter_readings_qs = MeterReading.all_objects.filter(tenant=tenant)
        anomaly_alerts_qs = AssetAnomalyAlert.all_objects.filter(tenant=tenant)
        rul_predictions_qs = AssetRulPrediction.all_objects.filter(tenant=tenant)
        pm_plans_qs = PmPlan.all_objects.filter(tenant=tenant)
        pm_checklists_qs = PmPlanChecklistItem.all_objects.filter(tenant=tenant)
        pm_materials_qs = PmPlanMaterial.all_objects.filter(tenant=tenant)
        pm_assignments_qs = PmPlanAssignment.all_objects.filter(tenant=tenant)
        work_orders_qs = WorkOrder.all_objects.filter(tenant=tenant)
        wo_checklists_qs = WorkOrderChecklistItem.all_objects.filter(tenant=tenant)
        wo_materials_qs = WorkOrderMaterial.all_objects.filter(tenant=tenant)
        labor_logs_qs = LaborLog.all_objects.filter(tenant=tenant)
        costs_qs = WorkOrderCost.all_objects.filter(tenant=tenant)
        attendances_qs = AttendanceLog.all_objects.filter(tenant=tenant)
        hsm_trans_qs = HsmStageTransition.all_objects.filter(tenant=tenant)
        fin_settings_qs = TenantFinancialSetting.all_objects.filter(tenant=tenant)
        forecasts_qs = BudgetForecast.all_objects.filter(tenant=tenant)
        notifications_qs = Notification.all_objects.filter(tenant=tenant)
        ga_jobs_qs = GAOptimizationJob.all_objects.filter(tenant=tenant)
        wo_attach_qs = WorkOrderAttachment.all_objects.filter(tenant=tenant)
        appr_budgets_qs = PeriodApprovedBudget.all_objects.filter(tenant=tenant)

        all_querysets = [
            tenant_qs, roles_qs, users_qs, skills_qs, cert_types_qs,
            user_certs_qs, shifts_qs, schedules_qs, biometrics_qs, tech_profiles_qs,
            locations_qs, categories_qs, hier_qs, tools_qs, tool_instances_qs,
            spare_parts_qs, stock_trans_qs, assets_qs, meter_readings_qs,
            anomaly_alerts_qs, rul_predictions_qs, pm_plans_qs, pm_checklists_qs,
            pm_materials_qs, pm_assignments_qs, work_orders_qs, wo_checklists_qs,
            wo_materials_qs, labor_logs_qs, costs_qs, attendances_qs, hsm_trans_qs,
            tool_res_qs, fin_settings_qs, forecasts_qs, notifications_qs,
            ga_jobs_qs, wo_attach_qs, appr_budgets_qs
        ]

        if TechnicalDocument and DocumentChunk and CuratedQAKnowledge:
            docs_qs = TechnicalDocument.all_objects.filter(tenant=tenant)
            chunks_qs = DocumentChunk.all_objects.filter(tenant=tenant)
            qa_qs = CuratedQAKnowledge.all_objects.filter(tenant=tenant)
            all_querysets.extend([docs_qs, chunks_qs, qa_qs])

        # Counts
        entity_counts = {}
        all_objects_list = []
        for qs in all_querysets:
            m_name = qs.model.__name__
            objs = list(qs)
            entity_counts[m_name] = len(objs)
            all_objects_list.extend(objs)

        self.stdout.write(f"-> Total Objects to Backup: {len(all_objects_list)} across {len(entity_counts)} models")

        # Serialize using Django Serializer
        serialized_json_str = serializers.serialize("json", all_objects_list, indent=2)

        # Manifest metadata
        manifest = {
            "backup_name": base_name,
            "created_at": timezone.now().isoformat(),
            "database_name": current_db,
            "tenant_code": EXPECTED_TENANT_CODE,
            "tenant_id": str(EXPECTED_TENANT_ID),
            "total_objects": len(all_objects_list),
            "entity_counts": entity_counts,
            "sha256": hashlib.sha256(serialized_json_str.encode('utf-8')).hexdigest()
        }

        full_payload = {
            "manifest": manifest,
            "data": json.loads(serialized_json_str)
        }

        full_payload_str = json.dumps(full_payload, indent=2, ensure_ascii=False)

        # Write readable JSON file
        with open(json_path, 'w', encoding='utf-8') as f:
            f.write(full_payload_str)

        # Write compressed .dump file (gzip compressed JSON)
        with gzip.open(dump_path, 'wt', encoding='utf-8') as f:
            f.write(full_payload_str)

        # If creating baseline, update canonical LATEST files
        if create_baseline:
            with open(latest_json_path, 'w', encoding='utf-8') as f:
                f.write(full_payload_str)
            with gzip.open(latest_dump_path, 'wt', encoding='utf-8') as f:
                f.write(full_payload_str)
            self.stdout.write(f"-> Canonical pointer updated: {latest_dump_path}")

        # 3. Verification Read
        self.stdout.write("-> Verifying backup readability...")
        with gzip.open(dump_path, 'rt', encoding='utf-8') as f:
            read_payload = json.load(f)
        read_obj_count = len(read_payload.get('data', []))
        if read_obj_count != len(all_objects_list):
            self.stdout.write(self.style.ERROR(f"[FAIL] Verification mismatch: dumped {len(all_objects_list)} but read {read_obj_count}"))
            return

        self.stdout.write("=" * 70)
        self.stdout.write(self.style.SUCCESS(f"[OK] BASELINE BACKUP CREATED AND VERIFIED SUCCESSFULLY!"))
        self.stdout.write(f"-> File:   {dump_path}")
        self.stdout.write(f"-> SHA256: {manifest['sha256']}")
        self.stdout.write(f"-> Total:  {len(all_objects_list)} objects verified")
        self.stdout.write("=" * 70)

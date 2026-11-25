import os
import sys
import json
import gzip
import uuid

from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import transaction
from django.core import serializers
from django.utils import timezone

from core.models import Tenant, AuditLog
from users.models import (
    User, Role, Permission, TechnicianProfile,
    WorkforceSkill, CertificationType, UserCertification,
    ShiftTemplate, TechnicianSchedule, BiometricProfile,
    InviteToken
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
from analytics.models import TenantFinancialSetting, BudgetForecast, ExportJob, PeriodApprovedBudget
from analytics.services import DashboardCacheService

try:
    from assistant.models import TechnicalDocument, DocumentChunk, CuratedQAKnowledge, CurationQueueItem
except ImportError:
    TechnicalDocument = DocumentChunk = CuratedQAKnowledge = CurationQueueItem = None


EXPECTED_TENANT_CODE = "VANLAM_DEMO_2026"
EXPECTED_TENANT_ID = uuid.UUID("ba11a3d0-2026-4000-8000-000000000001")


class Command(BaseCommand):
    help = "Safely reset or restore Van Lam Demo Tenant (VANLAM_DEMO_2026) without affecting any other tenant"

    def add_arguments(self, parser):
        parser.add_argument(
            '--restore-baseline',
            action='store_true',
            help='Restore tenant to the saved baseline backup (.dump file)'
        )
        parser.add_argument(
            '--reseed',
            action='store_true',
            help='Wipe tenant demo data and re-seed clean baseline from scratch'
        )
        parser.add_argument(
            '--clean-qa',
            action='store_true',
            help='Safely delete only QA/Test records (prefixed with QA_VANLAM_)'
        )
        parser.add_argument(
            '--baseline-file',
            type=str,
            default=None,
            help='Specific baseline dump file path to restore from'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Bypass interactive confirmation prompt'
        )

    def handle(self, *args, **options):
        restore_baseline = options.get('restore_baseline', False)
        reseed = options.get('reseed', False)
        clean_qa = options.get('clean_qa', False)
        baseline_file = options.get('baseline_file')
        force = options.get('force', False)

        if not (restore_baseline or reseed or clean_qa):
            from django.core.management.base import CommandError
            raise CommandError(
                "[ERROR] Please specify an action: --restore-baseline, --reseed, or --clean-qa\n"
                "Examples:\n"
                "  python manage.py reset_vanlam_demo --restore-baseline\n"
                "  python manage.py reset_vanlam_demo --reseed\n"
                "  python manage.py reset_vanlam_demo --clean-qa\n"
            )

        self.stdout.write("=" * 70)
        self.stdout.write("[*] VAN LAM DEMO RESET & RESTORE ENGINE")
        self.stdout.write("=" * 70)

        # 1. STRICT SAFETY CHECKS
        current_db = settings.DATABASES['default']['NAME']
        self.stdout.write(f"-> Target Database: {current_db}")

        if 'eam_db' not in current_db and 'test' not in current_db.lower():
            self.stdout.write(self.style.ERROR(f"[FATAL] Safety violation: Attempted to run reset on unexpected database '{current_db}'!"))
            return

        tenant = Tenant.objects.filter(tenant_code=EXPECTED_TENANT_CODE).first()
        if not tenant:
            if reseed:
                self.stdout.write(self.style.WARNING(f"[INFO] Tenant {EXPECTED_TENANT_CODE} does not exist yet. Will create via reseed."))
            else:
                self.stdout.write(self.style.ERROR(f"[FAIL] Tenant code '{EXPECTED_TENANT_CODE}' does not exist!"))
                return

        if tenant:
            if tenant.id != EXPECTED_TENANT_ID:
                self.stdout.write(self.style.ERROR(f"[FATAL] Tenant ID mismatch! Expected {EXPECTED_TENANT_ID}, got {tenant.id}"))
                return

            if str(tenant.id).startswith("00000000") or tenant.tenant_code in ["SYSTEM", "VF_MFG", "VF_HP"]:
                self.stdout.write(self.style.ERROR(f"[FATAL] Safety breach: Refusing to reset non-demo tenant {tenant.name}!"))
                return

        # 2. Confirmation prompt if not force
        if not force:
            action_desc = "RESTORE BASELINE" if restore_baseline else ("RE-SEED BASELINE" if reseed else "PURGE QA DATA")
            self.stdout.write(self.style.WARNING(
                f"\n[CONFIRMATION REQUIRED] You are about to {action_desc} for tenant:\n"
                f"  - Tenant Name: Nhà Máy Sản Xuất & Lắp Ráp Vân Lam\n"
                f"  - Tenant Code: {EXPECTED_TENANT_CODE}\n"
                f"  - Tenant UUID: {EXPECTED_TENANT_ID}\n"
                f"  - Database:    {current_db}\n"
            ))
            confirm = input("Type 'CONFIRM' to proceed, or anything else to abort: ").strip()
            if confirm != "CONFIRM":
                self.stdout.write(self.style.NOTICE("[ABORTED] Operation cancelled by user."))
                return

        # Action A: Clean QA data only
        if clean_qa:
            self._clean_qa_data(tenant)
            return

        # Action B: Restore Baseline
        if restore_baseline:
            self._restore_from_baseline(tenant, baseline_file)
            return

        # Action C: Reseed fresh from seed_vanlam_demo
        if reseed:
            self._reseed_baseline(tenant)
            return

    def _clean_qa_data(self, tenant):
        """Purges only records prefixed with QA_VANLAM_ belonging to this tenant."""
        self.stdout.write("-> Purging QA/Test records for Vân Lam...")
        with transaction.atomic():
            qa_wos = WorkOrder.all_objects.filter(tenant=tenant, title__startswith="QA_VANLAM_")
            wo_count = qa_wos.count()
            for wo in qa_wos:
                WorkOrderChecklistItem.all_objects.filter(work_order=wo).delete()
                WorkOrderMaterial.all_objects.filter(work_order=wo).delete()
                LaborLog.all_objects.filter(work_order=wo).delete()
                WorkOrderCost.all_objects.filter(work_order=wo).delete()
                WorkOrderAttachment.all_objects.filter(work_order=wo).delete()
                wo.delete()

            qa_pm = PmPlan.all_objects.filter(tenant=tenant, name__startswith="QA_VANLAM_")
            pm_count = qa_pm.count()
            for p in qa_pm:
                PmPlanChecklistItem.all_objects.filter(pm_plan=p).delete()
                PmPlanMaterial.all_objects.filter(pm_plan=p).delete()
                PmPlanAssignment.all_objects.filter(pm_plan=p).delete()
                p.delete()

            qa_parts = SparePart.all_objects.filter(tenant=tenant, part_number__startswith="QA_VANLAM_")
            part_count = qa_parts.count()
            for sp in qa_parts:
                StockTransaction.all_objects.filter(spare_part=sp).delete()
                sp.delete()

            qa_tools = Tool.all_objects.filter(tenant=tenant, name__startswith="QA_VANLAM_")
            tool_count = qa_tools.count()
            for tl in qa_tools:
                ToolReservation.all_objects.filter(tool=tl).delete()
                ToolInstance.all_objects.filter(tool=tl).delete()
                tl.delete()

            qa_locations = Location.all_objects.filter(tenant=tenant, name__startswith="QA_VANLAM_")
            location_count = qa_locations.count()
            for loc in qa_locations:
                loc.delete()

            qa_categories = AssetCategory.all_objects.filter(tenant=tenant, name__startswith="QA_VANLAM_")
            category_count = qa_categories.count()
            for cat in qa_categories:
                cat.delete()

            qa_assets = Asset.all_objects.filter(tenant=tenant, name__startswith="QA_VANLAM_")
            asset_count = qa_assets.count()
            for a in qa_assets:
                MeterReading.all_objects.filter(asset=a).delete()
                AssetAnomalyAlert.all_objects.filter(asset=a).delete()
                AssetRulPrediction.all_objects.filter(asset=a).delete()
                a.delete()

            qa_users = User.all_objects.filter(tenant=tenant, username__startswith="QA_VANLAM_")
            user_count = qa_users.count()
            for u in qa_users:
                u.roles.clear()
                TechnicianProfile.all_objects.filter(user=u).delete()
                BiometricProfile.all_objects.filter(user=u).delete()
                TechnicianSchedule.all_objects.filter(user=u).delete()
                UserCertification.all_objects.filter(user=u).delete()
                Notification.all_objects.filter(recipient=u).delete()
                u.delete()

            DashboardCacheService.invalidate_all(tenant.id)

        self.stdout.write(self.style.SUCCESS(
            f"[OK] Cleaned QA data: {wo_count} WOs, {pm_count} PM Plans, {part_count} Parts, {tool_count} Tools, {asset_count} Assets, {user_count} Users deleted."
        ))

    def _safe_purge_tenant_data(self, tenant):
        """Safely deletes strictly tenant-scoped child data in reverse dependency order."""
        self.stdout.write("-> Safely deleting existing Vân Lam tenant entities...")
        counts = {}

        # Child tables and auxiliary session/job tables first
        counts['ga_jobs'] = GAOptimizationJob.all_objects.filter(tenant=tenant).delete()[0]
        counts['wo_attachments'] = WorkOrderAttachment.all_objects.filter(tenant=tenant).delete()[0]
        counts['notifications'] = Notification.all_objects.filter(tenant=tenant).delete()[0]
        counts['notif_preferences'] = NotificationPreference.all_objects.filter(tenant=tenant).delete()[0]
        counts['device_push_tokens'] = DevicePushToken.all_objects.filter(tenant=tenant).delete()[0]
        counts['export_jobs'] = ExportJob.all_objects.filter(tenant=tenant).delete()[0]
        counts['approved_budgets'] = PeriodApprovedBudget.all_objects.filter(tenant=tenant).delete()[0]
        counts['invite_tokens'] = InviteToken.all_objects.filter(tenant=tenant).delete()[0]
        if CurationQueueItem:
            counts['curation_queue'] = CurationQueueItem.all_objects.filter(tenant=tenant).delete()[0]

        counts['tool_reservations'] = ToolReservation.all_objects.filter(tenant=tenant).delete()[0]
        counts['attendance_logs'] = AttendanceLog.all_objects.filter(tenant=tenant).delete()[0]
        counts['hsm_transitions'] = HsmStageTransition.all_objects.filter(tenant=tenant).delete()[0]
        counts['costs'] = WorkOrderCost.all_objects.filter(tenant=tenant).delete()[0]
        counts['labor_logs'] = LaborLog.all_objects.filter(tenant=tenant).delete()[0]
        counts['wo_materials'] = WorkOrderMaterial.all_objects.filter(tenant=tenant).delete()[0]
        counts['wo_checklists'] = WorkOrderChecklistItem.all_objects.filter(tenant=tenant).delete()[0]
        counts['work_orders'] = WorkOrder.all_objects.filter(tenant=tenant).delete()[0]

        counts['pm_assignments'] = PmPlanAssignment.all_objects.filter(tenant=tenant).delete()[0]
        counts['pm_materials'] = PmPlanMaterial.all_objects.filter(tenant=tenant).delete()[0]
        counts['pm_checklists'] = PmPlanChecklistItem.all_objects.filter(tenant=tenant).delete()[0]
        counts['pm_plans'] = PmPlan.all_objects.filter(tenant=tenant).delete()[0]

        counts['rul_predictions'] = AssetRulPrediction.all_objects.filter(tenant=tenant).delete()[0]
        counts['anomaly_alerts'] = AssetAnomalyAlert.all_objects.filter(tenant=tenant).delete()[0]
        counts['meter_readings'] = MeterReading.all_objects.filter(tenant=tenant).delete()[0]
        counts['stock_transactions'] = StockTransaction.all_objects.filter(tenant=tenant).delete()[0]
        counts['spare_parts'] = SparePart.all_objects.filter(tenant=tenant).delete()[0]

        counts['tool_instances'] = ToolInstance.all_objects.filter(tenant=tenant).delete()[0]
        counts['tools'] = Tool.all_objects.filter(tenant=tenant).delete()[0]

        counts['assets'] = Asset.all_objects.filter(tenant=tenant).delete()[0]
        counts['hierarchy_templates'] = HierarchyTemplate.all_objects.filter(tenant=tenant).delete()[0]
        counts['asset_categories'] = AssetCategory.all_objects.filter(tenant=tenant).delete()[0]
        counts['locations'] = Location.all_objects.filter(tenant=tenant).delete()[0]

        counts['schedules'] = TechnicianSchedule.all_objects.filter(tenant=tenant).delete()[0]
        counts['user_certs'] = UserCertification.all_objects.filter(tenant=tenant).delete()[0]
        counts['shift_templates'] = ShiftTemplate.all_objects.filter(tenant=tenant).delete()[0]
        counts['cert_types'] = CertificationType.all_objects.filter(tenant=tenant).delete()[0]
        counts['skills'] = WorkforceSkill.all_objects.filter(tenant=tenant).delete()[0]
        counts['biometrics'] = BiometricProfile.all_objects.filter(tenant=tenant).delete()[0]
        counts['tech_profiles'] = TechnicianProfile.all_objects.filter(tenant=tenant).delete()[0]

        counts['fin_settings'] = TenantFinancialSetting.all_objects.filter(tenant=tenant).delete()[0]
        counts['budget_forecasts'] = BudgetForecast.all_objects.filter(tenant=tenant).delete()[0]

        if TechnicalDocument and DocumentChunk and CuratedQAKnowledge:
            counts['curated_qa'] = CuratedQAKnowledge.all_objects.filter(tenant=tenant).delete()[0]
            counts['document_chunks'] = DocumentChunk.all_objects.filter(tenant=tenant).delete()[0]
            # NEVER delete where is_system_guide=True or tenant is None
            counts['technical_docs'] = TechnicalDocument.all_objects.filter(tenant=tenant, is_system_guide=False).delete()[0]

        counts['audit_logs'] = AuditLog.all_objects.filter(tenant_id=tenant.id).delete()[0]

        # Users and Roles
        u_count = 0
        for u in User.all_objects.filter(tenant=tenant):
            u.roles.clear()
            u.delete()
            u_count += 1
        counts['users'] = u_count
        counts['roles'] = Role.all_objects.filter(tenant=tenant).delete()[0]

        total_deleted = sum(counts.values())
        self.stdout.write(f"-> Total purged entities: {total_deleted}")
        return counts

    def _restore_from_baseline(self, tenant, baseline_file):
        """Restores all entities from baseline dump file."""
        # Locate baseline dump file
        target_file = baseline_file
        if not target_file:
            candidates = [
                os.path.abspath(os.path.join(settings.BASE_DIR, '..', 'backups', 'VANLAM_DEMO_BASELINE_LATEST.dump')),
                os.path.abspath(os.path.join(settings.BASE_DIR, 'backups', 'VANLAM_DEMO_BASELINE_LATEST.dump')),
                os.path.abspath(os.path.join('backups', 'VANLAM_DEMO_BASELINE_LATEST.dump')),
            ]
            for c in candidates:
                if os.path.exists(c):
                    target_file = c
                    break

        if not target_file or not os.path.exists(target_file):
            self.stdout.write(self.style.ERROR(
                f"[FAIL] Baseline dump file not found! Checked: {candidates if not baseline_file else baseline_file}\n"
                "Please run 'python manage.py backup_vanlam_demo --create-baseline' first."
            ))
            return

        self.stdout.write(f"-> Reading Baseline Dump: {target_file}")
        try:
            with gzip.open(target_file, 'rt', encoding='utf-8') as f:
                payload = json.load(f)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"[FAIL] Baseline dump file is corrupted or unreadable: {e}"))
            return

        manifest = payload.get('manifest', {})
        raw_data = payload.get('data', [])

        # Validate manifest
        if manifest.get('tenant_code') != EXPECTED_TENANT_CODE:
            self.stdout.write(self.style.ERROR(f"[FAIL] Manifest tenant_code mismatch: {manifest.get('tenant_code')} != {EXPECTED_TENANT_CODE}"))
            return

        self.stdout.write(f"-> Backup timestamp: {manifest.get('created_at')}")
        self.stdout.write(f"-> Objects in dump:  {len(raw_data)}")

        with transaction.atomic():
            if tenant:
                self._safe_purge_tenant_data(tenant)

            self.stdout.write("-> Deserializing and restoring objects into database...")
            data_str = json.dumps(raw_data)
            restored_count = 0
            m2m_count = 0

            for deserialized_obj in serializers.deserialize("json", data_str):
                deserialized_obj.save()
                restored_count += 1
                if deserialized_obj.m2m_data:
                    deserialized_obj.save_m2m()
                    m2m_count += 1

            # Invalidate caches
            DashboardCacheService.invalidate_all(EXPECTED_TENANT_ID)

        self.stdout.write("=" * 70)
        self.stdout.write(self.style.SUCCESS(
            f"[PASS] VAN LAM DEMO TENANT SUCCESSFULLY RESTORED TO BASELINE!\n"
            f"-> Total Restored: {restored_count} entities\n"
            f"-> M2M Relations:  {m2m_count} mappings saved\n"
            f"-> All demo users and test workflows restored to initial state."
        ))
        self.stdout.write("=" * 70)

    def _reseed_baseline(self, tenant):
        """Wipes tenant and runs clean seeder."""
        from django.core.management import call_command
        with transaction.atomic():
            if tenant:
                self._safe_purge_tenant_data(tenant)

        self.stdout.write("-> Re-running seed_vanlam_demo seeder...")
        call_command('seed_vanlam_demo', silent=False)

        self.stdout.write("=" * 70)
        self.stdout.write(self.style.SUCCESS(
            "[PASS] VAN LAM DEMO TENANT RESEEDED CLEANLY TO BASELINE!"
        ))
        self.stdout.write("=" * 70)

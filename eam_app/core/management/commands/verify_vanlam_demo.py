import json
import uuid
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import connection
from django.contrib.auth import authenticate

from core.models import Tenant, AuditLog
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
from notifications.models import Notification
from analytics.models import TenantFinancialSetting, BudgetForecast, PeriodApprovedBudget

try:
    from assistant.models import TechnicalDocument, DocumentChunk, CuratedQAKnowledge
except ImportError:
    TechnicalDocument = DocumentChunk = CuratedQAKnowledge = None


EXPECTED_TENANT_CODE = "VANLAM_DEMO_2026"
EXPECTED_TENANT_ID = uuid.UUID("ba11a3d0-2026-4000-8000-000000000001")


class Command(BaseCommand):
    help = "Verify integrity, credentials, and data counts of Van Lam Demo Tenant (VANLAM_DEMO_2026)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant-code',
            type=str,
            default=EXPECTED_TENANT_CODE,
            help=f"Tenant code to verify (default: {EXPECTED_TENANT_CODE})"
        )
        parser.add_argument(
            '--check-baseline',
            action='store_true',
            help='Compare current counts against saved baseline manifest'
        )
        parser.add_argument(
            '--baseline-file',
            type=str,
            default=None,
            help='Path to specific baseline manifest file for comparison'
        )
        parser.add_argument(
            '--json',
            action='store_true',
            dest='output_json',
            help='Output results formatted as JSON'
        )

    def handle(self, *args, **options):
        tenant_code = options['tenant_code']
        check_baseline = options['check_baseline']
        baseline_file = options.get('baseline_file')
        output_json = options['output_json']

        errors = []
        warnings = []
        info_data = {}

        # 1. Database check
        current_db = settings.DATABASES['default']['NAME']
        info_data['database'] = current_db
        if 'eam_db' not in current_db and 'test' not in current_db.lower():
            warnings.append(f"Connected to non-standard database: {current_db} (expected eam_db)")

        # 2. Strict Tenant Verification
        tenant = Tenant.objects.filter(tenant_code=tenant_code).first()
        if not tenant:
            self.stdout.write(self.style.ERROR(f"[FAIL] Tenant code '{tenant_code}' not found in database!"))
            return

        if tenant.id != EXPECTED_TENANT_ID:
            errors.append(f"Tenant UUID mismatch: expected {EXPECTED_TENANT_ID}, got {tenant.id}")

        if tenant_code != EXPECTED_TENANT_CODE:
            errors.append(f"Tenant code mismatch: expected {EXPECTED_TENANT_CODE}, got {tenant_code}")

        # Protect SYSTEM and VinFast
        if str(tenant.id).startswith("00000000") or tenant.tenant_code in ["SYSTEM", "VF_MFG", "VF_HP"]:
            self.stdout.write(self.style.ERROR(f"[FATAL] Refusing to verify non-demo tenant {tenant.name}!"))
            return

        info_data['tenant'] = {
            'id': str(tenant.id),
            'code': tenant.tenant_code,
            'name': tenant.name,
            'status': tenant.status,
            'service_plan': tenant.service_plan,
            'theme_color': tenant.theme_color,
            'enable_ai_hungarian': tenant.enable_ai_hungarian,
            'enable_ai_genetic': tenant.enable_ai_genetic,
            'enable_tsp_routing': tenant.enable_tsp_routing,
            'enable_ai_rul': tenant.enable_ai_rul,
            'enable_ai_anomaly_detection': tenant.enable_ai_anomaly_detection,
            'enable_ai_cost_forecasting': tenant.enable_ai_cost_forecasting,
        }

        # 3. User & Authentication Verification
        demo_password = settings.SECRET_KEY if False else __import__('os').getenv("VANLAM_DEMO_PASSWORD", "Admin@123456")
        test_accounts = [
            ("vanlam_admin", demo_password, "TENANT_ADMIN"),
            ("vanlam_manager", demo_password, "MAINTENANCE_MANAGER"),
            ("vanlam_tech_an", demo_password, "TECHNICIAN"),
            ("vanlam_tech_binh", demo_password, "TECHNICIAN"),
            ("vanlam_tech_cuong", demo_password, "TECHNICIAN"),
            ("vanlam_tech_dung", demo_password, "TECHNICIAN"),
            ("vanlam_viewer", demo_password, "VIEWER"),
        ]

        auth_results = {}
        for username, password, expected_role in test_accounts:
            user_obj = User.all_objects.filter(tenant=tenant, username=username).first()
            if not user_obj:
                errors.append(f"Missing expected user: {username}")
                auth_results[username] = "MISSING"
                continue

            pw_ok = user_obj.check_password(password)
            if not pw_ok:
                errors.append(f"Password verification failed for user: {username}")
                auth_results[username] = "WRONG_PASSWORD"
                continue

            has_role = user_obj.roles.filter(name=expected_role).exists()
            if not has_role:
                warnings.append(f"User {username} missing expected role {expected_role}")
                auth_results[username] = f"OK (Missing role {expected_role})"
            else:
                auth_results[username] = "PASS"

        info_data['auth_verification'] = auth_results

        # 4. Count All Entities for this Tenant
        counts = {
            'users': User.all_objects.filter(tenant=tenant).count(),
            'roles': Role.all_objects.filter(tenant=tenant).count(),
            'skills': WorkforceSkill.all_objects.filter(tenant=tenant).count(),
            'cert_types': CertificationType.all_objects.filter(tenant=tenant).count(),
            'user_certs': UserCertification.all_objects.filter(tenant=tenant).count(),
            'shift_templates': ShiftTemplate.all_objects.filter(tenant=tenant).count(),
            'schedules': TechnicianSchedule.all_objects.filter(tenant=tenant).count(),
            'biometric_profiles': BiometricProfile.all_objects.filter(tenant=tenant).count(),
            'technician_profiles': TechnicianProfile.all_objects.filter(tenant=tenant).count(),
            'locations': Location.all_objects.filter(tenant=tenant).count(),
            'floorplans': Location.all_objects.filter(tenant=tenant, zone_type='FLOORPLAN').count(),
            'asset_categories': AssetCategory.all_objects.filter(tenant=tenant).count(),
            'hierarchy_templates': HierarchyTemplate.all_objects.filter(tenant=tenant).count(),
            'tools': Tool.all_objects.filter(tenant=tenant).count(),
            'tool_instances': ToolInstance.all_objects.filter(tenant=tenant).count(),
            'tool_reservations': ToolReservation.all_objects.filter(tenant=tenant).count(),
            'spare_parts': SparePart.all_objects.filter(tenant=tenant).count(),
            'stock_transactions': StockTransaction.all_objects.filter(tenant=tenant).count(),
            'assets': Asset.all_objects.filter(tenant=tenant).count(),
            'meter_readings': MeterReading.all_objects.filter(tenant=tenant).count(),
            'anomaly_alerts': AssetAnomalyAlert.all_objects.filter(tenant=tenant).count(),
            'rul_predictions': AssetRulPrediction.all_objects.filter(tenant=tenant).count(),
            'pm_plans': PmPlan.all_objects.filter(tenant=tenant).count(),
            'pm_checklists': PmPlanChecklistItem.all_objects.filter(tenant=tenant).count(),
            'pm_materials': PmPlanMaterial.all_objects.filter(tenant=tenant).count(),
            'pm_assignments': PmPlanAssignment.all_objects.filter(tenant=tenant).count(),
            'work_orders': WorkOrder.all_objects.filter(tenant=tenant).count(),
            'wo_created': WorkOrder.all_objects.filter(tenant=tenant, status='CREATED').count(),
            'wo_assigned': WorkOrder.all_objects.filter(tenant=tenant, status='ASSIGNED').count(),
            'wo_in_progress': WorkOrder.all_objects.filter(tenant=tenant, status='IN_PROGRESS').count(),
            'wo_completed': WorkOrder.all_objects.filter(tenant=tenant, status='COMPLETED').count(),
            'wo_checklists': WorkOrderChecklistItem.all_objects.filter(tenant=tenant).count(),
            'wo_materials': WorkOrderMaterial.all_objects.filter(tenant=tenant).count(),
            'labor_logs': LaborLog.all_objects.filter(tenant=tenant).count(),
            'work_order_costs': WorkOrderCost.all_objects.filter(tenant=tenant).count(),
            'attendance_logs': AttendanceLog.all_objects.filter(tenant=tenant).count(),
            'hsm_transitions': HsmStageTransition.all_objects.filter(tenant=tenant).count(),
            'financial_settings': TenantFinancialSetting.all_objects.filter(tenant=tenant).count(),
            'budget_forecasts': BudgetForecast.all_objects.filter(tenant=tenant).count(),
            'notifications': Notification.all_objects.filter(tenant=tenant).count(),
            'ga_jobs': GAOptimizationJob.all_objects.filter(tenant=tenant).count(),
            'work_order_attachments': WorkOrderAttachment.all_objects.filter(tenant=tenant).count(),
            'period_approved_budgets': PeriodApprovedBudget.all_objects.filter(tenant=tenant).count(),
        }

        if TechnicalDocument and DocumentChunk and CuratedQAKnowledge:
            counts['technical_documents'] = TechnicalDocument.all_objects.filter(tenant=tenant).count()
            counts['document_chunks'] = DocumentChunk.all_objects.filter(tenant=tenant).count()
            counts['curated_qa'] = CuratedQAKnowledge.all_objects.filter(tenant=tenant).count()

        info_data['entity_counts'] = counts

        # Minimum required counts verification
        min_thresholds = {
            'users': 7,
            'roles': 4,
            'skills': 6,
            'locations': 5,
            'floorplans': 2,
            'assets': 6,
            'tools': 4,
            'tool_instances': 8,
            'spare_parts': 6,
            'pm_plans': 4,
            'work_orders': 6,
            'meter_readings': 60,
            'anomaly_alerts': 1,
            'rul_predictions': 4,
        }
        for metric, min_val in min_thresholds.items():
            actual = counts.get(metric, 0)
            if actual < min_val:
                errors.append(f"Insufficient count for {metric}: got {actual}, expected at least {min_val}")

        # Baseline comparison if requested
        baseline_diff = {}
        if check_baseline:
            import os
            # Locate baseline manifest
            target_path = baseline_file
            if not target_path:
                candidate_paths = [
                    os.path.abspath(os.path.join(settings.BASE_DIR, '..', 'backups', 'VANLAM_DEMO_BASELINE_LATEST.json')),
                    os.path.abspath(os.path.join(settings.BASE_DIR, 'backups', 'VANLAM_DEMO_BASELINE_LATEST.json')),
                    os.path.abspath(os.path.join('backups', 'VANLAM_DEMO_BASELINE_LATEST.json')),
                ]
                for cp in candidate_paths:
                    if os.path.exists(cp):
                        target_path = cp
                        break

            if not target_path or not os.path.exists(target_path):
                warnings.append(f"Baseline manifest file not found for comparison! Tried: {candidate_paths if not baseline_file else baseline_file}")
            else:
                try:
                    with open(target_path, 'r', encoding='utf-8') as f:
                        b_payload = json.load(f)
                    b_manifest = b_payload.get('manifest', {})
                    b_counts_raw = b_manifest.get('entity_counts', {})

                    # Map ModelName in manifest to metric key in counts
                    model_to_metric = {
                        'User': 'users',
                        'Role': 'roles',
                        'WorkforceSkill': 'skills',
                        'CertificationType': 'cert_types',
                        'UserCertification': 'user_certs',
                        'ShiftTemplate': 'shift_templates',
                        'TechnicianSchedule': 'schedules',
                        'BiometricProfile': 'biometric_profiles',
                        'TechnicianProfile': 'technician_profiles',
                        'Location': 'locations',
                        'AssetCategory': 'asset_categories',
                        'HierarchyTemplate': 'hierarchy_templates',
                        'Tool': 'tools',
                        'ToolInstance': 'tool_instances',
                        'ToolReservation': 'tool_reservations',
                        'SparePart': 'spare_parts',
                        'StockTransaction': 'stock_transactions',
                        'Asset': 'assets',
                        'MeterReading': 'meter_readings',
                        'AssetAnomalyAlert': 'anomaly_alerts',
                        'AssetRulPrediction': 'rul_predictions',
                        'PmPlan': 'pm_plans',
                        'PmPlanChecklistItem': 'pm_checklists',
                        'PmPlanMaterial': 'pm_materials',
                        'PmPlanAssignment': 'pm_assignments',
                        'WorkOrder': 'work_orders',
                        'WorkOrderChecklistItem': 'wo_checklists',
                        'WorkOrderMaterial': 'wo_materials',
                        'LaborLog': 'labor_logs',
                        'WorkOrderCost': 'work_order_costs',
                        'AttendanceLog': 'attendance_logs',
                        'HsmStageTransition': 'hsm_transitions',
                        'TenantFinancialSetting': 'financial_settings',
                        'BudgetForecast': 'budget_forecasts',
                        'Notification': 'notifications',
                        'GAOptimizationJob': 'ga_jobs',
                        'WorkOrderAttachment': 'work_order_attachments',
                        'PeriodApprovedBudget': 'period_approved_budgets',
                        'TechnicalDocument': 'technical_documents',
                        'DocumentChunk': 'document_chunks',
                        'CuratedQAKnowledge': 'curated_qa'
                    }

                    for model_name, b_val in b_counts_raw.items():
                        metric_key = model_to_metric.get(model_name)
                        if metric_key and metric_key in counts:
                            c_val = counts[metric_key]
                            if c_val != b_val:
                                baseline_diff[metric_key] = {'baseline': b_val, 'current': c_val, 'diff': c_val - b_val}
                                warnings.append(f"Data drift detected in {metric_key}: baseline={b_val}, current={c_val} ({c_val - b_val:+d})")

                    info_data['baseline_file'] = target_path
                    info_data['baseline_diff'] = baseline_diff
                except Exception as e:
                    errors.append(f"Failed to read baseline manifest {target_path}: {e}")

        # Check for QA records across all entities
        qa_users = User.all_objects.filter(tenant=tenant, username__startswith="QA_VANLAM_").count()
        qa_assets = Asset.all_objects.filter(tenant=tenant, name__startswith="QA_VANLAM_").count()
        qa_wos = WorkOrder.all_objects.filter(tenant=tenant, title__startswith="QA_VANLAM_").count()
        qa_pm = PmPlan.all_objects.filter(tenant=tenant, name__startswith="QA_VANLAM_").count()
        qa_parts = SparePart.all_objects.filter(tenant=tenant, part_number__startswith="QA_VANLAM_").count()
        qa_tools = Tool.all_objects.filter(tenant=tenant, name__startswith="QA_VANLAM_").count()
        qa_locations = Location.all_objects.filter(tenant=tenant, name__startswith="QA_VANLAM_").count()
        qa_categories = AssetCategory.all_objects.filter(tenant=tenant, name__startswith="QA_VANLAM_").count()
        qa_count = qa_users + qa_assets + qa_wos + qa_pm + qa_parts + qa_tools + qa_locations + qa_categories
        info_data['qa_records_detected'] = {
            'qa_users': qa_users,
            'qa_assets': qa_assets,
            'qa_work_orders': qa_wos,
            'qa_pm_plans': qa_pm,
            'qa_spare_parts': qa_parts,
            'qa_tools': qa_tools,
            'qa_locations': qa_locations,
            'qa_categories': qa_categories,
            'total_qa': qa_count
        }

        status_str = "PASS" if len(errors) == 0 else "FAIL"
        info_data['overall_status'] = status_str
        info_data['errors'] = errors
        info_data['warnings'] = warnings

        if output_json:
            self.stdout.write(json.dumps(info_data, indent=2, ensure_ascii=False))
            return

        # Console Output
        self.stdout.write("=" * 70)
        self.stdout.write(f"[*] VAN LAM DEMO VERIFICATION REPORT -- [{tenant_code}]")
        self.stdout.write("=" * 70)
        self.stdout.write(f"Database:      {current_db}")
        self.stdout.write(f"Tenant Name:   {tenant.name}")
        self.stdout.write(f"Tenant ID:     {tenant.id}")
        self.stdout.write(f"Service Plan:  {tenant.service_plan} | Status: {tenant.status}")
        self.stdout.write("-" * 70)

        self.stdout.write("AUTHENTICATION ACCOUNTS CHECK:")
        for u, st in auth_results.items():
            color_fn = self.style.SUCCESS if st == "PASS" else self.style.ERROR
            self.stdout.write(f"  - {u:<20}: " + color_fn(st))

        self.stdout.write("-" * 70)
        self.stdout.write("KEY ENTITY COUNTS:")
        col_items = list(counts.items())
        for i in range(0, len(col_items), 2):
            k1, v1 = col_items[i]
            s1 = f"{k1:<24}: {v1:>5}"
            if i + 1 < len(col_items):
                k2, v2 = col_items[i + 1]
                s2 = f"{k2:<24}: {v2:>5}"
                self.stdout.write(f"  {s1}  |  {s2}")
            else:
                self.stdout.write(f"  {s1}")

        self.stdout.write("-" * 70)
        if qa_count > 0:
            self.stdout.write(self.style.WARNING(f"[!] QA/Test records present: {qa_count} (Users: {qa_users}, Assets: {qa_assets}, WOs: {qa_wos}, PM: {qa_pm}, Parts: {qa_parts}, Tools: {qa_tools})"))
            self.stdout.write("    (Run 'python manage.py reset_vanlam_demo --clean-qa' to purge QA data)")

        if check_baseline:
            if len(baseline_diff) == 0 and 'baseline_file' in info_data:
                self.stdout.write(self.style.SUCCESS("[OK] 100% MATCH with Baseline Manifest! Zero drift detected."))
            elif baseline_diff:
                self.stdout.write(self.style.WARNING(f"[!] Baseline Data Drift in {len(baseline_diff)} entities:"))
                for k, diff_info in baseline_diff.items():
                    self.stdout.write(f"    * {k}: baseline={diff_info['baseline']} -> current={diff_info['current']} ({diff_info['diff']:+d})")

        if warnings:
            self.stdout.write(self.style.WARNING(f"Warnings ({len(warnings)}):"))
            for w in warnings:
                self.stdout.write(self.style.WARNING(f"  - {w}"))

        if errors:
            self.stdout.write(self.style.ERROR(f"Errors ({len(errors)}):"))
            for e in errors:
                self.stdout.write(self.style.ERROR(f"  - {e}"))

        self.stdout.write("=" * 70)
        if status_str == "PASS":
            self.stdout.write(self.style.SUCCESS("[PASS] VAN LAM DEMO TENANT INTEGRITY VERIFIED!"))
        else:
            self.stdout.write(self.style.ERROR("[FAIL] VAN LAM DEMO TENANT VERIFICATION FAILED!"))
        self.stdout.write("=" * 70)

        if errors:
            import sys
            sys.exit(1)

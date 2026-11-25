import os
import uuid
from decimal import Decimal
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.conf import settings

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
    LaborLog, WorkOrderCost, AttendanceLog, HsmStageTransition
)
from analytics.models import TenantFinancialSetting, BudgetForecast
from analytics.services import DashboardCacheService

try:
    from assistant.models import TechnicalDocument, DocumentChunk, CuratedQAKnowledge
except ImportError:
    TechnicalDocument = DocumentChunk = CuratedQAKnowledge = None


# Cố định Tenant Code và deterministic UUID cho Tenant Vân Lam Demo
VANLAM_TENANT_CODE = "VANLAM_DEMO_2026"
VANLAM_TENANT_ID = uuid.UUID("ba11a3d0-2026-4000-8000-000000000001")
VANLAM_DEMO_PASSWORD = os.getenv("VANLAM_DEMO_PASSWORD", "Admin@123456")


class Command(BaseCommand):
    help = "Seed comprehensive, fully functional master data for Van Lam Demo Tenant (VANLAM_DEMO_2026)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force re-seed: overwrite existing records if tenant already exists'
        )
        parser.add_argument(
            '--silent',
            action='store_true',
            help='Run silently with minimal stdout'
        )

    def handle(self, *args, **options):
        force = options.get('force', False)
        silent = options.get('silent', False)

        def log(msg, style_func=None):
            if not silent:
                if style_func:
                    self.stdout.write(style_func(msg))
                else:
                    self.stdout.write(msg)

        log("=" * 70, self.style.MIGRATE_HEADING)
        log(f"[*] SEEDING VAN LAM DEMO TENANT [{VANLAM_TENANT_CODE}]", self.style.MIGRATE_HEADING)
        log("=" * 70, self.style.MIGRATE_HEADING)

        # 0. Safety Checks
        db_name = settings.DATABASES['default']['NAME']
        log(f"-> Target Database: {db_name}")
        log(f"-> Tenant Code: {VANLAM_TENANT_CODE}")
        log(f"-> Tenant UUID: {VANLAM_TENANT_ID}")

        now = timezone.now()
        today = now.date()

        with transaction.atomic():
            # If force requested and tenant already exists, safely purge old demo records first
            existing_tenant = Tenant.objects.filter(id=VANLAM_TENANT_ID).first()
            if existing_tenant and force:
                log("-> [--force] Purging existing Van Lam tenant data before fresh re-seed...")
                from core.management.commands.reset_vanlam_demo import Command as ResetCommand
                rc = ResetCommand()
                rc.stdout = self.stdout
                rc.style = self.style
                rc._safe_purge_tenant_data(existing_tenant)

            # 1. Tenant Creation or Update
            tenant, created = Tenant.objects.update_or_create(
                id=VANLAM_TENANT_ID,
                defaults={
                    "tenant_code": VANLAM_TENANT_CODE,
                    "name": "Nhà Máy Sản Xuất & Lắp Ráp Vân Lam",
                    "timezone": "Asia/Ho_Chi_Minh",
                    "service_plan": "ENTERPRISE",
                    "status": "ACTIVE",
                    "theme_color": "emerald",
                    "enable_tsp_routing": True,
                    "enable_ai_hungarian": True,
                    "enable_ai_genetic": True,
                    "enable_ai_rul": True,
                    "enable_ai_anomaly_detection": True,
                    "enable_ai_cost_forecasting": True,
                    "enable_geofencing": True,
                }
            )
            log(f" [1/14] Tenant record: {'CREATED' if created else 'UPDATED'} -> {tenant.name}")

            # 2. Roles & Permissions Setup
            all_perms = list(Permission.objects.all())
            non_system_perms = [p for p in all_perms if p.id != 'system:admin']

            # Role: TENANT_ADMIN
            role_admin, _ = Role.all_objects.update_or_create(
                tenant=tenant,
                name="TENANT_ADMIN",
                defaults={"description": "Quản trị viên toàn quyền Nhà Máy Vân Lam"}
            )
            role_admin.permissions.set(non_system_perms)

            # Role: MAINTENANCE_MANAGER
            manager_perm_ids = [
                'tenant:read', 'user:read', 'role:read', 'workforce:read',
                'asset:read', 'asset:create', 'asset:update',
                'asset_category:read', 'location:read', 'hierarchy_template:read',
                'work_order:read', 'work_order:create', 'work_order:update', 'work_order:reassign',
                'pm_plan:read', 'pm_plan:create', 'pm_plan:update',
                'inventory:read', 'inventory:create', 'inventory:update',
                'reports:read', 'reports:export', 'cost_forecast:read',
                'assistant:manage_knowledge', 'assistant:configure_safety', 'audit_logs:read'
            ]
            role_manager, _ = Role.all_objects.update_or_create(
                tenant=tenant,
                name="MAINTENANCE_MANAGER",
                defaults={"description": "Trưởng Bộ Phận Quản Lý Bảo Trì & Kế Hoạch"}
            )
            role_manager.permissions.set([p for p in all_perms if p.id in manager_perm_ids])

            # Role: TECHNICIAN
            tech_perm_ids = [
                'work_order:read', 'work_order:execute', 'workforce:read',
                'asset:read', 'location:read', 'inventory:read'
            ]
            role_tech, _ = Role.all_objects.update_or_create(
                tenant=tenant,
                name="TECHNICIAN",
                defaults={"description": "Kỹ thuật viên hiện trường"}
            )
            role_tech.permissions.set([p for p in all_perms if p.id in tech_perm_ids])

            # Role: VIEWER
            viewer_perm_ids = ['asset:read', 'work_order:read', 'reports:read', 'workforce:read']
            role_viewer, _ = Role.all_objects.update_or_create(
                tenant=tenant,
                name="VIEWER",
                defaults={"description": "Người xem báo cáo & tra cứu tài sản"}
            )
            role_viewer.permissions.set([p for p in all_perms if p.id in viewer_perm_ids])

            log(" [2/14] Roles & Permissions: Configured 4 roles (TENANT_ADMIN, MAINTENANCE_MANAGER, TECHNICIAN, VIEWER)")

            # 3. Users Setup
            users_dict = {}

            # 3.1 Admin User
            u_admin, _ = User.all_objects.update_or_create(
                tenant=tenant,
                username="vanlam_admin",
                defaults={
                    "email": "admin@vanlam.vn",
                    "status": "ACTIVE",
                    "theme_color": "emerald",
                    "preferred_language": "vi",
                    "is_staff": True
                }
            )
            u_admin.set_password(VANLAM_DEMO_PASSWORD)
            u_admin.save()
            u_admin.roles.set([role_admin])
            users_dict['admin'] = u_admin

            # 3.2 Maintenance Manager
            u_mgr, _ = User.all_objects.update_or_create(
                tenant=tenant,
                username="vanlam_manager",
                defaults={
                    "email": "manager@vanlam.vn",
                    "status": "ACTIVE",
                    "theme_color": "emerald",
                    "preferred_language": "vi",
                    "is_staff": False
                }
            )
            u_mgr.set_password(VANLAM_DEMO_PASSWORD)
            u_mgr.save()
            u_mgr.roles.set([role_manager])
            users_dict['manager'] = u_mgr

            # 3.3 Technicians
            tech_specs = [
                ("vanlam_tech_an", "an.tran@vanlam.vn", "Trần Văn An"),
                ("vanlam_tech_binh", "binh.le@vanlam.vn", "Lê Thị Bình"),
                ("vanlam_tech_cuong", "cuong.hoang@vanlam.vn", "Hoàng Văn Cường"),
                ("vanlam_tech_dung", "dung.pham@vanlam.vn", "Phạm Tiến Dũng"),
            ]
            for uname, email, fullname in tech_specs:
                u, _ = User.all_objects.update_or_create(
                    tenant=tenant,
                    username=uname,
                    defaults={
                        "email": email,
                        "status": "ACTIVE",
                        "theme_color": "emerald",
                        "preferred_language": "vi",
                    }
                )
                u.set_password(VANLAM_DEMO_PASSWORD)
                u.save()
                u.roles.set([role_tech])
                users_dict[uname] = u

            # 3.4 Viewer User
            u_viewer, _ = User.all_objects.update_or_create(
                tenant=tenant,
                username="vanlam_viewer",
                defaults={
                    "email": "viewer@vanlam.vn",
                    "status": "ACTIVE",
                    "theme_color": "emerald",
                    "preferred_language": "vi",
                }
            )
            u_viewer.set_password(VANLAM_DEMO_PASSWORD)
            u_viewer.save()
            u_viewer.roles.set([role_viewer])
            users_dict['viewer'] = u_viewer

            log(f" [3/14] Users: Created {len(users_dict)} users with configured secure credentials")

            # 4. Workforce Skills Master Data
            skills_data = [
                ("MECHANICAL", "Cơ khí & Bảo dưỡng máy công nghiệp", "Cơ khí"),
                ("ELECTRICAL", "Kỹ thuật điện & Tủ phân phối hạ thế", "Điện"),
                ("HVAC", "Hệ thống thông gió & Làm lạnh công nghiệp", "Nhiệt lạnh"),
                ("HYDRAULIC", "Thủy lực & Khí nén áp lực cao", "Cơ khí"),
                ("AUTOMATION", "Tự động hóa & Lập trình PLC/SCADA", "Tự động hóa"),
                ("GENERAL", "Bảo trì cơ điện tổng hợp", "Tổng hợp"),
            ]
            skills_dict = {}
            for code, name, cat in skills_data:
                sk, _ = WorkforceSkill.all_objects.update_or_create(
                    tenant=tenant,
                    code=code,
                    defaults={"name": name, "category": cat, "is_active": True}
                )
                skills_dict[code] = sk

            # 5. Certification Types Master Data
            cert_types_data = [
                ("CERT_HIGH_VOLTAGE", "Chứng chỉ an toàn điện cao áp >1kV", "Cục Kỹ thuật An toàn Lao động", 12),
                ("CERT_SAFETY_L1", "An toàn lao động chung Nhóm 3 (Bậc 1)", "Trung tâm Huấn luyện An toàn", 24),
                ("CERT_SAFETY_L2", "An toàn lao động & Làm việc trên cao (Bậc 2)", "Trung tâm Huấn luyện An toàn", 24),
                ("CERT_PLC_EXPERT", "Chứng chỉ chuyên gia lập trình điều khiển PLC", "Học viện Tự động hóa", 36),
            ]
            cert_types_dict = {}
            for code, name, body, months in cert_types_data:
                ct, _ = CertificationType.all_objects.update_or_create(
                    tenant=tenant,
                    code=code,
                    defaults={"name": name, "issuing_body": body, "validity_months": months, "is_active": True}
                )
                cert_types_dict[code] = ct

            # User Certifications
            user_certs_spec = [
                ("vanlam_tech_an", "CERT_HIGH_VOLTAGE", "VL-HV-2026-01", today - timedelta(days=60), today + timedelta(days=305)),
                ("vanlam_tech_an", "CERT_SAFETY_L2", "VL-SF2-2026-01", today - timedelta(days=120), today + timedelta(days=610)),
                ("vanlam_tech_binh", "CERT_SAFETY_L1", "VL-SF1-2026-02", today - timedelta(days=90), today + timedelta(days=640)),
                ("vanlam_tech_binh", "CERT_SAFETY_L2", "VL-SF2-2026-02", today - timedelta(days=30), today + timedelta(days=700)),
                ("vanlam_tech_cuong", "CERT_PLC_EXPERT", "VL-PLC-2026-03", today - timedelta(days=150), today + timedelta(days=945)),
                ("vanlam_tech_cuong", "CERT_HIGH_VOLTAGE", "VL-HV-2026-03", today - timedelta(days=45), today + timedelta(days=320)),
                ("vanlam_tech_dung", "CERT_SAFETY_L1", "VL-SF1-2026-04", today - timedelta(days=180), today + timedelta(days=550)),
            ]
            for uname, c_code, num, iss_date, exp_date in user_certs_spec:
                u_obj = users_dict.get(uname)
                ct_obj = cert_types_dict.get(c_code)
                if u_obj and ct_obj:
                    UserCertification.all_objects.update_or_create(
                        tenant=tenant,
                        user=u_obj,
                        certification_type=ct_obj,
                        defaults={
                            "certificate_number": num,
                            "issued_date": iss_date,
                            "expiry_date": exp_date,
                            "status": "ACTIVE"
                        }
                    )

            # 6. Shift Templates & Schedules
            shifts_data = [
                ("SHIFT_1", "Ca 1 (Sáng)", "06:00:00", "14:00:00", False, "#0284c7"),
                ("SHIFT_2", "Ca 2 (Chiều)", "14:00:00", "22:00:00", False, "#d97706"),
                ("SHIFT_3", "Ca 3 (Đêm)", "22:00:00", "06:00:00", True, "#6366f1"),
                ("SHIFT_OFFICE", "Ca Hành chính", "08:00:00", "17:00:00", False, "#10b981"),
            ]
            shifts_dict = {}
            for code, name, st, et, is_on, color in shifts_data:
                sh, _ = ShiftTemplate.all_objects.update_or_create(
                    tenant=tenant,
                    code=code,
                    defaults={
                        "name": name,
                        "start_time": st,
                        "end_time": et,
                        "is_overnight": is_on,
                        "color_code": color,
                        "is_active": True
                    }
                )
                shifts_dict[code] = sh

            # Schedules for today and current week
            schedules_spec = [
                ("vanlam_tech_an", today, "SHIFT_1", "ZONE_A1"),
                ("vanlam_tech_binh", today, "SHIFT_1", "ZONE_PRESS"),
                ("vanlam_tech_cuong", today, "SHIFT_2", "ZONE_CLEAN"),
                ("vanlam_tech_dung", today, "SHIFT_2", "ZONE_A1"),
            ]
            for uname, wdate, sh_code, dzone in schedules_spec:
                u_obj = users_dict.get(uname)
                sh_obj = shifts_dict.get(sh_code)
                if u_obj and sh_obj:
                    TechnicianSchedule.all_objects.update_or_create(
                        tenant=tenant,
                        user=u_obj,
                        work_date=wdate,
                        defaults={
                            "shift_template": sh_obj,
                            "status": "ON_DUTY",
                            "duty_zone_id": dzone,
                            "notes": f"Lịch trực chính thức ca {sh_obj.name}"
                        }
                    )

            # Biometric Profiles
            # 128-dim unit embedding
            unit_val = 1.0 / (128.0 ** 0.5)
            mock_embedding = [round(unit_val, 6)] * 128
            for uname in ["vanlam_tech_an", "vanlam_tech_binh", "vanlam_tech_cuong", "vanlam_tech_dung"]:
                u_obj = users_dict.get(uname)
                if u_obj:
                    BiometricProfile.all_objects.update_or_create(
                        tenant=tenant,
                        user=u_obj,
                        defaults={
                            "face_embedding": mock_embedding,
                            "is_active": True
                        }
                    )

            log(" [4/14] Workforce: 6 Skills, 4 Cert Types, 7 Certifications, 4 Shift Templates, 4 Schedules, 4 Biometric Profiles")

            # 7. Locations & Floorplans (2-Tier Hierarchy)
            # 7.1 Floorplan Parents (zone_type='FLOORPLAN')
            fp_main, _ = Location.all_objects.update_or_create(
                tenant=tenant,
                code="FP_VL_01",
                defaults={
                    "name": "Mặt Bằng Tầng 1 - Khu Gia Công & Lắp Ráp",
                    "zone_type": "FLOORPLAN",
                    "location_type": "FLOOR",
                    "floor_level": 1,
                    "center_x": 50.0,
                    "center_y": 50.0,
                    "pixel_to_meter_ratio": 10.0,
                    "floorplan_image": "/static/img/hero.png",
                    "description": "Sơ đồ mặt bằng tổng thể Tầng 1: Phân xưởng cơ khí, phòng sạch và kho trung tâm",
                    "is_active": True
                }
            )
            fp_upper, _ = Location.all_objects.update_or_create(
                tenant=tenant,
                code="FP_VL_02",
                defaults={
                    "name": "Mặt Bằng Tầng 2 - Phân Xưởng Dập Thủy Lực",
                    "zone_type": "FLOORPLAN",
                    "location_type": "FLOOR",
                    "floor_level": 2,
                    "center_x": 50.0,
                    "center_y": 50.0,
                    "pixel_to_meter_ratio": 10.0,
                    "floorplan_image": "/static/img/hero.png",
                    "description": "Sơ đồ mặt bằng Tầng 2: Khu vực máy dập hạng nặng và trạm thủy lực áp cao",
                    "is_active": True
                }
            )

            # 7.2 Sub-Zones
            zones_spec = [
                ("ZONE_A1", "Phân Xưởng Cơ Khí Chế Tạo A1", "STANDARD", "ROOM", fp_main, 1, 30.0, 40.0, "Khu vực máy tiện, phay CNC và gia công chính xác"),
                ("ZONE_PRESS", "Phân Xưởng Dập & Nén Thủy Lực", "PRODUCTION", "ROOM", fp_upper, 2, 55.0, 60.0, "Khu vực máy dập Komatsu 500T và trạm bơm thủy lực Denison"),
                ("ZONE_CLEAN", "Phòng Sạch & Vi Điện Tử ISO-6", "CLEANROOM", "ROOM", fp_main, 1, 85.0, 25.0, "Phòng vi sinh kiểm soát nhiệt độ, độ ẩm và bụi vi mô"),
                ("ZONE_WAREHOUSE", "Kho Vật Tư & Phụ Tùng Trung Tâm", "WAREHOUSE", "WAREHOUSE", fp_main, 1, 15.0, 80.0, "Kho lưu trữ vòng bi, phớt dầu, van thủy lực và cảm biến đo kiểm"),
                ("ZONE_STAIRS", "Lối Cầu Thang Chuyển Tầng 1-2", "STAIRS", "ROOM", fp_main, 1, 50.0, 50.0, "Hành lang kết nối chuyển tầng cho kỹ thuật viên và vận chuyển linh kiện"),
            ]
            zones_dict = {}
            for code, name, ztype, ltype, p_fp, flevel, cx, cy, desc in zones_spec:
                z, _ = Location.all_objects.update_or_create(
                    tenant=tenant,
                    code=code,
                    defaults={
                        "name": name,
                        "zone_type": ztype,
                        "location_type": ltype,
                        "parent_id": str(p_fp.id),
                        "floor_level": flevel,
                        "center_x": cx,
                        "center_y": cy,
                        "description": desc,
                        "is_active": True
                    }
                )
                zones_dict[code] = z

            # Update TechnicianProfiles with spatial coordinates & assigned floorplan
            tech_profiles_spec = [
                ("vanlam_tech_an", 30.0, 40.0, 1, fp_main, "ZONE_A1", 4, ["MECHANICAL", "ELECTRICAL", "HVAC"], ["CERT_HIGH_VOLTAGE", "CERT_SAFETY_L2"], 120.0),
                ("vanlam_tech_binh", 55.0, 60.0, 2, fp_upper, "ZONE_PRESS", 3, ["MECHANICAL", "HYDRAULIC"], ["CERT_SAFETY_L1", "CERT_SAFETY_L2"], 98.0),
                ("vanlam_tech_cuong", 85.0, 25.0, 1, fp_main, "ZONE_CLEAN", 4, ["AUTOMATION", "ELECTRICAL"], ["CERT_PLC_EXPERT", "CERT_HIGH_VOLTAGE"], 115.0),
                ("vanlam_tech_dung", 35.0, 45.0, 1, fp_main, "ZONE_A1", 2, ["GENERAL", "MECHANICAL"], ["CERT_SAFETY_L1"], 85.0),
            ]
            for uname, cx, cy, fl, fp_obj, zid, sk_lvl, sk_list, c_list, mhours in tech_profiles_spec:
                u_obj = users_dict.get(uname)
                if u_obj:
                    TechnicianProfile.all_objects.update_or_create(
                        tenant=tenant,
                        user=u_obj,
                        defaults={
                            "coords_x": cx,
                            "coords_y": cy,
                            "floor_level": fl,
                            "floorplan": fp_obj,
                            "zone_id": zid,
                            "skill_level": sk_lvl,
                            "skills": sk_list,
                            "certifications": c_list,
                            "monthly_accumulated_hours": Decimal(str(mhours)),
                            "is_on_duty": True,
                            "availability_status": "AVAILABLE",
                            "shift_end_time": now + timedelta(hours=6)
                        }
                    )

            log(" [5/14] Locations: 2 Floorplans (Tầng 1 & 2), 5 Functional Zones, 4 Spatial Technician Profiles")

            # 8. Asset Categories & Hierarchy Templates
            categories_data = [
                ("Máy Tiện Phay CNC & Cơ Khí", "Trung tâm gia công phay tiện CNC chính xác cao"),
                ("Máy Dập Thủy Lực & Nén Khí", "Máy ép dập thủy lực công nghiệp tải trọng lớn"),
                ("Robot Hàn & Cánh Tay Đòn Tự Động", "Robot công nghiệp 6 trục tự động hóa dây chuyền"),
                ("Hệ Thống Trợ Lực HVAC & Bơm Áp Lực", "Hệ thống làm mát, cấp gió sạch và trạm bơm thủy lực"),
                ("Dây Chuyền Đóng Gói & Băng Tải", "Băng tải phân loại và đóng bao bì tự động"),
            ]
            cat_dict = {}
            for cname, cdesc in categories_data:
                cat, _ = AssetCategory.all_objects.update_or_create(
                    tenant=tenant,
                    name=cname,
                    defaults={"description": cdesc, "is_active": True}
                )
                cat_dict[cname] = cat

            hier_tpl, _ = HierarchyTemplate.all_objects.update_or_create(
                tenant=tenant,
                name="Nhà Máy -> Phân Xưởng -> Dây Chuyền -> Cụm Thiết Bị",
                defaults={"description": "Cấu trúc cây phân cấp quản lý tài sản 4 cấp tiêu chuẩn", "is_active": True}
            )

            # 9. Tools & Tool Instances
            tools_data = [
                ("TOOL_THERMAL_CAM", "Camera Nhiệt Fluke Ti480 Pro", 2),
                ("TOOL_LASER_ALIGN", "Máy Cân Tâm Trục Laser Easy-Laser XT770", 2),
                ("TOOL_INSULATION_TESTER", "Đồng Hồ Đo Điện Trở Cách Điện Cao Thế 10kV", 2),
                ("TOOL_VIB_ANALYZER", "Máy Phân Tích Rung Động SKF Microlog Analyzer GX", 3),
            ]
            tools_dict = {}
            for tcode, tname, qty in tools_data:
                t, _ = Tool.all_objects.update_or_create(
                    tenant=tenant,
                    code=tcode,
                    defaults={
                        "name": tname,
                        "location": zones_dict.get("ZONE_WAREHOUSE"),
                        "available_quantity": qty,
                        "is_active": True
                    }
                )
                tools_dict[tcode] = t

            # Tool Instances with serials and active calibrations
            tool_instances_spec = [
                ("TOOL_THERMAL_CAM", "SN-VL-FLK-01", "TAG-VL-TC-01", today - timedelta(days=20), today + timedelta(days=345), "PASSED", "AVAILABLE"),
                ("TOOL_THERMAL_CAM", "SN-VL-FLK-02", "TAG-VL-TC-02", today - timedelta(days=50), today + timedelta(days=315), "PASSED", "AVAILABLE"),
                ("TOOL_LASER_ALIGN", "SN-VL-EL-01", "TAG-VL-EL-01", today - timedelta(days=40), today + timedelta(days=325), "PASSED", "AVAILABLE"),
                ("TOOL_LASER_ALIGN", "SN-VL-EL-02", "TAG-VL-EL-02", today - timedelta(days=90), today + timedelta(days=275), "PASSED", "AVAILABLE"),
                ("TOOL_INSULATION_TESTER", "SN-VL-CH-01", "TAG-VL-IT-01", today - timedelta(days=15), today + timedelta(days=350), "PASSED", "AVAILABLE"),
                ("TOOL_INSULATION_TESTER", "SN-VL-CH-02", "TAG-VL-IT-02", today - timedelta(days=60), today + timedelta(days=305), "PASSED", "AVAILABLE"),
                ("TOOL_VIB_ANALYZER", "SN-VL-SKF-01", "TAG-VL-VA-01", today - timedelta(days=30), today + timedelta(days=335), "PASSED", "AVAILABLE"),
                ("TOOL_VIB_ANALYZER", "SN-VL-SKF-02", "TAG-VL-VA-02", today - timedelta(days=70), today + timedelta(days=295), "PASSED", "AVAILABLE"),
                ("TOOL_VIB_ANALYZER", "SN-VL-SKF-03", "TAG-VL-VA-03", today - timedelta(days=10), today + timedelta(days=355), "PASSED", "AVAILABLE"),
            ]
            for tcode, sn, tag, cal_d, due_d, insp_st, inst_st in tool_instances_spec:
                p_tool = tools_dict.get(tcode)
                if p_tool:
                    ToolInstance.all_objects.update_or_create(
                        tenant=tenant,
                        tool=p_tool,
                        serial_number=sn,
                        defaults={
                            "asset_tag": tag,
                            "calibration_date": cal_d,
                            "calibration_due_date": due_d,
                            "inspection_status": insp_st,
                            "status": inst_st,
                            "notes": "Kiểm định định kỳ đạt chuẩn chất lượng"
                        }
                    )

            # 10. Spare Parts & Stock Transactions
            parts_data = [
                ("SP_BEARING_SKF_6208", "Vòng Bi Cầu SKF 6208-2Z", "PN-SKF-6208", Decimal("350000"), Decimal("30.00"), Decimal("5.00")),
                ("SP_OIL_SEAL_VITON", "Phớt Chặn Dầu Viton 45x65x10", "PN-VT-456510", Decimal("120000"), Decimal("50.00"), Decimal("10.00")),
                ("SP_HYDRAULIC_VALVE_REX", "Van Điều Áp Thủy Lực Rexroth 350 Bar", "PN-REX-DBDS10", Decimal("4500000"), Decimal("8.00"), Decimal("2.00")),
                ("SP_PLC_MODULE_S71200", "Module CPU PLC Siemens S7-1200 1214C", "PN-SIE-6ES7214", Decimal("8200000"), Decimal("5.00"), Decimal("1.00")),
                ("SP_VIB_SENSOR_IEPE", "Cảm Biến Rung Gia Tốc IEPE 100mV/g", "PN-IEPE-100", Decimal("2100000"), Decimal("15.00"), Decimal("3.00")),
                ("SP_TIMING_BELT_OPT", "Dây Curoa Răng Optibelt HTD 8M-1200", "PN-OPT-8M1200", Decimal("280000"), Decimal("40.00"), Decimal("8.00")),
            ]
            parts_dict = {}
            for code, pname, pnum, cost, qty, min_lvl in parts_data:
                sp, _ = SparePart.all_objects.update_or_create(
                    tenant=tenant,
                    part_number=pnum,
                    defaults={
                        "name": pname,
                        "description": f"Phụ tùng thay thế tiêu chuẩn {pname}",
                        "location": zones_dict.get("ZONE_WAREHOUSE"),
                        "unit_cost": cost,
                        "quantity_in_stock": qty,
                        "min_stock_level": min_lvl,
                        "lead_time_days": 5
                    }
                )
                parts_dict[code] = sp

                # Create initial Receipt StockTransaction
                StockTransaction.all_objects.update_or_create(
                    tenant=tenant,
                    spare_part=sp,
                    transaction_type="RECEIPT",
                    issue_date=now - timedelta(days=45),
                    defaults={
                        "quantity": qty,
                        "unit_price": cost,
                        "total_amount": qty * cost,
                        "cost_center_snapshot": "Kho Phụ Tùng Trung Tâm Vân Lam"
                    }
                )

            log(" [6/14] Assets Core: 5 Categories, 4 Specialized Tools (9 Instances), 6 Spare Parts (Stock Transactions)")

            # 11. Assets Master Data
            assets_spec = [
                {
                    "code": "ASSET_CNC_MAZAK",
                    "name": "Máy Phay CNC Mazak VCN-530C",
                    "category": cat_dict.get("Máy Tiện Phay CNC & Cơ Khí"),
                    "location": zones_dict.get("ZONE_A1"),
                    "serial": "SN-MZK-2026-01",
                    "model": "Mazak VCN-530C",
                    "mfr": "Yamazaki Mazak Corp",
                    "qr": "QR-VL-CNC-001",
                    "purchase_date": today - timedelta(days=400),
                    "purchase_cost": Decimal("1850000000"),
                    "value": Decimal("1850000000"),
                    "salvage_value": Decimal("185000000"),
                    "useful_life_years": 10,
                    "status": "OPERATIONAL",
                    "coords_x": 32.0, "coords_y": 42.0, "floor_level": 1, "zone_id": "ZONE_A1",
                    "primary_spare_part": parts_dict.get("SP_BEARING_SKF_6208"),
                    "rul_risk_level": "HEALTHY",
                    "current_rul_days": 180.0,
                    "current_rul_calendar_days": 195.0,
                    "rul_confidence_lower": 165.0,
                    "rul_confidence_upper": 195.0,
                },
                {
                    "code": "ASSET_PRESS_500T",
                    "name": "Máy Dập Thủy Lực Komatsu 500T",
                    "category": cat_dict.get("Máy Dập Thủy Lực & Nén Khí"),
                    "location": zones_dict.get("ZONE_PRESS"),
                    "serial": "SN-KMT-2026-02",
                    "model": "Komatsu OBS-500",
                    "mfr": "Komatsu Ltd",
                    "qr": "QR-VL-PRS-001",
                    "purchase_date": today - timedelta(days=600),
                    "purchase_cost": Decimal("3200000000"),
                    "value": Decimal("3200000000"),
                    "salvage_value": Decimal("320000000"),
                    "useful_life_years": 12,
                    "status": "OPERATIONAL",
                    "coords_x": 58.0, "coords_y": 62.0, "floor_level": 2, "zone_id": "ZONE_PRESS",
                    "primary_spare_part": parts_dict.get("SP_HYDRAULIC_VALVE_REX"),
                    "rul_risk_level": "WARNING",
                    "current_rul_days": 45.0,
                    "current_rul_calendar_days": 48.0,
                    "rul_confidence_lower": 38.0,
                    "rul_confidence_upper": 52.0,
                },
                {
                    "code": "ASSET_ROBOT_ABB",
                    "name": "Robot Hàn Tự Động ABB IRB-2600",
                    "category": cat_dict.get("Robot Hàn & Cánh Tay Đòn Tự Động"),
                    "location": zones_dict.get("ZONE_A1"),
                    "serial": "SN-ABB-2026-03",
                    "model": "IRB-2600-20/1.65",
                    "mfr": "ABB Robotics",
                    "qr": "QR-VL-ROB-001",
                    "purchase_date": today - timedelta(days=300),
                    "purchase_cost": Decimal("950000000"),
                    "value": Decimal("950000000"),
                    "salvage_value": Decimal("95000000"),
                    "useful_life_years": 8,
                    "status": "OPERATIONAL",
                    "coords_x": 38.0, "coords_y": 48.0, "floor_level": 1, "zone_id": "ZONE_A1",
                    "primary_spare_part": parts_dict.get("SP_PLC_MODULE_S71200"),
                    "rul_risk_level": "HEALTHY",
                    "current_rul_days": 210.0,
                    "current_rul_calendar_days": 225.0,
                    "rul_confidence_lower": 195.0,
                    "rul_confidence_upper": 225.0,
                },
                {
                    "code": "ASSET_CLEANROOM_AHU",
                    "name": "Hệ Thống Lọc Khí & Cấp Gió AHU ISO-6",
                    "category": cat_dict.get("Hệ Thống Trợ Lực HVAC & Bơm Áp Lực"),
                    "location": zones_dict.get("ZONE_CLEAN"),
                    "serial": "SN-AHU-2026-04",
                    "model": "Trane Climate-06",
                    "mfr": "Trane Technologies",
                    "qr": "QR-VL-AHU-001",
                    "purchase_date": today - timedelta(days=250),
                    "purchase_cost": Decimal("680000000"),
                    "value": Decimal("680000000"),
                    "salvage_value": Decimal("68000000"),
                    "useful_life_years": 7,
                    "status": "OPERATIONAL",
                    "coords_x": 88.0, "coords_y": 28.0, "floor_level": 1, "zone_id": "ZONE_CLEAN",
                    "primary_spare_part": parts_dict.get("SP_TIMING_BELT_OPT"),
                    "rul_risk_level": "HEALTHY",
                    "current_rul_days": 150.0,
                    "current_rul_calendar_days": 160.0,
                    "rul_confidence_lower": 135.0,
                    "rul_confidence_upper": 165.0,
                },
                {
                    "code": "ASSET_PUMP_STATION",
                    "name": "Trạm Bơm Thủy Lực Áp Cao Denison 350 Bar",
                    "category": cat_dict.get("Hệ Thống Trợ Lực HVAC & Bơm Áp Lực"),
                    "location": zones_dict.get("ZONE_PRESS"),
                    "serial": "SN-DNS-2026-05",
                    "model": "Denison Gold Cup P6",
                    "mfr": "Parker Hannifin",
                    "qr": "QR-VL-PMP-001",
                    "purchase_date": today - timedelta(days=500),
                    "purchase_cost": Decimal("520000000"),
                    "value": Decimal("520000000"),
                    "salvage_value": Decimal("52000000"),
                    "useful_life_years": 6,
                    "status": "MAINTENANCE",
                    "coords_x": 62.0, "coords_y": 65.0, "floor_level": 2, "zone_id": "ZONE_PRESS",
                    "primary_spare_part": parts_dict.get("SP_OIL_SEAL_VITON"),
                    "rul_risk_level": "HIGH",
                    "current_rul_days": 18.0,
                    "current_rul_calendar_days": 20.0,
                    "rul_confidence_lower": 14.0,
                    "rul_confidence_upper": 22.0,
                },
                {
                    "code": "ASSET_LATHE_DMG",
                    "name": "Máy Tiện Cơ Khí Vạn Năng DMG Mori NLX 2500",
                    "category": cat_dict.get("Máy Tiện Phay CNC & Cơ Khí"),
                    "location": zones_dict.get("ZONE_A1"),
                    "serial": "SN-DMG-2026-06",
                    "model": "NLX 2500/700",
                    "mfr": "DMG MORI",
                    "qr": "QR-VL-LTH-001",
                    "purchase_date": today - timedelta(days=350),
                    "purchase_cost": Decimal("1450000000"),
                    "value": Decimal("1450000000"),
                    "salvage_value": Decimal("145000000"),
                    "useful_life_years": 10,
                    "status": "OPERATIONAL",
                    "coords_x": 25.0, "coords_y": 38.0, "floor_level": 1, "zone_id": "ZONE_A1",
                    "primary_spare_part": parts_dict.get("SP_BEARING_SKF_6208"),
                    "rul_risk_level": "HEALTHY",
                    "current_rul_days": 175.0,
                    "current_rul_calendar_days": 190.0,
                    "rul_confidence_lower": 160.0,
                    "rul_confidence_upper": 190.0,
                },
            ]

            assets_dict = {}
            for aspec in assets_spec:
                ast, _ = Asset.all_objects.update_or_create(
                    tenant=tenant,
                    qr_code=aspec["qr"],
                    defaults={
                        "name": aspec["name"],
                        "category": aspec["category"],
                        "location": aspec["location"],
                        "hierarchy_template": hier_tpl,
                        "serial_number": aspec["serial"],
                        "model": aspec["model"],
                        "manufacturer": aspec["mfr"],
                        "purchase_date": aspec["purchase_date"],
                        "purchase_cost": aspec["purchase_cost"],
                        "value": aspec["value"],
                        "salvage_value": aspec["salvage_value"],
                        "useful_life_years": aspec["useful_life_years"],
                        "status": aspec["status"],
                        "coords_x": aspec["coords_x"],
                        "coords_y": aspec["coords_y"],
                        "floor_level": aspec["floor_level"],
                        "zone_id": aspec["zone_id"],
                        "primary_spare_part": aspec["primary_spare_part"],
                        "rul_risk_level": aspec["rul_risk_level"],
                        "current_rul_days": aspec["current_rul_days"],
                        "current_rul_calendar_days": aspec["current_rul_calendar_days"],
                        "rul_confidence_lower": aspec["rul_confidence_lower"],
                        "rul_confidence_upper": aspec["rul_confidence_upper"],
                        "last_rul_predicted_at": now - timedelta(hours=3),
                        "is_trackable": True,
                        "is_active": True
                    }
                )
                assets_dict[aspec["code"]] = ast

            # 12. Sensor Telemetry (Meter Readings), Anomaly Alerts & RUL Predictions
            total_readings = 0
            for acode, ast in assets_dict.items():
                is_noisy = (acode == "ASSET_PRESS_500T" or acode == "ASSET_PUMP_STATION")
                base_vib = 4.2 if is_noisy else 1.5
                base_temp = 55.0 if is_noisy else 38.0

                for day_offset in range(30, 0, -1):
                    r_date = now - timedelta(days=day_offset, hours=day_offset % 6)
                    # Simulated upward trend for press and pump
                    noise_factor = (30 - day_offset) * 0.05 if is_noisy else 0.0
                    vib_val = Decimal(str(round(base_vib + noise_factor + (day_offset % 3) * 0.1, 2)))
                    temp_val = round(base_temp + noise_factor * 2 + (day_offset % 4) * 0.5, 1)

                    mr = MeterReading.all_objects.create(
                        tenant=tenant,
                        asset=ast,
                        metric_code="VIBRATION",
                        reading_value=vib_val,
                        unit="mm/s",
                        reading_date=r_date,
                        ambient_temperature=temp_val,
                        load_factor=1.0,
                        shaft_rpm=1450.0,
                        machine_state="RUNNING",
                        measurement_phase="ROUTINE",
                        remarks="Đo tuần tra cảm biến gia tốc định kỳ"
                    )
                    total_readings += 1

                # Save official RUL Prediction record
                AssetRulPrediction.all_objects.create(
                    tenant=tenant,
                    asset=ast,
                    predicted_rul_op_days=ast.current_rul_days or 150.0,
                    predicted_rul_cal_days=ast.current_rul_calendar_days or 160.0,
                    confidence_lower=ast.rul_confidence_lower or 130.0,
                    confidence_upper=ast.rul_confidence_upper or 170.0,
                    std_deviation=4.5,
                    risk_level=ast.rul_risk_level,
                    trigger_source="WEEKLY_SCAN",
                    load_factor_average=1.0,
                    input_window_samples_count=30,
                    action_taken="CHECK_INVENTORY" if ast.rul_risk_level in ["WARNING", "HIGH"] else "NORMAL_MONITORING"
                )

            # Anomaly Alerts
            # Alert 1: Komatsu Press
            ast_press = assets_dict.get("ASSET_PRESS_500T")
            AssetAnomalyAlert.all_objects.create(
                tenant=tenant,
                asset=ast_press,
                metric_type="SINGLE_METRIC",
                metric_code="VIBRATION",
                current_value=4.85,
                z_score=2.85,
                anomaly_score=0.88,
                severity="WARNING",
                status="OPEN",
                occurrence_count=3,
                message="Độ rung trục chính vượt ngưỡng cảnh báo ISO 10816 Zone C (4.85 mm/s > 4.5 mm/s)"
            )

            # Alert 2: Denison Hydraulic Pump
            ast_pump = assets_dict.get("ASSET_PUMP_STATION")
            AssetAnomalyAlert.all_objects.create(
                tenant=tenant,
                asset=ast_pump,
                metric_type="SINGLE_METRIC",
                metric_code="VIBRATION",
                current_value=7.20,
                z_score=3.75,
                anomaly_score=0.96,
                severity="CRITICAL",
                status="OPEN",
                occurrence_count=5,
                message="Độ rung trạm bơm đạt mức nguy hiểm ISO 10816 Zone D (7.20 mm/s > 6.0 mm/s) - Nguy cơ kẹt piston"
            )

            log(f" [7/14] Telemetry & AI Analytics: {len(assets_dict)} Assets, {total_readings} Meter Readings, 2 Active Anomaly Alerts, 6 RUL Predictions")

            # 13. PM Plans & Assignments
            pm_plans_spec = [
                {
                    "code": "PM_CNC_MONTHLY",
                    "name": "Bảo Dưỡng Định Kỳ Hàng Tháng - Hệ Thống Bôi Trơn & Cân Tâm Máy CNC",
                    "trigger_type": "TIME",
                    "interval_value": Decimal("1.00"),
                    "interval_unit": "MONTHS",
                    "lead_time_days": 3,
                    "estimated_duration_minutes": 120,
                    "action": "MICRO_MAINTENANCE",
                    "assignee": users_dict.get("vanlam_tech_an"),
                    "asset": assets_dict.get("ASSET_CNC_MAZAK"),
                    "checklists": [
                        ("Kiểm tra mức dầu bôi trơn trục chính và bổ sung nếu thiếu", True, "PASS_FAIL"),
                        ("Đo kiểm độ rung trục chính bằng SKF Analyzer (RMS < 2.5 mm/s)", True, "NUMERIC"),
                        ("Vệ sinh lọc gió tủ điện điều khiển FANUC", False, "PASS_FAIL"),
                    ],
                    "materials": [
                        (parts_dict.get("SP_OIL_SEAL_VITON"), Decimal("2.00")),
                    ]
                },
                {
                    "code": "PM_PRESS_QUARTERLY",
                    "name": "Đại Tu Định Kỳ Quý - Cụm Thủy Lực & Van Điều Áp Máy Dập 500T",
                    "trigger_type": "TIME",
                    "interval_value": Decimal("3.00"),
                    "interval_unit": "MONTHS",
                    "lead_time_days": 7,
                    "estimated_duration_minutes": 240,
                    "action": "CORE_REPLACEMENT",
                    "assignee": users_dict.get("vanlam_tech_binh"),
                    "asset": assets_dict.get("ASSET_PRESS_500T"),
                    "checklists": [
                        ("Xả cặn và kiểm tra áp suất dầu 350 Bar", True, "NUMERIC"),
                        ("Thay thế cụm phớt Viton và lọc áp lực", True, "PASS_FAIL"),
                        ("Đo nghiệm thu độ rung sau thay thế", True, "NUMERIC"),
                    ],
                    "materials": [
                        (parts_dict.get("SP_HYDRAULIC_VALVE_REX"), Decimal("1.00")),
                        (parts_dict.get("SP_OIL_SEAL_VITON"), Decimal("4.00")),
                    ]
                },
                {
                    "code": "PM_ROBOT_BIWEEKLY",
                    "name": "Hiệu Chuẩn Cánh Tay Đòn & Cảm Biến Robot Hàn ABB",
                    "trigger_type": "TIME",
                    "interval_value": Decimal("2.00"),
                    "interval_unit": "WEEKS",
                    "lead_time_days": 2,
                    "estimated_duration_minutes": 90,
                    "action": "GENERAL",
                    "assignee": users_dict.get("vanlam_tech_cuong"),
                    "asset": assets_dict.get("ASSET_ROBOT_ABB"),
                    "checklists": [
                        ("Cân chỉnh tọa độ Zero các trục 1-6", True, "PASS_FAIL"),
                        ("Kiểm tra cáp tín hiệu Profinet và nguồn", True, "PASS_FAIL"),
                    ],
                    "materials": []
                },
                {
                    "code": "PM_AHU_MONTHLY",
                    "name": "Kiểm Tra Định Kỳ Hệ Thống Lọc Khí & Áp Suất Phòng Sạch AHU",
                    "trigger_type": "TIME",
                    "interval_value": Decimal("1.00"),
                    "interval_unit": "MONTHS",
                    "lead_time_days": 3,
                    "estimated_duration_minutes": 100,
                    "action": "GENERAL",
                    "assignee": users_dict.get("vanlam_tech_dung"),
                    "asset": assets_dict.get("ASSET_CLEANROOM_AHU"),
                    "checklists": [
                        ("Kiểm tra độ chênh áp qua màng lọc HEPA", True, "NUMERIC"),
                        ("Kiểm tra độ căng dây curoa quạt hút", True, "PASS_FAIL"),
                    ],
                    "materials": [
                        (parts_dict.get("SP_TIMING_BELT_OPT"), Decimal("1.00")),
                    ]
                }
            ]

            for pmspec in pm_plans_spec:
                pm_plan, _ = PmPlan.all_objects.update_or_create(
                    tenant=tenant,
                    name=pmspec["name"],
                    defaults={
                        "description": f"Kế hoạch bảo trì phòng ngừa định kỳ {pmspec['name']}",
                        "trigger_type": pmspec["trigger_type"],
                        "interval_value": pmspec["interval_value"],
                        "interval_unit": pmspec["interval_unit"],
                        "lead_time_days": pmspec["lead_time_days"],
                        "estimated_duration_minutes": pmspec["estimated_duration_minutes"],
                        "maintenance_action": pmspec["action"],
                        "assignee": pmspec["assignee"],
                        "is_active": True
                    }
                )

                # Checklists
                for c_name, is_m, inp_type in pmspec["checklists"]:
                    PmPlanChecklistItem.all_objects.update_or_create(
                        tenant=tenant,
                        pm_plan=pm_plan,
                        item_name=c_name,
                        defaults={
                            "is_mandatory": is_m,
                            "input_type": inp_type,
                            "expected_value": "PASSED" if inp_type == "PASS_FAIL" else "< 3.0"
                        }
                    )

                # Materials
                for sp_obj, qty in pmspec["materials"]:
                    if sp_obj:
                        PmPlanMaterial.all_objects.update_or_create(
                            tenant=tenant,
                            pm_plan=pm_plan,
                            spare_part=sp_obj,
                            defaults={"quantity": qty}
                        )

                # Assignment
                if pmspec["asset"]:
                    PmPlanAssignment.all_objects.update_or_create(
                        tenant=tenant,
                        pm_plan=pm_plan,
                        asset=pmspec["asset"],
                        defaults={
                            "status": "ACTIVE",
                            "last_triggered_at": now - timedelta(days=15)
                        }
                    )

            log(" [8/14] PM Management: 4 Active PM Plans, 9 Checklist Items, 3 Plan Materials, 4 Asset Assignments")

            # 14. Work Orders (Covering diverse flows: Hungarian, GA, TSP, HSM, Attendance)
            work_orders_spec = [
                # WO 1: Ready for Hungarian / GA (Unassigned, CREATED)
                {
                    "title": "Đo kiểm và cân tâm động cơ trục chính Máy Phay CNC Mazak",
                    "asset": assets_dict.get("ASSET_CNC_MAZAK"),
                    "type": "PREVENTIVE",
                    "priority": "HIGH",
                    "status": "CREATED",
                    "required_skill": "ELECTRICAL",
                    "min_skill_level": 3,
                    "required_certification": "CERT_HIGH_VOLTAGE",
                    "required_tools": ["TOOL_LASER_ALIGN", "TOOL_VIB_ANALYZER"],
                    "location": zones_dict.get("ZONE_A1"),
                    "coords_x": 32.0, "coords_y": 42.0, "floor_level": 1, "zone_id": "ZONE_A1",
                    "estimated_duration_minutes": 120,
                    "deadline": now + timedelta(days=2),
                    "checklists": [
                        ("Cách ly nguồn điện 3 pha và gắn thẻ LOTO", True),
                        ("Gá đặt thiết bị cân tâm laser Easy-Laser", True),
                        ("Cân chỉnh góc lệch khớp nối < 0.05mm", True),
                    ]
                },
                # WO 2: Ready for Hungarian / GA (Unassigned, CREATED, URGENT)
                {
                    "title": "Bảo dưỡng van điều áp và kiểm tra đường ống thủy lực Máy Dập 500T",
                    "asset": assets_dict.get("ASSET_PRESS_500T"),
                    "type": "CORRECTIVE",
                    "priority": "URGENT",
                    "status": "CREATED",
                    "required_skill": "HYDRAULIC",
                    "min_skill_level": 3,
                    "required_certification": "CERT_SAFETY_L1",
                    "required_tools": ["TOOL_THERMAL_CAM"],
                    "location": zones_dict.get("ZONE_PRESS"),
                    "coords_x": 58.0, "coords_y": 62.0, "floor_level": 2, "zone_id": "ZONE_PRESS",
                    "estimated_duration_minutes": 180,
                    "deadline": now + timedelta(days=1),
                    "checklists": [
                        ("Giảm áp lực toàn bộ hệ thống về 0 Bar", True),
                        ("Quét nhiệt phát hiện điểm nghẽn bằng Camera Nhiệt", True),
                        ("Xiết chặt bu-lông mặt bích van điều áp", False),
                    ]
                },
                # WO 3: Automation / PLC Expert
                {
                    "title": "Hiệu chỉnh chương trình PLC và vị trí hàn Robot ABB",
                    "asset": assets_dict.get("ASSET_ROBOT_ABB"),
                    "type": "CORRECTIVE",
                    "priority": "MEDIUM",
                    "status": "CREATED",
                    "required_skill": "AUTOMATION",
                    "min_skill_level": 4,
                    "required_certification": "CERT_PLC_EXPERT",
                    "required_tools": [],
                    "location": zones_dict.get("ZONE_A1"),
                    "coords_x": 38.0, "coords_y": 48.0, "floor_level": 1, "zone_id": "ZONE_A1",
                    "estimated_duration_minutes": 90,
                    "deadline": now + timedelta(days=3),
                    "checklists": [
                        ("Sao lưu chương trình PLC Siemens S7-1200", True),
                        ("Test chạy từng bước (Inching) đường hàn mẫu", True),
                    ]
                },
                # WO 4: HVAC & Cleanroom
                {
                    "title": "Thay lọc HEPA và cân chỉnh lưu lượng gió Phòng Sạch ISO-6",
                    "asset": assets_dict.get("ASSET_CLEANROOM_AHU"),
                    "type": "PREVENTIVE",
                    "priority": "MEDIUM",
                    "status": "CREATED",
                    "required_skill": "HVAC",
                    "min_skill_level": 2,
                    "required_certification": "CERT_SAFETY_L1",
                    "required_tools": [],
                    "location": zones_dict.get("ZONE_CLEAN"),
                    "coords_x": 88.0, "coords_y": 28.0, "floor_level": 1, "zone_id": "ZONE_CLEAN",
                    "estimated_duration_minutes": 100,
                    "deadline": now + timedelta(days=3),
                    "checklists": [
                        ("Đo vận tốc gió cửa hút và cửa xả", True),
                        ("Kiểm tra áp suất chênh lệch phòng sạch", True),
                    ]
                },
                # WO 5: Historical COMPLETED (with labor, materials, costs, attendance, HSM transition)
                {
                    "title": "Thay thế vòng bi và phớt trục bơm trạm Denison",
                    "asset": assets_dict.get("ASSET_PUMP_STATION"),
                    "type": "CORRECTIVE",
                    "priority": "URGENT",
                    "status": "COMPLETED",
                    "assigned_to": users_dict.get("vanlam_tech_an"),
                    "assigned_at": now - timedelta(days=5),
                    "actual_start_time": now - timedelta(days=5, hours=-1),
                    "completed_at": now - timedelta(days=5, hours=-5),
                    "actual_duration_minutes": 240,
                    "actual_cost": Decimal("4800000"),
                    "location": zones_dict.get("ZONE_PRESS"),
                    "coords_x": 62.0, "coords_y": 65.0, "floor_level": 2, "zone_id": "ZONE_PRESS",
                    "deadline": now - timedelta(days=4),
                    "checklists": [
                        ("Tháo cụm đầu bơm và kiểm tra rãnh phớt", True, True),
                        ("Ép vòng bi mới SKF 6208 vào ngõng trục", True, True),
                        ("Đo độ rung nghiệm thu sau khi thay thế", True, True),
                    ],
                    "materials": [
                        (parts_dict.get("SP_BEARING_SKF_6208"), Decimal("2.00"), Decimal("700000")),
                        (parts_dict.get("SP_OIL_SEAL_VITON"), Decimal("2.00"), Decimal("240000")),
                    ],
                    "labor": [
                        (users_dict.get("vanlam_tech_an"), Decimal("4.00"), Decimal("250000")),
                    ],
                    "attendance": True,
                    "hsm_transition": True
                },
                # WO 6: IN_PROGRESS
                {
                    "title": "Kiểm tra định kỳ rò rỉ khí nén và bảo dưỡng van điều áp",
                    "asset": assets_dict.get("ASSET_LATHE_DMG"),
                    "type": "PREVENTIVE",
                    "priority": "LOW",
                    "status": "IN_PROGRESS",
                    "assigned_to": users_dict.get("vanlam_tech_dung"),
                    "assigned_at": now - timedelta(hours=3),
                    "actual_start_time": now - timedelta(hours=2),
                    "location": zones_dict.get("ZONE_A1"),
                    "coords_x": 25.0, "coords_y": 38.0, "floor_level": 1, "zone_id": "ZONE_A1",
                    "estimated_duration_minutes": 120,
                    "deadline": now + timedelta(days=1),
                    "checklists": [
                        ("Quét bọt xà phòng kiểm tra cút nối khí nén", True, True),
                        ("Kiểm tra bộ tách nước khí nén tự động", False, False),
                    ]
                },
                # WO 7: ASSIGNED
                {
                    "title": "Khảo sát và siết ốc bệ đỡ Máy Tiện Vạn Năng DMG Mori",
                    "asset": assets_dict.get("ASSET_LATHE_DMG"),
                    "type": "CORRECTIVE",
                    "priority": "MEDIUM",
                    "status": "ASSIGNED",
                    "assigned_to": users_dict.get("vanlam_tech_binh"),
                    "assigned_at": now - timedelta(hours=1),
                    "location": zones_dict.get("ZONE_A1"),
                    "coords_x": 25.0, "coords_y": 38.0, "floor_level": 1, "zone_id": "ZONE_A1",
                    "estimated_duration_minutes": 60,
                    "deadline": now + timedelta(days=2),
                    "checklists": [
                        ("Dùng cờ lê lực kiểm tra lực siết bu-lông chân máy", True, False),
                    ]
                }
            ]

            seeded_wos = []
            for wspec in work_orders_spec:
                wo, _ = WorkOrder.all_objects.update_or_create(
                    tenant=tenant,
                    title=wspec["title"],
                    defaults={
                        "asset": wspec["asset"],
                        "type": wspec["type"],
                        "priority": wspec["priority"],
                        "status": wspec["status"],
                        "assigned_to": wspec.get("assigned_to"),
                        "assigned_at": wspec.get("assigned_at"),
                        "actual_start_time": wspec.get("actual_start_time"),
                        "completed_at": wspec.get("completed_at"),
                        "actual_duration_minutes": wspec.get("actual_duration_minutes"),
                        "estimated_duration_minutes": wspec.get("estimated_duration_minutes", 120),
                        "actual_cost": wspec.get("actual_cost"),
                        "required_skill": wspec.get("required_skill"),
                        "min_skill_level": wspec.get("min_skill_level", 1),
                        "required_certification": wspec.get("required_certification"),
                        "required_tools": wspec.get("required_tools", []),
                        "coords_x": wspec.get("coords_x"),
                        "coords_y": wspec.get("coords_y"),
                        "floor_level": wspec.get("floor_level", 1),
                        "zone_id": wspec.get("zone_id", ""),
                        "incident_location": wspec.get("location"),
                        "deadline": wspec.get("deadline", now + timedelta(days=2)),
                    }
                )
                seeded_wos.append(wo)

                # Checklists
                for item in wspec.get("checklists", []):
                    cname = item[0]
                    is_m = item[1]
                    is_done = item[2] if len(item) > 2 else False
                    WorkOrderChecklistItem.all_objects.update_or_create(
                        tenant=tenant,
                        work_order=wo,
                        item_name=cname,
                        defaults={
                            "is_mandatory": is_m,
                            "is_completed": is_done,
                            "input_type": "PASS_FAIL",
                            "expected_value": "PASSED"
                        }
                    )

                # Materials
                for sp_obj, mqty, mcost in wspec.get("materials", []):
                    if sp_obj:
                        WorkOrderMaterial.all_objects.update_or_create(
                            tenant=tenant,
                            work_order=wo,
                            spare_part=sp_obj,
                            defaults={"quantity": mqty, "actual_cost": mcost}
                        )

                # Labor Logs
                for u_tech, lhours, lrate in wspec.get("labor", []):
                    if u_tech:
                        LaborLog.all_objects.update_or_create(
                            tenant=tenant,
                            work_order=wo,
                            technician=u_tech,
                            work_date=today - timedelta(days=5),
                            defaults={
                                "hours_worked": lhours,
                                "hourly_rate": lrate,
                                "total_cost": lhours * lrate,
                                "cost_center_snapshot": "Phân Xưởng Dập Thủy Lực"
                            }
                        )

                # Cost Breakdown for completed WO
                if wspec.get("actual_cost"):
                    WorkOrderCost.all_objects.update_or_create(
                        tenant=tenant,
                        work_order=wo,
                        defaults={
                            "material_cost": Decimal("940000"),
                            "labor_cost": Decimal("1000000"),
                            "vendor_cost": Decimal("0.00"),
                            "gross_cost": Decimal("1940000"),
                            "net_cost": Decimal("1940000"),
                            "is_cost_frozen": True,
                            "cost_center_snapshot": "Phân Xưởng Dập Thủy Lực"
                        }
                    )

                # Attendance logs for completed WO
                if wspec.get("attendance") and wspec.get("assigned_to"):
                    AttendanceLog.all_objects.create(
                        tenant=tenant,
                        work_order=wo,
                        technician=wspec.get("assigned_to"),
                        verification_method="ESP32_UNIVERSAL_BEACON",
                        ble_beacon_id="e2c56db5-dffb-48d2-b060-d0f5a71096e0",
                        rssi_dbm=-62,
                        distance_meters=2.4,
                        similarity_score=0.94,
                        is_location_verified=True,
                        is_face_verified=True,
                        overall_compliance="PASSED",
                        gate_type="START_GATE"
                    )
                    AttendanceLog.all_objects.create(
                        tenant=tenant,
                        work_order=wo,
                        technician=wspec.get("assigned_to"),
                        verification_method="ESP32_UNIVERSAL_BEACON",
                        ble_beacon_id="e2c56db5-dffb-48d2-b060-d0f5a71096e0",
                        rssi_dbm=-65,
                        distance_meters=2.8,
                        similarity_score=0.92,
                        is_location_verified=True,
                        is_face_verified=True,
                        overall_compliance="PASSED",
                        gate_type="COMPLETE_GATE"
                    )

                # HSM Transition for completed WO
                if wspec.get("hsm_transition") and wspec.get("assigned_to"):
                    HsmStageTransition.all_objects.create(
                        tenant=tenant,
                        work_order=wo,
                        action_type="AI_EVALUATE",
                        severity_assigned="CRITICAL_OVERHAUL",
                        reason="Độ rung trạm bơm vượt ngưỡng 6.0 mm/s. Đề xuất quy trình đại tu thay phớt và vòng bi trục chính.",
                        performed_by=wspec.get("assigned_to"),
                        vibration_reading=6.8,
                        temperature_reading=58.5,
                        from_stage="DIAGNOSIS",
                        to_stage="TRIAL_ACCEPTANCE"
                    )

            # Tool Reservations linked to WO 1 & 2
            t_laser = tools_dict.get("TOOL_LASER_ALIGN")
            if t_laser and len(seeded_wos) > 0:
                ToolReservation.all_objects.update_or_create(
                    tenant=tenant,
                    tool=t_laser,
                    work_order=seeded_wos[0],
                    defaults={"reserved_quantity": 1, "status": "RESERVED"}
                )

            t_therm = tools_dict.get("TOOL_THERMAL_CAM")
            if t_therm and len(seeded_wos) > 1:
                ToolReservation.all_objects.update_or_create(
                    tenant=tenant,
                    tool=t_therm,
                    work_order=seeded_wos[1],
                    defaults={"reserved_quantity": 1, "status": "RESERVED"}
                )

            log(f" [9/14] Work Orders: Created {len(seeded_wos)} Work Orders (4 Unassigned for AI, 1 Completed, 1 In-Progress, 1 Assigned)")

            # 15. AI Knowledge Base & Chatbot Chunks
            if TechnicalDocument and DocumentChunk and CuratedQAKnowledge:
                doc_mazak, _ = TechnicalDocument.all_objects.update_or_create(
                    tenant=tenant,
                    title="Cẩm Nang Hướng Dẫn Vận Hành & Khắc Phục Lỗi Máy Phay CNC Mazak VCN-530C",
                    defaults={
                        "category": "OEM_MANUAL",
                        "applicable_model": "Mazak VCN-530C",
                        "applicable_year_start": 2020,
                        "applicable_year_end": 2030,
                        "file_path": "manuals/vanlam_mazak_vcn530c_manual.pdf",
                        "is_active": True
                    }
                )

                chunks_data = [
                    (
                        "Hướng dẫn xử lý sự cố lỗi quá tải động cơ trục chính (Spindle Overload Error 104)",
                        "Khi màn hình máy Mazak VCN-530C hiển thị lỗi 104 Spindle Overload: "
                        "1. Dừng cấp phôi ngay lập tức và nhấn phím RESET. "
                        "2. Kiểm tra tải trọng phoi cắt và độ mòn của dao phay. "
                        "3. Dùng Ampe kìm kiểm tra dòng điện cấp cho biến tần trục chính (không vượt quá 32A). "
                        "4. Kiểm tra hệ thống bơm dầu bôi trơn tuần hoàn trục chính."
                    ),
                    (
                        "Quy trình căn tâm trục máy CNC bằng thiết bị đo Laser Easy-Laser XT770",
                        "Quy trình căn chuẩn tâm trục máy gia công cơ khí chính xác: "
                        "1. Gắn đầu phát và đầu thu laser lên 2 đầu khớp nối trục động cơ và trục chính. "
                        "2. Nhập khoảng cách 3 điểm vào máy Easy-Laser XT770. "
                        "3. Quay trục theo 3 góc 9h, 12h, 3h (Phương pháp 9-12-3). "
                        "4. Điều chỉnh chêm căn (shims) dưới chân máy đến khi độ lệch góc và độ lệch song song đạt < 0.05 mm."
                    ),
                    (
                        "Tiêu chuẩn độ rung đánh giá tình trạng cơ khí theo ISO 10816-3",
                        "Phân loại độ rung rung chấn vận tốc hiệu dụng (RMS velocity 10-1000 Hz) theo chuẩn ISO 10816-3 cho máy cơ điện nhóm 1: "
                        "- Vùng A (Tốt): RMS < 1.4 mm/s. "
                        "- Vùng B (Cho phép): 1.4 mm/s <= RMS < 2.8 mm/s. "
                        "- Vùng C (Cảnh báo - Lập kế hoạch bảo trì): 2.8 mm/s <= RMS < 4.5 mm/s. "
                        "- Vùng D (Nguy hiểm - Dừng máy khẩn cấp): RMS >= 4.5 mm/s."
                    )
                ]

                zero_emb = [0.0] * 384
                for section_title, content_text in chunks_data:
                    DocumentChunk.all_objects.update_or_create(
                        tenant=tenant,
                        document=doc_mazak,
                        section_title=section_title,
                        defaults={
                            "content": content_text,
                            "parent_content": content_text,
                            "source_type": "OEM_MANUAL",
                            "embedding": zero_emb,
                            "is_active": True
                        }
                    )

                qa_items = [
                    (
                        "Làm thế nào để xử lý sự cố quá nhiệt động cơ bơm thủy lực Denison 350 Bar?",
                        "Kiểm tra mức dầu thủy lực trong bể chứa, vệ sinh dàn giải nhiệt dầu, đo dòng tải động cơ 3 pha và kiểm tra rơ-le nhiệt F3. Nếu nhiệt độ dầu vượt 65°C cần dừng máy ngay lập tức để tránh biến chất dầu thủy lực và hỏng phớt Viton.",
                        "Denison Gold Cup P6"
                    ),
                    (
                        "Quy trình đo kiểm rung chấn và nghiệm thu máy dập Komatsu 500T sau bảo dưỡng?",
                        "Gắn cảm biến gia tốc SKF tại 3 phương: Ngang (H), Dọc (V), Dọc trục (A) trên bệ đỡ trục khuỷu. Vận hành máy ở tốc độ 45 nhịp/phút. Đo vận tốc rung RMS theo chuẩn ISO 10816-3; giá trị đo được phải < 4.5 mm/s mới đủ điều kiện nghiệm thu.",
                        "Komatsu OBS-500"
                    )
                ]
                for q, a, model_app in qa_items:
                    CuratedQAKnowledge.all_objects.update_or_create(
                        tenant=tenant,
                        question_pattern=q,
                        defaults={
                            "gold_answer": a,
                            "applicable_model": model_app,
                            "category": "MAINTENANCE_PROCEDURE"
                        }
                    )

                log(" [10/14] AI Knowledge: 1 Technical Document, 3 Chunks, 2 Curated Q&A pairs for RAG Chatbot")

            # 16. Financial & Budget Forecasting Master Data
            TenantFinancialSetting.all_objects.update_or_create(
                tenant=tenant,
                defaults={
                    "default_labor_hourly_rate": Decimal("250000"),
                    "default_inflation_rate": Decimal("4.50"),
                    "default_contingency_rate": Decimal("10.00"),
                    "critical_spare_part_ratio": Decimal("1.25"),
                    "currency": "VND"
                }
            )

            # Budget Forecast for current and upcoming quarter
            BudgetForecast.all_objects.filter(tenant=tenant).delete()
            BudgetForecast.all_objects.create(
                tenant=tenant,
                forecast_period="2026-Q4",
                cost_center_snapshot=None,
                forecast_method="HYBRID_PM_CM_QRF",
                approved_budget=Decimal("150000000"),
                planned_pm_budget=Decimal("65000000"),
                predicted_cm_median=Decimal("48000000"),
                predicted_cm_lower_p10=Decimal("35000000"),
                predicted_cm_upper_p90=Decimal("68000000"),
                contingency_buffer=Decimal("15000000"),
                total_forecast_median=Decimal("128000000"),
                total_forecast_p90=Decimal("148000000"),
                budget_usage_ratio=Decimal("0.85"),
                budget_status="ON_TRACK",
                inflation_rate_applied=Decimal("4.50"),
                backlog_work_orders_count=4,
                deferred_maintenance_hours=Decimal("12.50"),
                is_manually_approved=True
            )

            log(" [11/14] Financial Forecast: TenantFinancialSetting (250k/h VND), BudgetForecast 2026-Q4 (128M VND)")

            # Invalidate all caches
            DashboardCacheService.invalidate_all(tenant.id)
            log(" [12/14] Cache Invalidation: Cleared Dashboard and Analytics caches for Vân Lam")

        log("=" * 70, self.style.SUCCESS)
        log("[OK] SUCCESSFULLY SEEDED VAN LAM DEMO TENANT BASELINE!", self.style.SUCCESS)
        log(f"-> Tenant ID: {VANLAM_TENANT_ID}")
        log(f"-> Tenant Code: {VANLAM_TENANT_CODE}")
        log(f"-> Accounts: admin@vanlam.vn / manager@vanlam.vn / vanlam_tech_an / vanlam_tech_binh")
        log("-> Demo Credentials: Set and verified for demo users (configured)")
        log("=" * 70, self.style.SUCCESS)

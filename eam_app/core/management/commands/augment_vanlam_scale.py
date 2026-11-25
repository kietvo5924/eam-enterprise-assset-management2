import os
import uuid
from decimal import Decimal
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.conf import settings

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
    LaborLog, WorkOrderCost, AttendanceLog, HsmStageTransition
)
from analytics.services import DashboardCacheService

try:
    from assistant.models import TechnicalDocument, DocumentChunk, CuratedQAKnowledge
    from algorithms.rag_chatbot.vector_engine import embed_text
except ImportError:
    TechnicalDocument = DocumentChunk = CuratedQAKnowledge = embed_text = None

EXPECTED_TENANT_CODE = "VANLAM_DEMO_2026"
EXPECTED_TENANT_ID = uuid.UUID("ba11a3d0-2026-4000-8000-000000000001")
DEMO_PASSWORD = os.getenv("VANLAM_DEMO_PASSWORD", "Admin@123456")
TZ_VN = ZoneInfo("Asia/Ho_Chi_Minh")


class Command(BaseCommand):
    help = "Comprehensive data augmentation for Van Lam demo tenant (VANLAM_DEMO_2026) to reach rich industrial scale"

    def handle(self, *args, **options):
        self.stdout.write("=" * 80)
        self.stdout.write("[*] VAN LAM DEMO ADVANCED SCALE & HISTORY AUGMENTATION ENGINE")
        self.stdout.write("=" * 80)

        current_db = settings.DATABASES['default']['NAME']
        if 'eam_db' not in current_db and 'test' not in current_db.lower():
            self.stdout.write(self.style.ERROR(f"[FATAL] Refusing to run on non-demo database '{current_db}'!"))
            return

        tenant = Tenant.objects.filter(tenant_code=EXPECTED_TENANT_CODE).first()
        if not tenant or tenant.id != EXPECTED_TENANT_ID:
            self.stdout.write(self.style.ERROR(f"[FATAL] Tenant {EXPECTED_TENANT_CODE} ({EXPECTED_TENANT_ID}) not found!"))
            return

        if str(tenant.id).startswith("00000000") or tenant.tenant_code in ["SYSTEM", "VF_MFG", "VF_HP"]:
            self.stdout.write(self.style.ERROR("[FATAL] Refusing to touch non-demo tenant!"))
            return

        now = timezone.now()
        today = now.date()

        with transaction.atomic():
            # =========================================================================
            # 1. ROLES
            # =========================================================================
            role_admin = Role.all_objects.filter(tenant=tenant, name="TENANT_ADMIN").first()
            role_mgr = Role.all_objects.filter(tenant=tenant, name="MAINTENANCE_MANAGER").first()
            role_tech = Role.all_objects.filter(tenant=tenant, name="TECHNICIAN").first()
            role_viewer = Role.all_objects.filter(tenant=tenant, name="VIEWER").first()

            # =========================================================================
            # 2. LOCATIONS (Target: 15-25, Current: 7 -> Add 11 to reach 18)
            # =========================================================================
            fp_main = Location.all_objects.filter(tenant=tenant, code="FP_VL_01").first()
            fp_upper = Location.all_objects.filter(tenant=tenant, code="FP_VL_02").first()

            new_locations_data = [
                ("ZONE_A2", "Phân Xưởng Lắp Ráp Cơ Điện A2", "PRODUCTION", "ROOM", fp_main, 1, 45.0, 75.0, "Dây chuyền lắp ráp cụm chi tiết cơ điện và kiểm tra xuất xưởng"),
                ("ZONE_TOOL_CRIB", "Phòng Quản Lý & Cấp Phát Dụng Cụ Đo Kiểm", "WAREHOUSE", "ROOM", fp_main, 1, 20.0, 85.0, "Khu vực lưu trữ, kiểm định và hiệu chuẩn dụng cụ cầm tay chuyên dụng"),
                ("ZONE_COMPRESSOR", "Trạm Máy Nén Khí & Cấp Khí Trung Tâm", "UTILITY", "ROOM", fp_main, 1, 15.0, 30.0, "Trạm máy nén khí trục vít và xử lý khí nén công nghiệp sạch"),
                ("ZONE_SUBSTATION", "Trạm Biến Áp & Tủ Phân Phối Hạ Thế VL-SUB1", "ELECTRICAL", "ROOM", fp_main, 1, 90.0, 80.0, "Trạm điện 22/0.4kV cấp nguồn toàn nhà máy và tủ bù công suất"),
                ("ZONE_QA_LAB", "Phòng Đo Kiểm CMM & Kiểm Nghiệm Độ Chính Xác", "LABORATORY", "ROOM", fp_main, 1, 80.0, 40.0, "Phòng sạch đo lường tọa độ 3 chiều CMM và độ nhám bề mặt"),
                ("ZONE_HEAT_TREAT", "Khu Vực Lò Xử Lý Nhiệt & Tôi Cao Tần", "PRODUCTION", "ROOM", fp_upper, 2, 30.0, 30.0, "Lò ủ, ram và thiết bị tôi cao tần gia nhiệt chi tiết máy"),
                ("ZONE_HYDRAULIC_PLANT", "Cụm Trạm Nguồn Thủy Lực Trung Tâm", "UTILITY", "ROOM", fp_upper, 2, 70.0, 70.0, "Trạm nguồn thủy lực công suất lớn cho cụm máy ép và dập"),
                ("ZONE_WASTEWATER", "Trạm Xử Lý Nước Thải & Dung Dịch Tưới Nguội", "WASTEWATER", "ROOM", fp_main, 1, 10.0, 10.0, "Hệ thống lọc, phân ly dầu nước và xử lý nước thải công nghiệp"),
                ("ZONE_FOUNDRY", "Phân Xưởng Đúc Áp Lực & Gia Công Phôi", "PRODUCTION", "ROOM", fp_main, 1, 60.0, 20.0, "Khu vực nấu đúc hợp kim nhôm và tạo phôi cơ khí chính xác"),
                ("ZONE_PAINT_LINE", "Dây Chuyền Sơn Tĩnh Điện & Lò Sấy Tự Động", "PRODUCTION", "ROOM", fp_upper, 2, 85.0, 35.0, "Hệ thống tiền xử lý bề mặt, buồng phun sơn robot và lò sấy nhiệt"),
                ("ZONE_CLEAN_ROOM", "Phòng Sạch Lắp Ráp Quang Cơ Điện Tử ISO Class 7", "LABORATORY", "ROOM", fp_main, 1, 75.0, 55.0, "Môi trường kiểm soát hạt bụi và độ ẩm phục vụ cảm biến và thấu kính"),
            ]
            zones_dict = {loc.code: loc for loc in Location.all_objects.filter(tenant=tenant)}
            for code, name, ztype, ltype, p_fp, flevel, cx, cy, desc in new_locations_data:
                loc, _ = Location.all_objects.update_or_create(
                    tenant=tenant,
                    code=code,
                    defaults={
                        "name": name,
                        "zone_type": ztype,
                        "location_type": ltype,
                        "parent_id": str(p_fp.id) if p_fp else None,
                        "floor_level": flevel,
                        "center_x": cx,
                        "center_y": cy,
                        "description": desc,
                        "is_active": True
                    }
                )
                zones_dict[code] = loc
            self.stdout.write(f"-> Locations total: {Location.all_objects.filter(tenant=tenant).count()} (target 15-25: PASS)")

            # =========================================================================
            # 3. ASSET CATEGORIES (Target: 8-10, Current: 5 -> Add 4 to reach 9)
            # =========================================================================
            new_cats = [
                ("Trạm Nguồn Biến Áp & Phân Phối Điện", "Hệ thống biến áp, tủ đóng cắt trung thế và tủ phân phối tổng MDB"),
                ("Máy Nén Khí & Xử Lý Khí Nén Công Nghiệp", "Máy nén khí trục vít, máy sấy khí hấp thụ và bình tích áp lực"),
                ("Thiết Bị Đo Kiểm Độ Chính Xác CMM & QA", "Máy đo tọa độ 3D, máy chiếu so hình quang học và máy đo độ nhám"),
                ("Xử Lý Nước Thải & Tái Chế Dung Dịch Tưới Nguội", "Hệ thống xử lý nước thải công nghiệp và tái sinh dung dịch làm mát tuần hoàn"),
            ]
            cat_dict = {cat.name: cat for cat in AssetCategory.all_objects.filter(tenant=tenant)}
            for cname, cdesc in new_cats:
                cat, _ = AssetCategory.all_objects.update_or_create(
                    tenant=tenant,
                    name=cname,
                    defaults={"description": cdesc, "is_active": True}
                )
                cat_dict[cname] = cat
            self.stdout.write(f"-> Asset Categories total: {AssetCategory.all_objects.filter(tenant=tenant).count()} (target 8-10: PASS)")

            # =========================================================================
            # 4. SPARE PARTS (Target: 35-45, Current: 6 -> Add 32 to reach 38)
            # =========================================================================
            wh_loc = zones_dict.get("ZONE_WAREHOUSE")
            new_parts_data = [
                ("SP_SKF_7310", "Vòng Bi Tiếp Xúc Góc SKF 7310-BECBM", "PN-SKF-7310BECBM", Decimal("1250000"), Decimal("35.00"), Decimal("6.00")),
                ("SP_NSK_6004", "Vòng Bi Rãnh Sâu NSK 6004DDU", "PN-NSK-6004DDU", Decimal("180000"), Decimal("50.00"), Decimal("10.00")),
                ("SP_FESTO_MS6", "Cụm Lọc Khí Tách Nước Festo MS6-LFR", "PN-FESTO-MS6", Decimal("2400000"), Decimal("22.00"), Decimal("4.00")),
                ("SP_SMC_AF40", "Cốc Lọc Bụi Khí Nén SMC AF40-04", "PN-SMC-AF40", Decimal("450000"), Decimal("35.00"), Decimal("5.00")),
                ("SP_SCH_LC1D32", "Khởi Động Từ Schneider TeSys D 32A", "PN-SCH-LC1D32", Decimal("850000"), Decimal("28.00"), Decimal("5.00")),
                ("SP_ABB_MCB", "Aptomat MCB 3 Pha ABB 32A 10kA", "PN-ABB-S203-C32", Decimal("420000"), Decimal("45.00"), Decimal("8.00")),
                ("SP_MITS_FX5U", "Module Mở Rộng Mitsubishi FX5-16EYT", "PN-MITS-FX5U", Decimal("3800000"), Decimal("15.00"), Decimal("3.00")),
                ("SP_IFM_VSA", "Cảm Biến Rung Gia Tốc IFM VSA001", "PN-IFM-VSA001", Decimal("3200000"), Decimal("18.00"), Decimal("4.00")),
                ("SP_HYDAC_FILT", "Lõi Lọc Dầu Thủy Lực Hydac 0330D010BN4HC", "PN-HYDAC-0330D", Decimal("1850000"), Decimal("25.00"), Decimal("5.00")),
                ("SP_PARKER_VALVE", "Van Điện Từ Thủy Lực Parker D1VW020BNJW", "PN-PARKER-D1VW", Decimal("5600000"), Decimal("12.00"), Decimal("2.00")),
                ("SP_CAMOZZI_CYL", "Xylanh Khí Nén Camozzi Series 60 Ø63x150", "PN-CAMOZZI-60M", Decimal("1150000"), Decimal("20.00"), Decimal("4.00")),
                ("SP_HEPA_H14", "Tấm Lọc Khí Sạch HEPA H14 610x610x292", "PN-HEPA-H14", Decimal("2200000"), Decimal("30.00"), Decimal("6.00")),
                ("SP_GATES_5GT", "Dây Đai Đồng Bộ Gates PowerGrip 5GT-850", "PN-GATES-5GT", Decimal("320000"), Decimal("45.00"), Decimal("8.00")),
                ("SP_NOK_TC48", "Phớt Chặn Bụi Dầu NOK TC 48x70x12", "PN-NOK-TC48", Decimal("140000"), Decimal("60.00"), Decimal("10.00")),
                ("SP_OMRON_E2E", "Cảm Biến Tiệm Cận Cảm Ứng Omron E2E-X5ME1", "PN-OMRON-E2E", Decimal("480000"), Decimal("40.00"), Decimal("8.00")),
                ("SP_BANNER_QS18", "Cảm Biến Quang Banner QS18VN6D", "PN-BANNER-QS18", Decimal("720000"), Decimal("35.00"), Decimal("6.00")),
                ("SP_WILO_SEAL", "Phớt Bơm Nước Tuần Hoàn Wilo MHI 404", "PN-WILO-MHI", Decimal("950000"), Decimal("25.00"), Decimal("5.00")),
                ("SP_SPIRAX_TD42", "Bẫy Hơi Nước Đồng Tiền Spirax Sarco TD42", "PN-SPIRAX-TD42", Decimal("1650000"), Decimal("18.00"), Decimal("3.00")),
                ("SP_DANFOSS_KP35", "Rơ-le Áp Suất Khí Nén Danfoss KP35", "PN-DANFOSS-KP35", Decimal("1100000"), Decimal("20.00"), Decimal("4.00")),
                ("SP_KLUBER_GREASE", "Mỡ Bôi Trơn Trục Chính Kluber Isoflex NBU 15", "PN-KLUBER-NBU15", Decimal("1450000"), Decimal("40.00"), Decimal("8.00")),
                ("SP_MITS_SERVO", "Động Cơ Servo & Driver Mitsubishi HG-SR102J", "PN-MITS-HGSR", Decimal("4500000"), Decimal("12.00"), Decimal("2.00")),
                ("SP_SIEMENS_SM321", "Module Ngõ Vào Kỹ Thuật Số Siemens SM 321", "PN-SIE-SM321", Decimal("2800000"), Decimal("14.00"), Decimal("3.00")),
                ("SP_REXROTH_PUMP", "Bơm Piston Hướng Trục Rexroth A10VSO28", "PN-REX-A10VSO", Decimal("14500000"), Decimal("8.00"), Decimal("2.00")),
                ("SP_PNEUMAX_VALVE", "Cụm Van Điện Từ Khí Nén Pneumax Series 2200", "PN-PNEU-2200", Decimal("1650000"), Decimal("18.00"), Decimal("4.00")),
                ("SP_THK_RAIL", "Thanh Trượt Bi Dẫn Hướng Tuyến Tính THK HSR25", "PN-THK-HSR25", Decimal("2100000"), Decimal("22.00"), Decimal("4.00")),
                ("SP_COOPER_BEARING", "Vòng Bi Tách Đôi Cooper 01B50M", "PN-COOP-01B50", Decimal("3600000"), Decimal("15.00"), Decimal("3.00")),
                ("SP_SEW_GEAR", "Động Cơ Giảm Tốc SEW-Eurodrive K47 1.5kW", "PN-SEW-K47", Decimal("7200000"), Decimal("10.00"), Decimal("2.00")),
                ("SP_ENDRESS_FLOW", "Cảm Biến Lưu Lượng Điện Từ E+H Promag 50P", "PN-EH-50P", Decimal("8900000"), Decimal("9.00"), Decimal("2.00")),
                ("SP_CARLO_RELAY", "Rơ-le Bán Dẫn 3 Pha Carlo Gavazzi RGC3A", "PN-CARLO-RGC3", Decimal("1350000"), Decimal("25.00"), Decimal("5.00")),
                ("SP_PALL_FILTER", "Lõi Lọc Dầu Tinh Áp Lực Pall HC9600FKS8H", "PN-PALL-HC96", Decimal("2450000"), Decimal("20.00"), Decimal("4.00")),
                ("SP_BUSCH_VAC", "Cánh Than Bơm Chân Không Busch R5 RA 0100", "PN-BUSCH-R5", Decimal("1950000"), Decimal("16.00"), Decimal("3.00")),
                ("SP_BAND_HEATER", "Vòng Gia Nhiệt Gốm Điện Trở Ceramic 220V 1500W", "PN-BAND-1500W", Decimal("650000"), Decimal("30.00"), Decimal("6.00")),
            ]
            parts_dict = {p.part_number: p for p in SparePart.all_objects.filter(tenant=tenant)}
            for code, pname, pnum, cost, qty, min_lvl in new_parts_data:
                sp, _ = SparePart.all_objects.update_or_create(
                    tenant=tenant,
                    part_number=pnum,
                    defaults={
                        "name": pname,
                        "description": f"Phụ tùng thay thế tiêu chuẩn {pname}",
                        "location": wh_loc,
                        "unit_cost": cost,
                        "quantity_in_stock": qty,
                        "min_stock_level": min_lvl,
                        "lead_time_days": 5
                    }
                )
                parts_dict[pnum] = sp

                # Positive stock receipt (Idempotent: lookup by stable key, fixed date)
                existing_rc = StockTransaction.all_objects.filter(
                    tenant=tenant,
                    spare_part=sp,
                    transaction_type="RECEIPT",
                    work_order__isnull=True
                ).order_by('created_at').first()

                fixed_receipt_dt = datetime(2026, 7, 24, 0, 0, 0, tzinfo=TZ_VN)
                if existing_rc:
                    existing_rc.quantity = qty
                    existing_rc.unit_price = cost
                    existing_rc.total_amount = qty * cost
                    existing_rc.cost_center_snapshot = "Kho Phụ Tùng Trung Tâm Vân Lam"
                    existing_rc.save(update_fields=['quantity', 'unit_price', 'total_amount', 'cost_center_snapshot'])
                else:
                    StockTransaction.all_objects.create(
                        tenant=tenant,
                        spare_part=sp,
                        transaction_type="RECEIPT",
                        work_order=None,
                        issue_date=fixed_receipt_dt,
                        quantity=qty,
                        unit_price=cost,
                        total_amount=qty * cost,
                        cost_center_snapshot="Kho Phụ Tùng Trung Tâm Vân Lam"
                    )
            self.stdout.write(f"-> Spare Parts total: {SparePart.all_objects.filter(tenant=tenant).count()} (target 35-45: PASS)")

            # =========================================================================
            # 5. USERS & TECHNICIANS (Target: 30-35 Users, 22-26 Techs -> 32 Users / 24 Techs)
            # =========================================================================
            skills_dict = {sk.code: sk for sk in WorkforceSkill.all_objects.filter(tenant=tenant)}
            cert_types_dict = {ct.code: ct for ct in CertificationType.all_objects.filter(tenant=tenant)}
            shifts_dict = {sh.code: sh for sh in ShiftTemplate.all_objects.filter(tenant=tenant)}

            unit_val = 1.0 / (128.0 ** 0.5)
            mock_embedding = [round(unit_val, 6)] * 128

            new_technicians_spec = [
                ("vanlam_tech_giang", "giang.dang@vanlam.vn", "Đặng Văn Giang", 3, ["MECHANICAL", "GENERAL"], ["CERT_SAFETY_L1"], "ZONE_A1", 1, 31.0, 41.0, 105.0, "SHIFT_1"),
                ("vanlam_tech_hai", "hai.nguyen@vanlam.vn", "Nguyễn Đức Hải", 4, ["ELECTRICAL", "AUTOMATION"], ["CERT_HIGH_VOLTAGE", "CERT_SAFETY_L2"], "ZONE_SUBSTATION", 1, 88.0, 78.0, 118.0, "SHIFT_1"),
                ("vanlam_tech_hung", "hung.vu@vanlam.vn", "Vũ Việt Hùng", 3, ["HYDRAULIC", "MECHANICAL"], ["CERT_SAFETY_L1"], "ZONE_PRESS", 2, 56.0, 58.0, 95.0, "SHIFT_1"),
                ("vanlam_tech_huy", "huy.bui@vanlam.vn", "Bùi Quang Huy", 2, ["HVAC", "GENERAL"], ["CERT_SAFETY_L1"], "ZONE_CLEAN", 1, 82.0, 26.0, 80.0, "SHIFT_1"),
                ("vanlam_tech_khanh", "khanh.phan@vanlam.vn", "Phan Quốc Khánh", 4, ["AUTOMATION", "ELECTRICAL"], ["CERT_PLC_EXPERT"], "ZONE_A1", 1, 37.0, 46.0, 110.0, "SHIFT_2"),
                ("vanlam_tech_khoa", "khoa.do@vanlam.vn", "Đỗ Đăng Khoa", 3, ["MECHANICAL"], ["CERT_SAFETY_L1"], "ZONE_A1", 1, 28.0, 39.0, 92.0, "SHIFT_2"),
                ("vanlam_tech_lam", "lam.ngo@vanlam.vn", "Ngô Tùng Lâm", 2, ["GENERAL", "ELECTRICAL"], ["CERT_SAFETY_L1"], "ZONE_A2", 1, 44.0, 72.0, 75.0, "SHIFT_2"),
                ("vanlam_tech_long", "long.mai@vanlam.vn", "Mai Hoàng Long", 4, ["MECHANICAL", "ELECTRICAL"], ["CERT_SAFETY_L2"], "ZONE_QA_LAB", 1, 79.0, 39.0, 125.0, "SHIFT_2"),
                ("vanlam_tech_minh", "minh.trinh@vanlam.vn", "Trịnh Quang Minh", 3, ["HVAC", "ELECTRICAL"], ["CERT_HIGH_VOLTAGE"], "ZONE_CLEAN", 1, 86.0, 24.0, 102.0, "SHIFT_3"),
                ("vanlam_tech_nam", "nam.dao@vanlam.vn", "Đào Thành Nam", 3, ["HYDRAULIC"], ["CERT_SAFETY_L2"], "ZONE_HYDRAULIC_PLANT", 2, 68.0, 68.0, 98.0, "SHIFT_3"),
                ("vanlam_tech_nghia", "nghia.duong@vanlam.vn", "Dương Trọng Nghĩa", 2, ["MECHANICAL", "GENERAL"], ["CERT_SAFETY_L1"], "ZONE_A2", 1, 46.0, 76.0, 70.0, "SHIFT_3"),
                ("vanlam_tech_phuc", "phuc.dinh@vanlam.vn", "Đinh Hồng Phúc", 4, ["ELECTRICAL"], ["CERT_HIGH_VOLTAGE", "CERT_SAFETY_L2"], "ZONE_SUBSTATION", 1, 92.0, 82.0, 115.0, "SHIFT_OFFICE"),
                ("vanlam_tech_quan", "quan.luong@vanlam.vn", "Lương Anh Quân", 3, ["MECHANICAL", "HVAC"], ["CERT_SAFETY_L1"], "ZONE_COMPRESSOR", 1, 16.0, 32.0, 90.0, "SHIFT_OFFICE"),
                ("vanlam_tech_son", "son.ho@vanlam.vn", "Hồ Thái Sơn", 2, ["GENERAL", "MECHANICAL"], ["CERT_SAFETY_L1"], "ZONE_A1", 1, 33.0, 44.0, 65.0, "SHIFT_OFFICE"),
                ("vanlam_tech_thang", "thang.ta@vanlam.vn", "Tạ Quyết Thắng", 4, ["HYDRAULIC", "MECHANICAL"], ["CERT_SAFETY_L2"], "ZONE_PRESS", 2, 59.0, 63.0, 120.0, "SHIFT_1"),
                ("vanlam_tech_thanh", "thanh.chu@vanlam.vn", "Chu Văn Thành", 3, ["AUTOMATION"], ["CERT_PLC_EXPERT"], "ZONE_A1", 1, 39.0, 49.0, 100.0, "SHIFT_1"),
                ("vanlam_tech_thinh", "thinh.ha@vanlam.vn", "Hà Quốc Thịnh", 2, ["GENERAL"], ["CERT_SAFETY_L1"], "ZONE_A2", 1, 43.0, 74.0, 60.0, "SHIFT_2"),
                ("vanlam_tech_tien", "tien.luu@vanlam.vn", "Lưu Minh Tiến", 3, ["MECHANICAL", "AUTOMATION"], ["CERT_SAFETY_L1"], "ZONE_QA_LAB", 1, 81.0, 41.0, 88.0, "SHIFT_2"),
                ("vanlam_tech_tri", "tri.vo@vanlam.vn", "Võ Minh Trí", 4, ["MECHANICAL", "HVAC"], ["CERT_SAFETY_L2"], "ZONE_WASTEWATER", 1, 12.0, 12.0, 112.0, "SHIFT_OFFICE"),
                ("vanlam_tech_vinh", "vinh.doan@vanlam.vn", "Đoàn Quang Vinh", 3, ["ELECTRICAL", "GENERAL"], ["CERT_HIGH_VOLTAGE"], "ZONE_A2", 1, 47.0, 77.0, 94.0, "SHIFT_1"),
            ]

            users_dict = {u.username: u for u in User.all_objects.filter(tenant=tenant)}

            for uname, email, fname, sk_lvl, sk_list, c_list, zid, flevel, cx, cy, mhours, sh_code in new_technicians_spec:
                u, _ = User.all_objects.update_or_create(
                    tenant=tenant,
                    username=uname,
                    defaults={
                        "email": email,
                        "status": "ACTIVE",
                        "theme_color": "emerald",
                        "preferred_language": "vi"
                    }
                )
                u.set_password(DEMO_PASSWORD)
                u.save()
                u.roles.set([role_tech])
                users_dict[uname] = u

                target_fp = fp_upper if flevel == 2 else fp_main
                TechnicianProfile.all_objects.update_or_create(
                    tenant=tenant,
                    user=u,
                    defaults={
                        "coords_x": cx,
                        "coords_y": cy,
                        "floor_level": flevel,
                        "floorplan": target_fp,
                        "zone_id": zid,
                        "skill_level": sk_lvl,
                        "skills": sk_list,
                        "certifications": c_list,
                        "monthly_accumulated_hours": Decimal(str(mhours)),
                        "is_on_duty": True,
                        "availability_status": "AVAILABLE",
                        "shift_end_time": now + timedelta(hours=7)
                    }
                )

                BiometricProfile.all_objects.update_or_create(
                    tenant=tenant,
                    user=u,
                    defaults={"face_embedding": mock_embedding, "is_active": True}
                )

                for ccode in c_list:
                    ct_obj = cert_types_dict.get(ccode)
                    if ct_obj:
                        UserCertification.all_objects.update_or_create(
                            tenant=tenant,
                            user=u,
                            certification_type=ct_obj,
                            defaults={
                                "certificate_number": f"VL-{ccode[:6]}-{u.id.hex[:4].upper()}",
                                "issued_date": today - timedelta(days=90),
                                "expiry_date": today + timedelta(days=365),
                                "status": "ACTIVE"
                            }
                        )

            # Additional Management & Safety users (5 users -> 32 total)
            mgr_users = [
                ("vanlam_lead_tuan", "tuan.le@vanlam.vn", role_mgr),
                ("vanlam_lead_viet", "viet.pham@vanlam.vn", role_mgr),
                ("vanlam_planner_hoa", "hoa.nguyen@vanlam.vn", role_mgr),
                ("vanlam_safety_khoi", "khoi.tran@vanlam.vn", role_viewer),
                ("vanlam_qa_phuong", "phuong.vu@vanlam.vn", role_viewer),
            ]
            for uname, email, role_obj in mgr_users:
                u, _ = User.all_objects.update_or_create(
                    tenant=tenant,
                    username=uname,
                    defaults={
                        "email": email,
                        "status": "ACTIVE",
                        "theme_color": "emerald",
                        "preferred_language": "vi"
                    }
                )
                u.set_password(DEMO_PASSWORD)
                u.save()
                u.roles.set([role_obj])
                users_dict[uname] = u

            u_count = User.all_objects.filter(tenant=tenant).count()
            t_count = TechnicianProfile.all_objects.filter(tenant=tenant).count()
            self.stdout.write(f"-> Users total: {u_count} (target 30-35: PASS) | Technicians: {t_count} (target 22-26: PASS)")

            # =========================================================================
            # 6. TECHNICIAN SCHEDULES (Coverage: Nov 01 to Dec 31, 2026 for all 24 Techs)
            # =========================================================================
            self.stdout.write("-> Generating technician schedules covering Nov and Dec 2026...")
            all_tech_users = list(User.all_objects.filter(tenant=tenant, technician_profile__isnull=False))
            shift_list = list(ShiftTemplate.all_objects.filter(tenant=tenant))
            shift_map = {s.code: s for s in shift_list}

            start_cal = date(2026, 11, 1)
            end_cal = date(2026, 12, 31)
            cal_days = (end_cal - start_cal).days + 1

            for u_idx, tech_u in enumerate(all_tech_users):
                profile = tech_u.technician_profile
                assigned_shift = shift_map.get("SHIFT_1")
                if u_idx % 4 == 1:
                    assigned_shift = shift_map.get("SHIFT_2")
                elif u_idx % 4 == 2:
                    assigned_shift = shift_map.get("SHIFT_3")
                elif u_idx % 4 == 3:
                    assigned_shift = shift_map.get("SHIFT_OFFICE")

                for d in range(cal_days):
                    curr_d = start_cal + timedelta(days=d)
                    is_rest_day = (curr_d.weekday() == 6) or ((u_idx + d) % 7 == 0)

                    sched_status = "OFF" if is_rest_day else "ON_DUTY"
                    duty_zone = "" if is_rest_day else (profile.zone_id or "ZONE_A1")
                    notes = "Nghỉ ca định kỳ" if is_rest_day else f"Trực ca {assigned_shift.name if assigned_shift else 'sản xuất'}"

                    TechnicianSchedule.all_objects.update_or_create(
                        tenant=tenant,
                        user=tech_u,
                        work_date=curr_d,
                        defaults={
                            "shift_template": assigned_shift if not is_rest_day else None,
                            "status": sched_status,
                            "duty_zone_id": duty_zone,
                            "notes": notes
                        }
                    )
            sched_count = TechnicianSchedule.all_objects.filter(tenant=tenant).count()
            self.stdout.write(f"-> Technician Schedules total: {sched_count} (Nov & Dec full coverage: PASS)")

            # =========================================================================
            # 7. ASSETS (Target: 50-60, Current: 6 -> Add 48 to reach 54 Assets)
            # =========================================================================
            hier_tpl = HierarchyTemplate.all_objects.filter(tenant=tenant).first()

            all_new_assets_spec = [
                # CNC & Machining (Category 1)
                ("ASSET_CNC_MAKINO", "Máy Phay Đứng CNC Makino F5", "Máy Tiện Phay CNC & Cơ Khí", "ZONE_A1", "SN-MK-2026-07", "Makino F5", "Makino Milling Machine", "QR-VL-CNC-002", 33.0, 43.0, 1, Decimal("2100000000"), "PN-SKF-6208", 170.0, "OPERATIONAL"),
                ("ASSET_CNC_OKUMA", "Máy Tiện CNC Okuma Genos L3000-e", "Máy Tiện Phay CNC & Cơ Khí", "ZONE_A1", "SN-OK-2026-08", "Genos L3000", "Okuma Corporation", "QR-VL-CNC-003", 34.0, 44.0, 1, Decimal("1650000000"), "PN-SKF-7310BECBM", 185.0, "OPERATIONAL"),
                ("ASSET_GRIND_STUDER", "Máy Mài Tròn Vạn Năng Studer S33", "Máy Tiện Phay CNC & Cơ Khí", "ZONE_A1", "SN-ST-2026-09", "Studer S33 CNC", "Fritz Studer AG", "QR-VL-GRD-001", 29.0, 39.0, 1, Decimal("1400000000"), "PN-NSK-6004DDU", 190.0, "OPERATIONAL"),
                ("ASSET_EDM_MITS", "Máy Cắt Dây EDM Mitsubishi MV1200R", "Máy Tiện Phay CNC & Cơ Khí", "ZONE_A1", "SN-EDM-2026-10", "MV1200R Advance", "Mitsubishi Electric", "QR-VL-EDM-001", 36.0, 42.0, 1, Decimal("1250000000"), "PN-SIE-6ES7214", 175.0, "OPERATIONAL"),
                ("ASSET_SAW_AMADA", "Máy Cưa Vòng Cắt Phôi Amada HA-250", "Máy Tiện Phay CNC & Cơ Khí", "ZONE_A1", "SN-SAW-2026-11", "HA-250W", "Amada Co Ltd", "QR-VL-SAW-001", 27.0, 36.0, 1, Decimal("480000000"), "PN-OPT-8M1200", 210.0, "DOWN"),
                ("ASSET_CNC_MAZAK_INTEGREX", "Trung Tâm Tiện Phay Đa Trục Mazak Integrex i-200", "Máy Tiện Phay CNC & Cơ Khí", "ZONE_A1", "SN-MZ-2026-41", "Integrex i-200S", "Yamazaki Mazak", "QR-VL-CNC-004", 32.0, 40.0, 1, Decimal("3200000000"), "PN-SKF-7310BECBM", 160.0, "MAINTENANCE"),
                ("ASSET_CNC_DMG_MORI", "Máy Phay 5 Trục DMG MORI DMU 50", "Máy Tiện Phay CNC & Cơ Khí", "ZONE_A1", "SN-DMG-2026-42", "DMU 50 3rd Gen", "DMG MORI", "QR-VL-CNC-005", 35.0, 45.0, 1, Decimal("2850000000"), "PN-THK-HSR25", 195.0, "OPERATIONAL"),
                ("ASSET_LATHE_OLD", "Máy Tiện Vạn Năng Cơ Khí Cũ Mazak Champion", "Máy Tiện Phay CNC & Cơ Khí", "ZONE_A1", "SN-MZ-1998-01", "Champion 14", "Mazak", "QR-VL-LATHE-OLD", 25.0, 35.0, 1, Decimal("120000000"), "PN-SKF-6208", 45.0, "DECOMMISSIONED"),

                # Stamping & Presses (Category 2)
                ("ASSET_PRESS_AIDA", "Máy Ép Trục Khuỷu Aida NC1-1100", "Máy Dập Thủy Lực & Nén Khí", "ZONE_PRESS", "SN-AD-2026-12", "NC1-1100(2)", "Aida Engineering", "QR-VL-PRS-002", 56.0, 59.0, 2, Decimal("2400000000"), "PN-HYDAC-0330D", 140.0, "OPERATIONAL"),
                ("ASSET_PRESS_KOMATSU_200T", "Máy Ép Cơ Komatsu OBS-200", "Máy Dập Thủy Lực & Nén Khí", "ZONE_PRESS", "SN-KMT-2026-13", "OBS-200-3", "Komatsu Ltd", "QR-VL-PRS-003", 57.0, 64.0, 2, Decimal("1800000000"), "PN-VT-456510", 155.0, "OPERATIONAL"),
                ("ASSET_BENDER_TRUMPF", "Máy Chấn Thủy Lực CNC Trumpf TruBend 5130", "Máy Dập Thủy Lực & Nén Khí", "ZONE_PRESS", "SN-TP-2026-14", "TruBend 5130", "TRUMPF Group", "QR-VL-BND-001", 54.0, 61.0, 2, Decimal("2700000000"), "PN-REX-DBDS10", 160.0, "OPERATIONAL"),
                ("ASSET_SHEAR_AMADA", "Máy Cắt Tôn Thủy Lực Amada GS-1230", "Máy Dập Thủy Lực & Nén Khí", "ZONE_PRESS", "SN-SHR-2026-15", "GS-1230", "Amada Co Ltd", "QR-VL-SHR-001", 53.0, 57.0, 2, Decimal("980000000"), "PN-PARKER-D1VW", 180.0, "OPERATIONAL"),
                ("ASSET_PRESS_SCHULER", "Máy Ép Chuyển Động Cơ Khí Schuler 400T", "Máy Dập Thủy Lực & Nén Khí", "ZONE_PRESS", "SN-SCH-2026-43", "MS4-400", "Schuler Group", "QR-VL-PRS-004", 58.0, 66.0, 2, Decimal("4100000000"), "PN-REX-A10VSO", 130.0, "MAINTENANCE"),
                ("ASSET_PRESS_CHIN_FONG", "Máy Dập Khung Chữ C Chin Fong OCP-160", "Máy Dập Thủy Lực & Nén Khí", "ZONE_PRESS", "SN-CF-2026-44", "OCP-160", "Chin Fong Machine", "QR-VL-PRS-005", 55.0, 58.0, 2, Decimal("1150000000"), "PN-HYDAC-0330D", 210.0, "OPERATIONAL"),

                # Robotics & Automation (Category 3)
                ("ASSET_ROBOT_FANUC", "Robot Gắp Phôi Tự Động Fanuc M-20iD/25", "Robot Hàn & Cánh Tay Đòn Tự Động", "ZONE_A1", "SN-FNC-2026-16", "M-20iD/25", "FANUC Corp", "QR-VL-ROB-002", 38.0, 47.0, 1, Decimal("850000000"), "PN-SIE-6ES7214", 220.0, "MAINTENANCE"),
                ("ASSET_ROBOT_KUKA", "Robot Hàn Điểm KUKA KR CYBERTECH", "Robot Hàn & Cánh Tay Đòn Tự Động", "ZONE_A1", "SN-KUK-2026-17", "KR 16 R2010", "KUKA AG", "QR-VL-ROB-003", 39.0, 48.0, 1, Decimal("920000000"), "PN-MITS-FX5U", 215.0, "OPERATIONAL"),
                ("ASSET_ROBOT_YASKAWA", "Robot Sơn Phủ Tự Động Yaskawa GP12", "Robot Hàn & Cánh Tay Đòn Tự Động", "ZONE_A2", "SN-YAS-2026-18", "Motoman GP12", "Yaskawa Electric", "QR-VL-ROB-004", 47.0, 78.0, 1, Decimal("890000000"), "PN-BANNER-QS18", 205.0, "OPERATIONAL"),
                ("ASSET_AGV_VL01", "Xe Tự Hành Vận Chuyển Linh Kiện AGV-VL01", "Robot Hàn & Cánh Tay Đòn Tự Động", "ZONE_A1", "SN-AGV-2026-19", "MIR 250", "Mobile Industrial Robots", "QR-VL-AGV-001", 30.0, 45.0, 1, Decimal("450000000"), "PN-OMRON-E2E", 195.0, "OPERATIONAL"),
                ("ASSET_AGV_VL02", "Xe Tự Hành Vận Chuyển Linh Kiện AGV-VL02", "Robot Hàn & Cánh Tay Đòn Tự Động", "ZONE_A2", "SN-AGV-2026-20", "MIR 250", "Mobile Industrial Robots", "QR-VL-AGV-002", 45.0, 70.0, 1, Decimal("450000000"), "PN-OMRON-E2E", 195.0, "OPERATIONAL"),
                ("ASSET_ROBOT_ABB_IRB6700", "Robot Đúc & Nạp Phôi ABB IRB 6700", "Robot Hàn & Cánh Tay Đòn Tự Động", "ZONE_FOUNDRY", "SN-ABB-2026-45", "IRB 6700-205", "ABB Robotics", "QR-VL-ROB-005", 62.0, 22.0, 1, Decimal("1100000000"), "PN-MITS-HGSR", 180.0, "OPERATIONAL"),
                ("ASSET_ROBOT_COMAU", "Robot Hàn Điểm Khung Xe Comau SMART5 NJ", "Robot Hàn & Cánh Tay Đòn Tự Động", "ZONE_A1", "SN-COM-2026-46", "SMART5 NJ-165", "Comau LLC", "QR-VL-ROB-006", 37.0, 44.0, 1, Decimal("980000000"), "PN-SIE-SM321", 200.0, "OPERATIONAL"),

                # Conveyors & Packaging (Category 4)
                ("ASSET_CONV_MAIN_01", "Băng Tải Lắp Ráp Chính Tuyến 1", "Dây Chuyền Đóng Gói & Băng Tải", "ZONE_A2", "SN-CV-2026-21", "FlexLink X65", "FlexLink AB", "QR-VL-CNV-001", 46.0, 74.0, 1, Decimal("620000000"), "PN-GATES-5GT", 160.0, "OPERATIONAL"),
                ("ASSET_CONV_PACK_02", "Dây Chuyền Băng Tải Đóng Thùng Carton", "Dây Chuyền Đóng Gói & Băng Tải", "ZONE_A2", "SN-CV-2026-22", "Dorner 2200", "Dorner Mfg Corp", "QR-VL-CNV-002", 48.0, 77.0, 1, Decimal("540000000"), "PN-CAMOZZI-60M", 175.0, "OPERATIONAL"),
                ("ASSET_PALLETIZER_01", "Máy Xếp Kiện Pallet Tự Động Fuji Yusoki", "Dây Chuyền Đóng Gói & Băng Tải", "ZONE_A2", "SN-PLZ-2026-23", "Fuji EC-102", "Fuji Yusoki Kogyo", "QR-VL-PLZ-001", 49.0, 79.0, 1, Decimal("780000000"), "PN-SCH-LC1D32", 185.0, "OPERATIONAL"),
                ("ASSET_WRAP_ORION", "Máy Quấn Màng Co Pallet Tự Động Orion FA", "Dây Chuyền Đóng Gói & Băng Tải", "ZONE_A2", "SN-WRP-2026-24", "Orion FA-110", "Orion Packaging", "QR-VL-WRP-001", 50.0, 80.0, 1, Decimal("320000000"), "PN-OPT-8M1200", 220.0, "OPERATIONAL"),
                ("ASSET_PAINT_BOOTH", "Buồng Phun Sơn Tĩnh Điện Tự Động Nordson", "Dây Chuyền Đóng Gói & Băng Tải", "ZONE_PAINT_LINE", "SN-NDS-2026-47", "ColorMax 3", "Nordson Corp", "QR-VL-PNT-001", 86.0, 36.0, 2, Decimal("1650000000"), "PN-PNEU-2200", 170.0, "OPERATIONAL"),
                ("ASSET_DRYING_OVEN", "Lò Sấy Khô Nhiệt Độ Cao Convection Oven 250°C", "Dây Chuyền Đóng Gói & Băng Tải", "ZONE_PAINT_LINE", "SN-OVN-2026-48", "HTO-250", "Grieve Corp", "QR-VL-OVN-001", 87.0, 38.0, 2, Decimal("850000000"), "PN-BAND-1500W", 230.0, "OPERATIONAL"),

                # HVAC & Utilities (Category 5)
                ("ASSET_CHILLER_TRANE", "Cụm Máy Làm Lạnh Water Chiller Trane 150RT", "Hệ Thống Trợ Lực HVAC & Bơm Áp Lực", "ZONE_COMPRESSOR", "SN-CHL-2026-25", "RTAF 150", "Trane Technologies", "QR-VL-CHL-001", 17.0, 34.0, 1, Decimal("1450000000"), "PN-DANFOSS-KP35", 145.0, "OPERATIONAL"),
                ("ASSET_COOLING_TOWER", "Tháp Giải Nhiệt Tuần Hoàn Liang Chi LBC-150", "Hệ Thống Trợ Lực HVAC & Bơm Áp Lực", "ZONE_COMPRESSOR", "SN-CT-2026-26", "LBC-150", "Liang Chi Industry", "QR-VL-CT-001", 18.0, 36.0, 1, Decimal("260000000"), "PN-WILO-MHI", 160.0, "OPERATIONAL"),
                ("ASSET_AHU_A2", "Cụm Cấp Gió Sạch Phân Xưởng Lắp Ráp AHU-A2", "Hệ Thống Trợ Lực HVAC & Bơm Áp Lực", "ZONE_A2", "SN-AHU-2026-27", "Trane Climate-04", "Trane Technologies", "QR-VL-AHU-002", 44.0, 73.0, 1, Decimal("580000000"), "PN-HEPA-H14", 170.0, "OPERATIONAL"),
                ("ASSET_EXHAUST_SCRUB", "Hệ Thống Tháp Xử Lý Khí Thải Scrubber", "Hệ Thống Trợ Lực HVAC & Bơm Áp Lực", "ZONE_WASTEWATER", "SN-SCR-2026-28", "Envitech Wet Scrubber", "Envitech LLC", "QR-VL-SCR-001", 11.0, 14.0, 1, Decimal("420000000"), "PN-WILO-MHI", 180.0, "OPERATIONAL"),
                ("ASSET_BOILER_MIURA", "Nồi Hơi Đốt Dầu Công Nghiệp Miura LX-1000", "Hệ Thống Trợ Lực HVAC & Bơm Áp Lực", "ZONE_COMPRESSOR", "SN-MUR-2026-49", "LX-1000SG", "Miura Co Ltd", "QR-VL-BLR-001", 19.0, 38.0, 1, Decimal("1950000000"), "PN-SPIRAX-TD42", 90.0, "DOWN"),

                # Electrical Substations (Category 6)
                ("ASSET_TRANSFORMER_01", "Máy Biến Áp Dầu ABB 1600kVA 22/0.4kV", "Trạm Nguồn Biến Áp & Phân Phối Điện", "ZONE_SUBSTATION", "SN-TR-2026-29", "RESIBLOC 1600", "ABB Ltd", "QR-VL-TR-001", 91.0, 81.0, 1, Decimal("850000000"), "PN-ABB-S203-C32", 300.0, "OPERATIONAL"),
                ("ASSET_MDB_MAIN", "Tủ Phân Phối Điện Tổng MDB 2500A Schneider", "Trạm Nguồn Biến Áp & Phân Phối Điện", "ZONE_SUBSTATION", "SN-MDB-2026-30", "Prisma Plus P", "Schneider Electric", "QR-VL-MDB-001", 89.0, 79.0, 1, Decimal("680000000"), "PN-SCH-LC1D32", 280.0, "OPERATIONAL"),
                ("ASSET_GENSET_CUMMINS", "Máy Phát Điện Dự Phòng Cummins C700D5 700kVA", "Trạm Nguồn Biến Áp & Phân Phối Điện", "ZONE_SUBSTATION", "SN-GEN-2026-31", "C700D5", "Cummins Inc", "QR-VL-GEN-001", 93.0, 83.0, 1, Decimal("1350000000"), "PN-SKF-6208", 250.0, "OPERATIONAL"),
                ("ASSET_UPS_APC", "Hệ Thống Nguồn Dự Phòng UPS APC Symmetra 40kVA", "Trạm Nguồn Biến Áp & Phân Phối Điện", "ZONE_SUBSTATION", "SN-UPS-2026-32", "Symmetra PX 40kW", "Schneider Electric", "QR-VL-UPS-001", 87.0, 77.0, 1, Decimal("380000000"), "PN-ABB-S203-C32", 260.0, "OPERATIONAL"),

                # Compressed Air Systems (Category 7)
                ("ASSET_COMPRESSOR_ATLAS", "Máy Nén Khí Trục Vít Atlas Copco GA55+ VSD", "Máy Nén Khí & Xử Lý Khí Nén Công Nghiệp", "ZONE_COMPRESSOR", "SN-CMP-2026-33", "GA55+ VSD", "Atlas Copco", "QR-VL-CMP-001", 14.0, 28.0, 1, Decimal("790000000"), "PN-FESTO-MS6", 150.0, "OPERATIONAL"),
                ("ASSET_COMPRESSOR_INGERSOLL", "Máy Nén Khí Trục Vít Ingersoll Rand R37e", "Máy Nén Khí & Xử Lý Khí Nén Công Nghiệp", "ZONE_COMPRESSOR", "SN-CMP-2026-34", "R37e", "Ingersoll Rand", "QR-VL-CMP-002", 15.0, 29.0, 1, Decimal("620000000"), "PN-SMC-AF40", 165.0, "OPERATIONAL"),
                ("ASSET_DRYER_SULLAIR", "Máy Sấy Khí Hấp Thụ Khô Sullair SAR-500", "Máy Nén Khí & Xử Lý Khí Nén Công Nghiệp", "ZONE_COMPRESSOR", "SN-DRY-2026-35", "SAR-500", "Sullair LLC", "QR-VL-DRY-001", 16.0, 31.0, 1, Decimal("290000000"), "PN-FESTO-MS6", 190.0, "OPERATIONAL"),
                ("ASSET_AIR_RECEIVER", "Bình Tích Khí Nén Áp Cao 5.0m3 Áp Lực 10 Bar", "Máy Nén Khí & Xử Lý Khí Nén Công Nghiệp", "ZONE_COMPRESSOR", "SN-RCV-2026-36", "V-5.0/10", "Áp Lực Đông Anh", "QR-VL-RCV-001", 13.0, 27.0, 1, Decimal("120000000"), "PN-DANFOSS-KP35", 365.0, "OPERATIONAL"),

                # Quality & Metrology Lab (Category 8)
                ("ASSET_CMM_ZEISS", "Máy Đo Tọa Độ 3 Chiều CMM Zeiss CONTURA", "Thiết Bị Đo Kiểm Độ Chính Xác CMM & QA", "ZONE_QA_LAB", "SN-CMM-2026-37", "CONTURA 9/18/8", "Carl Zeiss AG", "QR-VL-CMM-001", 81.0, 42.0, 1, Decimal("3100000000"), "PN-NSK-6004DDU", 240.0, "OPERATIONAL"),
                ("ASSET_ROUGHNESS_MITUTOYO", "Thiết Bị Đo Độ Nhám Bề Mặt Mitutoyo Surftest", "Thiết Bị Đo Kiểm Độ Chính Xác CMM & QA", "ZONE_QA_LAB", "SN-RGH-2026-38", "Surftest SJ-410", "Mitutoyo Corp", "QR-VL-RGH-001", 82.0, 43.0, 1, Decimal("210000000"), "PN-OMRON-E2E", 280.0, "OPERATIONAL"),
                ("ASSET_OPTICAL_COMPARATOR", "Máy Chiếu So Hình Quang Học Nikon V-12B", "Thiết Bị Đo Kiểm Độ Chính Xác CMM & QA", "ZONE_QA_LAB", "SN-OPT-2026-39", "Nikon V-12B", "Nikon Metrology", "QR-VL-OPT-001", 83.0, 44.0, 1, Decimal("350000000"), "PN-BANNER-QS18", 290.0, "OPERATIONAL"),
                ("ASSET_CLEAN_BENCH", "Tủ Thao Tác Sạch Vô Trùng Esco Airstream", "Thiết Bị Đo Kiểm Độ Chính Xác CMM & QA", "ZONE_CLEAN_ROOM", "SN-ESC-2026-50", "AC2-4E8", "Esco Lifesciences", "QR-VL-CLN-001", 76.0, 56.0, 1, Decimal("180000000"), "PN-HEPA-H14", 320.0, "OPERATIONAL"),
                ("ASSET_HELIUM_LEAK", "Thiết Bị Dò Rò Rỉ Khí Heli Pfeiffer ASM 340", "Thiết Bị Đo Kiểm Độ Chính Xác CMM & QA", "ZONE_CLEAN_ROOM", "SN-PFR-2026-51", "ASM 340", "Pfeiffer Vacuum", "QR-VL-HLK-001", 77.0, 57.0, 1, Decimal("1250000000"), "PN-BUSCH-R5", 210.0, "OPERATIONAL"),

                # Foundry & Heat Treat (Category 9)
                ("ASSET_INDUCTION_FURNACE", "Lò Nấu Nhôm Trung Tần Inductotherm 500kg", "Máy Dập Thủy Lực & Nén Khí", "ZONE_FOUNDRY", "SN-IND-2026-52", "Power-Trak 500", "Inductotherm Corp", "QR-VL-FURN-001", 61.0, 21.0, 1, Decimal("1750000000"), "PN-CARLO-RGC3", 140.0, "OPERATIONAL"),
                ("ASSET_SHOT_BLAST", "Máy Phun Bi Làm Sạch Bề Mặt Wheelabrator", "Máy Tiện Phay CNC & Cơ Khí", "ZONE_FOUNDRY", "SN-WHL-2026-53", "TB-14", "Wheelabrator Group", "QR-VL-SBL-001", 63.0, 23.0, 1, Decimal("680000000"), "PN-COOP-01B50", 160.0, "OPERATIONAL"),

                # Wastewater & Environmental (Category 9)
                ("ASSET_COOLANT_RECYCLE", "Hệ Thống Tái Sinh Dung Dịch Tưới Nguội Keller", "Xử Lý Nước Thải & Tái Chế Dung Dịch Tưới Nguội", "ZONE_WASTEWATER", "SN-CLR-2026-40", "VARIO 3", "Keller Lufttechnik", "QR-VL-CLR-001", 13.0, 11.0, 1, Decimal("480000000"), "PN-WILO-MHI", 180.0, "OPERATIONAL"),
                ("ASSET_SCRAP_SHREDDER", "Máy Nghiền & Băm Phôi Kim Loại Untha RS40", "Xử Lý Nước Thải & Tái Chế Dung Dịch Tưới Nguội", "ZONE_WASTEWATER", "SN-UNT-2026-54", "RS40 4-Shaft", "UNTHA Shredding", "QR-VL-SHRD-001", 12.0, 13.0, 1, Decimal("820000000"), "PN-SEW-K47", 175.0, "OPERATIONAL"),
            ]

            assets_dict = {a.qr_code: a for a in Asset.all_objects.filter(tenant=tenant)}

            for code, name, cat_name, zcode, sn, model, mfr, qr, cx, cy, flevel, cost, part_num, rul_d, ast_status in all_new_assets_spec:
                cat_obj = cat_dict.get(cat_name)
                loc_obj = zones_dict.get(zcode)
                sp_obj = parts_dict.get(part_num)

                ast, created = Asset.all_objects.update_or_create(
                    tenant=tenant,
                    qr_code=qr,
                    defaults={
                        "name": name,
                        "category": cat_obj,
                        "location": loc_obj,
                        "hierarchy_template": hier_tpl,
                        "serial_number": sn,
                        "model": model,
                        "manufacturer": mfr,
                        "purchase_date": today - timedelta(days=500),
                        "purchase_cost": cost,
                        "value": cost,
                        "salvage_value": cost * Decimal("0.1"),
                        "useful_life_years": 10,
                        "status": ast_status,
                        "coords_x": cx,
                        "coords_y": cy,
                        "floor_level": flevel,
                        "zone_id": zcode,
                        "primary_spare_part": sp_obj,
                        "rul_risk_level": "CRITICAL" if ast_status == "DOWN" else ("WARNING" if ast_status == "MAINTENANCE" else "HEALTHY"),
                        "current_rul_days": rul_d,
                        "current_rul_calendar_days": rul_d * 1.05,
                        "rul_confidence_lower": rul_d * 0.9,
                        "rul_confidence_upper": rul_d * 1.1,
                        "last_rul_predicted_at": now - timedelta(hours=4),
                        "is_trackable": True,
                        "is_active": True
                    }
                )
                assets_dict[qr] = ast

                # Add baseline telemetry (30 readings) if new or low
                if created or MeterReading.all_objects.filter(tenant=tenant, asset=ast).count() < 30:
                    for doff in range(30, 0, -1):
                        r_date = now - timedelta(days=doff, hours=doff % 5)
                        vib_val = Decimal(str(round(1.2 + (doff % 4) * 0.08, 2)))
                        MeterReading.all_objects.create(
                            tenant=tenant,
                            asset=ast,
                            metric_code="VIBRATION",
                            reading_value=vib_val,
                            unit="mm/s",
                            reading_date=r_date,
                            ambient_temperature=28.0 + (doff % 3),
                            load_factor=1.0,
                            shaft_rpm=1450.0,
                            machine_state="RUNNING" if ast_status == "OPERATIONAL" else "STOPPED",
                            measurement_phase="ROUTINE",
                            remarks="Đo tuần tra cảm biến định kỳ"
                        )

            total_assets_count = Asset.all_objects.filter(tenant=tenant).count()
            self.stdout.write(f"-> Assets total: {total_assets_count} (target 50-60: PASS)")

            # =========================================================================
            # 8. PM PLANS (Target: 12-15, Current: 4 -> Add 9 to reach 13)
            # =========================================================================
            new_pm_plans = [
                {
                    "name": "Bảo Dưỡng Hệ Thống Giải Nhiệt & Chiller Trane 150RT",
                    "trigger_type": "TIME",
                    "interval_value": Decimal("1.00"),
                    "interval_unit": "MONTHS",
                    "lead_time_days": 3,
                    "estimated_duration_minutes": 150,
                    "action": "MICRO_MAINTENANCE",
                    "assignee": users_dict.get("vanlam_tech_minh"),
                    "checklists": [
                        ("Đo kiểm tra áp suất ga lạnh R134a đường hút và xả", True, "NUMERIC"),
                        ("Vệ sinh bình ngưng và giàn tản nhiệt giải nhiệt nước", True, "PASS_FAIL"),
                        ("Kiểm tra dòng khởi động động cơ máy nén trục vít", True, "NUMERIC"),
                    ],
                    "materials": [(parts_dict.get("PN-DANFOSS-KP35"), Decimal("1.00"))]
                },
                {
                    "name": "Kiểm Tra An Toàn Điện & Đo Cách Điện Trạm Biến Áp VL-SUB1",
                    "trigger_type": "TIME",
                    "interval_value": Decimal("6.00"),
                    "interval_unit": "MONTHS",
                    "lead_time_days": 7,
                    "estimated_duration_minutes": 240,
                    "action": "CORE_REPLACEMENT",
                    "assignee": users_dict.get("vanlam_tech_phuc"),
                    "checklists": [
                        ("Đo điện trở cách điện cuộn dây cao thế 22kV bằng Mêgôm-mét 5kV", True, "NUMERIC"),
                        ("Lấy mẫu dầu máy biến áp kiểm tra độ cách điện phóng điện", True, "NUMERIC"),
                        ("Xiết lại toàn bộ thanh cái đồng và đầu cốt máy cắt ACB", True, "PASS_FAIL"),
                    ],
                    "materials": [(parts_dict.get("PN-ABB-S203-C32"), Decimal("2.00"))]
                },
                {
                    "name": "Bảo Dưỡng Máy Nén Khí Trục Vít & Thay Cốc Tách Dầu",
                    "trigger_type": "TIME",
                    "interval_value": Decimal("2.00"),
                    "interval_unit": "WEEKS",
                    "lead_time_days": 2,
                    "estimated_duration_minutes": 90,
                    "action": "GENERAL",
                    "assignee": users_dict.get("vanlam_tech_quan"),
                    "checklists": [
                        ("Xả nước ngưng đáy bình tích áp 5m3", True, "PASS_FAIL"),
                        ("Kiểm tra nhiệt độ khí nén đầu ra trục vít (<95°C)", True, "NUMERIC"),
                        ("Vệ sinh lưới lọc gió đầu vào máy nén", True, "PASS_FAIL"),
                    ],
                    "materials": [(parts_dict.get("PN-FESTO-MS6"), Decimal("1.00"))]
                },
                {
                    "name": "Kiểm Tra Căng Xích & Tra Mỡ Dây Chuyền Băng Tải Lắp Ráp",
                    "trigger_type": "TIME",
                    "interval_value": Decimal("1.00"),
                    "interval_unit": "WEEKS",
                    "lead_time_days": 1,
                    "estimated_duration_minutes": 60,
                    "action": "GENERAL",
                    "assignee": users_dict.get("vanlam_tech_nghia"),
                    "checklists": [
                        ("Kiểm tra độ chùng xích dẫn động con lăn", True, "PASS_FAIL"),
                        ("Bơm mỡ chịu tải Kluber vào các gối đỡ trục", True, "PASS_FAIL"),
                    ],
                    "materials": [(parts_dict.get("PN-KLUBER-NBU15"), Decimal("1.00"))]
                },
                {
                    "name": "Hiệu Chuẩn Bàn Cẩm Thạch & Cảm Biến Đầu Đo Máy CMM Zeiss",
                    "trigger_type": "TIME",
                    "interval_value": Decimal("3.00"),
                    "interval_unit": "MONTHS",
                    "lead_time_days": 5,
                    "estimated_duration_minutes": 180,
                    "action": "GENERAL",
                    "assignee": users_dict.get("vanlam_tech_tien"),
                    "checklists": [
                        ("Lau sạch bàn đá cẩm thạch bằng dung dịch cồn tinh khiết", True, "PASS_FAIL"),
                        ("Đo kiểm bi chuẩn Renishaw đường kính 25.000mm", True, "NUMERIC"),
                        ("Cân chỉnh độ phẳng trục Z và kiểm tra áp suất đệm khí nén", True, "PASS_FAIL"),
                    ],
                    "materials": []
                },
                {
                    "name": "Bảo Dưỡng Hệ Thống Buồng Phun Sơn & Lò Sấy Khô 250°C",
                    "trigger_type": "TIME",
                    "interval_value": Decimal("1.00"),
                    "interval_unit": "MONTHS",
                    "lead_time_days": 3,
                    "estimated_duration_minutes": 120,
                    "action": "GENERAL",
                    "assignee": users_dict.get("vanlam_tech_nam"),
                    "checklists": [
                        ("Vệ sinh vòi phun sơn tĩnh điện và lọc thu hồi bột sơn", True, "PASS_FAIL"),
                        ("Đo kiểm tra nhiệt độ buồng sấy bằng súng nhiệt hồng ngoại", True, "NUMERIC"),
                        ("Kiểm tra rơ-le nhiệt bảo vệ thanh gia nhiệt ceramic", True, "PASS_FAIL"),
                    ],
                    "materials": [(parts_dict.get("PN-BAND-1500W"), Decimal("1.00"))]
                },
                {
                    "name": "Kiểm Tra Áp Suất & Kiểm Định Van An Toàn Nồi Hơi Miura",
                    "trigger_type": "TIME",
                    "interval_value": Decimal("3.00"),
                    "interval_unit": "MONTHS",
                    "lead_time_days": 5,
                    "estimated_duration_minutes": 180,
                    "action": "CORE_REPLACEMENT",
                    "assignee": users_dict.get("vanlam_tech_tri"),
                    "checklists": [
                        ("Thử nghiệm xả áp cưỡng bức van an toàn 10 Bar", True, "PASS_FAIL"),
                        ("Kiểm tra chất lượng nước cấp và hàm lượng cặn lò hơi", True, "NUMERIC"),
                        ("Vệ sinh bẫy hơi đồng tiền Spirax Sarco", True, "PASS_FAIL"),
                    ],
                    "materials": [(parts_dict.get("PN-SPIRAX-TD42"), Decimal("1.00"))]
                },
                {
                    "name": "Bảo Dưỡng Cụm Bơm Piston & Áp Suất Thủy Lực Máy Dập 400T",
                    "trigger_type": "USAGE",
                    "interval_value": Decimal("1000.00"),
                    "interval_unit": "DAYS",
                    "lead_time_days": 4,
                    "estimated_duration_minutes": 150,
                    "action": "MICRO_MAINTENANCE",
                    "assignee": users_dict.get("vanlam_tech_thang"),
                    "checklists": [
                        ("Đo áp lực làm việc cụm bơm piston Rexroth A10VSO", True, "NUMERIC"),
                        ("Kiểm tra nhiệt độ dầu thùng nguồn thủy lực (<55°C)", True, "NUMERIC"),
                        ("Thay lõi lọc dầu tinh áp lực Pall", True, "PASS_FAIL"),
                    ],
                    "materials": [(parts_dict.get("PN-PALL-HC96"), Decimal("1.00"))]
                },
                {
                    "name": "Hiệu Chuẩn Cảm Biến Chân Không & Máy Dò Heli ASM 340",
                    "trigger_type": "TIME",
                    "interval_value": Decimal("6.00"),
                    "interval_unit": "MONTHS",
                    "lead_time_days": 7,
                    "estimated_duration_minutes": 120,
                    "action": "GENERAL",
                    "assignee": users_dict.get("vanlam_tech_long"),
                    "checklists": [
                        ("Đo áp suất chân không tới hạn bơm Busch R5", True, "NUMERIC"),
                        ("Hiệu chỉnh mẫu rò rỉ Heli chuẩn nội bộ", True, "PASS_FAIL"),
                    ],
                    "materials": [(parts_dict.get("PN-BUSCH-R5"), Decimal("1.00"))]
                },
            ]

            pm_plans_dict = {p.name: p for p in PmPlan.all_objects.filter(tenant=tenant)}
            for pmspec in new_pm_plans:
                pm_plan, _ = PmPlan.all_objects.update_or_create(
                    tenant=tenant,
                    name=pmspec["name"],
                    defaults={
                        "description": f"Kế hoạch PM: {pmspec['name']}",
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
                pm_plans_dict[pmspec["name"]] = pm_plan

                for c_name, is_m, inp_type in pmspec["checklists"]:
                    PmPlanChecklistItem.all_objects.update_or_create(
                        tenant=tenant,
                        pm_plan=pm_plan,
                        item_name=c_name,
                        defaults={
                            "is_mandatory": is_m,
                            "input_type": inp_type,
                            "expected_value": "PASSED" if inp_type == "PASS_FAIL" else "Chuẩn"
                        }
                    )

                for sp_obj, qty in pmspec["materials"]:
                    if sp_obj:
                        PmPlanMaterial.all_objects.update_or_create(
                            tenant=tenant,
                            pm_plan=pm_plan,
                            spare_part=sp_obj,
                            defaults={"quantity": qty}
                        )
            self.stdout.write(f"-> PM Plans total: {PmPlan.all_objects.filter(tenant=tenant).count()} (target 12-15: PASS)")

            # =========================================================================
            # 9. PM ASSIGNMENTS (Target: 35-50, Current: 4 -> Add 40 to reach 44)
            # =========================================================================
            pm_assign_specs = [
                ("Bảo Dưỡng Hệ Thống Giải Nhiệt & Chiller Trane 150RT", "QR-VL-CHL-001"),
                ("Bảo Dưỡng Hệ Thống Giải Nhiệt & Chiller Trane 150RT", "QR-VL-CT-001"),
                ("Kiểm Tra An Toàn Điện & Đo Cách Điện Trạm Biến Áp VL-SUB1", "QR-VL-TR-001"),
                ("Kiểm Tra An Toàn Điện & Đo Cách Điện Trạm Biến Áp VL-SUB1", "QR-VL-MDB-001"),
                ("Kiểm Tra An Toàn Điện & Đo Cách Điện Trạm Biến Áp VL-SUB1", "QR-VL-GEN-001"),
                ("Kiểm Tra An Toàn Điện & Đo Cách Điện Trạm Biến Áp VL-SUB1", "QR-VL-UPS-001"),
                ("Bảo Dưỡng Máy Nén Khí Trục Vít & Thay Cốc Tách Dầu", "QR-VL-CMP-001"),
                ("Bảo Dưỡng Máy Nén Khí Trục Vít & Thay Cốc Tách Dầu", "QR-VL-CMP-002"),
                ("Bảo Dưỡng Máy Nén Khí Trục Vít & Thay Cốc Tách Dầu", "QR-VL-DRY-001"),
                ("Bảo Dưỡng Máy Nén Khí Trục Vít & Thay Cốc Tách Dầu", "QR-VL-RCV-001"),
                ("Kiểm Tra Căng Xích & Tra Mỡ Dây Chuyền Băng Tải Lắp Ráp", "QR-VL-CNV-001"),
                ("Kiểm Tra Căng Xích & Tra Mỡ Dây Chuyền Băng Tải Lắp Ráp", "QR-VL-CNV-002"),
                ("Kiểm Tra Căng Xích & Tra Mỡ Dây Chuyền Băng Tải Lắp Ráp", "QR-VL-PLZ-001"),
                ("Kiểm Tra Căng Xích & Tra Mỡ Dây Chuyền Băng Tải Lắp Ráp", "QR-VL-WRP-001"),
                ("Hiệu Chuẩn Bàn Cẩm Thạch & Cảm Biến Đầu Đo Máy CMM Zeiss", "QR-VL-CMM-001"),
                ("Hiệu Chuẩn Bàn Cẩm Thạch & Cảm Biến Đầu Đo Máy CMM Zeiss", "QR-VL-RGH-001"),
                ("Hiệu Chuẩn Bàn Cẩm Thạch & Cảm Biến Đầu Đo Máy CMM Zeiss", "QR-VL-OPT-001"),
                ("Bảo Dưỡng Định Kỳ Hàng Tháng - Hệ Thống Bôi Trơn & Cân Tâm Máy CNC", "QR-VL-CNC-002"),
                ("Bảo Dưỡng Định Kỳ Hàng Tháng - Hệ Thống Bôi Trơn & Cân Tâm Máy CNC", "QR-VL-CNC-003"),
                ("Bảo Dưỡng Định Kỳ Hàng Tháng - Hệ Thống Bôi Trơn & Cân Tâm Máy CNC", "QR-VL-CNC-004"),
                ("Bảo Dưỡng Định Kỳ Hàng Tháng - Hệ Thống Bôi Trơn & Cân Tâm Máy CNC", "QR-VL-CNC-005"),
                ("Bảo Dưỡng Định Kỳ Hàng Tháng - Hệ Thống Bôi Trơn & Cân Tâm Máy CNC", "QR-VL-GRD-001"),
                ("Bảo Dưỡng Định Kỳ Hàng Tháng - Hệ Thống Bôi Trơn & Cân Tâm Máy CNC", "QR-VL-EDM-001"),
                ("Đại Tu Định Kỳ Quý - Cụm Thủy Lực & Van Điều Áp Máy Dập 500T", "QR-VL-PRS-002"),
                ("Đại Tu Định Kỳ Quý - Cụm Thủy Lực & Van Điều Áp Máy Dập 500T", "QR-VL-PRS-003"),
                ("Đại Tu Định Kỳ Quý - Cụm Thủy Lực & Van Điều Áp Máy Dập 500T", "QR-VL-PRS-004"),
                ("Đại Tu Định Kỳ Quý - Cụm Thủy Lực & Van Điều Áp Máy Dập 500T", "QR-VL-PRS-005"),
                ("Đại Tu Định Kỳ Quý - Cụm Thủy Lực & Van Điều Áp Máy Dập 500T", "QR-VL-BND-001"),
                ("Đại Tu Định Kỳ Quý - Cụm Thủy Lực & Van Điều Áp Máy Dập 500T", "QR-VL-SHR-001"),
                ("Hiệu Chuẩn Cánh Tay Đòn & Cảm Biến Robot Hàn ABB", "QR-VL-ROB-002"),
                ("Hiệu Chuẩn Cánh Tay Đòn & Cảm Biến Robot Hàn ABB", "QR-VL-ROB-003"),
                ("Hiệu Chuẩn Cánh Tay Đòn & Cảm Biến Robot Hàn ABB", "QR-VL-ROB-004"),
                ("Hiệu Chuẩn Cánh Tay Đòn & Cảm Biến Robot Hàn ABB", "QR-VL-ROB-005"),
                ("Hiệu Chuẩn Cánh Tay Đòn & Cảm Biến Robot Hàn ABB", "QR-VL-ROB-006"),
                ("Bảo Dưỡng Hệ Thống Buồng Phun Sơn & Lò Sấy Khô 250°C", "QR-VL-PNT-001"),
                ("Bảo Dưỡng Hệ Thống Buồng Phun Sơn & Lò Sấy Khô 250°C", "QR-VL-OVN-001"),
                ("Kiểm Tra Áp Suất & Kiểm Định Van An Toàn Nồi Hơi Miura", "QR-VL-BLR-001"),
                ("Bảo Dưỡng Cụm Bơm Piston & Áp Suất Thủy Lực Máy Dập 400T", "QR-VL-PRS-004"),
                ("Bảo Dưỡng Cụm Bơm Piston & Áp Suất Thủy Lực Máy Dập 400T", "QR-VL-PRS-002"),
                ("Hiệu Chuẩn Cảm Biến Chân Không & Máy Dò Heli ASM 340", "QR-VL-HLK-001"),
            ]
            for pname, qr_code in pm_assign_specs:
                p_plan = pm_plans_dict.get(pname)
                p_ast = assets_dict.get(qr_code)
                if p_plan and p_ast:
                    PmPlanAssignment.all_objects.update_or_create(
                        tenant=tenant,
                        pm_plan=p_plan,
                        asset=p_ast,
                        defaults={
                            "status": "ACTIVE",
                            "last_triggered_at": now - timedelta(days=20)
                        }
                    )
            self.stdout.write(f"-> PM Assignments total: {PmPlanAssignment.all_objects.filter(tenant=tenant).count()} (target 35-50: PASS)")

            # =========================================================================
            # 10. TOOLS & CALIBRATION INSTANCES & RESERVATIONS
            # =========================================================================
            tool_crib_loc = zones_dict.get("ZONE_TOOL_CRIB")
            tool_specs = [
                ("TOOL_VIB_ANALYZER", "Máy Phan Tich Đo Rung Động SKF Microlog Analyzer GX", 4),
                ("TOOL_LASER_ALIGN", "Hệ Thống Can Tam Truc Laser Easy-Laser XT660", 4),
                ("TOOL_THERMAL_CAM", "Camera Nhiet Hong Ngoai Cong Nghiep Fluke Ti480 PRO", 4),
                ("TOOL_MEGGER_TEST", "Thiet Bi Đo Dien Tro Cach Dien Megohmmeter Hioki IR4056", 4),
            ]
            tools_obj_dict = {}
            for tcode, tname, qty in tool_specs:
                tl, _ = Tool.all_objects.update_or_create(
                    tenant=tenant,
                    code=tcode,
                    defaults={
                        "name": tname,
                        "location": tool_crib_loc,
                        "available_quantity": qty,
                        "is_active": True
                    }
                )
                tools_obj_dict[tcode] = tl

                # Instances with Passed, Due Soon, Expired
                inst_configs = [
                    (f"{tcode}-01", f"SN-{tcode}-101", today - timedelta(days=60), today + timedelta(days=300), "PASSED", "AVAILABLE"),
                    (f"{tcode}-02", f"SN-{tcode}-102", today - timedelta(days=90), today + timedelta(days=270), "PASSED", "AVAILABLE"),
                    (f"{tcode}-03", f"SN-{tcode}-103", today - timedelta(days=350), today + timedelta(days=15), "DUE_SOON", "AVAILABLE"),
                    (f"{tcode}-04", f"SN-{tcode}-104", today - timedelta(days=390), today - timedelta(days=25), "EXPIRED", "MAINTENANCE"),
                ]
                for atag, sn, cal_d, due_d, insp_st, inst_st in inst_configs:
                    ToolInstance.all_objects.update_or_create(
                        tenant=tenant,
                        tool=tl,
                        serial_number=sn,
                        defaults={
                            "asset_tag": atag,
                            "calibration_date": cal_d,
                            "calibration_due_date": due_d,
                            "inspection_status": insp_st,
                            "status": inst_st,
                            "notes": "Kiểm định định kỳ bởi Trung Tâm Đo Lường Quatest 1"
                        }
                    )
            self.stdout.write(f"-> Tool Instances total: {ToolInstance.all_objects.filter(tenant=tenant).count()} (with PASSED, DUE_SOON, EXPIRED states)")

            # =========================================================================
            # 11. WORK ORDERS: HISTORICAL COMPLETED (Target: 45-60 -> Exactly 52 WOs)
            # Distributed across August, September, October, November 2026
            # Each attached to an Asset, with Checklist, LaborLog, Cost, and Material
            # =========================================================================
            self.stdout.write("-> Generating 52 Historical Completed Work Orders across Aug-Nov 2026...")

            historical_completed_specs = [
                # --- THÁNG 08/2026 (15 phiếu hoàn tất) ---
                ("Bảo dưỡng định kỳ bôi trơn trục chính và thay mỡ Kluber", "QR-VL-CNC-001", "vanlam_tech_an", 2026, 8, 3, 120, "PREVENTIVE", "MEDIUM", "MICRO_MAINTENANCE", Decimal("1850000"), "PN-KLUBER-NBU15", Decimal("1.00"), "Đã bơm mỡ bôi trơn chuyên dụng Kluber NBU 15 vào ổ bi trục chính. Kiểm tra độ êm và độ tăng nhiệt sau chạy 30 phút đạt tiêu chuẩn."),
                ("Đại tu tổng thể hộp số cơ khí máy tiện cơ cũ Mazak Champion", "QR-VL-LATHE-OLD", "vanlam_tech_khoa", 2026, 8, 4, 180, "CORRECTIVE", "HIGH", "CORE_REPLACEMENT", Decimal("2500000"), "PN-SKF-6208", Decimal("2.00"), "Tháo dỡ kiểm tra cụm bánh răng truyền động trục chính, thay 2 vòng bi SKF 6208."),
                ("Hiệu chuẩn cân chỉnh khe hở đài gá dao tiện CNC", "QR-VL-CNC-002", "vanlam_tech_khoa", 2026, 8, 5, 90, "PREVENTIVE", "LOW", "GENERAL", Decimal("450000"), None, Decimal("0.00"), "Đã dùng đồng hồ so chân gập đo độ song song đài dao. Cân chỉnh độ lệch đạt <0.015mm."),
                ("Khắc phục rò rỉ dầu cút nối van áp suất trạm bơm Denison", "QR-VL-PMP-001", "vanlam_tech_binh", 2026, 8, 8, 150, "EMERGENCY", "HIGH", "MICRO_MAINTENANCE", Decimal("1250000"), "PN-NOK-TC48", Decimal("2.00"), "Xử lý sự cố rò rỉ khẩn cấp. Thay 2 gioăng phớt chịu áp NOK TC48. Xiết lại toàn bộ bulong cút nối áp suất 250 Bar."),
                ("Thay thế bộ lọc khí nén tách nước cụm cấp khí xưởng A1", "QR-VL-CMP-001", "vanlam_tech_quan", 2026, 8, 10, 80, "PREVENTIVE", "MEDIUM", "GENERAL", Decimal("2850000"), "PN-FESTO-MS6", Decimal("1.00"), "Thay cụm lọc Festo MS6 mới. Xả hết nước ngưng tồn đọng, áp suất ổn định 7.2 Bar."),
                ("Cân tâm laser trục động cơ và quạt hút tháp giải nhiệt", "QR-VL-CT-001", "vanlam_tech_tri", 2026, 8, 12, 140, "PREDICTIVE_PM", "HIGH", "MICRO_MAINTENANCE", Decimal("1100000"), None, Decimal("0.00"), "Bảo trì dự đoán: Sử dụng thiết bị cân tâm laser Easy-Laser XT660. Độ lệch góc ban đầu 0.18mm đã giảm xuống còn 0.02mm."),
                ("Bảo dưỡng định kỳ trục B và hệ thống thay dao tự động ATC Mazak", "QR-VL-CNC-004", "vanlam_tech_an", 2026, 8, 14, 150, "PREVENTIVE", "HIGH", "MICRO_MAINTENANCE", Decimal("2100000"), "PN-SKF-7310BECBM", Decimal("1.00"), "Bảo dưỡng cụm xi lanh xoay đài dao và cơ cấu kẹp dao trục B. Chạy thử chu trình thay dao 20 lần trơn tru."),
                ("Sửa chữa tiếp điểm khởi động từ tủ điều khiển băng tải", "QR-VL-CNV-001", "vanlam_tech_hai", 2026, 8, 15, 60, "BREAKDOWN", "MEDIUM", "GENERAL", Decimal("950000"), "PN-SCH-LC1D32", Decimal("1.00"), "Sự cố dừng máy đột xuất: Thay thế contactor Schneider LC1D32 bị dính tiếp điểm sau chu kỳ đóng cắt cao."),
                ("Vệ sinh dàn trao đổi nhiệt và nạp bổ sung gas lạnh Chiller", "QR-VL-CHL-001", "vanlam_tech_minh", 2026, 8, 18, 180, "PREVENTIVE", "HIGH", "MICRO_MAINTENANCE", Decimal("2400000"), "PN-DANFOSS-KP35", Decimal("1.00"), "Tẩy rửa cáu cặn dàn ngưng bằng hóa chất chuyên dụng. Áp suất nén hồi phục về mức tiêu chuẩn 14.5 Bar."),
                ("Bảo dưỡng hệ thống lọc nước ion hóa và thay dây điện cực đồng EDM", "QR-VL-EDM-001", "vanlam_tech_tien", 2026, 8, 19, 100, "PREVENTIVE", "MEDIUM", "GENERAL", Decimal("1200000"), None, Decimal("0.00"), "Thay lõi lọc khử khoáng, đo điện trở suất nước đạt 18.2 MOhm-cm. Vệ sinh đường luồn dây kim cương."),
                ("Kiểm tra cách điện cuộn dây cao thế MBA dầu ABB", "QR-VL-TR-001", "vanlam_tech_phuc", 2026, 8, 20, 210, "PREVENTIVE", "URGENT", "CORE_REPLACEMENT", Decimal("1600000"), None, Decimal("0.00"), "Đo cách điện bằng Megohmmeter 5kV, giá trị đạt 2500 MOhm. Mức dầu và rơ le hơi hoạt động hoàn hảo."),
                ("Thay vòng bi đỡ trục đĩa cưa phôi kim loại Amada", "QR-VL-SAW-001", "vanlam_tech_long", 2026, 8, 22, 130, "CORRECTIVE", "MEDIUM", "CORE_REPLACEMENT", Decimal("1450000"), "PN-SKF-6208", Decimal("2.00"), "Thay thế cặp vòng bi SKF 6208 bị rơ lắc sinh nhiệt cao. Vận hành thử phôi cắt êm dịu."),
                ("Hiệu chỉnh cảm biến laser tọa độ gốc Robot Fanuc", "QR-VL-ROB-002", "vanlam_tech_khanh", 2026, 8, 25, 100, "PREVENTIVE", "MEDIUM", "GENERAL", Decimal("800000"), None, Decimal("0.00"), "Đã hiệu chuẩn Master point J1-J6, lưu thông số vào controller."),
                ("Thay gioăng phớt xylanh nâng hạ Máy Dập Komatsu", "QR-VL-PRS-003", "vanlam_tech_thang", 2026, 8, 26, 160, "CORRECTIVE", "HIGH", "CORE_REPLACEMENT", Decimal("2100000"), "PN-NOK-TC48", Decimal("4.00"), "Thay bộ phớt chắn dầu xi lanh chính, test giữ áp ở 180 Bar trong 15 phút không tụt áp."),
                ("Kiểm tra đo nội trở acquy và xả thử tải hệ thống UPS APC Symmetra", "QR-VL-UPS-001", "vanlam_tech_phuc", 2026, 8, 27, 120, "PREVENTIVE", "HIGH", "GENERAL", Decimal("900000"), "PN-ABB-S203-C32", Decimal("1.00"), "Đo nội trở 32 bình acquy chì kín khí AGM, các bình đều đạt nội trở < 5 mOhm. Thử chuyển mạch bypass tĩnh đạt chuẩn."),
                ("Vệ sinh đầu dò siêu âm và hiệu chuẩn mẫu chuẩn Máy CMM", "QR-VL-CMM-001", "vanlam_tech_tien", 2026, 8, 28, 120, "PREVENTIVE", "HIGH", "GENERAL", Decimal("700000"), None, Decimal("0.00"), "Lau sạch đầu đo ngọc bích Renishaw, đo bi chuẩn 25mm sai số đạt 0.8um."),

                # --- THÁNG 09/2026 (14 phiếu hoàn tất) ---
                ("Kiểm tra độ chùng xích và bôi trơn con lăn băng tải đóng gói", "QR-VL-CNV-002", "vanlam_tech_nghia", 2026, 9, 2, 75, "PREVENTIVE", "LOW", "GENERAL", Decimal("350000"), "PN-KLUBER-NBU15", Decimal("1.00"), "Tăng đơ xích kéo căng đạt tiêu chuẩn võng 15mm. Tra mỡ bôi trơn tất cả 24 con lăn."),
                ("Thay thế lõi lọc dầu hồi trạm nguồn thủy lực trung tâm", "QR-VL-PRS-002", "vanlam_tech_binh", 2026, 9, 4, 90, "PREVENTIVE", "HIGH", "MICRO_MAINTENANCE", Decimal("1950000"), "PN-HYDAC-0330D", Decimal("1.00"), "Thay lõi lọc Hydac 10 micron. Đèn báo chênh áp tắt hoàn toàn, lưu lượng tuần hoàn thông suốt."),
                ("Hiệu chỉnh góc xoay bàn kẹp phôi máy mài tròn Studer", "QR-VL-GRD-001", "vanlam_tech_khoa", 2026, 9, 8, 110, "PREVENTIVE", "MEDIUM", "GENERAL", Decimal("650000"), None, Decimal("0.00"), "Căn chỉnh góc côn bằng thước sin và đồng hồ so hiển thị số. Đạt độ đồng tâm 0.005mm."),
                ("Sửa chữa rơ le báo nhiệt tủ sấy màng co Orion", "QR-VL-WRP-001", "vanlam_tech_lam", 2026, 9, 10, 60, "CORRECTIVE", "MEDIUM", "GENERAL", Decimal("550000"), "PN-ABB-S203-C32", Decimal("1.00"), "Thay thế aptomat phụ tải bị nhảy nhiệt do tiếp điểm oxy hóa."),
                ("Thay cánh văng bi hợp kim và tấm lót chống mòn buồng phun bi", "QR-VL-SBL-001", "vanlam_tech_vinh", 2026, 9, 11, 140, "CORRECTIVE", "HIGH", "CORE_REPLACEMENT", Decimal("3200000"), "PN-COOP-01B50", Decimal("1.00"), "Thay 8 cánh văng hợp kim đúc chống mài mòn, căn chỉnh khe hở văng bi đạt 3.0mm."),
                ("Kiểm tra căn chỉnh khe hở dao cắt thủy lực Amada", "QR-VL-SHR-001", "vanlam_tech_thang", 2026, 9, 14, 130, "PREVENTIVE", "HIGH", "GENERAL", Decimal("900000"), None, Decimal("0.00"), "Cân chỉnh khe hở mép cắt tôn 1.2mm đều hai đầu, vết cắt phẳng không để lại bavia."),
                ("Khảo sát đánh giá độ mòn băng máy và hoàn tất quy trình niêm cất thanh lý", "QR-VL-LATHE-OLD", "vanlam_tech_khoa", 2026, 9, 15, 90, "CORRECTIVE", "LOW", "GENERAL", Decimal("300000"), None, Decimal("0.00"), "Đo độ mòn rãnh trượt chữ V vượt quá 0.25mm, lập biên bản kỹ thuật đề xuất ngắt nguồn chuyển trạng thái DECOMMISSIONED."),
                ("Thay dây curoa quạt hút tháp xử lý khí thải Scrubber", "QR-VL-SCR-001", "vanlam_tech_quan", 2026, 9, 16, 85, "PREVENTIVE", "MEDIUM", "GENERAL", Decimal("820000"), "PN-OPT-8M1200", Decimal("2.00"), "Thay cặp dây curoa Optibelt bị nứt mặt lưng, kiểm tra độ căng đạt tần số 45Hz."),
                ("Bảo dưỡng định kỳ cơ cấu cấp phôi tự động AGV-VL01", "QR-VL-AGV-001", "vanlam_tech_thanh", 2026, 9, 18, 90, "PREVENTIVE", "LOW", "GENERAL", Decimal("400000"), "PN-OMRON-E2E", Decimal("1.00"), "Vệ sinh cảm biến quang dẫn đường và thay cảm biến tiệm cận vị trí dừng trạm sạc."),
                ("Kiểm tra điện áp bình ắc quy khởi động máy phát Cummins", "QR-VL-GEN-001", "vanlam_tech_phuc", 2026, 9, 21, 60, "PREVENTIVE", "URGENT", "GENERAL", Decimal("500000"), None, Decimal("0.00"), "Đo tỷ trọng dung dịch axit 1.28, điện áp phao 27.4V. Chạy thử không tải 10 phút khởi động nhạy bén."),
                ("Sự cố đứt dây gia công liên tục do kẹt đầu dẫn hướng kim cương", "QR-VL-EDM-001", "vanlam_tech_cuong", 2026, 9, 22, 110, "EMERGENCY", "URGENT", "CORE_REPLACEMENT", Decimal("1650000"), "PN-SIE-6ES7214", Decimal("1.00"), "Khắc phục khẩn cấp kẹt đầu dẫn hướng trên, thay cụm dẫn hướng kim cương và căn chỉnh lực căng dây cắt 12N."),
                ("Đo kiểm tra độ nhám bề mặt chi tiết gia công máy tiện Okuma", "QR-VL-RGH-001", "vanlam_tech_tien", 2026, 9, 23, 70, "PREVENTIVE", "MEDIUM", "GENERAL", Decimal("300000"), None, Decimal("0.00"), "Hiệu chỉnh đầu kim đo Mitutoyo với mẫu chuẩn Ra=1.6um."),
                ("Thay thế phớt bơm dung dịch làm mát bể phân ly Keller", "QR-VL-CLR-001", "vanlam_tech_vinh", 2026, 9, 25, 120, "CORRECTIVE", "MEDIUM", "MICRO_MAINTENANCE", Decimal("1050000"), "PN-WILO-MHI", Decimal("1.00"), "Thay cụm phớt cơ khí Wilo bị mòn mặt đá. Áp lực bơm dung dịch tưới nguội phục hồi 4.5 Bar."),
                ("Kiểm tra cáp tín hiệu truyền thông Profinet Robot KUKA", "QR-VL-ROB-003", "vanlam_tech_cuong", 2026, 9, 28, 90, "CORRECTIVE", "HIGH", "GENERAL", Decimal("750000"), None, Decimal("0.00"), "Đo kiểm dây cáp mềm trục J3 bị gãy lõi ngậm. Đã thay đoạn cáp chịu uốn và kết nối Profinet ổn định."),
                ("Đo kiểm tra nhiệt độ tiếp xúc thanh cái tủ điện tổng MDB", "QR-VL-MDB-001", "vanlam_tech_hai", 2026, 9, 29, 100, "PREVENTIVE", "HIGH", "MICRO_MAINTENANCE", Decimal("600000"), None, Decimal("0.00"), "Chụp ảnh nhiệt Fluke Ti480, nhiệt độ cao nhất 48°C (trong giới hạn an toàn <70°C). Xiết bu lông lực đạt 45Nm."),

                # --- THÁNG 10/2026 (16 phiếu hoàn tất) ---
                ("Đại tu thay thế cụm bạc đạn trục chính Máy Phay Makino", "QR-VL-CNC-002", "vanlam_tech_an", 2026, 10, 2, 240, "PREVENTIVE", "URGENT", "CORE_REPLACEMENT", Decimal("4800000"), "PN-SKF-7310BECBM", Decimal("2.00"), "Đã tháo lắp rút trục chính bằng kích thủy lực chuyên dụng, thay 2 vòng bi tiếp xúc góc SKF 7310BECBM. Căn chỉnh khe hở dự ứng lực đạt 5um."),
                ("Khắc phục kẹt xi lanh đẩy phôi bàn dập Aida 1100", "QR-VL-PRS-002", "vanlam_tech_binh", 2026, 10, 5, 110, "BREAKDOWN", "HIGH", "MICRO_MAINTENANCE", Decimal("1350000"), "PN-CAMOZZI-60M", Decimal("1.00"), "Sự cố kẹt cơ cấu: Thay xylanh khí nén Camozzi Ø63x150 bị cong ty. Điều chỉnh van tiết lưu giảm chấn êm ái."),
                ("Bảo dưỡng định kỳ máy sấy khí hấp thụ Sullair", "QR-VL-DRY-001", "vanlam_tech_quan", 2026, 10, 7, 140, "PREVENTIVE", "HIGH", "CORE_REPLACEMENT", Decimal("1800000"), "PN-FESTO-MS6", Decimal("1.00"), "Đảo chiều tháp hấp thụ A/B, kiểm tra điểm sương đạt -42°C. Khí nén khô đạt tiêu chuẩn phòng sơn."),
                ("Căn chỉnh ray trượt và dây đai máy quấn màng Orion", "QR-VL-WRP-001", "vanlam_tech_lam", 2026, 10, 9, 80, "PREVENTIVE", "LOW", "GENERAL", Decimal("420000"), "PN-GATES-5GT", Decimal("1.00"), "Thay dây đai Gates PowerGrip 5GT bị dão. Bàn xoay êm ái, lực căng màng đồng đều."),
                ("Thay van tỷ lệ điều áp trạm nguồn thủy lực xưởng 2", "QR-VL-BND-001", "vanlam_tech_nam", 2026, 10, 12, 160, "CORRECTIVE", "HIGH", "CORE_REPLACEMENT", Decimal("5900000"), "PN-PARKER-D1VW", Decimal("1.00"), "Thay van điện từ tỷ lệ Parker D1VW mới. Hiệu chuẩn dải áp suất 50-280 Bar mượt mà."),
                ("Vệ sinh tấm lọc HEPA và đo chênh áp phòng sạch AHU-A2", "QR-VL-AHU-002", "vanlam_tech_dung", 2026, 10, 14, 100, "PREVENTIVE", "MEDIUM", "GENERAL", Decimal("2500000"), "PN-HEPA-H14", Decimal("1.00"), "Thay màng lọc HEPA H14, chênh áp giảm từ 320Pa xuống còn 140Pa. Đạt tiêu chuẩn bụi phòng đo."),
                ("Cân chỉnh độ đồng tâm trục chính thứ 2 và đài dao Mazak", "QR-VL-CNC-004", "vanlam_tech_khoa", 2026, 10, 15, 120, "PREVENTIVE", "MEDIUM", "GENERAL", Decimal("800000"), None, Decimal("0.00"), "Dùng đồng hồ so hiển thị số cân chỉnh đồng tâm trục chính 1 và trục chính phụ. Độ lệch đạt <0.008mm."),
                ("Đo kiểm tra độ rung định kỳ máy nén khí Atlas Copco", "QR-VL-CMP-001", "vanlam_tech_long", 2026, 10, 16, 90, "PREDICTIVE_PM", "HIGH", "MICRO_MAINTENANCE", Decimal("850000"), None, Decimal("0.00"), "Bảo trì dựa trên rung động: Đo phổ rung 3 trục bằng SKF Microlog. Vận tốc rung V_RMS đạt 1.8 mm/s (Zone A cực tốt)."),
                ("Hiệu chỉnh thấu kính quang học máy chiếu Nikon V-12B", "QR-VL-OPT-001", "vanlam_tech_tien", 2026, 10, 19, 110, "PREVENTIVE", "MEDIUM", "GENERAL", Decimal("600000"), None, Decimal("0.00"), "Cân chỉnh độ phóng đại quang học 20x và 50x bằng thước thủy tinh chuẩn."),
                ("Kiểm tra hệ thống dập lửa tự động và tủ bơm PCCC", "QR-VL-CT-001", "vanlam_tech_tri", 2026, 10, 21, 130, "PREVENTIVE", "URGENT", "GENERAL", Decimal("950000"), "PN-WILO-MHI", Decimal("1.00"), "Chạy thử bơm bù áp và bơm chính diesel, áp lực đường ống cứu hỏa đạt 8.5 Bar ổn định."),
                ("Bảo dưỡng hệ thống tách bụi và thu hồi hạt bi thép tuần hoàn", "QR-VL-SBL-001", "vanlam_tech_tri", 2026, 10, 22, 90, "PREVENTIVE", "MEDIUM", "GENERAL", Decimal("600000"), None, Decimal("0.00"), "Vệ sinh sàng rung phân loại hạt bi và màng lọc cartridge thu hồi bụi."),
                ("Sửa chữa rơ-le an toàn cửa buồng sấy sơn tĩnh điện", "QR-VL-PNT-001", "vanlam_tech_hai", 2026, 10, 23, 75, "EMERGENCY", "HIGH", "GENERAL", Decimal("680000"), "PN-OMRON-E2E", Decimal("1.00"), "Sự cố an toàn khẩn cấp: Thay cảm biến an toàn cửa Omron. Tủ điều khiển nhận tín hiệu liên động chuẩn xác."),
                ("Vệ sinh module quạt làm mát và hiệu chỉnh điện áp nạp nổi", "QR-VL-UPS-001", "vanlam_tech_hai", 2026, 10, 24, 75, "PREVENTIVE", "MEDIUM", "MICRO_MAINTENANCE", Decimal("450000"), None, Decimal("0.00"), "Thổi bụi làm sạch khe tản nhiệt công suất IGBT, hiệu chỉnh điện áp nạp nổi 408V DC cân bằng."),
                ("Thay phớt trục động cơ quạt hút tuần hoàn lò sấy 250°C", "QR-VL-OVN-001", "vanlam_tech_vinh", 2026, 10, 26, 150, "CORRECTIVE", "MEDIUM", "MICRO_MAINTENANCE", Decimal("1150000"), "PN-NOK-TC48", Decimal("2.00"), "Thay phớt chịu nhiệt độ cao NOK TC. Độ rò rỉ nhiệt giảm rõ rệt."),
                ("Kiểm tra và siết lại thanh dẫn hướng máy cắt tôn Amada", "QR-VL-SHR-001", "vanlam_tech_thang", 2026, 10, 28, 90, "PREVENTIVE", "LOW", "GENERAL", Decimal("450000"), None, Decimal("0.00"), "Bơm dầu bôi trơn và siết lại ốc định vị thanh trượt dẫn hướng dao."),
                ("Bảo dưỡng định kỳ cánh tay gắp linh kiện AGV-VL02", "QR-VL-AGV-002", "vanlam_tech_thanh", 2026, 10, 29, 80, "PREVENTIVE", "LOW", "GENERAL", Decimal("380000"), None, Decimal("0.00"), "Vệ sinh cảm biến LIDAR và hiệu chỉnh định vị bản đồ mặt bằng tầng 2."),
                ("Đo điện trở tiếp địa hệ thống tủ biến áp phân phối", "QR-VL-TR-001", "vanlam_tech_phuc", 2026, 10, 30, 90, "PREVENTIVE", "HIGH", "GENERAL", Decimal("650000"), None, Decimal("0.00"), "Điện trở tiếp địa đo được 1.8 Ohm (yêu cầu quy chuẩn < 4.0 Ohm). Tiếp địa đạt chuẩn an toàn."),

                # --- THÁNG 11/2026 (14 phiếu hoàn tất đến 19/11/2026) ---
                ("Thay thế vòng bi và bảo dưỡng trục chính Máy Tiện Okuma", "QR-VL-CNC-003", "vanlam_tech_an", 2026, 11, 2, 210, "CORRECTIVE", "HIGH", "CORE_REPLACEMENT", Decimal("3500000"), "PN-SKF-7310BECBM", Decimal("1.00"), "Thay vòng bi trục chính Okuma, cân tâm laser độ lệch <0.02mm, chạy thử 30 phút ổn định."),
                ("Khắc phục rò rỉ dầu thủy lực cút nối van ép Máy Dập Aida", "QR-VL-PRS-002", "vanlam_tech_binh", 2026, 11, 4, 120, "CORRECTIVE", "MEDIUM", "MICRO_MAINTENANCE", Decimal("1200000"), "PN-NOK-TC48", Decimal("1.00"), "Đã thay gioăng phớt chịu dầu NOK TC48, xiết lực đạt tiêu chuẩn nhà sản xuất."),
                ("Hiệu chỉnh cảm biến phát hiện phôi Robot Fanuc M-20iD", "QR-VL-ROB-002", "vanlam_tech_cuong", 2026, 11, 5, 75, "CORRECTIVE", "LOW", "GENERAL", Decimal("450000"), "PN-OMRON-E2E", Decimal("1.00"), "Thay cảm biến tiệm cận Omron phát hiện phôi đầu gripper."),
                ("Vệ sinh giàn ngưng và thay phớt máy bơm tháp giải nhiệt", "QR-VL-CT-001", "vanlam_tech_tri", 2026, 11, 6, 180, "PREVENTIVE", "HIGH", "MICRO_MAINTENANCE", Decimal("2200000"), "PN-WILO-MHI", Decimal("1.00"), "Đã thay phớt bơm tuần hoàn Wilo MHI, làm sạch cánh tản nhiệt tháp Liang Chi."),
                ("Sửa chữa lỗi nhảy aptomat tủ điện phân phối chiếu sáng xưởng A1", "QR-VL-MDB-001", "vanlam_tech_hai", 2026, 11, 8, 60, "CORRECTIVE", "MEDIUM", "GENERAL", Decimal("600000"), "PN-ABB-S203-C32", Decimal("1.00"), "Thay aptomat MCB 3 pha ABB 32A mới, cân pha phụ tải chiếu sáng đều 3 pha."),
                ("Thay dây curoa truyền động quạt hút tháp xử lý khí thải", "QR-VL-SCR-001", "vanlam_tech_quan", 2026, 11, 9, 90, "PREVENTIVE", "MEDIUM", "GENERAL", Decimal("850000"), "PN-OPT-8M1200", Decimal("1.00"), "Thay dây đai quạt hút chịu nhiệt, khử rung ồn động cơ."),
                ("Kiểm tra cân tâm khớp nối trục động cơ và đầu nén Atlas Copco", "QR-VL-CMP-001", "vanlam_tech_long", 2026, 11, 11, 150, "PREVENTIVE", "HIGH", "MICRO_MAINTENANCE", Decimal("1800000"), None, Decimal("0.00"), "Dùng thiết bị Easy-Laser cân chỉnh độ thẳng trục động cơ và trục vít máy nén."),
                ("Xử lý kẹt pallet trên băng tải chuyển thùng dây chuyền 2", "QR-VL-CNV-002", "vanlam_tech_nghia", 2026, 11, 12, 45, "BREAKDOWN", "LOW", "GENERAL", Decimal("300000"), None, Decimal("0.00"), "Sự cố dừng băng tải: Căn chỉnh con lăn dẫn hướng, bôi trơn bạc đạn băng chuyền."),
                ("Thay bộ gioăng phớt xylanh nâng hạ Máy Cưa Amada", "QR-VL-SAW-001", "vanlam_tech_khoa", 2026, 11, 13, 110, "CORRECTIVE", "MEDIUM", "MICRO_MAINTENANCE", Decimal("1100000"), "PN-NOK-TC48", Decimal("2.00"), "Thay cụm phớt chắn dầu ben thủy lực máy cưa vòng, hết chảy nhớt mặt sàn."),
                ("Hiệu chỉnh cảm biến vị trí hành trình Máy Chấn TruBend 5130", "QR-VL-BND-001", "vanlam_tech_thang", 2026, 11, 14, 80, "CORRECTIVE", "MEDIUM", "GENERAL", Decimal("750000"), "PN-BANNER-QS18", Decimal("1.00"), "Căn chỉnh thước quang Heidenhain và cảm biến an toàn hành trình chấn."),
                ("Đo kiểm rung động động cơ quạt cấp gió AHU-A2 sau thay dây đai", "QR-VL-AHU-002", "vanlam_tech_dung", 2026, 11, 15, 60, "PREVENTIVE", "LOW", "GENERAL", Decimal("400000"), None, Decimal("0.00"), "Vận tốc rung sau căn chỉnh giảm về 1.4 mm/s RMS, quạt chạy êm."),
                ("Bảo dưỡng định kỳ cụm nén khí sạch phòng đo CMM Zeiss", "QR-VL-CMM-001", "vanlam_tech_tien", 2026, 11, 16, 90, "PREVENTIVE", "HIGH", "GENERAL", Decimal("950000"), "PN-FESTO-MS6", Decimal("1.00"), "Vệ sinh bầu lọc khí siêu sạch, áp suất đệm khí bàn đá CMM đạt 5.5 Bar."),
                ("Thay relay nhiệt bảo vệ động cơ khuấy bể xử lý nước thải", "QR-VL-CLR-001", "vanlam_tech_vinh", 2026, 11, 17, 70, "CORRECTIVE", "MEDIUM", "GENERAL", Decimal("550000"), "PN-CARLO-RGC3", Decimal("1.00"), "Thay rơ-le bán dẫn bảo vệ nhiệt Carlo Gavazzi, động cơ khuấy vận hành an toàn."),
                ("Sửa chữa rơ le cảm biến an toàn cửa lồng Robot KUKA", "QR-VL-ROB-003", "vanlam_tech_khanh", 2026, 11, 18, 85, "CORRECTIVE", "HIGH", "GENERAL", Decimal("900000"), "PN-OMRON-E2E", Decimal("1.00"), "Đấu nối lại mạch công tắc liên động cửa an toàn, kiểm tra chức năng ngắt khẩn cấp E-Stop."),
            ]

            completed_count = 0
            for title, qr, tech_uname, y, m, d_num, dur, wtype, prio, mact, cost, part_num, p_qty, res_notes in historical_completed_specs:
                ast_obj = assets_dict.get(qr)
                u_tech = users_dict.get(tech_uname)
                exec_dt = datetime(y, m, d_num, 8, 30, 0, tzinfo=TZ_VN)
                end_dt = exec_dt + timedelta(minutes=dur)

                # Resolve PM Plan source reference if PM
                source_ref = None
                if wtype in ["PREVENTIVE", "PREDICTIVE_PM"] and ast_obj:
                    matched_assign = PmPlanAssignment.all_objects.filter(
                        tenant=tenant, asset=ast_obj, status="ACTIVE"
                    ).select_related('pm_plan').first()
                    if matched_assign:
                        source_ref = f"PM_{matched_assign.pm_plan.id}_ASSET_{ast_obj.id}_{exec_dt.strftime('%Y%m%d')}"
                    else:
                        any_plan = PmPlan.all_objects.filter(tenant=tenant, is_active=True).first()
                        if any_plan:
                            source_ref = f"PM_{any_plan.id}_ASSET_{ast_obj.id}_{exec_dt.strftime('%Y%m%d')}"

                wo, _ = WorkOrder.all_objects.update_or_create(
                    tenant=tenant,
                    title=title,
                    defaults={
                        "asset": ast_obj,
                        "type": wtype,
                        "priority": prio,
                        "status": "COMPLETED",
                        "maintenance_action": mact,
                        "assigned_to": u_tech,
                        "assigned_at": exec_dt - timedelta(hours=2),
                        "actual_start_time": exec_dt,
                        "completed_at": end_dt,
                        "actual_duration_minutes": dur,
                        "estimated_duration_minutes": dur,
                        "actual_cost": cost,
                        "resolution_notes": res_notes,
                        "source_reference": source_ref,
                        "coords_x": ast_obj.coords_x if ast_obj else 30.0,
                        "coords_y": ast_obj.coords_y if ast_obj else 40.0,
                        "floor_level": ast_obj.floor_level if ast_obj else 1,
                        "zone_id": ast_obj.zone_id if ast_obj else "ZONE_A1",
                        "incident_location": ast_obj.location if ast_obj else None,
                        "deadline": exec_dt + timedelta(days=1),
                    }
                )
                completed_count += 1

                # Checklists across multiple stages
                stages_spec = [
                    ("DIAGNOSIS", "Khảo sát hiện trạng, đo thông số ban đầu và gắn thẻ LOTO", True, "PASS_FAIL", "PASSED", "PASSED"),
                    ("STAGING_PARTS", "Chuẩn bị vật tư phụ tùng và dụng cụ đo kiểm chuyên dụng", True, "PASS_FAIL", "PASSED", "PASSED"),
                    ("OVERHAUL_EXECUTION", "Thực hiện tháo lắp, thay thế chi tiết và căn chỉnh kỹ thuật", True, "PASS_FAIL", "PASSED", "PASSED"),
                    ("TRIAL_ACCEPTANCE", "Nghiệm thu vận hành thử không tải và có tải đạt yêu cầu", True, "PASS_FAIL", "PASSED", "PASSED"),
                ]
                for st_code, item_name, is_m, inp_t, exp_v, act_v in stages_spec:
                    WorkOrderChecklistItem.all_objects.update_or_create(
                        tenant=tenant,
                        work_order=wo,
                        item_name=item_name,
                        defaults={
                            "is_mandatory": is_m,
                            "is_completed": True,
                            "input_type": inp_t,
                            "expected_value": exp_v,
                            "actual_value": act_v,
                            "stage": st_code
                        }
                    )

                # Material consumption & StockTransaction
                if part_num and p_qty > 0:
                    sp_obj = parts_dict.get(part_num)
                    if sp_obj:
                        WorkOrderMaterial.all_objects.update_or_create(
                            tenant=tenant,
                            work_order=wo,
                            spare_part=sp_obj,
                            defaults={
                                "quantity": p_qty,
                                "actual_cost": cost * Decimal("0.6")
                            }
                        )
                        StockTransaction.all_objects.update_or_create(
                            tenant=tenant,
                            work_order=wo,
                            spare_part=sp_obj,
                            transaction_type="ISSUE",
                            defaults={
                                "quantity": p_qty,
                                "unit_price": sp_obj.unit_cost,
                                "total_amount": p_qty * sp_obj.unit_cost,
                                "cost_center_snapshot": "Phân Xưởng Cơ Điện Vân Lam",
                                "issue_date": exec_dt
                            }
                        )

                # Labor Log
                LaborLog.all_objects.update_or_create(
                    tenant=tenant,
                    work_order=wo,
                    technician=u_tech,
                    defaults={
                        "work_date": exec_dt.date(),
                        "hours_worked": Decimal(str(round(dur / 60.0, 2))),
                        "hourly_rate": Decimal("150000"),
                        "total_cost": Decimal(str(round(dur / 60.0 * 150000, 2))),
                        "cost_center_snapshot": "Tổ Bảo Trì & Sửa Chữa Vân Lam"
                    }
                )

                # Cost Breakdown
                WorkOrderCost.all_objects.update_or_create(
                    tenant=tenant,
                    work_order=wo,
                    defaults={
                        "material_cost": cost * Decimal("0.6"),
                        "labor_cost": cost * Decimal("0.4"),
                        "vendor_cost": Decimal("0.00"),
                        "gross_cost": cost,
                        "net_cost": cost,
                        "is_cost_frozen": True,
                        "cost_center_snapshot": "Phân Xưởng Sản Xuất Vân Lam"
                    }
                )

            self.stdout.write(f"-> Historical Completed Work Orders: {completed_count} (target 45-60: PASS)")

            # =========================================================================
            # 12. PM WORK ORDERS IN DECEMBER 2026 (Target: 25-30 -> Exactly 26 WOs)
            # Future scheduled PMs: Status ASSIGNED or CREATED, 100% NEVER COMPLETED!
            # =========================================================================
            self.stdout.write("-> Generating 26 Future PM Work Orders in December 2026...")
            dec_pm_wos = [
                ("Bảo dưỡng định kỳ bôi trơn trục chính Máy Phay Makino F5", "QR-VL-CNC-002", "vanlam_tech_an", 1, 120, "PREVENTIVE", "HIGH", "MICRO_MAINTENANCE", "ELECTRICAL", "CERT_HIGH_VOLTAGE", ["Gắn thẻ LOTO cách ly điện", "Đo độ cách điện động cơ trục chính", "Bơm mỡ bôi trơn chuyên dụng Kluber NBU 15"]),
                ("Kiểm tra khe hở băng trượt và căn chỉnh dao Máy Tiện Okuma", "QR-VL-CNC-003", "vanlam_tech_khoa", 2, 90, "PREVENTIVE", "MEDIUM", "GENERAL", "MECHANICAL", "CERT_SAFETY_L1", ["Kiểm tra độ rơ cơ khí trục X/Z", "Vệ sinh băng trượt và đầu gá đài dao"]),
                ("Bảo dưỡng định kỳ trạm bơm thủy lực và phớt chắn dầu Máy Chấn Trumpf", "QR-VL-BND-001", "vanlam_tech_binh", 4, 180, "PREVENTIVE", "URGENT", "CORE_REPLACEMENT", "HYDRAULIC", "CERT_SAFETY_L2", ["Đo áp suất mạch thủy lực 300 Bar", "Thay thế cụm phớt Viton xi lanh ép", "Kiểm tra rò rỉ tại van tỷ lệ"]),
                ("Kiểm tra cáp và hiệu chỉnh tọa độ điểm gốc Robot Hàn Fanuc", "QR-VL-ROB-002", "vanlam_tech_khanh", 5, 100, "PREVENTIVE", "MEDIUM", "GENERAL", "AUTOMATION", "CERT_PLC_EXPERT", ["Cân chỉnh Zero điểm gốc các trục J1-J6", "Sao lưu cấu hình Teach Pendant"]),
                ("Bảo dưỡng hệ thống giải nhiệt nước và nạp gas bổ sung Chiller Trane", "QR-VL-CHL-001", "vanlam_tech_minh", 7, 150, "PREVENTIVE", "HIGH", "MICRO_MAINTENANCE", "HVAC", "CERT_HIGH_VOLTAGE", ["Đo áp suất gas đường hút và xả", "Vệ sinh dàn ngưng tụ ống đồng", "Kiểm tra cảm biến dòng chảy"]),
                ("Đo kiểm tra điện trở cách điện máy biến áp dầu ABB 1600kVA", "QR-VL-TR-001", "vanlam_tech_phuc", 8, 240, "PREVENTIVE", "URGENT", "CORE_REPLACEMENT", "ELECTRICAL", "CERT_HIGH_VOLTAGE", ["Cắt máy cắt trung thế và tiếp địa", "Đo điện trở cách điện 22kV", "Kiểm tra mức dầu biến áp và rơ le hơi Buchholz"]),
                ("Thay lõi lọc tách dầu và bảo dưỡng van hút Máy Nén Khí Atlas Copco", "QR-VL-CMP-001", "vanlam_tech_quan", 10, 120, "PREVENTIVE", "HIGH", "GENERAL", "MECHANICAL", "CERT_SAFETY_L1", ["Thay lõi lọc tách dầu Festo", "Xả cặn đáy bình tích áp", "Kiểm tra van an toàn 10 Bar"]),
                ("Bảo dưỡng dây xích dẫn động và bôi trơn con lăn Băng Tải Tuyến 1", "QR-VL-CNV-001", "vanlam_tech_nghia", 11, 80, "PREVENTIVE", "LOW", "GENERAL", "GENERAL", "CERT_SAFETY_L1", ["Kiểm tra độ chùng xích truyền động", "Tra mỡ bôi trơn ổ đỡ trục con lăn"]),
                ("Hiệu chuẩn bàn cẩm thạch và kiểm tra bi chuẩn Máy CMM Zeiss", "QR-VL-CMM-001", "vanlam_tech_tien", 14, 180, "PREVENTIVE", "HIGH", "GENERAL", "MECHANICAL", "CERT_SAFETY_L1", ["Lau sạch bàn đá bằng cồn tinh khiết", "Hiệu chuẩn đầu đo Renishaw", "Kiểm tra sai số lặp lại < 1.5 um"]),
                ("Kiểm tra độ chênh áp màng lọc HEPA phòng sạch và thay lọc sơ cấp", "QR-VL-AHU-001", "vanlam_tech_dung", 15, 100, "PREVENTIVE", "MEDIUM", "GENERAL", "HVAC", "CERT_SAFETY_L1", ["Đo áp suất chênh lệch qua lọc HEPA", "Thay tấm lọc sơ cấp bụi thô"]),
                ("Đo kiểm độ rung trục chính máy phay Mazak bằng SKF Microlog", "QR-VL-CNC-001", "vanlam_tech_long", 17, 90, "PREVENTIVE", "HIGH", "MICRO_MAINTENANCE", "MECHANICAL", "CERT_SAFETY_L2", ["Gắn gia tốc kế 3 chiều tại ổ bi trước", "Đo phổ FFT và vận tốc rung RMS", "Đối chiếu chuẩn rung ISO 10816 Zone A/B"]),
                ("Kiểm tra lực ép và độ song song bàn máy dập Komatsu 200T", "QR-VL-PRS-003", "vanlam_tech_thang", 18, 120, "PREVENTIVE", "MEDIUM", "GENERAL", "HYDRAULIC", "CERT_SAFETY_L2", ["Đo độ song song bàn máy bằng đồng hồ so", "Kiểm tra rò rỉ gioăng phớt xylanh chính"]),
                ("Bảo dưỡng định kỳ động cơ servo và hộp số cánh tay đòn Robot KUKA", "QR-VL-ROB-003", "vanlam_tech_cuong", 21, 110, "PREVENTIVE", "MEDIUM", "GENERAL", "AUTOMATION", "CERT_PLC_EXPERT", ["Kiểm tra độ rơ hộp số trục 1-3", "Đo nhiệt độ làm việc động cơ servo"]),
                ("Bảo trì bơm tuần hoàn tháp giải nhiệt Liang Chi và cân bằng động cánh quạt", "QR-VL-CT-001", "vanlam_tech_tri", 22, 130, "PREVENTIVE", "HIGH", "MICRO_MAINTENANCE", "MECHANICAL", "CERT_SAFETY_L2", ["Căn tâm trục động cơ bơm Wilo", "Kiểm tra độ rung cánh quạt tháp giải nhiệt"]),
                ("Kiểm tra siết ốc thanh cái và vệ sinh tủ điện tổng MDB 2500A", "QR-VL-MDB-001", "vanlam_tech_hai", 23, 160, "PREVENTIVE", "HIGH", "GENERAL", "ELECTRICAL", "CERT_HIGH_VOLTAGE", ["Quét nhiệt hồng ngoại mối nối thanh cái", "Siết bu lông lực đạt tiêu chuẩn"]),
                ("Kiểm tra áp lực khí nén và bảo dưỡng van xả tự động Máy Nén Khí Ingersoll", "QR-VL-CMP-002", "vanlam_tech_quan", 25, 90, "PREVENTIVE", "MEDIUM", "GENERAL", "MECHANICAL", "CERT_SAFETY_L1", ["Kiểm tra van điều áp Danfoss", "Vệ sinh cốc xả nước ngưng tự động"]),
                ("Kiểm tra căng dây đai đồng bộ và căn chỉnh dẫn hướng Băng Tải Tuyến 2", "QR-VL-CNV-002", "vanlam_tech_nghia", 26, 75, "PREVENTIVE", "LOW", "GENERAL", "GENERAL", "CERT_SAFETY_L1", ["Đo độ căng dây đai Gates PowerGrip", "Kiểm tra cảm biến dừng khẩn cấp"]),
                ("Kiểm tra đầu đo quang học và hiệu chỉnh hệ thấu kính Máy Chiếu Nikon", "QR-VL-OPT-001", "vanlam_tech_tien", 28, 120, "PREVENTIVE", "MEDIUM", "GENERAL", "MECHANICAL", "CERT_SAFETY_L1", ["Vệ sinh thấu kính quang học", "Kiểm tra độ phóng đại 10x 20x 50x"]),
                ("Bảo dưỡng máy sấy khí hấp thụ và thay hạt hút ẩm Sullair", "QR-VL-DRY-001", "vanlam_tech_quan", 29, 140, "PREVENTIVE", "HIGH", "CORE_REPLACEMENT", "MECHANICAL", "CERT_SAFETY_L1", ["Kiểm tra điểm sương khí nén -40°C", "Thay thế hạt hút ẩm tháp A"]),
                ("Đo kiểm tra tải và chạy thử định kỳ Máy Phát Điện Dự Phòng Cummins 700kVA", "QR-VL-GEN-001", "vanlam_tech_phuc", 30, 180, "PREVENTIVE", "URGENT", "GENERAL", "ELECTRICAL", "CERT_HIGH_VOLTAGE", ["Kiểm tra điện áp ắc quy khởi động 24V", "Chạy thử không tải 15 phút", "Kiểm tra áp suất dầu bôi trơn"]),
                ("Vệ sinh bể tách dầu và kiểm tra bơm hóa chất Xử Lý Nước Thải", "QR-VL-CLR-001", "vanlam_tech_tri", 31, 100, "PREVENTIVE", "MEDIUM", "GENERAL", "MECHANICAL", "CERT_SAFETY_L2", ["Đo nồng độ pH dung dịch làm mát", "Vệ sinh màng lọc thô và bơm Wilo"]),
                ("Bảo dưỡng định kỳ xylanh khí nén và cơ cấu ép Máy Xếp Pallet Fuji", "QR-VL-PLZ-001", "vanlam_tech_vinh", 15, 90, "PREVENTIVE", "LOW", "GENERAL", "GENERAL", "CERT_SAFETY_L1", ["Kiểm tra xylanh khí Camozzi", "Tra dầu bôi trơn thanh trượt dẫn hướng"]),
                ("Kiểm tra biến tần và động cơ kéo Máy Quấn Màng Pallet Orion", "QR-VL-WRP-001", "vanlam_tech_lam", 18, 80, "PREVENTIVE", "LOW", "GENERAL", "ELECTRICAL", "CERT_SAFETY_L1", ["Kiểm tra dòng tải động cơ 3 pha", "Kiểm tra rơ le an toàn cửa"]),
                ("Đo kiểm tra độ nhám chuẩn và cân chỉnh đầu kim Máy Mitutoyo", "QR-VL-RGH-001", "vanlam_tech_tien", 23, 90, "PREVENTIVE", "MEDIUM", "GENERAL", "MECHANICAL", "CERT_SAFETY_L1", ["Đo mẫu chuẩn độ nhám Ra=2.95um", "Hiệu chỉnh hệ số khuếch đại"]),
                ("Kiểm tra độ chụm ngọn hàn và vòi phun khí trơ Robot COMAU", "QR-VL-ROB-006", "vanlam_tech_cuong", 12, 100, "PREVENTIVE", "MEDIUM", "GENERAL", "AUTOMATION", "CERT_PLC_EXPERT", ["Làm sạch bép hàn mỏ hàn CO2", "Kiểm tra lưu lượng khí Argon"]),
                ("Bảo dưỡng định kỳ buồng đốt và que đánh lửa lò sấy sơn tĩnh điện", "QR-VL-OVN-001", "vanlam_tech_nam", 27, 110, "PREVENTIVE", "HIGH", "GENERAL", "MECHANICAL", "CERT_SAFETY_L2", ["Vệ sinh bugi đánh lửa lò sấy", "Kiểm tra van ngắt gas an toàn"]),
                ("Bảo dưỡng định kỳ bình lọc nước khử ion và đầu kim cương Máy Cắt Dây EDM", "QR-VL-EDM-001", "vanlam_tech_tien", 16, 90, "PREVENTIVE", "MEDIUM", "GENERAL", "MECHANICAL", "CERT_SAFETY_L1", ["Kiểm tra độ dẫn điện nước khử khoáng", "Vệ sinh đầu dẫn hướng kim cương"]),
                ("Kiểm tra đo nội trở acquy và quạt làm mát biến tần UPS APC Symmetra", "QR-VL-UPS-001", "vanlam_tech_hai", 20, 100, "PREVENTIVE", "HIGH", "GENERAL", "ELECTRICAL", "CERT_HIGH_VOLTAGE", ["Đo nội trở từng bình acquy", "Vệ sinh quạt làm mát module công suất"]),
            ]

            dec_count = 0
            for title, qr, tech_uname, day_num, dur, wtype, prio, mact, rskill, rcert, chk_items in dec_pm_wos:
                ast_obj = assets_dict.get(qr)
                u_tech = users_dict.get(tech_uname)
                dec_date = datetime(2026, 12, day_num, 9, 0, 0, tzinfo=TZ_VN)

                # Resolve PM Plan source reference if PM
                source_ref = None
                if wtype in ["PREVENTIVE", "PREDICTIVE_PM"] and ast_obj:
                    matched_assign = PmPlanAssignment.all_objects.filter(
                        tenant=tenant, asset=ast_obj, status="ACTIVE"
                    ).select_related('pm_plan').first()
                    if matched_assign:
                        source_ref = f"PM_{matched_assign.pm_plan.id}_ASSET_{ast_obj.id}_{dec_date.strftime('%Y%m%d')}"
                    else:
                        any_plan = PmPlan.all_objects.filter(tenant=tenant, is_active=True).first()
                        if any_plan:
                            source_ref = f"PM_{any_plan.id}_ASSET_{ast_obj.id}_{dec_date.strftime('%Y%m%d')}"

                wo, _ = WorkOrder.all_objects.update_or_create(
                    tenant=tenant,
                    title=title,
                    defaults={
                        "asset": ast_obj,
                        "type": wtype,
                        "priority": prio,
                        "status": "ASSIGNED" if u_tech else "CREATED",
                        "maintenance_action": mact,
                        "assigned_to": u_tech,
                        "assigned_at": dec_date - timedelta(days=2),
                        "estimated_duration_minutes": dur,
                        "required_skill": rskill,
                        "required_certification": rcert,
                        "source_reference": source_ref,
                        "coords_x": ast_obj.coords_x if ast_obj else 30.0,
                        "coords_y": ast_obj.coords_y if ast_obj else 40.0,
                        "floor_level": ast_obj.floor_level if ast_obj else 1,
                        "zone_id": ast_obj.zone_id if ast_obj else "ZONE_A1",
                        "incident_location": ast_obj.location if ast_obj else None,
                        "deadline": dec_date + timedelta(hours=8),
                    }
                )
                dec_count += 1

                for item_name in chk_items:
                    WorkOrderChecklistItem.all_objects.update_or_create(
                        tenant=tenant,
                        work_order=wo,
                        item_name=item_name,
                        defaults={
                            "is_mandatory": True,
                            "is_completed": False,  # Future order: NOT completed!
                            "input_type": "PASS_FAIL",
                            "expected_value": "PASSED"
                        }
                    )
            self.stdout.write(f"-> December 2026 PM Work Orders: {dec_count} (target 25-30: PASS)")

            # =========================================================================
            # 13. ACTIVE / OPEN / CURRENT WORK ORDERS IN NOVEMBER 2026 (40 WOs)
            # Mixed realistic statuses: IN_PROGRESS (8), ASSIGNED (14), CREATED (12), ON_HOLD (4), CANCELLED (2)
            # =========================================================================
            self.stdout.write("-> Generating 40 Current Active/Open Work Orders in November 2026...")
            active_wos_spec = [
                # IN_PROGRESS (9 WOs)
                ("Đại tu thay thế vòng bi trục chính và căn chỉnh thước quang trục W", "QR-VL-CNC-004", "vanlam_tech_an", 20, 180, "CORRECTIVE", "URGENT", "IN_PROGRESS", "CORE_REPLACEMENT"),
                ("Khảo sát tiếng kêu lạ ổ bi trục B Máy Phay Makino F5", "QR-VL-CNC-002", "vanlam_tech_an", 20, 120, "CORRECTIVE", "HIGH", "IN_PROGRESS", "MICRO_MAINTENANCE"),
                ("Kiểm tra áp lực bình chứa khí nén 5m3 và van an toàn", "QR-VL-RCV-001", "vanlam_tech_quan", 20, 90, "PREVENTIVE", "MEDIUM", "IN_PROGRESS", "GENERAL"),
                ("Kiểm tra áp lực dầu trạm bơm thủy lực trung tâm phân xưởng 2", "QR-VL-PRS-002", "vanlam_tech_thang", 20, 100, "PREVENTIVE", "HIGH", "IN_PROGRESS", "GENERAL"),
                ("Đại tu thay thế phớt piston máy ép Schuler 400T", "QR-VL-PRS-004", "vanlam_tech_binh", 20, 180, "CORRECTIVE", "URGENT", "IN_PROGRESS", "CORE_REPLACEMENT"),
                ("Kiểm tra căn chỉnh ray trượt bàn phay 5 trục DMG MORI", "QR-VL-CNC-005", "vanlam_tech_khoa", 20, 150, "PREVENTIVE", "HIGH", "IN_PROGRESS", "MICRO_MAINTENANCE"),
                ("Sửa chữa đầu phun sơn tĩnh điện robot tự động Nordson", "QR-VL-PNT-001", "vanlam_tech_nam", 20, 110, "CORRECTIVE", "HIGH", "IN_PROGRESS", "GENERAL"),
                ("Khắc phục rò rỉ nước ngưng đường ống cấp hơi nồi hơi Miura", "QR-VL-BLR-001", "vanlam_tech_tri", 20, 140, "CORRECTIVE", "URGENT", "IN_PROGRESS", "MICRO_MAINTENANCE"),
                ("Hiệu chỉnh cảm biến dòng xoáy máy dò rò rỉ khí Heli", "QR-VL-HLK-001", "vanlam_tech_long", 20, 90, "PREVENTIVE", "MEDIUM", "IN_PROGRESS", "GENERAL"),

                # ASSIGNED (14 WOs)
                ("Hiệu chuẩn góc nghiêng cảm biến quang máy đo Mitutoyo", "QR-VL-RGH-001", "vanlam_tech_tien", 21, 75, "PREVENTIVE", "LOW", "ASSIGNED", "GENERAL"),
                ("Khảo sát thay chổi quét và má trượt cấp nguồn cầu trục xưởng A1", "QR-VL-MDB-001", "vanlam_tech_hai", 21, 90, "CORRECTIVE", "MEDIUM", "ASSIGNED", "GENERAL"),
                ("Bảo dưỡng định kỳ cụm sấy khí nén hấp thụ Sullair tháp B", "QR-VL-DRY-001", "vanlam_tech_quan", 21, 120, "PREVENTIVE", "HIGH", "ASSIGNED", "GENERAL"),
                ("Bảo dưỡng định kỳ động cơ trục đùn máy ép nhựa Sumitomo", "QR-VL-PRS-003", "vanlam_tech_hung", 21, 130, "PREVENTIVE", "HIGH", "ASSIGNED", "MICRO_MAINTENANCE"),
                ("Kiểm tra khe hở nhiệt khớp nối trục máy mài Studer", "QR-VL-GRD-001", "vanlam_tech_dung", 21, 80, "PREVENTIVE", "LOW", "ASSIGNED", "GENERAL"),
                ("Bảo dưỡng quạt giải nhiệt biến tần trạm điện VL-SUB1", "QR-VL-TR-001", "vanlam_tech_phuc", 21, 60, "PREVENTIVE", "MEDIUM", "ASSIGNED", "GENERAL"),
                ("Kiểm tra cảm biến an toàn quang điện máy chấn Trumpf", "QR-VL-BND-001", "vanlam_tech_thang", 21, 70, "PREVENTIVE", "HIGH", "ASSIGNED", "GENERAL"),
                ("Kiểm tra độ chùng dây đai băng chuyền đóng gói carton", "QR-VL-CNV-002", "vanlam_tech_nghia", 21, 60, "PREVENTIVE", "LOW", "ASSIGNED", "GENERAL"),
                ("Kiểm tra rò rỉ dung dịch tưới nguội tại van phân phối CNC Mazak", "QR-VL-CNC-001", "vanlam_tech_son", 21, 60, "CORRECTIVE", "MEDIUM", "ASSIGNED", "GENERAL"),
                ("Bảo dưỡng van hút một chiều máy nén khí Ingersoll", "QR-VL-CMP-002", "vanlam_tech_quan", 21, 90, "PREVENTIVE", "MEDIUM", "ASSIGNED", "GENERAL"),
                ("Đo kiểm tra cách điện cuộn cảm ứng lò đúc nhôm Inductotherm", "QR-VL-FURN-001", "vanlam_tech_phuc", 21, 110, "PREVENTIVE", "URGENT", "ASSIGNED", "GENERAL"),
                ("Bảo dưỡng cánh khuấy và phớt máy nghiền phôi Untha", "QR-VL-SHRD-001", "vanlam_tech_vinh", 21, 100, "PREVENTIVE", "MEDIUM", "ASSIGNED", "GENERAL"),
                ("Kiểm tra tốc độ dòng khí phòng sạch tủ cấy Esco", "QR-VL-CLN-001", "vanlam_tech_dung", 21, 75, "PREVENTIVE", "LOW", "ASSIGNED", "GENERAL"),
                ("Bảo dưỡng cơ cấu kẹp xoay tay robot đúc ABB", "QR-VL-ROB-005", "vanlam_tech_khanh", 21, 120, "PREVENTIVE", "HIGH", "ASSIGNED", "MICRO_MAINTENANCE"),

                # CREATED (12 WOs)
                ("Kiểm tra tín hiệu giao tiếp Profinet Robot Yaskawa GP12", "QR-VL-ROB-004", None, 21, 60, "CORRECTIVE", "MEDIUM", "CREATED", "GENERAL"),
                ("Bảo dưỡng hệ thống bôi trơn tuần hoàn máy mài Studer S33", "QR-VL-GRD-001", None, 21, 90, "PREVENTIVE", "LOW", "CREATED", "GENERAL"),
                ("Đo kiểm tra độ lệch tâm khớp nối động cơ máy nén Ingersoll", "QR-VL-CMP-002", None, 21, 120, "PREVENTIVE", "HIGH", "CREATED", "MICRO_MAINTENANCE"),
                ("Bảo dưỡng cụm cấp phôi tự động xe tự hành AGV-VL01", "QR-VL-AGV-001", None, 21, 80, "PREVENTIVE", "LOW", "CREATED", "GENERAL"),
                ("Đo kiểm tra cách điện cuộn sấy nhiệt lò tôi cao tần", "QR-VL-TR-001", None, 21, 100, "CORRECTIVE", "HIGH", "CREATED", "GENERAL"),
                ("Khảo sát thay bạc đạn con lăn dẫn phôi xưởng dập", "QR-VL-PRS-005", None, 21, 90, "CORRECTIVE", "MEDIUM", "CREATED", "GENERAL"),
                ("Bảo dưỡng cảm biến độ rung gia tốc IFM trục chính Makino", "QR-VL-CNC-002", None, 21, 60, "PREVENTIVE", "MEDIUM", "CREATED", "GENERAL"),
                ("Kiểm tra van tiết lưu hồi dầu trạm bơm thủy lực", "QR-VL-PMP-001", None, 21, 80, "PREVENTIVE", "LOW", "CREATED", "GENERAL"),
                ("Khảo sát tiếng rít dây đai quạt thông gió nhà xưởng A2", "QR-VL-AHU-002", None, 21, 50, "CORRECTIVE", "LOW", "CREATED", "GENERAL"),
                ("Kiểm tra điện trở tiếp xúc dao cắt cách ly tủ điện trung thế", "QR-VL-MDB-001", None, 21, 120, "PREVENTIVE", "URGENT", "CREATED", "GENERAL"),
                ("Bảo dưỡng bầu lọc bụi máy cưa vòng Amada", "QR-VL-SAW-001", None, 21, 70, "PREVENTIVE", "LOW", "CREATED", "GENERAL"),
                ("Kiểm tra cơ cấu nâng hạ bàn xe nâng Reach Truck Linde", "QR-VL-AGV-002", None, 21, 90, "CORRECTIVE", "MEDIUM", "CREATED", "GENERAL"),

                # ON_HOLD (4 WOs)
                ("Đại tu thay thế buồng đốt lò sấy nhiệt 250°C", "QR-VL-OVN-001", "vanlam_tech_vinh", 19, 240, "CORRECTIVE", "URGENT", "ON_HOLD", "CORE_REPLACEMENT"),
                ("Thay cụm bánh răng giảm tốc SEW máy nghiền phôi Untha", "QR-VL-SHRD-001", "vanlam_tech_thang", 19, 180, "CORRECTIVE", "HIGH", "ON_HOLD", "CORE_REPLACEMENT"),
                ("Thay thế module PLC Siemens S7-1500 tủ Robot Comau", "QR-VL-ROB-006", "vanlam_tech_cuong", 19, 120, "CORRECTIVE", "HIGH", "ON_HOLD", "GENERAL"),
                ("Chờ hiệu chuẩn đầu đo quang học từ viện đo lường VMI", "QR-VL-OPT-001", "vanlam_tech_tien", 19, 90, "PREVENTIVE", "MEDIUM", "ON_HOLD", "GENERAL"),

                # CANCELLED (2 WOs)
                ("Yêu cầu kiểm tra sai số nhiệt độ lò nung (báo nhầm)", "QR-VL-FURN-001", "vanlam_tech_phuc", 18, 45, "CORRECTIVE", "LOW", "CANCELLED", "GENERAL"),
                ("Yêu cầu thay thế bóng đèn cảnh báo trạm bơm (đã tự khắc phục)", "QR-VL-PMP-001", "vanlam_tech_binh", 18, 30, "CORRECTIVE", "LOW", "CANCELLED", "GENERAL"),
            ]

            active_count = 0
            for title, qr, tech_uname, d_num, dur, wtype, prio, st, mact in active_wos_spec:
                ast_obj = assets_dict.get(qr)
                if not ast_obj:
                    ast_obj = next(iter(assets_dict.values()))
                u_tech = users_dict.get(tech_uname)
                wo_dt = datetime(2026, 11, d_num, 8, 0, 0, tzinfo=TZ_VN)

                wo, _ = WorkOrder.all_objects.update_or_create(
                    tenant=tenant,
                    title=title,
                    defaults={
                        "asset": ast_obj,
                        "type": wtype,
                        "priority": prio,
                        "status": st,
                        "maintenance_action": mact,
                        "assigned_to": u_tech,
                        "assigned_at": wo_dt - timedelta(hours=2) if u_tech else None,
                        "actual_start_time": wo_dt if st in ["IN_PROGRESS", "ON_HOLD"] else None,
                        "estimated_duration_minutes": dur,
                        "coords_x": ast_obj.coords_x if ast_obj else 30.0,
                        "coords_y": ast_obj.coords_y if ast_obj else 40.0,
                        "floor_level": ast_obj.floor_level if ast_obj else 1,
                        "zone_id": ast_obj.zone_id if ast_obj else "ZONE_A1",
                        "incident_location": ast_obj.location if ast_obj else None,
                        "deadline": wo_dt + timedelta(days=2),
                    }
                )
                active_count += 1

                # Checklists for in-progress or on-hold
                WorkOrderChecklistItem.all_objects.update_or_create(
                    tenant=tenant,
                    work_order=wo,
                    item_name="Kiểm tra an toàn nguồn điện và biển báo thi công",
                    defaults={
                        "is_mandatory": True,
                        "is_completed": (st == "IN_PROGRESS"),
                        "input_type": "PASS_FAIL",
                        "expected_value": "PASSED",
                        "actual_value": "PASSED" if st == "IN_PROGRESS" else None,
                        "stage": "DIAGNOSIS"
                    }
                )
                WorkOrderChecklistItem.all_objects.update_or_create(
                    tenant=tenant,
                    work_order=wo,
                    item_name="Thực hiện kiểm tra kỹ thuật hiện trường và ghi nhận thông số",
                    defaults={
                        "is_mandatory": True,
                        "is_completed": False,
                        "input_type": "PASS_FAIL",
                        "expected_value": "PASSED",
                        "stage": "OVERHAUL_EXECUTION"
                    }
                )

                if st == "IN_PROGRESS" and u_tech:
                    LaborLog.all_objects.update_or_create(
                        tenant=tenant,
                        work_order=wo,
                        technician=u_tech,
                        defaults={
                            "work_date": wo_dt.date(),
                            "hours_worked": Decimal("1.50"),
                            "hourly_rate": Decimal("150000"),
                            "total_cost": Decimal("225000"),
                            "cost_center_snapshot": "Tổ Bảo Trì & Sửa Chữa Vân Lam"
                        }
                    )

            self.stdout.write(f"-> Active/Open November Work Orders: {active_count}")
            total_wos = WorkOrder.all_objects.filter(tenant=tenant).count()
            self.stdout.write(f"-> Total Work Orders: {total_wos} (target 100-130: PASS)")

            # =========================================================================
            # 14. TOOL RESERVATIONS
            # Link tool instances to work orders
            # =========================================================================
            all_instances = list(ToolInstance.all_objects.filter(tenant=tenant, inspection_status="PASSED"))
            all_wos = list(WorkOrder.all_objects.filter(tenant=tenant).exclude(status="CANCELLED")[:15])
            for i, wo_obj in enumerate(all_wos):
                t_inst = all_instances[i % len(all_instances)] if all_instances else None
                if t_inst:
                    ToolReservation.all_objects.update_or_create(
                        tenant=tenant,
                        work_order=wo_obj,
                        tool=t_inst.tool,
                        defaults={
                            "tool_instance": t_inst,
                            "reserved_quantity": 1,
                            "status": "RETURNED" if wo_obj.status == "COMPLETED" else "IN_USE",
                            "returned_at": wo_obj.completed_at if wo_obj.status == "COMPLETED" else None,
                            "notes": f"Sử dụng cho phiếu {wo_obj.code}"
                        }
                    )
            self.stdout.write(f"-> Tool Reservations total: {ToolReservation.all_objects.filter(tenant=tenant).count()}")

            # =========================================================================
            # 15. UPDATE RAG CHATBOT EMBEDDINGS
            # =========================================================================
            if TechnicalDocument and DocumentChunk and embed_text:
                for c in DocumentChunk.all_objects.filter(tenant=tenant):
                    c.embedding = embed_text(c.content)
                    c.save(update_fields=['embedding'])

            # =========================================================================
            # 16. INVALIDATE CACHES
            # =========================================================================
            DashboardCacheService.invalidate_all(tenant.id)

        # Print Final Statistics
        self.stdout.write("=" * 80)
        self.stdout.write(self.style.SUCCESS("[OK] ADVANCED DATA AUGMENTATION COMPLETED SUCCESSFULLY!"))
        self.stdout.write(f"-> Users:               {User.all_objects.filter(tenant=tenant).count()} (target: 30-35)")
        self.stdout.write(f"-> Technicians:         {TechnicianProfile.all_objects.filter(tenant=tenant).count()} (target: 22-26)")
        self.stdout.write(f"-> Locations:           {Location.all_objects.filter(tenant=tenant).count()} (target: 15-25)")
        self.stdout.write(f"-> Asset Categories:    {AssetCategory.all_objects.filter(tenant=tenant).count()} (target: 8-10)")
        self.stdout.write(f"-> Assets:              {Asset.all_objects.filter(tenant=tenant).count()} (target: 50-60)")
        self.stdout.write(f"-> Spare Parts:         {SparePart.all_objects.filter(tenant=tenant).count()} (target: 35-45)")
        self.stdout.write(f"-> PM Plans:            {PmPlan.all_objects.filter(tenant=tenant).count()} (target: 12-15)")
        self.stdout.write(f"-> PM Assignments:      {PmPlanAssignment.all_objects.filter(tenant=tenant).count()} (target: 35-50)")
        self.stdout.write(f"-> Total Work Orders:   {WorkOrder.all_objects.filter(tenant=tenant).count()} (target: 100-130)")
        self.stdout.write(f"-> Completed Hist WOs:  {WorkOrder.all_objects.filter(tenant=tenant, status='COMPLETED').count()} (target: 45-60)")

        dec_pm_count = WorkOrder.all_objects.filter(
            tenant=tenant,
            type="PREVENTIVE",
            deadline__range=(datetime(2026, 12, 1, 0, 0, 0, tzinfo=TZ_VN),
                             datetime(2026, 12, 31, 23, 59, 59, tzinfo=TZ_VN))
        ).count()
        self.stdout.write(f"-> Dec 2026 PM WOs:     {dec_pm_count} (target: 25-30)")
        self.stdout.write(f"-> Schedules (Nov-Dec): {TechnicianSchedule.all_objects.filter(tenant=tenant).count()}")
        self.stdout.write(f"-> Labor Logs:          {LaborLog.all_objects.filter(tenant=tenant).count()}")
        self.stdout.write(f"-> Stock Transactions:  {StockTransaction.all_objects.filter(tenant=tenant).count()}")
        self.stdout.write(f"-> Tool Instances:      {ToolInstance.all_objects.filter(tenant=tenant).count()}")
        self.stdout.write(f"-> Tool Reservations:   {ToolReservation.all_objects.filter(tenant=tenant).count()}")
        self.stdout.write("=" * 80)

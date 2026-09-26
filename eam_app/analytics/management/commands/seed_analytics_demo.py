import uuid
from decimal import Decimal
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.models import Tenant, AuditLog
from users.models import User, Role
from assets.models import Asset, AssetCategory, Location, SparePart, StockTransaction
from workorders.models import WorkOrder, WorkOrderMaterial, LaborLog
from analytics.services import DashboardCacheService


class Command(BaseCommand):
    help = 'Seeds rich, comprehensive test scenarios for Dashboard KPIs and Enterprise Reports'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant-code',
            type=str,
            default='VF_HP',
            help='Tenant code to seed data into (default: VF_HP)'
        )

    def handle(self, *args, **options):
        tenant_code = options['tenant_code']
        self.stdout.write(f"Seeding Analytics and Reports demo data for tenant [{tenant_code}]...")

        with transaction.atomic():
            tenant, _ = Tenant.objects.get_or_create(
                tenant_code=tenant_code,
                defaults={
                    'name': 'Tổ Hợp Cơ Khí & Ô Tô Hải Phòng',
                    'timezone': 'Asia/Ho_Chi_Minh',
                    'service_plan': 'ENTERPRISE',
                    'status': 'ACTIVE'
                }
            )

            # 1. Locations (Workshops / Cost Centers)
            loc_names = [
                "Xưởng Dập Thép (Stamping Shop)",
                "Xưởng Hàn Thân Xe (Body Shop)",
                "Xưởng Sơn Tĩnh Điện (Paint Shop)",
                "Xưởng Động Cơ & Truyền Động (Powertrain)",
                "Xưởng Lắp Ráp Hoàn Thiện (General Assembly)"
            ]
            locations = {}
            for name in loc_names:
                loc, _ = Location.all_objects.get_or_create(
                    tenant=tenant,
                    name=name,
                    defaults={'is_active': True, 'description': f'Trung tâm chi phí {name}'}
                )
                locations[name] = loc

            # 2. Categories
            cat_names = ["Máy Dập & Tạo Hình", "Robot Hàn Tự Động", "Buồng Sơn & Sấy", "Hệ Thống Băng Tải", "Cơ Khí Tiện Phay"]
            categories = {}
            for cname in cat_names:
                cat, _ = AssetCategory.all_objects.get_or_create(
                    tenant=tenant,
                    name=cname,
                    defaults={'is_active': True}
                )
                categories[cname] = cat

            # 3. Staff & Technicians
            tech_role, _ = Role.all_objects.get_or_create(
                tenant=tenant,
                name='TECHNICIAN',
                defaults={'description': 'Kỹ thuật viên bảo trì'}
            )
            admin_user = User.all_objects.filter(tenant=tenant).first()
            if not admin_user:
                admin_user = User.all_objects.create_user(
                    tenant=tenant,
                    username=f"admin_{tenant_code.lower()}",
                    email=f"admin@{tenant_code.lower()}.vn",
                    password="password123"
                )

            tech_user, _ = User.all_objects.get_or_create(
                tenant=tenant,
                username=f"tech_lead_{tenant_code.lower()}",
                defaults={'email': f"tech@{tenant_code.lower()}.vn"}
            )
            tech_user.roles.add(tech_role)

            now = timezone.now()
            today = now.date()

            # 4. Assets Covering Diverse Financial & Operational Scenarios
            assets_spec = [
                # Scenario A: High-value modern machine in normal straight-line depreciation
                {
                    "name": "Máy Dập Thủy Lực Komatsu 1200T",
                    "qr_code": f"AST-{tenant_code}-01",
                    "status": "OPERATIONAL",
                    "category": categories["Máy Dập & Tạo Hình"],
                    "location": locations["Xưởng Dập Thép (Stamping Shop)"],
                    "purchase_date": today - timedelta(days=365),
                    "purchase_cost": Decimal("850000000.00"),
                    "salvage_value": Decimal("50000000.00"),
                    "useful_life_years": 10,
                    "capitalized_cost": Decimal("0.00"),
                    "is_trackable": True
                },
                # Scenario B: Overhauled Asset with Capitalized CAPEX
                {
                    "name": "Robot Hàn Điểm KUKA KR-210",
                    "qr_code": f"AST-{tenant_code}-02",
                    "status": "OPERATING",
                    "category": categories["Robot Hàn Tự Động"],
                    "location": locations["Xưởng Hàn Thân Xe (Body Shop)"],
                    "purchase_date": today - timedelta(days=730),
                    "purchase_cost": Decimal("400000000.00"),
                    "salvage_value": Decimal("20000000.00"),
                    "useful_life_years": 5,
                    "capitalized_cost": Decimal("120000000.00"),
                    "capitalized_date": today - timedelta(days=90),
                    "is_trackable": True
                },
                # Scenario C: Fully depreciated asset still in service (VAS 03 Floor Guardrail)
                {
                    "name": "Máy Phay Vạn Năng Bridgeport V5",
                    "qr_code": f"AST-{tenant_code}-03",
                    "status": "OPERATIONAL",
                    "category": categories["Cơ Khí Tiện Phay"],
                    "location": locations["Xưởng Động Cơ & Truyền Động (Powertrain)"],
                    "purchase_date": today - timedelta(days=7 * 365),
                    "purchase_cost": Decimal("150000000.00"),
                    "salvage_value": Decimal("10000000.00"),
                    "useful_life_years": 5,
                    "capitalized_cost": Decimal("0.00"),
                    "is_trackable": True
                },
                # Scenario D: Lemon Bad Actor Asset (RRR >= 70% Scrapping Warning)
                {
                    "name": "Máy Nén Khí Trục Vít Cũ Sullair 75",
                    "qr_code": f"AST-{tenant_code}-04",
                    "status": "MAINTENANCE",
                    "category": categories["Cơ Khí Tiện Phay"],
                    "location": locations["Xưởng Sơn Tĩnh Điện (Paint Shop)"],
                    "purchase_date": today - timedelta(days=3 * 365),
                    "purchase_cost": Decimal("90000000.00"),
                    "salvage_value": Decimal("5000000.00"),
                    "useful_life_years": 6,
                    "capitalized_cost": Decimal("0.00"),
                    "is_trackable": True
                },
                # Scenario E: Machine currently DOWN (Unresolved ongoing failure)
                {
                    "name": "Hệ Thống Băng Tải Lắp Ráp Chassis #1",
                    "qr_code": f"AST-{tenant_code}-05",
                    "status": "DOWN",
                    "category": categories["Hệ Thống Băng Tải"],
                    "location": locations["Xưởng Lắp Ráp Hoàn Thiện (General Assembly)"],
                    "purchase_date": today - timedelta(days=500),
                    "purchase_cost": Decimal("350000000.00"),
                    "salvage_value": Decimal("20000000.00"),
                    "useful_life_years": 8,
                    "capitalized_cost": Decimal("0.00"),
                    "is_trackable": True
                },
                # Scenario F: Newly arrived asset without purchase cost yet
                {
                    "name": "Cụm Cấp Keo Kính Chắn Gió Tự Động",
                    "qr_code": f"AST-{tenant_code}-06",
                    "status": "OPERATIONAL",
                    "category": categories["Robot Hàn Tự Động"],
                    "location": locations["Xưởng Lắp Ráp Hoàn Thiện (General Assembly)"],
                    "purchase_date": today - timedelta(days=10),
                    "purchase_cost": Decimal("0.00"),
                    "value": Decimal("0.00"),
                    "salvage_value": Decimal("0.00"),
                    "useful_life_years": 5,
                    "capitalized_cost": Decimal("0.00"),
                    "is_trackable": True
                }
            ]

            created_assets = {}
            for spec in assets_spec:
                qr = spec.pop("qr_code")
                asset, _ = Asset.all_objects.update_or_create(
                    tenant=tenant,
                    qr_code=qr,
                    defaults=spec
                )
                created_assets[qr] = asset

            # 5. Spare Parts & Inventory
            parts_spec = [
                {"name": "Dầu Thủy Lực Shell Tellus S2 V46", "part_number": "OIL-SH-46", "qty": Decimal("150.00"), "cost": Decimal("85000.00")},
                {"name": "Vòng Bi Côn NSK HR30208", "part_number": "BRG-NSK-30208", "qty": Decimal("-3.00"), "cost": Decimal("320000.00")}, # Negative stock
                {"name": "Bộ Lọc Khí Nén SMC AF40", "part_number": "FLT-SMC-40", "qty": Decimal("25.00"), "cost": Decimal("450000.00")},
                {"name": "Đầu Phun Sơn Tĩnh Điện Wagner", "part_number": "NOZ-WAG-02", "qty": Decimal("12.00"), "cost": Decimal("1250000.00")},
            ]
            created_parts = {}
            for ps in parts_spec:
                pn = ps.pop("part_number")
                part, _ = SparePart.all_objects.update_or_create(
                    tenant=tenant,
                    part_number=pn,
                    defaults={
                        'name': ps["name"],
                        'quantity_in_stock': ps["qty"],
                        'unit_cost': ps["cost"]
                    }
                )
                created_parts[pn] = part

            # 6. Work Orders & Maintenance History (Over the last 30 days)
            # 6.1. Bad Actor OPEX accumulation for AST-04 (Total OPEX >= 70,000,000 > 70% of 90m)
            bad_asset = created_assets[f"AST-{tenant_code}-04"]
            WorkOrder.all_objects.get_or_create(
                tenant=tenant,
                asset=bad_asset,
                title="Thay thế toàn bộ trục vít và bạc đạn",
                defaults={
                    "type": "CORRECTIVE",
                    "priority": "HIGH",
                    "status": "COMPLETED",
                    "actual_cost": Decimal("45000000.00"),
                    "actual_duration_minutes": 360,
                    "completed_at": now - timedelta(days=20),
                    "assigned_to": tech_user
                }
            )
            WorkOrder.all_objects.get_or_create(
                tenant=tenant,
                asset=bad_asset,
                title="Sửa chữa biến tần và quạt giải nhiệt",
                defaults={
                    "type": "CORRECTIVE",
                    "priority": "HIGH",
                    "status": "COMPLETED",
                    "actual_cost": Decimal("25000000.00"),
                    "actual_duration_minutes": 240,
                    "completed_at": now - timedelta(days=8),
                    "assigned_to": tech_user
                }
            )

            # 6.2. Ongoing Unresolved Breakdown for AST-05 (DOWN machine)
            down_asset = created_assets[f"AST-{tenant_code}-05"]
            WorkOrder.all_objects.get_or_create(
                tenant=tenant,
                asset=down_asset,
                title="Sự cố đứt xích tải truyền động chính",
                defaults={
                    "type": "EMERGENCY",
                    "priority": "URGENT",
                    "status": "IN_PROGRESS",
                    "assigned_to": tech_user,
                    "actual_start_time": now - timedelta(hours=3)
                }
            )

            # 6.3. PM Overlap Suppression Pair on AST-01
            press_asset = created_assets[f"AST-{tenant_code}-01"]
            corrective_overlap, _ = WorkOrder.all_objects.get_or_create(
                tenant=tenant,
                asset=press_asset,
                title="Sửa chữa rò rỉ gioăng phớt thủy lực (làm checklist PM)",
                defaults={
                    "type": "CORRECTIVE",
                    "priority": "HIGH",
                    "status": "COMPLETED",
                    "completed_at": now - timedelta(days=12),
                    "actual_duration_minutes": 180,
                    "assigned_to": tech_user
                }
            )
            WorkOrder.all_objects.get_or_create(
                tenant=tenant,
                asset=press_asset,
                title="Bảo trì định kỳ máy ép tháng này",
                defaults={
                    "type": "PREVENTIVE",
                    "status": "CANCELLED",
                    "skipped_reason": "SKIPPED_DUE_TO_OVERLAP",
                    "skipped_reference_wo": corrective_overlap,
                    "deadline": now - timedelta(days=10)
                }
            )

            # 6.4. PM Compliance: 1 on-time, 1 late, 1 pending
            robot_asset = created_assets[f"AST-{tenant_code}-02"]
            WorkOrder.all_objects.get_or_create(
                tenant=tenant,
                asset=robot_asset,
                title="Kiểm tra hệ thống khí nén robot hàn",
                defaults={
                    "type": "PREVENTIVE",
                    "status": "COMPLETED",
                    "deadline": now - timedelta(days=15),
                    "completed_at": now - timedelta(days=14),  # On-time
                    "assigned_to": tech_user
                }
            )
            WorkOrder.all_objects.get_or_create(
                tenant=tenant,
                asset=robot_asset,
                title="Bôi trơn khớp xoay J1-J6",
                defaults={
                    "type": "PREVENTIVE",
                    "status": "COMPLETED",
                    "deadline": now - timedelta(days=18),
                    "completed_at": now - timedelta(days=12),  # Late by 6 days > 3
                    "assigned_to": tech_user
                }
            )

            # 6.5. 30-day Trend Distribution Series
            for day_offset in range(1, 28, 3):
                target_dt = now - timedelta(days=day_offset)
                wo_item, _ = WorkOrder.all_objects.get_or_create(
                    tenant=tenant,
                    asset=press_asset,
                    title=f"Bảo trì giám sát chu kỳ ngày -{day_offset}",
                    defaults={
                        "type": "PREVENTIVE" if day_offset % 2 == 0 else "CORRECTIVE",
                        "status": "COMPLETED",
                        "completed_at": target_dt,
                        "actual_duration_minutes": 45 + day_offset * 2,
                        "actual_cost": Decimal("1500000.00")
                    }
                )
                WorkOrder.all_objects.filter(id=wo_item.id).update(created_at=target_dt - timedelta(hours=4))

            # 7. Stock Transactions: Negative Issue & Price Variance Adjustment
            skf_part = created_parts["BRG-NSK-30208"]
            StockTransaction.all_objects.get_or_create(
                tenant=tenant,
                spare_part=skf_part,
                transaction_type='ISSUE',
                work_order=corrective_overlap,
                defaults={
                    "quantity": Decimal("3.00"),
                    "unit_price": Decimal("320000.00"),
                    "total_amount": Decimal("960000.00"),
                    "cost_center_snapshot": "Xưởng Dập Thép (Stamping Shop)",
                    "issue_date": now - timedelta(days=12),
                    "is_variance_adjustment": False
                }
            )
            StockTransaction.all_objects.get_or_create(
                tenant=tenant,
                spare_part=skf_part,
                transaction_type='ADJUSTMENT',
                work_order=corrective_overlap,
                defaults={
                    "quantity": Decimal("3.00"),
                    "unit_price": Decimal("30000.00"),
                    "total_amount": Decimal("90000.00"),
                    "cost_center_snapshot": "Xưởng Dập Thép (Stamping Shop)",
                    "issue_date": now - timedelta(days=10),
                    "is_variance_adjustment": True
                }
            )

            # 8. Labor Logs for Temporal Cost Center Slicing
            LaborLog.all_objects.get_or_create(
                tenant=tenant,
                work_order=corrective_overlap,
                technician=tech_user,
                work_date=today - timedelta(days=12),
                defaults={
                    "hours_worked": Decimal("3.00"),
                    "hourly_rate": Decimal("250000.00"),
                    "total_cost": Decimal("750000.00"),
                    "cost_center_snapshot": "Xưởng Dập Thép (Stamping Shop)"
                }
            )

            # 9. Audit Logs for Activity Feed
            audit_events = [
                ('WO_CREATED', 'WorkOrder', str(corrective_overlap.id), now - timedelta(hours=1)),
                ('WO_COMPLETED', 'WorkOrder', str(corrective_overlap.id), now - timedelta(minutes=45)),
                ('ASSET_STATUS_DOWN', 'Asset', str(down_asset.id), now - timedelta(minutes=30)),
                ('SPARE_PART_LOW_STOCK', 'SparePart', str(skf_part.id), now - timedelta(minutes=15)),
            ]
            for action, etype, eid, ts in audit_events:
                AuditLog.all_objects.create(
                    tenant=tenant,
                    user_id=str(tech_user.id),
                    action_type=action,
                    entity_type=etype,
                    entity_id=eid,
                    timestamp=ts
                )

            # 10. Flush dashboard cache to immediately reflect fresh scenario calculations
            DashboardCacheService.invalidate_all(tenant.id)

        self.stdout.write(self.style.SUCCESS(
            f"Successfully seeded comprehensive Dashboard & Report scenarios for [{tenant_code}]:\n"
            f"  - 6 Diverse Assets (VAS 03 Straight-line, Fully Depreciated, Lemon Bad Actor RRR >= 70%, Capitalized CAPEX, Ongoing DOWN, Uncosted)\n"
            f"  - 4 Spare Parts (Stocked, Negative balance -3, Moving average, Price variance adjustment)\n"
            f"  - 10+ Work Orders (On-time PM, Overdue PM, Overlap suppression, 30-day continuous trend)\n"
            f"  - Multi-workshop Cost Center allocations with material issues, labor logs, and variance adjustments\n"
            f"  - Operational Audit Logs feed\n"
            f"Dashboard and Reports cache successfully refreshed!"
        ))

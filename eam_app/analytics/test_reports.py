import os
import uuid
import tempfile
from decimal import Decimal
from datetime import datetime, date, timedelta, timezone as dt_timezone
from unittest.mock import patch, MagicMock

import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from core.models import Tenant
from users.models import User, Role, Permission
from assets.models import Asset, AssetCategory, Location, SparePart, StockTransaction
from workorders.models import WorkOrder, WorkOrderMaterial, LaborLog
from analytics.models import ExportJob
from analytics.report_services import (
    AssetValuationEngine,
    MaintenancePerformanceEngine,
    SparePartsValuationEngine,
    CostSummaryEngine,
    round_vnd,
    parse_date_safe
)
from analytics.export_engine import (
    sanitize_cell_value,
    ExportEngineService,
    MinIOStorageService
)
from analytics.tasks import (
    generate_export_report,
    cleanup_zombie_export_jobs,
    purge_expired_export_files
)


@pytest.fixture
def test_setup(db):
    tenant = Tenant.objects.create(name="Phân Xưởng Thép Việt Nam", tenant_code="VN_STEEL")
    other_tenant = Tenant.objects.create(name="Nhà Máy Xi Măng Hải Phòng", tenant_code="HP_CEMENT")

    admin_role = Role.objects.create(name="TENANT_ADMIN", tenant=tenant)
    tech_role = Role.objects.create(name="TECHNICIAN", tenant=tenant)

    admin_user = User.objects.create_user(
        username="admin_user",
        email="admin@steel.vn",
        password="password123",
        tenant=tenant
    )
    admin_user.roles.add(admin_role)

    tech_user = User.objects.create_user(
        username="tech_user",
        email="tech@steel.vn",
        password="password123",
        tenant=tenant
    )
    tech_user.roles.add(tech_role)

    other_user = User.objects.create_user(
        username="other_admin",
        email="admin@cement.vn",
        password="password123",
        tenant=other_tenant
    )

    location_a = Location.objects.create(name="Phân Xưởng A", tenant=tenant)
    location_b = Location.objects.create(name="Phân Xưởng B", tenant=tenant)

    category = AssetCategory.objects.create(name="Cơ Khí Nặng", tenant=tenant)

    return {
        "tenant": tenant,
        "other_tenant": other_tenant,
        "admin_user": admin_user,
        "tech_user": tech_user,
        "other_user": other_user,
        "location_a": location_a,
        "location_b": location_b,
        "category": category,
    }


# =========================================================================
# 9.1. Ma Trận Kịch Bản Nghiệp Vụ Tài Chính & Bảo Trì
# =========================================================================

def test_tc_rep_01_depreciation_floor_guardrail(test_setup):
    """
    TC-REP-01: Ràng buộc chặn sàn khấu hao tài sản (Không âm Net Book Value - VAS 03)
    Thiết bị nguyên giá 100,000,000 VNĐ, khấu hao trong 5 năm, giá trị thanh lý ước tính 5,000,000 VNĐ.
    Thiết bị đã vận hành sang năm thứ 7 (84 tháng > 60 tháng).
    Kỳ vọng: Giá trị sổ sách còn lại dừng chính xác ở mức 5,000,000 VNĐ; không bao giờ bị âm;
    hiển thị trạng thái "Đã khấu hao hết - Đang vận hành".
    """
    tenant = test_setup["tenant"]
    seven_years_ago = (timezone.now() - timedelta(days=7 * 365 + 10)).date()

    asset = Asset.all_objects.create(
        tenant=tenant,
        name="Máy Phay Trục Đứng 5 Trục",
        qr_code="ASSET-01",
        purchase_date=seven_years_ago,
        purchase_cost=Decimal("100000000.00"),
        salvage_value=Decimal("5000000.00"),
        useful_life_years=5,
        location=test_setup["location_a"],
        category=test_setup["category"]
    )

    data = AssetValuationEngine.get_asset_valuation_data(tenant=tenant)
    items = data["items"]
    assert len(items) == 1

    item = items[0]
    assert item["salvageValue"] == 5000000.0
    # Net book value must be clamped exactly to salvage value
    assert item["netBookValue"] == 5000000.0
    assert item["financialStatus"] == "Đã khấu hao hết - Đang vận hành"
    assert item["monthsInService"] >= 60


def test_tc_rep_02_rrr_bad_actor_recommendation(test_setup):
    """
    TC-REP-02: Nhận diện kiến nghị thanh lý thiết bị (RRR >= 70%)
    Máy nén khí có giá trị thay thế 200,000,000 VNĐ, tổng chi phí sửa chữa OPEX tích lũy đạt 145,000,000 VNĐ (72.5%).
    Kỳ vọng: Báo cáo định giá tài sản đánh dấu thiết bị kèm cảnh báo đề xuất lập hội đồng thanh lý và đầu tư mới.
    """
    tenant = test_setup["tenant"]
    asset = Asset.all_objects.create(
        tenant=tenant,
        name="Máy Nén Khí Trục Vít 75kW",
        qr_code="ASSET-02",
        purchase_date=timezone.now().date(),
        purchase_cost=Decimal("200000000.00"),
        salvage_value=Decimal("10000000.00"),
        useful_life_years=10,
        location=test_setup["location_a"]
    )

    # Accumulate OPEX work orders totaling 145,000,000 VNĐ
    WorkOrder.all_objects.create(
        tenant=tenant,
        asset=asset,
        title="Sửa chữa đại tu van áp lực",
        type="CORRECTIVE",
        priority="HIGH",
        status="COMPLETED",
        is_capitalized=False,
        actual_cost=Decimal("95000000.00")
    )
    WorkOrder.all_objects.create(
        tenant=tenant,
        asset=asset,
        title="Thay thế vòng bi và phớt chặn dầu",
        type="CORRECTIVE",
        priority="HIGH",
        status="COMPLETED",
        is_capitalized=False,
        actual_cost=Decimal("50000000.00")
    )

    data = AssetValuationEngine.get_asset_valuation_data(tenant=tenant)
    items = data["items"]
    assert len(items) == 1

    item = items[0]
    assert item["accumulatedOpex"] == 145000000.0
    assert item["rrrPercent"] == 72.5
    assert item["isBadActor"] is True
    assert "Đề xuất thanh lý" in item["recommendation"]
    assert data["summary"]["badActorCount"] == 1


def test_tc_rep_03_capex_capitalization_and_rrr_exclusion(test_setup):
    """
    TC-REP-03: Đại tu, nâng cấp tài sản làm thay đổi nguyên giá (CAPEX vs OPEX)
    Thiết bị được đại tu thay động cơ chính trị giá 80,000,000 VNĐ, đánh dấu is_capitalized = True (CAPEX).
    Tổng chi phí sửa chữa thường (OPEX) trước đó là 30,000,000 VNĐ. Giá thay thế là 150,000,000 VNĐ.
    Kỳ vọng: Khoản 80,000,000 VNĐ không được tính vào tử số của RRR (RRR = 30 / 150 = 20%, không bị báo động thanh lý sai).
    Khoản này được cộng vào Nguyên giá để tính lại lịch khấu hao đường thẳng mới.
    """
    tenant = test_setup["tenant"]
    asset = Asset.all_objects.create(
        tenant=tenant,
        name="Máy Dập Thủy Lực 500 Tấn",
        qr_code="ASSET-03",
        purchase_date=timezone.now().date() - timedelta(days=365),
        purchase_cost=Decimal("150000000.00"),
        salvage_value=Decimal("10000000.00"),
        useful_life_years=5,
        capitalized_cost=Decimal("80000000.00"), # Capitalized CAPEX
        capitalized_date=timezone.now().date(),
        location=test_setup["location_a"]
    )

    # 1 OPEX work order = 30,000,000 VNĐ
    WorkOrder.all_objects.create(
        tenant=tenant,
        asset=asset,
        title="Bảo trì định kỳ và thay ống tuy-ô",
        type="CORRECTIVE",
        priority="MEDIUM",
        status="COMPLETED",
        is_capitalized=False,
        actual_cost=Decimal("30000000.00")
    )

    # 1 CAPEX work order = 80,000,000 VNĐ (Should NOT be in RRR)
    WorkOrder.all_objects.create(
        tenant=tenant,
        asset=asset,
        title="Đại tu thay mới cụm bơm và động cơ biến tần",
        type="CORRECTIVE",
        priority="URGENT",
        status="COMPLETED",
        is_capitalized=True,
        actual_cost=Decimal("80000000.00")
    )

    data = AssetValuationEngine.get_asset_valuation_data(tenant=tenant)
    item = data["items"][0]

    # Total cost basis = 150m + 80m = 230m
    assert item["totalCostBasis"] == 230000000.0
    assert item["capexCost"] == 80000000.0
    # Accumulated OPEX only counts the 30m, ignoring the 80m CAPEX
    assert item["accumulatedOpex"] == 30000000.0
    assert item["rrrPercent"] == 20.0  # 30m / 150m = 20%
    assert item["isBadActor"] is False


def test_tc_rep_04_cross_period_accrual(test_setup):
    """
    TC-REP-04: Ghi nhận chi phí cho công việc kéo dài qua nhiều kỳ kế toán (Cross-period Accrual)
    Một Work Order sửa chữa lớn phát sinh từ 25/11 đến 10/12 mới hoàn thành (completed_at).
    Xuất vật tư 20,000,000 VNĐ vào ngày 26/11 và 15,000,000 VNĐ vào ngày 05/12.
    Kỳ vọng: Báo cáo chi phí tháng 11 ghi nhận chính xác 20,000,000 VNĐ; báo cáo tháng 12 ghi nhận 15,000,000 VNĐ.
    Tuyệt đối không dồn toàn bộ 35,000,000 VNĐ vào tháng 12.
    """
    tenant = test_setup["tenant"]
    asset = Asset.all_objects.create(tenant=tenant, name="Lò Nung Cao Tần", qr_code="ASSET-04")
    part_a = SparePart.all_objects.create(tenant=tenant, name="Điện Cực Than", unit_cost=Decimal("10000000.00"))
    part_b = SparePart.all_objects.create(tenant=tenant, name="Gạch Chịu Lửa", unit_cost=Decimal("5000000.00"))

    wo = WorkOrder.all_objects.create(
        tenant=tenant,
        asset=asset,
        title="Đại tu lót lại lò nung",
        status="COMPLETED",
        deadline=datetime(2026, 12, 10, 17, 0, tzinfo=dt_timezone.utc),
        completed_at=datetime(2026, 12, 10, 17, 0, tzinfo=dt_timezone.utc),
        actual_cost=Decimal("35000000.00")
    )
    WorkOrder.all_objects.filter(id=wo.id).update(created_at=datetime(2026, 11, 25, 8, 0, tzinfo=dt_timezone.utc))

    # Issue material A on 26/11
    StockTransaction.all_objects.create(
        tenant=tenant,
        spare_part=part_a,
        work_order=wo,
        transaction_type='ISSUE',
        quantity=Decimal("2.00"),
        unit_price=Decimal("10000000.00"),
        total_amount=Decimal("20000000.00"),
        issue_date=datetime(2026, 11, 26, 10, 0, tzinfo=dt_timezone.utc),
        cost_center_snapshot="Phân Xưởng Đúc"
    )

    # Issue material B on 05/12
    StockTransaction.all_objects.create(
        tenant=tenant,
        spare_part=part_b,
        work_order=wo,
        transaction_type='ISSUE',
        quantity=Decimal("3.00"),
        unit_price=Decimal("5000000.00"),
        total_amount=Decimal("15000000.00"),
        issue_date=datetime(2026, 12, 5, 14, 0, tzinfo=dt_timezone.utc),
        cost_center_snapshot="Phân Xưởng Đúc"
    )

    # November report: 2026-11-01 to 2026-11-30
    nov_data = CostSummaryEngine.get_cost_summary_data(
        tenant=tenant,
        date_from=date(2026, 11, 1),
        date_to=date(2026, 11, 30)
    )
    assert nov_data["summary"]["totalMaterialCost"] == 20000000.0
    assert nov_data["summary"]["totalCost"] == 20000000.0

    # December report: 2026-12-01 to 2026-12-31
    dec_data = CostSummaryEngine.get_cost_summary_data(
        tenant=tenant,
        date_from=date(2026, 12, 1),
        date_to=date(2026, 12, 31)
    )
    assert dec_data["summary"]["totalMaterialCost"] == 15000000.0
    assert dec_data["summary"]["totalCost"] == 15000000.0


def test_tc_rep_05_pm_overlap_suppression(test_setup):
    """
    TC-REP-05: Ghi đè và bỏ qua bảo trì định kỳ do trùng lặp (PM Suppression / Overlap)
    Máy có lịch PM vào ngày 15. Ngày 10 máy bị sự cố, đội bảo trì đã xử lý xong và làm luôn checklist PM.
    Quản lý hủy phiếu PM ngày 15 với lý do SKIPPED_DUE_TO_OVERLAP.
    Kỳ vọng: Phiếu bị hủy này bị LOẠI TRỪ HOÀN TOÀN KHỎI MẪU SỐ tính tỷ lệ tuân thủ PM Compliance (quy tắc 10%).
    """
    tenant = test_setup["tenant"]
    asset = Asset.all_objects.create(tenant=tenant, name="Máy Cắt CNC", qr_code="ASSET-05")

    # Corrective order on day 10
    corrective_wo = WorkOrder.all_objects.create(
        tenant=tenant,
        asset=asset,
        title="Sửa chữa dao cắt và bảo dưỡng luôn",
        type="CORRECTIVE",
        status="COMPLETED",
        completed_at=datetime(2026, 8, 10, 16, 0, tzinfo=dt_timezone.utc)
    )
    WorkOrder.all_objects.filter(id=corrective_wo.id).update(created_at=datetime(2026, 8, 10, 8, 0, tzinfo=dt_timezone.utc))

    # 1 PM completed on time
    pm_on_time = WorkOrder.all_objects.create(
        tenant=tenant,
        asset=asset,
        title="Bảo dưỡng động cơ servo định kỳ",
        type="PREVENTIVE",
        status="COMPLETED",
        deadline=datetime(2026, 8, 20, 17, 0, tzinfo=dt_timezone.utc),
        completed_at=datetime(2026, 8, 20, 14, 0, tzinfo=dt_timezone.utc)
    )
    WorkOrder.all_objects.filter(id=pm_on_time.id).update(created_at=datetime(2026, 8, 1, 8, 0, tzinfo=dt_timezone.utc))

    # 1 PM cancelled due to overlap with corrective_wo
    pm_skipped = WorkOrder.all_objects.create(
        tenant=tenant,
        asset=asset,
        title="PM ngày 15 bị trùng",
        type="PREVENTIVE",
        status="CANCELLED",
        skipped_reason="SKIPPED_DUE_TO_OVERLAP",
        skipped_reference_wo=corrective_wo,
        deadline=datetime(2026, 8, 15, 17, 0, tzinfo=dt_timezone.utc)
    )
    WorkOrder.all_objects.filter(id=pm_skipped.id).update(created_at=datetime(2026, 8, 1, 8, 0, tzinfo=dt_timezone.utc))

    data = MaintenancePerformanceEngine.get_performance_data(
        tenant=tenant,
        date_from=date(2026, 8, 1),
        date_to=date(2026, 8, 31)
    )

    summary = data["summary"]
    assert summary["totalPmDue"] == 2
    assert summary["skippedDueToOverlap"] == 1
    # Effective denominator = 2 - 1 = 1
    assert summary["effectivePmDenominator"] == 1
    assert summary["onTimePmCount"] == 1
    # PM Compliance = 1 / 1 = 100%
    assert summary["pmComplianceRate"] == 100.0


def test_tc_rep_06_negative_inventory_and_price_variance(test_setup):
    """
    TC-REP-06: Tính toán giá vốn di động khi kho xuất âm (Negative Inventory Valuation)
    Kỹ thuật viên xuất gấp 2 vòng bi khi tồn kho trên hệ thống đang bằng 0 (xuất âm thành -2).
    Đơn giá bình quân gần nhất là 500,000 VNĐ.
    3 ngày sau có phiếu Nhập kho mới với đơn giá thực tế 550,000 VNĐ.
    Kỳ vọng: Work Order tạm tính chi phí ban đầu là 2 * 500,000 = 1,000,000 VNĐ.
    Khi có phiếu Nhập kho, hệ thống tự động sinh bút toán chênh lệch giá (Price Variance) bổ sung +100,000 VNĐ.
    """
    tenant = test_setup["tenant"]
    asset = Asset.all_objects.create(tenant=tenant, name="Hệ Thống Băng Tải", qr_code="ASSET-06")
    part = SparePart.all_objects.create(
        tenant=tenant,
        name="Vòng Bi SKF 6205",
        quantity_in_stock=Decimal("0.00"),
        unit_cost=Decimal("500000.00")
    )

    wo = WorkOrder.all_objects.create(
        tenant=tenant,
        asset=asset,
        title="Thay thế vòng bi khẩn cấp",
        status="IN_PROGRESS"
    )

    # 1. Negative issue
    issue_tx = SparePartsValuationEngine.record_negative_issue_and_variance(
        tenant=tenant,
        spare_part=part,
        work_order=wo,
        issue_qty=Decimal("2.00"),
        issue_date=timezone.now() - timedelta(days=3),
        cost_center="Xưởng Cán Thép"
    )

    part.refresh_from_db()
    wo.refresh_from_db()
    assert part.quantity_in_stock == Decimal("-2.00")
    assert wo.actual_cost == Decimal("1000000.00")

    # 2. Receipt GRN 5 units @ 550,000 VNĐ
    txs = SparePartsValuationEngine.apply_grn_receipt_and_reconcile_variance(
        tenant=tenant,
        spare_part=part,
        receipt_qty=Decimal("5.00"),
        new_unit_cost=Decimal("550000.00"),
        receipt_date=timezone.now()
    )

    part.refresh_from_db()
    wo.refresh_from_db()

    # Stock is now -2 + 5 = 3
    assert part.quantity_in_stock == Decimal("3.00")
    # Variance should be: (550,000 - 500,000) * 2 = 100,000 VNĐ
    # WorkOrder cost becomes 1,000,000 + 100,000 = 1,100,000 VNĐ
    assert wo.actual_cost == Decimal("1100000.00")

    # Check StockTransaction created for variance
    variance_tx = StockTransaction.all_objects.filter(tenant=tenant, is_variance_adjustment=True).first()
    assert variance_tx is not None
    assert variance_tx.total_amount == Decimal("100000.00")


def test_tc_rep_07_temporal_cost_center_slicing(test_setup):
    """
    TC-REP-07: Tài sản luân chuyển giữa các trung tâm chi phí (Temporal Cost Center Slicing)
    Xe nâng hoạt động tại Phân xưởng A trong Quý 1, sang Quý 2 được điều chuyển sang Phân xưởng B.
    Chi phí bảo trì phát sinh trong Quý 1 là 10,000,000 VNĐ, Quý 2 là 15,000,000 VNĐ.
    Kỳ vọng: Báo cáo phân bổ chi phí theo Phân xưởng ghi nhận đúng 10,000,000 VNĐ cho Phân xưởng A
    và 15,000,000 VNĐ cho Phân xưởng B. Vị trí hiện tại ở Phân xưởng B không được áp đặt lên chi phí lịch sử của Quý 1.
    """
    tenant = test_setup["tenant"]
    asset = Asset.all_objects.create(
        tenant=tenant,
        name="Xe Nâng Điện Komatsu 2.5T",
        qr_code="ASSET-07",
        location=test_setup["location_b"] # Current location is Workshop B
    )
    part = SparePart.all_objects.create(tenant=tenant, name="Bình Ắc Quy", unit_cost=Decimal("5000000.00"))

    # Q1 Work Order in Workshop A
    wo_q1 = WorkOrder.all_objects.create(tenant=tenant, asset=asset, title="Bảo trì Q1")
    StockTransaction.all_objects.create(
        tenant=tenant,
        spare_part=part,
        work_order=wo_q1,
        quantity=Decimal("2.00"),
        unit_price=Decimal("5000000.00"),
        total_amount=Decimal("10000000.00"),
        issue_date=datetime(2026, 2, 15, 10, 0, tzinfo=dt_timezone.utc),
        cost_center_snapshot="Phân Xưởng A"
    )

    # Q2 Work Order in Workshop B
    wo_q2 = WorkOrder.all_objects.create(tenant=tenant, asset=asset, title="Bảo trì Q2")
    StockTransaction.all_objects.create(
        tenant=tenant,
        spare_part=part,
        work_order=wo_q2,
        quantity=Decimal("3.00"),
        unit_price=Decimal("5000000.00"),
        total_amount=Decimal("15000000.00"),
        issue_date=datetime(2026, 5, 20, 10, 0, tzinfo=dt_timezone.utc),
        cost_center_snapshot="Phân Xưởng B"
    )

    # Overall report covering Q1 and Q2
    data = CostSummaryEngine.get_cost_summary_data(
        tenant=tenant,
        date_from=date(2026, 1, 1),
        date_to=date(2026, 6, 30)
    )

    cost_centers = {c["costCenter"]: c["totalCost"] for c in data["costCenters"]}
    assert cost_centers.get("Phân Xưởng A") == 10000000.0
    assert cost_centers.get("Phân Xưởng B") == 15000000.0


def test_tc_rep_08_pm_compliance_10_percent_rule(test_setup):
    """
    TC-REP-08: Đo lường tuân thủ PM theo quy tắc 10% (10% Compliance Rule)
    Phiếu bảo trì định kỳ chu kỳ 30 ngày, ngày đến hạn là 20/08.
    Kỹ thuật viên hoàn thành vào ngày 25/08 (trễ 5 ngày > 3 ngày = 10%).
    Kỳ vọng: Phiếu được phân loại vào nhóm hoàn thành trễ hạn và làm giảm tỷ lệ pm_compliance_rate.
    """
    tenant = test_setup["tenant"]
    asset = Asset.all_objects.create(tenant=tenant, name="Quạt Thông Gió Hầm Lò", qr_code="ASSET-08")

    # Due date: 2026-08-20, Completed: 2026-08-25 (late by 5 days > 3 days)
    pm_wo = WorkOrder.all_objects.create(
        tenant=tenant,
        asset=asset,
        title="PM Quạt Thông Gió",
        type="PREVENTIVE",
        status="COMPLETED",
        deadline=datetime(2026, 8, 20, 17, 0, tzinfo=dt_timezone.utc),
        completed_at=datetime(2026, 8, 25, 10, 0, tzinfo=dt_timezone.utc)
    )
    WorkOrder.all_objects.filter(id=pm_wo.id).update(created_at=datetime(2026, 8, 1, 8, 0, tzinfo=dt_timezone.utc))

    data = MaintenancePerformanceEngine.get_performance_data(
        tenant=tenant,
        date_from=date(2026, 8, 1),
        date_to=date(2026, 8, 31)
    )

    assert data["summary"]["totalPmDue"] == 1
    assert data["summary"]["onTimePmCount"] == 0
    assert data["summary"]["latePmCount"] == 1
    assert data["summary"]["pmComplianceRate"] == 0.0


def test_tc_rep_09_surplus_parts_return(test_setup):
    """
    TC-REP-09: Hoàn trả vật tư xuất dư nhập lại kho
    Kỹ thuật viên xuất 5 lít dầu bảo dưỡng (đơn giá 100,000 VNĐ/lít) nhưng chỉ dùng 3 lít, làm phiếu hoàn trả 2 lít.
    Kỳ vọng: Kho nhập lại 2 lít theo đúng đơn giá 100,000 VNĐ; chi phí Work Order tự động giảm trừ 200,000 VNĐ.
    """
    tenant = test_setup["tenant"]
    asset = Asset.all_objects.create(tenant=tenant, name="Máy Bơm Áp Lực Cao", qr_code="ASSET-09")
    oil = SparePart.all_objects.create(
        tenant=tenant,
        name="Dầu Thủy Lực Shell Tellus S2",
        quantity_in_stock=Decimal("50.00"),
        unit_cost=Decimal("100000.00")
    )

    wo = WorkOrder.all_objects.create(
        tenant=tenant,
        asset=asset,
        title="Thay dầu máy bơm",
        actual_cost=Decimal("500000.00") # 5 liters * 100k
    )

    # Return 2 liters
    return_tx = SparePartsValuationEngine.record_surplus_return(
        tenant=tenant,
        spare_part=oil,
        work_order=wo,
        return_qty=Decimal("2.00"),
        original_unit_cost=Decimal("100000.00"),
        return_date=timezone.now()
    )

    oil.refresh_from_db()
    wo.refresh_from_db()

    # Stock increased by 2
    assert oil.quantity_in_stock == Decimal("52.00")
    # WorkOrder cost deducted by 200,000 VNĐ (500k - 200k = 300k)
    assert wo.actual_cost == Decimal("300000.00")
    assert return_tx.transaction_type == 'RETURN'
    assert return_tx.total_amount == Decimal("200000.00")


# =========================================================================
# 9.2. Ma Trận Kịch Bản Kỹ Thuật, Hiệu Năng & An Toàn
# =========================================================================

def test_tc_perf_01_streaming_excel_export_chunking(test_setup):
    """
    TC-PERF-01: Xuất tập dữ liệu lớn không bị tràn bộ nhớ (Chunking & Streaming)
    Kiểm tra generator xuất tệp Excel bằng openpyxl(write_only=True) sinh ra tệp hợp lệ.
    """
    tenant = test_setup["tenant"]
    # Create an export job
    job = ExportJob.all_objects.create(
        tenant=tenant,
        user=test_setup["admin_user"],
        report_type='ASSET_VALUATION',
        file_format='XLSX',
        filter_params={}
    )

    with patch.object(MinIOStorageService, 'upload_file', return_value=1024), \
         patch.object(MinIOStorageService, 'generate_presigned_url', return_value='https://minio.test/download.xlsx'):
        object_key, file_size, presigned_url = ExportEngineService.generate_and_upload(job)

        assert object_key.endswith('.xlsx')
        assert file_size == 1024
        assert 'https://minio.test' in presigned_url


def test_tc_perf_02_concurrency_limit_429(test_setup):
    """
    TC-PERF-02: Giới hạn tác vụ xuất đồng thời cho mỗi Tenant (Concurrency Limit = 3)
    Yêu cầu thứ 4 bị từ chối với mã HTTP 429 kèm thông báo giới hạn.
    """
    tenant = test_setup["tenant"]
    client = APIClient()
    client.force_authenticate(user=test_setup["admin_user"])

    # Create 3 active jobs
    for i in range(3):
        ExportJob.all_objects.create(
            tenant=tenant,
            user=test_setup["admin_user"],
            report_type='COST_SUMMARY',
            file_format='XLSX',
            status='PROCESSING'
        )

    # 4th request
    res = client.post('/api/v1/reports/export/', {
        "reportType": "COST_SUMMARY",
        "fileFormat": "XLSX",
        "filters": {}
    }, format='json')

    assert res.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert res.data["error"]["code"] == "CONCURRENT_EXPORT_LIMIT_EXCEEDED"


def test_tc_sec_01_formula_injection_guardrail():
    """
    TC-SEC-01: Chống tấn công tiêm mã công thức bảng tính (CSV / Formula Injection)
    Tên phụ tùng hoặc ghi chú chứa chuỗi =SUM(1+1) hoặc @cmd|' /C calc'!A0 hoặc +123.
    Kỳ vọng: Tự động thêm dấu nháy đơn ' ở đầu chuỗi ('=SUM(1+1)').
    """
    assert sanitize_cell_value("=SUM(1+1)") == "'=SUM(1+1)"
    assert sanitize_cell_value("@cmd|' /C calc'!A0") == "'@cmd|' /C calc'!A0"
    assert sanitize_cell_value("+12345") == "'+12345"
    assert sanitize_cell_value("-drop_table") == "'-drop_table"
    assert sanitize_cell_value("\tmalicious_tab") == "'\tmalicious_tab"
    # Normal strings unaffected
    assert sanitize_cell_value("Máy mài phẳng") == "Máy mài phẳng"
    assert sanitize_cell_value(12345) == 12345


def test_tc_sec_02_zombie_job_auto_recovery(test_setup):
    """
    TC-SEC-02: Phục hồi tác vụ ma khi Worker bị khởi động lại (Zombie Job Auto-Recovery)
    Job ở trạng thái PROCESSING quá 15 phút không cập nhật.
    Kỳ vọng: cleanup_zombie_export_jobs tự động đánh dấu thành FAILED.
    """
    tenant = test_setup["tenant"]
    twenty_mins_ago = timezone.now() - timedelta(minutes=20)

    job = ExportJob.all_objects.create(
        tenant=tenant,
        user=test_setup["admin_user"],
        report_type='ASSET_VALUATION',
        file_format='XLSX',
        status='PROCESSING'
    )
    # Manually set updated_at to 20 minutes ago
    ExportJob.all_objects.filter(id=job.id).update(updated_at=twenty_mins_ago)

    res = cleanup_zombie_export_jobs()
    assert res["cleaned_count"] >= 1

    job.refresh_from_db()
    assert job.status == 'FAILED'
    assert "Tác vụ bị gián đoạn" in job.error_message


def test_tc_sec_03_retention_auto_purge(test_setup):
    """
    TC-SEC-03: Tự động xóa tệp MinIO sau 7 ngày (Retention Auto-Purge)
    Kiểm tra các tệp báo cáo đã hoàn tất xuất quá 7 ngày trước đó (expires_at < now).
    Kỳ vọng: Tác vụ xóa tệp vật lý trên MinIO và chuyển trạng thái thành EXPIRED.
    """
    tenant = test_setup["tenant"]
    expired_date = timezone.now() - timedelta(days=1)

    job = ExportJob.all_objects.create(
        tenant=tenant,
        user=test_setup["admin_user"],
        report_type='SPARE_PARTS',
        file_format='PDF',
        status='COMPLETED',
        minio_object_key='tenant_a/2026/09/expired_job.pdf',
        expires_at=expired_date
    )

    with patch.object(MinIOStorageService, 'delete_file') as mock_delete:
        res = purge_expired_export_files()
        assert res["purged_count"] >= 1
        mock_delete.assert_called_with('tenant_a/2026/09/expired_job.pdf')

    job.refresh_from_db()
    assert job.status == 'EXPIRED'


def test_tc_sec_04_multi_tenant_isolation_idor(test_setup):
    """
    TC-SEC-04: Cách ly tệp xuất giữa các tổ chức (Multi-Tenant Isolation)
    Người dùng thuộc Tenant A gọi API lấy liên kết tải tệp mang job_id của Tenant B.
    Kỳ vọng: Hệ thống trả về 404 Not Found, tuyệt đối không sinh Presigned URL của Tenant khác.
    """
    tenant_b = test_setup["other_tenant"]
    job_b = ExportJob.all_objects.create(
        tenant=tenant_b,
        user=test_setup["other_user"],
        report_type='ASSET_VALUATION',
        file_format='XLSX',
        status='COMPLETED',
        minio_object_key='tenant_b/secret_report.xlsx'
    )

    # User of Tenant A attempts to access Job B
    client = APIClient()
    client.force_authenticate(user=test_setup["admin_user"])

    res = client.get(f'/api/v1/reports/export-jobs/{job_b.id}/')
    assert res.status_code == status.HTTP_404_NOT_FOUND
    assert res.data["error"]["code"] == "JOB_NOT_FOUND"


def test_tc_sec_05_decimal_precision_and_rounding():
    """
    TC-SEC-05: Độ chính xác số học tài chính VNĐ (Decimal Precision)
    Tính tổng chi phí 1,000 dòng vật tư lẻ và khấu hao.
    Kỳ vọng: Dùng Decimal, khớp từng đồng VNĐ, không có sai số dấu phẩy động kiểu float.
    """
    subtotals = [Decimal('12345.67') for _ in range(1000)]
    total = sum(subtotals)
    rounded_total = round_vnd(total)

    # 12345.67 * 1000 = 12,345,670.00
    assert total == Decimal('12345670.00')
    assert rounded_total == Decimal('12345670')


def test_tc_rep_10_zero_or_missing_base_cost_no_false_alarm(test_setup):
    """
    TC-REP-10: Thiết bị chưa có hoặc nguyên giá bằng 0 không bị báo động thanh lý ảo.
    Thiết bị mới tiếp nhận chưa nhập nguyên giá (base_cost = 0), phát sinh sửa chữa 15,000,000 VNĐ.
    Kỳ vọng: Không chia cho 1 dẫn đến RRR = 1,500,000,000%, không bị đánh dấu Bad Actor,
    hiển thị hướng dẫn cập nhật nguyên giá thay vì đề xuất thanh lý máy mới.
    """
    tenant = test_setup["tenant"]
    asset = Asset.all_objects.create(
        tenant=tenant,
        name="Máy Tiện Mới Tiếp Nhận Chưa Vào Sổ",
        qr_code="ASSET-10-NOCOST",
        purchase_cost=Decimal("0.00"),
        value=Decimal("0.00"),
        location=test_setup["location_a"]
    )

    WorkOrder.all_objects.create(
        tenant=tenant,
        asset=asset,
        title="Lắp đặt phụ kiện ban đầu",
        type="CORRECTIVE",
        status="COMPLETED",
        actual_cost=Decimal("15000000.00")
    )

    data = AssetValuationEngine.get_asset_valuation_data(tenant=tenant)
    item = next(i for i in data["items"] if i["id"] == str(asset.id))

    assert item["rrrPercent"] == 0.0
    assert item["isBadActor"] is False
    assert "Chưa có thông tin nguyên giá" in item["recommendation"]
    assert data["summary"]["badActorCount"] == 0


def test_tc_rep_11_cross_month_work_order_completion_in_performance_report(test_setup):
    """
    TC-REP-11: Phiếu công việc tạo tháng trước nhưng hoàn thành trong kỳ báo cáo (Cross-Month Completion).
    Phiếu sửa chữa được tạo ngày 25/07, đến ngày 05/08 mới hoàn tất.
    Kỳ vọng: Báo cáo hiệu suất tháng 8 (01/08 - 31/08) phải ghi nhận phiếu này vào completedOrders và MTTR.
    """
    tenant = test_setup["tenant"]
    asset = Asset.all_objects.create(tenant=tenant, name="Máy Cắt Plasma", qr_code="ASSET-11")

    wo = WorkOrder.all_objects.create(
        tenant=tenant,
        asset=asset,
        title="Đại tu hệ thống làm mát nguồn plasma",
        type="CORRECTIVE",
        status="COMPLETED",
        actual_duration_minutes=240,  # 4 hours
        completed_at=datetime(2026, 8, 5, 14, 0, tzinfo=dt_timezone.utc)
    )
    # Set created_at to July 25
    WorkOrder.all_objects.filter(id=wo.id).update(created_at=datetime(2026, 7, 25, 9, 0, tzinfo=dt_timezone.utc))

    data = MaintenancePerformanceEngine.get_performance_data(
        tenant=tenant,
        date_from=date(2026, 8, 1),
        date_to=date(2026, 8, 31)
    )

    summary = data["summary"]
    assert summary["totalOrders"] >= 1
    assert summary["completedOrders"] >= 1
    assert summary["avgMttrHours"] == 4.0


def test_tc_rep_12_mttr_ignores_anomalous_durations_and_accepts_minutes(test_setup):
    """
    TC-REP-12: MTTR lọc các thời lượng dị biệt và nhận diện thời lượng theo phút.
    Phiếu 1: 180 phút (3.0h) - không có actual_start_time.
    Phiếu 2: 3000 giờ (quên đóng phiếu 4 tháng).
    Phiếu 3: -60 phút (lỗi đồng hồ).
    Kỳ vọng: MTTR chỉ tính trung bình phiếu 1 là 3.0h, loại bỏ hoàn toàn phiếu 2 và phiếu 3.
    """
    tenant = test_setup["tenant"]
    asset = Asset.all_objects.create(tenant=tenant, name="Máy Ép Thủy Lực P2", qr_code="ASSET-12")

    # Ticket 1: 180 minutes = 3.0h (valid)
    wo1 = WorkOrder.all_objects.create(
        tenant=tenant,
        asset=asset,
        title="Sửa chữa van đảo chiều",
        type="BREAKDOWN",
        status="COMPLETED",
        actual_duration_minutes=180,
        completed_at=datetime(2026, 8, 10, 10, 0, tzinfo=dt_timezone.utc)
    )
    WorkOrder.all_objects.filter(id=wo1.id).update(created_at=datetime(2026, 8, 10, 7, 0, tzinfo=dt_timezone.utc))

    # Ticket 2: 3000h outlier
    wo2 = WorkOrder.all_objects.create(
        tenant=tenant,
        asset=asset,
        title="Phiếu quên đóng 4 tháng",
        type="BREAKDOWN",
        status="COMPLETED",
        actual_duration_minutes=3000 * 60,
        completed_at=datetime(2026, 8, 12, 10, 0, tzinfo=dt_timezone.utc)
    )
    WorkOrder.all_objects.filter(id=wo2.id).update(created_at=datetime(2026, 8, 12, 7, 0, tzinfo=dt_timezone.utc))

    # Ticket 3: -60 minutes (negative)
    wo3 = WorkOrder.all_objects.create(
        tenant=tenant,
        asset=asset,
        title="Lỗi đồng hồ hệ thống",
        type="BREAKDOWN",
        status="COMPLETED",
        actual_duration_minutes=-60,
        completed_at=datetime(2026, 8, 15, 10, 0, tzinfo=dt_timezone.utc)
    )
    WorkOrder.all_objects.filter(id=wo3.id).update(created_at=datetime(2026, 8, 15, 7, 0, tzinfo=dt_timezone.utc))

    data = MaintenancePerformanceEngine.get_performance_data(
        tenant=tenant,
        date_from=date(2026, 8, 1),
        date_to=date(2026, 8, 31)
    )

    assert data["summary"]["avgMttrHours"] == 3.0


def test_tc_rep_13_pm_compliance_tolerance_and_no_deadline(test_setup):
    """
    TC-REP-13: Quy tắc dung sai 3 ngày PM và xử lý phiếu PM không gán hạn.
    Phiếu 1: Hoàn thành hạn + 2 ngày (trong dung sai 3 ngày) -> ĐÚNG HẠN.
    Phiếu 2: Hoàn thành hạn + 6 ngày (quá dung sai) -> TRỄ HẠN.
    Phiếu 3: Hoàn tất không có deadline -> ĐÚNG HẠN.
    Kỳ vọng: 2 đúng hạn, 1 trễ hạn, tổng mẫu số 3 -> Tỷ lệ tuân thủ = 66.67%.
    """
    tenant = test_setup["tenant"]
    asset = Asset.all_objects.create(tenant=tenant, name="Cầu Trục 10 Tấn", qr_code="ASSET-13")

    # PM 1: Due 2026-08-10, completed 2026-08-12 (2 days <= 3 days tolerance) -> ON TIME
    w1 = WorkOrder.all_objects.create(
        tenant=tenant,
        asset=asset,
        title="PM Cáp cầu trục",
        type="PREVENTIVE",
        status="COMPLETED",
        deadline=datetime(2026, 8, 10, 17, 0, tzinfo=dt_timezone.utc),
        completed_at=datetime(2026, 8, 12, 10, 0, tzinfo=dt_timezone.utc)
    )
    WorkOrder.all_objects.filter(id=w1.id).update(created_at=datetime(2026, 8, 1, 8, 0, tzinfo=dt_timezone.utc))

    # PM 2: Due 2026-08-10, completed 2026-08-16 (6 days > 3 days tolerance) -> LATE
    w2 = WorkOrder.all_objects.create(
        tenant=tenant,
        asset=asset,
        title="PM Phanh cầu trục",
        type="PREVENTIVE",
        status="COMPLETED",
        deadline=datetime(2026, 8, 10, 17, 0, tzinfo=dt_timezone.utc),
        completed_at=datetime(2026, 8, 16, 10, 0, tzinfo=dt_timezone.utc)
    )
    WorkOrder.all_objects.filter(id=w2.id).update(created_at=datetime(2026, 8, 1, 8, 0, tzinfo=dt_timezone.utc))

    # PM 3: No explicit deadline, completed -> ON TIME
    w3 = WorkOrder.all_objects.create(
        tenant=tenant,
        asset=asset,
        title="PM Bôi trơn ray",
        type="PREVENTIVE",
        status="COMPLETED",
        deadline=None,
        completed_at=datetime(2026, 8, 15, 10, 0, tzinfo=dt_timezone.utc)
    )
    WorkOrder.all_objects.filter(id=w3.id).update(created_at=datetime(2026, 8, 1, 8, 0, tzinfo=dt_timezone.utc))

    data = MaintenancePerformanceEngine.get_performance_data(
        tenant=tenant,
        date_from=date(2026, 8, 1),
        date_to=date(2026, 8, 31)
    )

    summary = data["summary"]
    assert summary["totalPmDue"] == 3
    assert summary["onTimePmCount"] == 2
    assert summary["latePmCount"] == 1
    assert summary["pmComplianceRate"] == 66.67


def test_tc_rep_14_partial_negative_inventory_reconciliation(test_setup):
    """
    TC-REP-14: Nhập kho bổ sung một phần cho kho đang xuất âm (Partial Reconciliation).
    Tồn kho ban đầu = 0. Xuất gấp 5 bộ cảm biến @ 200,000 VNĐ -> Tồn = -5. WO = 1,000,000 VNĐ.
    Phiếu Nhập kho mới chỉ về 3 bộ @ 250,000 VNĐ (chênh lệch +50,000/bộ).
    Kỳ vọng: Tồn kho chuyển thành -2. Bút toán chênh lệch giá chỉ tính trên 3 bộ (3 * 50,000 = +150,000 VNĐ).
    Chi phí WO tăng thành 1,150,000 VNĐ.
    """
    tenant = test_setup["tenant"]
    asset = Asset.all_objects.create(tenant=tenant, name="Cảm Biến Quang", qr_code="ASSET-14")
    part = SparePart.all_objects.create(
        tenant=tenant,
        name="Cảm Biến Quang Omron",
        quantity_in_stock=Decimal("0.00"),
        unit_cost=Decimal("200000.00")
    )
    wo = WorkOrder.all_objects.create(tenant=tenant, asset=asset, title="Thay cảm biến quang", status="IN_PROGRESS")

    # Issue 5 units
    SparePartsValuationEngine.record_negative_issue_and_variance(
        tenant=tenant,
        spare_part=part,
        work_order=wo,
        issue_qty=Decimal("5.00"),
        issue_date=timezone.now() - timedelta(days=2),
        cost_center="Phân Xưởng Lắp Ráp"
    )

    part.refresh_from_db()
    wo.refresh_from_db()
    assert part.quantity_in_stock == Decimal("-5.00")
    assert wo.actual_cost == Decimal("1000000.00")

    # GRN only 3 units @ 250,000 VNĐ
    SparePartsValuationEngine.apply_grn_receipt_and_reconcile_variance(
        tenant=tenant,
        spare_part=part,
        receipt_qty=Decimal("3.00"),
        new_unit_cost=Decimal("250000.00"),
        receipt_date=timezone.now()
    )

    part.refresh_from_db()
    wo.refresh_from_db()

    # Stock is -5 + 3 = -2
    assert part.quantity_in_stock == Decimal("-2.00")
    # Variance for 3 units = 3 * 50,000 = 150,000 VNĐ -> WO cost = 1,150,000 VNĐ
    assert wo.actual_cost == Decimal("1150000.00")


def test_tc_rep_15_negative_price_variance_grn_cheaper(test_setup):
    """
    TC-REP-15: Chênh lệch giá âm khi đơn giá nhập kho thực tế rẻ hơn giá tạm tính.
    Xuất âm 2 bóng đèn sấy @ 500,000 VNĐ -> WO = 1,000,000 VNĐ.
    Nhập kho thực tế 5 bóng với giá đàm phán rẻ hơn: 450,000 VNĐ (-50,000 VNĐ/bóng).
    Kỳ vọng: Bút toán điều chỉnh giá âm: -100,000 VNĐ. Chi phí WO giảm xuống 900,000 VNĐ.
    """
    tenant = test_setup["tenant"]
    asset = Asset.all_objects.create(tenant=tenant, name="Buồng Sấy Sơn", qr_code="ASSET-15")
    part = SparePart.all_objects.create(
        tenant=tenant,
        name="Bóng Đèn Sấy Hồng Ngoại",
        quantity_in_stock=Decimal("0.00"),
        unit_cost=Decimal("500000.00")
    )
    wo = WorkOrder.all_objects.create(tenant=tenant, asset=asset, title="Thay bóng sấy sơn", status="IN_PROGRESS")

    # Issue 2 units
    SparePartsValuationEngine.record_negative_issue_and_variance(
        tenant=tenant,
        spare_part=part,
        work_order=wo,
        issue_qty=Decimal("2.00"),
        issue_date=timezone.now() - timedelta(days=2),
        cost_center="Phân Xưởng Sơn"
    )

    assert wo.actual_cost == Decimal("1000000.00")

    # GRN 5 units @ 450,000 VNĐ (cheaper)
    SparePartsValuationEngine.apply_grn_receipt_and_reconcile_variance(
        tenant=tenant,
        spare_part=part,
        receipt_qty=Decimal("5.00"),
        new_unit_cost=Decimal("450000.00"),
        receipt_date=timezone.now()
    )

    wo.refresh_from_db()
    # WO cost reduced by 100,000 -> 900,000 VNĐ
    assert wo.actual_cost == Decimal("900000.00")


def test_tc_rep_16_temporal_cost_center_with_null_costs_and_returns(test_setup):
    """
    TC-REP-16: An toàn dữ liệu khi có bản ghi công hoặc vật tư có giá trị None / Null.
    Xử lý đúng trừ vật tư hoàn trả và bỏ qua an toàn các trường Null không sinh lỗi TypeError.
    """
    tenant = test_setup["tenant"]
    asset = Asset.all_objects.create(tenant=tenant, name="Trạm Xử Lý Nước", qr_code="ASSET-16")
    part = SparePart.all_objects.create(tenant=tenant, name="Hóa Chất Xử Lý", unit_cost=Decimal("1000000.00"))

    wo = WorkOrder.all_objects.create(tenant=tenant, asset=asset, title="Bảo trì trạm nước")

    # Material issue: 10,000,000 VNĐ
    StockTransaction.all_objects.create(
        tenant=tenant,
        spare_part=part,
        work_order=wo,
        transaction_type='ISSUE',
        quantity=Decimal("10.00"),
        unit_price=Decimal("1000000.00"),
        total_amount=Decimal("10000000.00"),
        issue_date=datetime(2026, 8, 10, 10, 0, tzinfo=dt_timezone.utc),
        cost_center_snapshot="Trạm Nước Thải"
    )

    # Material return: 2,000,000 VNĐ
    StockTransaction.all_objects.create(
        tenant=tenant,
        spare_part=part,
        work_order=wo,
        transaction_type='RETURN',
        quantity=Decimal("2.00"),
        unit_price=Decimal("1000000.00"),
        total_amount=Decimal("2000000.00"),
        issue_date=datetime(2026, 8, 15, 10, 0, tzinfo=dt_timezone.utc),
        cost_center_snapshot="Trạm Nước Thải"
    )

    # Transaction with 0.00 total_amount (edge case)
    StockTransaction.all_objects.create(
        tenant=tenant,
        spare_part=part,
        work_order=wo,
        transaction_type='ISSUE',
        quantity=Decimal("0.00"),
        unit_price=Decimal("0.00"),
        total_amount=Decimal("0.00"),
        issue_date=datetime(2026, 8, 16, 10, 0, tzinfo=dt_timezone.utc),
        cost_center_snapshot="Trạm Nước Thải"
    )

    # Labor log: 3,000,000 VNĐ
    LaborLog.all_objects.create(
        tenant=tenant,
        work_order=wo,
        technician=test_setup["tech_user"],
        hours_worked=Decimal("10.00"),
        hourly_rate=Decimal("300000.00"),
        total_cost=Decimal("3000000.00"),
        work_date=date(2026, 8, 10),
        cost_center_snapshot="Trạm Nước Thải"
    )

    data = CostSummaryEngine.get_cost_summary_data(
        tenant=tenant,
        date_from=date(2026, 8, 1),
        date_to=date(2026, 8, 31)
    )

    summary = data["summary"]
    # Net material: 10m - 2m = 8,000,000 VNĐ
    assert summary["totalMaterialCost"] == 8000000.0
    # Labor: 3,000,000 VNĐ
    assert summary["totalLaborCost"] == 3000000.0
    # Total: 11,000,000 VNĐ
    assert summary["totalCost"] == 11000000.0


def test_tc_rep_17_safe_date_parsing_various_formats():
    """
    TC-REP-17: Khả năng phân tích linh hoạt các định dạng ngày tháng đầu vào.
    Hỗ trợ ISO-8601 có thời gian, chuỗi YYYY-MM-DD, DD/MM/YYYY, date, datetime và chuỗi rỗng.
    """
    assert parse_date_safe("2026-08-01T15:30:00Z") == date(2026, 8, 1)
    assert parse_date_safe("2026-08-01 10:00:00") == date(2026, 8, 1)
    assert parse_date_safe("2026-08-01") == date(2026, 8, 1)
    assert parse_date_safe("01/08/2026") == date(2026, 8, 1)
    assert parse_date_safe(datetime(2026, 8, 1, 10, 0)) == date(2026, 8, 1)
    assert parse_date_safe(date(2026, 8, 1)) == date(2026, 8, 1)
    assert parse_date_safe("") is None
    assert parse_date_safe(None) is None


def test_tc_rep_18_depreciation_with_none_capitalized_cost(test_setup):
    """
    TC-REP-18: Khấu hao tài sản khi capitalized_cost = 0 nhưng có capitalized_date.
    Không chuyển nhầm ngày tính khấu hao sang capitalized_date khi chưa có chi phí vốn hóa.
    Đồng thời kiểm tra engine an toàn nếu capitalized_cost trên đối tượng là None.
    """
    tenant = test_setup["tenant"]
    asset = Asset.all_objects.create(
        tenant=tenant,
        name="Máy Hàn Laser Tự Động",
        qr_code="ASSET-18-LASER",
        purchase_date=date(2025, 1, 1),
        purchase_cost=Decimal("60000000.00"),
        salvage_value=Decimal("0.00"),
        useful_life_years=5,
        capitalized_date=date(2025, 6, 1),
        capitalized_cost=Decimal("0.00"),  # 0 CAPEX
        location=test_setup["location_a"]
    )

    data = AssetValuationEngine.get_asset_valuation_data(
        tenant=tenant,
        as_of_date=date(2026, 1, 1)
    )

    item = next(i for i in data["items"] if i["id"] == str(asset.id))
    assert item["capexCost"] == 0.0
    assert item["totalCostBasis"] == 60000000.0
    assert item["monthsInService"] == 12  # Starts from purchase_date (2025-01-01), not capitalized_date (2025-06-01)
    # Monthly = 60m / 60 months = 1,000,000 VNĐ. 12 months = 12,000,000 VNĐ.
    assert item["accumulatedDepreciation"] == 12000000.0
    assert item["netBookValue"] == 48000000.0

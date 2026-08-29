import pytest
from playwright.sync_api import expect
from faker import Faker
from pages.work_orders_page import WorkOrdersPage
from pages.assets_page import AssetsPage

fake = Faker()

@pytest.fixture(scope="module")
def wo_data():
    return {
        "title": f"E2E WO {fake.word()}",
        "asset": "E2E Asset", # Assume this exists or will just type it
        "priority": "HIGH",
        "new_status": "IN_PROGRESS"
    }

def test_work_order_crud_and_lifecycle(auth_page, base_url, wo_data):
    page = WorkOrdersPage(auth_page, base_url)
    page.go_to()
    
    page.create_work_order(wo_data["title"], "E2E Asset", wo_data["priority"])
    auth_page.wait_for_url("**/work-orders/")
    
    # Check if WO appears in the table
    expect(auth_page.locator(f'tr:has-text("{wo_data["title"]}")').first).to_be_visible()
    
    # Transition status to IN_PROGRESS
    page.change_status(wo_data["title"], wo_data["new_status"])
    auth_page.wait_for_url("**/work-orders/")
    
    # Verify status badge updated
    row = auth_page.locator(f'tr:has-text("{wo_data["title"]}")').first
    expect(row.locator('td:nth-child(4)')).to_have_text(wo_data["new_status"])

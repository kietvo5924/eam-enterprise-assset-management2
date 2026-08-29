import pytest
from playwright.sync_api import expect
from faker import Faker
from pages.inventory_page import InventoryPage

fake = Faker()

@pytest.fixture(scope="module")
def inventory_data():
    return {
        "part_name": f"E2E Part {fake.word()}",
        "part_sku": f"SKU-{fake.ean8()}",
        "stock": 100,
        "min_stock": 20
    }

def test_inventory_crud(auth_page, base_url, inventory_data):
    page = InventoryPage(auth_page, base_url)
    page.go_to()
    
    page.create_spare_part(
        inventory_data["part_name"],
        inventory_data["part_sku"],
        inventory_data["stock"],
        inventory_data["min_stock"]
    )
    
    auth_page.wait_for_url("**/inventory/")
    expect(auth_page.locator(f'tr:has-text("{inventory_data["part_sku"]}")').first).to_be_visible()

@pytest.mark.skip(reason="Adjustment modal not implemented yet")
def test_inventory_adjustment_and_threshold(auth_page, base_url, inventory_data):
    page = InventoryPage(auth_page, base_url)
    page.go_to()
    
    # We started with 100 stock. We adjust out 90, so stock becomes 10.
    # Since 10 < 20 (min_stock), the threshold warning badge should appear.
    page.adjust_stock(inventory_data["part_sku"], 90, is_in=False)
    page.get_toast("success").wait_for(state="visible", timeout=5000)
    
    row = auth_page.locator(f'tr:has-text("{inventory_data["part_sku"]}")').first
    
    # Assert stock is 10
    expect(row.locator('.stock-quantity')).to_have_text("10")
    
    # Assert threshold alert class (e.g. text-danger) is applied
    expect(row.locator('.stock-quantity')).to_have_class("text-danger")

import re
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
    
    auth_page.wait_for_url(re.compile(r".*\/inventory\/.*"))
    expect(auth_page.locator(f'tr:has-text("{inventory_data["part_sku"]}")').first).to_be_visible()


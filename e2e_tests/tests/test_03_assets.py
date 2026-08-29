import pytest
from playwright.sync_api import expect
from faker import Faker
from pages.assets_page import HierarchyTemplatesPage, AssetCategoriesPage, AssetsPage

fake = Faker()

@pytest.fixture(scope="module")
def asset_data():
    return {
        "template_name": f"E2E Template {fake.word()}",
        "category_name": f"E2E Category {fake.word()}",
        "asset_name": f"E2E Asset {fake.word()}",
        "asset_model": "Model-X",
        "asset_serial": fake.uuid4()[:8]
    }

def test_hierarchy_templates(auth_page, base_url, asset_data):
    page = HierarchyTemplatesPage(auth_page, base_url)
    page.go_to()
    page.create_template(asset_data["template_name"], "E2E Test Template")
    
    # Form does standard post and reload
    auth_page.wait_for_url(f"{base_url}/hierarchy-templates/")
    
def test_asset_categories(auth_page, base_url, asset_data):
    page = AssetCategoriesPage(auth_page, base_url)
    page.go_to()
    page.create_category(asset_data["category_name"], "E2E Test Category")
    auth_page.wait_for_url(f"{base_url}/asset-categories/")

def test_asset_registry(auth_page, base_url, asset_data):
    page = AssetsPage(auth_page, base_url)
    page.go_to()
    page.create_asset(asset_data["asset_name"], asset_data["asset_model"], asset_data["asset_serial"])
    auth_page.wait_for_url(f"{base_url}/assets/")
    
    # Verify the asset appears in the tree view
    expect(auth_page.locator(f'.tree-node:has-text("{asset_data["asset_name"]}")').first).to_be_visible()

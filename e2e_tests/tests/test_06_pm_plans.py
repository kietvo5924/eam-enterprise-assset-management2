import pytest
from playwright.sync_api import expect
from faker import Faker
from pages.pm_plans_page import PmPlansPage

fake = Faker()

@pytest.fixture(scope="module")
def pm_data():
    return {
        "title": f"E2E PM {fake.word()}",
        "frequency": "MONTHS"
    }

def test_pm_plans_crud(auth_page, base_url, pm_data):
    page = PmPlansPage(auth_page, base_url)
    page.go_to()
    
    page.create_pm_plan(pm_data["title"], pm_data["frequency"])
    auth_page.wait_for_url("**/pm-plans/")
    page.switch_to_plans_view()
    
    # Check if PM plan appears
    expect(auth_page.locator(f'tr:has-text("{pm_data["title"]}")').first).to_be_visible()

    # Edit PM plan
    page.edit_pm_plan(pm_data["title"], f"{pm_data['title']} Edited")
    auth_page.reload()
    page.switch_to_plans_view()
    
    expect(auth_page.locator(f'tr:has-text("{pm_data["title"]} Edited")').first).to_be_visible()

    # Delete PM plan
    page.delete_pm_plan(f"{pm_data['title']} Edited")
    auth_page.reload()
    page.switch_to_plans_view()
    
    expect(auth_page.locator(f'tr:has-text("{pm_data["title"]} Edited")')).not_to_be_visible()

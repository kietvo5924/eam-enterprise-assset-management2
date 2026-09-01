import pytest
from playwright.sync_api import expect
from faker import Faker
from pages.settings_page import SettingsPage
from pages.roles_page import RolesPage

fake = Faker()

@pytest.fixture(scope="module")
def admin_data():
    return {
        "org_name": f"E2E Corp {fake.company()}",
        "role_name": f"E2E Role {fake.job()}",
        "role_name_edited": f"E2E Role Edited {fake.job()}",
        "role_desc": "Automated role for E2E testing",
        "fallback_role": "SUPER_ADMIN" # We will use the system super admin as fallback for deletion testing
    }

def test_tenant_settings(auth_page, base_url, admin_data):
    settings_page = SettingsPage(auth_page, base_url)
    settings_page.go_to()
    
    # Wait for the current data to load
    expect(auth_page.locator('#input-name')).not_to_be_empty(timeout=5000)
    
    # Update settings
    logo_url = "https://example.com/logo.png"
    settings_page.update_settings(admin_data["org_name"], "Asia/Ho_Chi_Minh", logo_url)
    
    # Wait for the success message to ensure API call finished
    settings_page.wait_for_success()
    
    # Reload page to verify persistence
    auth_page.reload()
    
    # Wait for reload to complete
    expect(auth_page.locator('#input-name')).not_to_be_empty(timeout=5000)
    
    # Verify the UI reflects the new name in the left panel
    expect(auth_page.locator('#display-name')).to_have_text(admin_data["org_name"])
    expect(auth_page.locator('#display-timezone')).to_have_text("Asia/Ho_Chi_Minh")
    
    # Verify inputs have the saved values
    expect(auth_page.locator('#input-name')).to_have_value(admin_data["org_name"])
    expect(auth_page.locator('#input-timezone')).to_have_value("Asia/Ho_Chi_Minh")
    expect(auth_page.locator('#input-logoUrl')).to_have_value(logo_url)

def test_roles_crud(auth_page, base_url, admin_data):
    roles_page = RolesPage(auth_page, base_url)
    roles_page.go_to()
    
    # Create role
    # Assuming some permissions from the system exist, e.g. "asset:read", "work_order:read"
    roles_page.create_role(admin_data["role_name"], admin_data["role_desc"], ["Read Assets", "Read Work Orders"])
    
    # Verify role appears in the list (wait for reload/rendering)
    roles_page.verify_role_exists(admin_data["role_name"])
    
    # Edit role
    roles_page.edit_role(admin_data["role_name"], admin_data["role_name_edited"])
    roles_page.verify_role_exists(admin_data["role_name_edited"])
    
    # Delete role
    roles_page.delete_role(admin_data["role_name_edited"])
    
    # Verify deletion
    expect(auth_page.locator(f'tr:has-text("{admin_data["role_name_edited"]}")').first).not_to_be_visible()

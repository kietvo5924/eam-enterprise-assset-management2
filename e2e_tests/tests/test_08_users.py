import pytest
from playwright.sync_api import expect
from faker import Faker
from pages.users_page import UsersPage

fake = Faker()

@pytest.fixture(scope="module")
def user_data():
    return {
        "username": f"e2e_user_{fake.user_name()}",
        "email": f"e2e_{fake.email()}",
        "password": "Password123!",
        "username_edited": f"e2e_user_edited_{fake.user_name()}",
        "email_edited": f"e2e_edited_{fake.email()}"
    }

def test_users_crud(auth_page, base_url, user_data):
    users_page = UsersPage(auth_page, base_url)
    users_page.go_to()
    
    # Create user
    users_page.open_create_modal()
    users_page.fill_user_form(
        user_data["username"], 
        user_data["email"], 
        user_data["password"], 
        "ACTIVE"
    )
    users_page.submit_form()
    
    # Wait for page reload
    auth_page.wait_for_url("**/users/")
    
    # Verify user appears
    users_page.verify_user_exists(user_data["username"])
    users_page.verify_user_status(user_data["username"], "ACTIVE")
    
    # Edit user
    users_page.edit_user(
        user_data["username"], 
        user_data["username_edited"], 
        user_data["email_edited"]
    )
    
    # Wait for page reload
    auth_page.wait_for_url("**/users/")
    
    # Verify edited user exists
    users_page.verify_user_exists(user_data["username_edited"])
    
    # Delete user
    users_page.delete_user(user_data["username_edited"])
    
    # Wait for reload
    auth_page.wait_for_url("**/users/")
    
    # Verify deletion
    expect(auth_page.locator(f'tr:has-text("{user_data["username_edited"]}")').first).not_to_be_visible()

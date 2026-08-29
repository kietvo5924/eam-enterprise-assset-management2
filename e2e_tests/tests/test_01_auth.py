import pytest
from playwright.sync_api import expect
from pages.auth_page import AuthPage

def test_login_success(page, base_url, admin_user):
    auth_page = AuthPage(page, base_url)
    auth_page.login(admin_user["username"], admin_user["password"])
    
    # Wait for navigation to dashboard
    page.wait_for_url(f"{base_url}/")
    
    # Verify Dashboard elements (look for the "Chào buổi sáng" text or the sidebar Dashboard item)
    expect(page.locator("h1").filter(has_text="Chào buổi sáng")).to_be_visible()
    
def test_login_failure(page, base_url):
    auth_page = AuthPage(page, base_url)
    auth_page.login("wronguser", "wrongpass")
    
    # Look for the error alert
    # The django login view flashes a message, but let's check if we stay on login
    expect(page).to_have_url(f"{base_url}/login/")

def test_logout(page, base_url, admin_user):
    auth_page = AuthPage(page, base_url)
    auth_page.login(admin_user["username"], admin_user["password"])
    page.wait_for_url(f"{base_url}/")
    
    # Open the user menu
    page.locator('#user-menu-btn').first.click()
    # Click logout
    auth_page.logout()
    
    # Expect redirect to login
    page.wait_for_url(f"{base_url}/login/")

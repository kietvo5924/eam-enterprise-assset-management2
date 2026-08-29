import pytest
from playwright.sync_api import Browser, Page

@pytest.fixture(scope="session")
def admin_user():
    # Credentials from the seed_core script
    return {
        "username": "superadmin@eam.local",
        "password": "admin123"
    }

@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {
        **browser_context_args,
        "viewport": {
            "width": 1280,
            "height": 720,
        }
    }

@pytest.fixture
def auth_page(page: Page, base_url: str, admin_user: dict):
    """
    Logs in the user and returns the authenticated page.
    This fixture ensures we start from the dashboard for tests requiring auth.
    """
    page.goto(f"{base_url}/login/")
    page.fill('input[name="username"]', admin_user["username"])
    page.fill('input[name="password"]', admin_user["password"])
    page.click('button[type="submit"]')
    page.wait_for_url(f"{base_url}/")
    return page

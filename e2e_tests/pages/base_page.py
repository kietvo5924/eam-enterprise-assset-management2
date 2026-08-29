from playwright.sync_api import Page, expect

class BasePage:
    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url

    def navigate(self, path: str):
        self.page.goto(f"{self.base_url}{path}")

    def get_toast(self, type="success"):
        # We look for elements containing the success or danger classes that our UI templates use
        if type == "success":
            return self.page.locator('.text-success').first
        return self.page.locator('.text-danger').first

from playwright.sync_api import Page, expect
from .base_page import BasePage

class AuthPage(BasePage):
    def __init__(self, page: Page, base_url: str):
        super().__init__(page, base_url)

    def login(self, username, password):
        self.navigate("/login/")
        self.page.fill('input[name="username"]', username)
        self.page.fill('input[name="password"]', password)
        self.page.click('button[type="submit"]')

    def logout(self):
        self.page.click('button:has-text("Logout")')

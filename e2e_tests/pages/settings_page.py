from playwright.sync_api import Page, expect
from .base_page import BasePage

class SettingsPage(BasePage):
    def __init__(self, page: Page, base_url: str):
        super().__init__(page, base_url)

    def go_to(self):
        self.navigate("/settings/")

    def update_settings(self, name, timezone):
        self.page.fill('input[name="name"]', name)
        self.page.select_option('select[name="timezone"]', value=timezone)
        self.page.click('#save-btn')
        
    def wait_for_success(self):
        expect(self.page.locator('#settings-message').filter(has_text="Settings updated successfully!")).to_be_visible()

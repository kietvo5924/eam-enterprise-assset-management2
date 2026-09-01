from playwright.sync_api import Page, expect
from .base_page import BasePage

class ReportsPage(BasePage):
    def __init__(self, page: Page, base_url: str):
        super().__init__(page, base_url)

    def go_to(self):
        self.navigate("/reports/")

    def verify_page_loads(self):
        expect(self.page.locator('h2', has_text="System Reports")).to_be_visible()
        expect(self.page.locator('h3', has_text="Monthly Analytics")).to_be_visible()
        expect(self.page.locator('h3', has_text="Asset Downtime by Category")).to_be_visible()
        expect(self.page.locator('h3', has_text="Maintenance Cost Trend")).to_be_visible()

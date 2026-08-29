from playwright.sync_api import Page, expect
from .base_page import BasePage

class DashboardPage(BasePage):
    def __init__(self, page: Page, base_url: str):
        super().__init__(page, base_url)

    def go_to(self):
        self.navigate("/")

    def verify_kpis_visible(self):
        expect(self.page.locator('h3:has-text("Work Order Trends")')).to_be_visible(timeout=5000)
        
    def verify_chart_visible(self):
        expect(self.page.locator('svg').first).to_be_visible()

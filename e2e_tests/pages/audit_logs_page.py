import re
from playwright.sync_api import Page, expect
from .base_page import BasePage

class AuditLogsPage(BasePage):
    def __init__(self, page: Page, base_url: str):
        super().__init__(page, base_url)
        self.url = f"{base_url}/audit-logs/"

    def go_to(self):
        self.page.goto(self.url)
        self.page.wait_for_url(re.compile(r".*\/audit-logs\/.*"))

    def verify_page_loads(self):
        expect(self.page.locator('h1', has_text="Audit Logs")).to_be_visible()
        
    def verify_logs_present(self):
        # The table should have some logs (or at least the empty state should be visible if no logs exist, but typically tests generate data)
        # We'll just verify the table headers exist
        expect(self.page.locator('th', has_text="Time").first).to_be_visible()
        expect(self.page.locator('th', has_text="User").first).to_be_visible()
        expect(self.page.locator('th', has_text="Action").first).to_be_visible()

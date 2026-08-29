from playwright.sync_api import Page, expect
from .base_page import BasePage

class WorkOrdersPage(BasePage):
    def __init__(self, page: Page, base_url: str):
        super().__init__(page, base_url)

    def go_to(self):
        self.navigate("/work-orders/")

    def create_work_order(self, title, asset_name, priority="HIGH"):
        self.page.evaluate('openWoModal()')
        expect(self.page.locator('#wo-modal')).to_be_visible()
        self.page.fill('#wo-title', title)
        
        # Select asset (assuming it's a select element or searchable dropdown)
        # Using a simple select for now, adjust based on actual DOM
        self.page.select_option('#wo-asset', index=1)
        self.page.select_option('#wo-priority', value=priority)
        
        self.page.click('#btn-save-wo')

    def change_status(self, title, new_status):
        row = self.page.locator(f'tr:has-text("{title}")').first
        # Click the edit button
        row.locator('button[title="Chỉnh sửa"]').click()
        
        expect(self.page.locator('#wo-modal')).to_be_visible()
        
        # Depending on the UI, status change might be a button or dropdown
        # Example: a direct button for status transition
        status_btn = self.page.locator(f'button:has-text("{new_status}")').first
        if status_btn.is_visible():
            status_btn.click()
        else:
            self.page.select_option('#wo-status', value=new_status)
            self.page.click('#btn-save-wo')

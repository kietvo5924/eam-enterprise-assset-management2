from playwright.sync_api import Page, expect
from .base_page import BasePage

class PmPlansPage(BasePage):
    def __init__(self, page: Page, base_url: str):
        super().__init__(page, base_url)

    def go_to(self):
        self.navigate("/pm-plans/")

    def switch_to_plans_view(self):
        self.page.evaluate('switchView("plans")')
        expect(self.page.locator('#view-plans')).to_be_visible()

    def create_pm_plan(self, title, frequency):
        self.page.evaluate('openPmModal()')
        expect(self.page.locator('#pm-modal')).to_be_visible()
        self.page.fill('#pm-name', title)
        
        self.page.fill('#pm-interval-value', "1")
        self.page.select_option('#pm-interval-unit', value=frequency)
        
        self.page.click('#btn-save-pm')

    def edit_pm_plan(self, old_title, new_title):
        self.switch_to_plans_view()
        row = self.page.locator(f'tr:has-text("{old_title}")').first
        row.click()
        expect(self.page.locator('#pm-modal')).to_be_visible()
        self.page.fill('#pm-name', new_title)
        self.page.click('#btn-save-pm')
        
    def delete_pm_plan(self, title):
        self.switch_to_plans_view()
        self.page.on("dialog", lambda dialog: dialog.accept())
        row = self.page.locator(f'tr:has-text("{title}")').first
        row.locator('button[onclick*="deletePm"]').evaluate("node => node.click()")

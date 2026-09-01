import re
from playwright.sync_api import Page, expect
from .base_page import BasePage

class UsersPage(BasePage):
    def __init__(self, page: Page, base_url: str):
        super().__init__(page, base_url)
        self.url = f"{base_url}/users/"

    def go_to(self):
        self.page.goto(self.url)
        self.page.wait_for_url(re.compile(r".*\/users\/.*"))

    def open_create_modal(self):
        self.page.get_by_role("button", name="Add User").click()
        expect(self.page.locator('#user-modal')).to_be_visible()

    def fill_user_form(self, username: str, email: str, password: str, status: str = "ACTIVE"):
        self.page.locator('#user-username').fill(username)
        self.page.locator('#user-email').fill(email)
        if password:
            self.page.locator('#user-password').fill(password)
        
        status_locator = self.page.locator('#user-status')
        if status_locator.is_visible():
            status_locator.select_option(status)
        
    def submit_form(self):
        self.page.locator('#btn-save-user').click()
        
    def verify_user_exists(self, username: str):
        row = self.page.locator(f'tr:has-text("{username}")').first
        expect(row).to_be_visible()
        
    def verify_user_status(self, username: str, status: str):
        row = self.page.locator(f'tr:has-text("{username}")').first
        if status == "ACTIVE":
            expect(row.locator('.bg-green-50')).to_contain_text("ACTIVE")
        elif status == "PENDING":
            expect(row.locator('.bg-warning\\/10')).to_contain_text("PENDING")
        else:
            expect(row).to_contain_text(status)
            
    def edit_user(self, old_username: str, new_username: str, new_email: str):
        row = self.page.locator(f'tr:has-text("{old_username}")').first
        row.locator('button i.ph-pencil-simple').locator('..').click()
        expect(self.page.locator('#user-modal')).to_be_visible()
        self.fill_user_form(new_username, new_email, "")
        self.submit_form()

    def disable_user(self, username: str):
        row = self.page.locator(f'tr:has-text("{username}")').first
        self.page.once("dialog", lambda dialog: dialog.accept())
        row.locator('button i.ph-prohibit').locator('..').click()

from playwright.sync_api import Page, expect
from .base_page import BasePage

class RolesPage(BasePage):
    def __init__(self, page: Page, base_url: str):
        super().__init__(page, base_url)

    def go_to(self):
        self.navigate("/roles/")

    def create_role(self, name, description, permission_names=None):
        self.page.click('button:has-text("Create Role")')
        expect(self.page.locator('#role-modal')).to_be_visible()
        self.page.fill('#role-name', name)
        self.page.fill('#role-desc', description)
        
        if permission_names:
            for p_name in permission_names:
                # Find the checkbox that is a sibling/descendant of the label containing the text
                label = self.page.locator('label').filter(has_text=p_name).first
                label.click()
        
        self.page.click('#btn-save-role')
        
    def edit_role(self, role_name, new_name):
        # Click edit button for the specific role row
        row = self.page.locator(f'tr:has-text("{role_name}")').first
        row.locator('button[title="Edit"]').click()
        
        expect(self.page.locator('#role-modal')).to_be_visible()
        self.page.fill('#role-name', new_name)
        self.page.click('#btn-save-role')

    def verify_role_exists(self, name):
        expect(self.page.locator(f'tr:has-text("{name}")').first).to_be_visible()

    def delete_role(self, name):
        # Need to handle confirmation dialog
        self.page.on("dialog", lambda dialog: dialog.accept())
        row = self.page.locator(f'tr:has-text("{name}")').first
        row.locator('button[title="Delete"]').click()

    def delete_assigned_role_and_reassign(self, name, fallback_name):
        # This will trigger the reassign modal instead of standard JS confirm if the role has users
        self.page.once("dialog", lambda dialog: dialog.accept())
        row = self.page.locator(f'tr:has-text("{name}")').first
        row.locator('button[title="Delete"]').click()
        
        # Now expect the reassign modal
        expect(self.page.locator('#reassign-modal')).to_be_visible(timeout=5000)
        self.page.select_option('#fallback-role-id', label=fallback_name)
        self.page.click('#btn-confirm-delete')

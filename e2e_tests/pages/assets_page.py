from playwright.sync_api import Page, expect
from .base_page import BasePage

class HierarchyTemplatesPage(BasePage):
    def __init__(self, page: Page, base_url: str):
        super().__init__(page, base_url)

    def go_to(self):
        self.navigate("/hierarchy-templates/")

    def create_template(self, name, desc):
        self.page.click('button[onclick="openTemplateModal()"]')
        expect(self.page.locator('#template-modal')).to_be_visible()
        self.page.fill('#template-name', name)
        self.page.fill('#template-desc', desc)
        self.page.click('#btn-save-template')

class AssetCategoriesPage(BasePage):
    def __init__(self, page: Page, base_url: str):
        super().__init__(page, base_url)

    def go_to(self):
        self.navigate("/asset-categories/")

    def create_category(self, name, desc):
        self.page.click('button[onclick="openCategoryModal()"]')
        expect(self.page.locator('#category-modal')).to_be_visible()
        self.page.fill('#category-name', name)
        self.page.fill('#category-desc', desc)
        self.page.click('#btn-save-category')

class AssetsPage(BasePage):
    def __init__(self, page: Page, base_url: str):
        super().__init__(page, base_url)

    def go_to(self):
        self.navigate("/assets/")

    def create_asset(self, name, model, serial):
        self.page.click('button[onclick="openAssetModal()"]')
        expect(self.page.locator('#asset-modal')).to_be_visible()
        self.page.fill('#asset-name', name)
        self.page.fill('#asset-model', model)
        self.page.fill('#asset-serial', serial)
        # Assuming we can just save it directly
        self.page.click('#btn-save-asset')
        
    def add_meter_reading(self, asset_name, reading_value):
        # Select the asset in the left tree
        self.page.locator(f'.tree-node:has-text("{asset_name}")').first.click()
        
        # Click Add Reading in the Details Panel
        self.page.click('button[title="Add Meter Reading"]')
        self.page.fill('#meter-reading-value', str(reading_value))
        self.page.fill('#meter-reading-unit', "Hours")
        self.page.click('#btn-save-reading')

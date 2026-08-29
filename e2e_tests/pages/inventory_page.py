from playwright.sync_api import Page, expect
from .base_page import BasePage

class InventoryPage(BasePage):
    def __init__(self, page: Page, base_url: str):
        super().__init__(page, base_url)

    def go_to(self):
        self.navigate("/inventory/")

    def create_spare_part(self, name, sku, stock, min_stock=0, unit_cost=0):
        self.page.click('button[onclick="openInventoryModal()"]')
        expect(self.page.locator('#inventory-modal')).to_be_visible()
        self.page.fill('#inv-name', name)
        self.page.fill('#inv-part-number', sku)
        self.page.fill('#inv-quantity', str(stock))
        self.page.fill('#inv-unit-cost', str(unit_cost))
        self.page.click('#btn-save-inv')
        
    def adjust_stock(self, sku, amount, is_in=True):
        row = self.page.locator(f'tr:has-text("{sku}")').first
        row.locator('button[title="Adjust Stock"]').click()
        
        if is_in:
            self.page.click('#type-in')
        else:
            self.page.click('#type-out')
            
        self.page.fill('#adjust-amount', str(amount))
        self.page.click('#btn-save-adjustment')

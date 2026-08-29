import pytest
from playwright.sync_api import expect
from pages.dashboard_page import DashboardPage

def test_dashboard_elements(auth_page, base_url):
    page = DashboardPage(auth_page, base_url)
    page.go_to()
    
    # Wait for the dashboard to load
    expect(auth_page.locator("h3").filter(has_text="Work Order Trends")).to_be_visible()
    
    # Verify KPI cards and charts
    # These verify the UI layout is intact and the canvas rendered
    page.verify_kpis_visible()
    page.verify_chart_visible()

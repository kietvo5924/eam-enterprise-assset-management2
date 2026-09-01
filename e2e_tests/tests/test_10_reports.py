import pytest
from pages.reports_page import ReportsPage

def test_reports_view(auth_page, base_url):
    reports_page = ReportsPage(auth_page, base_url)
    reports_page.go_to()
    
    # Verify the page loaded correctly and all placeholder charts are visible
    reports_page.verify_page_loads()

import pytest
from playwright.sync_api import expect
from pages.audit_logs_page import AuditLogsPage

def test_audit_logs_view(auth_page, base_url):
    page = AuditLogsPage(auth_page, base_url)
    page.go_to()
    
    # Verify the page loaded correctly
    page.verify_page_loads()
    
    # Verify the logs table is present
    page.verify_logs_present()

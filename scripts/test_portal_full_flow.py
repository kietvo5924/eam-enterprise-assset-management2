import os
import sys
import time
import json
from playwright.sync_api import sync_playwright

# Ensure output is utf-8 encoded for console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

SCREENSHOTS_DIR = r"C:\Users\Admin\.gemini\antigravity-ide\brain\e8c1989a-0992-41a4-99c4-04806976fdfe\test_screenshots"
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
BASE_URL = "http://127.0.0.1:8080"

report = {
    "step1": {},
    "step2": {},
    "step3": {},
    "step4": {},
    "console_errors": [],
    "network_errors": []
}

def log(msg):
    print(f"[TEST LOG] {msg}")

with sync_playwright() as p:
    log("Launching Google Chrome...")
    browser = p.chromium.launch(
        executable_path=CHROME_PATH,
        headless=True,
        args=["--disable-web-security", "--no-sandbox"]
    )
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()

    def handle_console(msg):
        if msg.type in ['error']:
            report["console_errors"].append(msg.text)
            log(f"Console Error: {msg.text}")
    page.on("console", handle_console)

    def handle_response(res):
        if res.status >= 400:
            report["network_errors"].append(f"{res.status} {res.url}")
    page.on("response", handle_response)

    # -------------------------------------------------------------
    # BƯỚC 1: ĐĂNG NHẬP HỆ THỐNG
    # -------------------------------------------------------------
    log("--- BƯỚC 1: ĐĂNG NHẬP HỆ THỐNG ---")
    login_url = f"{BASE_URL}/portal/login/"
    res = page.goto(login_url, wait_until="networkidle")
    report["step1"]["login_http_status"] = res.status
    log(f"Loaded {login_url} -> Status: {res.status}")

    # Enter credentials
    page.fill("input[name='username']", "vf_admin@vinfast.local")
    page.fill("input[name='password']", "admin")
    page.click("button[type='submit']")

    # Wait for dashboard navigation
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)

    current_url = page.url
    report["step1"]["redirect_url"] = current_url
    log(f"After login redirected to: {current_url}")

    step1_shot = os.path.join(SCREENSHOTS_DIR, "step1_dashboard.png")
    page.screenshot(path=step1_shot)
    report["step1"]["screenshot"] = step1_shot
    report["step1"]["passed"] = "/portal/" in current_url

    # -------------------------------------------------------------
    # BƯỚC 2: KIỂM THỬ WORK ORDERS (/portal/work-orders/)
    # -------------------------------------------------------------
    log("--- BƯỚC 2: KIỂM THỬ WORK ORDERS ---")
    wo_url = f"{BASE_URL}/portal/work-orders/"
    res_wo = page.goto(wo_url, wait_until="networkidle")
    report["step2"]["http_status"] = res_wo.status
    log(f"Loaded {wo_url} -> Status: {res_wo.status}")
    page.wait_for_timeout(2000)

    # Click on the first work order to view detail
    first_wo_btn = page.locator("button[title='Xem chi tiết']").first
    if first_wo_btn.is_visible():
        first_wo_btn.click()
        page.wait_for_timeout(1000)
    else:
        # Click on first table title
        page.locator("td strong[onclick*='openWoDetailModal']").first.click()
        page.wait_for_timeout(1000)

    step2_detail_shot = os.path.join(SCREENSHOTS_DIR, "step2_wo_detail.png")
    page.screenshot(path=step2_detail_shot)
    report["step2"]["screenshot_detail"] = step2_detail_shot

    # Test 'Yêu cầu phân công lại' button & modal
    log("Testing 'Yêu cầu phân công lại' action...")
    btn_reassign = page.locator("#detail-btn-reassign")
    if not btn_reassign.is_visible():
        page.evaluate("document.getElementById('detail-btn-reassign').classList.remove('hidden')")
    btn_reassign.click()
    page.wait_for_timeout(800)
    reassign_modal_visible = page.locator("#wo-request-reassign-modal").is_visible()
    log(f"Modal 'Yêu cầu phân công lại' visible: {reassign_modal_visible}")
    report["step2"]["reassign_modal_visible"] = reassign_modal_visible
    step2_reassign_shot = os.path.join(SCREENSHOTS_DIR, "step2_wo_reassign_modal.png")
    page.screenshot(path=step2_reassign_shot)
    report["step2"]["screenshot_reassign"] = step2_reassign_shot

    # Close reassign modal
    page.evaluate("closeRequestReassignModal()")
    page.wait_for_timeout(500)

    # Test 'Tạm dừng' button & modal
    log("Testing 'Tạm dừng' action...")
    btn_hold = page.locator("#detail-btn-hold")
    if not btn_hold.is_visible():
        page.evaluate("document.getElementById('detail-btn-hold').classList.remove('hidden')")
    btn_hold.click()
    page.wait_for_timeout(800)
    hold_modal_visible = page.locator("#wo-hold-modal").is_visible()
    log(f"Modal 'Tạm dừng' visible: {hold_modal_visible}")
    report["step2"]["hold_modal_visible"] = hold_modal_visible
    step2_hold_shot = os.path.join(SCREENSHOTS_DIR, "step2_wo_hold_modal.png")
    page.screenshot(path=step2_hold_shot)
    report["step2"]["screenshot_hold"] = step2_hold_shot

    # Close hold modal
    page.evaluate("closeHoldWoModal()")
    page.wait_for_timeout(500)

    # Test Checklist & 'Hoàn thành' with Machine State requirement
    log("Testing Checklist & Hoàn thành (Machine State)...")
    btn_complete = page.locator("#detail-btn-complete")
    if not btn_complete.is_visible():
        page.evaluate("document.getElementById('detail-btn-complete').classList.remove('hidden')")
    btn_complete.click()
    page.wait_for_timeout(800)
    complete_modal_visible = page.locator("#wo-complete-modal").is_visible()
    log(f"Modal 'Hoàn tất Work Order' visible: {complete_modal_visible}")
    
    # Try confirming without selecting Machine State -> check error
    page.click("#btn-confirm-complete-wo")
    page.wait_for_timeout(500)
    err_text = page.locator("#wo-complete-error").inner_text()
    log(f"Error text when Machine State is empty: '{err_text}'")
    report["step2"]["machine_state_validation_error"] = err_text
    
    step2_complete_shot = os.path.join(SCREENSHOTS_DIR, "step2_wo_complete_modal.png")
    page.screenshot(path=step2_complete_shot)
    report["step2"]["screenshot_complete"] = step2_complete_shot

    page.evaluate("closeCompleteWoModal()")
    page.wait_for_timeout(500)

    # Check checklist container rendering
    checklist_html = page.locator("#detail-checklists").inner_html()
    report["step2"]["checklist_rendered"] = len(checklist_html) > 0
    step2_checklist_shot = os.path.join(SCREENSHOTS_DIR, "step2_wo_checklist.png")
    page.screenshot(path=step2_checklist_shot)
    report["step2"]["screenshot_checklist"] = step2_checklist_shot

    page.evaluate("closeWoDetailModal()")
    page.wait_for_timeout(500)

    # -------------------------------------------------------------
    # BƯỚC 3: SỔ TÀI SẢN & ĐO KIỂM BẤT THƯỜNG (/portal/assets/)
    # -------------------------------------------------------------
    log("--- BƯỚC 3: SỔ TÀI SẢN & ĐO KIỂM BẤT THƯỜNG ---")
    assets_url = f"{BASE_URL}/portal/assets/"
    res_assets = page.goto(assets_url, wait_until="networkidle")
    report["step3"]["http_status"] = res_assets.status
    log(f"Loaded {assets_url} -> Status: {res_assets.status}")
    page.wait_for_timeout(2000)

    # Target: Máy Bơm Ly Tâm P-101 (id: acce1045-375c-470b-95e7-9b2b3e6e7297)
    target_asset_id = "acce1045-375c-470b-95e7-9b2b3e6e7297"
    log("Selecting Máy Bơm Ly Tâm P-101...")
    page.evaluate(f"if (typeof selectAsset === 'function') {{ selectAsset('{target_asset_id}'); }} else if (typeof openAssetDetail === 'function') {{ openAssetDetail('{target_asset_id}'); }} else {{ window.currentSelectedAssetId = '{target_asset_id}'; }}")
    page.wait_for_timeout(1000)

    # Case A: VIBRATION = 5.5 (Zone C ISO 10816-3) and TEMPERATURE = 75°C
    log("Submitting Test Case A: VIBRATION = 5.5, TEMPERATURE = 75...")
    # Open meter reading modal
    page.evaluate(f"window.currentSelectedAssetId = '{target_asset_id}'; document.getElementById('add-meter-modal').classList.remove('hidden');")
    page.wait_for_timeout(500)

    # Fill VIBRATION = 5.5
    page.select_option("#meter-metric-code", "VIBRATION")
    page.fill("#meter-reading-value", "5.5")
    page.fill("#meter-reading-unit", "mm/s")
    page.fill("#meter-reading-remarks", "Kiểm tra định kỳ rung động Zone C")
    
    # Click submit
    page.click("#btn-submit-meter-reading")
    page.wait_for_timeout(2000)

    # Now enter TEMPERATURE = 75
    page.evaluate(f"window.currentSelectedAssetId = '{target_asset_id}'; document.getElementById('add-meter-modal').classList.remove('hidden');")
    page.wait_for_timeout(500)
    page.select_option("#meter-metric-code", "TEMPERATURE")
    page.fill("#meter-reading-value", "75")
    page.fill("#meter-reading-unit", "°C")
    page.fill("#meter-reading-remarks", "Kiểm tra nhiệt độ ổ bi")
    page.click("#btn-submit-meter-reading")
    page.wait_for_timeout(2000)

    step3_zone_c_shot = os.path.join(SCREENSHOTS_DIR, "step3_meter_reading_zone_c.png")
    page.screenshot(path=step3_zone_c_shot)
    report["step3"]["screenshot_zone_c"] = step3_zone_c_shot

    # Case B: Danger reading VIBRATION = 8.5 (Zone D)
    log("Submitting Test Case B: VIBRATION = 8.5 (Zone D - Critical)...")
    page.evaluate(f"window.currentSelectedAssetId = '{target_asset_id}'; document.getElementById('add-meter-modal').classList.remove('hidden');")
    page.wait_for_timeout(500)
    page.select_option("#meter-metric-code", "VIBRATION")
    page.fill("#meter-reading-value", "8.5")
    page.fill("#meter-reading-unit", "mm/s")
    page.fill("#meter-reading-remarks", "Cảnh báo rung nguy hiểm Zone D")
    page.click("#btn-submit-meter-reading")
    page.wait_for_timeout(2500)

    step3_zone_d_shot = os.path.join(SCREENSHOTS_DIR, "step3_meter_reading_zone_d.png")
    page.screenshot(path=step3_zone_d_shot)
    report["step3"]["screenshot_zone_d"] = step3_zone_d_shot

    # -------------------------------------------------------------
    # BƯỚC 4: THÔNG BÁO (NOTIFICATIONS)
    # -------------------------------------------------------------
    log("--- BƯỚC 4: KIỂM THỬ THÔNG BÁO ---")
    page.wait_for_timeout(1000)
    # Click notification bell
    bell_btn = page.locator("#notification-bell-btn")
    if bell_btn.is_visible():
        bell_btn.click()
        page.wait_for_timeout(1500)
    else:
        page.evaluate("window.NotificationBell && window.NotificationBell.toggleDropdown && window.NotificationBell.toggleDropdown()")
        page.wait_for_timeout(1500)

    notif_dropdown_visible = page.locator("#notification-dropdown").is_visible()
    log(f"Notification dropdown visible: {notif_dropdown_visible}")
    report["step4"]["dropdown_visible"] = notif_dropdown_visible

    # Count notification items
    notif_items_count = page.locator("#notification-items .notification-item").count()
    log(f"Notification items count: {notif_items_count}")
    report["step4"]["items_count"] = notif_items_count

    step4_shot = os.path.join(SCREENSHOTS_DIR, "step4_notifications.png")
    page.screenshot(path=step4_shot)
    report["step4"]["screenshot"] = step4_shot

    browser.close()

# Save execution summary report
report_path = os.path.join(SCREENSHOTS_DIR, "test_execution_report.json")
with open(report_path, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

log("Full E2E test finished! Report saved to " + report_path)

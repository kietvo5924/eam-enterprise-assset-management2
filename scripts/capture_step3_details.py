import os
import sys
import time
from playwright.sync_api import sync_playwright

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

SCREENSHOTS_DIR = r"C:\Users\Admin\.gemini\antigravity-ide\brain\e8c1989a-0992-41a4-99c4-04806976fdfe\test_screenshots"
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
BASE_URL = "http://127.0.0.1:8080"
target_asset_id = "acce1045-375c-470b-95e7-9b2b3e6e7297"

with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path=CHROME_PATH,
        headless=True,
        args=["--disable-web-security", "--no-sandbox"]
    )
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()

    # Login
    page.goto(f"{BASE_URL}/portal/login/", wait_until="networkidle")
    page.fill("input[name='username']", "vf_admin@vinfast.local")
    page.fill("input[name='password']", "admin")
    page.click("button[type='submit']")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)

    # Assets page
    page.goto(f"{BASE_URL}/portal/assets/", wait_until="networkidle")
    page.wait_for_timeout(2000)

    # Select Bơm Ly Tâm P-101
    page.evaluate(f"selectAsset('{target_asset_id}')")
    page.wait_for_timeout(1000)

    # Switch to tab 'meterReadings'
    page.evaluate("switchTab('meterReadings')")
    page.wait_for_timeout(800)

    # 1. Open modal with VIBRATION = 5.5 (Zone C)
    page.evaluate("openAddMeterModal()")
    page.wait_for_timeout(500)
    page.select_option("#meter-metric-code", "VIBRATION")
    page.fill("#meter-reading-value", "5.5")
    page.fill("#meter-reading-unit", "mm/s")
    page.fill("#meter-reading-remarks", "Đo kiểm rung động ISO 10816-3 (Vùng C: 5.5 mm/s)")
    page.wait_for_timeout(500)

    shot1 = os.path.join(SCREENSHOTS_DIR, "step3_modal_vibration_5_5.png")
    page.screenshot(path=shot1)
    print("Saved shot1:", shot1)

    # Submit 5.5
    page.click("#btn-submit-meter-reading")
    page.wait_for_timeout(2000)

    # 2. Open modal with TEMPERATURE = 75
    page.evaluate("openAddMeterModal()")
    page.wait_for_timeout(500)
    page.select_option("#meter-metric-code", "TEMPERATURE")
    page.fill("#meter-reading-value", "75.0")
    page.fill("#meter-reading-unit", "°C")
    page.fill("#meter-reading-remarks", "Đo kiểm nhiệt độ vòng bi (75°C)")
    page.wait_for_timeout(500)

    shot2 = os.path.join(SCREENSHOTS_DIR, "step3_modal_temperature_75.png")
    page.screenshot(path=shot2)
    print("Saved shot2:", shot2)

    # Submit 75
    page.click("#btn-submit-meter-reading")
    page.wait_for_timeout(2000)

    # 3. Take screenshot of the history table showing both metrics
    shot3 = os.path.join(SCREENSHOTS_DIR, "step3_meter_history_table.png")
    page.screenshot(path=shot3)
    print("Saved shot3:", shot3)

    # 4. Open modal with VIBRATION = 8.5 (Zone D - Dangerous/Critical)
    page.evaluate("openAddMeterModal()")
    page.wait_for_timeout(500)
    page.select_option("#meter-metric-code", "VIBRATION")
    page.fill("#meter-reading-value", "8.5")
    page.fill("#meter-reading-unit", "mm/s")
    page.fill("#meter-reading-remarks", "RUNG ĐỘNG NGUY HIỂM VÙNG D (8.5 mm/s) - ISO 10816-3")
    page.wait_for_timeout(500)

    shot4 = os.path.join(SCREENSHOTS_DIR, "step3_modal_vibration_8_5_zone_d.png")
    page.screenshot(path=shot4)
    print("Saved shot4:", shot4)

    # Submit 8.5
    page.click("#btn-submit-meter-reading")
    page.wait_for_timeout(2500)

    # 5. Take screenshot of the result on asset detail
    shot5 = os.path.join(SCREENSHOTS_DIR, "step3_critical_alert_dedup.png")
    page.screenshot(path=shot5)
    print("Saved shot5:", shot5)

    browser.close()
    print("All Step 3 detail captures completed successfully!")

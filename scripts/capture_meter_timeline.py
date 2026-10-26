import os
import sys
from playwright.sync_api import sync_playwright

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

SCREENSHOTS_DIR = r"C:\Users\Admin\.gemini\antigravity-ide\brain\e8c1989a-0992-41a4-99c4-04806976fdfe\test_screenshots"
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
BASE_URL = "http://127.0.0.1:8080"

with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path=CHROME_PATH,
        headless=True,
        args=["--disable-web-security", "--no-sandbox"]
    )
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()

    page.goto(f"{BASE_URL}/portal/login/", wait_until="networkidle")
    page.fill("input[name='username']", "vf_admin@vinfast.local")
    page.fill("input[name='password']", "admin")
    page.click("button[type='submit']")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1500)

    page.goto(f"{BASE_URL}/portal/assets/", wait_until="networkidle")
    page.wait_for_timeout(2000)

    # Switch to meterReadings and scroll
    page.evaluate("switchTab('meterReadings')")
    page.wait_for_timeout(1000)
    page.evaluate("document.getElementById('tab-content-meterReadings').scrollIntoView({behavior: 'instant', block: 'center'})")
    page.wait_for_timeout(1000)

    shot = os.path.join(SCREENSHOTS_DIR, "step3_meter_timeline_scroll.png")
    page.screenshot(path=shot)
    print("Saved timeline screenshot:", shot)

    browser.close()

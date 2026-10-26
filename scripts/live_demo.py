import os
import sys
import time
from playwright.sync_api import sync_playwright

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
BASE_URL = "http://127.0.0.1:8080"

def run_live_interactive_demo():
    print("=" * 60)
    print("KHỞI CHẠY GOOGLE CHROME TRỰC TIẾP TRÊN MÀN HÌNH (HEADLESS = FALSE)")
    print("Bạn sẽ thấy trình duyệt Chrome thật xuất hiện và thao tác trực quan...")
    print("=" * 60)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=CHROME_PATH,
            headless=False,
            slow_mo=1200, # Thao tác chậm rãi 1.2s mỗi bước để người dùng quan sát rõ
            args=["--start-maximized"]
        )
        context = browser.new_context(no_viewport=True)
        page = context.new_page()

        # 1. ĐĂNG NHẬP
        print("[1/5] Đang mở trang đăng nhập...")
        page.goto(f"{BASE_URL}/portal/login/", wait_until="networkidle")
        time.sleep(1)

        print("[1/5] Điền tài khoản vf_admin@vinfast.local...")
        page.fill("input[name='username']", "vf_admin@vinfast.local")
        page.fill("input[name='password']", "admin")
        print("[1/5] Bấm Đăng nhập...")
        page.click("button[type='submit']")
        page.wait_for_load_state("networkidle")
        time.sleep(2)

        # 2. KIỂM THỬ WORK ORDERS
        print("[2/5] Chuyển tới Quản lý Work Orders...")
        page.goto(f"{BASE_URL}/portal/work-orders/", wait_until="networkidle")
        time.sleep(2)

        print("[2/5] Mở chi tiết Work Order đầu tiên...")
        first_wo = page.locator("button[title='Xem chi tiết'], td strong[onclick*='openWoDetailModal']").first
        if first_wo.is_visible():
            first_wo.click()
            time.sleep(2)

        print("[2/5] Mở popup Tạm dừng (Hold)...")
        hold_btn = page.locator("#btnActionHold")
        if hold_btn.is_visible():
            hold_btn.click()
            time.sleep(2.5)
            # Đóng modal
            page.locator("#holdModal button[onclick*='closeHoldModal']").click()
            time.sleep(1)

        print("[2/5] Mở popup Yêu cầu phân công lại (Reassign)...")
        reassign_btn = page.locator("#btnActionReassign")
        if reassign_btn.is_visible():
            reassign_btn.click()
            time.sleep(2.5)
            # Đóng modal
            page.locator("#reassignModal button[onclick*='closeReassignModal']").click()
            time.sleep(1)

        print("[2/5] Mở popup Hoàn thành để kiểm tra trường Trạng thái máy (Machine State)...")
        complete_btn = page.locator("#btnActionComplete")
        if complete_btn.is_visible():
            complete_btn.click()
            time.sleep(2.5)
            # Đóng modal
            page.locator("#completeWoModal button[onclick*='closeCompleteModal']").click()
            time.sleep(1)

        # Đóng modal detail
        close_detail = page.locator("#woDetailModal button[onclick*='closeWoDetailModal']")
        if close_detail.is_visible():
            close_detail.click()
            time.sleep(1)

        # 3. KIỂM THỬ SỔ TÀI SẢN (ASSET REGISTRY) & CẢNH BÁO
        print("[3/5] Chuyển tới Sổ tài sản...")
        page.goto(f"{BASE_URL}/portal/assets/", wait_until="networkidle")
        time.sleep(2)

        print("[3/5] Chọn tài sản có cảnh báo bất thường...")
        # Tìm AHU hoặc P-101
        asset_item = page.locator("tr[onclick*='selectAsset'], .asset-row").first
        if asset_item.is_visible():
            asset_item.click()
            time.sleep(2)

        print("[3/5] Cuộn xuống xem Cảnh báo bất thường đã được gộp gọn gàng & Metric dải phụ...")
        page.evaluate("window.scrollBy(0, 400)")
        time.sleep(3)

        # 4. CHUÔNG THÔNG BÁO
        print("[4/5] Mở menu Chuông thông báo trên Topbar...")
        bell = page.locator("#notifBellBtn, button[onclick*='toggleNotifDropdown']")
        if bell.is_visible():
            bell.click()
            time.sleep(2.5)

        # 5. GIỮ NGUYÊN TRÌNH DUYỆT ĐỂ NGƯỜI DÙNG TỰ DO SỬ DỤNG
        print("=" * 60)
        print("HOÀN THÀNH DEMO TRỰC QUAN!")
        print("Trình duyệt Chrome vẫn ĐANG MỞ trên màn hình của bạn để bạn tiếp tục tự do bấm thử.")
        print("Nhấn Ctrl+C trong terminal khi muốn kết thúc phiên.")
        print("=" * 60)

        # Giữ phiên mở trong 10 phút hoặc cho đến khi đóng
        try:
            while not page.is_closed():
                time.sleep(1)
        except Exception:
            pass

if __name__ == "__main__":
    run_live_interactive_demo()

import os
import sys
import time
import shutil
from pathlib import Path
from playwright.sync_api import sync_playwright

def run_mobile_demo():
    video_dir = Path("D:/GameLinkNeverDie/eam-enterprise-assset-management/videos")
    temp_dir = video_dir / "mobile_temp"
    final_video_path = video_dir / "phase_11_9_mobile_demo.webm"
    
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)

    print("Launching Chromium with Pixel 7 Mobile Emulation for Mobile Demo...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-web-security'
            ]
        )
        
        # Emulate Pixel 7 mobile device
        pixel_7 = p.devices['Pixel 7']
        context = browser.new_context(
            **pixel_7,
            record_video_dir=str(temp_dir),
            record_video_size={"width": 412, "height": 915}
        )
        
        page = context.new_page()
        
        # Setup dialog handler to auto-accept confirm/alert dialogs
        def handle_dialog(dialog):
            print(f"[Mobile Dialog] Type: {dialog.type}, Message: {dialog.message}")
            if dialog.type == 'prompt':
                dialog.accept("Cần bổ sung thông số mỡ bôi trơn chịu nhiệt cao")
            else:
                dialog.accept()
        page.on("dialog", handle_dialog)

        # 1. Mobile Login
        print("1. Navigating to login page on mobile...")
        page.goto("http://127.0.0.1:8000/login/", wait_until="networkidle")
        page.wait_for_timeout(1500)

        print("Logging in as admin on mobile viewport...")
        page.fill("input[name='username']", "admin")
        page.wait_for_timeout(500)
        page.fill("input[name='password']", "admin123")
        page.wait_for_timeout(800)
        page.click("button[type='submit']")
        
        page.wait_for_url("**/portal/", timeout=15000)
        page.wait_for_timeout(2500)
        print("Logged in successfully, on Mobile Portal Dashboard.")

        # 2. Inspect Mobile Floating FAB & Bottom Sheet
        print("2. Tapping AI Assistant Floating FAB on mobile screen...")
        page.wait_for_selector("#ai-assistant-fab", timeout=5000)
        page.click("#ai-assistant-fab")
        page.wait_for_selector("#ai-assistant-drawer:not(.hidden)", timeout=5000)
        page.wait_for_timeout(2000)
        print("Mobile chat bottom sheet opened in full-width responsive view.")

        # 3. Test Mobile Life Safety Emergency Alert (Rule 1)
        print("3. Testing Life-Safety Emergency Alert on mobile...")
        page.fill("#ai-chat-input", "Cháy dầu máy biến áp đang bốc khói khẩn cấp")
        page.wait_for_timeout(1000)
        page.click("#ai-chat-send-btn")
        
        # Wait for emergency banner
        page.wait_for_selector("text=CẢNH BÁO AN TOÀN SINH MẠNG", timeout=15000)
        print("Life-safety emergency alert triggered on mobile!")
        page.wait_for_timeout(4500)

        # 4. Test Mobile Slang Query Expansion & Live Inventory Interlock (Rules 2, 6, 7)
        print("4. Testing Slang Query Expansion & Live Inventory on mobile...")
        page.fill("#ai-chat-input", "Bơm kêu lạch cạch, tụ phù thì xử lý thế nào?")
        page.wait_for_timeout(1000)
        page.click("#ai-chat-send-btn")
        
        # Wait for inventory section
        page.wait_for_selector("text=Tồn kho phụ tùng thực tế", timeout=20000)
        print("Mobile slang response with live inventory tag displayed!")
        page.wait_for_timeout(4500)

        # 5. Test Mobile Action Chip (System Guide)
        print("5. Testing Action Chip: Nút trên trang này? on mobile...")
        chip_btn = page.locator("button:has-text('❓ Nút trên trang này?')")
        if chip_btn.is_visible():
            chip_btn.scroll_into_view_if_needed()
            page.wait_for_timeout(800)
            chip_btn.click()
        else:
            page.evaluate("sendActionChip('Nút trên trang này dùng để làm gì?')")
            
        page.wait_for_selector("text=HƯỚNG DẪN TÍNH NĂNG", timeout=20000)
        print("System guide response displayed on mobile!")
        page.wait_for_timeout(4000)

        # 6. Test Native Mobile Offline Package Pre-fetch Action Chip (Rule 8)
        print("6. Testing Native Mobile Offline Package Action Chip (Rule 8)...")
        offline_chip = page.locator("#btn-chip-offline")
        if offline_chip.is_visible():
            offline_chip.scroll_into_view_if_needed()
            page.wait_for_timeout(800)
            offline_chip.click()
        else:
            page.evaluate("fetchOfflinePackUI()")
            
        page.wait_for_selector("text=Đã tải trước gói ngoại tuyến", timeout=20000)
        print("Native offline package pre-fetch card loaded cleanly into mobile chat!")
        page.wait_for_timeout(4500)

        # 7. Test Actionable Chat-to-WorkOrder Draft Creation on Mobile (Rule 9)
        print("7. Testing Mobile Actionable Chat-to-WorkOrder Draft Creation (status=CREATED)...")
        draft_btn = page.locator("button:has-text('Tạo Bản Thảo Phiếu Sửa Chữa')").first
        if draft_btn.is_visible():
            draft_btn.scroll_into_view_if_needed()
            page.wait_for_timeout(800)
            draft_btn.click()
            page.wait_for_timeout(4000)
            print("Mobile Chat-to-WorkOrder draft confirmed and navigated to Work Orders!")
        else:
            print("Draft button not visible, clicking via js...")
            page.evaluate("handleCreateWorkOrderDraft('Khắc phục xâm thực và thay phớt cơ khí PUMP-X100', 'CAVITATION_NOISE', '7253e5a2-dd25-4378-8f83-c4da326ef053')")
            page.wait_for_timeout(4000)

        # 8. Feedback Thumb-Up on Mobile (Rule 10)
        print("8. Testing Feedback (Thumbs-up) on mobile...")
        page.wait_for_timeout(1500)
        # Re-open FAB on the Work Orders page to rate
        page.click("#ai-assistant-fab")
        page.wait_for_selector("#ai-assistant-drawer:not(.hidden)", timeout=5000)
        page.wait_for_timeout(1000)
        
        thumbs_up_btn = page.locator("button[title='Hài lòng']").first
        if thumbs_up_btn.is_visible():
            thumbs_up_btn.scroll_into_view_if_needed()
            page.wait_for_timeout(800)
            thumbs_up_btn.click()
            page.wait_for_timeout(2500)
            print("Feedback submitted on mobile!")

        print("Mobile demonstration complete! Finalizing video recording...")
        page.wait_for_timeout(2000)
        
        # Save video
        video_recorded = page.video
        context.close()
        browser.close()

        if video_recorded:
            temp_video_path = video_recorded.path()
            print(f"Temporary mobile video saved at: {temp_video_path}")
            if final_video_path.exists():
                final_video_path.unlink()
            shutil.copy2(temp_video_path, final_video_path)
            print(f"Final Mobile Demo Video successfully saved to: {final_video_path}")
            print(f"Mobile Video file size: {final_video_path.stat().st_size} bytes")
        else:
            print("Warning: page.video was not available.")

if __name__ == "__main__":
    run_mobile_demo()

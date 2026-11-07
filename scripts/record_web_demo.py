import os
import sys
import time
import shutil
from pathlib import Path
from playwright.sync_api import sync_playwright

def run_web_demo():
    video_dir = Path("D:/GameLinkNeverDie/eam-enterprise-assset-management/videos")
    temp_dir = video_dir / "web_temp"
    final_video_path = video_dir / "phase_11_9_web_demo.webm"
    
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)

    print("Launching Chromium for Web Demo recording...")
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
        
        context = browser.new_context(
            record_video_dir=str(temp_dir),
            record_video_size={"width": 1280, "height": 720},
            viewport={"width": 1280, "height": 720}
        )
        
        page = context.new_page()
        
        # Setup dialog handler to auto-accept confirm/alert dialogs and provide feedback on prompt
        def handle_dialog(dialog):
            print(f"[Web Dialog] Type: {dialog.type}, Message: {dialog.message}")
            if dialog.type == 'prompt':
                dialog.accept("Cần bổ sung thông số mỡ bôi trơn chịu nhiệt cao ISO VG 220 cho ổ bi PUMP-X100")
            else:
                dialog.accept()
        page.on("dialog", handle_dialog)

        # 1. Login
        print("1. Navigating to login page...")
        page.goto("http://127.0.0.1:8000/login/", wait_until="networkidle")
        page.wait_for_timeout(1500)

        print("Logging in as admin...")
        page.fill("input[name='username']", "admin")
        page.wait_for_timeout(500)
        page.fill("input[name='password']", "admin123")
        page.wait_for_timeout(800)
        page.click("button[type='submit']")
        
        page.wait_for_url("**/portal/", timeout=15000)
        page.wait_for_timeout(2500)
        print("Logged in successfully, on Portal Dashboard.")

        # 2. Inspect Floating FAB & Drawer
        print("2. Opening AI Assistant Floating Chat Widget FAB...")
        page.hover("#ai-assistant-fab")
        page.wait_for_timeout(1500)
        page.click("#ai-assistant-fab")
        page.wait_for_selector("#ai-assistant-drawer:not(.hidden)", timeout=5000)
        page.wait_for_timeout(2000)

        # 3. Maximize and Restore Drawer
        print("3. Testing Drawer Maximize / Restore Toggle...")
        page.click("#ai-drawer-max-icon")
        page.wait_for_timeout(2000)
        page.click("#ai-drawer-max-icon")
        page.wait_for_timeout(1500)

        # 4. Test Life Safety Emergency Alert (Rule 1)
        print("4. Testing Life-Safety Emergency Alert (Rule 1)...")
        page.fill("#ai-chat-input", "Cháy dầu máy biến áp đang bốc khói khẩn cấp")
        page.wait_for_timeout(1000)
        page.click("#ai-chat-send-btn")
        page.wait_for_selector("text=CẢNH BÁO AN TOÀN SINH MẠNG", timeout=15000)
        print("Life-safety emergency alert triggered successfully!")
        page.wait_for_timeout(4500)

        # 5. Test Slang Query Expansion, Plant Tacit Knowledge & Live Inventory (Rules 2, 3, 4, 6, 7)
        print("5. Testing Slang Query Expansion & Live Inventory (Rules 2, 3, 4, 6, 7)...")
        page.fill("#ai-chat-input", "Bơm kêu lạch cạch, tụ phù thì xử lý thế nào?")
        page.wait_for_timeout(1000)
        page.click("#ai-chat-send-btn")
        page.wait_for_selector("text=Tồn kho phụ tùng thực tế", timeout=20000)
        print("Slang query expansion, tacit advice and inventory interlock displayed!")
        page.wait_for_timeout(4500)

        # 6. Test Quick Action Chips (System Guide & Native Offline Pack)
        print("6a. Testing Action Chip: Nút trên trang này dùng để làm gì?...")
        page.click("button:has-text('❓ Nút trên trang này?')")
        page.wait_for_selector("text=HƯỚNG DẪN TÍNH NĂNG", timeout=15000)
        print("System guide response displayed!")
        page.wait_for_timeout(3500)

        print("6b. Testing Native Action Chip: 📥 Gói ngoại tuyến...")
        page.click("#btn-chip-offline")
        page.wait_for_selector("text=Đã tải trước gói ngoại tuyến", timeout=15000)
        print("Offline package pre-fetch card loaded in chat!")
        page.wait_for_timeout(4000)

        # 7. Test Feedback Downvote (Sends to Chief Engineer Curation Queue - Rule 10)
        print("7. Testing Downvote Feedback Loop (Rule 10)...")
        downvote_btn = page.locator("button[title='Chưa hài lòng']").first
        if downvote_btn.is_visible():
            downvote_btn.scroll_into_view_if_needed()
            page.wait_for_timeout(800)
            downvote_btn.click()
            page.wait_for_timeout(2000)
            print("Technician feedback submitted to Curation Queue!")
        else:
            print("Downvote button not visible.")

        # 8. Test Actionable Chat-to-WorkOrder Draft Creation (Rule 9)
        print("8. Testing Chat-to-WorkOrder Draft Creation (status=CREATED)...")
        draft_btn = page.locator("button:has-text('Tạo Bản Thảo Phiếu Sửa Chữa')").first
        if draft_btn.is_visible():
            draft_btn.scroll_into_view_if_needed()
            page.wait_for_timeout(1000)
            draft_btn.click()
            page.wait_for_timeout(4000)
            print("Chat-to-WorkOrder draft triggered and navigated to Work Orders!")
        else:
            print("Draft button not visible.")

        # 9. Test Admin Knowledge Hub (/admin/rag-knowledge/)
        print("9. Navigating to Admin Knowledge Hub (/admin/rag-knowledge/)...")
        page.goto("http://127.0.0.1:8000/admin/rag-knowledge/", wait_until="networkidle")
        page.wait_for_timeout(2500)

        # Tab 1: Curated Q&A
        print("9.1 Exploring Tab 1: Curated Q&A Knowledge...")
        page.click("#filter-equip")
        page.wait_for_timeout(1500)
        page.click("#filter-sys")
        page.wait_for_timeout(1500)
        page.click("#filter-all")
        page.wait_for_timeout(1000)
        
        # Search Q&A
        page.fill("#qa-search-input", "phớt")
        page.wait_for_timeout(1500)
        page.fill("#qa-search-input", "")
        page.wait_for_timeout(1000)

        # Open Add Q&A Modal
        print("Opening Add Q&A Modal...")
        page.click("button:has-text('Thêm Q&A Mẫu')")
        page.wait_for_selector("#add-qa-modal:not(.hidden)", timeout=5000)
        page.wait_for_timeout(1500)
        
        page.fill("#modal-qa-model", "PUMP-X100")
        page.fill("#modal-qa-question", "Cách kiểm tra áp suất dầu hồi máy nén khí")
        page.fill("#modal-qa-answer", "1. Quan sát đồng hồ áp kế tại cổng hồi dầu.\n2. Áp suất tiêu chuẩn trong dải 2.5 - 3.2 bar.\n3. Nếu vượt ngưỡng, vệ sinh lưới lọc phớt dầu.")
        page.wait_for_timeout(2000)
        
        page.click("button:has-text('Lưu Tri Thức')")
        page.wait_for_timeout(3000)
        print("New Curated Q&A saved successfully!")

        # Tab 2: Curation Queue
        print("9.2 Exploring Tab 2: Chief Engineer Curation Queue...")
        page.click("#tab-btn-queue")
        page.wait_for_timeout(3000)
        approve_btn = page.locator("button:has-text('Duyệt & Lưu Thành Tri Thức Vàng')").first
        if approve_btn.is_visible():
            approve_btn.scroll_into_view_if_needed()
            page.wait_for_timeout(1000)
            approve_btn.click()
            page.wait_for_timeout(3000)
            print("Curation queue item approved by Chief Engineer!")
        else:
            print("No pending curation queue item visible.")

        # Tab 3: Technical Documents Library & Reindex
        print("9.3 Exploring Tab 3: OEM & System Documents Library...")
        page.click("#tab-btn-docs")
        page.wait_for_timeout(2500)
        
        print("Triggering Reindex Work Orders...")
        page.click("button:has-text('Tái Lập Chỉ Mục Work Order')")
        page.wait_for_timeout(3500)

        # Tab 4: Slang Dictionary & Life Safety Settings
        print("9.4 Exploring Tab 4: Slang Dictionary & Life Safety Settings...")
        page.click("#tab-btn-safety")
        page.wait_for_timeout(4500)

        print("Web demonstration complete! Finalizing video recording...")
        page.wait_for_timeout(2000)
        
        # Save video
        video_recorded = page.video
        context.close()
        browser.close()

        if video_recorded:
            temp_video_path = video_recorded.path()
            print(f"Temporary video saved at: {temp_video_path}")
            if final_video_path.exists():
                final_video_path.unlink()
            shutil.copy2(temp_video_path, final_video_path)
            print(f"Final Web Demo Video successfully saved to: {final_video_path}")
            print(f"Video file size: {final_video_path.stat().st_size} bytes")
        else:
            print("Warning: page.video was not available.")

if __name__ == "__main__":
    run_web_demo()

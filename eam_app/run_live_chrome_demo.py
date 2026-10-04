"""
LIVE CHROME DEMO: Thao tác trực tiếp trên trình duyệt Chrome có giao diện (headless=False)
Minh họa tất cả các tình huống nghiệp vụ:
1. Tạo Kỹ năng & Chứng chỉ riêng theo ý doanh nghiệp (ROBOT_ABB, CERT_PCCC)
2. Gán kỹ năng & chứng chỉ cho Thợ (Kỹ thuật viên)
3. Tạo Work Order yêu cầu chuyên môn & chứng chỉ riêng
4. Mở Hungarian Assignment: Xem thuật toán khớp đúng người đúng việc & phát hiện vi phạm Big-M
5. Kiểm tra giao diện tự động chọn đúng ô và nhận diện thông minh
"""
import sys
import os
import time

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from playwright.sync_api import sync_playwright

ARTIFACT_DIR = r"C:\Users\Admin\.gemini\antigravity-ide\brain\f67e1b5f-2cf2-4a52-bc75-44007dfa4f3f"
BASE_URL = "http://localhost:8000"

def log(msg):
    print(msg, flush=True)

def run_demo():
    log("=" * 70)
    log("KHOI DONG TRINH DUYET CHROME TRUC TIEP TREN MAN HINH (HEADLESS = FALSE)")
    log("=" * 70)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            slow_mo=350,
            args=["--start-maximized", "--no-sandbox"]
        )
        context = browser.new_context(no_viewport=True)
        page = context.new_page()

        # -------------------------------------------------------------
        # STEP 1: ĐĂNG NHẬP VÀO HỆ THỐNG
        # -------------------------------------------------------------
        log("\n[BƯỚC 1] Điều hướng đến trang Đăng nhập EAM...")
        page.goto(f"{BASE_URL}/portal/login/", wait_until="networkidle")
        time.sleep(1)

        page.locator('input[name="username"], input[name="login"], input[type="email"], #id_username').first.fill("superadmin@eam.local")
        page.locator('input[name="password"], input[type="password"], #id_password').first.fill("admin123")
        time.sleep(1)
        page.get_by_role("button", name="Sign In").click()
        page.wait_for_load_state("networkidle")
        log(f" -> Đăng nhập thành công! Trang hiện tại: {page.url}")
        time.sleep(1)

        # -------------------------------------------------------------
        # STEP 2: TỰ DO TẠO KỸ NĂNG & CHỨNG CHỈ RIÊNG CỦA DOANH NGHIỆP
        # -------------------------------------------------------------
        log("\n[BƯỚC 2] Vào trang Workforce & Tools...")
        page.goto(f"{BASE_URL}/portal/workforce-tools/?tab=skills", wait_until="networkidle")
        time.sleep(1.5)

        # 2a. Tạo Kỹ năng riêng ROBOT_ABB nếu chưa có
        existing_skill = page.locator('table tr:has-text("ROBOT_ABB")')
        if existing_skill.count() == 0:
            log(" -> Bấm nút 'Thêm kỹ năng'...")
            page.locator('button[onclick="openSkillModal()"]').click()
            page.wait_for_selector("#modal-skill", state="visible")
            time.sleep(1)

            page.locator('#skill-code').fill("ROBOT_ABB")
            page.locator('#skill-name').fill("Kỹ sư Robot ABB (Tự động hóa)")
            page.locator('#skill-category').select_option("Tự động hóa")
            page.locator('#skill-desc').fill("Chuyên môn lập trình & bảo trì cánh tay Robot ABB")
            time.sleep(1.5)

            log(" -> Bấm Lưu Kỹ năng...")
            page.locator('#form-skill button[type="submit"]').click()
            time.sleep(2)
            page.wait_for_load_state("networkidle")
            log(" -> Đã tạo xong Kỹ năng riêng: ROBOT_ABB!")
        else:
            log(" -> Kỹ năng ROBOT_ABB đã tồn tại trên hệ thống.")

        # 2b. Tạo Chứng chỉ riêng CERT_PCCC nếu chưa có
        existing_cert = page.locator('table tr:has-text("CERT_PCCC")')
        if existing_cert.count() == 0:
            log(" -> Bấm nút 'Thêm chứng chỉ'...")
            page.locator('button[onclick="openCertModal()"]').click()
            page.wait_for_selector("#modal-cert", state="visible")
            time.sleep(1)

            page.locator('#cert-code').fill("CERT_PCCC")
            page.locator('#cert-name').fill("Chứng chỉ PCCC Cơ sở Cấp 2")
            page.locator('#cert-body').fill("Cảnh sát PCCC TP.HCM")
            page.locator('#cert-validity').fill("24")
            time.sleep(1.5)

            log(" -> Bấm Lưu Chứng chỉ...")
            page.locator('#form-cert button[type="submit"]').click()
            time.sleep(2)
            page.wait_for_load_state("networkidle")
            log(" -> Đã tạo xong Chứng chỉ riêng: CERT_PCCC!")
        else:
            log(" -> Chứng chỉ CERT_PCCC đã tồn tại trên hệ thống.")

        page.screenshot(path=os.path.join(ARTIFACT_DIR, "demo_01_custom_skill_cert_created.png"))
        log(" -> [ĐÃ CHỤP ẢNH] demo_01_custom_skill_cert_created.png")

        # -------------------------------------------------------------
        # STEP 3: GÁN KỸ NĂNG & CHỨNG CHỈ CHO KỸ THUẬT VIÊN
        # -------------------------------------------------------------
        log("\n[BƯỚC 3] Vào trang Quản lý Người dùng để gán chuyên môn cho Thợ...")
        page.goto(f"{BASE_URL}/portal/users/", wait_until="networkidle")
        time.sleep(2)

        # Tìm dòng thợ kỹ thuật có badge "Thợ Bậc"
        tech_row = page.locator('tr:has-text("Thợ Bậc")').first
        if tech_row.count() == 0:
            tech_row = page.locator('table tbody tr.user-row').first

        edit_btn = tech_row.locator('button[title="Edit User"]')
        if edit_btn.is_visible():
            log(" -> Mở Modal chỉnh sửa hồ sơ thợ kỹ thuật...")
            edit_btn.click()
            page.wait_for_selector("#user-modal", state="visible")
            time.sleep(1.5)

            # Tích chọn kỹ năng ROBOT_ABB
            robot_cb = page.locator('.tech-skill-cb[value="ROBOT_ABB"]')
            if robot_cb.is_visible() and not robot_cb.is_checked():
                log(" -> Tích chọn kỹ năng: Kỹ sư Robot ABB (Tự động hóa)...")
                robot_cb.check()
            
            # Tích chọn chứng chỉ CERT_PCCC
            pccc_cb = page.locator('.tech-cert-cb[value="CERT_PCCC"]')
            if pccc_cb.is_visible() and not pccc_cb.is_checked():
                log(" -> Tích chọn chứng chỉ: Chứng chỉ PCCC Cơ sở Cấp 2...")
                pccc_cb.check()

            time.sleep(1.5)
            log(" -> Bấm Lưu thay đổi hồ sơ thợ...")
            page.locator('#btn-save-user').click()
            time.sleep(2)
            page.wait_for_load_state("networkidle")
            log(" -> Cập nhật hồ sơ thợ thành công!")

        page.screenshot(path=os.path.join(ARTIFACT_DIR, "demo_02_tech_profile_with_skills.png"))
        log(" -> [ĐÃ CHỤP ẢNH] demo_02_tech_profile_with_skills.png")

        # -------------------------------------------------------------
        # STEP 4: TẠO PHIẾU BẢO TRÌ (WORK ORDER) YÊU CẦU CHUYÊN MÔN RIÊNG
        # -------------------------------------------------------------
        log("\n[BƯỚC 4] Vào trang Work Orders để tạo phiếu yêu cầu kỹ năng riêng...")
        page.goto(f"{BASE_URL}/portal/work-orders/", wait_until="networkidle")
        time.sleep(2)

        log(" -> Bấm Tạo Work Order mới...")
        page.locator('button[onclick="openWoModal()"], button:has-text("Tạo Work Order")').first.click()
        page.wait_for_selector("#wo-modal", state="visible")
        time.sleep(1.5)

        page.locator('#wo-title').fill("Bảo trì định kỳ Robot ABB xưởng lắp ráp")
        
        asset_select = page.locator('#wo-asset')
        if asset_select.locator('option').count() > 1:
            asset_select.select_option(index=1)
        
        page.locator('#wo-priority').select_option("HIGH")
        page.locator('#wo-desc').fill("Bảo trì, tra mỡ khớp xoay và hiệu chuẩn cánh tay robot ABB")
        time.sleep(1)

        # Mở accordion Tiêu chuẩn Kỹ thuật nếu đang đóng
        tech_body = page.locator('#tech-accordion-body')
        if not tech_body.is_visible():
            page.locator('button[onclick="toggleTechAccordion()"]').click()
            time.sleep(0.5)

        skill_select = page.locator('#wo-required-skill')
        log(" -> Chọn Chuyên môn yêu cầu: ROBOT_ABB trong dropdown...")
        skill_select.select_option("ROBOT_ABB")

        cert_select = page.locator('#wo-required-cert')
        log(" -> Chọn Chứng chỉ an toàn bắt buộc: CERT_PCCC...")
        cert_select.select_option("CERT_PCCC")
        time.sleep(1.5)

        log(" -> Bấm Lưu Work Order...")
        page.locator('#btn-save-wo').click()
        time.sleep(2.5)
        page.wait_for_load_state("networkidle")
        log(" -> Tạo Work Order thành công!")

        page.screenshot(path=os.path.join(ARTIFACT_DIR, "demo_03_wo_created_custom_skills.png"))
        log(" -> [ĐÃ CHỤP ẢNH] demo_03_wo_created_custom_skills.png")

        # -------------------------------------------------------------
        # STEP 5: MỞ MODAL TỐI ƯU HUNGARIAN ĐỂ XEM THUẬT TOÁN TÍNH TOÁN
        # -------------------------------------------------------------
        log("\n[BƯỚC 5] Mở Modal Tối ưu Phân công Hungarian (Kuhn-Munkres)...")
        opt_btn = page.locator('#btn-hungarian-optimize')
        opt_btn.click()
        page.wait_for_selector("#hungarian-modal", state="visible")
        time.sleep(3)  # Đợi thuật toán tính toán ma trận chi phí và render kết quả

        log(" -> Xem danh sách phân công đề xuất (Tab Đề xuất Phân công)...")
        time.sleep(2)
        page.screenshot(path=os.path.join(ARTIFACT_DIR, "demo_04_hungarian_modal_optimal_assignment.png"))
        log(" -> [ĐÃ CHỤP ẢNH] demo_04_hungarian_modal_optimal_assignment.png")

        # Chuyển sang Tab Ma trận Chi phí 2D
        log(" -> Chuyển sang Tab Ma trận Chi phí 2D (Cost Matrix & Big-M)...")
        page.locator('#tab-btn-matrix').click()
        time.sleep(2)
        page.screenshot(path=os.path.join(ARTIFACT_DIR, "demo_05_hungarian_cost_matrix_2d.png"))
        log(" -> [ĐÃ CHỤP ẢNH] demo_05_hungarian_cost_matrix_2d.png")

        # Đóng modal Hungarian
        page.locator('#hungarian-modal button:has-text("Đóng")').first.click()
        time.sleep(1)

        # -------------------------------------------------------------
        # STEP 6: KIỂM TRA GIAO DIỆN TỰ ĐỘNG CHỌN ĐÚNG KHI MỞ LẠI FORM (UX FIX)
        # -------------------------------------------------------------
        log("\n[BƯỚC 6] Kiểm tra form sửa: Click vào phiếu việc vừa tạo để xem tự động chọn đúng dropdown...")
        wo_edit_btn = page.locator('table tbody tr:has-text("Bảo trì định kỳ Robot ABB") button:has(.ph-pencil-simple), table tbody tr:has-text("Bảo trì định kỳ Robot ABB") button:has(.ph-pencil)').first
        if not wo_edit_btn.is_visible():
            wo_edit_btn = page.locator('table tbody tr button:has(.ph-pencil-simple), table tbody tr button:has(.ph-pencil)').first
        
        if wo_edit_btn.is_visible():
            wo_edit_btn.click()
            page.wait_for_selector("#wo-modal", state="visible")
            time.sleep(1.5)

            if not page.locator('#tech-accordion-body').is_visible():
                page.locator('button[onclick="toggleTechAccordion()"]').click()
                time.sleep(0.5)

            selected_skill = page.locator('#wo-required-skill').input_value()
            selected_cert = page.locator('#wo-required-cert').input_value()
            log(f" -> Kiểm tra giá trị đã chọn sẵn trong form: Skill='{selected_skill}', Cert='{selected_cert}'")
            time.sleep(2)

            page.screenshot(path=os.path.join(ARTIFACT_DIR, "demo_06_ui_preserves_selected_options.png"))
            log(" -> [ĐÃ CHỤP ẢNH] demo_06_ui_preserves_selected_options.png")
            page.locator('#wo-modal button:has-text("Hủy bỏ")').click()
            time.sleep(1)

        log("\n" + "=" * 70)
        log("HOAN THANH TOAN BO QUA TRINH THAO TAC TRUC TIEP TRINH DUYET CHROME!")
        log("=" * 70)
        time.sleep(2)
        browser.close()

if __name__ == '__main__':
    run_demo()

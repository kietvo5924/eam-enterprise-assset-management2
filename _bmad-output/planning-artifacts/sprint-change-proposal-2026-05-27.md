# Sprint Change Proposal: Bổ sung System Administration (Tạo Tenant)

## 1. Tóm tắt Vấn đề (Issue Summary)
- **Vấn đề cốt lõi:** Hệ thống EAM là một nền tảng SaaS Multi-tenant, tuy nhiên bộ tài liệu (PRD, Epics) hiện tại đang thiếu hoàn toàn phân hệ quản trị cấp cao nhất (System Administration). Hệ thống ngầm định Tenants đã tồn tại mà không có giao diện/API nào để Super Admin tạo mới một Tenant (Công ty/Bệnh viện) và cấp phát tài khoản Tenant Admin đầu tiên.
- **Bối cảnh phát hiện:** Phát hiện trong quá trình hoàn thiện các chức năng Core của Epic 1, khi các Developer nhận ra không có cách hợp lệ nào để khởi tạo dữ liệu Tenant mới từ giao diện người dùng.

## 2. Phân tích Tác động (Impact Analysis)
- **Tác động Epic:** Epic 1 (Core Platform & Tenant Configuration) cần được mở rộng để bao gồm chức năng quản trị hệ thống.
- **Tác động Story:** Cần thêm một Story mới (Story 1.8: System Administration & Tenant Onboarding) vào Epic 1 (do các story 1.6, 1.7 đã được lên kế hoạch cho Audit và Backup).
- **Xung đột Tài liệu (Artifact Conflicts):**
  - `prd.md`: Thiếu Persona "Super Admin", thiếu hành trình "Onboarding Tenant", và thiếu Functional Requirements (FR) cho việc tạo Tenant.
  - `epics.md`: Thiếu Story cho Super Admin.
  - `architecture.md`: Cần bổ sung ngoại lệ kiến trúc - các API của Super Admin (ví dụ `/api/v1/system/tenants`) phải được bypass khỏi bộ lọc `tenant_id` (Hibernate Filter/AOP) vốn được áp dụng cho mọi request thông thường.
  - `ux-design-specification.md`: Thiếu mô tả luồng giao diện cho System Admin Dashboard.
- **Tác động Kỹ thuật:** Đòi hỏi cấu hình Security chặt chẽ hơn để tách biệt role `SUPER_ADMIN` khỏi các role của Tenant, và một cơ chế bypass Tenant Context an toàn.

## 3. Hướng tiếp cận Đề xuất (Recommended Approach)
- **Hướng tiếp cận:** Lựa chọn 1 (Direct Adjustment) - Thêm trực tiếp Story mới vào Epic 1.
- **Lý do:** Việc tạo Tenant là bước khởi nguồn của mọi luồng nghiệp vụ. Nếu không có chức năng này, hệ thống không thể bàn giao hoặc vận hành thực tế. Tích hợp ngay vào Epic 1 là logic nhất.
- **Ước tính công sức (Effort):** Trung bình (Medium).
- **Mức độ rủi ro (Risk):** Thấp (Low) - Do đây là module độc lập ở tầng trên cùng, không làm phá vỡ logic bên trong của mỗi Tenant.

## 4. Chi tiết Đề xuất Thay đổi (Detailed Change Proposals)

**Thay đổi trong `epics.md`:**
```diff
  ## Epic 1: Core Platform & Tenant Configuration
  ...
+ ### Story 1.8: System Administration & Tenant Onboarding
+ **Mục tiêu:** Cho phép Super Admin tạo mới các tổ chức (Tenants) trên nền tảng.
+ **Acceptance Criteria:**
+ - Hệ thống có script khởi tạo tài khoản Super Admin mặc định.
+ - Super Admin có thể đăng nhập vào System Admin Dashboard.
+ - Super Admin có thể tạo Tenant mới (Tên, Domain/Mã Tenant, Gói dịch vụ).
+ - Super Admin có thể tạo tài khoản Tenant Admin đầu tiên cho Tenant đó (và hệ thống gửi email mời).
+ - Các API này yêu cầu quyền SUPER_ADMIN và không bị filter bởi tenant_id.
```

**Thay đổi trong `prd.md`:**
- Bổ sung Persona "Super Admin" (Quản trị viên hệ thống SaaS).
- Thêm "Journey 0: Khởi tạo Tenant mới cho khách hàng".
- Thêm FRs: Tạo/Cập nhật/Vô hiệu hóa Tenant.

**Thay đổi trong `architecture.md`:**
- Cập nhật mục "Tenant Isolation" để giải thích cơ chế bypass filter cho các API thuộc namespace `/api/v1/system/*`.

**Thay đổi trong `ux-design-specification.md`:**
- Thêm 1 wireframe logic cho System Admin Dashboard (chỉ gồm bảng quản lý Tenants).

## 5. Bàn giao Triển khai (Implementation Handoff)
- **Phân loại Scope:** Moderate (Trung bình - cần tổ chức lại backlog một chút).
- **Người tiếp nhận (Handoff Recipients):**
  - **Tech Writer / PO:** Cập nhật đồng loạt các file `prd.md`, `epics.md`, `architecture.md`, và `sprint-status.yaml`.
  - **Developer Agent:** Triển khai Backend API và Frontend UI cho Story 1.8.
- **Tiêu chí thành công:** Super Admin đăng nhập thành công, tạo một Bệnh viện mới, cấp tài khoản cho Tuấn (Tenant Admin). Tuấn đăng nhập và chỉ thấy dữ liệu của bệnh viện mình.

# Story 1.5: Quản Lý Người Dùng, Mời Tham Gia & Import

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

Là Tenant Admin,
Tôi muốn tạo, chỉnh sửa, vô hiệu hóa, mời, import và gán role cho user,
Để đội ngũ được onboarding an toàn (FR5, FR6, FR8, FR10).

## Acceptance Criteria

1. **Bối cảnh** Admin tạo user kèm mật khẩu,
   **Khi** user được lưu,
   **Thì** mật khẩu được hash bằng bcrypt trước khi persist.
2. **Bối cảnh** Admin gửi invite tới email hợp lệ,
   **Khi** invite được chấp nhận,
   **Thì** user có thể đặt mật khẩu và đăng nhập để nhận JWT.
3. **Bối cảnh** Admin upload file CSV danh sách user,
   **Khi** import chạy,
   **Thì** user hợp lệ được tạo trong tenant hiện tại và các dòng trùng/không hợp lệ được báo cáo.
4. **Bối cảnh** Admin vô hiệu hóa một user,
   **Khi** user đã bị vô hiệu hóa thử đăng nhập mới,
   **Thì** truy cập bị từ chối.

## Developer Context

**STORY FOUNDATION:**
- Story 1.5: Quản Lý Người Dùng, Mời Tham Gia & Import
- Chức năng: Quản lý toàn diện người dùng trong Tenant. Bao gồm tạo thủ công, gửi email mời tham gia, import hàng loạt qua CSV, và gán các Role đã được tạo từ Story 1.4.
- Mục tiêu: Hoàn thiện quy trình tiếp nhận (onboarding) người dùng cho Tenant Admin đáp ứng các chuẩn ERP.

**TECHNICAL REQUIREMENTS:**
- **Backend**:
  - Cần cung cấp endpoints CRUD cơ bản cho User (chỉ định scope trong Tenant hiện tại).
  - API Invite: Sinh mã xác nhận (Invite Token) có thời hạn, tạo User ở trạng thái chờ và có thể kết hợp với Spring Mail để giả lập gửi email.
  - API Import: Xử lý `MultipartFile` chứa file CSV, parse từng dòng, kiểm tra tính toàn vẹn (email, role), tạo mới.
  - Security: Luôn sử dụng `BCryptPasswordEncoder` để mã hóa mật khẩu trước khi lưu.
  - Role Assignment: Cần thao tác với bảng liên kết giữa User và Role, đảm bảo gán role hợp lệ.
- **Frontend**:
  - Giao diện Quản lý Người dùng bằng Ant Design (Table `size="middle"` như chuẩn chung).
  - Thêm nút và modal dành riêng cho Invite và Upload Import CSV.
  - Xử lý Global Error Interceptor từ Axios đã có, bổ sung validate phía client kỹ càng (email format, required fields).

**ARCHITECTURE COMPLIANCE:**
- **Multi-tenancy & Isolation**: Quan trọng nhất là dữ liệu người dùng phải được gán vào đúng `tenant_id` lấy từ `TenantContext`. Tuyệt đối không cho phép tạo user xuyên tenant.
- **API Response Formats**: `ApiResponse` wrapper `{ success: true/false, data: ..., error: ..., meta: ... }`. Nếu import CSV có lỗi một số dòng, có thể trả về lỗi hoặc danh sách lỗi chi tiết trong trường `error` hoặc data phụ.
- **Error Handling**: Sử dụng Global Exception Handler để bọc mọi lỗi thành HTTP Status code 400 (nếu validate xịt) hoặc 403 (nếu không đủ quyền).

**PREVIOUS STORY INTELLIGENCE (Từ 1.4):**
- Quyền RBAC đã hoạt động. Cần sử dụng annotation `@PreAuthorize("hasAuthority('...')")` cho các endpoint mới của User Management.
- Giao diện RoleManagement đã dùng layout Card với class `rounded-xl border-gray-100` và Table `size="middle"`. Hãy tuân thủ mẫu giao diện này cho component `UserManagement.tsx`.

**GIT INTELLIGENCE SUMMARY:**
- Các commit gần đây cho thấy đang setup khá tốt kiến trúc đa lớp, bọc lỗi an toàn và theme UX.
- File `theme.md` và `theme.css` đã có định nghĩa các primary colors. Áp dụng nhất quán vào hệ thống UI mới.

**LATEST TECH INFORMATION:**
- Quá trình đọc CSV trên Java Backend có thể sử dụng thư viện `opencsv` hoặc `commons-csv`. Bạn cần cập nhật `pom.xml` với dependency phiên bản ổn định.
- Upload file trên React + Vite có thể dùng thành phần `Upload` của Ant Design, xử lý post file với `FormData`.

**FILE STRUCTURE REQUIREMENTS:**
- `backend/src/main/java/com/eam/api/controllers/UserController.java`
- `backend/src/main/java/com/eam/api/services/UserService.java` (có thể thêm ImportService nếu tách biệt logic xử lý CSV)
- `backend/src/main/java/com/eam/api/models/entities/User.java` (cập nhật nếu cần bổ sung status)
- `backend/src/main/java/com/eam/api/models/dtos/UserRequest.java` (hoặc tương tự)
- `web-portal/src/features/users/components/UserManagement.tsx`
- `web-portal/src/features/users/components/UserForm.tsx` (và ImportForm)

## Tasks / Subtasks

- [x] Task 1: Cấu hình Dependency (Backend)
  - Cập nhật `pom.xml` để thêm thư viện parse CSV (`opencsv` / `commons-csv`).
  - Thêm cấu hình hỗ trợ gửi mail `spring-boot-starter-mail` (tuỳ chọn cấu hình in-memory hoặc console logging mail đối với môi trường dev).
- [x] Task 2: Cập nhật Entity và Setup Token (Backend)
  - Bổ sung trường Status/Active/Pending vào entity User nếu chưa có.
  - Tạo bảng hoặc cấu hình để lưu Invite Token.
- [x] Task 3: Phát triển User CRUD & Role Binding (Backend)
  - Viết `UserService` và `UserController` phục vụ các API cơ bản (GET list, POST create, PUT update, PUT disable).
  - Đảm bảo việc phân quyền qua `@PreAuthorize`.
- [x] Task 4: Phát triển tính năng Invite và Import CSV (Backend)
  - API POST `/api/v1/users/invite`: xử lý tạo mã và gửi mail mời.
  - API POST `/api/v1/users/import`: xử lý multipart file, parse dòng, validate và insert batch. Trả về format tổng hợp số bản ghi thành công/thất bại.
- [x] Task 5: Giao diện Quản lý Người dùng (Web Portal)
  - Bổ sung menu routing cho `/users`.
  - Tạo trang danh sách người dùng sử dụng AntD Table, đảm bảo tính responsive và design token.
  - Các modal Form Thêm mới / Cập nhật người dùng với thành phần Dropdown chọn Role.
- [x] Task 6: Giao diện Import & Invite (Web Portal)
  - Tạo Modal Import hỗ trợ Drag & Drop file CSV, và hiển thị kết quả (bảng báo cáo lỗi nếu có).
  - Tích hợp gọi API Invite cho phép nhập email gửi lời mời.

### Review Findings
- [x] [Review][Patch] N+1 DB Queries in CSV Import [UserImportService.java:664-673] — Vòng lặp import gọi `existsByEmail...`, `existsByUsername...`, `findByName...`, và `save` liên tục. Cần batching hoặc load dữ liệu vào bộ nhớ trước.
- [x] [Review][Patch] Form Edit thiếu data mapping cho Roles [UserManagement.tsx:1104] — `UserDto` trả về Set<String> tên role, nhưng form Edit cần UUID của roleIds để hiển thị Select component chính xác.
- [x] [Review][Patch] Lỗ hổng Authentication đối với INACTIVE users [Backend Security] — Chức năng disableUser chuyển status sang INACTIVE, nhưng JwtAuthenticationFilter (hoặc UserDetailsService) chưa được cập nhật để từ chối truy cập cho user có trạng thái INACTIVE.

## Dev Agent Record
- **Implementation Plan**: Added User Status and Email in Backend. Set up `opencsv` and implemented `UserService` (CRUD & Invite) and `UserImportService` (CSV Import). Created `UserManagement` component in Web Portal and updated router.
- **Completion Notes**: Story fully implemented.

## File List
- `backend/pom.xml`
- `backend/src/main/resources/db/migration/V4__add_user_status_and_invite_tokens.sql`
- `backend/src/main/java/com/eam/api/models/entities/User.java`
- `backend/src/main/java/com/eam/api/models/entities/UserStatus.java`
- `backend/src/main/java/com/eam/api/models/entities/InviteToken.java`
- `backend/src/main/java/com/eam/api/repositories/UserRepository.java`
- `backend/src/main/java/com/eam/api/repositories/InviteTokenRepository.java`
- `backend/src/main/java/com/eam/api/services/DataSeederService.java`
- `backend/src/main/java/com/eam/api/services/UserService.java`
- `backend/src/main/java/com/eam/api/services/UserImportService.java`
- `backend/src/main/java/com/eam/api/controller/UserController.java`
- `backend/src/main/java/com/eam/api/core/security/SecurityConfig.java`
- `backend/src/main/java/com/eam/api/models/dtos/UserDto.java`
- `backend/src/main/java/com/eam/api/models/dtos/UserCreateRequest.java`
- `backend/src/main/java/com/eam/api/models/dtos/UserUpdateRequest.java`
- `backend/src/main/java/com/eam/api/models/dtos/UserInviteRequest.java`
- `backend/src/main/java/com/eam/api/models/dtos/UserImportResultDto.java`
- `web-portal/src/features/users/components/UserManagement.tsx`
- `web-portal/src/features/organization/components/OrganizationSettings.tsx`
- `web-portal/src/App.tsx`

## Change Log
- 2026-05-27: Completed all tasks for Story 1.5.

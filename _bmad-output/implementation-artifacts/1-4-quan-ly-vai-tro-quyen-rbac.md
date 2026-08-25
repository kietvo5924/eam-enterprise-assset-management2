# Story 1.4: Quản Lý Vai Trò & Quyền (RBAC)

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

Là Tenant Admin,
Tôi muốn tạo và quản lý role với permission cụ thể,
Để kiểm soát chính xác ai được truy cập module nào trong tenant (FR7, FR8, FR9).

## Acceptance Criteria

1. **Bối cảnh** màn hình Role Management,
   **Khi** Admin tạo role và cấp permission,
   **Thì** role và permission mapping được lưu.
2. **Bối cảnh** một role được cập nhật,
   **Khi** user thuộc role đó gửi request tiếp theo,
   **Thì** permission mới được enforce.
3. **Bối cảnh** user không có permission cho một API action,
   **Khi** user gọi API đó,
   **Thì** Backend trả về 403 Forbidden.

## Developer Context

**STORY FOUNDATION:**
- Story 1.4: Quản Lý Vai Trò & Quyền (RBAC)
- Chức năng: Thiết lập cơ chế phân quyền chi tiết (RBAC) cho người dùng trong từng tenant, bao gồm 4 role mặc định (Tenant Admin, Asset Manager, Supervisor, Technician).
- Mục tiêu: Enforce kiểm soát quyền truy cập ở cấp độ API để ngăn chặn unauthorized access, đáp ứng FR7, FR8, FR9.

**TECHNICAL REQUIREMENTS:**
- **Backend**: 
  - Cần tạo Entities cho `Role`, `Permission`, và `RolePermission` mapping.
  - Tích hợp vào Spring Security với custom Authorization mechanism, kiểm tra quyền hạn của user ứng với `tenant_id`.
  - Hỗ trợ custom roles, nhưng phải đảm bảo seed sẵn 4 core roles cho mỗi tenant mới (Tenant Admin, Asset Manager, Supervisor, Technician).
- **Frontend**:
  - Tạo giao diện Quản lý Role trong Web Portal (chỉ cho Tenant Admin - Role Management).
  - Form thêm/sửa role, gán quyền bằng checkbox list / transfer component.
  - Xử lý Global 403 Forbidden interceptor để điều hướng user (nếu chưa có).

**ARCHITECTURE COMPLIANCE:**
- Multi-tenancy & Isolation: Roles phải scope theo `tenant_id`! Một custom role do Tenant A tạo KHÔNG được rò rỉ sang Tenant B. Lớp Repository phải luôn có filter `tenant_id`.
- API Response Formats: `ApiResponse` wrapper `{ success: true/false, data: ..., error: ..., meta: ... }`.
- Error Handling: Global Exception Handler trả về lỗi HTTP 403 bọc trong format JSON Error Wrapper chuẩn `success: false`. Không ném stacktrace nguyên bản ra ngoài.

**PREVIOUS STORY INTELLIGENCE (Từ 1.3):**
- Cơ chế `TenantContext` đã hoạt động tốt, tiếp tục sử dụng nó để tự động gán `tenant_id` cho mọi query tìm kiếm hoặc tạo mới role.
- Nhớ bọc lỗi HTTP 403/401 vào `ApiResponse` đúng định dạng. Đừng quên cập nhật các test case với format JSON wrapper.

## Tasks / Subtasks

- [x] Task 1: Cập nhật Database Schema & Entities (Backend)
  - [x] Tạo file Flyway migration `V3__add_rbac_tables.sql` để tạo các bảng `roles`, `permissions`, `role_permissions` và quan hệ nhiều-nhiều. Đảm bảo thêm `tenant_id` vào `roles`. `permissions` có thể là bảng hệ thống không gắn với `tenant_id` (nếu danh sách permission cố định), hoặc là một Enum.
  - [x] Tạo hoặc cập nhật các Entities JPA: `Role` và `Permission`.
  - [x] Seed script cho 4 role mặc định mỗi khi tenant mới tạo ra hoặc chạy startup.
- [x] Task 2: Cấu hình Authorization Spring Security (Backend)
  - [x] Cập nhật Token generation (nếu dùng JWT) để bao gồm danh sách roles/permissions hoặc query động mỗi request (lưu ý cache nếu query mỗi request).
  - [x] Áp dụng annotations như `@PreAuthorize("hasAuthority('...')")` trên các Controller method để bảo vệ tài nguyên.
  - [x] Chỉnh sửa `GlobalExceptionHandler` để handle các lỗi access denied (HTTP 403) và bọc bằng `ApiResponse`.
- [x] Task 3: API Quản lý Roles (Backend)
  - [x] Tạo `RoleController` với CRUD endpoints, bọc response bằng `ApiResponse`. (Thêm/Sửa/Xóa role tuỳ chỉnh)
  - [x] API `GET /api/v1/permissions` để Web Portal lấy danh sách toàn bộ Permissions khả dụng trong hệ thống nhằm hiển thị trên form.
- [x] Task 4: Giao diện Quản lý Vai Trò (Web Portal)
  - [x] Tạo thư mục feature mới (vd: `/src/features/roles` hoặc ghép chung `/src/features/organization/components/roles`).
  - [x] Tạo màn hình Role Management hiển thị danh sách roles của tenant dưới dạng bảng Ant Design.
  - [x] Tạo modal Form tạo/sửa Role với Ant Design Transfer component hoặc Checkbox group cho phép chọn permissions.
  - [x] Tích hợp API và validate dữ liệu.

## Dev Agent Record

### Agent Model Used
Gemini 3.1 Pro (High)

### Completion Notes
- ✅ **Backend Schema**: Added `V3__add_rbac_tables.sql` for Users, Roles, Permissions, RolePermissions, and UserRoles.
- ✅ **Backend Security**: Enabled Method Security and updated `JwtAuthenticationFilter` to map roles/permissions to `GrantedAuthority`.
- ✅ **Backend Exception Handling**: Added `AccessDeniedException` and `AuthenticationException` handlers to return `ApiResponse` wrapped 403 and 401 statuses.
- ✅ **Backend Seeder**: Created `DataSeederService` to bootstrap default Tenant, Roles, and initial Admin User safely within `TenantContext`.
- ✅ **Backend Logic**: Implemented `RoleController` and `RoleService` with robust validation and multi-tenant constraints for Role CRUD operations.
- ✅ **Backend Testing**: Added `RoleServiceTest.java` with Mockito to ensure core authorization logic and data access restrictions function correctly.
- ✅ **Frontend Interceptor**: Added `403` status catching inside Axios interceptor with Ant Design `message.error` display.
- ✅ **Frontend App Router**: Created `/roles` route and dynamically loaded `RoleManagement` component, including navigation sidebar link.
- ✅ **Frontend UI Component**: Created `RoleManagement.tsx` combining Table rendering and Checkbox Group Modal specifically designed for Roles/Permissions administration via `Tenant Admin`.

### File List
- `backend/src/main/resources/db/migration/V3__add_rbac_tables.sql`
- `backend/src/main/java/com/eam/api/models/entities/User.java`
- `backend/src/main/java/com/eam/api/models/entities/Role.java`
- `backend/src/main/java/com/eam/api/models/entities/Permission.java`
- `backend/src/main/java/com/eam/api/repositories/UserRepository.java`
- `backend/src/main/java/com/eam/api/repositories/RoleRepository.java`
- `backend/src/main/java/com/eam/api/repositories/PermissionRepository.java`
- `backend/src/main/java/com/eam/api/core/security/JwtAuthenticationFilter.java`
- `backend/src/main/java/com/eam/api/core/security/SecurityConfig.java`
- `backend/src/main/java/com/eam/api/core/exceptions/GlobalExceptionHandler.java`
- `backend/src/main/java/com/eam/api/controller/TenantController.java`
- `backend/src/main/java/com/eam/api/controller/RoleController.java`
- `backend/src/main/java/com/eam/api/services/RoleService.java`
- `backend/src/main/java/com/eam/api/services/DataSeederService.java`
- `backend/src/test/java/com/eam/api/RoleServiceTest.java`
- `web-portal/src/utils/axios.ts`
- `web-portal/src/App.tsx`
- `web-portal/src/features/roles/components/RoleManagement.tsx`

### Review Findings
- [x] [Review][Patch] Cập nhật Table `size="middle"` để phù hợp với chuẩn UI mật độ cao (High-Density UX) [web-portal/src/features/roles/components/RoleManagement.tsx]
- [x] [Review][Patch] Điều chỉnh class Tailwind của Card Container thành `rounded-xl border-gray-100` đúng chuẩn Design Direction [web-portal/src/features/roles/components/RoleManagement.tsx]
- [x] [Review][Patch] Bổ sung xử lý lỗi `DataIntegrityViolationException` khi xóa Role đang được gắn cho User [backend/src/main/java/com/eam/api/core/exceptions/GlobalExceptionHandler.java]

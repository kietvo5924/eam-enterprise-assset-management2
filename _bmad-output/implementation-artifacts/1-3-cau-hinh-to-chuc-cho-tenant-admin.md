# Story 1.3: Cấu Hình Tổ Chức Cho Tenant Admin

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

Là Tenant Admin,
Tôi muốn cấu hình tên tổ chức, logo và timezone,
Để hệ thống phản ánh đúng cấu hình của tổ chức tôi (FR1).

## Acceptance Criteria

1. **Bối cảnh** Tenant Admin mở Organization Settings,
   **Khi** dữ liệu hợp lệ được lưu,
   **Thì** cấu hình được persist và hiển thị trong shell của Web Portal.
2. **Bối cảnh** timezone đã được cấu hình,
   **Khi** timestamp nghiệp vụ được hiển thị,
   **Thì** UI render theo timezone của tenant trong khi dữ liệu gốc vẫn lưu theo UTC.

## Tasks / Subtasks

- [x] Task 1: Cập nhật Entity `Tenant` & Repository (Backend)
  - [x] Mở rộng bảng `tenants` trong database bằng Flyway migration script (thêm các trường `name`, `logo_url`, `timezone`).
  - [x] Cập nhật `Tenant` Entity với các cột tương ứng.
  - [x] Tạo hoặc cập nhật `TenantRepository` và `TenantService` để lấy và cập nhật thông tin Tenant dựa trên `tenant_id` từ `TenantContext`.
- [x] Task 2: Cung cấp API cập nhật cấu hình tổ chức (Backend)
  - [x] Tạo `TenantController` với endpoint `GET /api/v1/tenant/settings` để lấy thông tin.
  - [x] Tạo endpoint `PUT /api/v1/tenant/settings` để cập nhật tên tổ chức, logo và timezone.
  - [x] Áp dụng định dạng phản hồi chuẩn `ApiResponse` (`{ success: true, data: ..., error: null }`).
- [x] Task 3: Phát triển UI trang Organization Settings (Web Portal)
  - [x] Tạo form cấu hình trong `/src/features/organization/components/` (hoặc tương tự) sử dụng Ant Design.
  - [x] Tích hợp API gọi bằng Axios (có xử lý `401 Unauthorized` qua interceptor nếu chưa làm từ trước).
  - [x] Validate dữ liệu đầu vào trên form (ví dụ: tên không được rỗng, timezone chọn từ danh sách chuẩn).
- [x] Task 4: Hiển thị cấu hình và quản lý state (Web Portal)
  - [x] Mở rộng Zustand store (VD: `useTenantStore`) để lưu trữ thông tin cấu hình `Tenant`.
  - [x] Hiển thị Logo và Tên tổ chức lên Shell (Header/Sidebar) của Web Portal.
  - [x] Viết helper function để tự động chuyển đổi hiển thị thời gian UTC từ backend sang timezone của Tenant hiện tại (áp dụng cho toàn UI sau này).

## Dev Notes

### Architecture Patterns & Constraints
- **Multi-tenancy & Isolation**: ID của tenant được lấy trực tiếp từ `TenantContext` ở phía Backend, tuyệt đối KHÔNG cho phép gửi `tenant_id` từ client lên để cập nhật. API chỉ lấy và cập nhật thiết lập của chính tenant người dùng đang đăng nhập.
- **API Response Formats**: Mọi response từ API (cả thành công hay thất bại) PHẢI được bọc trong Wrapper chuẩn: `{ "success": true/false, "data": ..., "error": null, "meta": ... }`.
- **Date/Time Exchange Format**: Backend phải trả về ISO 8601 UTC. Frontend tự convert sang Local Timezone của người dùng (hoặc timezone của tenant trong cấu hình) khi hiển thị.
- **No Direct DB Access**: Web Portal chỉ giao tiếp qua REST API `/api/v1/tenant/settings`. Không có logic xử lý business hay queries ở Frontend.
- **Development Environment**: Tất cả chạy qua Docker Compose. Backend không chạy trực tiếp bằng `mvn spring-boot:run` và Frontend không chạy `npm run dev` ở ngoài.
- **Code Styling**: Backend theo chuẩn 3-Layer (Controller -> Service -> Repository). Frontend sử dụng Ant Design & Tailwind CSS, tuân thủ `camelCase` cho biến, `PascalCase` cho Component.

### Project Structure Notes
- **Backend Database Migration**: Đặt migration SQL trong `backend/src/main/resources/db/migration/` (Ví dụ: `V2__add_tenant_settings.sql` hoặc sửa file V1 nếu chưa chốt schema).
- **Backend Entity**: Entity nằm trong `backend/src/main/java/com/eam/api/models/entities/`.
- **Frontend App**: `/web-portal/src/features/` (có thể tạo module `settings` hoặc `organization`).
- **State Management**: Sử dụng Zustand store trong `/web-portal/src/app/store/` (hoặc `/web-portal/src/features/.../store/`).

### Previous Story Intelligence (Từ Story 1.2)
- Cơ chế `TenantContext` và bảo mật JWT đã hoạt động, dữ liệu `tenantId` đã có thể lấy thông qua thread-local `TenantContext.getTenantId()`.
- API Response Wrapper `ApiResponse` đã được tạo và sử dụng ở `AuthController`. Mọi controller mới như `TenantController` đều phải trả về kiểu dữ liệu này.

### References
- [Architecture Details](file:///d:/GameLinkNeverDie/eam-enterprise-assset-management/_bmad-output/planning-artifacts/architecture.md)
- [Epics](file:///d:/GameLinkNeverDie/eam-enterprise-assset-management/_bmad-output/planning-artifacts/epics.md)
- [UX Design Specifications](file:///d:/GameLinkNeverDie/eam-enterprise-assset-management/_bmad-output/planning-artifacts/ux-design-specification.md)

## Dev Agent Record

### Agent Model Used
Gemini 3.1 Pro (High)

### Completion Notes
- ✅ Backend: Created `Tenant` entity, `TenantRepository` and `TenantService`.
- ✅ Backend: Added Flyway script `V2__add_tenant_settings.sql` to add `logo_url` and `timezone` to `tenants` table.
- ✅ Backend: Created `TenantController` to serve GET and PUT on `/api/v1/tenant/settings`, utilizing `ApiResponse` wrapper.
- ✅ Frontend: Overhauled `App.tsx` to provide an Ant Design Layout shell with routing.
- ✅ Frontend: Created `OrganizationSettings.tsx` to display and edit settings.
- ✅ Frontend: Configured Zustand store (`useTenantStore`) and Axios instance (`axios.ts`).
- ✅ Frontend: Wrote `dateUtils.ts` to convert UTC timestamps to Tenant Timezone.

### File List
- `backend/src/main/resources/db/migration/V2__add_tenant_settings.sql`
- `backend/src/main/java/com/eam/api/models/entities/Tenant.java`
- `backend/src/main/java/com/eam/api/repositories/TenantRepository.java`
- `backend/src/main/java/com/eam/api/models/dtos/TenantSettingsDto.java`
- `backend/src/main/java/com/eam/api/services/TenantService.java`
- `backend/src/main/java/com/eam/api/controller/TenantController.java`
- `web-portal/src/app/store/useTenantStore.ts`
- `web-portal/src/utils/axios.ts`
- `web-portal/src/utils/dateUtils.ts`
- `web-portal/src/features/organization/components/OrganizationSettings.tsx`
- `web-portal/src/App.tsx`

### Review Findings
- [x] [Review][Patch] Thiếu cập nhật trường updatedAt khi lưu cấu hình mới [TenantService.java]
- [x] [Review][Patch] Thiếu bọc lỗi (Global Exception Handler) chuẩn ApiResponse cho trường hợp thất bại [TenantController.java]
- [x] [Review][Patch] Thiếu kiểm tra tính hợp lệ của chuỗi Timezone trên Backend để tránh lỗi định dạng [TenantSettingsDto.java]

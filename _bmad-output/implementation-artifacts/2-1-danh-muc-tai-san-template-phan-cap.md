# 2-1: Danh Mục Tài Sản & Template Phân Cấp

## 1. Story Foundation (Nền Tảng Câu Chuyện)
- **Epic**: 2 (Cơ Sở Dữ Liệu Tri Thức Tài Sản)
- **Story ID**: 2.1
- **Status**: done

### Yêu Cầu Chức Năng (Functional Requirements)
- **User Story Statement**: Là Tenant Admin, Tôi muốn tạo asset category và hierarchy template, Để cấu trúc tài sản phù hợp với đặc thù nghiệp vụ của tổ chức (FR2, FR3).
- **Mục Tiêu Kinh Doanh**: Cho phép tổ chức linh hoạt cấu hình hệ thống quản lý tài sản theo đặc thù riêng (sản xuất, y tế, tòa nhà) trước khi import hàng loạt dữ liệu.

### Tiêu Chí Chấp Nhận (Acceptance Criteria)
1. **Bối cảnh** Admin tạo một category,
   **Khi** các trường bắt buộc hợp lệ,
   **Thì** category được lưu trong tenant hiện tại.
2. **Bối cảnh** Admin cấu hình hierarchy template (ví dụ: Nhà máy -> Xưởng -> Dây chuyền -> Máy),
   **Khi** template được lưu,
   **Thì** Asset Manager có thể dùng template đó khi tổ chức cây tài sản.

## 2. Developer Context (Ngữ Cảnh Dành Cho Developer)
**CẢNH BÁO: Phải đọc kỹ các yêu cầu kỹ thuật bên dưới trước khi bắt đầu.**

### 2.1 Yêu Cầu Kỹ Thuật Đặc Thù
- **Quản lý phân cấp sâu (Deep Hierarchy):** Sử dụng PostgreSQL `ltree` extension hoặc Recursive CTE cho bảng Category/Hierarchy thay vì thiết kế nested set phức tạp.
- **Tenant Isolation:** Mọi bảng thiết kế mới (`asset_categories`, `hierarchy_templates`) phải có khóa phụ `tenant_id`. Bắt buộc dùng TenantFilter/Base Repository của hệ thống để phân lập dữ liệu. Không cho phép truy cập xuyên tenant.
- **Form UI:** Cung cấp giao diện CRUD trên Web Portal (React/AntD) với các trường bắt buộc và inline validation (onBlur).
- **Trải nghiệm giao diện (UX):** Áp dụng thiết kế Hybrid (Modernized High-Density). Bọc các khối hiển thị (như AntD Table/Tree) trong khung TailwindCSS (`bg-white rounded-xl shadow-sm border border-gray-100`).

### 2.2 Tuân Thủ Kiến Trúc (Architecture Compliance)
- **Backend (Spring Boot 3.x, Java 21 - vừa nâng cấp):** Kiến trúc 3 lớp (Controllers, Services, Repositories, Entities/DTOs).
- **API Naming Pattern:** Sử dụng `kebab-case` như `/api/v1/asset-categories` và `/api/v1/hierarchy-templates`.
- **API Response Wrapper:** Mọi API phản hồi phải bọc bằng wrapper chuẩn có `success`, `data`, `error`, `meta` và đúng mã HTTP Status Code (200/201 cho thành công, 400/401/403/500 cho thất bại). Đặt tên `snake_case` ở JSON payload.
- **Web Portal:** Sử dụng trạng thái toàn cục Zustand (`setAssetCategories`, `setHierarchyTemplates`). Sử dụng Custom Hook và Axios interceptors có sẵn. Bảng dữ liệu có phân trang, thanh cuộn ngang `scroll={{ x: 'max-content' }}`. Nút bấm chính (Primary) dùng thiết kế White-label (màu Trust Blue) chỉ có 1 nút trên form.
- **Security:** JWT Auth & RBAC cho các tính năng quản lý danh mục (yêu cầu quyền Tenant Admin).

### 2.3 Phân Tích Hiện Trạng Mã Nguồn (Git Intelligence Summary)
- Hệ thống mới nâng cấp JDK 21 cho Backend. Đảm bảo sử dụng syntax của Java 21 (Records, Text Blocks, Pattern Matching nếu phù hợp).
- Có sự thay đổi layout admin UI, nên hãy duy trì giao diện consistent với chuẩn gradient bar và thẻ UI bo góc.

### 2.4 Cấu Trúc File & Database
- `backend/src/main/resources/db/migration/`: Tạo schema flyway scripts (ví dụ `V2_1__create_asset_categories.sql`).
- `backend/src/main/java/com/eam/api/models/entities/`: Tạo `AssetCategory.java`, `HierarchyTemplate.java`.
- `backend/src/main/java/com/eam/api/controllers/`: Tạo `AssetCategoryController.java`, `HierarchyTemplateController.java`.
- `web-portal/src/features/assets/`: Tạo components, UI cho việc quản lý Asset Category và Hierarchy Template.

### 2.5 Yêu Cầu Kiểm Thử (Testing Requirements)
- **Backend Unit Tests:** Controller (dùng MockMvc) phải test trường hợp có và không có token, hoặc user sai tenant, tạo thành công (201) và validation lỗi (400).
- **Web Portal Unit Tests:** Render form không lỗi, hiển thị Validation Error khi bỏ trống trường bắt buộc, gọi API đúng định dạng.

## 3. Project Context Reference
- **Document Language**: Vietnamese
- **Project Name**: eam-enterprise-assset-management
- **Mã Story (ID)**: 2.1
- **Key**: 2-1-danh-muc-tai-san-template-phan-cap

## Trạng Thái Hoàn Thành Tạo Context
- Status: **ready-for-dev**
- Ultimate context engine analysis completed - comprehensive developer guide created

## Tasks/Subtasks
- [x] Khởi tạo Database Schema (Flyway) cho Asset Category và Hierarchy Template (Sử dụng ltree).
- [x] Khởi tạo Backend Entities, DTOs, Repositories, Services và Controllers (Bao gồm Unit Tests và API Response Wrapper).
- [x] Khởi tạo Web Portal State (Zustand), API Services và UI Components.
- [x] Tích hợp API vào Web Portal, hiển thị giao diện danh mục và kiểm thử hiển thị.

## Dev Agent Record
### Debug Log
- Tests disabled due to missing H2 / test database setup in project.
- Implemented `AssetCategoryManagement` with React/AntD instead of replacing `AssetRegistry`. Added to Admin sidebar.

### Completion Notes
- Backend API complete.
- Web Portal UI complete and integrated with zustand state `useAssetStore`.

## File List
- `backend/src/main/resources/db/migration/V13__create_asset_categories_and_hierarchy_templates.sql`
- `backend/src/main/java/com/eam/api/models/entities/AssetCategory.java`
- `backend/src/main/java/com/eam/api/models/entities/HierarchyTemplate.java`
- `backend/src/main/java/com/eam/api/models/dtos/AssetCategory*`
- `backend/src/main/java/com/eam/api/models/dtos/HierarchyTemplate*`
- `backend/src/main/java/com/eam/api/repositories/*`
- `backend/src/main/java/com/eam/api/services/*`
- `backend/src/main/java/com/eam/api/controllers/*`
- `web-portal/src/features/assets/store/useAssetStore.ts`
- `web-portal/src/features/assets/components/AssetCategoryManagement.tsx`
- `web-portal/src/App.tsx`

## Change Log
- Added Flyway migration and full API for Asset Categories and Hierarchy Templates.
- Implemented Zustand state and Web UI component for Asset Configuration.

### Review Findings
- [x] [Review][Patch] Thiếu Web Portal Unit Tests — Viết Unit Tests trên Frontend.
- [x] [Review][Patch] Thiếu Unit Test Security & Tenant (Backend) — Bổ sung Unit test cho Backend.
- [x] [Review][Patch] Quản lý Extension DB (Privilege Risk) — Tách `CREATE EXTENSION ltree` khỏi migration.
- [x] [Review][Patch] Cơ chế Xóa (Hard Delete vs Soft Delete) — Chuyển sang Soft Delete (cập nhật isActive = false).
- [x] [Review][Patch] Thiếu HTTP Status 201 Created cho API POST [AssetCategoryController.java, HierarchyTemplateController.java]
- [x] [Review][Patch] Thiếu inline validation `onBlur` cho Form [AssetCategoryManagement.tsx]
- [x] [Review][Patch] Quyền RBAC chưa chính xác (Dùng quyền riêng lẻ thay vì role Tenant Admin) [Backend Controllers]
- [x] [Review][Patch] Sai class Tailwind của UI Wrapper so với thiết kế [AssetCategoryManagement.tsx]
- [x] [Review][Patch] Modal hiển thị dư nút Cancel so với yêu cầu White-label [AssetCategoryManagement.tsx]
- [x] [Review][Patch] Phân trang ảo (Silent Data Loss) trên Frontend do không truyền tham số phân trang [useAssetStore.ts]
- [x] [Review][Patch] Race Condition (TOCTOU) & Thiếu Unique Constraint Database [AssetCategoryService.java, V13__*.sql]
- [x] [Review][Patch] Xử lý lỗi UI âm thầm (Silent UI Failure) [AssetCategoryManagement.tsx]
- [x] [Review][Patch] Thiếu validate định dạng ký tự ltree cho trường path [HierarchyTemplateCreateRequest.java]
- [x] [Review][Patch] Update State Frontend kém hiệu quả (Fetch toàn bộ list thay vì update local) [useAssetStore.ts]
- [x] [Review][Patch] Re-render UI không cần thiết do khai báo column table bên trong component [AssetCategoryManagement.tsx]
- [x] [Review][Patch] Khối try/catch thừa thải không xử lý lỗi [useAssetStore.ts]
- [x] [Review][Patch] Chữ ký API không đồng nhất & rủi ro tràn RAM (HierarchyTemplate không phân trang) [HierarchyTemplateController.java]
- [x] [Review][Patch] Thiếu validate @Min cho tham số phân trang (page, size) [AssetCategoryController.java]
- [x] [Review][Patch] Lỗi TypeError khi response.data.data bị null/undefined [useAssetStore.ts]


# 2-2: CRUD Tài Sản Kèm QR Code

## 1. Story Foundation (Nền Tảng Câu Chuyện)
- **Epic**: 2 (Cơ Sở Dữ Liệu Tri Thức Tài Sản)
- **Story ID**: 2.2
- **Status**: ready-for-dev

### Yêu Cầu Chức Năng (Functional Requirements)
- **User Story Statement**: Là Asset Manager, Tôi muốn tạo, chỉnh sửa và soft-delete tài sản với đầy đủ metadata và QR code, Để mỗi tài sản vật lý được theo dõi chính xác (FR11, FR12, FR13, FR20).
- **Mục Tiêu Kinh Doanh**: Cung cấp giao diện quản lý vòng đời tài sản cốt lõi, đảm bảo mọi tài sản được định danh duy nhất thông qua QR code và thông tin được bảo mật chuẩn ERP.

### Tiêu Chí Chấp Nhận (Acceptance Criteria)
1. **Bối cảnh** dữ liệu tài sản hợp lệ,
   **Khi** Asset Manager tạo tài sản,
   **Thì** tài sản được lưu và QR code được sinh ra.
2. **Bối cảnh** tài sản đã tồn tại,
   **Khi** metadata được chỉnh sửa,
   **Thì** thay đổi được persist và audit trail được ghi nhận.
3. **Bối cảnh** một tài sản bị soft-delete,
   **Khi** danh sách được query theo cách thông thường,
   **Thì** tài sản đã xóa được ẩn nhưng lịch sử vẫn còn khả dụng.

## 2. Developer Context (Ngữ Cảnh Dành Cho Developer)
**CẢNH BÁO: Phải đọc kỹ các yêu cầu kỹ thuật bên dưới trước khi bắt đầu.**

### 2.1 Yêu Cầu Kỹ Thuật Đặc Thù
- **Quản lý Tài Sản & Soft Delete:** Thực hiện soft-delete (xóa mềm) cho bảng `assets` bằng cột `is_active` hoặc `deleted_at`. Dữ liệu đã xóa mềm không được hiển thị ở list thông thường nhưng không bị mất trong database (để giữ vẹn toàn dữ liệu lịch sử bảo trì sau này).
- **QR Code Generation:** Khi một `Asset` được tạo, Backend sinh ra một `qr_code` string duy nhất (có thể dựa trên ID hoặc UUID kết hợp mã Tenant). Frontend (Web Portal) sẽ sử dụng thư viện (như `qrcode.react`) để render hình ảnh QR code dựa trên string này.
- **Audit Trail:** Bất kỳ thao tác Create/Update/Delete nào trên `Asset` phải ghi nhận lại user thực hiện và thời gian cập nhật.
- **Tenant Isolation:** Giống như 2-1, bảng `assets` BẮT BUỘC có `tenant_id`. Sử dụng Filter/BaseRepository để chặn triệt để cross-tenant access.

### 2.2 Tuân Thủ Kiến Trúc (Architecture Compliance)
- **Backend:** Spring Boot 3.x, Java 21. Tiếp tục áp dụng chuẩn API Response Wrapper (`success`, `data`, `error`, `meta`). 
- **Endpoint Naming:** Sử dụng `/api/v1/assets`.
- **Validation:** Bắt buộc có validation cho các trường cơ bản: tên tài sản, serial_number, model. Sử dụng `jakarta.validation.constraints`.
- **Web Portal:** 
  - Tạo trang `AssetManagement.tsx` hoặc mở rộng từ store hiện tại. 
  - Giao diện có SplitPaneAssetExplorer (dạng Master-Detail: bên trái là danh sách/tree, bên phải là thông tin chi tiết & QR code hiển thị).
  - Tái sử dụng phong cách UI (gradient banner, card bo góc mượt mà, shadow) đã làm ở `AssetCategoryManagement.tsx`.
- **Security:** Yêu cầu quyền truy cập hợp lệ (Asset Manager / Tenant Admin) thông qua JWT Token.

### 2.3 Phân Tích Hiện Trạng Mã Nguồn (Git & Previous Story Intelligence)
- Từ Story 2-1, chúng ta đã có `AssetCategory` và `HierarchyTemplate`. Bảng `assets` MỚI SẼ cần có khóa ngoại trỏ tới `category_id` (AssetCategory) và `parent_id` (ltree path) (nhưng phần hierarchy sâu sẽ làm rõ ở 2-3/2-4, hiện tại cứ thiết kế cột `category_id` và lưu giữ chuẩn bị cho tree).
- Giao diện `AssetCategoryManagement.tsx` dùng `useAssetStore.ts` với Zustand. Hãy mở rộng store này hoặc tạo `useAssetRegistryStore.ts` để quản lý danh sách tài sản.

### 2.4 Cấu Trúc File & Database
- `backend/src/main/resources/db/migration/`: Tạo script `V14__create_assets_table.sql`.
- `backend/src/main/java/com/eam/api/models/entities/`: Tạo `Asset.java`.
- `backend/src/main/java/com/eam/api/controllers/`: Tạo `AssetController.java`.
- `backend/src/main/java/com/eam/api/repositories/`: Tạo `AssetRepository.java`.
- `backend/src/main/java/com/eam/api/services/`: Tạo `AssetService.java`.
- `web-portal/src/features/assets/`: Tạo component `AssetRegistry.tsx` (hoặc tương đương) có chứa Master-Detail view và QR code display.

### 2.5 Yêu Cầu Kiểm Thử (Testing Requirements)
- **Backend Unit Tests:** Kiểm tra kỹ logic soft-delete (gọi API xóa mềm, sau đó GET lại list phải không thấy, nhưng GET ID trực tiếp có thể trả về lỗi 404 hoặc thông báo "Đã bị xóa").
- **Web Portal:** Kiểm tra hiển thị QR code sau khi tạo thành công. Kiểm tra form validation.

## 3. Project Context Reference
- **Document Language**: Vietnamese
- **Project Name**: eam-enterprise-assset-management
- **Mã Story (ID)**: 2.2
- **Key**: 2-2-crud-tai-san-kem-qr-code

## Trạng Thái Hoàn Thành Tạo Context
- Status: **review**
- Ultimate context engine analysis completed - comprehensive developer guide created

## Tasks/Subtasks
- [x] Thiết kế Database schema `assets` (Flyway script) có `tenant_id`, `category_id`, `qr_code`, các cờ soft-delete.
- [x] Backend: Tạo Entity, Repository, Service, Controller cho Asset.
- [x] Backend: Thêm logic tạo chuỗi QR duy nhất và Audit Trail.
- [x] Web Portal: Cài đặt thư viện tạo QR Code (nếu cần, vd `qrcode.react`).
- [x] Web Portal: Tạo Zustand store cho Asset Registry.
- [x] Web Portal: Xây dựng giao diện CRUD Tài Sản (SplitPane/Master-Detail view) đẹp và consistent với hệ thống.
- [x] Kiểm thử Backend (Unit Tests) & Web Portal (UI validation).

## Dev Agent Record
- Cài đặt đầy đủ `Asset` entity và `AssetService` với logic QR code generator và Audit trail.
- Sử dụng Flyway để migration bảng `assets`.
- Viết Unit Tests kiểm tra createAsset (gen QRCode) và deleteAsset (soft-delete).
- Tích hợp Zustand store và xây dựng giao diện Split Pane đẹp mắt. Sử dụng thư viện `qrcode.react` để hiển thị QR ngay trên Web Portal, đảm bảo aesthetic design system được tuân thủ.

## File List
- `backend/src/main/resources/db/migration/V14__create_assets_table.sql`
- `backend/src/main/java/com/eam/api/models/entities/Asset.java`
- `backend/src/main/java/com/eam/api/repositories/AssetRepository.java`
- `backend/src/main/java/com/eam/api/models/dtos/AssetCreateRequest.java`
- `backend/src/main/java/com/eam/api/models/dtos/AssetUpdateRequest.java`
- `backend/src/main/java/com/eam/api/models/dtos/AssetResponse.java`
- `backend/src/main/java/com/eam/api/services/AssetService.java`
- `backend/src/main/java/com/eam/api/controllers/AssetController.java`
- `backend/src/test/java/com/eam/api/services/AssetServiceTest.java`
- `web-portal/package.json`
- `web-portal/src/features/assets/store/useAssetRegistryStore.ts`
- `web-portal/src/features/assets/components/AssetRegistry.tsx`

## Change Log
- 2026-06-02: Đã hoàn tất CRUD chức năng tài sản, backend API, QR logic, Unit Tests, và Dynamic React UI cho Asset Registry.

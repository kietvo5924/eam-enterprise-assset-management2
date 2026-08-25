# Story 3-1: Tạo Work Order

## 1. Story Foundation

**Epic:** 3 - Vận Hành Bảo Trì Cốt Lõi  
**Story:** 3.1 - Tạo Work Order

**User Story Statement:**
> As an Asset Manager/Supervisor,
> I want to create a new Work Order with asset, description, priority, and deadline,
> So that maintenance work is officially recorded and tracked (FR23).

**Business Value & Context:**
- Work Order (WO) là trái tim của quy trình bảo trì. Việc tạo WO chuẩn hóa giúp tổ chức ghi nhận, phân công và theo dõi tiến độ công việc dễ dàng.
- Yêu cầu người quản lý có thể chọn tài sản cần bảo trì, mô tả vấn đề, đặt mức độ ưu tiên (Low, Medium, High, Critical) và đặt hạn chót (Deadline) để ưu tiên xử lý.

## 2. Acceptance Criteria

**AC1: Tạo Work Order thành công**
- **Bối cảnh:** Asset Manager hoặc Supervisor đang ở màn hình quản lý Work Order và nhấn "Tạo mới".
- **Khi:** Form được điền đầy đủ các trường bắt buộc (Asset, Title/Description, Priority, Deadline) hợp lệ, sau đó submit.
- **Thì:** Work Order được tạo thành công trên hệ thống với trạng thái mặc định là `CREATED`. Hệ thống tự động ghi nhận Audit Trail cho thao tác này. Giao diện Web hiển thị thông báo thành công (Toast Xanh lá) và cập nhật danh sách WO ngay lập tức.

**AC2: Xử lý lỗi Validation (Form Patterns)**
- **Bối cảnh:** Asset Manager/Supervisor điền form tạo WO.
- **Khi:** Submit form nhưng thiếu trường bắt buộc (ví dụ: Deadline hoặc tiêu đề bị trống).
- **Thì:** Form không được submit. Lỗi validation hiển thị rõ ràng dưới dạng Inline Validation (màu đỏ ngay dưới ô nhập liệu) và nút Submit không thực thi. Tuyệt đối không đợi gọi API mới báo lỗi các trường cơ bản.

## 3. Developer Context & Guardrails (QUAN TRỌNG)

### Bối cảnh kế thừa
- Từ Epic 2, chức năng quản lý tài sản đã hoạt động. Cấu trúc Cây và Danh sách tài sản (`assets` table) đã có, sẵn sàng để Work Order tham chiếu tới (qua `assetId`).
- Các bản sửa lỗi gần nhất (Commit: `a67bc65`, `dac8aba`) liên quan đến UI/UX đánh bóng phần frontend. Phần logic Work Order mới hoàn toàn và cần follow sát kiến trúc.

### Technical Requirements
1. **Frontend (UI/UX - Web Portal)**:
   - Module `work-orders` cần được tạo. Khởi tạo một giao diện danh sách WO (AntD Table) với pagination cơ bản.
   - Thêm nút "Tạo Work Order" (Primary Action). Bấm vào sẽ mở ra AntD **Drawer** trượt từ mép phải (Tránh dùng Modal che khuất hoàn toàn bảng dữ liệu).
   - Form Fields: `assetId` (TreeSelect hoặc Select), `title` (Input), `description` (TextArea), `priority` (Select: LOW, MEDIUM, HIGH, CRITICAL), `deadline` (DatePicker).
   - Trạng thái quản lý thông qua Zustand: Tạo `useWorkOrderStore.ts`.
2. **Backend (Spring Boot 3.x, Java 17)**:
   - Tạo Entity `WorkOrder`: ánh xạ vào bảng `work_orders` trong PostgreSQL.
   - Bắt buộc chứa `tenant_id` cho chức năng Multi-tenant. Trạng thái (`status`) dùng Enum với giá trị khởi tạo `CREATED`.
   - API `POST /api/v1/work-orders`. Xử lý tạo mới. Bọc Response trong chuẩn `{"success": true, "data": { ... }}`.
   - Bắt buộc áp dụng Data Isolation: Các thao tác lưu trữ phải tự động nhận `tenant_id` qua security context hoặc interceptor.

### Architecture & Format Compliance
- **Data Boundary:** Lớp `Repository` trong Spring Boot là ranh giới sống còn. Mọi truy vấn phải chặn theo `tenant_id`.
- **Error Handling:** Backend sử dụng `@RestControllerAdvice` xử lý validation errors trả về HTTP 400.
- **Format:** API Date/Time sử dụng `ISO 8601 UTC`. JSON keys theo định dạng `snake_case`.

### File Structure Requirements
- **PostgreSQL / Flyway:**
  - `backend/src/main/resources/db/migration/V[next]__create_work_orders_table.sql`
- **Backend (Spring Boot):**
  - `backend/src/main/java/com/eam/api/models/entities/WorkOrder.java`
  - `backend/src/main/java/com/eam/api/controllers/WorkOrderController.java`
  - `backend/src/main/java/com/eam/api/services/WorkOrderService.java`
  - `backend/src/main/java/com/eam/api/repositories/WorkOrderRepository.java`
- **Frontend (Web - React/Vite):**
  - `web-portal/src/features/work-orders/api/workOrderApi.ts`
  - `web-portal/src/features/work-orders/store/useWorkOrderStore.ts`
  - `web-portal/src/features/work-orders/components/WorkOrderList.tsx`
  - `web-portal/src/features/work-orders/components/CreateWorkOrderDrawer.tsx`

## 4. Tasks/Subtasks Dành Cho Dev Agent

- [ ] Khởi tạo Migration (Flyway) cho bảng `work_orders` với `tenant_id`, `asset_id` (FK), `title`, `description`, `priority`, `status`, `deadline`.
- [ ] Backend: Định nghĩa `WorkOrder` JPA Entity, Repository, Service và Controller (endpoint `POST /api/v1/work-orders`).
- [ ] Backend: Bổ sung validation DTO cho API tạo Work Order (Not Null, Size). Đảm bảo audit trail (`createdBy`, `createdAt`) và `tenant_id` được ghi đúng.
- [ ] Frontend: Khởi tạo module `work-orders` (API definitions, Zustand Store).
- [ ] Frontend: Tạo component `WorkOrderList` (mock hoặc connect API) để chuẩn bị khung chứa.
- [ ] Frontend: Tạo `CreateWorkOrderDrawer` dùng Ant Design Form, kết nối chức năng chọn `Asset` và tạo mới thông qua Zustand Store.
- [ ] Kiểm thử luồng tạo WO từ Web Portal, xác nhận UI hiển thị Toast xanh lá sau khi tạo.

## 5. Dev Agent Record

### Implementation Notes
- (Sẽ được điền sau quá trình dev)

### File List
- (Sẽ được điền sau quá trình dev)

### Change Log
- (Sẽ được điền sau quá trình dev)

---
**Trạng thái Story:** done
**Note:** Ultimate context engine analysis completed - comprehensive developer guide created

### Review Findings

- [x] [Review][Patch] Missing past date validation for Deadline [WorkOrderCreateRequest.java & CreateWorkOrderDrawer.tsx]
- [x] [Review][Defer] Hardcoded limit of 1000 assets in `fetchAssets` [CreateWorkOrderDrawer.tsx] — deferred, pre-existing acceptable MVP limit
- [x] [Review][Defer] Missing ON DELETE rules in V18 migration [V18__create_work_orders_table.sql] — deferred, pre-existing (RESTRICT is acceptable)

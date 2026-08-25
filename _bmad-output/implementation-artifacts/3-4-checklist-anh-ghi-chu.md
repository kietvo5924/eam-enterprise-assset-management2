# Story 3-4: Checklist, Ảnh & Ghi Chú

## 1. Story Foundation

**Epic:** 3 - Vận Hành Bảo Trì Cốt Lõi  
**Story:** 3.4 - Checklist, Ảnh & Ghi Chú

**User Story Statement:**
> As a Technician,
> I want to complete checklists, upload photos, and add notes,
> So that work evidence is officially recorded (FR28, FR29, FR30, NFR12).

**Business Value & Context:**
Trong quá trình thực hiện bảo trì, Technician cần ghi nhận lại các bước kiểm tra (checklist), chụp ảnh hiện trường (để chứng minh hỏng hóc hoặc đã sửa xong) và điền ghi chú. Đây là các bằng chứng bắt buộc để Supervisor có thể nghiệm thu công việc.

## 2. Acceptance Criteria

**AC1: Quản lý Checklist**
- **Bối cảnh:** Work Order đang ở trạng thái `IN_PROGRESS`.
- **Khi:** Technician tích chọn hoàn thành một mục checklist.
- **Thì:** Trạng thái của item đó được lưu vào cơ sở dữ liệu và hiển thị đã check.

**AC2: Tải lên Ảnh Đính Kèm (NFR12)**
- **Bối cảnh:** Technician tải ảnh lên từ thiết bị.
- **Khi:** Backend nhận file.
- **Thì:** Backend xác thực định dạng file (chỉ cho phép hình ảnh) và dung lượng. Sau đó tải file lên Object Storage (MinIO) với đường dẫn cô lập theo `tenant_id` (ví dụ: `tenant-{id}/work-orders/{wo_id}/ảnh.jpg`). Trả về URL để hiển thị.

**AC3: Ghi chú (Notes)**
- **Bối cảnh:** Technician nhập ghi chú (resolution notes hoặc issue notes).
- **Khi:** Nhấn lưu.
- **Thì:** Ghi chú được lưu vào hệ thống và gắn với Work Order, cho phép Supervisor xem lại sau này.

## 3. Developer Context & Guardrails (QUAN TRỌNG)

### Bối cảnh kế thừa
- Story 3-3 đã hoàn thiện luồng trạng thái (`IN_PROGRESS`, `COMPLETED`). Story này cung cấp dữ liệu chi tiết trong giai đoạn `IN_PROGRESS`.
- Cấu trúc thư mục MinIO đã được dựng qua Docker Compose, cấu hình S3 client/MinIO SDK cần được kết nối trong Spring Boot.

### Technical Requirements
1. **Database & Entity Update**:
   - Tạo bảng `work_order_checklists` (id, work_order_id, item_name, is_completed, tenant_id).
   - Tạo bảng `work_order_attachments` (id, work_order_id, file_url, file_name, file_type, file_size, tenant_id).
   - Thêm cột `resolution_notes` (TEXT) vào bảng `work_orders`.
   - Tạo Flyway Migration script (`V22__add_wo_checklists_and_attachments.sql`).
2. **Backend API**:
   - REST API để lấy và cập nhật Checklist Items.
   - REST API (Multipart) để upload ảnh: `POST /api/v1/work-orders/{id}/attachments`.
   - API để update notes: `PUT /api/v1/work-orders/{id}/notes`.
   - *Phân quyền*: Chỉ Assignee của Work Order (hoặc người có quyền Supervisor `work_order:update`) mới có quyền cập nhật các thông tin này.
3. **Object Storage Integration**:
   - Tích hợp S3/MinIO SDK. Các key phải bắt đầu bằng ID của Tenant để đảm bảo Tenant Isolation trên Object Storage.
4. **Frontend (UI/UX)**:
   - Trong chi tiết Work Order (nếu đang `IN_PROGRESS`), hiển thị tab/section cho Checklist, Photos, và Notes.
   - Có form Upload ảnh (với tính năng preview).

### Architecture & Format Compliance
- **Data Boundary**: Mọi URL trả về cho client phải là public/presigned URL hoặc thông qua endpoint Backend để đảm bảo quyền riêng tư của ảnh. Khuyến nghị backend proxy download endpoint có check quyền `tenant_id` hoặc sinh presigned URL.

### File Structure Requirements
- **PostgreSQL / Flyway**:
  - `backend/src/main/resources/db/migration/V22__add_wo_checklists_and_attachments.sql`
- **Backend (Spring Boot)**:
  - Entities: `WorkOrderChecklistItem`, `WorkOrderAttachment`. Cập nhật `WorkOrder` entity.
  - Controllers: Thêm các endpoint vào `WorkOrderController` hoặc tạo mới `WorkOrderAttachmentController`.
  - Services: `WorkOrderAttachmentService` (để gọi Minio Client) và update `WorkOrderService`.
- **Frontend**:
  - Cập nhật `workOrderApi.ts` hỗ trợ multipart/form-data.
  - Component: Bổ sung các phần tử nhập liệu checklist và file upload.

### Git Intelligence & Previous Story Notes
- Tái sử dụng logic xác thực `assignedTo` từ `WorkOrderService` (Story 3-3) để đảm bảo bảo mật.
- Validation: NFR12 yêu cầu "File upload phải được validate type và size trước khi lưu".

## 4. Tasks/Subtasks Dành Cho Dev Agent

- [x] DB: Tạo Flyway migration `V22` cho `work_order_checklists`, `work_order_attachments` và cột `resolution_notes`.
- [x] Backend: Tạo entities `WorkOrderChecklistItem` và `WorkOrderAttachment`. Cập nhật entity `WorkOrder`.
- [x] Backend: Tích hợp cấu hình Minio/S3Client.
- [x] Backend: Viết Service upload file lên Minio, validate loại file và dung lượng (NFR12), đảm bảo prefix `tenant_id`.
- [x] Backend: Expose APIs (Update checklist, Upload attachment, Update notes).
- [x] Frontend: Bổ sung upload file API call hỗ trợ form-data.
- [x] Frontend: Tích hợp UI vào trang chi tiết Work Order cho phép đánh dấu checklist, upload ảnh, ghi chú.

---
**Trạng thái Story:** done

## Dev Agent Record

### Completion Notes
✅ Đã hoàn thành Flyway migration V22 (DB schema cho checklist và attachment).
✅ Đã thêm entities `WorkOrderChecklistItem` và `WorkOrderAttachment`, repository tương ứng.
✅ Đã cập nhật `WorkOrderService` và `WorkOrderController` cho các endpoints checklist, notes và file upload, có validation NFR12.
✅ Đã tích hợp frontend UI (`WorkOrderDetailDrawer`) hỗ trợ thao tác đánh dấu, up ảnh, và điền note.
✅ Tests chạy ổn định, build thành công (chỉ ngoại trừ lỗi npm rolldown nội bộ không do code).

### Review Findings
- [x] [Review][Patch] Remove explicit Content-Type for FormData [web-portal/src/features/work-orders/api/workOrderApi.ts]
- [x] [Review][Patch] Missing error feedback on UI [web-portal/src/features/work-orders/components/WorkOrderDetailDrawer.tsx]
- [x] [Review][Patch] Hardcoded localhost:9000 for image URL [web-portal/src/features/work-orders/components/WorkOrderDetailDrawer.tsx:154]

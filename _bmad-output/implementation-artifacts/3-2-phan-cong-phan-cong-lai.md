# Story 3-2: Phân Công & Phân Công Lại

## 1. Story Foundation

**Epic:** 3 - Vận Hành Bảo Trì Cốt Lõi  
**Story:** 3.2 - Phân Công & Phân Công Lại

**User Story Statement:**
> As a Supervisor,
> I want to assign and reassign Work Orders to Technicians,
> So that work is routed to the right person to handle (FR24, FR25).

**Business Value & Context:**
- Để công việc bảo trì được xử lý, cần có người thực hiện (Technician). 
- Supervisor cần gán người phụ trách cho các Work Order ở trạng thái `CREATED`.
- Nếu Technician đang bận, Supervisor có thể reassign sang Technician khác. Khi đó nếu Work Order đang `IN_PROGRESS`, cần reset trạng thái về `ASSIGNED` và làm sạch các số liệu thời gian (Metrics) của người cũ để bắt đầu lại.

## 2. Acceptance Criteria

**AC1: Assign Work Order từ trạng thái Created**
- **Bối cảnh:** Work Order đang ở trạng thái `CREATED`.
- **Khi:** Supervisor chọn một Technician và bấm phân công.
- **Thì:** Work Order chuyển trạng thái thành `ASSIGNED`. Ghi nhận người được phân công (`assigned_to`) và thời điểm phân công (`assigned_at`). Audit log tự động ghi nhận thao tác sửa đổi.

**AC2: Reassign Work Order**
- **Bối cảnh:** Work Order đã được phân công.
- **Khi:** Supervisor thay đổi người phụ trách sang một Technician khác.
- **Thì:** 
  - Cập nhật người phụ trách mới.
  - Nếu WO đang ở trạng thái `IN_PROGRESS`, hệ thống tự động đưa status về lại `ASSIGNED` và xóa các thông số đo lường thực thi (ví dụ: `actual_start_time` set lại thành null).
  - Hệ thống phát sinh Event Notification (ví dụ Kafka Event: `work_order.reassigned`) để sau này đẩy push notification cho người cũ và mới (chuẩn bị cho Epic 6).

## 3. Developer Context & Guardrails (QUAN TRỌNG)

### Bối cảnh kế thừa
- Story 3-1 đã dựng entity `WorkOrder` và module `work-orders` ở frontend.
- Cấu trúc hệ thống đã có tenant isolation và RBAC. Cần filter user theo role (`TECHNICIAN` hoặc có các permission tương đương) khi hiển thị danh sách để gán.

### Technical Requirements
1. **Database & Entity Update**:
   - Thêm cột `assigned_to` (UUID) và `assigned_at` (TIMESTAMP) vào bảng `work_orders` (cần tạo thêm migration Flyway, ví dụ `V19__add_assignee_to_work_orders.sql`).
   - Thêm cột `actual_start_time` (TIMESTAMP) để phục vụ cho việc reset metrics ở AC2.
   - Thêm quan hệ `@ManyToOne` tới `User` trong entity `WorkOrder`.
2. **Backend API**:
   - API lấy danh sách Technician: Kiểm tra `UserController` xem có filter theo `role` chưa, nếu chưa thì thêm `GET /api/v1/users?roleName=TECHNICIAN` hoặc trả về toàn bộ list để Client tự filter. (Nên filter ở server).
   - API phân công: `PUT /api/v1/work-orders/{id}/assign` với body `{"assignee_id": "UUID"}`.
   - Xử lý logic tại Service: 
     - Kiểm tra quyền truy cập hợp lệ, Work Order có tồn tại.
     - Kiểm tra user được gán có tồn tại trong cùng `tenant_id` không.
     - Xử lý AC2 (Reset status về `ASSIGNED` và `actual_start_time = null` nếu WO đang `IN_PROGRESS`).
     - Phát event vào Kafka topic `work_order.assigned` hoặc `work_order.reassigned` chứa payload cơ bản (WO ID, old assignee, new assignee, tenant_id).
3. **Frontend (UI/UX)**:
   - Trên bảng `WorkOrderList`, thêm cột "Người phụ trách" (Assignee). 
   - Thêm nút/icon "Phân công" (Assign) hoặc chọn trực tiếp inline. Sử dụng Drawer hoặc Modal đơn giản để Supervisor chọn Technician.
   - Gọi API cập nhật và refresh lại danh sách qua Zustand store.

### Architecture & Format Compliance
- **Data Boundary:** Lớp `Repository` là ranh giới cô lập. Mọi thao tác phải dựa trên Hibernate Filter.
- **Status Constants:** Các trạng thái `CREATED`, `ASSIGNED`, `IN_PROGRESS`, `COMPLETED`, `CANCELED` (Cần dùng Enum ở DB hoặc code Backend).
- **Communication Pattern:** Kafka Publisher cần được inject vào Service, gửi kèm `tenant_id` trong Kafka message header/body.

### File Structure Requirements
- **PostgreSQL / Flyway:**
  - `backend/src/main/resources/db/migration/V19__add_assignee_to_work_orders.sql`
- **Backend (Spring Boot):**
  - Cập nhật `WorkOrder.java` entity.
  - Cập nhật `WorkOrderController.java`, `WorkOrderService.java`.
- **Frontend (Web - React/Vite):**
  - Cập nhật `WorkOrderList.tsx` (Thêm cột, modal chọn assignee).
  - Cập nhật `useWorkOrderStore.ts` (Thêm hàm assign).
  - Cập nhật `workOrderApi.ts`.

## 4. Tasks/Subtasks Dành Cho Dev Agent

- [x] Tạo file migration Flyway (`V19`) để thêm cột `assigned_to`, `assigned_at`, `actual_start_time` vào bảng `work_orders`.
- [x] Backend: Cập nhật JPA Entity `WorkOrder`.
- [x] Backend: Bổ sung API lấy danh sách Users theo Role nếu hệ thống chưa hỗ trợ tìm theo role trực tiếp.
- [x] Backend: Tạo endpoint `PUT /api/v1/work-orders/{id}/assign`. Implement logic thay đổi assignee, reset thời gian nếu trạng thái là `IN_PROGRESS`.
- [x] Backend: Tích hợp Kafka phát tín hiệu khi assign/reassign thành công.
- [x] Frontend: Bổ sung logic fetch technician.
- [x] Frontend: Bổ sung UI phân công (Assign) trên giao diện `WorkOrderList` và cập nhật Zustand store.
- [x] Kiểm thử luồng phân công và phân công lại, check Flyway run mượt.

### Review Findings
- [x] [Review][Patch] No backend validation for assignee role — Changed validation to check for `work_order:update` permission instead of hardcoded `TECHNICIAN` role.
- [x] [Review][Patch] Cannot assign COMPLETED/CANCELED Work Orders [WorkOrderService.java]
- [x] [Review][Patch] Redundant reassignment event [WorkOrderService.java]
- [x] [Review][Patch] Hide/Disable Assign button for completed/canceled WOs [WorkOrderList.tsx]
- [x] [Review][Defer] AssignWorkOrderModal uses size: 100 for technicians [AssignWorkOrderModal.tsx] — deferred, pre-existing limitation to be improved with pagination/search later

## 5. Dev Agent Record

### Implementation Notes
- Added `V19__add_assignee_to_work_orders.sql` for Flyway migration, adding `assigned_to`, `assigned_at`, and `actual_start_time` fields to the `work_orders` table.
- Updated `WorkOrder` entity with `assignedTo` and `actualStartTime` mappings.
- Refactored `UserController` and `UserService` to support filtering users by role name via `GET /api/v1/users?roleName=TECHNICIAN` API.
- Implemented `PUT /api/v1/work-orders/{id}/assign` endpoint to handle assignments, clear metrics if changing from `IN_PROGRESS`, and emit `work_order.assigned` / `work_order.reassigned` Kafka events using Spring Boot's `KafkaTemplate`.
- Developed `AssignWorkOrderModal` in the frontend (React/AntD) and integrated it with `WorkOrderList` logic via Zustand.

### File List
- `backend/src/main/resources/db/migration/V19__add_assignee_to_work_orders.sql` (New)
- `backend/src/main/java/com/eam/api/models/entities/WorkOrder.java` (Modified)
- `backend/src/main/java/com/eam/api/repositories/UserRepository.java` (Modified)
- `backend/src/main/java/com/eam/api/controllers/UserController.java` (Modified)
- `backend/src/main/java/com/eam/api/services/UserService.java` (Modified)
- `backend/src/main/java/com/eam/api/models/dtos/WorkOrderAssignRequest.java` (New)
- `backend/src/main/java/com/eam/api/models/dtos/WorkOrderDto.java` (Modified)
- `backend/src/main/java/com/eam/api/controllers/WorkOrderController.java` (Modified)
- `backend/src/main/java/com/eam/api/services/WorkOrderService.java` (Modified)
- `web-portal/src/features/work-orders/api/workOrderApi.ts` (Modified)
- `web-portal/src/features/work-orders/store/useWorkOrderStore.ts` (Modified)
- `web-portal/src/features/work-orders/components/AssignWorkOrderModal.tsx` (New)
- `web-portal/src/features/work-orders/components/WorkOrderList.tsx` (Modified)

### Change Log
- Added `assigned_to`, `assigned_at`, `actual_start_time` schema structure in backend and APIs.
- Extended user list API to support `roleName` query param for fetching TECHNICIANs.
- Published Kafka events for `work_order.assigned` and `work_order.reassigned`.
- Integrated assignment UI action into the web-portal `WorkOrderList`.

---
**Trạng thái Story:** done
**Note:** Ultimate context engine analysis completed - comprehensive developer guide created

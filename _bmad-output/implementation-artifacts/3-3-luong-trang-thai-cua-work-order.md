# Story 3-3: Luồng Trạng Thái Của Work Order

## 1. Story Foundation

**Epic:** 3 - Vận Hành Bảo Trì Cốt Lõi  
**Story:** 3.3 - Luồng Trạng Thái Của Work Order

**User Story Statement:**
> As a Technician,
> I want to update Work Order statuses following the allowed flow,
> So that work progress is tracked and displayed clearly (FR26, FR27).

**Business Value & Context:**
- Quản lý vòng đời trạng thái của một Work Order là rất quan trọng để đảm bảo tiến độ công việc minh bạch.
- Flow cơ bản: `CREATED` -> `ASSIGNED` -> `IN_PROGRESS` -> `COMPLETED`. Ngoài ra còn trạng thái `CANCELED`.
- Technician cần một API và UI (nút bấm chuyển trạng thái) để tự mình chuyển từ `ASSIGNED` -> `IN_PROGRESS` khi bắt đầu làm, và từ `IN_PROGRESS` -> `COMPLETED` khi đã hoàn thành công việc.

## 2. Acceptance Criteria

**AC1: Chuyển sang In Progress**
- **Bối cảnh:** Work Order đã được assign cho tôi (Technician).
- **Khi:** Tôi click nút bắt đầu làm việc.
- **Thì:** Trạng thái Work Order chuyển thành `IN_PROGRESS`. Hệ thống cập nhật thời điểm `actual_start_time`.

**AC2: Hoàn thành Work Order**
- **Bối cảnh:** Work Order đang ở trạng thái `IN_PROGRESS`.
- **Khi:** Tôi báo cáo hoàn thành.
- **Thì:** Trạng thái chuyển thành `COMPLETED`. Cập nhật thời điểm `completed_at`. Có Audit trail ghi nhận.

**AC3: Validate chuyển trạng thái**
- **Bối cảnh:** Hệ thống nhận một request chuyển đổi trạng thái.
- **Khi:** Logic Backend tiến hành kiểm tra (ví dụ từ `CREATED` nhảy thẳng lên `COMPLETED` hoặc `COMPLETED` về `IN_PROGRESS`).
- **Thì:** Nếu luồng không hợp lệ, từ chối với lỗi HTTP 400 Business Error.

## 3. Developer Context & Guardrails (QUAN TRỌNG)

### Bối cảnh kế thừa
- Story 3-1 và 3-2 đã xây dựng khung Entity `WorkOrder` cùng API lấy danh sách và phân công.
- Trạng thái hiện tại đang được lưu là kiểu `String` mặc định `"CREATED"`.

### Technical Requirements
1. **Database & Entity Update**:
   - Bổ sung cột `completed_at` (TIMESTAMP WITH TIME ZONE) vào bảng `work_orders`.
   - Nên tạo Flyway Migration script (`V21__add_completed_at_to_work_orders.sql`).
   - Cập nhật entity `WorkOrder` ánh xạ với các field mới.
2. **Backend API**:
   - Endpoint: `PUT /api/v1/work-orders/{id}/status` với request body `{"status": "NEW_STATUS"}`.
   - Workflow kiểm tra trạng thái:
     - `CREATED` -> `ASSIGNED` (Story 3-2 đã xử lý).
     - `ASSIGNED` -> `IN_PROGRESS` (Kích hoạt `actual_start_time`).
     - `IN_PROGRESS` -> `COMPLETED` (Kích hoạt `completed_at`).
     - Các trạng thái đang diễn ra đều có thể bị chuyển thành `CANCELED` (bởi Supervisor).
   - *Phân quyền*: Nên sử dụng `@PreAuthorize("hasAnyAuthority('work_order:execute', 'work_order:update')")`.
   - *Ràng buộc Assignment*: Technician chỉ có thể cập nhật Work Order được gán cho chính mình (validate UUID của user hiện tại với `assigned_to`).
3. **Frontend (UI/UX)**:
   - Trên bảng `WorkOrderList`, hoặc Action Menu, thêm các tùy chọn để đổi trạng thái. Ví dụ:
     - Nút "Bắt đầu làm" khi trạng thái là `ASSIGNED`.
     - Nút "Hoàn thành" khi trạng thái là `IN_PROGRESS`.
   - Cập nhật trực quan và Feedback rõ ràng.

### Architecture & Format Compliance
- **Data Boundary**: Mọi query hay update database đều phải qua Repository với Tenant Filter.
- **Error Handling**: Request không hợp lệ (nhảy state sai quy tắc) phải bắn Exception (kế thừa từ `RuntimeException` của base code) và response JSON bọc `{ "success": false }` kèm message.

### File Structure Requirements
- **PostgreSQL / Flyway**:
  - `backend/src/main/resources/db/migration/V21__add_completed_at_to_work_orders.sql`
- **Backend (Spring Boot)**:
  - Cập nhật `WorkOrder.java`.
  - Tạo Enum `WorkOrderStatus` để sử dụng thay cho String constants (cần cẩn thận khi refactor để không hỏng code cũ).
  - DTO: `WorkOrderStatusUpdateRequest`.
  - API: `WorkOrderController`, `WorkOrderService`.
- **Frontend**:
  - `web-portal/src/features/work-orders/api/workOrderApi.ts`
  - Cập nhật store trạng thái.
  - Cập nhật Component list.

### Git Intelligence & Previous Story Notes
- *Bài học từ Story 3-2*: Validation nên kiểm tra theo permission (ví dụ `work_order:execute`) thay vì role hardcode.
- Nếu gửi thông báo, khi WO `COMPLETED` cần phát Kafka event (topic `work_order.completed`) để sau này Notification service xử lý.

## 4. Tasks/Subtasks Dành Cho Dev Agent

- [x] DB: Thêm Flyway migration `V21` cho `completed_at`.
- [x] Backend: Khai báo Enum `WorkOrderStatus` với các giá trị: `CREATED, ASSIGNED, IN_PROGRESS, COMPLETED, CANCELED`. Chỉnh sửa lại các khai báo String thành Enum nếu an toàn.
- [x] Backend: Thêm DTO `WorkOrderStatusUpdateRequest`.
- [x] Backend: Viết endpoint `PUT /api/v1/work-orders/{id}/status`.
- [x] Backend: Implement Service method xử lý trạng thái.
  - Validate state machine flow.
  - Kiểm tra xem user hiện hành có phải là assignee (nếu là kỹ thuật viên) hoặc có quyền hạn phù hợp không.
  - Cập nhật `actualStartTime` nếu status = `IN_PROGRESS`.
  - Cập nhật `completedAt` nếu status = `COMPLETED` và gửi Kafka event.
- [x] Frontend: Bổ sung API call cho update status.
- [x] Frontend: Tích hợp logic nút bấm trạng thái trên UI tuỳ theo role người dùng và trạng thái của Work Order.

**Trạng thái Story:** done
**Note:** Ultimate context engine analysis completed - comprehensive developer guide created

## File List
- `backend/src/main/resources/db/migration/V21__add_completed_at_to_work_orders.sql`
- `backend/src/main/java/com/eam/api/models/enums/WorkOrderStatus.java`
- `backend/src/main/java/com/eam/api/models/dtos/WorkOrderStatusUpdateRequest.java`
- `backend/src/main/java/com/eam/api/models/entities/WorkOrder.java`
- `backend/src/main/java/com/eam/api/models/dtos/WorkOrderDto.java`
- `backend/src/main/java/com/eam/api/controllers/WorkOrderController.java`
- `backend/src/main/java/com/eam/api/services/WorkOrderService.java`
- `backend/src/test/java/com/eam/api/services/WorkOrderServiceTest.java`
- `web-portal/src/features/work-orders/api/workOrderApi.ts`
- `web-portal/src/features/work-orders/store/useWorkOrderStore.ts`
- `web-portal/src/features/work-orders/components/WorkOrderList.tsx`

## Dev Agent Record
- ✅ Added Flyway Migration V21.
- ✅ Extracted `WorkOrderStatus` enum and updated `WorkOrder` entity/DTO.
- ✅ Created `WorkOrderStatusUpdateRequest` and added PUT `/status` endpoint in Controller.
- ✅ Implemented state machine transition logic in `WorkOrderService` handling constraints and actualStartTime / completedAt updates, plus Kafka event publishing.
- ✅ Created `WorkOrderServiceTest` for the new status change logic.
- ✅ Updated `workOrderApi.ts` and `useWorkOrderStore.ts` with update method.
- ✅ Integrated "Start Work" and "Complete" action buttons in `WorkOrderList.tsx` based on the status state machine.

### Review Findings
- [x] [Review][Defer] Missing optimistic locking for WorkOrder state transitions [WorkOrderService.java] — deferred, pre-existing

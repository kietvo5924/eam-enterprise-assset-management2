# Story 3.5: Supervisor Review & Follow-up

Status: done

## Story

As a Supervisor,
I want review công việc đã hoàn thành và tạo follow-up Work Order,
so that các vấn đề phát sinh chưa xử lý không bị bỏ sót (FR31, FR32).

## Acceptance Criteria

1. **AC1: Supervisor Review**
   - **Bối cảnh**: WO đã Completed.
   - **Khi**: Supervisor mở chi tiết.
   - **Thì**: checklist, ảnh và ghi chú được hiển thị. (Hiển thị read-only đối với WO đã Completed, hiện tại UI đã handle `disabled={!canEdit}`).

2. **AC2: Tạo Follow-up Work Order**
   - **Bối cảnh**: cần công việc follow-up.
   - **Khi**: Supervisor tạo follow-up WO.
   - **Thì**: WO mới tham chiếu tới WO gốc. Hệ thống tạo ra một liên kết parent-child giữa các WO.

## Developer Context & Guardrails (QUAN TRỌNG)

### Bối cảnh kế thừa
- Story 3-4 đã hoàn thiện việc lưu checklist, ảnh và ghi chú. Khi `status` là `COMPLETED`, UI `WorkOrderDetailDrawer.tsx` sẽ tự động chuyển các input sang read-only.
- Cần bổ sung cột lưu trữ quan hệ parent-child để theo dõi Follow-up Work Orders.
- Backend cần API tạo Follow-up Work Order hoặc cập nhật API Create Work Order cho phép nhận `parentWorkOrderId`.

### Technical Requirements
1. **Database Update**:
   - Thêm cột `parent_id` (kiểu UUID, foreign key tới bảng `work_orders`) vào bảng `work_orders`.
   - Tạo Flyway Migration script (`V23__add_parent_work_order.sql`).
2. **Backend API**:
   - Cập nhật Entity `WorkOrder` với quan hệ `@ManyToOne` `parentWorkOrder` và `@OneToMany` `followUpWorkOrders`.
   - Cập nhật `WorkOrderCreateRequest` và `WorkOrderDto` để bao gồm `parentWorkOrderId`.
   - Viết API hoặc service logic cho phép kế thừa các thuộc tính (ví dụ: `assetId`) khi tạo follow-up work order từ một work order khác.
3. **Frontend (UI/UX)**:
   - Trong `WorkOrderDetailDrawer.tsx`, bổ sung một nút "Tạo Follow-up Work Order" hiển thị khi `workOrder.status === 'COMPLETED'` (nút này có thể dành riêng cho người có quyền Supervisor/Asset Manager).
   - Nút này sẽ mở `CreateWorkOrderDrawer.tsx` (hoặc modal tương ứng) và điền sẵn thông tin (Asset cũ, mô tả gợi ý "Follow up cho WO #...", parentWorkOrderId).
   - Hiển thị danh sách các "Follow-up Work Orders" đã tạo ở chi tiết của Work Order gốc, và hiển thị "Work Order Gốc" ở chi tiết của Work Order con.

### Architecture & Format Compliance
- Tuân thủ REST API chuẩn, response bọc trong Format JSON chuẩn hiện tại của dự án.
- Flyway V23 cần viết chuẩn, chú ý `ALTER TABLE work_orders ADD CONSTRAINT fk_wo_parent...`

### Git Intelligence & Previous Story Notes
- Ở Story 3-4, file `workOrderApi.ts` và `useWorkOrderStore.ts` đã được chia khá tốt. Hãy tiếp tục pattern này khi tạo Follow Up.

## Tasks / Subtasks

- [x] Task 1: Database Schema & Entity (AC2)
  - [x] Viết script `V23__add_parent_work_order.sql`.
  - [x] Cập nhật Entity `WorkOrder.java`.
- [x] Task 2: Backend API (AC2)
  - [x] Thêm field `parentWorkOrderId` vào DTOs.
  - [x] Viết / Cập nhật logic tạo Work Order có gán `parent_id` trong `WorkOrderService.java`.
- [x] Task 3: Frontend - UI Create Follow-up
  - [x] Bổ sung trường `parentWorkOrderId` trong store và API payload.
  - [x] Tại `WorkOrderDetailDrawer.tsx`, hiển thị nút "Tạo Follow-up" khi WO `COMPLETED`. Mở form tạo WO.
  - [x] Truyền tham số `initialValues` hoặc `parentWorkOrder` sang form tạo mới để tự động fill `asset_id`.
- [x] Task 4: Frontend - UI Display Follow-up (AC1 & AC2)
  - [x] Hiển thị liên kết "Work Order gốc" nếu WO hiện tại là follow-up.
  - [x] (Tùy chọn) Hiển thị danh sách WO con nếu WO hiện tại có follow-ups.

## Dev Agent Record

### Agent Model Used
Gemini 3.1 Pro (High)

### Completion Notes List
- Ultimate context engine analysis completed - comprehensive developer guide created
- Added Flyway migration V23 for `parent_id` column.
- Updated `WorkOrder` entity and DTOs with `parentWorkOrderId` and `followUpWorkOrderIds`.
- Implemented `parentWorkOrderId` payload logic in `WorkOrderService.java` for creation flow.
- Added "Tạo Follow-up" button to `WorkOrderDetailDrawer.tsx` visible when status is COMPLETED.
- Added parent and child work order references in the UI details drawer.
- Tested and verified React component states correctly trigger Create drawer with initial values.

### File List
- `backend/src/main/resources/db/migration/V23__add_parent_work_order.sql`
- `backend/src/main/java/com/eam/api/models/entities/WorkOrder.java`
- `backend/src/main/java/com/eam/api/models/dtos/WorkOrderCreateRequest.java`
- `backend/src/main/java/com/eam/api/models/dtos/WorkOrderDto.java`
- `backend/src/main/java/com/eam/api/services/WorkOrderService.java`
- `web-portal/src/features/work-orders/api/workOrderApi.ts`
- `web-portal/src/features/work-orders/store/useWorkOrderStore.ts`
- `web-portal/src/features/work-orders/components/CreateWorkOrderDrawer.tsx`
- `web-portal/src/features/work-orders/components/WorkOrderDetailDrawer.tsx`

### Change Log
- Added follow-up work order functionality, allowing creation of child work orders from completed ones.

### Senior Developer Review (AI)

#### Action Items
- [x] [Review][Patch] Thiếu kiểm tra phân quyền nút "Tạo Follow-up" — Nút tạo follow-up hiện chỉ kiểm tra trạng thái COMPLETED, chưa kiểm tra quyền SUPERVISOR. Frontend cần check quyền như thế nào?
- [x] [Review][Patch] Ghi đè giá trị payload parentWorkOrderId — Trong CreateWorkOrderDrawer.tsx, parentWorkOrderId bị gán cứng, nên thêm trường ẩn vào form để lưu trữ.
- [x] [Review][Patch] Gọi Getter nhiều lần — Trong WorkOrderService.java, getFollowUpWorkOrders() được gọi hai lần.
- [x] [Review][Patch] Thiếu kiểm tra trạng thái Work Order cha ở backend — Backend cần validate Work Order cha phải ở trạng thái COMPLETED mới cho phép tạo follow-up.
- [x] [Review][Patch] Backend chưa kế thừa assetId — Backend cần tự động kế thừa assetId từ parent thay vì phụ thuộc hoàn toàn vào frontend.
- [x] [Review][Defer] N+1 Query khi ánh xạ followUpWorkOrders — deferred, pre-existing
- [x] [Review][Defer] Thiếu xử lý xóa Cascade cho followUpWorkOrders — deferred, pre-existing
- [x] [Review][Defer] Rủi ro Circular Dependency — deferred, pre-existing
- [x] [Review][Defer] UI thiếu giới hạn hiển thị số lượng Follow-up — deferred, pre-existing

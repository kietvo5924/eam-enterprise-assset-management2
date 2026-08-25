# 5-2-gan-pm-plan-cho-tai-san

## 1. Story Foundation (Epic 5, Story 2)

**User Story:** 
Là Asset Manager, tôi muốn gán PM Plan cho một hoặc nhiều tài sản, để quy tắc bảo trì được áp dụng nhất quán (FR36).

**Mục Tiêu:**
Cho phép Asset Manager liên kết Kế hoạch bảo trì phòng ngừa (PM Plan) đã tạo ở story 5-1 vào danh sách các tài sản (Assets). Lưu lại baseline value (giá trị khởi điểm) lúc gán để làm căn cứ tính toán lần trigger tiếp theo (sẽ dùng ở story 5.3). 

**Tiêu Chí Chấp Nhận (Acceptance Criteria):**
1. **Gán PM Plan cho tài sản:** 
   **Bối cảnh:** PM Plan tồn tại.
   **Khi:** Manager gán plan cho các tài sản được chọn.
   **Thì:** Assignment record được tạo cho từng tài sản.
2. **Khởi tạo Baseline Value:** 
   **Bối cảnh:** Plan đã được gán.
   **Khi:** next trigger được tính toán.
   **Thì:** Baseline value (ngày gán hoặc meter reading lúc gán) được tính từ thời điểm assignment.

---

## 2. Developer Context & Technical Guardrails

### 2.1. Backend Architecture (Spring Boot 3.x & Java 17)
- **Cấu trúc gói:** Đặt tại `com.eam.api.features.maintenance` (nơi đã chứa `PmPlan`).
- **Entity (`PmPlanAssignment`):** Entity ánh xạ nhiều-nhiều giữa `PmPlan` và `Asset`. Cần các trường: `pm_plan_id`, `asset_id`, `tenant_id`, `assigned_at`, `baseline_meter_reading` (nếu trigger là METER).
- **Controller & API:** Cung cấp endpoint POST `/api/v1/pm-plans/{planId}/assign` nhận danh sách `assetId`. 
  - Validate: Tất cả `assetId` và `planId` phải thuộc cùng `tenant_id` của user hiện tại. Tránh lỗi cross-tenant data leak.
- **Tenant Isolation (Bắt Buộc):** Cực kỳ quan trọng. Sử dụng Hibernate `@Filter` như các module khác, và kiểm tra tính hợp lệ của danh sách `assetId` trước khi tạo assignment.

### 2.2. Frontend Architecture (React + Vite, Zustand)
- **Vị trí Component:** Nằm trong thư mục `src/features/maintenance/components` và `src/features/maintenance/api`.
- **UI Design (Ant Design):** 
  - Thêm action "Assign to Assets" (Gán cho tài sản) vào danh sách PM Plans hoặc ở màn hình chi tiết.
  - Mở Modal / Drawer hiển thị Component dạng Transfer, List hoặc Tree/Table có Checkbox để Manager chọn nhiều tài sản.
  - Khi lưu, gọi API gửi danh sách `assetIds`.
- **Quản lý trạng thái:** Cập nhật state (ví dụ thêm hàm trong `usePmPlanStore` hoặc hook tùy chỉnh). Xử lý loading state bằng Skeleton/Spin.

### 2.3. Cấu Trúc Database (PostgreSQL & Flyway)
- **Tệp Migration:** Khởi tạo tệp `.sql` mới trong `db/migration` (VD: `V5.2__create_pm_plan_assignments.sql`).
- **Mô hình Dữ Liệu Tham Khảo:**
```sql
CREATE TABLE pm_plan_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id BIGINT NOT NULL,
    pm_plan_id UUID NOT NULL REFERENCES pm_plans(id) ON DELETE CASCADE,
    asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    assigned_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    baseline_meter_reading NUMERIC, -- Lấy từ asset nếu trigger là METER
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by UUID,
    UNIQUE(tenant_id, pm_plan_id, asset_id)
);
CREATE INDEX idx_pm_plan_assignments_tenant_id ON pm_plan_assignments(tenant_id);
```

### 2.4. Lưu ý Hệ Thống NFR (Non-Functional Requirements)
- **NFR1:** API response time P95 ≤ 500ms. Sử dụng batch insert thay vì loop insert trong Hibernate (nếu cần thiết cho số lượng lớn tài sản).
- **NFR9:** Mọi request được filter theo `tenant_id`.

---

## 3. Previous Story Intelligence
- **Dev notes từ 5-1:** 
  - Endpoint API trả về bọc chuẩn `{ "success": true, "data": ... }`. Đừng quên áp dụng.
  - `triggerType` của PM Plan có các giá trị (TIME, USAGE, METER). Lúc assign, backend có thể phải check trigger type của `PmPlan` để quyết định lấy `baseline_meter_reading` từ `Asset` hay gán null.
  - Frontend sử dụng `verbatimModuleSyntax`, chú ý thêm `type` khi import type.

---

## 4. Status

- **Trạng thái:** done
- **Ghi chú hoàn thành:** Backend entities, endpoints and tests added. Frontend UI updated with Assign modal and store method. All tests pass and build succeeds.

## 5. Tasks/Subtasks

- [x] Task 1: Create Database Migration
  - [x] Create Flyway migration script `V25__create_pm_plan_assignments.sql`
- [x] Task 2: Backend Implementation
  - [x] Create `PmPlanAssignment` entity
  - [x] Create `PmPlanAssignmentRepository`
  - [x] Create DTO `AssignPmPlanRequest`
  - [x] Update `PmPlanService` to handle assignment logic
  - [x] Add endpoint in `PmPlanController` (POST `/api/v1/pm-plans/{planId}/assign`)
  - [x] Add backend unit tests
- [x] Task 3: Frontend Implementation
  - [x] Update `maintenanceApi.ts` with assign API call (in store directly)
  - [x] Update `usePmPlanStore` to handle assign action
  - [x] Create `AssignPmPlanModal` component in `src/features/maintenance/components`
  - [x] Integrate modal into `Maintenance.tsx` or PmPlan list/details view

## 6. Dev Agent Record
### Debug Log
- Adjusted test context since `TENANT_ID` uses String in `TenantContext`.
- Fixed unused `Button` import in `AssignPmPlanModal.tsx` to pass tsc check.

### Completion Notes
- All backend entities (`PmPlanAssignment`), repository, request DTO, and controller endpoints created successfully.
- Tests updated and verified.
- Frontend added a new `AssignPmPlanModal` capable of bulk-assigning multiple assets to a PM plan.

## 7. File List
- `backend/src/main/resources/db/migration/V25__create_pm_plan_assignments.sql`
- `backend/src/main/java/com/eam/api/models/entities/PmPlanAssignment.java`
- `backend/src/main/java/com/eam/api/repositories/PmPlanAssignmentRepository.java`
- `backend/src/main/java/com/eam/api/models/dtos/AssignPmPlanRequest.java`
- `backend/src/main/java/com/eam/api/services/PmPlanService.java`
- `backend/src/main/java/com/eam/api/controllers/PmPlanController.java`
- `backend/src/test/java/com/eam/api/services/PmPlanServiceTest.java`
- `web-portal/src/features/maintenance/store/usePmPlanStore.ts`
- `web-portal/src/features/maintenance/components/AssignPmPlanModal.tsx`
- `web-portal/src/features/maintenance/components/Maintenance.tsx`

## 8. Change Log
- Added logic for Assigning a PM Plan to Assets. Database migration included. Backend tests passing. Frontend form created. (2026-07-01)

### Review Findings

- [x] [Review][Patch] Hardcoded Asset Pagination and Over-fetching — implement debounced search
- [x] [Review][Patch] Missing Baseline Meter Reading — default to 0/null and persist it
- [x] [Review][Patch] Unhandled Transactional Partial Failure — keep atomic but add precise error message
- [x] [Review][Patch] N+1 Query Loop and Missing Batch Insert [PmPlanService.java:342-358]
- [x] [Review][Patch] Silent UI Failure on API Exception [AssignPmPlanModal.tsx:517-533]
- [x] [Review][Patch] Unhandled Duplicate Asset IDs [PmPlanService.java / AssignPmPlanRequest.java]
- [x] [Review][Patch] Potential NullPointerException on Tenant Validation [PmPlanService.java]
- [x] [Review][Patch] Missing Explicit Tenant Isolation `@Filter` [PmPlanAssignment.java]

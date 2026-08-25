# Story 5.4: Calendar View Lịch Bảo Trì

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a Asset Manager,
I want xem lịch bảo trì trên calendar,
so that có thể lập kế hoạch workload hiệu quả (FR38).

## Acceptance Criteria

1. **Bối cảnh** PM Plan và Work Order đã sinh tồn tại,
   **Khi** Manager mở calendar view,
   **Thì** các item theo lịch được hiển thị theo ngày kèm status và ngữ cảnh tài sản.
2. **Bối cảnh** filter được áp dụng,
   **Khi** Manager lọc theo asset/category/status,
   **Thì** calendar cập nhật tương ứng.

## Tasks / Subtasks

- [x] Task 1: Thiết kế & Triển khai API cho Calendar (Backend) (AC: 1, 2)
  - [x] Subtask 1.1: Tạo endpoint GET `/api/v1/work-orders/calendar` hoặc tích hợp vào service Work Order hiện có để trả về danh sách sự kiện bảo trì (bao gồm PM Plans / WOs) theo `startDate` và `endDate` (tương ứng với tháng đang xem trên Calendar).
  - [x] Subtask 1.2: Đảm bảo lọc dữ liệu tuân thủ nghiêm ngặt `tenant_id` ở tầng Repository (BaseTenantEntity).
  - [x] Subtask 1.3: Hỗ trợ các query params để lọc (Ví dụ: `asset_id`, `category`, `status`).

- [x] Task 2: Cập nhật State Management Web (Frontend) (AC: 1, 2)
  - [x] Subtask 2.1: Tạo/Cập nhật Zustand store (ví dụ: `useCalendarStore`) để quản lý các mốc thời gian xem lịch, trạng thái loading (`isLoading`), và dữ liệu WO/PM Plan.
  - [x] Subtask 2.2: Tích hợp gọi API bằng Axios, xử lý các lỗi thường gặp, và phân tách metadata logic.

- [x] Task 3: Xây dựng Giao diện Calendar bằng Ant Design (Frontend) (AC: 1, 2)
  - [x] Subtask 3.1: Xây dựng màn hình Calendar View trong `web-portal/src/features/maintenance` hoặc `work-orders`. Sử dụng `<Calendar />` của Ant Design để hiển thị dữ liệu mật độ cao.
  - [x] Subtask 3.2: Thiết kế thẻ hiển thị sự kiện bảo trì trên từng ô ngày trong Calendar (Màu sắc theo status, label tài sản).
  - [x] Subtask 3.3: Thêm công cụ Filter (lọc theo tài sản, trạng thái) phía trên/hoặc bên cạnh Calendar.
  - [x] Subtask 3.4: Khi click vào sự kiện, hiển thị Drawer/Modal thông tin chi tiết Work Order hoặc PM Plan. Đảm bảo UI Responsive, kế thừa hệ thống Theme/Dark mode hiện tại của `ConfigProvider`.

## Dev Notes

- **Architecture Patterns (Kiến trúc & Ranh giới):**
  - Data Retrieval: Backend TUYỆT ĐỐI áp dụng tenant isolation (`tenant_id`). Các endpoints bắt đầu bằng `/api/v1/`.
  - API Response Format: Backend phải trả về dữ liệu bọc trong wrapper chuẩn: `{ success: true, data: [...], error: null, meta: {...} }`. Date Format phải là chuẩn `ISO 8601 UTC` (`2026-05-15T08:00:00Z`).
  - Frontend State Management: Không mutate Zustand state trực tiếp, bắt buộc dùng hàm Set state như thiết kế.
- **Source Tree Components:**
  - Backend: `WorkOrderController`, `WorkOrderService`, `WorkOrderRepository` (có thể cần viết câu lệnh JPQL riêng để filter range time tối ưu nhất).
  - Web: Components & API thuộc feature group `work-orders` (hoặc `maintenance` - nếu quy định riêng).
- **Error Handling:** 
  - Đảm bảo Backend không bao giờ trả về HTTP 200 cho Response Lỗi.
  - Bắt Exception ở Global Exception Handler (`@RestControllerAdvice`).
- **NFR Compliance:**
  - Rendering tốc độ cao (<2s) khi render Calendar có hàng trăm items. Cần tối ưu query phía server để trả về list WO đã format gọn nhẹ.

### Project Structure Notes

- Web: Đặt file tại `web-portal/src/features/...`
- Đảm bảo tính nhất quán của class names, CSS logic với TailwindCSS + AntD v5.
- Component `<Calendar />` của Ant Design rất tiện nhưng cần truyền hàm `cellRender` chuẩn để custom UI các block trong ngày.

### References

- [Source: docs/_bmad-output/planning-artifacts/prd.md#Epic-5] - Yêu cầu nghiệp vụ FR38.
- [Source: docs/_bmad-output/planning-artifacts/architecture.md#Format-Patterns] - Quy tắc định dạng API response.
- [Source: docs/_bmad-output/planning-artifacts/ux-design-specification.md] - Quy chuẩn UI Ant Design (high-density data).

## Dev Agent Record

### Agent Model Used

Gemini 3.1 Pro (High)

### Debug Log References

### Completion Notes List

### File List

### Review Findings

- [x] [Review][Patch] Critical Tenant Isolation Leak in PM Plan Retrieval [WorkOrderService.java]
- [x] [Review][Patch] Potential Infinite Loop (CPU Exhaustion) in PM Projection [WorkOrderService.java]
- [x] [Review][Patch] Incomplete Projection of PM Plan Frequencies [WorkOrderService.java]
- [x] [Review][Patch] Frontend Race Condition & Double API Fetching [useCalendarStore.ts / MaintenanceCalendar.tsx]
- [x] [Review][Patch] Timezone Offset Shifting [MaintenanceCalendar.tsx]
- [x] [Review][Patch] Drawer Shows Stale Data on API Failure [MaintenanceCalendar.tsx]
- [x] [Review][Patch] Missing Backend Query Parameters for Filtering [WorkOrderController.java / WorkOrderService.java]
- [x] [Review][Patch] Incomplete UI Filter Implementation [MaintenanceCalendar.tsx]
- [x] [Review][Patch] Missing Asset Context on Calendar Event Cards [MaintenanceCalendar.tsx]
- [x] [Review][Patch] Unhandled Error State in Calendar View [MaintenanceCalendar.tsx]
- [x] [Review][Defer] Performance Bottleneck: In-Memory OOM Risk [WorkOrderService.java] — deferred, pre-existing

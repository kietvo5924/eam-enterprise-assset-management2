# Story 1.6: Nhật Ký Audit Hệ Thống

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

Là Tenant Admin,
Tôi muốn xem audit trail cho các thao tác Create/Update/Delete trên dữ liệu nghiệp vụ,
Để đảm bảo khả năng truy vết trách nhiệm (FR4, FR50).

## Acceptance Criteria

1. **Bối cảnh** một thao tác CUD thành công,
   **Khi** transaction commit,
   **Thì** audit log ghi user_id, tenant_id, timestamp, action_type, entity_type và entity_id.
2. **Bối cảnh** Admin mở Audit Log,
   **Khi** áp dụng filter,
   **Thì** kết quả có thể lọc theo user, action, entity và khoảng ngày.

## Developer Context

**STORY FOUNDATION:**
- Story 1.6: Nhật Ký Audit Hệ Thống
- Chức năng: Hệ thống lưu vết (Audit Log) tự động ghi nhận mọi thao tác Create/Update/Delete (CUD) trên dữ liệu nghiệp vụ (entities). Tenant Admin có thể xem và lọc các log này trên Web Portal.
- Mục tiêu: Đảm bảo tính minh bạch và truy vết trách nhiệm trong hoạt động của tenant, tuân thủ FR4 và FR50.

**TECHNICAL REQUIREMENTS:**
- **Backend**:
  - Tạo Entity `AuditLog` lưu các thông tin: `id`, `tenantId`, `userId`, `actionType` (CREATE, UPDATE, DELETE), `entityType`, `entityId`, `timestamp`.
  - Xây dựng cơ chế tự động ghi log: Sử dụng JPA `@EntityListeners` (kết hợp với `TenantContext` và `SecurityContextHolder` để lấy thông tin tenant và user) hoặc Spring AOP (`@Aspect` trên các phương thức service có `@Transactional`). Ưu tiên JPA EntityListeners để đảm bảo bắt được các thay đổi chính xác.
  - API GET `/api/v1/audit-logs`: Hỗ trợ phân trang (pagination) và lọc theo `userId`, `actionType`, `entityType`, và khoảng ngày.
  - Tạo file Flyway migration (VD: `V5__create_audit_logs.sql`) để khởi tạo bảng và thêm indexes trên `tenant_id`, `timestamp` để tối ưu truy vấn.
- **Frontend (Web Portal)**:
  - Tạo trang `AuditLogViewer.tsx` nằm trong thư mục `src/features/audit/components/`.
  - Sử dụng Ant Design `Table` (`size="middle"`) với các cột hiển thị thông tin rõ ràng.
  - Cung cấp bộ lọc với `RangePicker`, `Select` phía trên bảng để tiện tra cứu.
  - Áp dụng cấu trúc UI nhất quán: Bọc trong thẻ Card có border bo góc và đổ shadow mượt.

**ARCHITECTURE COMPLIANCE:**
- **Multi-tenancy & Isolation**: Entity `AuditLog` phải chứa `tenant_id` và áp dụng TenantFilter. Admin chỉ được xem các log thuộc tenant của mình.
- **Performance**: Audit logs chỉ thêm mới (insert-only). Lập chỉ mục (index) là bắt buộc.
- **Event-Driven / Synchronous**: Quá trình ghi audit log không được cản trở hoặc làm vỡ logic chính. JPA EntityListeners chạy synchronous trong cùng transaction là đủ cho MVP, nhưng cần handle lỗi để không văng lỗi lên thao tác của người dùng nếu có thể.

**PREVIOUS STORY INTELLIGENCE (Từ 1.5):**
- Authorization đã hoạt động. Nhớ bọc API Audit bằng quyền hợp lệ, ví dụ `@PreAuthorize("hasAuthority('TENANT_ADMIN')")` hoặc quyền chuyên biệt.
- Cấu trúc thư mục theo Feature-based ở Frontend và 3-Layer ở Backend.

**GIT INTELLIGENCE SUMMARY:**
- Dự án sử dụng TailwindCSS kết hợp Ant Design. Đảm bảo form filter và bảng dùng các design tokens đã định nghĩa.

**LATEST TECH INFORMATION:**
- Sử dụng Spring Data JPA `@EntityListeners(AuditingEntityListener.class)` mặc định chỉ hỗ trợ `createdDate`, `lastModifiedBy`. Để bắt cụ thể sự kiện INSERT/UPDATE/DELETE sinh ra row audit riêng biệt, cần tự viết một Listener tùy chỉnh (ví dụ `AuditTrailListener`) gắn vào Entity bằng `@EntityListeners(AuditTrailListener.class)`.

**FILE STRUCTURE REQUIREMENTS:**
- `backend/src/main/resources/db/migration/V5__create_audit_logs.sql`
- `backend/src/main/java/com/eam/api/models/entities/AuditLog.java`
- `backend/src/main/java/com/eam/api/models/enums/ActionType.java`
- `backend/src/main/java/com/eam/api/repositories/AuditLogRepository.java`
- `backend/src/main/java/com/eam/api/services/AuditLogService.java`
- `backend/src/main/java/com/eam/api/controllers/AuditLogController.java`
- `backend/src/main/java/com/eam/api/core/audit/AuditTrailListener.java`
- `web-portal/src/features/audit/components/AuditLogViewer.tsx`
- `web-portal/src/App.tsx` (Bổ sung route)

## Tasks / Subtasks

- [x] Task 1: Cấu trúc Database và Entity
  - [x] Viết file Flyway tạo bảng `audit_logs`.
  - [x] Khai báo Entity `AuditLog` và enum `ActionType`.
- [x] Task 2: Core Audit Listener
  - [x] Xây dựng `AuditTrailListener` bắt các hook `@PostPersist`, `@PostUpdate`, `@PostRemove`.
  - [x] Extract `userId` từ Security context và `tenantId` từ Tenant context. Bắn một event nội bộ hoặc lưu trực tiếp qua bean tiêm vào listener (cẩn thận lỗi inject bean trong entity listener).
  - [x] Áp dụng listener này lên một số entity quan trọng như `User`, `Organization` để test.
- [x] Task 3: API truy vấn Audit Logs
  - [x] Xây dựng Repository với support Specification hoặc custom query.
  - [x] Cung cấp API GET `/api/v1/audit-logs` hỗ trợ lọc và phân trang, bọc kết quả theo chuẩn `ApiResponse`.
- [x] Task 4: Web Portal UI
  - [x] Thêm route cho Audit Logs trong Layout chính.
  - [x] Thiết kế màn hình `AuditLogViewer` tích hợp Table và Form filter theo chuẩn UX Design (High Density Hybrid).
- [x] Task 5: Testing
  - [x] Thực hiện một thao tác chỉnh sửa User/Org từ giao diện.
  - [x] Mở trang Audit Log và xác minh log được ghi đúng thông tin người thực hiện, thời gian, và loại thao tác.

### Review Findings

- [x] [Review][Patch] Phân quyền cho AuditLogController — Controller đã được cập nhật sử dụng `@PreAuthorize("hasAuthority('audit_logs:read')")` và permission được thêm vào DB qua migration V6.
- [x] [Review][Defer] Kiến trúc AuditTrailListener — Listener đang sử dụng `static ApplicationContext` để lấy event publisher. Đây là cách giải quyết tạm thời cho MVP. Về lâu dài nên config `SpringBeanContainer` cho Hibernate để có thể `@Autowired` trực tiếp. [AuditTrailListener.java:16] — deferred, pre-existing
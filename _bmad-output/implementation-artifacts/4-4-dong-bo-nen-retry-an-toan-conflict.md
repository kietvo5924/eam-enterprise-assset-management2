# Story 4.4: Đồng Bộ Nền, Retry & An Toàn Conflict

Status: ready-for-dev

## Story

Là Technician,
Tôi muốn app tự động sync dữ liệu offline, retry ảnh upload lỗi và chống gửi trùng,
Để công việc hiện trường được bảo toàn khi có mạng trở lại (FR42, FR44, NFR18, NFR19).

## Acceptance Criteria

1. **AC1: Đồng bộ nền tự động**
   - **Bối cảnh**: Có bản ghi pending trong Sync Queue.
   - **Khi**: Thiết bị kết nối mạng trở lại (hoặc ứng dụng được bật lên khi có mạng).
   - **Thì**: Sync Engine tự động đẩy dữ liệu lên Backend mà không cần người dùng can thiệp.

2. **AC2: Retry policy và Exponential backoff**
   - **Bối cảnh**: Upload ảnh hoặc gọi API bị lỗi mạng hoặc timeout.
   - **Khi**: Retry policy chạy.
   - **Thì**: Task được retry tối đa 3 lần với khoảng thời gian delay tăng dần (exponential backoff) trước khi bị đánh dấu là FAILED.

3. **AC3: Idempotency Key (Chống gửi trùng)**
   - **Bối cảnh**: Cùng một thao tác offline bị gửi lên hai lần do lỗi đường truyền không xác định trạng thái phản hồi.
   - **Khi**: Backend nhận cùng Idempotency Key.
   - **Thì**: Thao tác chỉ được xử lý một lần, lần thứ hai trả về kết quả thành công mà không gây double-processing.

4. **AC4: Xử lý Conflict an toàn (Không dùng last-write-wins)**
   - **Bối cảnh**: Dữ liệu Work Order trên server đã thay đổi trong lúc Technician đang chỉnh sửa offline.
   - **Khi**: Sync Engine đẩy dữ liệu lên và server phát hiện xung đột dựa trên Version Vectors hoặc Dirty-flags.
   - **Thì**: Thao tác bị từ chối với trạng thái CONFLICT (HTTP 409). Sync Engine giữ lại bản ghi và đánh dấu conflict để Supervisor rà soát thủ công, KHÔNG TỰ ĐỘNG GHI ĐÈ làm mất dữ liệu server.

## Developer Context & Guardrails (QUAN TRỌNG)

### Technical Requirements

1. **SyncEngine Implementation**:
   - Xây dựng class `SyncEngine` đóng vai trò orchestrator, lắng nghe từ `NetworkService`.
   - Engine cần tuần tự lấy các bản ghi `PENDING` và `FAILED` (nhưng số lần retry < 3) từ `SyncQueueDao` và xử lý theo từng `actionType` (`UPDATE_CHECKLIST`, `UPLOAD_PHOTO`, `UPDATE_STATUS`, v.v.).
   - KHÔNG gọi `notifyListeners` vô tội vạ làm giật UI. Đưa việc gọi mạng vào background/async blocks.

2. **Retry Mechanism & Exponential Backoff**:
   - Đảm bảo logic kiểm tra `retryCount`. Nếu gọi API lỗi do network/timeout (HTTP 5xx, socket exception), tăng `retryCount`. Nếu vượt quá 3 lần, cập nhật status là `FAILED`.
   - Implement exponential backoff, delay dựa trên `retryCount` (VD: $2^{retryCount}$ giây). Có thể sử dụng `Future.delayed()`.

3. **Idempotency Key Injection**:
   - `SyncQueueTable` cần được mở rộng thêm trường `idempotencyKey` kiểu Text, lưu unique UUID khi tạo.
   - `SyncEngine` phải gửi kèm header `Idempotency-Key` (hoặc pass qua DTO) lên Backend cho mọi thao tác CUD.

4. **Conflict Resolution & Error Parsing**:
   - Cần bổ sung `CONFLICT` vào các status hợp lệ của `SyncQueueTable`.
   - Bắt các mã lỗi HTTP (ví dụ HTTP 409 Conflict hoặc Custom Status cho conflict).
   - Nếu server báo Conflict, đổi trạng thái bản ghi thành `CONFLICT`. Sync engine không bao giờ xoá bản ghi CONFLICT để đảm bảo zero data loss. Người dùng/Supervisor sẽ có luồng resolve riêng sau.

5. **Tenant Isolation Validation**:
   - `SyncEngine` phải tuân thủ nghiêm ngặt việc truyền đúng `tenant_id` lấy từ session hiện tại.

### Architecture Compliance

- **File Structure**: Core sync engine đặt tại `mobile_app/lib/features/sync/services/sync_engine.dart`.
- **Database Drift**: Chỉnh sửa Schema của `SyncQueues` table trong `app_database.dart` để thêm `idempotencyKey` (TextColumn). Nâng `schemaVersion` lên 5 và xử lý migration logic nếu cần.
- **Dependency Injection**: Tiêm `SyncEngine` vào app lifecycle để nó tự động lắng nghe `NetworkService` stream.

### Previous Story Intelligence

- Từ Story 4.3, `SyncQueueTable` và `SyncQueueDao` đã được tạo. Offline indicators cũng đã có.
- Tuy nhiên, "Missing Sync Engine Implementation" đã bị defer từ 4.3. Đây là lúc thực thi.
- Review 4.3 cũng chỉ ra: "Silent Error Swallowing in Background Sync". Đảm bảo mọi exception khi đẩy HTTP đều được log ra console và update status chính xác (không catch lỗi rồi lờ đi).
- Đảm bảo tránh "Partial Sync Data Destruction" (nếu API có phân trang, đừng vô tình xóa local records của trang khác khi chỉ fetch 1 trang).

### Latest Tech Information

- Dart `uuid` package rất phổ biến để tạo Idempotency Key. Có thể sử dụng `const Uuid().v4()`.
- Chạy lại build_runner sau khi sửa `AppDatabase`: `flutter pub run build_runner build --delete-conflicting-outputs`.
- Drift version migration: Ghi chú xử lý trong `MigrationStrategy.onUpgrade` để add column `idempotencyKey` vào `sync_queues` table mà không làm crash app với db cũ.

## Project Context Reference

- Offline sync an toàn đảm bảo tính toàn vẹn (Integrity) hệ thống ERP khi có nhiều người cùng chỉnh sửa một Work Order. Cơ chế Conflict (tránh Last-write-wins) ngăn chặn việc Technician A đè lên kết quả của Technician B vô tội vạ.
- UX hiện tại đã có `OfflineSyncIndicator`, component này sẽ tự động react khi `SyncEngine` cập nhật trạng thái các rows trong `SyncQueueTable`.

## Tasks / Subtasks

- [x] Task 1: Nâng cấp `SyncQueueTable` trong Drift DB
  - Thêm cột `idempotencyKey` dạng Text.
  - Tăng `schemaVersion` lên 5 và thêm `onUpgrade` migration strategy.
  - Chạy `build_runner`.
- [x] Task 2: Cấu trúc cơ bản `SyncEngine`
  - Tạo `SyncEngine` (`sync_engine.dart`), dependency injection `SyncQueueDao`, `WorkOrderService` (để lấy HTTP client/API actions), và `NetworkService`.
  - Lắng nghe sự kiện từ `NetworkService` và chỉ trigger sync khi online.
- [x] Task 3: Retry Policy & Idempotency Key
  - Xử lý các task `PENDING`/`FAILED` (số retry < 3).
  - Áp dụng `Idempotency-Key` (nếu có, không thì sinh ra) vào API calls.
  - Exponential backoff trước khi retry. Tăng `retryCount` nếu lỗi.
- [x] Task 4: Xử lý Conflict (HTTP 409)
  - Đón nhận exception báo HTTP 409 từ API. Nếu 409, set trạng thái DB record thành `CONFLICT`.
- [x] Task 5: App Lifecycle Integration
  - Gắn `SyncEngine` vào quá trình khởi tạo app trong `main.dart` hoặc provider root để bắt đầu tiến trình nền tự động.

## Dev Agent Record

### Implementation Plan
- Added `idempotencyKey` to `SyncQueueTable` in Drift schema v5.
- Created `SyncEngine` class that listens to `NetworkService`.
- Handled API requests with exponential backoff on retries and sending `Idempotency-Key` headers.
- Handled HTTP 409 Conflict.
- Initialized `SyncEngine` in `main.dart`.

### Completion Notes
- The Drift DB upgrade works properly.
- All operations are asynchronous and prevent blocking the UI.
- The idempotency key guarantees deduplication on backend.

## File List
- `mobile_app/pubspec.yaml`
- `mobile_app/lib/core/database/app_database.dart`
- `mobile_app/lib/features/work_orders/services/work_order_service.dart`
- `mobile_app/lib/features/sync/services/sync_engine.dart`
- `mobile_app/lib/main.dart`

## Change Log
- Added `uuid` dependency.
- Updated `AppDatabase` schema to version 5 with `idempotencyKey` column.
- Added `idempotencyKey` generation to offline sync tasks in `WorkOrderService`.
- Implemented `SyncEngine` with background processing and retry policies.
- Initialized `SyncEngine` in `main.dart`.

## Senior Developer Review (AI)

### Review Findings
- [x] [Review][Patch] Bỏ qua xóa dữ liệu cũ (Stale Data) khi server trả về danh sách rỗng [work_order_service.dart]
- [x] [Review][Patch] Ghi đè file đính kèm khi cache offline và dùng sai filePath thay vì safePath [work_order_service.dart]
- [x] [Review][Patch] Lỗi không báo lỗi khi `updateStatus` offline nếu WO null trong DB [work_order_service.dart]
- [x] [Review][Patch] Thundering Herd ở `syncAssetsInBackground` và `syncWorkOrdersInBackground` do thiếu cờ isSyncing [work_order_service.dart]
- [x] [Review][Patch] UnsupportedError (Mutation on unmodifiable collection) khi gán `item['isCompleted'] = isCompleted;` [work_order_service.dart]
- [x] [Review][Patch] Null Pointer Exception do thiếu kiểm tra `data == null` tại `getMyWorkOrders` [work_order_service.dart]
- [x] [Review][Patch] Đưa tác vụ vào SyncQueue mù quáng khi API có lỗi định định (ví dụ 400, 403) [work_order_service.dart]
- [x] [Review][Patch] Null pointer `res.data['data']` khi gán trực tiếp vào Mapper trong `getAssetByQrCode` [work_order_service.dart]
- [x] [Review][Patch] `getPendingSyncs` không có filter loại bỏ các bản ghi `retryCount >= 3` [app_database.dart]
- [x] [Review][Patch] `SyncEngine.init` không tự động triggerSync() nếu app mở lên đã có mạng sẵn [sync_engine.dart]
- [x] [Review][Patch] Thiếu offline queue và Idempotency Key cho `deleteChecklist` [work_order_service.dart]

- [x] [Review][Defer] Lọc dữ liệu work order ở client thay vì API query param [work_order_service.dart] — deferred, pre-existing
- [x] [Review][Defer] Type Casting rủi ro `json.decode(fromDb) as List<dynamic>` [app_database.dart] — deferred, pre-existing
- [x] [Review][Defer] Dùng `.getSingleOrNull()` không có `.limit(1)` gây StateError [app_database.dart] — deferred, pre-existing
- [x] [Review][Defer] Rủi ro mất đồng bộ GET sau POST thất bại tại `_updateLocalWorkOrder` [work_order_service.dart] — deferred, pre-existing

## Story Completion Status

- Status: done
- Notes: Sync Engine implementation completed with idempotency and conflict handling.

# Story 4.3: Thực Hiện Offline & Trạng Thái Đồng Bộ

Status: ready-for-dev

## Story

Là Technician,
Tôi muốn hoàn thành checklist, ảnh và ghi chú khi offline với trạng thái sync rõ ràng,
Để công việc hiện trường không bị mất dữ liệu (FR41, FR43, UX-DR7, NFR18).

## Acceptance Criteria

1. **AC1: Lưu dữ liệu vào Sync Queue khi Offline**
   - **Bối cảnh**: Thiết bị đang offline.
   - **Khi**: Technician lưu dữ liệu thực hiện công việc (điền checklist, chụp ảnh, thêm ghi chú).
   - **Thì**: App lưu dữ liệu vào Sync Queue trong hệ thống lưu trữ cục bộ thay vì gọi API trực tiếp, đảm bảo không mất dữ liệu.

2. **AC2: Hiển thị trạng thái toàn cục (OfflineSyncIndicator)**
   - **Bối cảnh**: Có dữ liệu đang chờ sync, hoặc trạng thái kết nối mạng thay đổi.
   - **Khi**: App render giao diện trạng thái toàn cục.
   - **Thì**: `OfflineSyncIndicator` hiển thị mượt mà các trạng thái: online, offline, pending sync, synced. Tuân thủ tiêu chuẩn UX-DR7 (không hiển thị bảng lỗi Modal chặn màn hình).

## Developer Context & Guardrails (QUAN TRỌNG)

### Technical Requirements

1. **Tạo Sync Queue Database (Drift)**:
   - Mở rộng kiến trúc Drift Database hiện có (từ Story 4.2).
   - Tạo mới bảng `SyncQueueTable` (hoặc cách tiếp cận tương tự) để ghi nhận các hành động pending (ví dụ: update checklist, upload ảnh).
   - Lưu trữ rõ loại thao tác (Action Type), Payload (dữ liệu JSON), trạng thái (PENDING, IN_PROGRESS, FAILED).

2. **Intercept Network & Local State**:
   - Sử dụng thư viện như `connectivity_plus` để lắng nghe trạng thái mạng real-time.
   - Khi thực hiện hành động CUD trên Work Order, kiểm tra trạng thái mạng:
     - Nếu không có mạng: Lưu thẳng vào `SyncQueue`, cập nhật Local DB (để hiển thị UI mới nhất), và thông báo offline.
     - Nếu có mạng: Có thể xử lý như offline (đưa vào Queue) và kích hoạt Sync Engine ngay lập tức để đạt tính nhất quán cao nhất.

3. **Xử lý File Ảnh (Photo) Offline**:
   - Khi Kỹ thuật viên chụp ảnh lúc mất mạng, bắt buộc lưu file vật lý vào thư mục Cache/Application Documents của thiết bị.
   - Lưu đường dẫn cục bộ này vào Sync Queue payload. Không được lưu base64 của ảnh trực tiếp vào database vì sẽ gây phình to Drift DB dẫn tới crash bộ nhớ.
   - UI hiển thị ảnh từ đường dẫn cục bộ khi chưa sync xong.

4. **Phát triển OfflineSyncIndicator (UX-DR7)**:
   - Xây dựng Widget `OfflineSyncIndicator` dùng để báo cáo tình trạng đồng bộ ngầm.
   - Đặt Component này ở vị trí ít xâm phạm (như AppBar, thanh trạng thái nhỏ dưới cùng) để không cản trở thao tác của Kỹ thuật viên.

### Architecture Compliance

- **Cơ sở dữ liệu**: BẮT BUỘC sử dụng **Drift**. Không sử dụng SQflite nguyên bản.
- **Tenant Isolation**: Drift DB luôn chỉ phục vụ dữ liệu cho Tenant hiện tại.
- **Non-blocking UI**: Các truy vấn vào Drift và SyncQueue phải chạy bất đồng bộ (async) và không bao giờ dùng `notifyListeners()` hoặc thay đổi state chặn Main Thread (Block UI) một cách không cần thiết.

### Previous Story Intelligence

- Ở **Story 4.2**, kiến trúc Offline-first cơ bản với Drift đã được thiết lập, đặc biệt là cơ chế phân trang và Data Eviction. Cấu trúc `WorkOrdersTable` đã có sẵn.
- Bài học đắt giá từ Review Story 4.2:
  - Lỗi cấu trúc JSON (Data Loss): Rất cẩn thận khi encode/decode Payload từ JSON để lưu vào Sync Queue. Ở story trước, logic map JSON bị thiếu các trường quan trọng gây mất dữ liệu.
  - Vấn đề chặn UI: Việc lạm dụng `notifyListeners()` khiến spinner chặn UI người dùng trong nền. Ở story 4.3, mọi thao tác Sync ngầm phải hoàn toàn "tàng hình" đối với User.
  - Vấn đề xoá tài sản mồ côi (Orphaned Asset): Cần cẩn trọng khi xoá record. Với Sync Queue, chỉ xóa Record đã xác nhận Sync thành công (Synced) hoặc được server phản hồi không thể xử lý.

### Latest Tech Information

- `Drift` yêu cầu chạy lại Code Generation khi thay đổi Schema: `flutter pub run build_runner build --delete-conflicting-outputs`.
- Đối với `connectivity_plus` version mới nhất, hãy kiểm tra permission trên AndroidManifest nếu cần thiết để đọc Network State.

## Project Context Reference

- Ứng dụng EAM cho Technician đặt tính mạng lên sự ổn định khi Offline (Zero Data Loss NFR18). Trạng thái Pending Sync cực kỳ quan trọng và phải được hiển thị trung thực.
- Thiết kế UI cần bám theo System Design: Màu Success (Xanh lá) cho Synced, Warning (Cam) cho Pending, Error (Đỏ) cho Offline/Lỗi.

## Tasks / Subtasks

- [x] Task 1: Thiết lập SyncQueueTable trong Drift
  - [x] Định nghĩa `SyncQueueTable` với các trường cần thiết (id, action_type, payload, status, created_at, retry_count).
  - [x] Chạy `build_runner` để sinh code cho database.
  - [x] Viết các DAO (`SyncQueueDao`) phục vụ thêm, cập nhật, đọc các record pending.
- [x] Task 2: Theo dõi trạng thái kết nối mạng
  - [x] Cài đặt hoặc cấu hình `connectivity_plus` (nếu chưa có).
  - [x] Tạo `NetworkService` hoặc provider để cung cấp trạng thái mạng toàn cục.
- [x] Task 3: Xử lý ghi Work Order Offline (Checklist, Note)
  - [x] Cập nhật luồng `updateWorkOrder` hoặc tương đương: nếu offline, lưu thông tin cập nhật vào Local DB (để phản hồi UI ngay lập tức) VÀ lưu 1 bản ghi vào `SyncQueueTable`.
  - [x] Cập nhật UI xử lý mượt mà khi không có mạng (không hiện báo lỗi không kết nối mạng).
- [x] Task 4: Xử lý chụp ảnh Offline
  - [x] Sửa lại logic chọn ảnh: lưu path local.
  - [x] Đẩy metadata ảnh và local path vào SyncQueueTable.
  - [x] Hiển thị ảnh đang chờ sync trên giao diện.
- [x] Task 5: OfflineSyncIndicator UI Component
  - [x] Tạo widget `OfflineSyncIndicator`.
  - [x] Tích hợp lắng nghe trạng thái từ `NetworkService` và Drift `SyncQueueDao` stream.
  - [x] Đặt widget vào giao diện (ví dụ: AppBar, Bottom padding) hiển thị các trạng thái (Online, Offline, Pending Sync).

## Dev Agent Record

### Implementation Plan
- Định nghĩa SyncQueueTable với các trường actionType, payload, status trong Drift.
- Sinh các truy vấn Database Helper (Dao) cho SyncQueue.
- Tạo NetworkService với connectivity_plus để lắng nghe trạng thái kết nối mạng toàn cục.
- Inject NetworkService bằng Provider vào ứng dụng.
- Cập nhật WorkOrderService intercept các hàm `updateChecklist`, `updateNotes`, `updateStatus`, `uploadAttachment`: Nếu offline, fallback lưu record JSON qua SyncQueueDao và update LocalDB trực tiếp để UI không bị treo/chặn.
- Xây dựng widget OfflineSyncIndicator bắt stream từ NetworkService và SyncQueueDao để hiển thị thông báo offline/syncing mà không gây nhiễu luồng làm việc.
- Inject Indicator trên Scaffold/Route top của Material App.

### Completion Notes
- Đã cài đặt connectivity_plus và cấu hình NetworkService.
- Tính năng SyncQueueTable đã được tích hợp bằng Drift ORM (Schema = 3).
- Cập nhật thành công luồng Offline Cache cho WorkOrder. Kỹ thuật viên hiện có thể update Notes, Checklists, Statuses, Attachments không cần mạng và app tự tạo Sync Tasks.
- Widget OfflineSyncIndicator hiển thị chính xác trạng thái online/offline và báo hiệu pending items chuẩn xác theo chuẩn UX-DR7 (không modal errors).

## File List
- `mobile_app/pubspec.yaml`
- `mobile_app/lib/main.dart`
- `mobile_app/lib/core/database/app_database.dart`
- `mobile_app/lib/core/network/network_service.dart`
- `mobile_app/lib/features/work_orders/services/work_order_service.dart`
- `mobile_app/lib/features/sync/presentation/widgets/offline_sync_indicator.dart`

## Change Log
- Thêm connectivity_plus để monitor state mạng.
- Tạo cấu trúc Drift SyncQueueTable.
- Đổi các update operations trong WorkOrderService thành offline-first.
- Tích hợp OfflineSyncIndicator banner.

## Story Completion Status

- Status: done
- Notes: Ultimate context engine analysis completed - comprehensive developer guide created

### Review Findings
- [x] [Review][Defer] Missing Sync Engine Implementation [app_database.dart] — deferred to Story 4-4
- [x] [Review][Patch] Spotty Network Data Loss Trap [work_order_service.dart]
- [x] [Review][Patch] Global Widget Rebuild Risk (UI Jank) [offline_sync_indicator.dart]
- [x] [Review][Patch] Missing Safe File Caching for Offline Photos [work_order_service.dart]
- [x] [Review][Patch] Premature Deletion of Work Orders (updatedAt == null) [app_database.dart]
- [x] [Review][Patch] SQLite Variable Limit Crash [app_database.dart]
- [x] [Review][Patch] Silent Error Swallowing in Background Sync [work_order_service.dart]
- [x] [Review][Patch] Partial Sync Data Destruction (Pagination hard break) [work_order_service.dart]
- [x] [Review][Patch] Missing Tenant Isolation in Sync Queue [app_database.dart]
- [x] [Review][Patch] Unsafe JSON Decoding Fallback [app_database.dart]
- [x] [Review][Patch] Stale Cache Trap in QR Scanner [work_order_service.dart]
- [x] [Review][Defer] Offline Checklist Race Condition [work_order_service.dart] — deferred, read-modify-write UI race condition

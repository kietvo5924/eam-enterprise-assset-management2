# Story 4.2: Cache Dữ Liệu Cục Bộ

Status: ready-for-dev

## Story

Là Technician,
Tôi muốn Work Order được giao và tài sản liên quan được cache cục bộ,
Để có thể làm việc khi không có kết nối mạng (FR40).

## Acceptance Criteria

1. **AC1: Pagination / Chunking cho Initial Sync**
   - **Bối cảnh**: Ứng dụng cần tải danh mục tài sản lớn lần đầu (First-load).
   - **Khi**: Thực hiện initial sync qua mạng yếu.
   - **Thì**: Dữ liệu phải được phân trang (Pagination/Chunking) để tránh quá tải bộ nhớ và timeout.

2. **AC2: Lưu trữ Drift Database cho thiết bị online**
   - **Bối cảnh**: Thiết bị đang online.
   - **Khi**: Dữ liệu được giao được tải về.
   - **Thì**: Work Order và tài sản liên quan được lưu trong Drift local database.

3. **AC3: Data Eviction (TTL) & Quota**
   - **Bối cảnh**: Dữ liệu lưu trữ local (Drift DB) ngày càng tăng.
   - **Khi**: Chạm giới hạn quota hoặc các Work Order đã đóng quá 7 ngày.
   - **Thì**: Chính sách Data Eviction (TTL) tự động xóa dữ liệu cũ để giải phóng dung lượng thiết bị.

4. **AC4: Chế độ Offline truy xuất dữ liệu cache**
   - **Bối cảnh**: Thiết bị đang offline.
   - **Khi**: Technician mở công việc được giao.
   - **Thì**: Dữ liệu đã cache vẫn khả dụng để đọc và hiển thị giao diện bình thường.

## Developer Context & Guardrails (QUAN TRỌNG)

### Technical Requirements

1. **Khởi tạo Database và Entities (Drift)**:
   - Cài đặt thư viện `drift`, `drift_dev`, `sqlite3_flutter_libs` vào thư mục `mobile_app`.
   - Tạo cấu hình Drift Database tại `mobile_app/lib/core/database/`.
   - Tạo các bảng `WorkOrdersTable`, `AssetsTable` ánh xạ các Model tương ứng, chú ý chỉ lưu các trường cần thiết phục vụ cho quá trình làm việc ngoại tuyến. 

2. **Logic Fetch và Cache (SyncManager/Service)**:
   - Thay đổi các hàm lấy danh sách Work Order ở `WorkOrderService` (như `getMobileHomeWorkOrders()`) để chúng ưu tiên:
     - Trả về dữ liệu từ Stream/Query của Drift DB cho UI hiển thị ngay lập tức.
     - Background thực hiện API Fetch từ Server.
     - Cập nhật dữ liệu từ Server xuống Drift DB (insert/update).
   - Xử lý tương tự đối với việc lấy Asset details khi tải Work Order.

3. **Chính sách Eviction (Xóa dữ liệu cũ)**:
   - Viết query Drift thực hiện xóa các `WorkOrder` đã sang trạng thái `COMPLETED` cách đây hơn 7 ngày.
   - Viết query dọn dẹp các `Asset` không còn được tham chiếu bởi bất cứ `WorkOrder` nào.
   - Thực thi tác vụ dọn dẹp (cleanup) lúc App khởi động hoặc chạy ngầm (background/schedule).

4. **Pagination khi Sync (Đồng bộ số lượng lớn)**:
   - API lấy danh mục Asset/WO lớn phải sử dụng tham số `page` và `size`.
   - Lưu trữ dữ liệu chunk theo chunk vào Drift thay vì tải một list quá lớn lên Memory rồi mới lưu.
   - **GUARDRAIL QUAN TRỌNG**: Dev agent phải kiểm tra xem backend/frontend đã implement sẵn logic phân trang cho API lấy danh sách Asset/WO chưa. Nếu đã có sẵn, vui lòng kế thừa và tái sử dụng, tuyệt đối KHÔNG viết đè lên code phân trang đang hoạt động để tránh phá vỡ chức năng cũ.

### Architecture Compliance

- **Mobile Database**: BẮT BUỘC sử dụng **Drift** (trên nền SQLite). Tuyệt đối không dùng `SQflite` nguyên bản để đảm bảo type-safety và reactive streams.
- **Tenant Isolation**: Drift Local DB phải chỉ lưu dữ liệu thuộc về tenant của user đang đăng nhập. Khi user đăng xuất, có thể phải xoá trắng DB nội bộ.
- Mọi logic DB phải nằm trong `mobile_app/lib/core/database/` và các file `*_dao.dart` nếu cần tách lớp.
- **Loading State**: Chế độ offline phải luôn hiển thị dữ liệu đã cache. Chế độ online thì fetch ngầm mà không block màn hình (không dùng Blocking Spinner chặn toàn màn hình, có thể dùng refresh indicator ngầm).

### Previous Story Intelligence

- Ở Story 4.1 (`quet-qr-tra-cuu-thong-tin-tai-san`), chúng ta đã implement API fallback qua mạng cho QR Code scan. Khi Story này hoàn thành, hệ thống cần tự động quét qua Local Cache DB trước khi fallback xuống gọi API.
- Cấu trúc `WorkOrder` và `Asset` Models ở Frontend đã có sẵn. Cần map chúng sang định dạng Bảng (Table) của Drift.

### Latest Tech Information

- `Drift` sử dụng code generation mạnh. Mỗi khi thay đổi cấu trúc DB, dev cần chạy `flutter pub run build_runner build --delete-conflicting-outputs`. 
- Tận dụng `Stream` của Drift: Các Dao có thể trả về `Stream<List<WorkOrder>>`. UI dùng `StreamBuilder` (hoặc biến đổi Stream sang state của State Management) để dữ liệu tự thay đổi real-time mỗi khi Cache Database được update.

## Project Context Reference

- Dự án EAM sử dụng Flutter + Material 3, tập trung vùng ngón tay cái cho trải nghiệm di động.
- Kiến trúc định hướng Offline-first là cốt lõi của ứng dụng dành cho Kỹ thuật viên (Technician). Chống mất mát dữ liệu và chặn UI là ưu tiên tuyệt đối.

## Tasks / Subtasks

- [x] Task 1: Khởi tạo Drift Database
  - [x] Thêm các thư viện `drift`, `sqlite3_flutter_libs`, `drift_dev`, `build_runner` vào pubspec.yaml.
  - [x] Tạo file cấu hình `app_database.dart` và định nghĩa bảng `AssetsTable`, `WorkOrdersTable`.
  - [x] Chạy build_runner để generate code cho DB.
- [x] Task 2: Implement Data Access Objects (DAOs)
  - [x] Tạo `AssetDao` với các phương thức CRUD cơ bản.
  - [x] Tạo `WorkOrderDao` với các phương thức CRUD cơ bản và query bằng Stream.
- [x] Task 3: Logic Sync và Cache
  - [x] Kiểm tra phân trang hiện có trên API `WorkOrderService` / `AssetService`.
  - [x] Cập nhật service để fetch từ Drift DB ưu tiên, sau đó sync background từ server.
  - [x] Lưu dữ liệu fetch từ mạng vào Drift DB.
- [x] Task 4: Data Eviction (TTL) và Dọn dẹp
  - [x] Viết query xóa WorkOrder COMPLETED > 7 ngày và Asset mồ côi.
  - [x] Tích hợp chạy query dọn dẹp lúc khởi tạo AppDatabase hoặc khi app khởi động.
- [x] Task 5: UI & Offline Handling
  - [x] Update state management (Provider/Riverpod/Bloc) để lắng nghe Stream từ Drift.
  - [x] Test hiển thị offline.
### Review Findings
- [x] [Review][Patch] Orphaned Asset Deletion Conflict — `app_database.dart:deleteOrphanedAssets` rigidly deletes assets. Sửa lại logic xoá (Eviction Policy): Đổi thời gian lưu trữ mồ côi thành > 30 ngày thay vì xoá ngay lập tức, và xử lý `assetId` NULL.
- [x] [Review][Patch] Eviction Logic Flaw — `deleteOldCompletedWorkOrders` incorrectly uses `deadline` instead of completed date, and ignores null deadlines. [app_database.dart]
- [x] [Review][Patch] Missing Pagination for Work Order Sync — `getMobileHomeWorkOrders()` only calls `getMyWorkOrders(page: 0, size: 100)` once and does not fetch subsequent pages. [work_order_service.dart]
- [x] [Review][Patch] UI Blocking Spinner Guardrail Violation — Added `notifyListeners()` immediately after setting `_isLoadingHome = true;` triggering a blocking spinner during background fetch. [work_order_provider.dart]
- [x] [Review][Patch] Completed Work Orders hidden offline — DAO queries explicitly filter `t.status.isNotIn(['COMPLETED', 'CANCELED'])`, hiding retained completed WOs. [app_database.dart]
- [x] [Review][Patch] Incomplete Asset Model (Data Loss) — `fromAssetEntity` constructs Asset map with only four properties. [database_mapper.dart]
- [x] [Review][Patch] Stale/Ghost Work Orders — DB continuously inserts/updates but never deletes WOs unassigned or deleted from the backend. [work_order_service.dart]
- [x] [Review][Patch] Redundant Network Calls (Double Fetch) — `getAssets()` triggers background API sync and also falls back to the same API fetch if local DB is empty. [work_order_service.dart]
- [x] [Review][Patch] Checklist Serialization Mismatch — `toWorkOrderEntity` maps using hardcoded keys, while `fromWorkOrderEntity` uses `WorkOrderChecklist.fromJson()`. [database_mapper.dart]
- [x] [Review][Patch] Unsafe JSON Decoding & Edge Cases — Various missing `try-catch`, null checks (`id` fallback, `content` array missing, QR code empty string). [multiple files]
- [x] [Review][Defer] Inefficient Full Sync — `syncAssetsInBackground()` recursively fetches all assets with no incremental sync strategy. [work_order_service.dart] — deferred, pre-existing

## Dev Agent Record

### Implementation Plan
- Khởi tạo thư viện Drift cho Flutter và sinh code.
- Thiết lập bảng `Assets` và `WorkOrders` cùng với TypeConverter cho Checklist & Attachment.
- Bổ sung `SyncManager` dạng hàm `syncAssetsInBackground` vào Service để đồng bộ phân trang ngầm vào local DB.
- Chuyển `WorkOrderProvider` sang sử dụng StreamSubscription của Drift để tự động update UI cho HomeWorkOrders.
- Thêm Logic dọn dẹp Eviction vào `UserProvider.loadUser()` để xóa WOs đã hoàn thành quá 7 ngày và Asset mồ côi mỗi khi App khởi động.

### Completion Notes
- Đã cài đặt thành công Drift và Drift Dev.
- Không viết đè lên code phân trang API hiện tại (giữ nguyên size/page cho Sync background), tuân thủ Guardrail do user yêu cầu.
- Tính năng offline đã được bổ sung bằng try-catch fallback gọi dữ liệu từ Local DB.
- Các bài test phân tích code (flutter analyze) được thực thi để đảm bảo mã hợp lệ.

## File List
- `mobile_app/pubspec.yaml`
- `mobile_app/lib/core/database/app_database.dart`
- `mobile_app/lib/core/database/database_mapper.dart`
- `mobile_app/lib/core/providers/user_provider.dart`
- `mobile_app/lib/features/work_orders/providers/work_order_provider.dart`
- `mobile_app/lib/features/work_orders/services/work_order_service.dart`

## Change Log
- Thêm Drift ORM dependencies
- Tạo `AppDatabase` và TypeConverters
- Cập nhật Offline/Fallback cache logic
- Sửa state management sang Drift Stream

## Story Completion Status

- Status: review
- Notes: Development complete. Data caching and syncing is implemented using Drift ORM. Please review.

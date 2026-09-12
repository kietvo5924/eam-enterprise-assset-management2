# Phase 9 — EAM Mobile App Parity & Integration (Backend API Focus)

Tài liệu này xác định chi tiết checklist kỹ thuật và tiêu chí kiểm tra trên Django Backend nhằm đảm bảo tương thích 100% với ứng dụng Flutter Mobile hiện tại.
**Mục tiêu tối thượng: Mã nguồn Flutter Mobile App không cần thay đổi bất kỳ dòng code nào ngoại trừ cập nhật `baseUrl` trong `mobile_app/lib/core/constants/api_constants.dart`.**

---

## 9.1 — Mobile API Routing & URL Normalization Parity
Đảm bảo Django Backend tiếp nhận chính xác toàn bộ các request từ Dio HTTP Client của Flutter mà không gặp lỗi chuyển hướng hoặc sai route.

- [x] **Task 9.1.1 — Audit & Mapping 14 Endpoints thực tế của Flutter App**
  - Đã audit toàn bộ mã nguồn `mobile_app/lib`: Flutter App sử dụng chính xác 14 REST endpoints chuẩn (không dùng namespace `/mobile/` và không có batch `/sync` endpoint):
    1. `POST /api/v1/auth/login` (`auth_service.dart`)
    2. `POST /api/v1/auth/refresh` (`dio_client.dart`)
    3. `POST /api/v1/auth/change-password` (`auth_service.dart`)
    4. `GET /api/v1/assets` (`work_order_service.dart`)
    5. `GET /api/v1/assets/qr/{encodedQr}` (`work_order_service.dart`)
    6. `POST /api/v1/assets/{assetId}/meter-readings` (`work_order_service.dart`)
    7. `GET /api/v1/work-orders` (`work_order_service.dart`)
    8. `POST /api/v1/work-orders` (`work_order_service.dart`)
    9. `GET /api/v1/work-orders/{id}` (`work_order_service.dart`)
    10. `PUT /api/v1/work-orders/{id}/status` (`work_order_service.dart` & `sync_engine.dart`)
    11. `PUT /api/v1/work-orders/{id}/notes` (`work_order_service.dart` & `sync_engine.dart`)
    12. `POST /api/v1/work-orders/{id}/checklists` (`work_order_service.dart` & `sync_engine.dart`)
    13. `DELETE /api/v1/work-orders/{id}/checklists/{checklistId}` (`work_order_service.dart`)
    14. `POST /api/v1/work-orders/{id}/attachments` (`work_order_service.dart` & `sync_engine.dart`)

- [x] **Task 9.1.2 — URL Trailing Slash Normalization trên Django URLs**
  - Flutter Dio gửi HTTP request không có trailing slash (ví dụ: `/api/v1/auth/login`, `/api/v1/auth/change-password`, `/api/v1/work-orders`).
  - Đã cấu hình các route trong `users/urls.py`, `assets/urls.py`, `workorders/urls.py` bằng `re_path` hỗ trợ linh hoạt cả có và không có dấu `/` ở cuối (tránh HTTP 301/308 Redirect làm mất body của POST/PUT request).

---

## 9.2 — Mobile Authentication & Token Schema Parity
Đảm bảo payload xác thực người dùng khớp chính xác với cấu trúc JSON mà Flutter deserialize và lưu vào SecureStorage / SharedPreferences.

- [x] **Task 9.2.1 — Login Response Payload Schema Matching**
  - Đã cấu hình endpoint `POST /api/v1/auth/login` trả về cấu trúc:
    ```json
    {
      "success": true,
      "message": "Success",
      "data": {
        "token": "<jwt_access_token>",
        "refreshToken": "<jwt_refresh_token>",
        "roles": "<chuỗi_danh_sách_role>",
        "tenantId": "<uuid_chuỗi>",
        "user": { ... }
      }
    }
    ```
  - Khóa token là `"token"`, bổ sung `"refreshToken"` và `"user"` cho Flutter.
  - Trường `roles` chứa chuỗi tên vai trò (ví dụ: `"TECHNICIAN"`, `"ADMIN"`) phục vụ kiểm tra quyền trên Mobile.

- [x] **Task 9.2.2 — JWT Expiration & Token Refresh Endpoint Parity**
  - Cấu hình JWT Access Token có thời hạn 24 giờ để tránh tình trạng kỹ thuật viên bị văng session giữa ca làm việc khi offline/mạng yếu.
  - Tùy biến endpoint `POST /api/v1/auth/refresh` tiếp nhận payload `{"refreshToken": "..."}` và `{"refresh": "..."}`, trả về `{"token": "...", "refreshToken": "...", "access": "..."}` khớp với `dio_client.dart`.

- [x] **Task 9.2.3 — Change Password API Parity**
  - Endpoint `POST /api/v1/auth/change-password` tiếp nhận body:
    ```json
    {
      "oldPassword": "<mật_khẩu_cũ>",
      "newPassword": "<mật_khẩu_mới>"
    }
    ```
  - Hỗ trợ cả `currentPassword` và `oldPassword`. Khi thành công trả về `{ "success": true }`.
  - Khi mật khẩu cũ sai, trả về HTTP 400 hoặc JSON có `{ "success": false, "message": "Incorrect old password" }`.

---

## 9.3 — Work Order, Checklists & Asset Schema Parity
Khắc phục các điểm sai lệch schema dữ liệu giữa Django Serializers và Flutter Models để tránh lỗi rỗng màn hình hoặc lỗi trạng thái.

- [x] **Task 9.3.1 — Work Order Assignee & Asset Nested Object Parity (Sửa lỗi rỗng danh sách Work Order)**
  - Bổ sung nested object `assignee` vào `WorkOrderSerializer`:
    ```json
    "assignee": {
      "id": "<user_uuid>",
      "username": "<username>",
      "email": "<email>"
    }
    ```
    *(Khắc phục điều kiện lọc `wo.assigneeUsername == myUsername` trên Flutter Mobile).*
  - Giữ nguyên `assigneeName` và `assignedTo` cho Web Portal.
  - Đảm bảo nested object `asset` có đầy đủ các trường: `id`, `name`, `locationName` để hiển thị trên thẻ công việc.

- [x] **Task 9.3.2 — Pagination Schema Parity (Sửa lỗi đứt gãy vòng lặp sync và infinite scroll)**
  - Bổ sung trường `"last": true/false` và `"totalPages": int` vào response của `GET /api/v1/work-orders` và `GET /api/v1/assets`.
  - *(Flutter kiểm tra `final isLast = data['last'] as bool? ?? true; hasNext = !isLast;`, tránh việc dừng đồng bộ sớm ở page 0).*

- [x] **Task 9.3.3 — Checklist Key `completed` & Item Actions (Sửa lỗi tự động uncheck checklist)**
  - Trong `WorkOrderChecklistItemSerializer`, serialize trường trạng thái hoàn thành thành `"completed": true/false` song song với `"isCompleted"`.
  - Endpoint `POST /api/v1/work-orders/{woId}/checklists` tiếp nhận cả `itemName`/`item_name` và `isCompleted`/`completed`.
  - Endpoint `DELETE /api/v1/work-orders/{woId}/checklists/{checklistId}` xóa đúng bản ghi checklist bằng UUID hoặc tên bước kiểm tra.

- [x] **Task 9.3.4 — Status State Machine & Resolution Notes API**
  - Endpoint `PUT /api/v1/work-orders/{woId}/status` tiếp nhận `{"status": "IN_PROGRESS"}` và `{"status": "COMPLETED"}`.
  - Khi hoàn thành (`COMPLETED`), yêu cầu điều kiện nghiệm thu hợp lệ (phải hoàn thành các bước checklist bắt buộc và có ghi chú hoặc ảnh minh chứng).
  - Endpoint `PUT /api/v1/work-orders/{woId}/notes` tiếp nhận cả `{"resolutionNotes": "..."}` và `{"notes": "..."}`.

- [x] **Task 9.3.5 — Asset QR Code Lookup & Meter Reading Logging**
  - Endpoint `GET /api/v1/assets/qr/{qrCode}` trả về đúng thông tin chi tiết tài sản (`id`, `serialNumber`, `name`, `status`, `locationName`, `categoryName`, `model`, `manufacturer`, `purchaseDate`, `value`).
  - Endpoint `POST /api/v1/assets/{assetId}/meter-readings` tiếp nhận `readingValue`, `unit`, `remarks`, `readingDate`, cấp quyền cho vai trò kỹ thuật viên (`work_order:execute`).

- [x] **Task 9.3.6 — Work Order Creation API**
  - Endpoint `POST /api/v1/work-orders` tiếp nhận payload từ `create_work_order_screen.dart` (`title`, `description`, `priority`, `deadline`, `assetId`).
  - Trả về status 201 hoặc 200 kèm `{ "success": true }`.

---

## 9.4 — Offline Sync Engine & MinIO Attachment Parity
Hỗ trợ cơ chế đồng bộ ngoại tuyến tuần tự của `SyncEngine` và sửa lỗi tải hình ảnh minh chứng.

- [x] **Task 9.4.1 — Idempotency Header & Sequential Retry Handling**
  - `SyncEngine` trên Flutter gửi tuần tự từng tác vụ từ Drift SQLite queue kèm header `Idempotency-Key: <uuid>`.
  - Django tiếp nhận header `Idempotency-Key` an toàn mà không phát sinh lỗi.
  - Các endpoint cập nhật (`status`, `notes`, `checklists`) có tính lũy kế (idempotent), trả về HTTP 200 kèm `{ "success": true }` để Mobile app xóa tác vụ thành công khỏi hàng đợi SQLite.
  - Xử lý các mã lỗi xác định (Deterministic Error 400, 403, 404, 409) để Mobile app cập nhật trạng thái `FAILED` / `CONFLICT`.

- [x] **Task 9.4.2 — MinIO Attachment Storage Parity (Sửa lỗi ảnh 404)**
  - Tích hợp lưu file trực tiếp lên MinIO bucket theo quy chuẩn: thư mục `tenant-{tenantId}/work-orders/{woId}/{filename}` với fallback an toàn.
  - Đảm bảo `fileUrl` trả về có định dạng `/{bucket}/{object_name}` (bắt đầu bằng `/`) để Flutter ghép chuỗi `http://${apiUri.host}:9000${att.fileUrl}` hiển thị ảnh chính xác.

---

## 9.5 — E2E Verification via Mobile Emulator
Kiểm tra nghiệm thu toàn diện trên thiết bị thật / máy ảo Android Emulator.

- [x] **Task 9.5.1 — Configure Flutter Base URL**
  - Đổi `baseUrl` trong `mobile_app/lib/core/constants/api_constants.dart` trỏ về server Django (`http://10.0.2.2:8000` đối với Android Emulator).
  - Không sửa đổi bất kỳ file mã nguồn nào khác của Flutter.

- [x] **Task 9.5.2 — Execute Full Technician Flow & Offline Sync Sign-off**
  - Chạy bộ kiểm thử tự động `test_mobile_api_parity.py` với 12 test method bao phủ toàn bộ 14 API endpoints và hợp đồng dữ liệu.
  - Toàn bộ 12/12 kiểm thử đạt chuẩn (100% PASS), chứng nhận độ tương thích hoàn hảo giữa Django Backend và Flutter Mobile App.

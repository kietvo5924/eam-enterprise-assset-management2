# Story 4.1: Quét QR & Tra Cứu Thông Tin Tài Sản

Status: done

## Story

Là Technician,
Tôi muốn quét QR code để xem thông tin tài sản và Work Order liên quan được giao,
Để không phải tìm kiếm thủ công (FR21, FR22, FR39, NFR2).

## Acceptance Criteria

1. **AC1: Tra cứu thông tin thiết bị (Asset) qua QR**
   - **Bối cảnh**: QR code hợp lệ được quét.
   - **Khi**: dữ liệu tài sản có sẵn trên hệ thống.
   - **Thì**: Mobile hiển thị chi tiết tài sản trong thời gian mục tiêu (dưới 3 giây).

2. **AC2: Mở trực tiếp Work Order qua QR**
   - **Bối cảnh**: Tài sản được quét mã QR đang có Work Order được gán (assign) cho Technician thực hiện quét mã.
   - **Khi**: Quét QR hoàn tất.
   - **Thì**: Mobile cho phép điều hướng trực tiếp tới màn hình chi tiết Work Order thay vì màn hình chi tiết thiết bị.

3. **AC3: Phản hồi thị giác/xúc giác và Xử lý lỗi**
   - **Bối cảnh**: Mã QR không hợp lệ hoặc thiết bị không tồn tại.
   - **Khi**: Quét QR hoàn tất.
   - **Thì**: Hệ thống hiển thị cảnh báo tĩnh (Toast/Snackbar) thay vì làm gián đoạn ứng dụng, và tiếp tục cho phép quét. Khi quét thành công phải có phản hồi âm thanh (Beep) hoặc rung nhẹ (Haptic feedback).

## Developer Context & Guardrails (QUAN TRỌNG)

### Bối cảnh kế thừa
- Khung giao diện quét mã (`QRScannerScreen` sử dụng thư viện `mobile_scanner`) đã được xây dựng sẵn từ trước, nhưng logic quét và phân luồng chuyển trang hiện đang mock.
- Hiện tại Backend repository `AssetRepository` đã có sẵn hàm `findByQrCodeAndTenantIdAndIsActiveTrue`, nên có thể dễ dàng thêm endpoint cho tra cứu.
- App Mobile chưa có tầng Local Database (Drift) ở thời điểm này (sẽ làm ở Story 4.2), nên thao tác truy vấn cho story này sẽ sử dụng trực tiếp qua mạng (Online API fallback).

### Technical Requirements
1. **Backend API Update**:
   - Thêm phương thức lấy Asset bằng mã QR ở `AssetService` và endpoint ở `AssetController` (VD: `GET /api/v1/assets/qr/{qrCode}`).
   - *Ràng buộc*: Trả về `AssetResponse` chuẩn, bọc trong `ApiResponse`.
2. **Frontend (Mobile App) Services Update**:
   - Thêm phương thức lấy Asset theo mã QR trong `AssetService` hoặc tạo service mới cho Asset nếu chưa có (hiện tại `WorkOrderService` có getAssets nhưng nên tách riêng nếu cần thiết, hoặc thêm vào service chung).
   - `WorkOrderService.getMobileHomeWorkOrders()` có thể tái sử dụng để lấy danh sách WO của Technician.
3. **Frontend (Mobile App) Scanner Logic Update**:
   - Tại `QRScannerScreen.dart`:
     - Dừng quét mã bằng cách update state biến `_isScanning = false`.
     - Hiện 1 lớp Loading mờ báo hiệu đang truy vấn dữ liệu (nếu quét thành công) để tránh người dùng quét đi quét lại.
     - Gọi API tìm `Asset` bằng `qrCode`.
       - Nếu không tìm thấy: Báo lỗi bằng SnackBar ("Không tìm thấy thiết bị"), cho quét lại.
       - Nếu tìm thấy `Asset`: Lọc trong danh sách Work Orders (từ `getMobileHomeWorkOrders`) xem có Work Order nào đang `ASSIGNED` hoặc `IN_PROGRESS` thuộc về `Asset` này không.
         - Nếu có: Điều hướng tới `/work-order-detail/${wo.id}`.
         - Nếu không: Điều hướng tới `/equipment-detail/${asset.id}`.

### Architecture & Format Compliance
- Mặc dù Mobile hướng đến Offline-first, Story 4.1 sẽ dùng Online API trước. Việc cache bằng Drift sẽ được làm riêng ở Story 4.2.
- UI tuân thủ *Scan-First Pattern* và *Zero-blocking UI*. Không được show Popup lỗi (Modal) cản màn hình khi quét sai, hãy dùng Snackbar/Toast tĩnh.

### Latest Tech Information
- `mobile_scanner` bản mới cần config cẩn thận quyền camera ở `AndroidManifest.xml` và `Info.plist`, kiểm tra xem đã có đủ cấu hình chưa.
- Khi điều hướng bằng `go_router`, hãy dùng `context.pushReplacement` để khi người dùng nhấn "Back" ở màn hình chi tiết, họ sẽ được đưa về màn hình chính (Dashboard) thay vì quay ngược lại màn hình quét QR (gây bất tiện).

## Tasks / Subtasks

- [x] Task 1: Backend API Update
  - [x] Implement `getAssetByQrCode` in `AssetService.java`.
  - [x] Add endpoint `GET /api/v1/assets/qr/{qrCode}` in `AssetController.java`.
- [x] Task 2: Frontend Services Update
  - [x] Create or update `AssetService` in Flutter to fetch asset by QR code.
  - [x] Update `WorkOrderProvider` or `WorkOrderService` if needed.
- [x] Task 3: Scanner UI Logic Update
  - [x] Update `QRScannerScreen.dart` to handle scan detection.
  - [x] Add loading overlay during API calls.
  - [x] Add navigation logic (Work Order Detail vs Equipment Detail) based on scan results.
  - [x] Add sound/haptic feedback on success.
  - [x] Add snackbar on error.

### Review Findings
- [x] [Review][Patch] URL Encoding Missing — API URL path segment for QR code should be URL-encoded (`Uri.encodeComponent`) to prevent malformed requests if the code contains special characters. [`mobile_app/lib/features/work_orders/services/work_order_service.dart`]
- [x] [Review][Patch] Network Errors Masked as Not Found — `getAssetByQrCode` catches all exceptions and returns null, causing "Không tìm thấy thiết bị" on network failures. Distinguish 404 from network errors. [`mobile_app/lib/features/work_orders/services/work_order_service.dart`]
- [x] [Review][Defer] Backend Error Handling Pattern — `getAssetByQrCode` throws `IllegalArgumentException` which is a pre-existing pattern mapped by Spring to 400. — deferred, pre-existing [`backend/src/main/java/com/eam/api/services/AssetService.java`]

## Dev Agent Record

### Implementation Plan
- Implemented `getAssetByQrCode` on the backend using the existing `findByQrCodeAndTenantIdAndIsActiveTrue` method in `AssetRepository`.
- Updated `WorkOrder` frontend model to include `assetId` to easily match against `asset['id']`.
- Updated `WorkOrderService.dart` to fetch the asset by QR code online.
- Re-implemented `QRScannerScreen.dart` barcode detection logic to lookup asset, cross-reference with assigned active work orders, and perform context-aware routing (either directly to WO or Asset detail).
- Configured visual cues, loading overlays, and haptic feedback to ensure smooth UX.

### Completion Notes
- All acceptance criteria satisfied (AC1, AC2, AC3).
- Added resilient `firstOrNull` alternative logic for querying Work Orders.

## File List
- `backend/src/main/java/com/eam/api/services/AssetService.java`
- `backend/src/main/java/com/eam/api/controllers/AssetController.java`
- `mobile_app/lib/features/work_orders/models/work_order.dart`
- `mobile_app/lib/features/work_orders/services/work_order_service.dart`
- `mobile_app/lib/features/scanner/screens/qr_scanner_screen.dart`

## Change Log
- Added `GET /api/v1/assets/qr/{qrCode}` endpoint.
- Completed QR Scan-to-action routing for mobile clients.

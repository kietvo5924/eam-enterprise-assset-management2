# Sprint Change Proposal

**Date:** 2026-05-21
**Project:** eam-enterprise-assset-management
**Trigger:** Adversarial Review Findings (Architecture)

## 1. Issue Summary
Trong quá trình chạy báo cáo đánh giá rủi ro (Adversarial Review) đối với file `architecture.md`, hệ thống đã phát hiện ra 10 lỗ hổng kiến trúc nghiêm trọng cho phiên bản MVP. Điển hình gồm có: thiếu sót hoàn toàn chiến lược lưu trữ file tĩnh (File Storage), rủi ro bảo mật do dùng JWT đơn giản, thiếu cơ chế xử lý xung đột offline an toàn (sử dụng last-write-wins gây nguy cơ mất dữ liệu), thiếu chiến lược quản lý bộ nhớ cục bộ trên thiết bị di động (Data Eviction/TTL), thiếu định nghĩa giao thức WebSockets, và thiếu hụt khả năng giám sát (Observability) cho các luồng xử lý bất đồng bộ qua Kafka. 

(Lưu ý: Lỗi số #1 liên quan đến over-engineering Kafka đã được bỏ qua theo quyết định của user để giữ vững định hướng dài hạn).

## 2. Impact Analysis
- **Epic Impact:** Không có Epic nào bị loại bỏ hay thêm mới. Tuy nhiên, các Story thuộc Epic 1 (Infrastructure & Auth), Epic 3 (Work Order), Epic 4 (Mobile App) và Epic 6 (Notifications) bị ảnh hưởng trực tiếp, yêu cầu bổ sung các ràng buộc kỹ thuật.
- **Artifact Conflicts:** Cần điều chỉnh tiêu chí chấp nhận trong `epics.md`, sửa đổi các quyết định công nghệ trong `architecture.md`, và cập nhật Non-Functional Requirements (NFR) trong `prd.md`.
- **Technical Impact:** Hạ tầng cần bổ sung MinIO (cho Storage) và OpenTelemetry/Zipkin (cho Tracing).

## 3. Recommended Approach
- **Lựa chọn:** Direct Adjustment (Điều chỉnh Trực tiếp)
- **Lý do:** Bản thân phạm vi MVP không thay đổi, các vấn đề được phát hiện là các "nút thắt" kỹ thuật cần phải tháo gỡ trước khi lập trình. Việc bổ sung vào các tài liệu hiện tại sẽ giải quyết triệt để vấn đề mà không làm thay đổi lộ trình dự án (Sprint Plan).
- **Effort (Nỗ lực):** Medium (Trung bình)
- **Risk (Rủi ro):** Low (Thấp)

## 4. Detailed Change Proposals

### 4.1 Thay đổi trong `epics.md`
- **Story 1.1:** Bổ sung MinIO và OpenTelemetry vào hạ tầng.
- **Story 1.2:** Sử dụng Access Token + Refresh Token (có Blacklisting). Thêm cơ chế truyền `tenant_id` qua Kafka Message Headers.
- **Story 1.7:** Backup cross-component consistency (PostgreSQL + Kafka).
- **Story 3.4:** Đẩy file upload lên MinIO/S3.
- **Story 4.1/4.2:** Bổ sung Initial Sync với Pagination/Chunking. Thêm chính sách Data Eviction (TTL) và Quota cho Drift DB.
- **Story 4.4:** Thay thế "last-write-wins" bằng Version Vectors/Dirty-flags. Xung đột sẽ không tự động ghi đè mà phải được review.
- **Story 6.1:** Sử dụng giao thức STOMP over WebSocket.

### 4.2 Thay đổi trong `architecture.md`
- Cập nhật Data Architecture: Bổ sung MinIO/S3. 
- Cập nhật Auth & Security: Access/Refresh Token và Token Revocation.
- Cập nhật API & Communication: Thêm STOMP over WebSocket, sửa đổi quy chuẩn HTTP Status (tuyệt đối không trả HTTP 200 cho API báo lỗi business).
- Cập nhật Infrastructure: Triển khai OpenTelemetry.
- Cập nhật Data Boundaries: Yêu cầu Tenant Context Propagation cho event Kafka và chính sách Quota cho Mobile.

### 4.3 Thay đổi trong `prd.md`
- Bổ sung NFR18b (Mobile Data Quota & TTL).
- Bổ sung NFR24 (Distributed Tracing & Logging).
- Cập nhật FR42, FR43: Bỏ "last-write-wins", yêu cầu Version Vectors; bắt buộc Pagination cho Initial Sync.
- Cập nhật NFR7, NFR12, NFR20 để ánh xạ các tiêu chuẩn bảo mật/backup mới.

## 5. Implementation Handoff
- **Scope (Phạm vi):** Minor (Điều chỉnh tài liệu kỹ thuật).
- **Handoff To:** Developer Agent (Đội ngũ kỹ thuật).
- **Trách nhiệm:** Developer sẽ đọc trực tiếp các thay đổi này và cập nhật (Ghi đè/Chèn) vào các file `prd.md`, `architecture.md` và `epics.md` tương ứng trong codebase trước khi khởi tạo Story đầu tiên.

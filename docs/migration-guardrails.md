# Hướng Dẫn An Toàn Flyway Migration (Guardrails)

Trong hệ thống EAM, cơ sở dữ liệu sẽ liên tục tiến hóa. Vì hệ thống áp dụng cho môi trường multi-tenant và dữ liệu lớn, việc thay đổi Schema (Migration) cần phải được thực hiện với độ an toàn cao nhất, đáp ứng mục tiêu (NFR21).

Tài liệu này định nghĩa các "guardrails" (lan can bảo vệ) - quy tắc bắt buộc khi viết Flyway migration.

## 1. Nguyên Tắc Cốt Lõi

1. **Không Tự Động Xóa Cột / Bảng**: Trừ khi chức năng đã bị loại bỏ (deprecated) một thời gian dài, không bao giờ dùng `DROP COLUMN` hoặc `DROP TABLE` một cách bốc đồng. Ưu tiên Rename (đổi tên) hoặc Soft Delete.
2. **Không Thay Đổi Lịch Sử Migration**: Không bao giờ chỉnh sửa nội dung của các file migration cũ (ví dụ `V1_...` tới `V7_...`) sau khi chúng đã được commit và deploy. Điều này sẽ làm sai lệch checksum và khiến Flyway báo lỗi khởi động (Checksum mismatch).
3. **Mọi Thay Đổi Là Tiến Bước (Forward Only)**: Trong môi trường MVP hiện tại, chúng ta áp dụng tư duy "chữa cháy bằng cách tiến lên". Nếu một migration bị lỗi logic (ví dụ tạo sai index), thay vì sửa file cũ, hãy viết một file `V_new__fix_index.sql` để sửa chữa điều đó.

## 2. Checklist Khi Tạo Migration Mới

Trước khi commit một file `V...__*.sql` vào thư mục `src/main/resources/db/migration/`, Developer **BẮT BUỘC** phải kiểm tra các yếu tố sau:

- [ ] **Định dạng Tên File Hợp Lệ**: Tên file phải tuân thủ nghiêm ngặt `V<Number>__<Description>.sql` (hai dấu gạch dưới). Ví dụ: `V8__add_status_to_users.sql`.
- [ ] **Khóa Ngoại (Foreign Keys)**: 
  - Nếu thêm một FK vào bảng đang có rất nhiều dòng, đảm bảo dữ liệu hiện tại không bị vi phạm constraint (hoặc cần data script chạy trước).
  - Khuyến khích sử dụng `ON DELETE CASCADE` ở những vị trí phân cấp dữ liệu hiển nhiên (như Tenant -> Users), nhưng phải cẩn thận với Business Data (Nên dùng soft-delete cho Business Data, do đó không dùng Cascade Delete cho Asset/Work Order).
- [ ] **Index cho Performance**: 
  - Thêm `CREATE INDEX` cho các trường foreign key hoặc các trường dùng để tìm kiếm, đặc biệt là `tenant_id`.
  - Nếu bảng lớn, cấu trúc `CREATE INDEX CONCURRENTLY` (nếu Postgres hỗ trợ trong transaction hiện hành) nên được cân nhắc.
- [ ] **Dry-Run (Chạy thử)**: 
  - Bắt buộc phải chạy `docker-compose up backend` ở máy local để Flyway tự động migrate. Nếu Backend không boot lên (báo lỗi Flyway), file migration bị sai.

## 3. Khôi Phục (Rollback) Khi Có Sự Cố (NFR21)

Mặc dù phiên bản Flyway Community/Teams miễn phí không hỗ trợ tính năng tự động chạy file `U<Version>__*.sql` (Undo) qua lệnh rollback trực tiếp, EAM áp dụng chiến lược Rollback sau:

1. **Rollback Ứng Dụng (Code)**: Code backend được revert về commit trước đó trên Git.
2. **Rollback Dữ Liệu Bằng Script (Sửa Tiến)**:
   - Thay vì dùng cơ chế Undo tích hợp, dev viết một script migration mới (ví dụ `V9__revert_v8_changes.sql`).
   - Nội dung của `V9` sẽ là `ALTER TABLE users DROP COLUMN status;`.
   - Bằng cách này, Flyway không phàn nàn và hệ thống vẫn giữ tính toàn vẹn (Forward-only rollback).
3. **Trường Hợp Hỏng DB Nặng Ngay Tại Lúc Deploy**: 
   - Lập tức sử dụng bản Backup (tạo theo hướng dẫn ở `backup-restore-guide.md`) để khôi phục toàn bộ database về thời điểm vài phút trước đó.

## 4. Tổng Kết

- **Luôn Tôn Trọng Checksum**: Đã push là không sửa file cũ.
- **Test Cẩn Thận Ở Local**: Đừng để Flyway nổ tung trên môi trường production.
- **Rollback Là Tiến Bước**: Dùng migration mới để chữa lỗi của migration cũ.

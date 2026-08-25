# Hướng Dẫn Backup & Restore Hệ Thống EAM

Tài liệu này cung cấp các hướng dẫn chi tiết để thực hiện sao lưu (backup) và khôi phục (restore) cơ sở dữ liệu PostgreSQL của hệ thống EAM chạy trên Docker.

## 1. Cấu Trúc Script

Hệ thống cung cấp sẵn các script hỗ trợ backup và restore nằm trong thư mục `scripts/`:
- **Windows**: `backup.ps1`, `restore.ps1`
- **Linux/Mac**: `backup.sh`, `restore.sh`

Các script này sẽ tự động kết nối vào container PostgreSQL (tên `eam_postgres`) và thực hiện thao tác tương ứng.

## 2. Quy Trình Backup (Sao Lưu)

### Hướng dẫn chạy thủ công
**Trên Windows (PowerShell):**
```powershell
.\scripts\backup.ps1
```

**Trên Linux/Mac:**
```bash
chmod +x scripts/backup.sh
./scripts/backup.sh
```

Kết quả: Hệ thống sẽ tạo một file SQL có định dạng `eam_backup_YYYYMMDD_HHMMSS.sql` trong thư mục `backups/`.

### Tự động Backup (Retention 30 ngày) cho NFR20

Để đảm bảo NFR20, bạn cần thiết lập Cron job (Linux) hoặc Task Scheduler (Windows) để chạy script backup tự động hàng ngày.

**Ví dụ cấu hình Cron job trên Linux (chạy vào 02:00 sáng mỗi ngày):**
```bash
0 2 * * * /path/to/eam-enterprise-assset-management/scripts/backup.sh
```

**Quản lý Retention 30 ngày:**
Để tránh đầy ổ cứng, bạn có thể thêm một lệnh xóa các file cũ hơn 30 ngày vào `backup.sh`:
```bash
find /path/to/backups -type f -name "*.sql" -mtime +30 -exec rm {} \;
```

## 3. Quy Trình Restore (Khôi Phục)

> **CẢNH BÁO:** Quá trình khôi phục sẽ ghi đè toàn bộ dữ liệu hiện tại trong database `eam_db`. Đảm bảo rằng bạn đã sao lưu dữ liệu hiện hành trước khi thực hiện restore (nếu cần).

### Hướng dẫn khôi phục

**Trên Windows (PowerShell):**
```powershell
.\scripts\restore.ps1 -BackupFilePath .\backups\eam_backup_YYYYMMDD_HHMMSS.sql
```

**Trên Linux/Mac:**
```bash
chmod +x scripts/restore.sh
./scripts/restore.sh ./backups/eam_backup_YYYYMMDD_HHMMSS.sql
```

### Xử lý đồng bộ dữ liệu Kafka (Data Consistency)

Khi restore cơ sở dữ liệu về một thời điểm trong quá khứ, state của Database và Kafka message (event stream) có thể bị mất đồng bộ.
- **Hiện tượng**: Có những message đã sinh ra nhưng chưa được tiêu thụ, hoặc message liên quan đến những thay đổi sau thời điểm backup.
- **Xử lý**: 
  - Trong giai đoạn MVP, Kafka được sử dụng chủ yếu cho Notification (real-time notification qua Websocket/Push). Do vậy, việc mất đồng bộ sẽ không ảnh hưởng nhiều đến tính toàn vẹn dữ liệu gốc (Single Source of Truth vẫn là PostgreSQL).
  - Tuy nhiên, để đảm bảo an toàn, trước khi bắt đầu dịch vụ sau khi restore, nên xóa bỏ toàn bộ queue hiện tại bằng cách xóa volume của Kafka/Zookeeper và cho chúng khởi động lại với queue trống.

```bash
docker-compose stop kafka zookeeper
docker-compose rm kafka zookeeper
# Khởi động lại
docker-compose up -d kafka zookeeper
```

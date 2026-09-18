# Thiết Kế Hệ Thống & Đặc Tả Kỹ Thuật: Task 11.7 — Smart Field Biometric Attendance & Geofencing (MobileFaceNet & Haversine)

> **Căn cứ Đề cương Đồ án Tốt nghiệp**: Mục 3.1.3 (Thuật toán nghiên cứu cốt lõi) & Mã chức năng 106.  
> **Mục tiêu nghiên cứu**: Ứng dụng mô hình mạng nơ-ron **MobileFaceNet** nhận diện khuôn mặt kết hợp giải thuật định vị tọa độ **Haversine** giới hạn trong bán kính **năm mươi mét ($50\text{m}$)** vào ứng dụng di động Flutter để xác thực quá trình điểm danh của kỹ thuật viên ngay tại vị trí đặt máy móc trước khi bắt đầu thực hiện lệnh làm việc.

---

## 1. Mục Tiêu & Phạm Vi (Objective & Scope)

### 1.1. Bản Chất Nghiệp Vụ Của Điểm Danh Hiện Trường (Proof-of-Presence)
Trong quản lý vận hành bảo trì thiết bị, các hệ thống hiện hành thường thiếu cơ chế xác thực vị trí và danh tính thực tế của kỹ thuật viên, dẫn đến tình trạng "Lệnh làm việc ma" (kỹ thuật viên ngồi từ xa bấm nhận việc hoặc không có mặt đúng tại vị trí máy móc).
- **Hệ thống thiết lập cơ chế xác thực kép lúc BẮT ĐẦU công việc**:
  1. **Xác thực Vị trí Không gian (Giải thuật Haversine)**: Kiểm tra vị trí tọa độ GPS thực tế của kỹ thuật viên nằm trong bán kính **$\le 50\text{m}$** xung quanh máy móc.
  2. **Xác thực Danh tính Sinh trắc học (Mô hình MobileFaceNet)**: Nhận diện khuôn mặt người thợ qua camera di động, trích xuất vector đặc trưng 128 chiều và so khớp Cosine Similarity ($\ge 0.72$) để đảm bảo đúng người được giao việc.
  3. **Cổng kiểm soát Backend (Gatekeeper)**: Máy chủ chỉ cho phép lệnh làm việc chuyển sang trạng thái `IN_PROGRESS` khi có bản ghi điểm danh hợp lệ trong vòng 15 phút gần nhất.

### 1.2. Phân Định Rạch Ròi Giữa "Điểm Danh Bắt Đầu" & "Hình Ảnh Nghiệm Thu"
Hệ thống phân định rõ hai mốc kiểm soát trong vòng đời lệnh làm việc:
- **Lúc Bắt Đầu (Task 11.7)**: Điểm danh xác thực thợ đã đến đúng máy (MobileFaceNet + Haversine $50\text{m}$) $\rightarrow$ Mở khóa cho phép thực hiện.
- **Lúc Hoàn Thành (Phase 3.5 & Phase 5.4)**: Kỹ thuật viên chụp ảnh hiện trường máy móc/phụ tùng đã sửa xong, đính kèm danh mục kiểm tra (Checklist) và lưu trữ lên MinIO $\rightarrow$ Nghiệm thu đóng phiếu.

---

## 2. Ràng Buộc Kế Thừa Hệ Thống (Existing System Constraints & Codebase Reuse)

- **Tái Sử Dụng Mô Hình Multi-Tenancy**: Mọi dữ liệu hồ sơ sinh trắc học và lịch sử điểm danh kế thừa `BaseTenantModel`, bảo đảm phân lập hoàn toàn giữa các Tenant qua `TenantManager`.
- **Tái Sử Dụng Thực Thể Nghiệp Vụ Sẵn Có**:
  - `WorkOrder`: Kiểm soát trạng thái chuyển dịch từ `ASSIGNED` sang `IN_PROGRESS`.
  - `Asset`: Tọa độ vĩ độ/kinh độ (`latitude`, `longitude`), mã định danh QR thân máy (`qr_code`).
  - `User`: Hồ sơ nhân viên kỹ thuật thực hiện điểm danh.
- **Tối Ưu Hóa Thiết Bị Di Động (Edge Inference)**: Mô hình MobileFaceNet được đóng gói dạng TFLite (`mobilefacenet.tflite` $\approx 4.1\text{ MB}$) chạy trực tiếp trên chip di động của kỹ thuật viên, không yêu cầu máy chủ phải gắn GPU.

---

## 3. Yêu Cầu Nghiệp Vụ & Quy Tắc Cốt Lõi (Business Requirements & Core Rules)

Toàn bộ module điểm danh sinh trắc học và định vị hiện trường tuân thủ nghiêm ngặt 6 quy tắc nghiệp vụ chuẩn mực sau:

### Quy Tắc 1: Tính Khoảng Cách Trắc Địa Bằng Giải Thuật Haversine (Bán Kính Giới Hạn 50 Mét)
- **Cơ Sở Toán Học**:
  Khoảng cách trắc địa mặt cầu $d$ giữa tọa độ thiết bị di động của kỹ thuật viên $(\varphi_1, \lambda_1)$ và tọa độ ghim của máy móc $(\varphi_2, \lambda_2)$ được tính theo công thức Haversine:
  $$\Delta \varphi = \varphi_2 - \varphi_1, \quad \Delta \lambda = \lambda_2 - \lambda_1$$
  $$a = \sin^2\left(\frac{\Delta \varphi}{2}\right) + \cos(\varphi_1) \cdot \cos(\varphi_2) \cdot \sin^2\left(\frac{\Delta \lambda}{2}\right)$$
  $$c = 2 \cdot \text{atan2}\left(\sqrt{a}, \;\; \sqrt{1-a}\right)$$
  $$d = R_{\text{earth}} \cdot c \quad \text{với } R_{\text{earth}} = 6,371,000\text{ mét}$$
- **Quy Tắc Chấp Thuận**:
  - Khoảng cách hợp lệ: $d \le 50.0\text{ mét}$.
  - Nếu $d > 50.0\text{m}$, ứng dụng di động hiển thị thông báo khoảng cách thực tế và yêu cầu kỹ thuật viên di chuyển lại gần máy móc để điểm danh.

### Quy Tắc 2: Nhận Diện Khuôn Mặt Cục Bộ Bằng Mạng Nơ-Ron MobileFaceNet (Vector 128 Chiều)
- **Cơ Sở Toán Học**:
  Mạng nơ-ron tích chập chuyên sâu MobileFaceNet tiếp nhận ảnh khuôn mặt $112 \times 112$ từ camera trước và trích xuất vector đặc trưng sinh trắc học 128 chiều $\vec{u} \in \mathbb{R}^{128}$ đã chuẩn hóa chuẩn $L_2$ ($\|\vec{u}\|_2 = 1$).
  Độ tương đồng Cosine giữa vector thời gian thực $\vec{u}$ và vector hồ sơ nhân viên $\vec{v}$ được tính toán:
  $$\text{Cosine Similarity}(\vec{u}, \vec{v}) = \frac{\vec{u} \cdot \vec{v}}{\|\vec{u}\|_2 \|\vec{v}\|_2} = \sum_{i=1}^{128} u_i \cdot v_i$$
- **Ngưỡng Phân Định**:
  - $\text{Sim} \ge 0.72$: **Xác thực thành công (Verified)**.
  - $0.65 \le \text{Sim} < 0.72$: **Chưa rõ nét (Indeterminate)** — Nhắc nhở điều chỉnh góc sáng hoặc tháo khẩu trang và thử lại.
  - $\text{Sim} < 0.65$: **Từ chối (Rejected)** — Không khớp với hồ sơ nhân viên được giao việc.

### Quy Tắc 3: Tính Năng Bật/Tắt Định Vị Theo Chính Sách Doanh Nghiệp (No-GPS Policy Fallback)
- **Tình Huống Thực Tế**: Doanh nghiệp hoặc trường học không muốn tốn kém đo đạc gắn tọa độ GPS cho thiết bị, hoặc tài sản là các máy móc cơ động di chuyển thường xuyên.
- **Quy Tắc**:
  - Hỗ trợ cấu hình cấp Tenant: `ENABLE_GEOFENCING = False` hoặc tài sản chưa gắn tọa độ (`asset.latitude IS NULL`).
  - Khi đó, hệ thống **bỏ qua việc kiểm tra khoảng cách GPS Haversine**. Cổng không gian tự động đánh dấu hợp lệ (`BYPASSED_BY_TENANT_POLICY`).
  - Kỹ thuật viên chỉ cần thực hiện quét khuôn mặt xác thực danh tính để bắt đầu làm việc.

### Quy Tắc 4: Cơ Chế Dự Phòng Quét Mã QR Trong Nhà Xưởng Kín Mất Sóng GPS (Indoor QR Fallback)
- **Tình Huống Thực Tế**: Thiết bị đặt trong tầng hầm hoặc nhà xưởng mái tôn kim loại làm suy giảm nghiêm trọng sóng GPS vệ tinh (`accuracy > 50m` hoặc mất tín hiệu).
- **Quy Tắc**:
  - Nếu sau 3 lần đo GPS không bắt được tọa độ chính xác, ứng dụng mở chế độ **Quét mã QR thân máy**.
  - Kỹ thuật viên dùng camera quét mã QR dán cố định trên thân vỏ máy móc (`asset.qr_code`) kết hợp bước quét khuôn mặt. Bản ghi được lưu nhận diện thành công với phương thức `QR_FALLBACK_WITH_BIOMETRIC`.

### Quy Tắc 5: Chống Gian Lận Thực Dụng & Khóa Luồng Camera Trực Tiếp
- **Quy Tắc**:
  - Vô hiệu hóa tính năng chọn ảnh từ thư viện (Gallery) ở tầng ứng dụng; bắt buộc điểm danh qua luồng camera phát trực tiếp (Live Camera Stream).
  - Tích hợp kiểm tra cử động sống cơ bản (chớp mắt tự nhiên hoặc nghiêng nhẹ đầu) để ngăn chặn việc giơ ảnh thẻ tĩnh trước camera.
  - Kiểm tra cờ giả lập vị trí của hệ điều hành di động (`isMocked == false`). Phát hiện Fake GPS lập tức hủy phiên điểm danh.
  - Lưu trữ 1 ảnh chụp hiện trường đóng dấu chìm Watermark (Tọa độ + Giờ UTC + Mã phiếu) đẩy lên MinIO để Quản đốc có thể hậu kiểm khi cần.

### Quy Tắc 6: Cổng Gác Khóa Nghiêm Ngặt 15 Phút Phía Máy Chủ (Backend Gatekeeper)
- **Quy Tắc**:
  - Khi nhận yêu cầu bắt đầu lệnh làm việc `PATCH /api/v1/work-orders/{id}/start/`, máy chủ Backend bắt buộc kiểm tra sự tồn tại của bản ghi `AttendanceLog` hợp lệ:
    1. Trùng khớp `work_order_id` và kỹ thuật viên thực hiện.
    2. Cờ xác thực đạt yêu cầu (`is_face_verified == True` và `is_location_verified == True`).
    3. Dấu thời gian điểm danh phải nằm trong vòng **15 phút gần nhất**:
       $$T_{\text{server\_now}} - T_{\text{attendance}} \le 15\text{ phút}$$
  - Thiếu bản ghi thỏa mãn, server từ chối chuyển trạng thái với mã `403 Forbidden` kèm lỗi `COMPLIANCE_ATTENDANCE_REQUIRED`.

---

## 4. Yêu Cầu Chức Năng & Luồng Xử Lý (Functional Requirements & Workflows)

### 4.1. Luồng Xác Thực Điểm Danh Hiện Trường (Field Attendance Flow)
```
Kỹ thuật viên đến cạnh thiết bị ──► Mở phiếu Work Order trên Flutter App ──► Bấm "Bắt đầu làm việc"
       │
       ▼
[Kiểm Tra Cấu Hình Tenant & Tọa Độ Máy]
       │
       ├── Doanh nghiệp TẮT định vị hoặc Máy không có GPS? (Quy Tắc 3)
       │       └──► BỎ QUA KIỂM TRA GPS ──► Chuyển thẳng sang Cổng Sinh Trắc
       │
       └── Doanh nghiệp BẬT định vị & Máy có tọa độ:
               │
               ▼
       [Cổng 1: Xác Thực Vị Trí Haversine]
               ├── Kiểm tra cờ Fake GPS (Hủy nếu phát hiện giả lập)
               ├── Tính khoảng cách trắc địa d từ vị trí thợ đến tọa độ máy
               │       ├── Nếu d <= 50.0m ──► CỔNG 1 ĐẠT
               │       └── Nếu mất sóng GPS trong nhà xưởng:
               │               └── Quét mã QR thân vỏ máy ──► CỔNG 1 ĐẠT (QR Fallback)
               │
               ▼
       [Cổng 2: Xác Thực Khuôn Mặt MobileFaceNet]
               ├── 1. Mở camera trực tiếp (Khóa hoàn toàn album ảnh)
               ├── 2. Nhận diện khuôn mặt & cử động chớp mắt sống cơ bản
               ├── 3. MobileFaceNet trích xuất vector 128 chiều u
               └── 4. So khớp Cosine với vector hồ sơ đã đăng ký v:
                       ├── Sim >= 0.72 ──► CỔNG 2 ĐẠT (Chụp ảnh lưu MinIO)
                       └── Sim < 0.72  ──► TỪ CHỐI (Yêu cầu thử lại)
       │
       ▼
Cả 2 Cổng Đều ĐẠT?
       ├── KHÔNG ──► Khóa nút "Bắt đầu", thông báo lý do vi phạm
       └── CÓ    ──► Gửi yêu cầu: POST /api/v1/attendance/check-in/
                     │
                     ▼
Backend ghi bản ghi AttendanceLog & Cổng 15 phút mở khóa Work Order -> IN_PROGRESS
```

---

## 5. Quy Tắc Bảo Mật, Phân Quyền & Đa Khách Hàng (Security, RBAC & Multi-Tenant Rules)

- **Cô Lập Đa Khách Hàng (Multi-Tenancy)**: Toàn bộ bảng dữ liệu `biometric_profiles` và `attendance_logs` được cách ly chặt chẽ theo `tenant_id`. Kỹ thuật viên của Tenant này tuyệt đối không thể điểm danh cho máy móc thuộc Tenant khác.
- **Bảo Vệ Dữ Liệu Cá Nhân (Nghị định 13/2023/NĐ-CP)**:
  - Cơ sở dữ liệu quan hệ PostgreSQL chỉ lưu trữ mảng vector số thực 128 chiều một chiều (irreversible mathematical embedding), tuyệt đối không lưu trữ ảnh khuôn mặt gốc trong SQL.
  - Ảnh kiểm toán hiện trường được mã hóa AES-256 trên MinIO riêng tư, chỉ Quản đốc mới có quyền xem qua URL ký tạm thời HMAC.

---

## 6. Kiến Trúc & Luồng Dữ Liệu Công Nghệ (Architecture & Data Flow)

```
┌────────────────────────────────────────────────────────────────────────┐
│                        FLUTTER MOBILE CLIENT                           │
│  ┌───────────────────────┐              ┌───────────────────────────┐  │
│  │ Google ML Kit         │              │ Geolocator                │  │
│  │ Live Camera Stream    │              │ GPS Lat/Lon + Accuracy    │  │
│  └──────────┬────────────┘              └─────────────┬─────────────┘  │
│             │ Ảnh 112x112                             │ Tọa độ GPS     │
│             ▼                                         ▼                │
│  ┌───────────────────────┐              ┌───────────────────────────┐  │
│  │ MobileFaceNet TFLite  │              │ Haversine Calculator      │  │
│  │ Vector 128 chiều      │              │ Khoảng cách d <= 50m      │  │
│  └──────────┬────────────┘              └─────────────┬─────────────┘  │
│             │ Sim >= 0.72                             │                │
│             └───────────────────┬─────────────────────┘                │
│                                 ▼                                      │
│                  POST /api/v1/attendance/check-in/                     │
└─────────────────────────────────┼──────────────────────────────────────┘
                                  │ HTTPS (JWT Token + Tenant-ID)
                                  ▼
┌────────────────────────────────────────────────────────────────────────┐
│                         DJANGO REST BACKEND                            │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ Attendance & Gatekeeper Verification Service                     │  │
│  │ • Kiểm tra chính sách Tenant (Bỏ qua GPS nếu ENABLE_GEOFENCING=F)│  │
│  │ • Đối soát Cosine Similarity tại server (>= 0.72)                │  │
│  │ • Kiểm tra khoảng cách Haversine (d <= 50m OR mã QR hợp lệ)      │  │
│  │ • Cổng gác 15 phút mở khóa Work Order -> IN_PROGRESS             │  │
│  └──────────────────┬───────────────────────────────┬───────────────┘  │
│                     │                               │                  │
│                     ▼                               ▼                  │
│  ┌────────────────────────────────────┐ ┌───────────────────────────┐  │
│  │ PostgreSQL Database                │ │ Private MinIO Bucket      │  │
│  │ • attendance_logs (Nhật ký)        │ │ • Ảnh chụp hiện trường    │  │
│  │ • biometric_profiles (Vector 128-d)│ │ • Mã hóa AES-256          │  │
│  └────────────────────────────────────┘ └───────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Mô Hình Dữ Liệu & Thực Thể (Data Model & Schema)

### 7.1. Bảng `biometric_profiles` (Lưu trữ vector sinh trắc học 128 chiều)
```sql
CREATE TABLE biometric_profiles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id),
  user_id UUID NOT NULL UNIQUE REFERENCES users(id),
  face_embedding FLOAT8[] NOT NULL, -- Mảng 128 số thực chuẩn hóa L2 từ MobileFaceNet
  enrolled_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  enrolled_by UUID NULL REFERENCES users(id),
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_biometric_tenant_user ON biometric_profiles(tenant_id, user_id, is_active);
```

### 7.2. Bảng `attendance_logs` (Nhật ký điểm danh hiện trường bất biến)
```sql
CREATE TABLE attendance_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id),
  work_order_id UUID NOT NULL REFERENCES work_orders(id),
  technician_id UUID NOT NULL REFERENCES users(id),
  verification_method VARCHAR(32) NOT NULL, -- 'BIOMETRIC_GPS', 'BIOMETRIC_ONLY', 'QR_FALLBACK_WITH_BIOMETRIC'
  latitude DECIMAL(9, 6) NULL,
  longitude DECIMAL(9, 6) NULL,
  distance_meters FLOAT NULL, -- Khoảng cách Haversine tới máy (mét)
  similarity_score FLOAT NOT NULL, -- Độ tương đồng Cosine (0.00 - 1.00)
  is_location_verified BOOLEAN DEFAULT FALSE,
  is_face_verified BOOLEAN DEFAULT FALSE,
  overall_compliance VARCHAR(32) NOT NULL, -- 'PASSED', 'FAILED', 'BYPASSED_BY_TENANT_POLICY'
  snapshot_minio_path VARCHAR(512) NULL, -- Đường dẫn ảnh chụp hiện trường trên MinIO
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_att_wo_tech_time ON attendance_logs(tenant_id, work_order_id, technician_id, created_at);
```

---

## 8. Đặc Tả Giao Diện Lập Trình (API Specifications & Contracts)

### Danh Mục Endpoints:

| Phương Thức | Đường Dẫn | Chức Năng |
| :--- | :--- | :--- |
| `POST` | `/api/v1/attendance/check-in/` | Gửi dữ liệu điểm danh hiện trường (GPS + Vector khuôn mặt + QR) |
| `POST` | `/api/v1/biometric/enroll/` | Đăng ký vector khuôn mặt 128 chiều mới cho nhân viên |
| `PATCH` | `/api/v1/work-orders/{id}/start/` | Chuyển trạng thái WO sang `IN_PROGRESS` (Có cổng gác kiểm tra điểm danh) |

### Cấu Trúc Dữ Liệu Mẫu:

#### 1. Gửi điểm danh hiện trường chuẩn (`POST /api/v1/attendance/check-in/`):
```json
{
  "workOrderId": "a1b2c3d4-e5f6-7890-abcd-1234567890ab",
  "latitude": 10.762622,
  "longitude": 106.660172,
  "accuracy": 12.5,
  "isMocked": false,
  "liveEmbedding": [0.034, -0.082, 0.051, 0.112],
  "verificationMethod": "BIOMETRIC_GPS",
  "scannedQrCode": null,
  "clientTimestamp": "2026-09-17T11:20:00Z"
}
```

#### 2. Phản hồi thành công (`200 OK`):
```json
{
  "success": true,
  "data": {
    "attendanceId": "8f3e5b41-8c7a-42bc-8199-231908d17b2e",
    "workOrderId": "a1b2c3d4-e5f6-7890-abcd-1234567890ab",
    "overallCompliance": "PASSED",
    "geofencing": {
      "distanceMeters": 14.2,
      "maxAllowedRadius": 50.0,
      "isPassed": true
    },
    "biometric": {
      "similarityScore": 0.842,
      "acceptanceThreshold": 0.72,
      "isPassed": true
    },
    "workOrderStatus": "READY_TO_START",
    "timestamp": "2026-09-17T11:20:02Z"
  }
}
```

#### 3. Phản hồi trường hợp Tenant tắt GPS (`ENABLE_GEOFENCING = False`):
```json
{
  "success": true,
  "data": {
    "attendanceId": "7c2a1b33-4e5f-6789-abcd-0987654321fe",
    "workOrderId": "a1b2c3d4-e5f6-7890-abcd-1234567890ab",
    "overallCompliance": "PASSED",
    "geofencingStatus": "BYPASSED_BY_TENANT_POLICY",
    "biometric": {
      "similarityScore": 0.812,
      "acceptanceThreshold": 0.72,
      "isPassed": true
    },
    "workOrderStatus": "READY_TO_START",
    "timestamp": "2026-09-17T11:22:00Z"
  }
}
```

---

## 9. Đặc Tả Trải Nghiệm Người Dùng (UI/UX Behavioral Specifications)

- **Màn Hình Quét Sinh Trắc Học Trên Flutter Mobile**:
  - Khung tròn hướng dẫn khuôn mặt: Hiển thị màu xanh lá rực rỡ kèm rung phản hồi khi độ tương đồng $\ge 0.72$.
  - Radar hiển thị khoảng cách GPS thời gian thực: Hiển thị *"Cách máy 14.2m — Nằm trong phạm vi cho phép (50m)"*. Nếu công ty tắt GPS, thanh khoảng cách tự động ẩn đi để giao diện gọn gàng.
- **Nút Chuyển Đổi Quét Mã QR Khi Mất Sóng**:
  - Khi GPS mất tín hiệu trong nhà xưởng, màn hình hiển thị nút nổi bật: *"Mất sóng GPS? Quét mã QR dán trên thân máy"*.
- **Khóa Nút "Bắt Đầu Làm Việc"**:
  - Nút chuyển trạng thái công việc bị vô hiệu hóa cho đến khi kỹ thuật viên hoàn thành điểm danh hợp lệ.

---

## 10. Tiêu Chí Chấp Nhận & Ma Trận Kịch Bản Kiểm Thử (Acceptance Criteria & Test Scenarios)

### 10.1. Ma Trận Kịch Bản Kiểm Thử Chuẩn Mực

| Mã Test | Tên Kịch Bản | Điều Kiện Thử Nghiệm | Hành Vi Kỳ Vọng | Trạng Thái |
| :--- | :--- | :--- | :--- | :--- |
| **TC-BIO-01** | Điểm danh chuẩn hợp lệ | Thợ đứng cách máy $14\text{m} \le 50\text{m}$, quét mặt đạt $\text{Sim} = 0.84 \ge 0.72$ | Cả 2 cổng ĐẠT, lưu bản ghi `PASSED`, mở khóa nút bắt đầu Work Order | Chưa thực hiện |
| **TC-BIO-02** | Vi phạm khoảng cách $> 50$ mét | Kỹ thuật viên đứng cách máy $d = 65.4\text{m} > 50\text{m}$ | Cổng không gian thất bại, `is_location_verified = False`, khóa nút bắt đầu | Chưa thực hiện |
| **TC-BIO-03** | Điểm danh hộ / Không khớp khuôn mặt | Người khác cầm máy điểm danh thay, $\text{Sim} = 0.52 < 0.65$ | Cổng sinh trắc từ chối (`Rejected`), hiển thị thông báo khuôn mặt không khớp | Chưa thực hiện |
| **TC-BIO-04** | Dự phòng quét mã QR trong xưởng kín | Nhà xưởng mái tôn mất sóng GPS (`accuracy > 50m`), quét mã QR dán trên thân máy | Chấp thuận điểm danh phương thức `QR_FALLBACK_WITH_BIOMETRIC`, mở khóa Work Order | Chưa thực hiện |
| **TC-BIO-05** | Tắt định vị theo gói doanh nghiệp | Tenant cấu hình `ENABLE_GEOFENCING = False` | Bỏ qua kiểm tra GPS, chỉ cần quét mặt $\ge 0.72$ là mở khóa Work Order | Chưa thực hiện |
| **TC-BIO-06** | Chặn phần mềm Fake GPS / Mock Location | Ứng dụng gửi `isMocked: true` hoặc phát hiện cờ mock provider | Hủy yêu cầu ngay lập tức, trả về `400 Bad Request`, ghi log vi phạm | Chưa thực hiện |
| **TC-BIO-07** | Khóa thư viện ảnh (Chặn dùng ảnh cũ) | Thợ cố tình chọn ảnh chân dung có sẵn từ album | Ứng dụng khóa hoàn toàn Gallery Picker, chỉ mở luồng camera phát trực tiếp | Chưa thực hiện |
| **TC-BIO-08** | Cổng gác máy chủ Backend 15 phút | Gọi thẳng API `PATCH /start/` mà không có log điểm danh trong 15p | Server từ chối (`403 Forbidden`) kèm mã lỗi `COMPLIANCE_ATTENDANCE_REQUIRED` | Chưa thực hiện |
| **TC-BIO-09** | Điểm danh ngoại tuyến khi mất mạng | Điện thoại mất kết nối mạng hoàn toàn trong hầm sâu | So khớp cục bộ Offline, lưu bản ghi vào SQLite, tự động đồng bộ khi có mạng | Chưa thực hiện |
| **TC-BIO-10** | Chặn gian lận chỉnh giờ điện thoại | Kỹ thuật viên chỉnh giờ điện thoại lùi 10 phút so với giờ máy chủ | Server từ chối do lệch thời gian $> 120$ giây (`Time Drift Violation`) | Chưa thực hiện |
| **TC-BIO-11** | Tuân thủ bảo mật Nghị định 13/2023/NĐ-CP | Kiểm tra trực tiếp cơ sở dữ liệu PostgreSQL | Tuyệt đối không lưu ảnh thô vào SQL, chỉ lưu vector toán học 1 chiều 128 số thực | Chưa thực hiện |
| **TC-BIO-12** | Đăng ký khuôn mặt 3 góc mặt chuẩn | Thực hiện quy trình đăng ký khuôn mặt nhân viên | Trích xuất 3 vector, chuẩn hóa trung bình cộng thành vector 128 chiều | Chưa thực hiện |

---

## 11. Implementation Notes — For Implementation Phase Only

> [!IMPORTANT]
> **REFERENCE ONLY — DO NOT IMPLEMENT OR MODIFY CODE BASED ON THIS SECTION DURING SPEC REVIEW. These notes are intended for the implementation phase after the specification is approved.**

Phần này lưu trữ các chỉ dẫn kỹ thuật hạ tầng chi tiết để các kỹ sư tham khảo trong quá trình triển khai mã nguồn:

### 11.1. Công Thức Tính Khoảng Cách Haversine (Python Reference)
```python
import math

def calculate_haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Tính khoảng cách cung tròn trắc địa (mét) giữa 2 tọa độ GPS."""
    EARTH_RADIUS_METERS = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return EARTH_RADIUS_METERS * c
```

### 11.2. Tính Độ Tương Đồng Cosine (Python Reference)
```python
import numpy as np

def verify_face_cosine_similarity(live_vec: list, profile_vec: list, threshold: float = 0.72) -> tuple[bool, float]:
    """Tính Cosine Similarity giữa 2 vector đặc trưng khuôn mặt 128 chiều."""
    u = np.array(live_vec, dtype=np.float32)
    v = np.array(profile_vec, dtype=np.float32)
    norm_u = np.linalg.norm(u)
    norm_v = np.linalg.norm(v)
    if norm_u == 0 or norm_v == 0:
        return False, 0.0
    cosine_sim = float(np.dot(u, v) / (norm_u * norm_v))
    return (cosine_sim >= threshold), round(cosine_sim, 4)
```

### 11.3. Cổng Gác Khóa Work Order Phía Máy Chủ (Backend Gatekeeper)
```python
from datetime import timedelta
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

def check_work_order_attendance_gatekeeper(work_order, user, enable_geofencing=True):
    cutoff = timezone.now() - timedelta(minutes=15)
    
    # Kiểm tra bản ghi điểm danh hợp lệ trong 15 phút gần nhất
    has_valid_attendance = AttendanceLog.objects.filter(
        work_order=work_order,
        technician=user,
        is_face_verified=True,
        is_location_verified=True,
        created_at__gte=cutoff
    ).exists()

    if not has_valid_attendance:
        return Response({
            "success": False,
            "error": {
                "code": "COMPLIANCE_ATTENDANCE_REQUIRED",
                "message": "Yêu cầu điểm danh sinh trắc học hợp lệ trong vòng 15 phút gần nhất trước khi bắt đầu."
            }
        }, status=status.HTTP_403_FORBIDDEN)
    return None
```

---

## 12. Kế Hoạch Triển Khai & Nghiệm Thu (Implementation Checklist)

- [ ] **Task 11.7.1 — Biometric Schema & Decree 13 Compliance**
  - [ ] Xây dựng bảng `BiometricProfile` lưu vector 128-d (`ArrayField(Float)`).
  - [ ] Xây dựng bảng `AttendanceLog` lưu lịch sử điểm danh bất biến.
  - [ ] Thiết lập lưu trữ ảnh hiện trường mã hóa AES-256 trên MinIO.
- [ ] **Task 11.7.2 — Haversine Spatial Geofencing & Flexible Toggle**
  - [ ] Cài đặt công thức tính khoảng cách Haversine chính xác với bán kính 50m.
  - [ ] Cài đặt cờ cấu hình Tenant `ENABLE_GEOFENCING` (cho phép bỏ qua GPS cho doanh nghiệp không dùng vị trí).
  - [ ] Xây dựng cơ chế dự phòng quét mã QR thân vỏ máy khi sóng GPS suy giảm trong nhà xưởng kín.
- [ ] **Task 11.7.3 — Mobile Edge AI & MobileFaceNet Integration**
  - [ ] Nhúng mô hình `mobilefacenet.tflite` vào ứng dụng Flutter di động.
  - [ ] Tích hợp Google ML Kit Face Detection để chuẩn hóa bounding box $112 \times 112$.
  - [ ] Khóa tính năng chọn ảnh từ thư viện, bắt buộc dùng luồng camera trực tiếp kèm cử động sống cơ bản.
- [ ] **Task 11.7.4 — Backend 15-Minute Compliance Gatekeeper**
  - [ ] Tích hợp cổng kiểm tra điểm danh 15 phút vào endpoint `PATCH /work-orders/{id}/start/`.
  - [ ] Xây dựng API điểm danh `POST /api/v1/attendance/check-in/`.
- [ ] **Task 11.7.5 — Mobile UI & Test Matrix Verification**
  - [ ] Thiết kế màn hình quét sinh trắc học với khung reticle đổi màu và radar GPS (tự ẩn khi tắt định vị).
  - [ ] Triển khai bộ kiểm thử tự động 12 test cases (`TC-BIO-01` đến `TC-BIO-12`).

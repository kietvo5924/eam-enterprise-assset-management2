# Thiết Kế Hệ Thống & Đặc Tả Kỹ Thuật: Task 10.2 — Executive Dashboard KPIs & Analytics Engine

Tài liệu này xác định kiến trúc kỹ thuật, công thức tính toán chỉ số, thiết kế tầng dịch vụ (Service Layer), cơ chế lưu đệm siêu tốc (Redis Caching), quy chuẩn hiển thị UI/UX và **bộ kịch bản kiểm thử chấp nhận & trường hợp biên (Acceptance Criteria & Edge Cases)** dành cho **Bảng Điều Khiển Tổng Hợp (Executive Dashboard)** của hệ thống Quản lý Tài sản Doanh nghiệp (EAM).

Tài liệu đóng vai trò là **Đặc Tả Kỹ Thuật & Chuẩn Kiểm Thử (Technical Specification & Audit Baseline)** nhằm đối chiếu, rà soát và thực thi trọn vẹn toàn bộ tính năng mà không bị thiếu sót bất kỳ nghiệp vụ enterprise nào.

---

## 1. Mục Tiêu & Phạm Vi (Objective & Scope)

Khác với phân hệ Báo cáo phân tích chuyên sâu (Reports - 10.3), **Executive Dashboard** là màn hình trung tâm của Lãnh đạo, Giám đốc Nhà máy và Quản lý bảo trì với các mục tiêu:
- **Tức thời (Immediate Visibility)**: Nắm bắt toàn bộ "nhịp tim" vận hành của nhà xưởng ngay khi mở màn hình trong vòng $< 50\text{ms}$.
- **Tối ưu tốc độ phản hồi**: Sử dụng cơ chế lưu đệm (Caching) cho toàn bộ chỉ số tổng hợp, loại bỏ việc quét toàn bộ cơ sở dữ liệu mỗi lần tải trang, đồng thời chống nghẽn đồng thời (Cache Stampede).
- **Chính xác & Minh bạch**: Số liệu phản ánh đúng thực tế vận hành và xử lý triệt để mọi trường hợp biên (dữ liệu rỗng, phép chia cho 0, ngày nghỉ lễ/cuối tuần, múi giờ ranh giới, dữ liệu ngoại lai).
- **Nhất quán tương tác (Drill-Down Consistency)**: Mọi số liệu trên thẻ KPI đều có thể nhấp chuột để điều hướng chính xác đến danh sách thực thể tương ứng mà không bị vênh số lượng.

---

## 2. Ràng Buộc Kế Thừa Hệ Thống (Existing System Constraints & Codebase Reuse)

- **Tái Sử Dụng Mô Hình Multi-Tenancy**: Toàn bộ dữ liệu tính toán thống kê kế thừa từ `BaseTenantModel` và được cô lập qua `TenantManager`, bảo đảm dữ liệu truy vấn luôn được đóng khung chặt chẽ theo `tenant_id` của phiên làm việc hiện tại.
- **Tái Sử Dụng Thực Thể Nghiệp Vụ Có Sẵn**:
  - `Asset`: Lấy thông tin trạng thái vận hành (`status` thuộc `OPERATING`, `MAINTENANCE`, `DOWN`) và cờ theo dõi (`is_trackable`).
  - `WorkOrder`: Lấy thông tin trạng thái (`status`), loại phiếu (`type`), ngày tạo (`created_at`), hạn chót (`due_date`), ngày hoàn thành (`completed_at`) và thời gian thực tế (`actual_duration_hours`).
  - `AuditLog`: Lấy dòng nhật ký hoạt động hệ thống đã có sẵn từ `core.models`.
- **Tái Sử Dụng Cấu Trúc Response**: Mọi endpoint API phải trả về dữ liệu được bọc trong hàm chuẩn hóa `success_response` của dự án.

---

## 3. Yêu Cầu Nghiệp Vụ & Quy Tắc Cốt Lõi (Business Requirements & Core Rules)

Toàn bộ logic tính toán thống kê trên Dashboard phải tuân thủ nghiêm ngặt 10 quy tắc nghiệp vụ phòng thủ sau:

### Quy Tắc 1: Phạm Vi Phân Cấp Tài Sản & Chuẩn Hóa Tỷ Lệ Vận Hành (Asset Lifecycle & Rounding Guardrail)
- **Điểm Yếu Nghiệp Vụ**:
  - Trong mô hình cây tài sản, một dây chuyền lớn chứa nhiều máy con và linh kiện nhỏ. Nếu đếm đơn thuần `Asset.objects.count()`, số lượng sẽ bị đội lên do tính cả linh kiện phụ tùng nhỏ nhặt.
  - Các tài sản đã thanh lý (`SCRAPPED`), đã bán (`DISPOSED`), ngừng sử dụng (`DECOMMISSIONED`) hoặc bản nháp (`DRAFT`) nếu bị tính vào mẫu số sẽ làm sai lệch tỷ lệ khả dụng của nhà máy.
  - Khi chia phần trăm ra số thập phân (ví dụ: $33.333\% \times 3$), hàm làm tròn thông thường sẽ tạo tổng phần trăm bằng $99.9\%$ hoặc $100.1\%$, gây lỗi hiển thị trên giao diện biểu đồ tròn/thanh phân bổ.
- **Quy Tắc Bắt Buộc**:
  1. Chỉ thống kê các thiết bị độc lập có thể theo dõi vận hành: `is_trackable = True` và có trạng thái `status IN ('OPERATING', 'MAINTENANCE', 'DOWN')`.
  2. Loại trừ tuyệt đối các tài sản có trạng thái vòng đời kết thúc hoặc không khả dụng: `status IN ('DRAFT', 'DECOMMISSIONED', 'SCRAPPED', 'DISPOSED', 'LOST', 'SOLD')`.
  3. Áp dụng thuật toán chia tỷ lệ phần dư lớn nhất (**Largest Remainder Method / Hamilton-Hare**) để đảm bảo tổng ba tỷ lệ (`Operating`, `Maintenance`, `Down`) luôn luôn đạt chính xác **$100.0\%$** trên giao diện người dùng.

### Quy Tắc 2: An Toàn Phép Tính MTBF / MTTR & Tách Biệt Phiếu PM (Preventive Filtering & Zero-Division Guardrail)
- **Điểm Yếu Nghiệp Vụ**:
  - Khi nhà máy vận hành hoàn hảo không có sự cố nào trong kỳ đánh giá ($N_{\text{failures}} = 0$), phép tính MTBF và MTTR sẽ gặp lỗi chia cho 0 (`ZeroDivisionError`) gây sập trang.
  - **Biến dạng MTBF do phiếu bảo trì định kỳ (PM)**: Nếu đưa nhầm cả phiếu bảo trì phòng ngừa (`PREVENTIVE`) vào mẫu số số lần hỏng hóc, nhà máy càng bảo dưỡng phòng ngừa thường xuyên (ví dụ 50 phiếu PM) thì MTBF tính ra sẽ càng tụt thê thảm, báo cáo sai lệch rằng máy móc hỏng liên tục.
- **Quy Tắc Bắt Buộc**:
  1. **Tuyệt đối loại trừ phiếu bảo trì định kỳ (`type == 'PREVENTIVE'`) khỏi mẫu số số lần hỏng hóc**. Chỉ tính toán trên các phiếu sự cố kỹ thuật thực tế: `type IN ('CORRECTIVE', 'EMERGENCY', 'BREAKDOWN')`.
  2. Khi số lần sự cố trong kỳ bằng 0 ($N_{\text{failures}} = 0$), trường `mtbf_hours` và `mttr_hours` phải trả về giá trị `null` và giao diện hiển thị nhãn trạng thái `"100% Khả dụng (0 Sự cố)"`. Không được phép phát sinh lỗi chia cho 0 và không trả về số 0 giả tạo.

### Quy Tắc 3: Bù Dữ Liệu Biểu Đồ Chuỗi Thời Gian Liên Tục (Zero-Filling Time-Series Guardrail)
- **Điểm Yếu Nghiệp Vụ**: Khi gom nhóm dữ liệu theo ngày phát sinh, những ngày nghỉ cuối tuần hoặc ngày lễ không có Work Order nào được tạo hoặc hoàn thành sẽ bị cơ sở dữ liệu bỏ qua. Nếu đưa trực tiếp dữ liệu này lên biểu đồ, trục thời gian sẽ bị nhảy cóc, làm đứt gãy hoặc thu hẹp trục X của biểu đồ.
- **Quy Tắc Bắt Buộc**:
  1. Tầng dịch vụ phải luôn khởi tạo khung mảng đủ 30 ngày liên tục tính ngược từ ngày hiện tại.
  2. Ánh xạ kết quả truy vấn thực tế vào khung 30 ngày. Những ngày không có dữ liệu bắt buộc gán giá trị mặc định bằng 0 (`created: 0, completed: 0`).

### Quy Tắc 4: Tách Biệt Độc Lập Ngày Phát Sinh vs Ngày Hoàn Thành (Cross-Period Completion Guardrail)
- **Điểm Yếu Nghiệp Vụ**: Kỹ thuật viên nhận một Work Order từ tháng trước (ví dụ ngày 28/07) nhưng đến tháng này (ví dụ ngày 05/08) mới hoàn thành. Nếu chỉ truy vấn gom nhóm theo ngày tạo thì công sức giải quyết phiếu này bị biến mất khỏi biểu đồ tháng hiện tại, làm méo mó năng suất giải tỏa khối lượng công việc.
- **Quy Tắc Bắt Buộc**:
  1. Tách bạch thành hai luồng truy vấn gom nhóm độc lập:
     - Chuỗi việc tạo mới (`Created Series`): Lọc theo ngày tạo (`created_at`) trong 30 ngày qua.
     - Chuỗi việc hoàn tất (`Completed Series`): Lọc theo ngày hoàn thành (`completed_at`) trong 30 ngày qua.
  2. Biểu đồ đường của thẻ Created sẽ ghi nhận ở ngày 28/07, và đường của thẻ Completed sẽ ghi nhận vào đúng ngày 05/08.

### Quy Tắc 5: Bộ Lọc Nhật Ký Hoạt Động Điều Hành (Activity Feed Whitelist Guardrail)
- **Điểm Yếu Nghiệp Vụ**: Bảng ghi nhận kiểm toán (`AuditLog`) lưu tất cả thao tác của người dùng (đổi mật khẩu, xem báo cáo, chỉnh sửa profile cá nhân, GET API). Nếu đưa toàn bộ bảng này lên Activity Feed, màn hình sẽ ngập tràn nhật ký rác (Noise) và che lấp các sự cố vận hành then chốt.
- **Quy Tắc Bắt Buộc**:
  1. Áp dụng danh sách trắng (Whitelist) các loại sự kiện mang tính tác động vận hành:
     - Biến động công việc: `WO_CREATED`, `WO_ASSIGNED`, `WO_COMPLETED`.
     - Biến động thiết bị: `ASSET_STATUS_DOWN`, `ASSET_RESTORED`.
     - Biến động tồn kho: `SPARE_PART_LOW_STOCK`.
  2. Loại bỏ hoàn toàn các sự kiện truy cập dữ liệu (`GET`), quản trị người dùng, đổi mật khẩu và cập nhật hồ sơ cá nhân.

### Quy Tắc 6: Chuẩn Hóa Múi Giờ Ranh Giới Nửa Đêm (Timezone Midnight Boundary Guardrail)
- **Điểm Yếu Nghiệp Vụ**: PostgreSQL lưu `timestamptz` theo UTC. Một kỹ thuật viên bấm hoàn thành phiếu lúc 01:30 AM ngày 01/08 tại Việt Nam (UTC+7), nhưng tại UTC thời điểm đó mới là 18:30 ngày 31/07. Nếu dùng `DATE_TRUNC('day', completed_at)` thông thường không chuyển đổi múi giờ, phiếu sẽ bị tụt về tháng trước, gây lệch số liệu giữa Dashboard và báo cáo bàn giao ca.
- **Quy Tắc Bắt Buộc**:
  1. Mọi phép gom nhóm thời gian trong truy vấn ORM/SQL bắt buộc phải chuyển đổi theo múi giờ địa phương của Tenant:
     `DATE_TRUNC('day', completed_at AT TIME ZONE tenant_timezone)`.
  2. Khung 30 ngày của Zero-filling phải tính từ 00:00:00 đến 23:59:59 theo múi giờ Tenant.

### Quy Tắc 7: Cách Ly Sự Cố Đang Xử Lý Dở Dang (Ongoing Unresolved Downtime Isolation)
- **Điểm Yếu Nghiệp Vụ**: Thiết bị gặp sự cố dừng máy từ hôm qua và hiện đang được khắc phục (`status = IN_PROGRESS`, chưa có `completed_at` và chưa chốt `actual_duration_hours`). Nếu tính nhầm phiếu chưa hoàn tất này vào MTTR sẽ gây lỗi hoặc sai lệch thời gian sửa trung bình.
- **Quy Tắc Bắt Buộc**:
  1. **MTTR chỉ được tính toán trên các sự cố ĐÃ HOÀN THÀNH** (`status == 'COMPLETED'` và có `actual_duration_hours` hợp lệ).
  2. Thiết bị đó **vẫn được tính là DOWN** trên biểu đồ Asset Health, đồng thời API trả về chỉ số `ongoingDownCount` để giao diện hiển thị cảnh báo trực quan cho Quản lý.

### Quy Tắc 8: Lọc Dữ Liệu Thời Gian Ngoại Lai & Dị Thường (Anomalous Duration / Outlier Guardrail)
- **Điểm Yếu Nghiệp Vụ**: Kỹ thuật viên sửa xong máy trong 2 giờ nhưng quên bấm "Hoàn thành" trên app, 2 tháng sau (1,440 giờ) mới bấm hoàn thành; hoặc do đồng hồ thiết bị client bị lệch dẫn đến `completed_at < created_at` (thời gian âm). Nếu đưa con số 1,440 giờ vào MTTR, chỉ số của cả nhà máy sẽ bị phá hỏng hoàn toàn.
- **Quy Tắc Bắt Buộc**:
  1. Loại trừ các phiếu có `actual_duration_hours <= 0`.
  2. Thiết lập ngưỡng trần ngoại lai: Các phiếu sửa chữa có thời lượng thực tế vượt quá 168 giờ (1 tuần) sẽ bị loại khỏi mẫu số MTTR tiêu chuẩn và gắn nhãn cảnh báo ngoại lai (`is_outlier = True`).

### Quy Tắc 9: An Toàn Tính Toán Biến Động Kỳ Trước (Safe Delta Calculation Guardrail)
- **Điểm Yếu Nghiệp Vụ**: Khi tính toán tỷ lệ tăng/giảm so với kỳ trước $\Delta \% = \frac{\text{Current} - \text{Previous}}{\text{Previous}} \times 100\%$, nếu tổ chức mới hoạt động (tháng đầu) hoặc tháng trước có giá trị bằng 0 (ví dụ 0 sự cố), công thức sẽ phát sinh lỗi chia cho 0 hoặc hiển thị vô cực ($\infty\%$).
- **Quy Tắc Bắt Buộc**:
  1. Nếu `Previous == 0`, hệ thống hiển thị số lượng thay đổi tuyệt đối kèm nhãn `"Kỳ đầu / Mới"` thay vì cố tính toán phần trăm.
  2. Đảm bảo cấu trúc dữ liệu trả về luôn có `delta`, `deltaType` (`positive`, `negative`, `neutral`) và `deltaLabel`.

### Quy Tắc 10: Chống Nghẽn Bộ Đệm & Fallback An Toàn (Cache Stampede & Graceful Fallback)
- **Điểm Yếu Nghiệp Vụ**: Khi khóa Redis 5 phút hết hạn vào 8:00 sáng (lúc toàn bộ quản lý đăng nhập ca sáng), hàng chục request đồng thời cùng đổ vào DB để tính toán lại toàn bộ KPI phức tạp, gây quá tải cơ sở dữ liệu. Đồng thời, nếu Redis bị ngắt kết nối, trang Dashboard không được phép sập.
- **Quy Tắc Bắt Buộc**:
  1. Áp dụng cơ chế **Redis Mutex Lock** hoặc cơ chế chạy ngầm cập nhật trước khi hết hạn (Pre-warming qua Celery Beat).
  2. Bọc an toàn mọi thao tác gọi Redis. Khi dịch vụ bộ đệm tạm ngắt kết nối, tự động Fallback truy vấn trực tiếp DB chính mà không trả về lỗi HTTP 500.

---

## 4. Yêu Cầu Chức Năng & Luồng Xử Lý (Functional Requirements & Workflows)

### 4.1. Bốn Thẻ Chỉ Số Trọng Yếu (KPI Cards) & Drill-Down
- **Tổng tài sản quản lý (`totalAssets`)**: Số lượng thiết bị đang hoạt động thuộc phạm vi quản lý, kèm độ tăng giảm so với kỳ trước.
  - *Drill-Down Link*: `/portal/assets/?status=OPERATING,MAINTENANCE,DOWN&is_trackable=true`
- **Phiếu đang xử lý (`activeWorkOrders`)**: Số lượng Work Order chưa hoàn thành (`status IN ('CREATED', 'ASSIGNED', 'IN_PROGRESS')`).
  - *Drill-Down Link*: `/portal/work-orders/?status=CREATED,ASSIGNED,IN_PROGRESS`
- **Phiếu hoàn tất 30 ngày (`completedWorkOrders`)**: Tổng số Work Order đã hoàn tất trong vòng 30 ngày gần nhất.
  - *Drill-Down Link*: `/portal/work-orders/?status=COMPLETED&period=30d`
- **Độ sẵn sàng vận hành (`plantAvailability`)**: Tỷ lệ phần trăm giữa thời gian hoạt động và tổng thời gian khả dụng theo công thức:
  $$\text{Availability (\%)} = \frac{\text{MTBF}}{\text{MTBF} + \text{MTTR}} \times 100\%$$
  *(Nếu không có sự cố nào trong kỳ, độ sẵn sàng mặc định đạt $100.0\%$).*
- **Chỉ số phụ: Tỷ lệ tuân thủ bảo trì định kỳ (`pmComplianceRate`)**:
  $$\text{PM Compliance (\%)} = \frac{\text{Số phiếu PM hoàn thành đúng hạn (trước due\_date)}}{\text{Tổng số phiếu PM đến hạn trong 30 ngày}} \times 100\%$$

### 4.2. Cơ Cấu Phân Bổ Sức Khỏe Thiết Bị (Asset Health Distribution)
- Tính toán số lượng và tỷ lệ phần trăm phân bổ:
  - $\% \text{Operating}$: Tỷ lệ thiết bị đang hoạt động bình thường.
  - $\% \text{Maintenance}$: Tỷ lệ thiết bị đang bảo trì theo kế hoạch.
  - $\% \text{Down}$: Tỷ lệ thiết bị đang dừng hoạt động do sự cố.
- **Quy tắc làm tròn**: Bắt buộc dùng thuật toán Hamilton-Hare để tổng $3$ phần trăm luôn đạt chính xác $100.0\%$.
- **Nhãn trạng thái tổng thể nhà máy (Plant Status)**:
  - **Tối ưu (Optimal)**: $\% \text{Down} == 0\%$ và $\% \text{Operating} \ge 90\%$.
  - **Bình thường (Normal)**: $0\% < \% \text{Down} \le 5\%$.
  - **Cần chú ý (Warning)**: $5\% < \% \text{Down} \le 15\%$.
  - **Báo động (Critical)**: $\% \text{Down} > 15\%$.

### 4.3. Chỉ Số Độ Tin Cậy & Sửa Chữa (MTBF & MTTR Metrics)
- **MTBF (Mean Time Between Failures)**:
  $$\text{MTBF (Giờ)} = \frac{\text{Tổng thời gian hoạt động thực tế của toàn bộ máy trong kỳ}}{\text{Số lượng sự cố đột xuất (Breakdown/Emergency Work Orders)}}$$
- **MTTR (Mean Time To Repair)**:
  $$\text{MTTR (Giờ)} = \frac{\text{Tổng thời gian khắc phục các sự cố đã hoàn thành (không tính outlier)}}{\text{Số lượng sự cố đã khắc phục xong}}$$
- **Cách ly Ongoing Down**: Cung cấp trường `ongoingDownCount` cho các sự cố chưa giải quyết xong.

### 4.4. Biểu Đồ Xu Hướng Khối Lượng & Giải Quyết Công Việc 30 Ngày (Work Order Trends)
- Xuất mảng 30 ngày liên tục theo Local Timezone chứa hai chuỗi dữ liệu độc lập: Số lượng tạo mới (`created`) và Số lượng hoàn tất (`completed`), tự động bù đắp 0 cho các ngày không có phát sinh.

### 4.5. Dòng Hoạt Động Vận Hành Trực Tiếp (Executive Activity Feed)
- Trả về danh sách 5 đến 10 sự kiện vận hành quan trọng gần nhất (đã lọc qua Whitelist), kèm thời gian tương đối thân thiện và liên kết điều hướng an toàn tới thực thể.

---

## 5. Quy Tắc Bảo Mật, Phân Quyền & Đa Khách Hàng (Security, RBAC & Multi-Tenant Rules)

- **Cô Lập Đa Khách Hàng (Multi-Tenancy Scoping)**:
  - Mọi câu lệnh truy vấn số liệu và khóa lưu đệm phải gắn liền với `tenant_id` của người dùng hiện tại.
  - Không cho phép bất kỳ tham số nào trên URL ghi đè hoặc thay đổi phạm vi tenant.
- **Phân Quyền Theo Vai Trò (RBAC Scoping)**:
  - `TENANT_ADMIN` & `MAINTENANCE_MANAGER`: Toàn quyền xem đầy đủ số liệu KPI tài chính, độ sẵn sàng và danh sách hoạt động toàn xưởng.
  - `TECHNICIAN`: Chỉ xem các chỉ số liên quan đến công việc cá nhân được phân công, không truy cập các số liệu chiến lược cấp quản trị.

---

## 6. Kiến Trúc & Luồng Dữ Liệu (Architecture & Data Flow)

```
[Người Dùng Mở Executive Dashboard]
          │
          ▼
[API View: GET /api/v1/dashboard/summary/] ──► Kiểm tra xác thực & Ngữ cảnh Tenant
          │
          ├───► [Kiểm Tra Bộ Đệm Redis] (Tenant-Scoped Cache)
          │       ├── Nếu CÓ Dữ Liệu ──► Trả về ngay lập tức (< 50ms)
          │       └── Nếu CHƯA CÓ hoặc LỖI ──► Dùng Redis Mutex Lock chống Stampede
          │
          ▼
[Dashboard Service Layer]
  ├── (1) Tính tỷ lệ tài sản (Lọc trackable, loại trừ scrapped/disposed, chia phần dư 100%)
  ├── (2) Tính MTBF & MTTR (Lọc loại PM, loại outlier > 168h, bọc an toàn chia cho 0, tách ongoing)
  ├── (3) Bù khuyết chuỗi ngày 30 ngày (Zero-filling theo Local Timezone)
  ├── (4) Tính tỷ lệ tuân thủ PM đúng hạn (PM Compliance SLA)
  └── (5) Lọc sự kiện vận hành quan trọng (Activity Feed Whitelist)
          │
          ▼
[Lưu Kết Quả Vào Bộ Đệm] (TTL 5 phút, giải phóng Mutex Lock)
          │
          ▼
[Client Render] ──► Hiển thị KPI Cards (có Drill-Down link), Biểu đồ động & Activity Feed
```

---

## 7. Mô Hình Dữ Liệu & Chỉ Mục Tối Ưu (Data Model & Schema)

Chức năng sử dụng dữ liệu tổng hợp từ các bảng cơ sở dữ liệu hiện có:
- **Bảng `assets`**: Khóa ngoại `tenant_id`, trường `status`, `is_trackable`.
- **Bảng `work_orders`**: Khóa ngoại `tenant_id`, trường `status`, `type`, `created_at`, `due_date`, `completed_at`, `actual_duration_hours`.
- **Bảng `audit_logs`**: Khóa ngoại `tenant_id`, trường `action`, `entity_name`, `entity_id`, `created_at`, `details`.

Chỉ mục cơ sở dữ liệu quan trọng phục vụ tốc độ truy vấn:
- `assets`: Index ghép `[tenant_id, is_trackable, status]`.
- `work_orders`: Index ghép `[tenant_id, status, type, created_at]`.
- `work_orders`: Index ghép `[tenant_id, completed_at]`.
- `audit_logs`: Index ghép `[tenant_id, created_at DESC]`.

---

## 8. Đặc Tả Giao Diện Lập Trình (API Specifications & Contracts)

### 8.1. `GET /api/v1/dashboard/summary/`
Trả về toàn bộ số liệu 4 thẻ KPI, Tỷ lệ sức khỏe thiết bị, MTBF/MTTR, PM Compliance và đường dẫn Drill-Down.

**Cấu trúc dữ liệu trả về**:
```json
{
  "success": true,
  "data": {
    "kpis": {
      "totalAssets": {
        "value": 142,
        "delta": "+8",
        "deltaType": "positive",
        "deltaLabel": "so với tháng trước",
        "label": "Thiết bị đang quản lý",
        "drillDownUrl": "/portal/assets/?status=OPERATING,MAINTENANCE,DOWN&is_trackable=true"
      },
      "activeWorkOrders": {
        "value": 7,
        "delta": "-2",
        "deltaType": "positive",
        "deltaLabel": "so với hôm qua",
        "label": "Phiếu đang xử lý",
        "drillDownUrl": "/portal/work-orders/?status=CREATED,ASSIGNED,IN_PROGRESS"
      },
      "completedWorkOrders": {
        "value": 58,
        "delta": "+12",
        "deltaType": "positive",
        "deltaLabel": "so với 30 ngày trước",
        "label": "Phiếu hoàn tất (30 ngày)",
        "drillDownUrl": "/portal/work-orders/?status=COMPLETED&period=30d"
      },
      "plantAvailability": {
        "value": "98.9%",
        "delta": "+0.3%",
        "deltaType": "positive",
        "deltaLabel": "so với tháng trước",
        "label": "Độ sẵn sàng vận hành",
        "drillDownUrl": null
      },
      "pmComplianceRate": {
        "value": "95.2%",
        "delta": "+2.1%",
        "deltaType": "positive",
        "deltaLabel": "so với tháng trước",
        "label": "Tuân thủ bảo trì định kỳ",
        "drillDownUrl": "/portal/work-orders/?type=PREVENTIVE&period=30d"
      }
    },
    "assetHealth": {
      "totalActive": 142,
      "operating": { "count": 125, "percentage": 88.0 },
      "maintenance": { "count": 14, "percentage": 10.0 },
      "down": { "count": 3, "percentage": 2.0 },
      "plantStatus": "NORMAL",
      "plantStatusLabel": "Bình thường"
    },
    "reliability": {
      "mtbfHours": 182.4,
      "mtbfDisplay": "182.4 giờ / sự cố",
      "isZeroFailure": false,
      "mttrHours": 1.6,
      "mttrDisplay": "1.6 giờ",
      "ongoingDownCount": 1
    }
  }
}
```

### 8.2. `GET /api/v1/dashboard/trends/`
Trả về mảng 30 ngày liên tục (được ánh xạ theo Local Timezone của Tenant) phục vụ vẽ biểu đồ Created vs Completed.

**Cấu trúc dữ liệu trả về**:
```json
{
  "success": true,
  "data": {
    "timezone": "Asia/Ho_Chi_Minh",
    "series": [
      { "date": "18/08", "created": 2, "completed": 1 },
      { "date": "19/08", "created": 0, "completed": 0 },
      { "date": "28/07", "created": 1, "completed": 0 },
      { "date": "05/08", "created": 0, "completed": 1 },
      { "date": "16/09", "created": 1, "completed": 2 }
    ]
  }
}
```

### 8.3. `GET /api/v1/dashboard/activity-feed/`
Trả về danh sách các sự kiện vận hành quan trọng gần nhất (đã lọc Whitelist).

**Cấu trúc dữ liệu trả về**:
```json
{
  "success": true,
  "data": {
    "activities": [
      {
        "id": "act-01",
        "eventType": "WO_COMPLETED",
        "title": "WO-2026-088 Hoàn tất",
        "description": "Bảo dưỡng máy CNC phay hoàn tất bởi Nguyễn Minh.",
        "timeAgo": "25 phút trước",
        "timestamp": "2026-09-16T22:15:00Z",
        "link": "/portal/work-orders/wo-088/"
      }
    ]
  }
}
```

---

## 9. Đặc Tả Trải Nghiệm Người Dùng (UI/UX Behavioral Specifications)

- **Hành vi hiển thị thẻ KPI**:
  - Mỗi thẻ hiển thị giá trị hiện tại, nhãn định danh và chỉ số biến động an toàn so với kỳ trước.
  - Khi người dùng nhấp vào thẻ KPI, hệ thống điều hướng trực tiếp đến trang danh sách tương ứng với bộ lọc đã được chuẩn hóa sẵn (`drillDownUrl`).
  - Khi dữ liệu bằng 0, hiển thị số 0 rõ ràng, không hiển thị khoảng trắng hoặc dấu gạch ngang lỗi.
- **Hành vi hiển thị sức khỏe thiết bị**:
  - Thanh phân bổ hiển thị 3 phần tỷ lệ trực quan tương ứng với 3 trạng thái (`Operating`, `Maintenance`, `Down`).
  - Tổng của 3 tỷ lệ luôn luôn đạt $100.0\%$ (không xảy ra lỗi $99.9\%$ hay $100.1\%$).
  - Hiển thị nhãn trạng thái tổng thể của nhà máy tương ứng với mức độ khả dụng.
- **Hành vi tương tác dòng hoạt động**:
  - Hiển thị thời gian tương đối thân thiện (ví dụ: "Vừa xong", "15 phút trước", "Hôm qua").
  - Cho phép người dùng nhấp vào từng dòng hoạt động để điều hướng an toàn tới trang chi tiết của đối tượng.
- **Hành vi biểu đồ**:
  - Trục thời gian luôn hiển thị đầy đủ 30 ngày liên tục, không nhảy cóc ngày nghỉ.

---

## 10. Tiêu Chí Chấp Nhận & Ma Trận Kịch Bản Kiểm Thử (Acceptance Criteria & Test Matrix)

Dưới đây là bảng ma trận kiểm thử chi tiết hóa toàn bộ 17 kịch bản chấp nhận và trường hợp biên (Edge Cases):

### 10.1. Ma Trận Kịch Bản Nghiệp Vụ & Dữ Liệu Biên

- [ ] **TC-DASH-01: Tenant rỗng chưa có dữ liệu (Empty State)**
  - *Mô tả*: Một tổ chức mới tạo chưa có tài sản hoặc công việc nào.
  - *Kỳ vọng*: Dashboard tải bình thường; các thẻ KPI hiển thị `0`; tỷ lệ hiển thị `0%`; MTBF/MTTR hiển thị `"N/A"`; biểu đồ trả về 30 ngày đều có giá trị `0`.

- [ ] **TC-DASH-02: Bảo toàn giá trị khi 100% không có sự cố (Zero-Division Safe)**
  - *Mô tả*: Nhà máy hoạt động bình thường, không có bất kỳ Work Order sự cố đột xuất nào trong 30 ngày qua ($N_{\text{failures}} = 0$).
  - *Kỳ vọng*: Không xảy ra lỗi chia cho 0; MTBF/MTTR trả về `null`; nhãn hiển thị `"100% Khả dụng (0 Sự cố)"`; độ sẵn sàng vận hành đạt $100.0\%$.

- [ ] **TC-DASH-03: Biến động vòng đời tài sản (Asset Lifecycle Filtering)**
  - *Mô tả*: Tổ chức có 10 máy đang chạy (`OPERATING`), 2 máy dừng (`DOWN`), và công ty thanh lý 50 thiết bị cũ (`SCRAPPED` / `DISPOSED`).
  - *Kỳ vọng*: Tự động loại bỏ 50 thiết bị thanh lý khỏi biến `totalAssets`. Mẫu số tính toán chỉ là $10 + 2 = 12$ máy; 50 máy thanh lý bị loại bỏ hoàn toàn khỏi phân bổ tỷ lệ.

- [ ] **TC-DASH-04: Bù lấp dữ liệu những ngày nghỉ (Zero-filling Time-series)**
  - *Mô tả*: Nhà máy nghỉ cuối tuần (Thứ 7, Chủ Nhật) không phát sinh Work Order nào. Trong 30 ngày qua chỉ có 3 ngày có phát sinh công việc.
  - *Kỳ vọng*: Dữ liệu trả về đủ 30 điểm ngày liên tục; các ngày không có việc đều có giá trị `{ created: 0, completed: 0 }`; trục X của biểu đồ không bị gãy hoặc thu hẹp.

- [ ] **TC-DASH-05: Khả năng hoạt động khi dịch vụ bộ đệm gián đoạn (Graceful Cache Fallback)**
  - *Mô tả*: Dịch vụ Redis bị ngắt kết nối hoặc tràn bộ nhớ.
  - *Kỳ vọng*: Hệ thống tự động chuyển tiếp (Fallback) truy vấn trực tiếp cơ sở dữ liệu; trang tải thành công bình thường và không trả về lỗi HTTP 500.

- [ ] **TC-DASH-06: Làm mới bộ đệm theo sự kiện (Event Invalidation Signals)**
  - *Mô tả*: Một máy móc chuyển sang trạng thái dừng khẩn cấp (`DOWN`).
  - *Kỳ vọng*: Gọi lại Dashboard ngay lập tức số máy `Down` tăng lên tương ứng mà không phải chờ hết thời gian sống 5 phút của bộ đệm.

- [ ] **TC-DASH-07: Cách ly dữ liệu giữa hai tổ chức độc lập (Multi-Tenant Isolation)**
  - *Mô tả*: Người dùng thuộc Tenant A và Tenant B cùng truy cập Dashboard.
  - *Kỳ vọng*: Toàn bộ số liệu KPI, biểu đồ và dòng hoạt động hoàn toàn tách biệt theo từng `tenant_id`.

- [ ] **TC-DASH-08: MTBF & MTTR bị biến dạng do phiếu bảo trì phòng ngừa (PM Exclusion)**
  - *Mô tả*: Tháng này nhà máy thực hiện 50 phiếu bảo trì định kỳ (`type == 'PREVENTIVE'`) và chỉ có 1 phiếu sửa chữa khẩn cấp (`type == 'EMERGENCY'`).
  - *Kỳ vọng*: Khi tính MTBF và MTTR, hệ thống bắt buộc loại trừ 50 phiếu PM khỏi mẫu số số lần hỏng hóc. Mẫu số $N_{\text{failures}}$ phải bằng đúng 1, không được đưa 50 phiếu PM vào làm giảm thê thảm MTBF.

- [ ] **TC-DASH-09: Chồng lấn thời gian hoàn thành công việc (Cross-period Completion)**
  - *Mô tả*: Kỹ thuật viên nhận 1 Work Order từ tháng trước (ngày 28/07) nhưng đến tháng này (ngày 05/08) mới hoàn thành.
  - *Kỳ vọng*: Trên biểu đồ xu hướng 30 ngày, điểm của đường Created ghi nhận tại ngày 28/07, còn điểm của đường Completed ghi nhận vào đúng ngày 05/08. Không bị bỏ quên phiếu khỏi năng suất của tháng hoàn thành.

- [ ] **TC-DASH-10: Làm tròn tỷ lệ phần trăm phân bổ tài sản (Rounding Percentage Gap)**
  - *Mô tả*: Tổ chức có 3 máy: 1 máy Operating, 1 máy Maintenance, 1 máy Down. Tỷ lệ thô tính ra là $33.333\%$, $33.333\%$, $33.333\%$.
  - *Kỳ vọng*: Dashboard áp dụng thuật toán phần dư lớn nhất (Largest Remainder) để làm tròn thành $33.4\%$, $33.3\%$, $33.3\%$. Tổng 3 trạng thái trên biểu đồ luôn tuyệt đối bằng $100.0\%$, không xảy ra lỗi UI $99.9\%$ hay $100.1\%$.

- [ ] **TC-DASH-11: Chống tràn nhật ký hoạt động (Audit Log Noise Filter)**
  - *Mô tả*: Cơ sở dữ liệu ghi nhận 10 sự kiện: nhân viên đổi mật khẩu, xem báo cáo, sửa profile, tạo Work Order mới, máy CNC bị sự cố dừng khẩn cấp.
  - *Kỳ vọng*: Activity Feed trên Dashboard chỉ hiển thị 2 sự kiện mang tính tác động vận hành (Tạo Work Order, Máy dừng khẩn cấp). Toàn bộ các log thao tác hệ thống rác (đổi mật khẩu, xem trang, profile) bị loại bỏ hoàn toàn.

- [ ] **TC-DASH-12: Lệch ngày biểu đồ do ranh giới Múi giờ UTC (Timezone Midnight Boundary)**
  - *Mô tả*: Kỹ thuật viên bấm hoàn thành phiếu lúc 01:30 AM ngày 01/08 tại Việt Nam (UTC+7), tương ứng 18:30 ngày 31/07 (UTC).
  - *Kỳ vọng*: Điểm hoàn thành trên biểu đồ 30 ngày phải được ghi nhận vào ngày 01/08 theo múi giờ `Asia/Ho_Chi_Minh`, không bị thụt lùi về ngày 31/07.

- [ ] **TC-DASH-13: Cách ly sự cố dở dang chưa hoàn tất (Ongoing Unresolved Downtime)**
  - *Mô tả*: Một thiết bị bị sự cố từ hôm qua và hiện vẫn đang được sửa chữa (`status = IN_PROGRESS`, chưa có `completed_at`).
  - *Kỳ vọng*: Phiếu này không được đưa vào mẫu số của MTTR; trường `ongoingDownCount` trả về giá trị `1`; thiết bị vẫn được phân bổ vào nhóm `Down`.

- [ ] **TC-DASH-14: Lọc dữ liệu thời gian sửa chữa ngoại lai (Anomalous Duration Filter)**
  - *Mô tả*: Có 1 phiếu sửa chữa bị kỹ thuật viên quên đóng trong 3 tháng dẫn đến `actual_duration_hours = 2160`, và 1 phiếu lỗi đồng hồ client dẫn đến thời gian âm (`actual_duration_hours = -2`).
  - *Kỳ vọng*: Cả 2 phiếu bất thường này bị loại trừ khỏi phép tính MTTR tiêu chuẩn, tránh phá vỡ số liệu MTTR của toàn nhà máy.

- [ ] **TC-DASH-15: Phòng chống thảm họa bộ đệm (Cache Stampede Mutex Guardrail)**
  - *Mô tả*: Khi khóa Redis vừa hết hạn, gửi đồng thời 30 requests `GET /api/v1/dashboard/summary/` vào hệ thống.
  - *Kỳ vọng*: Cơ chế Mutex Lock chỉ cho phép 1 luồng duy nhất thực thi truy vấn tính toán cơ sở dữ liệu; 29 luồng còn lại chờ nhận kết quả đệm; cơ sở dữ liệu không bị nghẽn đột ngột.

- [ ] **TC-DASH-16: An toàn tính biến động $\Delta$ khi kỳ trước rỗng (Safe Delta Zero-Division)**
  - *Mô tả*: Tháng trước nhà máy có 0 sự cố (`Previous = 0`), tháng này phát sinh 2 sự cố (`Current = 2`).
  - *Kỳ vọng*: Hệ thống không phát sinh lỗi chia cho 0; hiển thị biến động `delta = "+2"` kèm nhãn `"Kỳ đầu / Mới"`.

- [ ] **TC-DASH-17: Đồng nhất điều kiện lọc khi Drill-Down (Click-through Consistency)**
  - *Mô tả*: Thẻ KPI hiển thị "7 Phiếu đang xử lý". Người dùng nhấp vào link `drillDownUrl` chuyển sang màn hình Work Order.
  - *Kỳ vọng*: Trang đích áp dụng chính xác bộ lọc `status=CREATED,ASSIGNED,IN_PROGRESS` và trả về đúng 7 bản ghi khớp hoàn toàn với số hiển thị trên Dashboard.

---

## 11. Implementation Notes — For Implementation Phase Only

> [!IMPORTANT]
> **REFERENCE ONLY — DO NOT IMPLEMENT OR MODIFY CODE BASED ON THIS SECTION DURING SPEC REVIEW. These notes are intended for the implementation phase after the specification is approved.**

Phần này lưu trữ các chỉ dẫn kỹ thuật hạ tầng chi tiết để các kỹ sư tham khảo trong quá trình triển khai mã nguồn:

### 11.1. Quy Ước Khóa Lưu Đệm & Phòng Chống Stampede
- **Quy tắc đặt tên khóa**:
  - `eam:dashboard:summary:{tenant_id}`: Lưu trữ toàn bộ dữ liệu KPI cards, phân bổ tài sản, MTBF/MTTR.
  - `eam:dashboard:trends:{tenant_id}`: Lưu trữ mảng dữ liệu biểu đồ 30 ngày.
  - `eam:dashboard:activity:{tenant_id}`: Lưu trữ danh sách Activity Feed.
  - `eam:dashboard:lock:{tenant_id}`: Khóa phân tán Redis Mutex (TTL 10 giây).
- **Thời gian sống (TTL)**: 300 giây (5 phút).
- **Cơ chế hủy bộ đệm theo sự kiện (Event Invalidation Signals)**:
  - Khi `Asset.status` chuyển sang `DOWN`.
  - Khi phát sinh `WorkOrder` loại `EMERGENCY` hoặc `BREAKDOWN`.
  - Khi một `WorkOrder` chuyển trạng thái sang `COMPLETED`.
  $\Rightarrow$ Kích hoạt xóa khóa `eam:dashboard:*:{tenant_id}`.

### 11.2. Thuật Toán Phần Dư Lớn Nhất (Hamilton-Hare Method Reference)
```python
def calculate_largest_remainder_percentages(counts: dict[str, int]) -> dict[str, float]:
    total = sum(counts.values())
    if total == 0:
        return {k: 0.0 for k in counts}
    
    # 1. Tính tỷ lệ chính xác
    raw_percentages = {k: (v / total) * 100 for k, v in counts.items()}
    # 2. Lấy phần nguyên (làm tròn 1 chữ số thập phân, ví dụ nhân 10 lấy int)
    floored = {k: int(pct * 10) / 10 for k, pct in raw_percentages.items()}
    remainder_sum = round(100.0 - sum(floored.values()), 1)
    
    # 3. Phân bổ phần dư 0.1% cho các nhóm có phần thập phân dư cao nhất
    remainders = sorted(
        counts.keys(),
        key=lambda k: raw_percentages[k] - floored[k],
        reverse=True
    )
    for i in range(int(round(remainder_sum * 10))):
        key = remainders[i % len(remainders)]
        floored[key] = round(floored[key] + 0.1, 1)
        
    return floored
```

### 11.3. Chuyển Đổi Múi Giờ Trong Truy Vấn PostgreSQL ORM
```python
from django.db.models.functions import TruncDay
from django.utils.timezone import pytz

# Truy vấn gom nhóm theo ngày khớp với Timezone của Tenant
tenant_tz = pytz.timezone(tenant.timezone or 'Asia/Ho_Chi_Minh')
created_qs = (
    WorkOrder.objects.filter(tenant=tenant, created_at__gte=start_date)
    .annotate(day=TruncDay('created_at', tzinfo=tenant_tz))
    .values('day')
    .annotate(count=Count('id'))
)
```

---

## 12. Kế Hoạch Triển Khai & Nghiệm Thu (Implementation Checklist)

- [ ] **Task 10.2.1 — Calculate Asset Health Distribution**
  - [ ] Xây dựng dịch vụ tính toán phân bổ 3 trạng thái (`OPERATING`, `MAINTENANCE`, `DOWN`).
  - [ ] Loại trừ toàn bộ tài sản thanh lý (`SCRAPPED`, `DISPOSED`, `DECOMMISSIONED`).
  - [ ] Áp dụng thuật toán Hamilton-Hare đảm bảo tổng 3 trạng thái luôn đạt tuyệt đối 100.0%.
  - [ ] Gán nhãn trạng thái vận hành tổng thể của nhà máy.
- [ ] **Task 10.2.2 — Calculate MTBF & MTTR Metrics**
  - [ ] Xây dựng logic tính MTBF loại trừ hoàn toàn 100% phiếu PM (`PREVENTIVE`).
  - [ ] Bọc an toàn chống lỗi chia cho 0 khi không có sự cố (trả về null và nhãn 100% khả dụng).
  - [ ] Tính toán MTTR từ thời gian sửa chữa thực tế, cách ly các phiếu sự cố đang dở dang (`ongoingDownCount`).
  - [ ] Lọc bỏ dữ liệu ngoại lai bất thường (âm hoặc $> 168$ giờ).
- [ ] **Task 10.2.3 — Dynamic 30-Day Work Order Trends**
  - [ ] Xây dựng truy vấn gom nhóm số lượng độc lập theo ngày tạo (`created_at`) và ngày hoàn thành (`completed_at`).
  - [ ] Áp dụng chuyển đổi múi giờ địa phương của Tenant (`AT TIME ZONE`).
  - [ ] Khởi tạo mảng bù khuyết (Zero-filling) đủ 30 ngày liên tục.
- [ ] **Task 10.2.4 — Executive Activity Feed**
  - [ ] Áp dụng bộ lọc danh sách trắng (Whitelist) các sự kiện nghiệp vụ quan trọng từ AuditLog.
  - [ ] Chuyển đổi định dạng thời gian tương đối thân thiện.
- [ ] **Task 10.2.5 — Caching, Stampede Protection & Resilience Engine**
  - [ ] Cài đặt khóa lưu đệm theo Tenant với thời gian sống 5 phút.
  - [ ] Thiết lập cơ chế khóa Mutex chống nghẽn đồng thời (Cache Stampede).
  - [ ] Thiết lập cơ chế xóa bộ đệm tức thì khi có biến động sự cố khẩn cấp.
  - [ ] Thiết lập cơ chế Fallback truy vấn trực tiếp cơ sở dữ liệu khi bộ đệm gặp sự cố.
- [ ] **Task 10.2.6 — Drill-Down Deep Link & Safe Delta**
  - [ ] Cung cấp các liên kết Drill-Down chuẩn hóa cho các thẻ KPI.
  - [ ] Xử lý an toàn khi tính biến động $\Delta$ so với kỳ trước.

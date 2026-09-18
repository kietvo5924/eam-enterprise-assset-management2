# Thiết Kế Hệ Thống & Đặc Tả Kỹ Thuật: Task 11.4 — Condition Monitoring & Inspection Anomaly Detection (Sliding Z-score, Theil-Sen Robust Drift & Isolation Forest)

Tài liệu này xác định kiến trúc thu thập dữ liệu kiểm tra định kỳ (Condition Monitoring & Meter Readings), mô hình đánh giá độ lệch chuỗi ngày (Observation-Based Sliding Z-score), giải thuật học máy đa biến không giám sát (Multivariate Isolation Forest), động cơ suy diễn xu hướng hồi quy mạnh mẽ (Theil-Sen Robust Trend Drift), cơ chế tái lập đường cơ sở sau sửa chữa (Post-Repair Window Reset), chống báo động giả do khởi động máy hoặc nhiệt độ môi trường, cùng **bộ kịch bản kiểm thử chấp nhận & trường hợp biên (Acceptance Criteria & Edge Cases)** cho bài toán **Phát Hiện Bất Thường Từ Dữ Liệu Giám Sát Tình Trạng Thiết Bị** trong hệ thống Quản lý Tài sản Doanh nghiệp (EAM).

Tài liệu đóng vai trò là **Đặc Tả Kỹ Thuật & Chuẩn Kiểm Thử (Technical Specification & Audit Baseline)** nhằm đối chiếu, rà soát và thực thi trọn vẹn toàn bộ tính năng mà không bị thiếu sót bất kỳ nghiệp vụ enterprise nào.

---

## 1. Mục Tiêu & Phạm Vi (Objective & Scope)

### 1.1. Bản Chất Nghiệp Vụ Thực Tế Trong Quản Lý Thiết Bị
Trong các nhà máy sản xuất chưa lắp đặt hệ thống cảm biến IoT tự động hoàn toàn:
- **Tuần tra đo đạc định kỳ (Inspection Rounds)**: Hàng ngày hoặc đầu mỗi ca trực, kỹ thuật viên sử dụng thiết bị đo chuyên dụng cầm tay (súng đo nhiệt độ hồng ngoại, thiết bị đo độ rung cầm tay, đồng hồ áp kế) để kiểm tra tình trạng máy móc.
- **Ghi nhận số liệu hiện trường**: Kỹ thuật viên nhập các thông số đo được (Nhiệt độ, Độ rung, Áp suất, Dòng điện) vào ứng dụng di động Flutter hoặc Web Portal.
- **Mục tiêu hệ thống**: Phân tích chuỗi số liệu tích lũy để:
  1. Phát hiện đột biến bất thường tức thời trong ngày hôm nay (Đơn biến - Sliding Z-Score).
  2. Phát hiện bất thường tương quan đa chỉ số (Đa biến - Isolation Forest).
  3. Suy diễn tốc độ suy thoái chống nhiễu ngoại lai (Theil-Sen Robust Drift) và dự báo số ngày còn lại trước khi chạm ngưỡng nguy hiểm, tự động tạo bản thảo phiếu bảo trì phòng ngừa (Draft PM Work Order) mà không gây bão hòa cảnh báo (Alert Fatigue).

---

## 2. Ràng Buộc Kế Thừa Hệ Thống (Existing System Constraints & Codebase Reuse)

- **Tái Sử Dụng Mô Hình Multi-Tenancy**: Toàn bộ chỉ số đo đạc và cảnh báo bất thường kế thừa `BaseTenantModel`, bảo đảm độc lập tuyệt đối giữa các Tenant qua `TenantManager`.
- **Tái Sử Dụng Thực Thể Nghiệp Vụ Có Sẵn**:
  - `MeterReading`: Mô hình đã tồn tại trong `assets/models.py` lưu trữ lịch sử các lần đo (`asset`, `metric_code`, `value`, `recorded_at`).
  - `Asset`: Phân loại danh mục tài sản, ngưỡng kỹ thuật an toàn của nhà sản xuất (OEM static limits).
  - `WorkOrder`: Loại công việc (`type`), trạng thái (`status`). Khi Work Order hoàn thành, kích hoạt tín hiệu tái lập cửa sổ trượt (Post-Repair Reset).
- **Tích Hợp Hệ Thống Thông Báo Thời Gian Thực (Task 10.1)**: Tự động kích hoạt thông báo mức `CRITICAL` gửi cho Quản lý bảo trì khi phát hiện đột biến nghiêm trọng.

---

## 3. Yêu Cầu Nghiệp Vụ & Quy Tắc Cốt Lõi (Business Requirements & Core Rules)

Toàn bộ logic phát hiện bất thường đo đạc phải tuân thủ nghiêm ngặt 10 quy tắc nghiệp vụ phòng thủ sau:

### Quy Tắc 1: Lọc Ngữ Cảnh Trạng Thái Máy Tránh Báo Động Giả Lúc Khởi Động (Warm-Up / Cold-State Guardrail)
- **Điểm Yếu Nghiệp Vụ**: Kỹ thuật viên đi đo nhiệt độ ổ bi ngay lúc máy vừa mới bật lên được 2 phút. Dĩ nhiên nhiệt độ lúc này chỉ bằng nhiệt độ phòng ($25^\circ\text{C}$), thấp hơn rất nhiều so với mức trung bình khi máy chạy ổn định ($75^\circ\text{C}$). Mô hình Z-score sẽ thấy nhiệt độ tụt thê thảm ($Z < -3.0$) và báo động bất thường giả.
- **Quy Tắc Bắt Buộc**:
  1. Mẫu đo đạc bắt buộc kèm theo trường **Trạng thái máy lúc đo (`machine_state`)**: `RUNNING` (Đang chạy ổn định), `WARM_UP` (Vừa khởi động chưa đủ nhiệt), `IDLE` (Đang dừng / Nghỉ ca).
  2. Các thuật toán AI (Sliding Z-Score, Isolation Forest, Theil-Sen Drift) **CHỈ ĐƯỢC PHÉP CHẠY** trên các mẫu có `machine_state == 'RUNNING'`.
  3. Mẫu có trạng thái `IDLE` hoặc `WARM_UP` chỉ được lưu vào lịch sử để theo dõi, tuyệt đối không kích hoạt phân tích bất thường và không đưa vào mẫu số tính trung bình.

### Quy Tắc 2: Tái Lập Cửa Sổ Trượt Sau Khi Sửa Chữa Xong (Post-Repair Window Reset Guardrail)
- **Điểm Yếu Nghiệp Vụ**: Thiết bị rung mạnh trong suốt 20 ngày qua (dữ liệu xấu). Hôm qua thợ đã thay thế vòng bi mới, hôm nay máy chạy êm ru (độ rung giảm mạnh). Nhưng vì cửa sổ trượt 30 lần đo vẫn chứa 20 lần đo rung lắc cũ, đường trung bình $\mu_W$ bị sai lệch. Hệ thống sẽ báo "Độ rung hôm nay thấp bất thường ($Z < -3.0$)" hoặc đường xu hướng dự báo máy vẫn sắp hỏng.
- **Quy Tắc Bắt Buộc**:
  1. Khi một Work Order loại `CORRECTIVE` hoặc `PREVENTIVE` trên thiết bị chuyển sang trạng thái `COMPLETED`:
  2. Hệ thống tự động kích hoạt **Cắt tỉa & Tái lập cửa sổ trượt (Sliding Window Reset / Pruning)**.
  3. Toàn bộ các lần đo trước thời điểm hoàn thành sửa chữa bị đánh dấu đóng băng (`is_pre_repair = True`). Cửa sổ trượt mới chỉ tính các lần đo phát sinh sau ngày sửa chữa (khởi động lại chế độ Cold-Start so sánh ngưỡng tĩnh OEM cho đến khi tích lũy đủ 15 lần đo mới).

### Quy Tắc 3: Hồi Quy Xu Hướng Mạnh Mẽ Chống Điểm Đo Trượt Tay (Theil-Sen Robust Regression Guardrail)
- **Điểm Yếu Nghiệp Vụ**: Trong 10 lần đo gần nhất, có 1 lần kỹ thuật viên cầm súng đo hồng ngoại bị trượt tay (đo nhầm vào ống xả nhiệt $120^\circ\text{C}$ thay vì thân máy $80^\circ\text{C}$). Phương pháp hồi quy bình phương tối thiểu thông thường (OLS) rất nhạy cảm với ngoại lai, chỉ cần 1 điểm dị biệt sẽ kéo đường xu hướng dốc đứng lên trời, kích hoạt lệnh tạo phiếu PM khẩn cấp sai sự thật.
- **Quy Tắc Bắt Buộc**:
  1. Động cơ dự phóng xu hướng (Trend Drift Engine) tuyệt đối không dùng OLS thuần túy.
  2. Bắt buộc sử dụng thuật toán **Hồi quy mạnh mẽ Theil-Sen Estimator** (từ `sklearn.linear_model.TheilSenRegressor`): Thuật toán tính trung vị của tất cả các hệ số góc giữa các cặp điểm, có khả năng miễn nhiễm hoàn toàn với các điểm nhiễu ngoại lai lên tới $29\%$ tổng số mẫu đo.

### Quy Tắc 4: Chuẩn Hóa Độ Tăng Nhiệt Theo Môi Trường (Ambient Temperature Normalization & $\Delta T$)
- **Điểm Yếu Nghiệp Vụ**: Mùa đông nhiệt độ xưởng $10^\circ\text{C}$, máy chạy $50^\circ\text{C}$. Mùa hè xưởng nóng $40^\circ\text{C}$, máy lên $80^\circ\text{C}$. Nếu AI học trên giá trị tuyệt đối, mùa hè máy sẽ bị báo động cháy liên tục dù độ tăng nhiệt nội tại do ma sát không hề thay đổi.
- **Quy Tắc Bắt Buộc**:
  1. Với các chỉ số nhiệt độ, biểu mẫu nhập liệu thu thập thêm trường: **Nhiệt độ môi trường xưởng ($T_{\text{ambient}}$)** (hoặc tự động lấy từ trạm thời tiết/cảm biến môi trường chung của Tenant).
  2. Mô hình AI được huấn luyện và đánh giá trên biến hiệu số:
     $$\Delta T = T_{\text{machine}} - T_{\text{ambient}} \quad (\text{Độ tăng nhiệt nội tại})$$
  3. Chỉ số $\Delta T$ phản ánh trung thực 100% tình trạng ma sát và mài mòn cơ khí, triệt tiêu hoàn toàn nhiễu thời tiết mùa đông/mùa hè.

### Quy Tắc 5: Giảm Âm Cảnh Báo & Chống Trùng Lặp Phiếu Draft (Alert Throttling & De-duplication)
- **Điểm Yếu Nghiệp Vụ**: Hôm qua hệ thống báo động máy rung lắc, tự sinh 1 phiếu PM Draft. Quản đốc bận chưa duyệt. Hôm nay kỹ thuật viên đi đo lại, thông số vẫn xấu. Hệ thống lại tiếp tục báo động và sinh thêm 1 phiếu PM Draft thứ 2. Sau 5 ngày chưa kịp sửa, xưởng ngập trong 5 phiếu rác giống hệt nhau (Alert Fatigue).
- **Quy Tắc Bắt Buộc**:
  1. Áp dụng cơ chế Giảm âm cảnh báo:
  2. Nếu trên thiết bị đó đang tồn tại một cảnh báo ở trạng thái `OPEN` hoặc một bản thảo `Draft PM Work Order` chưa được duyệt/đóng:
     - Lần đo xấu tiếp theo chỉ cập nhật thông tin vào bản ghi cảnh báo cũ (`last_detected_at = now()`, `occurrence_count += 1`).
     - **Tuyệt đối KHÔNG sinh thêm phiếu Draft PM mới** để tránh làm rác hệ thống quản trị.

### Quy Tắc 6: Nhận Diện Cảm Biến Bị Đóng Băng / Kẹt Giá Trị (Frozen Sensor Detection)
- **Điểm Yếu Nghiệp Vụ**: Súng đo bị hỏng cảm biến hoặc kỹ thuật viên lười đo, ngày nào cũng nhập đúng một con số $28.0^\circ\text{C}$ giống hệt nhau trong 7 ngày liên tiếp dù máy đang chạy 100% công suất.
- **Quy Tắc Bắt Buộc**:
  - Nếu 7 lần đo liên tiếp khi máy đang `RUNNING` có giá trị giống hệt nhau ($\sigma_W == 0$ hoặc không đổi ở mức vi phân), hệ thống phát cảnh báo bất thường: *"Dữ liệu đo bị đóng băng bất thường. Vui lòng kiểm tra lại thiết bị đo hoặc thao tác kiểm tra"*.

### Quy Tắc 7: Hồi Quy Theo Mốc Ngày Thực Tế Thay Vì Chỉ Số Rời Rạc (Timestamp-Based Elapsed Days)
- **Điểm Yếu Nghiệp Vụ**: Thợ đo thứ Hai, thứ Tư, rồi tuần sau nghỉ lễ 10 ngày mới đo lại. Nếu thuật toán hồi quy coi các điểm đo cách đều nhau $t = 1, 2, 3 \dots$, tốc độ suy thoái mỗi ngày sẽ bị tính sai lệch nghiêm trọng.
- **Quy Tắc Bắt Buộc**:
  - Trục thời gian $t_k$ của phương trình hồi quy Theil-Sen bắt buộc phải tính theo số ngày thực tế trôi qua:
    $$t_k = \frac{\text{Timestamp}_k - \text{Timestamp}_0}{86400\text{ giây}}$$

### Quy Tắc 8: Vòng Lặp Phản Hồi Của Con Người Để Khử Nhiễu (Human-in-the-Loop Feedback)
- **Điểm Yếu Nghiệp Vụ**: Máy bị rung do xe nâng hàng nặng vừa chạy ngang qua sàn xưởng lúc thợ bấm đo. AI báo động đỏ. Quản đốc kiểm tra thực tế thấy máy hoàn toàn bình thường.
- **Quy Tắc Bắt Buộc**:
  - Quản đốc có quyền bấm nút *"Đánh dấu Báo động giả (False Positive)"* trên giao diện.
  - Điểm đo đó được gắn cờ `is_suppressed = True` và bị loại trừ vĩnh viễn khỏi tập dữ liệu huấn luyện của mô hình Isolation Forest trong tương lai.

### Quy Tắc 9: Tích Hợp Dải Tiêu Chuẩn Độ Rung Quốc Tế ISO 10816-3 (ISO Standards Benchmark)
- **Quy Tắc Bắt Buộc**:
  - Đối với chỉ số độ rung vận tốc RMS (mm/s), hệ thống tích hợp sẵn dải đánh giá theo tiêu chuẩn quốc tế ISO 10816-3:
    - **Vùng A/B (Tốt / Đạt tiêu chuẩn)**: $< 2.8\text{ mm/s}$ (máy trung bình) hoặc $< 4.5\text{ mm/s}$ (máy lớn bệ cứng).
    - **Vùng C (Cảnh báo - Cần theo dõi)**: $2.8 - 7.1\text{ mm/s}$.
    - **Vùng D (Nguy hiểm - Dừng máy khẩn cấp)**: $> 7.1\text{ mm/s}$.
  - Giao diện hiển thị các dải màu xanh/vàng/đỏ tương ứng để kỹ sư có cơ sở đối chiếu chuẩn mực công nghiệp.

### Quy Tắc 10: Ràng Buộc Giới Hạn Vật Lý Khả Thi & Phân Luồng Tài Sản Tĩnh
- **Quy Tắc Bắt Buộc**:
  - Cài đặt ngưỡng giới hạn vật lý khả thi (Nhiệt độ $[0, 180^\circ\text{C}]$, Rung $[0.01, 50\text{ mm/s}]$, Áp suất $[0, 30\text{ bar}]$). Giá trị ngoài biên bị từ chối ngay lập tức tại tầng xác thực với lỗi `400 Bad Request`.
  - Đối với tài sản tĩnh (bàn ghế, giường bệnh): Chuyển sang Phiếu Kiểm Tra Định Tính (Checklist Pass/Fail), không chạy AI rung nhiệt.

---

## 4. Yêu Cầu Chức Năng & Luồng Xử Lý (Functional Requirements & Workflows)

### 4.1. Kiến Trúc Phân Tích 3 Cấp Độ Cải Tiến
1. **Cấp độ 1 (Sliding Z-Score đơn biến trên mẫu RUNNING)**:
   - Chỉ lọc các mẫu có `machine_state == 'RUNNING'` sau ngày sửa chữa gần nhất.
   - Tính trung bình $\mu_W$ và độ lệch chuẩn $\sigma_W$ trên $W = 30$ lần đo gần nhất.
   - Tính chỉ số $Z = (x_{\text{today}} - \mu_W) / \sigma_W$.
   - Phân loại: $|Z| < 2.0$ (Bình thường), $2.0 \le |Z| < 3.0$ (Cảnh báo), $|Z| \ge 3.0$ (Đột biến nghiêm trọng).
2. **Cấp độ 2 (Multivariate Isolation Forest đa biến trên vector hiệu số $\Delta T$)**:
   - Vector đầu vào: $[\text{Vibration}, \;\; \Delta T = T_{\text{machine}} - T_{\text{ambient}}, \;\; \text{Pressure}, \;\; \text{Current}]$.
   - Điểm số bất thường $s \ge 0.65$ kích hoạt cảnh báo bất thường tương quan đa biến.
3. **Cấp độ 3 (Động cơ Theil-Sen Robust Trend Drift & Dự báo ngày vượt ngưỡng)**:
   - Áp dụng hồi quy mạnh mẽ Theil-Sen trên chuỗi ngày thực tế $t_k$.
   - Tìm hệ số góc suy thoái $a$ (tốc độ tăng trưởng mỗi ngày).
   - Dự báo số ngày còn lại: $\text{Days Remaining} = (Y_{\text{limit}} - y_{\text{today}}) / a$.
   - Nếu $\text{Days Remaining} \le 7$ ngày và chưa có cảnh báo mở: Tự động tạo bản thảo `Draft PM Work Order`.

---

## 5. Quy Tắc Bảo Mật, Phân Quyền & Đa Khách Hàng (Security, RBAC & Multi-Tenant Rules)

- **Cô Lập Đa Khách Hàng (Multi-Tenancy)**: Toàn bộ dữ liệu đo đạc, mô hình huấn luyện và lịch sử cảnh báo chỉ lưu trữ và truy vấn trong phạm vi `tenant_id` của tổ chức.
- **Phân Quyền Theo Vai Trò (RBAC)**:
  - `TECHNICIAN`: Quyền nhập số liệu đo đạc hiện trường qua Mobile hoặc Web Portal.
  - `MAINTENANCE_MANAGER`: Quyền xem phân tích bất thường, nhận thông báo cảnh báo sớm, bấm xác nhận "Báo động giả" và phê duyệt bản thảo Work Order phòng ngừa.

---

## 6. Kiến Trúc & Luồng Dữ Liệu (Architecture & Data Flow)

```
[Kỹ Thuật Viên Nhập Số Đo Trên Mobile / Web]
  ├── Nhập: Giá trị đo, Trạng thái máy (RUNNING), Nhiệt độ môi trường (T_amb)
          │
          ▼
[API: POST /api/v1/assets/{id}/meter-readings/]
          │
          ├── (1) Kiểm tra giới hạn vật lý (Sanity Bounds Check)
          ├── (2) Lưu bản ghi vào bảng meter_readings
          └── (3) Chuyển giao tác vụ phân tích ngầm
                      │
                      ▼
[Condition Monitoring Anomaly Engine]
  ├── Bước 1: Kiểm tra trạng thái máy (Bỏ qua nếu WARM_UP hoặc IDLE)
  ├── Bước 2: Kiểm tra tín hiệu sửa chữa ──► Tái lập cửa sổ nếu có WO COMPLETED
  ├── Bước 3: Tính Sliding Z-Score trên 30 lần đo RUNNING gần nhất
  ├── Bước 4: Đánh giá tương quan đa biến qua Isolation Forest (với biến Delta T)
  └── Bước 5: Hồi quy mạnh mẽ Theil-Sen tính tốc độ suy thoái chống nhiễu
                      │
                      ▼
[Bộ Lọc Giảm Âm Cảnh Báo (Alert Throttling)]
  ├── Đã có Alert OPEN hoặc Draft PM? ──► Cập nhật occurrence_count, KHÔNG tạo mới
  └── Chưa có cảnh báo? ──► Tạo Alert mới + Tự động tạo Draft PM nếu chạm ngưỡng <= 7 ngày
```

---

## 7. Mô Hình Dữ Liệu & Thực Thể (Data Model & Schema)

### 7.1. Bảng `meter_readings` (Mở rộng trường trạng thái và môi trường)
- `id`: `UUID` (Primary Key).
- `tenant_id`: `UUID` (Kế thừa `BaseTenantModel`).
- `asset_id`: `UUID` (Foreign Key tới `Asset`).
- `metric_code`: `VARCHAR(64)` (`TEMPERATURE`, `VIBRATION`, `PRESSURE`, `CURRENT`).
- `value`: `FLOAT` (Giá trị đo được).
- `ambient_temperature`: `FLOAT`, `null=True` (Nhiệt độ môi trường xưởng lúc đo).
- `machine_state`: `VARCHAR(20)` (`RUNNING`, `WARM_UP`, `IDLE`, `default='RUNNING'`).
- `is_pre_repair`: `BOOLEAN`, `default=False` (Cờ đánh dấu dữ liệu trước lần sửa chữa).
- `unit`: `VARCHAR(20)` (`°C`, `mm/s`, `bar`, `A`).
- `recorded_at`: `TIMESTAMP WITH TIME ZONE`.
- `recorded_by_id`: `UUID` (Foreign Key tới `User`).

### 7.2. Bảng `asset_anomaly_alerts` (Mở rộng cờ giảm âm & phản hồi)
- `id`: `UUID` (Primary Key).
- `tenant_id`: `UUID` (Kế thừa `BaseTenantModel`).
- `asset_id`: `UUID` (Foreign Key tới `Asset`).
- `reading_id`: `UUID` (Foreign Key tới `MeterReading`).
- `metric_type`: `VARCHAR(32)` (`SINGLE_METRIC`, `MULTIVARIATE`).
- `current_value`: `FLOAT`.
- `z_score`: `FLOAT`, `null=True`.
- `anomaly_score`: `FLOAT`, `null=True`.
- `trend_slope`: `FLOAT`, `null=True` (Hệ số góc Theil-Sen).
- `predicted_failure_date`: `DATE`, `null=True`.
- `days_remaining`: `INTEGER`, `null=True`.
- `severity`: `VARCHAR(16)` (`WARNING`, `CRITICAL`).
- `status`: `VARCHAR(16)` (`OPEN`, `ACKNOWLEDGED`, `RESOLVED`, `FALSE_ALARM`).
- `occurrence_count`: `INTEGER`, `default=1` (Số lần lặp lại cảnh báo liên tiếp).
- `is_suppressed`: `BOOLEAN`, `default=False` (Cờ loại trừ khỏi tập huấn luyện AI).
- `draft_work_order_id`: `UUID`, `null=True`.
- `created_at`: `TIMESTAMP WITH TIME ZONE`.
- `last_detected_at`: `TIMESTAMP WITH TIME ZONE`.

---

## 8. Đặc Tả Giao Diện Lập Trình (API Specifications & Contracts)

### Danh Mục Endpoints:

| Phương Thức | Đường Dẫn | Chức Năng |
| :--- | :--- | :--- |
| `POST` | `/api/v1/assets/{id}/meter-readings/` | Nhập số đo kiểm tra hiện trường & kích hoạt phân tích AI |
| `GET` | `/api/v1/assets/{id}/anomaly-history/` | Lấy lịch sử đo đạc, ngưỡng ISO 10816 và đường xu hướng Theil-Sen |
| `POST` | `/api/v1/condition-monitoring/alerts/{id}/feedback/` | Phản hồi của Quản lý: Xác nhận bất thường thật hoặc Báo động giả |

### Cấu Trúc Dữ Liệu Mẫu:

#### 1. Nhập số đo kiểm tra (`POST /api/v1/assets/{id}/meter-readings/`):
- **Request Body**:
```json
{
  "machineState": "RUNNING",
  "ambientTemperature": 32.0,
  "readings": [
    { "metricCode": "TEMPERATURE", "value": 78.5, "unit": "°C" },
    { "metricCode": "VIBRATION", "value": 5.2, "unit": "mm/s" },
    { "metricCode": "PRESSURE", "value": 2.4, "unit": "bar" }
  ],
  "recordedAt": "2026-09-17T09:30:00Z"
}
```
- **Response**:
```json
{
  "success": true,
  "data": {
    "savedReadingsCount": 3,
    "analysisSummary": {
      "machineState": "RUNNING",
      "hasAnomaly": true,
      "highestSeverity": "WARNING",
      "zScoreAlert": { "metric": "VIBRATION", "zScore": 2.45, "status": "ELEVATED_VIBRATION" },
      "iso10816Status": { "zone": "ZONE_C", "label": "Cảnh báo (Vùng C: 2.8 - 7.1 mm/s)" },
      "trendDrift": {
        "isDrifting": true,
        "slopePerDay": 0.35,
        "daysRemaining": 5,
        "predictedFailureDate": "2026-09-22",
        "draftWorkOrderAction": "UPDATED_EXISTING_DRAFT"
      }
    }
  }
}
```

---

## 9. Đặc Tả Trải Nghiệm Người Dùng (UI/UX Behavioral Specifications)

- **Ứng dụng di động (Mobile Inspection UI)**:
  - Nút chuyển trạng thái máy trực quan ngay đầu form: **[RUNNING] [WARM-UP] [IDLE]**. Khi bấm Warm-Up, giao diện hiển thị nhãn xanh: *"Chỉ ghi nhận lịch sử, không kích hoạt cảnh báo AI"*.
  - Tự động hiển thị dải đo theo chuẩn ISO 10816 (Xanh: Bình thường, Vàng: Cảnh báo, Đỏ: Nguy hiểm).
- **Giao diện Web Portal (Condition Monitoring Dashboard)**:
  - Đồ thị chuỗi đo hiển thị đường xu hướng hồi quy mạnh mẽ Theil-Sen và dải nhiệt độ môi trường song song.
  - Thẻ cảnh báo có nút bấm nhanh: **[Tạo phiếu sửa chữa ngay]** và **[Đánh dấu Báo động giả]**.

---

## 10. Tiêu Chí Chấp Nhận & Ma Trận Kịch Bản Kiểm Thử (Acceptance Criteria & Test Matrix)

Dưới đây là bảng ma trận kiểm thử chi tiết hóa toàn bộ 12 kịch bản chấp nhận và trường hợp biên (Edge Cases):

### 10.1. Ma Trận Kịch Bản Nghiệp Vụ & Khử Nhiễu Thực Tế

- [ ] **TC-ANOM-01: Bất thường giả do máy chưa chạy đủ công suất (Warm-Up Guardrail)**
  - *Mô tả*: Đo nhiệt độ máy lúc vừa bật 2 phút ($25^\circ\text{C}$ so với mức trung bình $75^\circ\text{C}$), chọn trạng thái `WARM_UP`.
  - *Kỳ vọng*: Dữ liệu được lưu thành công; hệ thống KHÔNG kích hoạt cảnh báo Z-score âm ($Z < -3.0$); không phát sinh báo động giả.

- [ ] **TC-ANOM-02: Tái lập cửa sổ trượt sau khi sửa chữa xong (Post-Repair Reset)**
  - *Mô tả*: Máy rung lắc mạnh 20 lần đo. Kỹ thuật viên hoàn thành phiếu thay vòng bi (`WorkOrder.status = 'COMPLETED'`). Hôm nay đo độ rung máy giảm mạnh về mức êm.
  - *Kỳ vọng*: Cửa sổ 30 lần đo được tái lập; toàn bộ dữ liệu rung lắc cũ trước lúc sửa bị loại bỏ khỏi baseline; không báo lỗi "độ rung thấp bất thường".

- [ ] **TC-ANOM-03: Chống méo đường xu hướng do súng đo trượt tay (Theil-Sen Robustness)**
  - *Mô tả*: Trong 10 lần đo gần nhất có 1 lần nhập nhầm $120^\circ\text{C}$ (trượt tay vào ống xả), các lần khác đều $80^\circ\text{C}$.
  - *Kỳ vọng*: Thuật toán Theil-Sen bỏ qua điểm ngoại lai $120^\circ\text{C}$; đường xu hướng vẫn duy trì nằm ngang ổn định; không bị kéo dốc đứng kích hoạt Draft PM sai.

- [ ] **TC-ANOM-04: Khử nhiễu biến đổi thời tiết mùa hè/mùa đông ($\Delta T$)**
  - *Mô tả*: Mùa hè xưởng nóng $38^\circ\text{C}$, máy chạy $78^\circ\text{C}$ ($\Delta T = 40^\circ\text{C}$). Mùa đông xưởng $12^\circ\text{C}$, máy $52^\circ\text{C}$ ($\Delta T = 40^\circ\text{C}$).
  - *Kỳ vọng*: Mô hình học trên biến $\Delta T = 40^\circ\text{C}$ đánh giá trạng thái hoàn toàn ổn định bình thường, không kích hoạt cảnh báo quá nhiệt vào mùa hè.

- [ ] **TC-ANOM-05: Chống bão hòa cảnh báo & Không spam Draft PM (Alert Throttling)**
  - *Mô tả*: Thiết bị đã có 1 cảnh báo OPEN và 1 Draft PM tạo từ hôm qua. Hôm nay đo tiếp thấy thông số vẫn xấu.
  - *Kỳ vọng*: Bản ghi cảnh báo cũ được tăng `occurrence_count = 2`; hệ thống tuyệt đối KHÔNG tạo thêm bản thảo Draft PM thứ 2.

- [ ] **TC-ANOM-06: Nhận diện cảm biến bị kẹt / đóng băng số liệu (Frozen Sensor)**
  - *Mô tả*: 7 lần đo liên tiếp khi máy đang `RUNNING` đều ghi nhận giá trị $28.00^\circ\text{C}$ không đổi.
  - *Kỳ vọng*: Hệ thống phát cảnh báo thiết bị đo bị kẹt giá trị hoặc hỏng hóc.

- [ ] **TC-ANOM-07: Hồi quy theo mốc ngày thực tế (Timestamp Elapsed Days)**
  - *Mô tả*: Đo cách nhau 10 ngày do nghỉ lễ.
  - *Kỳ vọng*: Tốc độ suy thoái $a$ được tính toán trên khoảng cách 10 ngày thực tế, không coi là 1 bước đo liền kề.

- [ ] **TC-ANOM-08: Phản hồi của Quản lý loại trừ báo động giả (Human Feedback Loop)**
  - *Mô tả*: Quản đốc bấm nút "Đánh dấu Báo động giả" cho một cảnh báo rung do xe nâng đi ngang qua.
  - *Kỳ vọng*: Trạng thái chuyển thành `FALSE_ALARM`, `is_suppressed = True`; điểm đo bị loại trừ khỏi tập huấn luyện Isolation Forest trong tương lai.

### 10.2. Ma Trận Kịch Bản Kỹ Thuật, Ngưỡng & Hiệu Năng

- [ ] **TC-ANOM-09: Chặn số liệu gõ nhầm vượt ngưỡng vật lý khả thi**
  - *Mô tả*: Người dùng nhập nhiệt độ $750^\circ\text{C}$ hoặc độ rung $200\text{ mm/s}$.
  - *Kỳ vọng*: Hệ thống từ chối lưu với mã lỗi `400 Bad Request`.

- [ ] **TC-ANOM-10: Phân luồng tài sản tĩnh (Bàn ghế, tủ tài liệu)**
  - *Mô tả*: Kiểm tra một tài sản thuộc danh mục tài sản tĩnh.
  - *Kỳ vọng*: Hệ thống hiển thị biểu mẫu kiểm tra định tính (Pass/Fail); không chạy mô hình Z-score hay Isolation Forest rung nhiệt.

- [ ] **TC-ANOM-11: Tích hợp đối chiếu dải tiêu chuẩn quốc tế ISO 10816-3**
  - *Mô tả*: Máy bơm công nghiệp có độ rung $5.5\text{ mm/s}$.
  - *Kỳ vọng*: Hệ thống phân loại chính xác vào `Vùng C (Cảnh báo: 2.8 - 7.1 mm/s)`.

- [ ] **TC-ANOM-12: Dự báo ngày chạm ngưỡng & tự động tạo Draft PM khi $\le 7$ ngày**
  - *Mô tả*: Độ rung máy tăng đều đặn theo quy luật Theil-Sen, dự báo chạm ngưỡng đỏ sau 4 ngày.
  - *Kỳ vọng*: Hệ thống tạo 1 bản thảo Draft PM duy nhất kèm thông báo gửi Quản đốc.

---

## 11. Implementation Notes — For Implementation Phase Only

> [!IMPORTANT]
> **REFERENCE ONLY — DO NOT IMPLEMENT OR MODIFY CODE BASED ON THIS SECTION DURING SPEC REVIEW. These notes are intended for the implementation phase after the specification is approved.**

Phần này lưu trữ các chỉ dẫn kỹ thuật hạ tầng chi tiết để các kỹ sư tham khảo trong quá trình triển khai mã nguồn:

### 11.1. Cài Đặt Hồi Quy Mạnh Mẽ Theil-Sen
```python
import numpy as np
from sklearn.linear_model import TheilSenRegressor

def compute_theil_sen_drift(timestamps, values, limit_value):
    """
    timestamps: Danh sách các datetime thực tế
    values: Danh sách các giá trị đo đạc
    """
    if len(values) < 5:
        return None, None  # Chưa đủ điểm suy diễn
        
    t0 = timestamps[0]
    # Tính số ngày thực tế trôi qua
    X = np.array([(t - t0).total_seconds() / 86400.0 for t in timestamps]).reshape(-1, 1)
    y = np.array(values)
    
    # Hồi quy Theil-Sen miễn nhiễm 29% ngoại lai
    reg = TheilSenRegressor(random_state=42).fit(X, y)
    slope = float(reg.coef_[0])  # Tốc độ suy thoái mỗi ngày
    
    if slope <= 0.01:
        return slope, None  # Không có xu hướng tăng
        
    current_val = values[-1]
    if current_val >= limit_value:
        return slope, 0  # Đã chạm ngưỡng
        
    days_remaining = int((limit_value - current_val) / slope)
    return slope, max(1, days_remaining)
```

### 11.2. Cơ Chế Tái Lập Cửa Sổ Sau Khi Sửa Chữa (Signal Trigger)
```python
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=WorkOrder)
def on_work_order_completed(sender, instance, **kwargs):
    if instance.status == 'COMPLETED' and instance.type in ('CORRECTIVE', 'PREVENTIVE'):
        # Đánh dấu toàn bộ các lần đo trước thời điểm này là lịch sử cũ
        MeterReading.objects.filter(
            asset=instance.asset,
            recorded_at__lte=instance.completed_at
        ).update(is_pre_repair=True)
```

---

## 12. Kế Hoạch Triển Khai & Nghiệm Thu (Implementation Checklist)

- [ ] **Task 11.4.1 — Metric Sanity Check & Physical Bounds**
  - [ ] Bổ sung trường `machine_state`, `ambient_temperature` vào `MeterReading`.
  - [ ] Cài đặt bộ lọc ngưỡng vật lý khả thi và phân luồng tài sản tĩnh.
- [ ] **Task 11.4.2 — Sliding Z-Score Engine with Machine State Filter**
  - [ ] Cài đặt cửa sổ trượt $W = 30$ lần đo chỉ lấy mẫu `machine_state == 'RUNNING'`.
  - [ ] Cài đặt tín hiệu tín hiệu tự động tái lập cửa sổ (Post-Repair Reset) khi Work Order hoàn thành.
- [ ] **Task 11.4.3 — Multivariate Isolation Forest with Delta T Normalization**
  - [ ] Chuẩn hóa biến $\Delta T = T_{\text{machine}} - T_{\text{ambient}}$.
  - [ ] Tích hợp mô hình rừng cô lập đánh giá tương quan đa biến.
- [ ] **Task 11.4.4 — Theil-Sen Robust Trend Drift & Alert Throttling**
  - [ ] Cài đặt hồi quy mạnh mẽ Theil-Sen tính toán tốc độ suy thoái chống ngoại lai trượt tay.
  - [ ] Cài đặt cơ chế giảm âm cảnh báo chống trùng lặp phiếu Draft PM.
  - [ ] Tích hợp tiêu chuẩn độ rung ISO 10816-3.
- [ ] **Task 11.4.5 — REST APIs, UI & Human Feedback Loop**
  - [ ] Endpoint nhập số đo kèm trạng thái máy và nhiệt độ môi trường.
  - [ ] Endpoint phản hồi của Quản lý đánh dấu Báo động giả.
  - [ ] Giao diện Web/Mobile hiển thị dải màu ISO và đường xu hướng.
- [ ] **Task 11.4.6 — Verification & Testing Suite**
  - [ ] Viết test cases kiểm thử đầy đủ 12 kịch bản chấp nhận (`TC-ANOM-01` đến `TC-ANOM-12`).

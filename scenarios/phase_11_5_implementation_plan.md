# Kế Hoạch Triển Khai Chi Tiết: Phase 11.5 — Deep Learning Predictive Maintenance (LSTM for Remaining Useful Life - RUL)

Tài liệu này đóng vai trò là **Bản Đặc Tả Kỹ Thuật, Đánh Giá Nghiệp Vụ & Kế Hoạch Thực Thi (Implementation Plan)** đã được chuẩn hóa theo đúng hiện trạng codebase thực tế của dự án EAM. 

---

## PHẦN I: RÀ SOÁT KIẾN TRÚC & GIẢI ĐÁP TOÀN DIỆN CÁC CÂU HỎI NGHIỆP VỤ

### 1. Bổ Sung Các Trường Vào Bảng `Asset`: Được Nhập Số Liệu Trong Tình Huống Nào?

Khi bổ sung các trường vào bảng `assets`, chúng được phân định rạch ròi thành 2 nhóm: **Nhóm do con người cấu hình (User-Configured)** và **Nhóm do hệ thống AI tự động ghi nhận (System-Calculated)**:

| Tên Trường | Phân Loại | Được Nhập / Cập Nhật Trong Tình Huống Nào? | Tiện Lợi & Dễ Hiểu Không? |
| :--- | :--- | :--- | :--- |
| **`duty_cycle_ratio`** | **Người dùng cấu hình** | - Khi tạo tài sản mới hoặc bấm **"Sửa tài sản"** trên Web Portal.<br>- Mặc định là `1.0` (máy chạy 24/7).<br>- Nếu máy chạy luân phiên 12h/ngày, người dùng chọn preset `0.5` hoặc nhập tỷ lệ mong muốn ($0.1 - 1.0$). | **Rất tiện & dễ hiểu**: Trên form sửa tài sản hiển thị dropdown có sẵn các preset trực quan: *(24/7 = 1.0; 2 ca luân phiên = 0.5; Hành chính 8h = 0.33; 5 ngày/tuần = 0.71)*. Người dùng không cần tính toán thủ công. |
| **`current_rul_days`** | **AI tự động ghi** | - **Không cho nhập tay** (Read-only $100\%$).<br>- Hệ thống tự động tính toán và cập nhật khi: (1) Lưu số đo `MeterReading` RUNNING; (2) Phase 11.4 phát hiện bất thường; (3) Bấm "Chạy RUL tức thời"; (4) Quét định kỳ hàng tuần Celery Beat. | **Tuyệt đối an toàn**: Người dùng không thể can thiệp làm sai lệch chỉ số tuổi thọ của máy móc. |
| **`current_rul_calendar_days`** | **Hệ thống tự quy đổi** | - Tự động tính toán $= \frac{\text{current\_rul\_days}}{\text{duty\_cycle\_ratio}}$ ngay khi mô hình RUL xuất kết quả. | Giúp người quản lý biết chính xác **ngày nào trên lịch làm việc** cần dừng máy để thay thế vật tư, không bị nhầm lẫn giữa giờ máy chạy và ngày dương lịch. |
| **`rul_confidence_lower`**<br>**`rul_confidence_upper`** | **AI tự động ghi** | - Tự động trích xuất từ 20 lần forward pass của **Monte Carlo Dropout** trong quá trình suy diễn (tương ứng khoảng tin cậy 90% $[\mu - 1.645\sigma, \mu + 1.645\sigma]$). | Kỹ sư bảo trì nhìn vào cận dưới (`lower`) để lập phương án an toàn nhất (Worst-case scenario), triệt tiêu nguy cơ máy hỏng bất ngờ. |
| **`rapid_degradation_alert`** | **AI tự động kích hoạt** | - Tự động bật `True` khi RUL tụt dốc $> 50\%$ hoặc tốc độ suy thoái $\ge 5$ ngày/lần đo giữa 3 lần đo liên tiếp.<br>- Tự động reset về `False` khi máy được sửa chữa/đại tu. | Hoạt động như chiếc phanh khẩn cấp, cảnh báo nứt rỗ ổ bi đột ngột để quản đốc can thiệp dừng máy ngay. |
| **`last_rul_predicted_at`** | **Hệ thống tự động ghi** | - Tự động gán bằng `timezone.now()` mỗi khi mô hình RUL chạy xong cho tài sản. | Cho biết độ tươi mới (freshness) của dữ liệu; hỗ trợ Celery background job nhận biết máy nào đã quá hạn quét RUL. |
| **`is_phantom_recovery`** | **AI tự động kích hoạt** | - Tự động bật `True` khi sau hành động bôi trơn/siết ốc (`MICRO_MAINTENANCE`), RUL tính toán đột ngột tăng vọt $> 30\%$.<br>- Quản đốc có quyền bấm nút **"Override"** trên UI sau khi thẩm định thực tế. | Ngăn chặn bẫy "hồi phục ảo", bảo vệ an toàn cho nhà xưởng. |

---

### 2. Có Ảnh Hưởng Tới Những Chức Năng Khác Không? (Impact Analysis)

| Chức Năng Hiện Tại | Đánh Giá Tác Động & Phương Án Bảo Vệ |
| :--- | :--- |
| **Tạo / Sửa Tài Sản (`AssetCreateUpdateSerializer`)** | **Không ảnh hưởng tiêu cực**: Chỉ thêm trường `duty_cycle_ratio` (cho phép null/optional, mặc định `1.0`). Toàn bộ các trường RUL khác đều là read-only, người dùng không thể ghi đè tùy tiện. |
| **Cây Phân Cấp & Danh Sách (`AssetSerializer`)** | **Hoàn toàn tương thích**: Thêm các trường RUL vào payload trả về để UI hiển thị. Các frontend cũ không đọc các trường này vẫn hoạt động bình thường mà không bị crash. |
| **Import Tài Sản Bằng Excel** | **Không bị ảnh hưởng**: File Excel mẫu cũ không có cột RUL vẫn import bình thường vì các cột RUL đều có giá trị mặc định hoặc cho phép null. |
| **Quy Trình Nghiệm Thu (`WorkOrderTransitionService`)** | **Đồng bộ tối đa**: Khi hoàn thành Work Order loại `CORE_REPLACEMENT`, hệ thống tự động reset `is_phantom_recovery = False` và đưa `rul_risk_level = 'CALIBRATING'` đúng chuẩn logic. |
| **Dashboard KPI (`DashboardCacheService`)** | **Tương thích**: Khi `Asset.save()` được gọi để cập nhật RUL, hàm `invalidate_all(tenant_id)` sẽ tự động xóa cache Redis để bảng điều khiển Dashboard cập nhật ngay số lượng thiết bị cảnh báo. |

---

### 3. Hiển Thị Ở Giao Diện Nào & Khi Nào Là Hợp Lý Nhất?

#### A. Giao diện Web Portal:
1. **Tại Màn Hình Chi Tiết Tài Sản (`asset_registry.html`)**:
   - **Vị trí**: Đặt một **Thẻ Sức Khỏe Tuổi Thọ RUL (RUL Health Card)** ngay tại đầu tab **"Chỉ số hoạt động"** (`tab-content-meterReadings`).
   - **Nội dung hiển thị**:
     - Đồng hồ vòm / Thanh đo tiến trình 4 màu: Xanh lá (`LOW` > 60 ngày), Vàng (`MEDIUM` 30-60 ngày), Cam (`HIGH`), Đỏ (`CRITICAL`).
     - Chỉ số song hành: `18.5 Ngày Vận Hành` $\approx$ `26.4 Ngày Dương Lịch` (Hệ số tải $D_c = 0.70$).
     - Vệt bóng mờ độ tin cậy 90%: `[15.2 — 21.8 ngày]` kèm nhãn đánh giá độ bất định.
     - Trạng thái vật tư thay thế: `Vòng bi SKF 6205 - Tồn kho: 2 (Khả dụng) - Thời gian chờ hàng: 20 ngày`.
     - Nút bấm: `Chạy Dự Đoán RUL Tức Thời (AI LSTM)` có hiệu ứng xoay loading.
   - **Banner Hồi phục ảo (Phantom Recovery Warning)**:
     - Xuất hiện thanh banner màu vàng cam nổi bật khi `is_phantom_recovery == True`:
       *"Cảnh báo: Chỉ số rung/nhiệt giảm tạm thời sau khi bơm mỡ/siết ốc. RUL được giữ nguyên 18 ngày để phòng ngừa vỡ vòng bi."*
     - Có nút bấm *"Quản đốc xác thực ghi đè (Override)"* kèm modal nhập lý do kỹ thuật.
2. **Tại Màn Hình Danh Sách Phiếu Bảo Trì (`work_orders.html`)**:
   - Các phiếu bảo trì đón đầu do AI tự sinh (`PREDICTIVE_PM`) hiển thị huy hiệu tím nổi bật `[DỰ ĐOÁN RUL]`, kèm đường link mở trực tiếp phân tích suy thoái của thiết bị.

---

### 4. Có Cần Bắn Notification Không? Gửi Cho Ai & Khi Nào?

- **Có**, nhưng phải tuân thủ nghiêm ngặt **Cơ Chế Gom Cảnh Báo (Alert Consolidation)** và **Sliding-Window Deduplication (Phase 10.1)** để triệt tiêu nguy cơ bão hòa cảnh báo (Alert Fatigue):
  
| Cấp Độ RUL | Có Gửi Notification Không? | Người Nhận & Hành Vi Hệ Thống |
| :--- | :---: | :--- |
| **`CALIBRATING` / `LOW` / `MEDIUM`** | **KHÔNG** | Không làm phiền nhân sự khi thiết bị còn an toàn. |
| **`HIGH`** | **Thông báo nội bộ trên Web** | Gửi thông báo mức `WARNING` vào thanh chuông Topbar để Quản đốc chú ý theo dõi. |
| **`CRITICAL`** ($RUL \le \max(14, \text{lead\_time} + 5)$) | **GỬI NGAY** | Gửi thông báo mức `CRITICAL` tới toàn bộ Quản lý bảo trì (Maintenance Managers) kèm mã phiếu bảo trì đón đầu `PREDICTIVE_PM` đã được tự động khởi tạo. |
| **`RAPID_DEGRADATION`** (Rơi tự do) | **GỬI HỎA TỐC** | Gửi thông báo mức `URGENT` tới Quản đốc trực ca và Trưởng nhóm kỹ thuật kèm cờ đỏ khẩn cấp. |

- **Cơ chế Hợp nhất 2 tầng (11.4 $\rightarrow$ 11.5)**:
  - Khi Phase 11.4 phát hiện rung độ bất thường ($|Z| \ge 3.0$) và kích hoạt Phase 11.5 tính ra RUL, hệ thống **chỉ gửi đúng 1 thông báo hợp nhất**:
    > *"[CẢNH BÁO TỔNG HỢP] Bơm ly tâm P-101: Phát hiện rung bất thường (Z-score 3.4). Mô hình LSTM dự báo RUL chỉ còn 12 ngày vận hành (Độ tin cậy 90%: 10–14 ngày). Đã tự động tạo bản thảo phiếu WO-2026-001."*

---

### 5. Có Cần Thêm Ở Ứng Dụng Mobile Không?

- **CÓ THÊM, NHƯNG THEO TRIẾT LÝ: CHỈ XEM (READ-ONLY) & CẢNH BÁO AN TOÀN HIỆN TRƯỜNG**:
  - **Không làm trên Mobile**: Không đưa các cấu hình phức tạp (như chỉnh `duty_cycle_ratio`, chỉnh siêu tham số AI) vào điện thoại; những việc này thuộc thẩm quyền Quản đốc trên Web Portal.
  - **Cần hiển thị trên Mobile**:
    1. **Khi Kỹ thuật viên quét mã QR tài sản**: Thẻ thông tin máy hiển thị thêm 1 dòng tóm tắt sức khỏe: `Tuổi thọ còn lại: 18 ngày [NGUY CƠ CAO]`.
    2. **Khi Kỹ thuật viên bấm Bắt đầu làm việc (`IN_PROGRESS`) trên Work Order**: Nếu máy có cờ `rapid_degradation_alert == True` hoặc `is_phantom_recovery == True`, ứng dụng Mobile hiện một hộp thoại Toast lưu ý an toàn: *"Lưu ý an toàn: Vòng bi máy này đang có dấu hiệu nứt vỡ gia tốc cao. Kiểm tra kỹ trước khi khởi động chạy thử."*
  - **Hạ tầng API Backend**: Đã hỗ trợ sẵn sàng 100% qua endpoint `GET /api/v1/assets/{id}/`, mobile chỉ cần đọc các trường `currentRulDays`, `rulRiskLevel`, `isPhantomRecovery`.

---

## PHẦN II: MASTER TASK BREAKDOWN & CHECKLIST THỰC THI

```
[ ] Phase 11.5 — Deep Learning Predictive Maintenance (LSTM for Remaining Useful Life - RUL)
    ├── [ ] Task 11.5.1: Mở rộng Model Asset, tạo Model AssetRulPrediction & Django Migration
    ├── [ ] Task 11.5.2: Xây dựng Package Giải thuật eam_app/algorithms/predictive_rul/
    │       ├── constants.py: Siêu tham số & ngưỡng vật lý
    │       ├── model.py: Mạng PyTorch LSTM + Pure NumPy Inference Fallback
    │       ├── dataset_pipeline.py: Pipeline dữ liệu suy thoái FEMTO / UCI AI4I
    │       ├── guardrails.py: Bộ 10 quy tắc phòng vệ (Phantom clamp, Monotonic, Cold start)
    │       └── service.py: RULPredictiveService nhạc trưởng điều phối toàn diện
    ├── [ ] Task 11.5.3: Xây dựng Bộ Endpoints RESTful API & Serializers cho RUL
    ├── [ ] Task 11.5.4: Tích hợp Liên Hoàn 2 Tầng giữa Phase 11.4 và Phase 11.5
    ├── [ ] Task 11.5.5: Nâng Cấp Giao Diện Web Portal (RUL Health Card, Gauge, Phantom Banner)
    └── [ ] Task 11.5.6: Bộ Kiểm Thử Tự Động 12 Kịch Bản Nghiệm Thu (TC-RUL-01 -> TC-RUL-12)
```

### Bước 1: Mở Rộng Cơ Sở Dữ Liệu
- Cập nhật model `Asset` trong [assets/models.py](file:///d:/GameLinkNeverDie/eam-enterprise-assset-management/eam_app/assets/models.py): Thêm `current_rul_calendar_days`, `duty_cycle_ratio`, `rul_confidence_lower`, `rul_confidence_upper`, `rapid_degradation_alert`, `last_rul_predicted_at`.
- Tạo model `AssetRulPrediction` lưu lịch sử dự phóng phục vụ phân tích xu hướng và đối soát kiểm toán.
- Chạy `makemigrations` và `migrate`.

### Bước 2: Đóng Gói Package Giải Thuật `predictive_rul`
- Tạo module chuyên biệt [eam_app/algorithms/predictive_rul/](file:///d:/GameLinkNeverDie/eam-enterprise-assset-management/eam_app/algorithms/):
  - `model.py`: Mạng 2 tầng LSTM gọn nhẹ kết hợp Monte Carlo Dropout ($M=20$).
  - `guardrails.py`: Cài đặt trọn vẹn 10 quy tắc nghiệp vụ phòng thủ (Cold Start Bypass $<15$ mẫu, Phantom Recovery Clamp $>30\%$, Monotonic Filter $\epsilon=1.0$, Dynamic Lead-Time Critical Threshold $\max(14, \text{lead\_time} + 5)$).
  - `service.py`: Nhạc trưởng `RULPredictiveService` nạp chuỗi trượt 30x4, suy diễn, cập nhật tài sản, tra cứu kho phụ tùng và tự động tạo phiếu PM đón đầu.

### Bước 3: Tích Hợp API RESTful
- Thêm các endpoint tại [assets/views.py](file:///d:/GameLinkNeverDie/eam-enterprise-assset-management/eam_app/assets/views.py) và [assets/urls.py](file:///d:/GameLinkNeverDie/eam-enterprise-assset-management/eam_app/assets/urls.py):
  - `GET /api/v1/assets/{id}/rul-prediction/`
  - `POST /api/v1/assets/{id}/rul-prediction/run/`
  - `POST /api/v1/assets/{id}/rul-prediction/override-phantom/`
  - `GET /api/v1/predictive-maintenance/critical-assets/`

### Bước 4: Tích Hợp Hai Tầng (11.4 $\rightarrow$ 11.5)
- Trong [ConditionMonitoringEngine.process_readings()](file:///d:/GameLinkNeverDie/eam-enterprise-assset-management/eam_app/algorithms/anomaly_detection/engine.py), khi phát hiện bất thường đo đạc, tự động kích hoạt tính toán RUL và gom cảnh báo phát 1 thông báo duy nhất.

### Bước 5: Nâng Cấp Web Portal UI
- Cập nhật [asset_registry.html](file:///d:/GameLinkNeverDie/eam-enterprise-assset-management/eam_app/templates/asset_registry.html):
  - Thêm RUL Health Card trực quan với dải bóng mờ khoảng tin cậy 90%.
  - Thêm Banner cảnh báo Phantom Recovery kèm nút Quản đốc Override.
  - Tích hợp nút bấm kiểm tra RUL tức thời.

### Bước 6: Bộ Kiểm Thử Tự Động Toàn Diện
- Viết test suite `eam_app/algorithms/tests/test_predictive_maintenance_rul.py` kiểm chứng $100\%$ 12 test cases:
  - `TC-RUL-01`: Chặn tài sản tĩnh
  - `TC-RUL-02`: Bypass khởi động nguội (< 15 mẫu đo RUNNING)
  - `TC-RUL-03`: Lọc bỏ trạng thái IDLE / STANDBY
  - `TC-RUL-04`: Vector 4 chiều kèm biến tải trọng chống báo động giả
  - `TC-RUL-05`: Kẹp chặn bẫy hồi phục ảo Phantom Recovery
  - `TC-RUL-06`: Bộ lọc suy thoái đơn điệu vật lý
  - `TC-RUL-07`: Ước lượng độ bất định Monte Carlo Dropout
  - `TC-RUL-08`: Ngưỡng Critical động theo Lead-Time kho phụ tùng
  - `TC-RUL-09`: Hợp nhất cảnh báo 2 tầng 11.4 + 11.5
  - `TC-RUL-10`: Báo động gia tốc suy thoái đột biến (Rapid Degradation)
  - `TC-RUL-11`: Kẹp trần Piece-wise Linear ($RUL \le 125$)
  - `TC-RUL-12`: Tự động tra kho và sinh bản thảo Work Order đón đầu

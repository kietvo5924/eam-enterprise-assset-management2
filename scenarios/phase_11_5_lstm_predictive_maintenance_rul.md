# Thiết Kế Hệ Thống & Đặc Tả Kỹ Thuật: Task 11.5 — Deep Learning Predictive Maintenance (LSTM for Remaining Useful Life - RUL)

Tài liệu này xác định kiến trúc mô hình học sâu chuỗi thời gian (Time-Series Deep Learning), quy trình tiền xử lý dữ liệu và tạo chuỗi trượt 4 chiều (Sliding-Window 4-Feature Sequence Generation), tích hợp tập dữ liệu suy thoái công nghiệp thực tế (**FEMTO / PRONOSTIA Bearing Degradation Dataset & UCI AI4I Industrial Maintenance**), kiến trúc mạng nơ-ron hồi quy LSTM (Long Short-Term Memory) kết hợp định lượng độ bất định **Monte Carlo Dropout**, dịch vụ suy diễn thời gian thực trên CPU, và **bộ kịch bản kiểm thử chấp nhận & trường hợp biên (Acceptance Criteria & Edge Cases)** cho bài toán **Dự Đoán Tuổi Thọ Hoạt Động Còn Lại (Remaining Useful Life - RUL)** trong hệ thống Quản lý Tài sản Doanh nghiệp (EAM).

Tài liệu đóng vai trò là **Đặc Tả Kỹ Thuật & Chuẩn Kiểm Thử (Technical Specification & Audit Baseline)** nhằm đối chiếu, rà soát và thực thi trọn vẹn toàn bộ tính năng mà không bị thiếu sót bất kỳ nghiệp vụ enterprise nào.

---

## 1. Mục Tiêu & Phạm Vi (Objective & Scope)

### 1.1. Bản Chất Nghiệp Vụ Của Bảo Trì Dự Đoán (Predictive Maintenance - PdM)
Trong quản lý tài sản hiện đại, hệ thống chuyển dịch từ bảo trì bị động (hỏng mới sửa) và bảo trì định kỳ (cứ đến hạn là thay thế dù linh kiện còn tốt) sang **Bảo trì dự đoán (Predictive Maintenance)**:
- Mô hình học sâu phân tích chuỗi dữ liệu suy thoái để trả lời câu hỏi chiến lược: *"Thiết bị này còn hoạt động an toàn được bao nhiêu ngày/giờ vận hành nữa trước khi hỏng hoàn toàn (RUL)?"*.
- Doanh nghiệp chủ động chuẩn bị vật tư, điều phối kỹ thuật viên và dừng máy theo kế hoạch, tối ưu hóa $100\%$ vòng đời tài sản và triệt tiêu nguy cơ dừng dây chuyền đột xuất gây thiệt hại lớn.

### 1.2. Mối Quan Hệ Phối Hợp 2 Tầng Giữa Task 11.4 và Task 11.5 (The Two-Stage Pipeline)
Hệ thống được thiết kế theo kiến trúc phòng vệ 2 tầng liên hoàn:
- **Tầng 1 (Task 11.4 - Tuyến Tiền Trạm)**: Phát hiện dị biệt tức thời tại một điểm đo (`Point Anomaly Detection`) bằng Sliding Z-Score và Isolation Forest siêu nhẹ ngay khi kỹ thuật viên lưu số đo. Trả lời: *"Hôm nay thông số có dấu hiệu bất thường không?"*.
- **Tầng 2 (Task 11.5 - Tuyến Chiến Lược)**: Dự đoán quỹ đạo suy thoái tương lai (`Trajectory Prognostics`) bằng mạng LSTM trên chuỗi 30 lần đo vận hành thực tế. Trả lời: *"Với tốc độ suy thoái này, còn chính xác bao nhiêu ngày vận hành nữa thì thiết bị chạm ngưỡng hỏng hoàn toàn?"*.
- **Cơ Chế Liên Hoàn & Hợp Nhất Cảnh Báo (Alert Consolidation)**: Khi Tầng 1 phát hiện bất thường ($|Z| \ge 3.0$ hoặc Isolation Forest cảnh báo Outlier), hệ thống tự động kích hoạt Tầng 2 để tính toán lại RUL mới nhất. Toàn bộ thông điệp cảnh báo từ 2 tầng được gom thành **1 thông báo duy nhất**, tránh gây bão hòa cảnh báo (Alert Fatigue).

---

## 2. Ràng Buộc Kế Thừa Hệ Thống (Existing System Constraints & Codebase Reuse)

- **Tái Sử Dụng Mô Hình Multi-Tenancy**: Mọi dữ liệu đo đạc, suy diễn RUL và đề xuất bảo trì đều kế thừa `BaseTenantModel`, bảo đảm phân lập hoàn toàn giữa các Tenant qua `TenantManager`.
- **Tái Sử Dụng Thực Thể Nghiệp Vụ Có Sẵn**:
  - `MeterReading`: Nguồn dữ liệu chuỗi thời gian 30 lần đo `RUNNING` gần nhất (`vibration_rms`, `bearing_temperature`, `hydraulic_pressure`, kết hợp thông số tải `load_factor` hoặc công suất động cơ).
  - `Asset`: Cập nhật chỉ số `current_rul_days`, `rul_risk_level`, `rul_confidence_lower`, `rul_confidence_upper`, `is_phantom_recovery`.
  - `SparePart`: Kiểm tra tự động số lượng tồn kho khả dụng và thời gian đặt hàng (`lead_time_days`) khi RUL chạm ngưỡng cảnh báo đón đầu.
  - `WorkOrder`: Tự động tạo bản thảo phiếu bảo trì phòng ngừa đón đầu (`type = 'PREDICTIVE_PM'`) khi RUL chạm mức nguy cấp.
- **Tiền Tệ Chuẩn Hóa**: Mọi chi phí ước tính linh kiện thay thế tuân thủ chuẩn `Decimal` / `DECIMAL(18, 2)` Việt Nam Đồng (VNĐ).

---

## 3. Yêu Cầu Nghiệp Vụ & 10 Quy Tắc Cốt Lõi (Business Requirements & Core Rules)

Toàn bộ logic học sâu dự đoán RUL phải tuân thủ nghiêm ngặt 10 quy tắc nghiệp vụ phòng thủ sau:

### Quy Tắc 1: Vector Đặc Trưng 4 Chiều Kèm Biến Trạng Thái Tải (4-Feature Load-Aware Vector Guardrail)
- **Điểm Yếu Nghiệp Vụ**: Nếu chỉ dùng 3 cảm biến rung, nhiệt, áp suất, khi nhà máy ép tiến độ chạy quá tải 110%, độ rung và nhiệt độ tăng vọt sẽ khiến LSTM hoảng loạn báo RUL sụt từ 100 ngày xuống 5 ngày dù vòng bi hoàn toàn bình thường.
- **Quy Tắc Bắt Buộc**:
  1. Đầu vào của mạng LSTM bắt buộc là ma trận 4 chiều $(W = 30, \text{Features} = 4)$:
     $$X_t = [v_{\text{vibration\_rms}}, \; \Delta T_{\text{bearing}}, \; v_{\text{pressure}}, \; L_{\text{load\_factor}}]$$
     trong đó $\Delta T_{\text{bearing}} = T_{\text{bearing}} - T_{\text{ambient}}$ (loại trừ biến thiên thời tiết theo Task 11.4).
  2. Hệ số tải $L_{\text{load\_factor}} \in [0.2, 1.5]$ được tự động thu thập từ cảm biến Dòng điện Motor / Vòng quay RPM hoặc do kỹ thuật viên chọn (`LOW = 0.5`, `NORMAL = 1.0`, `HEAVY = 1.2`, `OVERLOAD = 1.4`).
  3. Mô hình phân biệt rõ ràng: Rung/nhiệt cao do chạy quá tải tạm thời vs. Rung/nhiệt cao do mài mòn rỗ bề mặt vòng bi.

### Quy Tắc 2: Ngưỡng Khởi Động Nguội & Bỏ Qua Chuỗi Ngắn (Short-Sequence Cold Start & Bypass Threshold)
- **Điểm Yếu Nghiệp Vụ**: Máy mới đưa vào vận hành hoặc vừa đại tu xong mới có 5 lần đo. Nếu nhồi 25 số 0 (Zero-padding) vào cửa sổ $W=30$, LSTM sẽ suy diễn sai lệch nghiêm trọng (ví dụ: máy mới keng nhưng báo 5 ngày hỏng).
- **Quy Tắc Bắt Buộc**:
  1. **Ngưỡng Bỏ Qua (Bypass Threshold $N_{\text{min}} = 15$)**: Nếu số bản ghi đo đạc hợp lệ ở trạng thái `RUNNING` sau lần sửa chữa gần nhất $< 15$, hệ thống **KHÔNG chạy mô hình LSTM**.
  2. API trả về `current_rul_days = null`, trường trạng thái ghi nhận: `CALIBRATING (x/15 readings)`.
  3. Trong giai đoạn thu thập dữ liệu gốc này, hệ thống áp dụng bảo trì định kỳ truyền thống theo khuyến cáo tĩnh của nhà sản xuất (OEM MTBF).

### Quy Tắc 3: Lọc Bỏ Trạng Thái Nghỉ & Chuẩn Hóa Ngày Vận Hành Thực Tế (Operating Days vs Calendar Days Guardrail)
- **Điểm Yếu Nghiệp Vụ**: Trạm bơm chạy luân phiên (Bơm A chạy ngày lẻ, Bơm B chạy ngày chẵn). Ngày Bơm A nghỉ (`STANDBY`), rung nhiệt gần bằng 0. Nạp xen kẽ dữ liệu nghỉ/chạy khiến chuỗi trượt bị gián đoạn và RUL nảy loạn xạ.
- **Quy Tắc Bắt Buộc**:
  1. Bộ lọc tiền xử lý bắt buộc loại bỏ mọi bản ghi có trạng thái `IDLE` hoặc `STANDBY`. Chuỗi 30 Sequence nạp vào LSTM phải là **30 lần đo khi thiết bị đang chạy (`RUNNING`)**.
  2. Đơn vị dự đoán gốc của LSTM là **Ngày Vận Hành Thực Tế (Operating Days - OpDays)** hoặc Giờ Vận Hành (Operating Hours).
  3. Khi hiển thị cho người quản lý, hệ thống tính toán quy đổi sang Ngày Dương Lịch (Calendar Days) dựa trên hệ số tải chu kỳ luân phiên (Duty Cycle Ratio $D_c$):
     $$\text{CalendarDays} = \frac{\text{OperatingDays}}{D_c} \quad (0 < D_c \le 1.0)$$
     *(Ví dụ: Còn 15 ngày vận hành thực tế, máy chạy luân phiên 50% thời gian $\rightarrow$ Còn 30 ngày dương lịch).*

### Quy Tắc 4: Bẫy Trôi Dạt Khái Niệm Do Bảo Trì Nhỏ & Kẹp Chặn Hồi Phục Ảo (Micro-Maintenance Drift & Phantom Recovery Clamp)
- **Điểm Yếu Nghiệp Vụ**: Máy ở mức `HIGH RISK` (RUL = 20 ngày). Kỹ thuật viên bơm thêm mỡ bôi trơn hoặc siết ốc. Rung và nhiệt giảm nhẹ tạm thời. LSTM thấy số đo giảm tưởng máy đã "trẻ lại" và tăng vọt RUL lên 80 ngày. Nhưng thực tế mỡ chỉ là giải pháp tình thế, rãnh bi đã xước sâu và sẽ vỡ sau 15 ngày.
- **Quy Tắc Bắt Buộc**:
  1. Hệ thống lưu vết các lệnh công việc can thiệp nhỏ (`MICRO_MAINTENANCE`: bơm mỡ, siết ốc, vệ sinh bề mặt, căn chỉnh dây curoa) khác biệt hoàn toàn với thay mới phụ tùng (`CORE_REPLACEMENT`).
  2. Nếu sau một hành động `MICRO_MAINTENANCE`, giá trị RUL mô hình tính toán đột ngột tăng vọt $> 30\%$ so với RUL trước can thiệp:
     - Hệ thống kích hoạt cờ cảnh báo: `is_phantom_recovery = True` (**Cảnh Báo Suy Diễn Ảo - Phantom Recovery Warning**).
     - **Khóa Chặn RUL (Clamp Rule)**: Giữ nguyên chỉ số RUL ở mức trước khi can thiệp:
       $$RUL_t = \min\big(RUL_{\text{model}}, \;\; RUL_{t-1}\big)$$
     - Duy trì mức rủi ro `HIGH RISK`, cảnh báo quản đốc: *"Độ rung giảm tạm thời do bôi trơn/siết ốc. Không tăng RUL vì linh kiện chưa được thay mới cốt lõi."*

### Quy Tắc 5: Ràng Buộc Suy Thoái Đơn Điệu Vật Lý (Physics-Informed Monotonic Degradation Filter)
- **Điểm Yếu Nghiệp Vụ**: Trong điều kiện vận hành bình thường không có sửa chữa, máy móc kim loại chỉ có thể mòn đi chứ không thể tự lành lặn. Dao động đo đạc ngẫu nhiên giữa các ngày có thể làm RUL hôm nay là 25 ngày, ngày mai vọt lên 30 ngày.
- **Quy Tắc Bắt Buộc**:
  1. Áp dụng bộ lọc suy thoái đơn điệu (Monotonic Degradation Filter):
     $$RUL_{\text{filtered}}(t) = \min\Big(RUL_{\text{filtered}}(t-1), \;\; RUL_{\text{pred}}(t) + \epsilon_{\text{noise}}\Big)$$
     với dung sai nhiễu cảm biến $\epsilon_{\text{noise}} = 1.0$ ngày.
  2. RUL chỉ được phép tăng khi và chỉ khi có bản ghi Work Order hoàn thành thuộc nhóm **Thay thế phụ tùng cốt lõi (`CORE_REPLACEMENT` / `OVERHAUL`)**.

### Quy Tắc 6: Định Lượng Độ Bất Định Bằng Monte Carlo Dropout (Uncertainty Quantification via MC-Dropout)
- **Điểm Yếu Nghiệp Vụ**: Dự đoán một con số điểm duy nhất (ví dụ: 18 ngày) không cho biết mô hình tự tin đến mức nào. Khi dữ liệu đo đạc bị nhiễu hoặc máy gặp dạng suy thoái lạ chưa từng học, dự đoán điểm có thể gây ngộ nhận chết người.
- **Quy Tắc Bắt Buộc**:
  1. Trong quá trình suy diễn (Inference), giữ nguyên các lớp Dropout hoạt động (`model.train()` mode cục bộ cho Dropout) và thực hiện $M = 20$ lần suy diễn ngẫu nhiên (Monte Carlo Dropout).
  2. Tính giá trị trung bình $\mu_{\text{RUL}}$ và độ lệch chuẩn $\sigma_{\text{RUL}}$:
     $$\mu_{\text{RUL}} = \frac{1}{M} \sum_{m=1}^M RUL^{(m)}, \quad \sigma_{\text{RUL}} = \sqrt{\frac{1}{M} \sum_{m=1}^M (RUL^{(m)} - \mu_{\text{RUL}})^2}$$
  3. Xuất khoảng tin cậy $90\%$ $[\mu - 1.645\sigma, \; \mu + 1.645\sigma]$.
  4. Nếu $\sigma_{\text{RUL}} > 10.0$ ngày, bật cờ cảnh báo `HIGH_PREDICTION_UNCERTAINTY` để khuyến cáo kỹ thuật viên kiểm tra thủ công.

### Quy Tắc 7: Cảnh Báo Thích Ứng Theo Thời Gian Đặt Hàng Phụ Tùng (Lead-Time Aware Predictive Alerting)
- **Điểm Yếu Nghiệp Vụ**: Quy tắc cứng báo động ở mốc $\le 14$ ngày sẽ thất bại nếu vòng bi đặc chủng nhập khẩu mất 30 ngày giao hàng (`lead_time_days = 30`). Đợi đến 14 ngày mới tạo phiếu PM thì máy chắc chắn phải dừng chờ hàng suốt 16 ngày.
- **Quy Tắc Bắt Buộc**:
  1. Ngưỡng cảnh báo `CRITICAL RISK` được tính động theo thời gian giao hàng của phụ tùng cốt lõi liên kết với thiết bị:
     $$\text{Threshold}_{\text{CRITICAL}} = \max\Big(14, \;\; T_{\text{lead\_time\_days}} + 5\Big)$$
     *(Ví dụ: Linh kiện có lead time 25 ngày $\rightarrow$ Ngưỡng sinh phiếu PM tự động nâng lên $25 + 5 = 30$ ngày).*
  2. Nếu kho không còn đủ số lượng phụ tùng khả dụng, hệ thống kích hoạt đồng thời quy trình dự thảo yêu cầu mua sắm vật tư (Purchase Requisition Draft).

### Quy Tắc 8: Hợp Nhất Cảnh Báo Hai Tầng Chống Bão Hòa (Two-Stage Alert Consolidation Guardrail)
- **Điểm Yếu Nghiệp Vụ**: Khi Task 11.4 phát hiện bất thường gửi 1 email báo động đỏ, 30 giây sau kích hoạt Task 11.5 chạy LSTM phát hiện CRITICAL RISK tiếp tục gửi thêm 1 email báo động đỏ nữa về cùng 1 thiết bị. Quản đốc nhận liên tiếp 2 tin nhắn gây rối loạn và nhờn cảnh báo (Alert Fatigue).
- **Quy Tắc Bắt Buộc**:
  1. Áp dụng cơ chế gom cảnh báo (Alert Consolidation Window 5 phút).
  2. Khi Tầng 1 kích hoạt Tầng 2, Tầng 1 tạm hoãn phát thông báo ra ngoài (đặt cờ `PENDING_RUL_STAGE2`).
  3. Khi Tầng 2 hoàn tất suy diễn, hệ thống phát **1 thông báo hợp nhất duy nhất**:
     *"[CẢNH BÁO TỔNG HỢP] Bơm ly tâm P-101: Phát hiện bất thường rung độ Z-score 3.4. Mô hình LSTM dự báo RUL chỉ còn 12 ngày vận hành (Độ tin cậy 90%: 10–14 ngày). Đã tự động tạo bản thảo phiếu bảo trì đón đầu WO-2026-09-001."*

### Quy Tắc 9: Phát Hiện Gia Tốc Suy Thoái Đột Biến (Sudden Catastrophic Spike Detection)
- **Điểm Yếu Nghiệp Vụ**: Vòng bi bị nứt vỡ đột ngột (spalling), tốc độ suy thoái không diễn ra từ từ mà RUL sụt giảm $> 50\%$ chỉ trong vòng 3 ngày đo đạc. Nếu đợi theo quy trình PM định kỳ thông thường sẽ không kịp cứu máy.
- **Quy Tắc Bắt Buộc**:
  1. Theo dõi đạo hàm suy thoái:
     $$\Delta RUL_{\text{rate}} = \frac{RUL_{t-3} - RUL_t}{3} \quad (\text{ngày sụt giảm mỗi ngày đo})$$
  2. Nếu $\Delta RUL_{\text{rate}} \ge 5.0$ ngày/lần đo hoặc RUL giảm $> 50\%$ trong 3 lần đo liên tiếp:
     - Kích hoạt trạng thái `RAPID_DEGRADATION_ALARM`.
     - Tự động gán độ ưu tiên `URGENT` cho phiếu bảo trì đón đầu và thông báo khẩn cấp tới Trưởng ca trực.

### Quy Tắc 10: Phân Luồng Nghiêm Ngặt Thiết Bị Cơ Điện vs Tài Sản Tĩnh (Machinery vs Passive Asset Guardrail)
- **Điểm Yếu Nghiệp Vụ**: Người dùng chọn một chiếc bàn làm việc, ghế xoay hoặc tủ tài liệu rồi bấm "Dự đoán RUL bằng AI LSTM" gây lỗi tính toán hoặc trả về số ngày vô nghĩa.
- **Quy Tắc Bắt Buộc**:
  1. Chặn thực thi tại tầng dịch vụ và API: Chỉ cho phép kích hoạt mô hình LSTM RUL đối với các tài sản thuộc danh mục máy móc cơ khí, động lực (`asset_category.is_mechanical = True` hoặc có cấu hình giám sát rung/nhiệt).
  2. Các tài sản tĩnh bị từ chối với thông báo hướng dẫn chuẩn: *"Tài sản tĩnh không đo đạc rung nhiệt; tuổi thọ được quản lý qua Khấu hao đường thẳng tại Phân hệ 10.3"*.

---

## 4. Yêu Cầu Chức Năng & Luồng Xử Lý (Functional Requirements & Workflows)

### 4.1. Kiến Trúc Mạng Hồi Quy LSTM (Model Architecture Specification)
- **Kích thước Tensor đầu vào (Input Tensor Shape)**:
  $$(B, W, F) = (\text{BatchSize}, 30, 4)$$
  với $W = 30$ bước thời gian liên tiếp của 4 đặc trưng đã chuẩn hóa Min-Max:
  $$F = [v_{\text{vibration\_rms}}, \; \Delta T_{\text{bearing}}, \; v_{\text{pressure}}, \; L_{\text{load\_factor}}]$$
- **Chi Tiết Các Tầng Mạng**:
  1. `Layer 1 - nn.LSTM`: `input_size = 4`, `hidden_size = 64`, `batch_first = True`, xuất toàn bộ chuỗi trạng thái (`return_sequences = True`).
  2. `Layer 2 - nn.Dropout`: $p = 0.20$ (hoạt động cả khi Training và khi MC-Dropout Inference).
  3. `Layer 3 - nn.LSTM`: `input_size = 64`, `hidden_size = 32`, `batch_first = True`, chỉ lấy trạng thái ẩn cuối cùng $h_{30}$ (`return_sequences = False`).
  4. `Layer 4 - nn.Dropout`: $p = 0.20$.
  5. `Layer 5 - nn.Linear`: `in_features = 32`, `out_features = 1` (Hồi quy tuyến tính xuất giá trị RUL).
  6. `Output Activation`: `nn.ReLU()` bảo đảm tuổi thọ dự đoán $RUL \ge 0$.

### 4.2. Thuật Toán Gán Nhãn Huấn Luyện (Piece-wise Linear RUL Target)
Trong dữ liệu huấn luyện (FEMTO / PRONOSTIA & UCI AI4I), áp dụng hàm kẹp trần với ngưỡng tối đa $RUL_{\text{max\_clip}} = 125$ chu kỳ/ngày:
$$RUL_{\text{target}}(t) = \min\Big(125, \;\; T_{\text{failure}} - t\Big)$$
Điều này ngăn chặn mô hình học vẹt sai lệch trong giai đoạn đầu khi thiết bị hoàn toàn mới tinh.

### 4.3. Quy Trình Suy Diễn Monte Carlo Dropout & Lọc Đơn Điệu
```python
def predict_rul_with_uncertainty(model, input_sequence_30x4, num_mc_passes=20, previous_rul=None, is_micro_maint=False):
    """
    input_sequence_30x4: Tensor shape (1, 30, 4)
    num_mc_passes: 20 iterations
    """
    model.eval()
    # Kích hoạt Dropout layers trong quá trình suy diễn
    for m in model.modules():
        if isinstance(m, torch.nn.Dropout):
            m.train()
            
    predictions = []
    with torch.no_grad():
        for _ in range(num_mc_passes):
            pred = model(input_sequence_30x4)
            predictions.append(pred.item())
            
    rul_mean = float(np.mean(predictions))
    rul_std = float(np.std(predictions))
    rul_lower = max(0.0, rul_mean - 1.645 * rul_std)
    rul_upper = rul_mean + 1.645 * rul_std
    
    # Kiểm tra Bẫy Phantom Recovery
    is_phantom_recovery = False
    if is_micro_maint and previous_rul is not None:
        if rul_mean > previous_rul * 1.30:
            is_phantom_recovery = True
            rul_mean = previous_rul  # Clamp RUL không cho tăng ảo
            
    # Áp dụng bộ lọc suy thoái đơn điệu nếu không có thay thế cốt lõi
    if previous_rul is not None and not is_phantom_recovery:
        rul_mean = min(previous_rul, rul_mean + 1.0)
        
    return {
        "rul_mean": round(rul_mean, 1),
        "rul_std": round(rul_std, 2),
        "confidence_lower": round(rul_lower, 1),
        "confidence_upper": round(rul_upper, 1),
        "is_phantom_recovery": is_phantom_recovery,
        "high_uncertainty": (rul_std > 10.0)
    }
```

---

## 5. Quy Tắc Bảo Mật, Phân Quyền & Đa Khách Hàng (Security, RBAC & Multi-Tenant Rules)

- **Cô Lập Đa Khách Hàng (Multi-Tenancy)**: Quá trình suy diễn và dữ liệu huấn luyện được cách ly hoàn toàn theo `tenant_id`. Kết quả RUL và cảnh báo chỉ người dùng thuộc Tenant đó mới có quyền truy cập.
- **Phân Quyền Theo Vai Trò (RBAC)**:
  - `MAINTENANCE_MANAGER`: Toàn quyền xem kết quả RUL, phân tích xu hướng suy thoái, ghi đè cờ Phantom Recovery và phê duyệt phiếu PM đón đầu.
  - `TECHNICIAN`: Xem thẻ sức khỏe và khuyến cáo an toàn khi thực hiện bảo trì, nhập hệ số tải máy tại hiện trường.
  - `AUDITOR`: Xem lịch sử dự phóng và độ chính xác của mô hình qua các chu kỳ thay thế phụ tùng.

---

## 6. Kiến Trúc & Luồng Dữ Liệu Hai Tầng Hợp Nhất (Architecture & Data Flow)

```
[Sự Kiện Kích Hoạt (Trigger Event)]
  ├── (A) Task 11.4 phát hiện bất thường đo đạc (|Z| >= 3.0 hoặc Outlier)
  ├── (B) Kỹ thuật viên lưu số đo MeterReading RUNNING định kỳ
  └── (C) Tác vụ định kỳ quét kiểm tra hàng tuần Celery Beat
          │
          ▼
[Kiểm Tra Điều Kiện Tiên Quyết (Prerequisite Guards)]
  ├── 1. Kiểm tra danh mục thiết bị (Loại trừ tài sản tĩnh theo Quy Tắc 10)
  ├── 2. Lọc bỏ trạng thái IDLE / STANDBY (Chỉ lấy RUNNING theo Quy Tắc 3)
  └── 3. Kiểm tra số lượng mẫu đo RUNNING sau sửa chữa gần nhất:
         └── Nếu N < 15 ──► Trả về CALIBRATING (x/15), BỎ QUA LSTM (Quy Tắc 2)
          │ (Nếu N >= 15)
          ▼
[Xây Dựng Ma Trận Đầu Vào (W=30, F=4)]
  ├── Lấy 30 lần đo RUNNING gần nhất: [Vibration, ΔT_bearing, Pressure, Load_Factor]
  └── Chuẩn hóa MinMax Scaling về đoạn [0, 1] (Quy Tắc 1)
          │
          ▼
[Suy Diễn PyTorch LSTM CPU với Monte Carlo Dropout] (Quy Tắc 6)
  ├── Thực hiện 20 lần forward pass với Dropout hoạt động
  ├── Tính Mean RUL, Std Dev, Khoảng tin cậy 90% [Lower, Upper]
  ├── Kiểm tra Bẫy Micro-maintenance Phantom Recovery (Quy Tắc 4)
  └── Áp dụng Bộ lọc suy thoái đơn điệu Monotonic Filter (Quy Tắc 5)
          │
          ▼
[Đánh Giá Ma Trận Rủi Ro & Lead-Time Phụ Tùng] (Quy Tắc 7, 9)
  ├── Tính ngưỡng động CRITICAL: max(14, lead_time_days + 5)
  ├── Đánh giá gia tốc suy thoái đột biến (Rapid Degradation Spike)
  ├── Cập nhật current_rul_days, rul_risk_level, confidence intervals trên Asset
  ├── Nếu HIGH RISK ──► Kiểm tra tồn kho phụ tùng SparePart
  └── Nếu CRITICAL RISK ──► Tự động tạo bản thảo Draft PM Work Order
          │
          ▼
[Cơ Chế Hợp Nhất Cảnh Báo (Alert Consolidation)] (Quy Tắc 8)
  └── Gộp báo cáo dị biệt (11.4) + kết quả RUL (11.5) ──► Phát 1 thông báo duy nhất
```

---

## 7. Mô Hình Dữ Liệu & Thực Thể (Data Model & Schema)

### 7.1. Bảng `assets` (Mở rộng trường theo dõi sức khỏe & RUL)
```sql
ALTER TABLE assets
  ADD COLUMN current_rul_days FLOAT NULL,
  ADD COLUMN current_rul_calendar_days FLOAT NULL,
  ADD COLUMN duty_cycle_ratio FLOAT DEFAULT 1.0,
  ADD COLUMN rul_confidence_lower FLOAT NULL,
  ADD COLUMN rul_confidence_upper FLOAT NULL,
  ADD COLUMN rul_risk_level VARCHAR(16) NULL, -- 'CALIBRATING', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
  ADD COLUMN is_phantom_recovery BOOLEAN DEFAULT FALSE,
  ADD COLUMN rapid_degradation_alert BOOLEAN DEFAULT FALSE,
  ADD COLUMN last_core_overhaul_at TIMESTAMP WITH TIME ZONE NULL,
  ADD COLUMN last_rul_predicted_at TIMESTAMP WITH TIME ZONE NULL;
```

### 7.2. Bảng `asset_rul_predictions` (Lịch sử dự phóng tuổi thọ)
```sql
CREATE TABLE asset_rul_predictions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id),
  asset_id UUID NOT NULL REFERENCES assets(id),
  predicted_rul_op_days FLOAT NOT NULL,
  predicted_rul_cal_days FLOAT NOT NULL,
  confidence_lower FLOAT NOT NULL,
  confidence_upper FLOAT NOT NULL,
  std_deviation FLOAT NOT NULL,
  risk_level VARCHAR(16) NOT NULL,
  trigger_source VARCHAR(32) NOT NULL, -- 'MANUAL', 'ANOMALY_TRIGGER_11_4', 'WEEKLY_SCAN'
  load_factor_average FLOAT NOT NULL,
  input_window_samples_count INT NOT NULL,
  is_phantom_recovery BOOLEAN DEFAULT FALSE,
  rapid_degradation_rate FLOAT NULL,
  action_taken VARCHAR(64) NOT NULL, -- 'CALIBRATING', 'MAINTAIN_PM', 'CHECK_INVENTORY', 'DRAFT_PM_CREATED'
  work_order_id UUID NULL REFERENCES work_orders(id),
  model_version VARCHAR(32) NOT NULL DEFAULT 'v1.0.0-cpu',
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

### 7.3. Bảng `meter_readings` (Bổ sung biến trạng thái tải)
```sql
ALTER TABLE meter_readings
  ADD COLUMN machine_state VARCHAR(16) DEFAULT 'RUNNING', -- 'RUNNING', 'WARM_UP', 'IDLE', 'STANDBY'
  ADD COLUMN ambient_temperature FLOAT NULL,
  ADD COLUMN load_factor FLOAT DEFAULT 1.0, -- Hệ số tải: 0.5 (Low), 1.0 (Normal), 1.2 (Heavy), 1.4 (Overload)
  ADD COLUMN motor_current_amp FLOAT NULL,
  ADD COLUMN shaft_rpm FLOAT NULL;
```

---

## 8. Đặc Tả Giao Diện Lập Trình (API Specifications & Contracts)

### Danh Mục Endpoints:

| Phương Thức | Đường Dẫn | Chức Năng |
| :--- | :--- | :--- |
| `GET` | `/api/v1/assets/{id}/rul-prediction/` | Lấy kết quả RUL chi tiết, khoảng tin cậy, phân tích tải và khuyến nghị |
| `POST` | `/api/v1/assets/{id}/rul-prediction/run/` | Kích hoạt dự đoán RUL tức thời (hỗ trợ nhập ghi đè load factor) |
| `GET` | `/api/v1/predictive-maintenance/critical-assets/` | Danh sách các thiết bị có nguy cơ cao hoặc gia tốc suy thoái đột biến |
| `POST` | `/api/v1/assets/{id}/rul-prediction/override-phantom/` | Quản đốc xác nhận bỏ qua cảnh báo Phantom Recovery sau thẩm định |

### Cấu Trúc Dữ Liệu Mẫu:

#### 1. Lấy kết quả dự đoán RUL (`GET /api/v1/assets/{id}/rul-prediction/`):
```json
{
  "success": true,
  "data": {
    "assetId": "ast-pump-01",
    "assetName": "Bơm ly tâm trục đứng P-101",
    "currentStatus": "ACTIVE",
    "operatingRulDays": 18.5,
    "calendarRulDays": 26.4,
    "dutyCycleRatio": 0.70,
    "confidenceInterval": {
      "lower": 15.2,
      "upper": 21.8,
      "stdDeviation": 2.01,
      "isHighUncertainty": false
    },
    "riskLevel": "HIGH",
    "riskLabel": "Nguy cơ cao (Cần chuẩn bị vật tư)",
    "isPhantomRecovery": false,
    "rapidDegradationRate": 1.2,
    "rapidDegradationAlert": false,
    "lastEvaluatedAt": "2026-09-17T10:30:00Z",
    "loadConditionSummary": {
      "averageLoadFactor": 1.05,
      "loadCategory": "NORMAL",
      "isLoadShiftDetected": false
    },
    "sparePartStatus": {
      "partCode": "BEARING-SKF-6205",
      "partName": "Vòng bi cầu đỡ chặn SKF 6205-2RSH",
      "availableQuantity": 2,
      "minimumRequired": 1,
      "leadTimeDays": 20,
      "dynamicCriticalThreshold": 25,
      "isStockSufficient": true
    },
    "recommendedAction": "Thời gian đặt hàng vòng bi là 20 ngày. RUL còn 18.5 ngày vận hành. Đã vượt ngưỡng an toàn động (25 ngày). Lên lịch bảo trì thay thế trong vòng 7 ngày tới."
  }
}
```

#### 2. Phản hồi khi thiết bị đang ở giai đoạn khởi động nguội (`CALIBRATING`):
```json
{
  "success": true,
  "data": {
    "assetId": "ast-cnc-02",
    "assetName": "Máy phay CNC Makino PS95 (Mới đại tu)",
    "currentStatus": "CALIBRATING",
    "validRunningSamples": 8,
    "requiredSamplesThreshold": 15,
    "operatingRulDays": null,
    "calendarRulDays": null,
    "riskLevel": "CALIBRATING",
    "message": "Thiết bị mới vận hành sau đại tu cốt lõi (8/15 lần đo RUNNING). Đang thu thập baseline chuẩn, tạm thời áp dụng kế hoạch bảo dưỡng định kỳ OEM (90 ngày)."
  }
}
```

---

## 9. Đặc Tả Trải Nghiệm Người Dùng (UI/UX Behavioral Specifications)

- **Đồng hồ đo sức khỏe thiết bị đa thông số (RUL Health Gauge)**:
  - Vòng cung đo hiển thị 4 phân vùng màu: Xanh lá (`LOW` > 60 ngày), Vàng (`MEDIUM` 30–60 ngày), Cam (`HIGH` ngưỡng động), Đỏ (`CRITICAL` chạm ngưỡng lead time).
  - Vạch bóng mờ (Shaded Band) thể hiện khoảng tin cậy $90\%$ của Monte Carlo Dropout $[\text{RUL}_{\text{lower}}, \text{RUL}_{\text{upper}}]$.
- **Thẻ Cảnh Báo "Phantom Recovery Warning" (Hồi phục ảo)**:
  - Khi cờ `is_phantom_recovery = True`, xuất hiện thanh banner màu vàng cam nhấp nháy: *"Cảnh báo: Chỉ số rung/nhiệt giảm tạm thời sau hành động bơm mỡ/siết ốc. RUL được giữ nguyên 20 ngày để bảo đảm an toàn."*
  - Nút bấm: *"Quản đốc xác thực ghi đè (Override)"* kèm hộp thoại yêu cầu nhập lý do kỹ thuật.
- **Biểu đồ suy thoái 4 trục**:
  - Trục 1: Rung động hiệu dụng (mm/s).
  - Trục 2: Nhiệt độ ổ trục vi sai $\Delta T$ (°C).
  - Trục 3: Hệ số tải máy $L_{\text{load\_factor}}$ (%).
  - Trục 4: Đường đếm ngược RUL dự báo kèm dải phân kỳ độ bất định.
- **Hộp thoại thông báo hợp nhất (Consolidated Notification Modal)**:
  - Khi xem thông báo khẩn cấp, người dùng thấy toàn bộ bối cảnh: Điểm đo vượt ngưỡng ở Task 11.4 $\rightarrow$ Kết quả RUL tương ứng ở Task 11.5 $\rightarrow$ Trạng thái kho phụ tùng $\rightarrow$ Nút xem/duyệt bản thảo Phiếu bảo trì đón đầu.

---

## 10. Tiêu Chí Chấp Nhận & Ma Trận Kịch Bản Kiểm Thử (Acceptance Criteria & Test Scenarios)

### 10.1. Ma Trận Kịch Bản Kiểm Thử Nghiệp Vụ & Mô Hình

| Mã Test | Tên Kịch Bản | Điều Kiện Thử Nghiệm | Hành Vi Kỳ Vọng | Trạng Thái |
| :--- | :--- | :--- | :--- | :--- |
| **TC-RUL-01** | Chặn phân tích tài sản tĩnh | Gọi API RUL cho bàn làm việc hoặc ghế văn phòng | Trả về `400 Bad Request`, hướng dẫn sử dụng module khấu hao Phân hệ 10.3 | Chưa thực hiện |
| **TC-RUL-02** | Ngưỡng khởi động nguội Short-Sequence | Thiết bị mới vận hành/đại tu chỉ có 6 bản ghi `RUNNING` | Bỏ qua mô hình LSTM, trả về `current_rul_days = null`, trạng thái `CALIBRATING (6/15)` | Chưa thực hiện |
| **TC-RUL-03** | Lọc bỏ trạng thái Standby trạm bơm | Bơm A chạy luân phiên, xen kẽ 15 ngày `RUNNING` và 15 ngày `STANDBY` | Tiền xử lý lọc sạch 15 bản ghi `STANDBY`, nạp đúng 30 bản ghi `RUNNING`, tính chuẩn đơn vị `OperatingDays` | Chưa thực hiện |
| **TC-RUL-04** | Biến tải trọng ngăn báo động giả | Thiết bị chạy quá tải $120\%$, rung/nhiệt tăng mạnh, $L_{\text{load\_factor}} = 1.2$ | LSTM nhận diện rung/nhiệt cao do tải, không làm sụt giảm RUL vô căn cứ | Chưa thực hiện |
| **TC-RUL-05** | Bẫy phục hồi ảo Phantom Recovery | Máy đang $RUL = 18$ ngày, kỹ thuật viên bơm mỡ, mô hình dự đoán $RUL = 65$ ngày | Bật cờ `is_phantom_recovery = True`, kẹp $RUL = 18$ ngày, giữ nguyên cảnh báo `HIGH RISK` | Chưa thực hiện |
| **TC-RUL-06** | Bộ lọc suy thoái đơn điệu | Dữ liệu đo đạc rung lắc ngẫu nhiên, ngày hôm sau RUL dự đoán tăng $4$ ngày | Bộ lọc kẹp trần $\le RUL_{t-1} + 1.0$, ngăn chặn RUL tự động trẻ hóa vô cớ | Chưa thực hiện |
| **TC-RUL-07** | Định lượng độ bất định MC-Dropout | Chạy suy diễn 20 lần với MC-Dropout | Tính đúng $\mu$ và $\sigma$. Nếu $\sigma > 10$ ngày, bật cờ `HIGH_PREDICTION_UNCERTAINTY` | Chưa thực hiện |
| **TC-RUL-08** | Ngưỡng động theo Lead-Time kho | Vòng bi có `lead_time_days = 25`, $RUL = 28$ ngày | Tự động nâng ngưỡng Critical lên $25+5=30$ ngày, kích hoạt tạo Draft PM Work Order đón đầu | Chưa thực hiện |
| **TC-RUL-09** | Hợp nhất cảnh báo 2 tầng 11.4 $\rightarrow$ 11.5 | Task 11.4 phát hiện Z-score 3.5, kích hoạt 11.5 dự đoán $RUL = 10$ ngày | Chỉ phát 1 thông báo hợp nhất duy nhất trong vòng 5 phút, không gửi 2 email riêng lẻ | Chưa thực hiện |
| **TC-RUL-10** | Phát hiện gia tốc suy thoái đột biến | Nứt rỗ vòng bi làm RUL tụt từ 40 ngày xuống 15 ngày trong 3 lần đo | Kích hoạt cờ `RAPID_DEGRADATION_ALARM`, gắn ưu tiên `URGENT` cho phiếu bảo trì | Chưa thực hiện |
| **TC-RUL-11** | Kẹp trần Piece-wise Linear | Dữ liệu máy mới tinh trong giai đoạn $T_{\text{failure}} - t = 180$ ngày | Gán nhãn huấn luyện kẹp chính xác ở mức $125.0$ ngày | Chưa thực hiện |
| **TC-RUL-12** | Tự động tra tồn kho và sinh Draft PM | $RUL = 12$ ngày (thấp hơn ngưỡng Critical) | Hệ thống kiểm tra số lượng tồn kho `SparePart`, tạo bản thảo Work Order phòng ngừa đón đầu | Chưa thực hiện |

---

## 11. Implementation Notes — For Implementation Phase Only

> [!IMPORTANT]
> **REFERENCE ONLY — DO NOT IMPLEMENT OR MODIFY CODE BASED ON THIS SECTION DURING SPEC REVIEW. These notes are intended for the implementation phase after the specification is approved.**

Phần này lưu trữ các chỉ dẫn kỹ thuật hạ tầng chi tiết để các kỹ sư tham khảo trong quá trình triển khai mã nguồn:

### 11.1. Cấu Trúc Khối Mạng PyTorch 4 Kênh & Monte Carlo Dropout
- Định nghĩa lớp mạng:
  ```python
  import torch
  import torch.nn as nn

  class LSTMRULPredictor(nn.Module):
      def __init__(self, input_dim=4, hidden_dim_1=64, hidden_dim_2=32, dropout_rate=0.20):
          super().__init__()
          self.lstm1 = nn.LSTM(input_size=input_dim, hidden_size=hidden_dim_1, batch_first=True)
          self.dropout1 = nn.Dropout(p=dropout_rate)
          self.lstm2 = nn.LSTM(input_size=hidden_dim_1, hidden_size=hidden_dim_2, batch_first=True)
          self.dropout2 = nn.Dropout(p=dropout_rate)
          self.fc = nn.Linear(in_features=hidden_dim_2, out_features=1)
          self.relu = nn.ReLU()

      def forward(self, x):
          # x: (batch_size, 30, 4)
          out, _ = self.lstm1(x)
          out = self.dropout1(out)
          out, _ = self.lstm2(out)
          out = self.dropout2(out[:, -1, :])  # Lấy time step cuối cùng
          out = self.fc(out)
          return self.relu(out)
  ```
- Khi khởi tạo dịch vụ suy diễn, nạp trọng số qua `torch.load(weights_path, map_location=torch.device('cpu'))`. Bật chế độ CPU đa luồng qua `torch.set_num_threads(2)`.

### 11.2. Dữ Liệu Huấn Luyện FEMTO / PRONOSTIA & UCI AI4I
- **FEMTO Bearing Dataset**: Tập dữ liệu gia tốc rung động và nhiệt độ ổ trục suy thoái đến khi hỏng hoàn toàn (IEEE PHM 2012 Challenge). Trích xuất `RMS` độ rung và gia tốc đỉnh `Peak-to-Peak`.
- **UCI AI4I 2020 Predictive Maintenance**: Tích hợp các thuộc tính nhiệt độ môi trường, nhiệt độ quy trình, tốc độ quay [RPM], mô-men xoắn [Nm] và thời gian mài mòn dụng cụ [Tool Wear min].

### 11.3. Liên Kết Thông Minh Với Kho Phụ Tùng (Lead-Time Aware Join)
Trong logic sinh cảnh báo:
```python
# Truy vấn lead time phụ tùng liên kết
spare_part = asset.primary_spare_part
lead_time = spare_part.lead_time_days if spare_part else 0
critical_threshold = max(14, lead_time + 5)
```

---

## 12. Kế Hoạch Triển Khai & Nghiệm Thu (Implementation Checklist)

- [ ] **Task 11.5.1 — Industrial Dataset Mapping & 4-Feature Pipeline**
  - [ ] Xây dựng bộ nạp dữ liệu suy thoái vòng bi FEMTO / PRONOSTIA và UCI AI4I.
  - [ ] Thiết lập pipeline tạo ma trận chuỗi trượt $(W = 30, \text{Features} = 4)$: Vibrate, $\Delta T$, Pressure, Load Factor.
  - [ ] Cài đặt thuật toán kẹp trần Piece-wise Linear RUL Target ($RUL \le 125$).
- [ ] **Task 11.5.2 — PyTorch LSTM CPU Inference Service & MC-Dropout**
  - [ ] Xây dựng kiến trúc mạng 2 lớp LSTM gọn nhẹ phục vụ suy diễn thuần CPU.
  - [ ] Cài đặt vòng lặp suy diễn Monte Carlo Dropout ($M=20$) trích xuất khoảng tin cậy 90%.
  - [ ] Đóng gói `RULInferenceService` với cơ chế tải trọng số an toàn.
- [ ] **Task 11.5.3 — Cold Start Bypass & Standby Filtering Engine**
  - [ ] Cài đặt quy tắc Bypass Threshold: Bỏ qua LSTM và gán nhãn `CALIBRATING` khi số mẫu `RUNNING` $< 15$.
  - [ ] Cài đặt bộ lọc loại bỏ mẫu `IDLE` / `STANDBY` và thuật toán quy đổi `OperatingDays` sang `CalendarDays`.
- [ ] **Task 11.5.4 — Phantom Recovery Clamp & Monotonic Filter**
  - [ ] Lưu vết lịch sử `MICRO_MAINTENANCE` và kích hoạt cờ `is_phantom_recovery` khi RUL tăng vọt $> 30\%$.
  - [ ] Cài đặt bộ lọc suy thoái đơn điệu $RUL_t \le RUL_{t-1} + \epsilon$.
- [ ] **Task 11.5.5 — Dynamic Lead-Time Aware Risk Matrix & Alert Consolidation**
  - [ ] Cài đặt ma trận 4 cấp độ rủi ro với ngưỡng Critical động dựa trên `lead_time_days` của kho phụ tùng.
  - [ ] Tích hợp cơ chế gom thông báo (Alert Consolidation Window) liên kết hai tầng Task 11.4 $\rightarrow$ Task 11.5.
  - [ ] Tự động sinh bản thảo Work Order đón đầu (`type = 'PREDICTIVE_PM'`) khi chạm ngưỡng Critical.
- [ ] **Task 11.5.6 — UI Integration & Test Verification**
  - [ ] Thiết kế đồng hồ đo sức khỏe RUL có dải bóng mờ khoảng tin cậy và thẻ cảnh báo Phantom Recovery.
  - [ ] Triển khai bộ kiểm thử tự động 12 test cases (`TC-RUL-01` đến `TC-RUL-12`).

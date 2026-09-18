# Thiết Kế Hệ Thống & Đặc Tả Kỹ Thuật: Task 11.6 — Maintenance Cost & Budget Forecasting (Random Forest Regressor & Hybrid Budgeting Engine)

Tài liệu này xác định kiến trúc mô hình học máy hồi quy rừng ngẫu nhiên phân vị (**Quantile Regression Forests - QRF**), quy trình dự báo tài chính hai nhịp kết hợp giữa **Kế hoạch bảo dưỡng định kỳ xác định (Deterministic PM)** và **Dự phóng sự cố ngẫu nhiên (Stochastic CM Regressor)**, quy trình trích xuất đặc trưng chuỗi thời gian đa biến (**Multi-variate Time-Series Feature Engineering**), cơ chế phòng ngừa bẫy bảo trì hoãn lại (Deferred Maintenance Trap), xử lý điểm mù ngoại suy khi lạm phát, kiểm định tập trung chi phí Pareto bóc tách thiết bị "Quả chanh" (Lemon Assets), và **bộ kịch bản kiểm thử chấp nhận & trường hợp biên (Acceptance Criteria & Edge Cases)** cho bài toán **Quản Lý & Dự Báo Ngân Sách Bảo Trì Doanh Nghiệp** trong hệ thống Quản lý Tài sản Doanh nghiệp (EAM).

Tài liệu đóng vai trò là **Đặc Tả Kỹ Thuật & Chuẩn Kiểm Thử (Technical Specification & Audit Baseline)** nhằm đối chiếu, rà soát và thực thi trọn vẹn toàn bộ tính năng mà không bị thiếu sót bất kỳ nghiệp vụ enterprise nào.

---

## 1. Mục Tiêu & Phạm Vi (Objective & Scope)

### 1.1. Bản Chất Nghiệp Vụ Quản Trị Chi Phí Trong EAM
Chi phí bảo trì thường chiếm từ 15% đến 40% tổng chi phí vận hành của doanh nghiệp sản xuất. Phương thức lập ngân sách truyền thống thường gặp các hạn chế nghiêm trọng:
- **Thiếu minh bạch tại thời điểm phát sinh**: Chi phí chỉ được ghi nhận chung chung sau khi kết thúc kỳ kế toán, không bóc tách được từng lệnh bảo trì tiêu hao bao nhiêu tiền phụ tùng và bao nhiêu giờ công thợ.
- **Lập ngân sách cảm tính**: Thường lấy số liệu năm trước cộng thêm phần trăm dự phòng mà không tính đến sự xuống cấp lũy tiến của máy móc già cỗi hoặc nợ kỹ thuật tồn đọng (Backlog Debt).
- **Bẫy ngoại suy và thao túng số liệu**: Cắt giảm bảo trì tạm thời khiến chi phí giảm giả tạo, hoặc xả ngân sách mua vật tư cuối năm làm biến dạng dòng tiền.

### 1.2. Vai Trò Của Mô Hình Học Máy Lai Ghép (Hybrid Budgeting Engine)
Mô hình dự báo chi phí là điểm hội tụ tài chính của toàn bộ hệ thống EAM:
- **Tách bạch 2 dòng tiền**: Ngân sách kế hoạch PM xác định từ lịch (Task 3.6 & 3.7) + Ngân sách sự cố CM ngẫu nhiên dự báo bằng Random Forest Regressor.
- **Cầu nối với Tầng Dự đoán Suy thoái RUL (Task 11.5)**: Tự động chuyển đổi các cảnh báo thiết bị sắp hỏng thành nghĩa vụ tài chính vật tư dự phòng cho kỳ tới.
- **Định lượng rủi ro bằng Rừng Hồi Quy Phân Vị (QRF)**: Xuất kết quả trung vị $P_{50}$ kèm kịch bản xấu nhất $P_{90}$ để ban giám đốc và kế toán trưởng luôn có phương án dự phòng an toàn tiền mặt.

---

## 2. Ràng Buộc Kế Thừa Hệ Thống (Existing System Constraints & Codebase Reuse)

- **Tái Sử Dụng Mô Hình Multi-Tenancy**: Mọi dữ liệu chi phí, hạn mức ngân sách và mô hình huấn luyện kế thừa `BaseTenantModel`, bảo đảm phân lập hoàn toàn giữa các Tenant qua `TenantManager`.
- **Tái Sử Dụng Thực Thể Nghiệp Vụ Có Sẵn**:
  - `WorkOrder`: Trạng thái hoàn thành (`status = 'COMPLETED'`), loại công việc (`PM`, `CORRECTIVE`, `EMERGENCY`), thời điểm nghiệm thu.
  - `SparePart`: Đơn giá xuất kho bình quân tại thời điểm xuất kho (`unit_cost_snapshot`).
  - `Asset`: Nguyên giá, giá trị thay thế hiện hành (RAV), tình trạng hoạt động, trung tâm chi phí (`cost_center_id`).
  - `PmPlan`: Lịch bảo dưỡng định kỳ trong tương lai phục vụ tính toán phần ngân sách PM xác định.
- **Tiền Tệ Chuẩn Hóa**: Mọi chi phí và dự báo tuân thủ nghiêm ngặt kiểu dữ liệu `Decimal` / `DECIMAL(18, 2)` Việt Nam Đồng (VNĐ). Tuyệt đối không làm tròn thô bạo làm sai lệch số liệu kế toán.
- **Tích Hợp Hệ Thống Thông Báo Thời Gian Thực (Task 10.1)**: Tự động gửi cảnh báo mức `WARNING` hoặc `CRITICAL_OVERRUN` đến Quản trị viên và Kế toán trưởng khi ngân sách dự báo vượt ngưỡng.

---

## 3. Yêu Cầu Nghiệp Vụ & 10 Quy Tắc Cốt Lõi (Business Requirements & Core Rules)

Toàn bộ module quản lý chi phí và dự báo ngân sách phải tuân thủ nghiêm ngặt 10 quy tắc nghiệp vụ phòng thủ sau:

### Quy Tắc 1: Khóa Bất Biến Đơn Giá Snapshot Tại Thời Điểm Chốt Chi Phí (Immutable Point-in-Time Cost Snapshot Guardrail)
- **Điểm Yếu Nghiệp Vụ**: Nếu chi phí Work Order tính bằng cách liên kết trực tiếp sang bảng giá hiện tại của phụ tùng hoặc mức lương hiện tại của thợ, sau 1 năm giá cả tăng sẽ làm thay đổi toàn bộ số liệu chi phí các lệnh bảo trì đã quyết toán trong quá khứ, phá vỡ tính toàn vẹn của báo cáo tài chính và làm sai lệch dữ liệu huấn luyện AI.
- **Quy Tắc Bắt Buộc**:
  1. Vật tư xuất kho phải lưu trường đơn giá ảnh chụp (`unit_cost_snapshot`) tại chính thời điểm xuất kho.
  2. Giờ công thợ phải lưu trường đơn giá giờ công ảnh chụp (`hourly_rate_snapshot`) tại thời điểm thực hiện.
  3. Khi Work Order chuyển trạng thái sang `COMPLETED`: Hệ thống tính tổng chi phí, gán cờ khóa cứng `is_cost_frozen = True` và ghi nhận thời điểm khóa. Sau mốc này, chi phí là bất biến, không bao giờ được phép tự động tính lại theo giá hiện hành.
  4. Nếu có phát sinh nhập trả vật tư dư thừa, hệ thống tạo bản ghi ghi giảm chi phí tương ứng có lưu vết kiểm toán (Audit Trail) rõ ràng.

### Quy Tắc 2: Phân Tách Chi Phí Thường Xuyên (OpEx) vs Đại Tu Vốn Hóa (CapEx) (OpEx Routine vs CapEx Major Overhaul Guardrail)
- **Điểm Yếu Nghiệp Vụ**: Một sự cố đại tu lớn tiêu tốn hàng trăm triệu (được vốn hóa là CapEx theo chuẩn kế toán), trong khi bảo trì thường xuyên chỉ tốn vài chục triệu (OpEx). Nếu đưa trực tiếp con số đột biến cực trị này vào huấn luyện, mô hình sẽ bị méo mó và dự báo chi phí các tháng sau tăng vọt bất hợp lý.
- **Quy Tắc Bắt Buộc**:
  1. Tách bạch rõ giữa chi phí bảo trì thường xuyên (Routine OpEx) và chi phí đại tu lớn (Major Overhaul CapEx).
  2. Gắn nhãn `is_capital_overhaul = True` cho các lệnh sửa chữa lớn có thay thế cụm chi tiết cốt lõi hoặc chi phí vượt ngưỡng ngoại lai thống kê ($> 3\sigma$).
  3. Áp dụng biến đổi ổn định phương sai (Log-Transform $y = \ln(1 + \text{cost})$) cho chuỗi chi phí trước khi huấn luyện để nén biên độ các cú sốc cực trị. Khi xuất kết quả, mô hình giải biến đổi ngược về giá trị tiền tệ thực tế ($\exp(y) - 1$).

### Quy Tắc 3: Bẫy "Bảo Trì Hoãn Lại" & Biến Tích Lũy Nợ Kỹ Thuật (Deferred Maintenance Trap & Backlog Surge Guardrail)
- **Điểm Yếu Nghiệp Vụ**: Doanh nghiệp thắt lưng buộc bụng trong Quý 3, hủy bỏ hoặc hoãn 50% các phiếu bảo trì PM. Chi phí Quý 3 giảm mạnh. Nếu AI chỉ nhìn vào chi phí quá khứ, nó sẽ ngây thơ dự báo Quý 4 chi phí cũng rất thấp. Nhưng thực tế do không được bảo dưỡng, máy móc hỏng hàng loạt trong Quý 4 khiến chi phí vọt lên gấp 3 lần.
- **Quy Tắc Bắt Buộc**:
  1. Mô hình không được phép chỉ học từ "Chi phí đã tiêu". Bắt buộc phải bổ sung 2 đặc trưng tích lũy nợ kỹ thuật:
     - $N_{\text{backlog\_orders}}$: Số lượng Work Order bị quá hạn hoặc bị hoãn thực thi (`status IN ('PENDING', 'DEFERRED', 'OVERDUE')`).
     - $T_{\text{deferred\_hours}}$: Tổng số giờ bảo trì bị trì hoãn so với lịch chuẩn.
  2. Khi chi phí kỳ trước giảm nhưng tỷ lệ Backlog tăng vọt ($> 20\%$), mô hình nhận diện sự tích tụ rủi ro và kích hoạt dự báo **"Cú sốc chi phí bùng nổ" (Post-deferral Cost Surge)** ở các kỳ tiếp theo.

### Quy Tắc 4: Khắc Phục Điểm Mù Ngoại Suy Của Random Forest Khi Lạm Phát (Extrapolation Blindspot & Two-Step Hybrid Forecasting)
- **Điểm Yếu Nghiệp Vụ**: Về mặt toán học, cây quyết định và Random Forest không thể ngoại suy ngoài miền huấn luyện ($\hat{y} \le \max(y_{\text{train}})$). Nếu xảy ra lạm phát hoặc giá phụ tùng tăng 30% so với quá khứ, Random Forest sẽ luôn dự báo thấp hơn thực tế một cách nguy hiểm.
- **Quy Tắc Bắt Buộc**:
  1. Áp dụng cơ chế **Dự Báo Hai Nhịp (Two-Step Hybrid Forecasting)**:
     - **Nhịp 1 (Vật lý - Random Forest Regressor)**: Dự báo **Khối lượng tiêu hao thực tế**: Số lượng phụ tùng tiêu hao ($\hat{Q}_{\text{parts}}$) và Số giờ công bảo dưỡng ($\hat{H}_{\text{labor}}$). Vì khối lượng vật lý không bị lạm phát làm biến dạng nên nằm hoàn toàn trong miền học của Random Forest.
     - **Nhịp 2 (Tài chính - Post-Processing)**: Nhân khối lượng dự báo với Bảng đơn giá hiện hành kết hợp Chỉ số trượt giá vật tư (Material Price Index - $I_{\text{inflation}}$):
       $$\hat{Y}_{\text{CM\_Financial}} = \sum_{i} \Big(\hat{Q}_i \times \text{UnitCost}_i \times (1 + I_{\text{inflation}})\Big) + \Big(\hat{H}_{\text{labor}} \times \text{HourlyRate}\Big)$$
  2. Người dùng được phép cấu hình tỷ lệ lạm phát kỳ vọng theo năm (mặc định $4.5\%$/năm).

### Quy Tắc 5: Phân Tách Mua Hàng Lưu Kho vs Tiêu Hao Thực Tế Chống "Xả Ngân Sách Cuối Năm" (Inventory Purchasing vs Actual Consumption Guardrail)
- **Điểm Yếu Nghiệp Vụ**: Hiện tượng "Use it or lose it" vào tháng 12: Thấy dư ngân sách, quản đốc ồ ạt chi tiền mua phụ tùng chất đầy kho. Nếu lấy dòng tiền mua hàng này làm dữ liệu bảo trì, AI sẽ tưởng lầm rằng cứ đến tháng 12 là máy móc hỏng nghiêm trọng (tính mùa vụ ảo).
- **Quy Tắc Bắt Buộc**:
  1. Dữ liệu huấn luyện mô hình chi phí **TUYỆT ĐỐI LOẠI TRỪ 100%** các hóa đơn mua sắm vật tư nhập kho (`PurchaseOrder` / `StockIn`). Việc nhập kho là tài sản lưu động của kho, không phải chi phí vận hành bảo trì.
  2. Dữ liệu huấn luyện chỉ được lấy duy nhất từ **Chi phí Tiêu hao Thực tế (Actual Consumption Cost)** — tức là vật tư đã thực sự được xuất kho và gắn vào máy thông qua các Work Order đã nghiệm thu hoàn thành (`status = 'COMPLETED'`).

### Quy Tắc 6: Bóc Tách Chi Phí Ròng Bảo Hành & Bảo Hiểm (Warranty & Insurance Overlap / Net Cost Guardrail)
- **Điểm Yếu Nghiệp Vụ**: Động cơ CNC hỏng, chi phí thay thế hết 500 triệu nhưng được hãng bảo hành 100% (công ty không mất tiền). Nếu ghi nhận chi phí 500 triệu vào ngân sách bảo trì, AI sẽ dự báo công ty cần chuẩn bị một khoản tiền mặt khổng lồ vô lý vào tháng tới.
- **Quy Tắc Bắt Buộc**:
  1. Bảng `work_order_costs` lưu trữ rạch ròi 2 cấp độ chi phí:
     - **Chi phí gộp (Gross Cost)**: Toàn bộ giá trị vật tư và nhân công thực tế phát sinh (dùng để đo lường độ tin cậy và tần suất hư hỏng của máy móc).
     - **Chi phí ròng (Net Cost)**: Số tiền thực tế doanh nghiệp phải chi trả bằng tiền mặt:
       $$\text{Net Cost} = \text{Gross Cost} - (\text{Warranty Covered} + \text{Insurance Covered})$$
  2. Mô hình dự báo ngân sách tiền mặt **bắt buộc chỉ huấn luyện và dự phóng trên Chi Phí Ròng (Net Cost)**.

### Quy Tắc 7: Kiểm Định Tập Trung Chi Phí Pareto & Khấu Trừ Thiết Bị "Quả Chanh" (Cost Concentration 80/20 & Lemon Asset Skew Guardrail)
- **Điểm Yếu Nghiệp Vụ**: Cả nhà máy có 100 máy chạy êm, nhưng có 1 chiếc máy bơm tồi liên tục hỏng và "uống" hết 60% tổng ngân sách bảo trì. Nếu dự báo tổng thể ở mức vĩ mô, mô hình sẽ yêu cầu ngân sách rất lớn. Đến khi công ty thanh lý chiếc máy bơm đó đi, ngân sách tháng sau tụt mạnh nhưng AI vẫn dự báo mức cao ngất ngưởng.
- **Quy Tắc Bắt Buộc**:
  1. Tích hợp thuật toán **Kiểm định Phân bổ Chi phí Pareto (80/20 Cost Concentration Test)**:
     - Định kỳ tính toán tỷ lệ phân bổ chi phí trên toàn bộ danh mục tài sản.
     - Nếu phát hiện $\ge 50\%$ tổng chi phí bảo trì tập trung vào $\le 5\%$ số lượng thiết bị (nhóm "Lemon Assets / Bad Actors"), hệ thống bật cảnh báo XAI:
       *"Cảnh báo: 58% chi phí bảo trì kỳ qua tập trung vào Máy bơm P-101. Đề xuất ban giám đốc xem xét phương án thay thế/thanh lý thiết bị này để giảm tức thì 58% dự báo ngân sách tương lai."*
  2. Khi một tài sản chuyển trạng thái sang `DISPOSED` (Thanh lý), pipeline tiền xử lý tự động khấu trừ toàn bộ lịch sử chi phí của tài sản đó ra khỏi chuỗi dữ liệu huấn luyện, ngăn chặn việc mô hình bị ám ảnh bởi cái bóng chi phí của máy đã bán.

### Quy Tắc 8: Cơ Chế Ngân Sách Lai Ghép: Tách Bạch PM Xác Định vs CM Ngẫu Nhiên (Deterministic PM vs Stochastic CM Decoupling Guardrail)
- **Điểm Yếu Nghiệp Vụ**: Bảo trì định kỳ (PM) là kế hoạch đã được lên lịch rõ ràng theo chu kỳ ngày/giờ (Task 3.6 & 3.7), định mức vật tư và nhân công là biết trước $100\%$. Nếu ném chung vào để Random Forest "đoán mò" cả phần PM sẽ làm giảm độ chính xác và mất tính kiểm soát.
- **Quy Tắc Bắt Buộc**:
  Ngân sách tổng thể được tính theo công thức lai ghép (Hybrid Budget Architecture):
  $$\hat{Y}_{\text{Total}} = Y_{\text{Planned\_PM (Xác định từ lịch)}} + \hat{Y}_{\text{Breakdown\_CM (Dự báo bằng Random Forest)}} + \text{Buffer}_{\text{Contingency}}$$
  - $Y_{\text{Planned\_PM}}$: Tổng hợp tự động từ danh sách PM Plans có hạn trong kỳ tới $\times$ Định mức BOM phụ tùng và giờ công quy định.
  - $\hat{Y}_{\text{Breakdown\_CM}}$: Do mô hình Random Forest Regressor dự báo dựa trên chuỗi thời gian, độ tuổi máy móc và điều kiện vận hành.
  - $\text{Buffer}_{\text{Contingency}}$: Quỹ dự phòng khẩn cấp cấu hình theo chính sách của Tenant (thường từ 5% - 10%).

### Quy Tắc 9: Định Lượng Rủi Ro Bằng Rừng Hồi Quy Phân Vị (Quantile Regression Forests - QRF Guardrail)
- **Điểm Yếu Nghiệp Vụ**: Dự báo một con số trung bình duy nhất không giúp ban giám đốc phòng vệ được rủi ro cạn tiền mặt trong những tháng dây chuyền gặp sự cố dồn dập.
- **Quy Tắc Bắt Buộc**:
  1. Huấn luyện mô hình **Quantile Regression Forests (QRF)** để xuất đồng thời 3 phân vị có cơ sở toán học chặt chẽ:
     - Phân vị 10% ($P_{10}$): Kịch bản chi phí tối thiểu (máy móc vận hành rất ổn định).
     - Phân vị 50% ($P_{50}$): Kịch bản chi phí trung vị (dự báo cơ sở phục vụ kế hoạch tài chính).
     - Phân vị 90% ($P_{90}$): Kịch bản chi phí rủi ro xấu nhất (Worst-Case Scenario phục vụ quỹ dự phòng tiền mặt).
  2. Kế toán trưởng có thể tùy chọn căn cứ duyệt ngân sách theo $P_{50}$ hoặc $P_{90}$.

### Quy Tắc 10: Cầu Nối Nghĩa Vụ Tài Chính Từ Task 11.5 RUL & Quy Mô Tài Sản Thay Thế (Task 11.5 RUL Financial Liability & RAV Guardrail)
- **Điểm Yếu Nghiệp Vụ**: Phân hệ AI RUL (Task 11.5) phát hiện 3 động cơ công suất lớn sắp hỏng trong 30 ngày tới ($RUL \le 14$ ngày), nhưng phân hệ tài chính (Task 11.6) lại không biết gì về điều này, dẫn đến việc không dự trù đủ tiền mặt để mua động cơ thay thế.
- **Quy Tắc Bắt Buộc**:
  1. Tự động truy vấn danh sách các thiết bị có mức cảnh báo `CRITICAL RISK` hoặc `HIGH RISK` từ Task 11.5:
     $$\text{Liability}_{\text{PdM}} = \sum_{\text{Asset}_k \in \text{CRITICAL}} \text{PrimarySparePartCost}_k$$
     Khoản nghĩa vụ tài chính này được cộng trực tiếp vào ngân sách phụ tùng dự phóng của kỳ tới.
  2. Bổ sung chỉ số chuẩn hóa quốc tế: Tỷ lệ chi phí bảo trì trên Giá trị Thay thế Tài sản (% RAV - Replacement Asset Value):
     $$\% \text{Cost/RAV} = \frac{\text{Annual Maintenance Cost}}{\text{Total Fleet RAV}} \times 100\%$$
     Giúp ban lãnh đạo so sánh hiệu quả chi phí với chuẩn mực ngành (thường dao động $2.5\% - 4.5\%$).

---

## 4. Yêu Cầu Chức Năng & Luồng Xử Lý (Functional Requirements & Workflows)

### 4.1. Bộ 16 Đặc Trưng Chuỗi Thời Gian Đa Biến (Feature Engineering Pipeline)
1. **Chi phí ròng kỳ trễ 1** ($\text{NetCost}_{t-1}$).
2. **Chi phí ròng kỳ trễ 2** ($\text{NetCost}_{t-2}$).
3. **Chi phí ròng kỳ trễ 3** ($\text{NetCost}_{t-3}$).
4. **Trung bình trượt chi phí ròng 3 tháng** ($\text{SMA}_3$).
5. **Trung bình trượt chi phí ròng 6 tháng** ($\text{SMA}_6$).
6. **Độ biến động chi phí trượt 3 tháng** (Rolling Std Dev).
7. **Số lượng Work Order tồn đọng quá hạn** ($N_{\text{backlog\_orders}}$ - Bẫy bảo trì hoãn lại).
8. **Tổng số giờ bảo dưỡng bị hoãn lại** ($T_{\text{deferred\_hours}}$).
9. **Tổng số lượng thiết bị đang hoạt động** ($N_{\text{active\_assets}}$).
10. **Độ tuổi trung bình dàn máy móc** (tính theo năm vận hành).
11. **Tỷ lệ sự cố đột xuất** ($N_{\text{CM}} / N_{\text{Total}}$).
12. **Nghĩa vụ tài chính phụ tùng từ các máy RUL Critical Task 11.5** ($\text{Liability}_{\text{PdM}}$).
13. **Tổng giá trị thay thế toàn bộ dàn máy** (Total Fleet RAV).
14. **Tỷ trọng chi phí thuộc nhóm thiết bị trọng yếu Class A** (%).
15. **Hệ số mùa vụ** (Tháng trong năm từ 1 đến 12).
16. **Số ngày làm việc thực tế trong tháng** (loại trừ ngày nghỉ/lễ).

### 4.2. Kiến Trúc Mô Hình Quantile Regression Forests (QRF Specification)
- Tập hợp gồm 100 cây quyết định hồi quy (`n_estimators = 100`).
- Kiểm soát độ sâu tối đa `max_depth = 6`, `min_samples_split = 4`, `min_samples_leaf = 2` để chống quá khớp.
- Thay vì chỉ tính trung bình các lá cây, giữ lại toàn bộ phân phối giá trị tại các lá của từng cây để trích xuất hàm phân phối tích lũy có điều kiện $F(y|x)$ và tính toán chính xác các phân vị:
  $$Q_{\alpha}(x) = \inf \{y: F(y|x) \ge \alpha\}, \quad \alpha \in \{0.10, 0.50, 0.90\}$$

---

## 5. Quy Tắc Bảo Mật, Phân Quyền & Đa Khách Hàng (Security, RBAC & Multi-Tenant Rules)

- **Cô Lập Đa Khách Hàng (Multi-Tenancy)**: Mọi dữ liệu tài chính, hạn mức ngân sách và mô hình dự báo được giới hạn nghiêm ngặt theo `tenant_id`.
- **Phân Quyền Theo Vai Trò (RBAC)**:
  - `TENANT_ADMIN` & `FINANCE_MANAGER`: Toàn quyền cấu hình hạn mức ngân sách, xem dự báo chi phí tổng thể doanh nghiệp, điều chỉnh tham số lạm phát và nhận cảnh báo bội chi.
  - `MAINTENANCE_MANAGER`: Quyền xem dự báo chi phí cấp phân xưởng (Cost Center) và danh mục thiết bị để lập kế hoạch mua sắm vật tư, xem danh sách thiết bị "Quả chanh" cần thay thế.
  - `TECHNICIAN`: Không có quyền truy cập các thông tin dự báo tài chính và ngân sách doanh nghiệp.

---

## 6. Kiến Trúc & Luồng Dữ Liệu Hai Nhịp (Architecture & Data Flow)

```
[Dữ Liệu Vận Hành Hàng Ngày: Work Orders COMPLETED]
          │
          ├── 1. Khóa snapshot đơn giá vật tư & giờ công (is_cost_frozen = True)
          ├── 2. Bóc tách Warranty & Insurance ──► Tính Net Cost thực tế
          ├── 3. Loại trừ 100% hóa đơn mua sắm vật tư lưu kho (Chỉ lấy tiêu hao thực)
          └── 4. Khấu trừ lịch sử chi phí của thiết bị đã thanh lý (DISPOSED)
          │
          ▼
[Kiểm Định Tập Trung Chi Phí Pareto (80/20 Test)]
          └── Phát hiện thiết bị "Quả chanh" (>50% chi phí tại <5% máy) ──► Gợi ý thanh lý
          │
          ▼
[Feature Engineering Service: Trích Xuất 16 Đặc Trưng Đa Biến]
          ├── Bổ sung biến tích lũy nợ kỹ thuật: Backlog Orders & Deferred Hours
          ├── Bổ sung nghĩa vụ tài chính từ máy RUL Critical (Task 11.5)
          └── Biến đổi log1p ổn định phương sai cho chuỗi chi phí
          │
          ▼
[Cơ Chế Ngân Sách Lai Ghép Hai Nhịp (Hybrid Forecasting Engine)]
  ┌─────────────────────────────────┴─────────────────────────────────┐
  ▼                                                                   ▼
[Nhịp 1: Kế Hoạch PM Xác Định]                       [Nhịp 2: QRF Dự Báo CM Ngẫu Nhiên]
  - Quét lịch PM Plans kỳ tới (Task 3.6)                - Dự báo khối lượng vật lý (Phụ tùng + Giờ công)
  - Nhân BOM định mức vật tư tiêu chuẩn                 - Nhân Đơn giá hiện tại * (1 + Lạm phát)
  - Tính Y_Planned_PM chính xác 100%                    - Xuất phân vị QRF: P10, P50, P90
  └─────────────────────────────────┬─────────────────────────────────┘
                                    │
                                    ▼
                     [Tổng Hợp Ngân Sách Toàn Diện]
           Y_Total = Y_Planned_PM + Y_CM_Predicted (P50/P90) + Buffer
                                    │
                                    ▼
                     [Động Cơ Cảnh Báo Sớm Bội Chi]
  ├── So sánh Y_Total với Ngân Sách Được Duyệt (Approved Budget)
  ├── Nếu Tỷ lệ > 85% ──► Trạng thái WARNING
  └── Nếu Tỷ lệ > 100% ──► Trạng thái CRITICAL_OVERRUN ──► Bắn thông báo Real-time (Task 10.1)
```

---

## 7. Mô Hình Dữ Liệu & Thực Thể (Data Model & Schema)

### 7.1. Bảng `work_order_costs` (Lưu trữ snapshot chi phí bất biến và chi phí ròng)
```sql
CREATE TABLE work_order_costs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id),
  work_order_id UUID NOT NULL UNIQUE REFERENCES work_orders(id),
  cost_center_id UUID NULL REFERENCES cost_centers(id),
  material_cost DECIMAL(18, 2) NOT NULL DEFAULT 0.00,
  labor_cost DECIMAL(18, 2) NOT NULL DEFAULT 0.00,
  vendor_cost DECIMAL(18, 2) NOT NULL DEFAULT 0.00,
  gross_cost DECIMAL(18, 2) NOT NULL DEFAULT 0.00, -- Tổng giá trị thực tế phát sinh
  warranty_covered_amount DECIMAL(18, 2) NOT NULL DEFAULT 0.00, -- Hãng bảo hành chi trả
  insurance_covered_amount DECIMAL(18, 2) NOT NULL DEFAULT 0.00, -- Bảo hiểm chi trả
  net_cost DECIMAL(18, 2) NOT NULL DEFAULT 0.00, -- Số tiền thực tế doanh nghiệp bỏ tiền mặt
  is_capital_overhaul BOOLEAN DEFAULT FALSE, -- Cờ đại tu lớn CapEx
  is_cost_frozen BOOLEAN DEFAULT FALSE, -- Khóa bất biến sau khi nghiệm thu
  cost_frozen_at TIMESTAMP WITH TIME ZONE NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_wo_costs_tenant_frozen ON work_order_costs(tenant_id, is_cost_frozen, created_at);
```

### 7.2. Bảng `budget_forecasts` (Lưu trữ kết quả dự báo ngân sách lai ghép)
```sql
CREATE TABLE budget_forecasts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id),
  cost_center_id UUID NULL REFERENCES cost_centers(id), -- NULL là cấp Macro toàn công ty
  forecast_period VARCHAR(16) NOT NULL, -- Ví dụ: '2026-Q4' hoặc '2026-11'
  forecast_method VARCHAR(32) NOT NULL DEFAULT 'HYBRID_QRF',
  approved_budget DECIMAL(18, 2) NOT NULL, -- Ngân sách được duyệt
  planned_pm_budget DECIMAL(18, 2) NOT NULL, -- Ngân sách PM định kỳ xác định
  predicted_cm_median DECIMAL(18, 2) NOT NULL, -- Dự báo sự cố ngẫu nhiên P50
  predicted_cm_lower_p10 DECIMAL(18, 2) NOT NULL, -- Kịch bản tốt P10
  predicted_cm_upper_p90 DECIMAL(18, 2) NOT NULL, -- Kịch bản xấu P90
  contingency_buffer DECIMAL(18, 2) NOT NULL DEFAULT 0.00,
  total_forecast_median DECIMAL(18, 2) NOT NULL, -- Tổng dự báo P50
  total_forecast_p90 DECIMAL(18, 2) NOT NULL, -- Tổng dự báo P90
  budget_usage_ratio FLOAT NOT NULL, -- % tỷ lệ sử dụng ngân sách
  budget_status VARCHAR(16) NOT NULL, -- 'HEALTHY', 'WARNING', 'CRITICAL_OVERRUN'
  inflation_rate_applied FLOAT NOT NULL DEFAULT 0.045, -- Tỷ lệ lạm phát áp dụng
  backlog_work_orders_count INT NOT NULL DEFAULT 0,
  rul_critical_liability DECIMAL(18, 2) NOT NULL DEFAULT 0.00,
  lemon_assets_detected JSONB NULL, -- Danh sách các thiết bị "Quả chanh" chiếm chi phí
  top_cost_drivers JSONB NOT NULL, -- Top đặc trưng ảnh hưởng mạnh nhất
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

---

## 8. Đặc Tả Giao Diện Lập Trình (API Specifications & Contracts)

### Danh Mục Endpoints:

| Phương Thức | Đường Dẫn | Chức Năng |
| :--- | :--- | :--- |
| `GET` | `/api/v1/cost-forecasting/current-forecast/` | Lấy kết quả dự báo ngân sách kỳ hiện tại (Macro hoặc theo Cost Center) |
| `POST` | `/api/v1/cost-forecasting/run-forecast/` | Kích hoạt tác vụ tính toán dự báo ngân sách mới |
| `GET` | `/api/v1/cost-forecasting/lemon-assets/` | Danh sách thiết bị "Quả chanh" chiếm dụng chi phí theo kiểm định Pareto |
| `GET` | `/api/v1/cost-forecasting/historical-trends/` | Lấy chuỗi chi phí thực tế đối sánh với đường dự báo $P_{10}, P_{50}, P_{90}$ |

### Cấu Trúc Dữ Liệu Mẫu:

#### 1. Lấy kết quả dự báo ngân sách (`GET /api/v1/cost-forecasting/current-forecast/`):
```json
{
  "success": true,
  "data": {
    "period": "2026-Q4",
    "forecastMethod": "HYBRID_QUANTILE_FOREST",
    "currency": "VND",
    "budgetOverview": {
      "approvedBudget": 250000000.0,
      "plannedPmDeterministic": 110000000.0,
      "predictedCmMedianP50": 135000000.0,
      "predictedCmRiskP90": 175000000.0,
      "contingencyBuffer": 15000000.0,
      "totalForecastMedian": 260000000.0,
      "totalForecastP90": 300000000.0,
      "usageRatioPercent": 104.0,
      "budgetStatus": "CRITICAL_OVERRUN",
      "statusLabel": "Báo động: Nguy cơ vượt ngân sách 4.0% ở kịch bản trung vị (Vượt 20.0% ở kịch bản rủi ro P90)"
    },
    "riskFactors": {
      "backlogOrdersCount": 14,
      "deferredMaintenanceHours": 128.5,
      "postDeferralSurgeRisk": "HIGH",
      "rulCriticalLiabilityAmount": 45000000.0,
      "inflationRateAppliedPercent": 4.5
    },
    "lemonAssetsAlert": {
      "isConcentrationDetected": true,
      "topLemonAsset": {
        "assetId": "ast-pump-101",
        "assetName": "Bơm hóa chất ly tâm P-101",
        "historicalCostContributionPercent": 56.4,
        "recommendation": "Thiết bị chiếm 56.4% chi phí sửa chữa toàn xưởng. Đề xuất lập hồ sơ thanh lý để giảm ngay 76,000,000 VNĐ dự báo chi phí Quý 4."
      }
    },
    "topCostDrivers": [
      { "feature": "Khối lượng công việc bảo trì tồn đọng (Backlog Orders)", "importance": 0.32 },
      { "feature": "Nghĩa vụ tài chính vật tư từ thiết bị RUL Nguy cấp (Task 11.5)", "importance": 0.28 },
      { "feature": "Tần suất sự cố đột xuất 3 tháng gần nhất", "importance": 0.18 },
      { "feature": "Chỉ số trượt giá vật tư vòng bi & phớt", "importance": 0.12 },
      { "feature": "Độ tuổi trung bình dàn máy móc (>7 năm)", "importance": 0.10 }
    ]
  }
}
```

---

## 9. Đặc Tả Trải Nghiệm Người Dùng (UI/UX Behavioral Specifications)

- **Đồng hồ đo áp lực ngân sách đa phân vị (Multi-Quantile Budget Gauge)**:
  - Kim đo chính hiển thị kịch bản trung vị $P_{50}$.
  - Vạch dải bóng mờ hiển thị kịch bản rủi ro $P_{90}$ và vùng dự phòng khẩn cấp.
  - Ba phân vùng màu: Xanh lá ($< 85\%$), Vàng cam ($85\% - 100\%$), Đỏ ($> 100\%$ Bội chi).
- **Thẻ Cảnh Báo "Thiết Bị Quả Chanh" (Lemon Asset Bad Actor Banner)**:
  - Khi kiểm định Pareto phát hiện máy chiếm $>50\%$ ngân sách, hiển thị banner màu đỏ mận:
    *"Phát hiện 1 thiết bị bất thường ngốn 56% chi phí bảo trì. Nhấn vào để xem báo cáo thẩm định thanh lý thiết bị."*
  - Nút bấm: *"Mô phỏng cắt giảm chi phí nếu thanh lý máy này"* hiển thị ngay đồ thị chi phí giảm sốc cho ban giám đốc.
- **Thanh đo Nợ Kỹ Thuật (Deferred Maintenance Debt Bar)**:
  - Hiển thị số lượng lệnh PM bị hoãn và cảnh báo mức độ tích lũy nguy cơ bùng nổ chi phí trong kỳ tới.
- **Bộ lọc Trung Tâm Chi Phí (Cost Center Selector)**:
  - Cho phép Kế toán trưởng lọc xem toàn công ty (Macro) hoặc chọn từng phân xưởng cụ thể để giao chỉ tiêu ngân sách cho từng Quản đốc.

---

## 10. Tiêu Chí Chấp Nhận & Ma Trận Kịch Bản Kiểm Thử (Acceptance Criteria & Test Scenarios)

### 10.1. Ma Trận Kịch Bản Kiểm Thử Nghiệp Vụ & Tài Chính

| Mã Test | Tên Kịch Bản | Điều Kiện Thử Nghiệm | Hành Vi Kỳ Vọng | Trạng Thái |
| :--- | :--- | :--- | :--- | :--- |
| **TC-COST-01** | Khóa bất biến đơn giá snapshot | Nghiệm thu hoàn thành Work Order. Sau đó thay đổi giá phụ tùng trong kho | `is_cost_frozen = True`, chi phí đơn hàng cũ giữ nguyên $100\%$ không đổi | Chưa thực hiện |
| **TC-COST-02** | Bẫy bảo trì hoãn lại (Deferred Trap) | Quý 3 cắt giảm 50% PM khiến chi phí giảm, nhưng Backlog tăng vọt 15 phiếu | Mô hình nhận diện nợ kỹ thuật, dự báo Quý 4 chi phí tăng đột biến thay vì tiếp tục giảm | Chưa thực hiện |
| **TC-COST-03** | Khắc phục điểm mù ngoại suy lạm phát | Giá phụ tùng toàn cầu tăng 30% so với dữ liệu lịch sử | Dự báo Khối lượng vật lý $\times$ Giá hiện tại $(1 + I_{\text{inflation}})$, kết quả vượt trần lịch sử chính xác | Chưa thực hiện |
| **TC-COST-04** | Chống bão hòa xả ngân sách cuối năm | Tháng 12 chi 200 triệu mua phụ tùng cất vào kho dự trữ | Dữ liệu huấn luyện loại trừ hóa đơn nhập kho, không tạo tính mùa vụ ảo cho tháng 12 | Chưa thực hiện |
| **TC-COST-05** | Bóc tách chi phí bảo hành & bảo hiểm | Thay cụm trục chính 300 triệu được hãng bảo hành chi trả 100% | `gross_cost = 300M`, `warranty = 300M`, `net_cost = 0M`. AI chỉ huấn luyện trên `net_cost` | Chưa thực hiện |
| **TC-COST-06** | Kiểm định Pareto thiết bị "Quả chanh" | 1 máy bơm chiếm 58% chi phí toàn nhà máy | Kích hoạt cảnh báo Bad Actor, đề xuất thanh lý kèm con số cắt giảm chi phí dự phóng | Chưa thực hiện |
| **TC-COST-07** | Khấu trừ lịch sử máy đã thanh lý | Thiết bị Quả chanh được gắn nhãn `DISPOSED` | Pipeline tự động loại bỏ chi phí của máy này ra khỏi tập huấn luyện kỳ tới | Chưa thực hiện |
| **TC-COST-08** | Cơ chế ngân sách lai ghép (PM + CM) | Có 10 PM Plans định kỳ cố định trong tháng tới | Tính chính xác 100% chi phí PM theo định mức BOM, chỉ dùng AI dự báo phần sự cố CM | Chưa thực hiện |
| **TC-COST-09** | Xuất phân vị Quantile Forests P10/P50/P90 | Chạy mô hình QRF trên dữ liệu chi phí | Xuất đủ 3 phân vị $P_{10} \le P_{50} \le P_{90}$ có cơ sở toán học rõ ràng | Chưa thực hiện |
| **TC-COST-10** | Tích hợp nghĩa vụ tài chính từ RUL 11.5 | 2 động cơ rơi vào cảnh báo RUL $\le 14$ ngày | Tự động cộng chi phí phụ tùng thay thế vào dự báo ngân sách kỳ tới | Chưa thực hiện |
| **TC-COST-11** | Cảnh báo sớm nguy cơ bội chi ngân sách | Tổng dự báo vượt hạn mức ngân sách được duyệt ($Usage > 100\%$) | Gán trạng thái `CRITICAL_OVERRUN`, gửi thông báo Real-time cho Quản trị viên & Kế toán | Chưa thực hiện |
| **TC-COST-12** | Khởi động lạnh cho cơ sở mới mở | Chi nhánh nhà xưởng mới hoạt động được 1 tháng | Kích hoạt Tầng 1 (Định mức 3-5% nguyên giá tài sản RAV), không quăng ngoại lệ thiếu dữ liệu | Chưa thực hiện |

---

## 11. Implementation Notes — For Implementation Phase Only

> [!IMPORTANT]
> **REFERENCE ONLY — DO NOT IMPLEMENT OR MODIFY CODE BASED ON THIS SECTION DURING SPEC REVIEW. These notes are intended for the implementation phase after the specification is approved.**

Phần này lưu trữ các chỉ dẫn kỹ thuật hạ tầng chi tiết để các kỹ sư tham khảo trong quá trình triển khai mã nguồn:

### 11.1. Cài Đặt Quantile Regression Forests Bằng Scikit-Learn / Quantile-Forest
- Khuyến nghị sử dụng thư viện `quantile-forest` hoặc trích xuất phân vị trực tiếp từ `RandomForestRegressor`:
  ```python
  from quantile_forest import RandomForestQuantileRegressor

  qrf = RandomForestQuantileRegressor(
      n_estimators=100,
      max_depth=6,
      min_samples_split=4,
      min_samples_leaf=2,
      random_state=42
  )
  # Dự đoán đồng thời 3 phân vị P10, P50, P90
  predictions = qrf.predict(X_test, quantiles=[0.10, 0.50, 0.90])
  p10, p50, p90 = predictions[:, 0], predictions[:, 1], predictions[:, 2]
  ```

### 11.2. Công Thức Hai Nhịp Áp Dụng Chỉ Số Trượt Giá
```python
def calculate_hybrid_budget(planned_pm_cost, predicted_parts_volume, predicted_labor_hours, current_price_index, inflation_rate=0.045):
    # Nhịp 2: Nhân khối lượng với đơn giá điều chỉnh lạm phát
    cm_materials = sum(vol * price * (1.0 + inflation_rate) for vol, price in zip(predicted_parts_volume, current_price_index))
    cm_labor = predicted_labor_hours * CURRENT_LABOR_HOURLY_RATE
    cm_total = cm_materials + cm_labor
    
    contingency = (planned_pm_cost + cm_total) * 0.05  # 5% dự phòng
    return planned_pm_cost + cm_total + contingency
```

---

## 12. Kế Hoạch Triển Khai & Nghiệm Thu (Implementation Checklist)

- [ ] **Task 11.6.1 — Immutable Cost Snapshot & Net Cost Schema**
  - [ ] Mở rộng bảng `work_order_costs`: Lưu snapshot đơn giá, bóc tách `gross_cost`, `warranty_covered_amount`, `insurance_covered_amount`, `net_cost`.
  - [ ] Thiết lập cơ chế khóa cứng chi phí bất biến (`is_cost_frozen`) khi Work Order chuyển `COMPLETED`.
- [ ] **Task 11.6.2 — Actual Consumption Pipeline & Disposed Pruning**
  - [ ] Lọc sạch 100% hóa đơn nhập kho vật tư, chỉ trích xuất dữ liệu từ Work Order tiêu hao thực tế.
  - [ ] Cài đặt cơ chế tự động khấu trừ lịch sử chi phí của thiết bị đã thanh lý (`DISPOSED`).
- [ ] **Task 11.6.3 — Feature Engineering & Backlog Debt Tracking**
  - [ ] Xây dựng pipeline trích xuất 16 đặc trưng chuỗi thời gian đa biến.
  - [ ] Tích hợp 2 biến nợ kỹ thuật: `backlog_orders_count` và `deferred_maintenance_hours`.
  - [ ] Tích hợp nghĩa vụ tài chính từ các thiết bị cảnh báo RUL nguy cấp (Task 11.5).
- [ ] **Task 11.6.4 — Two-Step Hybrid Forecasting & Quantile Forests (QRF)**
  - [ ] Xây dựng module tính toán ngân sách PM định kỳ xác định từ `PmPlan`.
  - [ ] Cài đặt mô hình Quantile Regression Forests dự báo khối lượng CM và xuất $P_{10}, P_{50}, P_{90}$.
  - [ ] Áp dụng hệ số trượt giá lạm phát ($I_{\text{inflation}}$) ở tầng hậu xử lý tài chính.
- [ ] **Task 11.6.5 — Pareto Lemon Asset Audit & Early Overrun Warning**
  - [ ] Cài đặt thuật toán kiểm định phân bổ chi phí 80/20 phát hiện nhóm Bad Actors.
  - [ ] Xây dựng động cơ đối soát hạn mức ngân sách và phát cảnh báo Real-time (Task 10.1).
- [ ] **Task 11.6.6 — Web Portal UI Integration & Test Matrix Verification**
  - [ ] Thiết kế đồng hồ đo áp lực ngân sách đa phân vị, thẻ cảnh báo thiết bị Quả chanh, và thanh nợ kỹ thuật.
  - [ ] Triển khai bộ kiểm thử tự động 12 test cases (`TC-COST-01` đến `TC-COST-12`).

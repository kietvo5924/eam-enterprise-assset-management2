# Thiết Kế Hệ Thống & Đặc Tả Kỹ Thuật: Task 11.6 — Maintenance Cost & Budget Forecasting (Random Forest Regressor & Hybrid Budgeting Engine)

Tài liệu này xác định kiến trúc mô hình học máy hồi quy rừng ngẫu nhiên phân vị (**Quantile Regression Forests - QRF**), quy trình dự báo tài chính hai nhịp kết hợp giữa **Kế hoạch bảo dưỡng định kỳ xác định (Deterministic PM)** và **Dự phóng sự cố ngẫu nhiên (Stochastic CM Regressor)**, quy trình trích xuất đặc trưng chuỗi thời gian đa biến (**Multi-variate Time-Series Feature Engineering**), cơ chế phòng ngừa bẫy bảo trì hoãn lại (Deferred Maintenance Trap), xử lý điểm mù ngoại suy khi lạm phát, kiểm định tập trung chi phí Pareto kết hợp chỉ số tỷ lệ sửa chữa trên giá trị thay thế (RRR Bad Actors) bóc tách thiết bị "Quả chanh" (Lemon Assets), cơ chế kiểm soát quản trị AI cấp Tenant (AI Governance Toggles & Fallback Mode), và **bộ kịch bản kiểm thử chấp nhận & trường hợp biên (Acceptance Criteria & Edge Cases)** cho bài toán **Quản Lý & Dự Báo Ngân Sách Bảo Trì Doanh Nghiệp** trong hệ thống Quản lý Tài sản Doanh nghiệp (EAM).

Tài liệu đóng vai trò là **Đặc Tả Kỹ Thuật & Chuẩn Kiểm Thử (Technical Specification & Audit Baseline)** nhằm đối chiếu, rà soát và thực thi trọn vẹn toàn bộ tính năng mà không bị thiếu sót bất kỳ nghiệp vụ enterprise nào.

---

## 1. Mục Tiêu & Phạm Vi (Objective & Scope)

### 1.1. Bản Chất Nghiệp Vụ Quản Trị Chi Phí Trong EAM
Chi phí bảo trì thường chiếm từ 15% đến 40% tổng chi phí vận hành của doanh nghiệp sản xuất. Phương thức lập ngân sách truyền thống thường gặp các hạn chế nghiêm trọng:
- **Thiếu minh bạch tại thời điểm phát sinh & sai lệch kế toán dồn tích**: Chi phí chỉ được ghi nhận chung chung sau khi kết thúc kỳ kế toán hoặc khi thanh toán hóa đơn. Không bóc tách được từng lệnh bảo trì tiêu hao bao nhiêu tiền phụ tùng (theo đơn giá bình quân gia quyền tại thời điểm xuất kho) và bao nhiêu giờ công thợ (theo mức lương và phân xưởng tại thời điểm ghi nhận công việc).
- **Lập ngân sách cảm tính & Bỏ qua nợ kỹ thuật tồn đọng (Backlog Debt)**: Thường lấy số liệu chi phí năm trước cộng thêm phần trăm dự phòng lạm phát mà không tính đến sự xuống cấp lũy tiến của máy móc già cỗi, số lượng lệnh bảo trì quá hạn bị hoãn lại, hoặc các rủi ro hư hỏng sắp xảy ra đã được hệ thống cảm biến cảnh báo.
- **Bẫy ngoại suy, xả ngân sách ảo và thao túng số liệu**: Cắt giảm bảo trì tạm thời khiến chi phí giảm giả tạo trong ngắn hạn, hoặc ồ ạt chi tiền mua vật tư tích trữ vào kho cuối năm làm biến dạng dòng tiền và đánh lừa các mô hình học máy ngây thơ.

### 1.2. Vai Trò Của Mô Hình Học Máy Lai Ghép (Hybrid Budgeting Engine)
Mô hình dự báo chi phí là điểm hội tụ tài chính của toàn bộ hệ thống EAM, đóng vai trò kết nối giữa tầng vận hành kỹ thuật và tầng quản trị tài chính doanh nghiệp:
- **Tách bạch 2 dòng tiền (Deterministic vs Stochastic)**: Ngân sách kế hoạch bảo dưỡng định kỳ PM được tính toán xác định 100% từ lịch bảo trì đã lên kế hoạch (`PmPlan`) và định mức phụ tùng (BOM); trong khi ngân sách sửa chữa sự cố đột xuất CM được dự báo bằng Random Forest Regressor dựa trên chuỗi thời gian, cường độ vận hành và độ tuổi máy móc.
- **Cầu nối trực tiếp với Tầng Dự đoán Suy thoái RUL (Task 11.5) & Cảnh Báo Bất Thường (Task 11.4)**: Tự động chuyển đổi các cảnh báo thiết bị sắp hỏng nguy cấp (`rul_risk_level == 'CRITICAL'` hoặc `rapid_degradation_alert == True`) thành nghĩa vụ tài chính vật tư dự phòng (`primary_spare_part`) cần chuẩn bị ngân sách giải ngân trong kỳ tới.
- **Định lượng rủi ro bằng Rừng Hồi Quy Phân Vị (QRF)**: Thay vì chỉ dự đoán một con số trung bình duy nhất, mô hình xuất đồng thời 3 phân vị có cơ sở toán học chặt chẽ: Kịch bản tối thiểu ($P_{10}$), Kịch bản trung vị cơ sở ($P_{50}$) và Kịch bản rủi ro xấu nhất ($P_{90}$) để Kế toán trưởng và Ban Giám đốc chủ động lập quỹ dự phòng thanh khoản tiền mặt.
- **Tích Hợp Quản Trị AI Doanh Nghiệp (AI Governance Toggles)**: Cung cấp cờ cấu hình `enable_ai_cost_forecasting` cấp Tenant. Khi tắt hoặc khi hệ thống mới đưa vào vận hành (chưa đủ dữ liệu huấn luyện), engine tự động kích hoạt chế độ Fallback xác định an toàn (Deterministic PM + trung bình trượt SMA / định mức % RAV) mà không làm gián đoạn hệ thống.

---

## 2. Ràng Buộc Kế Thừa Hệ Thống (Existing System Constraints & Codebase Reuse)

- **Tái Sử Dụng Mô Hình Multi-Tenancy**: Mọi dữ liệu chi phí, cấu hình hạn mức ngân sách và mô hình huấn luyện kế thừa `BaseTenantModel`, bảo đảm phân lập hoàn toàn giữa các Tenant qua `TenantManager` và `get_current_tenant()`. Hỗ trợ thuộc tính quản trị AI `Tenant.enable_ai_cost_forecasting` và cá nhân hóa giao diện `Tenant.theme_color`.
- **Tái Sử Dụng Thực Thể Nghiệp Vụ Sẵn Có**:
  - `WorkOrder`: Trạng thái hoàn thành (`status = 'COMPLETED'`), loại công việc (`type IN ('CORRECTIVE', 'PREVENTIVE', 'EMERGENCY', 'BREAKDOWN', 'PREDICTIVE_PM')`), cấp độ can thiệp bảo trì (`maintenance_action IN ('GENERAL', 'MICRO_MAINTENANCE', 'CORE_REPLACEMENT')`), cờ đại tu vốn hóa CapEx (`is_capitalized`), chi phí thực tế lũy kế (`actual_cost`), lý do miễn trừ PM trùng lặp (`skipped_reason = 'OVERLAP_PREVENTED'`), và mốc thời gian nghiệm thu (`completed_at`, `completion_processed_at`).
  - `StockTransaction` (Phase 10.3 & Inventory): Nhật ký xuất/nhập kho phản ánh chính xác đơn giá xuất kho (`unit_price`), thành tiền (`total_amount`), loại giao dịch (`transaction_type IN ('ISSUE', 'RECEIPT', 'ADJUSTMENT', 'RETURN')`), cờ điều chỉnh chênh lệch giá (`is_variance_adjustment`), và trung tâm chi phí ảnh chụp (`cost_center_snapshot`).
  - `LaborLog` (Phase 10.3 & WorkOrders): Nhật ký giờ công thợ lưu đơn giá giờ công ảnh chụp (`hourly_rate`), số giờ làm việc (`hours_worked`), thành tiền công thợ (`total_cost`), cờ làm ngoài giờ (`is_overtime`), và trung tâm chi phí ảnh chụp (`cost_center_snapshot`).
  - `Asset`: Nguyên giá (`purchase_cost` / `value`), giá trị vốn hóa đại tu (`capitalized_cost`), giá trị thanh lý ước tính (`salvage_value`), thời gian trích khấu hao (`useful_life_years`), bản chất tài sản (`asset_type IN ('MACHINERY', 'STATIC')`), linh kiện cốt lõi chính (`primary_spare_part`), trạng thái RUL nguy cấp (`rul_risk_level`, `current_rul_days`, `rapid_degradation_alert`), và trạng thái vận hành (`status IN ('OPERATIONAL', 'OPERATING', 'DOWN', 'MAINTENANCE', 'RETIRED', 'SCRAPPED', 'DISPOSED', 'DECOMMISSIONED', 'SOLD')`).
  - `SparePart`: Đơn giá hiện hành (`unit_cost`), tồn kho thực tế (`quantity_in_stock`), mức tồn kho an toàn (`min_stock_level`), và thời gian đặt hàng bổ sung (`lead_time_days`).
  - `PmPlan`, `PmPlanMaterial`, `PmPlanAssignment`: Danh mục kế hoạch bảo trì định kỳ đang kích hoạt (`status = 'ACTIVE'`), tần suất chu kỳ ngày/giờ (`interval_value`, `interval_unit`), thời điểm kích hoạt gần nhất (`last_triggered_at`), định mức vật tư tiêu hao (`PmPlanMaterial.quantity`), và số giờ công tiêu chuẩn (`estimated_duration_minutes`).
- **Chuẩn Hóa Trung Tâm Chi Phí (Temporal Cost Center Slicing)**: Hệ thống sử dụng chuỗi ảnh chụp phân xưởng `cost_center_snapshot` trên từng giao dịch vật tư và giờ công (theo chuẩn kế toán thời gian thực của Phase 10.3), kết hợp phân cấp không gian `Location` (`SITE`, `BUILDING`, `FLOOR`, `ROOM`). Tuyệt đối không phụ thuộc vào khóa ngoại cứng để bảo toàn tính toàn vẹn của báo cáo khi tài sản điều chuyển giữa các phân xưởng.
- **Tiền Tệ Chuẩn Hóa & Làm Tròn VNĐ (VND Financial Rounding)**: Mọi giá trị tiền tệ trong cơ sở dữ liệu tuân thủ kiểu `DecimalField(max_digits=19, decimal_places=2)`. Khi hiển thị và tổng hợp ngân sách VNĐ, hệ thống áp dụng hàm chuẩn `round_vnd()` (sử dụng thuật toán `ROUND_HALF_UP` không có số lẻ thập phân cho VNĐ, tỷ lệ phần trăm giữ 1 đến 2 chữ số thập phân).
- **Tích Hợp Hệ Thống Thông Báo Thời Gian Thực (Task 10.1)**: Tự động phát sinh thực thể `Notification` với mức độ nghiêm trọng `severity = 'WARNING'` (khi sử dụng ngân sách $> 85\%$) hoặc `severity = 'CRITICAL'` (khi dự báo vượt ngân sách $> 100\%$, tức `CRITICAL_OVERRUN`), hỗ trợ cơ chế Topbar Bell Polling chu kỳ 10 giây trên giao diện Web Portal.
- **Kiến Trúc Đóng Gói Module Giải Thuật (Dedicated Algorithms Package)**: Toàn bộ mã nguồn giải thuật dự báo chi phí (trích xuất đặc trưng chuỗi thời gian, mô hình rừng hồi quy phân vị Quantile Regression Forests - QRF, động cơ lập ngân sách lai ghép hai nhịp, kiểm định tài sản chanh chua Lemon Asset / RRR Bad Actor, và bộ phân tích nợ kỹ thuật tồn đọng) **bắt buộc phải được đóng gói trong thư mục riêng biệt `eam_app/algorithms/cost_forecasting/`** (thuộc tầng backend Django). Tách biệt hoàn toàn tầng logic giải thuật khỏi tầng controller và view CRUD thông thường.

---

## 3. Yêu Cầu Nghiệp Vụ & 10 Quy Tắc Cốt Lõi (Business Requirements & Core Rules)

Toàn bộ module quản lý chi phí và dự báo ngân sách phải tuân thủ nghiêm ngặt 10 quy tắc nghiệp vụ phòng thủ sau:

### Quy Tắc 1: Khóa Bất Biến Đơn Giá Snapshot Tại Thời Điểm Chốt Chi Phí (Immutable Point-in-Time Cost Snapshot Guardrail)
- **Điểm Yếu Nghiệp Vụ**: Nếu chi phí Work Order tính bằng cách liên kết động sang bảng giá hiện hành của phụ tùng hoặc mức lương hiện tại của thợ, sau 1 năm khi giá cả lạm phát tăng lên, việc truy vấn lại sẽ làm thay đổi toàn bộ số liệu chi phí các lệnh bảo trì đã quyết toán trong quá khứ, phá vỡ tính toàn vẹn của báo cáo kế toán dồn tích và làm sai lệch tập dữ liệu huấn luyện học máy.
- **Quy Tắc Bắt Buộc**:
  1. Vật tư xuất kho phải ghi nhận đơn giá ảnh chụp (`unit_price`) tại chính thời điểm phát sinh giao dịch trên bảng `StockTransaction`.
  2. Giờ công thợ phải ghi nhận đơn giá giờ công ảnh chụp (`hourly_rate`) tại thời điểm thực hiện trên bảng `LaborLog`.
  3. Khi Work Order hoàn tất chuyển sang `COMPLETED`: Hệ thống tổng hợp toàn bộ chi phí vật tư và nhân công vào thực thể `work_order_costs`, gán cờ khóa cứng `is_cost_frozen = True` và đóng dấu mốc thời gian `cost_frozen_at = timezone.now()`. Sau mốc này, chi phí là bất biến, không bao giờ được phép tự động tính toán lại theo giá thị trường hiện hành.
  4. **Xử lý biến động sau nghiệm thu**: Nếu có phát sinh xuất trả phụ tùng dư thừa (`transaction_type = 'RETURN'`) hoặc điều chỉnh chênh lệch giá mua hàng thực tế từ biên bản nhập kho GRN (`is_variance_adjustment = True`), hệ thống hạch toán dòng ghi giảm/tăng chi phí tương ứng thông qua giao dịch điều chỉnh có lưu vết kiểm toán (Audit Trail) rõ ràng, tuyệt đối không sửa đè trực tiếp lên bản ghi snapshot cũ.

### Quy Tắc 2: Phân Tách Chi Phí Thường Xuyên (OpEx) vs Đại Tu Vốn Hóa (CapEx) (OpEx Routine vs CapEx Major Overhaul Guardrail)
- **Điểm Yếu Nghiệp Vụ**: Một sự cố đại tu lớn (ví dụ: thay thế toàn bộ trục chính máy ép trị giá 500 triệu VNĐ) được chuẩn mực kế toán ghi nhận là Vốn hóa Tài sản (CapEx) và trích khấu hao dần theo thời gian, trong khi chi phí bảo trì thường xuyên hàng tháng chỉ tốn khoảng 30 triệu VNĐ (OpEx). Nếu đưa trực tiếp con số đột biến cực trị này vào tập huấn luyện của Random Forest, mô hình sẽ bị méo mó và dự báo chi phí thường xuyên của các tháng tiếp theo tăng vọt bất hợp lý.
- **Quy Tắc Bắt Buộc**:
  1. Tách bạch hoàn toàn giữa chi phí bảo trì vận hành thường xuyên (Routine OpEx) và chi phí đại tu lớn (Major Overhaul CapEx).
  2. Kế thừa cờ `is_capitalized = True` trên `WorkOrder` và cập nhật vào trường `Asset.capitalized_cost`. Gắn nhãn CapEx cho các lệnh bảo trì có cấp độ can thiệp `maintenance_action = 'CORE_REPLACEMENT'` hoặc chi phí vượt ngưỡng ngoại lai thống kê ($> 3\sigma$).
  3. Khi trích xuất dữ liệu huấn luyện cho mô hình Random Forest Regressor dự báo chi phí thường xuyên, **loại trừ toàn bộ các Work Order được gắn nhãn CapEx (`is_capitalized = True`)**.
  4. Áp dụng phép biến đổi ổn định phương sai Log-Transform $y = \ln(1 + \text{cost})$ cho chuỗi chi phí OpEx trước khi huấn luyện để nén biên độ các cú sốc chi phí. Khi xuất kết quả dự báo, mô hình giải biến đổi ngược về giá trị tiền tệ thực tế thông qua hàm $\hat{Y} = \exp(y) - 1$.

### Quy Tắc 3: Bẫy "Bảo Trì Hoãn Lại" & Biến Tích Lũy Nợ Kỹ Thuật (Deferred Maintenance Trap & Backlog Surge Guardrail)
- **Điểm Yếu Nghiệp Vụ**: Doanh nghiệp thắt chặt ngân sách trong Quý 3, quản đốc trì hoãn hoặc hủy bỏ 50% các phiếu bảo trì định kỳ PM. Chi phí Quý 3 giảm mạnh rõ rệt. Nếu mô hình AI chỉ nhìn vào số tiền đã tiêu trong quá khứ, nó sẽ dự báo ngây thơ rằng Quý 4 chi phí cũng sẽ rất thấp. Nhưng thực tế do không được bảo dưỡng đúng hạn, máy móc xuống cấp nghiêm trọng và hỏng hóc hàng loạt trong Quý 4, dẫn đến chi phí sửa chữa sự cố CM tăng vọt gấp 3 lần bình thường.
- **Quy Tắc Bắt Buộc**:
  1. Mô hình không được phép chỉ học từ "Chi phí lịch sử đã chi". Bắt buộc phải bổ sung 2 đặc trưng tích lũy nợ kỹ thuật:
     - $N_{\text{backlog\_orders}}$: Số lượng Work Order bị quá hạn hoặc bị hoãn thực thi (`status IN ('CREATED', 'ASSIGNED', 'IN_PROGRESS', 'ON_HOLD')` với `deadline < now()`).
     - $T_{\text{deferred\_hours}}$: Tổng số giờ bảo dưỡng tiêu chuẩn bị trì hoãn so với lịch bảo trì ban đầu.
  2. Khi chi phí kỳ trước giảm nhưng tỷ lệ Backlog nợ kỹ thuật tăng cao ($> 20\%$), mô hình nhận diện sự tích tụ rủi ro vật lý và kích hoạt dự báo **"Cú sốc chi phí bùng nổ" (Post-deferral Cost Surge)** ở các kỳ tiếp theo.

### Quy Tắc 4: Khắc Phục Điểm Mù Ngoại Suy Của Random Forest Khi Lạm Phát (Extrapolation Blindspot & Two-Step Hybrid Forecasting)
- **Điểm Yếu Nghiệp Vụ**: Về mặt toán học, cây quyết định và mô hình Random Forest không thể ngoại suy ngoài miền giá trị mục tiêu đã huấn luyện ($\hat{y} \le \max(y_{\text{train}})$). Nếu xảy ra lạm phát kinh tế hoặc nhà cung cấp tăng giá phụ tùng 30% so với quá khứ, Random Forest sẽ luôn dự báo số tiền bị chặn trần ở mức cũ, gây thiếu hụt ngân sách tiền mặt nghiêm trọng.
- **Quy Tắc Bắt Buộc**:
  1. Áp dụng cơ chế **Dự Báo Hai Nhịp (Two-Step Hybrid Forecasting)**:
     - **Nhịp 1 (Vật lý - Random Forest Regressor)**: Dự báo **Khối lượng tiêu hao thực tế**: Số lượng phụ tùng tiêu hao ước tính ($\hat{Q}_{\text{parts}}$) và Số giờ công bảo dưỡng ($\hat{H}_{\text{labor}}$). Do khối lượng vật lý và số giờ công không bị lạm phát giá cả làm méo mó, chúng nằm hoàn toàn trong miền học của Random Forest.
     - **Nhịp 2 (Tài chính - Post-Processing)**: Nhân khối lượng dự báo với Bảng đơn giá hiện hành kết hợp Chỉ số trượt giá vật tư (Material Price Inflation Index - $I_{\text{inflation}}$):
       $$\hat{Y}_{\text{CM\_Financial}} = \sum_{i} \Big(\hat{Q}_i \times \text{CurrentUnitCost}_i \times (1 + I_{\text{inflation}})\Big) + \Big(\hat{H}_{\text{labor}} \times \text{CurrentHourlyRate}\Big)$$
  2. Người dùng được phép cấu hình tỷ lệ lạm phát kỳ vọng theo năm (mặc định $4.5\%$/năm trong `budget_forecasts.inflation_rate_applied`).

### Quy Tắc 5: Phân Tách Mua Hàng Lưu Kho vs Tiêu Hao Thực Tế Chống "Xả Ngân Sách Cuối Năm" (Inventory Purchasing vs Actual Consumption Guardrail)
- **Điểm Yếu Nghiệp Vụ**: Hiện tượng "Use it or lose it" vào tháng 12: Nhận thấy ngân sách năm còn dư, ban quản đốc ồ ạt ký đơn mua sắm vật tư phụ tùng chất đầy kho lưu trữ. Nếu lấy dòng tiền mua sắm nhập kho này làm dữ liệu chi phí bảo trì, mô hình AI sẽ lầm tưởng rằng cứ vào tháng 12 hàng năm là máy móc hư hỏng cực kỳ nghiêm trọng (tính mùa vụ ảo).
- **Quy Tắc Bắt Buộc**:
  1. Dữ liệu huấn luyện mô hình chi phí **TUYỆT ĐỐI LOẠI TRỪ 100%** các giao dịch nhập kho mua sắm mới (`StockTransaction` có `transaction_type = 'RECEIPT'`). Việc mua hàng nhập kho là chuyển dịch tài sản lưu động của kho vật tư, không phải là chi phí vận hành bảo trì đã tiêu hao.
  2. Dữ liệu huấn luyện chỉ được lấy duy nhất từ **Chi phí Tiêu hao Thực tế (Actual Consumption Cost)** — tức là vật tư đã thực sự được xuất kho và gắn vào máy móc thông qua các lệnh bảo trì đã nghiệm thu hoàn tất (`StockTransaction` có `transaction_type = 'ISSUE'` trừ đi `transaction_type = 'RETURN'`, gắn với Work Order có `status = 'COMPLETED'`).

### Quy Tắc 6: Bóc Tách Chi Phí Ròng Bảo Hành & Bảo Hiểm (Warranty & Insurance Overlap / Net Cost Guardrail)
- **Điểm Yếu Nghiệp Vụ**: Một động cơ máy CNC gặp sự cố, chi phí thay thế hết 300 triệu VNĐ nhưng do thiết bị còn trong thời hạn bảo hành của hãng nên nhà cung cấp chi trả 100% (doanh nghiệp không mất tiền mặt). Nếu ghi nhận chi phí 300 triệu VNĐ vào ngân sách bảo trì, mô hình AI sẽ dự báo công ty cần chuẩn bị một khoản tiền mặt khổng lồ vô lý vào tháng tiếp theo.
- **Quy Tắc Bắt Buộc**:
  1. Bảng `work_order_costs` lưu trữ rạch ròi 2 cấp độ chi phí:
     - **Chi phí gộp (Gross Cost)**: Toàn bộ giá trị vật tư và nhân công thực tế tiêu hao (dùng để đo lường độ tin cậy cơ học và tần suất hư hỏng của máy móc).
     - **Chi phí ròng (Net Cost)**: Số tiền thực tế doanh nghiệp phải chi trả bằng tiền mặt từ quỹ vận hành:
       $$\text{Net Cost} = \text{Gross Cost} - (\text{Warranty Covered Amount} + \text{Insurance Covered Amount})$$
  2. Mô hình dự báo ngân sách tiền mặt **bắt buộc chỉ huấn luyện và dự phóng trên Chi Phí Ròng (Net Cost)**.
  3. Kế thừa chuẩn kế toán dồn tích (Accrual Accounting) từ Phase 10.3: Chi phí vật tư được ghi nhận theo ngày xuất kho (`issue_date`), chi phí nhân công ghi nhận theo ngày thực hiện công việc (`work_date`), độc lập với ngày thanh toán hóa đơn.

### Quy Tắc 7: Kiểm Định Tập Trung Chi Phí Pareto & Khấu Trừ Thiết Bị "Quả Chanh" (Cost Concentration 80/20 & Lemon Asset Skew Guardrail)
- **Điểm Yếu Nghiệp Vụ**: Nhà máy có 100 máy hoạt động ổn định, nhưng có 1 chiếc máy bơm cũ liên tục hỏng hóc và "ngốn" tới 58% tổng ngân sách bảo trì toàn xưởng. Nếu dự báo chung ở cấp vĩ mô, mô hình AI sẽ yêu cầu một hạn mức ngân sách rất lớn. Đến khi doanh nghiệp thanh lý chiếc máy bơm đó đi, chi phí thực tế tháng sau giảm mạnh nhưng AI vẫn tiếp tục dự báo ở mức cao chót vót.
- **Quy Tắc Bắt Buộc**:
  1. Tích hợp thuật toán **Kiểm định Phân bổ Chi phí Pareto (80/20 Cost Concentration Test)** kết hợp chỉ số Tỷ lệ Sửa chữa trên Giá trị Thay thế (Repair-to-Replacement Ratio - RRR từ Phase 10.3):
     - Định kỳ tính toán tỷ trọng chi phí bảo trì trên từng thiết bị trong toàn bộ danh mục tài sản.
     - Nếu phát hiện $\ge 50\%$ tổng chi phí bảo trì tập trung vào $\le 5\%$ số lượng thiết bị, hoặc tài sản có chỉ số $RRR = \frac{\text{Accumulated Maintenance OpEx}}{\text{Effective Purchase Cost}} \times 100\% \ge 70\%$, hệ thống kích hoạt cảnh báo nhóm thiết bị "Quả chanh" (Lemon Assets / Bad Actors):
       *"Cảnh báo: 56.4% chi phí sửa chữa kỳ qua tập trung vào Bơm P-101 (RRR = 78.5%). Đề xuất ban giám đốc xem xét phương án thanh lý/thay thế thiết bị này để giảm tức thì chi phí dự báo kỳ tới."*
  2. **Khấu trừ tài sản thanh lý (Disposed Pruning)**: Khi một tài sản chuyển trạng thái sang `DISPOSED`, `RETIRED`, `SCRAPPED` hoặc `SOLD`, pipeline tiền xử lý dữ liệu tự động loại bỏ toàn bộ lịch sử chi phí sửa chữa của tài sản đó ra khỏi chuỗi dữ liệu huấn luyện, ngăn chặn việc mô hình bị ám ảnh bởi cái bóng chi phí của máy đã bán.

### Quy Tắc 8: Cơ Chế Ngân Sách Lai Ghép: Tách Bạch PM Xác Định vs CM Ngẫu Nhiên (Deterministic PM vs Stochastic CM Decoupling Guardrail)
- **Điểm Yếu Nghiệp Vụ**: Bảo trì định kỳ (PM) là công việc đã được lên lịch rõ ràng theo chu kỳ ngày/tuần/tháng (Task 3.6 & 3.7), danh mục linh kiện thay thế và định mức giờ công đã biết trước $100\%$. Nếu ném chung toàn bộ số liệu vào để Random Forest "đoán mò" cả phần PM sẽ làm giảm sút độ chính xác và mất đi tính kiểm soát của kế hoạch tài chính.
- **Quy Tắc Bắt Buộc**:
  Ngân sách bảo trì tổng thể được tính theo công thức kiến trúc lai ghép (Hybrid Budget Architecture):
  $$\hat{Y}_{\text{Total}} = Y_{\text{Planned\_PM (Xác định từ lịch)}} + \hat{Y}_{\text{Breakdown\_CM (Dự báo bằng QRF)}} + \text{Buffer}_{\text{Contingency}}$$
  - $Y_{\text{Planned\_PM}}$: Tổng hợp tự động từ danh sách các kế hoạch `PmPlanAssignment` có hạn kích hoạt trong kỳ tới $\times$ Định mức phụ tùng (`PmPlanMaterial`) và số giờ công tiêu chuẩn (`estimated_duration_minutes`). Đồng thời tự động trừ bớt chi phí của các phiếu PM được dự kiến miễn trừ do trùng lặp (`skipped_reason = 'OVERLAP_PREVENTED'`).
  - $\hat{Y}_{\text{Breakdown\_CM}}$: Do mô hình Random Forest Regressor dự báo dựa trên chuỗi thời gian, độ tuổi máy móc và điều kiện vận hành.
  - $\text{Buffer}_{\text{Contingency}}$: Quỹ dự phòng khẩn cấp được tính theo tỷ lệ cấu hình của Tenant (mặc định 5% đến 10% tổng ngân sách dự báo).

### Quy Tắc 9: Định Lượng Rủi Ro Bằng Rừng Hồi Quy Phân Vị (Quantile Regression Forests - QRF Guardrail)
- **Điểm Yếu Nghiệp Vụ**: Dự báo một con số trung bình duy nhất không giúp ban giám đốc phòng vệ được rủi ro cạn kiệt thanh khoản tiền mặt trong những tháng dây chuyền sản xuất chạy hết công suất và gặp sự cố dồn dập.
- **Quy Tắc Bắt Buộc**:
  1. Huấn luyện mô hình **Quantile Regression Forests (QRF)** để xuất đồng thời 3 phân vị có cơ sở toán học chặt chẽ:
     - Phân vị 10% ($P_{10}$): Kịch bản chi phí tối thiểu (thiết bị vận hành rất ổn định, ít sự cố).
     - Phân vị 50% ($P_{50}$): Kịch bản chi phí trung vị (dự báo cơ sở phục vụ kế hoạch tài chính tiêu chuẩn).
     - Phân vị 90% ($P_{90}$): Kịch bản chi phí rủi ro xấu nhất (Worst-Case Scenario phục vụ lập quỹ dự phòng thanh khoản tiền mặt khẩn cấp).
  2. Kế toán trưởng và Giám đốc tài chính có thể tùy chọn căn cứ phê duyệt ngân sách theo kịch bản an toàn $P_{50}$ hoặc kịch bản phòng thủ $P_{90}$.

### Quy Tắc 10: Cầu Nối Nghĩa Vụ Tài Chính Từ Task 11.5 RUL & Quy Mô Tài Sản Thay Thế (% RAV) (Task 11.5 RUL Financial Liability & RAV Guardrail)
- **Điểm Yếu Nghiệp Vụ**: Phân hệ học sâu RUL (Task 11.5) phát hiện 2 động cơ nghiền chính sắp hỏng trong vòng 14 ngày tới (`rul_risk_level == 'CRITICAL'`), nhưng phân hệ tài chính (Task 11.6) lại hoàn toàn mù mờ, dẫn đến việc doanh nghiệp không dự trù đủ tiền mặt để đặt mua phụ tùng thay thế ngay trong tháng tới.
- **Quy Tắc Bắt Buộc**:
  1. Tự động quét và liên kết dữ liệu từ Task 11.5 đối với các thiết bị rơi vào trạng thái `rul_risk_level == 'CRITICAL'` ($RUL \le \text{lead\_time} + 5$ ngày hoặc $RUL \le 14$ ngày) hoặc có cờ cảnh báo suy thoái đột biến `rapid_degradation_alert = True`:
     $$\text{Liability}_{\text{PdM}} = \sum_{\text{Asset}_k \in \text{CRITICAL}} \Big(\text{Asset}_k.\text{primary\_spare\_part}.\text{unit\_cost} \times Q_{\text{req}} + \text{EstLaborHours} \times \text{HourlyRate}\Big)$$
     Nếu phụ tùng cốt lõi chưa đủ mức tồn kho an toàn (`quantity_in_stock < min_stock_level`), khoản nghĩa vụ tài chính này bắt buộc được cộng trực tiếp vào ngân sách phụ tùng dự phóng của kỳ tới.
  2. Bổ sung chỉ số chuẩn hóa quốc tế: Tỷ lệ Chi phí Bảo trì trên Giá trị Thay thế Tài sản (% RAV - Replacement Asset Value):
     $$\% \text{Cost/RAV} = \frac{\text{Annual Maintenance Cost}}{\sum (\text{Asset}.\text{effective\_purchase\_cost} + \text{Asset}.\text{capitalized\_cost})} \times 100\%$$
     Giúp ban lãnh đạo so sánh hiệu quả chi phí với chuẩn mực ngành công nghiệp (thường dao động trong khoảng $2.5\% - 4.5\%$).

### Quy Tắc Phòng Vệ Bổ Sung: Cơ Chế Quản Trị AI & Khởi Động Nguội (AI Governance Toggle & Cold-Start Graceful Fallback Guardrail)
- **Điểm Yếu Nghiệp Vụ**: Tenant mới mở chi nhánh hoặc Quản trị viên tắt tính năng AI do chính sách nội bộ. Nếu hệ thống ép buộc phải có đủ 100 cây quyết định và ném ngoại lệ lỗi khi thiếu dữ liệu, toàn bộ phân hệ báo cáo tài chính sẽ bị tê liệt.
- **Quy Tắc Bắt Buộc**:
  1. Kiểm tra cờ quản trị `Tenant.enable_ai_cost_forecasting`. Nếu cờ mang giá trị `False`, hệ thống tự động chuyển sang chế độ **Fallback Xác Định (Deterministic Fallback Engine)**:
     - Ngân sách PM tính từ `PmPlan`.
     - Ngân sách CM lấy theo trung bình trượt 3 tháng gần nhất ($\text{SMA}_3$) hoặc định mức kinh nghiệm ($3.0\%$ tổng giá trị RAV).
     - Đánh dấu cờ `is_ai_fallback = True` trong kết quả trả về, giải thích rõ phương pháp tính toán cho người dùng.
  2. Áp dụng quy tắc tương tự khi tập dữ liệu lịch sử của Tenant $< 3$ tháng vận hành (Cold Start).

---

## 4. Yêu Cầu Chức Năng & Luồng Xử Lý (Functional Requirements & Workflows)

### 4.1. Bộ 16 Đặc Trưng Chuỗi Thời Gian Đa Biến (Feature Engineering Pipeline)
Pipeline tiền xử lý dữ liệu trích xuất chính xác 16 đặc trưng đa biến đầu vào nạp cho mô hình học máy:
1. **Chi phí ròng kỳ trễ 1** ($\text{NetCost}_{t-1}$): Tổng chi phí ròng OpEx tháng trước.
2. **Chi phí ròng kỳ trễ 2** ($\text{NetCost}_{t-2}$): Tổng chi phí ròng OpEx cách 2 tháng.
3. **Chi phí ròng kỳ trễ 3** ($\text{NetCost}_{t-3}$): Tổng chi phí ròng OpEx cách 3 tháng.
4. **Trung bình trượt chi phí ròng 3 tháng** ($\text{SMA}_3 = \frac{1}{3}\sum_{k=1}^3 \text{NetCost}_{t-k}$).
5. **Trung bình trượt chi phí ròng 6 tháng** ($\text{SMA}_6 = \frac{1}{6}\sum_{k=1}^6 \text{NetCost}_{t-k}$).
6. **Độ biến động chi phí trượt 3 tháng** (Rolling Standard Deviation): Đo lường biên độ dao động chi phí.
7. **Số lượng Work Order tồn đọng quá hạn** ($N_{\text{backlog\_orders}}$): Số lệnh sửa chữa quá hạn chưa hoàn tất (Bẫy bảo trì hoãn lại).
8. **Tổng số giờ bảo dưỡng bị hoãn lại** ($T_{\text{deferred\_hours}}$): Thời lượng giờ bảo dưỡng tích lũy bị trễ so với lịch.
9. **Tổng số lượng thiết bị đang hoạt động** ($N_{\text{active\_assets}}$: Đếm số lượng máy có `status IN ('OPERATIONAL', 'OPERATING')`).
10. **Độ tuổi trung bình dàn máy móc** (tính theo năm vận hành từ mốc `purchase_date`).
11. **Tỷ lệ sự cố đột xuất** ($N_{\text{CM}} / N_{\text{Total}}$: Tỷ số giữa số lệnh Corrective/Emergency so với tổng số lệnh bảo trì).
12. **Nghĩa vụ tài chính phụ tùng từ các máy RUL Critical Task 11.5** ($\text{Liability}_{\text{PdM}}$).
13. **Tổng giá trị thay thế toàn bộ dàn máy** (Total Fleet RAV: $\sum (\text{effective\_purchase\_cost} + \text{capitalized\_cost})$).
14. **Tỷ trọng chi phí thuộc nhóm thiết bị trọng yếu Class A / Bad Actors** (%): Đo lường mức độ tập trung chi phí.
15. **Hệ số mùa vụ** (Tháng trong năm từ 1 đến 12).
16. **Số ngày làm việc thực tế trong tháng** (loại trừ các ngày nghỉ thứ 7, chủ nhật và ngày nghỉ lễ quốc gia).

### 4.2. Kiến Trúc Mô Hình Quantile Regression Forests (QRF Specification)
- Tập hợp gồm 100 cây quyết định hồi quy (`n_estimators = 100`).
- Kiểm soát độ sâu tối đa `max_depth = 6`, `min_samples_split = 4`, `min_samples_leaf = 2` để chống hiện tượng quá khớp (overfitting) trên chuỗi dữ liệu tài chính ngắn.
- Biến đổi dữ liệu đầu vào: Chuỗi mục tiêu được chuẩn hóa qua hàm Log-Transform $y = \ln(1 + \text{cost})$ trước khi nạp vào cây quyết định.
- Cơ chế trích xuất phân vị: Thay vì chỉ lấy trung bình số học các lá cây như Random Forest truyền thống, mô hình lưu trữ toàn bộ tập phân phối giá trị quan sát tại các nút lá của từng cây để xây dựng hàm phân phối tích lũy có điều kiện $F(y|x)$:
  $$F(y|x) = \sum_{i=1}^n w_i(x) \cdot \mathbf{1}_{\{y_i \le y\}}$$
  Từ đó trích xuất chính xác 3 phân vị hồi quy:
  $$Q_{\alpha}(x) = \inf \{y: F(y|x) \ge \alpha\}, \quad \alpha \in \{0.10, 0.50, 0.90\}$$
- Hậu xử lý giải biến đổi: Các phân vị được giải ngược về đơn vị tiền tệ thực tế thông qua hàm $\hat{Y}_{\alpha} = \exp(Q_{\alpha}(x)) - 1$, sau đó nhân với chỉ số trượt giá lạm phát $I_{\text{inflation}}$.

---

## 5. Quy Tắc Bảo Mật, Phân Quyền & Đa Khách Hàng (Security, RBAC & Multi-Tenant Rules)

- **Cô Lập Đa Khách Hàng (Multi-Tenancy)**: Mọi dữ liệu tài chính, hạn mức ngân sách và mô hình dự báo được giới hạn nghiêm ngặt theo `tenant_id` qua `TenantManager`. Tuyệt đối không cho phép truy vấn chéo dữ liệu tài chính giữa các doanh nghiệp khác nhau.
- **Phân Quyền Theo Vai Trò (RBAC) & Mã Quyền Hệ Thống**:
  - `SYSTEM_ADMIN` & `TENANT_ADMIN`: Toàn quyền cấu hình hạn mức ngân sách, xem dự báo chi phí tổng thể toàn doanh nghiệp, điều chỉnh tham số lạm phát, cấu hình tỷ lệ dự phòng rủi ro, và bật/tắt cờ `enable_ai_cost_forecasting`.
  - `FINANCE_MANAGER` (Quyền `cost_forecast:read`, `cost_forecast:run`): Quyền kích hoạt chạy dự báo chi phí mới, xem phân tích đa phân vị $P_{10}, P_{50}, P_{90}$, đối soát ngân sách thực tế với dự báo, và nhận cảnh báo sớm nguy cơ bội chi.
  - `MAINTENANCE_MANAGER` (Quyền `cost_forecast:read`): Quyền xem dự báo chi phí cấp phân xưởng (`cost_center_snapshot`) và danh mục thiết bị để lập kế hoạch mua sắm vật tư, xem danh sách thiết bị "Quả chanh" cần đề xuất thanh lý.
  - `TECHNICIAN`: Bị chặn truy cập toàn bộ các API và giao diện dự báo tài chính/ngân sách của doanh nghiệp.

---

## 6. Kiến Trúc & Luồng Dữ Liệu Hai Nhịp (Architecture & Data Flow)

```
[Dữ Liệu Vận Hành Hàng Ngày: Work Orders COMPLETED]
          │
          ├── 1. Khóa snapshot đơn giá vật tư (StockTransaction) & giờ công (LaborLog)
          ├── 2. Bóc tách Warranty & Insurance ──► Tính Net Cost thực tế
          ├── 3. Loại trừ 100% hóa đơn mua sắm vật tư lưu kho (Chỉ lấy tiêu hao thực)
          ├── 4. Bóc tách chi phí đại tu vốn hóa CapEx (is_capitalized = True)
          └── 5. Khấu trừ toàn bộ lịch sử chi phí của thiết bị đã thanh lý (DISPOSED)
          │
          ▼
[Kiểm Định Tập Trung Chi Phí Pareto & RRR Bad Actor]
          └── Phát hiện thiết bị "Quả chanh" (>50% chi phí tại <5% máy hoặc RRR >= 70%) ──► Gợi ý thanh lý
          │
          ▼
[Kiểm Tra Trạng Thái Quản Trị AI (Tenant.enable_ai_cost_forecasting)]
   ├── Nếu BẬT (và đủ dữ liệu >= 3 tháng) ──► Tiếp tục Pipeline AI QRF
   └── Nếu TẮT (hoặc Cold Start) ──────────► Kích hoạt Fallback Xác Định (Deterministic + SMA3 / %RAV)
          │
          ▼
[Feature Engineering Service: Trích Xuất 16 Đặc Trưng Đa Biến]
          ├── Bổ sung biến tích lũy nợ kỹ thuật: Backlog Orders & Deferred Hours
          ├── Bổ sung nghĩa vụ tài chính vật tư từ máy RUL Critical (Task 11.5)
          └── Biến đổi log1p (ln(1 + cost)) ổn định phương sai cho chuỗi chi phí
          │
          ▼
[Cơ Chế Ngân Sách Lai Ghép Hai Nhịp (Hybrid Forecasting Engine)]
  ┌─────────────────────────────────┴─────────────────────────────────┐
  ▼                                                                   ▼
[Nhịp 1: Kế Hoạch PM Xác Định]                       [Nhịp 2: QRF Dự Báo CM Ngẫu Nhiên]
  - Quét lịch PM Plans kỳ tới (Task 3.6)                - Dự báo khối lượng vật lý (Phụ tùng + Giờ công)
  - Nhân BOM định mức vật tư tiêu chuẩn                 - Nhân Đơn giá hiện tại * (1 + Lạm phát)
  - Trừ các PM được miễn trừ do trùng lặp                - Xuất phân vị QRF: P10, P50, P90
  - Tính Y_Planned_PM chính xác 100%                    - Giải biến đổi ngược exp(y) - 1
  └─────────────────────────────────┬─────────────────────────────────┘
                                    │
                                    ▼
                     [Tổng Hợp Ngân Sách Toàn Diện]
           Y_Total = Y_Planned_PM + Y_CM_Predicted (P50/P90) + Buffer
                                    │
                                    ▼
                     [Động Cơ Cảnh Báo Sớm Bội Chi]
  ├── So sánh Y_Total với Ngân Sách Được Duyệt (Approved Budget)
  ├── Nếu Tỷ lệ > 85% ──► Trạng thái WARNING ──► Gửi Notification mức WARNING (Task 10.1)
  └── Nếu Tỷ lệ > 100% ──► Trạng thái CRITICAL_OVERRUN ──► Bắn thông báo Real-time mức CRITICAL
```

---

## 7. Mô Hình Dữ Liệu & Thực Thể (Data Model & Schema)

### 7.1. Bảng `work_order_costs` (Lưu trữ snapshot chi phí bất biến và chi phí ròng)
```sql
CREATE TABLE work_order_costs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id),
  work_order_id UUID NOT NULL UNIQUE REFERENCES work_orders(id),
  cost_center_snapshot VARCHAR(255) NULL, -- Ảnh chụp phân xưởng/trung tâm chi phí tại thời điểm chốt
  material_cost DECIMAL(19, 2) NOT NULL DEFAULT 0.00, -- Tổng chi phí vật tư snapshot
  labor_cost DECIMAL(19, 2) NOT NULL DEFAULT 0.00, -- Tổng chi phí giờ công snapshot
  vendor_cost DECIMAL(19, 2) NOT NULL DEFAULT 0.00, -- Chi phí thuê ngoài dịch vụ
  gross_cost DECIMAL(19, 2) NOT NULL DEFAULT 0.00, -- Tổng giá trị thực tế phát sinh
  warranty_covered_amount DECIMAL(19, 2) NOT NULL DEFAULT 0.00, -- Hãng bảo hành chi trả
  insurance_covered_amount DECIMAL(19, 2) NOT NULL DEFAULT 0.00, -- Bảo hiểm chi trả
  net_cost DECIMAL(19, 2) NOT NULL DEFAULT 0.00, -- Số tiền thực tế doanh nghiệp bỏ tiền mặt (Gross - Bảo hành - Bảo hiểm)
  is_capital_overhaul BOOLEAN DEFAULT FALSE, -- Cờ đại tu lớn CapEx (vốn hóa tài sản)
  is_cost_frozen BOOLEAN DEFAULT FALSE, -- Khóa bất biến sau khi nghiệm thu hoàn tất
  cost_frozen_at TIMESTAMP WITH TIME ZONE NULL, -- Mốc thời gian khóa cứng chi phí
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_wo_costs_tenant_frozen ON work_order_costs(tenant_id, is_cost_frozen, created_at);
CREATE INDEX idx_wo_costs_cost_center ON work_order_costs(tenant_id, cost_center_snapshot);
```

### 7.2. Bảng `budget_forecasts` (Lưu trữ kết quả dự báo ngân sách lai ghép)
```sql
CREATE TABLE budget_forecasts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id),
  cost_center_snapshot VARCHAR(255) NULL, -- NULL là cấp Macro toàn công ty, chuỗi ký tự là phân xưởng cụ thể
  forecast_period VARCHAR(16) NOT NULL, -- Ví dụ: '2026-Q4' hoặc '2026-11'
  forecast_method VARCHAR(32) NOT NULL DEFAULT 'HYBRID_QRF', -- 'HYBRID_QRF' hoặc 'DETERMINISTIC_FALLBACK'
  approved_budget DECIMAL(19, 2) NOT NULL DEFAULT 0.00, -- Ngân sách được phê duyệt (VNĐ)
  planned_pm_budget DECIMAL(19, 2) NOT NULL DEFAULT 0.00, -- Ngân sách PM định kỳ xác định từ lịch
  predicted_cm_median DECIMAL(19, 2) NOT NULL DEFAULT 0.00, -- Dự báo sự cố ngẫu nhiên P50
  predicted_cm_lower_p10 DECIMAL(19, 2) NOT NULL DEFAULT 0.00, -- Kịch bản tối thiểu P10
  predicted_cm_upper_p90 DECIMAL(19, 2) NOT NULL DEFAULT 0.00, -- Kịch bản rủi ro xấu nhất P90
  contingency_buffer DECIMAL(19, 2) NOT NULL DEFAULT 0.00, -- Quỹ dự phòng khẩn cấp
  total_forecast_median DECIMAL(19, 2) NOT NULL DEFAULT 0.00, -- Tổng ngân sách dự báo P50
  total_forecast_p90 DECIMAL(19, 2) NOT NULL DEFAULT 0.00, -- Tổng ngân sách dự báo P90
  budget_usage_ratio FLOAT NOT NULL DEFAULT 0.0, -- % tỷ lệ sử dụng ngân sách (Total Forecast / Approved Budget * 100)
  budget_status VARCHAR(16) NOT NULL DEFAULT 'HEALTHY', -- 'HEALTHY', 'WARNING', 'CRITICAL_OVERRUN'
  inflation_rate_applied FLOAT NOT NULL DEFAULT 0.045, -- Tỷ lệ lạm phát áp dụng (mặc định 4.5%)
  backlog_work_orders_count INT NOT NULL DEFAULT 0, -- Số lượng phiếu bảo trì tồn đọng
  deferred_maintenance_hours FLOAT NOT NULL DEFAULT 0.0, -- Số giờ bảo trì bị hoãn lại
  rul_critical_liability DECIMAL(19, 2) NOT NULL DEFAULT 0.00, -- Nghĩa vụ tài chính phụ tùng từ Task 11.5 RUL
  lemon_assets_detected JSONB NOT NULL DEFAULT '[]', -- Danh sách các thiết bị "Quả chanh" chiếm dụng chi phí
  top_cost_drivers JSONB NOT NULL DEFAULT '[]', -- Top các đặc trưng ảnh hưởng mạnh nhất (Feature Importance)
  is_ai_fallback BOOLEAN DEFAULT FALSE, -- Cờ báo hiệu kết quả sinh ra từ cơ chế Fallback khi tắt AI
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_budget_forecast_tenant_period ON budget_forecasts(tenant_id, forecast_period);
CREATE INDEX idx_budget_forecast_center ON budget_forecasts(tenant_id, cost_center_snapshot, created_at DESC);
```

---

## 8. Đặc Tả Giao Diện Lập Trình (API Specifications & Contracts)

### Danh Mục Endpoints:

| Phương Thức | Đường Dẫn | Chức Năng |
| :--- | :--- | :--- |
| `GET` | `/api/v1/cost-forecasting/current-forecast/` | Lấy kết quả dự báo ngân sách kỳ hiện tại (Macro toàn công ty hoặc theo phân xưởng `cost_center`) |
| `POST` | `/api/v1/cost-forecasting/run-forecast/` | Kích hoạt tác vụ tính toán dự báo ngân sách mới cho kỳ được chỉ định |
| `GET` | `/api/v1/cost-forecasting/lemon-assets/` | Lấy danh sách thiết bị "Quả chanh" & Bad Actors theo kiểm định Pareto 80/20 và ngưỡng $RRR \ge 70\%$ |
| `GET` | `/api/v1/cost-forecasting/historical-trends/` | Lấy chuỗi chi phí thực tế quá khứ đối sánh với đường phân vị dự báo $P_{10}, P_{50}, P_{90}$ |
| `GET` | `/api/v1/cost-forecasting/readiness/` | Kiểm tra tính sẵn sàng của dữ liệu huấn luyện và trạng thái cờ quản trị AI của Tenant |

### Cấu Trúc Dữ Liệu Mẫu:

#### 1. Lấy kết quả dự báo ngân sách (`GET /api/v1/cost-forecasting/current-forecast/?cost_center=PhanXuongCoDien&period=2026-Q4`):
```json
{
  "success": true,
  "data": {
    "period": "2026-Q4",
    "costCenter": "PhanXuongCoDien",
    "forecastMethod": "HYBRID_QUANTILE_FOREST",
    "isAiFallback": false,
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
      "inflationRateAppliedPercent": 4.5,
      "fleetRavCostRatioPercent": 3.8
    },
    "lemonAssetsAlert": {
      "isConcentrationDetected": true,
      "totalBadActorsCount": 1,
      "topLemonAsset": {
        "assetId": "ast-pump-101",
        "assetName": "Bơm hóa chất ly tâm P-101",
        "historicalCostContributionPercent": 56.4,
        "rrrPercent": 78.5,
        "recommendation": "Thiết bị chiếm 56.4% chi phí sửa chữa toàn xưởng (RRR = 78.5% nguyên giá). Đề xuất lập hồ sơ thanh lý để giảm ngay 76,000,000 VNĐ dự báo chi phí Quý 4."
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

#### 2. Kích hoạt tính toán dự báo mới (`POST /api/v1/cost-forecasting/run-forecast/`):
- **Request Payload**:
```json
{
  "period": "2026-Q4",
  "costCenter": null,
  "approvedBudget": 500000000.0,
  "inflationRate": 0.045,
  "contingencyBufferPercent": 0.05
}
```
- **Response**:
```json
{
  "success": true,
  "message": "Tính toán dự báo ngân sách lai ghép thành công.",
  "data": {
    "forecastId": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "budgetStatus": "HEALTHY",
    "totalForecastMedian": 445000000.0,
    "usageRatioPercent": 89.0
  }
}
```

---

## 9. Đặc Tả Trải Nghiệm Người Dùng (UI/UX Behavioral Specifications)

- **Đồng hồ đo áp lực ngân sách đa phân vị (Multi-Quantile Budget Gauge)**:
  - Kim đo chính hiển thị kịch bản trung vị $P_{50}$ (kế hoạch cơ sở).
  - Vạch dải bóng mờ hiển thị kịch bản rủi ro $P_{90}$ và vùng đệm dự phòng khẩn cấp (`contingency_buffer`).
  - Ba phân vùng màu trực quan: Xanh lá ($< 85\%$), Vàng cam ($85\% - 100\%$), Đỏ rực ($> 100\%$ Nguy cơ bội chi).
  - Tự động thay đổi màu sắc chủ đạo đồng bộ với Theme thương hiệu của Tenant (`Tenant.theme_color`).
- **Thẻ Cảnh Báo "Thiết Bị Quả Chanh" (Lemon Asset Bad Actor Banner)**:
  - Khi kiểm định Pareto hoặc RRR phát hiện máy chiếm dụng bất thường ngân sách, hiển thị banner màu đỏ mận:
    *"Phát hiện 1 thiết bị bất thường ngốn 56% chi phí bảo trì toàn xưởng (RRR = 78.5%). Nhấn vào để xem báo cáo thẩm định thanh lý thiết bị."*
  - Nút bấm hành động: *"Mô phỏng cắt giảm chi phí nếu thanh lý máy này"* — hiển thị ngay biểu đồ chi phí giảm sốc cho Ban Giám đốc đối chiếu tức thì.
- **Thanh đo Nợ Kỹ Thuật (Deferred Maintenance Debt Bar)**:
  - Hiển thị số lượng lệnh PM bị hoãn và số giờ bảo trì tồn đọng, đi kèm nhãn cảnh báo mức độ tích lũy nguy cơ bùng nổ chi phí ("Surge Risk: LOW / MEDIUM / HIGH") trong kỳ tới.
- **Bộ lọc Trung Tâm Chi Phí (Cost Center Selector)**:
  - Cho phép Kế toán trưởng lọc xem dữ liệu toàn công ty (Macro) hoặc chọn từng phân xưởng cụ thể dựa trên chuỗi ảnh chụp `cost_center_snapshot` để giao chỉ tiêu hạn mức ngân sách cho từng Quản đốc.
- **Huy Hiệu Trạng Thái Quản Trị AI (AI Governance Status Badge)**:
  - Hiển thị biểu tượng `AI Engine Active (Quantile Forest)` khi cờ `enable_ai_cost_forecasting = True`.
  - Hiển thị nhãn `Heuristic Fallback Mode` màu vàng cam kèm chú thích *"Chế độ dự báo xác định theo lịch PM & trung bình trượt"* khi quản trị viên tắt cờ AI hoặc cơ sở mới mở.

---

## 10. Tiêu Chí Chấp Nhận & Ma Trận Kịch Bản Kiểm Thử (Acceptance Criteria & Test Scenarios)

### 10.1. Ma Trận Kịch Bản Kiểm Thử Nghiệp Vụ & Tài Chính

| Mã Test | Tên Kịch Bản | Điều Kiện Thử Nghiệm | Hành Vi Kỳ Vọng | Trạng Thái |
| :--- | :--- | :--- | :--- | :--- |
| **TC-COST-01** | Khóa bất biến đơn giá snapshot | Nghiệm thu hoàn tất Work Order. Sau đó thay đổi tăng đơn giá phụ tùng và lương thợ trong kho dữ liệu | `work_order_costs.is_cost_frozen = True`, chi phí đơn hàng cũ giữ nguyên $100\%$ không bị biến động | Chưa thực hiện |
| **TC-COST-02** | Bẫy bảo trì hoãn lại (Deferred Trap) | Quý 3 cắt giảm 50% PM khiến chi phí giảm giả tạo, nhưng Backlog nợ kỹ thuật tăng vọt 15 phiếu | Mô hình nhận diện nợ kỹ thuật qua 2 đặc trưng tích lũy, dự báo Quý 4 chi phí tăng đột biến thay vì tiếp tục giảm | Chưa thực hiện |
| **TC-COST-03** | Khắc phục điểm mù ngoại suy lạm phát | Giá phụ tùng toàn cầu tăng 30% so với miền dữ liệu huấn luyện lịch sử | Dự báo khối lượng vật lý $\times$ Giá hiện tại $(1 + I_{\text{inflation}})$, kết quả dự báo tài chính vượt trần lịch sử chính xác | Chưa thực hiện |
| **TC-COST-04** | Chống bão hòa xả ngân sách cuối năm | Tháng 12 chi 200 triệu VNĐ mua sắm phụ tùng cất vào kho dự trữ (`transaction_type = 'RECEIPT'`) | Dữ liệu huấn luyện loại trừ 100% hóa đơn nhập kho, không tạo tính mùa vụ ảo cho tháng 12 hàng năm | Chưa thực hiện |
| **TC-COST-05** | Bóc tách chi phí bảo hành & bảo hiểm | Thay cụm trục chính 300 triệu VNĐ được nhà cung cấp bảo hành chi trả 100% | `gross_cost = 300M`, `warranty = 300M`, `net_cost = 0M`. Mô hình dự báo chỉ học và dự phóng trên `net_cost` | Chưa thực hiện |
| **TC-COST-06** | Kiểm định Pareto thiết bị "Quả chanh" | 1 máy bơm ly tâm chiếm 58% chi phí bảo trì toàn xưởng ($RRR = 78.5\%$) | Kích hoạt cảnh báo Lemon Asset Bad Actor, gợi ý phương án thanh lý kèm con số cắt giảm chi phí dự phóng | Chưa thực hiện |
| **TC-COST-07** | Khấu trừ lịch sử máy đã thanh lý | Thiết bị Quả chanh được chuyển trạng thái sang `DISPOSED` | Pipeline tiền xử lý tự động loại bỏ toàn bộ chi phí của máy này ra khỏi tập dữ liệu huấn luyện của kỳ tới | Chưa thực hiện |
| **TC-COST-08** | Cơ chế ngân sách lai ghép (PM + CM) | Có 10 PM Plans định kỳ cố định trong tháng tới, trong đó 1 PM được miễn trừ do trùng lặp | Tính chính xác 100% chi phí PM theo định mức BOM (đã trừ PM trùng lặp), chỉ dùng AI dự báo phần sự cố CM | Chưa thực hiện |
| **TC-COST-09** | Xuất phân vị Quantile Forests P10/P50/P90 | Chạy mô hình QRF trên chuỗi dữ liệu chi phí đã biến đổi Log-Transform | Xuất đủ 3 phân vị $P_{10} \le P_{50} \le P_{90}$ có cơ sở phân phối toán học rõ ràng và giải ngược $\exp(y) - 1$ chính xác | Chưa thực hiện |
| **TC-COST-10** | Tích hợp nghĩa vụ tài chính từ RUL 11.5 | 2 động cơ rơi vào mức cảnh báo `CRITICAL RISK` ($RUL \le 14$ ngày) từ Task 11.5 | Tự động cộng chi phí phụ tùng thay thế (`primary_spare_part`) vào dự báo ngân sách vật tư của kỳ tới | Chưa thực hiện |
| **TC-COST-11** | Cảnh báo sớm nguy cơ bội chi ngân sách | Tổng dự báo ngân sách vượt hạn mức được duyệt ($Usage > 100\%$) | Gán trạng thái `CRITICAL_OVERRUN`, kích hoạt phát sinh `Notification` Real-time gửi đến Admin & Kế toán | Chưa thực hiện |
| **TC-COST-12** | Chuyển đổi an toàn khi tắt AI / Khởi động lạnh | Tenant tắt `enable_ai_cost_forecasting = False` hoặc chi nhánh mới mở có $< 3$ tháng dữ liệu | Kích hoạt Fallback xác định (PM từ lịch + $\text{SMA}_3$ hoặc 3-5% RAV), gắn cờ `is_ai_fallback = True`, không ném lỗi | Chưa thực hiện |

---

## 11. Implementation Notes — For Implementation Phase Only

> [!IMPORTANT]
> **REFERENCE ONLY — DO NOT IMPLEMENT OR MODIFY CODE BASED ON THIS SECTION DURING SPEC REVIEW. These notes are intended for the implementation phase after the specification is approved.**

Phần này lưu trữ các chỉ dẫn kỹ thuật hạ tầng chi tiết để các kỹ sư tham khảo trong quá trình triển khai mã nguồn:

### 11.1. Cài Đặt Quantile Regression Forests Bằng Scikit-Learn / Quantile-Forest
- Khuyến nghị sử dụng thư viện `quantile-forest` (`RandomForestQuantileRegressor`) hoặc trích xuất phân vị trực tiếp từ lá cây của `RandomForestRegressor`:
  ```python
  import numpy as np
  from sklearn.ensemble import RandomForestRegressor
  from quantile_forest import RandomForestQuantileRegressor

  # Khởi tạo mô hình Rừng Hồi Quy Phân Vị với siêu tham số phòng thủ
  qrf = RandomForestQuantileRegressor(
      n_estimators=100,
      max_depth=6,
      min_samples_split=4,
      min_samples_leaf=2,
      random_state=42
  )
  
  # Huấn luyện trên chuỗi đã biến đổi Log-Transform: y_train_log = np.log1p(y_train)
  qrf.fit(X_train, y_train_log)
  
  # Dự đoán đồng thời 3 phân vị P10, P50, P90
  predictions_log = qrf.predict(X_test, quantiles=[0.10, 0.50, 0.90])
  
  # Giải biến đổi ngược về giá trị tiền tệ thực tế: exp(y) - 1
  p10 = np.expm1(predictions_log[:, 0])
  p50 = np.expm1(predictions_log[:, 1])
  p90 = np.expm1(predictions_log[:, 2])
  ```

### 11.2. Công Thức Hai Nhịp Áp Dụng Chỉ Số Trượt Giá
```python
from decimal import Decimal
from typing import List, Dict

def calculate_hybrid_budget(
    planned_pm_cost: Decimal,
    predicted_parts_volume: List[float],
    predicted_labor_hours: float,
    current_parts_unit_prices: List[Decimal],
    current_hourly_rate: Decimal,
    inflation_rate: float = 0.045,
    contingency_rate: float = 0.05
) -> Dict[str, Decimal]:
    """
    Quy tắc 4 & 8: Động cơ ngân sách lai ghép 2 nhịp kết hợp chỉ số trượt giá.
    """
    # Nhịp 2: Nhân khối lượng vật lý với đơn giá hiện tại điều chỉnh lạm phát
    inflation_factor = Decimal(str(1.0 + inflation_rate))
    cm_materials = sum(
        Decimal(str(vol)) * price * inflation_factor 
        for vol, price in zip(predicted_parts_volume, current_parts_unit_prices)
    )
    cm_labor = Decimal(str(predicted_labor_hours)) * current_hourly_rate
    cm_total = cm_materials + cm_labor
    
    subtotal = planned_pm_cost + cm_total
    contingency = subtotal * Decimal(str(contingency_rate))
    total_forecast = subtotal + contingency
    
    return {
        "planned_pm": planned_pm_cost,
        "predicted_cm_materials": cm_materials,
        "predicted_cm_labor": cm_labor,
        "predicted_cm_total": cm_total,
        "contingency_buffer": contingency,
        "total_forecast": total_forecast
    }
```

### 11.3. Cấu Trúc Đóng Gói Module Giải Thuật (`eam_app/algorithms/cost_forecasting/`)
Mã nguồn được tổ chức hoàn chỉnh thành một package độc lập:
```
eam_app/algorithms/cost_forecasting/
├── __init__.py               # Package initializer
├── constants.py              # Siêu tham số QRF, ngưỡng lạm phát mặc định, ngưỡng Pareto & RRR
├── feature_pipeline.py       # Pipeline trích xuất 16 đặc trưng chuỗi thời gian đa biến
├── qrf_model.py              # Lớp bao gói mô hình Quantile Regression Forests (P10, P50, P90)
├── hybrid_engine.py          # Động cơ lập ngân sách lai ghép 2 nhịp (PM xác định + CM ngẫu nhiên)
├── lemon_detector.py         # Module kiểm định Pareto 80/20 & RRR Bad Actor
└── service.py                # Service điều phối cấp cao tích hợp ORM, Governance toggle và Notifications
```

---

## 12. Kế Hoạch Triển Khai & Nghiệm Thu (Implementation Checklist)

- [ ] **Task 11.6.1 — Immutable Cost Snapshot & Net Cost Schema**
  - [ ] Mở rộng bảng `work_order_costs`: Lưu snapshot đơn giá vật tư (`unit_price`) và nhân công (`hourly_rate`), bóc tách `gross_cost`, `warranty_covered_amount`, `insurance_covered_amount`, `net_cost`.
  - [ ] Thiết lập cơ chế khóa cứng chi phí bất biến (`is_cost_frozen = True`, `cost_frozen_at`) khi Work Order chuyển `COMPLETED`.
  - [ ] Xử lý liên kết với điều chỉnh chênh lệch giá (`is_variance_adjustment`) và xuất trả vật tư dư thừa (`RETURN`).
- [ ] **Task 11.6.2 — Actual Consumption Pipeline & Disposed Pruning**
  - [ ] Lọc sạch 100% hóa đơn nhập kho mua sắm mới (`RECEIPT`), chỉ trích xuất dữ liệu từ các lệnh bảo trì đã hoàn tất có tiêu hao vật tư thực tế (`ISSUE`).
  - [ ] Cài đặt cơ chế tự động khấu trừ toàn bộ lịch sử chi phí của thiết bị đã thanh lý (`status IN ('DISPOSED', 'RETIRED', 'SCRAPPED', 'SOLD')`).
- [ ] **Task 11.6.3 — Feature Engineering & Backlog Debt Tracking**
  - [ ] Xây dựng pipeline trích xuất 16 đặc trưng chuỗi thời gian đa biến.
  - [ ] Tích hợp 2 biến nợ kỹ thuật: `backlog_work_orders_count` và `deferred_maintenance_hours`.
  - [ ] Tích hợp nghĩa vụ tài chính vật tư từ các thiết bị rơi vào cảnh báo RUL nguy cấp (Task 11.5) hoặc cảnh báo suy thoái đột biến.
- [ ] **Task 11.6.4 — Two-Step Hybrid Forecasting & Quantile Forests (QRF)**
  - [ ] Xây dựng module tính toán ngân sách PM định kỳ xác định từ `PmPlan` và `PmPlanMaterial`, trừ bớt PM được miễn trừ do trùng lặp.
  - [ ] Cài đặt mô hình Quantile Regression Forests dự báo khối lượng CM và xuất $P_{10}, P_{50}, P_{90}$ dựa trên biến đổi Log-Transform.
  - [ ] Áp dụng hệ số trượt giá lạm phát ($I_{\text{inflation}}$) và đơn giá hiện hành ở tầng hậu xử lý tài chính.
- [ ] **Task 11.6.5 — Pareto Lemon Asset Audit & Early Overrun Warning**
  - [ ] Cài đặt thuật toán kiểm định phân bổ chi phí 80/20 kết hợp chỉ số $RRR \ge 70\%$ phát hiện nhóm Bad Actors.
  - [ ] Xây dựng động cơ đối soát hạn mức ngân sách và phát cảnh báo Real-time (`Notification`) mức `WARNING` hoặc `CRITICAL_OVERRUN` (Task 10.1).
  - [ ] Tích hợp cơ chế Fallback xác định khi tắt cờ quản trị `enable_ai_cost_forecasting = False` hoặc khi gặp trường hợp khởi động nguội.
- [ ] **Task 11.6.6 — Web Portal UI Integration & Test Matrix Verification**
  - [ ] Thiết kế đồng hồ đo áp lực ngân sách đa phân vị, thẻ cảnh báo thiết bị Quả chanh, thanh nợ kỹ thuật, và huy hiệu trạng thái quản trị AI.
  - [ ] Triển khai bộ kiểm thử tự động 12 test cases (`TC-COST-01` đến `TC-COST-12`) bảo đảm bao phủ toàn bộ các trường hợp biên tài chính và vận hành.

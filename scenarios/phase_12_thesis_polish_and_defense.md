# Thiết Kế Hệ Thống & Đặc Tả Kỹ Thuật: Phase 12 — Final Graduation Thesis Polish, Demo Seeding & Defense Readiness

Tài liệu này xác định kiến trúc bộ khung thực nghiệm, khởi tạo dữ liệu mẫu và chuẩn bị môi trường báo cáo bảo vệ đồ án tốt nghiệp kỹ sư / luận văn thạc sĩ cho hệ thống Quản lý Tài sản Doanh nghiệp (EAM). Hệ thống thiết lập quy trình khởi tạo dữ liệu mẫu thực tế đa ngành có tính đơn công (**Idempotent Master Demo Seeding**) kết hợp **bộ sinh dữ liệu du hành thời gian 12 tháng (Time-Travel Historical Generator)**, bộ khung đo lường kiểm thử định lượng chuẩn khoa học (**Quantitative Academic Benchmark Harness**) với cơ chế **hạt giống đôi kiểm chứng tính bền bỉ (Dual-Seed: Golden Seed 42 vs Live Random Seed)**, bảo đảm vận hành độc lập ngoại tuyến $100\%$ không phụ thuộc Internet (**Zero-Internet Air-Gapped Operation**), khu vực cách ly thử tải cực đoan khi Hội đồng yêu cầu phá vỡ (**Ad-hoc Destructive Testing Sandbox**), cơ chế **khôi phục trạng thái tức thì (Instant Snapshot Restore)**, chế độ diễn tập bí mật (**Fail-Safe Presentation Simulation Mode**), bảo mật dữ liệu tổng hợp tuân thủ Nghị định 13 (**Synthetic Privacy Compliance & ND13**), quy trình dọn dẹp môi trường tinh khiết (**Pristine State Flush**), kịch bản khởi động 1 chạm (`run_defense_demo.bat`), và **bộ kịch bản kiểm thử chấp nhận & trường hợp biên (Acceptance Criteria & Edge Cases)**.

Tài liệu đóng vai trò là **Đặc Tả Kỹ Thuật & Chuẩn Kiểm Thử (Technical Specification & Audit Baseline)** nhằm đối chiếu, rà soát và thực thi trọn vẹn toàn bộ tính năng phục vụ hội đồng chấm bảo vệ luận văn đạt kết quả xuất sắc nhất.

---

## 1. Mục Tiêu & Phạm Vi (Objective & Scope)

### 1.1. Bản Chất Nghiệp Vụ Của Ngày Bảo Vệ Luận Văn Tốt Nghiệp
Trong các buổi bảo vệ đồ án tốt nghiệp trước Hội đồng Khoa học:
- **Rủi ro hạ tầng mạng**: Hội trường lớn thường bị nghẽn sóng 4G, Wifi trường đại học chặn cổng mạng hoặc rớt mạng đột ngột. Nếu hệ thống phụ thuộc vào CDN bên ngoài hoặc Cloud API, ứng dụng sẽ bị treo trắng xóa màn hình, dẫn đến thất bại thảm hại.
- **Bẫy demo rỗng & nghi ngờ số liệu**: Hội đồng bấm sang trang 2 hoặc lọc ngày tháng năm trước mà không có dữ liệu sẽ đánh giá đề tài là "bản vẽ dở dang". Ngược lại, nếu số liệu quá hoàn hảo do cố định hạt giống (Seed 42), Thầy cô có thể nghi ngờ thuật toán bị Overfitting (chỉ chạy tốt với đúng seed đó).
- **Các câu hỏi phá vỡ & thử thách tại chỗ**: Hội đồng bất ngờ yêu cầu thử các tình huống cực đoan (*"Thợ bận hết thì chia việc thế nào?", "Rung chấn cảm biến bị loạn thì AI có sập không?"*). Nếu chỉ có dữ liệu mẫu hoàn hảo, sinh viên sẽ lúng túng không thể tái tạo tình huống tại chỗ.

### 1.2. Vai Trò Của Phase 12
Phase 12 là tầng "đóng gói vũ khí tối thượng" đưa toàn bộ công trình nghiên cứu ra trước Hội đồng:
1. **Dữ liệu sống động 12 tháng (Time-Travel Authenticity)**: Tự động sinh ngược hàng ngàn Work Order, AuditLog và chuỗi cảm biến trong quá khứ, giúp biểu đồ phân tích và dự báo ngân sách lên xuống chân thực như một nhà máy đang vận hành thật.
2. **Khu vực Sandbox thử thách phá vỡ**: Chuẩn bị sẵn phân xưởng riêng biệt với các ca cực đoan để sẵn sàng cho Hội đồng "thử lửa" hệ thống mà không làm ảnh hưởng luồng demo chính.
3. **Cơ chế Hạt giống đôi (Dual-Seed)**: Cho phép chuyển đổi linh hoạt giữa Seed 42 (khớp số liệu báo cáo 100%) và Live Random Seed (chứng minh tính bền bỉ của thuật toán).
4. **Môi trường ngoại tuyến 100% & Khôi phục Snapshot**: Mọi dịch vụ chạy On-Premises, dọn sạch Redis/Cache trước khi diễn, và nút 1-chạm khôi phục CSDL về trạng thái sạch ban đầu trong 1.5 giây.

---

## 2. Ràng Buộc Kế Thừa Hệ Thống (Existing System Constraints & Codebase Reuse)

- **Tái Sử Dụng Mô Hình Multi-Tenancy**: Toàn bộ dữ liệu demo của 3 khách hàng mẫu và 1 phân xưởng Sandbox kế thừa `BaseTenantModel`, chứng minh khả năng cách ly phân quyền tuyệt đối trước hội đồng.
- **Tái Sử Dụng Thực Thể Nghiệp Vụ Toàn Hệ Thống**:
  - `Asset`, `FacilityComponent`, `MeterReading`, `WorkOrder`, `SparePart`, `PmPlan`, `AttendanceLog`, `TechnicalDocument`.
- **Tích Hợp Đồng Bộ 8 Thuật Toán Cốt Lõi**:
  1. Task 11.1: Phân công Hungary (Kuhn-Munkres).
  2. Task 11.2: Phân công đa mục tiêu Di truyền (Genetic Algorithm).
  3. Task 11.3: Tối ưu lộ trình di chuyển thợ TSP (2-Opt Manhattan).
  4. Task 11.4: Giám sát tình trạng & Phát hiện dị biệt (Z-score & Isolation Forest).
  5. Task 11.5: Dự đoán tuổi thọ còn lại RUL (PyTorch LSTM).
  6. Task 11.6: Dự báo ngân sách bảo trì (Random Forest Regressor).
  7. Task 11.7: Điểm danh sinh trắc học hiện trường (MobileFaceNet & Haversine).
  8. Task 11.9: Trợ lý AI RAG tra cứu kỹ thuật (Sentence-Transformers & PGVector).

---

## 3. Yêu Cầu Nghiệp Vụ & 10 Quy Tắc Cốt Lõi (Business Requirements & Core Rules)

Toàn bộ công tác đóng gói và chuẩn bị bảo vệ đồ án phải tuân thủ nghiêm ngặt 10 quy tắc phòng thủ sau:

### Quy Tắc 1: Khởi Tạo Dữ Liệu Đơn Công & Du Hành Thời Gian 12 Tháng (Idempotent Seeding & 12-Month Time-Travel)
- **Điểm Yếu Nghiệp Vụ (The "Empty Shell" Demo Effect)**: Khi mở danh sách Work Order hoặc Dashboard, màn hình có dữ liệu ngày hôm nay, nhưng khi bấm sang trang 2 hoặc lọc các tháng trước, màn hình trống trơn. Ứng dụng trông như một bản mockup thiếu sức sống.
- **Quy Tắc Bắt Buộc**:
  1. Lệnh quản trị `python manage.py seed_defense_demo` hỗ trợ cờ dọn dẹp `--clean`.
  2. **Bộ sinh dữ liệu Du hành thời gian (Time-Travel Generator)**:
     - Tự động sinh dữ liệu lùi về quá khứ $12 - 24\text{ tháng}$ với hơn 1,000 bản ghi Work Order đã hoàn thành rải rác.
     - Sinh chuỗi số đo viễn thám cảm biến mượt mà theo chu kỳ vận hành và mùa vụ.
     - Sinh đầy đủ nhật ký kiểm toán `AuditLog` và tiêu hao vật tư để biểu đồ Phân tích ([Task 10.3](file:///d:/GameLinkNeverDie/eam-enterprise-assset-management/scenarios/phase_10_3_reports_export_engine.md)) và Dự báo chi phí ([Task 11.6](file:///d:/GameLinkNeverDie/eam-enterprise-assset-management/scenarios/phase_11_6_maintenance_cost_forecasting.md)) hiển thị sống động như một nhà máy đang vận hành thực tế.

### Quy Tắc 2: Tính Tái Lập Khoa Học & Kiểm Thử Hạt Giống Đôi (Dual-Seed: Reproducibility vs Live Robustness)
- **Điểm Yếu Nghiệp Vụ (Overfitted Golden Seed)**: Giảng viên phản biện hỏi: *"Em set seed cố định (Seed=42) thì ra kết quả đẹp, nhỡ đâu thuật toán chỉ chạy tốt với seed này? Em thử đổi seed ngẫu nhiên xem hệ thống có sập không?"*. Sinh viên không có cơ chế chứng minh tính bền vững sẽ bị đánh giá thấp.
- **Quy Tắc Bắt Buộc**:
  1. Bảng điều khiển Demo tích hợp nút chuyển đổi **"Academic Seed (42) vs Live Random Seed (`time.time()`)"**.
  2. Khi chọn **Academic Seed**: Gọi `set_global_academic_seed(42)`, đảm bảo kết quả trùng khớp $100\%$ từng chữ số thập phân so với số liệu in trong quyển báo cáo luận văn.
  3. Khi chọn **Live Random Seed**: Hệ thống tự động chạy 5 lần lặp ngẫu nhiên và hiển thị bảng phân phối dao động chuẩn ($\mu \pm \sigma$):
     - Makespan GA: $4.2 \pm 0.3\text{ giờ}$.
     - RUL RMSE: $6.8 \pm 0.4\text{ ngày}$.
     - Chứng minh thuật toán cực kỳ ổn định (Robust), đập tan mọi nghi ngờ về việc gian lận số liệu.

### Quy Tắc 3: Vận Hành Ngoại Tuyến Độc Lập 100% Air-Gapped (Zero-Internet Guardrail)
- **Điểm Yếu Nghiệp Vụ**: Hội trường trường đại học sóng kém hoặc Wifi bắt đăng nhập cổng xác thực (Captive Portal). Các thư viện CDN bên ngoài tải không được khiến giao diện vỡ nát, mất biểu đồ và bản đồ.
- **Quy Tắc Bắt Buộc**:
  1. **100% tài nguyên giao diện (CSS, JS, Fonts, Icons)** được lưu trữ cục bộ tại `/static/vendor/` trong mã nguồn. Tuyệt đối không chứa bất kỳ liên kết CDN ra Internet nào (`cdn.jsdelivr.net`, `cdnjs.cloudflare.com`, v.v.).
  2. Bản đồ số hỗ trợ bộ nhớ đệm ngói bản đồ ngoại tuyến hoặc chuyển sang sơ đồ lưới phẳng 2D nội bộ nhà máy.
  3. Toàn bộ các mô hình AI (LSTM, TFLite, Sentence-Transformers, Ollama) chạy cục bộ trên máy tính cá nhân, không gọi bất kỳ Cloud API bên ngoài nào.

### Quy Tắc 4: Chế Độ Diễn Tập An Toàn & Khu Vực Sandbox Thử Tải Cực Đoan (Presentation Mode & Destructive Sandbox)
- **Điểm Yếu Nghiệp Vụ (Ad-hoc Destructive Testing)**: Hội đồng yêu cầu: *"Bây giờ Thầy muốn thợ điện và cơ khí đều bận hết, hệ thống Hungary của em sẽ chia 5 Work Order khẩn cấp này thế nào?"*. Nếu chỉ có dữ liệu mẫu hoàn hảo, sinh viên sẽ lúng túng không diễn giải được.
- **Quy Tắc Bắt Buộc**:
  1. Lệnh seed tạo riêng một **Tenant Sandbox (Khu vực Cách ly Thử thách)** với các trạng thái biên cực đoan:
     - Toàn bộ thợ đang bận làm việc khác $\rightarrow$ Trình diễn cơ chế Thợ ảo (Virtual Technician) và đẩy việc vào Backlog của GA ([Task 11.2](file:///d:/GameLinkNeverDie/eam-enterprise-assset-management/scenarios/phase_11_2_genetic_algorithm_assignment.md)).
     - Rung chấn cảm biến bị nhiễu loạn $\rightarrow$ Trình diễn bộ lọc Theil-Sen Robust Drift ([Task 11.4](file:///d:/GameLinkNeverDie/eam-enterprise-assset-management/scenarios/phase_11_4_sensor_anomaly_detection.md)).
     - Kho hết sạch phụ tùng $\rightarrow$ Trình diễn rào chắn Stage 2 Kitting Gate khóa đại tu ([Task 11.8](file:///d:/GameLinkNeverDie/eam-enterprise-assset-management/scenarios/phase_11_8_decision_tree_hsm_workflow.md)).
  2. Tích hợp chế độ diễn tập bí mật (Presentation Mode - Chạm 5 lần vào Logo) để bơm nhanh số đo giả lập khi camera hoặc phần cứng bị trục trặc ánh sáng.

### Quy Tắc 5: Phân Lập Thực Nghiệm 3 Miền & Dữ Liệu Tổng Hợp Tuân Thủ Nghị Định 13 (Synthetic Privacy Compliance & ND13)
- **Điểm Yếu Nghiệp Vụ (Copyright / Sensitive Info Leak)**: Sử dụng bản đồ có bản quyền hoặc ảnh đại diện của người thật cho MobileFaceNet khi chưa xin phép có thể vi phạm quyền riêng tư và Nghị định 13/2023/NĐ-CP khi báo cáo trước Hội đồng.
- **Quy Tắc Bắt Buộc**:
  1. $100\%$ dữ liệu mẫu là dữ liệu tổng hợp giả lập (Synthetic Data).
  2. Tên doanh nghiệp được ẩn danh hóa chuẩn mực: *Tenant 1: Cơ Khí Chính Xác Tân Thuận (Heavy Industry)*, *Tenant 2: Dược Phẩm Sinh Học PharmaTech (Cleanroom/Pharma)*, *Tenant 3: Đại Học Bách Khoa TP.HCM (Campus Facility)*.
  3. Ảnh khuôn mặt đăng ký sinh trắc học sử dụng ảnh AI tổng hợp (ThisPersonDoesNotExist) hoặc ảnh chính tác giả có văn bản chấp thuận, bảo đảm tuyệt đối tính pháp lý và đạo đức nghiên cứu.

### Quy Tắc 6: Khớp Nối Xâu Chuỗi Số Liệu Toàn Vẹn Giữa 8 Thuật Toán Cốt Lõi (Cross-Algorithm Continuity)
- **Điểm Yếu Nghiệp Vụ**: Các thuật toán bị rời rạc, làm thuật toán này chạy xong nhưng thuật toán kia không có dữ liệu đầu vào để trình diễn liên hoàn trước Hội đồng.
- **Quy Tắc Bắt Buộc**:
  Toàn bộ dữ liệu demo được xâu chuỗi thành kịch bản khép kín:
  $$\text{Rung chấn FEMTO (11.4)} \xrightarrow{\text{Z-score} \ge 3.0} \text{Dự báo RUL 4.2 ngày (11.5)} \xrightarrow{} \text{Sinh Work Order (10.1)} \xrightarrow{} \text{Phân công GA/Hungary (11.1/11.2)}$$
  $$\xrightarrow{} \text{Lộ trình TSP (11.3)} \xrightarrow{} \text{Điểm danh Face/GPS (11.7)} \xrightarrow{} \text{Trợ lý SOP RAG (11.9)} \xrightarrow{} \text{Đại tu HSM 8 bước (11.8)}$$

### Quy Tắc 7: Tự Động Xuất Bảng Đánh Giá Đối Sánh Benchmark Chuẩn Học Thuật (Automated Markdown Evaluation Benchmark Table)
- **Điểm Yếu Nghiệp Vụ**: Khi giảng viên phản biện hỏi *"Thuật toán GA tốt hơn Hungary ở điểm nào? Sai số RMSE của LSTM là bao nhiêu?"*, người trình bày lúng túng phải mở từng tệp mã nguồn để xem.
- **Quy Tắc Bắt Buộc**:
  1. Lệnh `python manage.py run_academic_benchmarks` tự động chạy đánh giá và in bảng Markdown tổng kết trực tiếp lên màn hình Console và lưu vào tệp `academic_benchmark_results.md`.
  2. Bảng tổng hợp đối sánh đầy đủ các chỉ số khoa học: Thời gian tính toán ($ms$), Độ phức tạp thời gian, Độ lệch chuẩn phân bổ tải $\sigma$, Tỷ lệ rút ngắn quãng đường ($\%$, Sai số dự báo $R^2$, RMSE, MAPE, Độ chính xác khớp khuôn mặt ($\%$) và Độ trễ sinh token đầu tiên.

### Quy Tắc 8: Dọn Dẹp Môi Trường Tinh Khiết & Khôi Phục Snapshot Tức Thì (Pristine Flush & Snapshot Restore)
- **Điểm Yếu Nghiệp Vụ (Dirty State Trap)**: Dữ liệu test từ hôm trước còn sót lại trong Redis Cache làm sai lệch biểu đồ hôm sau; hoặc sau khi làm theo một yêu cầu "phá hủy" của một Thầy, hệ thống bị kẹt ở trạng thái hỏng hóc, không demo tiếp được các chức năng khác.
- **Quy Tắc Bắt Buộc**:
  1. Kịch bản khởi động tự động thực hiện **Pristine State Flush**: Xóa sạch Redis (`redis-cli flushall`), dọn Django Cache (`clear_cache`), xóa `celerybeat-schedule`, hủy session/token cũ để môi trường sạch bóng $100\%$.
  2. Bổ sung nút **"Khôi phục Snapshot tức thì" (Instant Snapshot Restore)**: Phục hồi CSDL về trạng thái ban đầu trong vòng $\le 1.5\text{ giây}$ sau khi biểu diễn xong các tình huống thử thách của Hội đồng.

### Quy Tắc 9: Giả Lập Bất Thường Cảm Biến Kích Hoạt Chuỗi Hai Tầng (One-Click Anomaly Simulation)
- **Điểm Yếu Nghiệp Vụ**: Để chứng minh luồng liên hoàn Task 11.4 sang Task 11.5, người trình bày phải ngồi gõ từng số đo rung nhiệt bằng tay rất lâu và dễ gõ nhầm.
- **Quy Tắc Bắt Buộc**:
  Cung cấp API `POST /api/v1/demo/trigger-scenario/` cho phép chỉ với 1 cú click chuột trên giao diện Demo Panel:
  - Tự động bơm 1 số đo rung động dị biệt ($v = 7.85\text{ mm/s}$) vào Máy nén khí.
  - Hệ thống tự động nhảy thông báo chuông Real-time (Task 10.1).
  - Tự động gọi Task 11.5 cập nhật RUL về 4.2 ngày (`CRITICAL RISK`) và sinh phiếu Work Order khẩn cấp ngay trước mắt Hội đồng.

### Quy Tắc 10: Đóng Gói Triển Khai 1 Thao Tác Chống Lỗi Máy Tính Khách (One-Click Host Deployment)
- **Điểm Yếu Nghiệp Vụ**: Đến ngày bảo vệ laptop cá nhân gặp sự cố, phải mượn máy tính của khoa; việc cài đặt lại môi trường mất cả buổi sáng và dễ xung đột thư viện.
- **Quy Tắc Bắt Buộc**:
  1. Cung cấp tệp kịch bản khởi động 1 chạm tự động (`run_defense_demo.bat` trên Windows hoặc `docker-compose.yml`).
  2. Kịch bản tự động dọn Redis/Cache, kiểm tra dịch vụ PostgreSQL, Redis, MinIO, Ollama; tự migrate, seed dữ liệu du hành thời gian, và tự mở trình duyệt web sẵn sàng thuyết minh trong vòng 5 giây.

---

## 4. Bảng Đánh Giá Đối Sánh Định Lượng 8 Thuật Toán Khoa Học (Academic Benchmark Matrix)

Hệ thống cung cấp bộ công cụ đo lường thực nghiệm đối sánh tự động 8 thuật toán với các chỉ số mục tiêu xuất sắc:

| TT | Phân Hệ & Thuật Toán | Bài Toán Mục Tiêu | Chỉ Số Đánh Giá | Kết Quả Thực Nghiệm Chuẩn Luận Văn |
| :---: | :--- | :--- | :--- | :--- |
| **1** | **Hungary Optimization** (Task 11.1) | Phân công thợ 1-1 tối ưu | Thời gian tính ($ms$), Tổng chi phí phân công | Tối ưu tuyệt đối $O(N^3)$, thời gian giải $< 5\text{ms}$ cho $N=20$ thợ |
| **2** | **Thuật toán Di truyền (GA)** (Task 11.2) | Phân công ca kíp đa mục tiêu | Makespan (giờ), Độ lệch chuẩn tải ($\sigma$), Vi phạm ràng buộc | Giảm $28.4\%$ độ lệch tải giữa các thợ, $0\%$ vi phạm chứng chỉ kỹ năng |
| **3** | **TSP Routing (2-Opt & Manhattan)** (Task 11.3) | Lộ trình tuần tra hiện trường | Quãng đường di chuyển ($m$), Lỗi xuyên tường | Rút ngắn $34.2\%$ quãng đường di chuyển, triệt tiêu $100\%$ lỗi đi xuyên tường |
| **4** | **Sliding Z-Score & Isolation Forest** (Task 11.4) | Phát hiện dị biệt rung/nhiệt | Precision, Recall, $F_1\text{-score}$ trên dữ liệu FEMTO | $F_1\text{-score} \ge 0.94$, phát hiện trôi dạt sớm $7 - 10$ ngày trước khi vỡ bi |
| **5** | **PyTorch LSTM Sequence RUL** (Task 11.5) | Dự đoán tuổi thọ còn lại | $R^2$, RMSE (ngày), Độ trễ CPU ($ms$) | $R^2 \ge 0.88$, $\text{RMSE} \le 7.0\text{ ngày}$, độ trễ suy diễn CPU $< 10\text{ms}$ |
| **6** | **Random Forest Regressor** (Task 11.6) | Dự báo ngân sách bảo trì | $R^2$, MAPE ($\%$), XAI Feature Importance | $R^2 \ge 0.83$, $\text{MAPE} \le 9.0\%$, Nhân tố số 1: Tần suất hỏng hóc lặp lại |
| **7** | **MobileFaceNet & Haversine** (Task 11.7) | Điểm danh chống gian lận | Độ chính xác khớp ($\%$), Sai số trắc địa ($m$) | Khớp chính xác $98.6\%$ ($\text{Sim} \ge 0.72$), sai số vị trí GPS $\le 5.0\text{m}$ |
| **8** | **Sentence-Transformers & RAG** (Task 11.9) | Tra cứu quy trình SOP & mã lỗi | Độ trễ token đầu ($ms$), Độ chính xác trích dẫn | Độ trễ token đầu $\le 800\text{ms}$, trích dẫn chính xác $100\%$ trang PDF gốc |

---

## 5. Quy Tắc Bảo Mật, Phân Quyền & Đa Khách Hàng (Security, RBAC & Multi-Tenant Rules)

- **Minh Họa Đa Khách Hàng Tuyệt Đối**:
  - Đăng nhập tài khoản `admin_tanthuan` chỉ nhìn thấy dàn máy móc cơ khí nặng và phụ tùng cơ khí.
  - Đăng nhập tài khoản `admin_pharma` chỉ thấy hệ thống phòng sạch và thiết bị y tế.
  - Đăng nhập tài khoản `admin_sandbox` để thực hiện các bài test phá hủy của Hội đồng mà không làm hỏng dữ liệu của 3 Tenant chính.
- **Minh Họa 3 Vai Trò Người Dùng (RBAC)**:
  - `admin`: Trình diễn quản trị hệ thống, nhật ký kiểm toán Audit Log và cấu hình đa khách hàng.
  - `maintenance_manager`: Trình diễn biểu đồ Dashboard KPI (10.2), Báo cáo xuất MinIO (10.3), Dự báo chi phí (11.6), và Stepper 8 bước đại tu (11.8).
  - `technician`: Trình diễn ứng dụng di động Flutter, nhận việc ngoại tuyến, điểm danh khuôn mặt và hỏi đáp RAG.

---

## 6. Kiến Trúc & Luồng Dữ Liệu Công Nghệ (Architecture & Data Flow)

```
┌────────────────────────────────────────────────────────────────────────┐
│            HẠ TẦNG DIỄN TẬP NGOẠI TUYẾN 100% AIR-GAPPED               │
│                                                                        │
│   ┌───────────────────────┐              ┌──────────────────────────┐  │
│   │ Web Management Portal │              │ Flutter Mobile App       │  │
│   │ • Dashboard KPIs 10.2 │              │ • GPS Geofencing (50m)   │  │
│   │ • Báo cáo MinIO 10.3  │              │ • MobileFaceNet Cục bộ   │  │
│   │ • Dự báo ngân sách RF │              │ • Offline SQLite FTS5    │  │
│   │ • Stepper HSM 8 bước  │              │ • Chatbot RAG Giọng nói  │  │
│   │ • Snapshot Restore    │              │ • Bảng điều khiển Demo   │  │
│   └───────────┬───────────┘              └────────────┬─────────────┘  │
│               │                                       │                │
│               └───────────────────┬───────────────────┘                │
│                                   │ HTTPS / REST / SSE Cục bộ          │
│                                   ▼                                    │
│   ┌─────────────────────────────────────────────────────────────────┐  │
│   │ Dịch Vụ Lõi Django 5 Backend                                    │  │
│   │ • Phân công tối ưu: Hungary (11.1) + Di truyền GA (11.2)        │  │
│   │ • Định tuyến thợ: TSP Manhattan 2-Opt (11.3)                    │  │
│   │ • Phát hiện dị biệt: Dynamic Z-score & Isolation Forest (11.4)  │  │
│   │ • Dự đoán RUL: PyTorch LSTM Sequence Inference (11.5)           │  │
│   │ • Dự báo chi phí: Scikit-Learn Random Forest (11.6)             │  │
│   │ • Đại tu lớn: Cây quyết định & HSM 8 bước (11.8)                │  │
│   │ • Trợ lý RAG: Sentence-Transformers + PGVector (11.9)           │  │
│   └──────────────────┬───────────────────────────────┬──────────────┘  │
│                      │                               │                 │
│                      ▼                               ▼                 │
│   ┌────────────────────────────────────┐ ┌───────────────────────────┐  │
│   │ Hạ Tầng Cục Bộ Trên Máy Host       │ │ Local Ollama Daemon       │  │
│   │ • PostgreSQL 16 + PGVector (HNSW)  │ │ • Model: llama3 / qwen    │  │
│   │ • Redis 7 (Pristine Flushed)       │ │ • Nhiệt độ tất định: 0.1  │  │
│   │ • MinIO S3 Object Storage          │ └───────────────────────────┘  │
│   └────────────────────────────────────┘                               │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Mô Hình Dữ Liệu & Thực Thể Dữ Liệu Mẫu (Demo Data Specifications)

### 7.1. Bốn Khách Hàng Công Nghiệp Mẫu (4 Distinct Tenants Bao Gồm Sandbox)

| Mã Tenant | Tên Doanh Nghiệp | Lĩnh Vực Vận Hành | Danh Mục Thiết Bị Tiêu Biểu | Đặc Trưng Cảm Biến & Kịch Bản |
| :--- | :--- | :--- | :--- | :--- |
| `TENANT_TANTHUAN` | Cơ Khí Chính Xác Tân Thuận | Công nghiệp nặng, gia công cơ khí | Máy phay CNC Makino, Máy nén khí Atlas Copco, Máy dập 500 tấn | Rung động vòng bi FEMTO chuỗi thoái hóa, phân công tối ưu GA/Hungary |
| `TENANT_PHARMA` | Dược Phẩm Sinh Học PharmaTech | Phòng sạch, thực phẩm vô trùng | Nồi hơi công nghiệp, Dây chuyền chiết rót, Bơm hút chân không | Rung nhiệt áp suất chuẩn ISO, kịch bản đại tu lớn HSM 8 bước, khóa LOTO |
| `TENANT_CAMPUS` | Đại Học Bách Khoa TP.HCM | Cơ sở vật chất trường học | Hệ thống điều hòa VRV, Thang máy chở khách, Bàn ghế giảng đường | Tài sản tĩnh bàn ghế, khấu hao 10.3, phân tuyến không định vị bản đồ 11.3 |
| `TENANT_SANDBOX` | Phân Xưởng Thử Tải Sandbox | Khu vực thử nghiệm phá hủy | Máy thử tải cực hạn, Kho âm, Thợ bận $100\%$ | Dành riêng cho Hội đồng thử nghiệm các ca biên, không ảnh hưởng 3 Tenant chính |

---

## 8. Đặc Tả Giao Diện Lập Trình (API Specifications & Contracts)

### Danh Mục Endpoints:

| Phương Thức | Đường Dẫn | Chức Năng |
| :--- | :--- | :--- |
| `POST` | `/api/v1/demo/trigger-scenario/` | Kích hoạt nhanh kịch bản diễn tập thuyết minh (Bơm rung độ, Fake GPS, Khóa LOTO) |
| `POST` | `/api/v1/demo/restore-snapshot/` | Khôi phục CSDL về trạng thái Snapshot ban đầu trong 1.5 giây |
| `GET` | `/api/v1/demo/academic-summary/` | Lấy bảng dữ liệu đối sánh khoa học của 8 thuật toán (hỗ trợ Dual-Seed) |

### Cấu Trúc Dữ Liệu Mẫu:

#### 1. Khôi phục Snapshot tức thì (`POST /api/v1/demo/restore-snapshot/`):
*Response `200 OK`*:
```json
{
  "success": true,
  "data": {
    "snapshotName": "pre_defense_baseline",
    "restoredAt": "2026-09-17T13:00:00Z",
    "durationMs": 1250,
    "status": "PRISTINE_READY",
    "message": "Đã khôi phục toàn bộ CSDL về trạng thái sạch ban đầu. Sẵn sàng cho phần thuyết minh tiếp theo!"
  }
}
```

#### 2. Kích hoạt nhanh sự cố bất thường (`POST /api/v1/demo/trigger-scenario/`):
*Payload Request*:
```json
{
  "scenario": "SIMULATE_ANOMALY_SPIKE",
  "assetId": "a1b2c3d4-e5f6-7890-abcd-1234567890ab",
  "metric": "vibration_rms",
  "injectedValue": 7.85
}
```

*Response `200 OK`*:
```json
{
  "success": true,
  "data": {
    "scenario": "SIMULATE_ANOMALY_SPIKE",
    "status": "APPLIED",
    "anomalyDetected": true,
    "zscore": 3.65,
    "lstmRulDays": 4.2,
    "riskTier": "CRITICAL",
    "draftWorkOrderId": "wo-2026-pm-0042",
    "realtimeAlertDispatched": true,
    "message": "Đã bơm rung độ dị biệt 7.85 mm/s. Task 11.4 bắt Z-score 3.65. Task 11.5 dự báo RUL còn 4.2 ngày. Đã tự động sinh bản thảo Work Order khẩn cấp!"
  }
}
```

---

## 9. Kịch Bản Khởi Động Tinh Khiết 1 Chạm (`run_defense_demo.bat`)

```bat
@echo off
chcp 65001 > nul
echo ========================================================
echo   EAM ENTERPRISE - BỘ KHỞI ĐỘNG BẢO VỆ ĐỒ ÁN TỐT NGHIỆP
echo ========================================================

echo [1/5] Dọn dẹp môi trường tinh khiết (Pristine State Flush)...
docker exec -it eam_redis redis-cli flushall > nul 2>&1
python manage.py clear_cache > nul 2>&1
if exist celerybeat-schedule del /f /q celerybeat-schedule > nul 2>&1

echo [2/5] Kiểm tra và khởi động các dịch vụ hạ tầng Docker...
docker-compose up -d postgres redis minio ollama

echo [3/5] Áp dụng Database Migrations...
python manage.py migrate

echo [4/5] Khởi tạo dữ liệu mẫu du hành thời gian 12 tháng...
python manage.py seed_defense_demo --clean

echo [5/5] Khởi chạy máy chủ Django EAM và mở trình duyệt...
start http://127.0.0.1:8000/admin/
python manage.py runserver 0.0.0.0:8000
```

---

## 10. Tiêu Chí Chấp Nhận & Ma Trận Kịch Bản Kiểm Thử (Acceptance Criteria & Test Scenarios)

### 10.1. Ma Trận 12 Kịch Bản Kiểm Thử Nghiệm Thu Bảo Vệ Luận Văn

| Mã Test | Tên Kịch Bản | Điều Kiện Thử Nghiệm | Hành Vi Kỳ Vọng | Trạng Thái |
| :--- | :--- | :--- | :--- | :--- |
| **TC-DEF-01** | Khởi tạo đơn công `--clean` & Time-Travel 12 tháng *(User Scen 2)* | Chạy lệnh `seed_defense_demo --clean` | Sinh đúng 4 Tenant, 1,000+ Work Order lịch sử, biểu đồ 10.3 và 11.6 đầy đặn số liệu | Chưa thực hiện |
| **TC-DEF-02** | Thử nghiệm hạt giống đôi: Seed 42 vs Live Random *(User Scen 3)* | Chạy benchmark với Seed=42 và Seed ngẫu nhiên | Seed 42 khớp sách 100%; Seed ngẫu nhiên hiển thị $\mu \pm \sigma$ nằm trong khoảng an toàn | Chưa thực hiện |
| **TC-DEF-03** | Vận hành ngoại tuyến $100\%$ không lỗi CDN | Rút toàn bộ cáp mạng LAN, tắt Wifi máy tính | Toàn bộ Web Portal, biểu đồ ECharts và bản đồ tải bình thường, $0\%$ lỗi CDN | Chưa thực hiện |
| **TC-DEF-04** | Bảng điều khiển diễn tập thuyết minh | Chạm 5 lần vào logo, ấn nút "Simulate Compliant Check-In" | Bỏ qua trở ngại phần cứng camera, tạo ngay log điểm danh hợp lệ để demo | Chưa thực hiện |
| **TC-DEF-05** | Khu vực Sandbox chịu tải cực đoan *(User Scen 1)* | Hội đồng yêu cầu chia việc khi toàn bộ thợ đang bận | Chuyển sang Tenant Sandbox, GA xử lý kích hoạt Thợ ảo và đẩy vào Backlog mượt mà | Chưa thực hiện |
| **TC-DEF-06** | Khôi phục Snapshot tức thì *(Snapshot Restore)* | Sau khi biểu diễn kịch bản phá hủy cháy máy | Bấm nút "Restore Snapshot", CSDL quay về trạng thái ban đầu trong $\le 1.5$ giây | Chưa thực hiện |
| **TC-DEF-07** | Dữ liệu tổng hợp tuân thủ Nghị định 13 *(User Scen 5)* | Kiểm tra toàn bộ khuôn mặt và bản đồ nhà máy | $100\%$ ảnh mặt AI sinh, bản đồ giả lập, ẩn danh doanh nghiệp tuân thủ pháp lý | Chưa thực hiện |
| **TC-DEF-08** | Dọn sạch môi trường Pristine State *(User Scen 4)* | Chạy lệnh khởi động demo `run_defense_demo.bat` | Tự động flushall Redis, dọn cache, xóa session cũ, đảm bảo môi trường tinh khiết | Chưa thực hiện |
| **TC-DEF-09** | Luồng liên hoàn từ bất thường đến RUL | Ấn nút kích nổ sự cố rung động $7.85\text{ mm/s}$ | Task 11.4 báo Z-score $3.65 \rightarrow$ Task 11.5 hạ RUL còn 4.2 ngày $\rightarrow$ Sinh Draft WO | Chưa thực hiện |
| **TC-DEF-10** | Phân lập dữ liệu đa khách hàng | Đăng nhập tài khoản Tenant Cơ khí Tân Thuận | Không nhìn thấy bất kỳ máy móc hoặc phụ tùng nào của Tenant Dược phẩm | Chưa thực hiện |
| **TC-DEF-11** | Trợ lý RAG ngoại tuyến với Ollama | Đặt câu hỏi SOP kỹ thuật khi ngắt Internet | Mô hình `llama3:8b` cục bộ trả lời bình thường kèm trích dẫn số trang tài liệu | Chưa thực hiện |
| **TC-DEF-12** | Khởi động 1 chạm tự động `run_defense_demo.bat` | Chạy tệp `.bat` trên máy tính mới | Tự kiểm tra hạ tầng, dọn dẹp, migrate, seed dữ liệu và mở trình duyệt sẵn sàng | Chưa thực hiện |

---

## 11. Implementation Notes — For Implementation Phase Only

> [!IMPORTANT]
> **REFERENCE ONLY — DO NOT IMPLEMENT OR MODIFY CODE BASED ON THIS SECTION DURING SPEC REVIEW. These notes are intended for the implementation phase after the specification is approved.**

Phần này lưu trữ các chỉ dẫn kỹ thuật hạ tầng chi tiết để các kỹ sư tham khảo trong quá trình triển khai mã nguồn:

### 11.1. Cài Đặt Hạt Giống Ngẫu Nhiên Toàn Cục (Python Reference)
```python
import os
import random
import numpy as np
import torch

def set_global_academic_seed(seed: int = 42):
    """Thiết lập hạt giống tất định trên toàn bộ các bộ sinh số ngẫu nhiên."""
    os.environ['PYTHONHASHSEED'] = str(seed)
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
```

### 11.2. Cấu Trúc Lệnh Khởi Tạo Dữ Liệu Đơn Công & Time-Travel
```python
from django.core.management.base import BaseCommand
from django.db import transaction

class Command(BaseCommand):
    help = "Khởi tạo dữ liệu mẫu thực tế du hành thời gian phục vụ bảo vệ đồ án tốt nghiệp."

    def add_arguments(self, parser):
        parser.add_argument('--clean', action='store_true', help='Xóa sạch dữ liệu demo cũ trước khi khởi tạo.')

    @transaction.atomic
    def handle(self, *args, **options):
        if options['clean']:
            self.stdout.write("Đang dọn dẹp dữ liệu cũ...")
            self.clean_demo_records()

        self.stdout.write("Đang khởi tạo 4 Tenant công nghiệp (bao gồm Sandbox)...")
        self.seed_tenants()
        self.stdout.write("Đang sinh dữ liệu du hành thời gian 12 tháng quá khứ...")
        self.seed_time_travel_history()
        self.stdout.write(self.style.SUCCESS("Khởi tạo dữ liệu bảo vệ đồ án thành công 100%!"))
```

---

## 12. Kế Hoạch Triển Khai & Nghiệm Thu (Implementation Checklist)

- [ ] **Task 12.1 — Master Demo Seeding Infrastructure & Time-Travel Generator**
  - [ ] Viết lệnh quản trị `seed_defense_demo` hỗ trợ cờ `--clean` và Pristine State Flush.
  - [ ] Xây dựng bộ sinh dữ liệu Du hành thời gian (Time-Travel) lùi 12 tháng (1,000+ Work Order, AuditLog).
  - [ ] Khởi tạo 4 Tenant mẫu (3 Miền công nghiệp + 1 Tenant Sandbox thử nghiệm phá hủy).
  - [ ] Bảo đảm $100\%$ dữ liệu tổng hợp (Synthetic Data) tuân thủ Nghị định 13 và bản quyền.
- [ ] **Task 12.2 — Quantitative Academic Benchmark Harness & Dual-Seed Engine**
  - [ ] Viết lệnh quản trị `run_academic_benchmarks` hỗ trợ chuyển đổi Academic Seed 42 vs Live Random Seed.
  - [ ] Đo lường phân phối dao động chuẩn ($\mu \pm \sigma$) cho 8 thuật toán cốt lõi.
  - [ ] Tự động xuất bảng báo cáo Markdown đối sánh các chỉ số khoa học.
- [ ] **Task 12.3 — Air-Gapped Offline Package & Presentation Demo Mode**
  - [ ] Đóng gói toàn bộ static assets vào `/static/vendor/` loại trừ $100\%$ CDN bên ngoài.
  - [ ] Tích hợp chế độ diễn tập bí mật (chạm 5 lần mở thanh điều khiển kịch bản).
  - [ ] Viết tệp kịch bản khởi động 1 chạm tự động `run_defense_demo.bat` dọn sạch Redis/Cache.
- [ ] **Task 12.4 — Defense Readiness & Instant Snapshot Restore**
  - [ ] Xây dựng API `POST /api/v1/demo/restore-snapshot/` khôi phục CSDL tức thì trong $\le 1.5$ giây.
  - [ ] Kiểm thử ngắt Internet toàn phần xác nhận hệ thống vận hành ngoại tuyến hoàn hảo $100\%$.
  - [ ] Diễn tập kịch bản thuyết minh từng phút khớp nối 8 thuật toán và 12 test cases (`TC-DEF-01` đến `TC-DEF-12`).

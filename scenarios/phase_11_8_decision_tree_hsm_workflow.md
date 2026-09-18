# Thiết Kế Hệ Thống & Đặc Tả Kỹ Thuật: Task 11.8 — Complex Maintenance Workflow & Facility Management (Decision Tree & HSM)

Tài liệu này xác định kiến trúc điều phối quy trình đại tu phức tạp và quản lý cụm chi tiết cơ sở vật chất chuyên sâu trong hệ thống Quản lý Tài sản Doanh nghiệp (EAM). Hệ thống giải quyết các giới hạn của máy trạng thái phẳng thông thường bằng việc kết hợp: mô hình học máy cây quyết định giải thích được (**Explainable Decision Tree Classifier**) với **vùng đệm cảnh báo giáp ranh (Marginal Boundary Warning)**, máy trạng thái phân cấp tuần tự 8 giai đoạn (**Hierarchical State Machine - HSM**), cơ chế tạm ngưng khóa điện an toàn sinh mạng phục vụ chạy thử (**LOTO Temporary Suspension & `TESTING_ENERGIZED`**), cơ chế **lùi bước linh hoạt đa giai đoạn (Flexible Multi-Stage Rollback)**, cơ chế **đóng băng đồng hồ đo thời gian tạm hoãn ngoại cảnh (`ON_HOLD` Clock-Paused SLA)**, thuật toán kiểm tra chu trình đồ thị (**DAG DFS Cycle Detection**) kết hợp **phân tích đường găng điểm nghẽn (Critical Path Method - CPM)**, điều kiện nghiệm thu phiếu cha dựa trên **tập trạng thái kết thúc (Terminal States Set)**, rào chắn **tập kết vật tư BOM & triệt tiêu năng lượng (Kitting & Zero-Energy Interlock)**, cầu nối **tái đồng bộ đường cơ sở sau đại tu (Post-Overhaul Baseline Reset Bridge to Task 11.4 & 11.5)**, danh mục cây cụm chi tiết thiết bị 4 tầng (**4-Tier Facility Component Catalog**), và **chuỗi băm kiểm toán bất biến (Cryptographic Audit Hash Chain)**.

Tài liệu đóng vai trò là **Đặc Tả Kỹ Thuật & Chuẩn Kiểm Thử (Technical Specification & Audit Baseline)** nhằm đối chiếu, rà soát và thực thi trọn vẹn toàn bộ tính năng theo chuẩn đề cương tốt nghiệp đại học mà không bị thiếu sót bất kỳ nghiệp vụ enterprise nào.

---

## 1. Mục Tiêu & Phạm Vi (Objective & Scope)

### 1.1. Bản Chất Nghiệp Vụ Của Quy Trình Đại Tu Phức Tạp (Major Overhaul)
Trong bảo trì công nghiệp nặng, sửa chữa một sự cố nhỏ (thay cầu chì, vặn ốc, châm dầu) chỉ cần máy trạng thái phẳng 1 tầng (`CREATED` $\rightarrow$ `ASSIGNED` $\rightarrow$ `IN_PROGRESS` $\rightarrow$ `COMPLETED`). Tuy nhiên, đối với một sự cố đại tu lớn (cháy cuộn dây stator máy phát 500kW, vỡ hộp số máy cán thép, nứt cánh tuabin, hỏng cụm nén khí trục vít):
- **Thời gian dừng máy kéo dài hàng tuần**, chi phí phụ tùng và nhân công lên tới hàng trăm triệu hoặc hàng tỷ đồng.
- **Phối hợp liên phòng ban phức tạp**: Chẩn đoán nội soi $\rightarrow$ Tập kết vật tư nhập khẩu $\rightarrow$ Cắt điện/xả áp cô lập an toàn $\rightarrow$ Tháo rã & gia công cơ khí $\rightarrow$ Lắp ráp & căn tâm laser $\rightarrow$ Chạy thử không tải $\rightarrow$ Chạy thử có tải nghiệm thu.
- **Rủi ro chí mạng**: Nếu bỏ qua các bước kiểm tra an toàn hoặc cho phép thợ nhảy cóc quy trình, máy khởi động lại có thể phát nổ, gãy trục hoặc phóng điện gây tai nạn lao động nghiêm trọng.

### 1.2. Vai Trò Của Bộ Đôi Cây Quyết Định (Decision Tree) & HSM
- **Cây quyết định (Decision Tree Classifier)**: Tự động đánh giá các tham số sự cố đầu vào (thời gian dừng máy ước tính, nguy cơ an toàn, tỷ lệ chi phí, độ rung dị biệt) để phân loại sự cố vào 4 cấp độ nghiêm trọng minh bạch $100\%$ (White-box AI) kèm vùng đệm phân ngưỡng an toàn.
- **Máy trạng thái phân cấp (HSM)**: Khi sự cố thuộc Cấp 4 (`CRITICAL_OVERHAUL`), hệ thống tự động kích hoạt quy trình tuần tự 8 giai đoạn nghiêm ngặt, điều phối khóa an toàn LOTO linh hoạt, kiểm soát công việc con đa chuyên môn bằng đồ thị DAG, và quản lý các tình huống tạm ngưng/lùi bước thực tế tại hiện trường.

---

## 2. Ràng Buộc Kế Thừa Hệ Thống (Existing System Constraints & Codebase Reuse)

- **Tái Sử Dụng Mô Hình Multi-Tenancy**: Mọi dữ liệu phân cấp cơ sở vật chất, liên kết phụ thuộc công việc và nhật ký nghiệm thu kế thừa `BaseTenantModel`, bảo đảm phân lập hoàn toàn giữa các Tenant qua `TenantManager`.
- **Tái Sử Dụng Thực Thể Nghiệp Vụ Có Sẵn**:
  - `WorkOrder`: Mở rộng các trường phân cấp sự cố (`severity_level`, `marginal_boundary_warning`), giai đoạn HSM (`current_hsm_stage`, `hsm_status`), trạng thái tạm hoãn (`is_on_hold`, `hold_accumulated_seconds`), và chuỗi băm kiểm toán (`audit_hash_chain`).
  - `Asset`: Khóa trạng thái an toàn `LOCKED_SAFETY_LOTO` hoặc chuyển tạm thời sang `TESTING_ENERGIZED` trong suốt các giai đoạn đại tu.
  - `AuditLog`: Lưu vết kiểm toán toàn bộ các thao tác ghi đè cấp độ nghiêm trọng, lùi bước giai đoạn, cấp điện tạm và biên bản nghiệm thu.
- **Giao Dịch Nguyên Khối (Atomic Transactions)**: Mọi thao tác chuyển giai đoạn HSM, lùi bước linh hoạt và cập nhật khóa an toàn phải nằm trong khối `transaction.atomic()` của Django để tránh tình trạng dữ liệu dở dang khi xảy ra sự cố mạng.

---

## 3. Yêu Cầu Nghiệp Vụ & 10 Quy Tắc Cốt Lõi (Business Requirements & Core Rules)

Toàn bộ quy trình đại tu phức tạp và phân cấp sự cố phải tuân thủ nghiêm ngặt 10 quy tắc phòng thủ sau:

### Quy Tắc 1: Cây Quyết Định Giải Thích Được & Vùng Đệm Cảnh Báo Giáp Ranh (Explainable Decision Tree & Marginal Boundary Warning)
- **Điểm Yếu Nghiệp Vụ (Decision Tree Cliff Effect)**: Cây quyết định có các ngưỡng chia cắt cứng (Hard Splits). Ví dụ: Tỷ lệ chi phí $> 20\%$ phân loại Cấp 4 (Đại tu 8 bước), $\le 20\%$ phân loại Cấp 3 (Sửa chữa khẩn). Nếu một sự cố có tỷ lệ chi phí là $19.99\%$, AI tự động xếp vào Cấp 3 và bỏ qua toàn bộ quy trình kiểm định LOTO/Rung động nghiêm ngặt, tạo ra rủi ro cực lớn dù tính chất sự cố gần như tương đương Cấp 4.
- **Quy Tắc Bắt Buộc**:
  1. Sử dụng mô hình `DecisionTreeClassifier` với tiêu chuẩn Gini Impurity, khống chế độ sâu tối đa `max_depth <= 4` để trích xuất $100\%$ logic dưới dạng luật IF-THEN rõ ràng:
     $$I_G(t) = 1 - \sum_{i=1}^{4} p(i|t)^2$$
  2. Phân loại sự cố vào đúng 4 cấp độ:
     - **Cấp 1 (`LEVEL_1_MINOR`)**: Dừng máy $< 2\text{h}$, chi phí $< 2\%$ nguyên giá $\rightarrow$ Quy trình phẳng thông thường.
     - **Cấp 2 (`LEVEL_2_MEDIUM`)**: Thay linh kiện phổ thông, dừng máy $2 - 8\text{h}$, phụ tùng sẵn trong kho $\rightarrow$ Quy trình phẳng kèm cấp phát kho.
     - **Cấp 3 (`LEVEL_3_SEVERE`)**: Sự cố dừng chuyền đột xuất $\rightarrow$ Kích hoạt điều phối ưu tiên qua TSP ([Task 11.3](file:///d:/GameLinkNeverDie/eam-enterprise-assset-management/scenarios/phase_11_3_tsp_technician_routing.md)).
     - **Cấp 4 (`LEVEL_4_CRITICAL_OVERHAUL`)**: Hư hỏng kết cấu nặng, dừng máy $> 8\text{h}$, chi phí $> 20\%$ nguyên giá $\rightarrow$ **Kích hoạt Máy Trạng Thái HSM 8 Giai Đoạn**.
  3. **Vùng đệm cảnh báo giáp ranh (Fuzzy/Margin Zone)**:
     - Tại các ngưỡng quyết định cốt lõi (Chi phí $20\%$, Dừng máy $8\text{h}$, Z-score $3.0$), áp dụng vùng đệm an toàn $\pm 5\%$ giá trị ngưỡng (ví dụ: Tỷ lệ chi phí từ $19.0\%$ đến $21.0\%$).
     - Nếu đặc trưng rơi vào vùng đệm này, API trả về phân loại kèm cờ `marginal_boundary_warning = True`.
     - Giao diện người dùng bắt buộc bôi vàng kết quả cảnh báo và ép buộc Quản đốc phân xưởng phải review thủ công (**Human-in-the-loop**) để quyết định có nâng lên Cấp 4 hay không.

### Quy Tắc 2: Quyền Can Thiệp Ghi Đè & Lùi Bước Linh Hoạt Đa Giai Đoạn (Human Override & Flexible Multi-Stage Rollback)
- **Điểm Yếu Nghiệp Vụ (Rigid Rollback Blindspot)**: Tại Giai đoạn 6 (Chạy thử), độ rung vượt $4.5\text{ mm/s}$. Nếu hệ thống chỉ cho phép lùi về đúng 1 bước trước đó ($k \rightarrow k-1$, tức Giai đoạn 5 - Lắp ráp), nhưng nguyên nhân rung thực tế là do chi tiết gia công ở Giai đoạn 4 bị lỗi móp méo, hoặc phụ tùng mua ở Giai đoạn 2 bị sai quy cách. Việc lùi về Giai đoạn 5 không giải quyết được gốc rễ và tạo ra vòng lặp vô tận ($5 \leftrightarrow 6$).
- **Quy Tắc Bắt Buộc**:
  1. Kết quả từ Cây quyết định chỉ đóng vai trò khuyến nghị kỹ thuật (`suggested_severity`). Quản đốc có quyền ghi đè (`manual_severity`) kèm lý do kỹ thuật (`override_reason`) bắt buộc $\ge 20$ ký tự, lưu vết vĩnh viễn vào `AuditLog`.
  2. **Cơ chế Lùi bước linh hoạt (Flexible Multi-Stage Rollback)**:
     - Cho phép Kỹ sư trưởng hoặc Quản đốc chọn lùi Work Order về **bất kỳ giai đoạn nào trước đó** ($m < k$, ví dụ lùi thẳng từ Giai đoạn 6 về Giai đoạn 2 hoặc 4).
     - Hệ thống yêu cầu nhập lý do kỹ thuật lùi bước (`rollback_reason`) $\ge 20$ ký tự.
     - Hệ thống tự động thực hiện **Cascade Reset**: Thu hồi toàn bộ chữ ký nghiệm thu và đưa trạng thái của tất cả các giai đoạn trung gian từ $m$ đến $k$ về `PENDING_REEXECUTION`.

### Quy Tắc 3: Máy Trạng Thái HSM 8 Giai Đoạn & Cơ Chế Đóng Băng Đồng Hồ `ON_HOLD` (Strict 8-Stage Stepper & `ON_HOLD` Clock-Paused SLA)
- **Điểm Yếu Nghiệp Vụ (External Hold/Suspension)**: Tại Giai đoạn 2 (Chuẩn bị vật tư), nhà cung cấp báo phụ tùng nhập khẩu phải mất 3 tháng mới cập cảng. Nếu để Work Order nằm im ở Giai đoạn 2, hệ thống đo lường hiệu suất (SLA) sẽ ghi nhận thời gian xử lý sự cố (MTTR) tăng vọt lên hàng nghìn giờ, phá hỏng KPI của đội bảo trì dù lỗi hoàn toàn do ngoại cảnh.
- **Quy Tắc Bắt Buộc**:
  1. Quy trình đại tu Cấp 4 bắt buộc trải qua 8 giai đoạn tuần tự (chống nhảy cóc $k \rightarrow k+2$):
     - **Giai đoạn 1 (`DIAGNOSIS_SURVEY`)**: Khảo sát nội soi, đo phổ rung chẩn đoán, ký duyệt phương án kỹ thuật.
     - **Giai đoạn 2 (`PART_PROCUREMENT`)**: Đặt hàng & kiểm đếm tập kết $100\%$ phụ tùng tại Staging Area.
     - **Giai đoạn 3 (`LOTO_DISASSEMBLY`)**: Triệt tiêu năng lượng, khóa an toàn LOTO, tháo rã máy.
     - **Giai đoạn 4 (`REPAIR_FABRICATION`)**: Gia công cơ khí chính xác, hàn đắp phục hồi kết cấu.
     - **Giai đoạn 5 (`REASSEMBLY_ALIGN`)**: Lắp ráp cơ khí và căn tâm laser đồng trục (độ lệch $\le 0.05\text{ mm/m}$).
     - **Giai đoạn 6 (`NO_LOAD_TRIAL`)**: Chạy thử không tải liên tục 4 giờ, đo rung động kiểm tra.
     - **Giai đoạn 7 (`LOAD_ACCEPTANCE`)**: Chạy thử có tải sản xuất, ký biên bản nghiệm thu chất lượng.
     - **Giai đoạn 8 (`COMMISSIONED_DONE`)**: Giải phóng khóa an toàn LOTO, bàn giao máy vận hành.
  2. **Trạng thái treo ngoại cảnh (`ON_HOLD`)**:
     - Cho phép kích hoạt trạng thái `ON_HOLD` ở bất kỳ giai đoạn nào khi gặp trở ngại khách quan.
     - Bắt buộc chọn mã lý do chuẩn hóa: `WAITING_FOR_PARTS`, `WAITING_FOR_VENDOR`, `WAITING_BUDGET_APPROVAL`, `FORCE_MAJEURE` kèm văn bản minh chứng.
     - **Cơ chế đóng băng đồng hồ (Clock-Paused)**: Toàn bộ thời gian nằm ở trạng thái `ON_HOLD` được tích lũy vào `hold_accumulated_seconds` và **tự động trừ ra** khỏi tổng thời gian giải quyết sự cố khi tính toán chỉ số MTTR và tuân thủ SLA tại Báo cáo phân hệ [Task 10.2](file:///d:/GameLinkNeverDie/eam-enterprise-assset-management/scenarios/phase_10_2_dashboard_kpi_analytics.md) & [Task 10.3](file:///d:/GameLinkNeverDie/eam-enterprise-assset-management/scenarios/phase_10_3_reports_export_engine.md).

### Quy Tắc 4: Rào Chắn Kiểm Thử Tải & Rung Động ISO 10816 Khi Chạy Thử (No-Load Vibration ISO 10816 Guardrail)
- **Điểm Yếu Nghiệp Vụ**: Máy sau khi lắp ráp lại bị lệch trục hoặc rơ lỏng bu-lông chân đế nhưng thợ vẫn ký biên bản nghiệm thu để ép tiến độ sản xuất, dẫn đến việc gãy trục hoặc vỡ vòng bi ngay sau vài ngày.
- **Quy Tắc Bắt Buộc**:
  1. Khi chuyển từ Giai đoạn 6 (`NO_LOAD_TRIAL`) sang Giai đoạn 7 (`LOAD_ACCEPTANCE`), kỹ thuật viên bắt buộc phải nhập số đo độ rung hiệu dụng RMS ($v_{\text{rms}}$) của 4 giờ chạy thử không tải.
  2. Đối chiếu nghiêm ngặt tiêu chuẩn rung động quốc tế ISO 10816-3 (Nhóm máy công nghiệp Class II/III):
     $$v_{\text{rms\_trial}} \le 4.5\text{ mm/s}$$
  3. Nếu $v_{\text{rms}} > 4.5\text{ mm/s}$, hệ thống **khóa cứng không cho chuyển tiếp**, yêu cầu kích hoạt cơ chế lùi bước (Rollback) về Giai đoạn 5 để căn tâm lại hoặc về Giai đoạn 4/2 để kiểm tra khuyết tật sâu hơn.

### Quy Tắc 5: Khóa An Toàn Sinh Mạng LOTO & Tạm Cấp Điện Kiểm Thử (LOTO Life-Safety Interlock & `TESTING_ENERGIZED` Suspension)
- **Điểm Yếu Nghiệp Vụ (The LOTO / Trial-Run Contradiction)**: Máy bị khóa cách ly điện LOTO ở Giai đoạn 3 và chỉ được gỡ ở Giai đoạn 8. Tuy nhiên, tại Giai đoạn 6 (Chạy thử không tải) và Giai đoạn 7 (Chạy thử có tải), thiết bị bắt buộc phải được cấp điện và cấp nguyên liệu để động cơ quay. Nếu LOTO vẫn khóa cứng, máy không thể chạy thử; nếu thợ tự ý bẻ khóa LOTO, họ vi phạm nghiêm trọng quy chuẩn an toàn sinh mạng.
- **Quy Tắc Bắt Buộc**:
  1. Khi Work Order bước vào Giai đoạn 3 (`LOTO_DISASSEMBLY`), thiết bị tự động chuyển sang trạng thái:
     $$\text{Asset.status} = \text{'LOCKED\_SAFETY\_LOTO'}$$
     Hệ thống từ chối mọi thao tác vận hành hoặc tạo phiếu bảo dưỡng mới trên thiết bị; hiển thị banner đỏ cảnh báo nguy hiểm trên toàn hệ thống.
  2. **Cơ chế Tạm ngưng LOTO phục vụ kiểm thử (`TESTING_ENERGIZED`)**:
     - Trước khi khởi động chạy thử ở Giai đoạn 6, hệ thống yêu cầu Cán bộ An toàn (Safety Officer) ký số phê duyệt lệnh **Tạm cấp nguồn kiểm thử (Temporary Energization Permit)**.
     - Trạng thái thiết bị chuyển sang `TESTING_ENERGIZED`: Cho phép đóng điện tạm thời dưới sự giám sát độc quyền của đội chạy thử, banner đổi sang màu cam cảnh báo thử tải.
  3. **Ràng buộc sau chạy thử**:
     - Nếu chạy thử thất bại (rung chấn cao, rò rỉ), hệ thống tự động tái kích hoạt khóa an toàn `LOCKED_SAFETY_LOTO` trước khi cho phép thợ chạm tay vào sửa chữa tiếp.
     - Trạng thái khóa LOTO chỉ được giải phóng vĩnh viễn khi đạt Giai đoạn 8 (`COMMISSIONED_DONE`) với đầy đủ biên bản bàn giao có chữ ký số của Cán bộ an toàn.

### Quy Tắc 6: Đồ Thị Công Việc Con (DAG), Kiểm Tra Chu Trình DFS & Đường Găng CPM (DAG Sub-Tasks, DFS Cycle Detection & CPM Bottlenecks)
- **Điểm Yếu Nghiệp Vụ**: Đại tu lớn chia thành 20-50 công việc con cho nhiều tổ chuyên môn (Điện, Cơ khí, Tự động hóa). Tổ Cơ chờ tổ Điện xong mới lắp vỏ, nhưng tổ Điện lại chờ tổ Cơ căn chỉnh mới đấu dây $\rightarrow$ Khóa chết chu trình (Deadlock). Đồng thời, Quản đốc không biết công việc nào là "nút thắt" quyết định tiến độ, dẫn đến việc thợ làm các việc rảnh tay trong khi việc quyết định tiến độ bị trễ.
- **Quy Tắc Bắt Buộc**:
  1. Mạng lưới phụ thuộc giữa các công việc con bắt buộc tạo thành Đồ thị có hướng không chu trình (DAG).
  2. Trước khi lưu bất kỳ liên kết phụ thuộc nào (`task_A depends_on task_B`), hệ thống bắt buộc chạy thuật toán duyệt theo chiều sâu DFS với đánh dấu 3 màu (0: Chưa thăm, 1: Đang thăm, 2: Đã xong):
     $$\text{detect\_dag\_cycle(graph, start\_node)} \rightarrow \text{Boolean}$$
     Nếu phát hiện cạnh quay lui (Back-edge), hủy lệnh lập tức với mã lỗi `400 Bad Request (DAG_CIRCULAR_DEPENDENCY_DETECTED)` kèm đường dẫn chi tiết của chu trình lặp.
  3. **Phân tích Đường găng (Critical Path Method - CPM)**:
     - Tự động tính toán: $\text{Early Start (ES)}$, $\text{Early Finish (EF)}$, $\text{Late Start (LS)}$, $\text{Late Finish (LF)}$.
     - Xác định độ dự trữ thời gian: $\text{Float} = \text{LS} - \text{ES}$.
     - Các công việc có $\text{Float} = 0$ được gắn nhãn `is_critical_path = True` và viền đỏ trên giao diện, cảnh báo đây là chuỗi công việc quyết định ngày nghiệm thu toàn bộ dự án đại tu.

### Quy Tắc 7: Rào Chắn Nghiệm Thu Phiếu Cha Dựa Trên Tập Trạng Thái Kết Thúc (Hierarchical Parent WO Terminal States Guardrail)
- **Điểm Yếu Nghiệp Vụ (Child-Task Terminal State Trap)**: Quy tắc cứng nhắc yêu cầu tất cả phiếu con phải `COMPLETED` thì phiếu cha mới được đóng. Nhưng trong thực tế hiện trường, có những việc con thợ phát hiện không cần thiết nên xin Hủy (`CANCELLED`), hoặc phụ tùng cũ không thể phục hồi nên đánh dấu Bỏ qua/Loại bỏ (`SKIPPED` / `REJECTED`). Nếu hệ thống chỉ chấp nhận chữ `COMPLETED`, phiếu cha sẽ bị treo vĩnh viễn không thể nghiệm thu.
- **Quy Tắc Bắt Buộc**:
  1. Điều kiện nghiệm thu phiếu đại tu cha (`Parent Work Order`) không phải là kiểm tra `status == 'COMPLETED'`, mà là kiểm tra tất cả phiếu con phải nằm trong **Tập trạng thái kết thúc (Terminal States)**:
     $$\forall s \in \text{WorkOrder.sub\_tasks}, \quad s.\text{status} \in \{\text{'COMPLETED'}, \text{'CANCELLED'}, \text{'SKIPPED'}, \text{'REJECTED'}\}$$
  2. Bất kỳ công việc con nào còn ở trạng thái đang xử lý (`PENDING`, `IN_PROGRESS`, `ON_HOLD`) sẽ chặn đứng việc nghiệm thu phiếu cha với thông báo lỗi: `ACTIVE_SUB_TASKS_REMAINING`.
  3. Đối với các phiếu con ở trạng thái `CANCELLED` hoặc `SKIPPED`, hệ thống bắt buộc phải có lý do kỹ thuật phê duyệt từ Quản đốc để đảm bảo không bị bỏ sót hạng mục an toàn.

### Quy Tắc 8: Rào Chắn Tập Kết Vật Tư BOM & Triệt Tiêu Năng Lượng Trước Tháo Rã (Stage 2 Kitting Gate & Zero Energy State Interlock)
- **Điểm Yếu Nghiệp Vụ**: Thợ vội vàng chuyển từ Giai đoạn 2 sang Giai đoạn 3 để tháo tung máy khi vật tư mới chỉ "đặt hàng trên giấy" (PO pending). Khi máy đã bị rã thành từng mảnh, phát hiện phụ tùng giao sai quy cách, máy phải nằm trơ khung phơi mưa nắng hàng tháng trời. Ngoài ra, thợ chỉ cắt cầu dao điện mà không xả áp suất dư hoặc thông khí độc trong buồng máy, gây nguy cơ nổ áp lực hoặc ngạt khí khi tháo nắp.
- **Quy Tắc Bắt Buộc**:
  1. **Rào chắn Tập kết Vật tư (Stage 2 Physical Kitting Gate)**:
     - Điều kiện chuyển từ Giai đoạn 2 $\rightarrow$ Giai đoạn 3: $100\%$ danh mục phụ tùng trong BOM đại tu phải ở trạng thái `IN_STOCK_RESERVED` tại Khu vực tập kết (Staging Area).
     - Thủ kho bắt buộc quét mã QR kiểm đếm vật tư thực tế và ký số xác nhận (`kitting_verified_by`). Thiếu dù chỉ 1 phụ tùng trọng yếu, HSM **khóa cứng không cho chuyển sang Giai đoạn 3**.
  2. **Kiểm định Trạng thái Năng lượng Triệt tiêu (Zero Energy State Interlock)**:
     - Trước khi cấp quyền tháo máy ở Giai đoạn 3, hệ thống bắt buộc xác nhận an toàn môi trường:
       - Áp suất dư cơ học: $P_{\text{gauge}} = 0\text{ bar}$ (kèm van xả đáy đã khóa chốt cơ khí).
       - Nồng độ khí độc/khí cháy (Gas Clearance Test): $C_{\text{toxic}} \le \text{PEL}$ đối với thiết bị hóa chất/áp lực, có chữ ký xác nhận của Cán bộ an toàn.

### Quy Tắc 9: Cầu Nối Tái Đồng Bộ Baseline Sau Đại Tu Cho Giám Sát Cảm Biến & RUL (Post-Overhaul Baseline Reset Bridge to Task 11.4 & 11.5)
- **Điểm Yếu Nghiệp Vụ**: Khi máy hoàn tất đại tu (Giai đoạn 8), tất cả vòng bi, bánh răng đã được thay mới, động cơ được quấn lại hoàn hảo. Nhưng mô hình phát hiện dị biệt Sensor ([Task 11.4](file:///d:/GameLinkNeverDie/eam-enterprise-assset-management/scenarios/phase_11_4_sensor_anomaly_detection.md)) và mô hình dự đoán RUL ([Task 11.5](file:///d:/GameLinkNeverDie/eam-enterprise-assset-management/scenarios/phase_11_5_lstm_predictive_maintenance_rul.md)) vẫn đang lưu lịch sử rung chấn và dữ liệu suy thoái cũ. Kết quả: AI liên tục báo động giả hoặc dự báo RUL còn vài ngày ngay khi máy vừa xuất xưởng đại tu.
- **Quy Tắc Bắt Buộc**:
  1. Ngay khi Work Order chuyển sang `COMMISSIONED_DONE` (Giai đoạn 8), hệ thống tự động phát tín hiệu Webhook/Event nội bộ để tái đồng bộ toàn bộ pipeline AI:
     - **Reset Baseline Task 11.4**: Xóa bộ đệm cửa sổ trượt (Sliding Window Dynamic Z-score), tính toán lại đường cơ sở rung động chuẩn (Baseline Profile) từ số đo đo đạc 4 giờ chạy thử nghiệm thu.
     - **Reset Degradation Cycle Task 11.5**: Đưa chu kỳ suy thoái về chu kỳ 0, ghim tuổi thọ còn lại RUL về mức tối đa ($RUL = 125\text{ ngày}$), xóa bỏ các cảnh báo thoái hóa cũ.

### Quy Tắc 10: Cây Cụm Chi Tiết 4 Tầng, Cô Lập Đa Tiền Thuê & Chuỗi Băm Kiểm Toán (4-Tier Facility Hierarchy, Multi-Tenancy & Cryptographic Audit Hash)
- **Điểm Yếu Nghiệp Vụ**: Quản lý thiết bị chung chung "Hỏng máy nén khí" khiến thợ không rõ bộ phận nào hỏng; truy vấn dữ liệu bị lẫn lộn giữa các Tenant; khi xảy ra sự cố tai nạn lao động nghiêm trọng, các bên đổ lỗi cho nhau và can thiệp database để xóa dấu vết chuyển bước hoặc cấp điện chạy thử.
- **Quy Tắc Bắt Buộc**:
  1. Quản lý cấu trúc cơ sở vật chất theo phả hệ 4 tầng chuẩn mực:
     $$\text{Nhà Máy (Facility)} \longrightarrow \text{Hệ Thống (System)} \longrightarrow \text{Tài Sản (Asset)} \longrightarrow \text{Cụm Chi Tiết (Component)}$$
  2. Mọi truy vấn trên bảng `facility_components` và `work_order_dependencies` đều bắt buộc lọc qua `tenant_id`.
  3. **Chuỗi băm kiểm toán bất biến (Cryptographic Audit Hash Chain)**:
     - Mỗi thao tác chuyển giai đoạn HSM, cấp điện tạm thời (`TESTING_ENERGIZED`), ghi đè quyết định hoặc lùi bước (Rollback) đều được băm nối chuỗi bất biến:
       $$\text{Hash}_k = \text{SHA-256}(\text{TenantID} \,\|\, \text{WorkOrderID} \,\|\, \text{Stage}_k \,\|\, \text{Action} \,\|\, \text{SignerID} \,\|\, \text{Timestamp} \,\|\, \text{Hash}_{k-1})$$
     - Đảm bảo dữ liệu kiểm toán minh bạch $100\%$, chống chối bỏ trách nhiệm trước đoàn thanh tra an toàn lao động.

---

## 4. Yêu Cầu Chức Năng & Luồng Xử Lý (Functional Requirements & Workflows)

### 4.1. Luồng Vận Hành Toàn Diện Quy Trình Đại Tu (Overhaul Lifecycle Flow)

```
[Báo Cáo Sự Cố Đột Xuất] (Downtime, Nguy cơ an toàn, Tỷ lệ chi phí, Rung độ Z-score)
       │
       ▼
[Mô Hình Cây Quyết Định (Decision Tree - Gini max_depth=4)]
       │
       ├── Rơi vào Vùng đệm giáp ranh (±5% Ngưỡng) ──► Cờ MARGINAL_BOUNDARY_WARNING (Bôi vàng UI)
       │                                                └── Ép buộc Quản đốc Review (Human-in-the-loop)
       ├── Cấp 1-3 ──► Chuyển tiếp Quy trình phẳng / Điều phối TSP khẩn cấp (11.3)
       │
       └── Cấp 4 (CRITICAL_OVERHAUL) ──► Kích hoạt Máy Trạng Thái HSM 8 Giai Đoạn
              │
              ├── [Trạng thái ON_HOLD]: Cho phép tạm hoãn ngoại cảnh ở mọi bước (Đóng băng đồng hồ SLA)
              │
              ▼
       [Giai đoạn 1: DIAGNOSIS_SURVEY] ──► Nội soi, đo rung, phê duyệt phương án kỹ thuật
              │
              ▼
       [Giai đoạn 2: PART_PROCUREMENT] ──► Đặt hàng phụ tùng
              │                             └── [RÀO CHẮN STAGE 2]: 100% BOM tập kết tại Staging Area
              ▼
       [Giai đoạn 3: LOTO_DISASSEMBLY] ──► [Zero-Energy]: P = 0 bar, Khí độc <= PEL
              │                             Khóa an toàn LOCKED_SAFETY_LOTO
              │                             Giải phóng DAG công việc con (DFS kiểm tra chu trình + CPM)
              ▼
       [Giai đoạn 4: REPAIR_FABRICATION] ──► Gia công cơ khí chính xác, hàn đắp phục hồi
              │
              ▼
       [Giai đoạn 5: REASSEMBLY_ALIGN] ──► Lắp ráp & căn tâm laser (Độ lệch <= 0.05 mm/m)
              │
              ▼
       [Giai đoạn 6: NO_LOAD_TRIAL] ◄──────┐ [LOTO TẠM NGƯNG]: Cán bộ an toàn ký lệnh Tạm cấp nguồn
              │                            │ Chuyển sang trạng thái TESTING_ENERGIZED
              │                            │ Chạy thử 4h đo độ rung RMS
              ├── v_rms > 4.5 mm/s ────────┴──► [LÙI BƯỚC LINH HOẠT]: Tái khóa LOTO, lùi về Giai đoạn 5, 4 hoặc 2
              ▼ v_rms <= 4.5 mm/s
       [Giai đoạn 7: LOAD_ACCEPTANCE] ──► Chạy thử có tải sản xuất
              │                             Điều kiện: Tất cả việc con thuộc TERMINAL_STATES
              │                             Ký duyệt kép: Quản đốc + Cán bộ an toàn
              ▼
       [Giai đoạn 8: COMMISSIONED_DONE] ──► Giải phóng khóa an toàn LOTO vĩnh viễn
                                             Máy trở lại OPERATIONAL
                                             └── [EVENT/WEBHOOK TÁI ĐỒNG BỘ]:
                                                   • Reset Baseline cửa sổ trượt (Task 11.4)
                                                   • Reset Degradation Cycle & Ghim RUL = 125 ngày (Task 11.5)
```

---

## 5. Quy Tắc Bảo Mật, Phân Quyền & Đa Khách Hàng (Security, RBAC & Multi-Tenant Rules)

- **Cô Lập Đa Khách Hàng (Multi-Tenancy)**: Toàn bộ bảng `facility_components`, `work_order_dependencies`, `hsm_stage_transitions` được cách ly tuyệt đối theo `tenant_id`.
- **Ma Trận Phân Quyền Theo Vai Trò (RBAC)**:
  - `TECHNICIAN`: Cập nhật tiến độ việc con, đóng/hủy việc con, nhập số đo rung $v_{\text{rms}}$ lúc chạy thử.
  - `WAREHOUSE_KEEPER`: Quét QR nghiệm thu tập kết phụ tùng thực tế tại Staging Area (Mở rào chắn Giai đoạn 2).
  - `SAFETY_OFFICER`: Kiểm tra Zero-Energy khí độc/áp suất, kích hoạt khóa LOTO, ký phê duyệt cấp điện tạm `TESTING_ENERGIZED`, ký giải phóng LOTO khi bàn giao máy.
  - `MAINTENANCE_MANAGER`: Quyền ghi đè cấp độ AI khi có cờ `MARGINAL_BOUNDARY_WARNING`, phê duyệt lệnh tạm hoãn `ON_HOLD`, ra quyết định lùi bước linh hoạt (Rollback), và ký duyệt kép nghiệm thu tải.

---

## 6. Kiến Trúc & Luồng Dữ Liệu Công Nghệ (Architecture & Data Flow)

```
┌────────────────────────────────────────────────────────────────────────┐
│                          BÁO CÁO SỰ CỐ HIỆN TRƯỜNG                     │
│  (Asset ID, Dự kiến dừng máy, Nguy cơ an toàn, Tỷ lệ chi phí, Z-score) │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   DỊCH VỤ CÂY QUYẾT ĐỊNH (DECISION TREE)               │
│  • Phân nhánh theo tiêu chuẩn Gini (max_depth <= 4)                    │
│  • Trích xuất chuỗi giải thích IF-THEN rõ ràng                         │
│  • Kiểm tra vùng đệm giáp ranh: Gắn cờ MARGINAL_BOUNDARY_WARNING       │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                 ĐỘNG CƠ MÁY TRẠNG THÁI PHÂN CẤP (HSM ENGINE)           │
│  • Điều phối tuần tự 8 giai đoạn đại tu (Chặn nhảy cóc)                │
│  • Cơ chế đóng băng đồng hồ SLA khi vào trạng thái ON_HOLD             │
│  • Cơ chế lùi bước linh hoạt (Rollback) kèm Cascade Reset bước giữa    │
│  • Điều phối khóa LOTO: LOCKED_SAFETY_LOTO <-> TESTING_ENERGIZED       │
│  • Kiểm tra đồ thị DAG: DFS chu trình lặp + CPM tính đường găng        │
│  • Rào chắn hoàn thành việc con: Kiểm tra TERMINAL_STATES              │
│  • Cầu nối Event Webhook: Reset Baseline (11.4) & Reset RUL (11.5)     │
└──────────────────┬───────────────────────────────┬─────────────────────┘
                   │                               │
                   ▼                               ▼
┌────────────────────────────────────┐ ┌─────────────────────────────────┐
│ Database (PostgreSQL)              │ │ Audit Trail & Hash Chain        │
│ • work_orders (HSM & LOTO Fields)  │ │ • SHA-256 Audit Hash Chain      │
│ • facility_components (Cây 4 tầng) │ │ • Lý do ghi đè & lùi bước       │
│ • work_order_dependencies (DAG)    │ │ • Biên bản cấp điện tạm thời    │
│ • hsm_stage_transitions            │ │ • Nhật ký đóng băng đồng hồ SLA │
└────────────────────────────────────┘ └─────────────────────────────────┘
```

---

## 7. Mô Hình Dữ Liệu & Thực Thể (Data Model & Schema)

### 7.1. Bảng `facility_components` (Cây cụm chi tiết thiết bị 4 tầng)
```sql
CREATE TABLE facility_components (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id),
  asset_id UUID NOT NULL REFERENCES assets(id),
  parent_component_id UUID NULL REFERENCES facility_components(id) ON DELETE CASCADE,
  name VARCHAR(255) NOT NULL,
  component_code VARCHAR(100) NOT NULL,
  criticality VARCHAR(16) NOT NULL DEFAULT 'MEDIUM', -- 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
  failure_count_90d INT NOT NULL DEFAULT 0,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_comp_tenant_asset ON facility_components(tenant_id, asset_id, parent_component_id);
```

### 7.2. Bảng `work_order_dependencies` (Ràng buộc đồ thị DAG & Đường găng CPM)
```sql
CREATE TABLE work_order_dependencies (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id),
  task_id UUID NOT NULL REFERENCES work_orders(id) ON DELETE CASCADE,
  depends_on_task_id UUID NOT NULL REFERENCES work_orders(id) ON DELETE CASCADE,
  estimated_duration_hours FLOAT NOT NULL DEFAULT 1.0,
  is_critical_path BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT uq_task_dependency UNIQUE (tenant_id, task_id, depends_on_task_id),
  CONSTRAINT chk_no_self_dependency CHECK (task_id != depends_on_task_id)
);
```

### 7.3. Mở rộng bảng `work_orders` (Hỗ trợ phân cấp sự cố, HSM và LOTO)
```sql
ALTER TABLE work_orders
  ADD COLUMN severity_level VARCHAR(32) NULL, -- 'LEVEL_1_MINOR', 'LEVEL_2_MEDIUM', 'LEVEL_3_SEVERE', 'LEVEL_4_CRITICAL_OVERHAUL'
  ADD COLUMN marginal_boundary_warning BOOLEAN DEFAULT FALSE,
  ADD COLUMN current_hsm_stage VARCHAR(32) NULL, -- 8 giai đoạn HSM
  ADD COLUMN hsm_status VARCHAR(32) DEFAULT 'NORMAL', -- 'NORMAL', 'ON_HOLD', 'TESTING_ENERGIZED'
  ADD COLUMN is_on_hold BOOLEAN DEFAULT FALSE,
  ADD COLUMN hold_reason VARCHAR(64) NULL, -- 'WAITING_FOR_PARTS', 'WAITING_FOR_VENDOR', 'WAITING_BUDGET_APPROVAL', 'FORCE_MAJEURE'
  ADD COLUMN hold_started_at TIMESTAMP WITH TIME ZONE NULL,
  ADD COLUMN hold_accumulated_seconds INT DEFAULT 0,
  ADD COLUMN decision_path_explanation TEXT NULL,
  ADD COLUMN override_reason TEXT NULL,
  ADD COLUMN is_loto_active BOOLEAN DEFAULT FALSE,
  ADD COLUMN loto_state VARCHAR(32) DEFAULT 'OFF', -- 'OFF', 'LOCKED_SAFETY_LOTO', 'TESTING_ENERGIZED', 'RELEASED'
  ADD COLUMN loto_locked_by UUID NULL REFERENCES users(id),
  ADD COLUMN loto_energized_by UUID NULL REFERENCES users(id),
  ADD COLUMN loto_released_by UUID NULL REFERENCES users(id),
  ADD COLUMN no_load_trial_vibration_rms FLOAT NULL,
  ADD COLUMN kitting_verified_by UUID NULL REFERENCES users(id),
  ADD COLUMN kitting_verified_at TIMESTAMP WITH TIME ZONE NULL,
  ADD COLUMN audit_hash_chain VARCHAR(64) NULL;
```

### 7.4. Bảng `hsm_stage_transitions` (Nhật ký chuyển bước & Chuỗi băm kiểm toán)
```sql
CREATE TABLE hsm_stage_transitions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id),
  work_order_id UUID NOT NULL REFERENCES work_orders(id) ON DELETE CASCADE,
  from_stage VARCHAR(32) NULL,
  to_stage VARCHAR(32) NOT NULL,
  transition_type VARCHAR(32) NOT NULL, -- 'FORWARD', 'ROLLBACK', 'HOLD', 'RESUME', 'ENERGIZE'
  reason TEXT NULL,
  actor_id UUID NOT NULL REFERENCES users(id),
  vibration_rms FLOAT NULL,
  previous_hash VARCHAR(64) NULL,
  audit_hash VARCHAR(64) NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_hsm_transitions ON hsm_stage_transitions(tenant_id, work_order_id, created_at);
```

---

## 8. Đặc Tả Giao Diện Lập Trình (API Specifications & Contracts)

### Danh Mục Endpoints:

| Phương Thức | Đường Dẫn | Chức Năng |
| :--- | :--- | :--- |
| `POST` | `/api/v1/work-orders/{id}/evaluate-severity/` | Kích hoạt Cây quyết định đánh giá cấp độ sự cố (kèm cờ giáp ranh) |
| `POST` | `/api/v1/work-orders/{id}/hsm-transition/` | Chuyển tiếp giai đoạn tuần tự trong quy trình đại tu 8 bước |
| `POST` | `/api/v1/work-orders/{id}/hsm-rollback/` | Lùi bước linh hoạt về giai đoạn trước đó kèm cascade reset |
| `POST` | `/api/v1/work-orders/{id}/hsm-hold/` | Kích hoạt trạng thái tạm hoãn `ON_HOLD` / Tiếp tục `RESUME` |
| `POST` | `/api/v1/work-orders/{id}/loto-suspend-testing/` | Cán bộ an toàn ký duyệt tạm cấp điện phục vụ chạy thử (`TESTING_ENERGIZED`) |
| `POST` | `/api/v1/work-orders/{id}/loto-release/` | Cán bộ an toàn ký số giải phóng khóa an toàn LOTO vĩnh viễn |
| `POST` | `/api/v1/work-orders/{id}/add-dependency/` | Thiết lập phụ thuộc việc con (Có kiểm tra DFS chu trình & CPM) |

### Cấu Trúc Dữ Liệu Mẫu:

#### 1. Đánh giá cấp độ sự cố có cảnh báo giáp ranh (`POST /evaluate-severity/`):
*Payload Request*:
```json
{
  "downtimeHoursEstimate": 8.1,
  "safetyHazardLevel": 1,
  "estimatedCostRatio": 0.198,
  "failureRecurrenceCount": 2,
  "telemetryAnomalyZscore": 2.95
}
```

*Response `200 OK` (Bật cờ giáp ranh)*:
```json
{
  "success": true,
  "data": {
    "workOrderId": "a1b2c3d4-e5f6-7890-abcd-1234567890ab",
    "suggestedSeverity": "LEVEL_3_SEVERE",
    "marginalBoundaryWarning": true,
    "warningReason": "Tỷ lệ chi phí (19.8%) nằm trong vùng đệm ±5% của ngưỡng Cấp 4 (20.0%). Yêu cầu Quản đốc review thủ công.",
    "severityLabel": "Sự cố nghiêm trọng (Cảnh báo vùng đệm Cấp 4)",
    "decisionTreeExplanation": "Thời gian dừng máy (8.1h) > 8.0h ➔ Tỷ lệ chi phí (19.8%) <= 20.0% ➔ Phân loại: CẤP 3 (VÙNG GIÁP RANH)",
    "requiresHumanReview": true,
    "confidenceScore": 0.88
  }
}
```

#### 2. Lùi bước linh hoạt (`POST /hsm-rollback/`):
*Payload Request*:
```json
{
  "targetStage": "PART_PROCUREMENT",
  "rollbackReason": "Độ rung chạy thử 5.8 mm/s do phát hiện vòng bi SKF mua đợt 1 bị lỗi rơ lỏng xuất xưởng, cần đặt lại vật tư mới.",
  "vibrationReading": 5.8
}
```

*Response `200 OK`*:
```json
{
  "success": true,
  "data": {
    "workOrderId": "a1b2c3d4-e5f6-7890-abcd-1234567890ab",
    "previousStage": "NO_LOAD_TRIAL",
    "currentStage": "PART_PROCUREMENT",
    "cascadedStagesReset": ["LOTO_DISASSEMBLY", "REPAIR_FABRICATION", "REASSEMBLY_ALIGN", "NO_LOAD_TRIAL"],
    "lotoState": "LOCKED_SAFETY_LOTO",
    "auditHash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
  }
}
```

---

## 9. Đặc Tả Trải Nghiệm Người Dùng (UI/UX Behavioral Specifications)

- **Thanh tiến trình 8 giai đoạn đại tu (Overhaul 8-Stage Stepper)**:
  - Giai đoạn đã xong hiển thị màu xanh lá kèm dấu kiểm và chữ ký số người duyệt.
  - Giai đoạn đang làm hiển thị màu xanh dương kèm đồng hồ đếm thời gian.
  - Giai đoạn bị lùi bước (Rollback) hiển thị màu cam nhạt kèm thông báo lý do lùi.
  - Nút bấm **"Tạm hoãn ngoại cảnh (On-Hold)"** và **"Lùi bước (Rollback)"** hiển thị rõ ràng cho Quản đốc.
- **Banner cảnh báo an toàn sinh mạng LOTO đa trạng thái**:
  - Khi máy ở `LOCKED_SAFETY_LOTO`: Banner màu đỏ rực nhấp nháy toàn màn hình:
    > "NGUY HIỂM: THIẾT BỊ ĐANG BỊ KHÓA AN TOÀN LOTO BỞI [TÊN CÁN BỘ AN TOÀN]. CẤM ĐÓNG ĐIỆN DƯỚI MỌI HÌNH THỨC."
  - Khi máy ở `TESTING_ENERGIZED`: Banner màu cam cảnh báo thử tải:
    > "CẢNH BÁO: NGUỒN ĐIỆN ĐANG ĐƯỢC TẠM CẤP ĐỂ CHẠY THỬ KIỂM TRA. KHU VỰC CÁCH LY 5 MÉT."
- **Sơ đồ phụ thuộc việc con DAG & Đường găng**:
  - Hiển thị đồ thị trực quan: Các công việc nằm trên Đường găng (`Float = 0`) được đóng khung viền đỏ nổi bật.
  - Các công việc con đã hoàn thành hiển thị màu xanh lá, việc bị hủy/bỏ qua (`CANCELLED`/`SKIPPED`) hiển thị màu xám gạch ngang nhưng không làm nghẽn tiến độ đóng phiếu cha.

---

## 10. Tiêu Chí Chấp Nhận & Ma Trận Kịch Bản Kiểm Thử (Acceptance Criteria & Test Scenarios)

### 10.1. Ma Trận 12 Kịch Bản Kiểm Thử Nghiệp Vụ & Quy Trình HSM

| Mã Test | Tên Kịch Bản | Điều Kiện Thử Nghiệm | Hành Vi Kỳ Vọng | Trạng Thái |
| :--- | :--- | :--- | :--- | :--- |
| **TC-HSM-01** | Chặn nhảy cóc giai đoạn HSM | Đang ở `LOTO_DISASSEMBLY` (Giai đoạn 3), bấm nhảy sang `COMMISSIONED_DONE` (Giai đoạn 8) | Từ chối (`400 Bad Request`), thông báo bắt buộc chuyển tuần tự sang Giai đoạn 4 | Chưa thực hiện |
| **TC-HSM-02** | Bẫy vách đá & Vùng đệm giáp ranh AI *(User Scen 2)* | Nhập tỷ lệ chi phí $19.9\%$ (sát ngưỡng $20.0\%$ của Cấp 4) | Xếp loại Cấp 3 kèm cờ `marginal_boundary_warning = True`, bôi vàng UI, yêu cầu Quản đốc review | Chưa thực hiện |
| **TC-HSM-03** | Lùi bước linh hoạt đa giai đoạn *(User Scen 3)* | Chạy thử rung $5.5\text{ mm/s}$, Quản đốc chọn lùi thẳng từ Giai đoạn 6 về Giai đoạn 2 | Chấp thuận, cascade reset trạng thái các Giai đoạn 3, 4, 5 về pending, ghi lý do lùi bước | Chưa thực hiện |
| **TC-HSM-04** | Nghiệm thu phiếu cha với phiếu con bị hủy *(User Scen 4)* | Phiếu cha có 3 việc con: 2 việc `COMPLETED`, 1 việc `CANCELLED` hợp lệ | Cho phép nghiệm thu phiếu cha vì tất cả việc con đều thuộc `TERMINAL_STATES` | Chưa thực hiện |
| **TC-HSM-05** | Tạm hoãn ngoại cảnh đóng băng SLA *(User Scen 5)* | Phiếu bị treo 30 ngày ở trạng thái `ON_HOLD` do chờ phụ tùng nhập khẩu | Đồng hồ SLA tự động trừ 30 ngày này khi tính MTTR trong báo cáo Task 10.2 & 10.3 | Chưa thực hiện |
| **TC-HSM-06** | Tạm ngưng LOTO phục vụ chạy thử *(User Scen 1)* | Chuyển sang Giai đoạn 6, Cán bộ an toàn ký lệnh tạm cấp nguồn | Trạng thái thiết bị chuyển sang `TESTING_ENERGIZED`, cho phép quay động cơ để đo rung | Chưa thực hiện |
| **TC-HSM-07** | Rào chắn rung động ISO 10816 khi chạy thử | Chạy thử không tải có độ rung $v_{\text{rms}} = 5.2\text{ mm/s} > 4.5\text{ mm/s}$ | Khóa không cho chuyển sang Giai đoạn 7, tự động tái kích hoạt LOTO, yêu cầu lùi bước | Chưa thực hiện |
| **TC-HSM-08** | Rào chắn tập kết vật tư Stage 2 Gate *(Bổ sung 1)* | Thử chuyển sang Giai đoạn 3 khi kho mới chỉ cấp phát $80\%$ BOM | Từ chối chuyển bước, báo lỗi thiếu phụ tùng chưa tập kết tại Staging Area | Chưa thực hiện |
| **TC-HSM-09** | Triệt tiêu năng lượng Zero-Energy *(Bổ sung 4)* | Cố tình tháo máy khi áp suất dư $P_{\text{gauge}} = 1.5\text{ bar} > 0$ | Từ chối cấp phép LOTO, yêu cầu xả áp triệt tiêu về 0 bar và đo kiểm khí độc | Chưa thực hiện |
| **TC-HSM-10** | Phát hiện chu trình DAG & Tính đường găng *(Bổ sung 3)* | Nhập chu trình lặp Việc A $\rightarrow$ Việc B $\rightarrow$ Việc A | DFS phát hiện cạnh quay lui, chặn đứng lệnh; tính toán đúng công việc có `Float = 0` | Chưa thực hiện |
| **TC-HSM-11** | Cầu nối tái đồng bộ Baseline sau đại tu *(Bổ sung 2)* | Hoàn tất Giai đoạn 8 (`COMMISSIONED_DONE`) | Webhook tự động kích hoạt: Reset cửa sổ trượt Task 11.4 và đưa RUL về trần 125 ngày ở Task 11.5 | Chưa thực hiện |
| **TC-HSM-12** | Chuỗi băm kiểm toán bất biến *(Bổ sung 5)* | Thực hiện chuỗi chuyển bước: Giai đoạn 1 $\rightarrow$ 2 $\rightarrow$ 3 $\rightarrow$ Hold | Tạo chuỗi băm $\text{SHA-256}$ móc xích liên hoàn, phát hiện ngay nếu DB bị sửa tay | Chưa thực hiện |

---

## 11. Implementation Notes — For Implementation Phase Only

> [!IMPORTANT]
> **REFERENCE ONLY — DO NOT IMPLEMENT OR MODIFY CODE BASED ON THIS SECTION DURING SPEC REVIEW. These notes are intended for the implementation phase after the specification is approved.**

Phần này lưu trữ các thuật toán và logic xử lý cốt lõi để các kỹ sư tham khảo trong quá trình triển khai mã nguồn:

### 11.1. Phân Loại Cây Quyết Định Với Vùng Đệm Cảnh Báo Giáp Ranh
```python
from sklearn.tree import DecisionTreeClassifier

class IncidentSeverityEvaluator:
    def __init__(self):
        self.model = DecisionTreeClassifier(max_depth=4, criterion='gini', random_state=42)
        # Các ngưỡng quyết định chuẩn mực
        self.COST_RATIO_SPLIT = 0.20
        self.DOWNTIME_SPLIT = 8.0
        self.MARGIN_RATIO = 0.05  # ±5% Vùng đệm giáp ranh

    def evaluate(self, features: dict) -> dict:
        cost_ratio = features.get('estimated_cost_ratio', 0.0)
        downtime = features.get('downtime_hours', 0.0)
        
        # Kiểm tra vùng đệm giáp ranh (Marginal Boundary Check)
        is_marginal = False
        warning_msg = None
        
        cost_lower = self.COST_RATIO_SPLIT * (1.0 - self.MARGIN_RATIO)  # 19.0%
        cost_upper = self.COST_RATIO_SPLIT * (1.0 + self.MARGIN_RATIO)  # 21.0%
        
        if cost_lower <= cost_ratio <= cost_upper:
            is_marginal = True
            warning_msg = f"Tỷ lệ chi phí ({cost_ratio*100:.1f}%) nằm trong vùng đệm ±5% của ngưỡng Cấp 4 ({self.COST_RATIO_SPLIT*100:.0f}%)."

        # Giả định phân loại thô từ cây
        if cost_ratio > self.COST_RATIO_SPLIT and downtime > self.DOWNTIME_SPLIT:
            suggested = "LEVEL_4_CRITICAL_OVERHAUL"
        elif cost_ratio > 0.10 or downtime > 4.0:
            suggested = "LEVEL_3_SEVERE"
        elif downtime > 2.0:
            suggested = "LEVEL_2_MEDIUM"
        else:
            suggested = "LEVEL_1_MINOR"

        return {
            "suggested_severity": suggested,
            "marginal_boundary_warning": is_marginal,
            "warning_message": warning_msg,
            "requires_human_review": is_marginal
        }
```

### 11.2. Thuật Toán Duyệt Chu Trình DFS & Đường Găng CPM
```python
def detect_dag_cycle(adj_list: dict, start_node: str) -> bool:
    """DFS 3 màu: 0 = Chưa thăm, 1 = Đang thăm (Ngăn xếp), 2 = Đã xong."""
    visited = {}
    def dfs(node):
        visited[node] = 1
        for neighbor in adj_list.get(node, []):
            if visited.get(neighbor) == 1:
                return True # Phát hiện cạnh quay lui (Back-edge)
            if visited.get(neighbor) != 2:
                if dfs(neighbor):
                    return True
        visited[node] = 2
        return False
    return dfs(start_node)

def calculate_critical_path(tasks: list, dependencies: list) -> list:
    """Tính toán thời gian dự trữ Float và xác định Đường găng CPM."""
    # tasks: [{'id': ..., 'duration': ...}]
    # Early Start (ES), Late Start (LS)
    # Những task có Float = LS - ES == 0 là Critical Path
    critical_task_ids = []
    # (Được triển khai chi tiết trong service CPM tại Phase 11.8.3)
    return critical_task_ids
```

### 11.3. Tính Toán Chuỗi Băm Kiểm Toán Móc Nối (Audit Hash Chain)
```python
import hashlib
import json

def generate_audit_hash(tenant_id: str, work_order_id: str, stage: str, 
                        action: str, signer_id: str, timestamp_iso: str, 
                        previous_hash: str) -> str:
    raw_payload = f"{tenant_id}|{work_order_id}|{stage}|{action}|{signer_id}|{timestamp_iso}|{previous_hash or 'GENESIS'}"
    return hashlib.sha256(raw_payload.encode('utf-8')).hexdigest()
```

---

## 12. Kế Hoạch Triển Khai & Nghiệm Thu (Implementation Checklist)

- [ ] **Task 11.8.1 — Facility Component Catalog, Schema & Audit Hash Chain**
  - [ ] Xây dựng bảng `FacilityComponent` hỗ trợ cây phả hệ 4 tầng phân lập theo `tenant_id`.
  - [ ] Xây dựng bảng `WorkOrderDependency` lưu trữ cạnh đồ thị DAG và trường thời gian dự trữ CPM.
  - [ ] Mở rộng bảng `WorkOrder` với các trường: `severity_level`, `marginal_boundary_warning`, `current_hsm_stage`, `hsm_status`, `is_on_hold`, `hold_accumulated_seconds`, `loto_state`, `audit_hash_chain`.
  - [ ] Xây dựng bảng `HsmStageTransition` lưu vết kiểm toán nối chuỗi SHA-256.
- [ ] **Task 11.8.2 — Decision Tree Classifier & Marginal Boundary Warning Engine**
  - [ ] Huấn luyện mô hình `DecisionTreeClassifier(max_depth=4)` với 4 cấp độ nghiêm trọng.
  - [ ] Cài đặt thuật toán kiểm tra vùng đệm giáp ranh $\pm 5\%$ gắn cờ `marginal_boundary_warning`.
  - [ ] Cài đặt bộ trích xuất chuỗi giải thích IF-THEN minh bạch $100\%$.
  - [ ] Tích hợp tính năng Quản đốc ghi đè (`override_reason` $\ge 20$ ký tự) có lưu vết kiểm toán.
- [ ] **Task 11.8.3 — Hierarchical State Machine (HSM) 8-Stage Engine & Flexible Rollback**
  - [ ] Cài đặt bộ điều phối tuần tự 8 giai đoạn đại tu (chặn nhảy cóc).
  - [ ] Cài đặt cơ chế lùi bước linh hoạt đa giai đoạn (Rollback to any $m < k$) kèm Cascade Reset.
  - [ ] Cài đặt cơ chế tạm hoãn `ON_HOLD` và logic đóng băng đồng hồ đo thời gian (Clock-paused MTTR).
  - [ ] Cài đặt thuật toán DFS kiểm tra chu trình đồ thị và CPM xác định đường găng công việc con.
  - [ ] Cài đặt điều kiện nghiệm thu phiếu cha dựa trên tập trạng thái kết thúc `TERMINAL_STATES`.
- [ ] **Task 11.8.4 — LOTO Interlock, Quality Guards & Cross-Module Bridges**
  - [ ] Cài đặt cơ chế LOTO tạm ngưng phục vụ chạy thử (`TESTING_ENERGIZED`) có ký số của Cán bộ an toàn.
  - [ ] Cài đặt rào chắn rung động chạy thử ISO 10816 ($v_{\text{rms}} \le 4.5\text{ mm/s}$).
  - [ ] Cài đặt cổng kiểm soát tập kết vật tư Stage 2 ($100\%$ BOM tại Staging Area) và Zero-Energy.
  - [ ] Cài đặt Webhook/Event cầu nối sau đại tu: Reset Baseline cho Task 11.4 và Reset RUL cho Task 11.5.
- [ ] **Task 11.8.5 — UI Integration & Test Matrix Verification**
  - [ ] Xây dựng thanh tiến trình 8 bước HSM stepper, nút On-Hold/Rollback, banner LOTO đa trạng thái.
  - [ ] Hiển thị sơ đồ cây chi tiết 4 tầng và đồ thị DAG công việc con với viền đỏ đường găng.
  - [ ] Triển khai và xác minh bộ kiểm thử tự động 12 test cases (`TC-HSM-01` đến `TC-HSM-12`).

# Thiết Kế Hệ Thống & Đặc Tả Kỹ Thuật: Task 11.2 — Genetic Algorithm (GA) Multi-Objective Task Assignment Optimization

Tài liệu này xác định cơ sở toán học, mô hình mã hóa nhiễm sắc thể (Chromosome Encoding), kỹ thuật giải mã lộ trình phụ (Sub-decoding Heuristic), hàm thích nghi đa mục tiêu (Multi-Objective Fitness Function), các toán tử di truyền thích ứng (Adaptive Genetic Operators), giao diện trực quan hóa quá trình hội tụ (Convergence Visualizer), bộ kịch bản đo lường hiệu năng và **bộ kịch bản kiểm thử chấp nhận & trường hợp biên (Acceptance Criteria & Edge Cases)** cho bài toán **Tối Ưu Hóa Phân Công Ca Làm Việc Đa Mục Tiêu Bằng Thuật Toán Di Truyền (GA)** trong hệ thống Quản lý Tài sản Doanh nghiệp (EAM).

Tài liệu đóng vai trò là **Đặc Tả Kỹ Thuật & Chuẩn Kiểm Thử (Technical Specification & Audit Baseline)** nhằm đối chiếu, rà soát và thực thi trọn vẹn toàn bộ tính năng mà không bị thiếu sót bất kỳ nghiệp vụ enterprise nào.

---

## 1. Mục Tiêu & Phạm Vi (Objective & Scope)

### 1.1. Phân Định Chiến Lược: GA (11.2) Khác Gì Hungarian (11.1)?
Hệ thống giải quyết hai bài toán phân công với bản chất nghiệp vụ và phạm vi hoàn toàn khác nhau:

| Đặc Điểm So Sánh | Task 11.1 — Hungarian Algorithm | Task 11.2 — Genetic Algorithm (GA) |
| :--- | :--- | :--- |
| **Mô hình ánh xạ** | **Ánh xạ 1 - 1 (Bipartite Matching)**: Mỗi thợ nhận đúng 1 việc tại một thời điểm giao ca tức thời. | **Ánh xạ Nhiều - 1 (Many-to-One / Workload Scheduling)**: Mỗi thợ nhận một danh mục $K$ công việc ($K \ge 1$) trong suốt ca làm việc 8 tiếng. |
| **Bản chất mục tiêu** | **Đơn mục tiêu tuyến tính**: Tối thiểu hóa tổng chi phí đơn lẻ $\min \sum C_{ij}$. | **Đa mục tiêu xung đột**: Cân bằng đồng thời 4 mục tiêu: Độ khớp kỹ năng $\leftrightarrow$ Cân bằng tải làm việc $\leftrightarrow$ Giảm quãng đường di chuyển $\leftrightarrow$ Tuân thủ hạn chót (Due Date). |
| **Lớp bài toán** | Quy hoạch tuyến tính giải được trong thời gian đa thức $\mathcal{O}(N^3)$. | Thuộc lớp bài toán **NP-hard (Generalized Assignment & Scheduling Problem - GASP)**. |
| **Ngữ cảnh áp dụng** | **Điều phối tức thời đầu ca**: Có 5 thợ rảnh và 5 sự cố khẩn cấp cần người tới xử lý ngay lập tức. | **Lập kế hoạch phân bổ ca làm việc**: Đầu ngày có 30 phiếu bảo trì cần chia đều cho 5 kỹ thuật viên sao cho không ai bị quá tải và hoàn thành đúng hạn. |

### 1.2. Mục Tiêu Tối Ưu
Tìm phương án phân bổ toàn bộ danh mục công việc trong ca cho đội ngũ kỹ thuật viên sao cho tối ưu hóa đồng thời 4 mục tiêu:
1. **Đúng người đúng việc**: Phù hợp bậc thợ và chuyên môn kỹ thuật.
2. **Cân bằng tải làm việc thực tế**: Tổng thời gian sửa chữa cộng thời gian di chuyển đồng đều giữa các thợ.
3. **Giảm thiểu thời gian di chuyển**: Lộ trình di chuyển trong khuôn viên nhà máy ngắn nhất.
4. **Tuyệt đối tuân thủ hạn chót (Due Dates)**: Hạn chế tối đa việc chậm trễ tiến độ cam kết SLA.

---

## 2. Ràng Buộc Kế Thừa Hệ Thống (Existing System Constraints & Codebase Reuse)

- **Tái Sử Dụng Mô Hình Multi-Tenancy**: Mọi dữ liệu kỹ thuật viên, phiếu bảo trì và cấu hình thuật toán phải thuộc cùng một `tenant_id` qua `TenantManager`.
- **Tái Sử Dụng Thực Thể Nghiệp Vụ Có Sẵn**:
  - `User`: Vai trò `role = 'TECHNICIAN'`, hồ sơ tay nghề và chứng chỉ.
  - `TechnicianProfile`: Chuyên môn (`skills`), bậc thợ (`skill_level`), thời lượng ca trực (`max_shift_minutes`), vị trí xuất phát.
  - `WorkOrder`: Kỹ năng yêu cầu (`required_skill`), thời gian ước tính (`estimated_duration_minutes`), hạn chót hoàn thành (`due_date`), vị trí thiết bị (`coords_x, coords_y, zone_id`), phụ tùng yêu cầu (`required_spare_parts`).
- **Xử Lý Bất Đồng Bộ Qua Hàng Đợi Celery**: Do thuật toán GA cần tính toán qua 100–150 thế hệ, việc kích hoạt GA phải được giao cho Worker Celery ngầm xử lý (`celery_queue: optimization`) để không chặn luồng HTTP của máy chủ Web.

---

## 3. Yêu Cầu Nghiệp Vụ & Quy Tắc Cốt Lõi (Business Requirements & Core Rules)

Toàn bộ logic giải thuật di truyền lập lịch phân công phải tuân thủ nghiêm ngặt 10 quy tắc nghiệp vụ phòng thủ sau:

### Quy Tắc 1: Khắc Phục Lỗ Hổng Trình Tự Bằng Giải Mã Lộ Trình Phụ (Sub-decoding Routing Guardrail)
- **Điểm Yếu Nghiệp Vụ**: Nhiễm sắc thể $X = [g_0, g_1, \dots, g_{M-1}]$ chỉ cho biết "Ai làm việc nào" chứ **KHÔNG xác định "Làm theo thứ tự nào"**. Nếu không biết thợ làm việc số 0 trước hay việc số 2 trước, hệ thống không thể tính được chính xác quãng đường di chuyển ($f_{\text{travel}}$) và dòng thời gian đến máy.
- **Quy Tắc Bắt Buộc**:
  1. Trong bước đánh giá hàm thích nghi (Fitness Evaluation), trước khi tính quãng đường, hệ thống bắt buộc thực thi bước **Giải mã phụ (Sub-decoding Heuristic)** cho từng thợ:
  2. Sắp xếp danh mục công việc được gán của thợ theo Heuristic kết hợp: Ưu tiên công việc có hạn chót gần nhất (`due_date`) $\rightarrow$ Sắp xếp theo thuật toán Láng giềng gần nhất (Nearest Neighbor) để tối ưu cung đường di chuyển.
  3. Sau khi xác định chuỗi trình tự $[wo_{(1)} \rightarrow wo_{(2)} \rightarrow \dots]$, hệ thống mới tính toán quãng đường $f_{\text{travel}}$ và mốc thời gian hoàn tất từng phiếu.

### Quy Tắc 2: Tính Đủ Thời Gian Di Chuyển Tránh Quá Tải Thực Tế (Travel Time Workload Guardrail)
- **Điểm Yếu Nghiệp Vụ**: Nếu chỉ cộng dồn thời gian sửa chữa đơn thuần ($\sum \text{duration} = 7$ tiếng), nhưng thợ phải di chuyển giữa 5 phân xưởng xa nhau mất thêm 1.5 tiếng đi bộ. Tổng thời gian thực tế sẽ là 8.5 tiếng, vượt quá ca làm việc 8 tiếng quy định, dẫn đến vi phạm Luật Lao động và trễ việc.
- **Quy Tắc Bắt Buộc**:
  1. Tổng khối lượng công việc của kỹ thuật viên $i$ bắt buộc phải tính gộp cả thời gian di chuyển ước tính:
     $$\text{TotalTime}_i = \sum_{j \in \text{Tasks}_i} \text{estimated\_duration}_j + \sum_{k} \text{travel\_time}(loc_k, loc_{k+1})$$
  2. Nếu $\text{TotalTime}_i > \text{tech}_i.\text{max\_shift\_minutes}$ (mặc định 480 phút): Áp dụng hàm phạt quá tải phi tuyến tính lũy tiến $\text{Penalty}_{\text{overload}} = \beta \times (\text{TotalTime}_i - 480)^2$.

### Quy Tắc 3: Bổ Sung Kỹ Thuật Viên Ảo Tránh Sập Thuật Toán Do Thiếu Năng Lực (Virtual Tech & Death Penalty Trap)
- **Điểm Yếu Nghiệp Vụ**: Khi nhà máy phát sinh 40 sự cố (cần 50 giờ làm) nhưng ca trực chỉ có 5 thợ (tổng năng lực tối đa 40 giờ). Dù chia cách nào thì chắc chắn sẽ có thợ vượt trần 8 tiếng. Nếu dùng hình phạt tử hình (Death Penalty làm $Fitness = 0$), toàn bộ 100 cá thể trong quần thể đều nhận điểm 0 $\rightarrow$ Chọn lọc ngẫu nhiên vô hướng, **thuật toán bị đông cứng (Evolutionary Freeze) và sập hoàn toàn**.
- **Quy Tắc Bắt Buộc**:
  1. Bổ sung một **Kỹ thuật viên Ảo (Virtual/Backlog Technician có mã định danh $ID = N$)** vào không gian nghiệm.
  2. Công việc nào được gán cho Thợ Ảo mang ý nghĩa: "Tồn đọng chuyển sang ca sau" hoặc "Thuê thầu ngoài".
  3. Gán việc cho Thợ Ảo bị trừ điểm mềm $\text{Penalty}_{\text{backlog}}$ phụ thuộc vào mức độ ưu tiên của phiếu:
     $$\text{Penalty}_{\text{backlog}}(j) = \text{Priority\_Weight}_j \times 50.0$$
     *(Việc `URGENT` bị phạt cực nặng nếu hoãn, việc `LOW` bị phạt rất nhẹ).*
  4. Cơ chế này bảo đảm quần thể luôn có cá thể sống sót, giúp GA tự động học cách "hy sinh" các việc kém quan trọng nhất đẩy vào Backlog để giữ cho các thợ thật không bị quá tải.

### Quy Tắc 4: Ràng Buộc Hạn Chót Công Việc (Due Date SLA Guardrail)
- **Điểm Yếu Nghiệp Vụ**: Thợ làm việc trong 6 tiếng (không quá tải ca), nhưng việc cuối cùng trong ngày có hạn chót lúc 10:00 sáng, trong khi thợ đến máy lúc 14:00 chiều $\rightarrow$ Trễ hạn SLA nghiêm trọng.
- **Quy Tắc Bắt Buộc**:
  1. Mô phỏng mốc thời gian hoàn tất lũy kế của từng công việc:
     $$\text{FinishTime}_j = \text{ShiftStart} + \sum \text{duration} + \sum \text{travel}$$
  2. Nếu $\text{FinishTime}_j > \text{due\_date}_j$: Trừ điểm thích nghi $\text{Penalty}_{\text{late}} = \gamma \times (\text{FinishTime}_j - \text{due\_date}_j)$.

### Quy Tắc 5: Chống Khóa Chết Cực Trị Địa Phương Bằng Đột Biến Thích Ứng (Adaptive Mutation Guardrail)
- **Điểm Yếu Nghiệp Vụ**: Chiến lược giữ lại tinh hoa (Elitism 5%) khiến sau 20–30 thế hệ, quần thể ngập tràn các bản sao giống hệt nhau của một cực trị địa phương (Local Optima). Đồ thị thích nghi đi ngang sớm và thuật toán không thể tìm ra phương án tốt hơn.
- **Quy Tắc Bắt Buộc**:
  1. Theo dõi số thế hệ trì trệ (`stagnation_count`): Số thế hệ liên tiếp mà điểm số `Best Fitness` không cải thiện quá $0.1\%$.
  2. **Đột biến thích ứng (Adaptive Mutation)**:
     - Bình thường: Xác suất đột biến $P_m = 0.08$.
     - Khi `stagnation_count >= 15`: Tự động kích hoạt chế độ "Đột biến xung kích" (Cataclysmic Mutation), tăng vọt $P_m$ lên $0.30$ trong 3 thế hệ liên tiếp để xáo trộn mạnh cấu trúc gen.
     - Sau 3 thế hệ xung kích, trả $P_m$ về mức bình thường để quần thể tiếp tục hội tụ tinh chỉnh.

### Quy Tắc 6: Khởi Tạo Quần Thể Ban Đầu Có Định Hướng (Heuristic Seeding Guardrail)
- **Điểm Yếu Nghiệp Vụ**: Nếu khởi tạo 100% cá thể ngẫu nhiên, phần lớn cá thể ở thế hệ 0 đều là nghiệm rác (vi phạm chứng chỉ an toàn, dồn 10 việc cho 1 thợ). Thuật toán mất 40–50 thế hệ đầu tiên chỉ để học cách loại bỏ nghiệm rác.
- **Quy Tắc Bắt Buộc**:
  1. Áp dụng kỹ thuật Khởi tạo hạt giống (Heuristic Seeding):
     - **$20\%$ cá thể ban đầu**: Được sinh ra bằng thuật toán Greedy / Hungarian (ưu tiên gán việc khẩn cấp cho thợ có tay nghề cao nhất và san đều khối lượng công việc).
     - **$80\%$ cá thể còn lại**: Sinh ngẫu nhiên có kiểm tra điều kiện an toàn chuyên môn (Repair Operator).
  2. Giúp thuật toán xuất phát từ vùng nghiệm có chất lượng cao ngay từ thế hệ 0, đẩy nhanh tốc độ hội tụ gấp 3–5 lần.

### Quy Tắc 7: Chặng Dừng Nhận Phụ Tùng Tại Kho Vật Tư (Warehouse Pickup Routing)
- **Điểm Yếu Nghiệp Vụ**: Phiếu sửa chữa cần 2 vòng bi mới. Thợ không thể đi thẳng từ phòng giao ban đến máy mà phải rẽ qua Kho vật tư trung tâm để xuất kho trước.
- **Quy Tắc Bắt Buộc**:
  - Khi Work Order có yêu cầu phụ tùng (`required_spare_parts != []`), thuật toán tự động chèn điểm dừng **Kho vật tư** vào lộ trình trước khi tới thiết bị, tính đúng thời gian nhận vật tư vào tổng hành trình.

### Quy Tắc 8: Hỗ Trợ Ca Làm Việc Không Đồng Nhất (Heterogeneous Shift Lengths)
- **Điểm Yếu Nghiệp Vụ**: Trong thực tế, có thợ làm ca gãy 4 tiếng, thợ làm ca chính 8 tiếng, thợ làm ca 12 tiếng. Nếu áp trần 480 phút cố định cho tất cả thì thợ ca 4 tiếng sẽ bị quá tải nghiêm trọng.
- **Quy Tắc Bắt Buộc**:
  - Trần giờ làm việc được lấy động theo từng cá nhân: `tech.max_shift_minutes`.

### Quy Tắc 9: Xuất Tập Nghiệm Mặt Biên Pareto Cho Người Quản Lý (Pareto Front Multi-Objective)
- **Điểm Yếu Nghiệp Vụ**: Dùng trọng số cố định ($w_1, w_2, w_3$) không bao quát được mọi tình huống điều hành thực tế của Giám đốc nhà máy.
- **Quy Tắc Bắt Buộc**:
  - Thuật toán trích xuất **Top 3 phương án tối ưu trên mặt biên Pareto** để hiển thị trên giao diện:
    1. *Phương án Cân Bằng (Balanced)*: Trọng số chuẩn mực.
    2. *Phương án Tối Đa Tay Nghề (Skill-Focused)*: Ưu tiên thợ bậc cao nhất cho việc phức tạp.
    3. *Phương án Quãng Đường Ngắn Nhất (Min-Travel)*: Gom việc theo cụm phân xưởng để tiết kiệm thời gian di chuyển.

### Quy Tắc 10: Chống Phân Mảnh Lịch Làm Việc (Job Clustering Guardrail)
- **Điểm Yếu Nghiệp Vụ**: Thợ bị gán việc nhảy cóc liên tục giữa Xưởng A và Xưởng B (sáng ở A, trưa sang B, chiều lại về A).
- **Quy Tắc Bắt Buộc**:
  - Áp dụng điểm phạt phân mảnh nếu thợ phải di chuyển qua lại giữa các phân xưởng khác nhau nhiều hơn 2 lần trong ca.

---

## 4. Yêu Cầu Chức Năng & Luồng Xử Lý (Functional Requirements & Workflows)

### 4.1. Mô Hình Nhiễm Sắc Thể & Kỹ Thuật Sub-Decoding
- **Nhiễm Sắc Thể (Chromosome)**: Mảng số nguyên $X = [g_0, g_1, \dots, g_{M-1}]$ với $g_j \in \{0, 1, \dots, N\}$ (trong đó $N$ là chỉ số của Kỹ thuật viên Ảo / Backlog).
- **Quy Trình Giải Mã Phụ (Sub-decoding Pipeline)**:
  Đối với mỗi kỹ thuật viên $i \in \{0, \dots, N-1\}$:
  1. Trích xuất tập công việc $\text{Tasks}_i = \{j \mid g_j = i\}$.
  2. Sắp xếp $\text{Tasks}_i$ theo thứ tự tối ưu: Ưu tiên phiếu có `due_date` sớm hơn, sau đó áp dụng heuristic Nearest Neighbor để nối các tọa độ thiết bị thành chuỗi di chuyển $[wo_{(1)} \rightarrow wo_{(2)} \dots]$.
  3. Mô phỏng mốc thời gian hoàn tất từng phiếu:
     $$\text{FinishTime}_{wo_{(k)}} = \text{FinishTime}_{wo_{(k-1)}} + \text{travel\_time}(loc_{k-1}, loc_k) + \text{duration}_{wo_{(k)}}$$
  4. Tính tổng thời gian ca $\text{TotalTime}_i$ và tổng quãng đường di chuyển $\text{TotalDistance}_i$.

---

### 4.2. Hàm Thích Nghi Đa Mục Tiêu (Multi-Objective Fitness Function)
Hàm thích nghi tổng thể $F(X)$ được tính trên thang điểm $[0, 100]$:

$$F(X) = w_1 \cdot f_{\text{skill}}(X) + w_2 \cdot f_{\text{workload}}(X) + w_3 \cdot f_{\text{travel}}(X) - \text{Pen}_{\text{overload}}(X) - \text{Pen}_{\text{late}}(X) - \text{Pen}_{\text{backlog}}(X)$$

Trong đó:
1. **$f_{\text{skill}}(X)$ (Độ tương thích tay nghề)**:
   $$f_{\text{skill}}(X) = \frac{1}{|\text{Assigned Tasks}|} \sum_{j, g_j \ne N} \text{SkillScore}(g_j, j) \times 100$$
2. **$f_{\text{workload}}(X)$ (Cân bằng tải làm việc thực tế)**:
   $$f_{\text{workload}}(X) = 100 - \min\left(100, \;\; \frac{\sigma(\text{TotalTime}_0, \dots, \text{TotalTime}_{N-1})}{\overline{\text{TotalTime}}} \times 100\right)$$
3. **$f_{\text{travel}}(X)$ (Tối ưu quãng đường di chuyển)**:
   $$f_{\text{travel}}(X) = 100 \times \left(1.0 - \frac{\sum_{i} \text{TotalDistance}_i}{\text{MaxPossibleDistance}}\right)$$
4. **Các hàm phạt (Penalties)**:
   - $\text{Pen}_{\text{overload}}$: Phạt nếu $\text{TotalTime}_i > \text{tech}_i.\text{max\_shift\_minutes}$.
   - $\text{Pen}_{\text{late}}$: Phạt nếu phiếu bị hoàn thành trễ hơn `due_date`.
   - $\text{Pen}_{\text{backlog}}$: Phạt khi gán việc cho Kỹ thuật viên Ảo (dựa theo độ ưu tiên của phiếu).
5. **Trọng số chuẩn hóa**: $w_1 = 0.35$ (Kỹ năng), $w_2 = 0.35$ (Cân bằng tải), $w_3 = 0.30$ (Quãng đường).

---

### 4.3. Toán Tử Di Truyền Thích Ứng (Adaptive Operators)
- **Toán tử Chọn lọc**: Tournament Selection với kích thước $k=3$.
- **Toán tử Lai ghép**: Uniform Crossover hoặc Two-Point Crossover với tỷ lệ $P_c = 0.85$.
- **Toán tử Đột biến thích ứng (Adaptive Swap/Mutation)**:
  - Bình thường: $P_m = 0.08$.
  - Khi phát hiện trì trệ qua 15 thế hệ: Tăng $P_m = 0.30$ trong 3 thế hệ liên tiếp.
- **Bảo tồn tinh hoa (Elitism)**: Top 5% cá thể tốt nhất được sao chép nguyên vẹn sang thế hệ sau.

---

## 5. Quy Tắc Bảo Mật, Phân Quyền & Đa Khách Hàng (Security, RBAC & Multi-Tenant Rules)

- **Cô Lập Đa Khách Hàng (Multi-Tenancy)**: Quá trình tiến hóa di truyền chỉ chạy trên danh sách kỹ thuật viên và Work Order thuộc cùng một `tenant_id`. Không cho phép dữ liệu giữa các doanh nghiệp bị trộn lẫn trong quần thể.
- **Phân Quyền Theo Vai Trò (RBAC)**:
  - Chỉ người dùng có vai trò `MAINTENANCE_MANAGER` hoặc `TENANT_ADMIN` mới có quyền khởi tạo tác vụ lập lịch GA và áp dụng phương án phân công vào hệ thống.

---

## 6. Kiến Trúc & Luồng Dữ Liệu (Architecture & Data Flow)

```
[Quản Lý Bảo Trì Chọn Danh Sách Phiếu Đầu Ngày]
                     │
                     ▼
[POST /api/v1/work-orders/ga-auto-assign/] ──► Khởi tạo tác vụ Celery (Status: PENDING)
                     │                         Trả về ngay: {"taskId": "...", "status": "PENDING"}
                     ▼
[Celery Worker: Optimization Queue]
   ├── 1. Khởi tạo hạt giống (20% Greedy/Hungarian + 80% ngẫu nhiên an toàn)
   ├── 2. Bổ sung Thợ Ảo (Backlog Tech ID = N)
   ├── 3. Vòng lặp tiến hóa qua 100–150 thế hệ:
   │        ├── (a) Giải mã phụ (Sub-decoding Heuristic Nearest Neighbor & Due date)
   │        ├── (b) Tính toán tổng thời gian = Sửa chữa + Di chuyển + Nhận phụ tùng
   │        ├── (c) Đánh giá hàm thích nghi đa mục tiêu & các điểm phạt
   │        ├── (d) Bảo tồn tinh hoa (Elitism Top 5%)
   │        ├── (e) Kiểm tra trì trệ ──► Kích hoạt Đột biến thích ứng (Adaptive Mutation)
   │        └── (f) Cập nhật tiến độ thế hệ vào Celery backend
   └── 4. Hoàn thành: Trích xuất Top 3 phương án mặt biên Pareto
                     │
                     ▼
[Client Polling Tiến Độ & Đồ Thị Hội Tụ]
   ├── Client thăm dò GET /api/v1/work-orders/ga-auto-assign/{taskId}/progress/
   └── Hiển thị đồ thị đường cong hội tụ theo thời gian thực
                     │
                     ▼
[Quản Lý Xem 3 Phương Án Pareto & Lộ Trình Từng Thợ]
   ├── Lựa chọn 1 trong 3 phương án (Balanced / Skill-Focused / Min-Travel)
   ├── Xem danh sách việc chuyển sang ca sau (Backlog của Thợ Ảo)
   └── Cho phép điều chỉnh thủ công nếu cần
                     │
                     ▼
[POST /api/v1/work-orders/ga-auto-assign/apply/]
   ├── Cập nhật phân công chính thức cho các phiếu
   └── Phát thông báo Real-time (Task 10.1) đến từng kỹ thuật viên
```

---

## 7. Mô Hình Dữ Liệu & Thực Thể (Data Model & Schema)

### 7.1. Bảng `work_orders`
- `id`: `UUID` (Primary Key).
- `tenant_id`: `UUID` (Kế thừa `BaseTenantModel`).
- `required_skill`: `VARCHAR(64)` (Kỹ năng chuyên môn bắt buộc).
- `min_skill_level`: `SMALLINT` (Bậc thợ tối thiểu).
- `estimated_duration_minutes`: `INTEGER` (Thời gian sửa chữa ước tính).
- `due_date`: `TIMESTAMP WITH TIME ZONE` (Hạn chót hoàn thành).
- `required_spare_parts`: `JSONB` (Danh mục phụ tùng cần lấy ở kho, ví dụ: `[{"partId": "...", "qty": 2}]`).
- `coords_x`, `coords_y`, `floor_level`, `zone_id`: Tọa độ lắp đặt thiết bị.
- `assigned_to_id`: `UUID` (Foreign Key tới `User`, gán sau khi chốt phương án).
- `status`: `VARCHAR(20)` (`CREATED`, `ASSIGNED`, `IN_PROGRESS`, `COMPLETED`).

### 7.2. Bảng `technician_profiles`
- `user_id`: `UUID` (Foreign Key tới `User`).
- `tenant_id`: `UUID` (Kế thừa `BaseTenantModel`).
- `skills`: `JSONB` (Danh mục kỹ năng chuyên môn).
- `skill_level`: `SMALLINT` (Bậc thợ từ 1 đến 5).
- `max_shift_minutes`: `INTEGER` (Thời gian làm việc tối đa trong ca, mặc định 480 phút).
- `coords_x`, `coords_y`, `zone_id`: Vị trí xuất phát ca trực (thường là phòng giao ban).
- `is_on_duty`: `BOOLEAN` (Trạng thái đang trong ca làm việc).

---

## 8. Đặc Tả Giao Diện Lập Trình (API Specifications & Contracts)

### Danh Mục Endpoints:

| Phương Thức | Đường Dẫn | Chức Năng |
| :--- | :--- | :--- |
| `POST` | `/api/v1/work-orders/ga-auto-assign/` | Khởi tạo tác vụ lập lịch phân công ca bằng GA (trả về `task_id`) |
| `GET` | `/api/v1/work-orders/ga-auto-assign/{task_id}/progress/` | Thăm dò tiến độ tiến hóa, đồ thị hội tụ và 3 phương án Pareto |
| `POST` | `/api/v1/work-orders/ga-auto-assign/apply/` | Xác nhận và áp dụng phương án phân công đã chọn vào cơ sở dữ liệu |

### Cấu Trúc Dữ Liệu Mẫu:

#### 1. Thăm dò tiến độ & Top 3 phương án Pareto (`GET /api/v1/work-orders/ga-auto-assign/{task_id}/progress/`):
```json
{
  "success": true,
  "data": {
    "taskId": "task-ga-2026-9988",
    "status": "COMPLETED",
    "currentGeneration": 150,
    "maxGenerations": 150,
    "bestFitness": 93.8,
    "convergenceHistory": [
      { "generation": 10, "bestFitness": 68.2, "avgFitness": 51.4 },
      { "generation": 50, "bestFitness": 84.1, "avgFitness": 73.0 },
      { "generation": 100, "bestFitness": 91.5, "avgFitness": 85.2 },
      { "generation": 150, "bestFitness": 93.8, "avgFitness": 90.1 }
    ],
    "paretoSolutions": [
      {
        "strategy": "BALANCED",
        "label": "Phương án Cân Bằng (Khuyến nghị)",
        "fitnessScore": 93.8,
        "backlogCount": 2,
        "backlogTasks": [
          { "workOrderId": "wo-025", "code": "WO-2026-115", "title": "Bảo dưỡng định kỳ quạt thông gió", "priority": "LOW" }
        ],
        "schedules": [
          {
            "technicianId": "tech-01",
            "technicianName": "Nguyễn Văn An",
            "taskCount": 4,
            "repairMinutes": 320,
            "travelMinutes": 65,
            "totalMinutes": 385,
            "orderedTasks": [
              { "workOrderId": "wo-001", "code": "WO-2026-088", "estimatedFinish": "09:30", "dueTime": "10:00", "isLate": false },
              { "workOrderId": "wo-003", "code": "WO-2026-090", "estimatedFinish": "12:00", "dueTime": "14:00", "isLate": false }
            ]
          }
        ]
      },
      {
        "strategy": "SKILL_FOCUSED",
        "label": "Phương án Tối Đa Tay Nghề",
        "fitnessScore": 91.2
      },
      {
        "strategy": "MIN_TRAVEL",
        "label": "Phương án Quãng Đường Ngắn Nhất",
        "fitnessScore": 89.6
      }
    ]
  }
}
```

---

## 9. Đặc Tả Trải Nghiệm Người Dùng (UI/UX Behavioral Specifications)

- **Drawer Lập Lịch Ca Trực Đa Mục Tiêu (GA Scheduler Drawer)**:
  - Mở rộng từ cạnh phải màn hình khi người quản lý bấm "Lập lịch phân bổ ca (Genetic Algorithm)".
  - Hiển thị thanh tiến độ thế hệ và đồ thị hội tụ (`Best Fitness` vs `Avg Fitness`) chuyển động mượt mà.
- **Thẻ Lựa Chọn Chiến Lược Pareto (Pareto Option Selector)**:
  - Cho phép người quản lý bấm chọn giữa 3 thẻ chiến lược: **Cân Bằng**, **Ưu Tiên Kỹ Năng**, hoặc **Tiết Kiệm Di Chuyển**.
- **Danh Mục Công Việc Hoãn Lại (Backlog / Virtual Tech Card)**:
  - Hiển thị rõ danh sách các phiếu được thuật toán đề xuất hoãn sang ca sau (do tổng năng lực ca không đủ), kèm lý do minh bạch (ưu tiên thấp, không ảnh hưởng sản xuất).
- **Lộ Trình Trực Quan Của Kỹ Thuật Viên**:
  - Từng kỹ thuật viên có thanh thời gian biểu (Timeline) hiển thị thời gian sửa chữa từng máy, thời gian đi bộ giữa các máy và cảnh báo đỏ nếu có nguy cơ trễ hạn `due_date`.

---

## 10. Tiêu Chí Chấp Nhận & Ma Trận Kịch Bản Kiểm Thử (Acceptance Criteria & Test Matrix)

Dưới đây là bảng ma trận kiểm thử chi tiết hóa toàn bộ 12 kịch bản chấp nhận và trường hợp biên (Edge Cases):

### 10.1. Ma Trận Kịch Bản Nghiệp Vụ & Thuật Toán Tiến Hóa

- [ ] **TC-GA-01: Bảo toàn tính đơn điệu không giảm của điểm thích nghi (Elitism Preservation)**
  - *Mô tả*: Theo dõi điểm số `bestFitness` qua 150 thế hệ liên tiếp.
  - *Kỳ vọng*: Điểm số `bestFitness` của thế hệ sau luôn lớn hơn hoặc bằng thế hệ trước, không bao giờ bị thụt lùi.

- [ ] **TC-GA-02: Giải mã lộ trình phụ tính chuẩn quãng đường (Sub-decoding Nearest Neighbor)**
  - *Mô tả*: Thợ được gán 3 việc A, B, C nằm rải rác.
  - *Kỳ vọng*: Hệ thống tự động sắp xếp thứ tự di chuyển tối ưu trước khi tính $f_{\text{travel}}$, loại bỏ hoàn toàn việc tính toán quãng đường không có trình tự.

- [ ] **TC-GA-03: Tính đủ thời gian di chuyển tránh vỡ ca (Travel Time Overload Guardrail)**
  - *Mô tả*: Thợ nhận 5 việc có tổng thời gian sửa là 420 phút, thời gian đi bộ giữa các xưởng mất 90 phút (tổng 510 phút $> 480$ phút).
  - *Kỳ vọng*: Cá thể này bị áp hàm phạt quá tải $\text{Pen}_{\text{overload}}$; thuật toán tự động san bớt 1 việc cho thợ khác để giữ tổng thời gian dưới 480 phút.

- [ ] **TC-GA-04: Sống sót khi thiếu hụt tổng năng lực (Virtual Tech Capacity Overflow)**
  - *Mô tả*: 40 công việc cần tổng cộng 50 giờ làm, nhưng cả ca trực chỉ có 5 thợ (tổng năng lực tối đa 40 giờ).
  - *Kỳ vọng*: Thuật toán không bị chết đứng ($Fitness = 0$); Thợ Ảo tiếp nhận các việc có độ ưu tiên thấp nhất; 5 thợ thật không bị quá tải; trả về danh mục Backlog rõ ràng.

- [ ] **TC-GA-05: Ràng buộc hạn chót công việc (Due Date Violation Penalty)**
  - *Mô tả*: Việc có hạn chót 10:00 sáng nhưng bị xếp vào vị trí cuối ca (14:00).
  - *Kỳ vọng*: Phương án này bị phạt điểm $\text{Pen}_{\text{late}}$; thuật toán tự động đảo thứ tự đưa việc đó lên đầu ca hoặc gán cho thợ khác để hoàn thành trước 10:00 sáng.

- [ ] **TC-GA-06: Thoát khỏi cực trị địa phương nhờ Đột biến thích ứng (Adaptive Mutation)**
  - *Mô tả*: Điểm Best Fitness không thay đổi trong 15 thế hệ liên tiếp (stagnation).
  - *Kỳ vọng*: Tỷ lệ đột biến tự động tăng lên $P_m = 0.30$ trong 3 thế hệ tiếp theo; quần thể được đa dạng hóa và tiếp tục tìm ra điểm thích nghi cao hơn.

- [ ] **TC-GA-07: Tăng tốc hội tụ nhờ Hạt giống khởi tạo (Heuristic Seeding)**
  - *Mô tả*: So sánh tốc độ đạt điểm thích nghi 85 giữa quần thể ngẫu nhiên 100% và quần thể có 20% hạt giống Greedy.
  - *Kỳ vọng*: Quần thể có hạt giống đạt ngưỡng 85 nhanh hơn ít nhất gấp 3 lần so với ngẫu nhiên hoàn toàn.

- [ ] **TC-GA-08: Tự động chèn điểm dừng kho phụ tùng (Warehouse Pickup Stop)**
  - *Mô tả*: Phiếu yêu cầu xuất 2 vòng bi từ kho vật tư trung tâm.
  - *Kỳ vọng*: Lộ trình của thợ tự động thêm chặng xuất phát $\rightarrow$ Kho vật tư $\rightarrow$ Thiết bị; thời gian nhận vật tư được tính vào tổng thời gian ca.

- [ ] **TC-GA-09: Tương thích ca làm việc có độ dài khác nhau (Heterogeneous Shifts)**
  - *Mô tả*: Thợ 1 làm ca gãy 4 tiếng (240 phút), Thợ 2 làm ca 8 tiếng (480 phút).
  - *Kỳ vọng*: Thợ 1 chỉ được gán tối đa dưới 240 phút; Thợ 2 nhận phần việc dài hơn; không áp trần 480 phút cơ học cho Thợ 1.

- [ ] **TC-GA-10: Xuất Top 3 phương án mặt biên Pareto**
  - *Mô tả*: Hoàn thành tiến hóa di truyền.
  - *Kỳ vọng*: API trả về đủ 3 phương án: Balanced, Skill-Focused và Min-Travel để người quản lý lựa chọn.

### 10.2. Kịch Bản Kỹ Thuật, Hiệu Năng & An Toàn

- [ ] **TC-GA-11: Ràng buộc an toàn chứng chỉ tuyệt đối (Safety Certification Guardrail)**
  - *Mô tả*: Phiếu sửa chữa máy ép cao tần yêu cầu chứng chỉ đặc thù.
  - *Kỳ vọng*: Toàn bộ các phương án phân công trong Top Pareto đều gán việc này đúng cho thợ có chứng chỉ hợp lệ.

- [ ] **TC-GA-12: Xử lý bất đồng bộ không gây nghẽn kết nối Web**
  - *Mô tả*: Khởi tạo tác vụ GA chạy 150 thế hệ cho 40 công việc.
  - *Kỳ vọng*: Endpoint POST trả về `taskId` trong vòng $< 100\text{ms}$; giao diện Client thăm dò tiến độ mượt mà không gặp lỗi Timeout HTTP.

---

## 11. Implementation Notes — For Implementation Phase Only

> [!IMPORTANT]
> **REFERENCE ONLY — DO NOT IMPLEMENT OR MODIFY CODE BASED ON THIS SECTION DURING SPEC REVIEW. These notes are intended for the implementation phase after the specification is approved.**

Phần này lưu trữ các chỉ dẫn kỹ thuật hạ tầng chi tiết để các kỹ sư tham khảo trong quá trình triển khai mã nguồn:

### 11.1. Cấu Trúc Lớp Quản Lý Tiến Hóa GA Với Sub-Decoding & Adaptive Mutation
```python
import numpy as np

class MaintenanceGAScheduler:
    def __init__(self, work_orders, technicians, config):
        self.wos = work_orders
        self.techs = technicians
        self.pop_size = config.get('populationSize', 100)
        self.max_gen = config.get('maxGenerations', 150)
        self.mutation_rate = 0.08
        self.stagnation_count = 0
        self.best_fitness = 0.0

    def sub_decode_and_evaluate(self, individual):
        """
        individual: Mảng integer độ dài M, giá trị từ 0 đến N (N là Thợ Ảo)
        """
        n_techs = len(self.techs)
        total_fitness = 0.0
        
        for tech_idx in range(n_techs):
            assigned_task_indices = [j for j, val in enumerate(individual) if val == tech_idx]
            if not assigned_task_indices:
                continue
                
            # Sắp xếp Heuristic: Nearest Neighbor + Due Date
            ordered_tasks = self.sort_nearest_neighbor(tech_idx, assigned_task_indices)
            
            # Tính dòng thời gian tích lũy (Sửa chữa + Di chuyển)
            tech_time, travel_dist, is_late = self.simulate_timeline(tech_idx, ordered_tasks)
            # Áp hàm phạt nếu quá tải ca của thợ đó
            overload = max(0, tech_time - self.techs[tech_idx].max_shift_minutes)
            
        # Đánh giá Thợ Ảo (Backlog)
        backlog_indices = [j for j, val in enumerate(individual) if val == n_techs]
        backlog_penalty = sum(self.wos[j].priority_weight * 50.0 for j in backlog_indices)
        
        return total_fitness - backlog_penalty

    def step_generation(self):
        # Kiểm tra trì trệ và kích hoạt Đột biến thích ứng
        if self.current_best <= self.best_fitness * 1.001:
            self.stagnation_count += 1
        else:
            self.stagnation_count = 0
            self.best_fitness = self.current_best
            
        if self.stagnation_count >= 15:
            # Xung kích đột biến 3 thế hệ
            self.mutation_rate = 0.30
        elif self.stagnation_count == 0:
            self.mutation_rate = 0.08
```

---

## 12. Kế Hoạch Triển Khai & Nghiệm Thu (Implementation Checklist)

- [ ] **Task 11.2.1 — Sub-decoding & Timeline Simulation Engine**
  - [ ] Cài đặt thuật toán giải mã phụ (Sub-decoding Heuristic) sắp xếp thứ tự thực hiện theo Nearest Neighbor & Hạn chót.
  - [ ] Xây dựng mô hình mô phỏng dòng thời gian tích lũy gộp: Thời gian sửa chữa + Thời gian di chuyển + Thời gian nhận phụ tùng tại kho.
- [ ] **Task 11.2.2 — Virtual Technician & Multi-Objective Fitness Engine**
  - [ ] Tích hợp Kỹ thuật viên Ảo (Virtual Tech ID = N) xử lý tình huống quá tải tổng thể.
  - [ ] Thiết kế hàm thích nghi đa mục tiêu $F(X)$ với điểm phạt quá tải, phạt trễ hạn và phạt tồn đọng.
- [ ] **Task 11.2.3 — Adaptive Genetic Operators**
  - [ ] Cài đặt cơ chế khởi tạo hạt giống (20% Greedy/Hungarian).
  - [ ] Cài đặt toán tử Đột biến thích ứng (Adaptive Mutation) tự động tăng $P_m = 0.30$ khi trì trệ 15 thế hệ.
  - [ ] Cài đặt thuật toán trích xuất Top 3 phương án mặt biên Pareto.
- [ ] **Task 11.2.4 — Celery Background Optimization & REST APIs**
  - [ ] Đóng gói solver vào Celery task với cơ chế báo cáo tiến độ thế hệ thời gian thực.
  - [ ] Endpoint khởi tạo `POST /api/v1/work-orders/ga-auto-assign/`.
  - [ ] Endpoint tiến độ `GET /api/v1/work-orders/ga-auto-assign/{task_id}/progress/`.
  - [ ] Endpoint áp dụng `POST /api/v1/work-orders/ga-auto-assign/apply/`.
- [ ] **Task 11.2.5 — Web Portal UI Drawer & Pareto Selector**
  - [ ] Thiết kế Drawer hiển thị đồ thị đường cong hội tụ thích nghi theo thế hệ.
  - [ ] Thiết kế bộ chọn 3 phương án Pareto (Balanced, Skill-Focused, Min-Travel).
  - [ ] Hiển thị danh mục Backlog được đề xuất hoãn sang ca sau và Timeline lộ trình từng thợ.
- [ ] **Task 11.2.6 — Verification & Testing Suite**
  - [ ] Viết test cases kiểm thử đầy đủ 12 kịch bản chấp nhận và trường hợp biên (`TC-GA-01` đến `TC-GA-12`).

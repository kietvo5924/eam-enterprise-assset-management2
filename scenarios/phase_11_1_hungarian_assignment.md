# Thiết Kế Hệ Thống & Đặc Tả Kỹ Thuật: Task 11.1 — Hungarian Assignment Optimization (Kuhn-Munkres Algorithm)

Tài liệu này xác định cơ sở toán học, mô hình hóa dữ liệu (Data Modeling), thuật toán xây dựng ma trận chi phí đa yếu tố (Multi-Factor Cost Matrix), giải thuật Kuhn-Munkres (Hungarian Algorithm), thiết kế API, giao diện người dùng giải trình (Explainable UI Preview) và **bộ kịch bản kiểm thử chấp nhận & trường hợp biên (Acceptance Criteria & Edge Cases)** cho bài toán **Tự Động Phân Công Công Việc Tối Ưu trong Hệ Thống Quản Lý Tài Sản Doanh Nghiệp (EAM)**.

Tài liệu đóng vai trò là **Đặc Tả Kỹ Thuật & Chuẩn Kiểm Thử (Technical Specification & Audit Baseline)** nhằm đối chiếu, rà soát và thực thi trọn vẹn toàn bộ tính năng mà không bị thiếu sót bất kỳ nghiệp vụ enterprise nào.

---

## 1. Mục Tiêu & Phạm Vi (Objective & Scope)

### 1.1. Bản Chất Bài Toán Phân Công Tuyến Tính (Linear Sum Assignment Problem - LSAP)
Tại thời điểm đầu ca trực hoặc giao ca, có một tập hợp $M$ phiếu bảo trì chưa phân công (`Work Orders`) cần được giao cho $N$ kỹ thuật viên (`Technicians`) đang sẵn sàng làm việc.
- Mỗi kỹ thuật viên $i$ khi thực hiện công việc $j$ phát sinh một chi phí tổng hợp $C_{ij}$ (bao gồm khoảng cách di chuyển đa tầng, độ lệch tay nghề, mức độ tải công việc hiện tại, rào cản khu vực, và xung đột thời gian giao ca).
- **Mục tiêu**: Tìm ma trận gán nhị phân $X = [X_{ij}]$ với $X_{ij} \in \{0, 1\}$ sao cho tổng chi phí phân công trên toàn nhà xưởng đạt giá trị cực tiểu:
  $$\min \sum_{i=1}^{N} \sum_{j=1}^{M} C_{ij} X_{ij}$$
  với điều kiện mỗi thợ nhận tối đa 1 việc và mỗi việc được giao cho tối đa 1 thợ trong đợt điều phối tức thời này ($\sum_{j} X_{ij} \le 1$ và $\sum_{i} X_{ij} \le 1$).

### 1.2. Vai Trò Của Giải Thuật Hungarian
- Bảo đảm tìm ra **nghiệm tối ưu toàn cục (Globally Optimal)**, loại bỏ hoàn toàn các quyết định phân công cảm tính hoặc giải thuật tham lam cục bộ (Greedy).
- Thời gian giải quyết siêu tốc trên tập dữ liệu thực tế ($N, M \le 100$) thông qua thư viện `scipy.optimize.linear_sum_assignment` với độ phức tạp $O(K^3)$.

---

## 2. Ràng Buộc Kế Thừa Hệ Thống (Existing System Constraints & Codebase Reuse)

- **Tái Sử Dụng Mô Hình Multi-Tenancy**: Toàn bộ dữ liệu kỹ thuật viên và Work Order tham gia tính toán phải được lọc tuyệt đối trong cùng `tenant_id` qua `TenantManager`.
- **Tái Sử Dụng Thực Thể Nghiệp Vụ Có Sẵn**:
  - `User`: Vai trò `role = 'TECHNICIAN'`, trạng thái `is_active = True`.
  - `TechnicianProfile`: Chuyên môn (`skills`), bậc thợ (`skill_level`), chứng chỉ (`certifications`), vị trí hiện tại (`coords_x, coords_y, floor_level, zone_id`), thời gian hết ca (`shift_end_time`).
  - `WorkOrder`: Trạng thái `status = 'CREATED'`, mức độ ưu tiên `priority`, thời gian ước tính (`estimated_duration_hours`), công cụ yêu cầu (`required_tools`), quan hệ phụ thuộc (`depends_on_wo_id`).
- **Tích Hợp Luồng Phân Công Hiện Có**: Sau khi người quản lý xác nhận phương án phân công, hệ thống cập nhật `assigned_to` của Work Order, chuyển trạng thái sang `ASSIGNED` và kích hoạt thông báo thời gian thực (Task 10.1).

---

## 3. Yêu Cầu Nghiệp Vụ & Quy Tắc Cốt Lõi (Business Requirements & Core Rules)

Toàn bộ logic phân công Hungarian phải tuân thủ nghiêm ngặt 10 quy tắc nghiệp vụ phòng thủ sau:

### Quy Tắc 1: Khắc Phục Lỗ Hổng Hằng Số Ưu Tiên Bằng Hệ Số Nhân Khuếch Đại (Priority Multiplier Guardrail)
- **Điểm Yếu Toán Học Của Hungarian Nguyên Bản**:
  - Trong giải thuật Kuhn-Munkres, việc trừ một hằng số $w_p \cdot P_j$ vào toàn bộ cột $j$ là phép biến đổi ma trận chi phí tương đương. Vì mỗi việc $j$ chỉ được giao cho đúng 1 thợ ($\sum_{i=1}^N X_{ij} = 1$), tổng chi phí:
    $$\sum_{i,j} (f(i, j) - w_p P_j) X_{ij} = \sum_{i,j} f(i, j) X_{ij} - w_p \sum_{j=1}^M P_j$$
  - Vì $\sum_{j=1}^M P_j$ là hằng số cố định với mọi cách phân công, **phép trừ hằng số bị triệt tiêu hoàn toàn và KHÔNG HỀ làm thay đổi kết quả phân công**! Thuật toán vẫn gán y hệt như khi không có độ ưu tiên.
- **Quy Tắc Bắt Buộc**:
  - Độ ưu tiên bắt buộc phải là một **Hệ số nhân khuếch đại (Priority Multiplier $\ge 1.0$)** tác động lên các biến số khoảng cách và chênh lệch tay nghề:
    $$C_{ij} = \text{Priority\_Multiplier}_j \times (w_d \cdot D_{ij} + w_s \cdot S_{ij}) + w_w \cdot W_i + \dots$$
  - Khi công việc là `URGENT` (hệ số $\times 2.5$), sự chênh lệch khoảng cách và tay nghề giữa các thợ bị phóng đại lên gấp $2.5$ lần, ép thuật toán phải chọn người giỏi nhất và ở gần nhất cho việc khẩn cấp.

### Quy Tắc 2: Rào Cản Không Gian & Phạt Chuyển Khu Vực Cách Ly (Zone Transition Penalty Guardrail)
- **Điểm Yếu Nghiệp Vụ**: Kỹ thuật viên A đứng cách Máy 1 chỉ 10 mét đường chim bay, nhưng A đang ở trong Phòng Sạch (Cleanroom), khu vực an toàn sinh học hoặc xưởng sơn khử khuẩn. Muốn ra ngoài xưởng cơ khí, thợ phải mất 20–30 phút thay đồ bảo hộ và thực hiện quy trình khử khuẩn.
- **Quy Tắc Bắt Buộc**:
  1. Khoảng cách Euclid thuần túy không được sử dụng đơn lẻ.
  2. Bổ sung chi phí phạt chuyển vùng $\text{Pen}_{\text{zone}}(i, j)$: Nếu `tech.zone_id != wo.zone_id` và vùng yêu cầu quy trình cách ly/khử khuẩn, cộng thêm từ $+30$ đến $+50$ điểm phạt vào $C_{ij}$ để hạn chế tối đa việc điều động thợ qua lại giữa các khu vực kiểm soát ngặt nghèo.

### Quy Tắc 3: Xung Đột Thời Gian Giao Ca & Tránh Tăng Ca Ngoài Kế Hoạch (Shift Handover Clash Guardrail)
- **Điểm Yếu Nghiệp Vụ**: Thợ B chỉ còn 30 phút nữa là hết ca làm việc và chuẩn bị ra về. Thuật toán vô tình gán cho B một Work Order dự kiến kéo dài 3 tiếng (do B đứng gần máy nhất). Hậu quả là phát sinh chi phí làm thêm giờ (overtime) ngoài ý muốn hoặc thợ bàn giao dở dang làm chậm tiến độ.
- **Quy Tắc Bắt Buộc**:
  1. So sánh thời gian dự kiến của phiếu (`wo.estimated_duration_hours`) với thời gian còn lại trong ca của thợ (`remaining_shift_time_hours`).
  2. Nếu $\text{wo.estimated\_duration} > \text{remaining\_shift\_time}$:
     - Áp dụng điểm phạt mềm $\text{Pen}_{\text{shift}} = 40.0$ điểm để ưu tiên nhường việc đó cho thợ ca sau hoặc thợ có ca trực dài hơn.
     - Nếu $\text{wo.estimated\_duration} > \text{remaining\_shift\_time} + 2.0$ giờ: Áp dụng phạt cứng Big-M ($10^7$) chặn tuyệt đối việc giao việc lớn cho thợ sắp hết ca.

### Quy Tắc 4: Lọc Bỏ Công Việc Bị Khóa Do Phụ Thuộc Trình Tự (Task Dependency Filtering Guardrail)
- **Điểm Yếu Nghiệp Vụ**: Work Order Y (sửa bo mạch điện tử) phụ thuộc vào Work Order X (tháo vỏ bảo vệ máy CNC). Nếu đưa cả Y vào ma trận Hungarian và gán cho Thợ 2, Thợ 2 đến nơi nhưng chưa thể làm việc vì Thợ 1 chưa tháo xong vỏ máy.
- **Quy Tắc Bắt Buộc**:
  1. Tầng tiền xử lý (Pre-processing) bắt buộc kiểm tra trường `depends_on_wo_id`.
  2. Nếu phiếu tiên quyết chưa hoàn thành (`prerequisite_wo.status != 'COMPLETED'`), phiếu Y bị đánh dấu `is_blocked = True` và **loại bỏ hoàn toàn khỏi tập đầu vào của ma trận Hungarian đợt này**.

### Quy Tắc 5: Nhận Diện Xung Đột Công Cụ Dùng Chung (Shared Tool Bottleneck Detection Guardrail)
- **Điểm Yếu Nghiệp Vụ**: Giải thuật Hungarian giả định các công việc hoàn toàn độc lập. Thuật toán có thể gán đồng thời WO 1 cho Thợ A và WO 2 cho Thợ B. Cả 2 phiếu đều đòi hỏi cùng 1 máy đo nhiệt độ hồng ngoại chuyên dụng (toàn xưởng chỉ có duy nhất 1 chiếc).
- **Quy Tắc Bắt Buộc**:
  1. Sau khi Kuhn-Munkres tìm ra nghiệm tối ưu, tầng hậu xử lý (Post-solve) quét danh sách công cụ yêu cầu (`required_tools`) của toàn bộ các phiếu được chọn.
  2. Nếu phát hiện 2 phiếu chạy đồng thời đòi hỏi cùng 1 công cụ có số lượng tồn kho khả dụng $< 2$, hệ thống phát hiện xung đột và gắn cờ cảnh báo màu cam (`SHARED_TOOL_CONFLICT`) trên Modal Giải trình để người Quản lý chủ động lùi giờ hoặc điều chỉnh thợ thủ công.

### Quy Tắc 6: Phân Rã Công Việc Tổ Đội Nhiều Thợ (Multi-Technician Crew Slot Decomposition)
- **Điểm Yếu Nghiệp Vụ**: Công việc đại tu cẩu trục nặng bắt buộc 2 người: 1 thợ chính (Lead Tech Bậc $\ge 4$) và 1 thợ phụ (Assistant Tech Bậc $\ge 2$). Hungarian nguyên bản chỉ hỗ trợ gán 1-1.
- **Quy Tắc Bắt Buộc**:
  1. Phiếu có cờ `is_crew_task = True` tự động được phân rã thành $K$ nhiệm vụ con độc lập trong ma trận: `WO-xxx-Lead` và `WO-xxx-Assistant`.
  2. Mỗi slot nhiệm vụ có tiêu chí bậc thợ và kỹ năng riêng, đưa vào ma trận Hungarian như 2 cột công việc riêng biệt để gán cho 2 kỹ thuật viên khác nhau.

### Quy Tắc 7: Đệm Node Ảo Xử Lý Ma Trận Lệch Kích Thước (Zero-Cost Dummy Padding Guardrail)
- **Quy Tắc Bắt Buộc**:
  1. Tự động quy đổi ma trận về kích thước vuông $K \times K$ với $K = \max(N, M)$.
  2. **Trường hợp Dư thợ ($N > M$)**: Bổ sung $N - M$ cột công việc ảo với chi phí $C_{i, \text{dummy}} = 0$. Thợ được gán việc ảo ở trạng thái Dự phòng (Standby).
  3. **Trường hợp Thiếu thợ ($M > N$)**: Sắp xếp công việc theo độ ưu tiên khẩn cấp (`URGENT` > `HIGH` > `MEDIUM` > `LOW`) và `due_date`. Chỉ đưa $N$ việc cấp bách nhất vào giải nghiệm; các việc còn lại giữ nguyên trong danh sách chờ.

### Quy Tắc 8: Chặn Tuyệt Đối Vi Phạm Chứng Chỉ An Toàn & Tay Nghề (Big-M Penalty $10^7$)
- **Quy Tắc Bắt Buộc**:
  1. Thợ bắt buộc phải có kỹ năng chuyên môn (`required_skill IN tech.skills`) và đủ chứng chỉ an toàn bắt buộc (`required_certification IN tech.certifications`).
  2. Nếu vi phạm: Áp dụng chi phí phạt cực đại $C_{ij} = M_{\text{penalty}} = 10^7$.
  3. Sau khi giải, nếu cặp nào có chi phí $\ge 10^7$, hệ thống từ chối tự động áp dụng và hiển thị cảnh báo đỏ.

### Quy Tắc 9: Khóa Chống Tranh Chấp Phân Công Đồng Thời (Dispatch Concurrency & Database Lock)
- **Điểm Yếu Nghiệp Vụ**: Hai Quản lý ở 2 máy tính cùng bấm "Phân công tối ưu" vào đầu ca làm việc. Cả 2 đều thấy Thợ An đang rảnh và cùng bấm "Xác nhận & Áp dụng", khiến Thợ An bị gán 2 việc cùng lúc.
- **Quy Tắc Bắt Buộc**:
  1. Khi bấm Apply (`/api/v1/work-orders/auto-assign/apply/`), backend thực thi giao dịch có khóa hàng dữ liệu (`select_for_update`) trên bảng `technician_profiles` và `work_orders`.
  2. Nếu trạng thái của thợ hoặc phiếu đã bị thay đổi bởi phiên khác trước đó vài giây, giao dịch lập tức Rollback và trả về lỗi `CONCURRENT_DISPATCH_CONFLICT` kèm yêu cầu tải lại ma trận.

### Quy Tắc 10: Phá Vỡ Thế Hòa Điểm Số Xác Định & Công Bằng Khối Lượng (Deterministic Tie-Breaking)
- **Điểm Yếu Nghiệp Vụ**: Khi Thợ 1 và Thợ 2 có điểm chi phí hoàn toàn bằng nhau đối với Phiếu 1 ($C_{11} = C_{21} = 25.0$), thư viện có thể chọn ngẫu nhiên tùy theo vị trí sắp xếp mảng.
- **Quy Tắc Bắt Buộc**:
  1. Áp dụng cơ chế phá vỡ thế hòa điểm số có tính xác định (Deterministic Tie-Breaker): Khi có nhiều phương án bằng điểm, ưu tiên thợ có **tổng số giờ công tích lũy trong tháng thấp hơn** (`monthly_accumulated_hours`).
  2. Giúp cân bằng cơ hội làm việc và thu nhập giữa các thành viên trong đội bảo trì.

---

## 4. Yêu Cầu Chức Năng & Luồng Xử Lý (Functional Requirements & Workflows)

### 4.1. Công Thức Ma Trận Chi Phí Đa Yếu Tố Cải Tiến
Chi phí tổng hợp $C_{ij}$ giữa Kỹ thuật viên $i$ và Phiếu công việc $j$ được tính toán như sau:

$$C_{ij} = \begin{cases} 
10^7 & \text{nếu vi phạm Ràng Buộc Cứng (Thiếu chứng chỉ, sai kỹ năng, lệch ca > 2h)} \\
C_{\text{base}}(i, j) & \text{nếu thỏa mãn điều kiện an toàn}
\end{cases}$$

Trong đó:
$$C_{\text{base}}(i, j) = \text{Priority\_Multiplier}_j \times \left( w_d \cdot D_{ij} + w_s \cdot S_{ij} \right) + w_w \cdot W_i + \text{Pen}_{\text{zone}}(i, j) + \text{Pen}_{\text{shift}}(i, j) + \text{Pen}_{\text{disrupt}}(i)$$

Chi tiết các biến số:
1. **$\text{Priority\_Multiplier}_j$ (Hệ số nhân khuếch đại mức độ ưu tiên)**:
   - `URGENT`: $2.5$
   - `HIGH`: $1.8$
   - `MEDIUM`: $1.2$
   - `LOW`: $1.0$
2. **$D_{ij}$ (Chi phí di chuyển thực tế đa tầng - Manhattan Multi-Floor)**:
   $$D_{ij} = \min\left(100.0, \;\; 0.1 \times \left( |\Delta x| + |\Delta y| + 50 \times |\Delta z| \right)\right)$$
   *(Khoảng cách mặt phẳng chuẩn hóa thang 100 điểm, mỗi tầng chênh lệch tương đương 50m di chuyển).*
3. **$S_{ij}$ (Chi phí lệch bậc thợ)**:
   - So sánh $\Delta = \text{Level}_i - \text{Level}_{\text{req}, j}$.
   - Nếu thiếu bậc ($\Delta < 0$): Phạt nặng $S_{ij} = 20 \times |\Delta|$.
   - Nếu thừa bậc ($\Delta > 0$): Phạt nhẹ $S_{ij} = 5 \times \Delta$ (tránh lãng phí thợ bậc cao cho việc đơn giản).
4. **$W_i$ (Chi phí tải công việc hiện tại)**:
   $$W_i = 25 \times \text{active\_workload}_i$$
5. **$\text{Pen}_{\text{zone}}(i, j)$ (Điểm phạt rào cản khu vực/phòng sạch)**:
   - Khác phân xưởng/khu vực thông thường: $+15$ điểm.
   - Khu vực yêu cầu khử khuẩn/phòng sạch đặc biệt: $+40$ điểm.
   - Cùng phân xưởng/khu vực: $0$ điểm.
6. **$\text{Pen}_{\text{shift}}(i, j)$ (Điểm phạt xung đột giờ giao ca)**:
   - Nếu $\text{wo.estimated\_duration} > \text{remaining\_shift\_time}$: $+40$ điểm.
   - Ngược lại: $0$ điểm.
7. **$\text{Pen}_{\text{disrupt}}(i)$ (Điểm phạt gián đoạn công việc dở dang)**:
   - Thợ đang có việc dở dang sắp xong: $+15$ điểm (ưu tiên thợ đang rảnh $100\%$).
8. **Bộ trọng số chuẩn hóa**: $w_d = 0.50$, $w_s = 0.50$, $w_w = 0.20$.

---

### 4.2. Luồng Vận Hành Phân Công Tự Động
```
[Điều Phối Viên Bấm: "Phân Công Tối Ưu (Hungary)"]
                    │
                    ▼
[POST /api/v1/work-orders/auto-assign/preview/]
                    │
   ├── (1) Lọc Work Order chờ gán: LOẠI TRỪ các phiếu bị chặn (Task Dependency)
   ├── (2) Phân rã phiếu tổ đội nhiều thợ (Crew Task Slot Decomposition)
   ├── (3) Lọc Kỹ thuật viên sẵn sàng trong ca
   ├── (4) Xây dựng ma trận chi phí C_ij (áp Priority Multiplier, Zone & Shift penalty)
   ├── (5) Bổ sung hàng/cột ảo (Dummy Padding) cân bằng ma trận vuông
   ├── (6) Giải nghiệm tối ưu bằng scipy.optimize.linear_sum_assignment
   └── (7) Quét xung đột công cụ dùng chung (Shared Tool Bottleneck Detection)
                    │
                    ▼
[Giao Diện Modal Hiển Thị Ma Trận Giải Trình]
   ├── Hiển thị bảng ma trận chi phí trực quan và các cặp tối ưu được chọn
   ├── Hiển thị thẻ cảnh báo màu cam nếu có xung đột công cụ dùng chung
   ├── Cho phép Quản lý điều chỉnh thủ công nếu cần
                    │
                    ▼
[Quản Lý Bấm: "Xác Nhận & Phân Công Ngay"]
                    │
                    ▼
[POST /api/v1/work-orders/auto-assign/apply/]
   ├── Bật khóa giao dịch select_for_update chống race condition
   ├── Cập nhật assigned_to, chuyển trạng thái sang ASSIGNED
   └── Kích hoạt thông báo thời gian thực (Task 10.1) đến từng kỹ thuật viên
```

---

## 5. Quy Tắc Bảo Mật, Phân Quyền & Đa Khách Hàng (Security, RBAC & Multi-Tenant Rules)

- **Cô Lập Đa Khách Hàng (Multi-Tenancy)**: Ma trận chi phí chỉ được xây dựng trên tập dữ liệu kỹ thuật viên, phiếu công việc và công cụ có cùng `tenant_id`. Không để lọt dữ liệu chéo giữa các tổ chức.
- **Phân Quyền Vai Trò (RBAC)**:
  - Chỉ người dùng có vai trò `MAINTENANCE_MANAGER` hoặc `TENANT_ADMIN` mới có quyền truy cập endpoint tính toán và xác nhận phân công.
  - Kỹ thuật viên thông thường (`TECHNICIAN`) chỉ nhận thông báo khi được giao việc.

---

## 6. Mô Hình Dữ Liệu & Thực Thể (Data Model & Schema)

### 6.1. Hồ Sơ Kỹ Thuật Viên (`technician_profiles`)
- `user_id`: `UUID` (Foreign Key tới `User`).
- `tenant_id`: `UUID` (Foreign Key tới `Tenant`).
- `skills`: `JSONB` (Mảng kỹ năng: `["MECHANICAL", "ELECTRICAL", "AUTOMATION"]`).
- `skill_level`: `SMALLINT` (Bậc thợ từ 1 đến 5).
- `certifications`: `JSONB` (Mảng mã chứng chỉ an toàn hợp lệ).
- `coords_x`, `coords_y`: `FLOAT` (Tọa độ mặt bằng trong xưởng).
- `floor_level`: `SMALLINT` (Tầng làm việc hiện tại, mặc định 1).
- `zone_id`: `VARCHAR(64)` (Mã khu vực, ví dụ: `ZONE_CLEANROOM_01`, `ZONE_MACHINING_A`).
- `shift_end_time`: `TIMESTAMP WITH TIME ZONE` (Thời điểm kết thúc ca trực hiện tại).
- `monthly_accumulated_hours`: `DECIMAL(8, 2)` (Tổng giờ công tích lũy trong tháng phục vụ tie-breaking).
- `is_on_duty`: `BOOLEAN` (Trạng thái đang trong ca trực).
- `availability_status`: `VARCHAR(20)` (`AVAILABLE`, `BUSY`, `ON_LEAVE`).

### 6.2. Phiếu Công Việc (`work_orders`)
- `required_skill`: `VARCHAR(64)` (Kỹ năng chuyên môn bắt buộc).
- `min_skill_level`: `SMALLINT` (Bậc thợ tối thiểu yêu cầu).
- `required_certification`: `VARCHAR(100)` (Chứng chỉ an toàn bắt buộc, `null=True`).
- `priority`: `VARCHAR(16)` (`LOW`, `MEDIUM`, `HIGH`, `URGENT`).
- `estimated_duration_hours`: `DECIMAL(5, 2)` (Thời gian dự kiến thực hiện, ví dụ 2.5 giờ).
- `required_tools`: `JSONB` (Mảng mã dụng cụ cần thiết, ví dụ: `["TOOL_THERMAL_CAM_01"]`).
- `depends_on_wo_id`: `UUID` (Foreign Key tới `WorkOrder` tiên quyết, `null=True`).
- `is_crew_task`: `BOOLEAN` (Cờ công việc yêu cầu tổ đội nhiều người, `default=False`).
- `coords_x`, `coords_y`, `floor_level`, `zone_id`: Kế thừa từ thiết bị liên kết.

---

## 7. Đặc Tả Giao Diện Lập Trình (API Specifications & Contracts)

### 7.1. `POST /api/v1/work-orders/auto-assign/preview/`
Tính toán phương án phân công tối ưu và trả về ma trận chi phí giải trình kèm cảnh báo xung đột công cụ.

**Request Body**:
```json
{
  "workOrderIds": ["wo-uuid-101", "wo-uuid-102", "wo-uuid-103"]
}
```

**Response**:
```json
{
  "success": true,
  "data": {
    "totalOptimalCost": 64.2,
    "assignmentsCount": 2,
    "unassignedCount": 1,
    "assignments": [
      {
        "technicianId": "tech-uuid-001",
        "technicianName": "Nguyễn Văn An",
        "workOrderId": "wo-uuid-101",
        "workOrderCode": "WO-2026-088",
        "priority": "URGENT",
        "cost": 18.5,
        "breakdown": {
          "distanceScore": 12.0,
          "skillScore": 0.0,
          "workloadScore": 0.0,
          "priorityMultiplier": 2.5,
          "zonePenalty": 0.0,
          "shiftPenalty": 0.0
        },
        "explanation": "Việc URGENT (hệ số x2.5). Khoảng cách 15m, đúng bậc thợ Cơ khí, cùng Phân xưởng A, đủ thời gian ca trực."
      },
      {
        "technicianId": "tech-uuid-002",
        "technicianName": "Trần Minh Đức",
        "workOrderId": "wo-uuid-102",
        "workOrderCode": "WO-2026-089",
        "priority": "HIGH",
        "cost": 45.7,
        "breakdown": {
          "distanceScore": 35.0,
          "skillScore": 5.0,
          "workloadScore": 25.0,
          "priorityMultiplier": 1.8,
          "zonePenalty": 0.0,
          "shiftPenalty": 0.0
        },
        "explanation": "Việc HIGH (hệ số x1.8). Khoảng cách 45m, đúng chuyên môn Điện, đang có 1 việc nhẹ dở dang."
      }
    ],
    "sharedToolConflicts": [
      {
        "toolCode": "TOOL_THERMAL_CAM_01",
        "toolName": "Camera nhiệt Fluke Ti480",
        "availableQuantity": 1,
        "conflictingWorkOrders": ["WO-2026-088", "WO-2026-089"],
        "warningMessage": "Cả 2 phiếu đều yêu cầu Camera nhiệt chuyên dụng (chỉ có 1 chiếc trong kho). Đề xuất lùi giờ thực hiện của WO-2026-089."
      }
    ],
    "matrixHeader": {
      "technicians": ["Nguyễn Văn An", "Trần Minh Đức"],
      "workOrders": ["WO-2026-088", "WO-2026-089", "WO-2026-090 (Blocked)"]
    },
    "costMatrix": [
      [18.5, 62.0],
      [75.0, 45.7]
    ]
  }
}
```

### 7.2. `POST /api/v1/work-orders/auto-assign/apply/`
Chính thức áp dụng phân công công việc vào cơ sở dữ liệu với khóa dòng dữ liệu (`select_for_update`).

**Request Body**:
```json
{
  "assignments": [
    { "workOrderId": "wo-uuid-101", "technicianId": "tech-uuid-001" },
    { "workOrderId": "wo-uuid-102", "technicianId": "tech-uuid-002" }
  ]
}
```

**Response Thành Công (200 OK)**:
```json
{
  "success": true,
  "data": {
    "assignedCount": 2,
    "message": "Phân công công việc tối ưu thành công. Đã gửi thông báo cho các kỹ thuật viên."
  }
}
```

**Response Khi Có Tranh Chấp Đồng Thời (409 Conflict)**:
```json
{
  "success": false,
  "error": {
    "code": "CONCURRENT_DISPATCH_CONFLICT",
    "message": "Kỹ thuật viên Nguyễn Văn An vừa được phân công ở một phiên khác. Vui lòng tải lại phương án phân công mới."
  }
}
```

---

## 8. Đặc Tả Trải Nghiệm Người Dùng (UI/UX Behavioral Specifications)

- **Cửa sổ xem trước giải trình (Explainable Preview Modal)**:
  - **Bảng ma trận tương tác trực quan**: Hiển thị bảng chi phí đa chiều, tô đậm các ô được thuật toán chọn.
  - **Thẻ cảnh báo màu cam (Shared Tool Conflict Banner)**: Khi có xung đột thiết bị dùng chung, hiển thị banner cảnh báo nổi bật ở đầu modal kèm gợi ý điều chỉnh giờ.
  - **Cột giải trình chi tiết (Explainable Breakdown Tooltip)**: Khi rê chuột vào ô chi phí, tooltip hiển thị chi tiết điểm khoảng cách, chênh lệch bậc thợ, hệ số ưu tiên, phạt khu vực và phạt ca trực.
  - **Quyền can thiệp thủ công (Manual Override)**: Cho phép Quản lý đổi thợ trực tiếp trên dropdown của từng dòng trước khi nhấn nút "Xác Nhận & Áp Dụng".

---

## 9. Tiêu Chí Chấp Nhận & Ma Trận Kịch Bản Kiểm Thử (Acceptance Criteria & Test Matrix)

Dưới đây là bảng ma trận kiểm thử chi tiết hóa toàn bộ 12 kịch bản chấp nhận và trường hợp biên (Edge Cases):

### 9.1. Ma Trận Kịch Bản Nghiệp Vụ & Thuật Toán Tối Ưu

- [ ] **TC-HUNGARY-01: Ma trận vuông cân bằng ($N = M$)**
  - *Mô tả*: 3 thợ và 3 việc với chi phí xác định.
  - *Kỳ vọng*: Thuật toán tìm ra phương án phân công có tổng chi phí nhỏ nhất đúng 100% so với giải pháp toán học Kuhn-Munkres.

- [ ] **TC-HUNGARY-02: Điểm ưu tiên phát huy tác dụng nhờ Hệ số nhân (Priority Multiplier)**
  - *Mô tả*: Việc 1 là `URGENT` (Multiplier $\times 2.5$), Việc 2 là `LOW` (Multiplier $\times 1.0$). Thợ A gần Việc 1 (10m) và Thợ B xa hơn một chút (30m).
  - *Kỳ vọng*: Hệ thống ép buộc Thợ A phải nhận Việc 1 (URGENT), không để Thợ B làm Việc 1. Khắc phục triệt để lỗ hổng vô hiệu hóa của phép trừ hằng số.

- [ ] **TC-HUNGARY-03: Rào cản không gian và khu vực cách ly (Zone Transition Penalty)**
  - *Mô tả*: Thợ A ở trong Phòng Sạch (Cleanroom) cách Máy 1 chỉ 10m. Thợ B ở xưởng thường cách Máy 1 40m. Máy 1 nằm ở xưởng thường.
  - *Kỳ vọng*: Thợ A bị cộng thêm $40$ điểm phạt chuyển vùng ($\text{Pen}_{\text{zone}}$); thuật toán quyết định gán Thợ B đi làm để tránh việc Thợ A phải tốn 30 phút thay đồ bảo hộ và khử khuẩn.

- [ ] **TC-HUNGARY-04: Xung đột thời gian giao ca (Shift Handover Clash)**
  - *Mô tả*: Thợ A còn 30 phút là hết ca. Thợ B vừa vào ca còn 7.5 tiếng. Work Order yêu cầu thời gian dự kiến 3 tiếng.
  - *Kỳ vọng*: Thợ A bị cộng $40$ điểm phạt $\text{Pen}_{\text{shift}}$; thuật toán gán cho Thợ B để tránh tăng ca ngoài ý muốn.

- [ ] **TC-HUNGARY-05: Nhận diện xung đột công cụ dùng chung (Shared Tool Bottleneck)**
  - *Mô tả*: WO 1 và WO 2 cùng yêu cầu `TOOL_THERMAL_CAM_01` (toàn xưởng chỉ có 1 cái). Cả 2 phiếu đều được gán cho 2 thợ trong cùng đợt điều phối.
  - *Kỳ vọng*: Thuật toán phát hiện xung đột và trả về mảng `sharedToolConflicts`; giao diện Modal hiển thị cảnh báo màu cam rõ ràng cho Quản lý.

- [ ] **TC-HUNGARY-06: Lọc bỏ công việc bị phụ thuộc (Task Dependency Filtering)**
  - *Mô tả*: WO 2 phụ thuộc vào WO 1 (`depends_on_wo_id = WO-1`). Hiện tại WO 1 đang ở trạng thái `IN_PROGRESS` (chưa hoàn thành).
  - *Kỳ vọng*: WO 2 bị tự động loại bỏ khỏi tập đầu vào của ma trận Hungarian đợt này, không bị gán sớm cho bất kỳ ai.

- [ ] **TC-HUNGARY-07: Phân rã công việc tổ đội nhiều thợ (Crew Task Slot)**
  - *Mô tả*: Phiếu WO 3 yêu cầu 1 thợ chính Bậc $\ge 4$ và 1 thợ phụ Bậc $\ge 2$ (`is_crew_task = True`).
  - *Kỳ vọng*: Ma trận Hungarian tự động tạo 2 cột nhiệm vụ: `WO-3-Lead` và `WO-3-Assistant`, gán thành công cho 2 kỹ thuật viên khác nhau thỏa mãn bậc thợ.

- [ ] **TC-HUNGARY-08: Ràng buộc chứng chỉ an toàn tuyệt đối (Big-M Penalty)**
  - *Mô tả*: Phiếu sửa biến áp cao thế yêu cầu chứng chỉ `CERT_HIGH_VOLTAGE`. Thợ 1 ở cách 5m nhưng không có chứng chỉ; Thợ 2 ở cách 100m có chứng chỉ.
  - *Kỳ vọng*: Thợ 1 nhận chi phí phạt $10^7$; hệ thống tuyệt đối không gán Thợ 1, bắt buộc gán Thợ 2.

- [ ] **TC-HUNGARY-09: Phá vỡ thế hòa điểm số công bằng (Deterministic Tie-Breaking)**
  - *Mô tả*: Thợ 1 và Thợ 2 có điểm số chi phí bằng hệt nhau đối với WO 1. Thợ 1 đã tích lũy 160 giờ công trong tháng, Thợ 2 mới tích lũy 120 giờ công.
  - *Kỳ vọng*: Thuật toán luôn luôn ưu tiên gán cho Thợ 2 để đảm bảo công bằng thu nhập và san sẻ khối lượng công việc trong đội ngũ.

### 9.2. Ma Trận Kịch Bản Kỹ Thuật, Cạnh Tranh & Đa Khách Hàng

- [ ] **TC-HUNGARY-10: Khóa chống tranh chấp phân công đồng thời (Concurrency Conflict)**
  - *Mô tả*: 2 Quản lý cùng mở modal phân công. Quản lý 1 bấm xác nhận gán Thợ An. Sau đó 1 giây, Quản lý 2 bấm xác nhận gán Thợ An cho việc khác.
  - *Kỳ vọng*: Giao dịch của Quản lý 2 bị chặn lại bởi `select_for_update`, trả về HTTP 409 Conflict với thông báo dữ liệu thợ đã thay đổi, bảo vệ toàn vẹn dữ liệu.

- [ ] **TC-HUNGARY-11: Cân bằng ma trận khi dư thợ hoặc thiếu thợ (Dummy Padding)**
  - *Mô tả*: 5 thợ nhưng chỉ có 2 việc (hoặc 2 thợ nhưng có 5 việc).
  - *Kỳ vọng*: Kỹ thuật đệm node ảo hoạt động trơn tru; không phát sinh lỗi lệch ma trận không vuông; thợ dư thừa được đưa vào trạng thái Standby.

- [ ] **TC-HUNGARY-12: Cách ly tuyệt đối đa khách hàng (Multi-Tenant Isolation)**
  - *Mô tả*: Tenant A và Tenant B cùng kích hoạt phân công tự động.
  - *Kỳ vọng*: Thợ và việc của Tenant A tuyệt đối không xuất hiện trong ma trận chi phí của Tenant B.

---

## 10. Implementation Notes — For Implementation Phase Only

> [!IMPORTANT]
> **REFERENCE ONLY — DO NOT IMPLEMENT OR MODIFY CODE BASED ON THIS SECTION DURING SPEC REVIEW. These notes are intended for the implementation phase after the specification is approved.**

Phần này lưu trữ các chỉ dẫn kỹ thuật hạ tầng chi tiết để các kỹ sư tham khảo trong quá trình triển khai mã nguồn:

### 10.1. Tích Hợp Thư Viện SciPy Linear Sum Assignment
```python
import numpy as np
from scipy.optimize import linear_sum_assignment

def solve_hungarian_assignment(cost_matrix: np.ndarray):
    """
    cost_matrix: Ma trận vuông K x K đã được đệm dummy
    Trả về danh sách các cặp (row_idx, col_idx) tối ưu toàn cục
    """
    row_ind, col_ind = linear_sum_assignment(cost_matrix)
    return list(zip(row_ind, col_ind))
```

### 10.2. Thuật Toán Phát Hiện Xung Đột Công Cụ Dùng Chung
```python
from collections import defaultdict

def detect_shared_tool_conflicts(assignments, work_orders_map):
    tool_usage = defaultdict(list)
    for tech_id, wo_id in assignments:
        wo = work_orders_map.get(wo_id)
        if wo and wo.required_tools:
            for tool_code in wo.required_tools:
                tool_usage[tool_code].append(wo.code)
                
    conflicts = []
    for tool_code, wo_codes in tool_usage.items():
        if len(wo_codes) > 1:
            # Kiểm tra tồn kho khả dụng của tool
            tool = Tool.objects.filter(code=tool_code).first()
            if tool and tool.available_quantity < len(wo_codes):
                conflicts.append({
                    "toolCode": tool_code,
                    "toolName": tool.name,
                    "availableQuantity": tool.available_quantity,
                    "conflictingWorkOrders": wo_codes,
                    "warningMessage": f"Xung đột công cụ {tool.name}: Cần {len(wo_codes)} nhưng chỉ có {tool.available_quantity} khả dụng."
                })
    return conflicts
```

### 10.3. Cơ Chế Khóa Lạc Quan & Database Lock Khi Xác Nhận Phân Công
```python
from django.db import transaction

@transaction.atomic
def apply_assignments(tenant, assignment_pairs):
    tech_ids = [p['technicianId'] for p in assignment_pairs]
    wo_ids = [p['workOrderId'] for p in assignment_pairs]
    
    # Khóa các dòng dữ liệu để chống tranh chấp đồng thời
    techs = list(TechnicianProfile.objects.select_for_update().filter(tenant=tenant, user_id__in=tech_ids))
    work_orders = list(WorkOrder.objects.select_for_update().filter(tenant=tenant, id__in=wo_ids))
    
    # Kiểm tra trạng thái thợ còn rảnh không
    for tech in techs:
        if tech.availability_status != 'AVAILABLE':
            raise ConcurrentDispatchConflictException(f"Kỹ thuật viên {tech.user.get_full_name()} đã bị gán ở phiên khác.")
            
    # Tiến hành cập nhật
    for p in assignment_pairs:
        WorkOrder.objects.filter(id=p['workOrderId']).update(
            assigned_to_id=p['technicianId'],
            status='ASSIGNED'
        )
        TechnicianProfile.objects.filter(user_id=p['technicianId']).update(
            availability_status='BUSY'
        )
```

---

## 11. Kế Hoạch Triển Khai & Nghiệm Thu (Implementation Checklist)

- [ ] **Task 11.1.1 — Multi-Factor Cost Matrix Service with Multiplier & Penalties**
  - [ ] Cài đặt công thức ma trận chi phí mới với `Priority_Multiplier` dạng nhân.
  - [ ] Tích hợp tính khoảng cách đa tầng Manhattan ($D_{ij}$) và điểm phạt rào cản khu vực/phòng sạch ($\text{Pen}_{\text{zone}}$).
  - [ ] Tích hợp điểm phạt xung đột ca trực ($\text{Pen}_{\text{shift}}$) và phạt gián đoạn việc dở dang ($\text{Pen}_{\text{disrupt}}$).
  - [ ] Áp dụng cơ chế phạt Big-M ($10^7$) cho vi phạm chứng chỉ chuyên môn an toàn.
- [ ] **Task 11.1.2 — Pre-processing & Post-processing Engines**
  - [ ] Xây dựng bộ lọc loại bỏ các phiếu bị chặn do phụ thuộc (`depends_on_wo_id`).
  - [ ] Xây dựng bộ phân rã công việc tổ đội nhiều thợ (`is_crew_task`).
  - [ ] Xây dựng bộ phát hiện xung đột công cụ dùng chung sau khi giải nghiệm.
  - [ ] Cơ chế đệm node ảo (Zero-Cost Dummy Padding) và Tie-breaking xác định dựa trên số giờ công tích lũy trong tháng.
- [ ] **Task 11.1.3 — Core Hungarian Solver Integration**
  - [ ] Tích hợp thư viện `scipy.optimize.linear_sum_assignment`.
  - [ ] Tối ưu hóa chuyển đổi ma trận NumPy và trích xuất cặp tối ưu.
- [ ] **Task 11.1.4 — Auto-Assignment REST APIs with Concurrency Locking**
  - [ ] Endpoint xem trước giải trình: `POST /api/v1/work-orders/auto-assign/preview/`.
  - [ ] Endpoint áp dụng phân công chính thức: `POST /api/v1/work-orders/auto-assign/apply/` kèm khóa `select_for_update`.
  - [ ] Tích hợp thông báo Real-time (Task 10.1) sau khi phân công thành công.
- [ ] **Task 11.1.5 — Web Portal UI Integration & Explainable Modal**
  - [ ] Thêm nút thao tác "Phân công tối ưu (Hungary)" trên giao diện danh sách Work Orders.
  - [ ] Thiết kế Modal hiển thị ma trận giải trình, tooltip bóc tách chi phí và banner cảnh báo xung đột công cụ màu cam.
  - [ ] Hỗ trợ Quản lý điều chỉnh thợ thủ công (Manual Override) trước khi xác nhận.
- [ ] **Task 11.1.6 — Verification & Testing Suite**
  - [ ] Viết test cases kiểm thử đầy đủ 12 kịch bản chấp nhận và trường hợp biên (`TC-HUNGARY-01` đến `TC-HUNGARY-12`).

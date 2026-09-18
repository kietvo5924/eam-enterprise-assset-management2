# Thiết Kế Hệ Thống & Đặc Tả Kỹ Thuật: Task 11.3 — Technician Routing Optimization (Traveling Salesperson Problem - TSP)

Tài liệu này xác định cơ sở toán học, mô hình định vị 3 tầng (từ bản đồ 2D/GPS đến mô hình tô-pô phân cấp phi bản đồ cho trường học/văn phòng), giải thuật định tuyến bất đối xứng (Asymmetric TSP), ràng buộc khung giờ (TSPTW), cơ chế phân lớp khẩn cấp (Tiered TSP), trạm dừng tiếp vận và **bộ kịch bản kiểm thử chấp nhận & trường hợp biên (Acceptance Criteria & Edge Cases)** cho bài toán **Tối Ưu Hóa Lộ Trình Di Chuyển Của Kỹ Thuật Viên (Technician Routing Optimization - TSP)** trong hệ thống Quản lý Tài sản Doanh nghiệp (EAM).

Tài liệu đóng vai trò là **Đặc Tả Kỹ Thuật & Chuẩn Kiểm Thử (Technical Specification & Audit Baseline)** nhằm đối chiếu, rà soát và thực thi trọn vẹn toàn bộ tính năng mà không bị thiếu sót bất kỳ nghiệp vụ enterprise nào.

---

## 1. Mục Tiêu & Phạm Vi (Objective & Scope)

### 1.1. Vị Trí Của TSP Trong Chuỗi Tối Ưu Hóa EAM (The 3-Stage Optimization Pipeline)
Hệ thống điều phối bảo trì thông minh của EAM hoạt động theo chuỗi 3 bước khép kín:
1. **Bước 1 (Lập lịch đầu ca - Task 11.2 GA)**: Phân bổ danh mục công việc trong ngày cho các kỹ thuật viên. Kết quả trả lời câu hỏi: *"Ai làm việc gì trong ca?"*.
2. **Bước 2 (Tối ưu hóa lộ trình - Task 11.3 TSP)**: Sắp xếp thứ tự di chuyển qua các điểm máy móc/phòng ban của từng kỹ thuật viên để giảm thiểu quãng đường và thời gian đi bộ. Kết quả trả lời câu hỏi: *"Làm việc theo thứ tự nào để đi lại ít nhất và đúng giờ nhất?"*.
3. **Bước 3 (Điều phối tức thời - Task 11.1 Hungarian)**: Khi có sự cố máy dừng đột xuất giữa ca, điều động kỹ thuật viên phù hợp nhất đến ứng cứu và kích hoạt tái định tuyến động.

### 1.2. Thích Ứng Mọi Quy Mô Doanh Nghiệp & Môi Trường Phi Bản Đồ (Universality)
- **Nhà máy công nghiệp lớn**: Tối ưu quãng đường theo sơ đồ mặt bằng 2D hoặc tọa độ GPS ngoài trời, hỗ trợ luồng di chuyển 1 chiều.
- **Trường học, Bệnh viện, Tòa nhà văn phòng**: **Hoàn toàn không cần bản đồ số**. Tự động tối ưu hóa theo **Cây phân cấp logic (Tòa nhà $\rightarrow$ Tầng $\rightarrow$ Phòng)** để gom việc cùng phòng/tầng, triệt tiêu việc kỹ thuật viên leo cầu thang lên xuống nhiều lần.
- **Tài sản di động, không cố định (Bàn, ghế, máy chiếu di động)**: Định tuyến theo **Vị trí phát sinh sự cố trên Work Order** chứ không phụ thuộc vào vị trí danh nghĩa của tài sản.

---

## 2. Ràng Buộc Kế Thừa Hệ Thống (Existing System Constraints & Codebase Reuse)

- **Tái Sử Dụng Mô Hình Multi-Tenancy**: Toàn bộ dữ liệu vị trí, danh sách Work Order và cấu hình lộ trình phải được cô lập tuyệt đối theo `tenant_id` qua `TenantManager`.
- **Tái Sử Dụng Thực Thể Nghiệp Vụ Có Sẵn**:
  - `Location`: Cấu trúc cây phân cấp (`parent_id`, `type`: `SITE`, `BUILDING`, `FLOOR`, `ROOM`), ảnh sơ đồ 2D (nếu có).
  - `Asset`: Tọa độ $(X, Y)$ (nếu có), vị trí hiện tại (`current_location_id`).
  - `WorkOrder`: Vị trí sự cố (`incident_location_id`), mức độ ưu tiên (`priority`), khung thời gian cho phép dừng máy (`maintenance_window_start`, `maintenance_window_end`).

---

## 3. Yêu Cầu Nghiệp Vụ & Quy Tắc Cốt Lõi (Business Requirements & Core Rules)

Toàn bộ logic tối ưu hóa lộ trình phải tuân thủ nghiêm ngặt 11 quy tắc nghiệp vụ phòng thủ sau:

### Quy Tắc 1: Định Tuyến Tô-Pô Phân Cấp Cho Doanh Nghiệp Không Có Bản Đồ (Topological Hierarchical Routing)
- **Điểm Yếu Nghiệp Vụ**: Hầu hết trường học, bệnh viện và văn phòng không có bản đồ CAD hay hệ thống định vị đắt tiền. Nếu ép buộc phải có tọa độ $(X, Y)$ thì tính năng định tuyến sẽ bị tê liệt hoàn toàn.
- **Quy Tắc Bắt Buộc**:
  1. Khi hệ thống không có dữ liệu tọa độ phẳng $(X, Y)$, tự động kích hoạt chế độ **Định tuyến Tô-pô Phân cấp (Hierarchical Topological Routing)** dựa trên cây danh mục vị trí:
     $$\text{Cơ sở (Site)} \longrightarrow \text{Tòa nhà (Building)} \longrightarrow \text{Tầng (Floor)} \longrightarrow \text{Phòng (Room)}$$
  2. Ma trận khoảng cách bậc thang được tính toán tự động:
     - Cùng phòng: Chi phí $= 1$ điểm.
     - Cùng tầng, khác phòng: Chi phí $= 10$ điểm (đi dọc hành lang).
     - Cùng tòa nhà, khác tầng: Chi phí $= 10 + 30 \times |\Delta \text{tầng}|$ (chi phí leo cầu thang/thang máy).
     - Khác tòa nhà: Chi phí $= 150$ điểm (đi bộ qua sân trường/khuôn viên).
  3. Thuật toán TSP chạy trên ma trận bậc thang này bảo đảm gom việc tối ưu: Làm xong hết việc trong phòng $\rightarrow$ Chuyển các phòng cùng tầng $\rightarrow$ Chuyển tầng khác $\rightarrow$ Chuyển tòa nhà khác.

### Quy Tắc 2: Xử Lý Tài Sản Di Động Không Có Vị Trí Cố Định (Movable Assets & Incident Location Context)
- **Điểm Yếu Nghiệp Vụ**: Bàn, ghế, quạt cây, máy chiếu di động ở trường học bị chuyển từ phòng này sang phòng khác liên tục. Nếu lấy vị trí gốc trong hồ sơ tài sản (ví dụ Phòng 101), thợ sẽ đến nhầm phòng trong khi cái bàn đang bị hỏng ở Phòng 204.
- **Quy Tắc Bắt Buộc**:
  1. **Lộ trình TSP bắt buộc lấy vị trí phát sinh sự cố trên phiếu công việc (`work_order.incident_location_id`)** làm điểm đến của chặng, tuyệt đối không lấy vị trí danh nghĩa trong hồ sơ tài sản.
  2. **Tài sản không rõ vị trí (Floating Assets)**: Nếu phiếu không ghi rõ phòng, xếp vào danh sách "Điểm dừng linh hoạt", hiển thị ở cuối lộ trình hoặc cho phép xử lý tiện thể trên đường đi.
  3. **Quét QR cập nhật vị trí (Scan-to-Relocate)**: Khi kỹ thuật viên đến sửa và quét mã QR của tài sản, ứng dụng di động tự động hỏi để cập nhật vị trí thực tế mới nhất vào hồ sơ thiết bị.

### Quy Tắc 3: Phân Lớp Khẩn Cấp Cho Cụm Nhiều Việc URGENT (Tiered TSP for Multi-Urgent Cluster)
- **Điểm Yếu Nghiệp Vụ**: Đầu ca phát sinh đồng thời 3 sự cố `URGENT` ở 3 góc khác nhau của nhà máy. Nếu chỉ "đưa việc khẩn cấp lên đầu" chung chung, thuật toán không biết thứ tự tối ưu giữa 3 điểm này thế nào, dẫn đến thợ chạy lòng vòng giữa các điểm khẩn cấp.
- **Quy Tắc Bắt Buộc**:
  1. Áp dụng kỹ thuật **Phân Lớp Khẩn Cấp (Tiered TSP)**:
     - *Lớp 1 (Cụm Khẩn cấp)*: Lấy điểm xuất phát $v_0$, giải TSP cục bộ qua riêng 3 điểm `URGENT` để tìm đường đi ngắn nhất: $v_0 \rightarrow u_1 \rightarrow u_2 \rightarrow u_3$.
     - *Lớp 2 (Cụm Bình thường)*: Lấy điểm khẩn cấp cuối cùng $u_3$ làm điểm xuất phát mới, giải tiếp TSP cho các điểm bảo trì thông thường còn lại.
  2. Ghép 2 chuỗi thành lộ trình tổng thể: Vừa dứt điểm toàn bộ sự cố khẩn cấp sớm nhất, vừa tối ưu quãng đường cho nửa sau ca trực.

### Quy Tắc 4: Ràng Buộc Khung Thời Gian Cho Phép Dừng Máy (TSP with Time Windows - TSPTW)
- **Điểm Yếu Nghiệp Vụ**: Máy dập liên tục chỉ cho phép ngắt điện bảo dưỡng vào giờ nghỉ trưa (12:00 - 13:00). Nếu chỉ tối ưu quãng đường, thợ đến lúc 9:00 sáng thì máy đang chạy sản xuất, thợ không thể làm việc.
- **Quy Tắc Bắt Buộc**:
  1. Mỗi Work Order hỗ trợ khung thời gian bảo trì cho phép: $[e_j, l_j]$.
  2. Nếu thợ đến sớm ($t < e_j$): Chịu thời gian chờ (Waiting time).
  3. Nếu thợ đến trễ ($t > l_j$): Áp dụng điểm phạt vi phạm khung giờ (Time Window Penalty) cực lớn, ép thuật toán đảo thứ tự trạm dừng để thợ ghé thăm máy đúng khung giờ cho phép dừng.

### Quy Tắc 5: Ma Trận Bất Đối Xứng Do Lối Đi 1 Chiều (Asymmetric TSP - ATSP)
- **Điểm Yếu Nghiệp Vụ**: Trong nhà xưởng có hành lang 1 chiều dành cho xe tự hành (AGV), cửa từ an ninh chỉ cho quẹt thẻ đi ra, hoặc phòng sạch có luồng thổi khí vào và ra tách biệt. Khoảng cách $D(A, B) \ne D(B, A)$.
- **Quy Tắc Bắt Buộc**:
  1. Mô hình ma trận khoảng cách hỗ trợ đồ thị có hướng bất đối xứng (Asymmetric Matrix).
  2. Sử dụng giải thuật cải tiến cục bộ **Or-opt / Relocate Move** (nhấc trạm dừng ra chèn vào vị trí khác mà không lật ngược chiều các đoạn đường 1 chiều).

### Quy Tắc 6: Trạm Dừng Tiếp Vận Về Kho Lấy Vật Tư Giữa Ca (Intermediate Pit-Stops)
- **Điểm Yếu Nghiệp Vụ**: Kỹ thuật viên không thể mang vác 100kg vật tư cồng kềnh qua 10 máy cùng lúc. Sau khi sửa xong 3 máy đầu tiên, thợ hết sạch phụ tùng.
- **Quy Tắc Bắt Buộc**:
  1. Cho phép chèn **Trạm dừng tiếp vận (Intermediate Pit-stops)** vào lộ trình.
  2. Kỹ thuật viên có quyền bấm nút *"Về kho lấy vật tư"* trên app di động. Hệ thống lập tức bẻ gãy lộ trình: chèn điểm Kho vật tư ($v_{\text{depot}}$) vào ngay sau máy hiện tại và tự động tái định tuyến cho các điểm còn lại.

### Quy Tắc 7: Tái Định Tuyến Động Giữa Ca Từ Vị Trí Hiện Tại (Dynamic Mid-Shift Re-routing)
- **Điểm Yếu Nghiệp Vụ**: Thợ đang sửa ở trạm 2 (trong 6 trạm) thì phát sinh 1 sự cố khẩn cấp mới. Lộ trình tính từ sáng đã bị vô hiệu.
- **Quy Tắc Bắt Buộc**:
  1. Endpoint `/api/v1/routing/re-route-mid-shift/` lấy **Vị trí hiện tại của thợ (Current Location của trạm 2) làm điểm bắt đầu $v_0$ mới**.
  2. Chỉ gom các phiếu chưa hoàn thành (`status != 'COMPLETED'`) và phiếu mới thêm để giải lại lộ trình tối ưu cho nửa ca còn lại, không tính lại từ Kho xuất phát ban đầu.

### Quy Tắc 8: Chi Phí Chênh Lệch Tầng Lầu & Cầu Thang (Multi-Floor Vertical Penalty)
- **Điểm Yếu Nghiệp Vụ**: Leo 3 tầng cầu thang bộ hoặc chờ thang máy chở hàng mất 5–10 phút, tốn sức gấp nhiều lần đi bộ 50m trên mặt phẳng.
- **Quy Tắc Bắt Buộc**:
  - Ma trận khoảng cách tự động cộng thêm chi phí di chuyển thẳng đứng:
    $$D(A, B) = d_{\text{horizontal}} + 50\text{m} \times |\text{Floor}_A - \text{Floor}_B| + T_{\text{elevator}}$$
  - Thuật toán tự động gom các công việc cùng tầng làm xong hết trước khi chuyển tầng.

### Quy Tắc 9: Bộ Đệm Ngoại Tuyến Trên Mobile (Offline Mobile Route Cache)
- **Điểm Yếu Nghiệp Vụ**: Trong phòng máy kín, tầng hầm hoặc góc xa của khuôn viên trường học, điện thoại bị mất sóng 4G/Wi-Fi.
- **Quy Tắc Bắt Buộc**:
  - Toàn bộ danh sách trạm dừng, thứ tự chặng và hướng dẫn di chuyển được lưu đệm cục bộ trên SQLite/Local Storage của ứng dụng di động. Thợ vẫn xem được lộ trình bình thường khi ngoại tuyến.

### Quy Tắc 10: Chế Độ Chu Trình Đóng vs Đường Đi Mở (Closed vs Open Loop)
- **Quy Tắc Bắt Buộc**:
  - `return_to_depot = True`: Kỹ thuật viên cần quay về phòng bảo trì để trả dụng cụ và bàn giao sổ nhật ký.
  - `return_to_depot = False`: Kỹ thuật viên kết thúc ca làm việc trực tiếp tại hiện trường và ra về ngay.

### Quy Tắc 11: Cờ Bật/Tắt Module Theo Gói Tenant & Dự Phòng Không Vị Trí (Tenant Feature Toggle & Zero-Location Fallback)
- **Điểm Yếu Nghiệp Vụ**: Nhiều doanh nghiệp vừa và nhỏ, trường học tư thục hoặc cơ sở bảo dưỡng quy mô nhỏ không muốn tốn chi phí đo đạc tọa độ, không muốn nhập liệu vị trí và không muốn trả thêm phí bản quyền cho module định tuyến nâng cao.
- **Quy Tắc Bắt Buộc**:
  1. Hỗ trợ cờ cấu hình linh hoạt cấp Tenant: `ENABLE_TSP_ROUTING` (mặc định có thể là `False` cho gói Basic / Tiết kiệm).
  2. **Hành vi khi tắt tính năng**:
     - Toàn bộ giao diện Web Portal và Mobile ẩn sạch các nút "Tối ưu lộ trình", bản đồ và các chỉ số khoảng cách di chuyển mét.
     - Phiếu công việc (`WorkOrder`) hoàn toàn không bắt buộc nhập `incident_location_id` hay tọa độ (cho phép `null=True`).
     - Khi kỹ thuật viên mở danh sách công việc trong ngày, API tự động chuyển sang chế độ **Sắp xếp theo Nghiệp vụ thuần túy (Pure Business Ordering)**: Ưu tiên mức độ khẩn cấp (`priority`: `URGENT` $\rightarrow$ `HIGH` $\rightarrow$ `MEDIUM` $\rightarrow$ `LOW`), sau đó đến Hạn chót sớm nhất (`due_date` ASC).
     - Tuyệt đối không tiêu tốn tài nguyên tính toán ma trận trên server, tiết kiệm 100% chi phí vận hành cho doanh nghiệp.

---

## 4. Yêu Cầu Chức Năng & Luồng Xử Lý (Functional Requirements & Workflows)

### 4.1. Kiến Trúc Ma Trận Khoảng Cách Đa Cấp Độ
Hệ thống tự động lựa chọn 1 trong 3 cơ chế tính khoảng cách tùy thuộc dữ liệu sẵn có của Tenant:

```
[Dữ Liệu Vị Trí Của Tenant]
          │
          ├── Có Tọa Độ Phẳng (X, Y) trên Sơ Đồ 2D ──► Dùng Khoảng Cách Manhattan Lưới (L1 Norm)
          │                                            d = |x1 - x2| + |y1 - y2| + Vertical Penalty
          │
          ├── Có Tọa Độ GPS Ngoài Trời ──► Dùng Công Thức Haversine Địa Lý Trắc Địa
          │
          └── KHÔNG CÓ BẢN ĐỒ (Trường học, Bệnh viện) ──► Tự Động Kích Hoạt Định Tuyến Tô-Pô Phân Cấp
                                                          Dựa trên Cây: Site ➔ Building ➔ Floor ➔ Room
```

---

### 4.2. Quy Trình Giải Lộ Trình Phân Lớp (Tiered ATSP Solver)

1. **Bước 1: Tách nhóm công việc**:
   - Nhóm $U$: Các phiếu mức độ `URGENT` / `EMERGENCY`.
   - Nhóm $N$: Các phiếu bảo trì thông thường.
2. **Bước 2: Giải Lớp Khẩn Cấp (Tier 1)**:
   - Nếu $|U| > 0$: Khởi tạo từ $v_0$, giải TSP qua các điểm trong $U$ bằng Nearest Neighbor + 2-Opt/Or-opt $\rightarrow$ Thu được chuỗi lộ trình $[v_0 \rightarrow u_1 \rightarrow \dots \rightarrow u_k]$.
   - Điểm xuất phát cho chặng tiếp theo là $v_{\text{start2}} = u_k$.
   - Nếu $|U| == 0$: $v_{\text{start2}} = v_0$.
3. **Bước 3: Giải Lớp Thông Thường Có Ràng Buộc Khung Giờ (Tier 2 - TSPTW)**:
   - Khởi tạo từ $v_{\text{start2}}$, duyệt qua các điểm trong $N$.
   - Áp dụng hàm đánh giá kết hợp quãng đường và phạt vi phạm khung giờ $[e_j, l_j]$.
   - Tối ưu hóa cục bộ bằng Or-opt Relocate Move để bảo toàn tính bất đối xứng của đường 1 chiều.
4. **Bước 4: Kết thúc lộ trình**:
   - Nếu `return_to_depot = True`: Nối chặng từ điểm cuối về $v_0$.
   - Trả về danh sách trạm dừng hoàn chỉnh.

---

## 5. Quy Tắc Bảo Mật, Phân Quyền & Đa Khách Hàng (Security, RBAC & Multi-Tenant Rules)

- **Cô Lập Đa Khách Hàng (Multi-Tenancy)**: Toàn bộ danh mục vị trí, máy móc và lộ trình thuộc cùng `tenant_id`. Không để lộ sơ đồ mặt bằng giữa các tổ chức.
- **Phân Quyền Vai Trò (RBAC)**:
  - `MAINTENANCE_MANAGER`: Quyền xem và tạo lộ trình cho mọi kỹ thuật viên trong xưởng/trường học.
  - `TECHNICIAN`: Xem lộ trình của bản thân, bấm "Về kho lấy vật tư" hoặc "Tái định tuyến động".

---

## 6. Mô Hình Dữ Liệu & Thực Thể (Data Model & Schema)

### 6.1. Bảng `locations` (Mở rộng cấu trúc cây phân cấp)
- `id`: `UUID` (Primary Key).
- `tenant_id`: `UUID` (Kế thừa `BaseTenantModel`).
- `parent_id`: `UUID` (Foreign Key tự trỏ tới `Location`, xác định cây phân cấp: Tòa nhà $\rightarrow$ Tầng $\rightarrow$ Phòng).
- `type`: `VARCHAR(20)` (`SITE`, `BUILDING`, `FLOOR`, `ROOM`, `WAREHOUSE`).
- `floor_number`: `SMALLINT` (Số tầng, ví dụ 1, 2, 3 phục vụ tính chi phí di chuyển thẳng đứng).
- `floorplan_image_url`: `VARCHAR(500)` (Ảnh sơ đồ 2D, `null=True`).
- `pixel_to_meter_ratio`: `FLOAT` (Tỷ lệ quy đổi pixel sang mét, `null=True`).

### 6.2. Bảng `work_orders` (Bổ sung ngữ cảnh vị trí và khung giờ)
- `incident_location_id`: `UUID` (Foreign Key tới `Location`, **vị trí thực tế nơi phát sinh sự cố**).
- `priority`: `VARCHAR(16)` (`LOW`, `MEDIUM`, `HIGH`, `URGENT`).
- `maintenance_window_start`: `TIME` (Khung giờ bắt đầu cho phép bảo trì, ví dụ `11:30:00`, `null=True`).
- `maintenance_window_end`: `TIME` (Khung giờ kết thúc cho phép bảo trì, ví dụ `13:00:00`, `null=True`).
- `coords_x`, `coords_y`: `FLOAT` (Tọa độ 2D nếu có, `null=True`).

---

## 7. Đặc Tả Giao Diện Lập Trình (API Specifications & Contracts)

### Danh Mục Endpoints:

| Phương Thức | Đường Dẫn | Chức Năng |
| :--- | :--- | :--- |
| `POST` | `/api/v1/routing/optimize-route/` | Tối ưu hóa lộ trình đầu ca (hỗ trợ cả có bản đồ và tô-pô phân cấp) |
| `POST` | `/api/v1/routing/re-route-mid-shift/` | Tái định tuyến động giữa ca từ vị trí hiện tại hoặc khi về kho |
| `GET` | `/api/v1/routing/my-daily-route/` | Lấy lộ trình tối ưu trong ngày của kỹ thuật viên |

### Cấu Trúc Dữ Liệu Mẫu:

#### 1. Yêu cầu tái định tuyến giữa ca (`POST /api/v1/routing/re-route-mid-shift/`):
- **Request Body**:
```json
{
  "currentLocationId": "loc-room-b302",
  "currentCoords": { "x": 45.0, "y": 80.0 },
  "actionTrigger": "NEW_URGENT_TASK",
  "includeWarehousePitstop": false,
  "completedWorkOrderIds": ["wo-01", "wo-02"],
  "remainingWorkOrderIds": ["wo-03", "wo-04", "wo-05-urgent-new"]
}
```
- **Response**:
```json
{
  "success": true,
  "data": {
    "totalEstimatedMinutes": 185,
    "totalDistanceMeters": 420.0,
    "routingMode": "HIERARCHICAL_TOPOLOGICAL",
    "orderedStops": [
      {
        "step": 0,
        "type": "CURRENT_LOCATION",
        "name": "Phòng B302 (Tầng 3 - Tòa B)",
        "action": "DEPART"
      },
      {
        "step": 1,
        "type": "WORK_ORDER",
        "workOrderId": "wo-05-urgent-new",
        "workOrderCode": "WO-2026-118",
        "priority": "URGENT",
        "locationName": "Phòng B305 (Tầng 3 - Tòa B)",
        "assetName": "Quạt thông gió cháy động cơ",
        "estimatedArrival": "10:05",
        "timeWindow": null
      },
      {
        "step": 2,
        "type": "WORK_ORDER",
        "workOrderId": "wo-03",
        "workOrderCode": "WO-2026-095",
        "priority": "MEDIUM",
        "locationName": "Phòng B201 (Tầng 2 - Tòa B)",
        "assetName": "Bàn học gãy bản lề",
        "estimatedArrival": "11:15",
        "timeWindow": { "start": "11:00", "end": "12:00" }
      }
    ]
  }
}
```

---

## 8. Đặc Tả Trải Nghiệm Người Dùng (UI/UX Behavioral Specifications)

- **Ứng Dụng Di Động (Mobile App Routing UI)**:
  - Hiển thị danh sách thứ tự công việc được đánh số rõ ràng: **Trạm 1 $\rightarrow$ Trạm 2 $\rightarrow$ Trạm 3**.
  - Hiển thị vị trí rõ ràng theo cấu trúc phân cấp: *"Tòa B $\rightarrow$ Tầng 3 $\rightarrow$ Phòng 302"*.
  - **Nút bấm nhanh "Về kho lấy vật tư"**: Nhấn nút một chạm để chèn ngay điểm dừng Kho vào lộ trình tiếp theo.
  - **Nút quét mã QR cập nhật vị trí**: Quét QR trên bàn/ghế, app tự động gợi ý cập nhật vị trí mới nếu phát hiện bàn bị khiêng sang phòng khác.
- **Giao Diện Web Portal (Route Visualizer)**:
  - Nếu có sơ đồ 2D: Vẽ đường đi nối qua các trạm kèm mũi tên chỉ hướng.
  - Nếu không có sơ đồ (Trường học/Văn phòng): Hiển thị cây lộ trình phân cấp gom việc trực quan theo từng Tòa nhà và từng Tầng.

---

## 9. Tiêu Chí Chấp Nhận & Ma Trận Kịch Bản Kiểm Thử (Acceptance Criteria & Test Matrix)

Dưới đây là bảng ma trận kiểm thử chi tiết hóa toàn bộ 12 kịch bản chấp nhận và trường hợp biên (Edge Cases):

### 9.1. Ma Trận Kịch Bản Nghiệp Vụ & Thuật Toán Định Tuyến

- [ ] **TC-TSP-01: Định tuyến tô-pô phân cấp khi không có bản đồ (No-Map Hierarchical)**
  - *Mô tả*: Trường học không có bản đồ số. Có 5 phiếu: 2 phiếu ở Phòng 301, 1 phiếu ở Phòng 302, 2 phiếu ở Tầng 1.
  - *Kỳ vọng*: Thuật toán tự động gom việc: Sửa xong toàn bộ các phòng ở Tầng 3 trước rồi mới xuống Tầng 1; không chạy đi chạy lại giữa các tầng.

- [ ] **TC-TSP-02: Định tuyến tài sản di động theo vị trí sự cố (Movable Asset Context)**
  - *Mô tả*: Cái bàn `TB-01` có vị trí gốc ở Phòng 101, nhưng phiếu báo hỏng ghi tại Phòng 204.
  - *Kỳ vọng*: Chặng di chuyển được tính toán dẫn tới Phòng 204, không dẫn tới Phòng 101.

- [ ] **TC-TSP-03: Phân lớp khẩn cấp cho cụm nhiều việc URGENT (Tiered TSP)**
  - *Mô tả*: Có 3 việc `URGENT` ở 3 vị trí khác nhau và 4 việc bình thường.
  - *Kỳ vọng*: Thuật toán giải TSP tối ưu đường đi qua riêng 3 việc URGENT trước; sau khi giải quyết xong mới tiếp tục đi qua 4 việc bình thường.

- [ ] **TC-TSP-04: Ràng buộc khung thời gian cho phép bảo trì (TSPTW)**
  - *Mô tả*: Máy nén khí chỉ cho dừng máy từ 11:30 đến 12:30.
  - *Kỳ vọng*: Lộ trình tự động xếp máy nén khí vào khung giờ từ 11:30 đến 12:30; không đến sớm lúc 9:00 sáng.

- [ ] **TC-TSP-05: Ma trận bất đối xứng do lối đi 1 chiều (Asymmetric ATSP)**
  - *Mô tả*: Đi từ A đến B qua cửa 1 chiều mất 20m, nhưng từ B về A phải đi đường vòng mất 120m.
  - *Kỳ vọng*: Thuật toán tính toán đúng ma trận có hướng $D(A,B) \ne D(B,A)$, không áp dụng phép đảo ngược làm vi phạm đường 1 chiều.

- [ ] **TC-TSP-06: Trạm dừng trung gian về kho nhận vật tư (Intermediate Pit-stop)**
  - *Mô tả*: Thợ đang sửa ở máy 3 bấm "Về kho lấy vật tư".
  - *Kỳ vọng*: Lộ trình chèn trạm dừng Kho vật tư ngay sau máy 3 và tái định tuyến từ Kho tới các máy 4, 5.

- [ ] **TC-TSP-07: Tái định tuyến động giữa ca từ vị trí hiện tại (Dynamic Mid-shift Re-routing)**
  - *Mô tả*: Thợ đang ở trạm 2 thì phát sinh việc khẩn cấp mới.
  - *Kỳ vọng*: Lộ trình tái tính toán lấy vị trí trạm 2 làm điểm xuất phát mới $v_0$, không tính lại từ Kho ban đầu.

- [ ] **TC-TSP-08: Phạt chi phí di chuyển thẳng đứng giữa các tầng (Multi-Floor Penalty)**
  - *Mô tả*: Đi cùng Tầng 1 cách nhau 40m vs leo lên Tầng 3 cách 10m theo phương thẳng đứng.
  - *Kỳ vọng*: Hệ thống ưu tiên giải quyết các máy cùng Tầng 1 trước, hạn chế việc leo cầu thang liên tục.

### 9.2. Ma Trận Kịch Bản Kỹ Thuật, Ngoại Tuyến & An Toàn

- [ ] **TC-TSP-09: Hoạt động ngoại tuyến trên Mobile (Offline Route Cache)**
  - *Mô tả*: Thiết bị di động bị ngắt kết nối mạng Internet dưới tầng hầm.
  - *Kỳ vọng*: Ứng dụng vẫn hiển thị đầy đủ danh sách thứ tự trạm dừng và chỉ dẫn phòng ban từ bộ đệm SQLite nội bộ.

- [ ] **TC-TSP-10: Tự động Fallback khi dữ liệu tọa độ rỗng (Graceful No-Map Degradation)**
  - *Mô tả*: Dữ liệu hoàn toàn không có tọa độ $X, Y$ và không có tên phòng (chỉ có danh sách việc).
  - *Kỳ vọng*: Hệ thống tự động chuyển sang sắp xếp theo thứ tự ưu tiên khẩn cấp và hạn chót (`priority` + `due_date`), không phát sinh lỗi HTTP 500.

- [ ] **TC-TSP-11: Quét mã QR cập nhật vị trí tài sản di động (Scan-to-Relocate)**
  - *Mô tả*: Quét QR của bàn học tại Phòng 204.
  - *Kỳ vọng*: Ứng dụng di động cập nhật `current_location_id` của bàn về Phòng 204 thành công.

- [ ] **TC-TSP-12: Cách ly dữ liệu vị trí đa khách hàng (Multi-Tenant Isolation)**
  - *Mô tả*: Tenant A và Tenant B cùng tối ưu lộ trình.
  - *Kỳ vọng*: Cây vị trí và lộ trình của Tenant A hoàn toàn không thể bị truy xuất bởi người dùng Tenant B.

- [ ] **TC-TSP-13: Cờ bật/tắt tính năng theo gói Tenant & Sắp xếp ưu tiên không vị trí (Zero-Location Fallback)**
  - *Mô tả*: Cấu hình Tenant có `ENABLE_TSP_ROUTING = False`. Kỹ thuật viên gọi API lấy danh sách việc trong ngày.
  - *Kỳ vọng*: Hệ thống không chạy thuật toán ma trận TSP; trả về danh sách công việc thuần túy được sắp xếp theo `priority` và `due_date` kèm cờ `routingEnabled: false`; Web/Mobile ẩn hoàn toàn bản đồ và nút tối ưu; không phát sinh lỗi hệ thống.

---

## 10. Implementation Notes — For Implementation Phase Only

> [!IMPORTANT]
> **REFERENCE ONLY — DO NOT IMPLEMENT OR MODIFY CODE BASED ON THIS SECTION DURING SPEC REVIEW. These notes are intended for the implementation phase after the specification is approved.**

Phần này lưu trữ các chỉ dẫn kỹ thuật hạ tầng chi tiết để các kỹ sư tham khảo trong quá trình triển khai mã nguồn:

### 10.1. Thuật Toán Ma Trận Khoảng Cách Bậc Thang Tô-Pô
```python
def compute_hierarchical_topological_distance(loc_a, loc_b):
    if loc_a.id == loc_b.id:
        return 1.0  # Cùng phòng
        
    # Cùng tầng
    if loc_a.parent_id == loc_b.parent_id:
        return 10.0
        
    # Cùng tòa nhà khác tầng
    building_a = loc_a.get_building()
    building_b = loc_b.get_building()
    if building_a and building_b and building_a.id == building_b.id:
        floor_diff = abs((loc_a.floor_number or 1) - (loc_b.floor_number or 1))
        return 10.0 + 30.0 * floor_diff
        
    # Khác tòa nhà cùng cơ sở
    site_a = loc_a.get_site()
    site_b = loc_b.get_site()
    if site_a and site_b and site_a.id == site_b.id:
        return 150.0
        
    return 1000.0  # Khác cơ sở
```

### 10.2. Thuật Toán Phân Lớp Khẩn Cấp (Tiered TSP)
```python
def solve_tiered_tsp(start_node, work_orders, distance_matrix):
    urgent_wos = [wo for wo in work_orders if wo.priority in ('URGENT', 'EMERGENCY')]
    normal_wos = [wo for wo in work_orders if wo.priority not in ('URGENT', 'EMERGENCY')]
    
    route = [start_node]
    current = start_node
    
    # 1. Giải cụm khẩn cấp trước
    if urgent_wos:
        urgent_tour = solve_atsp(current, urgent_wos, distance_matrix)
        route.extend(urgent_tour)
        current = route[-1]
        
    # 2. Giải cụm bình thường tiếp theo
    if normal_wos:
        normal_tour = solve_tsptw(current, normal_wos, distance_matrix)
        route.extend(normal_tour)
        
    return route
```

---

## 11. Kế Hoạch Triển Khai & Nghiệm Thu (Implementation Checklist)

- [ ] **Task 11.3.1 — Multi-Tier Distance Engine with Topological Hierarchy**
  - [ ] Cài đặt thuật toán tính khoảng cách bậc thang tô-pô không cần bản đồ (Cơ sở $\rightarrow$ Tòa nhà $\rightarrow$ Tầng $\rightarrow$ Phòng).
  - [ ] Hỗ trợ khoảng cách lưới Manhattan 2D và GPS Haversine.
  - [ ] Tích hợp xử lý tài sản di động theo vị trí sự cố trên Work Order.
- [ ] **Task 11.3.2 — Core Tiered ATSP & Time Window Solver**
  - [ ] Cài đặt thuật toán phân lớp khẩn cấp (Tiered TSP).
  - [ ] Cài đặt thuật toán TSP with Time Windows (TSPTW) xử lý khung giờ cho phép dừng máy.
  - [ ] Cài đặt thuật toán Or-opt / Relocate Move cho ma trận bất đối xứng (ATSP).
- [ ] **Task 11.3.3 — Dynamic Mid-Shift Re-routing & Pit-Stop APIs**
  - [ ] Endpoint tối ưu lộ trình ban đầu: `POST /api/v1/routing/optimize-route/`.
  - [ ] Endpoint tái định tuyến giữa ca: `POST /api/v1/routing/re-route-mid-shift/` hỗ trợ trạm dừng kho và vị trí hiện tại.
- [ ] **Task 11.3.4 — Mobile & Web UI Integration**
  - [ ] Giao diện Mobile hiển thị thứ tự trạm dừng và nút bấm "Về kho lấy vật tư".
  - [ ] Tích hợp quét mã QR cập nhật vị trí tài sản di động (Scan-to-Relocate).
  - [ ] Bộ đệm ngoại tuyến lưu lộ trình trên thiết bị di động.
- [ ] **Task 11.3.5 — Verification & Testing Suite**
  - [ ] Viết test cases kiểm thử đầy đủ 12 kịch bản chấp nhận (`TC-TSP-01` đến `TC-TSP-12`).

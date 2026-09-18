# Thiết Kế Hệ Thống & Đặc Tả Kỹ Thuật: Task 10.1 — Real-time Notification System (Celery & Polling)

Tài liệu này xác định kiến trúc tổng thể, mô hình dữ liệu, danh mục sự kiện, cơ chế đa người thuê (Multi-tenancy), danh mục API, đặc tả trải nghiệm người dùng và bộ kịch bản kiểm thử chấp nhận (Acceptance Test Cases & Edge Cases) cho **Hệ thống Thông báo Thời gian thực (Real-time Notification System)** của giải pháp Quản lý Tài sản Doanh nghiệp (EAM).

Tài liệu này đóng vai trò là **Đặc Tả Kỹ Thuật & Chuẩn Kiểm Thử (Technical Specification & Audit Baseline)** nhằm đối chiếu, rà soát và thực thi trọn vẹn toàn bộ tính năng mà không bị thiếu sót bất kỳ nghiệp vụ enterprise nào.

---

## 1. Tổng Quan Kiến Trúc & Luồng Dữ Liệu (Architecture Overview)

### 1.1. Luồng Hoạt Động Cốt Lõi (End-to-End Workflow)
Hệ thống thông báo hoạt động theo cơ chế **Event-Driven Asynchronous Dispatching** kết hợp xử lý hàng đợi bất đồng bộ ở tầng Backend và bộ máy đồng bộ nhẹ (Smart Polling Engine) ở tầng Client:

```
[Business Event Trigger]
  (Work Order, PM Plan, Low Stock, Sensor Alert, System Admin)
         │
         ▼
[Notification Dispatcher Service] ──► Thu thập Recipient theo Tenant, Phân Quyền & Tùy Chọn Nhận Tin
         │
         ▼
[Asynchronous Task Queue] ──► Chuyển giao tác vụ xử lý thông báo ngầm
         │
         ├───► [Database Persistence] ──► Lưu bản ghi vào bảng notifications (Kế thừa BaseTenantModel)
         ├───► [Mobile Push Dispatch] ──► Gửi push token qua nhà cung cấp (FCM/APNs)
         └───► [Email Service]        ──► Gửi email đối với thông báo URGENT/CRITICAL
         │
         ▼
[Client Consumption (Web & Mobile)]
  ├── Web Portal: Định kỳ gọi endpoint unread-count siêu nhẹ để cập nhật badge chuông
  ├── Bell Badge: Cập nhật số lượng chưa đọc, phân nhóm danh sách dropdown (Tất cả / Cần hành động)
  └── User Action: Nhấp thông báo ──► Đánh dấu đã đọc + Điều hướng an toàn đến đối tượng nghiệp vụ
```

### 1.2. Các Nguyên Tắc Thiết Kế Then Chốt
- **Tenant Isolation First**: Cách ly tuyệt đối thông báo giữa các tổ chức (Tenant). Không cho phép bất kỳ thông báo nào của Tenant này bị nhìn thấy hoặc truy cập bởi người dùng của Tenant khác.
- **Asynchronous & Non-blocking**: Tác vụ tạo và gửi thông báo ra ngoài (Push, Email) phải chạy ngầm, không gây chậm trễ cho luồng xử lý HTTP request chính.
- **Lightweight Synchronization**: Cơ chế kiểm tra định kỳ từ Client chỉ truy vấn endpoint đếm số lượng nhẹ (`unread-count`), không tải lại toàn bộ nội dung cho đến khi người dùng tương tác trực tiếp với chuông thông báo.
- **Deduplication & Storm Throttling**: Chống quá tải và bão thông báo khi xảy ra sự cố lặp lại liên tục từ máy móc hoặc cảm biến.
- **Actionable State Separation**: Tách bạch rõ giữa trạng thái trực quan "Đã xem thông báo" (`is_read`) và trạng thái nghiệp vụ "Đã hoàn thành hành động" (`action_status`).

---

## 2. Các Quy Tắc Thiết Kế Bảo Vệ & Kịch Bản Nghiệp Vụ Phòng Thủ (Defensive Business Rules & Edge-Case Specification)

Tất cả các thành phần xử lý thông báo (Backend Services, API ViewSets, Workers, Web UI và Mobile App) phải tuân thủ nghiêm ngặt 9 quy tắc thiết kế phòng thủ sau:

---

### Quy Tắc 1: Chống Rò Rỉ Thông Báo Giữa Các Doanh Nghiệp (Tenant Leak Prevention Guardrail)
- **Điểm Yếu Bắt Lỗi (The Trap)**: Trong môi trường Multi-tenant SaaS, nhiều doanh nghiệp chia sẻ chung một cơ sở dữ liệu. Nếu truy vấn thiếu điều kiện lọc theo `tenant_id`, người dùng thuộc Công ty A có thể nhìn thấy hoặc đọc trộm thông báo sự cố, kế hoạch bảo trì nội bộ của Công ty B qua API hoặc giao diện chuông.
- **Quy Tắc Nghiệp Vụ & Ràng Buộc Bắt Buộc**:
  1. Tầng Model: Bảng `Notification` bắt buộc kế thừa `BaseTenantModel`, liên kết khóa ngoại với `Tenant` (`db_column='tenant_id'`) và tự động kích hoạt bộ quản lý lọc `TenantManager`.
  2. Tầng Queryset: Bắt buộc áp dụng cơ chế lọc kép: luôn luôn ràng buộc `tenant_id = request.user.tenant_id` và `recipient_id = request.user.id`. Tuyệt đối không cho phép truy xuất thông báo bỏ qua ngữ cảnh tenant.
  3. Tầng Xác thực: Phương thức `clean()` của Model phải chủ động từ chối lưu bản ghi nếu người nhận (`recipient`) không thuộc cùng `tenant_id` với thông báo.
  4. Phân vùng Super Admin: Tài khoản quản trị cấp cao thuộc `SYSTEM Tenant` chỉ tiếp nhận các cảnh báo bảo trì hạ tầng hệ thống, không tự động nhận thông báo nghiệp vụ nội bộ của các Tenant khách hàng.

---

### Quy Tắc 2: Chống Bão Thông Báo & Kiểm Soát Trùng Lặp (Notification Storm & De-duplication Guardrail)
- **Điểm Yếu Bắt Lỗi (The Trap)**: Khi một cảm biến nhiệt độ bị lỗi liên tục gửi chỉ số bất thường mỗi giây, hoặc một lệnh công việc bị sửa đổi liên tục qua API, việc phát thông báo tức thì cho mỗi sự kiện sẽ gây tràn ngập hộp thư người dùng, làm nghẽn hàng đợi xử lý và tiêu hao tài nguyên máy chủ.
- **Quy Tắc Nghiệp Vụ & Ràng Buộc Bắt Buộc**:
  1. Áp dụng cơ chế kiểm soát trùng lặp theo cửa sổ thời gian trượt (Sliding-Window Deduplication) với khoảng thời gian mặc định 5 phút (300 giây).
  2. Tạo khóa định danh trùng lặp duy nhất dựa trên tổ hợp: `[tenant_id, event_type, entity_id, recipient_id]`.
  3. Nếu sự kiện tương tự đã được phát trong cửa sổ kiểm soát: Hệ thống không tạo bản ghi thông báo mới và không phát thêm thông báo đẩy (Push/Email). Thay vào đó, cập nhật trường đếm số lần phát sinh `occurrence_count += 1` và cập nhật dấu thời gian `updated_at` trên thông báo hiện hữu.

---

### Quy Tắc 3: Phân Luồng Định Tuyến Chính Xác Theo Vai Trò (Role-Based Routing Guardrail)
- **Điểm Yếu Bắt Lỗi (The Trap)**: Phát tán thông báo toàn bộ người dùng trong công ty sẽ khiến kỹ thuật viên nhận cảnh báo ngân sách, thủ kho nhận thông báo giao việc sửa chữa máy may, gây loãng thông tin và vi phạm bảo mật nội bộ.
- **Quy Tắc Nghiệp Vụ & Ràng Buộc Bắt Buộc**:
  Bộ định tuyến thông báo (`NotificationRouter`) phải phân luồng chính xác theo ma trận vai trò:
  1. **Kỹ thuật viên (`TECHNICIAN`)**: Chỉ nhận thông báo liên quan trực tiếp đến công việc được gán cho bản thân, thay đổi lịch làm việc hoặc thông báo được ủy quyền. Không nhận thông báo về chi phí, giá phụ tùng hoặc công việc của kỹ thuật viên khác.
  2. **Quản lý bảo trì (`MAINTENANCE_MANAGER`)**: Nhận các sự cố khẩn cấp (`CRITICAL`/`EMERGENCY`), phiếu bảo trì tự động sinh từ kế hoạch định kỳ (PM), thông báo cần nghiệm thu công việc, và các cảnh báo leo thang (Escalation).
  3. **Thủ kho (`WAREHOUSE_KEEPER`)**: Nhận cảnh báo khi phụ tùng chạm ngưỡng tồn kho tối thiểu và các yêu cầu cấp phát vật tư cho phiếu công việc.
  4. **Quản trị doanh nghiệp (`TENANT_ADMIN`) / Kế toán (`FINANCE`)**: Nhận cảnh báo vượt ngân sách bảo trì, tổng kết KPI định kỳ và các sự kiện người dùng mới gia nhập tổ chức.

---

### Quy Tắc 4: Đồng Bộ Trạng Thái Đọc & Xử Lý Mất Mạng Đa Nền Tảng (Cross-Platform Read Sync Guardrail)
- **Điểm Yếu Bắt Lỗi (The Trap)**: Người dùng đã bấm đọc thông báo trên Web nhưng ứng dụng Mobile vẫn báo số lượng chưa đọc, hoặc khi thiết bị mất kết nối mạng, client liên tục gửi request thăm dò gây treo ứng dụng.
- **Quy Tắc Nghiệp Vụ & Ràng Buộc Bắt Buộc**:
  1. Đồng bộ trạng thái trung tâm: Thao tác đánh dấu đọc (từng thông báo hoặc tất cả) phải cập nhật ngay lập tức `is_read = True` và thời điểm `read_at = NOW()` vào cơ sở dữ liệu tập trung.
  2. Endpoint đếm số lượng nhẹ: Cung cấp endpoint tối ưu `/unread-count/` trả về số nguyên tổng lượng chưa đọc để cả Web và Mobile cùng đồng bộ badge hiển thị mà không cần tải danh sách chi tiết.
  3. Cơ chế thích ứng khi mất kết nối (Exponential Backoff): Khi phát hiện lỗi mạng trong quá trình thăm dò định kỳ, client tự động kéo dài chu kỳ kiểm tra theo cấp số nhân và khôi phục chu kỳ bình thường ngay khi có kết nối trở lại.

---

### Quy Tắc 5: Cơ Chế Ủy Quyền & Người Dùng Vắng Mặt (Delegation / Out of Office Guardrail)
- **Điểm Yếu Bắt Lỗi (The Trap)**: Kỹ thuật viên A đang trong kỳ nghỉ phép (Out of Office - OOO), hệ thống hoặc quản lý tự động phân công một phiếu bảo trì định kỳ (PM). Do kỹ thuật viên vắng mặt không xem thông báo, phiếu công việc bị bỏ quên, máy móc không được bảo dưỡng đúng hạn gây sự cố dừng dây chuyền.
- **Quy Tắc Nghiệp Vụ & Ràng Buộc Bắt Buộc**:
  1. Nhận diện trạng thái vắng mặt: Hệ thống kiểm tra cấu hình OOO của người nhận tại thời điểm phát sinh sự kiện phân công.
  2. Tự động chuyển tiếp (Delegation / CC): Khi người nhận chính đang OOO, hệ thống vẫn ghi nhận thông báo cho người nhận chính, đồng thời tự động tạo một thông báo chuyển tiếp có nhãn `TASK_DELEGATED` gửi đến Người được ủy quyền (`delegated_to_user`) hoặc Quản lý trực tiếp.
  3. Ghi vết ngữ cảnh: Bản ghi thông báo chuyển tiếp phải thể hiện rõ thông tin ủy quyền: người nhận gốc, lý do vắng mặt và thời gian ủy quyền trong trường `metadata`.

---

### Quy Tắc 6: Giao Thức Leo Thang Cảnh Báo Khẩn Cấp (Escalation Protocol Guardrail)
- **Điểm Yếu Bắt Lỗi (The Trap)**: Một sự cố dừng máy khẩn cấp hoặc nguy cơ cháy nổ (`CRITICAL`) xảy ra, thông báo được gửi đến kỹ thuật viên trực ban. Tuy nhiên, kỹ thuật viên không trực máy, thiết bị hết pin hoặc không đọc thông báo trong suốt 15–30 phút, khiến sự cố bị ngó lơ và gây tổn thất nghiêm trọng.
- **Quy Tắc Nghiệp Vụ & Ràng Buộc Bắt Buộc**:
  1. Ràng buộc thời hạn tiếp nhận (SLA Window): Mọi thông báo mức độ `CRITICAL` và `URGENT` phải được thiết lập thời hạn tiếp nhận tối đa (`escalate_at`, mặc định 15 đến 30 phút tùy cấu hình của Tenant).
  2. Tự động kích hoạt leo thang: Tác vụ kiểm tra định kỳ ngầm sẽ quét các thông báo nghiêm trọng chưa được đánh dấu đọc hoặc chưa được tiếp nhận xử lý khi đã quá hạn `escalate_at`.
  3. Phát sinh thông báo cấp cao: Hệ thống tự động sinh thông báo cảnh báo leo thang mang mã `WO_ESCALATED` gửi trực tiếp cho Quản lý bảo trì và Trưởng ca xưởng, nêu rõ sự cố chưa có người tiếp nhận để có biện pháp điều phối thay thế ngay lập tức.
  4. Cập nhật trạng thái thông báo gốc: Đánh dấu cờ `escalation_level += 1` trên bản ghi gốc để tránh lặp lại tiến trình leo thang nhiều lần.

---

### Quy Tắc 7: Phân Định Trạng Thái Đã Đọc vs Cần Hành Động (Read vs. Actionable / Pending Task Guardrail)
- **Điểm Yếu Bắt Lỗi (The Trap)**: Quản lý nhận thông báo "Có yêu cầu xuất kho chờ duyệt". Quản lý nhấp vào xem thông báo (hệ thống đánh dấu `is_read = True`), nhưng sau đó có việc bận nên chưa bấm nút Phê duyệt hay Từ chối. Do số đỏ chuông đã biến mất, quản lý quên bẵng yêu cầu này, dẫn đến dây chuyền thiếu vật tư sửa chữa.
- **Quy Tắc Nghiệp Vụ & Ràng Buộc Bắt Buộc**:
  1. Tách biệt hai trạng thái độc lập:
     - `is_read` (Đã xem / Đã đọc): Dùng riêng cho việc cập nhật hiển thị trực quan (tắt badge đỏ trên chuông).
     - `is_actionable` (Yêu cầu hành động): Xác định thông báo này có gắn liền với một tác vụ nghiệp vụ cần người dùng ra quyết định hay không (ví dụ: Duyệt Work Order, Phê duyệt xuất kho, Xác nhận nghiệm thu).
  2. Vòng đời trạng thái hành động (`action_status`):
     - `PENDING`: Hành động chưa được thực hiện, dù người dùng đã xem (`is_read = True`).
     - `RESOLVED`: Hành động nghiệp vụ đã hoàn tất (đã duyệt hoặc từ chối).
     - `EXPIRED`: Tác vụ đã hết hạn hoặc bị hủy bởi hệ thống.
  3. Giao diện bộ lọc chuyên biệt: Trung tâm thông báo phải cung cấp tab/bộ lọc riêng "Cần hành động" (`Pending Actions`). Chỉ khi tác vụ được giải quyết tại thực thể nguồn (Work Order, Inventory Request), trạng thái `action_status` mới chuyển sang `RESOLVED`.

---

### Quy Tắc 8: Bảo Toàn Danh Tính Người Gửi Dạng Ảnh Chụp (Sender Snapshot Guardrail)
- **Điểm Yếu Bắt Lỗi (The Trap)**: Quản lý A tạo thông báo giao việc cho kỹ thuật viên B. Vài tháng sau, Quản lý A nghỉ việc, tài khoản bị xóa hoặc vô hiệu hóa. Khi kỹ thuật viên B xem lại lịch sử thông báo cũ, do câu truy vấn join bảng User bị trả về `NULL`, hệ thống văng lỗi 500, lỗi giao diện hoặc hiển thị sai lệch thành "System" thay vì người giao việc ban đầu.
- **Quy Tắc Nghiệp Vụ & Ràng Buộc Bắt Buộc**:
  1. Ràng buộc toàn vẹn khóa ngoại: Trường liên kết người gửi `sender` phải sử dụng chính sách `on_delete=models.SET_NULL, null=True`.
  2. Chụp nhanh thông tin lúc gửi (Snapshot Fields): Khi bản ghi thông báo được khởi tạo, hệ thống phải lưu trữ tĩnh thông tin danh tính người gửi vào hai trường snapshot: `sender_name_snapshot` (họ tên/username) và `sender_role_snapshot` (vai trò tại thời điểm gửi).
  3. Cơ chế hiển thị an toàn: Tầng tuần tự hóa (Serializer) và Giao diện luôn ưu tiên lấy tên từ `sender_name_snapshot` nếu khóa ngoại `sender` bị NULL, đảm bảo lịch sử công việc luôn luôn đầy đủ, minh bạch và không bao giờ bị lỗi giao diện.

---

### Quy Tắc 9: Xử Lý An Toàn Khi Lệch Phân Quyền Sau Khi Nhận Thông Báo (Role Change Drift Guardrail)
- **Điểm Yếu Bắt Lỗi (The Trap)**: Người dùng X đang giữ vai trò Quản lý bảo trì, nhận được các thông báo phê duyệt ngân sách và chi phí. Ngày hôm sau, X được điều chuyển công tác thành Kỹ thuật viên bình thường và bị thu hồi quyền duyệt ngân sách. Khi X nhấp vào đường link trong thông báo cũ, nếu hệ thống không xử lý phân quyền chặt chẽ, X có thể thực hiện thao tác vượt quyền; ngược lại, nếu hệ thống xử lý thô bạo sẽ gây lỗi màn hình trắng hoặc crash trang.
- **Quy Tắc Nghiệp Vụ & Ràng Buộc Bắt Buộc**:
  1. Xác thực quyền tại thời điểm tương tác: Kiểm tra phân quyền nghiệp vụ (RBAC) được thực thi nghiêm ngặt tại endpoint đích của tài nguyên, không tin cậy dựa trên việc người dùng đang sở hữu thông báo.
  2. Phản hồi phân quyền chuẩn hóa: Khi người dùng không còn quyền truy cập tài nguyên liên kết, API trả về HTTP `403 Forbidden` với cấu trúc lỗi chuẩn.
  3. Trải nghiệm người dùng an toàn: Giao diện Web và Mobile khi nhận mã 403 từ liên kết thông báo phải bắt lỗi mượt mà, hiển thị thông báo cảnh báo dạng Toast: *"Bạn không còn quyền truy cập dữ liệu này hoặc dữ liệu đã được điều chuyển"*, đồng thời giữ nguyên trạng thái ứng dụng hoặc chuyển hướng về trang an toàn, tuyệt đối không gây sập ứng dụng.

---

## 3. Ma Trận Phân Loại Sự Kiện Thông Báo (Enterprise Notification Event Matrix)

Bảng tổng hợp toàn bộ các sự kiện thông báo trong hệ thống EAM:

| Mã Sự Kiện (`event_type`) | Phân Hệ | Mức Ưu Tiên (`severity`) | Đối Tượng Nhận | Có Cần Hành Động? (`is_actionable`) | Mục Đích & Điều Kiện Kích Hoạt | Đường Dẫn Điều Hướng (`link`) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `WO_ASSIGNED` | Work Order | `INFO` | Kỹ thuật viên được gán | `True` | Khi phiếu công việc được phân công cho kỹ thuật viên | `/portal/work-orders/{wo_id}/` |
| `WO_STATUS_CHANGED` | Work Order | `INFO` | Người tạo, Quản lý, Kỹ thuật viên | `False` | Khi trạng thái Work Order thay đổi | `/portal/work-orders/{wo_id}/` |
| `WO_OVERDUE` | Work Order | `URGENT` | Kỹ thuật viên & Quản lý bảo trì | `True` | Khi Work Order vượt quá thời hạn hoàn thành cam kết | `/portal/work-orders/{wo_id}/` |
| `WO_EMERGENCY_CREATED`| Work Order | `CRITICAL` | Toàn bộ Quản lý & Trưởng ca | `True` | Phát sinh phiếu công việc khẩn cấp do dừng máy/cháy nổ | `/portal/work-orders/{wo_id}/` |
| `WO_ESCALATED` | Work Order | `CRITICAL` | Quản lý bảo trì, Giám đốc xưởng | `True` | Cảnh báo sự cố khẩn cấp bị bỏ qua quá hạn thời gian tiếp nhận | `/portal/work-orders/{wo_id}/` |
| `TASK_DELEGATED` | Work Order | `INFO` | Người được ủy quyền / Quản lý | `True` | Chuyển tiếp công việc do kỹ thuật viên chính vắng mặt (OOO) | `/portal/work-orders/{wo_id}/` |
| `PM_SCHEDULE_TRIGGERED`| Maintenance | `INFO` | Quản lý bảo trì | `False` | Tác vụ định kỳ quét đến hạn chu kỳ và tự động sinh Work Order | `/portal/work-orders/{wo_id}/` |
| `PM_UPCOMING_REMINDER` | Maintenance | `INFO` | Quản lý bảo trì | `False` | Nhắc nhở kế hoạch bảo trì định kỳ sắp đến hạn trong vòng 48h | `/portal/maintenance/pm-plans/{pm_id}/`|
| `SPARE_PART_LOW_STOCK` | Inventory | `WARNING` | Thủ kho, Quản lý | `True` | Số lượng tồn khả dụng thấp hơn mức tồn tối thiểu an toàn | `/portal/inventory/parts/{part_id}/` |
| `SPARE_PART_REQUESTED` | Inventory | `INFO` | Thủ kho | `True` | Kỹ thuật viên yêu cầu xuất kho vật tư phụ tùng cho Work Order | `/portal/inventory/requests/{req_id}/` |
| `SENSOR_ANOMALY_DETECTED`| Asset Core | `CRITICAL` | Kỹ sư kỹ thuật, Quản lý | `True` | Cảm biến IoT/Thuật toán phát hiện độ rung hoặc nhiệt độ bất thường| `/portal/assets/{asset_id}/` |
| `ASSET_STATUS_DOWN` | Asset Core | `URGENT` | Quản lý, Kỹ thuật viên khu vực | `True` | Trạng thái vận hành của thiết bị chuyển sang trạng thái dừng máy | `/portal/assets/{asset_id}/` |
| `BUDGET_THRESHOLD_EXCEEDED`| Finance | `WARNING` | Quản trị Tenant, Quản lý tài chính | `False` | Chi phí bảo trì thực tế vượt ngưỡng định mức ngân sách quy định | `/portal/reports/costs/` |
| `USER_INVITATION_ACCEPTED`| Admin | `INFO` | Quản trị Tenant | `False` | Người dùng được mời kích hoạt thành công tài khoản thành viên | `/portal/admin/users/` |
| `SYSTEM_MAINTENANCE_ALERT`| System | `WARNING` | Toàn thể người dùng hệ thống | `False` | Thông báo kế hoạch bảo trì máy chủ từ Quản trị viên hệ thống | `/portal/announcements/` |

---

## 4. Đặc Tả Chi Tiết Kỹ Thuật (Technical Specifications)

### 4.1. Lược Đồ Dữ Liệu Cốt Lõi (Database Schema Design)

#### A. Bảng `notifications`
Mỗi bản ghi lưu trữ một thông báo được gửi đến một người dùng cụ thể trong tổ chức:
- `id`: `UUID` (Primary Key, default: `uuid4`).
- `tenant_id`: `UUID` (Foreign Key tới `Tenant`, bắt buộc, kế thừa từ `BaseTenantModel`).
- `recipient_id`: `UUID` (Foreign Key tới `User`, người nhận thông báo, `on_delete=CASCADE`).
- `sender_id`: `UUID` (Foreign Key tới `User`, người phát sự kiện, `null=True`, `on_delete=SET_NULL`).
- `sender_name_snapshot`: `VARCHAR(150)` (Lưu tĩnh tên hiển thị/username của người gửi lúc tạo).
- `sender_role_snapshot`: `VARCHAR(64)` (Lưu tĩnh vai trò của người gửi lúc tạo, ví dụ: `MAINTENANCE_MANAGER`).
- `event_type`: `VARCHAR(64)` (Mã sự kiện: ví dụ `WO_ASSIGNED`, `WO_ESCALATED`, `SPARE_PART_LOW_STOCK`).
- `category`: `VARCHAR(32)` (Phân nhóm: `WORK_ORDER`, `MAINTENANCE`, `INVENTORY`, `ASSET`, `SYSTEM`, `FINANCE`).
- `severity`: `VARCHAR(16)` (Mức độ nghiêm trọng: `INFO`, `WARNING`, `URGENT`, `CRITICAL`).
- `title`: `VARCHAR(255)` (Tiêu đề ngắn gọn hiển thị).
- `message`: `TEXT` (Nội dung chi tiết của thông báo).
- `link`: `VARCHAR(500)` (Đường dẫn chuyển hướng an toàn khi người dùng nhấp vào).
- `metadata`: `JSONB` (Dữ liệu mở rộng phục vụ render: `entity_type`, `entity_id`, thông tin ủy quyền OOO).
- `is_read`: `BOOLEAN` (Trạng thái xem thông báo, mặc định `False`).
- `read_at`: `TIMESTAMP WITH TIME ZONE` (Thời điểm đánh dấu đã xem, `null=True`).
- `is_actionable`: `BOOLEAN` (Cờ xác định thông báo có cần người dùng xử lý hành động hay không, mặc định `False`).
- `action_status`: `VARCHAR(20)` (Trạng thái hành động: `NOT_APPLICABLE`, `PENDING`, `RESOLVED`, `EXPIRED`, mặc định `NOT_APPLICABLE`).
- `action_resolved_at`: `TIMESTAMP WITH TIME ZONE` (Thời điểm tác vụ được hoàn tất hoặc từ chối, `null=True`).
- `escalation_level`: `SMALLINT` (Cấp độ leo thang cảnh báo, mặc định `0`).
- `escalate_at`: `TIMESTAMP WITH TIME ZONE` (Thời hạn tối đa cần tiếp nhận trước khi tự động leo thang, `null=True`).
- `occurrence_count`: `INTEGER` (Số lần sự kiện lặp lại được gộp trong cửa sổ chống bão, mặc định `1`).
- `is_deleted`: `BOOLEAN` (Trạng thái xóa mềm, mặc định `False`).
- `created_at`: `TIMESTAMP WITH TIME ZONE` (Thời điểm tạo thông báo, tự động gán).
- `updated_at`: `TIMESTAMP WITH TIME ZONE` (Thời điểm cập nhật gần nhất).

**Chỉ Mục Cốt Lõi (Database Indexes)**:
- `idx_notif_tenant_recip_read_created`: `(tenant_id, recipient_id, is_read, created_at DESC)` — Phục vụ truy vấn đếm unread và lấy danh sách chưa đọc.
- `idx_notif_recip_action_pending`: `(recipient_id, is_actionable, action_status)` — Phục vụ lọc các tác vụ chờ xử lý của người dùng.
- `idx_notif_escalation_scan`: `(severity, is_read, escalate_at)` — Phục vụ tác vụ quét tự động leo thang cảnh báo chưa đọc.

#### B. Bảng `notification_preferences`
Cho phép người dùng tùy biến kênh nhận tin và thiết lập trạng thái vắng mặt:
- `id`: `UUID` (Primary Key).
- `user_id`: `UUID` (Foreign Key tới `User`).
- `tenant_id`: `UUID` (Foreign Key tới `Tenant`, kế thừa `BaseTenantModel`).
- `category`: `VARCHAR(32)` (Nhóm thông báo: `WORK_ORDER`, `INVENTORY`, v.v.).
- `in_app_enabled`: `BOOLEAN` (Bật/tắt hiển thị chuông Web - Mặc định `True`).
- `email_enabled`: `BOOLEAN` (Bật/tắt nhận Email).
- `push_enabled`: `BOOLEAN` (Bật/tắt nhận thông báo đẩy Mobile).
- `quiet_hours_start`: `TIME` (Giờ bắt đầu chế độ im lặng, `null=True`).
- `quiet_hours_end`: `TIME` (Giờ kết thúc chế độ im lặng, `null=True`).
- `is_out_of_office`: `BOOLEAN` (Trạng thái nghỉ phép / vắng mặt, mặc định `False`).
- `delegated_to_user_id`: `UUID` (Foreign Key tới `User` được ủy quyền khi vắng mặt, `null=True`).

#### C. Bảng `device_push_tokens`
Quản lý mã đăng ký thiết bị di động của kỹ thuật viên:
- `id`: `UUID` (Primary Key).
- `user_id`: `UUID` (Foreign Key tới `User`).
- `tenant_id`: `UUID` (Foreign Key tới `Tenant`).
- `device_token`: `TEXT` (Mã token FCM / APNs).
- `device_type`: `VARCHAR(16)` (`ANDROID`, `IOS`, `WEB`).
- `is_active`: `BOOLEAN` (Mặc định `True`).
- `updated_at`: `TIMESTAMP WITH TIME ZONE`.

---

### 4.2. Đặc Tả RESTful API Specification

Toàn bộ API đều yêu cầu xác thực người dùng (`IsAuthenticated`) và tự động giới hạn phạm vi truy cập trong Tenant của người dùng đang đăng nhập.

#### Danh Mục Endpoints:

| Phương Thức | Đường Dẫn | Mục Đích | Tham Số Chính | Định Dạng Dữ Liệu Trả Về |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/notifications/` | Lấy danh sách thông báo phân trang của người dùng hiện tại | `page`, `size`, `is_read`, `is_actionable`, `action_status`, `category`, `severity` | Danh sách thông báo (`content`), tổng số lượng, số chưa đọc (`unread_count`), thông tin phân trang |
| `GET` | `/api/v1/notifications/unread-count/` | Endpoint nhẹ phục vụ thăm dò định kỳ (Polling) | Không | `{"unread_count": N, "unreadCount": N, "has_critical": boolean}` |
| `POST` | `/api/v1/notifications/{id}/read/` | Đánh dấu một thông báo là đã xem | Đường dẫn `{id}` | Bản ghi thông báo đã cập nhật (`is_read = True`, `read_at`) |
| `POST` | `/api/v1/notifications/mark-all-read/` *(alias: `/read-all/`)* | Đánh dấu toàn bộ thông báo của người dùng là đã xem | `{ "category": "..." }` (tùy chọn) | `{"updated_count": N, "updatedCount": N}` |
| `POST` | `/api/v1/notifications/{id}/resolve-action/` | Cập nhật trạng thái tác vụ hành động | `{ "action_status": "RESOLVED" }` | Bản ghi thông báo với `action_status` mới |
| `DELETE`| `/api/v1/notifications/{id}/` | Xóa mềm một thông báo khỏi danh sách | Đường dẫn `{id}` | `{"success": true}` |
| `GET` | `/api/v1/notifications/preferences/` | Lấy cấu hình nhận thông báo và trạng thái OOO | Không | Danh sách cấu hình tùy chọn và trạng thái ủy quyền |
| `PUT` | `/api/v1/notifications/preferences/` | Cập nhật cấu hình thông báo và trạng thái OOO | Dữ liệu cấu hình mới | Cấu hình đã cập nhật |
| `POST` | `/api/v1/notifications/devices/` | Đăng ký hoặc làm mới Device Token Mobile | `device_token`, `device_type` | `{"success": true}` |

#### Cấu Trúc Dữ Liệu Mẫu:

##### 1. Phản Hồi Đếm Số Lượng Chưa Đọc (`GET /api/v1/notifications/unread-count/`):
```json
{
  "success": true,
  "data": {
    "unread_count": 3,
    "unreadCount": 3,
    "has_critical": false
  }
}
```

##### 2. Phản Hồi Danh Sách Thông Báo (`GET /api/v1/notifications/?page=0&size=10`):
```json
{
  "success": true,
  "data": {
    "content": [
      {
        "id": "c1f72b20-4e3a-49a8-9d51-c0812e584f21",
        "eventType": "WO_ASSIGNED",
        "category": "WORK_ORDER",
        "severity": "INFO",
        "title": "Phân công công việc mới",
        "message": "Bạn đã được phân công thực hiện phiếu WO-2026-089.",
        "link": "/portal/work-orders/c1f72b20-4e3a-49a8-9d51-c0812e584f21/",
        "sender": {
          "id": "f2a11b33-1111-2222-3333-444455556666",
          "name": "Nguyễn Văn Quản Lý",
          "role": "MAINTENANCE_MANAGER"
        },
        "isRead": false,
        "readAt": null,
        "isActionable": true,
        "actionStatus": "PENDING",
        "actionResolvedAt": null,
        "createdAt": "2026-09-17T09:15:30Z"
      }
    ],
    "unread_count": 1,
    "unreadCount": 1,
    "totalElements": 1,
    "totalPages": 1,
    "page": 0,
    "size": 10,
    "last": true
  }
}
```

---

### 4.3. Đặc Tả Trải Nghiệm Người Dùng (UI/UX Specification - Conceptual & Functional)

Giao diện thông báo được thiết kế trực quan, hỗ trợ tương tác nhanh và đảm bảo khả năng đáp ứng cao:

- **Icon Chuông & Huy Hiệu Chưa Đọc (Topbar Bell & Unread Badge)**:
  - Nằm cố định tại thanh điều hướng trên cùng, ngay trước thông tin tài khoản người dùng.
  - Hiển thị badge số lượng chưa đọc khi `unread_count > 0`, ẩn hoàn toàn khi số lượng bằng 0. Khi số lượng vượt quá 99, hiển thị nhãn `99+`.
  - Có dấu hiệu thị giác nổi bật đối với các cảnh báo mức độ `CRITICAL` hoặc khi vừa nhận thêm thông báo mới.

- **Khung Cửa Sổ Thả Xuống (Dropdown Popover Panel)**:
  - **Phần Đầu**: Tiêu đề "Thông báo", nút thao tác nhanh "Đánh dấu tất cả đã đọc" và thanh chuyển tab phân loại: **Tất cả**, **Chưa đọc**, và **Cần hành động** (lọc riêng các thông báo có `is_actionable = True` và `action_status = 'PENDING'`).
  - **Danh Sách Mục Thông Báo**:
    - Hiển thị danh sách thông báo mới nhất với thanh cuộn độc lập.
    - Mỗi mục hiển thị rõ ràng: Biểu tượng phân hệ tương ứng, Nhãn mức độ nghiêm trọng (`CRITICAL`, `URGENT`, `WARNING`, `INFO`), Tiêu đề in đậm, Nội dung tóm tắt, Tên người gửi (lấy từ snapshot) và Thời gian tương đối.
    - Phân biệt trực quan rõ ràng giữa trạng thái Chưa đọc (nổi bật, có dấu chấm nhận diện) và Đã đọc (màu chữ dịu đi).
    - Các thông báo "Cần hành động" hiển thị thẻ trạng thái công việc (Ví dụ: "Chờ duyệt", "Đã xử lý").
  - **Tương Tác Nhấp Chuột (Click-through)**:
    - Khi người dùng nhấp vào một mục: Hệ thống tự động kích hoạt đánh dấu đã đọc ngầm, giảm số lượng badge ngay lập tức và điều hướng trình duyệt an toàn đến địa chỉ liên kết đối tượng.
  - **Phần Chân**: Nút liên kết chuyển đến Trang quản lý toàn bộ thông báo tập trung.

- **Trạng Thái Rỗng (Empty State)**:
  - Khi không có thông báo nào trong danh mục được chọn, hiển thị thông điệp thông báo trạng thái rỗng thân thiện, thông báo người dùng không có việc cần xử lý.

- **Xử Lý Lỗi Phân Quyền An Toàn (Role Drift Feedback)**:
  - Khi người dùng nhấp vào liên kết đối tượng nhưng đã bị thay đổi quyền truy cập, giao diện bắt mã lỗi `403 Forbidden` và hiển thị thông báo Toast cảnh báo: *"Bạn không còn quyền truy cập dữ liệu này hoặc dữ liệu đã được điều chuyển"*, không làm sập giao diện và không hiển thị trang lỗi hệ thống.

---

### 4.4. Cơ Chế Đồng Bộ Thời Gian Thực Phía Client (Client Polling Mechanics)

Hệ thống triển khai cơ chế kiểm tra định kỳ thông minh (Adaptive Lightweight Polling) giúp cập nhật dữ liệu kịp thời nhưng giảm thiểu tối đa tải máy chủ:

- **Chu Kỳ Hoạt Động Tiêu Chuẩn**: Client thực hiện truy vấn ngầm định kỳ đến endpoint nhẹ `/unread-count/` để cập nhật badge chuông.
- **Thích Ứng Khi Ẩn Tab (Page Visibility API)**: Khi người dùng thu nhỏ trình duyệt hoặc chuyển sang tab làm việc khác, client tự động giãn chu kỳ kiểm tra để tiết kiệm tài nguyên. Khi người dùng mở lại tab, client kích hoạt kiểm tra cập nhật ngay lập tức.
- **Nhận Diện Người Dùng Nhàn Rỗi (Idle Detection)**: Khi không phát hiện tương tác chuột hoặc phím trong thời gian dài, client chuyển sang chu kỳ nghỉ ngơi với tần suất thưa hơn.
- **Chống Đua Yêu Cầu (Concurrency Guard)**: Không phát sinh request kiểm tra mới nếu request thăm dò trước đó chưa hoàn thành.
- **Sẵn Sàng Mở Rộng**: Tầng giao tiếp Client được đóng gói qua một Interface trừu tượng, sẵn sàng chuyển đổi sang cơ chế Server-Sent Events (SSE) hoặc WebSocket trong tương lai mà không phải can thiệp lại giao diện.

---

## 5. Ma Trận Kịch Bản Kiểm Thử & Tiêu Chí Chấp Nhận (Acceptance Criteria & Test Matrix)

Bộ kịch bản kiểm thử dùng để nghiệm thu toàn bộ tính năng của Task 10.1:

### 5.1. Kịch Bản Cô Lập Đa Người Thuê (Multi-Tenant Scenarios)
- [ ] **TC-TENANT-01: Cách ly thông báo giữa hai doanh nghiệp độc lập**
  - *Mô tả*: Người dùng thuộc Tenant A tạo sự kiện phân công công việc.
  - *Kỳ vọng*: Chỉ người nhận thuộc Tenant A nhận được thông báo. Người dùng thuộc Tenant B tuyệt đối không nhìn thấy thông báo này, không có bản ghi nào liên quan trong phạm vi Tenant B.
- [ ] **TC-TENANT-02: Chặn truy cập trái phép qua API khác Tenant (Anti-IDOR)**
  - *Mô tả*: Người dùng Tenant A cố ý gửi request đánh dấu đã đọc hoặc xóa thông báo mang UUID thuộc sở hữu của Tenant B.
  - *Kỳ vọng*: Backend từ chối với mã HTTP `404 Not Found` hoặc `403 Forbidden`, ghi nhận cảnh báo bảo mật.
- [ ] **TC-TENANT-03: Xử lý thông báo cấp hệ thống (System Announcements)**
  - *Mô tả*: Super Admin gửi thông báo bảo trì toàn hệ thống.
  - *Kỳ vọng*: Mọi người dùng ở tất cả các Tenant đều nhận được thông báo với nhãn `SYSTEM`, dữ liệu không bị lộ thông tin riêng tư giữa các bên.

### 5.2. Kịch Bản Vận Hành Nghiệp Vụ Cốt Lõi (Functional Event Scenarios)
- [ ] **TC-EVENT-01: Tiếp nhận và hiển thị thông báo phân công Work Order**
  - *Mô tả*: Phân công Work Order mới cho kỹ thuật viên.
  - *Kỳ vọng*: Kỹ thuật viên nhận được thông báo với mức độ `INFO`, badge chuông tăng lên 1, mở dropdown hiển thị đầy đủ thông tin phiếu và liên kết trực tiếp đến trang chi tiết công việc.
- [ ] **TC-EVENT-02: Tự động đánh dấu đã đọc khi nhấp xem chi tiết**
  - *Mô tả*: Người dùng nhấp vào một thông báo chưa đọc trong danh sách chuông.
  - *Kỳ vọng*: Trạng thái thông báo chuyển thành đã đọc, badge chuông giảm đi 1 ngay lập tức trên giao diện, cơ sở dữ liệu cập nhật `is_read = True` và thời điểm `read_at`.
- [ ] **TC-EVENT-03: Thao tác đánh dấu tất cả đã đọc (Mark all as read)**
  - *Mô tả*: Người dùng bấm nút "Đánh dấu tất cả đã đọc".
  - *Kỳ vọng*: Badge chuông biến mất (về 0), toàn bộ thông báo chuyển sang trạng thái đã đọc, cơ sở dữ liệu cập nhật đồng loạt các bản ghi tương ứng.
- [ ] **TC-EVENT-04: Cảnh báo phụ tùng chạm ngưỡng tồn kho tối thiểu**
  - *Mô tả*: Xuất kho phụ tùng khiến số lượng khả dụng thấp hơn ngưỡng tối thiểu an toàn.
  - *Kỳ vọng*: Hệ thống phát cảnh báo mức `WARNING` gửi riêng cho Thủ kho và Quản lý bảo trì. Kỹ thuật viên thông thường không nhận thông báo này.
- [ ] **TC-EVENT-05: Tự động phát thông báo khi sinh phiếu bảo trì từ kế hoạch PM**
  - *Mô tả*: Tác vụ định kỳ kích hoạt kế hoạch PM và tự động tạo Work Order mới.
  - *Kỳ vọng*: Quản lý bảo trì nhận được thông báo thông tin phiếu mới sinh ra kèm đường dẫn kiểm tra.

### 5.3. Kịch Bản Kiểm Thử Kỹ Thuật & Nghiệp Vụ Phòng Thủ (Defensive & Edge Cases)
- [ ] **TC-OOO-01: Tự động chuyển tiếp khi người nhận nghỉ phép (Delegation / OOO)**
  - *Mô tả*: Kỹ thuật viên A đang bật chế độ nghỉ phép (OOO) và đã đăng ký ủy quyền cho Kỹ thuật viên B. Hệ thống phân công tự động phiếu PM cho A.
  - *Kỳ vọng*: Hệ thống ghi nhận thông báo cho A, đồng thời tự động phát thông báo chuyển tiếp (`TASK_DELEGATED`) cho Kỹ thuật viên B với thông tin ủy quyền rõ ràng trong metadata, đảm bảo công việc được tiếp nhận.
- [ ] **TC-ESCALATE-01: Tự động leo thang cảnh báo khẩn cấp bị bỏ qua quá hạn**
  - *Mô tả*: Sự cố dừng máy nghiêm trọng (`CRITICAL`) được gửi tới kỹ thuật viên trực nhưng sau 20 phút kỹ thuật viên vẫn chưa đọc hoặc tiếp nhận (`is_read = False`).
  - *Kỳ vọng*: Tác vụ kiểm tra phát hiện quá thời hạn SLA, tự động phát sinh thông báo leo thang (`WO_ESCALATED`) gửi trực tiếp cho Quản lý bảo trì thông báo sự cố chưa có người tiếp nhận.
- [ ] **TC-ACTION-01: Phân định trạng thái Đã đọc và Cần hành động**
  - *Mô tả*: Quản lý mở thông báo yêu cầu duyệt xuất kho (được đánh dấu `is_read = True`), nhưng chưa bấm Phê duyệt.
  - *Kỳ vọng*: Badge chuông giảm số lượng, nhưng thông báo vẫn nằm trong tab "Cần hành động" với trạng thái `action_status = 'PENDING'`. Khi người dùng thực hiện phê duyệt tại trang kho, trạng thái mới chuyển thành `RESOLVED`.
- [ ] **TC-SNAPSHOT-01: Toàn vẹn thông tin người gửi khi tài khoản gốc bị xóa**
  - *Mô tả*: Quản lý giao việc cho nhân viên rồi nghỉ việc (tài khoản bị xóa, `sender_id` trở thành NULL). Nhân viên xem lại lịch sử thông báo cũ.
  - *Kỳ vọng*: Giao diện và API vẫn hiển thị chính xác tên người giao việc ban đầu nhờ trường snapshot (`sender_name_snapshot`), không bị lỗi NULL và không crash trang.
- [ ] **TC-DRIFT-01: Xử lý an toàn khi người dùng bị thay đổi vai trò sau khi nhận tin**
  - *Mô tả*: Người dùng bị thu hồi quyền quản lý sau khi đã nhận thông báo duyệt ngân sách cũ. Người dùng nhấp vào link duyệt trong thông báo.
  - *Kỳ vọng*: API đích trả về mã `403 Forbidden`. Giao diện hiển thị Toast thông báo người dùng không còn quyền truy cập dữ liệu một cách trang nhã, không gây lỗi màn hình trắng.
- [ ] **TC-EDGE-01: Xử lý khi đối tượng liên kết đã bị gỡ bỏ**
  - *Mô tả*: Người dùng nhấp vào liên kết của một Work Order đã bị hủy hoặc xóa.
  - *Kỳ vọng*: Giao diện không bị lỗi hệ thống, hiển thị thông báo giải thích đối tượng không còn tồn tại.
- [ ] **TC-EDGE-02: Người nhận bị khóa tài khoản trước khi phát thông báo**
  - *Mô tả*: Tài khoản của kỹ thuật viên bị khóa hoặc vô hiệu hóa ngay trước khi tác vụ tạo thông báo kích hoạt.
  - *Kỳ vọng*: Tác vụ phát hiện tài khoản không còn hoạt động (`is_active = False`), bỏ qua việc tạo thông báo và ghi nhận log giải thích.
- [ ] **TC-EDGE-03: Đồng bộ trạng thái đọc đồng thời trên nhiều thiết bị**
  - *Mô tả*: Người dùng mở Web và ứng dụng Mobile cùng lúc, sau đó bấm đọc thông báo trên điện thoại.
  - *Kỳ vọng*: Trong chu kỳ thăm dò tiếp theo, chuông thông báo trên Web tự động cập nhật giảm số lượng chưa đọc mà không phát sinh xung đột dữ liệu.

---

## 6. Implementation Notes — For Implementation Phase Only

> [!IMPORTANT]
> **REFERENCE ONLY — DO NOT IMPLEMENT OR MODIFY CODE BASED ON THIS SECTION DURING SPEC REVIEW. These notes are intended for the implementation phase after the specification is approved.**

Phần này lưu trữ các chỉ dẫn kỹ thuật hạ tầng chi tiết để các kỹ sư tham khảo trong quá trình hiện thực hóa mã nguồn của Phase 10.1 sau này:

### 6.1. Quy Ước Khóa Bộ Đệm & Cơ Chế Kiểm Soát Trùng Lặp (Redis Caching & Keys)
- **Quy tắc đặt tên khóa khử trùng lặp (Deduplication Key)**:
  `notif_dedup:{tenant_id}:{event_type}:{entity_id}:{recipient_id}`
  - Thời gian sống (TTL): Mặc định 300 giây (5 phút) cho các cảnh báo sự cố lặp lại.
  - Hành vi: Nếu khóa đã tồn tại, thực hiện cập nhật `occurrence_count` và thời điểm cập nhật trên bản ghi thông báo đã tạo trước đó thay vì tạo bản ghi mới.
- **Quy tắc đặt tên khóa lưu đệm số lượng chưa đọc (Unread Count Cache Key)**:
  `notif_unread_count:{tenant_id}:{user_id}`
  - Thời gian sống (TTL): 60 giây.
  - Hành vi: Bị xóa hoặc giảm giá trị ngay khi người dùng gọi các endpoint `mark-read` hoặc `mark-all-read`.

### 6.2. Cấu Trúc Hàng Đợi Celery & Chính Sách Thử Lại (Celery Queues & Retries)
- **Phân tách hàng đợi Celery**:
  - `celery_queue: notifications` — Hàng đợi chuyên biệt ưu tiên cao cho việc phát thông báo (`send_notification_task`).
  - `celery_queue: periodic` — Hàng đợi dành cho các tác vụ Celery Beat quét định kỳ (kiểm tra Work Order quá hạn, quét cảnh báo khẩn cấp cần leo thang `escalation_deadline`, quét kế hoạch PM định kỳ).
- **Chính sách thử lại (Retry Policy)**:
  - Khi việc kết nối tới dịch vụ đẩy thông báo bên ngoài (FCM Push hoặc SMTP Email) gặp sự cố mạng tạm thời:
    - Thử lại với cơ chế lùi bước theo cấp số nhân (Exponential Backoff): Lần 1 sau 10s, lần 2 sau 60s, lần 3 sau 300s.
    - Sau tối đa 3 lần thất bại: Ghi nhận cảnh báo vào bảng ghi nhận kiểm toán (`AuditLog`) mà không làm gián đoạn worker.

### 6.3. Tối Ưu Hóa Ghi Dữ Liệu Hàng Loạt (Bulk Persistence)
- Khi phát thông báo tới nhiều người nhận cùng lúc (ví dụ: cảnh báo khẩn cấp tới toàn bộ quản lý và kỹ sư):
  - Khởi tạo danh sách các thực thể `Notification` trong bộ nhớ và lưu đồng thời bằng cơ chế ghi hàng loạt (`bulk_create`) trong một câu lệnh SQL duy nhất, đảm bảo tính nguyên tử và giảm tải kết nối cơ sở dữ liệu.
  - Luôn đảm bảo giá trị `tenant_id` được gán tường minh trên từng thực thể trước khi thực hiện ghi hàng loạt.

### 6.4. Tham Chiếu Cơ Chế Adaptive Polling Phía Frontend
- Mã kịch bản phía Client nên kiểm tra thuộc tính `document.visibilityState`:
  - Trạng thái `visible`: Chu kỳ thăm dò thông thường (10–15 giây).
  - Trạng thái `hidden`: Giãn chu kỳ thăm dò lên 60 giây.
- Kỹ thuật chống xung đột (In-flight Request Lock): Sử dụng cờ boolean để kiểm soát yêu cầu đang gửi; nếu yêu cầu thăm dò trước đó chưa nhận được phản hồi, bỏ qua chu kỳ hiện tại để tránh dồn ứ request khi đường truyền mạng suy giảm.

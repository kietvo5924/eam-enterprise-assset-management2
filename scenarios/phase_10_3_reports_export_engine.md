# Thiết Kế Hệ Thống & Đặc Tả Kỹ Thuật: Task 10.3 — Enterprise Reports & Export Engine (Celery & MinIO)

Tài liệu này xác định kiến trúc kỹ thuật, công thức kế toán tài chính và quản trị bảo trì theo chuẩn Việt Nam (VAS 03 / Kế toán dồn tích), quy trình xuất dữ liệu lớn bất đồng bộ (Async Big-Data Export), kiến trúc lưu trữ đám mây MinIO, danh mục API và **bộ kịch bản kiểm thử chấp nhận & trường hợp biên (Acceptance Criteria & Edge Cases)** cho **Phân Hệ Báo Cáo Doanh Nghiệp & Động Cơ Xuất Tệp (Enterprise Reports & Export Engine)** của hệ thống Quản lý Tài sản Doanh nghiệp (EAM).

Tài liệu đóng vai trò là **Đặc Tả Kỹ Thuật & Chuẩn Kiểm Thử (Technical Specification & Audit Baseline)** nhằm đối chiếu, rà soát và thực thi trọn vẹn toàn bộ tính năng mà không bị thiếu sót bất kỳ nghiệp vụ enterprise nào.

---

## 1. Mục Tiêu & Phạm Vi (Objective & Scope)

Phân hệ Báo cáo Doanh nghiệp phục vụ mục đích phân tích hồi cứu (Retrospective Analytics), kiểm toán chi phí bảo trì, đánh giá vòng đời thiết bị (Life-cycle Assessment) và lập kế hoạch ngân sách vận hành cho các nhà máy tại Việt Nam:
- **Xử lý khối lượng dữ liệu lớn an toàn**: Xử lý hàng chục nghìn bản ghi với nhiều tiêu chí lọc kết hợp mà không làm nghẽn ứng dụng hoặc tràn bộ nhớ máy chủ (OOM).
- **Hạch toán chi phí & hiệu suất chuẩn xác (Kế toán Việt Nam)**: Áp dụng chuẩn khấu hao đường thẳng có chặn sàn, phân tách rạch ròi CAPEX vs OPEX, kế toán dồn tích chi phí đa kỳ, định giá xuất kho bình quân di động kèm bút toán chênh lệch giá, và quy tắc đo lường tuân thủ bảo trì định kỳ 10%.
- **Xuất tệp bất đồng bộ, bảo mật & tối ưu tài nguyên**: Khởi tạo tác vụ nền qua Celery, tải tệp lên kho lưu trữ MinIO phân lập theo Tenant, dọn dẹp tự động sau 7 ngày, chống tấn công tiêm mã công thức (CSV/Formula Injection) và cấp liên kết tải có chữ ký số (Presigned URL).

---

## 2. Ràng Buộc Kế Thừa Hệ Thống (Existing System Constraints & Codebase Reuse)

- **Tái Sử Dụng Mô Hình Multi-Tenancy**: Bảng quản lý tác vụ xuất (`ExportJob`) bắt buộc kế thừa `BaseTenantModel`, tự động gán và lọc theo `tenant_id` qua `TenantManager`.
- **Đơn Vị Tiền Tệ Cố Định**: Hệ thống vận hành quy mô tại Việt Nam, đơn vị tiền tệ tiêu chuẩn cho mọi giao dịch chi phí là **Việt Nam Đồng (VNĐ)**. Mọi phép toán tài chính sử dụng kiểu dữ liệu `Decimal` với độ chính xác tuyệt đối, không áp dụng quy đổi ngoại tệ phức tạp.
- **Tái Sử Dụng Thực Thể Nghiệp Vụ Có Sẵn**:
  - `Asset`: Nguyên giá (`purchase_cost`), ngày đưa vào sử dụng, thời gian khấu hao, giá trị thanh lý ước tính (`salvage_value`), trung tâm chi phí hiện tại.
  - `WorkOrder`: Loại công việc (`type`), cờ vốn hóa nâng cấp (`is_capitalized`), chi phí thực tế (`actual_cost`), ngày đến hạn (`due_date`), ngày hoàn thành (`completed_at`).
  - `StockTransaction`: Phiếu xuất kho phụ tùng (`issue_date`), đơn giá xuất, số lượng xuất, Work Order liên kết.
  - `LaborLog`: Nhật ký chấm công bảo trì (`work_date`), số giờ làm, đơn giá giờ công kỹ thuật viên.
  - `SparePart`: Số lượng tồn kho (`current_stock`), đơn vị tính, đơn giá bình quân di động (`unit_cost`).
- **Tích Hợp Hệ Thống Thông Báo Thời Gian Thực (Task 10.1)**: Khi tác vụ xuất tệp hoàn tất hoặc thất bại, hệ thống tự động phát sinh thông báo cho người yêu cầu kèm đường dẫn tải về an toàn.

---

## 3. Yêu Cầu Nghiệp Vụ & Quy Tắc Cốt Lõi (Business Requirements & Core Rules)

Toàn bộ logic tính toán báo cáo và xuất tệp phải tuân thủ nghiêm ngặt 10 quy tắc nghiệp vụ phòng thủ sau:

### Quy Tắc 1: Ràng Buộc Chặn Sàn Khấu Hao Tài Sản Tránh Giá Trị Âm (Depreciation Floor Guardrail - VAS 03)
- **Điểm Yếu Nghiệp Vụ**: Trong kế toán tài sản theo chuẩn Việt Nam (VAS 03), nếu trừ hao mòn theo công thức cơ học, một thiết bị có thời hạn khấu hao 5 năm nhưng thực tế sử dụng sang năm thứ 6 hoặc thứ 8 sẽ có giá trị còn lại (Net Book Value) bị **ÂM**, làm sai lệch bảng cân đối kế toán.
- **Quy Tắc Bắt Buộc**:
  1. Áp dụng phương pháp Khấu hao đường thẳng (Straight-Line Depreciation Method).
  2. Ràng buộc chặn sàn tuyệt đối: Giá trị sổ sách còn lại không bao giờ được thấp hơn Giá trị thanh lý ước tính (Salvage Value, mặc định 0 VNĐ hoặc giá trị xác định trước):
     $$\text{Net Book Value} = \max(\text{Nguyên giá} - \text{Khấu hao tích lũy}, \;\; \text{Giá trị thanh lý ước tính})$$
  3. Khi thời gian sử dụng vượt quá thời hạn khấu hao định mức: Giá trị sổ sách cố định ở mức sàn và gán nhãn trạng thái tài chính `"Đã khấu hao hết - Đang vận hành"`.

### Quy Tắc 2: Đề Xuất Thanh Lý Theo Tỷ Lệ RRR $\ge 70\%$ & Phân Tách CAPEX vs OPEX (Capitalization Guardrail)
- **Điểm Yếu Nghiệp Vụ**:
  - Thiết bị hỏng hóc vặt liên miên, chi phí sửa chữa cộng dồn vượt quá tiền mua máy mới nhưng hệ thống không phát hiện, gây thất thoát ngân sách.
  - **Bẫy nhầm lẫn CAPEX vs OPEX**: Khi nhà máy đại tu lớn (thay thế động cơ chính, nâng cấp cụm điều khiển cốt lõi) với chi phí hàng trăm triệu VNĐ, đây là chi phí đầu tư vốn hóa (**CAPEX**) giúp kéo dài tuổi thọ tài sản, KHÔNG phải chi phí sửa chữa vận hành (**OPEX**). Nếu cộng nhầm khoản này vào tử số của RRR, chỉ số RRR sẽ lập tức vượt $70\%$, khiến hệ thống báo động thanh lý oan sai một thiết bị vừa mới được nâng cấp đại tu hoàn hảo.
- **Quy Tắc Bắt Buộc**:
  1. Cho phép đánh dấu Work Order là chi phí vốn hóa nâng cấp tài sản: `is_capitalized = True (CAPEX)`.
  2. **Khi tính Tỷ Lệ Sửa Chữa Trên Thay Thế (RRR)**:
     $$\text{RRR} = \frac{\sum \text{Chi phí sửa chữa vận hành tích lũy (OPEX)}}{\text{Giá trị thay thế tương đương}} \times 100\%$$
     Tuyệt đối **LOẠI TRỪ** toàn bộ các Work Order có `is_capitalized = True` khỏi tử số chi phí sửa chữa tích lũy.
  3. **Xử lý vốn hóa**: Chi phí của Work Order CAPEX được tự động **cộng dồn vào Nguyên giá mới** (`capitalized_cost`), đồng thời thiết lập lại thời gian sử dụng và tự động tính toán lại lịch khấu hao đường thẳng mới từ kỳ kế toán tiếp theo.
  4. Cảnh báo kinh tế: Khi $\text{RRR} \ge 70\%$ (chỉ tính OPEX), tự động gắn cờ "Tài sản kém hiệu quả kinh tế (Bad Actor)" và kiến nghị thanh lý/thay thế.

### Quy Tắc 3: Kế Toán Dồn Tích Chi Phí Bảo Trì Đa Kỳ (Cross-Period Accrual Guardrail)
- **Điểm Yếu Nghiệp Vụ**: Một phiếu sửa chữa lớn bắt đầu từ ngày 25/11 nhưng đến ngày 10/12 mới nghiệm thu hoàn thành (`completed_at`). Kỹ thuật viên xuất phụ tùng A vào tháng 11, xuất phụ tùng B và phát sinh công thợ vào tháng 12. Nếu dồn toàn bộ tổng chi phí của Work Order vào ngày hoàn thành, báo cáo tháng 11 sẽ bị trống chi phí (sai lệch ngân sách), trong khi tháng 12 lại bị đội chi phí đột biến.
- **Quy Tắc Bắt Buộc**:
  1. Báo cáo Tổng hợp chi phí hàng tháng (`COST_SUMMARY`) bắt buộc tuân thủ nguyên tắc **Kế toán dồn tích (Accrual Accounting)**:
     - Chi phí vật tư: Hạch toán vào tháng dựa trên **thời điểm phát sinh phiếu xuất kho thực tế** (`StockTransaction.issue_date`).
     - Chi phí nhân công: Hạch toán vào tháng dựa trên **ngày chấm công thực tế của kỹ thuật viên** (`LaborLog.work_date`).
  2. Tuyệt đối không dồn tổng chi phí của cả Work Order vào ngày đóng phiếu (`completed_at`).

### Quy Tắc 4: Miễn Trừ Bảo Trì Định Kỳ Do Trùng Lặp (PM Suppression / Overlap Guardrail)
- **Điểm Yếu Nghiệp Vụ**: Thiết bị có lịch bảo trì định kỳ (PM) vào ngày 15 hàng tháng. Tuy nhiên vào ngày 10, thiết bị gặp sự cố đột xuất (Corrective Maintenance), đội bảo trì đã tháo máy sửa chữa và tiện thể thực hiện toàn bộ checklist bảo dưỡng của kỳ PM luôn. Quản lý quyết định hủy phiếu PM ngày 15 để tránh lãng phí nhân công. Nếu hệ thống đánh dấu phiếu bị hủy này là "Không hoàn thành" hoặc "Trễ hạn", tỷ lệ tuân thủ PM của xưởng sẽ bị tụt oan uổng.
- **Quy Tắc Bắt Buộc**:
  1. Cung cấp trạng thái hủy hợp lệ: `SKIPPED_DUE_TO_OVERLAP` (Bỏ qua do đã thực hiện trong phiếu sửa chữa trước đó, kèm liên kết tới `WorkOrder` tham chiếu).
  2. Khi tính Tỷ lệ Tuân thủ Bảo trì Định kỳ (PM Compliance Rate theo quy tắc 10%):
     $$\text{PM Compliance (\%)} = \frac{\text{Số phiếu PM hoàn thành đúng hạn}}{\text{Tổng phiếu PM đến hạn} - \text{Số phiếu SKIPPED\_DUE\_TO\_OVERLAP}} \times 100\%$$
     Phiếu bị hủy do trùng lặp bắt buộc được **loại trừ hoàn toàn khỏi mẫu số**, bảo toàn tỷ lệ tuân thủ chuẩn xác cho đội ngũ.

### Quy Tắc 5: Định Giá Xuất Kho Bình Quân Di Động & Bút Toán Chênh Lệch Khi Xuất Âm (Moving Average & Price Variance)
- **Điểm Yếu Nghiệp Vụ**:
  - Phụ tùng nhập nhiều đợt với giá khác nhau. Đơn giá xuất kho phải được tính theo chuẩn Bình Quân Gia Quyền Di Động.
  - Trong tình huống khẩn cấp, máy móc dừng đột xuất cần phụ tùng thay thế ngay, thủ kho cho phép xuất hàng trên phần mềm trước (chấp nhận số lượng tồn kho âm tạm thời), vài ngày sau hóa đơn và chứng từ mua hàng mới về để làm phiếu Nhập kho (GRN) chính thức.
- **Quy Tắc Bắt Buộc**:
  1. Khi xuất kho bình thường: Chốt đơn giá xuất theo đơn giá bình quân di động tại thời điểm xuất kho.
  2. Khi xuất kho trong tình trạng tồn kho âm tạm thời: Mượn đơn giá bình quân gần nhất để tạm tính chi phí cho Work Order (`Interim Cost`).
  3. Khi có phiếu Nhập kho thực tế với đơn giá mua mới khác với đơn giá tạm tính: Hệ thống tự động sinh ra bút toán **Chênh lệch giá (Price Variance Adjustment)** để điều chỉnh bổ sung chi phí cho Work Order đã xuất trước đó, bảo đảm số liệu kế toán khớp tuyệt đối với sổ cái.
  4. Khi hoàn trả vật tư xuất dư: Nhập kho lại theo đúng đơn giá xuất ban đầu và tự động khấu trừ vào chi phí của Work Order liên quan.

### Quy Tắc 6: Cắt Lớp Lịch Sử Luân Chuyển Trung Tâm Chi Phí (Temporal Cost Center Slicing Guardrail)
- **Điểm Yếu Nghiệp Vụ**: Một xe nâng hoạt động tại Phân xưởng A (Trung tâm chi phí A) trong Quý 1, sang Quý 2 được điều chuyển sang Phân xưởng B (Trung tâm chi phí B). Nếu báo cáo chi phí cuối năm chỉ đơn thuần JOIN với vị trí/trung tâm chi phí hiện tại của tài sản (`asset.current_cost_center_id`), toàn bộ chi phí bảo trì trong Quý 1 của Phân xưởng A sẽ bị gán oan cho ngân sách của Phân xưởng B.
- **Quy Tắc Bắt Buộc**:
  1. Mọi bản ghi chi phí phát sinh (phiếu xuất kho, giờ công kỹ thuật viên) bắt buộc lưu vết trung tâm chi phí tại thời điểm giao dịch (`cost_center_snapshot`).
  2. Báo cáo phân bổ chi phí theo Trung tâm chi phí/Nhà xưởng phải cắt lớp theo mốc thời gian lịch sử: Chi phí Quý 1 tính cho Phân xưởng A, chi phí Quý 2 tính cho Phân xưởng B.

### Quy Tắc 7: Khống Chế Tác Vụ Xuất Đồng Thời & Phục Hồi Tác Vụ Ma (Concurrency & Zombie Recovery)
- **Điểm Yếu Nghiệp Vụ**: Người dùng bấm liên tiếp nút xuất Excel nhiều lần làm nghẽn hàng đợi Celery. Ngoài ra, khi máy chủ khởi động lại đột ngột, các tác vụ đang chạy bị kẹt ở trạng thái `PROCESSING` vĩnh viễn, người dùng thấy tiến độ treo mãi mãi.
- **Quy Tắc Bắt Buộc**:
  1. Giới hạn tối đa **3 tác vụ xuất đang xử lý đồng thời cho mỗi Tenant** (`MAX_CONCURRENT_EXPORTS_PER_TENANT = 3`). Yêu cầu thứ 4 sẽ bị từ chối với thông báo thân thiện hoặc đưa vào hàng đợi chờ.
  2. Cơ chế phát hiện "Tác vụ ma" (Zombie Job Detection): Celery Beat quét định kỳ, nếu bản ghi `ExportJob` ở trạng thái `PROCESSING` quá 15 phút mà không cập nhật tiến độ, tự động đánh dấu thành `FAILED` với thông báo lỗi rõ ràng.

### Quy Tắc 8: Bảo Mật Kho MinIO, Presigned URL & Tự Động Dọn Dẹp (Storage Retention & Auto-Purge)
- **Điểm Yếu Nghiệp Vụ**: Tệp báo cáo chứa bí mật kinh doanh và dữ liệu tài chính. Nếu lưu công khai hoặc để tệp tồn tại vĩnh viễn, dung lượng ổ đĩa sẽ cạn kiệt và có nguy cơ rò rỉ dữ liệu.
- **Quy Tắc Bắt Buộc**:
  1. Toàn bộ bucket MinIO đặt ở chế độ riêng tư tuyệt đối (`policy: None`), đường dẫn phân vùng theo Tenant: `eam-reports/{tenant_id}/{year}/{month}/{job_id}.{ext}`.
  2. Tải tệp thông qua liên kết tạm thời có chữ ký số (Presigned URL) với thời gian sống tối đa 24 giờ.
  3. Chính sách vòng đời lưu trữ (Lifecycle Retention): Tác vụ ngầm tự động xóa tệp vật lý trên MinIO sau **7 ngày** kể từ khi hoàn tất và chuyển trạng thái của `ExportJob` thành `EXPIRED`.

### Quy Tắc 9: An Toàn Tệp Bảng Tính & Chống Tiêm Mã Công Thức (CSV / Formula Injection Guardrail)
- **Điểm Yếu Nghiệp Vụ**: Kỹ thuật viên nhập mô tả hoặc tên phụ tùng chứa các ký tự đặc biệt: `=SUM(...)`, `@cmd`, `+12345`, `-delete...`. Khi người quản lý mở tệp Excel/CSV xuất ra, phần mềm bảng tính sẽ thực thi công thức hoặc kích hoạt mã macro độc hại.
- **Quy Tắc Bắt Buộc**:
  1. Bộ lọc Export Engine bắt buộc kiểm tra từng ô dữ liệu chuỗi (String cell).
  2. Nếu ô bắt đầu bằng các ký tự `=`, `+`, `-`, `@`, `\t`, `\r`, hệ thống tự động chèn thêm ký tự dấu nháy đơn `'` ở đầu chuỗi để phần mềm bảng tính xử lý thuần túy dưới dạng văn bản (Plain text).

### Quy Tắc 10: Độ Chính Xác Số Học Tài Chính Tuyệt Đối (Decimal Precision & Banker's Rounding)
- **Điểm Yếu Nghiệp Vụ**: Phép tính tiền tệ VNĐ nếu sử dụng kiểu số thực `float` trong Python sẽ gây ra sai số nhị phân dấu phẩy động (ví dụ: $0.1 + 0.2 = 0.30000000000000004$), dẫn đến tổng chi phí báo cáo bị lệch vài đồng so với hóa đơn kế toán.
- **Quy Tắc Bắt Buộc**:
  1. Bắt buộc dùng kiểu dữ liệu `Decimal` trong Python và `DECIMAL(18, 2)` trong PostgreSQL cho mọi trường tiền tệ, đơn giá và chi phí.
  2. Sử dụng quy tắc làm tròn tiêu chuẩn tài chính `ROUND_HALF_UP` cho đơn vị VNĐ (không lưu số lẻ thập phân cho tổng tiền VNĐ cuối cùng).

---

## 4. Yêu Cầu Chức Năng & Luồng Xử Lý (Functional Requirements & Workflows)

### 4.1. Bốn Phân Hệ Báo Cáo Chuyên Sâu
1. **Báo Cáo Khấu Hao & Định Giá Tài Sản (`ASSET_VALUATION`)**:
   - Thống kê nguyên giá ban đầu, chi phí đại tu vốn hóa (CAPEX), nguyên giá mới sau vốn hóa.
   - Khấu hao tích lũy theo phương pháp đường thẳng (chặn sàn ở mức giá trị thanh lý).
   - Tỷ lệ RRR chuẩn xác (chỉ tính chi phí sửa chữa OPEX, loại trừ CAPEX) và danh sách thiết bị đề xuất thanh lý khi $\text{RRR} \ge 70\%$.
2. **Báo Cáo Hiệu Suất Bảo Trì & SLA (`MAINTENANCE_PERFORMANCE`)**:
   - Tỷ lệ hoàn thành công việc đúng hạn, tỷ lệ tuân thủ PM Compliance (quy tắc 10%, đã loại trừ các phiếu `SKIPPED_DUE_TO_OVERLAP`).
   - Thời gian sửa chữa trung bình (MTTR) phân bổ theo mức độ nghiêm trọng và phân xưởng.
   - Bóc tách giờ công bảo trì trong giờ và ngoài giờ theo từng kỹ thuật viên.
3. **Báo Cáo Tiêu Hao Phụ Tùng & Kho (`SPARE_PARTS`)**:
   - Giá trị tồn kho khả dụng hiện tại tính theo đơn giá bình quân gia quyền di động.
   - Danh sách phụ tùng xuất trong tình trạng tồn kho âm và các bút toán chênh lệch giá (Price Variance) đã ghi nhận.
   - Danh sách vật tư xuất dư đã hoàn trả nhập kho và số tiền khấu trừ vào Work Order.
4. **Báo Cáo Tổng Hợp Chi Phí Bảo Trì (`COST_SUMMARY`)**:
   - Báo cáo theo chuẩn kế toán dồn tích (Accrual Accounting): Chi phí vật tư theo ngày xuất kho, chi phí nhân công theo ngày làm việc.
   - Phân bổ chi phí theo Trung tâm chi phí / Phân xưởng theo đúng lát cắt lịch sử luân chuyển của tài sản.

### 4.2. Quy Trình Xuất Tệp Bất Đồng Bộ (Async Export Pipeline)

```
[Người Dùng Chọn Báo Cáo, Bộ Lọc & Định Dạng (Excel/PDF)]
                     │
                     ▼
[POST /api/v1/reports/export/] ──► Kiểm tra giới hạn (Tối đa 3 jobs/Tenant)
                     │
                     ├── Vượt quá ──► Trả về HTTP 429: "Đang có 3 báo cáo đang xử lý..."
                     │
                     └── Hợp lệ ──► Tạo ExportJob trong PostgreSQL (Status: PENDING)
                                    Trả về ngay: {"jobId": "...", "status": "PENDING"}
                     │
                     ▼
[Celery Worker: Queue reports_export]
   ├── (1) Đọc dữ liệu phân khối từ PostgreSQL: iterator(chunk_size=2000)
   ├── (2) Sanitize chống tiêm mã công thức (CSV/Formula Injection)
   ├── (3) Ghi trực tiếp ra đĩa tạm bằng openpyxl (write_only=True) / ReportLab
   ├── (4) Tải tệp lên MinIO: eam-reports/{tenant_id}/{year}/{month}/{job_id}.{ext}
   └── (5) Cập nhật ExportJob thành COMPLETED, lưu minio_object_key & file_size
                     │
                     ▼
[Thông Báo & Tải Về]
   ├── Kích hoạt thông báo Real-time (Task 10.1): "Báo cáo của bạn đã sẵn sàng"
   └── Người dùng tải: GET /api/v1/reports/export-jobs/{id}/ ──► Cấp Presigned URL (24h)
```

---

## 5. Quy Tắc Bảo Mật, Phân Quyền & Đa Khách Hàng (Security, RBAC & Multi-Tenant Rules)

- **Cô Lập Đa Khách Hàng (Multi-Tenancy)**:
  - Mọi bản ghi `ExportJob` và truy vấn dữ liệu báo cáo bắt buộc gán liền với `tenant_id` của phiên làm việc.
  - Tệp trên MinIO lưu trong bucket riêng biệt với tiền tố `{tenant_id}/`.
  - Nghiêm cấm mọi hành vi truy cập hoặc sinh URL tải tệp thuộc `job_id` của Tenant khác (chống lỗi IDOR).
- **Phân Quyền Theo Vai Trò (RBAC)**:
  - `TENANT_ADMIN` & `MAINTENANCE_MANAGER`: Quyền xem và xuất toàn bộ 4 phân hệ báo cáo.
  - `WAREHOUSE_KEEPER`: Quyền xem và xuất báo cáo liên quan đến phụ tùng, kho và giá trị vật tư.
  - `TECHNICIAN`: Chỉ xem báo cáo giờ công cá nhân, không truy cập báo cáo tài chính và định giá tài sản.

---

## 6. Mô Hình Dữ Liệu & Thực Thể (Data Model & Schema)

### Bảng `export_jobs` (Quản lý vòng đời tác vụ xuất)
- `id`: `UUID` (Primary Key, default: `uuid4`).
- `tenant_id`: `UUID` (Foreign Key tới `Tenant`, kế thừa `BaseTenantModel`).
- `user_id`: `UUID` (Foreign Key tới `User`, người yêu cầu xuất).
- `report_type`: `VARCHAR(64)` (`ASSET_VALUATION`, `MAINTENANCE_PERFORMANCE`, `SPARE_PARTS`, `COST_SUMMARY`).
- `file_format`: `VARCHAR(16)` (`XLSX`, `PDF`, `CSV`).
- `filter_params`: `JSONB` (Các tham số lọc ngày, danh mục, phân xưởng đã áp dụng).
- `status`: `VARCHAR(16)` (`PENDING`, `PROCESSING`, `COMPLETED`, `FAILED`, `EXPIRED`).
- `progress_percent`: `INTEGER` (0 đến 100%).
- `file_name`: `VARCHAR(255)` (Tên tệp hiển thị).
- `minio_object_key`: `VARCHAR(500)` (Đường dẫn lưu trên MinIO, `null=True`).
- `file_size_bytes`: `BIGINT` (Dung lượng tệp thực tế, `null=True`).
- `error_message`: `TEXT` (Chi tiết lỗi nếu thất bại, `null=True`).
- `created_at`: `TIMESTAMP WITH TIME ZONE` (Thời điểm khởi tạo).
- `completed_at`: `TIMESTAMP WITH TIME ZONE` (Thời điểm hoàn tất, `null=True`).
- `expires_at`: `TIMESTAMP WITH TIME ZONE` (Thời điểm tệp MinIO bị xóa tự động, mặc định `completed_at + 7 ngày`).

Chỉ mục tối ưu:
- `idx_export_tenant_status_created`: `[tenant_id, status, created_at DESC]`.
- `idx_export_tenant_user_active`: `[tenant_id, user_id, status]`.

---

## 7. Đặc Tả Giao Diện Lập Trình (API Specifications & Contracts)

### Danh Mục Endpoints:

| Phương Thức | Đường Dẫn | Chức Năng |
| :--- | :--- | :--- |
| `POST` | `/api/v1/reports/preview/` | Lấy dữ liệu xem trước cho bảng và biểu đồ (tối đa 50 bản ghi) |
| `POST` | `/api/v1/reports/export/` | Khởi tạo tác vụ xuất file bất đồng bộ (trả về `job_id`) |
| `GET` | `/api/v1/reports/export-jobs/{id}/` | Thăm dò tiến độ tác vụ và lấy liên kết tải tệp khi hoàn tất |
| `GET` | `/api/v1/reports/export-jobs/` | Danh sách lịch sử các yêu cầu xuất gần đây của người dùng |

### Cấu Trúc Dữ Liệu Mẫu:

#### 1. Khởi tạo tác vụ xuất (`POST /api/v1/reports/export/`):
- **Request Body**:
```json
{
  "reportType": "COST_SUMMARY",
  "fileFormat": "XLSX",
  "filters": {
    "dateFrom": "2026-08-01",
    "dateTo": "2026-08-31",
    "costCenterId": "cc-plant-a-01",
    "includeCapex": false
  }
}
```
- **Response Thành Công (202 Accepted)**:
```json
{
  "success": true,
  "data": {
    "jobId": "e9b23c44-55d1-4bb2-8ef0-901122334455",
    "status": "PENDING",
    "message": "Yêu cầu xuất báo cáo đã được tiếp nhận và đang xử lý ngầm."
  }
}
```
- **Response Khi Vượt Quá 3 Jobs Đồng Thời (429 Too Many Requests)**:
```json
{
  "success": false,
  "error": {
    "code": "CONCURRENT_EXPORT_LIMIT_EXCEEDED",
    "message": "Bạn đang có 3 tác vụ xuất đang xử lý. Vui lòng chờ tác vụ trước hoàn tất."
  }
}
```

#### 2. Thăm dò tiến độ & Lấy liên kết tải (`GET /api/v1/reports/export-jobs/{id}/`):
```json
{
  "success": true,
  "data": {
    "jobId": "e9b23c44-55d1-4bb2-8ef0-901122334455",
    "reportType": "COST_SUMMARY",
    "fileFormat": "XLSX",
    "status": "COMPLETED",
    "progressPercent": 100,
    "fileName": "BaoCao_TongHopChiPhi_202608.xlsx",
    "fileSizeBytes": 524288,
    "downloadUrl": "https://minio.internal.eam/eam-reports/tenant-uuid/2026/09/e9b2.xlsx?X-Amz-Signature=...",
    "expiresAt": "2026-09-24T11:30:00Z"
  }
}
```

---

## 8. Đặc Tả Trải Nghiệm Người Dùng (UI/UX Behavioral Specifications)

- **Giao diện phân hệ đa tab**: Cho phép người dùng chuyển đổi mượt mà giữa 4 phân hệ báo cáo mà không tải lại toàn bộ trang.
- **Bộ lọc nghiệp vụ thông minh**:
  - Tùy chọn lọc rõ ràng: "Loại trừ CAPEX khỏi chi phí vận hành" để lãnh đạo đối chiếu bức tranh tài chính chính xác.
  - Bộ chọn khoảng thời gian hỗ trợ nhanh: Tháng này, Tháng trước, Quý này, Năm nay.
- **Tương tác xuất tệp không bị chặn (Non-blocking Interaction)**:
  - Khi bấm nút xuất tệp, giao diện hiển thị thông báo tiếp nhận thành công và hiển thị thanh tiến độ tác vụ ngầm ở góc màn hình.
  - Người dùng có thể tiếp tục thao tác các chức năng khác trong khi tệp đang được xử lý.
- **Tải tệp an toàn**:
  - Nút tải tệp hiển thị kèm dung lượng và cảnh báo hạn lưu trữ: *"Tệp sẽ tự động hủy trên hệ thống sau 7 ngày"*.

---

## 9. Tiêu Chí Chấp Nhận & Ma Trận Kịch Bản Kiểm Thử (Acceptance Criteria & Test Matrix)

Dưới đây là bảng ma trận kiểm thử chi tiết hóa toàn bộ 16 kịch bản chấp nhận và trường hợp biên (Edge Cases):

### 9.1. Ma Trận Kịch Bản Nghiệp Vụ Tài Chính & Bảo Trì

- [ ] **TC-REP-01: Ràng buộc chặn sàn khấu hao tài sản (Không âm Net Book Value)**
  - *Mô tả*: Thiết bị nguyên giá 100,000,000 VNĐ, khấu hao trong 5 năm, giá trị thanh lý ước tính 5,000,000 VNĐ. Thiết bị đã vận hành sang năm thứ 7.
  - *Kỳ vọng*: Giá trị sổ sách còn lại dừng chính xác ở mức 5,000,000 VNĐ; không bao giờ bị âm; hiển thị trạng thái `"Đã khấu hao hết - Đang vận hành"`.

- [ ] **TC-REP-02: Nhận diện kiến nghị thanh lý thiết bị (RRR $\ge 70\%$)**
  - *Mô tả*: Máy nén khí có giá trị thay thế 200,000,000 VNĐ, tổng chi phí sửa chữa OPEX tích lũy đạt 145,000,000 VNĐ ($72.5\%$).
  - *Kỳ vọng*: Báo cáo định giá tài sản đánh dấu thiết bị kèm cảnh báo đề xuất lập hội đồng thanh lý và đầu tư mới.

- [ ] **TC-REP-03: Đại tu, nâng cấp tài sản làm thay đổi nguyên giá (CAPEX vs OPEX)**
  - *Mô tả*: Thiết bị được đại tu thay động cơ chính trị giá 80,000,000 VNĐ, đánh dấu `is_capitalized = True (CAPEX)`. Tổng chi phí sửa chữa thường (OPEX) trước đó là 30,000,000 VNĐ. Giá thay thế là 150,000,000 VNĐ.
  - *Kỳ vọng*: Khoản 80,000,000 VNĐ **không được tính vào tử số của RRR** ($\text{RRR} = \frac{30}{150} = 20\%$, không bị báo động thanh lý sai). Khoản này được cộng vào Nguyên giá để tính lại lịch khấu hao đường thẳng mới.

- [ ] **TC-REP-04: Ghi nhận chi phí cho công việc kéo dài qua nhiều kỳ kế toán (Cross-period Accrual)**
  - *Mô tả*: Một Work Order sửa chữa lớn phát sinh từ 25/11 đến 10/12 mới hoàn thành (`completed_at`). Xuất vật tư 20,000,000 VNĐ vào ngày 26/11 và 15,000,000 VNĐ vào ngày 05/12.
  - *Kỳ vọng*: Báo cáo chi phí tháng 11 ghi nhận chính xác 20,000,000 VNĐ; báo cáo tháng 12 ghi nhận 15,000,000 VNĐ. Tuyệt đối không dồn toàn bộ 35,000,000 VNĐ vào tháng 12.

- [ ] **TC-REP-05: Ghi đè và bỏ qua bảo trì định kỳ do trùng lặp (PM Suppression / Overlap)**
  - *Mô tả*: Máy có lịch PM vào ngày 15. Ngày 10 máy bị sự cố, đội bảo trì đã xử lý xong sự cố và làm luôn checklist bảo dưỡng định kỳ. Quản lý hủy phiếu PM ngày 15 với lý do `SKIPPED_DUE_TO_OVERLAP`.
  - *Kỳ vọng*: Phiếu bị hủy này bị **loại trừ hoàn toàn khỏi mẫu số** tính tỷ lệ tuân thủ PM Compliance (quy tắc 10%), không bị đánh dấu là "Trễ hạn" hay "Thất bại".

- [ ] **TC-REP-06: Tính toán giá vốn di động khi kho xuất âm (Negative Inventory Valuation)**
  - *Mô tả*: Kỹ thuật viên xuất gấp 2 vòng bi khi tồn kho trên hệ thống đang bằng 0 (xuất âm thành -2). Đơn giá bình quân gần nhất là 500,000 VNĐ. 3 ngày sau có phiếu Nhập kho mới với đơn giá thực tế 550,000 VNĐ.
  - *Kỳ vọng*: Work Order tạm tính chi phí ban đầu là $2 \times 500,000 = 1,000,000$ VNĐ. Khi có phiếu Nhập kho, hệ thống tự động sinh bút toán chênh lệch giá (Price Variance) bổ sung $+100,000$ VNĐ vào chi phí thực tế của Work Order.

- [ ] **TC-REP-07: Tài sản luân chuyển giữa các trung tâm chi phí (Temporal Cost Center Slicing)**
  - *Mô tả*: Xe nâng hoạt động tại Phân xưởng A trong Quý 1, sang Quý 2 được điều chuyển sang Phân xưởng B. Chi phí bảo trì phát sinh trong Quý 1 là 10,000,000 VNĐ, Quý 2 là 15,000,000 VNĐ.
  - *Kỳ vọng*: Báo cáo phân bổ chi phí theo Phân xưởng ghi nhận đúng 10,000,000 VNĐ cho Phân xưởng A và 15,000,000 VNĐ cho Phân xưởng B. Vị trí hiện tại ở Phân xưởng B không được áp đặt lên chi phí lịch sử của Quý 1.

- [ ] **TC-REP-08: Đo lường tuân thủ PM theo quy tắc 10% (10% Compliance Rule)**
  - *Mô tả*: Phiếu bảo trì định kỳ chu kỳ 30 ngày, ngày đến hạn là 20/08. Kỹ thuật viên hoàn thành vào ngày 25/08 (trễ 5 ngày $> 3$ ngày $= 10\%$).
  - *Kỳ vọng*: Phiếu được phân loại vào nhóm hoàn thành trễ hạn và làm giảm tỷ lệ `pm_compliance_rate`.

- [ ] **TC-REP-09: Hoàn trả vật tư xuất dư nhập lại kho**
  - *Mô tả*: Kỹ thuật viên xuất 5 lít dầu bảo dưỡng (đơn giá 100,000 VNĐ/lít) nhưng chỉ dùng 3 lít, làm phiếu hoàn trả 2 lít vào kho.
  - *Kỳ vọng*: Kho nhập lại 2 lít theo đúng đơn giá 100,000 VNĐ; chi phí Work Order tự động giảm trừ $200,000$ VNĐ.

### 9.2. Ma Trận Kịch Bản Kỹ Thuật, Hiệu Năng & An Toàn

- [ ] **TC-PERF-01: Xuất tập dữ liệu lớn không bị tràn bộ nhớ (Chunking & Streaming)**
  - *Mô tả*: Xuất báo cáo lịch sử chi phí chứa 50,000 bản ghi ra tệp Excel.
  - *Kỳ vọng*: Worker xử lý theo từng khối `chunk_size=2000`, ghi trực tiếp vào đĩa tạm bằng `openpyxl(write_only=True)`; RAM duy trì ổn định dưới 200MB.

- [ ] **TC-PERF-02: Giới hạn tác vụ xuất đồng thời cho mỗi Tenant (Concurrency Limit)**
  - *Mô tả*: Một người dùng gửi liên tiếp 4 yêu cầu xuất báo cáo lớn trong vòng 10 giây.
  - *Kỳ vọng*: 3 yêu cầu đầu tiên được tiếp nhận (HTTP 202); yêu cầu thứ 4 bị từ chối với mã HTTP 429 kèm thông báo giới hạn.

- [ ] **TC-SEC-01: Chống tấn công tiêm mã công thức bảng tính (CSV / Formula Injection)**
  - *Mô tả*: Tên phụ tùng hoặc ghi chú bảo trì chứa chuỗi `=SUM(1+1)` hoặc `@cmd|' /C calc'!A0`.
  - *Kỳ vọng*: Tệp Excel/CSV xuất ra tự động thêm dấu nháy đơn `'` ở đầu chuỗi (`'=SUM(1+1)`); khi mở tệp trên Excel hiển thị dạng văn bản thuần túy, không kích hoạt công thức.

- [ ] **TC-SEC-02: Phục hồi tác vụ ma khi Worker bị khởi động lại (Zombie Job Auto-Recovery)**
  - *Mô tả*: Worker đang xuất báo cáo thì server bị restart đột ngột, bản ghi `ExportJob` bị kẹt ở trạng thái `PROCESSING`.
  - *Kỳ vọng*: Tác vụ Celery Beat sau 15 phút quét thấy job không cập nhật tiến độ, tự động chuyển thành `FAILED` với thông báo lỗi rõ ràng.

- [ ] **TC-SEC-03: Tự động xóa tệp MinIO sau 7 ngày (Retention Auto-Purge)**
  - *Mô tả*: Kiểm tra các tệp báo cáo đã hoàn tất xuất quá 7 ngày trước đó.
  - *Kỳ vọng*: Tác vụ Celery Beat hàng đêm xóa thành công tệp vật lý trên MinIO và cập nhật trạng thái `ExportJob` thành `EXPIRED`.

- [ ] **TC-SEC-04: Cách ly tệp xuất giữa các tổ chức (Multi-Tenant Isolation)**
  - *Mô tả*: Người dùng thuộc Tenant A gọi API lấy liên kết tải tệp mang `job_id` của Tenant B.
  - *Kỳ vọng*: Hệ thống trả về `404 Not Found` hoặc `403 Forbidden`, tuyệt đối không sinh Presigned URL của Tenant khác.

- [ ] **TC-SEC-05: Độ chính xác số học tài chính VNĐ (Decimal Precision)**
  - *Mô tả*: Tính tổng chi phí của 1,000 dòng vật tư lẻ và khấu hao hàng tháng.
  - *Kỳ vọng*: Sử dụng kiểu `Decimal` trong Python, tổng tiền khớp tuyệt đối từng đồng VNĐ so với phép cộng thủ công, không bị sai số dấu phẩy động của kiểu `float`.

---

## 10. Implementation Notes — For Implementation Phase Only

> [!IMPORTANT]
> **REFERENCE ONLY — DO NOT IMPLEMENT OR MODIFY CODE BASED ON THIS SECTION DURING SPEC REVIEW. These notes are intended for the implementation phase after the specification is approved.**

Phần này lưu trữ các chỉ dẫn kỹ thuật hạ tầng chi tiết để các kỹ sư tham khảo trong quá trình triển khai mã nguồn:

### 10.1. Hàm Làm Sạch Chống Formula Injection
```python
def sanitize_cell_value(value: any) -> any:
    if isinstance(value, str) and value:
        # Nếu chuỗi bắt đầu bằng các ký tự điều khiển công thức bảng tính
        if value[0] in ('=', '+', '-', '@', '\t', '\r'):
            return f"'{value}"
    return value
```

### 10.2. Cấu Hình Ghi Luồng Excel (Openpyxl Streaming)
```python
from openpyxl import Workbook

wb = Workbook(write_only=True)
ws = wb.create_sheet(title="BaoCaoChiPhi")

# Ghi tiêu đề
ws.append(["Mã WO", "Tài Sản", "Ngày Phát Sinh", "Vật Tư (VNĐ)", "Nhân Công (VNĐ)", "Tổng (VNĐ)"])

# Ghi từng dòng từ QuerySet iterator để tiết kiệm RAM
for row in queryset.iterator(chunk_size=2000):
    ws.append([
        sanitize_cell_value(row.code),
        sanitize_cell_value(row.asset_name),
        row.occurred_at.strftime('%d/%m/%Y'),
        int(row.material_cost),
        int(row.labor_cost),
        int(row.total_cost)
    ])

wb.save(temp_file_path)
```

### 10.3. Xử Lý Zombie Job Bằng Celery Beat Heartbeat
```python
from datetime import timedelta
from django.utils import timezone

@shared_task
def cleanup_zombie_export_jobs():
    cutoff = timezone.now() - timedelta(minutes=15)
    zombie_jobs = ExportJob.objects.filter(status='PROCESSING', updated_at__lt=cutoff)
    zombie_jobs.update(
        status='FAILED',
        error_message="Tác vụ bị gián đoạn do hệ thống bảo trì. Vui lòng nhấn xuất lại."
    )
```

---

## 11. Kế Hoạch Triển Khai & Nghiệm Thu (Implementation Checklist)

- [ ] **Task 10.3.1 — Interactive Analytics Interface**
  - [ ] Xây dựng giao diện phân hệ 4 tab báo cáo chuyên sâu.
  - [ ] Chế độ xem kép Biểu đồ tổng quan và Bảng dữ liệu chi tiết.
- [ ] **Task 10.3.2 — Multi-Filter Engine & Accrual Query**
  - [ ] Xây dựng bộ lọc đa tiêu chí (ngày phát sinh, danh mục, phân xưởng, tùy chọn loại trừ CAPEX).
  - [ ] Xây dựng truy vấn kế toán dồn tích (Accrual query) theo ngày xuất kho và ngày chấm công thực tế.
- [ ] **Task 10.3.3 — Asset Valuation & Capitalization Report**
  - [ ] Xây dựng logic tính khấu hao đường thẳng có chặn sàn giá trị thanh lý ước tính.
  - [ ] Xây dựng thuật toán tính chỉ số RRR loại trừ chi phí CAPEX.
  - [ ] Xây dựng cơ chế vốn hóa chi phí đại tu CAPEX vào nguyên giá và tính lại khấu hao mới.
- [ ] **Task 10.3.4 — Maintenance Performance & Resolution Report**
  - [ ] Xây dựng logic đo lường tỷ lệ hoàn thành đúng hạn và tỷ lệ tuân thủ PM theo quy tắc 10%.
  - [ ] Xử lý trạng thái `SKIPPED_DUE_TO_OVERLAP` loại trừ khỏi mẫu số tính tuân thủ PM.
- [ ] **Task 10.3.5 — Spare Parts Valuation & Variance Engine**
  - [ ] Xây dựng thuật toán định giá xuất kho theo chuẩn bình quân gia quyền di động.
  - [ ] Xử lý tạm tính chi phí khi kho xuất âm và tự động sinh bút toán chênh lệch giá (Price Variance) khi có phiếu Nhập kho.
  - [ ] Xử lý hoàn trừ chi phí khi vật tư xuất dư được nhập lại kho.
- [ ] **Task 10.3.6 — Asynchronous Export Engine with MinIO & Resilience**
  - [ ] Xây dựng model `ExportJob` và cơ chế khống chế tối đa 3 jobs đồng thời cho mỗi Tenant.
  - [ ] Tác vụ Celery xuất Excel/PDF tối ưu bộ nhớ qua chunking và streaming.
  - [ ] Tích hợp hàm khử độc chuỗi chống tiêm mã công thức (Formula Injection).
  - [ ] Tác vụ ngầm dọn dẹp tệp MinIO sau 7 ngày và tự động phục hồi tác vụ ma (Zombie Job).

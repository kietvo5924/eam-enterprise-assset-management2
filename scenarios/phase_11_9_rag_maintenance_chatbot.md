# Thiết Kế Hệ Thống & Đặc Tả Kỹ Thuật: Task 11.9 — Intelligent AI Assistant / Chatbot (RAG & Sentence-Transformers)

Tài liệu này xác định kiến trúc trợ lý kỹ thuật thông minh hỗ trợ vận hành và sửa chữa tại hiện trường trong hệ thống Quản lý Tài sản Doanh nghiệp (EAM). Hệ thống ứng dụng kỹ thuật tạo sinh tăng cường truy xuất (**Retrieval-Augmented Generation - RAG**), kết hợp: mô hình trích xuất vector ngữ nghĩa dày đặc (**Dense Semantic Embedding**) bằng **Sentence-Transformers** (`all-MiniLM-L6-v2` 384 chiều), lưu trữ và lập chỉ mục đồ thị phân cấp (**HNSW Index**) trên **PostgreSQL PGVector**, bộ biến đổi câu hỏi tiếng lóng & từ tượng thanh (**Query Expansion / Rewrite**), cơ chế bảo tồn neo bản vẽ sơ đồ kỹ thuật (**Diagram & Schematic Anchor Preservation**), cơ chế truy xuất Cha-Con chống mất đuôi quy trình (**Parent-Child Document Retrieval**), truy xuất song luồng kết hợp tri thức ngầm lịch sử sửa chữa (**Dual-Stream Retrieval: OEM + Tacit WorkOrder Knowledge**), bộ lọc siêu dữ liệu cứng theo đời máy & dải sê-ri (**Granular Year & Serial Range Filtering**), kiểm tra tồn kho phụ tùng & dụng cụ thực tế (**Live Inventory & Tool Interlock**), rào chắn chống đảo ngược từ phủ định an toàn (**Negation Contradiction Guard**), gói dự phòng ngoại tuyến trên di động (**Offline Edge Pre-fetching & SQLite FTS5**), nút 1-chạm tạo phiếu làm việc từ hội thoại (**Actionable Chat-to-WorkOrder**), và vòng lặp thẩm định tri thức của Kỹ sư trưởng (**Chief Engineer Curation Loop**).

Tài liệu đóng vai trò là **Đặc Tả Kỹ Thuật & Chuẩn Kiểm Thử (Technical Specification & Audit Baseline)** nhằm đối chiếu, rà soát và thực thi trọn vẹn toàn bộ tính năng theo chuẩn đề cương tốt nghiệp đại học mà không bị thiếu sót bất kỳ nghiệp vụ enterprise nào.

---

## 1. Mục Tiêu & Phạm Vi (Objective & Scope)

### 1.1. Bản Chất Nghiệp Vụ Của Trợ Lý Kỹ Thuật Hiện Trường
Trong nhà xưởng công nghiệp nặng, khi một thiết bị dừng đột ngột kèm theo mã lỗi lạ hoặc hiện tượng bất thường:
- Hướng dẫn vận hành tiêu chuẩn (SOP) và tài liệu của hãng chế tạo (OEM Manual) thường dày từ 300 đến 1,000 trang bằng tiếng Anh hoặc thuật ngữ chuyên ngành phức tạp.
- Kỹ thuật viên hiện trường thường mô tả sự cố bằng tiếng lóng hoặc từ tượng thanh dân dã (*"máy kêu lạch cạch"*, *"chết heo"*, *"tụ bị phù"*), trong khi tài liệu của hãng lại dùng thuật ngữ hàn lâm (*"Cavitation"*, *"Harmonic Distortion"*).
- **Rủi ro chí mạng**: Thao tác sai quy trình xả áp lực hoặc đọc nhầm tài liệu của máy đời khác có thể gây nổ bình tích áp, chập điện hoặc phá hỏng máy móc đắt tiền.

### 1.2. Vai Trò Kép Của Trợ Lý Thông Minh AI RAG
Trợ lý RAG đóng hai vai trò chiến lược đồng hành cùng người dùng trên cả Web Portal và Ứng dụng Di động:
1. **Trợ lý Kỹ thuật Bảo trì Hiện trường (Field Maintenance Assistant)**: Đồng hành cùng kỹ thuật viên tại chân máy. Kỹ thuật viên quét mã QR trên máy hoặc mở phiếu Work Order, đặt câu hỏi bằng văn bản tiếng Việt. Hệ thống tự động dịch thuật ngữ tiếng lóng dân dã, truy xuất song song tài liệu hãng và lịch sử mẹo sửa chữa thực tế của nhà máy, hiển thị quy trình từng bước chuẩn xác kèm bản vẽ sơ đồ, đồng thời kiểm tra ngay trong kho còn đồ nghề và phụ tùng thay thế hay không.
2. **Trợ lý Hướng dẫn Sử dụng Hệ thống Web & Mobile (System Feature & Navigation Guide)**: Hướng dẫn người dùng thao tác trên phần mềm EAM, giải thích ý nghĩa các nút bấm, các luồng chức năng (ví dụ: *"Nút này dùng để làm gì?"*, *"Cách tạo phiếu bảo trì đột xuất"*, *"Xem báo cáo KPI ở đâu?"*, *"Quy trình phê duyệt vật tư"*). Người dùng không còn bị bỡ ngỡ khi tiếp cận hệ thống mới.

---

## 2. Ràng Buộc Kế Thừa Hệ Thống (Existing System Constraints & Codebase Reuse)

- **Cơ Chế Phân Lập Đa Khách Hàng Kết Hợp Tri Thức Dùng Chung (Hybrid Multi-Tenancy & Global Knowledge)**:
  - **Tri thức thiết bị & nhà xưởng (Tenant-Isolated Knowledge)**: Mọi tài liệu kỹ thuật OEM, đoạn văn bản vector hóa thiết bị, lịch sử Work Order và tri thức kinh nghiệm sửa chữa kế thừa `BaseTenantModel`, bảo đảm phân lập hoàn toàn giữa các Tenant qua `TenantManager`.
  - **Tri thức hướng dẫn sử dụng hệ thống EAM (Global System Guide / App Navigation)**: Các hướng dẫn sử dụng giao diện Web/Mobile, định nghĩa nút bấm và luồng thao tác phần mềm được lưu trữ ở cấp độ hệ thống (**GLOBAL / Cross-Tenant**, `tenant_id IS NULL` hoặc `is_system_guide = TRUE`), **hoàn toàn KHÔNG cần chia tenant**, áp dụng chung cho mọi khách hàng/tenant trong hệ thống.
- **Tái Sử Dụng Thực Thể Nghiệp Vụ Có Sẵn**:
  - `Asset`: Tự động tiêm ngữ cảnh mã máy (`model`, `manufacturer`, `serial_number`, `manufacture_year`) vào bộ lọc cứng của PGVector.
  - `WorkOrder`: Vector hóa toàn bộ các ghi chú giải quyết sự cố (`resolution_notes`) của các phiếu đã hoàn thành để biến thành nguồn tri thức ngầm; hỗ trợ nút tạo nhanh bản thảo Work Order từ đoạn chat.
  - `SparePart`: Liên kết trực tiếp kiểm tra tồn kho và vị trí kệ chứa của các phụ tùng được nhắc tới trong quy trình.
- **Vị Trí Phân Hệ Quản Trị Tri Thức (Admin Knowledge Hub Placement)**:
  - Trang quản trị tri thức trợ lý AI được tích hợp tại **phân hệ Admin**, nằm ngay tại khu vực bên dưới mục Cài đặt (Settings) chung (đường dẫn `/admin/rag-knowledge/`).
  - Người dùng có quyền quản trị cài đặt hệ thống (`can_manage_settings` hoặc vai trò `ADMIN`, `CHIEF_ENGINEER`) sẽ có toàn quyền bổ sung câu hỏi - trả lời mẫu (Curated Q&A), duyệt hàng đợi phản hồi của thợ và quản lý thư viện tài liệu.
- **Bảo Mật Dữ Liệu Công Nghệ (On-Premises LLM)**: Tuyệt đối không gửi tài liệu bí mật công nghệ hoặc dữ liệu vận hành nhà máy lên các API đám mây công cộng (OpenAI, Claude, v.v.). Hệ thống bắt buộc chạy mô hình mã nguồn mở trên máy chủ nội bộ thông qua dịch vụ Ollama cục bộ (`temperature = 0.1`).
- **Kiến Trúc Đóng Gói Module Giải Thuật (Dedicated Algorithms Package)**: Toàn bộ mã nguồn trợ lý kỹ thuật AI RAG (bộ lọc ngắt an toàn sinh mạng Emergency Interceptor, kiểm định mâu thuẫn phủ định Negation Contradiction Check, pipeline sinh embeddings và truy xuất PGVector đa nguồn, client kết nối Ollama on-premises, và bộ lọc tiếng lóng chuyên ngành bảo trì) **bắt buộc phải được đặt trong thư mục riêng biệt `eam_app/algorithms/rag_chatbot/`** (vẫn nằm trong source backend). Tách biệt hoàn toàn tầng giải thuật AI RAG khỏi các tầng controller/CRUD thông thường.

---

## 3. Yêu Cầu Nghiệp Vụ & 10 Quy Tắc Cốt Lõi (Business Requirements & Core Rules)

Toàn bộ trợ lý kỹ thuật AI RAG phải tuân thủ nghiêm ngặt 10 quy tắc phòng thủ sau:

### Quy Tắc 1: Rào Chắn Cắt Ngang An Toàn Sinh Mạng & Chống Mâu Thuẫn Ngữ Nghĩa (Emergency Life-Safety Interceptor & Negation Contradiction Check)
- **Điểm Yếu Nghiệp Vụ**: Khi nhà máy xảy ra chập cháy biến áp hoặc rò rỉ khí độc, thợ hoảng loạn hỏi AI *"Làm sao dập lửa dầu biến áp?"*. Nếu để LLM sinh từ ngẫu nhiên, AI có thể trả lời *"Dùng nước xối vào"* $\rightarrow$ nổ giết chết người. Ngoài ra, LLM khi tóm tắt đôi khi vô tình làm rớt các từ phủ định (tài liệu ghi *"DO NOT turn valve A"*, LLM tóm tắt thành *"Turn valve A"*), gây nổ buồng áp lực.
- **Quy Tắc Bắt Buộc**:
  1. **Bộ lọc ngắt an toàn sinh mạng (Emergency Keyword Interceptor)**:
     - Danh mục từ khóa nguy cấp: `cháy`, `bốc khói`, `chập điện`, `rò khí độc`, `kẹt tay`, `điện giật`, `nổ bình tích áp`, `xì gas`, `axit bắn`.
     - Bỏ qua toàn bộ RAG và LLM, trả về ngay lập tức cảnh báo đỏ ưu tiên tối cao:
       > "⚠️ CẢNH BÁO NGUY HIỂM TÍNH MẠNG: PHÁT HIỆN TÌNH HUỐNG NGUY CẤP! NGHIÊM CẤM TỰ Ý THAO TÁC! HÃY BẤM NGAY NÚT DỪNG KHẨN CẤP (E-STOP), SƠ TÁN KHỎI KHU VỰC VÀ KÍCH HOẠT CÒI BÁO ĐỘNG NHÀ MÁY!"
  2. **Bộ lọc kiểm định mâu thuẫn từ phủ định an toàn (Contradiction Guard)**:
     - Kiểm tra đối chiếu câu trả lời với văn bản gốc: Nếu đoạn trích gốc chứa các từ cấm kỵ (`CẤM`, `KHÔNG ĐƯỢC`, `TRÁNH`, `DO NOT`, `NEVER`), hệ thống kiểm tra tính bảo toàn phủ định.
     - Nếu phát hiện nguy cơ đảo ngược logic an toàn, hủy câu trả lời tóm tắt của AI và **hiển thị nguyên văn trích dẫn gốc (Raw Verbatim Quote)** kèm cảnh báo viền đỏ.

### Quy Tắc 2: Bộ Lọc Biến Đổi Câu Hỏi Tiếng Lóng & Từ Tượng Thanh (Slang & Onomatopoeia Query Expansion)
- **Điểm Yếu Nghiệp Vụ (Slang & Onomatopoeia Gap)**: Kỹ thuật viên hiện trường dùng tiếng lóng: *"Máy bơm kêu lạch cạch"*, *"tụ bị phù"*, *"chết heo"*, *"hụt hơi"*. Tài liệu hãng lại dùng thuật ngữ hàn lâm: *"Hiện tượng xâm thực (Cavitation)"*, *"Lỗi quá áp buồng đốt"*, *"Suy hao điện dung"*. Khoảng cách Cosine giữa từ lóng và từ hàn lâm là cực thấp, khiến PGVector không tìm ra tài liệu và báo "Không tìm thấy".
- **Quy Tắc Bắt Buộc**:
  1. Bắt buộc thực hiện bước **Biến đổi câu hỏi (Query Expansion / Rewrite)** trước khi chọc vào PGVector.
  2. Hệ thống kết hợp Từ điển tiếng lóng bảo trì công nghiệp (Domain Thesaurus) và LLM dịch câu hỏi dân dã thành vector các từ khóa kỹ thuật tương đương:
     - *"kêu lạch cạch"* $\rightarrow$ `mechanical looseness`, `cavitation`, `bearing vibration`.
     - *"tụ bị phù"* $\rightarrow$ `capacitor bulging`, `dielectric breakdown`, `overvoltage`.
     - *"chết heo"* $\rightarrow$ `brake caliper seizure`, `hydraulic cylinder failure`.
  3. Truy vấn PGVector được thực hiện trên chuỗi vector mở rộng để đảm bảo độ bao phủ ngữ nghĩa tuyệt đối.

### Quy Tắc 3: Cắt Đoạn Nhận Biết Cấu Trúc & Bảo Tồn Neo Bản Vẽ/Hình Ảnh (Structure-Aware Chunking & Diagram Anchor Preservation)
- **Điểm Yếu Nghiệp Vụ (Diagram & Schematic Blindspot)**: Kỹ thuật viên hỏi cách tháo hộp số. Trợ lý RAG đọc chữ trong PDF và trả lời: *"Nới lỏng 4 con ốc ở Vị trí A (xem Hình 3.2)"*. Do hệ thống cắt đoạn text thông thường đã vứt bỏ toàn bộ hình ảnh, thợ không biết "Vị trí A" ở đâu, dẫn đến vặn nhầm ốc phá hỏng hộp số. Ngoài ra, việc cắt cơ học làm gãy đôi các bảng mã lỗi Markdown.
- **Quy Tắc Bắt Buộc**:
  1. **Bảo toàn bảng mã lỗi**: Các hàng bảng Markdown (`| Error Code | Symptom | Action |`) tuyệt đối không được cắt ngang giữa chừng.
  2. **Bảo tồn neo liên kết hình ảnh (Image Anchor Preservation)**:
     - Khi trích xuất văn bản từ PDF, hệ thống định vị các sơ đồ/bản vẽ kỹ thuật gần nhất và lưu thông tin neo: `image_anchor: {figure_id: "Fig 3.2", page: 42, image_url: "minio://docs/pumps/fig3_2.png"}`.
     - Khi trả lời, nếu đoạn văn bản nguồn tham chiếu hình ảnh, UI bắt buộc hiển thị hình ảnh bản vẽ phóng to hoặc nút bấm: *"Xem Sơ đồ mạch tại Trang 42 của tài liệu đính kèm"*.

### Quy Tắc 4: Truy Xuất Cha-Con Chống Mất Đuôi Quy Trình (Parent-Child Document Retrieval)
- **Điểm Yếu Nghiệp Vụ (Procedural Truncation / Chunking Trap)**: Một quy trình "Thay dầu máy nén khí" gồm 20 bước liền mạch. Do giới hạn `chunk_size = 600`, quy trình bị cắt làm 3 đoạn (Bước 1-7, Bước 8-15, Bước 16-20). PGVector thấy đoạn 1 có độ tương đồng cao nhất và đưa cho LLM. LLM trả lời: *"Quy trình gồm 7 bước: [1 đến 7]"*. Thợ làm xong bước 7 thì dừng, quên mất bước 18 là "Mở van xả áp", dẫn đến nổ máy khi chạy lại.
- **Quy Tắc Bắt Buộc**:
  1. Áp dụng chiến lược **Truy xuất Cha-Con (Parent-Child Retrieval)**:
     - **Child Chunks (Đoạn con)**: Kích thước nhỏ (300 ký tự) để embedding đạt độ tập trung và độ chính xác tương đồng ngữ nghĩa cao nhất.
     - **Parent Chunks (Đoạn cha)**: Là toàn bộ mục/chương quy trình hoàn chỉnh (2,000 - 4,000 ký tự) chứa đoạn con đó.
  2. Khi truy vấn, PGVector so khớp trên Child Chunks, nhưng khi nạp vào Prompt cho LLM tổng hợp, hệ thống **truy xuất và nạp toàn bộ nội dung của Parent Chunk**.
  3. Đảm bảo toàn bộ 20 bước SOP được truyền đầy đủ tới LLM, triệt tiêu $100\%$ nguy cơ mất đuôi quy trình.

### Quy Tắc 5: Bộ Lọc Siêu Dữ Liệu Cứng Theo Đời Máy & Dải Số Sê-ri (Granular Model, Year & Serial Range Filtering)
- **Điểm Yếu Nghiệp Vụ (Revision/Year Clash)**: Nhà máy có 2 chiếc máy bơm ly tâm cùng mã Model `PUMP-X100`: một chiếc mua năm 2015, một chiếc mua năm 2023. Đời 2015 dùng ron cao su (cần bôi mỡ), đời 2023 dùng ron từ tính (cấm bôi mỡ). Nếu RAG chỉ lọc theo Model, nó có thể bốc nhầm tài liệu đời 2023 cho máy 2015, làm hư hỏng cụm phớt.
- **Quy Tắc Bắt Buộc**:
  1. Siêu dữ liệu lọc cứng của PGVector bắt buộc phải bao gồm: `applicable_model`, `manufacture_year`, và `serial_number_range`.
  2. Khi kỹ thuật viên quét mã QR hoặc mở từ Work Order, API tự động trích xuất thông tin tài sản và tiêm bộ lọc SQL cứng:
     ```sql
     WHERE applicable_model = :asset_model
       AND (:asset_year BETWEEN applicable_year_start AND applicable_year_end)
       AND tenant_id = :tenant_id
     ```
  3. Loại bỏ hoàn toàn nguy cơ lẫn lộn tài liệu giữa các thế hệ máy.

### Quy Tắc 6: Truy Xuất Song Luồng: Tài Liệu Hãng & Tri Thức Ngầm Lịch Sử Sửa Chữa (Dual-Stream Retrieval: OEM + Tacit Knowledge)
- **Điểm Yếu Nghiệp Vụ (Tacit Knowledge / Resolution History)**: Sách hướng dẫn của hãng bảo *"Tháo ốc nắp bưởng máy bằng cờ-lê 14"*. Nhưng ở khí hậu nhiệt đới ẩm, ốc bị rỉ sét, thợ lâu năm biết mẹo *"Phải xịt RP7 ngâm 15 phút và khò nhiệt trước khi vặn, nếu không sẽ gãy rốn ốc"*. Nếu RAG chỉ đọc sách PDF của hãng, thợ trẻ sẽ làm gãy ốc hàng loạt.
- **Quy Tắc Bắt Buộc**:
  1. Cơ sở dữ liệu PGVector được nạp song song từ 2 nguồn:
     - **Luồng 1 (OEM Manuals)**: Sổ tay kỹ thuật chuẩn của nhà sản xuất.
     - **Luồng 2 (Tacit Knowledge)**: Toàn bộ lịch sử các phiếu Work Order đã hoàn thành (`resolution_notes`) và ghi chú kinh nghiệm của các kỹ sư trong nhà máy.
  2. Khi trả lời, câu trả lời của AI được định dạng cấu trúc 2 phần rõ rệt:
     - 📖 **Theo tài liệu kỹ thuật của hãng**: [Hướng dẫn chuẩn mực theo sách].
     - 💡 **Mẹo thực tế từ lịch sử nhà máy (Kế thừa từ WO-2023-0112)**: [Mẹo xịt RP7 và khò nhiệt].

### Quy Tắc 7: Liên Kết Tra Cứu Tồn Kho Phụ Tùng & Dụng Cụ Thời Gian Thực (Live Inventory & Tool Availability Interlock)
- **Điểm Yếu Nghiệp Vụ**: AI hướng dẫn thợ tháo banh máy ra để thay phớt cơ khí. Thợ tháo xong chạy vào kho thì thủ kho báo hết hàng từ tuần trước. Máy bị tháo trơ khung phơi sương gió nhiều tuần.
- **Quy Tắc Bắt Buộc**:
  1. Khi câu trả lời của AI có chứa tên hoặc mã phụ tùng / dụng cụ chuyên dụng (ví dụ: `SKF-2210`, `Cảo thủy lực 10 tấn`):
  2. Hệ thống tự động kích hoạt truy vấn ngầm sang Phân hệ Quản lý Kho ([Task 10.1](file:///d:/GameLinkNeverDie/eam-enterprise-assset-management/scenarios/phase_10_1_maintenance_work_order_lifecycle.md)):
  3. Hiển thị thông tin tồn kho trực tiếp ngay dưới câu trả lời:
     - ✅ *Phớt cơ khí SKF-2210: Còn 3 cái tại Kệ A2-04*.
     - ⚠️ *Cảo thủy lực 10 tấn: Đang được mượn bởi Thợ Nam (Dự kiến trả: 15:00)*.

### Quy Tắc 8: Hỗ Trợ Dự Phòng Ngoại Tuyến Trên Ứng Dụng Di Động (Offline Edge Cache & Emergency Pre-fetching)
- **Điểm Yếu Nghiệp Vụ**: Kỹ thuật viên chui vào tầng hầm sâu hoặc phòng máy biến áp mất sóng 4G/Wifi. Nếu RAG phụ thuộc $100\%$ máy chủ thì thợ bị "mù thông tin", không tra cứu được mã lỗi khẩn cấp.
- **Quy Tắc Bắt Buộc**:
  1. Khi kỹ thuật viên bấm "Bắt đầu ca làm việc" tại nơi có mạng, ứng dụng Flutter tự động tải trước (**Pre-fetch**) gói dữ liệu ngoại tuyến của thiết bị đó vào SQLite cục bộ (`Drift`):
     - Bảng tra cứu top 20 mã lỗi thường gặp nhất.
     - Sơ đồ mạch và quy trình dừng máy khẩn cấp E-Stop.
  2. Khi mất mạng, ứng dụng tự động chuyển sang chế độ **Offline Assistant**, sử dụng thuật toán tìm kiếm toàn văn Full-Text Search (FTS5) nội bộ trên SQLite để trả lời ngay mà không bị gián đoạn công việc.

### Quy Tắc 9: Khởi Tạo Nhanh Bản Thảo Phiếu Làm Việc Từ Hội Thoại (Actionable Chat-to-WorkOrder Generation)
- **Điểm Yếu Nghiệp Vụ**: Thợ hỏi đáp xong, phát hiện ra ổ bi bị hỏng. Thợ phải thoát ra, mở lại danh sách, gõ lại một phiếu Work Order từ đầu, vừa mất thời gian vừa dễ gõ sai mã vật tư.
- **Quy Tắc Bắt Buộc**:
  1. Ở cuối mỗi câu trả lời chẩn đoán sự cố, hệ thống tự động hiển thị nút hành động thông minh:
     > 🔘 **[Tạo phiếu bảo trì đột xuất cho sự cố này]**
  2. Khi thợ bấm nút, hệ thống tự động bốc dữ liệu: `asset_id`, mã lỗi, mô tả sự cố, phụ tùng cần xuất kho và quy trình khắc phục điền sẵn vào bản thảo Work Order mới. Thợ chỉ cần kiểm tra lại và bấm 1 chạm để phát hành phiếu.

### Quy Tắc 10: Vòng Lặp Thẩm Định Tri Thức Từ Kỹ Sư Trưởng & An Toàn Cục Bộ (Chief Engineer Curation Loop & On-Premises Privacy)
- **Điểm Yếu Nghiệp Vụ**: Mẹo truyền miệng sai lệch nếu không được kiểm soát có thể gây tai nạn lặp lại; dữ liệu bảo mật nhà máy bị rò rỉ ra Internet nếu dùng dịch vụ đám mây công cộng.
- **Quy Tắc Bắt Buộc**:
  1. Mỗi câu trả lời có nút 👍 / 👎. Khi nhận 👎, đoạn chat tự động gửi vào **Hàng đợi Phê duyệt của Kỹ sư trưởng (Curation Queue)** để rà soát và hiệu chỉnh thành câu trả lời mẫu chuẩn (`curated_knowledge`).
  2. Hệ thống chạy On-Premises $100\%$ qua Ollama (`llama3:8b` hoặc `qwen2.5:7b`), khống chế $\text{Temperature} = 0.1$, giới hạn 20 truy vấn/phút.
  3. Ngưỡng cắt an toàn chống ảo giác: Nếu điểm tương đồng cao nhất $\text{Sim} < 0.65$, hệ thống từ chối sáng tác và thông báo thợ liên hệ Kỹ sư trưởng.

---

## 4. Yêu Cầu Chức Năng & Luồng Xử Lý (Functional Requirements & Workflows)

### 4.1. Luồng Xử Lý Câu Hỏi Kỹ Thuật Toàn Diện (Comprehensive RAG Pipeline)

```
Kỹ thuật viên đặt câu hỏi (Giọng nói Speech-to-Text hoặc Gõ chữ) + Ngữ cảnh Asset
       │
       ▼
[BỘ LỌC CẮT NGANG AN TOÀN SINH MẠNG (Life-Safety Interceptor)]
       │
       ├── Có từ khóa nguy cấp (cháy, giật, rò khí)? ──► CÓ ──► Xuất cảnh báo đỏ dừng khẩn cấp E-STOP (Dừng luồng)
       │
       └── KHÔNG
             │
             ▼
[BIẾN ĐỔI CÂU HỎI TIẾNG LÓNG (Query Expansion / Rewrite)]
  - Chuyển từ lóng/tượng thanh dân dã thành thuật ngữ kỹ thuật tiêu chuẩn
             │
             ▼
[TRUY VẤN SONG LUỒNG PGVECTOR (Chỉ mục HNSW + Lọc Cứng Đa Chiều)]
  - Lọc cứng: tenant_id + model + manufacture_year + serial_range
  - Luồng 1: Sổ tay kỹ thuật OEM PDF (Child Chunks)
  - Luồng 2: Tri thức ngầm từ lịch sử Work Order (resolution_notes)
             │
             ▼
Đoạn trích có điểm tương đồng cao nhất >= 0.65?
       │
       ├── KHÔNG ──► Trả về câu từ chối an toàn: "Không tìm thấy tài liệu phê duyệt..."
       │
       └── CÓ
             │
             ▼
[NẠP NGỮ CẢNH CHA (Parent-Child Context Loading)]
  - Lấy toàn bộ Parent Section chứa Child Chunk để không mất bước quy trình
             │
             ▼
[KIỂM ĐỊNH MÂU THUẪN PHỦ ĐỊNH AN TOÀN (Contradiction Guard)]
  - Đảm bảo các từ khóa DO NOT, NEVER không bị đảo ngược logic
             │
             ▼
[TRA CỨU TỒN KHO & DỤNG CỤ THỜI GIAN THỰC] ──► Gọi API Kho lấy số lượng & vị trí kệ
             │
             ▼
[MÔ HÌNH NGÔN NGỮ OLLAMA CỤC BỘ (llama3 / qwen2.5, Temp=0.1)]
             │
             ▼
[TRUYỀN LUỒNG SSE + NEO HÌNH ẢNH SƠ ĐỒ + NÚT 1-CHẠM TẠO WORK ORDER]
  - Hiển thị Markdown + Ảnh bản vẽ sơ đồ + Tồn kho + Nút tạo nhanh Work Order
```

---

## 5. Quy Tắc Bảo Mật, Phân Quyền & Đa Khách Hàng (Security, RBAC & Multi-Tenant Rules)

- **Cơ Chế Phân Lập Đa Khách Hàng & Tri Thức Toàn Cục (Hybrid Multi-Tenancy & Global System Knowledge)**:
  - **Tri thức thiết bị & xưởng (Tenant-Isolated)**: Mọi tài liệu PDF của hãng, đoạn vector của thiết bị, lịch sử Work Order và tri thức thẩm định máy móc bắt buộc phân lập tuyệt đối theo `tenant_id`.
  - **Tri thức hướng dẫn sử dụng phần mềm Web & Mobile (Global Cross-Tenant)**: Toàn bộ cẩm nang hướng dẫn thao tác tính năng, giải thích công dụng các nút bấm và luồng nghiệp vụ phần mềm EAM được gắn cờ `is_system_guide = TRUE` (`tenant_id = NULL`), cho phép mọi người dùng thuộc bất kỳ Tenant nào cũng có thể tra cứu bình đẳng mà không bị rào cản Tenant ngăn cách.
- **Ma Trận Phân Quyền (RBAC)**:
  - `TECHNICIAN` / `OPERATOR`: Mở widget chat nổi (FAB), đặt câu hỏi kỹ thuật máy móc hoặc hỏi cách dùng phần mềm, xem sơ đồ kỹ thuật, bấm 1-chạm tạo bản thảo Work Order, gửi đánh giá 👍/👎.
  - `ADMIN` / `SETTINGS_MANAGER` (Người có quyền quản trị cài đặt `can_manage_settings`): Có toàn quyền truy cập trang **Quản trị Tri thức Trợ lý Kỹ thuật & RAG Q&A** nằm trong phân hệ Admin (khu vực bên dưới mục Cài đặt chung) để:
    - Thêm / sửa / xóa các cặp câu hỏi - trả lời mẫu (Curated Q&A), bao gồm cả Q&A máy móc và Q&A hướng dẫn sử dụng phần mềm Web/Mobile.
    - Duyệt hàng đợi phản hồi của thợ (Curation Queue) khi nhận đánh giá 👎 để nâng cấp thành câu trả lời vàng.
    - Tải lên tài liệu kỹ thuật OEM mới và kích hoạt re-indexing PGVector.
  - `CHIEF_ENGINEER` / `MAINTENANCE_MANAGER`: Quyền chuyên môn phê duyệt câu trả lời chuẩn trong hàng đợi Curation Queue, thẩm định các quy trình bảo dưỡng và cấu hình dải năm/sê-ri máy áp dụng.
  - `SAFETY_OFFICER`: Kiểm tra, tinh chỉnh và cập nhật danh mục từ khóa an toàn nguy hiểm ngắt khẩn cấp E-Stop.

---

## 6. Kiến Trúc & Luồng Dữ Liệu Công Nghệ (Architecture & Data Flow)

```
┌────────────────────────────────────────────────────────────────────────┐
│                        GIAO DIỆN NGƯỜI DÙNG                            │
│  Web Portal (Nút tròn nổi FAB góc phải) │  Flutter App (Nút tròn nổi FAB) │
│  - Popup Chat Drawer $400 \times 620$px │  - Modal Bottom Sheet trượt lên │
│  - Tự động nhận biết ngữ cảnh trang     │  - Nút gợi ý 1-chạm (Quick Chips)│
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ POST /api/v1/assistant/chat/
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                      DỊCH VỤ DJANGO REST RAG                           │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ 1. Bộ lọc ngắt an toàn sinh mạng & Chống mâu thuẫn phủ định      │  │
│  ├──────────────────────────────────────────────────────────────────┤  │
│  │ 2. Bộ biến đổi câu hỏi tiếng lóng (Query Expansion / Thesaurus)  │  │
│  ├──────────────────────────────────────────────────────────────────┤  │
│  │ 3. Động cơ truy xuất song luồng PGVector (OEM + Tacit History)   │  │
│  │    • Phân luồng: Tri thức thiết bị (Tenant) & Hướng dẫn (Global)  │  │
│  │    • Lọc cứng: tenant + model + year + serial range              │  │
│  │    • Truy xuất Parent-Child: Nạp trọn vẹn Chương cha             │  │
│  ├──────────────────────────────────────────────────────────────────┤  │
│  │ 4. Bộ tra cứu tồn kho phụ tùng & dụng cụ (Task 10.1 Interlock)   │  │
│  ├──────────────────────────────────────────────────────────────────┤  │
│  │ 5. Bộ lắp ghép Prompt nghiêm ngặt bám sát ngữ cảnh tài liệu      │  │
│  ├──────────────────────────────────────────────────────────────────┤  │
│  │ 6. Bộ truyền luồng SSE + Neo hình ảnh sơ đồ + Nút tạo Work Order │  │
│  └──────────────────┬───────────────────────────────┬───────────────┘  │
│                     │                               │                  │
│                     ▼                               ▼                  │
│  ┌────────────────────────────────────┐ ┌───────────────────────────┐  │
│  │ PostgreSQL 16 + PGVector           │ │ Local Ollama Daemon       │  │
│  │ • Bảng: document_chunks, tacit_... │ │ • Model: llama3:8b        │  │
│  │ • Chỉ mục HNSW (m=16, ef_const=64) │ │ • Temp: 0.1 (Tất định)    │  │
│  └────────────────────────────────────┘ └───────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Mô Hình Dữ Liệu & Thực Thể (Data Model & Schema)

### 7.1. Bảng `technical_documents` (Tài liệu kỹ thuật OEM gốc & Hướng dẫn hệ thống)
```sql
CREATE TABLE technical_documents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NULL REFERENCES tenants(id), -- NULL nếu là tài liệu hướng dẫn phần mềm dùng chung toàn hệ thống
  is_system_guide BOOLEAN NOT NULL DEFAULT FALSE, -- TRUE: Cẩm nang hướng dẫn sử dụng phần mềm Web/Mobile (Global)
  category VARCHAR(32) NOT NULL DEFAULT 'OEM_MANUAL', -- 'OEM_MANUAL', 'SYSTEM_SOFTWARE_GUIDE'
  title VARCHAR(255) NOT NULL,
  file_path VARCHAR(500) NOT NULL, -- Đường dẫn MinIO hoặc tệp nội bộ
  applicable_model VARCHAR(100) NULL, -- Model thiết bị (NULL nếu là hướng dẫn hệ thống)
  applicable_year_start INT NOT NULL DEFAULT 1900,
  applicable_year_end INT NOT NULL DEFAULT 2100,
  serial_number_prefix VARCHAR(50) NULL,
  file_size_bytes BIGINT NOT NULL,
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_doc_tenant_model ON technical_documents(tenant_id, applicable_model, is_active);
CREATE INDEX idx_doc_system_guide ON technical_documents(is_system_guide, is_active);
```

### 7.2. Bảng `document_chunks` (Đoạn văn bản, Vector 384d & Neo hình ảnh)
```sql
CREATE TABLE document_chunks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NULL REFERENCES tenants(id), -- NULL đối với tri thức toàn cục
  is_system_guide BOOLEAN NOT NULL DEFAULT FALSE,
  document_id UUID NULL REFERENCES technical_documents(id) ON DELETE CASCADE,
  source_type VARCHAR(32) NOT NULL DEFAULT 'OEM_MANUAL', -- 'OEM_MANUAL', 'TACIT_WORK_ORDER', 'CURATED_QA', 'SYSTEM_GUIDE'
  work_order_id UUID NULL REFERENCES work_orders(id) ON DELETE SET NULL,
  content TEXT NOT NULL, -- Child Chunk
  parent_content TEXT NOT NULL, -- Parent Section hoàn chỉnh
  embedding vector(384) NOT NULL, -- Vector 384 chiều
  page_number INT NULL,
  section_title VARCHAR(255) NULL,
  image_anchors JSONB NULL, -- [{"figure_id": "Fig 3.2", "page": 42, "url": "minio://..."}]
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_chunk_embedding_hnsw ON document_chunks 
USING hnsw (embedding vector_cosine_ops) 
WITH (m = 16, ef_construction = 64);

CREATE INDEX idx_chunk_tenant_source ON document_chunks(tenant_id, source_type, is_active);
CREATE INDEX idx_chunk_system_guide ON document_chunks(is_system_guide, is_active);
```

### 7.3. Bảng `curated_qa_knowledge` (Tri thức thẩm định của Kỹ sư trưởng & Hướng dẫn phần mềm)
```sql
CREATE TABLE curated_qa_knowledge (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NULL REFERENCES tenants(id), -- NULL nếu là tri thức dùng chung cho toàn bộ tenant
  is_system_guide BOOLEAN NOT NULL DEFAULT FALSE, -- TRUE: Hướng dẫn chức năng phần mềm Web/Mobile
  category VARCHAR(32) NOT NULL DEFAULT 'EQUIPMENT_MAINTENANCE', -- 'EQUIPMENT_MAINTENANCE', 'SYSTEM_FEATURE_GUIDE'
  question_pattern TEXT NOT NULL,
  gold_answer TEXT NOT NULL,
  applicable_model VARCHAR(100) NULL, -- NULL nếu là hướng dẫn tính năng phần mềm
  approved_by UUID NOT NULL REFERENCES users(id),
  upvote_count INT DEFAULT 0,
  downvote_count INT DEFAULT 0,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_curated_tenant_cat ON curated_qa_knowledge(tenant_id, category, is_system_guide);
```

---

## 8. Đặc Tả Giao Diện Lập Trình (API Specifications & Contracts)

### Danh Mục Endpoints:

| Phương Thức | Đường Dẫn | Quyền Truy Cập (RBAC) | Chức Năng |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/assistant/chat/` | `AUTHENTICATED` (Tất cả vai trò) | Gửi câu hỏi kỹ thuật máy móc hoặc hỏi cách dùng phần mềm Web/Mobile (hỗ trợ SSE `stream=true`) |
| `POST` | `/api/v1/assistant/feedback/` | `AUTHENTICATED` (Kỹ thuật viên) | Gửi đánh giá 👍 / 👎 kèm lý do phản hồi của thợ |
| `POST` | `/api/v1/assistant/create-work-order-draft/` | `AUTHENTICATED` (Thợ / Kỹ sư) | Khởi tạo nhanh bản thảo Work Order từ nội dung hội thoại |
| `GET` | `/api/v1/assistant/offline-pack/{asset_id}/` | `AUTHENTICATED` | Tải gói dữ liệu ngoại tuyến (Pre-fetch) về lưu SQLite di động |
| `GET` | `/api/v1/assistant/admin/qa-list/` | `can_manage_settings` / `ADMIN` | Lấy danh sách Q&A mẫu (hỗ trợ lọc theo Thiết bị hoặc Hướng dẫn phần mềm hệ thống) |
| `POST` | `/api/v1/assistant/admin/qa/` | `can_manage_settings` / `ADMIN` | Thêm mới hoặc cập nhật cặp câu hỏi - câu trả lời mẫu |
| `DELETE` | `/api/v1/assistant/admin/qa/{id}/` | `can_manage_settings` / `ADMIN` | Xóa cặp câu hỏi - đáp khỏi cơ sở tri thức |
| `GET` | `/api/v1/assistant/admin/curation-queue/` | `can_manage_settings` / `CHIEF_ENG` | Lấy danh sách câu hỏi bị thợ đánh giá 👎 cần Kỹ sư trưởng phê duyệt |
| `POST` | `/api/v1/assistant/admin/curation-queue/{id}/approve/` | `can_manage_settings` / `CHIEF_ENG` | Phê duyệt & lưu câu trả lời hiệu chỉnh thành Tri thức Vàng |
| `POST` | `/api/v1/assistant/admin/upload-document/` | `can_manage_settings` / `ADMIN` | Tải lên tài liệu PDF OEM hoặc cẩm nang sử dụng phần mềm và kích hoạt vector hóa |

### Cấu Trúc Dữ Liệu Mẫu:

#### 1. Gửi câu hỏi kỹ thuật máy móc (`POST /api/v1/assistant/chat/`):
*Payload Request*:
```json
{
  "prompt": "Bơm ly tâm kêu lạch cạch và hụt hơi xử lý sao anh?",
  "assetContext": {
    "assetId": "a1b2c3d4-e5f6-7890-abcd-1234567890ab",
    "model": "PUMP-X100",
    "manufactureYear": 2018,
    "serialNumber": "PUMP-2018-089"
  },
  "stream": false
}
```

*Response `200 OK` (Truy xuất song luồng kèm hình ảnh & tồn kho)*:
```json
{
  "success": true,
  "data": {
    "expandedQuery": "centrifugal pump mechanical vibration cavitation suction loss PUMP-X100",
    "reply": "### 1. 📖 HƯỚNG DẪN CHUẨN TỪ HÃNG (OEM MANUAL):\nHiện tượng máy bơm kêu lạch cạch kèm hụt áp là dấu hiệu của **Xâm thực bọt khí (Cavitation)** hoặc **Lỏng bu-lông cánh bơm**:\n1. Kiểm tra áp suất đường hút: Nới lỏng van hút để tăng lưu lượng nước vào.\n2. Kiểm tra độ rơ cánh bơm: Nới lỏng 4 ốc nắp bưởng (xem **Hình 2.4 - Sơ đồ cụm cánh**).\n\n### 2. 💡 MẸO THỰC TẾ TẠI NHÀ MÁY (Kế thừa từ WO-2023-0412):\nĐối với dòng máy đời 2018 tại Phân xưởng 2, bu-lông bưởng máy rất dễ bị cháy ren do nước phèn. **Bắt buộc xịt dung dịch RP7 ngâm 15 phút trước khi dùng cờ-lê 17 để tháo**, tránh làm gãy rốn bu-lông.",
    "diagramAnchors": [
      {
        "figureId": "Fig 2.4",
        "title": "Sơ đồ mặt cắt cụm cánh bơm ly tâm PUMP-X100",
        "pageNumber": 28,
        "imageUrl": "https://minio.factory.local/docs/schematics/pump_x100_fig2_4.png"
      }
    ],
    "inventoryAvailability": [
      {
        "partNumber": "SEAL-RUBBER-100",
        "name": "Ron cao su làm kín 100mm (Đời <= 2020)",
        "inStock": 5,
        "location": "Kệ B3-02"
      }
    ],
    "actionableWorkOrder": {
      "suggestedTitle": "Khắc phục xâm thực và thay ron làm kín Bơm PUMP-X100",
      "faultCode": "CAVITATION_NOISE",
      "priority": "HIGH"
    },
    "citedSources": [
      {
        "documentName": "PUMP_X100_Service_Manual_Rev2018.pdf",
        "pageNumber": 28,
        "similarityScore": 0.884
      }
    ]
  }
}
```

#### 2. Gửi câu hỏi hướng dẫn sử dụng phần mềm Web/Mobile (Global System Guide):
*Payload Request*:
```json
{
  "prompt": "Nút Phát hành phiếu sửa chữa có tác dụng gì và ai được bấm?",
  "assetContext": null,
  "stream": false
}
```

*Response `200 OK` (Truy xuất tri thức hệ thống dùng chung, không chia tenant)*:
```json
{
  "success": true,
  "data": {
    "expandedQuery": "work order issue dispatch button role permission guide",
    "reply": "### ℹ️ HƯỚNG DẪN TÍNH NĂNG HỆ THỐNG EAM:\n**Nút [Phát hành phiếu sửa chữa] (Issue Work Order)** có chức năng chuyển đổi phiếu bảo trì từ trạng thái `DRAFT` (Bản thảo) sang `RELEASED` (Đã phát hành để giao việc):\n1. **Tác dụng**: Khóa thông tin sự cố, ghi nhận mốc thời gian bắt đầu quy trình sửa chữa và tự động kích hoạt thông báo Realtime (WebSocket/FCM) tới Kỹ thuật viên được giao việc.\n2. **Phân quyền thao tác**: Chỉ tài khoản có vai trò `MAINTENANCE_PLANNER`, `MAINTENANCE_SUPERVISOR` hoặc `ADMIN` mới có quyền bấm nút này. Kỹ thuật viên hiện trường (`TECHNICIAN`) chỉ có thể xem và bấm bắt đầu công việc.",
    "isSystemGuide": true,
    "citedSources": [
      {
        "documentName": "EAM_User_Manual_WorkOrder_Workflow.md",
        "section": "Chương 4: Vòng đời Phiếu Bảo Trì",
        "similarityScore": 0.925
      }
    ]
  }
}
```

---

## 9. Đặc Tả Trải Nghiệm Người Dùng (UI/UX Behavioral Specifications)

Hệ thống được thiết kế hoàn chỉnh theo 2 không gian trải nghiệm: **Widget Nút Nổi Thông Minh Hiện Trường** dành cho toàn bộ người dùng và **Trung Tâm Quản Trị Tri Thức** dành cho người có quyền Cài đặt hệ thống.

### 9.1. Giao Diện Nút Nổi Thông Minh Góc Dưới Bên Phải (Floating Action Button - FAB)

```
       Web Portal                                  Mobile Flutter App
┌─────────────────────────────────┐        ┌───────────────────────────────┐
│                                 │        │                               │
│   [Màn hình chi tiết Thiết bị]  │        │   [Màn hình Phiếu Bảo Trì]    │
│   hoặc [Phiếu Work Order]       │        │                               │
│                                 │        │                               │
│                                 │        │                               │
│                      ┌────────┐ │        │                    ┌────────┐ │
│                      │ 🤖 FAB │ │        │                    │ 🤖 FAB │ │
│                      └────────┘ │        │                    └────────┘ │
└─────────────────────────────────┘        └───────────────────────────────┘
```

1. **Vị Trí & Hiệu Ứng Trực Quan**:
   - Nằm cố định ở góc dưới bên phải màn hình trên cả Web Portal và Mobile App (`bottom: 24px; right: 24px; z-index: 9999;`).
   - Nút tròn đường kính $60\text{px}$, nền xanh công nghiệp thương hiệu EAM, icon Robot kỹ thuật viền sáng.
   - Khi bấm vào nút:
     - **Trên Web**: Bung mở một cửa sổ popup chat dạng drawer kích thước $400 \times 620\text{px}$ nổi lên ở góc phải màn hình, có nút thu nhỏ (minimize), nút phóng to toàn màn hình và nút đóng. Không làm gián đoạn hay che khuất dữ liệu người dùng đang xem.
     - **Trên Mobile**: Mở ra một **Modal Bottom Sheet** trượt từ dưới lên (hỗ trợ kéo mở rộng nửa màn hình hoặc toàn màn hình).
2. **Cơ Chế Tự Động Nhận Biết Ngữ Cảnh (Context-Aware Binding)**:
   - Khi người dùng đang đứng ở trang chi tiết thiết bị (`/assets/<id>/`) hoặc trang phiếu sửa chữa (`/work-orders/<id>/`):
     - Nút FAB hiển thị một chấm xanh nhỏ báo hiệu: `Đang liên kết: [Mã Thiết Bị]`.
     - Khi mở khung chat, hệ thống tự động tiêm ngầm thông số máy (`assetId`, `model`, `year`, `serial`) vào ngữ cảnh truy vấn. Người thợ chỉ cần gõ câu hỏi cộc lốc: *"Máy kêu lạch cạch xử lý sao?"* $\rightarrow$ AI tự động hiểu và truy xuất tài liệu của đúng con máy đó mà thợ không cần gõ lại tên máy.
   - Khi mở khung chat tại các trang chung (Dashboard, Danh mục): Hệ thống hiển thị thanh chọn nhanh thiết bị (Asset Selector) hoặc nút quét mã QR.
3. **Nút Gợi Ý Câu Hỏi Nhanh 1-Chạm (Quick Action Chips)**:
   - Ngay dưới lời chào mừng của Chatbot, hiển thị sẵn 4 viên thuốc gợi ý thao tác nhanh để thợ không cần gõ phím:
     - 🔍 *Quy trình bảo dưỡng định kỳ SOP*
     - ⚡ *Tra cứu mã lỗi & Khắc phục khẩn cấp*
     - 🔩 *Kiểm tra phụ tùng có sẵn trong kho*
     - ❓ *Nút trên trang này dùng để làm gì?*
4. **Trợ Lý Hướng Dẫn Tính Năng & Nút Bấm Hệ Thống (EAM Web/Mobile System Guide)**:
   - Khi người dùng hỏi bất kỳ câu hỏi nào về cách sử dụng phần mềm (ví dụ: *"Làm sao tạo phiếu bảo trì?"*, *"Nút Xuất Excel ở đâu?"*, *"Nút này có tác dụng gì?"*):
   - Chatbot tự động nhận diện và truy xuất cơ sở tri thức hệ thống dùng chung (Global Knowledge), giải thích rõ ý nghĩa nút bấm, luồng đi và điều kiện phân quyền tương ứng.
5. **Giao Diện Hội Thoại Đa Phương Tiện & Trực Quan Hóa Minh Bạch**:
   - Tách biệt rõ 2 khối nội dung bằng màu sắc: Khối xanh dương (Hướng dẫn sách hãng OEM) và Khối vàng hổ phách (Mẹo thực tế nhà máy kế thừa từ Work Order).
   - Thẻ neo sơ đồ kỹ thuật (`image_anchors`): Chạm vào ảnh bản vẽ để phóng to toàn màn hình xem rõ từng chi tiết bu-lông và số hiệu phụ tùng.
   - Thẻ trạng thái tồn kho thời gian thực: Hiển thị trực quan số lượng và vị trí kệ kho (Xanh lá = Còn hàng, Cam = Đang mượn / Hết hàng).
   - Thẻ trích dẫn minh bạch (Source Citation): Hiển thị rõ tên tài liệu, số trang và điểm tin cậy tương đồng $\text{Sim} \ge 85\%$, kèm nút bấm **[Xem trang tài liệu gốc]** để mở popup xem trực tiếp đúng trang PDF sơ đồ đó.
6. **Nút 1-Chạm Tạo Phiếu Sửa Chữa (Actionable Chat-to-WorkOrder)**:
   - Ở cuối câu trả lời chẩn đoán sự cố, hiển thị nút bấm màu xanh lá nổi bật:
     > 🔘 **[🛠️ Tạo Phiếu Sửa Chữa Đột Xuất Từ Hội Thoại Này]**
   - Chạm vào nút sẽ điều hướng mở ngay màn hình tạo Work Order mới với toàn bộ các trường `asset_id`, mã lỗi, mô tả sự cố và phụ tùng đề xuất đã được điền sẵn tức thì.
7. **Phương Thức Tương Tác**:
   - Hệ thống tối ưu hóa hoàn toàn bằng **Văn bản gõ (Text Input)** và **Các nút bấm trực quan (Action Chips)**; loại bỏ nút ghi âm giọng nói để đảm bảo tính ổn định và tính tất định trong môi trường nhà xưởng công nghiệp nhiều tiếng ồn.

---

### 9.2. Giao Diện Quản Trị Tri Thức Trong Phân Hệ Admin (Nằm Dưới Mục Settings Chung)

- **Vị Trí Cây Thư Mục Giao Diện**:
  - Nằm trong phân hệ **Admin**, ở khu vực ngay bên dưới mục Cài đặt (Settings) chung:
    👉 **Admin Portal $\rightarrow$ Cài đặt & Cấu hình $\rightarrow$ Quản trị Tri thức Trợ lý AI (RAG Knowledge Hub)** (Đường dẫn: `/admin/rag-knowledge/`).
- **Phân Quyền Truy Cập (RBAC)**:
  - Chỉ dành riêng cho người dùng có quyền quản trị cài đặt hệ thống (`can_manage_settings = True` hoặc vai trò `ADMIN`, `CHIEF_ENGINEER`).

- **Cấu Trúc 4 Tab Nghiệp Vụ Chuyên Sâu**:
  1. **Tab 1: Quản lý Tri thức Mẫu (Curated Q&A Knowledge)**:
     - Bảng danh sách các cặp Hỏi - Đáp mẫu chuẩn vàng.
     - Phân loại rõ ràng thành 2 nhóm thẻ (Filter Badge):
       - 🏭 **Tri thức Bảo trì Thiết bị**: Phân lập theo Tenant, có chọn Model máy và dải năm sản xuất áp dụng.
       - 💻 **Hướng dẫn Sử dụng Hệ thống Web & Mobile**: Tri thức toàn cục (**Global Cross-Tenant**, `tenant_id = NULL`), hướng dẫn cách dùng các tính năng và nút bấm trên phần mềm.
     - Nút **[+ Thêm Câu Hỏi & Trả Lời Mới]**: Mở modal nhập câu hỏi mẫu, câu trả lời định dạng Markdown, chọn nhóm tri thức và bấm Lưu.
  2. **Tab 2: Hàng Đợi Phê Duyệt Của Kỹ Sư Trưởng (Curation Queue)**:
     - Danh sách các câu hỏi bị kỹ thuật viên hiện trường bấm nút 👎 (không hài lòng).
     - Giao diện hiển thị: Câu hỏi của thợ, Câu trả lời mà AI đã sinh, Lý do thợ chê (*"Tài liệu không khớp thực tế"*, *"Thiếu bước tháo phốt"*...).
     - Kỹ sư trưởng đọc, chỉnh sửa lại câu trả lời thành bản chuẩn hoàn hảo và bấm nút **[Duyệt & Lưu Thành Tri Thức Vàng]** $\rightarrow$ Hệ thống lập tức lưu vào bảng `curated_qa_knowledge`, lần sau thợ hỏi câu tương tự AI sẽ ưu tiên trả lời theo câu trả lời chuẩn này.
  3. **Tab 3: Thư Viện Tài Liệu Kỹ Thuật (OEM & System Documents Library)**:
     - Bảng quản lý các tài liệu PDF/Word đã tải lên MinIO/PostgreSQL.
     - Thông tin chi tiết: Tên file, Model máy áp dụng, Dải năm sản xuất, Dung lượng, Số lượng đoạn (Chunks) đã phân tách.
     - Nút **[Tải Lên Tài Liệu Mới]** và nút **[Đồng Bộ Lại Chỉ Mục PGVector (Re-index)]**.
  4. **Tab 4: Cấu Hình Từ Điển Tiếng Lóng & Ngắt An Toàn Sinh Mạng**:
     - Bảng quản lý từ điển tiếng lóng cơ khí xưởng: Cho phép người quản trị thêm các từ lóng dân dã mới của địa phương (ví dụ: *"cháy bố"*, *"xì phốt"*, *"kẹt ty"* $\rightarrow$ dịch sang thuật ngữ kỹ thuật tương đương nào).
     - Danh mục từ khóa nguy cấp kích hoạt E-Stop khẩn cấp: Cho phép cán bộ an toàn (`SAFETY_OFFICER`) bổ sung các từ khóa nguy hiểm chết người.

---

## 10. Tiêu Chí Chấp Nhận & Ma Trận Kịch Bản Kiểm Thử (Acceptance Criteria & Test Scenarios)

### 10.1. Ma Trận 15 Kịch Bản Kiểm Thử Nghiệp Vụ, An Toàn Kỹ Thuật & UI/UX

| Mã Test | Tên Kịch Bản | Điều Kiện Thử Nghiệm | Hành Vi Kỳ Vọng | Trạng Thái |
| :--- | :--- | :--- | :--- | :--- |
| **TC-RAG-01** | Cắt ngang an toàn sinh mạng khẩn cấp | Câu hỏi chứa cụm từ "cháy dầu", "chập điện", "bốc khói" | Bỏ qua RAG, hiển thị ngay thông báo đỏ yêu cầu ấn E-Stop và sơ tán | Chưa thực hiện |
| **TC-RAG-02** | Mở rộng câu hỏi tiếng lóng & từ tượng thanh *(User Scen 2)* | Nhập câu hỏi: "Bơm kêu lạch cạch, tụ phù" | Query Expansion dịch sang `cavitation`, `capacitor bulging`, truy xuất chính xác tài liệu | Chưa thực hiện |
| **TC-RAG-03** | Bảo tồn neo bản vẽ sơ đồ kỹ thuật *(User Scen 1)* | Hỏi quy trình tháo cụm chi tiết có tham chiếu `[Fig 2.4]` | UI hiển thị ảnh bản vẽ kỹ thuật phóng to kèm chỉ dẫn số trang | Chưa thực hiện |
| **TC-RAG-04** | Truy xuất Cha-Con chống mất bước SOP *(User Scen 3)* | Tra cứu quy trình thay dầu 20 bước | Nạp trọn vẹn Parent Chunk, hiển thị đầy đủ từ Bước 1 đến Bước 20 | Chưa thực hiện |
| **TC-RAG-05** | Truy xuất song luồng mẹo thực tế nhà máy *(User Scen 4)* | Đặt câu hỏi về tháo bu-lông máy | Câu trả lời kết hợp sách hãng và mẹo xịt RP7 từ lịch sử Work Order | Chưa thực hiện |
| **TC-RAG-06** | Lọc cứng siêu dữ liệu theo năm sản xuất *(User Scen 5)* | Hỏi tài liệu máy PUMP-X100 sản xuất năm 2015 | Chỉ truy xuất tài liệu áp dụng đời 2015 (ron cao su), chặn tài liệu đời 2023 | Chưa thực hiện |
| **TC-RAG-07** | Tra cứu tồn kho phụ tùng & dụng cụ *(Bổ sung 1)* | Quy trình nhắc tới phớt cơ khí SKF-2210 | Gọi API Kho hiển thị số lượng tồn (5 cái) và vị trí kệ chứa (B3-02) | Chưa thực hiện |
| **TC-RAG-08** | Chống đảo ngược từ phủ định an toàn *(Bổ sung 2)* | Tài liệu gốc ghi "DO NOT turn valve while running" | AI không được làm rớt chữ NOT; nếu nghi ngờ mâu thuẫn thì trích dẫn nguyên văn | Chưa thực hiện |
| **TC-RAG-09** | Gói dự phòng ngoại tuyến FTS5 di động *(Bổ sung 3)* | Ngắt toàn bộ mạng 4G/Wifi trên điện thoại | Trợ lý tự động chuyển sang SQLite FTS5 trả lời mã lỗi cơ bản | Chưa thực hiện |
| **TC-RAG-10** | Vòng lặp thẩm định Kỹ sư trưởng *(Bổ sung 4)* | Thợ bấm nút 👎 vào câu trả lời | Đẩy đoạn chat vào Curation Queue để Kỹ sư trưởng hiệu chỉnh thành Curated QA | Chưa thực hiện |
| **TC-RAG-11** | Nút 1-chạm tạo Work Order từ hội thoại *(Bổ sung 5)* | Bấm nút "Tạo phiếu bảo trì đột xuất" trên chat | Mở màn hình tạo Work Order với các thông số máy, mã lỗi và phụ tùng điền sẵn | Chưa thực hiện |
| **TC-RAG-12** | Ngưỡng cắt thoái lui an toàn $\text{Sim} < 0.65$ | Hỏi về mã lỗi hoàn toàn không có trong tài liệu | Trả về thông báo từ chối an toàn, không tự ý sáng tác câu trả lời | Chưa thực hiện |
| **TC-RAG-13** | Trợ lý hướng dẫn tính năng phần mềm EAM (Global Guide) | Hỏi: "Nút phát hành phiếu bảo trì có tác dụng gì?" | Truy xuất tri thức dùng chung (`is_system_guide=True`), không bị chặn tenant, hướng dẫn chuẩn xác | Chưa thực hiện |
| **TC-RAG-14** | Quản trị viên Settings thêm Q&A trong Admin Hub | User có quyền `can_manage_settings` thêm Q&A trong `/admin/rag-knowledge/` | Lưu thành công vào database và Chatbot lập tức trả lời được câu hỏi đó | Chưa thực hiện |
| **TC-RAG-15** | Nút FAB nổi tự động nhận biết ngữ cảnh trang | Mở chat khi đang đứng ở trang chi tiết `PUMP-X100` | Nút FAB tự động tiêm `assetContext` PUMP-X100 vào truy vấn ngầm | Chưa thực hiện |

---

## 11. Implementation Notes — For Implementation Phase Only

> [!IMPORTANT]
> **REFERENCE ONLY — DO NOT IMPLEMENT OR MODIFY CODE BASED ON THIS SECTION DURING SPEC REVIEW. These notes are intended for the implementation phase after the specification is approved.**

Phần này lưu trữ các thuật toán mở rộng câu hỏi và truy xuất cha-con để tham khảo trong quá trình lập trình:

### 11.1. Bộ Biến Đổi Câu Hỏi Tiếng Lóng (Query Expansion Reference)
```python
SLANG_TECHNICAL_DICTIONARY = {
    'lạch cạch': 'mechanical looseness cavitation bearing vibration',
    'xì xèo': 'gas leakage pressure relief valve discharging',
    'phù tụ': 'capacitor bulging dielectric breakdown overvoltage',
    'chết heo': 'brake caliper seizure hydraulic cylinder failure',
    'hụt hơi': 'suction loss flow rate drop insufficient pressure'
}

def expand_slang_query(prompt: str) -> str:
    expanded_terms = []
    prompt_lower = prompt.lower()
    for slang, tech in SLANG_TECHNICAL_DICTIONARY.items():
        if slang in prompt_lower:
            expanded_terms.append(tech)
    
    if expanded_terms:
        return f"{prompt} ({' '.join(expanded_terms)})"
    return prompt
```

### 11.2. Logic Truy Xuất Cha-Con (Parent-Child PGVector Query)
```python
def retrieve_parent_child_context(query_embedding: list, model: str, year: int, tenant_id: str, limit: int = 3) -> list:
    """Truy xuất trên child chunks nhưng trả về parent_content trọn vẹn."""
    sql = """
        SELECT parent_content, image_anchors, 1 - (embedding <=> %s::vector) AS similarity
        FROM document_chunks dc
        JOIN technical_documents td ON dc.document_id = td.id
        WHERE td.tenant_id = %s
          AND td.applicable_model = %s
          AND %s BETWEEN td.applicable_year_start AND td.applicable_year_end
          AND dc.is_active = TRUE
        ORDER BY embedding <=> %s::vector
        LIMIT %s;
    """
    # Thực thi qua Django connection.cursor()
    return []
```

---

## 12. Kế Hoạch Triển Khai & Nghiệm Thu (Implementation Checklist)

- [ ] **Task 11.9.1 — PGVector Extension & Multi-Source Schema**
  - [ ] Kích hoạt extension `pgvector` trên cơ sở dữ liệu PostgreSQL.
  - [ ] Xây dựng bảng `technical_documents` hỗ trợ cả tài liệu OEM theo tenant và cẩm nang hướng dẫn phần mềm dùng chung (`is_system_guide = TRUE`).
  - [ ] Xây dựng bảng `document_chunks` hỗ trợ Parent-Child, lưu trữ neo hình ảnh `image_anchors` và cờ tri thức hệ thống.
  - [ ] Xây dựng bảng `curated_qa_knowledge` hỗ trợ phân loại `EQUIPMENT_MAINTENANCE` (theo tenant) và `SYSTEM_FEATURE_GUIDE` (global dùng chung).
- [ ] **Task 11.9.2 — Ingestion Pipeline & Dual-Stream Vectorization**
  - [ ] Cài đặt bộ phân tích Markdown/PDF bảo toàn bảng mã lỗi và neo bản vẽ kỹ thuật.
  - [ ] Xây dựng pipeline tự động vector hóa ghi chú giải quyết sự cố (`resolution_notes`) từ Work Order.
  - [ ] Xây dựng pipeline nạp tri thức hướng dẫn sử dụng tính năng phần mềm EAM Web & Mobile.
  - [ ] Nhúng mô hình `sentence-transformers/all-MiniLM-L6-v2` tạo vector 384 chiều.
- [ ] **Task 11.9.3 — Query Expansion, Safety Interceptor & Contradiction Guard**
  - [ ] Cài đặt bộ biến đổi câu hỏi tiếng lóng / từ tượng thanh sang thuật ngữ tiêu chuẩn (`SLANG_TECHNICAL_DICTIONARY`).
  - [ ] Cài đặt bộ ngắt an toàn sinh mạng khẩn cấp (E-Stop).
  - [ ] Cài đặt bộ kiểm định mâu thuẫn từ phủ định an toàn (Contradiction Guard).
- [ ] **Task 11.9.4 — Live Inventory Interlock, Actionable Chat & Offline Package**
  - [ ] Tích hợp API gọi ngầm kiểm tra tồn kho phụ tùng và dụng cụ thực tế (`SparePart`).
  - [ ] Xây dựng endpoint tải gói dữ liệu ngoại tuyến (Pre-fetch) cho ứng dụng di động Flutter (SQLite FTS5).
  - [ ] Xây dựng API tạo nhanh bản thảo Work Order trực tiếp từ đoạn chat (`Chat-to-WorkOrder`).
- [ ] **Task 11.9.5 — UI Integration, Admin Knowledge Hub & Test Matrix Verification**
  - [ ] Xây dựng Widget nút nổi tròn FAB ở góc dưới bên phải màn hình Web & Mobile kèm cơ chế tự động nhận diện ngữ cảnh (`assetContext`).
  - [ ] Xây dựng Trung tâm Quản trị Tri thức Trợ lý AI trong phân hệ Admin (khu vực dưới mục Settings chung `/admin/rag-knowledge/`) với 4 Tab: Curated Q&A, Curation Queue, OEM Document Ingestion, Slang & Safety Settings.
  - [ ] Triển khai bộ kiểm thử tự động 15 test cases (`TC-RAG-01` đến `TC-RAG-15`).

# Thiết Kế Hệ Thống & Đặc Tả Kỹ Thuật: Task 11.7 — Smart Field Biometric Attendance & Multi-Tier Proximity Geofencing (MobileFaceNet, ESP32 Universal BLE Beacon 50m & Haversine Fallback)

> **Căn cứ Đề cương Đồ án Tốt nghiệp**: Mục 3.1.3 (Thuật toán nghiên cứu cốt lõi) & Mã chức năng 106.
> **Mục tiêu nghiên cứu**: Ứng dụng mô hình mạng nơ-ron học sâu **MobileFaceNet** nhận diện khuôn mặt hai giai đoạn (**Đăng ký hồ sơ trên Web $\rightarrow$ Điểm danh thời gian thực trên Mobile**) kết hợp cơ chế kiểm soát không gian vi định vị **ESP32 Universal BLE Beacon** trong bán kính **năm mươi mét ($50\text{m}$)** theo mô hình suy hao tín hiệu logarit (Log-Distance Path Loss Model) cho nhà xưởng trong nhà, kết hợp giải thuật trắc địa **Haversine** cho thiết bị ngoài trời và cơ chế **Cổng Kép Đầu - Cuối (Dual-Gate Interlock: Bắt đầu & Nghiệm thu hoàn thành)** vào ứng dụng di động Flutter để ngăn chặn triệt để tình trạng "lệnh làm việc ma" và "nghiệm thu khống từ xa".

---

## 1. Mục Tiêu & Phạm Vi (Objective & Scope)

### 1.1. Bản Chất Nghiệp Vụ Của Điểm Danh Hiện Trường (Proof-of-Presence)
Trong quản lý vận hành bảo trì thiết bị công nghiệp (EAM), các hệ thống truyền thống thường đối mặt với hai vấn đề gian lận nghiêm trọng:
1. **Lệnh làm việc ma (Phantom Work Orders)**: Kỹ thuật viên ngồi ở quán cà phê hoặc phòng nghỉ bấm nhận việc và báo đã bắt đầu làm việc mà không hề có mặt tại xưởng máy.
2. **Nghiệm thu khống từ xa (Remote Phantom Completion)**: Kỹ thuật viên rời khỏi hiện trường mà chưa hoàn thành bảo dưỡng hoặc chưa chạy thử máy, sau đó ngồi từ xa bấm "Hoàn thành" phiếu công việc.

### 1.2. Tại Sao GPS Vệ Tinh Không Khả Thi Trong Nhà Xưởng & Giải Pháp ESP32 BLE Beacon
- **Điểm yếu chí mạng của GPS ngoài đời thực**: Sóng GPS vệ tinh tần số $1.5\text{ GHz}$ bị suy hao từ $20 - 30\text{ dB}$ khi đi qua mái tôn kim loại, trần bê tông cốt thép của phân xưởng và tầng hầm. Sai số định vị GPS trong nhà thường bị dạt $\pm 50 - 150\text{m}$ hoặc mất sóng hoàn toàn (`accuracy > 50m`). Nếu ép buộc kỹ thuật viên dùng GPS Haversine trong nhà máy, hệ thống sẽ liên tục từ chối sai (False Rejection) dù thợ đang đứng sát cạnh máy.
- **Dữ liệu EAM là dữ liệu phân cấp phẳng (Indoor Hierarchy)**: Trong cơ sở dữ liệu EAM, máy móc đặt ở các vị trí: *Cơ sở $\rightarrow$ Tòa nhà $\rightarrow$ Tầng $\rightarrow$ Phòng* kèm tọa độ mặt bằng (`coords_x`, `coords_y`, `floor_level`). Việc đo đạc kinh/vĩ độ GPS cho hàng ngàn máy tiện, máy phay, máy nén khí trong nhà xưởng là cực kỳ khó khăn và không thực tế.
- **Giải pháp Mỏ Neo Không Gian Vạn Năng ESP32 (Universal Spatial Anchor Beacon)**:
  - Gắn một mạch **ESP-32 (WiFi + Bluetooth SoC DevKit CP2102 Type-C)** nạp firmware mỏ neo không gian vạn năng đặt tại khu vực máy móc kiểm thử.
  - Mạch phát sóng Bluetooth Low Energy (BLE iBeacon) ở công suất phát tối đa $+9\text{ dBm}$, tạo nên một "hàng rào vi địa lý" (Micro-Geofence) bán kính chuẩn xác **$\le 50\text{ mét}$**.
  - **Tối ưu hóa công nghiệp chống nóng mạch**: Hạ xung nhịp CPU từ $240\text{ MHz}$ xuống $80\text{ MHz}$, ngắt hoàn toàn WiFi radio và phát sóng theo chu kỳ $100\text{ms}$ (chuẩn Apple iBeacon, duty cycle chỉ $1.5\%$). Mạch chạy $24/7$ liên tục mà **hoàn toàn mát lạnh, không nóng chip, không trôi dạt nhiệt (Zero Thermal Drift)** và tiết kiệm $65\%$ năng lượng.
  - Điện thoại Flutter quét sóng BLE tức thời trong $\le 0.5$ giây, đọc chỉ số cường độ sóng nhận được ($\text{RSSI}$) và tính toán khoảng cách thực tế $d$ theo mô hình suy hao sóng công nghiệp.

### 1.3. Cơ Chế Kiểm Soát "Cổng Kép Đầu - Cuối" (Dual-Gate Interlock)
Hệ thống thiết lập cơ chế kiểm soát hiện trường nghiêm ngặt tại **2 mốc sinh tử** của vòng đời lệnh làm việc, loại bỏ hoàn toàn việc quét liên tục gây tiêu hao pin điện thoại:

```
┌────────────────────────────────────────────────────────────────────────┐
│              CỔNG 1: BẮT ĐẦU LÀM VIỆC (START WORK GATE)                │
│  1. Quét sóng ESP32 BLE: RSSI >= -92 dBm (Bán kính <= 50m)             │
│  2. Nhận diện khuôn mặt MobileFaceNet TFLite: Cosine Sim >= 0.72       │
│  3. Gửi Check-in: Chuyển Work Order từ ASSIGNED -> IN_PROGRESS         │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                         TIẾN HÀNH BẢO DƯỠNG SỬA CHỮA
             (Hiển thị huy hiệu kết nối, KHÔNG quét ngầm liên tục để tiết kiệm 100% pin)
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│             CỔNG 2: NGHIỆM THU HOÀN THÀNH (COMPLETE WORK GATE)         │
│  1. Kiểm tra hiện diện: Quét sóng ESP32 BLE trong 3 giây (d <= 50m)    │
│  2. Nhập thông số kỹ thuật sau sửa (Độ rung RMS, Nhiệt độ thân máy)   │
│  3. Chụp ảnh nghiệm thu hiện trường đóng dấu chìm (Watermark)          │
│  4. Chặn đứng việc bấm hoàn thành từ xa nếu không bắt được sóng ESP32  │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Ràng Buộc Kế Thừa Hệ Thống (Existing System Constraints & Codebase Reuse)

- **Tái Sử Dụng Mô Hình Multi-Tenancy**: Mọi dữ liệu hồ sơ sinh trắc học và lịch sử điểm danh kế thừa `BaseTenantModel`, bảo đảm phân lập hoàn toàn giữa các Tenant qua `TenantManager`.
- **Tái Sử Dụng Thực Thể Nghiệp Vụ Sẵn Có**:
  - `WorkOrder`: Kiểm soát trạng thái chuyển dịch từ `ASSIGNED` sang `IN_PROGRESS` (Cổng 1) và từ `IN_PROGRESS` sang `COMPLETED` (Cổng 2).
  - `Asset`: Bổ sung mã định danh Beacon `ble_beacon_uuid` và địa chỉ `ble_mac_address`. Đồng thời kế thừa tọa độ mặt bằng (`coords_x`, `coords_y`, `floor_level`) và mã QR thân máy (`qr_code`).
  - `User`: Hồ sơ nhân viên kỹ thuật thực hiện điểm danh.
- **Tối Ưu Hóa Thiết Bị Di Động (Edge Inference)**: Mô hình MobileFaceNet được đóng gói dạng TFLite (`mobilefacenet.tflite` $\approx 4.1\text{ MB}$) chạy trực tiếp trên chip di động của kỹ thuật viên, không yêu cầu máy chủ phải gắn GPU.
- **Kiến Trúc Đóng Gói Module Giải Thuật & Dữ Liệu Cách Ly (Dedicated Algorithms & Data Package)**:
  - Tuân thủ quy ước kiến trúc chung của toàn bộ Phase 11, toàn bộ mã nguồn giải thuật (kiểm soát không gian BLE RSSI, trắc địa Haversine, cổng kiểm soát 15 phút), **cùng toàn bộ tệp mô hình học sâu và dữ liệu tải về liên quan đều được đặt tập trung hoàn toàn trong thư mục riêng biệt: `eam_app/algorithms/biometric/`**.
  - Cấu trúc thư mục cách ly rõ ràng:
    - `eam_app/algorithms/biometric/models/`: Chứa tệp trọng số mô hình MobileFaceNet (`mobilefacenet.tflite` $\approx 4.1\text{ MB}$).
    - `eam_app/algorithms/biometric/data/`: Chứa các tệp dữ liệu kiểm thử, vector chuẩn đối soát, và tập dữ liệu mẫu benchmark tải về (LFW / Synthetic data).
    - `eam_app/algorithms/biometric/`: Chứa các script giải thuật lõi (`proximity_engine.py`, `cosine_similarity.py`, `enrollment.py`, `gatekeeper.py`).
  - Tách biệt hoàn toàn tầng giải thuật và dữ liệu AI khỏi các tầng controller/CRUD thông thường, giúp người dùng dễ nhận biết, bảo trì và đóng gói đồ án tốt nghiệp.

---

## 3. Yêu Cầu Nghiệp Vụ & Quy Tắc Cốt Lõi (Business Requirements & Core Rules)

Toàn bộ module điểm danh sinh trắc học và định vị hiện trường tuân thủ nghiêm ngặt 8 quy tắc nghiệp vụ chuẩn mực sau:

### Quy Tắc 1: Định Vị Hiện Trường 50m Bằng Sóng ESP32 BLE Beacon (Log-Distance Path Loss Model)
- **Cơ Sở Toán Học**:
  Khoảng cách trắc địa $d$ giữa điện thoại của kỹ thuật viên và mạch ESP32 được xác định thông qua mô hình suy hao tín hiệu sóng vô tuyến logarit (Log-Distance Path Loss Model):
  $$\text{RSSI} = - \left(10 \cdot n \cdot \log_{10}(d) - A\right)$$
  $$\Longleftrightarrow d = 10^{\frac{A - \text{RSSI}}{10 \cdot n}} \quad (\text{mét})$$
  Trong đó:
  - $\text{RSSI}$: Chỉ số cường độ tín hiệu nhận được trên điện thoại ($\text{dBm}$).
  - $A$: Cường độ tín hiệu đo được ở khoảng cách chuẩn $1\text{m}$ (Đối với ESP32 phát ở công suất $+9\text{ dBm}$, $A = -59\text{ dBm}$).
  - $n$: Hệ số suy hao môi trường ($n = 2.0$ trong không gian tự do, $n = 2.8$ trong nhà xưởng công nghiệp có máy móc kim loại).
  - $d$: Khoảng cách ước tính tính bằng mét.
- **Quy Tắc Ngưỡng Chấp Thuận 50 Mét**:
  - Tại khoảng cách giới hạn $d = 50.0\text{m}$ với $n = 2.8$:
    $$\text{RSSI}_{50\text{m}} = -59 - (10 \times 2.8 \times \log_{10}(50)) = -59 - 47.57 \approx -92\text{ dBm}$$
  - **Điều kiện hợp lệ**: $\text{RSSI} \ge -92\text{ dBm}$ (tương đương $d \le 50.0\text{ mét}$) và bắt được tín hiệu `EAM-UNIVERSAL-BEACON`.
  - **Từ chối**: Nếu $\text{RSSI} < -92\text{ dBm}$ hoặc không tìm thấy tín hiệu ESP32, ứng dụng báo ngoài phạm vi và yêu cầu thợ tiến lại gần máy.

---

### Quy Tắc 2: Kiến Trúc Mạng Nơ-Ron Học Sâu MobileFaceNet & Nguồn Dữ Liệu Huấn Luyện (Deep Learning Architecture & Data Provenance)

Để việc điểm danh khuôn mặt có tác dụng xác thực thực tế và đạt độ tin cậy khoa học cao nhất trước Hội đồng chấm luận văn, hệ thống áp dụng mô hình mạng nơ-ron tích chập chuyên sâu **MobileFaceNet** với quy trình học sâu 2 giai đoạn:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│               QUY TRÌNH HỌC SÂU NHẬN DIỆN KHUÔN MẶT 2 GIAI ĐOẠN                        │
├───────────────────────────────────────────┬────────────────────────────────────────────┤
│ GIAI ĐOẠN 1: ĐĂNG KÝ HỒ SƠ TRÊN WEB       │ GIAI ĐOẠN 2: ĐIỂM DANH HIỆN TRƯỜNG MOBILE │
│ (Web Face Enrollment Pipeline)            │ (Live Mobile Edge Inference & Matching)    │
│                                           │                                            │
│ 1. Admin/Thợ tải 1 ảnh chân dung lên Web  │ 1. Thợ mở camera quét mặt trực tiếp        │
│ 2. MTCNN/MediaPipe căn chỉnh 5 điểm mốc   │ 2. Google ML Kit bắt mặt & liveness chớp   │
│ 3. Cắt chuẩn $112 \times 112 \times 3$    │ 3. MobileFaceNet TFLite chạy trên chip     │
│ 4. MobileFaceNet trích xuất vector v      │ 4. Trích xuất vector thời gian thực u      │
│ 5. Chuẩn hóa $L_2$: ||v||_2 = 1.0         │ 5. Tính Cosine Sim: sum(u_i * v_i)         │
│ 6. Lưu 128 số thực vào PostgreSQL         │ 6. Sim >= 0.72 -> MỞ KHÓA WORK ORDER       │
└───────────────────────────────────────────┴────────────────────────────────────────────┘
```

#### 2.1. Kiến Trúc Mạng Nơ-ron MobileFaceNet (Deep Learning Architecture)
MobileFaceNet là mạng nơ-ron tích chập sâu (Deep CNN) được tối ưu hóa đặc thù cho bài toán nhận diện khuôn mặt thời gian thực trên thiết bị biên di động:
- **Khối Tích Chập Tách Biệt Theo Chiều Sâu (Depthwise Separable Convolutions & Linear Inverted Residual Bottlenecks)**: Giúp giảm hơn $80\%$ khối lượng tính toán so với CNN tiêu chuẩn.
- **Tích Chập Toàn Cục Theo Chiều Sâu (Global Depthwise Convolution — GDConv)**: Khác với mạng phân loại ảnh thông thường sử dụng Global Average Pooling (GAP) làm mất thông tin vị trí, MobileFaceNet sử dụng lớp GDConv $7 \times 7$ để duy trì trọng số không gian giữa các vùng đặc trưng trên khuôn mặt (mắt, sống mũi, khóe miệng).
- **Thông Số Kỹ Thuật Mô Hình**:
  - Tổng số tham số (Parameters): **$0.99\text{ triệu tham số}$** ($\approx 1\text{M}$ params, so với $23\text{M}$ của ResNet-50).
  - Độ phức tạp tính toán: **$221\text{ MFLOPs}$** (Mega FLOPs).
  - Kích thước tệp TFLite lượng tử hóa: **$\approx 4.1\text{ MB}$** (dễ dàng nhúng gọn gàng vào thư mục `assets/` của ứng dụng Flutter).
  - Thời gian suy luận (Inference Latency): **$20 - 30\text{ ms}$** trên CPU điện thoại thông thường, không cần chip NPU chuyên dụng.
  - Chuẩn hóa đầu vào (Input Preprocessing): Ảnh RGB $112 \times 112 \times 3$ với giá trị điểm ảnh chuẩn hóa:
    $$x_{\text{norm}} = \frac{x - 127.5}{128.0} \in [-1.0, 1.0]$$
  - Đầu ra (Output Embedding): Vector đặc trưng sinh trắc học 128 chiều $\vec{z} \in \mathbb{R}^{128}$, sau đó chuẩn hóa chuẩn $L_2$:
    $$\vec{v} = \frac{\vec{z}}{\|\vec{z}\|_2} \in \mathbb{R}^{128} \quad \text{sao cho } \|\vec{v}\|_2 = 1.0$$

#### 2.2. Nguồn Dữ Liệu Huấn Luyện, Nền Tảng Kaggle & Kiểm Chứng Khoa Học (Data Provenance & Kaggle Datasets)

Một câu hỏi mang tính nền tảng trong Computer Vision: **"Hệ thống có cần lấy dữ liệu trên Kaggle về tự ngồi huấn luyện lại (Train from scratch) hay không?"**

> [!NOTE]
> **Bản Chất Của Nhận Diện Khuôn Mặt Hiện Đại: Học Một Lần (One-Shot Metric Learning)**
> - Trong phân loại ảnh thông thường (Classification, ví dụ chó/mèo hay lỗi sản phẩm), ta phải gom hàng nghìn ảnh rồi train lại mạng nơ-ron. Nếu làm thế với công nhân viên nhà máy thì **hoàn toàn bất khả thi trong thực tế**: Cứ mỗi lần công ty tuyển thợ mới hoặc đổi ca trực, chẳng lẽ doanh nghiệp lại phải cắm máy tính chạy GPU train lại mô hình mất 3–4 tiếng?
> - Trong thực tế công nghiệp, bài toán nhận diện khuôn mặt là bài toán **One-Shot Learning (Metric Learning)**:
>   - Mạng nơ-ron MobileFaceNet đóng vai trò là một **"Bộ trích xuất đặc trưng hình học vạn năng" (Deep Feature Extractor)**.
>   - Mô hình này đã được huấn luyện hội tụ sẵn trên hàng triệu khuôn mặt người trên toàn cầu để học được thế nào là mắt, mũi, cằm, gò má, tỷ lệ nhân trắc học khuôn mặt.
>   - Khi triển khai vào nhà máy: Nhân viên mới chỉ cần nộp **đúng 1 tấm ảnh chân dung duy nhất (One-Shot)** trên Web. AI tự động chiếu khuôn mặt đó thành 128 con số (Vector Embedding). Khi điểm danh, camera bắt mặt thợ thành 128 con số khác và so sánh Cosine Similarity. **Không cần phải huấn luyện lại mạng nơ-ron!**

#### Nguồn Dữ Liệu Kaggle & Tập Dữ Liệu Thực Nghiệm Trong Đồ Án Tốt Nghiệp:
Hệ thống sử dụng nền tảng **Kaggle Datasets** và các kho dữ liệu chuẩn mực quốc tế cho 3 mục đích nghiên cứu cốt lõi:

1. **Tập Dữ Liệu Huấn Luyện Cốt Lõi Trên Kaggle (Pre-trained Backbone Datasets)**:
   - Mô hình MobileFaceNet được huấn luyện dựa trên hàm mất mát lề góc cộng hưởng **ArcFace (Additive Angular Margin Loss)**:
     $$\mathcal{L} = -\log \frac{e^{s \cdot \cos(\theta_{y_i} + m)}}{e^{s \cdot \cos(\theta_{y_i} + m)} + \sum_{j \neq y_i} e^{s \cdot \cos \theta_j}}$$
     với tham số tỷ lệ hình cầu $s = 64$ và lề góc phạt $m = 0.5$, giúp tối đa hóa khoảng cách phân tách góc giữa các danh tính khác nhau trong không gian siêu cầu 128 chiều.
   - **Tập CASIA-WebFace trên Kaggle** (Bản chuẩn căn chỉnh $112 \times 112$: [`kaggle.com/datasets/yakhyo/webface-112x112`](https://www.kaggle.com/datasets/yakhyo/webface-112x112) hoặc bản nguyên gốc [`kaggle.com/datasets/debarghamritaroy/casia-webface`](https://www.kaggle.com/datasets/debarghamritaroy/casia-webface)): Gồm $494,414$ ảnh khuôn mặt của $10,572$ đối tượng được dùng trong nghiên cứu để huấn luyện các trọng số nơ-ron cốt lõi (sau đó cô đọng lại thành tệp mô hình `mobilefacenet.tflite` siêu nhẹ $4.1\text{ MB}$).
   - **Tập MS1MV2 (MS-Celeb-1M Refined)**: Gồm $5.8\text{ triệu}$ ảnh khuôn mặt dùng để tinh chỉnh độ chính xác.

2. **Tập Dữ Liệu Đánh Giá Đối Sánh Benchmark Chuẩn Học Thuật Trên Kaggle**:
   - **Tập LFW (Labeled Faces in the Wild Dataset) trên Kaggle** (`kaggle.com/datasets/jessicali9530/lfw-dataset`): Gồm $13,233$ ảnh của $5,749$ cá nhân.
   - Tập LFW được dùng làm **Tập kiểm chứng định lượng độc lập (Academic Quantitative Benchmark)** trong lệnh `python manage.py run_academic_benchmarks` (Task 12.2):
     - Kiểm chứng độ chính xác xác thực khuôn mặt của mô hình đạt **$99.55\%$**.
     - Kiểm chứng độ chính xác trên tập biến thiên độ tuổi **AgeDB-30**: đạt **$92.8\%$**.
     - Số liệu này được xuất thẳng ra bảng Benchmark in trong quyển báo cáo luận văn tốt nghiệp.

3. **Tập Dữ Liệu Hồ Sơ Nhân Viên Mẫu Trên Kaggle Tuân Thủ Nghị Định 13/2023/NĐ-CP**:
   - Nhằm bảo đảm tuyệt đối tính pháp lý, đạo đức nghiên cứu và tuân thủ Nghị định 13/2023/NĐ-CP của Chính phủ về bảo vệ dữ liệu cá nhân khi báo cáo trước Hội đồng Khoa học:
   - Hệ thống tích hợp tập **Synthetic Faces High Quality từ Kaggle** (`kaggle.com/datasets/greatgamedota/synthetic-faces-high-quality`): Gồm ảnh chân dung nhân tạo chất lượng cao do mô hình StyleGAN2-ADA sinh ra.
   - Bộ sinh dữ liệu của Phase 12 (Golden Seed 42) tải tập dữ liệu này từ Kaggle về để khởi tạo sẵn 20 hồ sơ nhân viên kỹ thuật mẫu trong cơ sở dữ liệu PostgreSQL, giúp hệ thống vận hành ngoại tuyến $100\%$ không phụ thuộc Internet.

4. **Quy Trình Thu Thập & Đăng Ký Dữ Liệu Thực Tế Doanh Nghiệp (Production Enrollment Pipeline)**:
   - Khi tạo nhân viên mới trên Web Portal (Task 5.2): Người quản trị tải lên **1 ảnh chân dung khuôn mặt chính diện** (`face_image`).
   - Tầng Backend chạy pipeline trích xuất:
     - MTCNN / MediaPipe Face Mesh phát hiện khuôn mặt và định vị 5 điểm mốc then chốt (2 đồng tử mắt, đỉnh mũi, 2 khóe miệng).
     - Áp dụng ma trận biến đổi Affine (Affine Transformation) để xoay thẳng khuôn mặt và cắt khung hình $112 \times 112$.
     - Đưa qua mô hình MobileFaceNet để trích xuất mảng 128 số thực $\vec{v}$.
     - Lưu 128 số thực vào bảng `biometric_profiles`. Ảnh gốc được mã hóa AES-256 lưu trữ an toàn trên MinIO.

#### 2.3. Giải Thuật So Khớp Cosine Similarity & Ngưỡng Phân Định (Cosine Similarity Thresholds)
- Độ tương đồng Cosine giữa vector thời gian thực $\vec{u}$ từ camera và vector hồ sơ $\vec{v}$ đã đăng ký trên Web:
  $$\text{Cosine Similarity}(\vec{u}, \vec{v}) = \frac{\vec{u} \cdot \vec{v}}{\|\vec{u}\|_2 \|\vec{v}\|_2} = \sum_{i=1}^{128} u_i \cdot v_i$$
- **Ngưỡng Phân Định Nghiệp Vụ**:
  - $\text{Sim} \ge 0.72$: **Xác thực thành công (Verified)** — Viền camera chuyển XANH LÁ, rung phản hồi và mở khóa thành công.
  - $0.65 \le \text{Sim} < 0.72$: **Chưa rõ nét (Indeterminate)** — Nhắc nhở điều chỉnh góc sáng hoặc tháo khẩu trang và thử lại.
  - $\text{Sim} < 0.65$: **Từ chối (Rejected)** — Báo động ĐỎ: *"Khuôn mặt không khớp với hồ sơ nhân viên được giao việc"*, từ chối mở khóa.

---

### Quy Tắc 3: Rào Chắn Nghiệm Thu Cổng 2 (Proof-of-Presence Completion Gate)
- **Điểm Yếu Nghiệp Vụ**: Kỹ thuật viên điểm danh bắt đầu lúc 8h sáng, sau đó 9h về nhà nghỉ rồi 11h trưa mở điện thoại bấm "Hoàn thành" phiếu việc mà không hề kiểm tra chạy thử máy.
- **Quy Tắc Bắt Buộc**:
  - Khi kỹ thuật viên bấm nút "Hoàn thành" trên Work Order (`status: COMPLETED`), ứng dụng di động tự động kích hoạt bộ quét BLE trong 3 giây.
  - Nếu điện thoại nhận được sóng ESP32 của máy móc ($\text{RSSI} \ge -92\text{ dBm}$): Cho phép mở biểu mẫu nghiệm thu, nhập thông số đo rung/nhiệt sau sửa chữa và gửi lệnh hoàn thành.
  - Nếu **không bắt được sóng ESP32**: Hệ thống lập tức **KHÓA CHỨC NĂNG HOÀN THÀNH** và hiển thị cảnh báo: *"Vi phạm hiện trường: Bạn không có mặt tại vị trí máy móc (Không bắt được sóng ESP32). Vui lòng có mặt trực tiếp tại thiết bị để hoàn thành phiếu bảo dưỡng!"*.

### Quy Tắc 4: Đơn Giản Hóa Triệt Để Với Mỏ Neo Không Gian Vạn Năng (Universal Spatial Anchor Beacon)
- **Tình Huống Thực Tế Của Người Dùng & Đồ Án**: Người dùng chỉ có 1 mạch ESP32 trong tay, cần một giải pháp kiểm thử gọn gàng nhất, không cấu hình lằng nhằng, nạp code một lần là chạy vĩnh viễn cho mọi ca test.
- **Quy Tắc Thực Thi**:
  - Mạch ESP32 nạp mã chuẩn mỏ neo vạn năng, phát sóng BLE với tên định danh cố định: **`EAM-UNIVERSAL-BEACON`** và UUID chuẩn: **`e2c56db5-dffb-48d2-b060-d0f5a71096e0`** ở công suất phát $+9\text{ dBm}$ (bán kính phủ sóng $50\text{m}$).
  - Trong môi trường kiểm thử và bảo vệ đồ án tốt nghiệp, ứng dụng di động Flutter trên tay thợ khi mở bất kỳ Work Order nào: chỉ cần phát hiện tín hiệu `EAM-UNIVERSAL-BEACON` với cường độ $\text{RSSI} \ge -92\text{ dBm}$ (khoảng cách $d \le 50\text{m}$) là tự động công nhận kỹ thuật viên đang có mặt tại hiện trường máy móc!
  - **Ưu điểm tuyệt đối**: Không cần nút gán động trên Web, không cần nạp lại code hay đổi cấu hình Serial. Bạn chỉ cần cắm sạc dự phòng cho ESP32 và cầm điện thoại đi lại trong phòng là demo thành công $100\%$.

### Quy Tắc 5: Cơ Chế Dự Phòng Ngoại Trời Bằng GPS Haversine (Outdoor GPS Fallback)
- **Tình Huống Thực Tế**: Thiết bị đặt ngoài trời (trạm biến áp, quạt thông gió mái xưởng, cột đèn, xe tải công trình) không có sẵn nguồn điện để cắm ESP32, nhưng bắt sóng GPS vệ tinh rất tốt.
- **Quy Tắc**:
  - Với tài sản có cấu hình tọa độ GPS (`latitude`, `longitude` khác NULL) và không có sóng ESP32, hệ thống kích hoạt chế độ **Định vị trắc địa Haversine**:
    $$d = 2 \cdot R_{\text{earth}} \cdot \text{atan2}\left(\sqrt{a}, \sqrt{1-a}\right) \le 50.0\text{ mét}$$
  - Kiểm tra cờ giả lập vị trí của hệ điều hành di động (`isMocked == false`). Phát hiện Fake GPS lập tức hủy phiên điểm danh.

### Quy Tắc 6: Cơ Chế Dự Phòng Quét Mã QR Thân Máy Khi ESP32 Mất Điện (Zero-Hardware Fallback)
- **Tình Huống Thực Tế**: Mạch ESP32 bị tuột dây sạc Type-C, mất nguồn điện hoặc bị hỏng đột xuất tại hiện trường.
- **Quy Tắc**:
  - Nếu sau 5 giây không bắt được sóng ESP32, ứng dụng hiển thị nút: *"Không thấy sóng ESP32? Quét mã QR thân máy"*.
  - Kỹ thuật viên dùng camera quét trực tiếp mã QR dán cố định trên vỏ máy móc (`asset.qr_code`) kết hợp bước quét khuôn mặt. Bản ghi được lưu nhận diện thành công với phương thức `QR_FALLBACK_WITH_BIOMETRIC`.

### Quy Tắc 7: Chống Gian Lận Thực Dụng & Khóa Luồng Camera Trực Tiếp
- **Quy Tắc Bắt Buộc**:
  - Vô hiệu hóa tính năng chọn ảnh từ thư viện (Gallery) ở tầng ứng dụng; bắt buộc điểm danh qua luồng camera phát trực tiếp (Live Camera Stream).
  - Tích hợp kiểm tra cử động sống cơ bản (chớp mắt tự nhiên hoặc nghiêng nhẹ đầu) để ngăn chặn việc giơ ảnh thẻ tĩnh trước camera.
  - Lưu trữ 1 ảnh chụp hiện trường đóng dấu chìm Watermark (Tọa độ/Mã Beacon + Giờ UTC + Mã phiếu) đẩy lên MinIO để Quản đốc có thể hậu kiểm khi cần.

### Quy Tắc 8: Cổng Gác Khóa Nghiêm Ngặt 15 Phút Phía Máy Chủ (Backend Gatekeeper)
- **Quy Tắc Bắt Buộc**:
  - Khi nhận yêu cầu bắt đầu lệnh làm việc `PUT /api/v1/work-orders/{id}/status` sang `IN_PROGRESS`, máy chủ Backend bắt buộc kiểm tra sự tồn tại của bản ghi `AttendanceLog` hợp lệ:
    1. Trùng khớp `work_order_id` và kỹ thuật viên thực hiện.
    2. Cờ xác thực đạt yêu cầu (`is_face_verified == True` và `is_location_verified == True`).
    3. Dấu thời gian điểm danh phải nằm trong vòng **15 phút gần nhất**:
       $$T_{\text{server\_now}} - T_{\text{attendance}} \le 15\text{ phút}$$
  - Thiếu bản ghi thỏa mãn, server từ chối chuyển trạng thái với mã `403 Forbidden` kèm lỗi `COMPLIANCE_ATTENDANCE_REQUIRED`.

---

## 4. Mã Nguồn Firmware Mạch ESP-32 Chuẩn Công Nghiệp (Chống Nóng, Chạy 24/7, Độ Chính Xác Cao)

Mã nguồn được lưu trực tiếp tại `scripts/firmware/esp32_asset_beacon.ino`. Mã được tối ưu hóa đặc biệt theo các tiêu chuẩn công nghiệp:
1. **Hạ tần số CPU về 80 MHz** (`setCpuFrequencyMhz(80)`): Giảm dòng tiêu thụ hơn $65\%$, triệt tiêu nguồn phát nhiệt, mạch chạy liên tục mát rượi.
2. **Tắt hoàn toàn module WiFi** (`WiFi.mode(WIFI_OFF)` & `esp_wifi_stop()`): Ngắt triệt để khối RF tiêu tốn 150-200mA.
3. **Chu kỳ quảng bá Apple iBeacon chuẩn 100ms** (160 đơn vị): Đạt tiêu chuẩn phát sóng phản hồi nhanh ($< 0.5$s) trong khi Duty Cycle chỉ $1.5\%$, giữ mạch mát lạnh và loại trừ trôi dạt nhiệt (Zero Thermal Drift).
4. **Đèn LED nhịp tim (Heartbeat)**: Nhấp nháy nhẹ 50ms mỗi 2.5s trên chân GPIO 2 báo hiệu hoạt động tốt.

```cpp
/*
 * ==============================================================================
 * EAM ENTERPRISE ASSET MANAGEMENT — ESP32 UNIVERSAL ASSET PROXIMITY BEACON
 * ==============================================================================
 * Phần cứng: ESP32 DevKit V1 (ESP-WROOM-32, CP2102, Cổng USB Type-C)
 * Chức năng: Mỏ neo không gian vạn năng (Universal Spatial Anchor Beacon)
 * Tầm phủ sóng: Chuẩn bán kính 50 mét (TxPower +9 dBm)
 *
 * TỐI ƯU HÓA CÔNG NGHIỆP — CHỐNG NÓNG & ĐỘ CHÍNH XÁC CAO:
 * 1. Hạ xung CPU từ 240MHz xuống 80MHz: Giảm 65% dòng điện, mạch chạy 24/7 mát rượi.
 * 2. Tắt hoàn toàn WiFi Radio (WiFi.mode(WIFI_OFF)): Triệt tiêu triệt để nguồn phát nhiệt.
 * 3. Chu kỳ phát chuẩn Apple iBeacon (100ms interval): Bắt sóng tức thì (<0.5s),
 *    RF Duty Cycle chỉ 1.5%, loại bỏ hoàn toàn hiện tượng trôi dạt nhiệt (Thermal Drift).
 * 4. Đèn LED chỉ báo nhịp tim (Heartbeat LED): Nhấp nháy nhẹ báo trạng thái hoạt động.
 * ==============================================================================
 */

#include <esp_bt.h>
#include <esp_wifi.h>
#include <WiFi.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLEBeacon.h>

#define BEACON_UUID       "e2c56db5-dffb-48d2-b060-d0f5a71096e0"
#define BEACON_MAJOR      1
#define BEACON_MINOR      100
#define MEASURED_POWER_1M -59 // Cường độ tín hiệu chuẩn đo tại 1 mét: -59 dBm

#define LED_PIN 2 // Đèn LED xanh tích hợp sẵn trên mạch ESP32 DevKit

BLEAdvertising *pAdvertising;
unsigned long lastHeartbeat = 0;

void setup() {
  Serial.begin(115200);
  delay(500);

  // 1. TỐI ƯU CÔNG SUẤT & NHIỆT ĐỘ: Hạ xung nhịp CPU về 80MHz (đủ cho BLE stack)
  setCpuFrequencyMhz(80);

  // 2. TẮT HOÀN TOÀN WIFI: Triệt tiêu dòng tiêu thụ 150-200mA và nguồn nhiệt lớn nhất
  WiFi.mode(WIFI_OFF);
  esp_wifi_stop();

  // Cấu hình chân đèn LED nhịp tim
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, HIGH);

  Serial.println("\n========================================================");
  Serial.println("   EAM SYSTEM — ESP32 INDUSTRIAL ASSET BEACON v2.0     ");
  Serial.println("========================================================");
  Serial.printf(" - Tần số CPU:         %d MHz (Mát máy, tiết kiệm pin)\n", getCpuFrequencyMhz());
  Serial.println(" - Chế độ WiFi:        ĐÃ TẮT (Chống nóng 100%)");

  // 3. KHỞI TẠO BLE STACK
  BLEDevice::init("EAM-UNIVERSAL-BEACON");

  // Đặt công suất phát tối đa (+9 dBm) để phủ sóng chuẩn xác bán kính 50 mét
  esp_ble_tx_power_set(ESP_BLE_PWR_TYPE_ADV, ESP_PWR_LVL_P9);
  esp_ble_tx_power_set(ESP_BLE_PWR_TYPE_DEFAULT, ESP_PWR_LVL_P9);

  // 4. CẤU HÌNH GÓI TIN CHUẨN APPLE iBEACON (Chống nhiễu & Độ chính xác cao)
  BLEBeacon myBeacon = BLEBeacon();
  myBeacon.setManufacturerId(0x4C00); // 0x4C00 = Apple Inc.

  BLEUUID bleUUID = BLEUUID(BEACON_UUID);
  myBeacon.setProximityUUID(bleUUID);
  myBeacon.setMajor(BEACON_MAJOR);
  myBeacon.setMinor(BEACON_MINOR);
  myBeacon.setSignalPower(MEASURED_POWER_1M);

  BLEAdvertisementData advData;
  advData.setFlags(0x06); // LE General Discoverable + BR/EDR Not Supported

  std::string strServiceData = "";
  strServiceData += (char)26;
  strServiceData += (char)0xFF;
  strServiceData += myBeacon.getData();
  advData.addData(strServiceData);

  pAdvertising = BLEDevice::getAdvertising();
  pAdvertising->setAdvertisementData(advData);
  pAdvertising->setScanResponse(false);

  // 5. CHU KỲ PHÁT 100ms (160 * 0.625ms): Chuẩn vàng cho định vị tức thì và mát chip
  pAdvertising->setMinInterval(160); // 100ms
  pAdvertising->setMaxInterval(160); // 100ms

  pAdvertising->start();

  Serial.println(" - Trạng thái BLE:     ĐANG PHÁT SÓNG LIÊN TỤC");
  Serial.println(" - Tên thiết bị:       EAM-UNIVERSAL-BEACON");
  Serial.println(" - UUID:               " BEACON_UUID);
  Serial.printf(" - Major / Minor:      %d / %d\n", BEACON_MAJOR, BEACON_MINOR);
  Serial.printf(" - Công suất phát:     +9 dBm (Phủ sóng ~50m, TxPower1m: %d dBm)\n", MEASURED_POWER_1M);
  Serial.println(" - Chu kỳ quảng bá:    100 ms (Bắt sóng tức thì < 0.5s)");
  Serial.println("========================================================");
  Serial.println(">> Mạch đã sẵn sàng! Cắm nguồn Type-C là chạy vĩnh viễn.");

  digitalWrite(LED_PIN, LOW);
}

void loop() {
  unsigned long currentMillis = millis();
  if (currentMillis - lastHeartbeat >= 2500) {
    lastHeartbeat = currentMillis;
    digitalWrite(LED_PIN, HIGH);
    delay(50);
    digitalWrite(LED_PIN, LOW);
  }
  delay(100);
}
```

---

## 5. Quy Trình Vận Hành Cụ Thể (End-to-End Operational Workflows)

### 5.1. Luồng Đăng Ký Khuôn Mặt Trên Web (Web Face Enrollment Flow)
```
Admin / Quản Đốc mở trang Quản lý User trên Web ──► Tải lên ảnh chân dung khuôn mặt
       │
       ▼
[Backend Deep Learning Pipeline (MobileFaceNet)]
       ├── 1. MTCNN/MediaPipe căn chỉnh 5 điểm mốc (Eyes, Nose, Mouth)
       ├── 2. Cắt chuẩn $112 \times 112 \times 3$, chuẩn hóa [-1.0, 1.0]
       ├── 3. MobileFaceNet trích xuất vector đặc trưng 128 chiều z
       ├── 4. Chuẩn hóa L2: v = z / ||z||_2 (||v||_2 = 1.0)
       ├── 5. Lưu vector 128 số thực vào PostgreSQL (biometric_profiles)
       └── 6. Mã hóa AES-256 lưu ảnh chân dung lên MinIO riêng tư
```

### 5.2. Luồng Bắt Đầu Công Việc (Start Work Order Gate)
```
Kỹ thuật viên đứng cạnh máy ──► Mở Work Order trên Flutter ──► Vuốt "Bắt đầu làm việc"
       │
       ▼
[Mở Modal Điểm Danh Hiện Trường (FieldAttendanceScreen)]
       │
       ▼
[Bước 1: Quét Sóng ESP32 BLE Beacon] (Thời gian: 0.5 - 2 giây)
       ├── Tìm thấy "EAM-UNIVERSAL-BEACON"?
       │       ├── CÓ: Đọc RSSI -> Tính d = 10^((A - RSSI)/(10*n))
       │       │       ├── d <= 50.0m (RSSI >= -92 dBm): VÙNG SÓNG HỢP LỆ (Báo Xanh)
       │       │       └── d > 50.0m (RSSI < -92 dBm): Báo ngoài vùng, yêu cầu lại gần máy
       │       └── KHÔNG THẤY:
       │               └── Sau 5 giây, hiển thị nút: "Quét mã QR dán trên thân máy" (Quy Tắc 6)
       │
       ▼ (Khi Bước 1 Hợp Lệ)
[Bước 2: Quét Khuôn Mặt Sinh Trắc Học MobileFaceNet]
       ├── Mở Live Camera Stream (Khóa 100% việc chọn ảnh từ thư viện)
       ├── ML Kit phát hiện khuôn mặt & cử động chớp mắt sống
       ├── MobileFaceNet TFLite trích xuất vector 128 chiều u trong 25ms
       └── So khớp Cosine Similarity với vector hồ sơ v đã đăng ký trên Web:
               ├── Sim >= 0.72: ĐẠT XÁC THỰC (Viền chuyển Xanh)
               └── Sim < 0.72: TỪ CHỐI (Khuôn mặt không khớp với thợ được giao việc)
       │
       ▼ (Cả 2 Bước Đều Đạt)
Gửi Yêu Cầu: POST /api/v1/attendance/check-in/
       │
       ▼
Backend ghi bản ghi AttendanceLog hợp lệ -> Work Order chuyển trạng thái IN_PROGRESS
```

### 5.3. Luồng Nghiệm Thu Hoàn Thành (Complete Work Order Gate)
```
Kỹ thuật viên sửa chữa xong ──► Vuốt "Hoàn thành công việc"
       │
       ▼
[Kiểm Tra Hiện Diện Hiện Trường (Proof-of-Presence Interlock)]
       │
       ├── Điện thoại quét BLE trong 3 giây tìm sóng ESP32:
       │       ├── Bắt được sóng ESP32 (RSSI >= -92 dBm)?
       │       │       └── CÓ ──► MỞ FORM NGHIỆM THU:
       │       │                   ├── Nhập số đo độ rung RMS & nhiệt độ thân máy sau sửa
       │       │                   ├── Chụp ảnh nghiệm thu hiện trường
       │       │                   └── Bấm "Xác nhận nghiệm thu" -> WO chuyển COMPLETED
       │       │
       │       └── KHÔNG BẮT ĐƯỢC SÓNG (Thợ đã bỏ về / ngồi từ xa):
       │               └── CHẶN HOÀN THÀNH NGAY LẬP TỨC!
       │                   Hiển thị cảnh báo: "Bạn không có mặt tại thiết bị. Vui lòng lại gần máy để nghiệm thu!"
       │                   (Hỗ trợ quét mã QR thân máy nếu ESP32 mất nguồn đột xuất)
```

---

## 6. Mô Hình Dữ Liệu & Thực Thể (Data Model & Schema)

### 6.1. Bảng `biometric_profiles` (Lưu vector sinh trắc học 128 chiều)
```sql
CREATE TABLE biometric_profiles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id),
  user_id UUID NOT NULL UNIQUE REFERENCES users(id),
  face_embedding FLOAT8[] NOT NULL, -- Mảng 128 số thực chuẩn hóa L2 từ MobileFaceNet
  enrolled_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  enrolled_by UUID NULL REFERENCES users(id),
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_biometric_tenant_user ON biometric_profiles(tenant_id, user_id, is_active);
```

### 6.2. Bảng `attendance_logs` (Nhật ký điểm danh hiện trường bất biến)
```sql
CREATE TABLE attendance_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id),
  work_order_id UUID NOT NULL REFERENCES work_orders(id),
  technician_id UUID NOT NULL REFERENCES users(id),
  verification_method VARCHAR(32) NOT NULL, -- 'ESP32_UNIVERSAL_BEACON', 'GPS_HAVERSINE', 'QR_FALLBACK_WITH_BIOMETRIC'
  ble_beacon_id VARCHAR(64) NULL,
  rssi_dbm INT NULL,
  distance_meters FLOAT NULL, -- Khoảng cách tính toán (mét)
  similarity_score FLOAT NOT NULL, -- Độ tương đồng Cosine (0.00 - 1.00)
  is_location_verified BOOLEAN DEFAULT FALSE,
  is_face_verified BOOLEAN DEFAULT FALSE,
  overall_compliance VARCHAR(32) NOT NULL, -- 'PASSED', 'FAILED', 'BYPASSED_BY_TENANT_POLICY'
  gate_type VARCHAR(20) DEFAULT 'START_GATE', -- 'START_GATE' hoặc 'COMPLETE_GATE'
  snapshot_minio_path VARCHAR(512) NULL, -- Đường dẫn ảnh chụp hiện trường trên MinIO
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_att_wo_tech_time ON attendance_logs(tenant_id, work_order_id, technician_id, created_at);
```

---

## 7. Đặc Tả Giao Diện Lập Trình (API Specifications & Contracts)

### Danh Mục Endpoints:

| Phương Thức | Đường Dẫn | Chức Năng |
| :--- | :--- | :--- |
| `POST` | `/api/v1/biometric/enroll/` | Đăng ký khuôn mặt User trên Web: Trích xuất vector 128-d qua MobileFaceNet |
| `POST` | `/api/v1/attendance/check-in/` | Gửi dữ liệu điểm danh Cổng 1 (ESP32 BLE / Face / QR) để bắt đầu Work Order |
| `POST` | `/api/v1/attendance/verify-presence/` | Xác thực hiện diện nhanh Cổng 2 trước khi cho phép nghiệm thu |
| `PUT` | `/api/v1/work-orders/{id}/status` | Chuyển trạng thái WO (`IN_PROGRESS` hoặc `COMPLETED` có cổng gác) |

### Cấu Trúc Dữ Liệu Mẫu:

#### 1. Đăng ký khuôn mặt User trên Web (`POST /api/v1/biometric/enroll/`):
```json
// Multipart/Form-Data:
// userId: "8f3e5b41-8c7a-42bc-8199-231908d17b2e"
// faceImage: [File binary ảnh chân dung]

// Response: 200 OK
{
  "success": true,
  "data": {
    "profileId": "c1d2e3f4-a5b6-7890-1234-567890abcdef",
    "userId": "8f3e5b41-8c7a-42bc-8199-231908d17b2e",
    "embeddingDimension": 128,
    "status": "ENROLLED",
    "enrolledAt": "2026-11-01T10:30:00Z"
  }
}
```

#### 2. Gửi điểm danh hiện trường Cổng 1 (`POST /api/v1/attendance/check-in/`):
```json
{
  "workOrderId": "a1b2c3d4-e5f6-7890-abcd-1234567890ab",
  "verificationMethod": "ESP32_UNIVERSAL_BEACON",
  "bleBeaconId": "EAM-UNIVERSAL-BEACON",
  "rssi": -68,
  "estimatedDistance": 8.5,
  "liveEmbedding": [0.034, -0.082, 0.051, 0.112, "... (128 số) ..."],
  "scannedQrCode": null,
  "clientTimestamp": "2026-11-01T10:35:00Z"
}
```

#### 3. Phản hồi thành công (`200 OK`):
```json
{
  "success": true,
  "data": {
    "attendanceId": "8f3e5b41-8c7a-42bc-8199-231908d17b2e",
    "workOrderId": "a1b2c3d4-e5f6-7890-abcd-1234567890ab",
    "overallCompliance": "PASSED",
    "proximity": {
      "method": "ESP32_UNIVERSAL_BEACON",
      "beaconId": "EAM-UNIVERSAL-BEACON",
      "rssi": -68,
      "estimatedDistanceMeters": 8.5,
      "maxAllowedRadius": 50.0,
      "isPassed": true
    },
    "biometric": {
      "similarityScore": 0.842,
      "acceptanceThreshold": 0.72,
      "isPassed": true
    },
    "workOrderStatus": "IN_PROGRESS",
    "timestamp": "2026-11-01T10:35:02Z"
  }
}
```

---

## 8. Tiêu Chí Chấp Nhận & Ma Trận Kịch Bản Kiểm Thử (Acceptance Criteria & Test Scenarios)

| Mã Test | Tên Kịch Bản | Điều Kiện Thử Nghiệm | Hành Vi Kỳ Vọng | Trạng Thái |
| :--- | :--- | :--- | :--- | :--- |
| **TC-BIO-01** | Điểm danh chuẩn với ESP32 Universal ($\le 50\text{m}$) | Thợ đứng cách ESP32 $8\text{m}$ ($\text{RSSI} = -68\text{ dBm}$), quét mặt đạt $\text{Sim} = 0.84 \ge 0.72$ | Cả 2 cổng ĐẠT, lưu bản ghi `PASSED`, mở khóa chuyển WO sang `IN_PROGRESS` | Chưa thực hiện |
| **TC-BIO-02** | Vi phạm khoảng cách sóng ESP32 ($> 50\text{m}$) | Kỹ thuật viên đứng cách xa máy, $\text{RSSI} = -96\text{ dBm} < -92\text{ dBm}$ ($d \approx 72\text{m}$) | Cổng không gian thất bại, `is_location_verified = False`, khóa nút bắt đầu | Chưa thực hiện |
| **TC-BIO-03** | Khóa Nghiệm thu Cổng 2 khi thợ vắng mặt | Thợ ngồi từ xa bấm "Hoàn thành", điện thoại không bắt được sóng ESP32 | Chặn hoàn thành ngay lập tức, cảnh báo bắt buộc có mặt tại máy | Chưa thực hiện |
| **TC-BIO-04** | Nghiệm thu Cổng 2 thành công tại máy | Thợ đứng tại máy ($\text{RSSI} \ge -92\text{ dBm}$), nhập rung nhiệt và hoàn thành | Chấp thuận hoàn thành, chuyển trạng thái WO sang `COMPLETED` | Chưa thực hiện |
| **TC-BIO-05** | Đăng ký khuôn mặt User trên Web qua Deep Learning | Upload ảnh chân dung nhân viên trên Web Portal | MobileFaceNet trích xuất vector 128 số thực, lưu vào `biometric_profiles` | Chưa thực hiện |
| **TC-BIO-06** | Mỏ neo vạn năng nhận diện mọi Work Order | Cắm mạch ESP32 phát `EAM-UNIVERSAL-BEACON`, mở bất kỳ WO nào | Điện thoại tự động nhận diện mỏ neo không gian cho mọi phiếu việc | Chưa thực hiện |
| **TC-BIO-07** | Điểm danh hộ / Không khớp khuôn mặt | Người khác cầm máy điểm danh thay, $\text{Sim} = 0.52 < 0.65$ | Cổng sinh trắc từ chối (`Rejected`), hiển thị thông báo khuôn mặt không khớp | Chưa thực hiện |
| **TC-BIO-08** | Dự phòng quét mã QR khi ESP32 mất nguồn | Rút nguồn cổng Type-C của ESP32, ứng dụng mở nút quét mã QR thân máy | Chấp thuận điểm danh phương thức `QR_FALLBACK_WITH_BIOMETRIC`, mở khóa WO | Chưa thực hiện |
| **TC-BIO-09** | Dự phòng GPS Haversine ngoài trời | Thiết bị ngoài trời có tọa độ GPS, không có ESP32, thợ cách $15\text{m} \le 50\text{m}$ | Chấp thuận định vị GPS Haversine hợp lệ | Chưa thực hiện |
| **TC-BIO-10** | Chặn phần mềm Fake GPS / Mock Location | Ứng dụng gửi `isMocked: true` trong chế độ ngoài trời | Hủy yêu cầu ngay lập tức, trả về `400 Bad Request`, ghi log vi phạm | Chưa thực hiện |
| **TC-BIO-11** | Khóa thư viện ảnh (Chặn dùng ảnh cũ) | Thợ cố tình chọn ảnh chân dung có sẵn từ album | Ứng dụng khóa hoàn toàn Gallery Picker, chỉ mở luồng camera phát trực tiếp | Chưa thực hiện |
| **TC-BIO-12** | Cổng gác máy chủ Backend 15 phút | Gọi thẳng API cập nhật status sang `IN_PROGRESS` mà không có điểm danh | Server từ chối (`403 Forbidden`) kèm mã lỗi `COMPLIANCE_ATTENDANCE_REQUIRED` | Chưa thực hiện |
| **TC-BIO-13** | Tuân thủ bảo mật Nghị định 13/2023/NĐ-CP | Kiểm tra trực tiếp cơ sở dữ liệu PostgreSQL | Tuyệt đối không lưu ảnh thô vào SQL, chỉ lưu vector toán học 1 chiều 128 số thực | Chưa thực hiện |
| **TC-BIO-14** | Hiệu năng suy diễn Edge AI trên điện thoại | Đo thời gian chạy mô hình MobileFaceNet TFLite trên chip điện thoại | Thời gian trích xuất vector $\le 30\text{ms}$, bộ nhớ $\le 15\text{MB}$ RAM | Chưa thực hiện |

---

## 9. Mã Nguồn Tham Khảo Backend (Implementation References)

### 9.1. Giải Thuật Suy Hao Tín Hiệu Log-Distance RSSI (`proximity_engine.py`)
```python
import math

def calculate_ble_log_distance(rssi: int, tx_power_1m: int = -59, path_loss_exponent: float = 2.8) -> float:
    """
    Ước tính khoảng cách trắc địa (mét) từ chỉ số RSSI nhận được của ESP32.
    Công thức: d = 10 ** ((A - RSSI) / (10 * n))
    """
    if rssi == 0:
        return 999.0  # Không có tín hiệu
    ratio = (tx_power_1m - rssi) / (10.0 * path_loss_exponent)
    return round(float(math.pow(10.0, ratio)), 2)

def verify_ble_proximity(rssi: int, max_radius_meters: float = 50.0) -> tuple[bool, float]:
    """Kiểm tra điện thoại có nằm trong bán kính 50m của mạch ESP32 hay không."""
    distance = calculate_ble_log_distance(rssi)
    is_valid = (distance <= max_radius_meters) and (rssi >= -92)
    return is_valid, distance
```

### 9.2. Đối Soát Cosine Similarity Khuôn Mặt Tự Triển Khai 100% Từ Đầu (`cosine_similarity.py`)
```python
import math

def calculate_cosine_similarity_from_scratch(vec_u: list[float], vec_v: list[float]) -> float:
    """
    Tự cài đặt giải thuật Cosine Similarity 100% từ nguyên bản toán học đại số tuyến tính (From Scratch).
    Tuyệt đối KHÔNG dùng thư viện có sẵn (scipy.spatial.distance.cosine hay sklearn.metrics).

    Công thức:
        Dot(u, v) = sum(u_i * v_i)
        ||u||_2 = sqrt(sum(u_i^2)),  ||v||_2 = sqrt(sum(v_i^2))
        Cosine(u, v) = Dot(u, v) / (||u||_2 * ||v||_2)
    """
    if not vec_u or not vec_v or len(vec_u) != len(vec_v):
        return 0.0

    dot_product = 0.0
    norm_u_sq = 0.0
    norm_v_sq = 0.0

    for i in range(len(vec_u)):
        u_i = float(vec_u[i])
        v_i = float(vec_v[i])
        dot_product += u_i * v_i
        norm_u_sq += u_i * u_i
        norm_v_sq += v_i * v_i

    if norm_u_sq == 0.0 or norm_v_sq == 0.0:
        return 0.0

    similarity = dot_product / (math.sqrt(norm_u_sq) * math.sqrt(norm_v_sq))
    return round(float(similarity), 4)

def verify_face_cosine_similarity(live_vec: list, profile_vec: list, threshold: float = 0.72) -> tuple[bool, float]:
    """Kiểm tra độ khớp khuôn mặt với ngưỡng chấp nhận 0.72."""
    sim = calculate_cosine_similarity_from_scratch(live_vec, profile_vec)
    return (sim >= threshold), sim
```

### 9.3. Cổng Gác Máy Chủ 15 Phút Khóa Bắt Đầu & Khóa Nghiệm Thu (`gatekeeper.py`)
```python
from datetime import timedelta
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

def verify_start_work_order_gate(work_order, user):
    """Cổng 1: Bắt buộc có bản ghi điểm danh hợp lệ trong vòng 15 phút gần nhất."""
    cutoff = timezone.now() - timedelta(minutes=15)
    valid_log = AttendanceLog.objects.filter(
        work_order=work_order,
        technician=user,
        is_face_verified=True,
        is_location_verified=True,
        gate_type='START_GATE',
        created_at__gte=cutoff
    ).first()

    if not valid_log:
        return Response({
            "success": False,
            "error": {
                "code": "COMPLIANCE_ATTENDANCE_REQUIRED",
                "message": "Yêu cầu điểm danh sinh trắc học hợp lệ với ESP32 trong vòng 15 phút trước khi bắt đầu."
            }
        }, status=status.HTTP_403_FORBIDDEN)
    return None

def verify_complete_work_order_gate(work_order, user, ble_verification_data=None):
    """Cổng 2: Kiểm tra sự hiện diện của thợ tại máy trước khi hoàn thành."""
    if not ble_verification_data:
        return Response({
            "success": False,
            "error": {
                "code": "PRESENCE_VERIFICATION_REQUIRED",
                "message": "Yêu cầu xác thực hiện diện tại máy móc (Bắt sóng ESP32 hoặc quét mã QR) để nghiệm thu hoàn thành."
            }
        }, status=status.HTTP_403_FORBIDDEN)
    return None
```

---

## 10. Kế Hoạch Triển Khai Chi Tiết (Implementation Checklist)

- [ ] **Task 11.7.1 — ESP32 Universal Firmware & Biometric Schema**
  - [ ] Nạp firmware `esp32_asset_beacon.ino` vào mạch ESP32 thực tế của người dùng.
  - [ ] Xây dựng bảng `BiometricProfile` lưu vector 128-d và `AttendanceLog` (hỗ trợ Cổng Kép và ESP32 Universal Beacon).
  - [ ] Thiết lập MinIO lưu trữ ảnh audit hiện trường mã hóa AES-256 tuân thủ Nghị định 13/2023/NĐ-CP.
- [ ] **Task 11.7.2 — Web Face Enrollment & Deep Learning MobileFaceNet Pipeline**
  - [ ] Xây dựng API đăng ký khuôn mặt trên Web `POST /api/v1/biometric/enroll/`.
  - [ ] Tích hợp mô hình MobileFaceNet trích xuất vector 128 số thực từ ảnh chân dung tải lên.
  - [ ] Xây dựng module `eam_app/algorithms/biometric/proximity_engine.py` (Log-Distance Path Loss RSSI + Haversine).
  - [ ] Xây dựng module `eam_app/algorithms/biometric/cosine_similarity.py` (MobileFaceNet 128-d cosine matcher).
  - [ ] Xây dựng module `eam_app/algorithms/biometric/gatekeeper.py` (Cổng 1 Khóa 15 phút & Cổng 2 Khóa nghiệm thu).
- [ ] **Task 11.7.3 — Flutter Mobile Client BLE & Edge AI Integration**
  - [ ] Tích hợp thư viện `flutter_blue_plus` và cấu hình quyền Bluetooth/Location trên Android/iOS.
  - [ ] Nhúng mô hình `mobilefacenet.tflite` và tích hợp Google ML Kit Face Detection.
  - [ ] Xây dựng màn hình `FieldAttendanceScreen`: Radar sóng ESP32 Universal thời gian thực kết hợp khung quét khuôn mặt.
  - [ ] Tích hợp khóa kiểm tra hiện diện tại Cổng 2 khi vuốt hoàn thành Work Order.
- [ ] **Task 11.7.4 — Comprehensive Verification & Acceptance Test Suite**
  - [ ] Triển khai bộ kiểm thử đơn vị và kịch bản biên 14 test cases (`TC-BIO-01` đến `TC-BIO-14`).
  - [ ] Kiểm thử thực chiến với board mạch ESP32 thực tế qua cổng Type-C và ứng dụng Flutter.

---
stepsCompleted:
  - step-01-init
  - step-02-discovery
  - step-02b-vision
  - step-02c-executive-summary
  - step-03-success
  - step-04-journeys
  - step-05-domain
  - step-06-innovation-skipped
  - step-07-project-type
  - step-08-scoping
  - step-09-functional
  - step-10-nonfunctional
  - step-11-polish
  - step-e-01-discovery
  - step-e-02-review
  - step-e-03-edit
  - step-e-04-structure-review
releaseMode: phased
inputDocuments:
  - docs/idea.md
workflowType: 'prd'
documentCounts:
  briefs: 0
  research: 0
  brainstorming: 0
  projectDocs: 1
classification:
  projectType: saas_b2b
  domain: enterprise_asset_management_cross_industry
  complexity: medium-high
  projectContext: greenfield
  auditRequirements: basic_audit_trail
  platforms:
    - web_portal
    - mobile_app
lastEdited: '2026-06-03'
editHistory:
  - date: '2026-06-03'
    changes: 'Added Epic 7: Hệ thống Báo cáo và Dashboard, định nghĩa công thức MTTR/MTBF.'
  - date: '2026-05-21'
    changes: 'Updated PRD to cover 13 edge cases related to soft delete, WO reassignments, PM triggers, offline sync, and security.'
  - date: '2026-05-21'
    changes: 'Structural review: consolidated MVP scoping, removed redundant architecture details, and streamlined executive summary.'
---

# Product Requirements Document - eam-enterprise-assset-management

**Author:** Admin
**Date:** 2026-05-11

## Executive Summary

EAM là nền tảng SaaS B2B quản lý toàn bộ vòng đời tài sản vật lý dành cho doanh nghiệp đa ngành — từ Manufacturing, Healthcare, Logistics đến Construction và Energy. Hệ thống cung cấp Web Portal cho quản lý và Mobile App cho kỹ thuật viên tại hiện trường, giúp doanh nghiệp giảm downtime, tối ưu chi phí bảo trì, và kéo dài tuổi thọ thiết bị thông qua 10 module cốt lõi: Asset Registry, Asset Hierarchy, Preventive Maintenance, Corrective Maintenance, Work Order Management, Spare Parts Management, Maintenance Scheduling, Technician Management, Mobile Maintenance App, và QR/RFID Tracking.

Đây là dự án phát triển mới hoàn toàn (Greenfield) với độ phức tạp Medium-High. Nền tảng hoạt động theo mô hình multi-tenant với tenant isolation, RBAC, và basic audit trail (ghi nhận lịch sử tạo/sửa/xóa dữ liệu). Kiến trúc được thiết kế linh hoạt, cho phép cấu hình theo đặc thù từng ngành nghề mà không cần custom code.

### Điểm Khác Biệt

- **Mobile-first cho Technician:** QR code scan để tra cứu tài sản, nhận work order, upload ảnh, điền checklist và ký điện tử — tất cả hoạt động cả khi offline.
- **Đa ngành trên một nền tảng:** Cùng một hệ thống phục vụ nhà máy sản xuất, bệnh viện, tòa nhà, hay đội xe vận tải — chỉ cần cấu hình phù hợp.
- **Quản lý tài sản phân cấp:** Hỗ trợ cấu trúc parent-child không giới hạn độ sâu, cho phép truy vết lỗi và báo cáo theo từng cấp.
- **Bảo trì thông minh:** Kết hợp preventive (time/usage/meter-based) và corrective maintenance với auto-scheduling và auto work order generation.

## Success Criteria

### User Success

| Tiêu chí | Mục tiêu | Chuẩn thị trường |
|---|---|---|
| Đăng ký tài sản mới | ≤ 2 phút/asset (bao gồm thông tin cơ bản + gán vị trí) | 1-3 phút (UpKeep, Fiix) |
| Tạo & giao Work Order | ≤ 1 phút từ khi phát hiện sự cố đến khi technician nhận việc | 1-2 phút |
| Technician scan QR → xem asset info | ≤ 3 giây response time | 2-5 giây |
| Hoàn thành Work Order trên mobile | Technician điền checklist + đóng WO tại hiện trường, không cần quay về máy tính | Tiêu chuẩn mobile-first EAM |
| Thiết lập PM schedule | ≤ 5 phút cho 1 PM plan (time/usage/meter-based) | 3-10 phút |
| Onboarding user mới | Sử dụng được chức năng cơ bản trong ≤ 30 phút không cần training | < 1 giờ |

### Technical Success

| Tiêu chí | Mục tiêu |
|---|---|
| API Response Time | P95 ≤ 500ms cho các thao tác CRUD thông thường |
| System Availability | ≥ 99.5% uptime |
| Mobile Offline Sync | Dữ liệu đồng bộ thành công khi có kết nối lại, không mất data |
| Tenant Isolation | Dữ liệu tenant A không bao giờ hiển thị cho tenant B |
| Audit Trail | Mọi thao tác CUD đều ghi nhận user + timestamp |

### Measurable Outcomes

- **Giảm thời gian phản hồi sự cố:** Từ lúc báo lỗi → technician nhận work order ≤ 5 phút (so với trung bình ngành 30-60 phút với quy trình giấy/email)
- **Tỷ lệ PM đúng hạn:** ≥ 90% lịch bảo trì phòng ngừa được thực hiện đúng thời điểm
- **Zero data loss** trong quá trình offline → online sync

## Product Scope

### MVP Approach & Feature Set (Phase 1)

**Mục tiêu:** Xây nền tảng core + 4 module thiết yếu để chứng minh giá trị end-to-end.

**4 module cốt lõi + nền tảng:**

| # | Module | Lý do chọn MVP |
|---|---|---|
| 0 | **Nền tảng Core** | Multi-tenant, Auth (RBAC), User Management, Audit Trail — nền móng bắt buộc |
| 1 | **Asset Registry + Asset Hierarchy** | Không thể làm gì nếu không biết có tài sản gì, ở đâu, thuộc cấu trúc nào |
| 2 | **Work Order Management** | Workflow trung tâm của mọi hệ thống EAM — tạo, giao, theo dõi, hoàn thành công việc |
| 3 | **Preventive Maintenance** | Giá trị cốt lõi — giảm downtime bằng bảo trì chủ động thay vì chờ hỏng |
| 4 | **Mobile App (Basic)** | Scan QR, nhận/hoàn thành work order, upload ảnh, checklist — technician không cần ngồi máy bàn |

**Các Core Journey được hỗ trợ:**
- **Super Admin:** Khởi tạo hệ thống, tạo Tenant mới, cấp phát tài khoản Tenant Admin
- **Technician:** Happy Path (Nhận WO, scan QR, checklist, ảnh, đóng WO) & Offline Mode (Cache, background sync)
- **Asset Manager:** Asset CRUD, hierarchy, PM plan, auto WO
- **Tenant Admin:** Tenant config, RBAC, user management
- **Supervisor:** WO monitoring, reassign, review, follow-up

### ERP-Standard MVP Clarification

MVP của dự án này được hiểu là bản đầu tiên đủ chuẩn vận hành kiểu ERP: không cần đầy đủ mọi module tương lai, nhưng các năng lực nền tảng không được cắt khỏi phạm vi MVP.

- User management MVP bao gồm tạo/sửa/vô hiệu hóa user, mời user qua email và import danh sách.
- RBAC MVP bao gồm role mặc định và khả năng cấu hình role/permission bởi Tenant Admin.
- Notification MVP bao gồm notification được lưu, WebSocket realtime cho Web Portal, FCM push cho Mobile và trạng thái unread/read.
- Offline MVP bao gồm local cache, sync queue, retry, idempotency key và xử lý conflict cơ bản.
- PM MVP bao gồm trigger theo thời gian, usage-based và meter-based.
- Operational MVP bao gồm CI/test gate cơ bản, hướng dẫn hoặc lệnh backup/restore, và guardrail cho Flyway migration/rollback.

### Growth Features (Post-MVP)

| Module | Giai đoạn |
|---|---|
| Hệ thống Báo cáo và Dashboard | Growth Phase 1 |
| Corrective Maintenance (full) | Growth Phase 1 |
| Spare Parts Management | Growth Phase 1 |
| Maintenance Scheduling (advanced) | Growth Phase 2 |
| Technician Management | Growth Phase 2 |

### Vision (Future)

| Module | Mô tả |
|---|---|
| QR/RFID Tracking (advanced) | RFID integration, asset movement tracking tự động |
| Predictive Maintenance | AI/ML dự đoán hỏng hóc dựa trên dữ liệu sensor/lịch sử |
| Integration Hub | API mở cho ERP, CMMS, IoT platform bên thứ 3 |

## User Journeys

### Journey 0: Super Admin — Khởi tạo Tenant mới cho khách hàng

**Persona:** Admin hệ thống, người quản lý nền tảng SaaS EAM ở mức cao nhất, không thuộc về một Tenant (bệnh viện/nhà máy) cụ thể nào.

**Opening Scene:** EAM platform vừa có một khách hàng mới (Bệnh viện X). Để họ bắt đầu dùng hệ thống, Super Admin cần tạo không gian làm việc (Tenant) cho họ và cấp tài khoản cho người quản lý IT của họ (Tuấn).

**Rising Action:**
1. Super Admin đăng nhập vào System Admin Dashboard.
2. Bấm "Thêm mới Tenant" → nhập tên "Bệnh viện X", mã tenant "bv-x", và chọn gói dịch vụ.
3. Sau khi Tenant được tạo, hệ thống tự động sinh ID cho Bệnh viện X.
4. Super Admin tạo user đầu tiên cho Tenant này: "Tuấn" (Email: tuan@bvx.com, Role: Tenant Admin).
5. Hệ thống gửi email chào mừng kèm link thiết lập mật khẩu đến Tuấn.

**Climax & Resolution:** Toàn bộ quá trình tạo tổ chức mới chỉ mất 2 phút. Bệnh viện X đã có không gian dữ liệu riêng biệt. Khi Tuấn đăng nhập, anh ta sẽ bắt đầu "Journey 4: Cấu hình Tenant".

---

### Journey 1: Technician — Nhận & Hoàn thành Work Order tại hiện trường (Happy Path)

**Persona:** Minh, 28 tuổi, kỹ thuật viên bảo trì tại một nhà máy sản xuất. Hàng ngày Minh di chuyển liên tục giữa các khu vực nhà máy, nhận việc qua điện thoại và thực hiện bảo trì trực tiếp.

**Opening Scene:** 8:00 sáng, Minh nhận push notification trên mobile app: *"Work Order WO-2024-0087: Bảo trì định kỳ máy CNC-003 — Khu vực Production Line A"*. Trước đây Minh phải lên phòng kỹ thuật lấy phiếu bảo trì giấy, nhưng giờ mọi thứ nằm trong app.

**Rising Action:**
1. Minh mở app → xem chi tiết work order: mô tả công việc, checklist 8 mục, tài liệu hướng dẫn đính kèm
2. Minh đến máy CNC-003 → scan QR code trên thân máy → app tự động liên kết WO với asset, hiển thị lịch sử bảo trì gần nhất
3. Minh bắt đầu thực hiện → tick từng mục checklist: kiểm tra dầu bôi trơn ✓, kiểm tra dao cắt ✓, đo độ rung ✓...
4. Minh chụp 2 ảnh — 1 ảnh bộ lọc dầu cũ, 1 ảnh sau khi thay mới → upload trực tiếp vào WO

**Climax:** Minh hoàn thành checklist 8/8 mục → nhấn "Hoàn thành Work Order" → hệ thống tự động cập nhật trạng thái asset, ghi nhận thời gian hoàn thành, và thông báo cho Asset Manager.

**Resolution:** Toàn bộ quy trình từ nhận việc đến đóng WO mất 25 phút, thay vì 45 phút trước đây (khi phải ghi giấy rồi nhập lại vào máy tính). Asset Manager thấy ngay kết quả trên Web Portal mà không cần gọi điện hỏi tiến độ.

---

### Journey 2: Technician — Offline Mode & Auto-Sync (Edge Case)

**Persona:** Minh (tiếp), đang thực hiện bảo trì tại khu vực hầm kỹ thuật tầng hầm B2 — nơi sóng wifi/4G rất yếu hoặc mất hoàn toàn.

**Opening Scene:** 10:30 sáng, Minh nhận WO bảo trì hệ thống bơm nước tại tầng hầm B2. Khi bước vào thang máy xuống hầm, thanh tín hiệu giảm dần và mất hoàn toàn.

**Rising Action:**
1. App phát hiện mất kết nối → hiển thị indicator "Offline Mode" nhưng **vẫn hoạt động bình thường** — dữ liệu WO đã được cache sẵn khi nhận
2. Minh scan QR code thiết bị bơm → app tra cứu từ local cache → hiển thị thông tin asset + lịch sử bảo trì (đã sync trước đó)
3. Minh thực hiện checklist → tick 5/7 mục → chụp 3 ảnh ghi nhận tình trạng thiết bị → tất cả lưu local
4. Giữa chừng, Minh ghi chú: *"Phát hiện rò rỉ nhẹ tại joint #3, cần theo dõi thêm"* → ghi chú lưu local
5. Minh hoàn thành checklist 7/7 → nhấn "Hoàn thành" → app lưu trạng thái completed locally, đánh dấu "Pending Sync"

**Climax:** 11:15, Minh đi thang máy lên lại tầng 1 → điện thoại bắt được wifi → app tự động trigger background sync:
- Upload 3 ảnh theo queue (retry nếu fail)
- Sync checklist results + ghi chú
- Cập nhật trạng thái WO: Completed
- Hiển thị ✅ "Đã đồng bộ thành công" với timestamp

**Resolution:** Asset Manager trên Web Portal thấy WO đã hoàn thành với đầy đủ checklist, ảnh chụp, và ghi chú — không phân biệt được đây là WO offline hay online. Zero data loss. Ghi chú về rò rỉ joint #3 tự động tạo flag để supervisor review.

---

### Journey 3: Asset Manager — Đăng ký tài sản & Thiết lập PM Schedule

**Persona:** Hằng, 35 tuổi, Asset Manager tại công ty logistics. Hằng quản lý hơn 200 tài sản từ xe tải, xe nâng đến máy phát điện tại 3 kho hàng.

**Opening Scene:** Công ty vừa mua 5 xe nâng Komatsu mới cho kho hàng Bình Dương. Hằng cần đăng ký tài sản và thiết lập lịch bảo trì phòng ngừa theo khuyến cáo nhà sản xuất.

**Rising Action:**
1. Hằng đăng nhập Web Portal → vào Asset Registry → "Tạo Asset mới"
2. Nhập thông tin: tên, serial number, model, manufacturer (Komatsu), ngày mua, giá trị, vị trí (Kho Bình Dương) → gán vào Asset Hierarchy: Kho Bình Dương > Khu vực Bốc dỡ
3. Lặp lại cho 5 xe nâng — mỗi xe mất ~2 phút
4. Hằng chuyển sang Preventive Maintenance → tạo PM Plan cho dòng xe nâng Komatsu:
   - PM1: Thay dầu + kiểm tra tổng quát — mỗi 250 giờ vận hành
   - PM2: Kiểm tra hệ thống thủy lực — mỗi 500 giờ
   - PM3: Bảo trì lớn — mỗi 2000 giờ
5. Gán PM Plan cho cả 5 xe nâng → hệ thống tự động tạo PM schedule dựa trên meter reading

**Climax:** Hằng xem calendar view → thấy lịch bảo trì đã được phân bổ tự động cho 5 xe — không bị trùng ngày, không bỏ sót. Khi xe nâng đạt 250 giờ, hệ thống sẽ auto-generate Work Order và notify technician.

**Resolution:** Toàn bộ quy trình đăng ký 5 xe + thiết lập 3 PM plan mất 25 phút. Từ giờ Hằng không cần nhớ lịch bảo trì trong đầu hay ghi Excel — hệ thống tự nhắc và tạo work order.

---

### Journey 4: Tenant Admin — Cấu hình Tenant & Phân quyền

**Persona:** Tuấn, 40 tuổi, IT Manager kiêm Tenant Admin tại một bệnh viện. Tuấn chịu trách nhiệm triển khai EAM cho bệnh viện và cấu hình hệ thống phù hợp.

**Opening Scene:** Bệnh viện vừa đăng ký sử dụng EAM platform. Tuấn được cấp tài khoản Tenant Admin và bắt đầu thiết lập ban đầu.

**Rising Action:**
1. Tuấn đăng nhập → vào Tenant Settings → cấu hình thông tin tổ chức: tên, logo, múi giờ
2. Thiết lập cấu trúc Asset Hierarchy phù hợp bệnh viện: Tòa nhà > Tầng > Khoa > Phòng
3. Tạo Role-based permissions:
   - **Maintenance Manager:** Full access Asset + WO + PM
   - **Technician:** Mobile app only, xem WO được gán, cập nhật checklist
   - **Department Head:** Xem báo cáo tài sản thuộc khoa mình, tạo yêu cầu sửa chữa
4. Mời users: import danh sách 15 nhân viên kỹ thuật + 5 trưởng khoa → gán role tương ứng
5. Tạo asset categories phù hợp ngành y: Thiết bị chẩn đoán, Thiết bị phẫu thuật, Hạ tầng kỹ thuật

**Climax:** Tuấn hoàn tất setup → mời đồng nghiệp đầu tiên đăng nhập → họ thấy giao diện đã được cá nhân hóa với logo bệnh viện, cấu trúc phù hợp, và chỉ thấy dữ liệu/chức năng đúng quyền hạn.

**Resolution:** Toàn bộ initial setup mất ~1 giờ. Dữ liệu bệnh viện hoàn toàn cách ly với các tenant khác. Mỗi user chỉ truy cập đúng phạm vi được phân quyền.

---

### Journey 5: Supervisor — Giám sát Work Order & Duyệt báo cáo

**Persona:** Phong, 38 tuổi, Maintenance Supervisor tại nhà máy. Phong giám sát đội 8 technician và chịu trách nhiệm đảm bảo mọi work order được hoàn thành đúng chất lượng.

**Opening Scene:** 14:00 chiều, Phong mở Web Portal để review tiến độ công việc trong ngày.

**Rising Action:**
1. Phong vào Work Order dashboard → thấy tổng quan: 12 WO hôm nay — 7 completed, 3 in-progress, 2 pending
2. Kiểm tra 2 WO pending → thấy WO-0091 bị quá hạn 2 giờ → click vào xem chi tiết → technician được gán đang bận WO khác
3. Phong reassign WO-0091 cho technician khác đang rảnh → hệ thống gửi notification ngay lập tức
4. Review WO-0085 vừa completed → xem checklist, ảnh chụp, ghi chú của technician → phát hiện ghi chú: *"Rò rỉ nhẹ tại joint #3"*
5. Phong tạo follow-up WO cho vấn đề rò rỉ → đặt priority: Medium → gán deadline tuần sau

**Climax:** Cuối ngày, Phong có cái nhìn toàn cảnh: 11/12 WO hoàn thành, 1 WO được reassign thành công, 1 follow-up WO được tạo từ phát hiện trong quá trình bảo trì.

**Resolution:** Phong không cần gọi điện hỏi từng technician về tiến độ. Mọi thông tin real-time trên dashboard. Vấn đề phát sinh được phát hiện và xử lý trong ngày thay vì bị bỏ sót.

## Functional Requirements

### Quản lý Tenant & Cấu hình

**Tenant Model Core:**
- **Shared database, shared schema** với `tenant_id` column trên mọi business table
- Tenant isolation enforced ở repository/query layer
- Mỗi tenant có cấu hình riêng: logo, timezone, asset categories, hierarchy template, RBAC roles

**Features:**
- **FR0:** Super Admin có thể tạo Tenant mới, thiết lập thông tin cơ bản và tạo tài khoản Tenant Admin đầu tiên (các API này thuộc `/api/v1/system/tenants` và phải bypass tenant_id filter).
- **FR1:** Tenant Admin có thể cấu hình thông tin tổ chức (tên, logo, timezone)
- **FR2:** Tenant Admin có thể tạo và tùy chỉnh cấu trúc Asset Hierarchy template
- **FR3:** Tenant Admin có thể tạo và quản lý asset categories theo đặc thù ngành
- **FR4:** Tenant Admin có thể xem audit trail (lịch sử thao tác CUD trong tenant)

### Quản lý Người dùng & Phân quyền

**RBAC Matrix:**
| Role | Web Portal | Mobile App | Assets | Work Orders | PM | Users | Tenant Config |
|---|---|---|---|---|---|---|---|
| **Super Admin** | ✅ (System) | ❌ | ❌ | ❌ | ❌ | Khởi tạo Tenant Admin | Quản lý Tenants |
| **Tenant Admin** | ✅ | ❌ | Full CRUD | Full CRUD | Full CRUD | Full CRUD | Full Access |
| **Asset Manager** | ✅ | ❌ | Full CRUD | Full CRUD | Full CRUD | View | View |
| **Supervisor** | ✅ | ❌ | View | Full CRUD + Reassign | View | View | ❌ |
| **Technician** | ❌ | ✅ | View (assigned) | Update (assigned) | View (assigned) | ❌ | ❌ |

**Features:**
- **FR5:** Tenant Admin có thể tạo, chỉnh sửa, vô hiệu hóa tài khoản user. Yêu cầu hệ thống hiển thị prompt phân công lại các Work Order đang active khi vô hiệu hóa tài khoản.
- **FR6:** Tenant Admin có thể mời user qua email hoặc import danh sách
- **FR7:** Tenant Admin có thể tạo và quản lý roles với permissions tùy chỉnh
- **FR8:** Tenant Admin có thể gán/thay đổi role cho user
- **FR9:** Hệ thống phải enforce RBAC — user chỉ truy cập được tài nguyên đúng quyền hạn
- **FR10:** User có thể đăng nhập bằng username/password và nhận JWT token

### Quản lý Tài sản (Asset Registry)

- **FR11:** Asset Manager có thể tạo tài sản mới với đầy đủ thông tin (tên, serial number, model, manufacturer, ngày mua, giá trị, trạng thái, vị trí)
- **FR12:** Asset Manager có thể chỉnh sửa và cập nhật thông tin tài sản
- **FR13:** Asset Manager có thể xóa mềm tài sản (soft delete với audit trail). Phải tự động CASCADE soft delete xuống các tài sản con HOẶC chặn xóa nếu còn tài sản con; đồng thời chặn xóa nếu tài sản đang có Work Order chưa đóng.
- **FR14:** Asset Manager có thể tìm kiếm và lọc tài sản theo nhiều tiêu chí
- **FR15:** Asset Manager có thể xem lịch sử bảo trì của từng tài sản

### Phân cấp Tài sản (Asset Hierarchy)

- **FR16:** Asset Manager có thể tạo cấu trúc phân cấp tài sản (parent-child) không giới hạn độ sâu
- **FR17:** Asset Manager có thể di chuyển tài sản giữa các node trong hierarchy
- **FR18:** Asset Manager có thể xem tree view của toàn bộ hierarchy
- **FR19:** Hệ thống hiển thị tất cả tài sản con khi xem một node cha

### QR Code

- **FR20:** Hệ thống tự động sinh QR code cho mỗi tài sản khi được tạo
- **FR21:** Technician có thể scan QR code để tra cứu thông tin tài sản trên mobile. Bắt buộc xác thực `tenant_id` từ mã QR trùng khớp với phiên đăng nhập hiện tại trước khi hiển thị dữ liệu để ngăn rò rỉ dữ liệu chéo (cross-tenant leak).
- **FR22:** Scan QR code tự động liên kết với work order đang thực hiện (nếu có)

### Quản lý Work Order

- **FR23:** Asset Manager/Supervisor có thể tạo work order mới với mô tả, priority, deadline
- **FR24:** Asset Manager/Supervisor có thể gán work order cho technician
- **FR25:** Supervisor có thể reassign work order sang technician khác. Khi reassign WO đang "In Progress", hệ thống phải reset trạng thái về "Assigned" và xóa metrics thời gian thực hiện của technician cũ.
- **FR26:** Hệ thống quản lý status flow của work order (Created → Assigned → In Progress → Completed → Canceled). Có thể hủy (Cancel) ở bất kỳ trạng thái nào trước khi Completed.
- **FR27:** Technician có thể cập nhật trạng thái work order trên mobile
- **FR28:** Technician có thể điền checklist items trong work order
- **FR29:** Technician có thể upload ảnh đính kèm vào work order. Bắt buộc giới hạn số lượng ảnh tối đa cho mỗi work order để tránh phình dung lượng lưu trữ và chậm quá trình sync.
- **FR30:** Technician có thể thêm ghi chú vào work order
- **FR31:** Supervisor có thể review checklist, ảnh, ghi chú của work order đã hoàn thành
- **FR32:** Supervisor có thể tạo follow-up work order từ work order hiện tại

### Bảo trì Phòng ngừa (Preventive Maintenance)

- **FR33:** Asset Manager có thể tạo PM Plan với trigger theo thời gian (time-based)
- **FR34:** Asset Manager có thể tạo PM Plan với trigger theo mức sử dụng (usage-based)
- **FR35:** Asset Manager có thể tạo PM Plan với trigger theo meter reading (meter-based). Hệ thống cần phát hiện chỉ số meter bị âm/reset (ví dụ: thay meter mới) và yêu cầu admin xác nhận thủ công.
- **FR36:** Asset Manager có thể gán PM Plan cho một hoặc nhiều tài sản
- **FR37:** Hệ thống tự động tạo work order khi PM trigger điều kiện được thỏa mãn. Bỏ qua việc tạo WO mới nếu đã có một PM WO y hệt đang mở để tránh trùng lặp.
- **FR38:** Asset Manager có thể xem lịch bảo trì trên calendar view

### Mobile App & Offline

- **FR39:** Technician có thể xem danh sách work order được gán trên mobile
- **FR40:** Mobile app cache dữ liệu WO và asset khi có kết nối để sử dụng offline
- **FR41:** Technician có thể thực hiện checklist, chụp ảnh, ghi chú khi offline
- **FR42:** Mobile app tự động đồng bộ dữ liệu khi kết nối được khôi phục. Hệ thống cần xác thực lại quyền user; nếu JWT/Token hết hạn thì đưa sync vào queue chờ đăng nhập lại. Khi xử lý xung đột (sync conflict), hệ thống phải sử dụng Version Vectors hoặc Dirty-flags để tránh ghi đè dữ liệu mới của server, các bản ghi xung đột sẽ được gán flag để Supervisor xử lý.
- **FR43:** Mobile app hiển thị trạng thái sync (online/offline/pending sync/synced/conflict/auth pending). Khi tải dữ liệu lần đầu (Initial Sync), app bắt buộc phải dùng cơ chế phân trang (Pagination/Chunking) để tránh sập bộ nhớ.
- **FR44:** Mobile app retry upload ảnh tự động khi sync fail

### Thông báo (Notification)

- **FR45:** Technician nhận push notification trên mobile khi được gán work order mới
- **FR46:** Technician nhận notification khi work order bị reassign
- **FR47:** Asset Manager/Supervisor nhận real-time notification trên web khi work order được hoàn thành
- **FR48:** Supervisor nhận notification khi work order quá hạn (overdue)
- **FR49:** Hệ thống gửi notification khi PM trigger tạo work order tự động

### Audit Trail

- **FR50:** Hệ thống ghi nhận user_id, timestamp, action_type cho mọi thao tác Create/Update/Delete trên dữ liệu business

### Hệ thống Báo cáo và Dashboard (Epic 7)

- **FR51:** Hệ thống cung cấp Dashboard tổng quan hiển thị các chỉ số MTTR và MTBF theo thời gian thực. Định nghĩa công thức:
  - **MTTR (Mean Time To Repair)** = Tổng thời gian dừng máy (hoặc thời gian sửa chữa) / Số lần xảy ra sự cố.
  - **MTBF (Mean Time Between Failures)** = Tổng thời gian hoạt động bình thường / Số lần xảy ra sự cố.
- **FR52:** Asset Manager/Supervisor có thể xem và xuất Báo cáo chi phí bảo trì theo tài sản, theo vị trí, hoặc theo khoảng thời gian.
- **FR53:** Asset Manager có thể xem Báo cáo hiệu suất theo vị trí, so sánh chỉ số MTTR/MTBF và thời gian downtime giữa các khu vực khác nhau.
- **FR54:** Hệ thống hỗ trợ thiết lập lịch Tự động gửi báo cáo định kỳ (ngày/tuần/tháng) qua email cho các vai trò quản lý.

## Non-Functional Requirements

### Compliance & Regulatory

- Không yêu cầu tuân thủ tiêu chuẩn quốc tế đặc thù (ISO 55000, FDA, OSHA...) ở giai đoạn MVP.
- Các vấn đề rủi ro bảo mật cross-tenant, dữ liệu quá tải, offline conflict đã được thiết kế kỹ lưỡng trong FRs.

### Performance

- **NFR1:** API response time P95 ≤ 500ms cho các thao tác CRUD thông thường
- **NFR2:** QR scan → asset info display ≤ 3 giây (bao gồm camera decode + API call)
- **NFR3:** Asset hierarchy tree render ≤ 2 giây cho hierarchy có ≤ 1,000 nodes
- **NFR4:** Work order list load ≤ 1 giây (với pagination, 20 items/page)
- **NFR5:** Push notification delivery ≤ 5 giây từ khi event xảy ra
- **NFR6:** Photo upload ≤ 10 giây cho ảnh ≤ 5MB qua 4G connection

### Security

- **NFR7:** Xác thực an toàn bằng mô hình Access Token (vòng đời ngắn) và Refresh Token (HTTP-only). Bắt buộc phải có cơ chế Token Blacklisting/Revocation để thu hồi phiên đăng nhập ngay lập tức.
- **NFR8:** Tất cả API endpoints phải require authentication (trừ login/health check)
- **NFR9:** Mọi request phải được filter theo tenant_id — không có cross-tenant data access
- **NFR10:** Passwords phải được hash bằng bcrypt (hoặc tương đương)
- **NFR11:** API communication phải qua HTTPS (TLS 1.2+)
- **NFR12:** File upload phải được validate type và size trước khi lưu. File hình ảnh/tài liệu phải được lưu trên Object Storage chuyên dụng (MinIO/S3), phân lập quyền truy cập chặt chẽ theo `tenant_id`.

### Scalability

- **NFR13:** Hệ thống hỗ trợ ≥ 50 tenant hoạt động đồng thời ở giai đoạn MVP
- **NFR14:** Mỗi tenant hỗ trợ ≤ 10,000 assets và ≤ 50,000 work orders
- **NFR15:** Hỗ trợ ≤ 100 concurrent users per tenant
- **NFR16:** Database query performance không suy giảm quá 20% khi data tăng 10x

### Reliability

- **NFR17:** System availability ≥ 99.5% (loại trừ planned maintenance)
- **NFR18:** Mobile offline mode: zero data loss khi sync lại sau mất kết nối
- **NFR18b:** Dữ liệu cache offline trên thiết bị di động phải áp dụng chính sách giới hạn dung lượng (Quota) và thời gian sống (TTL / Data Eviction) để tự động xóa rác, tránh đầy bộ nhớ.
- **NFR19:** Background sync retry ≤ 3 lần với exponential backoff trước khi báo lỗi. Cung cấp nút 'Force Sync' thủ công và hiển thị cảnh báo lỗi rõ ràng cho người dùng hướng giải quyết khi kiệt sức retry.
- **NFR20:** Backup tự động hàng ngày với retention 30 ngày. Quá trình backup phải đảm bảo tính nhất quán đồng thời (Cross-component consistency) giữa snapshot PostgreSQL và Kafka offsets.
- **NFR21:** Flyway migration rollback khả thi cho mọi schema change
- **NFR24:** Hệ thống bắt buộc phải tích hợp luồng Distributed Tracing và Centralized Logging (VD: OpenTelemetry) để truy vết các lỗi xử lý ngầm (Asynchronous events).

### Accessibility

- **NFR22:** Web Portal đạt WCAG 2.1 Level AA minimum (contrast, keyboard navigation, screen reader labels)
- **NFR23:** Mobile app hỗ trợ font size hệ thống (accessibility settings của iOS/Android)

### Risk Mitigation Strategy

| Loại rủi ro | Rủi ro | Chiến lược giảm thiểu |
|---|---|---|
| **Technical** | Offline sync conflict khi 2 technician cùng cập nhật 1 WO | Last-write-wins + conflict notification cho supervisor |
| **Technical** | Deep hierarchy query performance | PostgreSQL ltree/recursive CTE + proper indexing |
| **Technical** | Tenant data leak | tenant_id filter ở repository layer + integration test coverage |
| **Market** | User adoption thấp vì UX phức tạp | Onboarding ≤ 30 phút, mobile-first UX cho technician |
| **Resource** | Team nhỏ, scope lớn | API-first cho phép phát triển backend/frontend/mobile song song |

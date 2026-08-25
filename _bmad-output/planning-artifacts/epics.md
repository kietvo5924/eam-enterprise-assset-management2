---
stepsCompleted:
  - step-01-validate-prerequisites
  - step-02-design-epics
  - step-03-create-stories
inputDocuments:
  - _bmad-output/planning-artifacts/prd.md
  - _bmad-output/planning-artifacts/architecture.md
  - _bmad-output/planning-artifacts/ux-design-specification.md
  - docs/idea.md
---

# eam-enterprise-assset-management - Epic Breakdown

## Tổng Quan

Tài liệu này cung cấp phân rã đầy đủ các epic và câu chuyện cho dự án eam-enterprise-assset-management, chuyển các yêu cầu từ PRD, UX Design và Architecture thành các đơn vị có thể triển khai.

## Ghi Chú Triển Khai MVP Chuẩn ERP

Mục tiêu triển khai đầu tiên là MVP đạt chuẩn ERP: dùng được end-to-end và có nền tảng đủ nghiêm túc cho vận hành thực tế. Các năng lực nền tảng như RBAC cấu hình được, audit trail, tenant isolation, invite/import user, realtime/push notification, offline sync an toàn, guardrail migration và quy trình backup/restore đều thuộc phạm vi MVP.

## Danh Mục Yêu Cầu

### Yêu Cầu Chức Năng

FR1: Tenant Admin có thể cấu hình thông tin tổ chức (tên, logo, timezone)
FR2: Tenant Admin có thể tạo và tùy chỉnh cấu trúc Asset Hierarchy template
FR3: Tenant Admin có thể tạo và quản lý asset categories theo đặc thù ngành
FR4: Tenant Admin có thể xem audit trail (lịch sử thao tác CUD trong tenant)
FR5: Tenant Admin có thể tạo, chỉnh sửa, vô hiệu hóa tài khoản user
FR6: Tenant Admin có thể mời user qua email hoặc import danh sách
FR7: Tenant Admin có thể tạo và quản lý roles với permissions tùy chỉnh
FR8: Tenant Admin có thể gán/thay đổi role cho user
FR9: Hệ thống phải enforce RBAC — user chỉ truy cập được tài nguyên đúng quyền hạn
FR10: User có thể đăng nhập bằng username/password và nhận JWT token
FR11: Asset Manager có thể tạo tài sản mới với đầy đủ thông tin (tên, serial number, model, manufacturer, ngày mua, giá trị, trạng thái, vị trí)
FR12: Asset Manager có thể chỉnh sửa và cập nhật thông tin tài sản
FR13: Asset Manager có thể xóa mềm tài sản (soft delete với audit trail)
FR14: Asset Manager có thể tìm kiếm và lọc tài sản theo nhiều tiêu chí
FR15: Asset Manager có thể xem lịch sử bảo trì của từng tài sản
FR16: Asset Manager có thể tạo cấu trúc phân cấp tài sản (parent-child) không giới hạn độ sâu
FR17: Asset Manager có thể di chuyển tài sản giữa các node trong hierarchy
FR18: Asset Manager có thể xem tree view của toàn bộ hierarchy
FR19: Hệ thống hiển thị tất cả tài sản con khi xem một node cha
FR20: Hệ thống tự động sinh QR code cho mỗi tài sản khi được tạo
FR21: Technician có thể scan QR code để tra cứu thông tin tài sản trên mobile
FR22: Scan QR code tự động liên kết với work order đang thực hiện (nếu có)
FR23: Asset Manager/Supervisor có thể tạo work order mới với mô tả, priority, deadline
FR24: Asset Manager/Supervisor có thể gán work order cho technician
FR25: Supervisor có thể reassign work order sang technician khác
FR26: Hệ thống quản lý status flow của work order (Created → Assigned → In Progress → Completed)
FR27: Technician có thể cập nhật trạng thái work order trên mobile
FR28: Technician có thể điền checklist items trong work order
FR29: Technician có thể upload ảnh đính kèm vào work order
FR30: Technician có thể thêm ghi chú vào work order
FR31: Supervisor có thể review checklist, ảnh, ghi chú của work order đã hoàn thành
FR32: Supervisor có thể tạo follow-up work order từ work order hiện tại
FR33: Asset Manager có thể tạo PM Plan với trigger theo thời gian (time-based)
FR34: Asset Manager có thể tạo PM Plan với trigger theo mức sử dụng (usage-based)
FR35: Asset Manager có thể tạo PM Plan với trigger theo meter reading (meter-based)
FR36: Asset Manager có thể gán PM Plan cho một hoặc nhiều tài sản
FR37: Hệ thống tự động tạo work order khi PM trigger điều kiện được thỏa mãn
FR38: Asset Manager có thể xem lịch bảo trì trên calendar view
FR39: Technician có thể xem danh sách work order được gán trên mobile
FR40: Mobile app cache dữ liệu WO và asset khi có kết nối để sử dụng offline
FR41: Technician có thể thực hiện checklist, chụp ảnh, ghi chú khi offline
FR42: Mobile app tự động đồng bộ dữ liệu khi kết nối được khôi phục (background sync)
FR43: Mobile app hiển thị trạng thái sync (online/offline/pending sync/synced)
FR44: Mobile app retry upload ảnh tự động khi sync fail
FR45: Technician nhận push notification trên mobile khi được gán work order mới
FR46: Technician nhận notification khi work order bị reassign
FR47: Asset Manager/Supervisor nhận real-time notification trên web khi work order được hoàn thành
FR48: Supervisor nhận notification khi work order quá hạn (overdue)
FR49: Hệ thống gửi notification khi PM trigger tạo work order tự động
FR50: Hệ thống ghi nhận user_id, timestamp, action_type cho mọi thao tác Create/Update/Delete trên dữ liệu business

### Yêu Cầu Phi Chức Năng

NFR1: API response time P95 ≤ 500ms cho các thao tác CRUD thông thường
NFR2: QR scan → asset info display ≤ 3 giây (bao gồm camera decode + API call)
NFR3: Asset hierarchy tree render ≤ 2 giây cho hierarchy có ≤ 1,000 nodes
NFR4: Work order list load ≤ 1 giây (với pagination, 20 items/page)
NFR5: Push notification delivery ≤ 5 giây từ khi event xảy ra
NFR6: Photo upload ≤ 10 giây cho ảnh ≤ 5MB qua 4G connection
NFR7: Xác thực qua JWT token với thời gian hết hạn có thể cấu hình
NFR8: Tất cả API endpoints phải yêu cầu xác thực (trừ login/health check)
NFR9: Mọi request phải được filter theo tenant_id — không có cross-tenant data access
NFR10: Passwords phải được hash bằng bcrypt (hoặc tương đương)
NFR11: API communication phải qua HTTPS (TLS 1.2+)
NFR12: File upload phải được validate type và size trước khi lưu
NFR13: Hệ thống hỗ trợ ≥ 50 tenant hoạt động đồng thời ở giai đoạn MVP
NFR14: Mỗi tenant hỗ trợ ≤ 10,000 assets và ≤ 50,000 work orders
NFR15: Hỗ trợ ≤ 100 concurrent users per tenant
NFR16: Database query performance không suy giảm quá 20% khi data tăng 10x
NFR17: System availability ≥ 99.5% (loại trừ planned maintenance)
NFR18: Mobile offline mode: zero data loss khi sync lại sau mất kết nối
NFR19: Background sync retry ≤ 3 lần với exponential backoff trước khi báo lỗi
NFR20: Database backup tự động hàng ngày với retention 30 ngày
NFR21: Flyway migration rollback khả thi cho mọi schema change
NFR22: Web Portal đạt WCAG 2.1 Level A minimum (contrast, keyboard navigation, screen reader labels)
NFR23: Mobile app hỗ trợ font size hệ thống (accessibility settings của iOS/Android)

### Yêu Cầu Bổ Sung

- Starter Template cho Web Portal (Vite + React-TS), Backend API (Spring Boot 3.x, Java 17, Maven), Mobile App (Flutter). Việc khởi tạo này sẽ là công việc của Epic 1 Câu chuyện 1.
- Database: PostgreSQL kết hợp với Flyway; Sử dụng `ltree` hoặc Recursive CTE cho phân cấp.
- Mobile Database: Sử dụng Drift (trên nền SQLite) hỗ trợ Offline Sync Engine.
- Xác thực/Bảo mật: Phân lập dữ liệu (Tenant Isolation) bắt buộc tại tầng Repository/Query Layer.
- Architecture / Backend: 3-Layer Architecture (Controller-Service-Repository), Spring Cache cho phân cấp, Kafka cho Messaging. Không dùng Redis. Phải chuẩn hoá định dạng API JSON Response Wrapper.
- Client Framework: Zustand cho trạng thái Web.
- Infrastructure: Chạy trên Docker và cấu hình bằng Docker Compose.

### Yêu Cầu UX Design

UX-DR1: Thiết lập hệ thống thiết kế màu sắc (Primary #1677FF, Success #52C41A, Warning #FAAD14, Error #F5222D).
UX-DR2: Sử dụng font chữ Inter làm chuẩn và hệ thống typography.
UX-DR3: Khoảng cách thống nhất sử dụng lưới (Grid) 8px, với các quy chuẩn layout Web (mật độ cao) và Mobile (vùng chạm lớn).
UX-DR4: Áp dụng hướng thiết kế Hybrid (Modernized High-Density) cho Web với Tailwind CSS + Ant Design `size="middle"`.
UX-DR5: Xây dựng UI Component `SwipeableChecklistTile` trên Mobile, hỗ trợ thao tác vuốt hoàn thành và rung Haptic feedback.
UX-DR6: Xây dựng UI Component `SplitPaneAssetExplorer` trên Web Portal (Master-Detail phân chia 30% - 70%).
UX-DR7: Xây dựng UI Component `OfflineSyncIndicator` dùng để báo cáo tình trạng đồng bộ ngầm mà không hiển thị bảng lỗi (Modal).
UX-DR8: Hệ thống nút bấm theo mức độ ưu tiên: luôn chỉ có duy nhất một nút Primary trên form.
UX-DR9: Chuẩn hoá Feedback UI (Toast cho thành công, Dialog/Modal cho lỗi nghiêm trọng).
UX-DR10: Form Validation nội bộ (Inline validation ngay trên trường nhập liệu - onBlur).
UX-DR11: Pattern Điều hướng: Collapsible Sidebar + Breadcrumbs trên Web, Bottom Navigation Bar trên Mobile (nút Scan ở chính giữa lồi lên).
UX-DR12: Chiến lược Breakpoint/Responsive cho hệ thống Web Portal (từ Desktop `md` trở lên) và tiêu chuẩn Mobile Touch Area (tối thiểu 48x48px).

### Bản Đồ Bao Phủ FR

- **FR0, FR1, FR4-10, FR50:** Epic 1 - Thiết lập tổ chức, Auth, RBAC & Audit.
- **FR2-3, FR11-20:** Epic 2 - Quản lý cấu trúc, danh mục tài sản và sinh QR code.
- **FR23-32:** Epic 3 - Quản lý vòng đời Work Order từ lúc tạo đến lúc đóng.
- **FR21-22, FR39-44:** Epic 4 - Mobile App: Quét mã QR, Offline mode & Sync.
- **FR33-38:** Epic 5 - Thiết lập PM Plan và Auto-scheduling WO.
- **FR45-49:** Epic 6 - Hệ thống Notifications cho các luồng sự kiện.

## Danh Sách Epic

### Epic 1: Nền Tảng Hệ Thống & Tiếp Nhận Người Dùng
Thiết lập khung dự án, kiến trúc multi-tenant, xác thực, RBAC cấu hình được, onboarding user, audit trail và guardrail vận hành cơ bản.
**FR bao phủ:** FR0, FR1, FR4, FR5, FR6, FR7, FR8, FR9, FR10, FR50

### Epic 2: Cơ Sở Dữ Liệu Tri Thức Tài Sản
Cho phép Asset Manager xây dựng cơ sở dữ liệu phân cấp về tài sản, danh mục, QR code, lịch sử bảo trì và thao tác cập nhật/xóa mềm có audit.
**FR bao phủ:** FR2, FR3, FR11, FR12, FR13, FR14, FR15, FR16, FR17, FR18, FR19, FR20

### Epic 3: Vận Hành Bảo Trì Cốt Lõi
Cung cấp quy trình tạo, phân công, thực hiện, hoàn thành, review và follow-up Work Order với checklist, ảnh, ghi chú và status flow chuẩn.
**FR bao phủ:** FR23, FR24, FR25, FR26, FR27, FR28, FR29, FR30, FR31, FR32

### Epic 4: Trải Nghiệm Di Động Cho Kỹ Thuật Viên Hiện Trường
Trang bị cho Kỹ thuật viên ứng dụng Mobile "Scan-to-Work", có cache offline tin cậy, sync queue, retry, idempotency và xử lý conflict cơ bản.
**FR bao phủ:** FR21, FR22, FR39, FR40, FR41, FR42, FR43, FR44

### Epic 5: Tự Động Hóa Bảo Trì Phòng Ngừa
Cho phép lập PM Plan theo thời gian, usage và meter reading, gán cho tài sản, tự động sinh Work Order và xem lịch bảo trì.
**FR bao phủ:** FR33, FR34, FR35, FR36, FR37, FR38

### Epic 6: Truyền Thông & Thông Báo Thời Gian Thực
Cung cấp notification engine theo tenant, gồm persisted notification, WebSocket cho Web Portal, FCM push cho Mobile, unread/read state và cảnh báo overdue/PM.
**FR bao phủ:** FR45, FR46, FR47, FR48, FR49

## Epic 1: Nền Tảng Hệ Thống & Tiếp Nhận Người Dùng

### Câu chuyện 1.1: Khởi Tạo Dự Án & Hạ Tầng
Là Technical Lead,
Tôi muốn khởi tạo Web, Backend, Mobile, Docker Compose, PostgreSQL, Kafka và Flyway,
Để đội phát triển có baseline kỹ thuật nhất quán theo chuẩn ERP.

**Tiêu chí chấp nhận:**

**Bối cảnh** repository ban đầu còn trống,
**Khi** chạy các lệnh khởi tạo starter,
**Thì** Web Portal, Backend API và Mobile App được tạo theo cấu trúc thư mục đã tài liệu hóa.

**Bối cảnh** Docker Compose được khởi động,
**Khi** các service boot thành công,
**Thì** PostgreSQL, Kafka, MinIO (Object Storage), OpenTelemetry (Observability) và Backend health check sẵn sàng, đồng thời Flyway migration chạy thành công.

**Bối cảnh** CI/test gate được kích hoạt,
**Khi** code được push,
**Thì** backend compile/tests, web build/tests và mobile analysis/tests được chạy hoặc được tài liệu hóa là required checks.

### Câu chuyện 1.2: Xác Thực Cốt Lõi & Cách Ly Tenant
Là Backend Developer,
Tôi muốn xác thực JWT và lọc tenant được enforce ở tầng API/repository,
Để user chỉ truy cập được dữ liệu thuộc tenant của mình (FR10, NFR8, NFR9).

**Tiêu chí chấp nhận:**

**Bối cảnh** request không có Access Token hợp lệ (hoặc Refresh Token đã bị thu hồi/hết hạn),
**Khi** request gọi protected API,
**Thì** Backend trả về 401 Unauthorized.

**Bối cảnh** Access Token hợp lệ có tenant_id,
**Khi** repository query dữ liệu nghiệp vụ,
**Thì** tenant_id được tự động enforce và dữ liệu cross-tenant không được trả về.

**Bối cảnh** Kafka consumer hoặc Background Job xử lý event bất đồng bộ,
**Khi** thực thi query tới database,
**Thì** `tenant_id` phải được trích xuất từ Kafka Message Headers để thực thi Data Isolation (do không có HTTP context).

### Câu chuyện 1.3: Cấu Hình Tổ Chức Cho Tenant Admin
Là Tenant Admin,
Tôi muốn cấu hình tên tổ chức, logo và timezone,
Để hệ thống phản ánh đúng cấu hình của tổ chức tôi (FR1).

**Tiêu chí chấp nhận:**

**Bối cảnh** Tenant Admin mở Organization Settings,
**Khi** dữ liệu hợp lệ được lưu,
**Thì** cấu hình được persist và hiển thị trong shell của Web Portal.

**Bối cảnh** timezone đã được cấu hình,
**Khi** timestamp nghiệp vụ được hiển thị,
**Thì** UI render theo timezone của tenant trong khi dữ liệu gốc vẫn lưu theo UTC.

### Câu chuyện 1.4: Quản Lý Vai Trò & Quyền (RBAC)
Là Tenant Admin,
Tôi muốn tạo và quản lý role với permission cụ thể,
Để kiểm soát chính xác ai được truy cập module nào trong tenant (FR7, FR8, FR9).

**Tiêu chí chấp nhận:**

**Bối cảnh** màn hình Role Management,
**Khi** Admin tạo role và cấp permission,
**Thì** role và permission mapping được lưu.

**Bối cảnh** một role được cập nhật,
**Khi** user thuộc role đó gửi request tiếp theo,
**Thì** permission mới được enforce.

**Bối cảnh** user không có permission cho một API action,
**Khi** user gọi API đó,
**Thì** Backend trả về 403 Forbidden.

### Câu chuyện 1.5: Quản Lý Người Dùng, Mời Tham Gia & Import
Là Tenant Admin,
Tôi muốn tạo, chỉnh sửa, vô hiệu hóa, mời, import và gán role cho user,
Để đội ngũ được onboarding an toàn (FR5, FR6, FR8, FR10).

**Tiêu chí chấp nhận:**

**Bối cảnh** Admin tạo user kèm mật khẩu,
**Khi** user được lưu,
**Thì** mật khẩu được hash bằng bcrypt trước khi persist.

**Bối cảnh** Admin gửi invite tới email hợp lệ,
**Khi** invite được chấp nhận,
**Thì** user có thể đặt mật khẩu và đăng nhập để nhận JWT.

**Bối cảnh** Admin upload file CSV danh sách user,
**Khi** import chạy,
**Thì** user hợp lệ được tạo trong tenant hiện tại và các dòng trùng/không hợp lệ được báo cáo.

**Bối cảnh** Admin vô hiệu hóa một user,
**Khi** user đã bị vô hiệu hóa thử đăng nhập mới,
**Thì** truy cập bị từ chối.

### Câu chuyện 1.6: Nhật Ký Audit Hệ Thống
Là Tenant Admin,
Tôi muốn xem audit trail cho các thao tác Create/Update/Delete trên dữ liệu nghiệp vụ,
Để đảm bảo khả năng truy vết trách nhiệm (FR4, FR50).

**Tiêu chí chấp nhận:**

**Bối cảnh** một thao tác CUD thành công,
**Khi** transaction commit,
**Thì** audit log ghi user_id, tenant_id, timestamp, action_type, entity_type và entity_id.

**Bối cảnh** Admin mở Audit Log,
**Khi** áp dụng filter,
**Thì** kết quả có thể lọc theo user, action, entity và khoảng ngày.

### Câu chuyện 1.7: Backup, Restore & An Toàn Migration
Là Technical Lead,
Tôi muốn có backup/restore cơ bản và guardrail cho migration,
Để thay đổi schema và dữ liệu đủ an toàn cho vận hành ERP MVP (NFR20, NFR21).

**Tiêu chí chấp nhận:**

**Bối cảnh** quy trình backup được chạy cho toàn hệ thống,
**Khi** tiến hành snapshot,
**Thì** dữ liệu PostgreSQL, Local DB và Kafka offsets phải được cấu hình đồng bộ nhất quán (Cross-component consistency) để tránh hỏng state khi restore.

**Bối cảnh** database đang chạy,
**Khi** quy trình backup được thực thi,
**Thì** tạo ra bản backup PostgreSQL có timestamp và tài liệu hóa hướng dẫn retention.

**Bối cảnh** bản backup tồn tại,
**Khi** restore được test trong môi trường non-production,
**Thì** dữ liệu được khôi phục và health check pass.

**Bối cảnh** một Flyway migration được thêm,
**Khi** CI/test gate chạy,
**Thì** migration validation và hướng dẫn rollback được kiểm tra trước release.

### Câu chuyện 1.8: System Administration & Tenant Onboarding
Là Super Admin,
Tôi muốn khởi tạo và quản lý các Tenant (tổ chức) trên nền tảng,
Để onboard khách hàng mới và cấp phát tài khoản Tenant Admin đầu tiên (FR0).

**Tiêu chí chấp nhận:**

**Bối cảnh** hệ thống vừa được deploy,
**Khi** chạy script seed dữ liệu,
**Thì** một tài khoản Super Admin mặc định được tạo.

**Bối cảnh** Super Admin đăng nhập vào System Dashboard,
**Khi** submit form tạo mới Tenant với Tên, Mã Tenant và Gói dịch vụ,
**Thì** record Tenant được sinh ra trong database và cấp phát ID.

**Bối cảnh** Tenant mới đã được tạo,
**Khi** Super Admin tạo user đầu tiên cho Tenant đó,
**Thì** user được gán quyền Tenant Admin và hệ thống gửi email mời tham gia thiết lập mật khẩu.

**Bối cảnh** gọi API thuộc namespace `/api/v1/system/tenants`,
**Khi** API được kích hoạt,
**Thì** nó yêu cầu quyền `SUPER_ADMIN` và bỏ qua filter `tenant_id` của Hibernate.

## Epic 2: Cơ Sở Dữ Liệu Tri Thức Tài Sản

### Câu chuyện 2.1: Danh Mục Tài Sản & Template Phân Cấp
Là Tenant Admin,
Tôi muốn tạo asset category và hierarchy template,
Để cấu trúc tài sản phù hợp với đặc thù nghiệp vụ của tổ chức (FR2, FR3).

**Tiêu chí chấp nhận:**

**Bối cảnh** Admin tạo một category,
**Khi** các trường bắt buộc hợp lệ,
**Thì** category được lưu trong tenant hiện tại.

**Bối cảnh** Admin cấu hình hierarchy template,
**Khi** template được lưu,
**Thì** Asset Manager có thể dùng template đó khi tổ chức cây tài sản.

### Câu chuyện 2.2: CRUD Tài Sản Kèm QR Code
Là Asset Manager,
Tôi muốn tạo, chỉnh sửa và soft-delete tài sản với đầy đủ metadata và QR code,
Để mỗi tài sản vật lý được theo dõi chính xác (FR11, FR12, FR13, FR20).

**Tiêu chí chấp nhận:**

**Bối cảnh** dữ liệu tài sản hợp lệ,
**Khi** Asset Manager tạo tài sản,
**Thì** tài sản được lưu và QR code được sinh ra.

**Bối cảnh** tài sản đã tồn tại,
**Khi** metadata được chỉnh sửa,
**Thì** thay đổi được persist và audit trail được ghi nhận.

**Bối cảnh** một tài sản bị soft-delete,
**Khi** danh sách được query theo cách thông thường,
**Thì** tài sản đã xóa được ẩn nhưng lịch sử vẫn còn khả dụng.

### Câu chuyện 2.3: Tìm Kiếm, Lọc & Tree View Tài Sản
Là Asset Manager,
Tôi muốn tìm kiếm, lọc và duyệt tài sản theo dạng cây,
Để nhanh chóng tìm tài sản và kiểm tra cấu trúc phân cấp (FR14, FR16, FR18, FR19, NFR3).

**Tiêu chí chấp nhận:**

**Bối cảnh** tài sản tồn tại ở nhiều node trong hierarchy,
**Khi** filter được áp dụng,
**Thì** các tài sản phù hợp được trả về kèm pagination.

**Bối cảnh** một hierarchy node được mở,
**Khi** dữ liệu con được yêu cầu,
**Thì** node con và tài sản liên quan được hiển thị trong performance target.

### Câu chuyện 2.4: Di Chuyển Tài Sản & Lịch Sử Bảo Trì
Là Asset Manager,
Tôi muốn di chuyển tài sản giữa các node hierarchy và xem lịch sử bảo trì,
Để vị trí tài sản và ngữ cảnh bảo trì luôn chính xác (FR15, FR17).

**Tiêu chí chấp nhận:**

**Bối cảnh** tài sản có parent node,
**Khi** Manager di chuyển tài sản sang node hợp lệ khác,
**Thì** hierarchy path được cập nhật và audit trail được ghi nhận.

**Bối cảnh** tài sản có Work Order đã hoàn thành,
**Khi** Manager mở lịch sử bảo trì,
**Thì** các WO đã hoàn thành được hiển thị theo thứ tự thời gian.

## Epic 3: Vận Hành Bảo Trì Cốt Lõi

### Câu chuyện 3.1: Tạo Work Order
Là Asset Manager/Supervisor,
Tôi muốn tạo Work Order với tài sản, mô tả, priority và deadline,
Để công việc bảo trì được ghi nhận chính thức (FR23).

**Tiêu chí chấp nhận:**

**Bối cảnh** các trường bắt buộc của WO hợp lệ,
**Khi** form được submit,
**Thì** Work Order được tạo ở trạng thái Created.

**Bối cảnh** deadline bị thiếu hoặc không hợp lệ,
**Khi** form được submit,
**Thì** lỗi validation được hiển thị inline.

### Câu chuyện 3.2: Phân Công & Phân Công Lại
Là Supervisor,
Tôi muốn assign và reassign Work Order cho Technician,
Để công việc được chuyển tới đúng người phụ trách (FR24, FR25).

**Tiêu chí chấp nhận:**

**Bối cảnh** WO đang ở trạng thái Created,
**Khi** Supervisor assign Technician,
**Thì** trạng thái chuyển thành Assigned và assignee được ghi nhận.

**Bối cảnh** WO đã được assign,
**Khi** Supervisor reassign,
**Thì** assignee mới được ghi nhận và notification event được phát ra.

### Câu chuyện 3.3: Luồng Trạng Thái Của Work Order
Là Technician,
Tôi muốn cập nhật trạng thái Work Order theo flow được phép,
Để tiến độ được kiểm soát và hiển thị rõ ràng (FR26, FR27).

**Tiêu chí chấp nhận:**

**Bối cảnh** WO được assign cho tôi,
**Khi** tôi bắt đầu thực hiện,
**Thì** trạng thái chuyển thành In Progress.

**Bối cảnh** các rule bắt buộc về checklist/photo đã thỏa mãn,
**Khi** tôi hoàn thành WO,
**Thì** trạng thái chuyển thành Completed.

**Bối cảnh** request chuyển trạng thái không hợp lệ,
**Khi** Backend validate,
**Thì** request bị từ chối.

### Câu chuyện 3.4: Checklist, Ảnh & Ghi Chú
Là Technician,
Tôi muốn hoàn thành checklist, upload ảnh và thêm ghi chú,
Để bằng chứng công việc được ghi nhận (FR28, FR29, FR30, NFR12).

**Tiêu chí chấp nhận:**

**Bối cảnh** checklist tồn tại,
**Khi** Technician đánh dấu item,
**Thì** trạng thái item được lưu.

**Bối cảnh** Technician upload ảnh,
**Khi** validation thành công,
**Thì** file được upload an toàn lên Object Storage (MinIO/S3) có phân lập quyền truy cập theo tenant, đồng thời từ chối các file sai định dạng/dung lượng.

**Bối cảnh** Technician thêm ghi chú,
**Khi** WO được lưu,
**Thì** ghi chú hiển thị cho Supervisor.

### Câu chuyện 3.5: Supervisor Review & Follow-up
Là Supervisor,
Tôi muốn review công việc đã hoàn thành và tạo follow-up Work Order,
Để các vấn đề phát sinh chưa xử lý không bị bỏ sót (FR31, FR32).

**Tiêu chí chấp nhận:**

**Bối cảnh** WO đã Completed,
**Khi** Supervisor mở chi tiết,
**Thì** checklist, ảnh và ghi chú được hiển thị.

**Bối cảnh** cần công việc follow-up,
**Khi** Supervisor tạo follow-up WO,
**Thì** WO mới tham chiếu tới WO gốc.

## Epic 4: Trải Nghiệm Di Động Cho Kỹ Thuật Viên Hiện Trường

### Câu chuyện 4.1: Quét QR & Tra Cứu Thông Tin Tài Sản
Là Technician,
Tôi muốn quét QR code để xem thông tin tài sản và Work Order liên quan được giao,
Để không phải tìm kiếm thủ công (FR21, FR22, FR39, NFR2).

**Tiêu chí chấp nhận:**

**Bối cảnh** QR code hợp lệ được quét,
**Khi** dữ liệu tài sản có sẵn,
**Thì** Mobile hiển thị chi tiết tài sản trong thời gian mục tiêu.

**Bối cảnh** tài sản có WO được assign cho Technician,
**Khi** quét QR hoàn tất,
**Thì** Mobile cho phép điều hướng trực tiếp tới chi tiết WO.

### Câu chuyện 4.2: Cache Dữ Liệu Cục Bộ
Là Technician,
Tôi muốn Work Order được giao và tài sản liên quan được cache cục bộ,
Để có thể làm việc khi không có kết nối mạng (FR40).

**Tiêu chí chấp nhận:**

**Bối cảnh** ứng dụng cần tải danh mục tài sản lớn lần đầu (First-load),
**Khi** thực hiện initial sync qua mạng yếu,
**Thì** dữ liệu phải được phân trang (Pagination/Chunking) để tránh quá tải bộ nhớ và timeout.

**Bối cảnh** thiết bị đang online,
**Khi** dữ liệu được giao được tải về,
**Thì** Work Order và tài sản liên quan được lưu trong Drift local database.

**Bối cảnh** dữ liệu lưu trữ local (Drift DB) ngày càng tăng,
**Khi** chạm giới hạn quota hoặc các Work Order đã đóng quá 7 ngày,
**Thì** chính sách Data Eviction (TTL) tự động xóa dữ liệu cũ để giải phóng dung lượng thiết bị.

**Bối cảnh** thiết bị đang offline,
**Khi** Technician mở công việc được giao,
**Thì** dữ liệu đã cache vẫn khả dụng.

### Câu chuyện 4.3: Thực Hiện Offline & Trạng Thái Đồng Bộ
Là Technician,
Tôi muốn hoàn thành checklist, ảnh và ghi chú khi offline với trạng thái sync rõ ràng,
Để công việc hiện trường không bị mất dữ liệu (FR41, FR43, UX-DR7, NFR18).

**Tiêu chí chấp nhận:**

**Bối cảnh** thiết bị đang offline,
**Khi** Technician lưu dữ liệu thực hiện công việc,
**Thì** app lưu dữ liệu vào Sync Queue.

**Bối cảnh** có dữ liệu đang chờ sync,
**Khi** app render trạng thái toàn cục,
**Thì** OfflineSyncIndicator hiển thị trạng thái online/offline/pending/synced.

### Câu chuyện 4.4: Đồng Bộ Nền, Retry & An Toàn Conflict
Là Technician,
Tôi muốn app tự động sync dữ liệu offline, retry ảnh upload lỗi và chống gửi trùng,
Để công việc hiện trường được bảo toàn khi có mạng trở lại (FR42, FR44, NFR18, NFR19).

**Tiêu chí chấp nhận:**

**Bối cảnh** có bản ghi pending,
**Khi** thiết bị kết nối mạng trở lại,
**Thì** Sync Engine tự động đẩy dữ liệu lên Backend.

**Bối cảnh** upload ảnh thất bại,
**Khi** retry policy chạy,
**Thì** upload được retry tối đa 3 lần với exponential backoff.

**Bối cảnh** cùng một thao tác offline bị gửi lên hai lần,
**Khi** Backend nhận cùng idempotency key,
**Thì** thao tác chỉ được xử lý một lần.

**Bối cảnh** dữ liệu trên server đã thay đổi trong lúc Technician offline,
**Khi** phát hiện sync conflict dựa trên Version Vectors hoặc Dirty-flags (tuyệt đối không dùng last-write-wins),
**Thì** thao tác được đưa vào trạng thái conflict để Supervisor rà soát, không tự ý ghi đè làm hỏng dữ liệu gốc.

## Epic 5: Tự Động Hóa Bảo Trì Phòng Ngừa

### Câu chuyện 5.1: Tạo PM Plan
Là Asset Manager,
Tôi muốn tạo PM Plan với trigger theo thời gian, usage-based và meter-based,
Để bảo trì bám theo khuyến nghị nhà sản xuất và điều kiện vận hành thực tế (FR33, FR34, FR35).

**Tiêu chí chấp nhận:**

**Bối cảnh** Manager chọn trigger Time-based,
**Khi** chu kỳ như mỗi 30 ngày được lưu,
**Thì** PM Plan lưu cấu hình lịch.

**Bối cảnh** Manager chọn trigger Usage-based,
**Khi** ngưỡng usage được lưu,
**Thì** PM Plan lưu cấu hình usage trigger.

**Bối cảnh** Manager chọn trigger Meter-based,
**Khi** ngưỡng meter được lưu,
**Thì** PM Plan lưu cấu hình meter trigger.

### Câu chuyện 5.2: Gán PM Plan Cho Tài Sản
Là Asset Manager,
Tôi muốn gán PM Plan cho một hoặc nhiều tài sản,
Để quy tắc bảo trì được áp dụng nhất quán (FR36).

**Tiêu chí chấp nhận:**

**Bối cảnh** PM Plan tồn tại,
**Khi** Manager gán plan cho các tài sản được chọn,
**Thì** assignment record được tạo cho từng tài sản.

**Bối cảnh** plan đã được gán,
**Khi** next trigger được tính toán,
**Thì** baseline value được tính từ thời điểm assignment.

### Câu chuyện 5.3: Tự Động Sinh Work Order
Là Asset Manager,
Tôi muốn hệ thống tự động tạo Work Order khi PM trigger thỏa điều kiện,
Để kế hoạch bảo trì không bị bỏ sót (FR37, FR49).

**Tiêu chí chấp nhận:**

**Bối cảnh** điều kiện PM trigger được thỏa mãn,
**Khi** scheduler đánh giá các plan,
**Thì** Backend phát event `maintenance.triggered` qua Kafka.

**Bối cảnh** Work Order module consume event,
**Khi** chưa có WO trùng cho cùng trigger window,
**Thì** Work Order được tạo và notification event được phát ra.

### Câu chuyện 5.4: Calendar View Lịch Bảo Trì
Là Asset Manager,
Tôi muốn xem lịch bảo trì trên calendar,
Để có thể lập kế hoạch workload (FR38).

**Tiêu chí chấp nhận:**

**Bối cảnh** PM Plan và Work Order đã sinh tồn tại,
**Khi** Manager mở calendar view,
**Thì** các item theo lịch được hiển thị theo ngày kèm status và ngữ cảnh tài sản.

**Bối cảnh** filter được áp dụng,
**Khi** Manager lọc theo asset/category/status,
**Thì** calendar cập nhật tương ứng.

## Epic 6: Truyền Thông & Thông Báo Thời Gian Thực

### Câu chuyện 6.1: Notification Engine Thời Gian Thực
Là Backend Developer,
Tôi muốn domain event tạo persisted notification và gửi qua WebSocket/FCM,
Để hành vi thông báo đáng tin cậy và được scoped theo tenant (FR45, FR47, FR48, FR49, NFR5).

**Tiêu chí chấp nhận:**

**Bối cảnh** các event như `work_order.assigned`, `work_order.completed`, `work_order.overdue` hoặc `maintenance.triggered`,
**Khi** Backend consume event,
**Thì** hệ thống tạo notification record cho user/role liên quan trong cùng tenant.

**Bối cảnh** recipient đang kết nối Web Portal,
**Khi** notification được tạo,
**Thì** Backend gửi notification qua giao thức STOMP over WebSocket với cơ chế quản lý lifecycle session chặt chẽ trong thời gian mục tiêu.

**Bối cảnh** recipient có mobile push token đã đăng ký,
**Khi** notification được tạo,
**Thì** Backend gửi FCM push và lưu delivery status.

**Bối cảnh** user đọc notification,
**Khi** thao tác read thành công,
**Thì** unread count và read timestamp được cập nhật.

### Câu chuyện 6.2: Push Notification Cho Technician
Là Technician,
Tôi muốn nhận mobile push notification khi công việc được assign hoặc reassign cho tôi,
Để biết nhanh khi có công việc mới (FR45, FR46).

**Tiêu chí chấp nhận:**

**Bối cảnh** Technician đã đăng nhập Mobile App và cấp quyền notification,
**Khi** Supervisor assign Work Order mới,
**Thì** Technician nhận FCM push notification.

**Bối cảnh** Work Order được reassign,
**Khi** thao tác reassign thành công,
**Thì** assignee cũ và assignee mới nhận notification phù hợp.

**Bối cảnh** Technician chạm vào notification,
**Khi** Mobile App mở,
**Thì** app điều hướng tới chi tiết Work Order liên quan.

### Câu chuyện 6.3: Web Notification Cho Supervisor
Là Supervisor/Asset Manager,
Tôi muốn nhận realtime Web notification khi Work Order hoàn thành, quá hạn hoặc được tạo bởi PM trigger,
Để có thể phản ứng nhanh (FR47, FR48, FR49).

**Tiêu chí chấp nhận:**

**Bối cảnh** Supervisor đang kết nối Web Portal,
**Khi** Technician hoàn thành Work Order,
**Thì** Web Portal nhận WebSocket notification và cập nhật badge.

**Bối cảnh** Work Order vượt deadline và chưa Completed,
**Khi** overdue detection chạy,
**Thì** Supervisor nhận overdue notification.

**Bối cảnh** PM trigger tạo Work Order,
**Khi** tạo Work Order thành công,
**Thì** Asset Manager/Supervisor nhận notification liên kết tới Work Order vừa sinh.

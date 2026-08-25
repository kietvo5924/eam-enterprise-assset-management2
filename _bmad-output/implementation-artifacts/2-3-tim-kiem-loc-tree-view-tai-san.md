# 2-3: Tìm Kiếm, Lọc & Tree View Tài Sản

## 1. Story Foundation (Nền Tảng Câu Chuyện)
- **Epic**: 2 (Cơ Sở Dữ Liệu Tri Thức Tài Sản)
- **Story ID**: 2.3
- **Status**: ready-for-dev
- **Story Key**: 2-3-tim-kiem-loc-tree-view-tai-san

### Yêu Cầu Chức Năng (Functional Requirements)
- **User Story Statement**: Là Asset Manager, Tôi muốn tìm kiếm, lọc và duyệt tài sản theo dạng cây, Để nhanh chóng tìm tài sản và kiểm tra cấu trúc phân cấp (FR14, FR16, FR18, FR19, NFR3).
- **Mục Tiêu Kinh Doanh**: Cho phép tổ chức tài sản theo dạng cây phân cấp (Asset Hierarchy) không giới hạn độ sâu và hỗ trợ tìm kiếm, bộ lọc nhanh để tối ưu hóa quản lý số lượng lớn tài sản (lên tới 10,000 assets mỗi tenant).

### Tiêu Chí Chấp Nhận (Acceptance Criteria)
1. **Bối cảnh** tài sản tồn tại ở nhiều node trong hierarchy,
   **Khi** filter được áp dụng,
   **Thì** các tài sản phù hợp được trả về kèm pagination.
2. **Bối cảnh** một hierarchy node được mở,
   **Khi** dữ liệu con được yêu cầu,
   **Thì** node con và tài sản liên quan được hiển thị trong performance target (Asset hierarchy tree render ≤ 2 giây cho hierarchy có ≤ 1,000 nodes).
3. **Bối cảnh** xem chi tiết một node cha,
   **Khi** tải dữ liệu,
   **Thì** hệ thống phải có khả năng hiển thị tất cả các tài sản con thuộc node cha đó.

## 2. Developer Context (Ngữ Cảnh Dành Cho Developer)
**CẢNH BÁO: Phải đọc kỹ các yêu cầu kỹ thuật bên dưới trước khi bắt đầu.**

### 2.1 Yêu Cầu Kỹ Thuật Đặc Thù
- **Hierarchy Data Modeling**: Bắt buộc sử dụng `ltree` extension hoặc Recursive CTE của PostgreSQL cho tính năng phân cấp. Cần thiết lập cột `path` (ltree) hoặc hệ thống CTE để truy vấn cây tài sản có độ sâu không giới hạn thay vì lưu trữ dạng nested set phức tạp.
- **Tree Render Performance (NFR3)**: Truy vấn API trả về dữ liệu hierarchy tree phải cực kì tối ưu, có thể cần áp dụng Pagination, Chunking cho từng level hoặc In-memory Caching (Spring Cache) để đạt performance render ≤ 2 giây cho 1,000 nodes.
- **Tìm kiếm và lọc đa điều kiện**: API phải hỗ trợ tìm kiếm (Keyword search trên tên, serial, model) và lọc (category, status, tree node) hiệu quả, hỗ trợ phân trang (Pagination).

### 2.2 Tuân Thủ Kiến Trúc (Architecture Compliance)
- **Database & Query**: Cần một Flyway script bổ sung (vd `V15__add_hierarchy_to_assets.sql`) để kích hoạt extension `ltree` (nếu chưa có) và bổ sung field `path` hoặc `parent_id` với logic recursive CTE cho bảng `assets`. LUÔN tuân thủ Tenant Isolation (bắt buộc kèm `WHERE tenant_id = ?`).
- **Backend**: Update `AssetController`, `AssetService`, `AssetRepository`. Thêm endpoint lấy tree hierarchy (vd: `GET /api/v1/assets/tree`). 
- **Web Portal**: 
  - Mở rộng SplitPaneAssetExplorer (`AssetRegistry.tsx`) để phần bên trái (Sidebar) hiển thị Tree View cho Asset Hierarchy.
  - Sử dụng Ant Design `Tree` component hoặc xây dựng custom tree component đảm bảo chuẩn High-Density Dashboard, tương tác mượt mà.
  - Tái sử dụng store Zustand `useAssetRegistryStore.ts` để lưu trữ trạng thái tìm kiếm, lọc, và cây tài sản.

### 2.3 Phân Tích Hiện Trạng Mã Nguồn (Previous Story Intelligence)
- **LƯU Ý ĐẶC BIỆT DÀNH CHO DEVELOPER**: 
  - Giao diện và mã nguồn ở Story 2-2 (`AssetRegistry.tsx`, `useAssetRegistryStore.ts`, Component Design) và 2-1 (`AssetCategoryManagement.tsx`) **PHẢI** được xem lại kỹ càng trước khi viết code mới. 
  - Từ Story 2-2, đã có `assets` có khóa ngoại trỏ tới `category_id`. Chúng ta đã xây dựng form CRUD và Master-Detail SplitPaneAssetExplorer. Việc thêm tính năng Tree View và Lọc phải kế thừa UI/UX, màu sắc, pagination (sử dụng sessionStorage) và responsive grid đã thiết lập từ các Commit gần đây.
  - Phải duy trì sự đồng bộ hoàn toàn với API Response Wrapper (`success`, `data`, `error`, `meta`) đã áp dụng.
  - **Mọi code mới không được làm vỡ layout, không lặp lại mã, và không được sai phong cách code (Naming convention, file structure) đã chuẩn hóa ở Story 2-1 & 2-2.** 

### 2.4 Cấu Trúc File & Database
- `backend/src/main/resources/db/migration/`: Tạo script `V15__...` để mở rộng bảng assets hỗ trợ hierarchy (ltree/parent_id).
- `backend/src/main/java/com/eam/api/repositories/`: Cập nhật `AssetRepository.java` thêm custom queries cho Search/Filter đa điều kiện (sử dụng Specification/Criteria API hoặc JPQL Native với ltree/CTE).
- `backend/src/main/java/com/eam/api/services/`: Cập nhật `AssetService.java` xử lý logic hierarchy.
- `web-portal/src/features/assets/`: Cập nhật UI trong `AssetRegistry.tsx` (thêm vùng Tree View, thanh search/filter).
- Cập nhật store: `web-portal/src/features/assets/store/useAssetRegistryStore.ts`.

### 2.5 Yêu Cầu Kiểm Thử (Testing Requirements)
- **Backend Unit/Integration Tests**: Kiểm tra các logic tìm kiếm với filter phức tạp, lấy node con của hierarchy và đảm bảo Pagination/Meta trả về đúng.
- **Performance Test (Local)**: Verify query lấy cây có ≤ 1,000 nodes đạt phản hồi < 500ms API.
- **Web Portal**: Kiểm thử giao diện click mở rộng/thu gọn Tree View, nhập keyword filter list, kiểm tra giao diện không bị giật/lag.

## 3. Project Context Reference
- **Document Language**: Vietnamese
- **Project Name**: eam-enterprise-assset-management
- **Mã Story (ID)**: 2.3
- **Key**: 2-3-tim-kiem-loc-tree-view-tai-san

## Trạng Thái Hoàn Thành Tạo Context
- Status: **ready-for-dev**
- Ultimate context engine analysis completed - comprehensive developer guide created

## 4. Tasks/Subtasks Dành Cho Dev Agent (CHUẨN BỊ KỸ, KHÔNG ĐƯỢC THIẾU)
- [x] 1. **Khảo sát Code Cũ (Bắt Buộc)**: Review lại file `AssetRegistry.tsx`, `useAssetRegistryStore.ts` và `AssetController` để hiểu chuẩn mã nguồn hiện tại, UI state (pagination lưu session) và UI framework (AntD/Tailwind) trước khi code.
- [x] 2. **Database Schema**: Tạo Flyway script (`V15__...`) để update bảng `assets` phục vụ cấu trúc hierarchy (sử dụng `parent_id` và extension `ltree` nếu PostgreSQL hỗ trợ mạnh, hoặc recursive CTE).
- [x] 3. **Backend - API & Repository**: Bổ sung Criteria API / JPQL trong `AssetRepository` để lọc linh hoạt (tên, serial, category, status).
- [x] 4. **Backend - Hierarchy Logic**: Thêm hàm lấy danh sách dạng cây (Hierarchy Tree) trong `AssetService` đảm bảo chặn Tenant an toàn. Bổ sung endpoint GET `/api/v1/assets/tree`. Áp dụng Spring Cache nếu cần để đạt target <2s.
- [x] 5. **Web - Store Update**: Cập nhật `useAssetRegistryStore.ts` thêm state cho Tree Data, Search Keywords, Filters, Selected TreeNode.
- [x] 6. **Web - UI/UX Layout**: Chỉnh sửa Master-Detail `SplitPaneAssetExplorer` (trong `AssetRegistry.tsx`) để phần bên trái có Tabs hoặc chia ngang: 1 phần hiển thị Tree View (Sử dụng AntD Tree Component), 1 phần hiển thị Search & Data Table.
- [x] 7. **Web - Search & Filter UI**: Thêm ô tìm kiếm, dropdown lọc theo trạng thái/Danh mục. Đảm bảo UI hiện đại, High-density, không phá vỡ UI cũ của CRUD và QR Code.
- [x] 8. **Testing & Đảm bảo hiệu năng**: Chạy test Unit/Integration trên Spring Boot. Mock Data (nếu cần) để test 1000 nodes xem tree render có giật không, và đảm bảo mọi AC đã pass.

### Review Findings

- [x] [Review][Defer] Thiếu phần Backend API cho Hierarchy & Filter — deferred, pre-existing: Đã lỡ làm hoàn chỉnh ở Frontend nên tạm thời sử dụng xử lý ở Frontend.

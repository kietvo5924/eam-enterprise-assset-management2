# Story 2-4: Di Chuyển Tài Sản & Lịch Sử Bảo Trì

## 1. Story Foundation

**Epic:** 2 - Cơ Sở Dữ Liệu Tri Thức Tài Sản  
**Story:** 2.4 - Di Chuyển Tài Sản & Lịch Sử Bảo Trì

**User Story Statement:**
> As an Asset Manager,
> I want to be able to move assets between different location nodes in the hierarchy and view their maintenance history,
> So that the physical location is always accurate and the maintenance context is preserved.

**Business Value & Context:**
- Tài sản thực tế thường xuyên được luân chuyển giữa các phòng ban, nhà máy hoặc chi nhánh.
- Việc ghi nhận lại lịch sử di chuyển (thông qua audit trail) là bắt buộc.
- Lịch sử bảo trì (các Work Order đã hoàn thành) cần gắn liền với tài sản để hỗ trợ đánh giá hiệu suất, lập kế hoạch bảo trì tương lai, và kiểm toán.

## 2. Acceptance Criteria

**AC1: Di chuyển tài sản trong Hierarchy**
- **Bối cảnh:** Tài sản đang được gắn tại một vị trí cụ thể (có `locationId`).
- **Khi:** Asset Manager chọn "Di chuyển" (hoặc chỉnh sửa vị trí) và chọn một node Location hợp lệ khác từ Tree View/Select.
- **Thì:** Thuộc tính `locationId` của tài sản được cập nhật, UI Tree View lập tức phản hồi (tài sản nhảy sang nhánh mới), và hệ thống Backend tự động ghi nhận thao tác này vào Audit Trail.

**AC2: Xem Lịch Sử Bảo Trì**
- **Bối cảnh:** Tài sản đã từng được gắn với các Work Order (WO) đã hoàn thành trong quá khứ.
- **Khi:** Asset Manager mở tab "Lịch Sử Bảo Trì" trong chi tiết tài sản.
- **Thì:** Danh sách các WO liên quan (nhấn mạnh các WO trạng thái `COMPLETED`) được liệt kê theo thứ tự thời gian giảm dần (mới nhất xếp trên).

## 3. Developer Context & Guardrails (QUAN TRỌNG)

### Bối cảnh kế thừa từ Story 2-3 (ĐỌC KỸ ĐỂ ĐỒNG BỘ)
- **Lưu ý đặc biệt:** Ở Story 2-3, tính năng **Tree View và Lọc đã được làm hoàn toàn ở Frontend** (xử lý danh sách phẳng thành cây bằng Javascript với `useMemo` và các hàm `getFullPath`, `formatLtree`). Backend API cho `/api/v1/assets/tree` đã được **Deferred** để giảm tải và tận dụng sức mạnh phía client.
- Do đó, khi làm tính năng Di chuyển tài sản:
  - **Không** cần thiết kế lại Tree API ở Backend.
  - Việc di chuyển bản chất là hành động **Update `locationId`** của đối tượng `Asset`.
  - Trên Frontend (`AssetRegistry.tsx`), việc cung cấp một Modal hoặc Dropdown TreeSelect cho phép chọn `Location` mới là đủ. Do cấu trúc `useMemo` đã được thiết lập, việc thay đổi `locationId` trong store sẽ tự động "nhấc" tài sản sang nhánh Location mới trên UI.

### Technical Requirements
1. **Frontend (UI/UX)**:
   - Thêm nút **Di chuyển** (Move) bên cạnh các nút Sửa/Xóa trong phần chi tiết tài sản.
   - Thêm tab **Lịch sử bảo trì** (Maintenance History) vào giao diện chi tiết tài sản (hiện tại `AssetRegistry.tsx` đang có phần thông số kỹ thuật, cần bổ sung hệ thống Tab của Ant Design để phân trang nội dung Detail: Thông tin chung / Lịch sử).
   - Component TreeSelect cho việc di chuyển cần sử dụng danh sách `locations` phẳng, và render ra dạng cây dựa trên `parentId` giống hệt cách `renderLocationNode` đang làm.
2. **Backend**:
   - Nếu endpoint Update Asset (`PUT /api/v1/assets/{id}`) đã xử lý việc thay đổi `locationId` và tự động trigger Audit Trail (đã làm ở Epic 1), thì không cần thêm endpoint mới. Chỉ cần đảm bảo Audit Trail bắt được sự kiện "Thay đổi locationId từ X sang Y".
   - (Tùy chọn cho tương lai, hiện tại có thể mock data) Endpoint `GET /api/v1/assets/{id}/work-orders` để lấy danh sách lịch sử bảo trì. Nếu module Work Order chưa sẵn sàng (thuộc Epic 3), hãy **Tạo Mock Data** hoặc chuẩn bị sẵn interface ở Frontend để gắn vào sau.

### File Structure Requirements
- `web-portal/src/features/assets/components/AssetRegistry.tsx`: Cần tái cấu trúc phần bên phải (Right Rail & Detail) để đưa vào AntD `Tabs`.
- `web-portal/src/features/assets/store/useAssetRegistryStore.ts`: Đảm bảo hàm `updateAsset` đã hoạt động tốt để xử lý `locationId`.

## 4. Tasks/Subtasks Dành Cho Dev Agent

### Review Findings
- [x] [Review][Patch] Tránh gọi API khi chọn lại vị trí cũ / Vô hiệu hóa vị trí hiện tại trong TreeSelect [AssetRegistry.tsx]
- [x] [Review][Patch] Reset state `movingLocationId` khi người dùng nhấn Hủy Modal [AssetRegistry.tsx]

- [x] 1. **Khảo sát UI Detail hiện tại**: Xem xét kỹ `AssetRegistry.tsx`, đặc biệt là giao diện hiển thị chi tiết tài sản hiện tại.
- [x] 2. **Tích hợp AntD Tabs**: Bao bọc phần "Thông số kỹ thuật chung" vào một Tab ("Thông Tin Chung"). Thêm một Tab mới ("Lịch Sử Bảo Trì").
- [x] 3. **Tính năng Di chuyển**:
  - Thêm một nút (Button) "Di Chuyển" vào Action bar của phần chi tiết.
  - Thiết kế một Modal chứa `TreeSelect` của Ant Design, map dữ liệu từ `locations` store để cho phép người dùng chọn đích đến mới.
  - Gọi hàm `updateAsset({ locationId: newId })` khi submit và hiển thị Toast thành công.
- [x] 4. **Mock Lịch sử bảo trì**: Xây dựng UI Timeline hoặc Table đơn giản trong Tab "Lịch Sử Bảo Trì", dùng dữ liệu tĩnh (Mock) tạm thời vì Epic 3 (Work Order) chưa bắt đầu. Đảm bảo UI khớp với thiết kế High-density.

## 5. Dev Agent Record

### Implementation Notes
- Đã khảo sát và tích hợp thành công Ant Design `Tabs` cho phần chi tiết tài sản.
- Đã thêm tính năng di chuyển tài sản bằng `TreeSelect` với dữ liệu cấu trúc Location lấy từ store.
- Modal di chuyển sử dụng `updateAsset` để cập nhật `locationId` và tải lại danh sách tài sản (thông qua store cập nhật state trực tiếp).
- Đã thêm Mock Data dạng `Timeline` của Ant Design cho "Lịch Sử Bảo Trì", đáp ứng giao diện High-density.
- Đã sửa type issue của `locationId` khi update.

### File List
- `web-portal/src/features/assets/components/AssetRegistry.tsx`

### Change Log
- Thêm `Tabs`, `TreeSelect`, `Timeline` vào `AssetRegistry.tsx`.
- Thêm tính năng Move Modal vào `AssetRegistry.tsx`.

---
**Trạng thái Story:** done
**Note:** Ultimate context engine analysis completed - comprehensive developer guide created based on deferral history.

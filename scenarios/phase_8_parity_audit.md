# Phase 8 Parity Audit

> [!IMPORTANT]
> **GLOBAL EXECUTION RULES FOR PHASE 8 TASKS**
> Khi Agent nhận được lệnh thực thi bất kỳ Task nào trong Phase 8, Agent **BẮT BUỘC** phải tuân thủ nghiêm ngặt quy trình sau đây trước khi sửa code:
> 
> 1. **Đọc Source Legacy Frontend:** Truy cập và đọc kỹ file tương ứng trong `web-portal/src/` để nắm UI/UX gốc.
> 2. **Đọc Source Legacy Backend:** Truy cập và đọc kỹ file tương ứng trong `backend/src/` để nắm logic API/Database gốc.
> 3. **Đọc Source Django Hiện Tại:** Truy cập và đọc file tương ứng trong `eam_app/` để xem hiện trạng.
> 4. **Đối Chiếu & Sửa Chữa Trực Tiếp:** So sánh 1:1 giữa Legacy và Django. Nếu phát hiện ra **BẤT KỲ ĐIỀU GÌ KHÁC BIỆT HOẶC BỊ THIẾU** (về UI, logic, URL, cấu trúc database, v.v.) so với source cũ, **TIẾN HÀNH FIX/CẬP NHẬT NGAY LẬP TỨC** vào source Django mà không cần hỏi lại ý kiến người dùng.

---


## Authentication & Bootstrap Flow

| Legacy Feature | Legacy Source Location | Django Current Location | Status | Difference | Required Action |
|---|---|---|---|---|---|
| Initial System Tenant | `V8__add_system_tenant_and_super_admin.sql` | `seed_core.py` | MATCH | None | Verify via execution. |
| SUPER_ADMIN Role & User | `V8__add_system_tenant_and_super_admin.sql` | `seed_core.py` | MATCH | None | Verify via execution. |
| Default Tenant Admin | `SystemTenantController.java` | `portal_tenants` view | MATCH | No default `admin` assumed in both. | None |

## WORKSPACE Navigation

| Legacy Feature | Legacy Source Location | Django Current Location | Status | Difference | Required Action |
|---|---|---|---|---|---|
| Dashboard | `App.tsx` & `Dashboard.tsx` | `base.html` & `dashboard.html` | MATCH | None | None |
| Asset Registry | `App.tsx` & `AssetRegistry.tsx` | `base.html` & `asset_registry.html` | MATCH | None | None |
| Work Orders | `App.tsx` & `WorkOrders.tsx` | `base.html` & `work_orders.html` | MATCH | None | None |
| Maintenance | `App.tsx` & `Maintenance.tsx`| `base.html` & `pm_plans.html` | MATCH | None | None |
| Reports | `App.tsx` & `Reports.tsx` | `base.html` & N/A | MISSING | Django lacks URL/View for Reports. | Implement view & template matching legacy placeholder. |
| Inventory | `App.tsx` & `SparePartsManagement.tsx` | `base.html` & `inventory.html` | MATCH | None | None |

## ADMIN Navigation

| Legacy Feature | Legacy Source Location | Django Current Location | Status | Difference | Required Action |
|---|---|---|---|---|---|
| Users | `App.tsx` & `UserManagement.tsx` | `base.html` & `users.html` | MATCH | None | None |
| Roles | `App.tsx` & `RoleManagement.tsx` | `base.html` & `roles.html` | MATCH | None | None |
| Asset Configuration | `App.tsx` (Admin menu) | `base.html` (Asset Registry active state) | DIFFERENT | Django groups Asset Config into Workspace instead of Admin sidebar. | Move Asset Config to Admin Sidebar. |
| Settings | `App.tsx` (Admin menu) | `base.html` (Missing) | MISSING | Django lacks Settings in Admin sidebar menu. | Add Settings to Admin Sidebar. |
| Audit Logs | `App.tsx` & `AuditLogViewer.tsx` | `base.html` & `audit_logs.html` | MATCH | None | None |
| Tenants (SuperAdmin) | `App.tsx` & `SystemTenants.tsx` | `base.html` & `tenants.html` | MATCH | None | None |

## Global & Backend Settings

| Legacy Feature | Legacy Source Location | Django Current Location | Status | Difference | Required Action |
|---|---|---|---|---|---|
| Tenant Settings API | `SystemTenantController.java` | `portal_settings` | MATCH | API/Views exist. | Need to verify RBAC `tenant:update` permission. |
| Reports API | N/A | N/A | NOT IMPLEMENTED IN LEGACY | Legacy is just a UI placeholder. | Do not overengineer Django backend, just serve template. |

---

**Summary of Differences:**
1. **Asset Configuration Navigation:** Misplaced in Django (grouped with Workspace instead of Admin).
2. **Settings Navigation:** Missing from Django sidebar.
3. **Reports Component:** Missing URL and template in Django.

## Asset Registry & Hierarchy
| Legacy Feature | Legacy Source Location | Django Current Location | Status | Difference | Required Action |
|---|---|---|---|---|---|
| Asset Tree Endpoint | AssetController.java getAssetTree() | ssets/views.py AssetTreeView | MATCH | Re-implemented AssetTreeView to return locations (nested tree) and unassignedAssets matching Legacy. | None |
| Export Assets | AssetController.java exportAssets() | ssets/views.py AssetExportView | MATCH | Returns CSV with same columns. | None |

| Portal View Asset Registry | AssetController.java & React AssetRegistry.tsx | portal_asset_registry in portal/views.py | MATCH | Fixed hierarchical ltree comparison bug, added strict HasPermission checks (CRUD), applied is_active=False soft-delete instead of hard delete. | None |

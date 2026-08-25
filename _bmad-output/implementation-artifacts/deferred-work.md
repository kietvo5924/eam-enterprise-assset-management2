## Deferred from: code review of 1-1-khoi-tao-du-an-ha-tang (2026-05-22)
- Default credentials used for PostgreSQL (`eam_password`) and MinIO (`minioadmin`) in `docker-compose.yml`. Acceptable for local development MVP but needs secure secrets management for production.

## Deferred from: code review of 1-6-nhat-ky-audit-he-thong (2026-05-28)
- Kiến trúc AuditTrailListener: Đang sử dụng `static ApplicationContext` để lấy event publisher. Đây là cách giải quyết tạm thời cho MVP. Về lâu dài nên config `SpringBeanContainer` cho Hibernate để có thể `@Autowired` trực tiếp.

## Deferred from: code review of 2-3-tim-kiem-loc-tree-view-tai-san (2026-06-03)
- Thiếu phần Backend API cho Hierarchy & Filter — Đã lỡ làm hoàn chỉnh ở Frontend nên tạm thời sử dụng xử lý ở Frontend cho nhẹ, chấp nhận nợ kỹ thuật chưa làm Criteria API và /api/v1/assets/tree ở backend.

## Deferred from: code review of 3-1-tao-work-order (2026-06-10)
- Hardcoded limit of 1000 assets in `fetchAssets` [CreateWorkOrderDrawer.tsx] — deferred, pre-existing acceptable MVP limit
- Missing ON DELETE rules in V18 migration [V18__create_work_orders_table.sql] — deferred, pre-existing (RESTRICT is acceptable)

## Deferred from: code review of 3-2-phan-cong-phan-cong-lai (2026-06-11)
- AssignWorkOrderModal uses size: 100 for technicians [AssignWorkOrderModal.tsx] — deferred, pre-existing limitation to be improved with pagination/search later

## Deferred from: code review of 3-3-luong-trang-thai-cua-work-order.md (2026-06-11)
- [Review][Defer] Missing optimistic locking for WorkOrder state transitions [WorkOrderService.java] � deferred, pre-existing

## Deferred from: code review of 3-5-supervisor-review-follow-up.md (2026-06-11)
- N+1 Query khi ánh xạ followUpWorkOrders
- Thiếu xử lý xóa Cascade cho followUpWorkOrders
- Rủi ro Circular Dependency
- UI thiếu giới hạn hiển thị số lượng Follow-up
  
## Deferred from: code review of 4-1-quet-qr-tra-cuu-thong-tin-tai-san (2026-06-12)  
- Backend Error Handling Pattern -- getAssetByQrCode throws IllegalArgumentException which is a pre-existing pattern mapped by Spring to 400. 

## Deferred from: code review of 4-2-cache-du-lieu-cuc-bo (2026-06-15)
- [Review][Defer] Inefficient Full Sync — `syncAssetsInBackground()` recursively fetches all assets with no incremental sync strategy. [work_order_service.dart] — deferred, pre-existing

## Deferred from: code review of 4-3-thuc-hien-offline-trang-thai-dong-bo.md (2026-06-15)
- [Review][Defer] Offline Checklist Race Condition [work_order_service.dart] — deferred, read-modify-write UI race condition

## Deferred from: code review of 4-4-dong-bo-nen-retry-an-toan-conflict (2026-06-15)
- Lọc dữ liệu work order ở client thay vì API query param [work_order_service.dart]
- Type Casting rủi ro json.decode(fromDb) as List<dynamic> [app_database.dart]
- Dùng .getSingleOrNull() không có .limit(1) gây StateError [app_database.dart]
- Rủi ro mất đồng bộ GET sau POST thất bại tại _updateLocalWorkOrder [work_order_service.dart]

## Deferred from: code review of 5-1-tao-pm-plan (2026-07-01)
- Test `PmPlanControllerTest` bị vô hiệu hoá (@Disabled) do cấu hình DB [backend/src/test/java/com/eam/api/controllers/PmPlanControllerTest.java] — deferred, pre-existing

## Deferred from: code review of 5-3-tu-dong-sinh-work-order.md (2026-07-01)
- Performance Bottleneck - Unpaginated DB Query [PmSchedulerService.java] � deferred, pre-existing
- Code Smell - Disabled Tests & Reflection [WorkOrderServiceTest.java] � deferred, pre-existing

## Deferred from: code review of 5-4-calendar-view-lich-bao-tri.md (2026-07-01)
- Performance Bottleneck: In-Memory OOM Risk [WorkOrderService.java] � Fetching all active PM assignments into memory and doing calculations in Java can cause OOM. Doing DB-level recursive date projection is highly complex in SQL/JPA and likely out of scope for this story without a materialized view.

# Workspace AI Agent Operational Guidelines (AGENTS.md)

This repository is an enterprise-grade, multi-tenant **Enterprise Asset Management (EAM)** solution spanning a full-stack, multi-platform architecture. All AI agents, assistants, and human contributors working within this workspace MUST adhere to these architectural pillars and operational guidelines.

---

## 1. Core Architectural Pillars

The codebase strictly consists of three core pillars. No task or refactoring should treat this workspace as merely a backend or merely a mobile application:

### Pillar 1: Backend Layer (`eam_app/`)
- **Framework**: Django 6.1 with Django REST Framework (DRF), Celery background queues, and Redis.
- **8 Core Django Apps**:
  1. `core`: Multi-tenant foundation (`Tenant`, `BaseTenantModel`, `TenantManager`, thread-local tenancy), automated `AuditLog`, MinIO S3 file storage integration.
  2. `users`: Custom `User` model, RBAC (`Role`, `Permission`), technician workforce profiles (`TechnicianProfile`, `WorkforceSkill`, `CertificationType`, `UserCertification`), and shift schedules (`ShiftTemplate`, `TechnicianSchedule`).
  3. `assets`: Hierarchy topologies (`Location`, `AssetCategory`, `HierarchyTemplate`, `Asset`), MRO inventory (`SparePart`, `StockTransaction`), specialized tools (`Tool`, `ToolInstance`, `ToolReservation`), sensor readings (`MeterReading`), and alerts (`AssetAnomalyAlert`, `AssetRulPrediction`).
  4. `workorders`: Work order lifecycle (`WorkOrder`), checklist items (`WorkOrderChecklistItem`), attachments (`WorkOrderAttachment`), material consumption (`WorkOrderMaterial`), labor logs (`LaborLog`), frozen cost breakdowns (`WorkOrderCost`), and GA jobs (`GAOptimizationJob`).
  5. `maintenance`: Reliability-Centered Maintenance (RCM) & Preventive Maintenance (PM) plans (`PmPlan`, `PmPlanChecklistItem`, `PmPlanMaterial`, `PmPlanAssignment`) evaluated via Celery Beat periodic triggers.
  6. `portal`: Server-Side Rendered (SSR) web console and executive dashboard for planners and asset managers.
  7. `notifications`: Multi-channel notifications (In-App, Email, FCM Mobile Push), preference matrices (`NotificationPreference`), and device push token registration (`DevicePushToken`).
  8. `analytics`: KPI summary engines, asynchronous multi-format report exports (`ExportJob` for XLSX, PDF, CSV), time-series cost forecasting (`BudgetForecast`, `TenantFinancialSetting`, `PeriodApprovedBudget`), and reliability analytics (`ReliabilityMetricsService` for MTBF, MTTR, Plant Availability).
- **Computational Modules (`eam_app/algorithms/`)**:
  - `hungarian`: Kuhn-Munkres LSAP algorithm for optimal technician task auto-assignment.
  - `genetic`: NSGA-II multi-objective genetic algorithm for multi-shift maintenance scheduling.
  - `tsp_routing`: Traveling Salesperson Problem solver with 2-opt and warehouse pit-stops for technician plant routing.
  - `anomaly_detection`: Real-time ISO 10816 vibration severity and Theil-Sen drift detection.
  - `predictive_rul`: Remaining Useful Life prediction using degradation modeling and Monte Carlo dropout intervals.
  - `cost_forecasting`: Quantile Regression Forest (QRF) and hybrid maintenance budget forecasting with "Lemon" asset detection.

### Pillar 2: Mobile Application Layer (`mobile_app/`)
- **Framework**: Flutter with Dart SDK (`^3.9.2`), Null Safety.
- **Architecture**: Feature-Driven Clean Architecture (`lib/core/` and `lib/features/`).
- **State Management**: `provider` (`UserProvider`, `WorkOrderProvider`, `NetworkService`).
- **Routing**: `go_router` (`AppRouter`) with authentication state redirect guards.
- **Networking**: `dio` (`DioClient`) with JWT bearer token injection, timeout handling, and idempotency headers.
- **Hardware Integration**:
  - `mobile_scanner`: High-speed camera QR/barcode scanner with haptic vibration feedback.
  - `image_picker`: Camera capture for work order visual attachments.
- **Key Modules (`lib/features/`)**:
  - `auth`: `LoginScreen`, `AuthService`.
  - `dashboard`: `HomeScreen`, `CalendarScreen`, `EquipmentScreen`, `EquipmentDetailScreen`, `FloorplanViewerScreen` (CAD layout visualizer), `NotificationsScreen`.
  - `scanner`: `QRScannerScreen` with local Drift SQLite caching.
  - `sync`: `SyncEngine`, `OfflineSyncIndicator`.
  - `work_orders`: `WorkOrderListScreen`, `CreateWorkOrderScreen`, `WorkOrderDetailScreen`, `TechnicianRouteScreen`, `RouteMapPainter`, `SwipeableChecklistTile`.

### Pillar 3: Data & Offline-Sync Layer
- **Mobile Local Storage**: Local SQLite managed by `drift` (`eam_db.sqlite`, `sqlite3_flutter_libs`).
  - Tables: `Assets`, `WorkOrders`, `SyncQueues`.
  - DAOs: `AssetDao`, `WorkOrderDao`, `SyncQueueDao`.
- **Backend Relational Storage**: PostgreSQL (production) / SQLite (local development) managed via Django ORM.
- **Bidirectional Offline-First Sync**:
  - **Downstream Sync**: Background chunked pagination fetches server records. Local work orders with pending mutations in `SyncQueues` are strictly protected from overwrite. Remote images are precached in background via `DefaultCacheManager`.
  - **Upstream Sync**: Local mutations immediately update SQLite and enqueue tasks into `SyncQueues`. `SyncEngine` processes pending tasks sequentially with exponential backoff (`delay = 2^retryCount` seconds), passing `Idempotency-Key` headers. HTTP 409 moves to `CONFLICT`; HTTP 400/403/404 are classified as deterministic `FAILED`; transient network errors retry up to 3 times.
  - **Eviction Policies**: Automated cleanup of orphaned assets (> 30 days) and old completed work orders (> 7 days) to conserve device storage.

---

## 2. Directory Exclusion & File Search Rules

When running file searches, grep, indexing, or terminal operations, **ALWAYS ignore the following bloated non-source directories**:
- `venv/`, `**/venv/**`
- `staticfiles/`
- `media/`
- `mobile_app/build/`
- `mobile_app/.dart_tool/`
- `**/__pycache__/**`
- `.pytest_cache/`
- `.git/`

---

## 3. Engineering Conventions & Testing

1. **Multi-Tenancy**: Every new backend model MUST inherit from `core.models.BaseTenantModel`. Direct database queries that bypass tenancy are forbidden except in designated background tasks via `.all_objects`.
2. **Reliability Metrics (RCM)**: When calculating MTBF and MTTR, never include Preventive Maintenance (`PREVENTIVE`). Always filter anomalous completed durations ($0 < \text{duration} \le 168.0\text{ hours}$). Zero-failure conditions must output `100% Khả dụng (0 Sự cố)`.
3. **Offline Sync Idempotency**: All mobile mutations queued for sync MUST provide a unique `idempotencyKey` UUID.
4. **Verification Commands**:
   - Backend tests:
     ```bash
     venv\Scripts\python eam_app/manage.py test algorithms.tests
     venv\Scripts\python eam_app/manage.py test analytics.tests
     venv\Scripts\python eam_app/manage.py test core.tests
     ```
   - Mobile tests:
     ```bash
     cd mobile_app
     flutter test test/notifications_test.dart
     ```

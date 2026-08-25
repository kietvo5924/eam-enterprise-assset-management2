---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8]
workflowType: 'architecture'
lastStep: 8
status: 'complete'
completedAt: '2026-05-15'
inputDocuments: 
  - "_bmad-output/planning-artifacts/prd.md"
  - "_bmad-output/planning-artifacts/ux-design-specification.md"
  - "_bmad-output/planning-artifacts/ux-design-directions.html"
  - "docs/idea.md"
workflowType: 'architecture'
project_name: 'eam-enterprise-assset-management'
user_name: 'Admin'
date: '2026-05-15'
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements:**
Hệ thống bao gồm 50 FRs xoay quanh 4 module MVP cốt lõi: Nền tảng Core (Multi-tenant, Auth, Audit), Asset Registry & Hierarchy, Work Order Management, và Preventive Maintenance. Về mặt kiến trúc, điều này đòi hỏi một thiết kế dữ liệu đa khách hàng (multi-tenant data model) mạnh mẽ, cơ chế lưu trữ cây phân cấp sâu (hierarchical tree storage), và một công cụ quy trình làm việc (workflow engine) để quản lý trạng thái của Work Order.

**Non-Functional Requirements:**
Các NFR sẽ định hình kiến trúc bao gồm:
- **Reliability & Offline:** Kiến trúc Offline-first trên Mobile, yêu cầu chiến lược đồng bộ dữ liệu ngầm (background sync) và giải quyết xung đột (conflict resolution).
- **Security:** Cách ly dữ liệu khách hàng (Tenant data isolation) tuyệt đối.
- **Performance:** Xử lý render cây cấu trúc tài sản lớn (<2s) và API phản hồi nhanh (<500ms).

**Scale & Complexity:**
Dự án có quy mô và độ phức tạp đáng kể do kết hợp cả nghiệp vụ B2B phức tạp và yêu cầu ứng dụng di động ngoại tuyến.
- Primary domain: Full-stack (Web Portal, Mobile App, Backend API, Event Broker)
- Complexity level: Medium-High
- Estimated architectural components: ~10-15 core components (Bao gồm API Gateway/Controllers, Tenant Filter, Sync Manager, Hierarchy Service, Auth/RBAC, Kafka Producers/Consumers, v.v.)

### Technical Constraints & Dependencies

- Bắt buộc sử dụng PostgreSQL (cho data/hierarchy) và Kafka (cho event-driven notification).
- Giới hạn về mặt UI/UX: Web Portal phải tối ưu cho Desktop (High-density data) sử dụng Ant Design; Mobile ưu tiên vùng ngón tay cái (Thumb-zone) và Offline-first sử dụng Material 3.
- Cách ly dữ liệu khách hàng (Tenant Isolation) phải được thực thi triệt để ở tầng Repository/Query.

### Cross-Cutting Concerns Identified

- **Multi-tenancy:** Quản lý `tenant_id` trên mọi bảng nghiệp vụ và context API.
- **Offline Data Synchronization:** Cơ chế lưu trữ cục bộ, hàng đợi đồng bộ (sync queue), và xử lý xung đột (ví dụ: last-write-wins).
- **Security & RBAC:** Phân quyền chi tiết dựa trên vai trò cho đa nền tảng và người dùng.
- **Audit Logging:** Theo dõi tự động mọi thao tác Create/Update/Delete.
- **Error Handling & Resilience:** Đặc biệt đối phó với môi trường mạng chập chờn trên Mobile.

## Starter Template Evaluation

### Primary Technology Domain

**Full-stack Multi-Platform** (Web Portal, Mobile App, Backend API) based on PRD requirements.

### Starter Options Considered

Dự án yêu cầu 3 nền tảng riêng biệt, do đó chúng ta không sử dụng một boilerplate nguyên khối (monolithic starter) mà sẽ sử dụng các CLI chính thức tốt nhất cho từng nền tảng:
- **Frontend Web**: `vite` (nhanh hơn create-react-app rất nhiều, hỗ trợ TypeScript out-of-the-box).
- **Backend API**: `Spring Initializr` (tiêu chuẩn công nghiệp cho Spring Boot).
- **Mobile**: `flutter create` (công cụ khởi tạo chính thức của SDK).

### Selected Starters: Vite (Web), Spring Initializr (Backend), Flutter CLI (Mobile)

**Rationale for Selection:**
Đây là các công cụ scaffolding (tạo khung dự án) chính thức, mới nhất và được duy trì tốt nhất cho các công nghệ đã được chốt trong PRD. Chúng giúp chúng ta tránh phải cấu hình thủ công Webpack (cho Web), pom.xml từ con số không (cho Backend) hay các native files phức tạp (cho Mobile).

**Initialization Commands:**

```bash
# 1. Khởi tạo Web Portal (React + TypeScript bằng Vite)
npm create vite@latest web-portal -- --template react-ts

# 2. Khởi tạo Backend API (Spring Boot 3.x, Java 17, Maven)
curl https://start.spring.io/starter.tgz \
  -d type=maven-project \
  -d language=java \
  -d baseDir=backend \
  -d groupId=com.eam \
  -d artifactId=api \
  -d name=eam-api \
  -d packaging=jar \
  -d javaVersion=17 \
  -d dependencies=web,data-jpa,postgresql,kafka,validation | tar -xzvf -

# 3. Khởi tạo Mobile App (Flutter)
flutter create --org com.eam --platforms=android,ios mobile_app
```

## ERP-Standard MVP Architecture Note

Bản triển khai đầu tiên nên có thể sử dụng end-to-end và sẵn sàng về mặt cấu trúc cho các hoạt động kiểu ERP.

- **Thông báo:** MVP bao gồm thông báo được lưu trữ, giao tiếp WebSocket cho Web Portal, FCM push cho Mobile, trạng thái chưa đọc/đã đọc, và nhắm tới người nhận theo tenant.
- **Kafka:** Kafka vẫn là bus sự kiện nội bộ cho các domain event như `work_order.completed` và `maintenance.triggered`.
- **Đồng bộ Offline:** MVP bao gồm bộ nhớ đệm cục bộ, hàng đợi đồng bộ, retry, khóa idempotency, và xử lý xung đột cơ bản sử dụng last-write-wins kèm thông báo rà soát cho supervisor.
- **RBAC:** MVP bao gồm vai trò và quyền cấu hình được quản lý bởi Tenant Admin, với các vai trò mặc định cố định seed sẵn khi cài đặt.
- **Vận hành:** MVP bao gồm cổng CI/test cơ bản và quy trình backup/restore phải đạt **Cross-component consistency** (snapshot PostgreSQL và lưu Kafka Offsets đồng thời để tránh mất đồng bộ state), kèm hướng dẫn Flyway migration.
- **Truy cập:** Tuân theo mục tiêu UX cho khả năng sử dụng ERP cơ bản; tối thiểu hiện thực điều hướng bằng bàn phím, tương phản, nhãn, và hỗ trợ kích thước font trên mobile.
- **Tenant Theme Delivery:** Cấu hình theme (màu chủ đạo, logo) được quản lý bởi Tenant Admin, lưu trữ tại Backend và được Web/Mobile tự động tải về áp dụng lúc khởi tạo ứng dụng nhằm đảm bảo tính cá nhân hóa (White-label) theo tổ chức.

**Kiến trúc được đề xuất bởi Starter:**

**Ngôn ngữ & Runtime:**
- **Web**: TypeScript/JavaScript trên môi trường Node.js.
- **Backend**: Java 17 trên JVM.
- **Mobile**: Dart 3.x.

**Giải pháp style:**
- **Web**: Cấu hình cơ bản của Vite hỗ trợ sẵn CSS/CSS modules. Chúng ta sẽ cần cài thêm Tailwind CSS và Ant Design thủ công ở các bước sau.
- **Mobile**: Material 3 mặc định được tích hợp sẵn trong template chuẩn của Flutter.

**Build Tooling:**
- **Web**: Vite (sử dụng esbuild cho tốc độ build cực nhanh).
- **Backend**: Maven (quản lý dependency và build lifecycle).
- **Mobile**: Gradle (cho Android) và CocoaPods/Xcode (cho iOS) được thiết lập tự động bởi Flutter CLI.

**Framework kiểm thử:**
- **Web**: Chưa có sẵn trong Vite template chuẩn (sẽ cần cài đặt thêm Vitest hoặc Jest).
- **Backend**: `spring-boot-starter-test` (bao gồm JUnit Jupiter, Mockito).
- **Mobile**: `flutter_test` (Unit/Widget testing mặc định).

**Tổ chức mã:**
- Khởi tạo cấu trúc thư mục chuẩn của ngành: `/src/main/java` cho Backend, `/src` cho Web, và `/lib/main.dart` cho Mobile.

**Trải nghiệm phát triển:**
- Hot Module Replacement (HMR) cực nhanh cho Web (Vite) và Mobile (Flutter Hot Reload). 
- Development server tích hợp sẵn cho Backend thông qua Maven plugin.

**Lưu ý:** Khởi tạo dự án bằng các lệnh này nên là các story đầu tiên của triển khai.
## Core Architectural Decisions

### Decision Priority Analysis

**Critical Decisions (Block Implementation):**
- **Data Architecture (Mobile):** Quyết định chọn cơ sở dữ liệu cục bộ cho tính năng Offline Sync trên Flutter.
- **Frontend Architecture (Web):** Quyết định chọn giải pháp quản lý trạng thái (State Management) cho ReactJS.

**Important Decisions (Shape Architecture):**
- **Caching Strategy (Backend):** Quyết định sử dụng bộ đệm (caching) để tối ưu hóa truy vấn cấu trúc cây phân cấp (Asset Hierarchy).

**Deferred Decisions (Post-MVP):**
- Tích hợp các hệ thống phân tích, dự đoán bảo trì bằng AI (Predictive Maintenance) được dời sang Phase 3.
- Các module tích hợp hệ thống bên ngoài (ERP, SSO, SMS) dời sang Post-MVP.

### Data Architecture

- **Primary Database:** PostgreSQL kết hợp với Flyway để quản lý versioning schema và hỗ trợ rollback.
- **Object Storage:** Sử dụng MinIO (giả lập S3 local) cho môi trường phát triển và AWS S3 cho production để lưu trữ file. Dữ liệu upload thông qua Presigned URLs hoặc Backend an toàn, với ACL phân lập theo `tenant_id`.
- **Mobile Local Database:** Sử dụng **Drift** (dựa trên SQLite).
  - *Phiên bản:* Drift mới nhất.
  - *Lý do:* Rất ổn định, type-safe bằng Dart, và phù hợp với các mô hình dữ liệu phức tạp. Đặc biệt hiệu quả để xây dựng Offline Sync Engine thay vì dùng SQflite nguyên bản.
- **Hierarchy Data Modeling:** Sử dụng `ltree` extension hoặc Recursive CTE của PostgreSQL để truy vấn cây tài sản có độ sâu không giới hạn thay vì lưu trữ dạng nested set phức tạp.

### Authentication & Security

- **Authentication Method:** Sử dụng Access Token (vòng đời ngắn) kết hợp với Refresh Token (vòng đời dài, HTTP-only cookie). Bắt buộc có cơ chế Token Revocation / Blacklisting.
- **Tenant Isolation:** Dữ liệu được cô lập bằng cách bắt buộc (enforce) bộ lọc `tenant_id` ở tầng Repository/Query Layer. Ngoại lệ duy nhất là các API của Super Admin (thuộc namespace `/api/v1/system/*`) sẽ bypass bộ lọc này để có thể quản lý và khởi tạo tổ chức toàn cầu.
- **Authorization:** Role-Based Access Control (RBAC) linh hoạt tùy chỉnh bởi Tenant Admin.

### API & Communication Patterns

- **API Architecture:** RESTful APIs (Spring Boot Controller) giao tiếp qua JSON. Cả Mobile App và Web Portal đều kết nối chung một bộ API.
- **Internal Messaging:** Sử dụng **Apache Kafka** để truyền tải các sự kiện nội bộ.
- **Real-time Notifications:** Sử dụng giao thức STOMP over WebSocket. Backend phải quản lý chặt chẽ vòng đời kết nối và có bước xác thực Token khi handshake.
- **Caching Strategy:** Sử dụng **Spring Cache (In-memory/Caffeine)**.
  - *Lý do:* Không sử dụng Redis trong giai đoạn MVP để giữ kiến trúc deployment Docker Build đơn giản nhất có thể. Tận dụng cache nội bộ để hỗ trợ các truy vấn cây tài sản thường xuyên.

### Frontend Architecture

- **Web Framework:** ReactJS + Vite.
- **Web UI Library:** Ant Design (hiển thị dữ liệu mật độ cao) + Tailwind CSS (hỗ trợ layout tinh chỉnh).
- **Web State Management:** Sử dụng **Zustand**.
  - *Phiên bản:* Zustand v5.0+
  - *Lý do:* Rất nhẹ, không cần viết nhiều boilerplate code, giải quyết tốt nhu cầu lưu trữ trạng thái Dashboard và cây dữ liệu phức tạp.
- **Mobile Framework:** Flutter + Material Design 3. Ưu tiên trải nghiệm người dùng với vùng chạm lớn (Thumb-zone) và tương tác quét QR mượt mà.

### Infrastructure & Deployment

- **Containerization & Execution (MANDATORY):** Tất cả các service (bao gồm Frontend Web Portal, Backend API, Database, Event Bus) đều phải được đóng gói và chạy 100% bằng **Docker / Docker Compose** trong cả môi trường phát triển (Dev) lẫn Production.
- **Strict Command Prohibition:** Nghiêm cấm tuyệt đối việc chạy project trực tiếp bằng lệnh terminal (như `npm run dev` hay `mvn spring-boot:run`) cho các Web/Backend service. Mọi hoạt động phát triển Web/Backend đều phải thông qua container.
  - **Ngoại lệ (Mobile App):** Ứng dụng Mobile (Flutter) là nền tảng Client-side cài đặt trên thiết bị, do đó **ĐƯỢC PHÉP** chạy trực tiếp bằng lệnh `flutter run` trên Máy ảo giả lập (Emulator/Simulator) hoặc thiết bị thật. Không yêu cầu đóng gói Docker cho Mobile App trong quá trình phát triển.
- **Observability:** Triển khai OpenTelemetry kết hợp với Zipkin (hoặc ELK Stack/Micrometer) để cung cấp Distributed Tracing và Centralized Logging cho môi trường Production, bắt buộc để debug event Kafka.

### Decision Impact Analysis

**Implementation Sequence:**
1. Khởi tạo dự án bằng các Starter CLI cho cả 3 nền tảng (Spring Initializr, Vite, Flutter).
2. Xây dựng Docker Compose (PostgreSQL, Kafka).
3. Cấu hình Flyway migration và Data Models (PostgreSQL + Spring Boot).
4. Cấu hình xác thực (Auth/JWT) và Tenant Isolation Filter ở Backend.
5. Thiết lập Zustand cho Web và Drift cho Mobile.

**Cross-Component Dependencies:**
- API Backend phải thiết kế luồng Sync Endpoint cho phép Mobile App đồng bộ dữ liệu Offline một cách trơn tru.
- Mobile Database (Drift) phải ánh xạ chính xác schema của PostgreSQL (nhưng tối giản hơn) để thuận tiện cho việc lưu Offline Sync Queue.

## Implementation Patterns & Consistency Rules

### Pattern Categories Defined

**Critical Conflict Points Identified:**
Có 5 khu vực dễ xảy ra xung đột giữa các AI agent khi triển khai mã: Naming (đặt tên), Structure (cấu trúc thư mục), Format (định dạng dữ liệu), Communication (giao tiếp nội bộ/sự kiện) và Process (Quy trình xử lý lỗi).

### Naming Patterns

**Database Naming Conventions (PostgreSQL):**
- **Tables**: `snake_case` số nhiều (Ví dụ: `assets`, `work_orders`, `tenants`).
- **Columns**: `snake_case` (Ví dụ: `serial_number`, `created_at`).
- **Foreign Keys**: Luôn kết thúc bằng `_id` (Ví dụ: `tenant_id`, `asset_id`).
- **Boolean fields**: Bắt đầu bằng `is_`, `has_`, `can_` (Ví dụ: `is_active`).

**API Naming Conventions:**
- **Endpoints**: `kebab-case` số nhiều, bắt đầu bằng `/api/v1/` (Ví dụ: `/api/v1/work-orders`).
- **Path Variables**: Nằm trong ngoặc nhọn `{id}` (Ví dụ: `/api/v1/assets/{id}`).
- **Query Params**: `snake_case` (Ví dụ: `?page=1&tenant_id=5`).

**Code Naming Conventions:**
- **Classes/Interfaces/Components**: `PascalCase` (Ví dụ: `WorkOrderService` trong Java, `AssetCard.tsx` trong React).
- **Functions/Variables**: `camel  Case` (Ví dụ: `getWorkOrders`, `isActive`).
- **Constants**: `UPPER_SNAKE_CASE` (Ví dụ: `MAX_RETRY_COUNT`).

### Structure Patterns

**Project Organization:**
- **Backend (Spring Boot)**: Áp dụng mô hình **3-Layer Architecture** truyền thống (Controllers, Services, Repositories, Models) để phù hợp với chuẩn tiêu chuẩn của Java Enterprise.
- **Web (React)** & **Mobile (Flutter)**: Áp dụng cấu trúc **Feature-based** (Nhóm theo chức năng) để dễ quản lý.
  - Web: `/src/features/{tên-module}/components/`, `/src/features/{tên-module}/api/`
  - Mobile: `/lib/features/{tên-module}/presentation/`, `/lib/features/{tên-module}/data/`

### Format Patterns

**API Response Formats:**
Mọi API response (kể cả thành công hay thất bại) phải được bọc trong một Wrapper chuẩn duy nhất:
```json
{
  "success": true,
  "data": { ... },
  "error": null,
  "meta": { "page": 1, "total": 50 }
}
```

**HTTP Status Codes & Error Handling:**
Mọi API response phải bọc trong Wrapper chuẩn, TUY NHIÊN HTTP Status Code phải phản ánh đúng kết quả:
- Thành công: HTTP 200/201 (`success: true`)
- Lỗi nghiệp vụ (Business Error): HTTP 400 (`success: false`)
- Lỗi hệ thống: HTTP 500 (`success: false`)
- Lỗi xác thực/phân quyền: HTTP 401/403 (`success: false`)
Nghiêm cấm tuyệt đối (Anti-pattern) việc trả về HTTP 200 OK kèm theo `success: false`.

**Data Exchange Formats:**
- **JSON keys**: Luôn dùng `snake_case` (Jackson ở Backend phải set `PropertyNamingStrategies.SNAKE_CASE`).
- **Date/Time**: Giao tiếp qua API luôn dùng định dạng chuỗi **ISO 8601 UTC** (Ví dụ: `2026-05-15T08:00:00Z`). Frontend và Mobile tự convert ra Local Timezone của người dùng khi hiển thị.

### Communication Patterns

**Event System Patterns (Kafka):**
- **Topic naming**: `noun.verb` (Ví dụ: `work_order.created`, `asset.updated`).
- **Payload format**: Phải chứa `event_id`, `timestamp`, `tenant_id` và `data`.
- **Tenant Context Propagation:** Vì Kafka Consumer không có HTTP Request, `tenant_id` bắt buộc phải được đẩy vào Kafka Message Headers. Worker phải trích xuất header này để nạp vào TenantContext nội bộ trước khi gọi Repository.

**State Management Patterns:**
- **Zustand (Web)**: Không mutate state trực tiếp. Mọi hàm cập nhật phải dùng format `set{Tên_State}` (Ví dụ: `setWorkOrders`).

### Process Patterns

**Error Handling Patterns:**
- **Backend**: Sử dụng `@RestControllerAdvice` (Global Exception Handler) duy nhất để bắt mọi Exception và trả về HTTP Status code chuẩn kèm format JSON Error Wrapper.
- **Client (Web/Mobile)**: Bắt buộc dùng Interceptor (Axios/Dio) để bắt lỗi `401 Unauthorized` và tự động refresh token hoặc đẩy về trang Login. Hiển thị Toast/Snackbar với user-friendly message, không show raw error code.

**Loading State Patterns:**
- Sử dụng `isLoading` thay vì `fetching`, `loading_status`. Luôn hiển thị Skeleton/Shimmer thay vì màn hình trắng trong quá trình tải dữ liệu lần đầu.

### Enforcement Guidelines

**All AI Agents MUST:**
- KHÔNG tự ý tạo thêm Utils/Helpers mới nếu hệ thống đã có hàm tương đương trong thư mục `/core` hoặc `/shared`.
- LUÔN kiểm tra quyền `tenant_id` khi thực hiện câu lệnh SQL/Repository CUD (Create/Update/Delete).
- KHÔNG ĐƯỢC catch Exception rồi "nuốt" lỗi (swallow errors) mà không ghi log.
- BẮT BUỘC phải dùng Docker / Docker Compose để chạy mọi service. NGHIÊM CẤM việc chạy trực tiếp bằng lệnh terminal như `npm run dev` hay `mvn spring-boot:run`.

### Pattern Examples

**Anti-Patterns (Tuyệt đối tránh):**
- Trả về API trực tiếp Array `[{id: 1}]` thay vì bọc trong `{ success: true, data: [] }`.
- Viết câu lệnh SQL trực tiếp ở tầng Controller trong Spring Boot.
- Đặt tên file React là `assetcard.tsx` (Sai: Phải là `AssetCard.tsx`).

## Project Structure & Boundaries

### Complete Project Directory Structure

Hệ thống sẽ được chia thành 3 thư mục gốc chính cho 3 nền tảng, quản lý tập trung thông qua Docker Compose ở ngoài cùng:

```text
eam-enterprise-assset-management/
├── docker-compose.yml           # Khởi chạy PostgreSQL, Kafka, và Backend
├── README.md
├── docs/                        # Tài liệu dự án (PRD, Architecture, UX)
│
├── backend/                     # Spring Boot API (Java 17, Maven)
│   ├── pom.xml
│   ├── src/main/java/com/eam/api/
│   │   ├── config/              # Cấu hình Security, Kafka, CORS, Swagger
│   │   ├── core/                # Base Exceptions, Tenant Filter, Interceptors
│   │   ├── controllers/         # Presentation Layer (REST APIs)
│   │   ├── services/            # Business Logic Layer
│   │   ├── repositories/        # Data Access Layer (Spring Data JPA)
│   │   └── models/              # Entities & DTOs
│   │       ├── entities/        # JPA Entities (Asset, WorkOrder, v.v.)
│   │       └── dtos/            # Data Transfer Objects
│   └── src/main/resources/
│       ├── application.yml
│       └── db/migration/        # File SQL cho Flyway Migration (V1__init.sql,...)
│
├── web-portal/                  # React + Vite (Web cho Quản lý)
│   ├── package.json
│   ├── vite.config.ts
│   ├── src/
│   │   ├── app/                 # Config routing, Global Store (Zustand)
│   │   ├── components/          # Shared UI (AntD wrappers, Buttons, Layouts)
│   │   ├── features/            # Cấu trúc nhóm theo Module nghiệp vụ
│   │   │   ├── auth/            # Màn hình Login
│   │   │   ├── dashboard/       # Overview Supervisor
│   │   │   ├── assets/          # SplitPaneAssetExplorer
│   │   │   └── work-orders/     # Quản lý công việc
│   │   ├── hooks/               # Custom hooks
│   │   └── utils/               # Axios instance, Formatters
│   └── tests/
│
└── mobile-app/                  # Flutter (App cho Kỹ thuật viên)
    ├── pubspec.yaml
    ├── lib/
    │   ├── core/                # Theme, Utility, Sync Engine, API client
    │   │   ├── database/        # Cấu hình Drift DB & Local Tables
    │   │   └── network/         # Dio interceptors
    │   ├── features/            # Cấu trúc nhóm theo Module nghiệp vụ
    │   │   ├── auth/            # Login & Token storage
    │   │   ├── scanner/         # QR Scan-to-action logic
    │   │   ├── work_orders/     # SwipeableChecklistTile, Photo Upload
    │   │   └── sync/            # Offline status & Sync indicator
    │   └── main.dart
    └── test/
```

### Architectural Boundaries

**API Boundaries (Ranh giới giao tiếp):**
- **Ngoại vi:** Web Portal và Mobile App tuyệt đối không kết nối trực tiếp với Database. Mọi thao tác phải đi qua REST API của Backend (`/api/v1/*`).
- **Nội bộ Mobile:** Mobile App ưu tiên đọc/ghi vào Local Database (Drift) trước. Lớp `Sync Engine` sẽ chịu trách nhiệm giao tiếp ranh giới với Backend khi có mạng.

**Data Boundaries (Ranh giới dữ liệu):**
- **Tenant Isolation:** Ở Backend, lớp `Repository` là ranh giới sống còn. Mọi câu lệnh SQL đều phải tự động nối thêm `WHERE tenant_id = ?` thông qua Hibernate Filter hoặc Base Repository, controller không được phép xử lý logic phân tách dữ liệu. Ngoại lệ: Cần cấu hình bypass filter an toàn cho các API của Super Admin (ví dụ `/api/v1/system/tenants`).
- **Offline Storage:** Cơ sở dữ liệu Drift trên Mobile chỉ lưu dữ liệu **của duy nhất tenant hiện tại**. Bắt buộc áp dụng **Data Eviction (TTL)** (VD: xóa Work Order đã đóng quá 7 ngày) và định mức **Storage Quota** để tránh tràn bộ nhớ.
- **Initial Sync (First-load):** Khi tải cây tài sản khổng lồ lần đầu, API phải hỗ trợ Pagination (phân trang), Chunking hoặc nén Protobuf để ngăn OOM (Out of Memory) trên kết nối mạng yếu.
- **Sync Conflict Resolution:** Không sử dụng "last-write-wins". Mọi dữ liệu phải có Version Vectors (hoặc Timestamp + Dirty-flag). Khi có xung đột giữa Local và Server, hệ thống không tự ghi đè mà đánh dấu bản ghi là Conflict để Supervisor quyết định (Manual merge).

**Service Boundaries (Ranh giới dịch vụ):**
- Các module nghiệp vụ trong Backend (như `assets`, `work_orders`, `maintenance`) giao tiếp lỏng lẻo (loose coupling). Khi module `maintenance` đến hạn bảo trì, nó không gọi hàm tạo Work Order trực tiếp, mà bắn một Message vào **Kafka** (topic: `maintenance.triggered`). Module `work_orders` sẽ lắng nghe Kafka để sinh ra Work Order tự động.

### Requirements to Structure Mapping

**Epic/Feature Mapping:**
- **Epic Quản lý Tài sản (Asset Registry/Hierarchy):**
  - Backend: Gồm các class `AssetController`, `AssetService`, `AssetRepository` và `Asset` entity.
  - Web: `web-portal/src/features/assets/`
  - Database: `backend/src/main/resources/db/migration/` (Tạo bảng `assets` và dùng `ltree`).
- **Epic Quản lý Công việc & Kỹ thuật viên (Work Order):**
  - Backend: Gồm các class `WorkOrderController`, `WorkOrderService`, `WorkOrderRepository` và `WorkOrder` entity.
  - Mobile: `mobile-app/lib/features/work_orders/`
  - Web: `web-portal/src/features/work-orders/`

**Cross-Cutting Concerns:**
- **Offline Sync Engine:**
  - Mobile: `mobile-app/lib/core/database/` (hàng đợi sync) và `mobile-app/lib/features/sync/` (giao diện trạng thái).
- **Tenant Isolation & Security:**
  - Backend: `backend/src/main/java/com/eam/api/core/filters/` (TenantFilter) và `backend/src/main/java/com/eam/api/features/auth/`

### File Organization Patterns

- **Configuration Files:** Toàn bộ biến môi trường (Database credentials, JWT secret) nằm ở `.env` của thư mục gốc, được `docker-compose.yml` nhồi vào Backend. Web Portal có `.env.local` riêng chứa URL của API.
- **Test Organization:** Mobile (Flutter test) và Web (Vitest) nằm cùng thư mục gốc của nền tảng tương ứng. Backend có cấu trúc `/src/test/java/` được Spring Boot sinh sẵn để viết Unit/Integration Tests.

## Architecture Validation Results

### Coherence Validation ✅

**Decision Compatibility:**
Tất cả các công nghệ được chọn (Spring Boot 3.x, React 19/Vite, Flutter 3.x, PostgreSQL, Kafka) đều tương thích hoàn hảo. Cấu trúc micro-services thu nhỏ thông qua Docker Compose cung cấp một môi trường phát triển nhất quán và cô lập.

**Pattern Consistency:**
Các quy tắc đặt tên (`snake_case` cho DB, `PascalCase` cho Component, `kebab-case` cho API) và cấu trúc Feature-based hỗ trợ rất tốt cho quy mô dự án và cách ly các module nghiệp vụ, giúp nhiều AI agent code độc lập mà không dẫm chân lên nhau.

**Structure Alignment:**
Cấu trúc cây dự án phân chia rõ rệt 3 ứng dụng ở gốc dự án giúp ngăn chặn tuyệt đối tình trạng rò rỉ mã nguồn (code leakage) giữa các nền tảng.

### Requirements Coverage Validation ✅

**Epic/Feature Coverage:**
Toàn bộ các tính năng lớn (Asset Hierarchy, Work Order, Offline Sync) đều đã có khu vực riêng trong cấu trúc mã nguồn.

**Functional Requirements Coverage:**
Các tính năng hạch toán tài sản sâu đã được hỗ trợ mạnh mẽ bởi PostgreSQL (`ltree`), giúp xử lý FR về tìm kiếm và đệ quy hiệu quả.

**Non-Functional Requirements Coverage:**
- **Performance**: Phản hồi <500ms được đảm bảo nhờ in-memory cache của Spring Boot và query optimization.
- **Offline Reliability**: Đảm bảo bởi Drift Local Database trên Mobile.
- **Security/Tenant Isolation**: Đảm bảo thông qua bộ lọc bắt buộc (tenant filter) ở cấp độ Repository của Spring Boot.

### Implementation Readiness Validation ✅

**Decision Completeness:**
Các quyết định cốt lõi đã có đủ (Từ DB engine, Mobile Database, Web State Management cho đến Caching Strategy).

**Structure Completeness:**
Cấu trúc thư mục chi tiết đến từng feature cho cả 3 nền tảng đã sẵn sàng.

**Pattern Completeness:**
Các Anti-patterns và quy tắc xử lý lỗi (Global Exception Handler, Token Refresh) đã được thống nhất, đủ để bắt đầu triển khai ngay.

### Gap Analysis Results

- **Minor Gap (Thiết lập CI/CD):** Chúng ta chưa thiết lập kịch bản chi tiết cho CI/CD pipeline (như GitHub Actions). Tuy nhiên, điều này không chặn việc phát triển MVP ở môi trường local/dev và có thể dễ dàng được cấu hình sau.
- **Minor Gap (Sync Conflict Strategy):** Mặc dù đã có kiến trúc ngầm cho Sync Engine, cơ chế xử lý xung đột (Last-Write-Wins vs. Merge) cần được định nghĩa chi tiết ở logic mã nguồn lúc code tính năng Offline.

### Validation Issues Addressed

- Đã chủ động loại bỏ Redis để giảm thiểu độ phức tạp cho môi trường Docker Compose MVP, tránh việc Over-engineering.
- Thay thế SQflite bằng Drift để cấu trúc dữ liệu trên Mobile type-safe hơn, giảm rủi ro lỗi runtime khi truy vấn offline.
- Điều chỉnh cấu trúc Backend sang mô hình 3-Layer Architecture truyền thống để phù hợp hơn với định hướng của người dùng và các quy chuẩn Enterprise Java.

### Architecture Completeness Checklist

**Requirements Analysis**
- [x] Project context thoroughly analyzed
- [x] Scale and complexity assessed
- [x] Technical constraints identified
- [x] Cross-cutting concerns mapped

**Architectural Decisions**
- [x] Critical decisions documented with versions
- [x] Technology stack fully specified
- [x] Integration patterns defined
- [x] Performance considerations addressed

**Implementation Patterns**
- [x] Naming conventions established
- [x] Structure patterns defined
- [x] Communication patterns specified
- [x] Process patterns documented

**Project Structure**
- [x] Complete directory structure defined
- [x] Component boundaries established
- [x] Integration points mapped
- [x] Requirements to structure mapping complete

### Architecture Readiness Assessment

**Overall Status:** READY FOR IMPLEMENTATION
**Confidence Level:** High

**Key Strengths:**
- Tính nhất quán cao giữa 3 nền tảng nhờ sự phân chia thư mục rõ ràng.
- Nền tảng công nghệ mạnh mẽ, phù hợp tiêu chuẩn Enterprise SaaS.
- Đã lường trước và thiết kế giải pháp cho bài toán Offline-first phức tạp.

**Areas for Future Enhancement:**
- Post-MVP: Tích hợp Redis nếu tải đọc cây tài sản tăng cao.
- Thiết lập tự động hóa CI/CD cho Mobile (Fastlane) và Web/Backend.

### Implementation Handoff

**AI Agent Guidelines:**
- Tuân thủ tuyệt đối cấu trúc thư mục và quy tắc định dạng trong tài liệu này.
- Mọi thắc mắc về phân định ranh giới (Ví dụ: "Logic này nên để ở Mobile hay Backend?") đều phải ưu tiên cho Backend xử lý (Fat-backend, Thin-client) trừ khi liên quan đến Offline Sync.

**First Implementation Priority:**
```bash
# Thực hiện các câu lệnh khởi tạo từ các Starter CLI cho Web, Backend và Mobile.
```

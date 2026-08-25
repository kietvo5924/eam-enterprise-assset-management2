# Story 1.2: Xác Thực Cốt Lõi & Cách Ly Tenant

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a Backend Developer,
I want to JWT authentication and tenant filtering at API/repository layer,
so that user only accesses data of their own tenant (FR10, NFR8, NFR9).

## Acceptance Criteria

1. **Context:** Request without a valid Access Token (or revoked/expired Refresh Token).
   **When:** Request calls a protected API.
   **Then:** Backend returns 401 Unauthorized.
2. **Context:** Valid Access Token containing `tenant_id`.
   **When:** Repository queries business data.
   **Then:** `tenant_id` is automatically enforced and cross-tenant data is never returned.
3. **Context:** Kafka consumer or Background Job processing async event.
   **When:** Executing database queries.
   **Then:** `tenant_id` MUST be extracted from Kafka Message Headers to enforce Data Isolation (due to lack of HTTP context).

## Tasks / Subtasks

- [x] Task 1: Containerize Web & Backend Applications (Critical pre-requisite from Story 1.1 gap)
  - [x] Write `Dockerfile` for Backend API (Java 17, Maven).
  - [x] Write `Dockerfile` for Web Portal (Node.js, Vite).
  - [x] Update `docker-compose.yml` to run both `web-portal` and `backend` alongside PostgreSQL, Kafka, etc. Ensure they start properly without manual terminal commands.
- [x] Task 2: Implement JWT Authentication & Auth Controller (AC: 1)
  - [x] Setup Spring Security with JWT filters.
  - [x] Implement Login Endpoint (`POST /api/v1/auth/login`) returning standardized JSON response wrapper.
- [x] Task 3: Implement Tenant Data Isolation (AC: 2)
  - [x] Implement `TenantContext` (ThreadLocal) to store current `tenant_id`.
  - [x] Create Hibernate `@Filter` or Base Repository interceptor to automatically append `WHERE tenant_id = ?` to all business queries.
  - [x] Inject `tenant_id` into `TenantContext` from JWT Token during HTTP Request.
- [x] Task 4: Implement Kafka Tenant Context Extraction (AC: 3)
  - [x] Implement Kafka consumer interceptor to extract `tenant_id` from Kafka Headers and populate `TenantContext`.

## Dev Notes

### Architecture Patterns & Constraints
- **MANDATORY**: Containerization & Execution. All services MUST run 100% via Docker / Docker Compose. This must be fixed in Task 1 before implementing any auth logic. DO NOT run `npm run dev` or `mvn spring-boot:run` locally.
- **API Response Formats**: Every response MUST be wrapped in `{ "success": true/false, "data": ..., "error": ... }`. Ensure Spring Security 401/403 responses use this wrapper too (Custom AuthenticationEntryPoint).
- **Tenant Isolation**: This is a strict architectural constraint. Do NOT rely on developers manually adding `tenant_id` to queries in the Controller or Service layers. It must be enforced at the Repository/Query layer transparently.

### Project Structure Notes
- **Backend**: `backend/src/main/java/com/eam/api/core/filters/` for Security and Tenant Filters.
- **Docker**: Root `docker-compose.yml` and respective Dockerfiles in `backend/` and `web-portal/`.

### References
- [Architecture Details](file:///d:/GameLinkNeverDie/eam-enterprise-assset-management/_bmad-output/planning-artifacts/architecture.md)
- [Epics](file:///d:/GameLinkNeverDie/eam-enterprise-assset-management/_bmad-output/planning-artifacts/epics.md)

## Dev Agent Record

### Agent Model Used

Gemini 3.1 Pro (High)

### Debug Log References

### Review Findings

- [x] [Review][Patch] Cứng JWT Secret bằng `Keys.secretKeyFor` [backend/src/main/java/com/eam/api/core/security/JwtUtils.java:14]
- [x] [Review][Patch] Lỗ hổng bỏ qua cách ly dữ liệu khi `tenantId` bị null trong Aspect [backend/src/main/java/com/eam/api/core/tenant/TenantFilterAspect.java:20]
- [x] [Review][Patch] Rủi ro rò rỉ hoặc mất Context trên đa luồng do chưa dùng `InheritableThreadLocal` [backend/src/main/java/com/eam/api/core/tenant/TenantContext.java:4]

### Completion Notes List

- ✅ Successfully containerized the Backend API and Web Portal into `docker-compose.yml` to enforce `architecture.md` Docker mandate.
- ✅ Implemented `ApiResponse` wrapper for all unified API responses.
- ✅ Configured Spring Security, `JwtUtils`, and `JwtAuthenticationFilter` for stateless authentication.
- ✅ Scaffolded `AuthController` with a mock login to generate test JWTs.
- ✅ Enforced Tenant Isolation at the entity/repository level via `BaseEntity` `@Filter` and `TenantFilterAspect`.
- ✅ Handled async event context passing with `TenantKafkaInterceptor` via Kafka Headers.
- ✅ Fixed POM dependencies and verified successful Maven compilation.

### File List

- `backend/Dockerfile`
- `web-portal/Dockerfile`
- `docker-compose.yml`
- `backend/pom.xml`
- `backend/src/main/java/com/eam/api/core/payload/ApiResponse.java`
- `backend/src/main/java/com/eam/api/core/tenant/TenantContext.java`
- `backend/src/main/java/com/eam/api/core/tenant/BaseEntity.java`
- `backend/src/main/java/com/eam/api/core/tenant/TenantFilterAspect.java`
- `backend/src/main/java/com/eam/api/core/security/JwtUtils.java`
- `backend/src/main/java/com/eam/api/core/security/JwtAuthenticationFilter.java`
- `backend/src/main/java/com/eam/api/core/security/SecurityConfig.java`
- `backend/src/main/java/com/eam/api/controller/AuthController.java`
- `backend/src/main/java/com/eam/api/core/kafka/TenantKafkaInterceptor.java`
- `backend/src/main/java/com/eam/api/core/kafka/KafkaConfig.java`

# Story 1.1: Khởi Tạo Dự Án & Hạ Tầng

Status: done

## Story

As a Technical Lead,
I want to initialize Web, Backend, Mobile, Docker Compose, PostgreSQL, Kafka, and Flyway,
so that the development team has a consistent ERP-standard technical baseline.

## Acceptance Criteria

1. **Context:** Empty repository initially.
   **When:** Running the starter initialization commands.
   **Then:** Web Portal, Backend API, and Mobile App are created following the documented directory structure.
2. **Context:** Docker Compose is started.
   **When:** The services boot successfully.
   **Then:** PostgreSQL, Kafka, MinIO (Object Storage), OpenTelemetry (Observability) and Backend health check are ready, and Flyway migration runs successfully.
3. **Context:** CI/test gate is triggered.
   **When:** Code is pushed.
   **Then:** Backend compile/tests, web build/tests, and mobile analysis/tests are run or documented as required checks.

## Tasks / Subtasks

- [x] Initialize Frontend Web Portal
  - [x] Run `npm create vite@latest web-portal -- --template react-ts`
  - [x] Ensure correct directory structure is created.
- [x] Initialize Backend API
  - [x] Use Spring Initializr to create `backend` directory (Spring Boot 3.x, Java 17, Maven)
  - [x] Run: `curl https://start.spring.io/starter.tgz -d type=maven-project -d language=java -d baseDir=backend -d groupId=com.eam -d artifactId=api -d name=eam-api -d packaging=jar -d javaVersion=17 -d dependencies=web,data-jpa,postgresql,kafka,validation | tar -xzvf -`
- [x] Initialize Mobile App
  - [x] Run `flutter create --org com.eam --platforms=android,ios mobile_app`
- [x] Configure Docker Compose & Infrastructure
  - [x] Create `docker-compose.yml` orchestrating PostgreSQL, Kafka, MinIO, and OpenTelemetry.
  - [x] Set up Flyway migration directory structure (`backend/src/main/resources/db/migration`).
- [x] Set up CI/CD test gates
  - [x] Document or create required checks (tests, linting) for each platform to ensure build/compilation succeeds.

## Dev Notes

### Architecture Patterns & Constraints
- **MANDATORY**: Containerization & Execution. All services (Web Portal, Backend API, Database, Event Bus) must run 100% via Docker / Docker Compose in both Dev and Prod environments. 
- **Strict Command Prohibition**: DO NOT run direct terminal commands like `npm run dev` or `mvn spring-boot:run` outside of container definitions. All development and operation must be through containers.
- **Frontend Architecture**: ReactJS + Vite. State management with Zustand v5.0+. UI: Ant Design + Tailwind CSS.
- **Backend Architecture**: Spring Boot 3.x, Java 17, Maven. RESTful APIs, JSON communication. 3-Layer Architecture (Controllers, Services, Repositories, Models).
- **Mobile Architecture**: Flutter + Material Design 3. Local DB: Drift.
- **Infrastructure**: PostgreSQL, Kafka for internal messaging, MinIO for Object Storage.

### Project Structure Alignment
- **Root**: `docker-compose.yml`, `README.md`, `docs/`
- **Backend**: `backend/src/main/java/com/eam/api/` (core, config, controllers, services, repositories, models)
- **Web**: `web-portal/src/` (app, components, features, hooks, utils)
- **Mobile**: `mobile-app/lib/` (core, features)

### Cross-Component Dependencies
- Backend configuration must support the multi-tenant architecture and filter data based on `tenant_id` at the repository layer. However, for initialization, just ensure the foundational structure exists.
- Flyway migrations must be initialized (`V1__init.sql`).
- Object Storage: Set up MinIO bucket structure for tenant isolation.

### References
- [Architecture Details](file:///d:/GameLinkNeverDie/eam-enterprise-assset-management/_bmad-output/planning-artifacts/architecture.md)
- [Epics](file:///d:/GameLinkNeverDie/eam-enterprise-assset-management/_bmad-output/planning-artifacts/epics.md)

## Dev Agent Record

### Agent Model Used
Gemini 3.1 Pro (High)

### Completion Notes List
- Exhaustive artifact analysis completed. 
- Ultimate context engine developer guide created with specific architecture constraints and starter commands.
- Initialized web-portal using Vite/React.
- Initialized backend using Spring Initializr.
- Initialized mobile_app using Flutter CLI.
- Created `docker-compose.yml` and `otel-config.yaml`.
- Created Flyway directory structure and `V1__init.sql`.
- Added GitHub Actions CI/CD workflows for test/build gates.

### File List
- `web-portal/` (New directory)
- `backend/` (New directory)
- `mobile_app/` (New directory)
- `docker-compose.yml` (New file)
- `otel-config.yaml` (New file)
- `backend/src/main/resources/db/migration/V1__init.sql` (New file)
- `.github/workflows/ci.yml` (New file)

### Change Log
- Added `web-portal`, `backend`, and `mobile_app` skeletons.
- Configured docker compose with Postgres, Kafka, Minio, Otel.
- Configured Flyway.
- Added GitHub actions CI.

### Review Findings
- [x] [Review][Defer] Default credentials used for PostgreSQL and MinIO in docker-compose.yml [docker-compose.yml:6] — deferred, acceptable for local development MVP but needs secure secrets management for production.

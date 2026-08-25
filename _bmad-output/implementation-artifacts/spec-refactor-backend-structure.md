---
title: 'Refactor Backend Structure'
type: 'refactor'
created: '2026-05-29'
status: 'done'
baseline_commit: '3bec15c4d6f0a092e787842f42fbf8c7dc0f8ff8'
context: 
  - '_bmad-output/planning-artifacts/architecture.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The current backend directory structure deviates from the planned architecture. Specifically, we have a redundant `controller` folder alongside `controllers`, and a `payload/request` folder when all DTOs should reside in `models/dtos`.

**Approach:** Move all files from `controller` to `controllers` and from `payload/request` to `models/dtos`. Delete the now-empty `controller` and `payload` folders. Finally, update all package declarations and imports across the backend source code to match the new paths.

## Boundaries & Constraints

**Always:** 
- Maintain exact file contents (classes, methods, logic) during the move; only modify `package` and `import` statements.
- Ensure the backend compiles successfully after refactoring.

**Ask First:** 
- If resolving an import conflict results in unexpected compilation errors.

**Never:** 
- Refactor or change the business logic of any controller or DTO during this process.
- Modify the frontend codebase, except if a backend endpoint path changes (which should not happen).

</frozen-after-approval>

## Code Map

- `backend/src/main/java/com/eam/api/controller/` -- Source folder for controllers to be moved.
- `backend/src/main/java/com/eam/api/controllers/` -- Target folder for controllers.
- `backend/src/main/java/com/eam/api/payload/request/` -- Source folder for request payloads to be moved.
- `backend/src/main/java/com/eam/api/models/dtos/` -- Target folder for request payloads.
- `backend/src/main/java/com/eam/api/` -- Root namespace containing usages of the moved classes (services, configuration, tests) requiring import updates.

## Tasks & Acceptance

**Execution:**
- [x] `backend/src/main/java/com/eam/api/controller/` -- Move all Java files to `backend/src/main/java/com/eam/api/controllers/`.
- [x] `backend/src/main/java/com/eam/api/payload/request/` -- Move all Java files to `backend/src/main/java/com/eam/api/models/dtos/`.
- [x] `backend/src/main/java/com/eam/api/controller/` & `backend/src/main/java/com/eam/api/payload/` -- Delete these empty directories.
- [x] `backend/src/main/java/com/eam/api/controllers/*.java` -- Update package declarations to `package com.eam.api.controllers;`.
- [x] `backend/src/main/java/com/eam/api/models/dtos/*.java` -- Update package declarations to `package com.eam.api.models.dtos;`.
- [x] `backend/src/main/java/com/eam/api/` (all files) -- Search and replace imports of `com.eam.api.controller.*` with `com.eam.api.controllers.*` and `com.eam.api.payload.request.*` with `com.eam.api.models.dtos.*`.

**Acceptance Criteria:**
- Given the backend codebase, when compiled with Maven (`mvn clean compile`), then it must compile without any `package does not exist` or `cannot find symbol` errors related to the moved classes.
- Given the project directory, when inspected, then the `controller` and `payload` folders must no longer exist.

## Verification

**Commands:**
- `cd backend && mvn clean compile` -- expected: BUILD SUCCESS

## Suggested Review Order

**Package Migration - Controllers**

- Moved AuthController to `controllers` package.
  [`AuthController.java:1`](../../backend/src/main/java/com/eam/api/controllers/AuthController.java#L1)

- Moved UserController to `controllers` package.
  [`UserController.java:1`](../../backend/src/main/java/com/eam/api/controllers/UserController.java#L1)

**Package Migration - DTOs**

- Moved SystemTenantCreateRequest to `models.dtos` package.
  [`SystemTenantCreateRequest.java:1`](../../backend/src/main/java/com/eam/api/models/dtos/SystemTenantCreateRequest.java#L1)

- Moved SystemTenantAdminRequest to `models.dtos` package.
  [`SystemTenantAdminRequest.java:1`](../../backend/src/main/java/com/eam/api/models/dtos/SystemTenantAdminRequest.java#L1)

**Import Updates**

- Updated DTO imports in SystemTenantService.
  [`SystemTenantService.java:6`](../../backend/src/main/java/com/eam/api/services/SystemTenantService.java#L6)

- Updated DTO imports in SystemTenantController.
  [`SystemTenantController.java:6`](../../backend/src/main/java/com/eam/api/controllers/system/SystemTenantController.java#L6)

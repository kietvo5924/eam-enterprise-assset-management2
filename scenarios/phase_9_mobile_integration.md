# Phase 9 — EAM Mobile App Parity & Integration (Backend API Focus)

This document outlines the detailed breakdown and checklist for ensuring the new Django backend provides complete API parity for the existing Flutter mobile app. 
**The goal is that the Flutter codebase requires NO CHANGES other than updating the base URL.**

## 9.1 — Mobile API Routing & Structure Parity
Ensure all API routes requested by the Flutter app are supported by the Django backend.

- [ ] **Task 9.1.1 — Audit Flutter API Calls**
  - Search the Flutter source code for all HTTP request paths.
  - Map them to the legacy backend's endpoints.
- [ ] **Task 9.1.2 — Update Django `urls.py`**
  - If the Flutter app expects routes like `/api/v1/mobile/login` or `/api/v1/work-orders/sync`, ensure Django exposes these exact routes.
  - Add specific mobile namespaces if necessary to avoid conflicting with the web portal.

## 9.2 — Mobile Authentication & Token JSON Parity
The mobile app's authentication heavily relies on specific JSON structures for parsing and storing tokens.

- [ ] **Task 9.2.1 — JWT Login Response Parity**
  - Verify if Flutter expects `{ "accessToken": "...", "refreshToken": "..." }` or `{ "access": "...", "refresh": "..." }`.
  - Ensure the user profile object returned upon login matches exactly what Flutter's data model expects.
- [ ] **Task 9.2.2 — Token Refresh Endpoint**
  - Ensure the refresh token endpoint URL matches.
  - Ensure the request body and response payload match the legacy system.
- [ ] **Task 9.2.3 — Change Password API**
  - Verify the mobile Change Password request format and ensure Django accepts it and returns the expected success/error JSON.

## 9.3 — Work Order & Checklists Sync API Parity
The core of the mobile app. The JSON schemas must match the Flutter data classes exactly.

- [ ] **Task 9.3.1 — Work Order List Payload**
  - Audit the JSON response for the Work Order list API.
  - Ensure all fields (e.g., `assignedTo`, `priority`, `status`, nested `asset` objects) use the correct naming conventions (camelCase vs snake_case).
- [ ] **Task 9.3.2 — Checklist Schemas**
  - Audit the JSON response for fetching a checklist.
  - Audit the JSON request body expected by the backend when the mobile app submits a checklist. Ensure Django can parse it correctly.
- [ ] **Task 9.3.3 — Status Transition API**
  - Ensure the mobile API for changing a Work Order status (e.g., `IN_PROGRESS` -> `COMPLETED`) matches the expected request format and returns the correct response.

## 9.4 — Offline Sync Engine API Support
The mobile app likely uses a bulk sync or queue mechanism to upload offline data when network is restored.

- [ ] **Task 9.4.1 — Analyze Offline Sync Behavior**
  - Review how the Flutter app sends offline data (e.g., batch endpoint or multiple individual requests).
- [ ] **Task 9.4.2 — Implement Batch/Sync Endpoints**
  - If a batch endpoint was used in the legacy system, ensure Django has a corresponding endpoint that can parse the batch JSON and process the changes atomically.
- [ ] **Task 9.4.3 — MinIO Attachment API**
  - Verify the multipart/form-data upload API for photos/signatures.
  - Ensure the Django response includes the URL/ID in the exact format Flutter expects.

## 9.5 — E2E Verification via Mobile Emulator
Final testing to prove the backend parity.

- [ ] **Task 9.5.1 — Configure Flutter Emulator**
  - Change `api_constants.dart` (or equivalent `.env`) to point to the local Django server (`10.0.2.2:8000` for Android emulator).
- [ ] **Task 9.5.2 — Run Workflows**
  - Run the Flutter app and go through a complete technician daily flow.
  - Verify Login, Syncing, Executing Work Orders, and Offline mode function flawlessly *without modifying any Flutter code*.

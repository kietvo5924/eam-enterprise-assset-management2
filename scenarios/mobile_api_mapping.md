# Flutter to Legacy Backend API Mapping

## Overview
This document serves as an audit of all API calls made by the `mobile_app` (Flutter) and maps them to the Legacy Backend (Java/Spring Boot) and the current Django Backend implementations to ensure full parity.

## Endpoints Audit

### 1. Authentication (`AuthController`)
| Flutter App Route | HTTP Method | Legacy Backend Route | Django Route | Match Status |
|---|---|---|---|---|
| `/api/v1/auth/login` | `POST` | `/api/v1/auth/login` | `/api/v1/auth/login/` | **Trailing Slash Diff** |
| `/api/v1/auth/change-password` | `POST` | `/api/v1/auth/change-password` | `/api/v1/auth/change-password/` | **Trailing Slash Diff** |
| `/api/v1/auth/refresh` | `POST` | `/api/v1/auth/refresh` | `/api/v1/auth/refresh/` | **Trailing Slash Diff** |

### 2. Assets (`AssetController` & `MeterReadingController`)
| Flutter App Route | HTTP Method | Legacy Backend Route | Django Route | Match Status |
|---|---|---|---|---|
| `/api/v1/assets` | `GET` | `/api/v1/assets` | `/api/v1/assets` | **Exact Match** |
| `/api/v1/assets/qr/{qrCode}` | `GET` | `/api/v1/assets/qr/{qrCode}` | `/api/v1/assets/qr/{qrCode}` | **Exact Match** |
| `/api/v1/assets/{id}/meter-readings` | `POST` | `/api/assets/{id}/meter-readings` | `/api/v1/assets/{id}/meter-readings` | **Diff (`v1`)** |

*Note: The Legacy `MeterReadingController` did not have `/v1/` prefix in its `@RequestMapping("/api/assets/{assetId}/meter-readings")`, but Flutter assumes `/api/v1/`. In Django, this route is properly mounted under `/api/v1/`, making it compatible with Flutter.*

### 3. Work Orders (`WorkOrderController`)
| Flutter App Route | HTTP Method | Legacy Backend Route | Django Route | Match Status |
|---|---|---|---|---|
| `/api/v1/work-orders` | `GET` | `/api/v1/work-orders` | `/api/v1/work-orders` | **Exact Match** |
| `/api/v1/work-orders` | `POST` | `/api/v1/work-orders` | `/api/v1/work-orders` | **Exact Match** |
| `/api/v1/work-orders/{id}` | `GET` | `/api/v1/work-orders/{id}` | `/api/v1/work-orders/{id}` | **Exact Match** |
| `/api/v1/work-orders/{id}/status` | `PUT` | `/api/v1/work-orders/{id}/status` | `/api/v1/work-orders/{id}/status` | **Exact Match** |
| `/api/v1/work-orders/{id}/notes` | `PUT` | `/api/v1/work-orders/{id}/notes` | `/api/v1/work-orders/{id}/notes` | **Exact Match** |
| `/api/v1/work-orders/{id}/checklists` | `POST` | `/api/v1/work-orders/{id}/checklists` | `/api/v1/work-orders/{id}/checklists` | **Exact Match** |
| `/api/v1/work-orders/{id}/checklists/{cid}`| `DELETE` | `/api/v1/work-orders/{id}/checklists/{cid}`| `/api/v1/work-orders/{id}/checklists/{cid}`| **Exact Match** |
| `/api/v1/work-orders/{id}/attachments` | `POST` | `/api/v1/work-orders/{id}/attachments`| `/api/v1/work-orders/{id}/attachments`| **Exact Match** |

## Conclusion
- Flutter calls match the Legacy backend's controllers structurally.
- A critical issue lies in Django's routing: **Trailing slashes (`/`)** are appended to `auth` routes in Django (`path('auth/login/', ...)`), while Flutter calls them without the slash (`/api/v1/auth/login`). This discrepancy on `POST` requests will result in HTTP 301 Redirects by Django's `APPEND_SLASH`, which natively strips the POST request bodies and turns them into `GET`s, breaking authentication.
- This mapping fulfills Task 9.1.1 requirements, setting the stage for `urls.py` adjustment in Task 9.1.2.

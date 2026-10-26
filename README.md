# Enterprise Asset Management (EAM) System

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-5.2%20LTS-green.svg)](https://www.djangoproject.com/)
[![Flutter](https://img.shields.io/badge/Flutter-3.x-02569B.svg)](https://flutter.dev/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-336791.svg)](https://www.postgresql.org/)
[![MinIO](https://img.shields.io/badge/MinIO-S3%20Storage-C72C48.svg)](https://min.io/)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D.svg)](https://redis.io/)

A modern, multi-tenant **Enterprise Asset Management (EAM / CMMS)** platform designed for industrial manufacturing, logistics, and plant operations. Built with a full-stack **Django monolith**, an **offline-first Flutter mobile application**, and containerized infrastructure.

> **Architecture Modernization**: This system has been consolidated from a legacy distributed stack into a unified, high-performance Django monolith with a Flutter mobile client, dramatically simplifying deployment, reducing operational overhead, and enhancing system reliability.

---

## 🌟 Key Features & Capabilities

### 1. Multi-Tenant Architecture & Granular RBAC
- Complete data isolation per organization/tenant (`TenantMiddleware`).
- Strict Role-Based Access Control:
  - **Super Administrator (`SUPER_ADMIN`)**: Global system management, tenant lifecycle, cross-tenant licensing.
  - **Tenant Administrator (`TENANT_ADMIN`)**: Organization configuration, factory layout, user & role provisioning, AI governance toggles.
  - **Maintenance Manager / Supervisor**: Planning, resource allocation, tool & spare parts approvals.
  - **Field Technician (`TECHNICIAN` / `FIELD_TECHNICIAN`)**: Work order execution, checklist inspection, on-site measurements, direct camera proof upload.
  - **Viewer**: Read-only dashboard and operational KPI monitoring.

### 2. Intelligent Work Order Management
- **Interactive Checklists**: Multi-type inspection steps (`PASS_FAIL`, `NUMBER`, `TEXT`).
- **Real-Time Measurement Validation**: Strict validation on numeric measurements (temperature, vibration, pressure, etc.) preventing incomplete submissions.
- **Mandatory Live Photo Proof**: Strict hardware camera requirement (`ImageSource.camera`) for technicians at machine sites.
- **Automated Resource Lifecycle**: Automatic check-out/check-in of reserved tools (`ToolReservation`) and inventory spare parts stock adjustment on completion or cancellation.

### 3. AI Algorithm Governance & Safe Fallbacks (Trung Tâm Quản Trị Thuật Toán AI)
Each organization/tenant has full granular control to enable or temporarily disable 6 advanced operations research and machine learning algorithms with automated defensive safe fallbacks:
- **Hungarian Algorithm Dispatcher**: Optimal assignment of pending work orders to technicians based on skill levels, certifications, and location. *When disabled: Falls back cleanly to Manual Dispatch mode.*
- **Genetic Algorithm (GA) Scheduler**: Multi-day NP-hard Pareto optimization distributing work orders across shifts and teams. *When disabled: Falls back to sequential calendar-based preventive maintenance (Calendar PM).*
- **Predictive Remaining Useful Life (RUL)**: Weibull distribution degradation modeling with 95% uncertainty bands for failure prediction. *When disabled: Falls back to cumulative runtime hours or calendar thresholds.*
- **Real-Time Sensor Anomaly Detection**: ISO 10816 vibration standards, Theil-Sen robust drift regression, and Isolation Forest. Automatically generates emergency Work Orders. *When disabled: Evaluates static min/max thresholds only, skipping automated AI WO generation.*
- **2D CAD Floorplan & TSP Routing**: Traveling Salesperson Problem (ATTSP) navigating technicians via stairs and corridors between factory floors. *When disabled: Falls back to pure business priority sequencing.*
- **Maintenance Cost Forecasting**: Time-series predictive models for labor and material cost projections. *When disabled: Displays historical actual invoiced expenses.*

### 4. Enterprise Personalization & Multilingual Experience
- **Personalized Multi-Palette Themes**: 5 curated enterprise themes (**EAM Cyan**, **Emerald**, **Navy Blue**, **Indigo**, **Amber**) customizable directly from the header dropdown, persistently synchronized with each user profile (`User.theme_color`) and runtime Tailwind CSS variables.
- **Client-Side Multilingual Engine**: Seamless in-place UI translation powered by Google Translate client engine (Vietnamese, English, Japanese, Korean, Chinese, German, etc.) without requiring hardcoded per-string translations.

### 5. Fault-Tolerant Storage & Auto-Sync Engine
- **Resilient Media Storage**: S3-compatible MinIO object storage with automatic graceful fallback to Django `default_storage` upon network timeouts or storage unavailability.
- **Background Auto-Sync & Local Purge**: Scheduled Celery background task (`core.tasks.sync_and_purge_local_fallback_files`) that automatically reconciles fallback files to MinIO and safely cleans local disk storage once remote storage connectivity is restored.

### 6. Offline-First Mobile Application (Flutter)
- Built for on-the-ground technicians in network-challenged industrial facilities.
- **Local Embedded Database**: Drift (SQLite) storing work orders, checklists, and asset telemetry locally.
- **Robust Background Sync Engine**: Automatic queue processing, conflict handling, deterministic error management, and tenant data isolation.

---

## 🛠 Technology Stack

| Layer | Technologies |
| :--- | :--- |
| **Backend & Core** | Python 3.11+, Django 5.2 LTS, Django REST Framework, SimpleJWT, Celery |
| **Algorithms & AI** | NumPy, SciPy, Scikit-learn (Isolation Forest, Theil-Sen, Hungarian algorithm) |
| **Web Frontend** | Django Templates, TailwindCSS, Phosphor Icons, Modern Vanilla JavaScript |
| **Mobile Client** | Flutter 3.x, Dart, Dio, Provider, GoRouter, Drift (SQLite), ImagePicker |
| **Data Storage & Cache** | PostgreSQL 15, Redis 7 (Cache & Task Broker), MinIO (S3-compatible Object Storage) |
| **Database Tooling** | pgAdmin 4 |
| **Testing Framework** | Pytest, Microsoft Playwright (E2E), Django Test Runner, Flutter Test |
| **Containerization** | Docker, Docker Compose |

---

## 📁 Repository Structure

```text
eam-enterprise-assset-management/
├── docker-compose.yml          # Container configuration (PostgreSQL, Redis, MinIO, pgAdmin)
├── requirements.txt            # Python dependencies for backend and testing
├── .env.example                # Template for environment variables
├── TEST_CREDENTIALS.md         # Comprehensive test credentials and tenant directory
├── docs/                       # Architectural specs, migration guides, and idea documentation
├── eam_app/                    # Core Django Backend Monolith
│   ├── manage.py               # Django management CLI
│   ├── config/                 # Settings, ASGI/WSGI, routing configurations
│   ├── core/                   # Multi-tenant middleware, audit logging, base models
│   ├── users/                  # Custom User model, technician profiles, RBAC
│   ├── assets/                 # Asset hierarchy, sensors, tool reservations, spare parts
│   ├── workorders/             # Work order lifecycle, checklists, attachments, dispatch
│   ├── maintenance/            # Preventive maintenance schedules, PM triggers
│   ├── algorithms/             # Anomaly detection, Hungarian dispatch, TSP routing
│   ├── portal/                 # Web views, dashboards, CAD floorplan maps
│   ├── templates/              # Server-rendered HTML templates with TailwindCSS
│   └── static/                 # Static assets, JavaScript utilities, stylesheets
├── mobile_app/                 # Offline-First Flutter Mobile App
│   ├── lib/
│   │   ├── core/               # Theme, database (Drift), network (Dio), security
│   │   ├── features/           # Work orders, sync engine, CAD routing, auth, dashboard
│   └── test/                   # Flutter unit and widget tests
└── e2e_tests/                  # End-to-End Playwright test suite
```

---

## 🚀 Getting Started (Step-by-Step)

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Docker Compose v2+)
- [Python 3.11+](https://www.python.org/downloads/)
- [Flutter SDK 3.x+](https://docs.flutter.dev/get-started/install) *(if developing on the mobile app)*
- [Git](https://git-scm.com/)

---

### Step 1: Clone Repository & Configure Environment

```bash
# Clone the repository
git clone https://github.com/kietvo5924/eam-enterprise-assset-management2.git
cd eam-enterprise-assset-management

# Copy environment variable template
# On Windows (PowerShell):
Copy-Item .env.example -Destination .env
Copy-Item .env.example -Destination eam_app\.env

# On Linux / macOS:
cp .env.example .env
cp .env.example eam_app/.env
```

Open `.env` (and `eam_app/.env`) to configure optional external services (such as `RESEND_API_KEY` for email notifications).

---

### Step 2: Launch Supporting Infrastructure via Docker

Start PostgreSQL, Redis, MinIO, and pgAdmin in detached mode:

```bash
docker-compose up -d
```

Verify that all containers are healthy:
```bash
docker-compose ps
```

---

### Step 3: Set Up Python Virtual Environment

Create and activate a virtual environment, then install dependencies:

```bash
# Create Virtual Environment
python -m venv venv

# Activate (Windows PowerShell):
.\venv\Scripts\activate

# Activate (Linux / macOS):
source venv/bin/activate

# Install all backend and testing dependencies
pip install -r requirements.txt
```

---

### Step 4: Apply Database Migrations & Seed Demo Data

Navigate into the `eam_app` directory to execute Django management commands:

```bash
cd eam_app

# Run database schema migrations
python manage.py migrate

# Seed comprehensive factory, asset, technician, and work order demo data
python manage.py seed_hungarian_demo
```

---

### Step 5: Start the Django Backend Server

```bash
# Run server on all network interfaces (accessible to mobile emulators and LAN)
python manage.py runserver 0.0.0.0:8000
```

The web application is now active at **http://localhost:8000**.

---

## 🌐 Service Endpoints & Default Credentials

| Service | Access URL | Credentials | Notes |
| :--- | :--- | :--- | :--- |
| **EAM Web Portal** | `http://localhost:8000` | Username: `superadmin@eam.local`<br>Password: `admin123` | Global System Super Admin (`SUPER_ADMIN`) |
| **VinFast Tenant Admin** | `http://localhost:8000` | Username: `admin_vf@vinfast.vn`<br>Password: `password123` | Factory Tenant Admin (`VF_MFG`) |
| **Field Technician** | Mobile App / Web | Username: `Le Thi Hoa`<br>Password: `admin123` | Field maintenance technician |
| **pgAdmin 4 (Web UI)** | `http://localhost:5050` | Email: `admin@admin.com`<br>Password: `admin` | Web-based PostgreSQL browser |
| **MinIO Console** | `http://localhost:9001` | Username: `minioadmin`<br>Password: `minioadmin` | Object storage browser (Host S3 API: `http://localhost:9900`, mapped to internal port `9000`) |
| **PostgreSQL Database** | `localhost:5433` | User: `eam_user`<br>Password: `eam_password`<br>DB: `eam_db` | Direct host connection (internal port: `5432`) |

> 📖 **Full Credentials Directory**: For a comprehensive table of all 20+ specialized technician accounts (electrical, hydraulic, PLC, robotics) and managers across all organizations, see **[TEST_CREDENTIALS.md](TEST_CREDENTIALS.md)**.

### Connecting pgAdmin to PostgreSQL:
When adding a new server in pgAdmin (`http://localhost:5050`):
- **Host name/address**: `postgres` *(inside Docker container network)*
- **Port**: `5432`
- **Maintenance database**: `eam_db`
- **Username**: `eam_user`
- **Password**: `eam_password`

*(Note: When connecting from desktop SQL tools like DBeaver or DataGrip on your host machine, use Host: `localhost` and Port: `5433`)*.

---

## 📱 Running the Mobile Application (Flutter)

The mobile application is located in `mobile_app/` and supports Android and iOS.

1. Ensure the backend server is running (`python manage.py runserver 0.0.0.0:8000`).
2. Open a separate terminal and navigate to the mobile folder:
   ```bash
   cd mobile_app
   ```
3. Fetch Flutter packages:
   ```bash
   flutter pub get
   ```
4. Run on a connected device or Android Emulator:
   ```bash
   flutter run
   ```

> **Network Note for Emulators**:
> - **Android Emulator**: Automatically routes to the host machine backend via `http://10.0.2.2:8000`.
> - **iOS Simulator**: Connects directly via `http://localhost:8000`.
> - **Physical Devices**: Configure the server IP address to match your computer's local Wi-Fi LAN IP in `mobile_app/lib/core/constants/api_constants.dart`.

---

## 🧪 Testing Suite

### 1. Backend Unit & Integration Tests
```bash
cd eam_app

# Run all work orders tests
python manage.py test workorders.tests

# Run AI algorithm governance toggles & defensive safe fallbacks
python manage.py test algorithms.tests.test_ai_governance_toggles

# Run fault-tolerant file upload & user preferences tests
python manage.py test core.tests.test_upload_and_preferences

# Run sensor anomaly detection & algorithm tests
pytest algorithms/tests/ -v
```

### 2. End-to-End (E2E) Browser Tests (Playwright)
```bash
# From project root with virtual environment activated:
pytest -v e2e_tests

# If running Playwright for the first time:
playwright install chromium
```

### 3. Flutter Mobile Unit Tests
```bash
cd mobile_app
flutter test
```

---

## 🔧 Common Troubleshooting

1. **Port Conflicts (`5433`, `5050`, `6379`, `8000`, `9001`)**
   - Check if existing services or old Docker containers are occupying the ports:
     ```bash
     docker ps
     ```
   - Update host port bindings in `docker-compose.yml` if necessary.

2. **Mobile App Cannot Connect to Backend**
   - Ensure the Django server was started with `0.0.0.0:8000` (not `127.0.0.1:8000`), allowing external interface binding.
   - For Android emulators, ensure you are using `10.0.2.2:8000`.

3. **Complete Environment Reset (Wipe Data & Start Fresh)**
   ```bash
   # Stop and purge all container volumes
   docker-compose down -v

   # Relaunch containers
   docker-compose up -d

   # Reapply migrations and seed data
   cd eam_app
   python manage.py migrate
   python manage.py seed_hungarian_demo
   ```

---

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

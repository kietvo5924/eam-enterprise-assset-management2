# EAM (Enterprise Asset Management) System

The Enterprise Asset Management (EAM) system provides a multi-tenant architecture to manage assets, maintenance, work orders, and reports.

> **Note**: This project has been modernized and rewritten from a legacy Spring Boot/React stack into a full-stack **Django** monolith to improve maintainability, development speed, and reduce infrastructure complexity.

## Technology Stack
- **Backend & Core**: Python 3.11, Django 4.8, PostgreSQL, Redis, MinIO
- **Frontend**: Django Templates, TailwindCSS, Phosphor Icons, Vanilla JavaScript
- **Mobile App**: Flutter, Dart, Dio, Provider, GoRouter
- **Testing**: Pytest, Microsoft Playwright (End-to-End Testing)
- **Infrastructure**: Docker, Docker Compose (for databases and object storage)

---

## Local Setup Instructions

The infrastructure (PostgreSQL, Redis, MinIO) is containerized with Docker Compose, while the Django application runs locally via a virtual environment.

### Step 1: Environment Variables
Open a terminal at the project root and create a `.env` file from the example:

```bash
# On Linux/Mac:
cp .env.example .env

# On Windows (PowerShell):
Copy-Item .env.example -Destination .env
```

Open the `.env` file and fill in your Resend API Key (used for system email notifications). You can get a free key at https://resend.com:
```env
RESEND_API_KEY=your_resend_api_key_here
```

### Step 2: Start the Infrastructure
Run the following command to start PostgreSQL, pgAdmin, Redis, and MinIO in the background:

```bash
docker-compose up -d
```
> Note: The first run may take 2-5 minutes to download Docker images.

### Step 3: Set up Virtual Environment & Dependencies
Create a Python virtual environment and install the required dependencies:

```bash
# Create Virtual Environment
python -m venv venv

# Activate (Windows PowerShell)
.\venv\Scripts\activate
# Activate (Mac/Linux)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 4: Run Database Migrations
Initialize the database schema and seed default data:

```bash
python manage.py migrate
```

### Step 5: Start the System
Start the Django development server:

```bash
python manage.py runserver
```

---

### Step 6: Access the System

Once the server and containers are Running/Healthy, you can access the system at the following addresses:

- **Web Portal (Django Admin/Frontend)**: http://localhost:8000
  - Default login credentials (if seeded):
    - Username/Email: `superadmin@eam.local`
    - Password: `admin` (or your default seeded password)

- **Database Management (pgAdmin)**: http://localhost:5050
  - Email: `admin@admin.com`
  - Password: `admin`
  - To view the database, click "Add New Server" in pgAdmin and use these settings:
    - General > Name: EAM Database
    - Connection > Host name/address: `postgres`
    - Connection > Port: `5432`
    - Connection > Maintenance database: `eam_db`
    - Connection > Username: `eam_user`
    - Connection > Password: `eam_password`

- **File/Object Storage (MinIO Console)**: http://localhost:9001
  - Username: `minioadmin`
  - Password: `minioadmin`

---

### Step 7: Run the Mobile App (EAM Mobile)

The EAM system includes a native mobile application for technicians and supervisors.

1. Ensure you have [Flutter SDK](https://docs.flutter.dev/get-started/install) installed on your machine.
2. Open a new terminal and navigate to the `mobile_app` directory:
   ```bash
   cd mobile_app
   ```
3. Get the dependencies:
   ```bash
   flutter pub get
   ```
4. Run the app on a connected device or emulator:
   ```bash
   flutter run
   ```
> Note: The mobile application connects to the local backend API. For Android emulators, it will map to `10.0.2.2`, while iOS simulators will use `localhost`. You can log in using the same credentials as the Web Portal.

---

## Testing (End-to-End)

This project utilizes **Pytest** and **Playwright** to run comprehensive End-to-End (E2E) tests simulating real user interactions on a Chromium browser.

To run the full test suite:
```bash
# Make sure your virtual environment is activated
pytest -v e2e_tests
```
*(If you are using playwright for the first time, you may need to install the browser binaries: `playwright install chromium`)*

---

## Troubleshooting

1. **Port Conflict (Port is already allocated)**
If you encounter port errors (e.g., 5433, 5050, 8000), ensure no local services are using these ports, or change the mapped ports in `docker-compose.yml`.

2. **Missing Module Errors**
If you see `ModuleNotFoundError`, ensure your virtual environment is activated (`.\venv\Scripts\activate`) and all dependencies are installed.

3. **Full System Reset (Wipe all data)**
If you want to completely clean up the databases and start fresh as a new installation, use the following command:
```bash
docker-compose down -v --rmi all
```
Warning: This command will permanently delete all database records and uploaded files in MinIO/PostgreSQL.

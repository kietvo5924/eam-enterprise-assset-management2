# EAM (Enterprise Asset Management) System

The Enterprise Asset Management (EAM) system provides a multi-tenant architecture to manage assets, maintenance, work orders, and reports.

## Technology Stack
- Backend: Java 17, Spring Boot 3.2, PostgreSQL, Kafka, MinIO, OpenTelemetry, Flyway.
- Frontend: React, Vite, TypeScript, Ant Design, Zustand, Axios.
- Mobile App: Flutter, Dart, Dio, Provider, GoRouter.
- Infrastructure: Docker, Docker Compose.

---

## Local Setup Instructions

The system is fully containerized with Docker Compose, allowing you to start the entire environment and seed default data with just a few commands.

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

### Step 2: Start the System
Run the following command to build and start all services (Database, Kafka, MinIO, Backend, Frontend, etc.):

```bash
docker-compose up -d --build
```
> Note: The first run may take 2-5 minutes to download Docker images and build the source code. The backend will automatically execute Flyway migrations (V1 to V12) to initialize the robust database schema and seed all necessary default data (including the `superadmin@eam.local` account).

### Step 3: Access the System

Once all containers are Running/Healthy, you can access the system at the following addresses:

- Web Portal (Frontend): http://localhost:5173
  - Default login credentials:
    - Email: superadmin@eam.local
    - Password: admin123

- Backend API: http://localhost:8080

- Database Management (pgAdmin): http://localhost:5050
  - Email: admin@admin.com
  - Password: admin
  - To view the database, click "Add New Server" in pgAdmin and use these settings:
    - General > Name: EAM Database
    - Connection > Host name/address: postgres
    - Connection > Port: 5432
    - Connection > Maintenance database: eam_db
    - Connection > Username: eam_user
    - Connection > Password: eam_password

- File/Object Storage (MinIO Console): http://localhost:9001
  - Username: minioadmin
  - Password: minioadmin

---

### Step 4: Run the Mobile App (EAM Mobile)

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

## Troubleshooting

1. Port Conflict (Port is already allocated)
If you encounter port errors (e.g., 5432, 8080, 5173), ensure no local services are using these ports, or change the mapped ports in `docker-compose.yml`.

2. Full System Reset (Wipe all data)
If you want to completely clean up and start fresh as a new installation, use the following command:
```bash
docker-compose down -v --rmi all
```
Warning: This command will permanently delete all database records and uploaded files.

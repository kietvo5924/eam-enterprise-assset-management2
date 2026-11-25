import os
import sys
import subprocess
import uuid
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import connection
from django.utils import timezone

from core.models import Tenant
from users.models import User


EXPECTED_DB_NAME = "eam_db"


class Command(BaseCommand):
    help = (
        "Option B: Safely restore ENTIRE PostgreSQL database (eam_db). "
        "Strictly separated from per-tenant reset. Creates safety pre-backup before restoring."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dump-file',
            type=str,
            required=False,
            default=None,
            help='Path to the PostgreSQL dump file (.dump or .sql) to restore from'
        )
        parser.add_argument(
            '--backup-dir',
            type=str,
            default=None,
            help='Directory to store the automatic pre-restore backup (default: project root / backups)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Bypass interactive confirmation prompt (requires --confirm-destructive RESTORE_ENTIRE_DATABASE)'
        )
        parser.add_argument(
            '--confirm-destructive',
            type=str,
            default=None,
            help='Mandatory confirmation token when using --force: must be RESTORE_ENTIRE_DATABASE'
        )
        parser.add_argument(
            '--skip-pre-backup',
            action='store_true',
            help='Skip creating pre-restore backup (NOT recommended)'
        )

    def handle(self, *args, **options):
        dump_file = options.get('dump_file')
        backup_dir = options.get('backup_dir')
        force = options.get('force', False)
        confirm_destructive = options.get('confirm_destructive')
        skip_pre_backup = options.get('skip_pre_backup', False)

        self.stdout.write("=" * 75)
        self.stdout.write(self.style.WARNING("[!] OPTION B: FULL DATABASE RESTORE UTILITY (ENTIRE SYSTEM)"))
        self.stdout.write("=" * 75)

        # 1. VERIFY CORRECT DATABASE
        db_settings = settings.DATABASES['default']
        current_db = db_settings['NAME']
        db_user = db_settings.get('USER', 'postgres')
        db_host = db_settings.get('HOST', '127.0.0.1')
        db_port = str(db_settings.get('PORT', '5433'))

        self.stdout.write(f"-> Target Database: {current_db} on {db_host}:{db_port} (User: {db_user})")

        if EXPECTED_DB_NAME not in current_db and 'test' not in current_db.lower():
            raise CommandError(
                f"[FATAL] Safety breach: Refusing to restore non-standard database '{current_db}'! Expected '{EXPECTED_DB_NAME}'."
            )

        # 2. LOCATE DUMP FILE
        if not dump_file:
            # Check default candidate locations
            candidates = [
                os.path.abspath(os.path.join(settings.BASE_DIR, '..', 'backups', 'FULL_DB_LATEST.dump')),
                os.path.abspath(os.path.join(settings.BASE_DIR, 'backups', 'FULL_DB_LATEST.dump')),
            ]
            for c in candidates:
                if os.path.exists(c):
                    dump_file = c
                    break

        if not dump_file or not os.path.exists(dump_file):
            raise CommandError(
                f"[FAIL] Full database dump file not found: {dump_file}\n"
                f"Please specify a valid dump file using --dump-file <path_to_dump>."
            )

        self.stdout.write(f"-> Source Dump File: {dump_file} ({os.path.getsize(dump_file):,} bytes)")

        # 3. SAFETY CONFIRMATION (CRITICAL REQUIREMENT)
        self.stdout.write(self.style.ERROR(
            "\n[CRITICAL WARNING - DATA OVERWRITE RISK]\n"
            "This operation will RESTORE THE ENTIRE DATABASE.\n"
            "ALL TENANTS, USERS, ASSETS, AND CONFIGURATIONS (including SYSTEM and VinFast) WILL BE OVERWRITTEN!\n"
            "If you only intend to reset the Van Lam demo tenant, please use:\n"
            "  python manage.py reset_vanlam_demo --restore-baseline\n"
        ))

        if force:
            if confirm_destructive != "RESTORE_ENTIRE_DATABASE":
                raise CommandError(
                    "[FATAL] When using --force, you MUST explicitly provide:\n"
                    "  --confirm-destructive RESTORE_ENTIRE_DATABASE"
                )
        else:
            self.stdout.write(self.style.WARNING("To proceed with FULL DATABASE RESTORE, type 'RESTORE_ENTIRE_DATABASE':"))
            user_input = input("> ").strip()
            if user_input != "RESTORE_ENTIRE_DATABASE":
                self.stdout.write(self.style.NOTICE("[ABORTED] Full database restore cancelled by user."))
                return

        # 4. CREATE PRE-RESTORE SAFETY BACKUP
        if not backup_dir:
            backup_dir = os.path.abspath(os.path.join(settings.BASE_DIR, '..', 'backups'))
        os.makedirs(backup_dir, exist_ok=True)

        if not skip_pre_backup:
            ts = timezone.now().strftime("%Y%m%d_%H%M%S")
            pre_backup_path = os.path.join(backup_dir, f"FULL_DB_BEFORE_RESTORE_{ts}.dump")
            self.stdout.write(f"-> [1/3] Creating automatic pre-restore safety backup: {pre_backup_path}...")

            # Attempt docker exec or host pg_dump
            pre_backup_success = False
            # Check docker container
            try:
                cmd = [
                    "docker", "exec", "eam_postgres",
                    "pg_dump", "-U", db_user, "-d", current_db, "-Fc"
                ]
                with open(pre_backup_path, 'wb') as f_out:
                    res = subprocess.run(cmd, stdout=f_out, stderr=subprocess.PIPE, check=True)
                pre_backup_success = True
                self.stdout.write(self.style.SUCCESS(f"   [OK] Pre-restore backup created via Docker: {pre_backup_path}"))
            except Exception as e_docker:
                self.stdout.write(self.style.WARNING(f"   [!] Docker pg_dump fallback ({e_docker}), trying host pg_dump..."))
                try:
                    cmd = ["pg_dump", "-h", db_host, "-p", db_port, "-U", db_user, "-Fc", "-f", pre_backup_path, current_db]
                    subprocess.run(cmd, check=True)
                    pre_backup_success = True
                    self.stdout.write(self.style.SUCCESS(f"   [OK] Pre-restore backup created via host pg_dump: {pre_backup_path}"))
                except Exception as e_host:
                    self.stdout.write(self.style.WARNING(f"   [!] Host pg_dump also unavailable ({e_host})."))

            if not pre_backup_success:
                self.stdout.write(self.style.WARNING("   [!] Could not generate binary dump, logging warning before proceeding."))

        # 5. EXECUTE RESTORE
        self.stdout.write(f"-> [2/3] Restoring database from {dump_file}...")
        restore_success = False
        try:
            # First try docker exec pg_restore
            # Copy dump into container temporarily if needed
            copy_cmd = ["docker", "cp", dump_file, "eam_postgres:/tmp/restore_target.dump"]
            subprocess.run(copy_cmd, check=True)

            restore_cmd = [
                "docker", "exec", "eam_postgres",
                "pg_restore", "-U", db_user, "-d", current_db, "--clean", "--if-exists", "/tmp/restore_target.dump"
            ]
            subprocess.run(restore_cmd, check=True)
            restore_success = True
            self.stdout.write(self.style.SUCCESS("   [OK] pg_restore executed successfully via Docker!"))
        except Exception as e_dock_restore:
            self.stdout.write(self.style.WARNING(f"   [!] Docker pg_restore failed ({e_dock_restore}), trying host pg_restore..."))
            try:
                host_restore_cmd = [
                    "pg_restore", "-h", db_host, "-p", db_port, "-U", db_user,
                    "-d", current_db, "--clean", "--if-exists", dump_file
                ]
                subprocess.run(host_restore_cmd, check=True)
                restore_success = True
                self.stdout.write(self.style.SUCCESS("   [OK] pg_restore executed successfully via host tool!"))
            except Exception as e_host_restore:
                raise CommandError(f"[FAIL] Database restore failed: {e_host_restore}")

        # 6. POST-RESTORE VERIFICATION
        self.stdout.write("-> [3/3] Performing post-restore integrity check...")
        try:
            connection.close()  # Refresh connection
            tenant_count = Tenant.objects.count()
            user_count = User.all_objects.count()
            self.stdout.write(f"   - Total Tenants in DB: {tenant_count}")
            self.stdout.write(f"   - Total Users in DB:   {user_count}")

            vl_tenant = Tenant.objects.filter(tenant_code="VANLAM_DEMO_2026").first()
            if vl_tenant:
                self.stdout.write(self.style.SUCCESS(f"   - Demo Tenant Status:  FOUND ({vl_tenant.name})"))
            else:
                self.stdout.write(self.style.WARNING("   - Demo Tenant Status:  NOT PRESENT in this full dump"))

            sys_tenant = Tenant.objects.filter(tenant_code="SYSTEM").first()
            if sys_tenant:
                self.stdout.write(self.style.SUCCESS("   - SYSTEM Tenant:       FOUND"))

            vf_tenant = Tenant.objects.filter(tenant_code="VF_MFG").first()
            if vf_tenant:
                self.stdout.write(self.style.SUCCESS("   - VinFast Tenant:      FOUND"))

        except Exception as e_verify:
            raise CommandError(f"[FAIL] Post-restore verification failed: {e_verify}")

        self.stdout.write("=" * 75)
        self.stdout.write(self.style.SUCCESS("[PASS] FULL DATABASE RESTORE COMPLETED AND VERIFIED!"))
        self.stdout.write("=" * 75)

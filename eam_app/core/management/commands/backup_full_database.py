import os
import sys
import subprocess
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.utils import timezone


EXPECTED_DB_NAME = "eam_db"


class Command(BaseCommand):
    help = "Create a full PostgreSQL database dump of eam_db for disaster recovery (Option B backup)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--output-dir',
            type=str,
            default=None,
            help='Directory to store the full database dump (default: project root / backups)'
        )
        parser.add_argument(
            '--filename',
            type=str,
            default=None,
            help='Custom filename for the full dump'
        )

    def handle(self, *args, **options):
        output_dir = options.get('output_dir')
        custom_filename = options.get('filename')

        self.stdout.write("=" * 70)
        self.stdout.write("[*] INITIATING FULL DATABASE BACKUP (OPTION B)")
        self.stdout.write("=" * 70)

        db_settings = settings.DATABASES['default']
        current_db = db_settings['NAME']
        db_user = db_settings.get('USER', 'postgres')
        db_host = db_settings.get('HOST', '127.0.0.1')
        db_port = str(db_settings.get('PORT', '5433'))

        self.stdout.write(f"-> Target Database: {current_db} on {db_host}:{db_port}")

        if EXPECTED_DB_NAME not in current_db and 'test' not in current_db.lower():
            raise CommandError(
                f"[FATAL] Safety breach: Refusing to dump non-standard database '{current_db}'! Expected '{EXPECTED_DB_NAME}'."
            )

        if not output_dir:
            output_dir = os.path.abspath(os.path.join(settings.BASE_DIR, '..', 'backups'))
        os.makedirs(output_dir, exist_ok=True)

        ts = timezone.now().strftime("%Y%m%d_%H%M%S")
        if custom_filename:
            dump_filename = custom_filename if custom_filename.endswith('.dump') else f"{custom_filename}.dump"
        else:
            dump_filename = f"FULL_DB_BACKUP_{ts}.dump"

        dump_path = os.path.join(output_dir, dump_filename)
        latest_path = os.path.join(output_dir, "FULL_DB_LATEST.dump")

        self.stdout.write(f"-> Destination: {dump_path}")

        # Attempt docker exec or host pg_dump
        success = False
        try:
            cmd = [
                "docker", "exec", "eam_postgres",
                "pg_dump", "-U", db_user, "-d", current_db, "-Fc"
            ]
            with open(dump_path, 'wb') as f_out:
                subprocess.run(cmd, stdout=f_out, stderr=subprocess.PIPE, check=True)
            success = True
            self.stdout.write(self.style.SUCCESS("-> pg_dump executed via Docker successfully!"))
        except Exception as e_docker:
            self.stdout.write(self.style.WARNING(f"-> Docker pg_dump fallback ({e_docker}), trying host pg_dump..."))
            try:
                cmd = ["pg_dump", "-h", db_host, "-p", db_port, "-U", db_user, "-Fc", "-f", dump_path, current_db]
                subprocess.run(cmd, check=True)
                success = True
                self.stdout.write(self.style.SUCCESS("-> pg_dump executed via host tool successfully!"))
            except Exception as e_host:
                raise CommandError(f"[FAIL] Could not create full database dump: {e_host}")

        if success and os.path.exists(dump_path):
            file_size = os.path.getsize(dump_path)
            # Update pointer
            import shutil
            shutil.copyfile(dump_path, latest_path)

            self.stdout.write("=" * 70)
            self.stdout.write(self.style.SUCCESS(f"[PASS] FULL DATABASE BACKUP CREATED SUCCESSFULLY!"))
            self.stdout.write(f"-> File:   {dump_path} ({file_size:,} bytes)")
            self.stdout.write(f"-> Latest: {latest_path}")
            self.stdout.write("=" * 70)

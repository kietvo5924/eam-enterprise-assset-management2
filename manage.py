#!/usr/bin/env python
"""
Workspace root forwarder for Django management tasks.
Allows running 'python manage.py <command>' directly from the repository root.
"""
import os
import sys

def main():
    repo_dir = os.path.dirname(os.path.abspath(__file__))
    app_dir = os.path.join(repo_dir, "eam_app")
    
    os.chdir(app_dir)
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)

if __name__ == '__main__':
    main()

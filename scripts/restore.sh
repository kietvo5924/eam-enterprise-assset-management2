#!/bin/bash

if [ -z "$1" ]; then
    echo "Usage: $0 <path_to_backup_file>"
    exit 1
fi

BACKUP_FILE="$1"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "Error: Backup file not found at $BACKUP_FILE"
    exit 1
fi

echo "Starting restore process from $BACKUP_FILE..."
echo "WARNING: This will overwrite existing data in eam_db."
read -p "Are you sure you want to proceed? (Y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Restore cancelled."
    exit 0
fi

echo "Restoring..."
docker exec -i eam_postgres psql -U postgres -d eam_db < "$BACKUP_FILE"

if [ $? -eq 0 ]; then
    echo "Restore successful!"
else
    echo "Restore failed!"
    exit 1
fi

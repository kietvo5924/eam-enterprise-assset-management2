#!/bin/bash

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="eam_backup_$TIMESTAMP.sql"
BACKUP_DIR="backups"

mkdir -p "$BACKUP_DIR"

DESTINATION="$BACKUP_DIR/$BACKUP_FILE"

echo "Starting backup for eam_db..."
docker exec -t eam_postgres pg_dump -U postgres -d eam_db -c -F p > "$DESTINATION"

if [ $? -eq 0 ]; then
    echo "Backup successful! File saved to: $DESTINATION"
else
    echo "Backup failed!"
    exit 1
fi

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupFile = "eam_backup_$timestamp.sql"
$backupDir = "backups"

if (!(Test-Path -Path $backupDir)) {
    New-Item -ItemType Directory -Path $backupDir | Out-Null
}

$destination = Join-Path -Path $backupDir -ChildPath $backupFile

Write-Host "Starting backup for eam_db..."
# Use -c to include clean (drop) commands before create
docker exec -t eam_postgres pg_dump -U postgres -d eam_db -c -F p > $destination

if ($LASTEXITCODE -eq 0) {
    Write-Host "Backup successful! File saved to: $destination" -ForegroundColor Green
} else {
    Write-Host "Backup failed!" -ForegroundColor Red
}

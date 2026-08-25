param (
    [Parameter(Mandatory=$true)]
    [string]$BackupFilePath
)

if (!(Test-Path -Path $BackupFilePath)) {
    Write-Host "Error: Backup file not found at $BackupFilePath" -ForegroundColor Red
    exit 1
}

# Resolve to absolute path for cmd.exe
$absolutePath = (Resolve-Path $BackupFilePath).Path

Write-Host "Starting restore process from $absolutePath..."
Write-Host "WARNING: This will overwrite existing data in eam_db." -ForegroundColor Yellow
$confirmation = Read-Host "Are you sure you want to proceed? (Y/N)"

if ($confirmation -ne 'Y' -and $confirmation -ne 'y') {
    Write-Host "Restore cancelled."
    exit 0
}

Write-Host "Restoring..."
# Using cmd to pipe the file into docker to avoid PowerShell encoding/memory issues with large files
cmd.exe /c "type `"$absolutePath`" | docker exec -i eam_postgres psql -U postgres -d eam_db"

if ($LASTEXITCODE -eq 0) {
    Write-Host "Restore successful!" -ForegroundColor Green
} else {
    Write-Host "Restore failed!" -ForegroundColor Red
}

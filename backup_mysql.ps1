$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"

$backupDir = ".\backups"

if (!(Test-Path $backupDir)) {
    New-Item -ItemType Directory -Path $backupDir
}

& "C:\Program Files\MySQL\MySQL Server 8.4\bin\mysqldump.exe" `
    -u ncs_app `
    -p `
    --single-transaction `
    --no-tablespaces `
    --routines `
    --triggers `
    ncs_charging `
    > "$backupDir\ncs_charging_$timestamp.sql"

if ($LASTEXITCODE -eq 0) {
    Write-Host "Backup completed successfully."
    Write-Host "File: $backupDir\ncs_charging_$timestamp.sql"
} else {
    Write-Host "Backup failed. mysqldump exit code: $LASTEXITCODE"
    exit $LASTEXITCODE
}
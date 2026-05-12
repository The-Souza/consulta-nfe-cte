# Reads ICON_FILE from .env if available
$iconFile = "icon.ico"
if (Test-Path ".env") {
    $envLine = Get-Content ".env" | Where-Object { $_ -match "^ICON_FILE=" }
    if ($envLine) { $iconFile = $envLine -replace "^ICON_FILE=", "" }
}

$iconArgs = if (Test-Path $iconFile) { @("--icon", $iconFile) } else { @() }

.venv\Scripts\pyinstaller.exe `
    --noconfirm `
    --onedir `
    --windowed `
    --name "consulta-nfe-cte" `
    --collect-all customtkinter `
    @iconArgs `
    script.py

Write-Host ""
Write-Host "Build concluido. Proximos passos:" -ForegroundColor Green
Write-Host "  1. Copie seu arquivo .env para dist\consulta-nfe-cte\"
Write-Host "  2. Copie o arquivo de icone ($iconFile) para dist\consulta-nfe-cte\"
Write-Host "  3. O executavel esta em dist\consulta-nfe-cte\consulta-nfe-cte.exe"

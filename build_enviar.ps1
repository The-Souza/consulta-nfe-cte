# Builds the "Enviar planilha" uploader into dist\enviar-planilha\, apart from the Canhotos app.
# Its config (enviar_planilha.env, with the Supabase secret key) is never bundled: copy it next to the .exe.

# The .exe icon is drawn by the app itself: no .ico file lives in the repo
New-Item -ItemType Directory -Force build | Out-Null
.venv\Scripts\python.exe -m sheet_sync.icon build\enviar-planilha.ico
if ($LASTEXITCODE -ne 0) {
    Write-Error "Nao foi possivel gerar o icone (codigo $LASTEXITCODE)."
    exit $LASTEXITCODE
}

.venv\Scripts\pyinstaller.exe `
    --noconfirm `
    --onedir `
    --windowed `
    --name "enviar-planilha" `
    --icon "build\enviar-planilha.ico" `
    --collect-all customtkinter `
    --add-data "assets;assets" `
    enviar_planilha.py

# Without this, a failed build still prints "Build concluido" and leaves the old dist\ in place
if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller falhou (codigo $LASTEXITCODE). O dist\ nao foi atualizado."
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "Build concluido. Proximos passos:" -ForegroundColor Green
Write-Host "  1. Copie seu enviar_planilha.env para dist\enviar-planilha\ (nunca o .env do app)"
Write-Host "  2. O executavel esta em dist\enviar-planilha\enviar-planilha.exe"

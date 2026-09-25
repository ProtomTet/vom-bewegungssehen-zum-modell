# Startskript - Seminar "Physik der Sportarten"
Set-Location -LiteralPath $PSScriptRoot

$venvPython = Join-Path $PSScriptRoot "..\..\.venv\Scripts\python.exe"
if (Test-Path -LiteralPath $venvPython) {
    $python = (Resolve-Path -LiteralPath $venvPython).Path
    Write-Host "Verwende Seminar-Umgebung: $python" -ForegroundColor DarkGray
} else {
    $python = "python"
    Write-Host "Seminar-Umgebung (.venv) nicht gefunden - verwende globales Python." -ForegroundColor Yellow
}

& $python -c "import streamlit, cv2, scipy, imageio_ffmpeg" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installiere fehlende Pakete ..." -ForegroundColor Cyan
    & $python -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Installation fehlgeschlagen." -ForegroundColor Red
        Read-Host "Enter zum Beenden"
        exit 1
    }
}

& $python -m streamlit run app.py --browser.gatherUsageStats false

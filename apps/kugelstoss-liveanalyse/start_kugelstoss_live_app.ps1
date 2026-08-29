# Startskript - Seminar "Physik der Sportarten"
# Nutzt die Seminar-Umgebung Seminar_SS26_CUO\.venv, falls vorhanden,
# sonst das global installierte python.
Set-Location -LiteralPath $PSScriptRoot

$venv = Join-Path $PSScriptRoot "..\..\.venv\Scripts\python.exe"
if (Test-Path $venv) {
    $py = (Resolve-Path $venv).Path
    Write-Host "Verwende Seminar-Umgebung: $py" -ForegroundColor DarkGray
} else {
    $py = "python"
    Write-Host "Seminar-Umgebung (.venv) nicht gefunden - verwende globales python." -ForegroundColor Yellow
}

& $py -m streamlit run app.py --browser.gatherUsageStats false

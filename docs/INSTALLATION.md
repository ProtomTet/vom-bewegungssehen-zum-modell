# Installation und Start

## 1. Python

Die Anwendungen sind mit Python 3.11 geprüft und laufen auch unter 3.12 und 3.13.
Prüfen Sie zuerst, ob Python vorhanden ist:

```powershell
py -3.11 --version
```

Kommt eine Fehlermeldung, installieren Sie Python von <https://www.python.org/downloads/windows/>.
Setzen Sie bei der Installation den Haken bei *Add python.exe to PATH*.

## 2. Umgebung anlegen

PowerShell im Ordner des Repositories öffnen — im Windows-Explorer oben in die Adresszeile
`powershell` eintippen und Enter drücken. Dann nacheinander:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Der letzte Schritt dauert einige Minuten. Er installiert alles, was die fünf Anwendungen
zusammen benötigen.

## 3. Starten

Jede Anwendung hat ein Startskript. Es findet die Umgebung `.venv` von selbst:

| Anwendung | Startskript |
|---|---|
| Videoplayer | `apps\videoplayer-kalibrierung\start_videoplayer.ps1` |
| Kamera-Bridge | `apps\kamera-desktop-bridge\start_droidcam_capture_bridge.ps1` |
| phyphox Echtzeit | `apps\phyphox-echtzeit\start_phyphox_echtzeit_app.ps1` |
| Kugelstoß Live | `apps\kugelstoss-liveanalyse\start_kugelstoss_live_app.ps1` |
| Flugbahn-Modellierer | `apps\flugbahn-modellierer\start_flugbahn_modellierer.ps1` |

Lässt Windows das Skript nicht zu, hilft einmalig:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

## 4. Wenn etwas nicht funktioniert

**Die Anwendung startet nicht.** Prüfen Sie, ob die Umgebung angelegt wurde: Es muss ein
Ordner `.venv` im Wurzelverzeichnis geben. Fehlt er, Schritt 2 wiederholen.

**phyphox wird nicht gefunden.** Rechner und Smartphone müssen im selben Netz sein.
Unter Android liegt die Schnittstelle meist auf Port 8080, unter iOS auf Port 80. In
großen Netzen werden Geräte oft getrennt; ein Hotspot ist dann zuverlässiger.

**Das Video lässt sich nicht öffnen.** Nicht jedes Format wird unterstützt. MP4 mit
H.264 ist die sicherste Wahl.

**Die Bildrate wird als „ANGENOMMEN" angezeigt.** Dann konnte sie aus der Datei nicht
gelesen werden und es wird mit 30 Bildern pro Sekunde gerechnet. Alle Zeitangaben sind
dann unsicher. Prüfen Sie die Bildrate in den Dateieigenschaften.

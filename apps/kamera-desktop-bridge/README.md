# DroidCam Capture Bridge

Einfache Desktop-Oberflaeche fuer Windows, die den DroidCam-HTTP-Stream live anzeigt und direkt auf dem PC als Videodatei aufzeichnet.

## Zweck

Die Anwendung verbindet sich mit dem von DroidCam bereitgestellten Browser-/MJPEG-Stream, zeigt ihn live an und speichert die Aufnahme lokal. Dadurch entfaellt die kompliziertere Steuerung per `adb` oder `scrcpy`.

## Enthaltene Funktionen

- Livebild aus DroidCam ueber IP und Port
- Auswahl einer Streamaufloesung fuer die URL
- Browseraufruf der DroidCam-Webvorschau
- Start und Stop einer lokalen Videoaufnahme
- Export direkt als Datei im lokalen Zielordner
- Protokoll und Live-FPS-Anzeige

## Voraussetzungen

- Windows
- Smartphone mit laufender DroidCam-App
- PC und Smartphone im selben Netzwerk
- Python 3.11 mit `PySide6`, `opencv-python`, `numpy` (siehe `requirements.txt` bzw. `00_Start/requirements_student_tools.txt`)

## Start

Im Windows-Explorer in diesen Ordner wechseln, oben in die Adresszeile `powershell` eintippen und Enter druecken. Dann:

```powershell
.\start_droidcam_capture_bridge.ps1
```

Das Startskript nutzt automatisch die Seminar-Umgebung `Seminar_SS26_CUO\.venv`, falls vorhanden, sonst das globale `python`.

Alternativ von Hand:

```powershell
python .\app.py
```

## Empfohlener Ablauf

1. DroidCam am Smartphone starten.
2. Die in DroidCam angezeigte IP-Adresse und den Port in der Desktop-App eintragen.
3. Livebild starten.
4. Kameraeinstellungen wie Fokus, Belichtung, Qualitaet und Framerate direkt in der DroidCam-App auf dem Smartphone setzen.
5. Falls gewuenscht eine Streamaufloesung fuer die URL waehlen.
6. Aufnahme am PC starten und stoppen.
7. Die exportierte Videodatei im gewaehlten Zielordner verwenden.

## Wichtige Hinweise

- Die eigentlichen Kameraoptionen kommen weiterhin aus der DroidCam-App auf dem Smartphone, nicht aus der Desktop-App.
- Die Desktop-App zeichnet den Stream lokal auf dem PC auf. Es wird keine Datei vom Smartphone herunterkopiert.
- Die Stream-URL nutzt den von DroidCam dokumentierten Browser-/Videozugriff. Mit `force` kann eine bestehende Verbindung ueberschrieben werden.
- Die effektive Live-FPS haengt vom Smartphone, WLAN und den Einstellungen in DroidCam ab. Die Export-FPS kann daran gekoppelt oder als Fallback fest vorgegeben werden.

## Technische Grundlage

- Browser-Vorschau: `http://<ip>:<port>/`
- Video-Stream: `http://<ip>:<port>/video`
- Erzwingbare URL-Aufloesung laut DroidCam-Dokumentation: `http://<ip>:<port>/video/force/1280x720`

## Referenzen

- Dev47Apps. (n.d.). *DroidCam Connect*. https://www.dev47apps.com/droidcam/connect/
- Dev47Apps. (n.d.). *DroidCam OBS Camera Help*. https://www.dev47apps.com/obs/help/
- Dev47Apps. (n.d.). *DroidCam Help*. https://www.dev47apps.com/droidcam/help/

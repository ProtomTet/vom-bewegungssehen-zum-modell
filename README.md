# Vom Bewegungssehen zum Modell — Begleitsoftware

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22161338.svg)](https://doi.org/10.5281/zenodo.22161338)

Fünf kleine Python-Anwendungen zum Seminar bzw. Reader *Vom Bewegungssehen zum Modell.
Sprint, Sprung und Wurf als fächerverbindender Lernraum für Sport, Mathematik, Physik,
Biologie und Informatik.*

Die Programme ersetzen keine Fachsoftware. Sie sind bewusst klein und lesbar gehalten,
damit im Seminar nachvollziehbar bleibt, was sie rechnen — und damit Studierende sie
verändern können. Für Kinovea und Tracker sind sie eine Ergänzung, kein Ersatz.

## Die Anwendungen

| Ordner | Zweck | Gebraucht in |
|---|---|---|
| [`videoplayer-kalibrierung`](apps/videoplayer-kalibrierung/) | Videoplayer mit Kalibrierung und Overlay | Tag 1, Aufgabe 1 und 2 sowie Tag 2, Aufgabe 3 |
| [`kamera-desktop-bridge`](apps/kamera-desktop-bridge/) | Smartphone-Livebild am Rechner aufzeichnen | alle Aufnahmesituationen |
| [`phyphox-echtzeit`](apps/phyphox-echtzeit/) | Beschleunigungsdaten aus phyphox live abrufen und als Excel exportieren | Tag 2, Aufgabe 4 |
| [`kugelstoss-liveanalyse`](apps/kugelstoss-liveanalyse/) | Live-Ansicht und Phasenerkennung fuer den Kugelstoss | Tag 3, Aufgabe 9 |
| [`flugbahn-modellierer`](apps/flugbahn-modellierer/) | Flugbahnen modellieren, Parameter variieren, Rechenweg anzeigen | Tag 3, Aufgabe 7 und 8 |

## Arbeitsmaterial

Neben den Programmen liegt im Ordner [`material`](material/) alles, was zum Reader gehoert,
sich aber nicht drucken laesst.

| Ordner | Inhalt |
|---|---|
| [`material/excel`](material/excel/) | Auswertungsvorlage fuer den Countermovement Jump und ein ausgefuelltes Beispiel |
| [`material/daten`](material/daten/) | Sprungrohdaten und der Sprintdatensatz zu Tokio 1991 |
| [`material/aufgabenblaetter`](material/aufgabenblaetter/) | die neun Aufgaben als einzelne, bearbeitbare Dateien |

Wer nur die Dateien braucht und nicht durch das Repositorium klicken moechte, laedt das
Gesamtarchiv ueber die
[dauerhafte Kennung](https://doi.org/10.5281/zenodo.22161338) herunter — dort liegt zu jeder
Veroeffentlichung ein vollstaendiges Archiv.

## Schnellstart

Voraussetzung ist Python 3.11 oder neuer. Im Ordner des Repositories:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Danach lässt sich jede Anwendung über ihr Startskript öffnen, zum Beispiel:

```powershell
.\apps\flugbahn-modellierer\start_flugbahn_modellierer.ps1
```

Die Startskripte suchen automatisch nach einer Umgebung `.venv` im Wurzelverzeichnis und
greifen sonst auf das global installierte `python` zurück. Ausführlicher steht das in
[`docs/INSTALLATION.md`](docs/INSTALLATION.md).

## Was die Programme voraussetzen

* **phyphox** auf dem Smartphone, für die beiden Sensoranwendungen. Rechner und Smartphone
  müssen im selben Netzwerk sein; ein eigener Hotspot ist zuverlässiger als ein
  Hochschul- oder Schulnetz.
* **DroidCam** oder eine vergleichbare Lösung, wenn das Smartphone als Kamera am Rechner
  dienen soll.
* Für die Sprungauswertung Videoaufnahmen in **Zeitlupe**. Bei 30 Bildern pro Sekunde ist
  die Ablesegenauigkeit der Sprunghöhe mit rund ±3,8 cm größer als der Unterschied
  zwischen Countermovement Jump und Squat Jump, den die Aufgabe zeigen soll. Sinnvoll sind
  mindestens 120, besser 240 Bilder pro Sekunde.

## Geprüfte Bezugswerte

Der Flugbahn-Modellierer ist auf die Musterlösungen des Readers abgestimmt:

| Voreinstellung | Eingangswerte | Erwartete Weite |
|---|---|---|
| Kugelstoß | v₀ = 10,34 m/s, α = 37,05°, h₀ = 1,83 m, x₀ = 0,51 m | 13,02 m |
| Weitsprung | v₀ = 7,24 m/s, α = 23,02°, h₀ = 1,04 m, x₀ = 0,35 m | 5,89 m |

Weichen die Werte ab, ist das ein Fehler und kein didaktischer Spielraum.

## Mitarbeit

Rückmeldungen und Fehlermeldungen sind willkommen — am besten als Issue. Wer eine
Anwendung im eigenen Unterricht angepasst hat, kann den Stand gern als Pull Request
beisteuern.

## Lizenz

[![Lizenz: CC BY-SA 4.0](https://img.shields.io/badge/Lizenz-CC%20BY--SA%204.0-1F3864.svg)](https://creativecommons.org/licenses/by-sa/4.0/deed.de)

Dieses Werk ist lizenziert unter [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/deed.de).
Sie dürfen es teilen und bearbeiten, auch kommerziell, wenn Sie den Urheber nennen und
Ihre Bearbeitung unter derselben Lizenz weitergeben. Der vollständige Text steht in
[`LICENSE`](LICENSE), eine deutsche Erläuterung in [`LICENSE-HINWEIS.md`](LICENSE-HINWEIS.md).

Vorgeschlagene Namensnennung:

> Thomas Ertelt (2026): *Vom Bewegungssehen zum Modell — Begleitsoftware.*
> Zenodo. https://doi.org/10.5281/zenodo.22161338 · Lizenz CC BY-SA 4.0

## Dauerhafte Adresse

Die Software ist bei Zenodo archiviert und über eine DOI dauerhaft erreichbar, auch
falls dieses Repository später umzieht oder umbenannt wird.

| | |
|---|---|
| **Concept-DOI** (immer die neueste Fassung) | [`10.5281/zenodo.22161338`](https://doi.org/10.5281/zenodo.22161338) |
| DOI der Fassung 1.0.1 | [`10.5281/zenodo.22161339`](https://doi.org/10.5281/zenodo.22161339) |

In gedruckten Materialien sollte die Concept-DOI angegeben werden — sie führt Leserinnen
und Leser automatisch zur jeweils aktuellen Fassung.

# Änderungen

## 1.0.0 — 29.08.2026

Erste veröffentlichte Fassung, abgestimmt auf den Reader in der Fassung SS 2026.

### Behoben
* **Kugelstoß-Liveanalyse:** Absturz bei kurzen Signalen. Die Tiefpassfunktion prüfte die
  Signallänge gegen einen zu kleinen Wert; bei 12 bis 15 Messwerten brach `filtfilt` mit
  einem `ValueError` ab. Das traf genau den Moment, in dem eine Live-Messung anläuft. Die
  Grenze wird jetzt aus den tatsächlichen Filterkoeffizienten abgeleitet.
* **Flugbahn-Modellierer:** Die Voreinstellungen für Kugelstoß und Weitsprung wichen von
  den Musterlösungen ab. Sie liefern jetzt nachgerechnet 13,02 m beziehungsweise 5,89 m.

### Geändert
* **Videoplayer:** Ist die Bildrate aus der Datei nicht lesbar, wird mit 30 Bildern pro
  Sekunde gerechnet. Dieser Ersatzwert wird jetzt dauerhaft in der Bildraten- und der
  Δt-Anzeige gekennzeichnet, nicht mehr nur einmalig in der Statuszeile.
* Alle Anwendungen haben ein Startskript, das die Umgebung `.venv` selbst findet.
* Jede Anwendung hat eine eigene `requirements.txt`; zusätzlich gibt es eine gemeinsame
  im Wurzelverzeichnis.
* Absolute Pfade aus der Entwicklungsumgebung wurden aus allen READMEs entfernt.

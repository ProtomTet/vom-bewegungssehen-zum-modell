# Änderungen

## 1.1.0 — 29.08.2026

### Neu
* **Arbeitsmaterial** unter `material/`. Damit liegt alles, was der gedruckte Reader hinter
  QR-Codes ankündigt, an derselben Stelle wie die Programme und unter derselben Lizenz.
  * `material/excel/` — Auswertungsvorlage für den Countermovement Jump mit den Kontrollen
    K1 bis K4 sowie eine mit 2794 Messpunkten ausgefüllte Beispielauswertung.
  * `material/daten/` — eigene Sprungrohdaten (rund 208 Hz) und der Sprintdatensatz zum
    100-m-Finale von Tokio 1991.
  * `material/aufgabenblaetter/` — die neun Aufgaben des Readers als einzelne, bearbeitbare
    Dateien mit Zielsetzung, Arbeitsauftrag, Materialliste und Produktbeschreibung. Ohne
    Lösungen; die stehen im Reader, Teil VII.
  * `material/README.md` — welche Datei zu welcher Aufgabe gehört und was sie voraussetzt.

### Behoben
* `.gitignore` schloss mit `*.xlsx` alle Tabellen aus und hätte das Arbeitsmaterial
  stillschweigend übergangen. Für `material/` gilt jetzt eine Ausnahme.

### Hinweis zur Herkunft des Sprintdatensatzes
Die Werte stammen aus Ae, M., Ito, A., & Suzuki, M. (1992). The men's 100 metres.
*New Studies in Athletics, 7*(1), 47–52, Tabelle 2 auf S. 49. Der Artikel ist über das
Archiv von World Athletics frei zugänglich. Reaktionszeiten, Zwischenzeiten und
Abschnittsgeschwindigkeiten aller sechs enthaltenen Läufer wurden gegen das Original
geprüft und stimmen zeilenweise überein.

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

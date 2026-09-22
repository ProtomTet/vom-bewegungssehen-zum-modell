# Änderungen

## 1.2.1 — 22.09.2026

### Behoben
* **CMJ-Auswertung:** Die automatische Erkennung von Absprung und Landung verwendet keine
  fehlerhaft gespeicherten `MINWENNS`- und `MAXWENNS`-Formeln mehr. Sie liefert jetzt den
  ersten und letzten Datenpunkt der erkannten Flugphase.
* **Kontrolle K4:** Die Mindestgeschwindigkeit vor dem Absprung wird mit einer kompatiblen
  Formel bestimmt. Ein Formelfehler kann deshalb nicht mehr unbemerkt als leeres Ergebnis
  erscheinen.

### Geändert
* Bewegungsbeginn, manueller Absprung und manuelle Landung werden als Datenpunktnummern
  eingegeben. Die zugehörigen Messzeiten berechnet die Arbeitsmappe aus der tatsächlichen
  Zeitspalte. Die Diagramme verwenden dafür ebenfalls die Datenpunktnummer als x-Achse.
* `material/daten/Rohdaten_CMJ_Smartphone.xlsx` ist jetzt eine saubere Übungsdatei mit
  Hinweisblatt und 2794 unveränderten Messpunkten. Formeln, Ereignismarken und fertige
  Auswertungen sind bewusst nicht enthalten.

## 1.2.0 — 31.08.2026

### Neu
* **Vorlagen zum Selberbauen** unter `vorlagen/`. Sie enthalten den Anfang eines Programms,
  nicht das Programm: den Teil, der immer gleich ist, mit `TODO` an den Stellen, an denen die
  fachliche Entscheidung fällt. Beide Skripte laufen mit reinem Python, ohne zusätzliche
  Bibliotheken.
  * `vorlagen/impuls_aus_beschleunigung.py` — Beschleunigungsdaten einlesen, Ruhewert
    abziehen und zu einer Geschwindigkeit aufintegrieren. Gehört zu den Aufgaben 4 und 5.
  * `vorlagen/wurfweite_winkelsweep.py` — Wurfweite über den Abwurfwinkel durchrechnen.
    Rechnet zunächst nur den Schulfall mit Abwurfhöhe null und weist beim Ausführen selbst
    darauf hin, dass ein Ergebnis von 45 Grad bei angegebener Abwurfhöhe nicht sein kann.
    Gehört zu den Aufgaben 7 und 8, der allgemeine Fall steht in Anhang B des Readers.
  * `vorlagen/KI_Prompt_Sammlung.md` — Einstiegsprompts für die Programmieranteile, nach
    Aufgaben geordnet. Zu jedem Prompt gehört die Gegenprobe, an der sich das Ergebnis
    prüfen lässt.

### Geändert
* Die Einordnung der fünf Anwendungen in `README.md` war unvollständig. Sie sind
  ausdrücklich **Notfalllösungen**: Im Seminar bauen die Studierenden ihr eigenes Werkzeug,
  das ist der Lerngegenstand. Die Anwendungen fangen den Fall auf, dass das im verfügbaren
  Zeitrahmen nicht zustande kommt — damit niemand am Werkzeug scheitert statt an der Sache.

### Hinweis zur Herkunft der Vorlagen
Die beiden Skripte gehen auf zwei Coding-Lab-Gerüste aus dem Begleitmaterial der ersten
Fassung zurück. Sie wurden auf den Aufgabenstand der zweiten Fassung gezogen; der offene
Punkt „Abwurfhöhe einbauen" ist bewusst offen geblieben, weil er inzwischen einem
ausgeführten Anhang des Readers entspricht und damit als Übung tragfähig ist.

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

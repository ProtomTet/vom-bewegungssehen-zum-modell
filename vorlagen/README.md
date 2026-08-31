# Vorlagen zum Selberbauen

Diese Dateien sind der Anfang eines Programms, nicht das Programm. Sie enthalten den
Teil, der immer gleich ist — eine Datei einlesen, eine Summe bilden, eine Schleife über
Winkel laufen lassen — und lassen genau die Stelle offen, an der die fachliche
Entscheidung fällt. Diese Stellen sind mit `TODO` markiert.

## Warum es diesen Ordner gibt

Im Seminar bauen die Studierenden ihr eigenes Werkzeug. Das ist der Punkt der Übung:
Wer eine Auswertung selbst programmiert, muss vorher entscheiden, was gemessen wird,
mit welcher Auflösung und gegen welche Annahme geprüft. Ein fertiges Programm nimmt
genau diese Entscheidungen ab und damit den Lerngegenstand.

Die Anwendungen unter `04_Programme` sind deshalb ausdrücklich **Notfalllösungen**. Sie
fangen den Fall auf, dass ein eigenes Tool im verfügbaren Zeitrahmen nicht zustande
kommt — damit die Aufgabe trotzdem bearbeitbar bleibt und niemand am Werkzeug scheitert
statt an der Sache. Wer weiterkommt, braucht sie nicht.

Die Reihenfolge ist also: erst hier anfangen, dann selbst weiterbauen, und nur wenn das
nicht trägt, auf die Fallback-Anwendung ausweichen.

## Was hier liegt

| Datei | Wofür | Gehört zu |
|---|---|---|
| `impuls_aus_beschleunigung.py` | Beschleunigungsdaten einlesen und über die Zeit zu einer Geschwindigkeit aufintegrieren | Aufgabe 4 und 5 |
| `wurfweite_winkelsweep.py` | Wurfweite über den Abwurfwinkel durchrechnen und das Maximum suchen | Aufgabe 7 und 8 |
| `KI_Prompt_Sammlung.md` | Einstiegsprompts für die Arbeit mit einem Sprachmodell, nach Aufgaben geordnet | alle Programmieranteile |

## Ausführen

Beide Skripte kommen ohne zusätzliche Bibliotheken aus. Sie brauchen nur Python 3.11
oder neuer:

```bash
python impuls_aus_beschleunigung.py
```

Das ist Absicht. Wer die Trapezregel einmal als sechs Zeilen Schleife geschrieben hat,
weiß danach, was `numpy.trapezoid` tut — und kann die Bibliothek anschließend guten
Gewissens verwenden.

## Lizenz

CC BY-SA 4.0, wie der übrige Bestand.

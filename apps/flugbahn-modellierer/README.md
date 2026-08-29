# Flugbahn-Modellierer

Streamlit-App zur didaktischen Modellierung von Flugbahnen für Weitsprung und Kugelstoß.

## Funktionen

- Basisfall mit Eingabe über `v0 + alpha` oder über `v0x + v0z`
- automatische Sweeps für einen veränderlichen Parameter
- manuelle Vergleichsvarianten mit überlagerten Flugbahnen
- Legende mit den tatsächlich geänderten Parametern
- Optimierungsdiagramm für Winkel, Geschwindigkeit oder Höhe
- nachvollziehbarer Rechenweg mit LaTeX-Formeln und eingesetzten Zahlenwerten
- Export der Grafik als PNG oder SVG sowie Export der Bahndaten als CSV

## Start

Im Windows-Explorer in diesen Ordner wechseln, oben in die Adresszeile `powershell` eintippen und Enter druecken. Dann:

```powershell
.\start_flugbahn_modellierer.ps1
```

Alternativ von Hand:

```powershell
python -m streamlit run app.py
```

## Fachliche Grundlage

Die beiden Presets sind exakt auf die Musterloesungen des Seminars abgestimmt:

- **Kugelstoß** (Aufgabe 8): v0x = 8,25 m/s, v0z = 6,23 m/s (v0 = 10,34 m/s, alpha = 37,05°), h0 = 1,83 m, x0 = 0,51 m  ->  erwartete Weite **13,02 m**
- **Weitsprung** (Aufgabe 7): v0x = 6,66 m/s, v0z = 2,83 m/s (v0 = 7,24 m/s, alpha = 23,02°), h0 = 1,04 m, x0 = 0,35 m  ->  erwartete Weite **5,89 m**

Quelle: `03_Aufgaben_und_Loesungen/Musterlösung_Kugelstoß_Aufgabe.docx` bzw. `..._Stickfigures_Weitsprung.docx`.
Weichen die Werte in der App von diesen Zahlen ab, ist das ein Fehler und kein didaktischer Spielraum.

## Modellgrenzen

- kein Luftwiderstand
- Punktmassenmodell
- ebene Landefläche bei `z = 0`

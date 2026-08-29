# Einfacher Videoplayer mit Kalibrierung und Overlay

## Start

```bash
pip install -r requirements_videoplayer.txt
python simple_videoplayer.py
```

## Enthaltene Funktionen

- Video per Dateidialog laden
- Play, Pause, langsame Wiedergabe
- Frameweises Vor- und Zurückspringen
- frei einstellbare Sprungweite in ganzen Frames
- Anzeige von FPS, Δt, aktuellem Frame und Zeit
- 2-Punkt-Kalibrierung für reine Längenreferenz
- 3-Punkt-Kalibrierung für horizontale und vertikale Referenz
- Eingabe des Realmaßes in cm oder m
- Maßstabsleiste im Videobild
- Overlay-Zeichenebene über dem Video
- farbiges Zeichnen mit variabler Stiftdicke
- horizontale und vertikale Overlay-Verschiebung per Drehfeld / Spinbox
- Speichern des Overlays als separates PNG
- PNG-Export automatisch auf den tatsächlich bemalten Bereich zugeschnitten

## Bedienung Kalibrierung

### Modus `horizontal`
1. Auf das gewünschte Frame gehen.
2. `Punkte erfassen / neu setzen` wählen.
3. Punkt 1 links bzw. Startpunkt anklicken.
4. Punkt 2 rechts bzw. Endpunkt anklicken.
5. Reales Maß eingeben.
6. `Kalibrierung anwenden` wählen.

### Modus `horizontal_und_vertikal`
1. Auf das gewünschte Frame gehen.
2. `Punkte erfassen / neu setzen` wählen.
3. Punkt 1 = gemeinsamer Ursprung.
4. Punkt 2 = horizontale Referenz.
5. Punkt 3 = vertikale Referenz.
6. Horizontales und vertikales Realmaß eingeben.
7. `Kalibrierung anwenden` wählen.

## Bedienung Overlay

1. `Overlay anzeigen` aktivieren.
2. `Zeichnen aktiv` einschalten.
3. Farbe wählen.
4. Stiftdicke einstellen.
5. Direkt im Videobild zeichnen.
6. Bei Bedarf das Overlay über `Overlay-Verschiebung X` und `Overlay-Verschiebung Y` frei verschieben.
7. Mit `Overlay als PNG speichern` nur die Zeichnungsebene exportieren.

## Hinweise

- Das gespeicherte PNG enthält **nicht** das Video, sondern nur die Zeichnungsebene.
- Der Export wird automatisch auf den Bereich zugeschnitten, in dem tatsächlich gezeichnet wurde.
- Die Overlay-Daten werden intern als Striche gespeichert. Dadurch bleibt die Verschiebung flexibel und die Ausgabe deutlich glatter als bei einem grob gerasterten Bitmap-Overlay.
- Bei Smartphone-Videos mit variabler Framerate sind FPS und Δt sehr gute Näherungen, aber nicht immer exakt timestamp-genau.
- Beim Laden eines neuen Videos werden Kalibrierung und Overlay bewusst zurückgesetzt, damit keine alten Referenzen versehentlich weiterverwendet werden.
- Referenzpunkte werden nur auf dem Frame angezeigt, auf dem die Kalibrierung gesetzt wurde; die Maßstabsleiste bleibt danach weiter nutzbar.

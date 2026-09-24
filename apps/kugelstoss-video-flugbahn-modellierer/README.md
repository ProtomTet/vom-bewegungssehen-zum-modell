# Kugelstoß – Videoanalyse und Flugbahn-Modellierer

Neue, eigenständige Streamlit-Anwendung. Die vorhandenen Programme **Flugbahn Modellierer** und **Fallback Kugelstoss Liveanalyse Phyphox** bleiben unverändert.

## Funktionen

- lokales Seminarvideo direkt öffnen oder eigenes Video hochladen
- einzelne Normalvideos direkt mit ihrer Metadaten-Bildrate auswerten
- einzelne Zeitlupenvideos mit bekanntem Verlangsamungsfaktor auswerten
- kombinierte Original-/Zeitlupenvideos über zwei gemeinsame Ereignisse zeitlich kalibrieren
- Zeitlupenfaktor bei kombinierten Videos automatisch aus den Bildabständen bestimmen
- zweidimensionale Bildkalibrierung über Ursprung, X- und Z-Referenz
- Kugelmittelpunkt in mehreren Einzelbildern per Mausklick markieren
- Abwurfparameter durch Ausgleichsrechnung bestimmen:
  - horizontale und vertikale Abfluggeschwindigkeit
  - resultierende Abfluggeschwindigkeit
  - Abflugwinkel
  - Abwurfhöhe und horizontale Abwurfposition
- gemessene Parameter direkt in die Flugbahnsimulation übernehmen
- Geschwindigkeit, Winkel oder Abwurfhöhe als Kurvenschar variieren
- Release-Videobild unverzerrt als Startbereich einer gemeinsamen Grafik verwenden
- getrackte Punkte über dem Video anzeigen und die Simulation über dessen Bildrand hinaus fortsetzen
- Export als JSON, CSV sowie gemeinsame Video-/Simulationsgrafik

## Start

Im Windows-Explorer diesen Ordner öffnen, in die Adresszeile `powershell` eingeben und dann ausführen:

```powershell
.\start_video_flugbahn_modellierer.ps1
```

Beim ersten Start werden fehlende Python-Pakete aus `requirements.txt` installiert. Falls im Seminarordner eine virtuelle Umgebung `.venv` vorhanden ist, wird diese bevorzugt.

## Empfohlener Messablauf

1. Beim ersten Laden kurz warten, während automatisch ein kleineres, bildgenau durchsuchbares Analysevideo erzeugt wird.
2. Zeitbasis wählen:
   - **Einzelnes Normalvideo:** `Normalgeschwindigkeit` wählen; eine weitere Zeitkalibrierung entfällt.
   - **Einzelnes Zeitlupenvideo:** den bekannten Zeitlupenfaktor eintragen.
   - **Kombiniertes Video:** Im Original und in der Zeitlupe dieselben zwei Ereignisse markieren und den berechneten Faktor übernehmen.
3. Bild kalibrieren:
   - **O:** Boden-Ursprung im Bewegungsraum
   - **X:** Punkt mit bekannter X-Koordinate; in Stoßrichtung positiv, hinter O negativ
   - **Z:** Punkt mit bekannter Höhe; auswählbar über O oder über der X-Referenz
   - **Ring-Beispiel:** O an der hinteren Ringkante, X am Balken mit `+2,135 m`, Z über X; alternativ O unter dem Balken, X hinten mit `−2,135 m`, Z über O
4. Das Release-Bild bestimmen und dort den Kugelmittelpunkt markieren.
5. Weitere vier bis acht Kugelmittelpunkte aus der frühen Flugphase markieren.
6. Die automatisch übernommenen Messwerte prüfen und Parameter variieren. Das Release-Bild, die getrackten Punkte und die fortgesetzte Simulation erscheinen in einer gemeinsamen Grafik.

## Fachliches Modell

Für die markierten Punkte werden die Gleichungen

```text
x(t) = x0 + v0x · t
z(t) = h0 + v0z · t − 1/2 · g · t²
```

gemeinsam angepasst. Die reale Zeit zwischen zwei Videobildern wird mit

```text
Δt_real = ΔBild / (Metadaten-fps · Zeitlupenfaktor)
```

berechnet. Für ein einzelnes Normalvideo ist der Zeitlupenfaktor `1`. Anschließend verwendet die Simulation dasselbe Punktmassenmodell ohne Luftwiderstand. Für die gemeinsame Grafik bleibt das Release-Bild unverändert; stattdessen werden die simulierten Weltkoordinaten über die inverse Kalibrierung in die ursprüngliche Pixelebene projiziert. Außerhalb des Videobildes wird diese Ebene mit einer weißen Zeichenfläche erweitert.

## Grenzen und Messqualität

- Die Kamera des vorhandenen Videos steht schräg zur Stoßrichtung. Deshalb ist die affine 3-Punkt-Kalibrierung der 2-Punkt-Variante vorzuziehen.
- Kalibrierpunkte und Kugelbahn sollten möglichst in derselben räumlichen Ebene liegen.
- Für eine neue, genauere Aufnahme: Kamera fest aufstellen, optische Achse senkrecht zur Flugbahnebene, bekannte horizontale und vertikale Referenz sichtbar lassen.
- Das vorhandene Video wurde laut Metadaten nachbearbeitet. Die reale Zeitbasis sollte deshalb über den Original-/Zeitlupenvergleich bestimmt werden.
- Mindestens drei, besser vier bis acht frühe Flugpunkte verwenden. Der angezeigte RMSE beschreibt die Streuung der Punkte um die angepasste Flugbahn.

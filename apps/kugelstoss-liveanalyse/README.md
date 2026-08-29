# Kugelstoss Live MVP

Streamlit-MVP fuer eine Phyphox-gestuetzte Live-Ansicht zum Kugelstoss.

## Start

```powershell
streamlit run app.py
```

## Erwartete Phyphox-Seite

Am einfachsten funktioniert ein Experiment, das gleichzeitig diese Buffer bereitstellt:

- Zeit
- lineare Beschleunigung `x/y/z`
- Gyroskop `x/y/z`

Die App versucht die Buffer automatisch zu erkennen. Falls das nicht passt, koennen die Zuordnungen in der Seitenleiste manuell gesetzt werden.

## MVP-Funktionen

- Verbindung zur Phyphox-Remote-Schnittstelle
- Start / Stop / Clear
- Live-Kurven fuer Beschleunigung und Winkelgeschwindigkeit
- automatische Phasenmarken
- einfrierbare Ansicht
- manuell verschiebbares Zeitfenster
- einfache Projektion der Kugelbahn aus `v0`, `alpha`, `h0`

## Hinweise

- Fuer Android liegt die Phyphox-Remote-Schnittstelle typischerweise auf `http://<ip>:8080`.
- Fuer die echte Kugelbahn sind `v0`, `alpha` und `h0` aus Video oder externer Bestimmung weiterhin die bessere Wahl.
- Die Phasenmarken sind in dieser ersten Version heuristisch und fuer Feldtests gedacht.

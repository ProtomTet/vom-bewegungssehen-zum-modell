# phyphox Realtime Accelerator

Lokale Flask-Webanwendung zum Live-Abruf von Beschleunigungsdaten aus **phyphox** über dessen Remote-Access-Schnittstelle.

## Funktionen

- Verbindung zu einem Smartphone mit laufendem phyphox im selben Netzwerk
- Start, Stop und Leeren der Messung
- Live-Darstellung von `a_x`, `a_y`, `a_z` und `|a|`
- Auswahl eines Zeitbereichs per **Zoom** oder **Rangeslider**
- Export des aktuell sichtbaren Bereichs als **Excel-Datei (.xlsx)**
- Manuelle Korrektur der Buffer-Zuordnung, falls die Auto-Erkennung nicht passt

## Start

```bash
python -m venv .venv
source .venv/bin/activate  # unter Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Danach im Browser öffnen:

```text
http://127.0.0.1:5000
```

## phyphox vorbereiten

1. Auf dem Smartphone ein passendes Beschleunigungs-Experiment in phyphox öffnen.
2. In phyphox **Remote Access** aktivieren.
3. Die angezeigte Adresse in diese Anwendung eintragen.

Beispiel:

```text
http://192.168.0.42:8080
```

## Hinweise

- Android verwendet für phyphox typischerweise Port `8080`.
- Auf iPhones läuft die Weboberfläche meist auf Port `80`, daher reicht oft die reine IP-Adresse.
- Beide Geräte müssen sich im selben Netzwerk befinden.
- Die Buffer-Namen hängen vom jeweils verwendeten phyphox-Experiment ab. Die App versucht eine automatische Zuordnung, erlaubt aber jederzeit eine manuelle Korrektur.

## Struktur

- `app.py` – Flask-Backend mit phyphox-Anbindung und Excel-Export
- `templates/index.html` – Oberfläche
- `static/plotly.min.js` – lokale Plotly-Bibliothek


# Kugelstoß – Phyphox und Videosequenzen

Eigenständige Streamlit-Anwendung zur gemeinsamen Darstellung von Phyphox-Signalen und Techniksequenzen eines Kugelstoßvideos. Die vorhandenen Programme bleiben unverändert.

## Zwei bewusst getrennte Betriebsarten

### Phasenreferenz – unterschiedliche Versuche

Für das derzeitige Seminarvideo existiert keine zugehörige Phyphox-Aufnahme. Deshalb werden hier lediglich gleich benannte Phasen nebeneinander dargestellt: etwa Power Position im Video und der automatisch erkannte Bereich in einer Demo-, Live- oder CSV-Messung. Absolute Zeiten dürfen nicht miteinander verglichen werden.

### Exakte Synchronisation – derselbe Versuch

Für zukünftige Versuche können Video und Phyphox denselben Stoß aufzeichnen. Zwei gemeinsame Ereignisse, beispielsweise Bewegungsbeginn und Release, werden in beiden Datenquellen angegeben. Daraus berechnet die App die vollständige lineare Zeitzuordnung einschließlich Startversatz und möglicher Abweichung der Zeitbasis.

## Funktionen

- vorhandenes Seminarvideo oder eigenes Video laden
- fünf Technikereignisse bildgenau markieren
- daraus einzelne Videosequenzen erzeugen und abspielen
- Datenquellen: Demo, Phyphox-CSV oder Phyphox Remote live
- automatische Zuordnung typischer Phyphox-Spalten und Buffer
- gefilterte Beschleunigungs- und Gyroskopsignale
- heuristische Erkennung von Bewegungsbeginn, Kreiszentrum, Power Position, Release und Abfangen
- phasenbezogener Vergleich oder Zwei-Anker-Synchronisation
- Export der Zuordnung als JSON und der verarbeiteten Daten als CSV

## Start

```powershell
.\start_phyphox_video_sequenzanalyse.ps1
```

Für Phyphox Live muss in der Phyphox-App der Fernzugriff aktiviert sein. Computer und Smartphone müssen sich im selben Netzwerk befinden.

# Prompts für die Programmieranteile

Eine Sammlung von Einstiegsprompts für die Arbeit mit einem Sprachmodell, geordnet nach
den Aufgaben des Readers. Sie ersetzen das Nachdenken nicht, sie verkürzen das Tippen.

## Die einzige Regel

Verwenden Sie keinen Code, dessen Ergebnis Sie nicht prüfen können.

Ein Sprachmodell liefert auf jede dieser Fragen sofort etwas Lauffähiges. Lauffähig ist
nicht dasselbe wie richtig: Der häufigste Fall ist nicht der Absturz, sondern die
plausible Zahl, die aus einer falschen Annahme stammt. Ein integriertes Signal, dessen
Nullpunkt nicht abgezogen wurde, läuft anstandslos durch und liefert eine
Absprunggeschwindigkeit, die einfach immer weiter wächst.

Zu jedem Prompt unten gehört deshalb eine Gegenprobe. Sie steht jeweils darunter.

## Tag 1 — Sprint

**Aufgabe 2, aus Bildnummern werden Zeiten**

> Ich habe eine Videoaufnahme mit 240 Bildern pro Sekunde und eine Tabelle mit
> Bildnummer und der abgelesenen Position eines Markers in Pixeln. Schreibe mir
> Python-Code, der daraus Zeit in Sekunden und Position in Metern macht. Die
> Umrechnung von Pixeln in Meter soll über eine im Bild sichtbare Referenzstrecke
> bekannter Länge laufen. Berechne anschließend Geschwindigkeit und Beschleunigung
> über Differenzenquotienten und sage mir bei jedem Schritt, welchen Fehler die
> Ableseungenauigkeit an dieser Stelle verursacht.

*Gegenprobe:* Lassen Sie sich die Geschwindigkeit im gleichmäßigen Abschnitt ausgeben.
Weicht sie stark von der ab, die Sie aus Gesamtstrecke durch Gesamtzeit ausrechnen, ist
die Kalibrierung falsch, nicht die Bewegung ungleichmäßig.

**Zusatzaufgabe S1, Differenzzeitdiagramm**

> Ich habe Zwischenzeiten von vier Läufern über 100 Meter, gemessen alle 10 Meter.
> Schreibe mir Code, der daraus ein Differenzzeitdiagramm gegen einen frei wählbaren
> Referenzlauf erzeugt. Erkläre mir vorher in zwei Sätzen, was auf der y-Achse steht
> und warum ein Differenzzeitdiagramm mehr zeigt als ein Weg-Zeit-Diagramm.

*Gegenprobe:* Der Referenzlauf muss im Diagramm eine waagerechte Linie bei null sein.
Ist er das nicht, ist die Subtraktionsrichtung vertauscht.

## Tag 2 — Sprung

**Aufgabe 4, Sensordaten einlesen und aufbereiten**

> Schreibe Python-Code, der eine CSV aus phyphox einliest (Zeit und
> Beschleunigungskomponenten), das Signal mit einem Savitzky-Golay-Filter glättet und
> daraus durch numerische Integration die Geschwindigkeit über der Zeit berechnet.
> Erkläre mir bei der Wahl von Fensterbreite und Polynomgrad, was ich damit an der
> Bewegung verliere.

*Gegenprobe:* Legen Sie das geglättete Signal über das rohe. Verschwindet der
Kraftgipfel beim Absprung, ist zu stark geglättet worden — dann glättet der Filter
nicht das Rauschen, sondern die Aussage.

**Aufgabe 5, Impuls und Sprunghöhe**

> Erkläre mir die Schritte, um aus einer Kraft-Zeit-Kurve den Impuls zu berechnen und
> daraus die Absprunggeschwindigkeit zu gewinnen. Gib mir das Ergebnis zweimal: als
> Excel-Formel und als Python-Funktion. Sage mir außerdem, welche Annahme über den
> Zustand zu Beginn der Messung ich dabei stillschweigend treffe.

*Gegenprobe:* Rechnen Sie die Sprunghöhe zusätzlich aus der Flugzeit. Die beiden Werte
werden auseinanderliegen. Diese Differenz ist das eigentliche Ergebnis der Aufgabe —
wer sie wegdiskutiert, hat die Aufgabe nicht gelöst, sondern umgangen.

**Aufgabe 6, eine Station zum Mitmessen**

> Entwirf mir eine kleine Streamlit-Anwendung für eine Sprungstation im Schulsport.
> Sie soll eine phyphox-Aufnahme entgegennehmen, die Sprunghöhe berechnen und sie
> zusammen mit dem Kurvenverlauf anzeigen. Wichtig: Die Anwendung soll die
> Absprungphase im Signal markieren, damit sichtbar ist, worauf sich die Zahl stützt.
> Halte den Code kurz genug, dass ich ihn im Seminar vorführen kann.

*Gegenprobe:* Testen Sie mit einer Aufnahme, in der jemand nicht springt, sondern nur
in die Knie geht. Zeigt die Anwendung trotzdem eine Sprunghöhe an, fehlt die
Plausibilitätsprüfung.

## Tag 3 — Wurf und Sprung in die Weite

**Aufgabe 8, theoretische Weite**

> Schreibe mir Python-Code, der die Wurfweite aus Abwurfgeschwindigkeit, Abwurfwinkel
> und Abwurfhöhe berechnet — ohne Luftwiderstand, aber mit Abwurfhöhe ungleich null.
> Zeige mir die Herleitung der Flugzeit als quadratische Gleichung, bevor du den Code
> schreibst. Lass mich anschließend den Winkel systematisch variieren und gib das
> Maximum aus.

*Gegenprobe:* Setzen Sie die Abwurfhöhe auf null. Das Maximum muss dann bei 45 Grad
liegen. Tut es das nicht, stimmt die Herleitung nicht.

**Aufgabe 9, Sensorik am Kugelstoß**

> Ich möchte den Abwurfzeitpunkt beim Kugelstoß aus einem Beschleunigungssignal
> automatisch erkennen. Schlage mir drei verschiedene Kriterien vor, nenne zu jedem
> den Fall, in dem es versagt, und empfiehl mir eines für eine Aufnahme mit rund
> 200 Hz Abtastrate.

*Gegenprobe:* Prüfen Sie das gewählte Kriterium an einer Aufnahme mit einem Fehlversuch.
Ein Kriterium, das nur bei gelungenen Versuchen funktioniert, ist keines.

## Tabellenkalkulation

**Fläche unter der Kurve in Excel**

> Schreibe ein VBA-Makro, das in Spalte A die Zeit in Sekunden und in Spalte B die
> Kraft in Newton liest, die Fläche unter der Kurve nach der Trapezregel berechnet und
> das Ergebnis in Zelle D2 ausgibt. Ergänze eine zweite Variante ohne Makro, nur mit
> Zellformeln, und sage mir, wann welche die bessere Wahl ist.

*Gegenprobe:* Legen Sie eine konstante Kraft von 100 N über 2 Sekunden an. Es müssen
200 Ns herauskommen. Weicht das Ergebnis ab, ist der erste oder der letzte Streifen
falsch gezählt.

## Unterrichtstransfer

> Formuliere einen Arbeitsauftrag für eine 11. oder 12. Klasse, in dem eine Wurfparabel
> per Videoanalyse gemessen und der optimale Abwurfwinkel diskutiert wird. Nenne
> Zielsetzung, Arbeitsauftrag, Materialliste und das erwartete Produkt getrennt
> voneinander. Ergänze Sicherheitshinweise und einen Hinweis darauf, welche
> Messgenauigkeit die beabsichtigte Aussage überhaupt verlangt.

*Gegenprobe:* Lesen Sie den Auftrag mit der Frage, ob eine Schülerin ihn ohne
Rückfrage ausführen könnte. Meist fehlt die Angabe, von wo aus gefilmt wird.

## Was nicht gut funktioniert

Nach der fertigen Auswertung zu fragen. „Werte mir diese Kugelstoßaufnahme aus" führt
zu einer Zahl ohne nachvollziehbaren Weg — und damit zu genau dem, was der Reader an
mehreren Stellen als die folgenreichere der beiden Abkürzungen beschreibt: Das Ergebnis
wird berechnet, aufgeschrieben und nicht geprüft.

Fragen Sie stattdessen nach dem Schritt, an dem Sie hängen. Und lassen Sie sich die
Annahmen mit ausgeben, nicht nur den Code.

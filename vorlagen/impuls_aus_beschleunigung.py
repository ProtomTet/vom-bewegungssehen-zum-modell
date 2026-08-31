# -*- coding: utf-8 -*-
"""Vorlage: aus Beschleunigungsdaten eine Geschwindigkeit gewinnen.

Gehoert zu Aufgabe 4 (Sensorik vorbereiten) und Aufgabe 5 (Absprunggeschwindigkeit
und Sprunghoehe vergleichen).

Was die Vorlage schon kann: eine CSV einlesen und ueber die Zeit integrieren.
Was Sie entscheiden muessen, steht als TODO im Text. Es sind vier Entscheidungen,
und drei davon sind fachlich, nicht technisch.

Ausfuehren:  python impuls_aus_beschleunigung.py phyphox_export.csv
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

G = 9.81  # m/s^2


def lade_zeit_und_beschleunigung(pfad: Path) -> tuple[list[float], list[float]]:
    """Liest zwei Spalten aus einer CSV.

    TODO 1 — Spaltennamen pruefen. phyphox benennt die Spalten je nach Sensor und
    Spracheinstellung unterschiedlich ("Time (s)", "Zeit (s)", "Absolute acceleration
    (m/s^2)" ...). Oeffnen Sie die Datei einmal in einem Editor und tragen Sie die
    tatsaechlichen Namen ein, statt zu raten.
    """
    spalte_zeit = "time"
    spalte_beschleunigung = "acc"

    zeit: list[float] = []
    wert: list[float] = []
    with pfad.open("r", encoding="utf-8", newline="") as f:
        leser = csv.DictReader(f)
        if leser.fieldnames and spalte_zeit not in leser.fieldnames:
            raise SystemExit(
                "Spalte %r nicht gefunden. Vorhanden sind: %s"
                % (spalte_zeit, ", ".join(leser.fieldnames))
            )
        for zeile in leser:
            zeit.append(float(zeile[spalte_zeit]))
            wert.append(float(zeile[spalte_beschleunigung]))
    return zeit, wert


def ruhewert(zeit: list[float], wert: list[float], bis_sekunde: float = 0.5) -> float:
    """Mittelwert der ersten ruhigen Sekundenbruchteile.

    TODO 2 — Die wichtigste Entscheidung der ganzen Aufgabe. Ein Beschleunigungssensor
    misst in Ruhe nicht null, sondern die Erdbeschleunigung. Wer diesen Anteil nicht
    abzieht, integriert ihn auf und bekommt eine Geschwindigkeit, die immer weiter
    waechst. Pruefen Sie, ob die hier angenommene Ruhephase in Ihrer Aufnahme
    tatsaechlich ruhig ist — sonst verschieben Sie den Nullpunkt mit dem Fehler.
    """
    proben = [w for t, w in zip(zeit, wert) if t - zeit[0] <= bis_sekunde]
    if not proben:
        raise SystemExit("Keine Ruhephase gefunden. Zeitfenster anpassen.")
    return sum(proben) / len(proben)


def integriere(zeit: list[float], wert: list[float]) -> list[float]:
    """Trapezregel: die Flaeche unter der Kurve, Stueck fuer Stueck aufsummiert.

    Genau das, was im Reader als Impulsflaeche beschrieben ist — hier fuer die
    Beschleunigung, sodass eine Geschwindigkeit herauskommt.
    """
    aus = [0.0]
    for i in range(1, len(zeit)):
        dt = zeit[i] - zeit[i - 1]
        aus.append(aus[-1] + 0.5 * (wert[i] + wert[i - 1]) * dt)
    return aus


def sprunghoehe_aus_geschwindigkeit(v_ab: float) -> float:
    """Steighoehe des Schwerpunkts aus der Absprunggeschwindigkeit."""
    return v_ab * v_ab / (2 * G)


if __name__ == "__main__":
    pfad = Path(sys.argv[1] if len(sys.argv) > 1 else "phyphox_export.csv")
    if not pfad.exists():
        raise SystemExit("Datei nicht gefunden: %s" % pfad)

    zeit, roh = lade_zeit_und_beschleunigung(pfad)
    null = ruhewert(zeit, roh)
    bereinigt = [w - null for w in roh]
    v = integriere(zeit, bereinigt)

    # TODO 3 — Bis wohin integrieren? Die Absprunggeschwindigkeit ist der Wert im
    # Moment des letzten Bodenkontakts, nicht der letzte Wert der Datei. Suchen Sie
    # diesen Zeitpunkt im Signal, statt v[-1] zu nehmen.
    v_ab = max(v)

    print("Messpunkte      : %d" % len(zeit))
    print("Abtastrate      : %.0f Hz" % ((len(zeit) - 1) / (zeit[-1] - zeit[0])))
    print("Ruhewert        : %.3f m/s^2  (abgezogen)" % null)
    print("v_ab (vorlaeufig): %.2f m/s" % v_ab)
    print("Sprunghoehe     : %.3f m" % sprunghoehe_aus_geschwindigkeit(v_ab))

    # TODO 4 — Gegenprobe. Rechnen Sie dieselbe Sprunghoehe zusaetzlich aus der
    # Flugzeit und vergleichen Sie. Die beiden Werte werden nicht gleich sein. Diese
    # Abweichung ist kein Fehler, sondern das Ergebnis der Aufgabe: Sie zerfaellt in
    # einen Anfangswertanteil und einen Anteil, den der Sensor nicht aufloest.

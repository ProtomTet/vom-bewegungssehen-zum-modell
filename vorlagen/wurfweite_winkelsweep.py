# -*- coding: utf-8 -*-
"""Vorlage: die Wurfweite ueber den Abwurfwinkel durchrechnen.

Gehoert zu Aufgabe 7 (Weitsprung) und Aufgabe 8 (Kugelstoss).

Die Vorlage rechnet den Schulfall: Abwurf und Aufkommen auf gleicher Hoehe, kein
Luftwiderstand. Dann liegt das Maximum bei 45 Grad — eine Zahl, die jeder kennt und
die im Sport fast nie stimmt.

Genau daran haengt die Aufgabe. Eine Kugel verlaesst die Hand in rund zwei Metern
Hoehe und kommt am Boden auf. Sobald die Abwurfhoehe groesser als null ist, sinkt der
optimale Winkel deutlich unter 45 Grad. Anhang B des Readers fuehrt den allgemeinen
Fall aus; hier ist er als TODO 1 offen gelassen.

Ausfuehren:  python wurfweite_winkelsweep.py
"""
from __future__ import annotations

import math

G = 9.81  # m/s^2


def weite(v0: float, winkel_grad: float, y0: float = 0.0, g: float = G) -> float:
    """Wurfweite bei Abwurfgeschwindigkeit v0, Winkel und Abwurfhoehe y0.

    TODO 1 — y0 wird bisher entgegengenommen, aber nicht verwendet. Ergaenzen Sie den
    allgemeinen Fall nach Anhang B des Readers. Sinnvoller Weg: Zerlegen Sie v0 in
    vx und vz, bestimmen Sie die Flugzeit als positive Loesung der quadratischen
    Gleichung fuer die Hoehe, und multiplizieren Sie sie mit vx.

    Kontrolle: Fuer y0 = 0 muss Ihre Formel wieder denselben Wert liefern wie die
    einfache Beziehung unten. Wenn nicht, ist der Fehler in Ihrer Herleitung, nicht
    in der Vorlage.
    """
    a = math.radians(winkel_grad)
    return (v0 * v0 * math.sin(2 * a)) / g


def bester_winkel(v0: float, y0: float = 0.0, schritt: float = 0.5) -> tuple[float, float]:
    """Sucht den Winkel mit der groessten Weite, indem er alle durchprobiert.

    Kein elegantes Verfahren, aber ein durchschaubares — und fuer die Frage, worauf
    es hier ankommt, das bessere.

    TODO 2 — Die Schrittweite bestimmt, wie genau das Ergebnis sein kann. Probieren
    Sie 5 Grad, 1 Grad und 0,1 Grad und sehen Sie nach, ab wann sich am Ergebnis
    nichts mehr aendert. Das ist dieselbe Frage wie die nach der Bildrate bei der
    Videoanalyse: Welche Aufloesung braucht die beabsichtigte Aussage?
    """
    beste = (0.0, -1.0)
    winkel = schritt
    while winkel < 90.0:
        s = weite(v0, winkel, y0)
        if s > beste[1]:
            beste = (winkel, s)
        winkel += schritt
    return beste


if __name__ == "__main__":
    v0 = 10.35   # m/s, Abwurfgeschwindigkeit aus der Kugelstoss-Messreihe
    y0 = 2.05    # m, Abwurfhoehe — wird erst nach TODO 1 wirksam

    winkel, s = bester_winkel(v0, y0)
    print("v0 = %.2f m/s, y0 = %.2f m" % (v0, y0))
    print("bester Winkel : %.1f Grad" % winkel)
    print("Weite dabei   : %.2f m" % s)
    if abs(winkel - 45.0) < 1.0 and y0 > 0.0:
        print()
        print("Achtung: Das Ergebnis liegt bei 45 Grad, obwohl eine Abwurfhoehe von")
        print("%.2f m angegeben ist. Das kann nicht sein - TODO 1 ist noch offen," % y0)
        print("y0 wird von weite() bisher nicht verwendet.")
    print()
    print("Weite ueber den Winkel:")
    for w in (30, 35, 40, 42, 45, 50, 55):
        print("   %2d Grad : %5.2f m" % (w, weite(v0, w, y0)))

    # TODO 3 — Vergleich mit der Wirklichkeit. Messen Sie an Ihrer eigenen Aufnahme
    # den tatsaechlichen Abwurfwinkel und die tatsaechliche Weite. Beides wird von
    # der Rechnung abweichen. Benennen Sie, welche Annahme dieses Modells dafuer
    # verantwortlich ist — das ist das Produkt der Aufgabe, nicht die Zahl.

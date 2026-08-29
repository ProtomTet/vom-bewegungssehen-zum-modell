from __future__ import annotations

from dataclasses import dataclass, replace
from math import atan2, cos, degrees, radians, sin, sqrt, tan
from typing import Iterable, Mapping

import numpy as np
import pandas as pd


DEFAULT_GRAVITY = 9.81
VARIANT_COLUMNS = ["label", "v0_m_s", "alpha_deg", "h0_m", "x0_m", "g_m_s2"]
PARAMETER_META = {
    "v0_m_s": {"label": "Abfluggeschwindigkeit v0", "unit": "m/s", "step": 0.1},
    "alpha_deg": {"label": "Abflugwinkel alpha", "unit": "deg", "step": 0.5},
    "h0_m": {"label": "Abflughöhe h0", "unit": "m", "step": 0.01},
    "x0_m": {"label": "Startversatz x0", "unit": "m", "step": 0.01},
    "g_m_s2": {"label": "Erdbeschleunigung g", "unit": "m/s²", "step": 0.01},
}


@dataclass(slots=True)
class VariantConfig:
    label: str
    v0_m_s: float
    alpha_deg: float
    h0_m: float
    x0_m: float
    g_m_s2: float = DEFAULT_GRAVITY
    note: str = ""


@dataclass(slots=True)
class FlightResult:
    variant: VariantConfig
    trajectory: pd.DataFrame
    vx_m_s: float
    vz_m_s: float
    flight_time_s: float
    peak_time_s: float
    peak_height_m: float
    landing_x_m: float
    flight_distance_m: float
    slope: float
    curvature: float


@dataclass(slots=True)
class ScenarioPreset:
    name: str
    description: str
    source_note: str
    base_variant: VariantConfig


PRESETS: dict[str, ScenarioPreset] = {
    "Kugelstoß": ScenarioPreset(
        name="Kugelstoß",
        description=(
            "Punktmassenmodell für den Abstoß ohne Luftwiderstand. "
            "Gut geeignet, um Abwurfwinkel, Abwurfgeschwindigkeit und Abwurfhöhe "
            "didaktisch gegeneinander abzuwägen."
        ),
        source_note=(
            "Dokumentwerte der Musterloesung zu Aufgabe 8 "
            "('03_Aufgaben_und_Loesungen/Musterloesung_Kugelstoss_Aufgabe.docx'): "
            "v0x = 8.25 m/s, v0z = 6.23 m/s -> v0 = 10.34 m/s, alpha = 37.05 deg, "
            "h0 = 1.83 m, x0 = 0.51 m (Handueberhang W1). "
            "Erwartete Weite: 13.02 m."
        ),
        base_variant=VariantConfig(
            label="Basisfall",
            v0_m_s=sqrt(8.25**2 + 6.23**2),
            alpha_deg=degrees(atan2(6.23, 8.25)),
            h0_m=1.83,
            x0_m=0.51,
            g_m_s2=DEFAULT_GRAVITY,
        ),
    ),
    "Weitsprung": ScenarioPreset(
        name="Weitsprung",
        description=(
            "Modellierte Flugphase des Körperschwerpunkts nach dem Absprung. "
            "Die Körperhaltung kann sich ändern, die Schwerpunktsbahn bleibt im Modell parabelförmig."
        ),
        source_note=(
            "Dokumentwerte der Musterloesung zu Aufgabe 7 "
            "('03_Aufgaben_und_Loesungen/Musterloesung_Stickfigures_Weitsprung.docx'): "
            "v0x = 6.66 m/s, v0z = 2.83 m/s -> v0 = 7.24 m/s, alpha = 23.02 deg, "
            "h0 = 1.04 m, x0 = 0.35 m (KSP-Ueberhang). "
            "Erwartete Weite: 5.89 m."
        ),
        base_variant=VariantConfig(
            label="Basisfall",
            v0_m_s=sqrt(6.66**2 + 2.83**2),
            alpha_deg=degrees(atan2(2.83, 6.66)),
            h0_m=1.04,
            x0_m=0.35,
            g_m_s2=DEFAULT_GRAVITY,
        ),
    ),
}


def empty_variant_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=VARIANT_COLUMNS)


def parameter_label(parameter_key: str) -> str:
    return str(PARAMETER_META[parameter_key]["label"])


def parameter_unit(parameter_key: str) -> str:
    return str(PARAMETER_META[parameter_key]["unit"])


def parameter_step(parameter_key: str) -> float:
    return float(PARAMETER_META[parameter_key]["step"])


def components_from_polar(v0_m_s: float, alpha_deg: float) -> tuple[float, float]:
    angle_rad = radians(float(alpha_deg))
    return float(v0_m_s) * cos(angle_rad), float(v0_m_s) * sin(angle_rad)


def polar_from_components(vx_m_s: float, vz_m_s: float) -> tuple[float, float]:
    v0_m_s = sqrt(float(vx_m_s) ** 2 + float(vz_m_s) ** 2)
    alpha_deg = degrees(atan2(float(vz_m_s), float(vx_m_s))) if v0_m_s else 0.0
    return v0_m_s, alpha_deg


def sanitize_variant(raw_variant: Mapping[str, object], fallback_label: str) -> VariantConfig:
    label = str(raw_variant.get("label") or "").strip() or fallback_label
    v0_m_s = max(0.0, float(raw_variant.get("v0_m_s") or 0.0))
    alpha_deg = float(raw_variant.get("alpha_deg") or 0.0)
    h0_m = max(0.0, float(raw_variant.get("h0_m") or 0.0))
    x0_m = float(raw_variant.get("x0_m") or 0.0)
    g_m_s2 = max(0.1, float(raw_variant.get("g_m_s2") or DEFAULT_GRAVITY))
    return VariantConfig(
        label=label,
        v0_m_s=v0_m_s,
        alpha_deg=alpha_deg,
        h0_m=h0_m,
        x0_m=x0_m,
        g_m_s2=g_m_s2,
    )


def variants_to_frame(variants: Iterable[VariantConfig]) -> pd.DataFrame:
    rows = []
    for variant in variants:
        rows.append(
            {
                "label": variant.label,
                "v0_m_s": variant.v0_m_s,
                "alpha_deg": variant.alpha_deg,
                "h0_m": variant.h0_m,
                "x0_m": variant.x0_m,
                "g_m_s2": variant.g_m_s2,
            }
        )
    if not rows:
        return empty_variant_frame()
    return pd.DataFrame(rows, columns=VARIANT_COLUMNS)


def frame_to_variants(frame: pd.DataFrame) -> list[VariantConfig]:
    if frame.empty:
        return []

    variants: list[VariantConfig] = []
    for idx, row in frame.fillna("").iterrows():
        if not any(str(value).strip() for value in row.to_list()):
            continue
        variants.append(sanitize_variant(row.to_dict(), fallback_label=f"Variante {idx + 1}"))
    return variants


def deduplicate_variants(variants: Iterable[VariantConfig]) -> list[VariantConfig]:
    unique_variants: list[VariantConfig] = []
    signatures: set[tuple[float, float, float, float, float]] = set()
    for variant in variants:
        signature = (
            round(variant.v0_m_s, 6),
            round(variant.alpha_deg, 6),
            round(variant.h0_m, 6),
            round(variant.x0_m, 6),
            round(variant.g_m_s2, 6),
        )
        if signature in signatures:
            continue
        signatures.add(signature)
        unique_variants.append(variant)
    return unique_variants


def flight_time_from_components(vz_m_s: float, h0_m: float, g_m_s2: float) -> float:
    discriminant = max(0.0, float(vz_m_s) ** 2 + 2.0 * float(g_m_s2) * float(h0_m))
    return (float(vz_m_s) + sqrt(discriminant)) / float(g_m_s2)


def evaluate_variant(variant: VariantConfig, num_points: int = 240) -> FlightResult:
    vx_m_s, vz_m_s = components_from_polar(variant.v0_m_s, variant.alpha_deg)
    flight_time_s = max(0.0, flight_time_from_components(vz_m_s, variant.h0_m, variant.g_m_s2))
    sample_count = max(80, int(num_points))
    times = np.linspace(0.0, flight_time_s, sample_count)
    x_values = variant.x0_m + vx_m_s * times
    z_values = variant.h0_m + vz_m_s * times - 0.5 * variant.g_m_s2 * times**2
    z_values = np.maximum(z_values, 0.0)

    peak_time_s = 0.0
    if vz_m_s > 0.0:
        peak_time_s = min(flight_time_s, vz_m_s / variant.g_m_s2)
    peak_height_m = variant.h0_m + vz_m_s * peak_time_s - 0.5 * variant.g_m_s2 * peak_time_s**2
    landing_x_m = float(x_values[-1]) if len(x_values) else variant.x0_m
    horizontal_speed = max(abs(vx_m_s), 1e-9)

    trajectory = pd.DataFrame(
        {
            "t_s": times,
            "x_m": x_values,
            "z_m": z_values,
        }
    )
    return FlightResult(
        variant=variant,
        trajectory=trajectory,
        vx_m_s=vx_m_s,
        vz_m_s=vz_m_s,
        flight_time_s=flight_time_s,
        peak_time_s=peak_time_s,
        peak_height_m=float(peak_height_m),
        landing_x_m=landing_x_m,
        flight_distance_m=landing_x_m - variant.x0_m,
        slope=vz_m_s / horizontal_speed,
        curvature=variant.g_m_s2 / (2.0 * horizontal_speed**2),
    )


def changed_parameters(variant: VariantConfig, base_variant: VariantConfig) -> list[str]:
    changes: list[str] = []
    if abs(variant.v0_m_s - base_variant.v0_m_s) > 1e-9:
        changes.append(f"v0={variant.v0_m_s:.2f} m/s")
    if abs(variant.alpha_deg - base_variant.alpha_deg) > 1e-9:
        changes.append(f"alpha={variant.alpha_deg:.2f} deg")
    if abs(variant.h0_m - base_variant.h0_m) > 1e-9:
        changes.append(f"h0={variant.h0_m:.2f} m")
    if abs(variant.x0_m - base_variant.x0_m) > 1e-9:
        changes.append(f"x0={variant.x0_m:.2f} m")
    if abs(variant.g_m_s2 - base_variant.g_m_s2) > 1e-9:
        changes.append(f"g={variant.g_m_s2:.2f} m/s²")
    return changes


def legend_label(variant: VariantConfig, base_variant: VariantConfig) -> str:
    base_name = variant.label.strip() or "Variante"
    if variant.label == base_variant.label and not changed_parameters(variant, base_variant):
        return base_name
    changes = changed_parameters(variant, base_variant)
    if not changes:
        return base_name
    return f"{base_name} ({', '.join(changes)})"


def build_sweep_variants(
    base_variant: VariantConfig,
    parameter_key: str,
    start_value: float,
    stop_value: float,
    curve_count: int,
    label_prefix: str = "Sweep",
) -> list[VariantConfig]:
    values = np.linspace(float(start_value), float(stop_value), num=max(2, int(curve_count)))
    variants: list[VariantConfig] = []
    for index, value in enumerate(values, start=1):
        updated_variant = replace(base_variant, label=f"{label_prefix} {index}")
        setattr(updated_variant, parameter_key, float(value))
        variants.append(updated_variant)
    return variants


def optimization_dataframe(
    base_variant: VariantConfig,
    parameter_key: str,
    start_value: float,
    stop_value: float,
    resolution: int = 161,
) -> tuple[pd.DataFrame, FlightResult]:
    values = np.linspace(float(start_value), float(stop_value), num=max(5, int(resolution)))
    rows = []
    best_result: FlightResult | None = None

    for value in values:
        variant = replace(base_variant, label="Optimum-Suche")
        setattr(variant, parameter_key, float(value))
        result = evaluate_variant(variant)
        rows.append(
            {
                "parameter_value": float(value),
                "flight_distance_m": result.flight_distance_m,
                "landing_x_m": result.landing_x_m,
                "peak_height_m": result.peak_height_m,
                "flight_time_s": result.flight_time_s,
            }
        )
        if best_result is None or result.flight_distance_m > best_result.flight_distance_m:
            best_result = result

    optimization_frame = pd.DataFrame(rows)
    if best_result is None:
        best_result = evaluate_variant(base_variant)
    return optimization_frame, best_result


def summary_dataframe(results: Iterable[FlightResult], base_variant: VariantConfig) -> pd.DataFrame:
    rows = []
    for result in results:
        rows.append(
            {
                "Variante": legend_label(result.variant, base_variant),
                "v0 [m/s]": result.variant.v0_m_s,
                "alpha [deg]": result.variant.alpha_deg,
                "h0 [m]": result.variant.h0_m,
                "x0 [m]": result.variant.x0_m,
                "Flugzeit [s]": result.flight_time_s,
                "Flugweite Delta x [m]": result.flight_distance_m,
                "Landepunkt x [m]": result.landing_x_m,
                "Scheitelhöhe [m]": result.peak_height_m,
            }
        )
    return pd.DataFrame(rows)


def combined_trajectory_dataframe(results: Iterable[FlightResult], base_variant: VariantConfig) -> pd.DataFrame:
    frames = []
    for result in results:
        trajectory = result.trajectory.copy()
        trajectory.insert(0, "Variante", legend_label(result.variant, base_variant))
        frames.append(trajectory)
    if not frames:
        return pd.DataFrame(columns=["Variante", "t_s", "x_m", "z_m"])
    return pd.concat(frames, ignore_index=True)


def suggested_bounds(base_variant: VariantConfig, parameter_key: str) -> tuple[float, float]:
    base_value = float(getattr(base_variant, parameter_key))
    if parameter_key == "alpha_deg":
        return max(5.0, base_value - 10.0), min(60.0, base_value + 10.0)
    if parameter_key == "v0_m_s":
        return max(0.5, base_value - 2.0), base_value + 2.0
    if parameter_key == "h0_m":
        return max(0.1, base_value - 0.35), base_value + 0.35
    if parameter_key == "x0_m":
        return base_value - 0.4, base_value + 0.4
    if parameter_key == "g_m_s2":
        return max(1.0, base_value - 0.5), base_value + 0.5
    return base_value, base_value


def z_of_x_expression(result: FlightResult) -> str:
    x0 = result.variant.x0_m
    h0 = result.variant.h0_m
    slope = tan(radians(result.variant.alpha_deg))
    curvature = result.curvature
    return (
        f"z(x) = {h0:.2f} + {slope:.3f}(x - {x0:.2f}) "
        f"- {curvature:.3f}(x - {x0:.2f})^2"
    )

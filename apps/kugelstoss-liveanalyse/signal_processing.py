from __future__ import annotations

from dataclasses import dataclass
from math import cos, radians, sin, sqrt

import numpy as np
import pandas as pd
from scipy.signal import butter, filtfilt, find_peaks


@dataclass(slots=True)
class PhaseEvent:
    label: str
    time_s: float
    color: str


@dataclass(slots=True)
class ProcessingSettings:
    phase_cutoff_hz: float = 7.0
    event_cutoff_hz: float = 16.0
    filter_order: int = 4


def estimate_sample_rate_hz(time_values: pd.Series) -> float:
    if len(time_values) < 3:
        return 0.0
    diffs = np.diff(time_values.to_numpy(dtype=float))
    diffs = diffs[diffs > 0]
    if len(diffs) == 0:
        return 0.0
    return float(1.0 / np.median(diffs))


def _lowpass(values: np.ndarray, sample_rate_hz: float, cutoff_hz: float, order: int) -> np.ndarray:
    if sample_rate_hz <= 0 or cutoff_hz <= 0:
        return values.copy()
    nyquist = 0.5 * sample_rate_hz
    normalized = min(cutoff_hz / nyquist, 0.99)
    if normalized <= 0:
        return values.copy()
    b_coeff, a_coeff = butter(order, normalized, btype="low", analog=False)
    # filtfilt spiegelt das Signal an den Raendern und braucht dafuer mehr Werte,
    # als der Filter Koeffizienten hat. Die Grenze ergibt sich aus den tatsaechlichen
    # Koeffizienten, nicht aus der Ordnung allein: padlen = 3 * max(len(a), len(b)).
    # Ist das Signal kuerzer, wird es ungefiltert durchgereicht, statt abzustuerzen.
    padlen = 3 * max(len(a_coeff), len(b_coeff))
    if len(values) <= padlen:
        return values.copy()
    return filtfilt(b_coeff, a_coeff, values)


def _safe_series(frame: pd.DataFrame, column: str) -> np.ndarray:
    if column in frame.columns:
        return frame[column].to_numpy(dtype=float)
    return np.zeros(len(frame), dtype=float)


def enrich_signals(frame: pd.DataFrame, settings: ProcessingSettings) -> tuple[pd.DataFrame, float]:
    if frame.empty:
        return frame.copy(), 0.0

    enriched = frame.copy()
    sample_rate_hz = estimate_sample_rate_hz(enriched["time"])

    acc_x = _safe_series(enriched, "acc_x")
    acc_y = _safe_series(enriched, "acc_y")
    acc_z = _safe_series(enriched, "acc_z")
    gyro_x = _safe_series(enriched, "gyro_x")
    gyro_y = _safe_series(enriched, "gyro_y")
    gyro_z = _safe_series(enriched, "gyro_z")

    enriched.loc[:, "acc_resultant"] = np.sqrt(acc_x**2 + acc_y**2 + acc_z**2)
    enriched.loc[:, "gyro_resultant"] = np.sqrt(gyro_x**2 + gyro_y**2 + gyro_z**2)

    for column in ("acc_x", "acc_z", "acc_resultant", "gyro_z", "gyro_resultant"):
        raw_values = _safe_series(enriched, column)
        enriched.loc[:, f"{column}_phase"] = _lowpass(
            raw_values,
            sample_rate_hz=sample_rate_hz,
            cutoff_hz=settings.phase_cutoff_hz,
            order=settings.filter_order,
        )
        enriched.loc[:, f"{column}_event"] = _lowpass(
            raw_values,
            sample_rate_hz=sample_rate_hz,
            cutoff_hz=settings.event_cutoff_hz,
            order=settings.filter_order,
        )

    return enriched, sample_rate_hz


def _first_true_run(mask: np.ndarray, min_run: int) -> int | None:
    run_length = 0
    for idx, value in enumerate(mask):
        if value:
            run_length += 1
            if run_length >= min_run:
                return idx - min_run + 1
        else:
            run_length = 0
    return None


def _clip_index(idx: int, length: int) -> int:
    return max(0, min(idx, length - 1))


def detect_phases(frame: pd.DataFrame, sample_rate_hz: float) -> list[PhaseEvent]:
    if frame.empty or sample_rate_hz <= 0:
        return []

    time_values = frame["time"].to_numpy(dtype=float)
    acc_resultant = frame["acc_resultant_event"].to_numpy(dtype=float)
    acc_forward = frame["acc_x_event"].to_numpy(dtype=float)
    acc_vertical = frame["acc_z_event"].to_numpy(dtype=float)
    gyro_turn = np.abs(frame["gyro_z_event"].to_numpy(dtype=float))
    gyro_resultant = frame["gyro_resultant_event"].to_numpy(dtype=float)

    baseline_mask = time_values <= (time_values[0] + min(0.8, max(time_values[-1] - time_values[0], 0.8) * 0.2))
    if not np.any(baseline_mask):
        baseline_mask = np.arange(len(frame)) < min(len(frame), max(10, int(0.2 * sample_rate_hz)))

    baseline_acc = acc_resultant[baseline_mask]
    baseline_gyro = gyro_resultant[baseline_mask]
    acc_threshold = float(np.mean(baseline_acc) + max(0.6, 2.5 * np.std(baseline_acc)))
    gyro_threshold = float(np.mean(baseline_gyro) + max(0.4, 2.0 * np.std(baseline_gyro)))

    min_run = max(3, int(0.06 * sample_rate_hz))
    movement_mask = (acc_resultant > acc_threshold) | (gyro_resultant > gyro_threshold)
    movement_start_idx = _first_true_run(movement_mask, min_run)
    if movement_start_idx is None:
        return []

    release_window_start = _clip_index(movement_start_idx + int(0.2 * sample_rate_hz), len(frame))
    z_forward = (acc_forward - np.mean(acc_forward)) / (np.std(acc_forward) + 1e-6)
    z_vertical = (acc_vertical - np.mean(acc_vertical)) / (np.std(acc_vertical) + 1e-6)
    z_gyro = (gyro_turn - np.mean(gyro_turn)) / (np.std(gyro_turn) + 1e-6)
    release_score = np.maximum(z_forward, 0.0) + 0.8 * np.maximum(z_vertical, 0.0) + 0.6 * np.maximum(z_gyro, 0.0)
    release_idx = int(np.argmax(release_score[release_window_start:]) + release_window_start)

    peak_distance = max(2, int(0.12 * sample_rate_hz))
    prominence = max(0.4, float(np.std(acc_vertical[movement_start_idx: release_idx + 1]) * 0.4))
    contact_peaks, _ = find_peaks(
        acc_vertical[movement_start_idx: release_idx + 1],
        distance=peak_distance,
        prominence=prominence,
    )
    contact_peaks = contact_peaks + movement_start_idx

    center_contact_idx = None
    power_position_idx = None
    if len(contact_peaks) >= 1:
        center_contact_idx = int(contact_peaks[0])
    if len(contact_peaks) >= 2:
        power_position_idx = int(contact_peaks[-1])
    elif release_idx > movement_start_idx:
        power_position_idx = int(np.argmax(gyro_turn[movement_start_idx:release_idx]) + movement_start_idx)

    recovery_idx = None
    after_release = np.arange(release_idx + 1, len(frame))
    if len(after_release) > 0:
        calm_threshold = float(np.mean(baseline_acc) + max(0.35, 1.2 * np.std(baseline_acc)))
        calm_mask = acc_resultant[after_release] < calm_threshold
        calm_idx = _first_true_run(calm_mask, max(2, int(0.08 * sample_rate_hz)))
        if calm_idx is not None:
            recovery_idx = int(after_release[calm_idx])

    events = [
        PhaseEvent("Bewegungsbeginn", float(time_values[movement_start_idx]), "#1f77b4"),
    ]
    if center_contact_idx is not None:
        events.append(PhaseEvent("Kreiszentrum", float(time_values[center_contact_idx]), "#2ca02c"))
    if power_position_idx is not None:
        events.append(PhaseEvent("Power Position", float(time_values[power_position_idx]), "#ff7f0e"))
    events.append(PhaseEvent("Release", float(time_values[release_idx]), "#d62728"))
    if recovery_idx is not None:
        events.append(PhaseEvent("Abfangen", float(time_values[recovery_idx]), "#9467bd"))
    return events


def summarize_events(events: list[PhaseEvent]) -> dict[str, float]:
    summary: dict[str, float] = {}
    event_map = {event.label: event.time_s for event in events}
    if "Bewegungsbeginn" in event_map and "Release" in event_map:
        summary["Gesamt bis Release"] = event_map["Release"] - event_map["Bewegungsbeginn"]
    if "Kreiszentrum" in event_map and "Power Position" in event_map:
        summary["Umsetzphase"] = event_map["Power Position"] - event_map["Kreiszentrum"]
    if "Power Position" in event_map and "Release" in event_map:
        summary["Ausstossphase"] = event_map["Release"] - event_map["Power Position"]
    return summary


def build_trajectory(v0_m_s: float, angle_deg: float, release_height_m: float, num_points: int = 150) -> pd.DataFrame:
    v0_m_s = max(0.0, float(v0_m_s))
    angle_rad = radians(float(angle_deg))
    release_height_m = max(0.0, float(release_height_m))
    gravity = 9.81
    vertical_speed = v0_m_s * sin(angle_rad)
    horizontal_speed = max(1e-6, v0_m_s * cos(angle_rad))
    flight_time = (vertical_speed + sqrt(vertical_speed**2 + 2.0 * gravity * release_height_m)) / gravity
    times = np.linspace(0.0, flight_time, num=max(2, num_points))
    x_values = horizontal_speed * times
    z_values = release_height_m + vertical_speed * times - 0.5 * gravity * times**2
    trajectory = pd.DataFrame({"x_m": x_values, "z_m": z_values})
    return trajectory[trajectory["z_m"] >= 0.0].reset_index(drop=True)

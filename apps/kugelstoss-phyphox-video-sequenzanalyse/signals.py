from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any
from urllib.parse import urlparse

import numpy as np
import pandas as pd
import requests
from scipy.signal import butter, filtfilt, find_peaks


LOGICAL_CHANNELS = ("time", "acc_x", "acc_y", "acc_z", "gyro_x", "gyro_y", "gyro_z")
CHANNEL_ALIASES = {
    "time": ("time", "t", "timestamp", "experimenttime", "sampletime", "zeit"),
    "acc_x": ("linaccx", "linearaccelerationx", "accx", "acc_x", "accelerationx", "xwithoutg"),
    "acc_y": ("linaccy", "linearaccelerationy", "accy", "acc_y", "accelerationy", "ywithoutg"),
    "acc_z": ("linaccz", "linearaccelerationz", "accz", "acc_z", "accelerationz", "zwithoutg"),
    "gyro_x": ("gyrox", "gyrx", "omega_x", "omegax", "rotationx"),
    "gyro_y": ("gyroy", "gyry", "omega_y", "omegay", "rotationy"),
    "gyro_z": ("gyroz", "gyrz", "omega_z", "omegaz", "rotationz"),
}


@dataclass(frozen=True, slots=True)
class PhaseEvent:
    label: str
    time_s: float
    color: str


@dataclass(frozen=True, slots=True)
class ProcessingSettings:
    phase_cutoff_hz: float = 7.0
    event_cutoff_hz: float = 16.0
    filter_order: int = 4


def make_demo_frame(duration_s: float = 5.0, sample_rate_hz: float = 120.0) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    time = np.arange(0.0, duration_s, 1.0 / sample_rate_hz)
    pulse = lambda center, width, amp: amp * np.exp(-0.5 * ((time - center) / width) ** 2)
    data = {
        "time": time,
        "acc_x": 0.05 * rng.normal(size=len(time)) + pulse(1.55, 0.12, 0.8) + pulse(2.40, 0.18, 1.4) + pulse(2.95, 0.08, 3.6),
        "acc_y": 0.04 * rng.normal(size=len(time)),
        "acc_z": 0.05 * rng.normal(size=len(time)) + pulse(1.70, 0.10, 0.7) + pulse(2.55, 0.05, 1.1) + pulse(2.98, 0.07, 2.2),
        "gyro_x": 0.02 * rng.normal(size=len(time)),
        "gyro_y": 0.02 * rng.normal(size=len(time)),
        "gyro_z": 0.03 * rng.normal(size=len(time)) + pulse(1.65, 0.15, 1.2) + pulse(2.35, 0.15, 2.1) + pulse(2.85, 0.11, 3.2) - pulse(3.20, 0.12, 1.1),
    }
    return pd.DataFrame(data)


def estimate_sample_rate_hz(time_values: pd.Series) -> float:
    differences = np.diff(time_values.to_numpy(dtype=float))
    differences = differences[differences > 0]
    return float(1.0 / np.median(differences)) if len(differences) else 0.0


def _lowpass(values: np.ndarray, rate: float, cutoff: float, order: int) -> np.ndarray:
    if rate <= 0 or cutoff <= 0:
        return values.copy()
    b, a = butter(order, min(cutoff / (0.5 * rate), 0.99), btype="low")
    if len(values) <= 3 * max(len(a), len(b)):
        return values.copy()
    return filtfilt(b, a, values)


def enrich_signals(frame: pd.DataFrame, settings: ProcessingSettings) -> tuple[pd.DataFrame, float]:
    if frame.empty:
        return frame.copy(), 0.0
    enriched = frame.copy()
    rate = estimate_sample_rate_hz(enriched["time"])
    for column in LOGICAL_CHANNELS[1:]:
        if column not in enriched:
            enriched[column] = 0.0
    enriched["acc_resultant"] = np.sqrt(enriched["acc_x"] ** 2 + enriched["acc_y"] ** 2 + enriched["acc_z"] ** 2)
    enriched["gyro_resultant"] = np.sqrt(enriched["gyro_x"] ** 2 + enriched["gyro_y"] ** 2 + enriched["gyro_z"] ** 2)
    for column in ("acc_x", "acc_z", "acc_resultant", "gyro_z", "gyro_resultant"):
        values = enriched[column].to_numpy(dtype=float)
        enriched[f"{column}_phase"] = _lowpass(values, rate, settings.phase_cutoff_hz, settings.filter_order)
        enriched[f"{column}_event"] = _lowpass(values, rate, settings.event_cutoff_hz, settings.filter_order)
    return enriched, rate


def _first_run(mask: np.ndarray, length: int) -> int | None:
    run = 0
    for index, value in enumerate(mask):
        run = run + 1 if value else 0
        if run >= length:
            return index - length + 1
    return None


def detect_phases(frame: pd.DataFrame, sample_rate_hz: float) -> list[PhaseEvent]:
    if frame.empty or sample_rate_hz <= 0:
        return []
    time = frame["time"].to_numpy(dtype=float)
    acc = frame["acc_resultant_event"].to_numpy(dtype=float)
    acc_x = frame["acc_x_event"].to_numpy(dtype=float)
    acc_z = frame["acc_z_event"].to_numpy(dtype=float)
    gyro = np.abs(frame["gyro_z_event"].to_numpy(dtype=float))
    gyro_all = frame["gyro_resultant_event"].to_numpy(dtype=float)
    baseline = time <= time[0] + min(0.8, max(time[-1] - time[0], 0.8) * 0.2)
    acc_threshold = float(np.mean(acc[baseline]) + max(0.6, 2.5 * np.std(acc[baseline])))
    gyro_threshold = float(np.mean(gyro_all[baseline]) + max(0.4, 2.0 * np.std(gyro_all[baseline])))
    start = _first_run((acc > acc_threshold) | (gyro_all > gyro_threshold), max(3, int(0.06 * sample_rate_hz)))
    if start is None:
        return []
    search_start = min(len(frame) - 1, start + int(0.2 * sample_rate_hz))
    z = lambda values: (values - np.mean(values)) / (np.std(values) + 1e-6)
    score = np.maximum(z(acc_x), 0) + 0.8 * np.maximum(z(acc_z), 0) + 0.6 * np.maximum(z(gyro), 0)
    release = int(np.argmax(score[search_start:]) + search_start)
    peaks, _ = find_peaks(acc_z[start : release + 1], distance=max(2, int(0.12 * sample_rate_hz)), prominence=max(0.4, np.std(acc_z[start : release + 1]) * 0.4))
    peaks = peaks + start
    center = int(peaks[0]) if len(peaks) else min(release, start + int(0.3 * sample_rate_hz))
    power = int(peaks[-1]) if len(peaks) >= 2 else int(np.argmax(gyro[start:release]) + start) if release > start else start
    events = [
        PhaseEvent("Bewegungsbeginn", float(time[start]), "#1f77b4"),
        PhaseEvent("Kreiszentrum", float(time[center]), "#2ca02c"),
        PhaseEvent("Power Position", float(time[power]), "#ff7f0e"),
        PhaseEvent("Release", float(time[release]), "#d62728"),
    ]
    after = np.arange(release + 1, len(frame))
    if len(after):
        calm = acc[after] < float(np.mean(acc[baseline]) + max(0.35, 1.2 * np.std(acc[baseline])))
        calm_index = _first_run(calm, max(2, int(0.08 * sample_rate_hz)))
        if calm_index is not None:
            events.append(PhaseEvent("Abfangen", float(time[int(after[calm_index])]), "#9467bd"))
    return sorted(events, key=lambda event: event.time_s)


def normalize_base_url(url: str) -> str:
    raw = url.strip()
    if "://" not in raw:
        raw = f"http://{raw}"
    parsed = urlparse(raw)
    if not parsed.hostname:
        return ""
    return f"{parsed.scheme or 'http'}://{parsed.hostname}:{parsed.port or 8080}"


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def extract_buffer_names(config: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for item in config.get("buffers", []):
        name = item.get("name")
        if isinstance(name, str) and name not in names:
            names.append(name)
    for export in config.get("export", []):
        for item in export.get("data", []):
            name = item.get("buffer")
            if isinstance(name, str) and name not in names:
                names.append(name)
    return names


def guess_live_mapping(config: dict[str, Any]) -> dict[str, str | None]:
    names = extract_buffer_names(config)
    mapping: dict[str, str | None] = {}
    used: set[str] = set()
    for logical in LOGICAL_CHANNELS:
        candidates = []
        for name in names:
            token = _normalize(name)
            score = max((1000 - i if token == _normalize(alias) else 100 - i if _normalize(alias) in token else -1) for i, alias in enumerate(CHANNEL_ALIASES[logical]))
            candidates.append((score, name))
        choice = next((name for score, name in sorted(candidates, reverse=True) if score >= 0 and name not in used), None)
        mapping[logical] = choice
        if choice:
            used.add(choice)
    return mapping


class PhyphoxClient:
    def __init__(self, url: str, timeout_s: float = 2.0) -> None:
        self.base_url = normalize_base_url(url)
        if not self.base_url:
            raise ValueError("Keine gültige Phyphox-URL angegeben.")
        self.timeout_s = timeout_s

    def _get(self, path: str, params=None):
        response = requests.get(f"{self.base_url}{path}", params=params, timeout=self.timeout_s)
        response.raise_for_status()
        return response.json()

    def config(self):
        return self._get("/config")

    def control(self, command: str) -> bool:
        return bool(self._get("/control", {"cmd": command}).get("result"))

    def poll(self, mapping: dict[str, str | None], last_time: float | None) -> tuple[pd.DataFrame, dict[str, Any]]:
        time_buffer = mapping.get("time")
        if not time_buffer:
            raise ValueError("Kein Zeitbuffer ausgewählt.")
        selector = "full" if last_time is None else f"{last_time:.12f}"
        params = {time_buffer: selector}
        for logical, buffer_name in mapping.items():
            if logical != "time" and buffer_name:
                params[buffer_name] = "full" if last_time is None else f"{last_time:.12f}|{time_buffer}"
        payload = self._get("/get", params)
        buffers = payload.get("buffer", {})
        times = buffers.get(time_buffer, {}).get("buffer", [])
        if not times:
            return pd.DataFrame(columns=LOGICAL_CHANNELS), payload.get("status", {})
        count = len(times)
        data = {"time": [float(value) for value in times]}
        for logical in LOGICAL_CHANNELS[1:]:
            name = mapping.get(logical)
            values = buffers.get(name, {}).get("buffer", []) if name else []
            numeric = [float(value) for value in values[:count]]
            numeric.extend([numeric[-1] if numeric else 0.0] * (count - len(numeric)))
            data[logical] = numeric
        return pd.DataFrame(data), payload.get("status", {})

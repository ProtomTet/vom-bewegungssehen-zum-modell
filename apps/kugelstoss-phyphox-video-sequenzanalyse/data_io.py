from __future__ import annotations

from io import StringIO
import re

import pandas as pd

from signals import CHANNEL_ALIASES, LOGICAL_CHANNELS


def _token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def read_sensor_csv(file_bytes: bytes) -> pd.DataFrame:
    text = None
    for encoding in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            text = file_bytes.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise ValueError("Die CSV-Datei konnte nicht dekodiert werden.")

    attempts = [
        {"sep": None, "engine": "python"},
        {"sep": ";", "engine": "python", "decimal": ","},
        {"sep": ",", "engine": "python"},
        {"sep": "\t", "engine": "python"},
    ]
    best: pd.DataFrame | None = None
    for options in attempts:
        try:
            candidate = pd.read_csv(StringIO(text), comment="#", **options)
        except Exception:
            continue
        if best is None or len(candidate.columns) > len(best.columns):
            best = candidate
    if best is None or best.empty:
        raise ValueError("In der CSV-Datei wurden keine Daten gefunden.")
    best.columns = [str(column).strip() for column in best.columns]
    return best


def guess_csv_mapping(columns) -> dict[str, str | None]:
    names = [str(column) for column in columns]
    mapping: dict[str, str | None] = {channel: None for channel in LOGICAL_CHANNELS}
    claimed: set[str] = set()
    for logical in LOGICAL_CHANNELS:
        aliases = [_token(alias) for alias in CHANNEL_ALIASES[logical]]
        scored: list[tuple[int, str]] = []
        for name in names:
            token = _token(name)
            score = -1
            for index, alias in enumerate(aliases):
                if token == alias:
                    score = max(score, 1000 - index)
                elif alias in token:
                    score = max(score, 100 - index)
            scored.append((score, name))
        for score, name in sorted(scored, reverse=True):
            if score >= 0 and name not in claimed:
                mapping[logical] = name
                claimed.add(name)
                break
    return mapping


def standardize_sensor_frame(raw: pd.DataFrame, mapping: dict[str, str | None]) -> pd.DataFrame:
    time_column = mapping.get("time")
    if not time_column or time_column not in raw.columns:
        raise ValueError("Bitte eine gültige Zeitspalte auswählen.")
    result = pd.DataFrame()
    for logical in LOGICAL_CHANNELS:
        source = mapping.get(logical)
        if source and source in raw.columns:
            values = raw[source].astype(str).str.replace(",", ".", regex=False)
            result[logical] = pd.to_numeric(values, errors="coerce")
        elif logical != "time":
            result[logical] = 0.0
    result = result.dropna(subset=["time"]).sort_values("time")
    result = result.drop_duplicates(subset="time", keep="last").reset_index(drop=True)
    for column in LOGICAL_CHANNELS:
        if column not in result:
            result[column] = 0.0
        result[column] = result[column].interpolate(limit_direction="both").fillna(0.0)
    return result[list(LOGICAL_CHANNELS)]

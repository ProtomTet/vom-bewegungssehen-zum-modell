from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any
from urllib.parse import urlparse

import pandas as pd
import requests


LOGICAL_CHANNELS = (
    "time",
    "acc_x",
    "acc_y",
    "acc_z",
    "gyro_x",
    "gyro_y",
    "gyro_z",
)


CHANNEL_ALIASES: dict[str, tuple[str, ...]] = {
    "time": (
        "time",
        "t",
        "timestamp",
        "experimenttime",
        "sampletime",
    ),
    "acc_x": (
        "linaccx",
        "linaccelerationx",
        "linearaccelerationx",
        "accx",
        "acc_x",
        "accelerationx",
        "xwithoutg",
        "xnog",
    ),
    "acc_y": (
        "linaccy",
        "linaccelerationy",
        "linearaccelerationy",
        "accy",
        "acc_y",
        "accelerationy",
        "ywithoutg",
        "ynog",
    ),
    "acc_z": (
        "linaccz",
        "linaccelerationz",
        "linearaccelerationz",
        "accz",
        "acc_z",
        "accelerationz",
        "zwithoutg",
        "znog",
    ),
    "gyro_x": (
        "gyrox",
        "gyrx",
        "omega_x",
        "omegax",
        "rotationx",
    ),
    "gyro_y": (
        "gyroy",
        "gyry",
        "omega_y",
        "omegay",
        "rotationy",
    ),
    "gyro_z": (
        "gyroz",
        "gyrz",
        "omega_z",
        "omegaz",
        "rotationz",
    ),
}


@dataclass(slots=True)
class PollResult:
    frame: pd.DataFrame
    status: dict[str, Any]
    session_id: str | None


def normalize_base_url(url: str) -> str:
    raw = url.strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = f"http://{raw}"
    parsed = urlparse(raw)
    scheme = parsed.scheme or "http"

    hostname = parsed.hostname
    if not hostname:
        fallback = (parsed.netloc or parsed.path).strip().strip("/")
        if fallback:
            return f"{scheme}://{fallback}"
        return ""

    port = parsed.port or 8080
    return f"{scheme}://{hostname}:{port}"


def _normalize_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _iter_named_buffers(config: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for item in config.get("buffers", []):
        name = item.get("name")
        if isinstance(name, str) and name not in names:
            names.append(name)

    for export_set in config.get("export", []):
        for data_set in export_set.get("data", []):
            buffer_name = data_set.get("buffer")
            if isinstance(buffer_name, str) and buffer_name not in names:
                names.append(buffer_name)
    return names


def _score_candidate(name: str, logical_channel: str) -> int:
    token = _normalize_token(name)
    best = -1
    for idx, alias in enumerate(CHANNEL_ALIASES[logical_channel]):
        alias_token = _normalize_token(alias)
        if token == alias_token:
            return 1000 - idx
        if alias_token in token:
            best = max(best, 100 - idx)
    return best


def guess_channel_mapping(config: dict[str, Any]) -> dict[str, str | None]:
    names = _iter_named_buffers(config)
    mapping: dict[str, str | None] = {channel: None for channel in LOGICAL_CHANNELS}
    claimed: set[str] = set()

    for logical_channel in LOGICAL_CHANNELS:
        scored = sorted(
            ((name, _score_candidate(name, logical_channel)) for name in names),
            key=lambda item: item[1],
            reverse=True,
        )
        for name, score in scored:
            if score < 0 or name in claimed:
                continue
            mapping[logical_channel] = name
            claimed.add(name)
            break

    return mapping


class PhyphoxClient:
    def __init__(self, base_url: str, timeout_s: float = 2.0) -> None:
        normalized = normalize_base_url(base_url)
        if not normalized:
            raise ValueError("Keine gueltige Phyphox-URL angegeben.")
        self.base_url = normalized
        self.timeout_s = timeout_s

    def _request_json(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        response = requests.get(
            f"{self.base_url}{path}",
            params=params,
            timeout=self.timeout_s,
        )
        response.raise_for_status()
        return response.json()

    def config(self) -> dict[str, Any]:
        return self._request_json("/config")

    def control(self, command: str) -> bool:
        result = self._request_json("/control", {"cmd": command})
        return bool(result.get("result"))

    def poll(
        self,
        mapping: dict[str, str | None],
        last_time: float | None,
    ) -> PollResult:
        time_buffer = mapping.get("time")
        if not time_buffer:
            raise ValueError("Kein Zeitbuffer ausgewaehlt.")

        params: dict[str, str] = {}
        if last_time is None:
            params[time_buffer] = "full"
        else:
            params[time_buffer] = f"{last_time:.12f}"

        for logical_channel, buffer_name in mapping.items():
            if logical_channel == "time" or not buffer_name:
                continue
            if last_time is None:
                params[buffer_name] = "full"
            else:
                params[buffer_name] = f"{last_time:.12f}|{time_buffer}"

        payload = self._request_json("/get", params)
        status = payload.get("status", {})
        session_id = status.get("session")
        buffers = payload.get("buffer", {})
        time_values = buffers.get(time_buffer, {}).get("buffer", [])
        if not time_values:
            return PollResult(frame=pd.DataFrame(columns=LOGICAL_CHANNELS), status=status, session_id=session_id)

        frame_dict: dict[str, list[float]] = {"time": [float(value) for value in time_values]}
        row_count = len(frame_dict["time"])
        for logical_channel, buffer_name in mapping.items():
            if logical_channel == "time":
                continue
            if not buffer_name:
                frame_dict[logical_channel] = [0.0] * row_count
                continue

            values = buffers.get(buffer_name, {}).get("buffer", [])
            numeric = [float(value) for value in values[:row_count]]
            if len(numeric) < row_count:
                numeric.extend([numeric[-1] if numeric else 0.0] * (row_count - len(numeric)))
            frame_dict[logical_channel] = numeric

        frame = pd.DataFrame(frame_dict)
        frame = frame.drop_duplicates(subset="time", keep="last").sort_values("time").reset_index(drop=True)
        return PollResult(frame=frame, status=status, session_id=session_id)

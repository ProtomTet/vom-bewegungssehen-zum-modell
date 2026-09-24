from __future__ import annotations

from dataclasses import dataclass, replace
from math import cos, radians, sin, sqrt

import numpy as np
import pandas as pd


@dataclass(frozen=True, slots=True)
class TrajectoryParameters:
    label: str
    v0_m_s: float
    angle_deg: float
    release_height_m: float
    release_x_m: float = 0.0
    gravity_m_s2: float = 9.81


@dataclass(frozen=True, slots=True)
class TrajectoryResult:
    parameters: TrajectoryParameters
    data: pd.DataFrame
    vx_m_s: float
    vz_m_s: float
    flight_time_s: float
    landing_x_m: float
    flight_distance_m: float
    peak_height_m: float


def simulate(parameters: TrajectoryParameters, points: int = 240) -> TrajectoryResult:
    v0 = max(0.0, float(parameters.v0_m_s))
    gravity = max(0.01, float(parameters.gravity_m_s2))
    height = max(0.0, float(parameters.release_height_m))
    angle = radians(float(parameters.angle_deg))
    vx = v0 * cos(angle)
    vz = v0 * sin(angle)
    discriminant = max(0.0, vz**2 + 2.0 * gravity * height)
    flight_time = (vz + sqrt(discriminant)) / gravity
    times = np.linspace(0.0, flight_time, max(20, int(points)))
    x = float(parameters.release_x_m) + vx * times
    z = height + vz * times - 0.5 * gravity * times**2
    z = np.maximum(0.0, z)
    peak_time = min(flight_time, max(0.0, vz / gravity))
    peak_height = height + vz * peak_time - 0.5 * gravity * peak_time**2
    landing_x = float(x[-1])
    return TrajectoryResult(
        parameters=parameters,
        data=pd.DataFrame({"t_s": times, "x_m": x, "z_m": z}),
        vx_m_s=float(vx),
        vz_m_s=float(vz),
        flight_time_s=float(flight_time),
        landing_x_m=landing_x,
        flight_distance_m=landing_x - float(parameters.release_x_m),
        peak_height_m=float(peak_height),
    )


def sweep(
    base: TrajectoryParameters,
    parameter_name: str,
    start: float,
    stop: float,
    count: int,
) -> list[TrajectoryResult]:
    allowed = {"v0_m_s", "angle_deg", "release_height_m"}
    if parameter_name not in allowed:
        raise ValueError(f"Unbekannter Variationsparameter: {parameter_name}")
    results: list[TrajectoryResult] = []
    for value in np.linspace(float(start), float(stop), max(2, int(count))):
        changed = replace(base, label=f"{parameter_name}={value:.2f}", **{parameter_name: float(value)})
        results.append(simulate(changed))
    return results

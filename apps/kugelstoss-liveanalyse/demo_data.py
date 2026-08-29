from __future__ import annotations

import numpy as np
import pandas as pd


def make_demo_frame(duration_s: float = 5.0, sample_rate_hz: float = 120.0) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    times = np.arange(0.0, duration_s, 1.0 / sample_rate_hz)

    acc_x = 0.05 * rng.normal(size=len(times))
    acc_y = 0.04 * rng.normal(size=len(times))
    acc_z = 0.05 * rng.normal(size=len(times))
    gyro_x = 0.02 * rng.normal(size=len(times))
    gyro_y = 0.02 * rng.normal(size=len(times))
    gyro_z = 0.03 * rng.normal(size=len(times))

    def pulse(center: float, width: float, amplitude: float) -> np.ndarray:
        return amplitude * np.exp(-0.5 * ((times - center) / width) ** 2)

    acc_x += pulse(1.55, 0.12, 0.8)
    acc_x += pulse(2.40, 0.18, 1.4)
    acc_x += pulse(2.95, 0.08, 3.6)

    acc_z += pulse(1.70, 0.10, 0.7)
    acc_z += pulse(2.10, 0.05, 1.0)
    acc_z += pulse(2.55, 0.05, 1.1)
    acc_z += pulse(2.98, 0.07, 2.2)

    gyro_z += pulse(1.65, 0.15, 1.2)
    gyro_z += pulse(2.35, 0.15, 2.1)
    gyro_z += pulse(2.85, 0.11, 3.2)
    gyro_z -= pulse(3.20, 0.12, 1.1)

    return pd.DataFrame(
        {
            "time": times,
            "acc_x": acc_x,
            "acc_y": acc_y,
            "acc_z": acc_z,
            "gyro_x": gyro_x,
            "gyro_y": gyro_y,
            "gyro_z": gyro_z,
        }
    )

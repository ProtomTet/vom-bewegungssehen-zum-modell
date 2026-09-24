from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from math import atan2, degrees, hypot
from pathlib import Path
import subprocess
import tempfile

import cv2
import numpy as np
import pandas as pd
from PIL import Image


@dataclass(frozen=True, slots=True)
class VideoInfo:
    path: str
    fps: float
    frame_count: int
    width: int
    height: int
    duration_s: float


@dataclass(frozen=True, slots=True)
class Calibration:
    origin_px: tuple[float, float]
    x_reference_px: tuple[float, float]
    x_distance_m: float
    z_reference_px: tuple[float, float] | None = None
    z_distance_m: float | None = None
    z_reference_x_m: float = 0.0


@dataclass(frozen=True, slots=True)
class ReleaseFit:
    vx_m_s: float
    vz_m_s: float
    v0_m_s: float
    angle_deg: float
    release_x_m: float
    release_height_m: float
    rmse_m: float
    point_count: int
    slow_factor: float
    release_frame: int

    def to_dict(self) -> dict[str, float | int]:
        return asdict(self)


def read_video_info(path: str | Path) -> VideoInfo:
    resolved = str(Path(path).resolve())
    capture = cv2.VideoCapture(resolved)
    if not capture.isOpened():
        raise ValueError(f"Video kann nicht geoeffnet werden: {resolved}")
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    capture.release()
    if fps <= 0 or frame_count <= 0 or width <= 0 or height <= 0:
        raise ValueError("Videometadaten sind unvollstaendig.")
    return VideoInfo(
        path=resolved,
        fps=fps,
        frame_count=frame_count,
        width=width,
        height=height,
        duration_s=frame_count / fps,
    )


def save_uploaded_video(file_bytes: bytes, original_name: str) -> Path:
    suffix = Path(original_name).suffix.lower() or ".mp4"
    digest = sha256(file_bytes).hexdigest()[:16]
    destination = Path(tempfile.gettempdir()) / f"kugelstoss_upload_{digest}{suffix}"
    if not destination.exists() or destination.stat().st_size != len(file_bytes):
        destination.write_bytes(file_bytes)
    return destination


def build_analysis_proxy(path: str | Path, max_width: int = 1100) -> Path:
    """Creates a seek-friendly H.264 proxy while preserving frame rate/count."""
    source = Path(path).resolve()
    signature = sha256(f"{source}:{source.stat().st_size}:{source.stat().st_mtime_ns}".encode()).hexdigest()[:16]
    destination = Path(tempfile.gettempdir()) / f"kugelstoss_proxy_{signature}.mp4"
    if destination.exists() and destination.stat().st_size > 10_000:
        return destination

    try:
        import imageio_ffmpeg

        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        scale = f"scale='min({int(max_width)},iw)':-2"
        command = [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-map",
            "0:v:0",
            "-vf",
            scale,
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-crf",
            "23",
            "-g",
            "12",
            "-keyint_min",
            "12",
            "-pix_fmt",
            "yuv420p",
            str(destination),
        ]
        subprocess.run(command, check=True, capture_output=True, timeout=300)
    except Exception:
        if destination.exists():
            destination.unlink(missing_ok=True)
        return source
    return destination


def read_frame(path: str | Path, frame_index: int, max_width: int = 1100) -> Image.Image:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise ValueError("Video kann nicht geoeffnet werden.")
    frame_index = max(0, int(frame_index))
    capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
    ok, frame_bgr = capture.read()
    capture.release()
    if not ok or frame_bgr is None:
        raise ValueError(f"Bild {frame_index} konnte nicht gelesen werden.")
    frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    image = Image.fromarray(frame_rgb)
    if image.width > max_width:
        height = round(image.height * max_width / image.width)
        image = image.resize((max_width, height), Image.Resampling.LANCZOS)
    return image


def estimate_slow_factor(
    original_start_frame: int,
    original_end_frame: int,
    slow_start_frame: int,
    slow_end_frame: int,
) -> float:
    original_frames = int(original_end_frame) - int(original_start_frame)
    slow_frames = int(slow_end_frame) - int(slow_start_frame)
    if original_frames <= 0 or slow_frames <= 0:
        raise ValueError("Start- und Endbilder muessen chronologisch geordnet sein.")
    return slow_frames / original_frames


def _calibration_basis(calibration: Calibration) -> np.ndarray:
    origin = np.asarray(calibration.origin_px, dtype=float)
    x_reference = np.asarray(calibration.x_reference_px, dtype=float)
    x_distance = float(calibration.x_distance_m)
    if abs(x_distance) < 1e-9:
        raise ValueError("Die X-Koordinate der Referenz darf nicht null sein.")
    x_basis = (x_reference - origin) / x_distance
    if np.linalg.norm(x_basis) < 1e-9:
        raise ValueError("Ursprung und X-Referenzpunkt duerfen nicht identisch sein.")

    if calibration.z_reference_px is not None and calibration.z_distance_m is not None:
        z_distance = float(calibration.z_distance_m)
        if z_distance <= 0:
            raise ValueError("Die vertikale Referenzstrecke muss groesser als null sein.")
        z_reference = np.asarray(calibration.z_reference_px, dtype=float)
        z_reference_x = float(calibration.z_reference_x_m)
        # The visible height reference can stand above O or above the X reference.
        # Remove its horizontal component before deriving the vertical pixel basis.
        z_basis = (z_reference - origin - x_basis * z_reference_x) / z_distance
    else:
        # Pixel y grows downwards. Rotate the x basis clockwise so positive z points up
        # when the x direction runs from left to right.
        z_basis = np.asarray([x_basis[1], -x_basis[0]], dtype=float)

    basis = np.column_stack([x_basis, z_basis])
    if abs(np.linalg.det(basis)) < 1e-9:
        raise ValueError("Die Kalibrierachsen sind nahezu parallel.")
    return basis


def pixel_to_world(point_px: tuple[float, float], calibration: Calibration) -> tuple[float, float]:
    basis = _calibration_basis(calibration)
    displacement = np.asarray(point_px, dtype=float) - np.asarray(calibration.origin_px, dtype=float)
    x_m, z_m = np.linalg.solve(basis, displacement)
    return float(x_m), float(z_m)


def world_to_pixel(point_world: tuple[float, float], calibration: Calibration) -> tuple[float, float]:
    """Project a calibrated world coordinate back into the analysed video image."""
    basis = _calibration_basis(calibration)
    point = np.asarray(point_world, dtype=float)
    pixel = np.asarray(calibration.origin_px, dtype=float) + basis @ point
    return float(pixel[0]), float(pixel[1])


def points_to_dataframe(
    points_by_frame: dict[int, tuple[float, float]],
    calibration: Calibration,
    fps: float,
    slow_factor: float,
    release_frame: int,
) -> pd.DataFrame:
    if fps <= 0 or slow_factor <= 0:
        raise ValueError("Bildrate und Zeitfaktor muessen groesser als null sein.")
    rows: list[dict[str, float | int]] = []
    for frame_index, point_px in sorted(points_by_frame.items()):
        x_m, z_m = pixel_to_world(point_px, calibration)
        rows.append(
            {
                "frame": int(frame_index),
                "video_time_s": int(frame_index) / float(fps),
                "real_time_from_release_s": (int(frame_index) - int(release_frame))
                / (float(fps) * float(slow_factor)),
                "x_px": float(point_px[0]),
                "y_px": float(point_px[1]),
                "x_m": x_m,
                "z_m": z_m,
            }
        )
    return pd.DataFrame(rows)


def fit_release_parameters(
    points_by_frame: dict[int, tuple[float, float]],
    calibration: Calibration,
    fps: float,
    slow_factor: float,
    release_frame: int,
    gravity_m_s2: float = 9.81,
) -> tuple[ReleaseFit, pd.DataFrame]:
    frame = points_to_dataframe(
        points_by_frame=points_by_frame,
        calibration=calibration,
        fps=fps,
        slow_factor=slow_factor,
        release_frame=release_frame,
    )
    frame = frame.loc[frame["frame"] >= int(release_frame)].copy()
    if len(frame) < 3:
        raise ValueError("Mindestens drei Kugelpunkte ab dem Release werden benoetigt.")

    t = frame["real_time_from_release_s"].to_numpy(dtype=float)
    x = frame["x_m"].to_numpy(dtype=float)
    z = frame["z_m"].to_numpy(dtype=float)
    corrected_z = z + 0.5 * float(gravity_m_s2) * t**2
    release_rows = np.isclose(t, 0.0, atol=1e-12)
    if np.any(release_rows):
        # Anchor the fitted trajectory exactly at the clicked release marker.
        # Only the two velocity components are fitted to the later points.
        release_x = float(np.mean(x[release_rows]))
        release_height = float(np.mean(z[release_rows]))
        time_square_sum = float(np.dot(t, t))
        if time_square_sum <= 1e-15:
            raise ValueError("Mindestens ein Kugelpunkt nach dem Release wird benoetigt.")
        vx = float(np.dot(t, x - release_x) / time_square_sum)
        vz = float(np.dot(t, corrected_z - release_height) / time_square_sum)
    else:
        design = np.column_stack([np.ones_like(t), t])
        release_x, vx = np.linalg.lstsq(design, x, rcond=None)[0]
        release_height, vz = np.linalg.lstsq(design, corrected_z, rcond=None)[0]

    x_fit = release_x + vx * t
    z_fit = release_height + vz * t - 0.5 * float(gravity_m_s2) * t**2
    residuals = np.concatenate([x - x_fit, z - z_fit])
    rmse = float(np.sqrt(np.mean(residuals**2)))
    v0 = hypot(float(vx), float(vz))
    angle = degrees(atan2(float(vz), float(vx))) if v0 else 0.0

    frame.loc[:, "x_fit_m"] = x_fit
    frame.loc[:, "z_fit_m"] = z_fit
    frame.loc[:, "residual_m"] = np.hypot(x - x_fit, z - z_fit)
    fit = ReleaseFit(
        vx_m_s=float(vx),
        vz_m_s=float(vz),
        v0_m_s=float(v0),
        angle_deg=float(angle),
        release_x_m=float(release_x),
        release_height_m=float(release_height),
        rmse_m=rmse,
        point_count=len(frame),
        slow_factor=float(slow_factor),
        release_frame=int(release_frame),
    )
    return fit, frame

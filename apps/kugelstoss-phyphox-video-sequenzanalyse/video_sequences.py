from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import subprocess
import tempfile


PHASE_LABELS = (
    "Bewegungsbeginn",
    "Kreiszentrum",
    "Power Position",
    "Release",
    "Abfangen",
)

PHASE_COLORS = {
    "Bewegungsbeginn": "#1f77b4",
    "Kreiszentrum": "#2ca02c",
    "Power Position": "#ff7f0e",
    "Release": "#d62728",
    "Abfangen": "#9467bd",
}


def ordered_event_frames(event_frames: dict[str, int]) -> list[tuple[str, int]]:
    return sorted(
        ((label, int(event_frames[label])) for label in PHASE_LABELS if label in event_frames),
        key=lambda item: item[1],
    )


def phase_bounds(event_frames: dict[str, int], label: str, last_frame: int) -> tuple[int, int]:
    ordered = ordered_event_frames(event_frames)
    labels = [item[0] for item in ordered]
    if label not in labels:
        raise ValueError(f"Für '{label}' wurde noch kein Videobild festgelegt.")
    index = labels.index(label)
    start = ordered[index][1]
    end = ordered[index + 1][1] if index + 1 < len(ordered) else min(int(last_frame), start + 90)
    if end <= start:
        end = min(int(last_frame), start + 1)
    return start, end


def build_phase_clip(video_path: str | Path, start_frame: int, end_frame: int, fps: float) -> Path:
    source = Path(video_path).resolve()
    if fps <= 0 or end_frame <= start_frame:
        raise ValueError("Ungültige Grenzen für die Videosequenz.")
    signature = sha256(
        f"{source}:{source.stat().st_size}:{source.stat().st_mtime_ns}:{start_frame}:{end_frame}:{fps}".encode()
    ).hexdigest()[:20]
    destination = Path(tempfile.gettempdir()) / f"kugelstoss_phase_{signature}.mp4"
    if destination.exists() and destination.stat().st_size > 5_000:
        return destination

    import imageio_ffmpeg

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    start_s = max(0.0, float(start_frame) / float(fps))
    duration_s = max(1.0 / float(fps), (float(end_frame) - float(start_frame)) / float(fps))
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        f"{start_s:.9f}",
        "-i",
        str(source),
        "-t",
        f"{duration_s:.9f}",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(destination),
    ]
    subprocess.run(command, check=True, capture_output=True, timeout=180)
    return destination


def synchronization_from_anchors(
    video_frame_a: int,
    sensor_time_a_s: float,
    video_frame_b: int,
    sensor_time_b_s: float,
) -> tuple[float, float]:
    frame_delta = float(video_frame_b) - float(video_frame_a)
    if abs(frame_delta) < 1e-12:
        raise ValueError("Die beiden Video-Anker müssen verschieden sein.")
    slope_s_per_frame = (float(sensor_time_b_s) - float(sensor_time_a_s)) / frame_delta
    if slope_s_per_frame <= 0:
        raise ValueError("Die Anker müssen in Video und Sensordaten dieselbe zeitliche Reihenfolge haben.")
    offset_s = float(sensor_time_a_s) - slope_s_per_frame * float(video_frame_a)
    return slope_s_per_frame, offset_s


def video_frame_to_sensor_time(frame_index: int, slope_s_per_frame: float, offset_s: float) -> float:
    return float(frame_index) * float(slope_s_per_frame) + float(offset_s)

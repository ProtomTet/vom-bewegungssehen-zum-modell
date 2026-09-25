from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import subprocess
import tempfile

import cv2
from PIL import Image


@dataclass(frozen=True, slots=True)
class VideoInfo:
    path: str
    fps: float
    frame_count: int
    width: int
    height: int
    duration_s: float


def read_video_info(path: str | Path) -> VideoInfo:
    resolved = str(Path(path).resolve())
    capture = cv2.VideoCapture(resolved)
    if not capture.isOpened():
        raise ValueError("Video kann nicht geöffnet werden.")
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    capture.release()
    if fps <= 0 or count <= 0:
        raise ValueError("Ungültige Videometadaten.")
    return VideoInfo(resolved, fps, count, width, height, count / fps)


def save_uploaded_video(file_bytes: bytes, original_name: str) -> Path:
    suffix = Path(original_name).suffix.lower() or ".mp4"
    digest = sha256(file_bytes).hexdigest()[:16]
    destination = Path(tempfile.gettempdir()) / f"kugelstoss_sequence_upload_{digest}{suffix}"
    if not destination.exists() or destination.stat().st_size != len(file_bytes):
        destination.write_bytes(file_bytes)
    return destination


def build_proxy(path: str | Path, max_width: int = 1100) -> Path:
    source = Path(path).resolve()
    digest = sha256(f"{source}:{source.stat().st_size}:{source.stat().st_mtime_ns}".encode()).hexdigest()[:16]
    destination = Path(tempfile.gettempdir()) / f"kugelstoss_sequence_proxy_{digest}.mp4"
    if destination.exists() and destination.stat().st_size > 10_000:
        return destination
    import imageio_ffmpeg

    command = [
        imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(source), "-map", "0:v:0", "-vf", f"scale='min({int(max_width)},iw)':-2",
        "-an", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
        "-g", "12", "-keyint_min", "12", "-pix_fmt", "yuv420p", str(destination),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, timeout=300)
    except Exception:
        destination.unlink(missing_ok=True)
        return source
    return destination


def read_frame(path: str | Path, frame_index: int, max_width: int = 1100) -> Image.Image:
    capture = cv2.VideoCapture(str(path))
    capture.set(cv2.CAP_PROP_POS_FRAMES, max(0, int(frame_index)))
    ok, frame = capture.read()
    capture.release()
    if not ok:
        raise ValueError(f"Bild {frame_index} konnte nicht gelesen werden.")
    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    image = Image.fromarray(frame)
    if image.width > max_width:
        image = image.resize((max_width, round(image.height * max_width / image.width)), Image.Resampling.LANCZOS)
    return image

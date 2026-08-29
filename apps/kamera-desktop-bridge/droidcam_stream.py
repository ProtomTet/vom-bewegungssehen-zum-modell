from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import time
from urllib import error, request

import cv2
import numpy as np
from PySide6 import QtCore


DEFAULT_IP = "192.168.178.182"
DEFAULT_PORT = 4747
DEFAULT_RESOLUTIONS = [
    ("Original", ""),
    ("640 x 480", "640x480"),
    ("1280 x 720", "1280x720"),
    ("1920 x 1080", "1920x1080"),
]


class DroidCamStreamError(RuntimeError):
    pass


@dataclass(slots=True)
class StreamConfig:
    ip: str
    port: int
    resolution: str = ""
    force_connection: bool = True


def build_base_url(ip: str, port: int) -> str:
    return f"http://{ip}:{port}"


def build_preview_url(ip: str, port: int) -> str:
    return build_base_url(ip, port) + "/"


def build_stream_url(config: StreamConfig) -> str:
    base = build_base_url(config.ip, config.port) + "/video"
    if config.resolution and config.force_connection:
        return f"{base}/force/{config.resolution}"
    if config.resolution:
        return f"{base}/{config.resolution}"
    if config.force_connection:
        return f"{base}/force"
    return base


class MjpegStreamThread(QtCore.QThread):
    frame_ready = QtCore.Signal(object, float, int)
    stream_started = QtCore.Signal(str)
    status = QtCore.Signal(str)
    error = QtCore.Signal(str)

    def __init__(self, config: StreamConfig) -> None:
        super().__init__()
        self.config = config
        self._running = True
        self._response: object | None = None

    def stop(self) -> None:
        self._running = False
        response = self._response
        if response is not None:
            try:
                response.close()
            except Exception:
                pass

    def run(self) -> None:
        stream_url = build_stream_url(self.config)
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Cache-Control": "no-cache",
        }
        req = request.Request(stream_url, headers=headers)
        frame_count = 0
        fps_values: deque[float] = deque(maxlen=20)
        last_frame_time: float | None = None
        buffer = b""

        try:
            self.status.emit(f"Verbinde mit {stream_url} ...")
            self._response = request.urlopen(req, timeout=10)
            self.stream_started.emit(stream_url)

            while self._running:
                chunk = self._response.read(4096)
                if not chunk:
                    raise DroidCamStreamError("DroidCam hat keine weiteren Bilddaten geliefert.")

                buffer += chunk

                while True:
                    start = buffer.find(b"\xff\xd8")
                    end = buffer.find(b"\xff\xd9", start + 2)
                    if start == -1 or end == -1:
                        if len(buffer) > 2_000_000:
                            buffer = buffer[-200_000:]
                        break

                    jpg_bytes = buffer[start : end + 2]
                    buffer = buffer[end + 2 :]

                    image_array = np.frombuffer(jpg_bytes, dtype=np.uint8)
                    frame = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
                    if frame is None:
                        continue

                    now = time.monotonic()
                    if last_frame_time is not None:
                        delta = now - last_frame_time
                        if delta > 0:
                            fps_values.append(1.0 / delta)
                    last_frame_time = now
                    fps = sum(fps_values) / len(fps_values) if fps_values else 0.0

                    frame_count += 1
                    self.frame_ready.emit(frame, fps, frame_count)
        except error.URLError as exc:
            self.error.emit(f"DroidCam-Stream nicht erreichbar: {exc.reason}")
        except TimeoutError:
            self.error.emit("Zeitueberschreitung beim Verbinden mit dem DroidCam-Stream.")
        except DroidCamStreamError as exc:
            self.error.emit(str(exc))
        except Exception as exc:
            self.error.emit(f"Unerwarteter Fehler im DroidCam-Stream: {exc}")
        finally:
            response = self._response
            self._response = None
            if response is not None:
                try:
                    response.close()
                except Exception:
                    pass

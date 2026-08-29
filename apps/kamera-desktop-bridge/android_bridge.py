from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import shutil
import subprocess
import time


OPEN_CAMERA_PACKAGE = "net.sourceforge.opencamera"
VIDEO_EXTENSIONS = ("mp4", "mkv", "webm", "3gp")


class AndroidBridgeError(RuntimeError):
    pass


@dataclass(slots=True)
class DeviceInfo:
    serial: str
    state: str
    model: str = ""
    transport_id: str = ""
    raw_line: str = ""


@dataclass(slots=True)
class VideoFile:
    remote_path: str
    modified_ts: int | None
    size_bytes: int | None

    @property
    def name(self) -> str:
        return Path(self.remote_path).name


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    unique: list[Path] = []
    for path in paths:
        key = str(path).lower()
        if key not in seen and path.exists():
            unique.append(path)
            seen.add(key)
    return unique


def detect_scrcpy_candidates() -> list[Path]:
    candidates: list[Path] = []

    which_path = shutil.which("scrcpy")
    if which_path:
        candidates.append(Path(which_path))

    home = Path.home()
    direct_candidates = [
        Path("C:/Program Files/scrcpy/scrcpy.exe"),
        Path("C:/tools/scrcpy/scrcpy.exe"),
        home / "Downloads" / "scrcpy.exe",
        home / "Downloads" / "scrcpy-win64" / "scrcpy.exe",
        home / "Downloads" / "scrcpy-win64-v3.1" / "scrcpy.exe",
    ]
    candidates.extend(direct_candidates)

    downloads_dir = home / "Downloads"
    if downloads_dir.exists():
        for match in downloads_dir.glob("scrcpy*/scrcpy.exe"):
            candidates.append(match)

    winget_dir = home / "AppData" / "Local" / "Microsoft" / "WinGet" / "Packages"
    if winget_dir.exists():
        for package_dir in winget_dir.glob("Genymobile.scrcpy*"):
            for match in package_dir.rglob("scrcpy.exe"):
                candidates.append(match)

    return _dedupe_paths(candidates)


def detect_adb_candidates(scrcpy_path: Path | None = None) -> list[Path]:
    candidates: list[Path] = []

    which_path = shutil.which("adb")
    if which_path:
        candidates.append(Path(which_path))

    home = Path.home()
    direct_candidates = [
        home / "AppData" / "Local" / "Android" / "Sdk" / "platform-tools" / "adb.exe",
        Path("C:/Program Files/Android/platform-tools/adb.exe"),
        Path("C:/tools/platform-tools/adb.exe"),
        home / "Downloads" / "platform-tools" / "adb.exe",
    ]
    candidates.extend(direct_candidates)

    if scrcpy_path:
        scrcpy_parent = scrcpy_path.parent
        candidates.append(scrcpy_parent / "adb.exe")
        candidates.append(scrcpy_parent / "platform-tools" / "adb.exe")

    return _dedupe_paths(candidates)


def quote_posix(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def unique_destination(path: Path) -> Path:
    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    counter = 1
    while True:
        candidate = path.with_name(f"{stem}_{counter}{suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


class AndroidBridge:
    def __init__(self, adb_path: Path | str) -> None:
        self.adb_path = Path(adb_path)
        if not self.adb_path.exists():
            raise AndroidBridgeError(f"ADB wurde nicht gefunden: {self.adb_path}")

    def _run(
        self,
        args: list[str],
        *,
        serial: str | None = None,
        timeout: float = 30.0,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        command = [str(self.adb_path)]
        if serial:
            command.extend(["-s", serial])
        command.extend(args)

        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace",
            )
        except FileNotFoundError as exc:
            raise AndroidBridgeError(f"ADB konnte nicht gestartet werden: {self.adb_path}") from exc
        except subprocess.TimeoutExpired as exc:
            raise AndroidBridgeError(f"ADB-Zeitlimit erreicht: {' '.join(command)}") from exc

        if check and completed.returncode != 0:
            error_text = completed.stderr.strip() or completed.stdout.strip() or "Unbekannter ADB-Fehler"
            raise AndroidBridgeError(error_text)
        return completed

    def shell(self, script: str, *, serial: str | None = None, timeout: float = 30.0) -> str:
        completed = self._run(["shell", "sh", "-c", script], serial=serial, timeout=timeout)
        return completed.stdout

    def list_devices(self) -> list[DeviceInfo]:
        completed = self._run(["devices", "-l"], timeout=20.0)
        devices: list[DeviceInfo] = []
        for line in completed.stdout.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("List of devices attached"):
                continue
            parts = stripped.split()
            if len(parts) < 2:
                continue
            serial = parts[0]
            state = parts[1]
            extras = {item.split(":", 1)[0]: item.split(":", 1)[1] for item in parts[2:] if ":" in item}
            devices.append(
                DeviceInfo(
                    serial=serial,
                    state=state,
                    model=extras.get("model", "").replace("_", " "),
                    transport_id=extras.get("transport_id", ""),
                    raw_line=stripped,
                )
            )
        return devices

    def is_package_installed(self, serial: str, package_name: str = OPEN_CAMERA_PACKAGE) -> bool:
        output = self._run(
            ["shell", "pm", "list", "packages", package_name],
            serial=serial,
            timeout=20.0,
        ).stdout
        return package_name in output

    def launch_open_camera(self, serial: str) -> None:
        self._run(
            [
                "shell",
                "monkey",
                "-p",
                OPEN_CAMERA_PACKAGE,
                "-c",
                "android.intent.category.LAUNCHER",
                "1",
            ],
            serial=serial,
            timeout=20.0,
        )

    def send_keyevent(self, serial: str, keycode: int) -> None:
        self._run(["shell", "input", "keyevent", str(keycode)], serial=serial, timeout=15.0)

    def list_recent_videos(self, serial: str, remote_dir: str) -> list[VideoFile]:
        quoted_dir = quote_posix(remote_dir.rstrip("/"))
        extension_patterns = " ".join(f'"$dir"/*.{ext} "$dir"/*.{ext.upper()}' for ext in VIDEO_EXTENSIONS)
        script = f"""
dir={quoted_dir}
for f in {extension_patterns}; do
  [ -f "$f" ] || continue
  mod=$(toybox stat -c '%Y' "$f" 2>/dev/null || stat -c '%Y' "$f" 2>/dev/null || echo 0)
  size=$(toybox stat -c '%s' "$f" 2>/dev/null || stat -c '%s' "$f" 2>/dev/null || echo -1)
  printf '%s|%s|%s\\n' "$mod" "$size" "$f"
done | sort -t '|' -k1,1nr
"""
        output = self.shell(script, serial=serial, timeout=20.0)
        files: list[VideoFile] = []
        for line in output.splitlines():
            stripped = line.strip()
            if not stripped or "|" not in stripped:
                continue
            parts = stripped.split("|", 2)
            if len(parts) != 3:
                continue
            mod_raw, size_raw, remote_path = parts
            try:
                modified_ts = int(float(mod_raw))
            except ValueError:
                modified_ts = None
            try:
                size_value = int(size_raw)
                size_bytes = size_value if size_value >= 0 else None
            except ValueError:
                size_bytes = None
            files.append(VideoFile(remote_path=remote_path, modified_ts=modified_ts, size_bytes=size_bytes))
        return files

    def get_remote_file_size(self, serial: str, remote_path: str) -> int | None:
        quoted_path = quote_posix(remote_path)
        script = f"toybox stat -c '%s' {quoted_path} 2>/dev/null || stat -c '%s' {quoted_path} 2>/dev/null"
        output = self.shell(script, serial=serial, timeout=15.0).strip()
        if not output:
            return None
        try:
            return int(output)
        except ValueError:
            return None

    def wait_for_file_stable(
        self,
        serial: str,
        remote_path: str,
        *,
        poll_interval_s: float = 1.0,
        max_wait_s: float = 20.0,
    ) -> int | None:
        previous_size: int | None = None
        stable_hits = 0
        deadline = time.monotonic() + max_wait_s

        while time.monotonic() < deadline:
            size_now = self.get_remote_file_size(serial, remote_path)
            if size_now and size_now == previous_size:
                stable_hits += 1
                if stable_hits >= 2:
                    return size_now
            else:
                stable_hits = 0
            previous_size = size_now
            time.sleep(poll_interval_s)

        return previous_size

    def pull_file(self, serial: str, remote_path: str, local_dir: Path) -> Path:
        local_dir.mkdir(parents=True, exist_ok=True)
        target_path = unique_destination(local_dir / Path(remote_path).name)
        self._run(["pull", remote_path, str(target_path)], serial=serial, timeout=300.0)
        if not target_path.exists():
            raise AndroidBridgeError(f"Datei wurde nicht exportiert: {target_path}")
        if target_path.stat().st_size <= 0:
            raise AndroidBridgeError(f"Exportierte Datei ist leer: {target_path}")
        return target_path

    def export_latest_video(
        self,
        serial: str,
        remote_dir: str,
        local_dir: Path,
        *,
        since_remote_path: str | None = None,
    ) -> tuple[Path, VideoFile]:
        recent_files = self.list_recent_videos(serial, remote_dir)
        if not recent_files:
            raise AndroidBridgeError(
                f"Keine Videodateien in {remote_dir} gefunden. Bitte Open Camera auf diesen Speicherpfad einstellen."
            )

        candidate = recent_files[0]
        if since_remote_path and candidate.remote_path == since_remote_path:
            newer_file = next((item for item in recent_files if item.remote_path != since_remote_path), None)
            if newer_file is None:
                raise AndroidBridgeError(
                    "Es wurde noch keine neue Videodatei gefunden. Bitte kurz warten und erneut exportieren."
                )
            candidate = newer_file

        remote_size = self.wait_for_file_stable(serial, candidate.remote_path)
        local_path = self.pull_file(serial, candidate.remote_path, local_dir)

        local_size = local_path.stat().st_size
        if remote_size and local_size != remote_size:
            raise AndroidBridgeError(
                f"Dateigroesse stimmt nicht ueberein ({local_size} lokal vs. {remote_size} auf dem Geraet)."
            )

        return local_path, candidate

    def path_for_subprocess(self) -> str:
        adb_dir = str(self.adb_path.parent)
        current_path = os.environ.get("PATH", "")
        path_parts = [adb_dir]
        if current_path:
            path_parts.append(current_path)
        return os.pathsep.join(path_parts)

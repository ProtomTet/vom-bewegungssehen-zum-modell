from __future__ import annotations

from datetime import datetime
from pathlib import Path
import time

import cv2
from PySide6 import QtCore, QtGui, QtWidgets

from droidcam_stream import (
    DEFAULT_IP,
    DEFAULT_PORT,
    DEFAULT_RESOLUTIONS,
    MjpegStreamThread,
    StreamConfig,
    build_preview_url,
    build_stream_url,
)


APP_TITLE = "DroidCam Capture Bridge"
DEFAULT_EXPORT_DIR = Path.home() / "Videos" / "DroidCamExports"


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


def frame_to_pixmap(frame) -> QtGui.QPixmap:
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    height, width, _channels = rgb_frame.shape
    bytes_per_line = rgb_frame.strides[0]
    image = QtGui.QImage(
        rgb_frame.data,
        width,
        height,
        bytes_per_line,
        QtGui.QImage.Format.Format_RGB888,
    ).copy()
    return QtGui.QPixmap.fromImage(image)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1480, 920)

        self.stream_thread: MjpegStreamThread | None = None
        self.last_frame = None
        self.last_pixmap: QtGui.QPixmap | None = None
        self.current_stream_fps = 0.0
        self.current_frame_count = 0

        self.recording_active = False
        self.recording_pending = False
        self.recording_writer: cv2.VideoWriter | None = None
        self.recording_path: Path | None = None
        self.recording_started_monotonic = 0.0
        self.recording_frame_count = 0

        self._build_ui()
        self._connect_signals()
        self.update_status_labels()

    def _build_ui(self) -> None:
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)

        root_layout = QtWidgets.QHBoxLayout(central_widget)
        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        root_layout.addWidget(splitter)

        left_scroll = QtWidgets.QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_container = QtWidgets.QWidget()
        self.left_layout = QtWidgets.QVBoxLayout(left_container)
        self.left_layout.setSpacing(14)
        left_scroll.setWidget(left_container)

        right_widget = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_widget)
        right_layout.setSpacing(10)

        splitter.addWidget(left_scroll)
        splitter.addWidget(right_widget)
        splitter.setSizes([460, 1020])
        splitter.setStretchFactor(1, 1)

        stream_box = QtWidgets.QGroupBox("DroidCam Verbindung")
        stream_form = QtWidgets.QFormLayout(stream_box)
        self.ip_edit = QtWidgets.QLineEdit(DEFAULT_IP)
        self.port_spin = QtWidgets.QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(DEFAULT_PORT)
        self.force_check = QtWidgets.QCheckBox("Vorhandene Verbindung ueberschreiben")
        self.force_check.setChecked(True)
        self.resolution_combo = QtWidgets.QComboBox()
        for label, value in DEFAULT_RESOLUTIONS:
            self.resolution_combo.addItem(label, value)
        self.stream_url_label = QtWidgets.QLabel()
        self.stream_url_label.setWordWrap(True)
        stream_form.addRow("IP-Adresse", self.ip_edit)
        stream_form.addRow("Port", self.port_spin)
        stream_form.addRow("Streamaufloesung", self.resolution_combo)
        stream_form.addRow("", self.force_check)
        stream_form.addRow("Verwendete Stream-URL", self.stream_url_label)

        stream_button_row = QtWidgets.QHBoxLayout()
        self.start_stream_button = QtWidgets.QPushButton("Livebild starten")
        self.stop_stream_button = QtWidgets.QPushButton("Livebild stoppen")
        self.open_browser_button = QtWidgets.QPushButton("DroidCam im Browser")
        stream_button_row.addWidget(self.start_stream_button)
        stream_button_row.addWidget(self.stop_stream_button)
        stream_button_row.addWidget(self.open_browser_button)
        stream_form.addRow("", self._wrap_layout(stream_button_row))
        self.left_layout.addWidget(stream_box)

        status_box = QtWidgets.QGroupBox("Status")
        status_form = QtWidgets.QFormLayout(status_box)
        self.connection_status_label = QtWidgets.QLabel("Noch keine Verbindung")
        self.connection_status_label.setWordWrap(True)
        self.live_fps_label = QtWidgets.QLabel("-")
        self.frame_size_label = QtWidgets.QLabel("-")
        self.recording_status_label = QtWidgets.QLabel("Keine laufende Aufnahme")
        self.recording_status_label.setWordWrap(True)
        status_form.addRow("Verbindung", self.connection_status_label)
        status_form.addRow("Live-FPS", self.live_fps_label)
        status_form.addRow("Bildgroesse", self.frame_size_label)
        status_form.addRow("Aufnahme", self.recording_status_label)
        self.left_layout.addWidget(status_box)

        recording_box = QtWidgets.QGroupBox("Lokale Aufnahme und Export")
        recording_form = QtWidgets.QFormLayout(recording_box)
        self.export_dir_edit = QtWidgets.QLineEdit(str(DEFAULT_EXPORT_DIR))
        self.file_prefix_edit = QtWidgets.QLineEdit("sportanalyse")
        self.record_fps_spin = QtWidgets.QDoubleSpinBox()
        self.record_fps_spin.setRange(1.0, 120.0)
        self.record_fps_spin.setDecimals(1)
        self.record_fps_spin.setValue(25.0)
        self.sync_fps_check = QtWidgets.QCheckBox("Export-FPS an Live-FPS koppeln")
        self.sync_fps_check.setChecked(True)
        recording_form.addRow("Exportordner", self._path_row(self.export_dir_edit, self.choose_export_dir))
        recording_form.addRow("Dateipraefix", self.file_prefix_edit)
        recording_form.addRow("Fallback Export-FPS", self.record_fps_spin)
        recording_form.addRow("", self.sync_fps_check)

        record_button_row = QtWidgets.QHBoxLayout()
        self.start_record_button = QtWidgets.QPushButton("Aufnahme starten")
        self.stop_record_button = QtWidgets.QPushButton("Aufnahme stoppen")
        self.open_export_button = QtWidgets.QPushButton("Exportordner oeffnen")
        record_button_row.addWidget(self.start_record_button)
        record_button_row.addWidget(self.stop_record_button)
        record_button_row.addWidget(self.open_export_button)
        recording_form.addRow("", self._wrap_layout(record_button_row))
        self.left_layout.addWidget(recording_box)

        hints_box = QtWidgets.QGroupBox("Hinweise")
        hints_layout = QtWidgets.QVBoxLayout(hints_box)
        hints_label = QtWidgets.QLabel(
            "DroidCam liefert hier den Live-Stream. Die eigentlichen Kameraoptionen wie Fokus, Belichtung, "
            "Bildqualitaet oder Framerate stellen Sie weiterhin in der DroidCam-App auf dem Smartphone ein. "
            "Die Desktop-App uebernimmt Vorschau, lokale Aufnahme und Export."
        )
        hints_label.setWordWrap(True)
        hints_layout.addWidget(hints_label)
        self.left_layout.addWidget(hints_box)

        log_box = QtWidgets.QGroupBox("Protokoll")
        log_layout = QtWidgets.QVBoxLayout(log_box)
        self.log_edit = QtWidgets.QPlainTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setMinimumHeight(180)
        log_layout.addWidget(self.log_edit)
        self.left_layout.addWidget(log_box)
        self.left_layout.addStretch(1)

        preview_title = QtWidgets.QLabel("Livebild")
        preview_title.setStyleSheet("font-size: 18px; font-weight: 600;")
        right_layout.addWidget(preview_title)

        self.preview_note_label = QtWidgets.QLabel(
            "Nach dem Start wird der DroidCam-Stream hier live angezeigt. "
            "Bei Verbindungsproblemen pruefen Sie IP, Port und ob Smartphone und PC im selben Netz sind."
        )
        self.preview_note_label.setWordWrap(True)
        right_layout.addWidget(self.preview_note_label)

        self.preview_label = QtWidgets.QLabel("Noch kein Livebild")
        self.preview_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(720, 480)
        self.preview_label.setStyleSheet(
            "background-color: #101010; color: #e8e8e8; border: 1px solid #333333; font-size: 18px;"
        )
        right_layout.addWidget(self.preview_label, 1)

        self.statusBar().showMessage("Bereit")

    def _connect_signals(self) -> None:
        self.ip_edit.textChanged.connect(self.update_status_labels)
        self.port_spin.valueChanged.connect(self.update_status_labels)
        self.resolution_combo.currentIndexChanged.connect(self.update_status_labels)
        self.force_check.stateChanged.connect(self.update_status_labels)
        self.start_stream_button.clicked.connect(self.start_stream)
        self.stop_stream_button.clicked.connect(self.stop_stream)
        self.open_browser_button.clicked.connect(self.open_browser_preview)
        self.start_record_button.clicked.connect(self.start_recording)
        self.stop_record_button.clicked.connect(self.stop_recording)
        self.open_export_button.clicked.connect(self.open_export_folder)

    def _wrap_layout(self, layout: QtWidgets.QLayout) -> QtWidgets.QWidget:
        wrapper = QtWidgets.QWidget()
        wrapper.setLayout(layout)
        return wrapper

    def _path_row(self, line_edit: QtWidgets.QLineEdit, browse_slot) -> QtWidgets.QWidget:
        wrapper = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        button = QtWidgets.QPushButton("Auswaehlen")
        button.clicked.connect(browse_slot)
        layout.addWidget(line_edit, 1)
        layout.addWidget(button)
        return wrapper

    def current_config(self) -> StreamConfig:
        return StreamConfig(
            ip=self.ip_edit.text().strip(),
            port=int(self.port_spin.value()),
            resolution=str(self.resolution_combo.currentData() or ""),
            force_connection=self.force_check.isChecked(),
        )

    def current_export_dir(self) -> Path:
        text = self.export_dir_edit.text().strip()
        if not text:
            raise RuntimeError("Bitte einen Exportordner angeben.")
        return Path(text)

    def append_log(self, text: str) -> None:
        stamp = time.strftime("%H:%M:%S")
        self.log_edit.appendPlainText(f"[{stamp}] {text}")
        self.statusBar().showMessage(text, 6000)

    def update_status_labels(self) -> None:
        config = self.current_config()
        self.stream_url_label.setText(build_stream_url(config))
        if self.last_frame is not None:
            height, width = self.last_frame.shape[:2]
            self.frame_size_label.setText(f"{width} x {height}")
        else:
            self.frame_size_label.setText("-")
        self.live_fps_label.setText(f"{self.current_stream_fps:.1f}" if self.current_stream_fps else "-")
        if self.recording_active:
            duration = time.monotonic() - self.recording_started_monotonic
            self.recording_status_label.setText(
                f"Laeuft seit {duration:.1f} s | Frames: {self.recording_frame_count} | Datei: {self.recording_path}"
            )
        elif self.recording_pending:
            self.recording_status_label.setText("Aufnahme wird mit dem naechsten Bild gestartet ...")
        else:
            self.recording_status_label.setText("Keine laufende Aufnahme")

    def choose_export_dir(self) -> None:
        selected = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Exportordner auswaehlen",
            self.export_dir_edit.text() or str(DEFAULT_EXPORT_DIR),
        )
        if selected:
            self.export_dir_edit.setText(selected)

    def start_stream(self) -> None:
        config = self.current_config()
        if not config.ip:
            self.show_error("Bitte eine IP-Adresse fuer DroidCam eintragen.")
            return

        self.stop_stream(show_log=False)
        self.preview_label.setText("Verbinde mit DroidCam ...")
        self.preview_label.setPixmap(QtGui.QPixmap())

        self.stream_thread = MjpegStreamThread(config)
        self.stream_thread.stream_started.connect(self.handle_stream_started)
        self.stream_thread.frame_ready.connect(self.handle_frame)
        self.stream_thread.status.connect(self.handle_stream_status)
        self.stream_thread.error.connect(self.handle_stream_error)
        self.stream_thread.finished.connect(self.handle_stream_finished)
        self.stream_thread.start()

    def stop_stream(self, *, show_log: bool = True) -> None:
        thread = self.stream_thread
        self.stream_thread = None
        if thread is not None:
            thread.stop()
            thread.wait(2000)
        self.connection_status_label.setText("Livebild gestoppt")
        self.preview_label.setText("Livebild gestoppt")
        self.preview_label.setPixmap(QtGui.QPixmap())
        if show_log:
            self.append_log("DroidCam-Livebild wurde gestoppt.")

    def handle_stream_started(self, stream_url: str) -> None:
        self.connection_status_label.setText(f"Verbunden mit {stream_url}")
        self.preview_note_label.setText("DroidCam-Stream laeuft.")
        self.append_log(f"Stream gestartet: {stream_url}")

    def handle_stream_status(self, text: str) -> None:
        self.connection_status_label.setText(text)
        self.append_log(text)

    def handle_stream_error(self, text: str) -> None:
        self.connection_status_label.setText(text)
        self.append_log(f"Fehler: {text}")
        if self.recording_active or self.recording_pending:
            self.stop_recording(notify=False)
        QtWidgets.QMessageBox.warning(self, APP_TITLE, text)

    def handle_stream_finished(self) -> None:
        if self.stream_thread is not None and self.sender() is self.stream_thread:
            self.stream_thread = None
        if not self.recording_active:
            self.connection_status_label.setText("Keine aktive Stream-Verbindung")
        self.preview_note_label.setText(
            "Nach dem Start wird der DroidCam-Stream hier live angezeigt. "
            "Bei Verbindungsproblemen pruefen Sie IP, Port und ob Smartphone und PC im selben Netz sind."
        )

    def handle_frame(self, frame, fps: float, frame_count: int) -> None:
        self.last_frame = frame
        self.current_stream_fps = fps
        self.current_frame_count = frame_count

        self.last_pixmap = frame_to_pixmap(frame)
        scaled = self.last_pixmap.scaled(
            self.preview_label.size(),
            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            QtCore.Qt.TransformationMode.SmoothTransformation,
        )
        self.preview_label.setPixmap(scaled)

        if self.recording_pending:
            try:
                self.begin_recording(frame, fps)
            except RuntimeError as exc:
                self.recording_pending = False
                self.show_error(str(exc))
                self.update_status_labels()
                return

        if self.recording_active and self.recording_writer is not None:
            self.recording_writer.write(frame)
            self.recording_frame_count += 1

        self.update_status_labels()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        if self.last_pixmap is not None:
            scaled = self.last_pixmap.scaled(
                self.preview_label.size(),
                QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation,
            )
            self.preview_label.setPixmap(scaled)

    def start_recording(self) -> None:
        if self.recording_active or self.recording_pending:
            QtWidgets.QMessageBox.information(self, APP_TITLE, "Es laeuft bereits eine Aufnahme.")
            return
        if self.stream_thread is None:
            QtWidgets.QMessageBox.information(self, APP_TITLE, "Bitte zuerst das Livebild starten.")
            return

        self.recording_pending = True
        self.recording_frame_count = 0
        self.recording_path = None
        self.append_log("Aufnahme vorgemerkt. Sie startet mit dem naechsten Bild.")
        self.update_status_labels()

    def begin_recording(self, frame, stream_fps: float) -> None:
        export_dir = self.current_export_dir()
        export_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        prefix = self.file_prefix_edit.text().strip() or "sportanalyse"
        base_path = export_dir / f"{prefix}_{timestamp}"

        writer_fps = float(self.record_fps_spin.value())
        if self.sync_fps_check.isChecked() and stream_fps >= 5.0:
            writer_fps = round(stream_fps, 2)

        height, width = frame.shape[:2]
        mp4_path = unique_destination(base_path.with_suffix(".mp4"))
        writer = cv2.VideoWriter(
            str(mp4_path),
            cv2.VideoWriter_fourcc(*"mp4v"),
            writer_fps,
            (width, height),
        )
        actual_path = mp4_path
        if not writer.isOpened():
            avi_path = unique_destination(base_path.with_suffix(".avi"))
            writer = cv2.VideoWriter(
                str(avi_path),
                cv2.VideoWriter_fourcc(*"MJPG"),
                writer_fps,
                (width, height),
            )
            actual_path = avi_path

        if not writer.isOpened():
            self.recording_pending = False
            raise RuntimeError("Videodatei konnte nicht zum Schreiben geoeffnet werden.")

        self.recording_writer = writer
        self.recording_path = actual_path
        self.recording_pending = False
        self.recording_active = True
        self.recording_started_monotonic = time.monotonic()
        self.recording_frame_count = 0
        self.append_log(f"Aufnahme gestartet: {actual_path.name} | Export-FPS: {writer_fps:.2f}")
        self.update_status_labels()

    def stop_recording(self, *, notify: bool = True) -> None:
        if self.recording_pending:
            self.recording_pending = False
            self.append_log("Vorgemerkte Aufnahme wurde verworfen.")
            self.update_status_labels()
            return
        if not self.recording_active:
            if notify:
                QtWidgets.QMessageBox.information(self, APP_TITLE, "Es laeuft aktuell keine Aufnahme.")
            return

        writer = self.recording_writer
        self.recording_writer = None
        if writer is not None:
            writer.release()

        self.recording_active = False
        saved_path = self.recording_path
        self.recording_path = None
        self.append_log(
            f"Aufnahme beendet. Exportiert wurden {self.recording_frame_count} Frames nach {saved_path}."
        )
        self.update_status_labels()

        if notify and saved_path is not None:
            QtWidgets.QMessageBox.information(
                self,
                APP_TITLE,
                f"Die Videodatei wurde lokal exportiert:\n{saved_path}",
            )

    def open_browser_preview(self) -> None:
        config = self.current_config()
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(build_preview_url(config.ip, config.port)))

    def open_export_folder(self) -> None:
        export_dir = self.current_export_dir()
        export_dir.mkdir(parents=True, exist_ok=True)
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(export_dir)))

    def show_error(self, message: str) -> None:
        self.append_log(f"Fehler: {message}")
        QtWidgets.QMessageBox.warning(self, APP_TITLE, message)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if self.recording_active or self.recording_pending:
            self.stop_recording(notify=False)
        self.stop_stream(show_log=False)
        super().closeEvent(event)


def main() -> int:
    app = QtWidgets.QApplication([])
    app.setApplicationName(APP_TITLE)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

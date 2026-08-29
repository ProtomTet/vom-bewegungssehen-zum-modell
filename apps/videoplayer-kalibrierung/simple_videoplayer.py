import math
import os
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, ttk

import cv2
from PIL import Image, ImageDraw, ImageFont, ImageTk


class SimpleVideoPlayer:
    """
    Einfacher Videoplayer mit Kalibrierung und frei verschiebbarer Overlay-Zeichenebene.

    Enthaltene Funktionen:
    - Video laden
    - Play / Pause / Slow Motion
    - Frameschritte vor / zurück
    - Anzeige von FPS, Delta-t, Frame und Zeit
    - 2-Punkt- oder 3-Punkt-Kalibrierung
    - eingeblendete Maßstabsleiste
    - Overlay als frei verschiebbare Zeichenebene über dem Video
    - horizontales und vertikales Verschieben des Overlays
    - farbiges Zeichnen mit variabler Stiftdicke
    - Zuschnitt beim PNG-Export auf den tatsächlich bemalten Bereich
    """

    LEFT_PANEL_WIDTH = 340
    DEFAULT_OVERLAY_COLOR = "#ff0000"
    DISPLAY_OVERLAY_SUPERSAMPLE = 2
    EXPORT_OVERLAY_SCALE = 4
    MAX_OFFSET_RANGE = 1000000

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Einfacher Videoplayer mit Kalibrierung und Overlay")
        self.root.minsize(1200, 800)

        # -----------------------------
        # Videozustand
        # -----------------------------
        self.cap = None
        self.video_path = None
        self.is_playing = False
        self.play_speed = 1.0
        self.after_job = None

        self.fps = 0.0
        self.fps_is_fallback = False
        self.total_frames = 0
        self.current_frame_index = 0
        self.video_width = 0
        self.video_height = 0
        self.current_frame_bgr = None

        # Darstellung im Canvas
        self.tk_image = None
        self.overlay_tk_image = None
        self.display_scale = 1.0
        self.display_offset_x = 0.0
        self.display_offset_y = 0.0
        self.display_width = 0
        self.display_height = 0
        self._base_frame_image = None
        self._base_frame_cache_size = None

        # -----------------------------
        # Kalibrierung
        # -----------------------------
        self.calibration_points = []
        self.is_collecting_calibration = False
        self.calibration_frame_index = None
        self.scale_x_m_per_px = None
        self.scale_y_m_per_px = None
        self.calibration_display_unit = None

        # -----------------------------
        # Overlay / Zeichnen
        # -----------------------------
        self.overlay_strokes = []
        self.current_stroke = None
        self.current_overlay_color = self.DEFAULT_OVERLAY_COLOR

        # -----------------------------
        # Tk-Variablen
        # -----------------------------
        self.jump_frames_var = tk.StringVar(value="10")
        self.slow_speed_var = tk.StringVar(value="0.50")

        self.file_var = tk.StringVar(value="Keine Datei geladen")
        self.fps_var = tk.StringVar(value="FPS: -")
        self.delta_t_var = tk.StringVar(value="Δt: -")
        self.frame_info_var = tk.StringVar(value="Frame: - / -")
        self.time_info_var = tk.StringVar(value="Zeit: - / -")
        self.status_var = tk.StringVar(value="Bereit")

        self.calibration_mode_var = tk.StringVar(value="horizontal")
        self.reference_x_var = tk.StringVar(value="1.00")
        self.reference_y_var = tk.StringVar(value="1.00")
        self.reference_unit_var = tk.StringVar(value="m")
        self.calibration_info_var = tk.StringVar(value="Kalibrierung: noch nicht gesetzt")
        self.scale_info_var = tk.StringVar(value="Maßstab: noch nicht berechnet")
        self.point_info_var = tk.StringVar(value="Punkte: 0 / 2")
        self.reference_order_var = tk.StringVar(
            value="Reihenfolge:\n1 = linker Startpunkt\n2 = rechter Endpunkt"
        )

        self.overlay_enabled_var = tk.BooleanVar(value=True)
        self.overlay_draw_mode_var = tk.BooleanVar(value=False)
        self.overlay_brush_size_var = tk.StringVar(value="3")
        self.overlay_color_var = tk.StringVar(value=self.DEFAULT_OVERLAY_COLOR)
        self.overlay_offset_x_var = tk.StringVar(value="0")
        self.overlay_offset_y_var = tk.StringVar(value="0")
        self.overlay_info_var = tk.StringVar(value="Overlay: leer")

        self._build_ui()
        self._bind_events()
        self._update_calibration_mode_ui()
        self._update_delta_t_display()
        self._update_overlay_controls_state()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(80, self._maximize_window)

    # ------------------------------------------------------------------
    # GUI
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=8)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(1, weight=1)
        outer.rowconfigure(0, weight=1)

        # Linke Werkzeugspalte
        left = ttk.Frame(outer, width=self.LEFT_PANEL_WIDTH)
        left.grid(row=0, column=0, sticky="nsw", padx=(0, 10))
        left.grid_propagate(False)
        left.columnconfigure(0, weight=1)
        left.rowconfigure(3, weight=1)

        # Rechter Hauptbereich
        right = ttk.Frame(outer)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)

        file_box = ttk.LabelFrame(left, text="Datei", padding=10)
        file_box.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        file_box.columnconfigure(0, weight=1)
        ttk.Button(file_box, text="Video laden", command=self.open_video).grid(
            row=0, column=0, sticky="ew", pady=(0, 8)
        )
        ttk.Label(file_box, textvariable=self.file_var, wraplength=290, justify="left").grid(
            row=1, column=0, sticky="w"
        )

        meta_box = ttk.LabelFrame(left, text="Metadaten", padding=10)
        meta_box.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        for idx, var in enumerate(
            [self.fps_var, self.delta_t_var, self.frame_info_var, self.time_info_var]
        ):
            ttk.Label(meta_box, textvariable=var, wraplength=290, justify="left").grid(
                row=idx, column=0, sticky="w", pady=2
            )

        calib_box = ttk.LabelFrame(left, text="Kalibrierung", padding=10)
        calib_box.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        calib_box.columnconfigure(0, weight=1)
        calib_box.columnconfigure(1, weight=1)

        ttk.Label(calib_box, text="Modus:").grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            calib_box,
            textvariable=self.calibration_mode_var,
            values=["horizontal", "horizontal_und_vertikal"],
            state="readonly",
            width=22,
        ).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(2, 8))

        ttk.Label(calib_box, text="Horizontales Realmaß:").grid(
            row=2, column=0, columnspan=2, sticky="w"
        )
        self.reference_x_entry = ttk.Entry(calib_box, textvariable=self.reference_x_var)
        self.reference_x_entry.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(2, 8))

        ttk.Label(calib_box, text="Vertikales Realmaß:").grid(
            row=4, column=0, columnspan=2, sticky="w"
        )
        self.reference_y_entry = ttk.Entry(calib_box, textvariable=self.reference_y_var)
        self.reference_y_entry.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(2, 8))

        ttk.Label(calib_box, text="Einheit:").grid(row=6, column=0, sticky="w")
        ttk.Combobox(
            calib_box,
            textvariable=self.reference_unit_var,
            values=["cm", "m"],
            state="readonly",
            width=8,
        ).grid(row=6, column=1, sticky="ew", pady=(0, 8))

        ttk.Button(
            calib_box,
            text="Punkte erfassen / neu setzen",
            command=self.start_calibration_collection,
        ).grid(row=7, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        ttk.Button(calib_box, text="Kalibrierung anwenden", command=self.apply_calibration).grid(
            row=8, column=0, columnspan=2, sticky="ew", pady=(0, 6)
        )
        ttk.Button(calib_box, text="Kalibrierung löschen", command=self.clear_calibration).grid(
            row=9, column=0, columnspan=2, sticky="ew", pady=(0, 8)
        )

        ttk.Label(calib_box, textvariable=self.point_info_var, wraplength=290, justify="left").grid(
            row=10, column=0, columnspan=2, sticky="w", pady=(0, 6)
        )
        ttk.Label(calib_box, textvariable=self.reference_order_var, wraplength=290, justify="left").grid(
            row=11, column=0, columnspan=2, sticky="w", pady=(0, 6)
        )
        ttk.Separator(calib_box, orient="horizontal").grid(
            row=12, column=0, columnspan=2, sticky="ew", pady=6
        )
        ttk.Label(calib_box, textvariable=self.calibration_info_var, wraplength=290, justify="left").grid(
            row=13, column=0, columnspan=2, sticky="w", pady=(0, 4)
        )
        ttk.Label(calib_box, textvariable=self.scale_info_var, wraplength=290, justify="left").grid(
            row=14, column=0, columnspan=2, sticky="w"
        )

        overlay_box = ttk.LabelFrame(left, text="Overlay / Zeichnen", padding=10)
        overlay_box.grid(row=3, column=0, sticky="nsew")
        overlay_box.columnconfigure(0, weight=1)
        overlay_box.columnconfigure(1, weight=1)

        ttk.Checkbutton(
            overlay_box,
            text="Overlay anzeigen",
            variable=self.overlay_enabled_var,
            command=self._redraw_current_frame,
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))

        ttk.Checkbutton(
            overlay_box,
            text="Zeichnen aktiv",
            variable=self.overlay_draw_mode_var,
            command=self._toggle_overlay_draw_mode,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 8))

        ttk.Label(overlay_box, text="Farbe:").grid(row=2, column=0, sticky="w")
        color_btn_row = ttk.Frame(overlay_box)
        color_btn_row.grid(row=2, column=1, sticky="ew")
        color_btn_row.columnconfigure(0, weight=1)
        self.color_preview = tk.Label(
            color_btn_row,
            width=3,
            bg=self.current_overlay_color,
            relief="sunken",
            bd=1,
        )
        self.color_preview.grid(row=0, column=0, sticky="w", padx=(0, 6))
        ttk.Button(color_btn_row, text="Wählen", command=self.choose_overlay_color).grid(
            row=0, column=1, sticky="ew"
        )

        ttk.Label(overlay_box, text="Stiftdicke:").grid(row=3, column=0, sticky="w", pady=(8, 0))
        ttk.Spinbox(
            overlay_box,
            from_=1,
            to=200,
            increment=1,
            textvariable=self.overlay_brush_size_var,
            width=8,
            command=self._redraw_current_frame,
        ).grid(row=3, column=1, sticky="w", pady=(8, 0))

        ttk.Label(overlay_box, text="Overlay-Verschiebung X [px]:").grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(12, 0)
        )
        ttk.Spinbox(
            overlay_box,
            from_=-self.MAX_OFFSET_RANGE,
            to=self.MAX_OFFSET_RANGE,
            increment=10,
            textvariable=self.overlay_offset_x_var,
            width=14,
            command=self._redraw_current_frame,
        ).grid(row=5, column=0, columnspan=2, sticky="w")

        ttk.Label(overlay_box, text="Overlay-Verschiebung Y [px]:").grid(
            row=6, column=0, columnspan=2, sticky="w", pady=(8, 0)
        )
        ttk.Spinbox(
            overlay_box,
            from_=-self.MAX_OFFSET_RANGE,
            to=self.MAX_OFFSET_RANGE,
            increment=10,
            textvariable=self.overlay_offset_y_var,
            width=14,
            command=self._redraw_current_frame,
        ).grid(row=7, column=0, columnspan=2, sticky="w")

        offset_btns = ttk.Frame(overlay_box)
        offset_btns.grid(row=8, column=0, columnspan=2, sticky="ew", pady=(6, 8))
        offset_btns.columnconfigure((0, 1, 2), weight=1)
        ttk.Button(offset_btns, text="X = 0", command=lambda: self._set_overlay_offset(x=0)).grid(
            row=0, column=0, sticky="ew", padx=(0, 4)
        )
        ttk.Button(offset_btns, text="Y = 0", command=lambda: self._set_overlay_offset(y=0)).grid(
            row=0, column=1, sticky="ew", padx=2
        )
        ttk.Button(offset_btns, text="Beides = 0", command=self.reset_overlay_offset).grid(
            row=0, column=2, sticky="ew", padx=(4, 0)
        )

        overlay_btns = ttk.Frame(overlay_box)
        overlay_btns.grid(row=9, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        overlay_btns.columnconfigure((0, 1), weight=1)
        ttk.Button(overlay_btns, text="Overlay leeren", command=self.clear_overlay).grid(
            row=0, column=0, sticky="ew", padx=(0, 4)
        )
        ttk.Button(overlay_btns, text="Overlay als PNG speichern", command=self.save_overlay_png).grid(
            row=0, column=1, sticky="ew", padx=(4, 0)
        )

        ttk.Label(overlay_box, text="Hinweis:", font=("TkDefaultFont", 9, "bold")).grid(
            row=10, column=0, columnspan=2, sticky="w"
        )
        ttk.Label(
            overlay_box,
            text=(
                "Offset-Werte verschieben das Overlay frei nach links/rechts bzw. oben/unten.\n"
                "Beim Export wird nur der tatsächlich bemalte Bereich gespeichert."
            ),
            wraplength=290,
            justify="left",
        ).grid(row=11, column=0, columnspan=2, sticky="w", pady=(2, 8))
        ttk.Label(overlay_box, textvariable=self.overlay_info_var, wraplength=290, justify="left").grid(
            row=12, column=0, columnspan=2, sticky="w"
        )

        # Rechter Bereich: Video + Steuerelemente
        video_box = ttk.LabelFrame(right, text="Videobild", padding=6)
        video_box.grid(row=0, column=0, sticky="nsew")
        video_box.columnconfigure(0, weight=1)
        video_box.rowconfigure(0, weight=1)

        self.video_canvas = tk.Canvas(video_box, bg="black", highlightthickness=0)
        self.video_canvas.grid(row=0, column=0, sticky="nsew")

        controls = ttk.Frame(video_box)
        controls.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        controls.columnconfigure(11, weight=1)

        ttk.Button(controls, text="⏮ Zurück", command=self.step_backward).grid(
            row=0, column=0, padx=(0, 6), pady=4
        )
        ttk.Button(controls, text="▶ Play", command=self.play_normal).grid(
            row=0, column=1, padx=6, pady=4
        )
        ttk.Button(controls, text="⏸ Pause", command=self.pause_video).grid(
            row=0, column=2, padx=6, pady=4
        )
        ttk.Button(controls, text="🐢 Langsam", command=self.play_slow).grid(
            row=0, column=3, padx=6, pady=4
        )
        ttk.Button(controls, text="⏭ Vor", command=self.step_forward).grid(
            row=0, column=4, padx=6, pady=4
        )
        ttk.Button(controls, text="Zum Anfang", command=self.go_to_start).grid(
            row=0, column=5, padx=(6, 12), pady=4
        )

        ttk.Separator(controls, orient="vertical").grid(row=0, column=6, sticky="ns", padx=(0, 12))

        ttk.Label(controls, text="Sprungweite [Frames]:").grid(row=0, column=7, sticky="e")
        ttk.Entry(controls, textvariable=self.jump_frames_var, width=7).grid(
            row=0, column=8, padx=(6, 12), pady=4
        )

        ttk.Label(controls, text="Slow-Faktor:").grid(row=0, column=9, sticky="e")
        ttk.Combobox(
            controls,
            textvariable=self.slow_speed_var,
            values=["0.25", "0.50", "0.75"],
            width=7,
            state="readonly",
        ).grid(row=0, column=10, padx=(6, 0), pady=4)

        status_frame = ttk.Frame(right)
        status_frame.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        ttk.Label(status_frame, textvariable=self.status_var).pack(side="left")

    def _bind_events(self) -> None:
        self.jump_frames_var.trace_add("write", lambda *_: self._update_delta_t_display())
        self.calibration_mode_var.trace_add("write", lambda *_: self._update_calibration_mode_ui())
        self.overlay_offset_x_var.trace_add("write", lambda *_: self._redraw_current_frame())
        self.overlay_offset_y_var.trace_add("write", lambda *_: self._redraw_current_frame())
        self.overlay_brush_size_var.trace_add("write", lambda *_: self._redraw_current_frame())

        self.video_canvas.bind("<Button-1>", self._on_canvas_left_down)
        self.video_canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.video_canvas.bind("<ButtonRelease-1>", self._on_canvas_left_up)
        self.video_canvas.bind("<Configure>", lambda _event: self._redraw_current_frame())

        self.root.bind("<Left>", lambda _event: self.step_backward())
        self.root.bind("<Right>", lambda _event: self.step_forward())
        self.root.bind("<space>", self._toggle_play_pause)
        self.root.bind("<Home>", lambda _event: self.go_to_start())

    def _maximize_window(self) -> None:
        try:
            self.root.state("zoomed")
            return
        except Exception:
            pass
        try:
            self.root.attributes("-zoomed", True)
            return
        except Exception:
            pass
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{sw}x{sh}+0+0")

    # ------------------------------------------------------------------
    # Hilfsfunktionen
    # ------------------------------------------------------------------
    def _get_jump_frames(self) -> int:
        try:
            value = int(self.jump_frames_var.get())
            return max(1, value)
        except ValueError:
            return 1

    def _get_slow_speed(self) -> float:
        try:
            value = float(self.slow_speed_var.get())
            return value if value > 0 else 0.5
        except ValueError:
            return 0.5

    def _get_overlay_offset_x(self) -> int:
        try:
            return int(float(self.overlay_offset_x_var.get().replace(",", ".")))
        except ValueError:
            return 0

    def _get_overlay_offset_y(self) -> int:
        try:
            return int(float(self.overlay_offset_y_var.get().replace(",", ".")))
        except ValueError:
            return 0

    def _get_overlay_brush_size(self) -> int:
        try:
            value = int(float(self.overlay_brush_size_var.get().replace(",", ".")))
            return max(1, value)
        except ValueError:
            return 3

    def _format_seconds(self, seconds: float) -> str:
        seconds = max(0.0, seconds)
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"
        return f"{minutes:02d}:{secs:06.3f}"

    def _unit_to_meter_factor(self) -> float:
        return 0.01 if self.reference_unit_var.get() == "cm" else 1.0

    def _invalidate_base_frame_cache(self) -> None:
        self._base_frame_image = None
        self._base_frame_cache_size = None

    def _expected_point_count(self) -> int:
        return 2 if self.calibration_mode_var.get() == "horizontal" else 3

    def _update_delta_t_display(self) -> None:
        jump_frames = self._get_jump_frames()
        if self.fps and self.fps > 0:
            delta_t = jump_frames / self.fps
            warnung = "  – Bildrate angenommen, Wert unsicher!" if self.fps_is_fallback else ""
            self.delta_t_var.set(
                f"Δt: {delta_t:.6f} s ({jump_frames} Frames bei {self.fps:.3f} FPS){warnung}"
            )
        else:
            self.delta_t_var.set(f"Δt: - ({jump_frames} Frames)")

    def _update_info_labels(self) -> None:
        if self.total_frames > 0:
            self.frame_info_var.set(f"Frame: {self.current_frame_index + 1} / {self.total_frames}")
        else:
            self.frame_info_var.set("Frame: - / -")

        if self.fps > 0:
            current_t = self.current_frame_index / self.fps
            total_t = (self.total_frames - 1) / self.fps if self.total_frames > 0 else 0.0
            self.time_info_var.set(
                f"Zeit: {self._format_seconds(current_t)} / {self._format_seconds(total_t)}"
            )
        else:
            self.time_info_var.set("Zeit: - / -")

    def _update_overlay_controls_state(self) -> None:
        draw_active = self.overlay_draw_mode_var.get()
        try:
            self.video_canvas.configure(cursor="pencil" if draw_active else "")
        except tk.TclError:
            self.video_canvas.configure(cursor="tcross" if draw_active else "")

    def _toggle_overlay_draw_mode(self) -> None:
        self._update_overlay_controls_state()
        self._redraw_current_frame()
        if self.overlay_draw_mode_var.get():
            self.status_var.set("Overlay-Zeichnen aktiv.")
        else:
            self.status_var.set("Overlay-Zeichnen deaktiviert.")

    def _update_overlay_info(self) -> None:
        point_count = sum(len(stroke["points"]) for stroke in self.overlay_strokes)
        self.overlay_info_var.set(
            f"Overlay: {len(self.overlay_strokes)} Strich(e), {point_count} Punkt(e), Export {self.EXPORT_OVERLAY_SCALE}×"
        )

    def _update_calibration_mode_ui(self) -> None:
        if self.calibration_mode_var.get() == "horizontal":
            self.reference_y_entry.state(["disabled"])
            self.point_info_var.set(f"Punkte: {len(self.calibration_points)} / 2")
            self.reference_order_var.set(
                "Reihenfolge:\n1 = linker Startpunkt\n2 = rechter Endpunkt"
            )
        else:
            self.reference_y_entry.state(["!disabled"])
            self.point_info_var.set(f"Punkte: {len(self.calibration_points)} / 3")
            self.reference_order_var.set(
                "Reihenfolge:\n1 = gemeinsamer Ursprung\n2 = Breite / horizontal\n3 = Höhe / vertikal"
            )
        self._invalidate_base_frame_cache()
        self._redraw_current_frame()

    def _parse_positive_float(self, value: str, field_name: str) -> float:
        try:
            parsed = float(value.replace(",", "."))
        except ValueError as exc:
            raise ValueError(f"{field_name} ist keine gültige Zahl.") from exc
        if parsed <= 0:
            raise ValueError(f"{field_name} muss größer als 0 sein.")
        return parsed

    def _canvas_to_video_coords(self, x: float, y: float):
        if self.display_width <= 0 or self.display_height <= 0 or self.display_scale <= 0:
            return None
        if not (
            self.display_offset_x <= x <= self.display_offset_x + self.display_width
            and self.display_offset_y <= y <= self.display_offset_y + self.display_height
        ):
            return None

        vx = (x - self.display_offset_x) / self.display_scale
        vy = (y - self.display_offset_y) / self.display_scale
        vx = max(0.0, min(vx, max(0, self.video_width - 1)))
        vy = max(0.0, min(vy, max(0, self.video_height - 1)))
        return vx, vy

    def _video_to_canvas(self, x: float, y: float):
        return (
            self.display_offset_x + x * self.display_scale,
            self.display_offset_y + y * self.display_scale,
        )

    def _set_overlay_offset(self, x=None, y=None) -> None:
        if x is not None:
            self.overlay_offset_x_var.set(str(int(x)))
        if y is not None:
            self.overlay_offset_y_var.set(str(int(y)))
        self._redraw_current_frame()

    def reset_overlay_offset(self) -> None:
        self.overlay_offset_x_var.set("0")
        self.overlay_offset_y_var.set("0")
        self._redraw_current_frame()

    def choose_overlay_color(self) -> None:
        result = colorchooser.askcolor(color=self.current_overlay_color, title="Overlay-Farbe wählen")
        if not result or not result[1]:
            return
        self.current_overlay_color = result[1]
        self.overlay_color_var.set(self.current_overlay_color)
        self.color_preview.configure(bg=self.current_overlay_color)
        self.status_var.set(f"Overlay-Farbe gesetzt: {self.current_overlay_color}")

    # ------------------------------------------------------------------
    # Video laden / freigeben
    # ------------------------------------------------------------------
    def _clear_overlay_state(self, reset_status: bool = True, redraw: bool = True) -> None:
        self.overlay_strokes = []
        self.current_stroke = None
        self._update_overlay_info()
        if redraw:
            self._redraw_current_frame()
        if reset_status:
            self.status_var.set("Overlay gelöscht.")

    def open_video(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Video auswählen",
            filetypes=[
                ("Videodateien", "*.mp4 *.mov *.avi *.mkv *.m4v *.wmv"),
                ("Alle Dateien", "*.*"),
            ],
        )
        if not file_path:
            return

        self._release_video()

        cap = cv2.VideoCapture(file_path)
        if not cap.isOpened():
            messagebox.showerror("Fehler", "Die Videodatei konnte nicht geöffnet werden.")
            return

        self.cap = cap
        self.video_path = file_path
        self.fps = float(self.cap.get(cv2.CAP_PROP_FPS) or 0.0)
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        self.video_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        self.video_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        self.current_frame_index = 0

        if self.fps <= 0:
            self.fps = 30.0
            self.fps_is_fallback = True
            self.status_var.set(
                "Warnung: Bildrate nicht lesbar, 30 FPS angenommen. "
                "Alle Zeitangaben sind damit unsicher!"
            )
        else:
            self.fps_is_fallback = False
            self.status_var.set("Video geladen.")

        self.file_var.set(os.path.basename(file_path))
        self.fps_var.set(
            f"FPS: {self.fps:.3f} Hz" + ("  (ANGENOMMEN!)" if self.fps_is_fallback else "")
        )
        self.clear_calibration(reset_status=False)
        self._clear_overlay_state(reset_status=False, redraw=False)
        self._update_delta_t_display()
        self._seek_to_frame(0)

    def _release_video(self) -> None:
        self.pause_video(cancel_only=True)
        if self.cap is not None:
            self.cap.release()
            self.cap = None

        self.video_path = None
        self.fps = 0.0
        self.fps_is_fallback = False
        self.total_frames = 0
        self.current_frame_index = 0
        self.video_width = 0
        self.video_height = 0
        self.current_frame_bgr = None
        self.tk_image = None
        self.overlay_tk_image = None
        self._invalidate_base_frame_cache()

        self.video_canvas.delete("all")
        self.file_var.set("Keine Datei geladen")
        self.fps_var.set("FPS: -")
        self.frame_info_var.set("Frame: - / -")
        self.time_info_var.set("Zeit: - / -")
        self._update_delta_t_display()

    # ------------------------------------------------------------------
    # Frame lesen / anzeigen / Seek
    # ------------------------------------------------------------------
    def _read_frame_at_current_position(self):
        if self.cap is None:
            return None

        success, frame = self.cap.read()
        if not success:
            return None

        pos_after_read = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))
        self.current_frame_index = max(0, pos_after_read - 1)
        return frame

    def _display_frame(self, frame) -> None:
        if frame is None:
            return
        self.current_frame_bgr = frame.copy()
        self._invalidate_base_frame_cache()
        self._redraw_current_frame()
        self._update_info_labels()

    def _redraw_current_frame(self) -> None:
        self.video_canvas.delete("all")
        if self.current_frame_bgr is None:
            return

        canvas_w = max(self.video_canvas.winfo_width(), 640)
        canvas_h = max(self.video_canvas.winfo_height(), 360)

        if self._base_frame_image is None or self._base_frame_cache_size != (canvas_w, canvas_h):
            frame_rgb = cv2.cvtColor(self.current_frame_bgr, cv2.COLOR_BGR2RGB)
            img_h, img_w = frame_rgb.shape[:2]
            if img_w <= 0 or img_h <= 0:
                return

            scale = min(canvas_w / img_w, canvas_h / img_h)
            scale = max(scale, 0.0001)
            new_w = max(1, int(img_w * scale))
            new_h = max(1, int(img_h * scale))
            self.display_scale = scale
            self.display_width = new_w
            self.display_height = new_h
            self.display_offset_x = (canvas_w - new_w) / 2
            self.display_offset_y = (canvas_h - new_h) / 2

            interpolation = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
            resized = cv2.resize(frame_rgb, (new_w, new_h), interpolation=interpolation)
            image = Image.fromarray(resized).convert("RGBA")
            self._draw_calibration_on_image(image)
            self._base_frame_image = image
            self._base_frame_cache_size = (canvas_w, canvas_h)

        self.tk_image = ImageTk.PhotoImage(image=self._base_frame_image)
        self.video_canvas.create_image(
            self.display_offset_x,
            self.display_offset_y,
            anchor="nw",
            image=self.tk_image,
        )

        if self.overlay_enabled_var.get():
            self._draw_overlay()

    def _draw_calibration_on_image(self, image: Image.Image) -> None:
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default()

        if self.scale_x_m_per_px is not None:
            self._draw_scale_bar(draw, image.size, font)

        show_calibration_points = (
            self.calibration_frame_index is not None
            and self.current_frame_index == self.calibration_frame_index
        )

        if show_calibration_points and self.calibration_points:
            for idx, (x, y) in enumerate(self.calibration_points, start=1):
                dx = x * self.display_scale
                dy = y * self.display_scale
                r = 6
                draw.ellipse((dx - r, dy - r, dx + r, dy + r), outline="yellow", width=2)
                draw.text((dx + 8, dy - 8), str(idx), fill="yellow", font=font)

            if len(self.calibration_points) >= 2:
                p1 = self.calibration_points[0]
                p2 = self.calibration_points[1]
                draw.line(
                    (
                        p1[0] * self.display_scale,
                        p1[1] * self.display_scale,
                        p2[0] * self.display_scale,
                        p2[1] * self.display_scale,
                    ),
                    fill="cyan",
                    width=2,
                )
            if len(self.calibration_points) >= 3:
                p1 = self.calibration_points[0]
                p3 = self.calibration_points[2]
                draw.line(
                    (
                        p1[0] * self.display_scale,
                        p1[1] * self.display_scale,
                        p3[0] * self.display_scale,
                        p3[1] * self.display_scale,
                    ),
                    fill="magenta",
                    width=2,
                )

        if self.is_collecting_calibration:
            needed = self._expected_point_count()
            if show_calibration_points:
                remaining = max(0, needed - len(self.calibration_points))
                info = f"Kalibrierung aktiv: noch {remaining} Punkt(e) setzen"
            else:
                info = f"Kalibrierung gehoert zu Frame {self.calibration_frame_index + 1}"
            box = (10, 10, min(image.size[0] - 10, 320), 36)
            draw.rectangle(box, fill=(20, 20, 20, 220))
            draw.text((16, 18), info, fill="white", font=font)

    def _draw_scale_bar(self, draw: ImageDraw.ImageDraw, image_size, font) -> None:
        width, height = image_size
        margin = 24
        bottom = height - 24
        x0 = margin

        scale_x = self.scale_x_m_per_px
        if scale_x is None or scale_x <= 0:
            return

        target_px = 160 / max(self.display_scale, 1e-9)
        target_real_m = target_px * scale_x
        candidates_m = [0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0]
        chosen_real_m = candidates_m[0]
        for cand in candidates_m:
            if cand <= target_real_m:
                chosen_real_m = cand
            else:
                break

        bar_px_video = chosen_real_m / scale_x
        bar_px = max(30, int(bar_px_video * self.display_scale))
        x1 = min(width - margin, x0 + bar_px)
        if x1 - x0 < 20:
            return

        draw.rectangle((x0 - 10, bottom - 28, x1 + 12, bottom + 12), fill=(20, 20, 20, 220))
        draw.line((x0, bottom, x1, bottom), fill="white", width=4)
        draw.line((x0, bottom - 7, x0, bottom + 7), fill="white", width=2)
        draw.line((x1, bottom - 7, x1, bottom + 7), fill="white", width=2)
        draw.text(
            (x0, bottom - 23),
            self._format_real_length(chosen_real_m, self.calibration_display_unit),
            fill="white",
            font=font,
        )

    def _draw_overlay(self) -> None:
        if self.display_width <= 0 or self.display_height <= 0:
            return

        overlay_image = self._render_overlay_display(self.display_width, self.display_height)
        if overlay_image is None:
            return

        self.overlay_tk_image = ImageTk.PhotoImage(overlay_image)
        self.video_canvas.create_image(
            self.display_offset_x,
            self.display_offset_y,
            anchor="nw",
            image=self.overlay_tk_image,
        )

    def _render_overlay_display(self, display_w: int, display_h: int):
        if not self.overlay_strokes and not self.current_stroke:
            return None

        ss = self.DISPLAY_OVERLAY_SUPERSAMPLE
        img = Image.new("RGBA", (display_w * ss, display_h * ss), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        ox = self._get_overlay_offset_x()
        oy = self._get_overlay_offset_y()

        for stroke in [*self.overlay_strokes, *([self.current_stroke] if self.current_stroke else [])]:
            if not stroke or not stroke.get("points"):
                continue
            points = []
            for wx, wy in stroke["points"]:
                vx = wx + ox
                vy = wy + oy
                dx = vx * self.display_scale * ss
                dy = vy * self.display_scale * ss
                points.append((dx, dy))

            width = max(1, int(stroke["width"] * self.display_scale * ss))
            color = self._hex_to_rgba(stroke["color"], 255)
            if len(points) == 1:
                self._draw_circle(draw, points[0], width / 2.0, color)
            else:
                draw.line(points, fill=color, width=width, joint="curve")
                self._draw_circle(draw, points[0], width / 2.0, color)
                self._draw_circle(draw, points[-1], width / 2.0, color)

        if ss > 1:
            img = img.resize((display_w, display_h), Image.Resampling.LANCZOS)
        return img

    def _draw_circle(self, draw: ImageDraw.ImageDraw, center, radius: float, color) -> None:
        cx, cy = center
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=color)

    def _hex_to_rgba(self, color_hex: str, alpha: int):
        color_hex = color_hex.lstrip("#")
        if len(color_hex) != 6:
            return 255, 0, 0, alpha
        return (
            int(color_hex[0:2], 16),
            int(color_hex[2:4], 16),
            int(color_hex[4:6], 16),
            alpha,
        )

    def _seek_to_frame(self, frame_index: int) -> None:
        if self.cap is None:
            return

        if self.total_frames > 0:
            frame_index = max(0, min(frame_index, self.total_frames - 1))
        else:
            frame_index = max(0, frame_index)

        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        frame = self._read_frame_at_current_position()
        if frame is None:
            self.status_var.set("Ziel-Frame konnte nicht gelesen werden.")
            return

        self._display_frame(frame)
        self.status_var.set(f"Frame {self.current_frame_index + 1} angezeigt.")

    def _refresh_current_view(self) -> None:
        if self.current_frame_bgr is not None:
            self._display_frame(self.current_frame_bgr)

    # ------------------------------------------------------------------
    # Wiedergabe
    # ------------------------------------------------------------------
    def play_normal(self) -> None:
        if self.cap is None:
            messagebox.showinfo("Hinweis", "Bitte zuerst ein Video laden.")
            return
        self.play_speed = 1.0
        self._start_playback(mode_text="Normale Wiedergabe")

    def play_slow(self) -> None:
        if self.cap is None:
            messagebox.showinfo("Hinweis", "Bitte zuerst ein Video laden.")
            return
        self.play_speed = self._get_slow_speed()
        self._start_playback(mode_text=f"Langsame Wiedergabe ({self.play_speed:.2f}x)")

    def _start_playback(self, mode_text: str) -> None:
        self.pause_video(cancel_only=True)
        self.is_playing = True
        self.status_var.set(mode_text)
        self._play_next_frame()

    def _play_next_frame(self) -> None:
        if not self.is_playing or self.cap is None:
            return

        frame = self._read_frame_at_current_position()
        if frame is None:
            self.pause_video(cancel_only=True)
            self.status_var.set("Videoende erreicht.")
            return

        self._display_frame(frame)
        effective_fps = max(self.fps * self.play_speed, 0.001)
        delay_ms = max(1, int(1000.0 / effective_fps))
        self.after_job = self.root.after(delay_ms, self._play_next_frame)

    def pause_video(self, cancel_only: bool = False) -> None:
        self.is_playing = False
        if self.after_job is not None:
            self.root.after_cancel(self.after_job)
            self.after_job = None
        if not cancel_only:
            self.status_var.set("Pausiert")

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------
    def step_forward(self) -> None:
        if self.cap is None:
            return
        self.pause_video(cancel_only=True)
        jump = self._get_jump_frames()
        self._seek_to_frame(self.current_frame_index + jump)
        self.status_var.set(f"{jump} Frames vorwärts gesprungen.")

    def step_backward(self) -> None:
        if self.cap is None:
            return
        self.pause_video(cancel_only=True)
        jump = self._get_jump_frames()
        self._seek_to_frame(self.current_frame_index - jump)
        self.status_var.set(f"{jump} Frames rückwärts gesprungen.")

    def go_to_start(self) -> None:
        if self.cap is None:
            return
        self.pause_video(cancel_only=True)
        self._seek_to_frame(0)
        self.status_var.set("Zum Anfang gesprungen.")

    def _toggle_play_pause(self, _event=None) -> None:
        if self.is_playing:
            self.pause_video()
        else:
            self.play_normal()

    # ------------------------------------------------------------------
    # Kalibrierung
    # ------------------------------------------------------------------
    def start_calibration_collection(self) -> None:
        if self.cap is None or self.current_frame_bgr is None:
            messagebox.showinfo("Hinweis", "Bitte zuerst ein Video laden und ein Frame anzeigen.")
            return

        self.pause_video(cancel_only=True)
        self.calibration_points = []
        self.is_collecting_calibration = True
        self.calibration_frame_index = self.current_frame_index
        required = self._expected_point_count()
        self.point_info_var.set(f"Punkte: 0 / {required}")
        self.calibration_info_var.set(
            f"Kalibrierung aktiv auf Frame {self.current_frame_index + 1}."
        )
        self.status_var.set("Kalibrierpunkte im Bild anklicken.")
        self._invalidate_base_frame_cache()
        self._refresh_current_view()

    def apply_calibration(self) -> None:
        required = self._expected_point_count()
        if len(self.calibration_points) != required:
            messagebox.showwarning(
                "Hinweis",
                f"Es werden {required} Punkte benötigt. Aktuell vorhanden: {len(self.calibration_points)}.",
            )
            return

        try:
            ref_x = self._parse_positive_float(self.reference_x_var.get(), "Horizontales Realmaß")
            ref_x_m = ref_x * self._unit_to_meter_factor()
        except ValueError as exc:
            messagebox.showerror("Fehler", str(exc))
            return

        p1 = self.calibration_points[0]
        p2 = self.calibration_points[1]
        px_dist_x = math.dist(p1, p2)
        if px_dist_x <= 0:
            messagebox.showerror("Fehler", "Die ersten beiden Punkte ergeben keine gültige Distanz.")
            return

        self.scale_x_m_per_px = ref_x_m / px_dist_x
        self.scale_y_m_per_px = self.scale_x_m_per_px

        if self.calibration_mode_var.get() != "horizontal":
            try:
                ref_y = self._parse_positive_float(self.reference_y_var.get(), "Vertikales Realmaß")
                ref_y_m = ref_y * self._unit_to_meter_factor()
            except ValueError as exc:
                messagebox.showerror("Fehler", str(exc))
                return

            p3 = self.calibration_points[2]
            px_dist_y = math.dist(p1, p3)
            if px_dist_y <= 0:
                messagebox.showerror("Fehler", "Punkt 1 und 3 ergeben keine gültige Höhe.")
                return
            self.scale_y_m_per_px = ref_y_m / px_dist_y

        self.calibration_display_unit = self.reference_unit_var.get()
        self._update_scale_info()
        self.status_var.set("Kalibrierung berechnet.")
        self._invalidate_base_frame_cache()
        self._refresh_current_view()

    def _update_scale_info(self) -> None:
        if self.scale_x_m_per_px is None:
            self.scale_info_var.set("Maßstab: noch nicht berechnet")
            return

        px_per_m_x = 1.0 / self.scale_x_m_per_px if self.scale_x_m_per_px > 0 else 0.0
        if self.scale_y_m_per_px is None:
            self.scale_y_m_per_px = self.scale_x_m_per_px
        px_per_m_y = 1.0 / self.scale_y_m_per_px if self.scale_y_m_per_px > 0 else 0.0

        if self.calibration_mode_var.get() == "horizontal":
            self.calibration_info_var.set(
                f"Kalibrierung auf Frame {self.calibration_frame_index + 1}: isotroper Maßstab aus 2 Punkten."
            )
            self.scale_info_var.set(
                f"Maßstab: 1 px = {self._format_real_length(self.scale_x_m_per_px, self.calibration_display_unit)} | 1 m = {px_per_m_x:.2f} px"
            )
        else:
            self.calibration_info_var.set(
                f"Kalibrierung auf Frame {self.calibration_frame_index + 1}: separater x/y-Maßstab aus 3 Punkten."
            )
            self.scale_info_var.set(
                f"Maßstab x: 1 px = {self._format_real_length(self.scale_x_m_per_px, self.calibration_display_unit)} | 1 m = {px_per_m_x:.2f} px   ||   "
                f"Maßstab y: 1 px = {self._format_real_length(self.scale_y_m_per_px, self.calibration_display_unit)} | 1 m = {px_per_m_y:.2f} px"
            )

    def _format_real_length(self, length_m: float, unit=None) -> str:
        unit = unit or self.reference_unit_var.get()
        if unit == "cm":
            return f"{length_m * 100:.2f} cm"
        return f"{length_m:.3f} m"

    def clear_calibration(self, reset_status: bool = True) -> None:
        self.calibration_points = []
        self.is_collecting_calibration = False
        self.calibration_frame_index = None
        self.scale_x_m_per_px = None
        self.scale_y_m_per_px = None
        self.calibration_display_unit = None
        self.calibration_info_var.set("Kalibrierung: noch nicht gesetzt")
        self.scale_info_var.set("Maßstab: noch nicht berechnet")
        self.point_info_var.set(f"Punkte: 0 / {self._expected_point_count()}")
        if reset_status:
            self.status_var.set("Kalibrierung gelöscht.")
        self._invalidate_base_frame_cache()
        self._refresh_current_view()

    # ------------------------------------------------------------------
    # Overlay / Zeichnen
    # ------------------------------------------------------------------
    def _on_canvas_left_down(self, event) -> None:
        coords = self._canvas_to_video_coords(event.x, event.y)
        if coords is None:
            return

        if self.is_collecting_calibration:
            self._add_calibration_point(coords)
            return

        if self.overlay_draw_mode_var.get():
            self.pause_video(cancel_only=True)
            vx, vy = coords
            ox = self._get_overlay_offset_x()
            oy = self._get_overlay_offset_y()
            world_point = (vx - ox, vy - oy)
            self.current_stroke = {
                "color": self.current_overlay_color,
                "width": self._get_overlay_brush_size(),
                "points": [world_point],
            }
            self.status_var.set("Overlay-Zeichnung gestartet.")
            self._redraw_current_frame()

    def _on_canvas_drag(self, event) -> None:
        if not self.overlay_draw_mode_var.get() or self.current_stroke is None:
            return
        coords = self._canvas_to_video_coords(event.x, event.y)
        if coords is None:
            return

        vx, vy = coords
        ox = self._get_overlay_offset_x()
        oy = self._get_overlay_offset_y()
        world_point = (vx - ox, vy - oy)
        points = self.current_stroke["points"]
        if not points or math.dist(points[-1], world_point) >= 0.5:
            points.append(world_point)
            self._redraw_current_frame()

    def _on_canvas_left_up(self, _event) -> None:
        if self.current_stroke is not None:
            self.overlay_strokes.append(self.current_stroke)
            self.current_stroke = None
            self._update_overlay_info()
            self.status_var.set("Overlay-Zeichnung abgeschlossen.")
            self._redraw_current_frame()

    def _add_calibration_point(self, coords) -> None:
        ox, oy = coords
        self.calibration_points.append((ox, oy))
        required = self._expected_point_count()
        self.point_info_var.set(f"Punkte: {len(self.calibration_points)} / {required}")
        self._invalidate_base_frame_cache()
        self._refresh_current_view()

        if len(self.calibration_points) >= required:
            self.is_collecting_calibration = False
            self.status_var.set("Punkte gesetzt. Nun Kalibrierung anwenden.")
            self.calibration_info_var.set(
                f"{required} Referenzpunkte auf Frame {self.calibration_frame_index + 1} gesetzt."
            )

    def clear_overlay(self) -> None:
        self._clear_overlay_state()

    def _overlay_content_bounds(self):
        all_strokes = [stroke for stroke in self.overlay_strokes if stroke.get("points")]
        if not all_strokes:
            return None

        min_x = float("inf")
        min_y = float("inf")
        max_x = float("-inf")
        max_y = float("-inf")

        for stroke in all_strokes:
            half_w = stroke["width"] / 2.0
            for px, py in stroke["points"]:
                min_x = min(min_x, px - half_w)
                min_y = min(min_y, py - half_w)
                max_x = max(max_x, px + half_w)
                max_y = max(max_y, py + half_w)

        if not math.isfinite(min_x):
            return None
        return min_x, min_y, max_x, max_y

    def save_overlay_png(self) -> None:
        bounds = self._overlay_content_bounds()
        if bounds is None:
            messagebox.showinfo("Hinweis", "Es gibt noch keine Overlay-Zeichnung zum Speichern.")
            return

        file_path = filedialog.asksaveasfilename(
            title="Overlay als PNG speichern",
            defaultextension=".png",
            filetypes=[("PNG-Bild", "*.png")],
        )
        if not file_path:
            return

        min_x, min_y, max_x, max_y = bounds
        padding = 8.0
        min_x -= padding
        min_y -= padding
        max_x += padding
        max_y += padding

        scale = self.EXPORT_OVERLAY_SCALE
        export_w = max(1, int(math.ceil((max_x - min_x) * scale)))
        export_h = max(1, int(math.ceil((max_y - min_y) * scale)))

        export_img = Image.new("RGBA", (export_w, export_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(export_img)

        for stroke in self.overlay_strokes:
            if not stroke.get("points"):
                continue
            points = [((x - min_x) * scale, (y - min_y) * scale) for x, y in stroke["points"]]
            width = max(1, int(stroke["width"] * scale))
            color = self._hex_to_rgba(stroke["color"], 255)
            if len(points) == 1:
                self._draw_circle(draw, points[0], width / 2.0, color)
            else:
                draw.line(points, fill=color, width=width, joint="curve")
                self._draw_circle(draw, points[0], width / 2.0, color)
                self._draw_circle(draw, points[-1], width / 2.0, color)

        export_img.save(file_path, "PNG")
        self.status_var.set(
            f"Overlay gespeichert: {os.path.basename(file_path)} ({export_w}×{export_h}px, zugeschnitten)"
        )

    # ------------------------------------------------------------------
    # Aufräumen
    # ------------------------------------------------------------------
    def on_close(self) -> None:
        self._release_video()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    try:
        style = ttk.Style()
        if "vista" in style.theme_names():
            style.theme_use("vista")
        elif "clam" in style.theme_names():
            style.theme_use("clam")
    except Exception:
        pass

    app = SimpleVideoPlayer(root)
    root.mainloop()

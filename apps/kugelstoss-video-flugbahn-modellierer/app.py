from __future__ import annotations

from dataclasses import asdict
from io import BytesIO
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from PIL import Image, ImageColor, ImageDraw, ImageFont
import streamlit as st

APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from trajectory import TrajectoryParameters, simulate, sweep
from video_analysis import (
    Calibration,
    build_analysis_proxy,
    estimate_slow_factor,
    fit_release_parameters,
    pixel_to_world,
    read_frame,
    read_video_info,
    save_uploaded_video,
    world_to_pixel,
)

try:
    from streamlit_image_coordinates import streamlit_image_coordinates

    CLICK_COMPONENT_AVAILABLE = True
except ImportError:
    CLICK_COMPONENT_AVAILABLE = False


st.set_page_config(page_title="Kugelstoß: Video & Flugbahn", page_icon="🎯", layout="wide")

def _seminarvideo() -> Path:
    """Sucht das Seminarvideo an beiden Orten, an denen es liegen kann.

    Im veroeffentlichten Repositorium liegt es unter material/videos, im
    Seminarordner unter 08_Videos. Existiert keines von beiden, wird der erste
    Kandidat zurueckgegeben — die Oberflaeche blendet die Auswahl dann aus.
    """
    name = "Kugelstoß.mp4"
    kandidaten = (
        APP_DIR.parent.parent / "material" / "videos" / name,
        APP_DIR.parent.parent / "08_Videos" / name,
    )
    for kandidat in kandidaten:
        if kandidat.exists():
            return kandidat
    return kandidaten[0]


DEFAULT_VIDEO = _seminarvideo()
COLORS = ["#00a6d6", "#d32f2f", "#2e7d32", "#ef6c00", "#6a1b9a", "#00838f"]
APP_STATE_VERSION = 4


@st.cache_data(show_spinner=False)
def cached_video_info(path: str):
    return read_video_info(path)


@st.cache_data(show_spinner=False, max_entries=160)
def cached_frame(path: str, frame_index: int) -> Image.Image:
    return read_frame(path, frame_index, max_width=1100)


def initialize_state() -> None:
    defaults = {
        "active_video_signature": "",
        "analysis_path": "",
        "inspect_frame": 0,
        "original_start_frame": 0,
        "original_release_frame": 1,
        "slow_start_frame": 2,
        "slow_release_frame": 3,
        "timebase_mode": "Ein einzelner Videoabschnitt",
        "single_speed_mode": "Normalgeschwindigkeit",
        "slow_factor": 4.0,
        "analysis_speed_mode": "Zeitlupe",
        "calibration_frame": 0,
        "calibration_mode": "Affine Kalibrierung (3 Punkte)",
        "calibration_marker": "Ursprung O",
        "z_reference_alignment": "X-Referenz",
        "calibration_points": {},
        "x_distance_m": 2.135,
        "z_distance_m": 1.80,
        "track_frame": 0,
        "release_frame": 0,
        "track_points": {},
        "click_epoch": 0,
        "last_click_signature": None,
        "sim_v0": 10.0,
        "sim_angle": 37.0,
        "sim_height": 1.80,
        "sim_x0": 0.0,
        "sim_g": 9.81,
        "sim_initialized_from_fit": False,
        "applied_fit_signature": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    if st.session_state.get("app_state_version") != APP_STATE_VERSION:
        st.session_state.app_state_version = APP_STATE_VERSION
        st.session_state.applied_fit_signature = None
        st.session_state.sim_initialized_from_fit = False


def activate_video(path: Path, frame_count: int) -> None:
    signature = f"{path.resolve()}:{path.stat().st_size}:{path.stat().st_mtime_ns}"
    if st.session_state.active_video_signature == signature:
        return
    last = max(0, frame_count - 1)
    is_combined_seminar_video = DEFAULT_VIDEO.exists() and path.resolve() == DEFAULT_VIDEO.resolve()
    initial_release_frame = round(frame_count * (0.75 if is_combined_seminar_video else 0.25))
    st.session_state.active_video_signature = signature
    st.session_state.analysis_path = str(path.resolve())
    st.session_state.timebase_mode = (
        "Original und Zeitlupe in einer Datei"
        if is_combined_seminar_video
        else "Ein einzelner Videoabschnitt"
    )
    st.session_state.single_speed_mode = "Normalgeschwindigkeit"
    st.session_state.analysis_speed_mode = "Zeitlupe" if is_combined_seminar_video else "Originalgeschwindigkeit"
    st.session_state.inspect_frame = 0
    st.session_state.original_start_frame = 0
    st.session_state.original_release_frame = min(last, max(1, round(frame_count * 0.10)))
    st.session_state.slow_start_frame = min(last, round(frame_count * 0.20))
    st.session_state.slow_release_frame = min(last, round(frame_count * 0.75))
    st.session_state.calibration_frame = min(last, initial_release_frame)
    st.session_state.track_frame = min(last, initial_release_frame)
    st.session_state.release_frame = min(last, initial_release_frame)
    st.session_state.calibration_points = {}
    st.session_state.track_points = {}
    st.session_state.click_epoch += 1
    st.session_state.last_click_signature = None
    st.session_state.sim_initialized_from_fit = False
    st.session_state.applied_fit_signature = None


def current_slow_factor() -> float:
    if st.session_state.timebase_mode == "Ein einzelner Videoabschnitt":
        if st.session_state.single_speed_mode == "Normalgeschwindigkeit":
            return 1.0
        return max(0.01, float(st.session_state.slow_factor))
    if st.session_state.analysis_speed_mode == "Originalgeschwindigkeit":
        return 1.0
    return max(0.01, float(st.session_state.slow_factor))


def get_calibration() -> Calibration | None:
    points = st.session_state.calibration_points
    if "origin" not in points or "x_ref" not in points:
        return None
    affine = st.session_state.calibration_mode.startswith("Affine")
    if affine and "z_ref" not in points:
        return None
    z_reference_x_m = (
        float(st.session_state.x_distance_m)
        if affine and st.session_state.z_reference_alignment == "X-Referenz"
        else 0.0
    )
    return Calibration(
        origin_px=tuple(points["origin"]),
        x_reference_px=tuple(points["x_ref"]),
        x_distance_m=float(st.session_state.x_distance_m),
        z_reference_px=tuple(points["z_ref"]) if affine else None,
        z_distance_m=float(st.session_state.z_distance_m) if affine else None,
        z_reference_x_m=z_reference_x_m,
    )


def _font(size: int = 22):
    for name in ("arial.ttf", "calibri.ttf", "segoeui.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def annotated_frame(image: Image.Image, frame_index: int, show_track: bool = True) -> Image.Image:
    output = image.copy()
    draw = ImageDraw.Draw(output)
    font = _font()
    points = st.session_state.calibration_points
    calibration_style = {
        "origin": ("O", "#fdd835"),
        "x_ref": ("X", "#00e676"),
        "z_ref": ("Z", "#ff4081"),
    }
    for key, (label, color) in calibration_style.items():
        if key not in points:
            continue
        x, y = points[key]
        draw.ellipse((x - 9, y - 9, x + 9, y + 9), fill=color, outline="black", width=2)
        draw.text((x + 12, y - 14), label, fill=color, stroke_width=2, stroke_fill="black", font=font)
    if "origin" in points and "x_ref" in points:
        draw.line((points["origin"], points["x_ref"]), fill="#00e676", width=4)
    if "origin" in points and "z_ref" in points:
        z_base_key = (
            "x_ref"
            if st.session_state.z_reference_alignment == "X-Referenz" and "x_ref" in points
            else "origin"
        )
        draw.line((points[z_base_key], points["z_ref"]), fill="#ff4081", width=4)

    if show_track and frame_index in st.session_state.track_points:
        x, y = st.session_state.track_points[frame_index]
        draw.ellipse((x - 10, y - 10, x + 10, y + 10), outline="#00b0ff", width=5)
        draw.line((x - 16, y, x + 16, y), fill="#00b0ff", width=3)
        draw.line((x, y - 16, x, y + 16), fill="#00b0ff", width=3)
        draw.text((x + 14, y + 8), f"Kugel {frame_index}", fill="#00b0ff", stroke_width=2, stroke_fill="black", font=font)
    return output


def clickable_image(image: Image.Image, key: str) -> dict[str, int] | None:
    if CLICK_COMPONENT_AVAILABLE:
        value = streamlit_image_coordinates(image, width=image.width, key=key)
        if value and "x" in value and "y" in value:
            return {"x": int(value["x"]), "y": int(value["y"])}
        return None

    st.image(image, width="stretch")
    st.warning(
        "Das Klick-Modul ist noch nicht installiert. Das Startskript installiert es automatisch; "
        "alternativ können die Pixelkoordinaten hier eingetragen werden."
    )
    x_col, y_col, button_col = st.columns([1, 1, 1])
    x_value = x_col.number_input("x [Pixel]", min_value=0, max_value=image.width - 1, value=image.width // 2, key=f"{key}_x")
    y_value = y_col.number_input("y [Pixel]", min_value=0, max_value=image.height - 1, value=image.height // 2, key=f"{key}_y")
    if button_col.button("Koordinate übernehmen", key=f"{key}_manual"):
        return {"x": int(x_value), "y": int(y_value)}
    return None


def register_click(signature: tuple, handler) -> None:
    if st.session_state.last_click_signature == signature:
        return
    st.session_state.last_click_signature = signature
    handler()
    st.session_state.sim_initialized_from_fit = False
    st.session_state.applied_fit_signature = None
    st.session_state.click_epoch += 1
    st.rerun()


def set_inspection_marker(name: str) -> None:
    st.session_state[name] = int(st.session_state.inspect_frame)


def draw_video_trajectory_composite(
    image: Image.Image,
    results,
    calibration: Calibration,
    measured: pd.DataFrame,
    release_point: tuple[float, float],
) -> Image.Image:
    """Keep the release frame undistorted and extend its pixel plane for trajectories."""
    projected_results: list[list[tuple[float, float]]] = []
    all_points: list[tuple[float, float]] = [
        (0.0, 0.0),
        (float(image.width), 0.0),
        (0.0, float(image.height)),
        (float(image.width), float(image.height)),
    ]
    for result in results:
        line_points = [
            world_to_pixel((float(x_m), float(z_m)), calibration)
            for x_m, z_m in zip(result.data["x_m"], result.data["z_m"])
        ]
        line_points = [
            (x_px, y_px)
            for x_px, y_px in line_points
            if np.isfinite(x_px) and np.isfinite(y_px) and abs(x_px) < 1_000_000 and abs(y_px) < 1_000_000
        ]
        projected_results.append(line_points)
        all_points.extend(line_points)

    measured_points = [(float(row.x_px), float(row.y_px)) for row in measured.itertuples(index=False)]
    all_points.extend(measured_points)
    release_pixel = world_to_pixel(release_point, calibration)
    all_points.append(release_pixel)

    padding = 36.0
    min_x = min(point[0] for point in all_points) - padding
    max_x = max(point[0] for point in all_points) + padding
    min_y = min(point[1] for point in all_points) - padding
    max_y = max(point[1] for point in all_points) + padding
    natural_width = max(1.0, max_x - min_x)
    natural_height = max(1.0, max_y - min_y)
    scale = min(1.0, 2400.0 / natural_width, 1400.0 / natural_height)
    canvas_width = max(1, round(natural_width * scale))
    canvas_height = max(1, round(natural_height * scale))
    offset_x = -min_x
    offset_y = -min_y

    canvas = Image.new("RGB", (canvas_width, canvas_height), "white")
    resized_image = image.convert("RGB").resize(
        (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
        Image.Resampling.LANCZOS,
    )
    canvas.paste(resized_image, (round(offset_x * scale), round(offset_y * scale)))
    draw = ImageDraw.Draw(canvas)

    def canvas_point(point: tuple[float, float]) -> tuple[float, float]:
        return ((point[0] + offset_x) * scale, (point[1] + offset_y) * scale)

    for index, line_points in enumerate(projected_results):
        if len(line_points) < 2:
            continue
        points = [canvas_point(point) for point in line_points]
        line_width = max(2, round((6 if index == 0 else 4) * scale))
        outline_width = max(line_width + 2, round((10 if index == 0 else 7) * scale))
        draw.line(points, fill="white", width=outline_width, joint="curve")
        draw.line(points, fill=COLORS[index % len(COLORS)], width=line_width, joint="curve")

    marker_radius = max(4, round(8 * scale))
    for point in measured_points:
        x_px, y_px = canvas_point(point)
        draw.ellipse(
            (x_px - marker_radius, y_px - marker_radius, x_px + marker_radius, y_px + marker_radius),
            fill="white",
            outline="black",
            width=max(2, round(3 * scale)),
        )

    release_x_px, release_y_px = canvas_point(release_pixel)
    release_radius = max(7, round(13 * scale))
    draw.ellipse(
        (
            release_x_px - release_radius,
            release_y_px - release_radius,
            release_x_px + release_radius,
            release_y_px + release_radius,
        ),
        fill=ImageColor.getrgb("#ffeb3b"),
        outline="black",
        width=max(2, round(3 * scale)),
    )
    cross_radius = max(9, round(17 * scale))
    draw.line(
        (release_x_px - cross_radius, release_y_px, release_x_px + cross_radius, release_y_px),
        fill="black",
        width=max(2, round(3 * scale)),
    )
    draw.line(
        (release_x_px, release_y_px - cross_radius, release_x_px, release_y_px + cross_radius),
        fill="black",
        width=max(2, round(3 * scale)),
    )
    return canvas


initialize_state()

st.title("Kugelstoß: Videoanalyse und Flugbahn-Modellierer")
st.caption(
    "Abwurfparameter aus markierten Videobildern bestimmen und anschließend Geschwindigkeit, "
    "Winkel und Abwurfhöhe systematisch variieren."
)

with st.sidebar:
    st.header("Video")
    sources = ["Video hochladen"]
    if DEFAULT_VIDEO.exists():
        sources.insert(0, "Seminarvideo Kugelstoß.mp4")
    selected_source = st.radio("Quelle", sources)
    video_path: Path | None = None
    if selected_source.startswith("Seminarvideo"):
        video_path = DEFAULT_VIDEO
    else:
        uploaded = st.file_uploader("Videodatei", type=["mp4", "mov", "m4v", "avi"])
        if uploaded is not None:
            video_path = save_uploaded_video(uploaded.getvalue(), uploaded.name)

    if video_path is None:
        st.info("Bitte zuerst ein Video auswählen.")
        st.stop()

    info = cached_video_info(str(video_path))
    activate_video(video_path, info.frame_count)
    if Path(st.session_state.analysis_path).resolve() == video_path.resolve():
        with st.spinner("Bildgenaues Analysevideo wird vorbereitet …"):
            st.session_state.analysis_path = str(build_analysis_proxy(video_path))
    st.write(f"**{info.width} × {info.height} px**")
    st.write(f"**{info.fps:.3g} Bilder/s · {info.duration_s:.2f} s**")
    st.write(f"**{info.frame_count} Bilder**")

    if st.button("Analysevideo prüfen/neu zuordnen", help="Verwendet eine kleinere, bildgenau durchsuchbare Arbeitskopie."):
        with st.spinner("Analysevideo wird erzeugt …"):
            proxy = build_analysis_proxy(video_path)
        st.session_state.analysis_path = str(proxy)
        cached_frame.clear()
        st.success("Analysevideo ist vorbereitet.")

    st.divider()
    st.header("Arbeitsschritt")
    step = st.radio(
        "Navigation",
        (
            "1 · Zeitbasis festlegen",
            "2 · Bild kalibrieren",
            "3 · Kugel markieren",
            "4 · Ergebnis & Simulation",
            "5 · Anleitung",
        ),
        label_visibility="collapsed",
    )

analysis_path = st.session_state.analysis_path or str(video_path)

if step.startswith("1"):
    st.header("1 · Zeitbasis des Videos festlegen")
    st.radio(
        "Welche Art von Video wird analysiert?",
        ("Ein einzelner Videoabschnitt", "Original und Zeitlupe in einer Datei"),
        key="timebase_mode",
        horizontal=True,
    )
    st.slider("Vorschaubild", 0, info.frame_count - 1, key="inspect_frame")
    preview = cached_frame(analysis_path, int(st.session_state.inspect_frame))
    st.image(preview, caption=f"Bild {st.session_state.inspect_frame} · {st.session_state.inspect_frame / info.fps:.3f} s Videozeit", width="stretch")

    if st.session_state.timebase_mode == "Ein einzelner Videoabschnitt":
        st.write(
            "Für ein gewöhnliches Video ist keine Zuordnung zweier Abschnitte nötig. "
            "Wählen Sie Normalgeschwindigkeit oder tragen Sie bei einer bereits verlangsamt "
            "gespeicherten Aufnahme den bekannten Zeitlupenfaktor ein."
        )
        st.radio(
            "Geschwindigkeit des Videoabschnitts",
            ("Normalgeschwindigkeit", "Zeitlupe mit bekanntem Faktor"),
            key="single_speed_mode",
            horizontal=True,
        )
        if st.session_state.single_speed_mode == "Zeitlupe mit bekanntem Faktor":
            st.number_input(
                "Zeitlupenfaktor",
                min_value=0.1,
                max_value=100.0,
                step=0.1,
                key="slow_factor",
                help="Beispiel: Eine vierfach verlangsamte Datei erhält den Faktor 4.",
            )
    else:
        st.write(
            "Wählen Sie nacheinander dieselben beiden Ereignisse im Original- und Zeitlupenteil, "
            "zum Beispiel Beginn der Ausstoßbewegung und Loslassen der Kugel. Aus dem Verhältnis "
            "der Bildabstände ergibt sich der Zeitlupenfaktor."
        )
        marker_cols = st.columns(4)
        marker_specs = [
            ("Original: Ereignis 1", "original_start_frame"),
            ("Original: Ereignis 2", "original_release_frame"),
            ("Zeitlupe: Ereignis 1", "slow_start_frame"),
            ("Zeitlupe: Ereignis 2 / Release", "slow_release_frame"),
        ]
        for column, (label, state_key) in zip(marker_cols, marker_specs):
            column.button(label, key=f"set_{state_key}", on_click=set_inspection_marker, args=(state_key,), width="stretch")
            column.caption(f"Bild {st.session_state[state_key]}")

        calculated_factor: float | None = None
        try:
            calculated_factor = estimate_slow_factor(
                st.session_state.original_start_frame,
                st.session_state.original_release_frame,
                st.session_state.slow_start_frame,
                st.session_state.slow_release_frame,
            )
            st.success(f"Berechneter Zeitlupenfaktor: **{calculated_factor:.3f}×**")
        except ValueError as error:
            st.warning(str(error))

        if calculated_factor is not None:
            st.button(
                "Berechneten Faktor verwenden",
                on_click=lambda value=calculated_factor: st.session_state.update(slow_factor=float(value)),
            )
        st.number_input("Zeitlupenfaktor", min_value=0.1, max_value=100.0, step=0.1, key="slow_factor")
        st.radio(
            "Welcher Abschnitt wird für die Kugelmarken verwendet?",
            ("Zeitlupe", "Originalgeschwindigkeit"),
            key="analysis_speed_mode",
            horizontal=True,
        )

    st.info(
        f"Wirksame Zeitbasis: reale Zeit zwischen zwei Videobildern = "
        f"{1000.0 / (info.fps * current_slow_factor()):.3f} ms."
    )

elif step.startswith("2"):
    st.header("2 · Koordinatensystem kalibrieren")
    st.write(
        "Setzen Sie O auf den gewünschten Boden-Ursprung. Die X-Referenz erhält eine bekannte, "
        "vorzeichenbehaftete Koordinate: in Stoßrichtung positiv, dahinter negativ. Z kann über O "
        "oder über der X-Referenz liegen. Für X kann beispielsweise der 2,135-m-Stoßring dienen."
    )
    st.slider("Kalibrierbild", 0, info.frame_count - 1, key="calibration_frame")
    option_cols = st.columns([1.3, 1.2, 1, 1.1])
    option_cols[0].selectbox(
        "Verfahren",
        ("Affine Kalibrierung (3 Punkte)", "Vereinfachte Kalibrierung (2 Punkte)"),
        key="calibration_mode",
    )
    option_cols[1].number_input(
        "X-Koordinate der Referenz [m]",
        min_value=-20.0,
        max_value=20.0,
        step=0.01,
        key="x_distance_m",
        help="In Stoßrichtung positiv, hinter dem Ursprung negativ; 0 ist nicht zulässig.",
    )
    if st.session_state.calibration_mode.startswith("Affine"):
        option_cols[2].number_input("Z-Höhe [m]", min_value=0.01, step=0.01, key="z_distance_m")
        option_cols[3].selectbox(
            "Z-Referenz liegt über",
            ("Ursprung O", "X-Referenz"),
            key="z_reference_alignment",
        )
        st.caption(
            "Ring-Varianten: O hinten, X am Balken = +2,135 m und Z über X; "
            "oder O unter dem Balken, X hinten = −2,135 m und Z über O."
        )
    st.selectbox("Nächster Klick setzt", ("Ursprung O", "X-Referenz", "Z-Referenz"), key="calibration_marker")
    st.caption("Ein vorhandener Kalibrierpunkt kann direkt neu gesetzt werden; alle übrigen Punkte und Eingaben bleiben erhalten.")

    frame_index = int(st.session_state.calibration_frame)
    image = annotated_frame(cached_frame(analysis_path, frame_index), frame_index, show_track=False)
    click = clickable_image(
        image,
        key=f"calibration_{frame_index}_{st.session_state.calibration_marker}_{st.session_state.click_epoch}",
    )
    if click:
        marker_key = {"Ursprung O": "origin", "X-Referenz": "x_ref", "Z-Referenz": "z_ref"}[st.session_state.calibration_marker]
        signature = ("calibration", marker_key, frame_index, click["x"], click["y"])
        register_click(
            signature,
            lambda: st.session_state.calibration_points.update({marker_key: (click["x"], click["y"])}),
        )

    action_cols = st.columns(3)
    if action_cols[0].button("Ausgewählten Kalibrierpunkt löschen"):
        marker_key = {"Ursprung O": "origin", "X-Referenz": "x_ref", "Z-Referenz": "z_ref"}[st.session_state.calibration_marker]
        st.session_state.calibration_points.pop(marker_key, None)
        st.session_state.sim_initialized_from_fit = False
        st.session_state.applied_fit_signature = None
        st.session_state.last_click_signature = None
        st.session_state.click_epoch += 1
        st.rerun()
    if action_cols[1].button("Kalibrierung löschen"):
        st.session_state.calibration_points = {}
        st.session_state.sim_initialized_from_fit = False
        st.session_state.applied_fit_signature = None
        st.session_state.last_click_signature = None
        st.session_state.click_epoch += 1
        st.rerun()

    saved_calibration_labels = [
        label
        for key, label in (("origin", "O"), ("x_ref", "X"), ("z_ref", "Z"))
        if key in st.session_state.calibration_points
    ]
    st.caption("Gespeicherte Kalibrierpunkte: " + (", ".join(saved_calibration_labels) or "noch keine"))

    calibration = get_calibration()
    if calibration is None:
        st.warning("Die Kalibrierung ist noch nicht vollständig.")
    else:
        try:
            origin_world = pixel_to_world(calibration.origin_px, calibration)
            x_world = pixel_to_world(calibration.x_reference_px, calibration)
            message = f"Kalibrierung gültig: O={origin_world}, X≈({x_world[0]:.3f} m, {x_world[1]:.3f} m)"
            if calibration.z_reference_px is not None:
                z_world = pixel_to_world(calibration.z_reference_px, calibration)
                message += f", Z≈({z_world[0]:.3f} m, {z_world[1]:.3f} m)"
            st.success(message)
        except ValueError as error:
            st.error(str(error))

elif step.startswith("3"):
    st.header("3 · Kugelpositionen markieren")
    calibration = get_calibration()
    if calibration is None:
        st.error("Bitte zuerst Arbeitsschritt 2 vollständig kalibrieren.")
        st.stop()

    st.write(
        "Setzen Sie das Release-Bild und markieren Sie danach den Kugelmittelpunkt im Release-Bild sowie "
        "in mindestens zwei späteren Bildern. Vier bis acht gut erkennbare Punkte aus der frühen Flugphase sind ideal."
    )
    nav_cols = st.columns([1, 1, 1, 1, 3])
    nav_cols[0].button("−5", on_click=lambda: st.session_state.update(track_frame=max(0, st.session_state.track_frame - 5)))
    nav_cols[1].button("−1", on_click=lambda: st.session_state.update(track_frame=max(0, st.session_state.track_frame - 1)))
    nav_cols[2].button("+1", on_click=lambda: st.session_state.update(track_frame=min(info.frame_count - 1, st.session_state.track_frame + 1)))
    nav_cols[3].button("+5", on_click=lambda: st.session_state.update(track_frame=min(info.frame_count - 1, st.session_state.track_frame + 5)))
    nav_cols[4].button(
        "Aktuelles Bild als Release setzen",
        on_click=lambda: st.session_state.update(
            release_frame=int(st.session_state.track_frame),
            sim_initialized_from_fit=False,
        ),
        width="stretch",
    )
    st.slider("Aktuelles Bild", 0, info.frame_count - 1, key="track_frame")
    st.number_input("Release-Bild", min_value=0, max_value=info.frame_count - 1, step=1, key="release_frame")

    frame_index = int(st.session_state.track_frame)
    delta_real = (frame_index - int(st.session_state.release_frame)) / (info.fps * current_slow_factor())
    st.caption(
        f"Bild {frame_index} · Videozeit {frame_index / info.fps:.3f} s · "
        f"reale Zeit relativ zum Release {delta_real:+.4f} s"
    )
    image = annotated_frame(cached_frame(analysis_path, frame_index), frame_index)
    click = clickable_image(image, key=f"track_{frame_index}_{st.session_state.click_epoch}")
    if click:
        signature = ("track", frame_index, click["x"], click["y"])
        register_click(
            signature,
            lambda: st.session_state.track_points.update({frame_index: (click["x"], click["y"])}),
        )

    control_cols = st.columns(3)
    if control_cols[0].button("Marker dieses Bildes löschen"):
        st.session_state.track_points.pop(frame_index, None)
        st.session_state.sim_initialized_from_fit = False
        st.session_state.applied_fit_signature = None
        st.session_state.last_click_signature = None
        st.session_state.click_epoch += 1
        st.rerun()
    if control_cols[1].button("Letzten Marker löschen") and st.session_state.track_points:
        st.session_state.track_points.pop(sorted(st.session_state.track_points)[-1], None)
        st.session_state.sim_initialized_from_fit = False
        st.session_state.applied_fit_signature = None
        st.session_state.last_click_signature = None
        st.session_state.click_epoch += 1
        st.rerun()
    if control_cols[2].button("Alle Kugelmarker löschen"):
        st.session_state.track_points = {}
        st.session_state.sim_initialized_from_fit = False
        st.session_state.applied_fit_signature = None
        st.session_state.last_click_signature = None
        st.session_state.click_epoch += 1
        st.rerun()

    if st.session_state.track_points:
        if int(st.session_state.release_frame) in st.session_state.track_points:
            st.success(f"Release-Bild {int(st.session_state.release_frame)} besitzt einen Kugelmarker.")
        else:
            first_marker_frame = min(int(frame) for frame in st.session_state.track_points)
            st.warning(
                "Im gewählten Release-Bild ist noch kein Kugelmarker gesetzt. Markieren Sie dort den "
                f"Kugelmittelpunkt; andernfalls verwendet die Auswertung automatisch Bild {first_marker_frame} als Release."
            )
        marker_rows = []
        for marker_frame, (x_px, y_px) in sorted(st.session_state.track_points.items()):
            x_m, z_m = pixel_to_world((x_px, y_px), calibration)
            marker_rows.append(
                {
                    "Bild": marker_frame,
                    "Δt real [s]": (marker_frame - int(st.session_state.release_frame)) / (info.fps * current_slow_factor()),
                    "x [m]": x_m,
                    "z [m]": z_m,
                }
            )
        st.dataframe(pd.DataFrame(marker_rows), hide_index=True, width="stretch")

elif step.startswith("4"):
    st.header("4 · Abwurfparameter und Simulation")
    calibration = get_calibration()
    if calibration is None:
        st.error("Die Kalibrierung fehlt.")
        st.stop()

    marker_frames = sorted(int(frame) for frame in st.session_state.track_points)
    requested_release_frame = int(st.session_state.release_frame)
    if marker_frames and requested_release_frame not in st.session_state.track_points:
        later_markers = [frame for frame in marker_frames if frame >= requested_release_frame]
        effective_release_frame = later_markers[0] if later_markers else marker_frames[0]
        st.session_state.release_frame = effective_release_frame
        st.session_state.applied_fit_signature = None
        st.info(
            f"Im bisher gewählten Release-Bild {requested_release_frame} war kein Kugelmarker vorhanden. "
            f"Als Release wird deshalb automatisch der erste passende Kugelmarker in Bild {effective_release_frame} verwendet."
        )
    try:
        fit, measured = fit_release_parameters(
            points_by_frame=st.session_state.track_points,
            calibration=calibration,
            fps=info.fps,
            slow_factor=current_slow_factor(),
            release_frame=int(st.session_state.release_frame),
            gravity_m_s2=9.81,
        )
    except ValueError as error:
        st.error(str(error))
        st.stop()

    release_measurement = measured.loc[measured["frame"] == int(st.session_state.release_frame)].iloc[0]
    release_x_for_simulation = float(release_measurement["x_m"])
    release_height_for_simulation = float(release_measurement["z_m"])

    metric_cols = st.columns(6)
    metric_cols[0].metric("v₀", f"{fit.v0_m_s:.2f} m/s")
    metric_cols[1].metric("v₀x", f"{fit.vx_m_s:.2f} m/s")
    metric_cols[2].metric("v₀z", f"{fit.vz_m_s:.2f} m/s")
    metric_cols[3].metric("Winkel", f"{fit.angle_deg:.2f}°")
    metric_cols[4].metric("Abwurfhöhe", f"{release_height_for_simulation:.2f} m")
    metric_cols[5].metric("Fit-RMSE", f"{fit.rmse_m * 100:.1f} cm")

    if fit.vx_m_s <= 0:
        st.warning("v₀x ist nicht positiv. Vermutlich zeigt die X-Achse entgegen der Stoßrichtung; X-Referenz bitte prüfen.")
    if release_height_for_simulation <= 0:
        st.warning("Die berechnete Abwurfhöhe ist nicht plausibel. Ursprung und Z-Kalibrierung bitte prüfen.")

    fit_signature = (
        fit.point_count,
        fit.release_frame,
        round(fit.slow_factor, 9),
        round(fit.v0_m_s, 9),
        round(fit.angle_deg, 9),
        round(release_x_for_simulation, 9),
        round(release_height_for_simulation, 9),
    )
    if st.session_state.applied_fit_signature != fit_signature:
        st.session_state.sim_v0 = max(0.0, fit.v0_m_s)
        st.session_state.sim_angle = fit.angle_deg
        st.session_state.sim_height = max(0.0, release_height_for_simulation)
        st.session_state.sim_x0 = release_x_for_simulation
        st.session_state.sim_g = 9.81
        st.session_state.sim_initialized_from_fit = True
        st.session_state.applied_fit_signature = fit_signature

    if st.button("Videomessung als Simulationsbasis übernehmen", type="primary"):
        st.session_state.sim_v0 = max(0.0, fit.v0_m_s)
        st.session_state.sim_angle = fit.angle_deg
        st.session_state.sim_height = max(0.0, release_height_for_simulation)
        st.session_state.sim_x0 = release_x_for_simulation
        st.session_state.sim_g = 9.81
        st.session_state.sim_initialized_from_fit = True
        st.session_state.applied_fit_signature = fit_signature

    st.subheader("Simulationsbasis")
    input_cols = st.columns(5)
    input_cols[0].number_input("v₀ [m/s]", min_value=0.0, max_value=100.0, step=0.1, key="sim_v0")
    input_cols[1].number_input("Winkel [°]", min_value=-180.0, max_value=180.0, step=0.5, key="sim_angle")
    input_cols[2].number_input("h₀ [m]", min_value=0.0, max_value=20.0, step=0.01, key="sim_height")
    input_cols[3].number_input("x₀ [m]", min_value=-1000.0, max_value=1000.0, step=0.01, key="sim_x0")
    input_cols[4].number_input("g [m/s²]", min_value=0.1, max_value=20.0, step=0.01, key="sim_g")

    base = TrajectoryParameters(
        label="Simulationsbasis",
        v0_m_s=float(st.session_state.sim_v0),
        angle_deg=float(st.session_state.sim_angle),
        release_height_m=float(st.session_state.sim_height),
        release_x_m=float(st.session_state.sim_x0),
        gravity_m_s2=float(st.session_state.sim_g),
    )
    results = [simulate(base)]

    with st.expander("Parameter automatisch variieren", expanded=True):
        vary = st.checkbox("Vergleichskurven anzeigen", value=True)
        parameter_labels = {
            "Abfluggeschwindigkeit v₀": "v0_m_s",
            "Abflugwinkel": "angle_deg",
            "Abwurfhöhe": "release_height_m",
        }
        variation_cols = st.columns(4)
        chosen_label = variation_cols[0].selectbox("Parameter", tuple(parameter_labels))
        key = parameter_labels[chosen_label]
        center = float(getattr(base, key))
        default_span = 2.0 if key == "v0_m_s" else (10.0 if key == "angle_deg" else 0.3)
        start_key = f"variation_start_{key}"
        stop_key = f"variation_stop_{key}"
        lower_bound = 0.0 if key in {"v0_m_s", "release_height_m"} else -180.0
        upper_bound = 100.0 if key == "v0_m_s" else (20.0 if key == "release_height_m" else 180.0)
        if start_key in st.session_state:
            st.session_state[start_key] = float(np.clip(st.session_state[start_key], lower_bound, upper_bound))
        if stop_key in st.session_state:
            st.session_state[stop_key] = float(np.clip(st.session_state[stop_key], lower_bound, upper_bound))
        start = variation_cols[1].number_input(
            "Startwert",
            min_value=lower_bound,
            max_value=upper_bound,
            value=max(lower_bound, center - default_span),
            key=start_key,
        )
        stop = variation_cols[2].number_input(
            "Endwert",
            min_value=lower_bound,
            max_value=upper_bound,
            value=min(upper_bound, center + default_span),
            key=stop_key,
        )
        count = variation_cols[3].slider("Kurven", 2, 9, 5)
        if vary:
            for candidate in sweep(base, key, float(start), float(stop), int(count)):
                if abs(float(getattr(candidate.parameters, key)) - center) > 1e-9:
                    results.append(candidate)

    release_image = cached_frame(analysis_path, int(st.session_state.release_frame))
    composite_image = draw_video_trajectory_composite(
        release_image,
        results=results,
        calibration=calibration,
        measured=measured,
        release_point=(release_x_for_simulation, release_height_for_simulation),
    )
    st.subheader("Release-Bild mit getrackten Punkten und fortgesetzter Simulation")
    st.image(composite_image, width="stretch")
    st.caption(
        "Das Videobild bleibt unverzerrt. Weiße Punkte liegen an den original angeklickten Pixelpositionen; "
        "die farbigen Simulationen beginnen am Release und laufen auf der weißen Erweiterungsfläche weiter."
    )

    summary = pd.DataFrame(
        [
            {
                "Variante": result.parameters.label,
                "v₀ [m/s]": result.parameters.v0_m_s,
                "Winkel [°]": result.parameters.angle_deg,
                "h₀ [m]": result.parameters.release_height_m,
                "Flugzeit [s]": result.flight_time_s,
                "Flugweite [m]": result.flight_distance_m,
                "Scheitelhöhe [m]": result.peak_height_m,
            }
            for result in results
        ]
    )
    st.dataframe(summary, hide_index=True, width="stretch")

    export_payload = {
        "video": asdict(info),
        "timebase_mode": st.session_state.timebase_mode,
        "single_speed_mode": st.session_state.single_speed_mode,
        "analysis_speed_mode": st.session_state.analysis_speed_mode,
        "effective_slow_factor": current_slow_factor(),
        "effective_release_frame": int(st.session_state.release_frame),
        "calibration": asdict(calibration),
        "release_fit": fit.to_dict(),
        "release_marker_position": {
            "x_m": release_x_for_simulation,
            "z_m": release_height_for_simulation,
        },
        "measured_points": measured.to_dict(orient="records"),
    }
    png_buffer = BytesIO()
    composite_image.save(png_buffer, format="PNG")
    download_cols = st.columns(3)
    download_cols[0].download_button(
        "Analyse als JSON",
        json.dumps(export_payload, ensure_ascii=False, indent=2),
        file_name="kugelstoss_videoanalyse.json",
        mime="application/json",
        width="stretch",
    )
    download_cols[1].download_button(
        "Messpunkte als CSV",
        measured.to_csv(index=False).encode("utf-8-sig"),
        file_name="kugelstoss_messpunkte.csv",
        mime="text/csv",
        width="stretch",
    )
    download_cols[2].download_button(
        "Video und Simulation als PNG",
        png_buffer.getvalue(),
        file_name="kugelstoss_video_und_simulation.png",
        mime="image/png",
        width="stretch",
    )
else:
    st.header("5 · Kurzanleitung")
    st.markdown(
        """
1. **Zeitbasis:** Bei einem einzelnen Normalvideo genügt `Normalgeschwindigkeit`. Bei einem einzelnen Zeitlupenvideo den bekannten Faktor eintragen. Nur bei einer kombinierten Datei dieselben Ereignisse in Original und Zeitlupe markieren.
2. **Kalibrierung:** O als Boden-Ursprung setzen. Der X-Referenz eine bekannte Koordinate geben (in Stoßrichtung positiv, dahinter negativ) und auswählen, ob Z über O oder über X liegt.
3. **Release:** Im analysierten Videoabschnitt das erste Bild bestimmen, in dem sich die Kugel sichtbar von der Hand löst.
4. **Kugelspur:** Kugelmittelpunkt im Release-Bild und in mindestens zwei späteren Bildern anklicken. Besser sind vier bis acht frühe Flugpunkte.
5. **Simulation:** Die Messwerte werden als Ausgangsbasis übernommen. Anschließend `v₀`, Winkel oder Abwurfhöhe variieren. Das Release-Bild bildet den Anfang der gemeinsamen Grafik; die Simulation läuft anschließend über dessen Bildrand hinaus weiter.

**Wichtig:** Die Messung ist nur so gut wie die Kalibrierung. Bei schräger Kamera sollten O, X, Z und die Kugelbahn möglichst in derselben räumlichen Ebene liegen. Beim vorhandenen Seminarvideo wurde die 60-fps-Ausgabe nachbearbeitet; dort ist deshalb der Vergleich der beiden Videoteile entscheidend. Bei einem gewöhnlichen Einzelvideo wird die Metadaten-Bildrate mit Faktor 1 verwendet.
        """
    )

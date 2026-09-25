from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import sys

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from data_io import guess_csv_mapping, read_sensor_csv, standardize_sensor_frame
from signals import (
    LOGICAL_CHANNELS,
    PhaseEvent,
    PhyphoxClient,
    ProcessingSettings,
    detect_phases,
    enrich_signals,
    extract_buffer_names,
    guess_live_mapping,
    make_demo_frame,
)
from video_sequences import (
    PHASE_COLORS,
    PHASE_LABELS,
    build_phase_clip,
    ordered_event_frames,
    phase_bounds,
    synchronization_from_anchors,
    video_frame_to_sensor_time,
)
from video_utils import build_proxy, read_frame, read_video_info, save_uploaded_video


st.set_page_config(page_title="Kugelstoß: Phyphox & Videosequenzen", page_icon="📱", layout="wide")

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
EMPTY_DATA = pd.DataFrame(columns=LOGICAL_CHANNELS)
SEQUENCE_TITLES = {
    "Bewegungsbeginn": "Angleiten / Eindrehen",
    "Kreiszentrum": "Umsetzen im Kreiszentrum",
    "Power Position": "Power Position und Ausstoß",
    "Release": "Release und Abfangen",
    "Abfangen": "Stabilisierung",
}


@st.cache_data(show_spinner=False)
def cached_info(path: str):
    return read_video_info(path)


@st.cache_data(show_spinner=False, max_entries=100)
def cached_frame(path: str, frame_index: int):
    return read_frame(path, frame_index)


@st.cache_data(show_spinner=False, max_entries=30)
def cached_clip(path: str, start_frame: int, end_frame: int, fps: float) -> str:
    return str(build_phase_clip(path, start_frame, end_frame, fps))


def initialize_state() -> None:
    defaults = {
        "active_video_signature": "",
        "analysis_path": "",
        "inspect_frame": 0,
        "event_frames": {},
        "video_event_to_set": "Bewegungsbeginn",
        "selected_phase": "Power Position",
        "slow_factor": 4.0,
        "sensor_source": "Demo",
        "previous_sensor_source": "Demo",
        "raw_data": make_demo_frame(),
        "csv_raw": None,
        "csv_signature": "",
        "live_url": "http://127.0.0.1:8080",
        "live_config": None,
        "live_buffers": [],
        "live_config_loaded": False,
        "live_error": None,
        "live_status": {},
        "auto_poll": False,
        "poll_interval_ms": 700,
        "phase_cutoff_hz": 7.0,
        "event_cutoff_hz": 16.0,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    for channel in LOGICAL_CHANNELS:
        st.session_state.setdefault(f"live_mapping_{channel}", "-")
        st.session_state.setdefault(f"csv_mapping_{channel}", "-")


def activate_video(path: Path, frame_count: int) -> None:
    signature = f"{path.resolve()}:{path.stat().st_size}:{path.stat().st_mtime_ns}"
    if st.session_state.active_video_signature == signature:
        return
    st.session_state.active_video_signature = signature
    st.session_state.analysis_path = str(path.resolve())
    st.session_state.inspect_frame = 0
    last = max(0, frame_count - 1)
    if frame_count >= 700 and path.name.lower() == "kugelstoß.mp4":
        seeds = (150, 420, 510, 600, 690)
    else:
        seeds = tuple(round(last * fraction) for fraction in (0.20, 0.40, 0.58, 0.72, 0.88))
    st.session_state.event_frames = dict(zip(PHASE_LABELS, seeds))


def append_live(frame: pd.DataFrame) -> None:
    if frame.empty:
        return
    combined = pd.concat([st.session_state.raw_data, frame], ignore_index=True)
    combined = combined.drop_duplicates("time", keep="last").sort_values("time")
    st.session_state.raw_data = combined.iloc[-30000:].reset_index(drop=True)


def current_live_mapping() -> dict[str, str | None]:
    return {
        channel: None if st.session_state.get(f"live_mapping_{channel}", "-") == "-" else st.session_state[f"live_mapping_{channel}"]
        for channel in LOGICAL_CHANNELS
    }


def load_live_config() -> None:
    payload = PhyphoxClient(st.session_state.live_url).config()
    guessed = guess_live_mapping(payload)
    st.session_state.live_config = payload
    st.session_state.live_buffers = extract_buffer_names(payload)
    st.session_state.live_config_loaded = True
    st.session_state.live_error = None
    for channel, value in guessed.items():
        st.session_state[f"live_mapping_{channel}"] = value or "-"


def poll_live(full: bool = False) -> None:
    mapping = current_live_mapping()
    last_time = None
    if not full and not st.session_state.raw_data.empty:
        last_time = float(st.session_state.raw_data["time"].iloc[-1])
    frame, status = PhyphoxClient(st.session_state.live_url).poll(mapping, last_time)
    append_live(frame)
    st.session_state.live_status = status
    st.session_state.live_error = None


def video_sequence(label: str, info, analysis_path: str) -> tuple[str, int, int]:
    start, end = phase_bounds(st.session_state.event_frames, label, info.frame_count - 1)
    return cached_clip(analysis_path, start, end, info.fps), start, end


def process_signals() -> tuple[pd.DataFrame, float, list[PhaseEvent]]:
    settings = ProcessingSettings(
        phase_cutoff_hz=float(st.session_state.phase_cutoff_hz),
        event_cutoff_hz=float(st.session_state.event_cutoff_hz),
    )
    enriched, rate = enrich_signals(st.session_state.raw_data.copy(), settings)
    return enriched, rate, detect_phases(enriched, rate)


def signal_figure(frame: pd.DataFrame, events: list[PhaseEvent], domain: tuple[float, float] | None = None):
    plotted = frame
    if domain is not None:
        plotted = frame[(frame["time"] >= domain[0]) & (frame["time"] <= domain[1])]
        if plotted.empty:
            plotted = frame
    figure, axes = plt.subplots(2, 1, figsize=(11, 6.2), sharex=True)
    axes[0].plot(plotted["time"], plotted["acc_x_phase"], label="aₓ", linewidth=1.7)
    axes[0].plot(plotted["time"], plotted["acc_z_phase"], label="a_z", linewidth=1.7)
    axes[0].plot(plotted["time"], plotted["acc_resultant_phase"], label="|a|", linewidth=2.2)
    axes[0].set_ylabel("Beschleunigung")
    axes[1].plot(plotted["time"], plotted["gyro_z_phase"], label="ω_z", linewidth=1.8)
    axes[1].plot(plotted["time"], plotted["gyro_resultant_phase"], label="|ω|", linewidth=2.2)
    axes[1].set_ylabel("Winkelgeschwindigkeit")
    axes[1].set_xlabel("Phyphox-Zeit [s]")
    for axis in axes:
        for event in events:
            if domain is None or domain[0] <= event.time_s <= domain[1]:
                axis.axvline(event.time_s, color=event.color, linestyle="--", alpha=0.8)
        axis.grid(alpha=0.25)
        axis.legend(loc="upper left", ncol=3)
    if domain is not None:
        axes[1].set_xlim(domain)
    figure.tight_layout()
    return figure


def next_phase(label: str) -> str | None:
    index = PHASE_LABELS.index(label)
    return PHASE_LABELS[index + 1] if index + 1 < len(PHASE_LABELS) else None


initialize_state()

st.title("Kugelstoß: Phyphox und Videosequenzen")
st.caption(
    "Sensorverläufe mit anschaulichen Techniksequenzen verbinden – als Phasenreferenz für unabhängige "
    "Versuche oder, bei gemeinsamer Aufnahme, über zwei Ereignisse exakt synchronisiert."
)

with st.sidebar:
    st.header("Video")
    video_options = ["Video hochladen"]
    if DEFAULT_VIDEO.exists():
        video_options.insert(0, "Seminarvideo Kugelstoß.mp4")
    video_source = st.radio("Videoquelle", video_options)
    video_path: Path | None = DEFAULT_VIDEO if video_source.startswith("Seminarvideo") else None
    if video_source == "Video hochladen":
        uploaded_video = st.file_uploader("Videodatei", type=["mp4", "mov", "m4v", "avi"])
        if uploaded_video:
            video_path = save_uploaded_video(uploaded_video.getvalue(), uploaded_video.name)
    if video_path is None:
        st.info("Bitte ein Video wählen.")
        st.stop()
    info = cached_info(str(video_path))
    activate_video(video_path, info.frame_count)
    if Path(st.session_state.analysis_path).resolve() == video_path.resolve():
        with st.spinner("Analysevideo wird vorbereitet …"):
            st.session_state.analysis_path = str(build_proxy(video_path))
    analysis_path = st.session_state.analysis_path
    st.caption(f"{info.frame_count} Bilder · {info.fps:.3g} fps · {info.duration_s:.2f} s")

    st.divider()
    st.header("Phyphox-Daten")
    source = st.radio("Datenquelle", ("Demo", "CSV-Export", "Phyphox Live"), key="sensor_source")
    if source != st.session_state.previous_sensor_source:
        st.session_state.raw_data = make_demo_frame() if source == "Demo" else EMPTY_DATA.copy()
        st.session_state.live_error = None
        st.session_state.live_status = {}
        st.session_state.previous_sensor_source = source
    if source == "Demo":
        if st.button("Demo neu laden", width="stretch"):
            st.session_state.raw_data = make_demo_frame()
    elif source == "CSV-Export":
        uploaded_csv = st.file_uploader("Phyphox-CSV", type=["csv", "txt"])
        if uploaded_csv:
            content = uploaded_csv.getvalue()
            signature = sha256(content).hexdigest()
            if signature != st.session_state.csv_signature:
                raw = read_sensor_csv(content)
                st.session_state.csv_raw = raw
                guessed = guess_csv_mapping(raw.columns)
                for channel, value in guessed.items():
                    st.session_state[f"csv_mapping_{channel}"] = value or "-"
                st.session_state.csv_signature = signature
    else:
        st.text_input("Phyphox-URL", key="live_url")
        control_cols = st.columns(2)
        if control_cols[0].button("Config laden", width="stretch"):
            try:
                load_live_config()
            except Exception as error:
                st.session_state.live_error = str(error)
        if control_cols[1].button("Daten holen", width="stretch"):
            try:
                poll_live(full=st.session_state.raw_data.empty)
            except Exception as error:
                st.session_state.live_error = str(error)
        if st.session_state.live_config_loaded:
            options = ["-"] + list(st.session_state.live_buffers)
            for channel in LOGICAL_CHANNELS:
                current = st.session_state.get(f"live_mapping_{channel}", "-")
                if current not in options:
                    st.session_state[f"live_mapping_{channel}"] = "-"
                st.selectbox(channel, options, key=f"live_mapping_{channel}")
            start_col, stop_col, clear_col = st.columns(3)
            for column, command, label in zip((start_col, stop_col, clear_col), ("start", "stop", "clear"), ("Start", "Stop", "Clear")):
                if column.button(label, width="stretch"):
                    try:
                        PhyphoxClient(st.session_state.live_url).control(command)
                        if command == "clear":
                            st.session_state.raw_data = EMPTY_DATA.copy()
                    except Exception as error:
                        st.session_state.live_error = str(error)
            st.toggle("Auto-Polling", key="auto_poll")
            st.slider("Intervall [ms]", 300, 2000, 100, key="poll_interval_ms")
        if st.session_state.live_error:
            st.error(st.session_state.live_error)

    st.divider()
    st.header("Ansicht")
    step = st.radio("Bereich", ("1 · Videosequenzen", "2 · Phyphox-Signale", "3 · Kombinierte Analyse"), label_visibility="collapsed")


def render_video_sequences() -> None:
    st.header("1 · Technikereignisse im Video festlegen")
    st.number_input("Zeitlupenfaktor", min_value=0.1, max_value=100.0, step=0.1, key="slow_factor")
    st.slider("Aktuelles Videobild", 0, info.frame_count - 1, key="inspect_frame")
    frame_index = int(st.session_state.inspect_frame)
    st.image(cached_frame(analysis_path, frame_index), caption=f"Bild {frame_index} · {frame_index / info.fps:.3f} s Videozeit", width="stretch")
    marker_cols = st.columns([2, 1])
    marker_cols[0].selectbox("Ereignis", PHASE_LABELS, key="video_event_to_set")
    if marker_cols[1].button("Aktuelles Bild zuweisen", type="primary", width="stretch"):
        st.session_state.event_frames[st.session_state.video_event_to_set] = frame_index
        st.rerun()

    rows = []
    ordered = ordered_event_frames(st.session_state.event_frames)
    for index, (label, frame) in enumerate(ordered):
        following = ordered[index + 1][1] if index + 1 < len(ordered) else None
        rows.append({
            "Ereignis": label,
            "Bild": frame,
            "Videozeit [s]": frame / info.fps,
            "reale Sequenzdauer [s]": ((following - frame) / (info.fps * st.session_state.slow_factor)) if following else None,
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

    st.subheader("Sequenzvorschau")
    selected = st.selectbox("Sequenz", PHASE_LABELS, format_func=lambda label: SEQUENCE_TITLES[label], key="selected_phase")
    try:
        clip, start, end = video_sequence(selected, info, analysis_path)
        st.video(clip)
        st.caption(f"Bilder {start}–{end}; reale Dauer bei {st.session_state.slow_factor:.2f}× Zeitlupe: {(end-start)/(info.fps*st.session_state.slow_factor):.3f} s")
    except Exception as error:
        st.warning(str(error))


def render_sensor_data() -> None:
    st.header("2 · Phyphox-Signale und automatische Ereignisse")
    if st.session_state.sensor_source == "CSV-Export":
        raw = st.session_state.csv_raw
        if raw is None:
            st.info("Bitte links eine Phyphox-CSV laden.")
            return
        st.subheader("Spalten zuordnen")
        options = ["-"] + list(raw.columns)
        columns = st.columns(4)
        for index, channel in enumerate(LOGICAL_CHANNELS):
            current = st.session_state.get(f"csv_mapping_{channel}", "-")
            if current not in options:
                st.session_state[f"csv_mapping_{channel}"] = "-"
            columns[index % 4].selectbox(channel, options, key=f"csv_mapping_{channel}")
        if st.button("CSV-Zuordnung anwenden", type="primary"):
            mapping = {channel: None if st.session_state[f"csv_mapping_{channel}"] == "-" else st.session_state[f"csv_mapping_{channel}"] for channel in LOGICAL_CHANNELS}
            st.session_state.raw_data = standardize_sensor_frame(raw, mapping)

    if st.session_state.raw_data.empty:
        st.info("Noch keine Sensordaten vorhanden.")
        return
    filter_cols = st.columns(2)
    filter_cols[0].slider("Phasen-Tiefpass [Hz]", 4.0, 12.0, 0.5, key="phase_cutoff_hz")
    filter_cols[1].slider("Ereignis-Tiefpass [Hz]", 8.0, 24.0, 0.5, key="event_cutoff_hz")
    enriched, rate, events = process_signals()
    metrics = st.columns(3)
    metrics[0].metric("Samplingrate", f"{rate:.1f} Hz")
    metrics[1].metric("Samples", len(enriched))
    metrics[2].metric("erkannte Ereignisse", len(events))
    figure = signal_figure(enriched, events)
    st.pyplot(figure, width="stretch")
    plt.close(figure)
    st.dataframe(pd.DataFrame([{"Ereignis": event.label, "Zeit [s]": event.time_s} for event in events]), hide_index=True, width="stretch")


def render_combined() -> None:
    st.header("3 · Video und Phyphox gemeinsam betrachten")
    if st.session_state.raw_data.empty:
        st.info("Noch keine Sensordaten vorhanden.")
        return
    enriched, rate, events = process_signals()
    event_map = {event.label: event.time_s for event in events}
    selected = st.selectbox("Techniksequenz", PHASE_LABELS, format_func=lambda label: SEQUENCE_TITLES[label])
    mode = st.radio(
        "Beziehung zwischen Video und Sensorversuch",
        ("Phasenreferenz – unterschiedliche Versuche", "Exakte Synchronisation – derselbe Versuch"),
    )
    try:
        clip, start_frame, end_frame = video_sequence(selected, info, analysis_path)
    except Exception as error:
        st.error(str(error))
        return

    sync_details = None
    if mode.startswith("Phasenreferenz"):
        st.info("Video und Phyphox stammen nicht aus demselben Versuch. Verglichen werden ausschließlich gleich benannte Technikphasen, keine absoluten Zeitpunkte.")
        start_sensor = event_map.get(selected)
        following = next_phase(selected)
        end_sensor = event_map.get(following) if following else None
        if start_sensor is None:
            start_sensor = float(enriched["time"].iloc[0])
        if end_sensor is None or end_sensor <= start_sensor:
            end_sensor = min(float(enriched["time"].iloc[-1]), start_sensor + 0.7)
    else:
        st.warning("Diese Option nur verwenden, wenn Video und Phyphox tatsächlich denselben Stoß aufgezeichnet haben.")
        anchor_cols = st.columns(4)
        anchor_a = anchor_cols[0].selectbox("Videoanker A", PHASE_LABELS, index=0)
        anchor_b = anchor_cols[1].selectbox("Videoanker B", PHASE_LABELS, index=3)
        sensor_a = anchor_cols[2].number_input("Phyphox-Zeit A [s]", value=float(event_map.get(anchor_a, 0.0)), step=0.01)
        sensor_b = anchor_cols[3].number_input("Phyphox-Zeit B [s]", value=float(event_map.get(anchor_b, max(sensor_a + 0.5, 1.0))), step=0.01)
        try:
            slope, offset = synchronization_from_anchors(
                st.session_state.event_frames[anchor_a], sensor_a,
                st.session_state.event_frames[anchor_b], sensor_b,
            )
            start_sensor = video_frame_to_sensor_time(start_frame, slope, offset)
            end_sensor = video_frame_to_sensor_time(end_frame, slope, offset)
            sync_details = {"anchor_a": anchor_a, "anchor_b": anchor_b, "slope_s_per_frame": slope, "offset_s": offset}
        except (ValueError, KeyError) as error:
            st.error(str(error))
            return

    left, right = st.columns([1, 1.6])
    with left:
        st.subheader(SEQUENCE_TITLES[selected])
        st.video(clip)
        st.caption(f"Videobilder {start_frame}–{end_frame}")
    with right:
        figure = signal_figure(enriched, events, (float(start_sensor), float(end_sensor)))
        st.pyplot(figure, width="stretch")
        plt.close(figure)

    video_duration = (end_frame - start_frame) / (info.fps * float(st.session_state.slow_factor))
    sensor_duration = float(end_sensor) - float(start_sensor)
    comparison = pd.DataFrame([{
        "Sequenz": SEQUENCE_TITLES[selected],
        "Video real [s]": video_duration,
        "Phyphox-Fenster [s]": sensor_duration,
        "Hinweis": "direkt vergleichbar" if mode.startswith("Exakte") else "nur Phasenreferenz",
    }])
    st.dataframe(comparison, hide_index=True, width="stretch")

    payload = {
        "mode": mode,
        "video": asdict(info),
        "slow_factor": float(st.session_state.slow_factor),
        "video_events": st.session_state.event_frames,
        "detected_sensor_events": {event.label: event.time_s for event in events},
        "selected_sequence": selected,
        "sensor_window_s": [float(start_sensor), float(end_sensor)],
        "synchronization": sync_details,
    }
    download_cols = st.columns(2)
    download_cols[0].download_button("Zuordnung als JSON", json.dumps(payload, ensure_ascii=False, indent=2), "kugelstoss_video_phyphox.json", "application/json", width="stretch")
    download_cols[1].download_button("Sensordaten als CSV", enriched.to_csv(index=False).encode("utf-8-sig"), "kugelstoss_phyphox_daten.csv", "text/csv", width="stretch")


run_every = None
if st.session_state.sensor_source == "Phyphox Live" and st.session_state.auto_poll and st.session_state.live_config_loaded:
    run_every = f"{int(st.session_state.poll_interval_ms)}ms"


@st.fragment(run_every=run_every)
def main_panel() -> None:
    if run_every:
        try:
            poll_live(full=st.session_state.raw_data.empty)
        except Exception as error:
            st.session_state.live_error = str(error)
    if step.startswith("1"):
        render_video_sequences()
    elif step.startswith("2"):
        render_sensor_data()
    else:
        render_combined()


main_panel()

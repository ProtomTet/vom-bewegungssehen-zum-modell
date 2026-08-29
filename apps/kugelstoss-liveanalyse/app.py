from __future__ import annotations

from typing import Any

from matplotlib import pyplot as plt
import pandas as pd
import streamlit as st

from demo_data import make_demo_frame
from phyphox_client import LOGICAL_CHANNELS, PhyphoxClient, guess_channel_mapping
from signal_processing import (
    PhaseEvent,
    ProcessingSettings,
    build_trajectory,
    detect_phases,
    enrich_signals,
    summarize_events,
)


MAX_SAMPLES = 30000
DEFAULT_URL = "http://127.0.0.1:8080"
EMPTY_FRAME = pd.DataFrame(columns=LOGICAL_CHANNELS)
CHANNEL_LABELS = {
    "time": "Zeit",
    "acc_x": "Beschl. x",
    "acc_y": "Beschl. y",
    "acc_z": "Beschl. z",
    "gyro_x": "Gyro x",
    "gyro_y": "Gyro y",
    "gyro_z": "Gyro z",
}


def ensure_state() -> None:
    defaults: dict[str, Any] = {
        "raw_data": EMPTY_FRAME.copy(),
        "config_payload": None,
        "buffer_names": [],
        "live_error": None,
        "live_status": {},
        "live_session_id": None,
        "config_loaded": False,
        "auto_poll": True,
        "poll_interval_ms": 700,
        "freeze_prev": False,
        "frozen_domain": None,
        "demo_loaded": False,
        "view_mode": "Release-zentriert",
        "manual_center": 0.0,
        "release_shift": 0.0,
        "window_width_s": 1.8,
        "freeze_view": False,
        "follow_release": True,
        "phase_cutoff_hz": 7.0,
        "event_cutoff_hz": 16.0,
        "trajectory_v0": 13.2,
        "trajectory_alpha": 37.0,
        "trajectory_h0": 2.05,
        "live_url": DEFAULT_URL,
        "source_mode": "Demo",
        "previous_source_mode": "Demo",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    for channel in LOGICAL_CHANNELS:
        key = f"mapping_{channel}"
        if key not in st.session_state:
            st.session_state[key] = "-"


def current_mapping() -> dict[str, str | None]:
    mapping: dict[str, str | None] = {}
    for channel in LOGICAL_CHANNELS:
        value = st.session_state.get(f"mapping_{channel}", "-")
        mapping[channel] = None if value in ("", "-") else value
    return mapping


def reset_live_buffers() -> None:
    st.session_state.raw_data = EMPTY_FRAME.copy()
    st.session_state.live_session_id = None
    st.session_state.frozen_domain = None
    st.session_state.demo_loaded = False


def load_demo_data() -> None:
    st.session_state.raw_data = make_demo_frame()
    st.session_state.demo_loaded = True
    st.session_state.live_error = None
    st.session_state.frozen_domain = None
    st.session_state.live_session_id = None


def get_client() -> PhyphoxClient:
    return PhyphoxClient(st.session_state.live_url)


def extract_buffer_names(config_payload: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for item in config_payload.get("buffers", []):
        name = item.get("name")
        if isinstance(name, str) and name not in names:
            names.append(name)

    for export_set in config_payload.get("export", []):
        for data_set in export_set.get("data", []):
            buffer_name = data_set.get("buffer")
            if isinstance(buffer_name, str) and buffer_name not in names:
                names.append(buffer_name)
    return names


def load_config() -> None:
    client = get_client()
    config_payload = client.config()
    guessed = guess_channel_mapping(config_payload)
    st.session_state.config_payload = config_payload
    st.session_state.buffer_names = extract_buffer_names(config_payload)
    st.session_state.config_loaded = True
    st.session_state.live_error = None
    for channel, value in guessed.items():
        st.session_state[f"mapping_{channel}"] = value or "-"


def append_samples(frame: pd.DataFrame) -> None:
    if frame.empty:
        return
    combined = pd.concat([st.session_state.raw_data, frame], ignore_index=True)
    combined = combined.drop_duplicates(subset="time", keep="last").sort_values("time")
    if len(combined) > MAX_SAMPLES:
        combined = combined.iloc[-MAX_SAMPLES:].copy()
    st.session_state.raw_data = combined.reset_index(drop=True)


def poll_live(force_full: bool = False) -> None:
    mapping = current_mapping()
    if not mapping.get("time"):
        raise ValueError("Bitte zuerst einen Zeitbuffer auswaehlen.")

    client = get_client()
    current_data = st.session_state.raw_data
    last_time = None if force_full or current_data.empty else float(current_data["time"].iloc[-1])
    result = client.poll(mapping, last_time=last_time)

    previous_session = st.session_state.live_session_id
    if previous_session and result.session_id and previous_session != result.session_id:
        reset_live_buffers()
        result = client.poll(mapping, last_time=None)

    if result.session_id:
        st.session_state.live_session_id = result.session_id
    st.session_state.live_status = result.status
    st.session_state.live_error = None
    append_samples(result.frame)


def send_control(command: str) -> None:
    client = get_client()
    client.control(command)
    st.session_state.live_error = None
    if command == "clear":
        reset_live_buffers()


def freeze_domain_if_needed(domain: tuple[float, float]) -> tuple[float, float]:
    freeze_view = bool(st.session_state.freeze_view)
    if freeze_view and not st.session_state.freeze_prev:
        st.session_state.frozen_domain = domain
    if not freeze_view:
        st.session_state.frozen_domain = None
    st.session_state.freeze_prev = freeze_view

    if freeze_view and st.session_state.frozen_domain is not None:
        return tuple(st.session_state.frozen_domain)
    return domain


def compute_view_domain(frame: pd.DataFrame, events: list[PhaseEvent]) -> tuple[float, float]:
    if frame.empty:
        return (0.0, 1.0)

    time_min = float(frame["time"].iloc[0])
    time_max = float(frame["time"].iloc[-1])
    width = float(max(0.6, st.session_state.window_width_s))
    mode = st.session_state.view_mode
    release_time = None
    for event in reversed(events):
        if event.label == "Release":
            release_time = event.time_s
            break

    if mode == "Letzte Daten":
        domain = (max(time_min, time_max - width), time_max)
    elif mode == "Manuell":
        center = float(st.session_state.manual_center)
        center = min(max(center, time_min), time_max)
        left = center - width / 2.0
        right = center + width / 2.0
        if left < time_min:
            right += time_min - left
            left = time_min
        if right > time_max:
            left -= right - time_max
            right = time_max
        domain = (max(time_min, left), min(time_max, right))
    else:
        center = release_time if release_time is not None else time_max
        center += float(st.session_state.release_shift)
        left = center - width / 2.0
        right = center + width / 2.0
        if left < time_min:
            right += time_min - left
            left = time_min
        if right > time_max:
            left -= right - time_max
            right = time_max
        domain = (max(time_min, left), min(time_max, right))

    if domain[0] == domain[1]:
        domain = (domain[0], domain[1] + 1.0)
    return freeze_domain_if_needed(domain)


def build_signal_chart(
    frame: pd.DataFrame,
    domain: tuple[float, float],
    events: list[PhaseEvent],
    value_specs: list[tuple[str, str]],
    title: str,
    y_label: str,
) -> plt.Figure:
    chart_frame = frame[(frame["time"] >= domain[0]) & (frame["time"] <= domain[1])].copy()
    if chart_frame.empty:
        chart_frame = frame.tail(min(len(frame), 5)).copy()

    fig, axis = plt.subplots(figsize=(10, 3.2))
    palette = ["#2b8cbe", "#31a354", "#756bb1", "#d95f02"]
    for idx, (column_name, label) in enumerate(value_specs):
        axis.plot(
            chart_frame["time"],
            chart_frame[column_name],
            label=label,
            linewidth=2.0,
            color=palette[idx % len(palette)],
        )

    visible_events = [event for event in events if domain[0] <= event.time_s <= domain[1]]
    y_limits = axis.get_ylim()
    for event in visible_events:
        axis.axvline(event.time_s, color=event.color, linestyle="--", linewidth=1.5, alpha=0.9)
        axis.text(
            event.time_s,
            y_limits[1],
            event.label,
            rotation=90,
            va="top",
            ha="right",
            color=event.color,
            fontsize=8,
        )

    axis.set_xlim(domain)
    axis.set_title(title)
    axis.set_xlabel("Zeit [s]")
    axis.set_ylabel(y_label)
    axis.grid(alpha=0.25)
    axis.legend(loc="upper left", frameon=False)
    fig.tight_layout()
    return fig


def build_trajectory_chart(v0_m_s: float, angle_deg: float, release_height_m: float) -> plt.Figure:
    trajectory = build_trajectory(v0_m_s=v0_m_s, angle_deg=angle_deg, release_height_m=release_height_m)
    fig, axis = plt.subplots(figsize=(5.2, 3.2))
    axis.plot(trajectory["x_m"], trajectory["z_m"], linewidth=3.0, color="#2b8cbe")
    if not trajectory.empty:
        axis.scatter(trajectory["x_m"].iloc[0], trajectory["z_m"].iloc[0], color="#d62728", s=60, zorder=3)
    axis.set_title("Kugelbahn-Projektion")
    axis.set_xlabel("Horizontale Distanz [m]")
    axis.set_ylabel("Hoehe [m]")
    axis.grid(alpha=0.25)
    fig.tight_layout()
    return fig


def render_dashboard() -> None:
    raw_frame = st.session_state.raw_data.copy()
    settings = ProcessingSettings(
        phase_cutoff_hz=float(st.session_state.phase_cutoff_hz),
        event_cutoff_hz=float(st.session_state.event_cutoff_hz),
    )
    enriched, sample_rate_hz = enrich_signals(raw_frame, settings=settings)
    events = detect_phases(enriched, sample_rate_hz=sample_rate_hz)
    summary = summarize_events(events)
    domain = compute_view_domain(enriched, events)

    status = st.session_state.live_status or {}
    event_map = {event.label: event.time_s for event in events}
    release_time = event_map.get("Release")

    status_col, rate_col, release_col, sample_col = st.columns(4)
    with status_col:
        state_text = status.get("measuring", False)
        st.metric("Phyphox misst", "Ja" if state_text else "Nein")
    with rate_col:
        st.metric("Samplingrate", f"{sample_rate_hz:.1f} Hz" if sample_rate_hz else "-")
    with release_col:
        st.metric("Release", f"{release_time:.3f} s" if release_time is not None else "-")
    with sample_col:
        st.metric("Samples", f"{len(enriched)}")

    if summary:
        summary_cols = st.columns(max(1, len(summary)))
        for idx, (label, value) in enumerate(summary.items()):
            summary_cols[idx].metric(label, f"{value * 1000.0:.0f} ms")

    if enriched.empty:
        st.info("Noch keine Daten verfuegbar. Im Demo-Modus ist die Testmessung per Klick ladbar.")
        return

    chart_top = build_signal_chart(
        frame=enriched,
        domain=domain,
        events=events,
        value_specs=[
            ("acc_x_phase", "a_x gefiltert"),
            ("acc_z_phase", "a_z gefiltert"),
            ("acc_resultant_phase", "|a| gefiltert"),
        ],
        title="Beschleunigung",
        y_label="m/s^2",
    )
    chart_bottom = build_signal_chart(
        frame=enriched,
        domain=domain,
        events=events,
        value_specs=[
            ("gyro_z_phase", "gyro_z gefiltert"),
            ("gyro_resultant_phase", "|gyro| gefiltert"),
        ],
        title="Winkelgeschwindigkeit",
        y_label="rad/s",
    )

    left_col, right_col = st.columns([2.2, 1.2])
    with left_col:
        st.pyplot(chart_top, use_container_width=True)
        st.pyplot(chart_bottom, use_container_width=True)

        if events:
            event_table = pd.DataFrame(
                {
                    "Phase": [event.label for event in events],
                    "Zeit [s]": [round(event.time_s, 3) for event in events],
                }
            )
            st.dataframe(event_table, use_container_width=True, hide_index=True)

    with right_col:
        trajectory_chart = build_trajectory_chart(
            v0_m_s=float(st.session_state.trajectory_v0),
            angle_deg=float(st.session_state.trajectory_alpha),
            release_height_m=float(st.session_state.trajectory_h0),
        )
        st.pyplot(trajectory_chart, use_container_width=True)

        st.caption(
            "Die Bahnprojektion nutzt manuelle Eingaben fuer v0, alpha und h0. "
            "Die Live-Signale kommen aus Phyphox; die reale Kugelbahn sollte fuer hohe Guete "
            "weiterhin per Video abgesichert werden."
        )


def main() -> None:
    st.set_page_config(page_title="Kugelstoss Live MVP", layout="wide")
    ensure_state()

    if st.session_state.source_mode != st.session_state.previous_source_mode:
        reset_live_buffers()
        st.session_state.config_loaded = False if st.session_state.source_mode == "Phyphox Live" else st.session_state.config_loaded
        st.session_state.live_error = None
        st.session_state.previous_source_mode = st.session_state.source_mode

    st.title("Kugelstoss Live-MVP mit Phyphox")
    st.caption(
        "MVP fuer Beschleunigung, Winkelgeschwindigkeit, heuristische Phasenmarken und eine "
        "einfrierbare Zeitansicht nach dem O'Brien-Prinzip."
    )

    with st.sidebar:
        st.subheader("Datenquelle")
        source_mode = st.radio("Quelle", ("Demo", "Phyphox Live"), horizontal=True, key="source_mode")
        if source_mode == "Demo":
            if st.button("Demo laden", use_container_width=True):
                load_demo_data()
            if not st.session_state.demo_loaded and st.session_state.raw_data.empty:
                load_demo_data()
        else:
            st.text_input("Phyphox URL", key="live_url", help="Beispiel: http://192.168.0.42:8080")
            connect_col, poll_col = st.columns(2)
            if connect_col.button("Config laden", use_container_width=True):
                try:
                    load_config()
                except Exception as exc:  # noqa: BLE001
                    st.session_state.live_error = str(exc)
            if poll_col.button("Pull once", use_container_width=True):
                try:
                    if not st.session_state.config_loaded:
                        load_config()
                    poll_live(force_full=st.session_state.raw_data.empty)
                except Exception as exc:  # noqa: BLE001
                    st.session_state.live_error = str(exc)

            start_col, stop_col, clear_col = st.columns(3)
            if start_col.button("Start", use_container_width=True):
                try:
                    send_control("start")
                except Exception as exc:  # noqa: BLE001
                    st.session_state.live_error = str(exc)
            if stop_col.button("Stop", use_container_width=True):
                try:
                    send_control("stop")
                except Exception as exc:  # noqa: BLE001
                    st.session_state.live_error = str(exc)
            if clear_col.button("Clear", use_container_width=True):
                try:
                    send_control("clear")
                except Exception as exc:  # noqa: BLE001
                    st.session_state.live_error = str(exc)

            st.toggle("Auto-Polling", key="auto_poll")
            st.slider("Poll-Intervall [ms]", min_value=300, max_value=2000, step=100, key="poll_interval_ms")

            if st.session_state.live_error:
                st.error(st.session_state.live_error)
            else:
                live_status = st.session_state.live_status or {}
                if st.session_state.config_loaded and not st.session_state.raw_data.empty:
                    st.success(f"Live-Daten aktiv: {len(st.session_state.raw_data)} Samples im Puffer.")
                elif st.session_state.config_loaded and live_status.get("measuring") is False:
                    st.info("Verbunden, aber Phyphox misst gerade noch nicht. Bitte in der App auf 'Start' klicken.")

            if st.session_state.config_loaded:
                st.markdown("**Buffer-Zuordnung**")
                options = ["-"] + list(st.session_state.buffer_names)
                for channel in LOGICAL_CHANNELS:
                    current_value = st.session_state.get(f"mapping_{channel}", "-")
                    if current_value not in options:
                        current_value = "-"
                    st.selectbox(
                        CHANNEL_LABELS[channel],
                        options=options,
                        index=options.index(current_value),
                        key=f"mapping_{channel}",
                    )

        st.divider()
        st.subheader("Signalverarbeitung")
        st.slider("Phase Lowpass [Hz]", min_value=4.0, max_value=12.0, step=0.5, key="phase_cutoff_hz")
        st.slider("Ereignis Lowpass [Hz]", min_value=8.0, max_value=24.0, step=0.5, key="event_cutoff_hz")

        st.divider()
        st.subheader("Zeitfenster")
        st.radio("Ansicht", ("Release-zentriert", "Letzte Daten", "Manuell"), key="view_mode")
        st.slider("Fensterbreite [s]", min_value=0.6, max_value=6.0, step=0.1, key="window_width_s")
        st.toggle("Ansicht einfrieren", key="freeze_view")
        if st.session_state.view_mode == "Release-zentriert":
            st.slider("Verschiebung zum Release [s]", min_value=-1.5, max_value=1.5, step=0.05, key="release_shift")

        data_frame = st.session_state.raw_data
        if not data_frame.empty and st.session_state.view_mode == "Manuell":
            time_min = float(data_frame["time"].iloc[0])
            time_max = float(data_frame["time"].iloc[-1])
            current_center = min(max(float(st.session_state.manual_center), time_min), time_max)
            st.session_state.manual_center = current_center
            st.slider(
                "Fensterzentrum [s]",
                min_value=time_min,
                max_value=time_max,
                step=0.01,
                key="manual_center",
            )

        st.divider()
        st.subheader("Bahnprojektion")
        st.number_input("v0 [m/s]", min_value=0.0, max_value=25.0, step=0.1, key="trajectory_v0")
        st.number_input("alpha [deg]", min_value=0.0, max_value=60.0, step=0.5, key="trajectory_alpha")
        st.number_input("h0 [m]", min_value=0.0, max_value=3.0, step=0.01, key="trajectory_h0")

    run_every = None
    if st.session_state.source_mode == "Phyphox Live" and st.session_state.auto_poll and st.session_state.config_loaded:
        run_every = f"{int(st.session_state.poll_interval_ms)}ms"

    @st.fragment(run_every=run_every)
    def live_panel() -> None:
        if st.session_state.source_mode == "Phyphox Live" and st.session_state.auto_poll and st.session_state.config_loaded:
            try:
                poll_live(force_full=st.session_state.raw_data.empty)
            except Exception as exc:  # noqa: BLE001
                st.session_state.live_error = str(exc)
        render_dashboard()

    live_panel()


if __name__ == "__main__":
    main()

from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd
import streamlit as st

APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from simple_charts import ChartSeries, RenderedChart, SERIES_COLORS, render_xy_chart
from trajectory_model import (
    PRESETS,
    VariantConfig,
    build_sweep_variants,
    changed_parameters,
    combined_trajectory_dataframe,
    components_from_polar,
    deduplicate_variants,
    empty_variant_frame,
    evaluate_variant,
    frame_to_variants,
    legend_label,
    optimization_dataframe,
    parameter_label,
    parameter_step,
    parameter_unit,
    polar_from_components,
    suggested_bounds,
    summary_dataframe,
    variants_to_frame,
    z_of_x_expression,
)


PARAMETER_CHOICES = {
    "Abflugwinkel alpha": "alpha_deg",
    "Abfluggeschwindigkeit v0": "v0_m_s",
    "Abflughöhe h0": "h0_m",
    "Startversatz x0": "x0_m",
}
OPTIMIZATION_CHOICES = {
    "Abflugwinkel alpha": "alpha_deg",
    "Abfluggeschwindigkeit v0": "v0_m_s",
    "Abflughöhe h0": "h0_m",
}


def empty_manual_variant_frame() -> pd.DataFrame:
    return empty_variant_frame()


def apply_preset(preset_name: str) -> None:
    preset = PRESETS[preset_name]
    base_variant = preset.base_variant
    vx_m_s, vz_m_s = components_from_polar(base_variant.v0_m_s, base_variant.alpha_deg)

    # This key is also owned by the selectbox widget. Only seed it before the widget exists.
    if "selected_preset_name" not in st.session_state:
        st.session_state.selected_preset_name = preset_name
    st.session_state.base_label = base_variant.label
    st.session_state.base_v0 = float(base_variant.v0_m_s)
    st.session_state.base_alpha = float(base_variant.alpha_deg)
    st.session_state.base_vx = float(vx_m_s)
    st.session_state.base_vz = float(vz_m_s)
    st.session_state.base_h0 = float(base_variant.h0_m)
    st.session_state.base_x0 = float(base_variant.x0_m)
    st.session_state.base_g = float(base_variant.g_m_s2)
    st.session_state.manual_variants_df = empty_manual_variant_frame()

    st.session_state.sweep_parameter_display = "Abflugwinkel alpha"
    start_value, stop_value = suggested_bounds(base_variant, "alpha_deg")
    st.session_state.sweep_start = float(start_value)
    st.session_state.sweep_stop = float(stop_value)
    st.session_state.sweep_curve_count = 5
    st.session_state.sweep_mode = "ersetzen"

    st.session_state.optimization_parameter_display = "Abflugwinkel alpha"
    opt_start, opt_stop = suggested_bounds(base_variant, "alpha_deg")
    st.session_state.optimization_start = float(opt_start)
    st.session_state.optimization_stop = float(opt_stop)
    st.session_state.optimization_resolution = 161


def ensure_state() -> None:
    if "selected_preset_name" not in st.session_state:
        apply_preset("Kugelstoß")
    if "input_mode" not in st.session_state:
        st.session_state.input_mode = "Geschwindigkeit und Winkel"
    if "manual_variants_df" not in st.session_state:
        st.session_state.manual_variants_df = empty_manual_variant_frame()


def current_base_variant() -> VariantConfig:
    if st.session_state.input_mode == "Geschwindigkeit und Winkel":
        v0_m_s = float(st.session_state.base_v0)
        alpha_deg = float(st.session_state.base_alpha)
        vx_m_s, vz_m_s = components_from_polar(v0_m_s, alpha_deg)
        st.session_state.base_vx = float(vx_m_s)
        st.session_state.base_vz = float(vz_m_s)
    else:
        vx_m_s = float(st.session_state.base_vx)
        vz_m_s = float(st.session_state.base_vz)
        v0_m_s, alpha_deg = polar_from_components(vx_m_s, vz_m_s)
        st.session_state.base_v0 = float(v0_m_s)
        st.session_state.base_alpha = float(alpha_deg)

    return VariantConfig(
        label=str(st.session_state.base_label).strip() or "Basisfall",
        v0_m_s=float(st.session_state.base_v0),
        alpha_deg=float(st.session_state.base_alpha),
        h0_m=float(st.session_state.base_h0),
        x0_m=float(st.session_state.base_x0),
        g_m_s2=float(st.session_state.base_g),
    )


def reset_sweep_bounds(base_variant: VariantConfig, state_prefix: str, parameter_key: str) -> None:
    start_value, stop_value = suggested_bounds(base_variant, parameter_key)
    st.session_state[f"{state_prefix}_start"] = float(start_value)
    st.session_state[f"{state_prefix}_stop"] = float(stop_value)


def add_optimization_variant(best_result) -> None:
    best_variant = best_result.variant
    addition = variants_to_frame(
        [
            VariantConfig(
                label="Optimum",
                v0_m_s=best_variant.v0_m_s,
                alpha_deg=best_variant.alpha_deg,
                h0_m=best_variant.h0_m,
                x0_m=best_variant.x0_m,
                g_m_s2=best_variant.g_m_s2,
            )
        ]
    )
    st.session_state.manual_variants_df = pd.concat(
        [st.session_state.manual_variants_df, addition],
        ignore_index=True,
    )


def trajectory_chart(results, base_variant: VariantConfig) -> RenderedChart:
    series_list: list[ChartSeries] = []
    max_z = 0.0
    max_x = 0.0
    min_x = 0.0

    for index, result in enumerate(results):
        color = SERIES_COLORS[index % len(SERIES_COLORS)]
        legend = legend_label(result.variant, base_variant)
        points = list(zip(result.trajectory["x_m"].tolist(), result.trajectory["z_m"].tolist()))
        series_list.append(
            ChartSeries(
                label=legend,
                points=points,
                color=color,
                markers=[(result.variant.x0_m, result.variant.h0_m), (result.landing_x_m, 0.0)],
                line_width=4,
            )
        )
        max_z = max(max_z, float(result.trajectory["z_m"].max()))
        max_x = max(max_x, float(result.trajectory["x_m"].max()))
        min_x = min(min_x, float(result.variant.x0_m) - 0.25)

    return render_xy_chart(
        series_list=series_list,
        title="Überlagerte Flugbahnen",
        x_label="Horizontale Position x [m]",
        y_label="Höhe z [m]",
        x_min=min_x,
        x_max=max_x * 1.03 if max_x > min_x else min_x + 1.0,
        y_min=0.0,
        y_max=max(1.1, max_z * 1.15),
        width=1280,
        height=760,
        show_legend=True,
    )


def optimization_chart(optimization_frame: pd.DataFrame, parameter_key: str, best_result) -> RenderedChart:
    series = ChartSeries(
        label="Optimierungsverlauf",
        points=list(
            zip(
                optimization_frame["parameter_value"].tolist(),
                optimization_frame["flight_distance_m"].tolist(),
            )
        ),
        color=SERIES_COLORS[0],
        markers=[(getattr(best_result.variant, parameter_key), best_result.flight_distance_m)],
        line_width=4,
    )
    x_values = optimization_frame["parameter_value"].tolist()
    y_values = optimization_frame["flight_distance_m"].tolist()
    x_min = min(x_values)
    x_max = max(x_values)
    y_min = min(y_values)
    y_max = max(y_values)

    return render_xy_chart(
        series_list=[series],
        title="Optimierung des Parameters",
        x_label=f"{parameter_label(parameter_key)} [{parameter_unit(parameter_key)}]",
        y_label="Flugweite Delta x [m]",
        x_min=x_min,
        x_max=x_max,
        y_min=max(0.0, y_min - max(0.05, 0.05 * max(y_max - y_min, 1.0))),
        y_max=y_max + max(0.05, 0.05 * max(y_max - y_min, 1.0)),
        width=1040,
        height=520,
        show_legend=False,
    )


def calculation_panel(result, base_variant: VariantConfig) -> None:
    st.subheader("Rechenweg")
    if changed_parameters(result.variant, base_variant):
        st.caption(f"Ausgewählte Kurve: {legend_label(result.variant, base_variant)}")
    else:
        st.caption("Ausgewählte Kurve: Basisfall")

    st.markdown("**1. Allgemeine Modellannahmen**")
    st.latex(r"x(t)=x_0 + v_{0x}t")
    st.latex(r"z(t)=h_0 + v_{0z}t - \frac{1}{2}gt^2")
    st.latex(r"t_{\mathrm{Flug}}=\frac{v_{0z}+\sqrt{v_{0z}^2+2gh_0}}{g}")

    st.markdown("**2. Zerlegung der Anfangsgeschwindigkeit**")
    st.latex(
        rf"v_{{0x}} = v_0 \cos(\alpha) = {result.variant.v0_m_s:.2f}\cos({result.variant.alpha_deg:.2f}^\circ)"
        rf" = {result.vx_m_s:.2f}\,\mathrm{{m/s}}"
    )
    st.latex(
        rf"v_{{0z}} = v_0 \sin(\alpha) = {result.variant.v0_m_s:.2f}\sin({result.variant.alpha_deg:.2f}^\circ)"
        rf" = {result.vz_m_s:.2f}\,\mathrm{{m/s}}"
    )

    st.markdown("**3. Einsetzen in die Ortsfunktionen**")
    st.latex(rf"x(t) = {result.variant.x0_m:.2f} + {result.vx_m_s:.2f}\,t")
    st.latex(
        rf"z(t) = {result.variant.h0_m:.2f} + {result.vz_m_s:.2f}\,t - {0.5 * result.variant.g_m_s2:.3f}\,t^2"
    )
    st.latex(z_of_x_expression(result))

    st.markdown("**4. Flugzeit, Scheitelpunkt und Landung**")
    st.latex(
        rf"t_{{\mathrm{{Flug}}}} = \frac{{{result.vz_m_s:.2f} + \sqrt{{{result.vz_m_s:.2f}^2 + 2 \cdot {result.variant.g_m_s2:.2f} \cdot {result.variant.h0_m:.2f}}}}}{{{result.variant.g_m_s2:.2f}}}"
        rf" = {result.flight_time_s:.3f}\,\mathrm{{s}}"
    )
    st.latex(
        rf"t_{{\mathrm{{Scheitel}}}} = \frac{{v_{{0z}}}}{{g}} = \frac{{{result.vz_m_s:.2f}}}{{{result.variant.g_m_s2:.2f}}}"
        rf" = {result.peak_time_s:.3f}\,\mathrm{{s}}"
    )
    st.latex(rf"z_{{\max}} = {result.peak_height_m:.3f}\,\mathrm{{m}}")
    st.latex(
        rf"x_{{\mathrm{{Landung}}}} = x_0 + v_{{0x}} \cdot t_{{\mathrm{{Flug}}}}"
        rf" = {result.variant.x0_m:.2f} + {result.vx_m_s:.2f} \cdot {result.flight_time_s:.3f}"
        rf" = {result.landing_x_m:.3f}\,\mathrm{{m}}"
    )
    st.latex(
        rf"\Delta x = x_{{\mathrm{{Landung}}}} - x_0 = {result.landing_x_m:.3f} - {result.variant.x0_m:.2f}"
        rf" = {result.flight_distance_m:.3f}\,\mathrm{{m}}"
    )

    st.markdown("**5. Interpretation**")
    st.write(
        "Die horizontale Komponente bestimmt vor allem die Weite, "
        "die vertikale Komponente verlängert die Flugzeit und erhöht den Scheitelpunkt. "
        "Ein größerer Winkel ist deshalb nur so lange sinnvoll, wie der Verlust an Horizontalgeschwindigkeit "
        "nicht überwiegt."
    )


def main() -> None:
    st.set_page_config(page_title="Flugbahn-Modellierer", layout="wide")
    ensure_state()

    st.title("Flugbahn-Modellierer für Weitsprung und Kugelstoß")
    st.caption(
        "Didaktische Vergleichs-App mit Basisfall, Variantenüberlagerung, Optimierung und transparentem Rechenweg."
    )

    with st.sidebar:
        st.subheader("Voreinstellung")
        st.selectbox(
            "Sportart / Beispiel",
            options=list(PRESETS.keys()),
            key="selected_preset_name",
        )
        if st.button("Voreinstellung laden", use_container_width=True):
            apply_preset(st.session_state.selected_preset_name)

        preset = PRESETS[st.session_state.selected_preset_name]
        st.info(preset.description)
        st.caption(preset.source_note)

        st.subheader("Modellannahmen")
        st.markdown(
            "- Luftwiderstand wird vernachlässigt.\n"
            "- Der Körper bzw. das Gerät wird als Punktmasse modelliert.\n"
            "- Die Landefläche liegt bei z = 0."
        )

    input_col, calculation_col = st.columns([1.15, 0.95])

    with input_col:
        st.subheader("Basisfall")
        st.text_input("Bezeichnung", key="base_label")
        st.radio(
            "Eingabeart",
            options=("Geschwindigkeit und Winkel", "Horizontale und vertikale Komponenten"),
            horizontal=True,
            key="input_mode",
        )

        if st.session_state.input_mode == "Geschwindigkeit und Winkel":
            st.number_input(
                "Abfluggeschwindigkeit v0 [m/s]",
                min_value=0.0,
                step=0.1,
                key="base_v0",
            )
            st.number_input(
                "Abflugwinkel alpha [deg]",
                min_value=-10.0,
                max_value=85.0,
                step=0.5,
                key="base_alpha",
            )
        else:
            st.number_input("Horizontalkomponente v0x [m/s]", step=0.1, key="base_vx")
            st.number_input("Vertikalkomponente v0z [m/s]", step=0.1, key="base_vz")

        st.number_input("Abflughöhe h0 [m]", min_value=0.0, step=0.01, key="base_h0")
        st.number_input("Startversatz x0 [m]", step=0.01, key="base_x0")
        st.number_input("Erdbeschleunigung g [m/s²]", min_value=0.1, step=0.01, key="base_g")

        base_variant = current_base_variant()
        st.caption(
            f"Aktuelle Zerlegung: v0x = {st.session_state.base_vx:.2f} m/s, "
            f"v0z = {st.session_state.base_vz:.2f} m/s."
        )

        st.divider()
        st.subheader("Varianten automatisch erzeugen")
        st.selectbox(
            "Zu variierender Parameter",
            options=list(PARAMETER_CHOICES.keys()),
            key="sweep_parameter_display",
        )
        sweep_parameter_key = PARAMETER_CHOICES[st.session_state.sweep_parameter_display]
        sweep_hint_col, sweep_button_col = st.columns([1.7, 1.0])
        if sweep_button_col.button("Bereich vorschlagen", use_container_width=True):
            reset_sweep_bounds(base_variant, "sweep", sweep_parameter_key)
        sweep_hint_col.caption(
            f"Parameter: {parameter_label(sweep_parameter_key)} [{parameter_unit(sweep_parameter_key)}]"
        )
        st.number_input("Startwert", step=parameter_step(sweep_parameter_key), key="sweep_start")
        st.number_input("Endwert", step=parameter_step(sweep_parameter_key), key="sweep_stop")
        st.slider("Anzahl Vergleichskurven", min_value=2, max_value=12, key="sweep_curve_count")
        st.radio(
            "Sweep in Variantenliste",
            options=("ersetzen", "anhängen"),
            horizontal=True,
            key="sweep_mode",
        )
        if st.button("Sweep in Variantenliste übernehmen", use_container_width=True):
            sweep_variants = build_sweep_variants(
                base_variant=base_variant,
                parameter_key=sweep_parameter_key,
                start_value=float(st.session_state.sweep_start),
                stop_value=float(st.session_state.sweep_stop),
                curve_count=int(st.session_state.sweep_curve_count),
                label_prefix="Sweep",
            )
            sweep_frame = variants_to_frame(sweep_variants)
            if st.session_state.sweep_mode == "ersetzen":
                st.session_state.manual_variants_df = sweep_frame
            else:
                st.session_state.manual_variants_df = pd.concat(
                    [st.session_state.manual_variants_df, sweep_frame],
                    ignore_index=True,
                )

        st.divider()
        st.subheader("Manuelle Vergleichsvarianten")
        if st.button("Variantenliste leeren", use_container_width=True):
            st.session_state.manual_variants_df = empty_manual_variant_frame()

        editor_frame = st.data_editor(
            st.session_state.manual_variants_df,
            use_container_width=True,
            hide_index=True,
            num_rows="dynamic",
            column_config={
                "label": st.column_config.TextColumn("Label"),
                "v0_m_s": st.column_config.NumberColumn("v0 [m/s]", format="%.2f"),
                "alpha_deg": st.column_config.NumberColumn("alpha [deg]", format="%.2f"),
                "h0_m": st.column_config.NumberColumn("h0 [m]", format="%.2f"),
                "x0_m": st.column_config.NumberColumn("x0 [m]", format="%.2f"),
                "g_m_s2": st.column_config.NumberColumn("g [m/s²]", format="%.2f"),
            },
        )
        st.session_state.manual_variants_df = editor_frame

    manual_variants = frame_to_variants(st.session_state.manual_variants_df)
    all_variants = deduplicate_variants([base_variant, *manual_variants])
    results = [evaluate_variant(variant) for variant in all_variants]
    summary_frame = summary_dataframe(results, base_variant)
    summary_display = summary_frame.round(
        {
            "v0 [m/s]": 2,
            "alpha [deg]": 2,
            "h0 [m]": 2,
            "x0 [m]": 2,
            "Flugzeit [s]": 3,
            "Flugweite Delta x [m]": 3,
            "Landepunkt x [m]": 3,
            "Scheitelhöhe [m]": 3,
        }
    )

    with calculation_col:
        st.subheader("Optimierung")
        st.selectbox(
            "Optimierungsparameter",
            options=list(OPTIMIZATION_CHOICES.keys()),
            key="optimization_parameter_display",
        )
        optimization_parameter_key = OPTIMIZATION_CHOICES[st.session_state.optimization_parameter_display]
        opt_hint_col, opt_button_col = st.columns([1.7, 1.0])
        if opt_button_col.button("Optimierungsbereich vorschlagen", use_container_width=True):
            reset_sweep_bounds(base_variant, "optimization", optimization_parameter_key)
        opt_hint_col.caption(
            f"Parameter: {parameter_label(optimization_parameter_key)} [{parameter_unit(optimization_parameter_key)}]"
        )
        st.number_input(
            "Optimierung Start",
            step=parameter_step(optimization_parameter_key),
            key="optimization_start",
        )
        st.number_input(
            "Optimierung Ende",
            step=parameter_step(optimization_parameter_key),
            key="optimization_stop",
        )
        st.slider(
            "Auflösung der Suche",
            min_value=31,
            max_value=401,
            step=10,
            key="optimization_resolution",
        )

        optimization_frame, best_result = optimization_dataframe(
            base_variant=base_variant,
            parameter_key=optimization_parameter_key,
            start_value=float(st.session_state.optimization_start),
            stop_value=float(st.session_state.optimization_stop),
            resolution=int(st.session_state.optimization_resolution),
        )

        st.metric(
            "Bestes Ergebnis",
            f"{best_result.flight_distance_m:.3f} m",
            delta=(
                f"{parameter_label(optimization_parameter_key)} = "
                f"{getattr(best_result.variant, optimization_parameter_key):.3f} "
                f"{parameter_unit(optimization_parameter_key)}"
            ),
        )
        opt_chart = optimization_chart(
            optimization_frame=optimization_frame,
            parameter_key=optimization_parameter_key,
            best_result=best_result,
        )
        st.image(opt_chart.png_bytes, use_container_width=True)
        if st.button("Optimum als Vergleichskurve hinzufügen", use_container_width=True):
            add_optimization_variant(best_result)
            st.rerun()

        st.divider()
        calculation_target_label = st.selectbox(
            "Rechenweg anzeigen für",
            options=[legend_label(result.variant, base_variant) for result in results],
            index=0,
        )
        selected_result = next(
            result
            for result in results
            if legend_label(result.variant, base_variant) == calculation_target_label
        )
        calculation_panel(selected_result, base_variant)

    st.divider()
    plot_col, table_col = st.columns([1.25, 0.95])

    with plot_col:
        trajectory_chart_export = trajectory_chart(results, base_variant)
        st.image(trajectory_chart_export.png_bytes, use_container_width=True)
        export_col_png, export_col_svg, export_col_csv = st.columns(3)
        export_col_png.download_button(
            "Grafik als PNG",
            data=trajectory_chart_export.png_bytes,
            file_name="flugbahnen_vergleich.png",
            mime="image/png",
            use_container_width=True,
        )
        export_col_svg.download_button(
            "Grafik als SVG",
            data=trajectory_chart_export.svg_bytes,
            file_name="flugbahnen_vergleich.svg",
            mime="image/svg+xml",
            use_container_width=True,
        )
        export_col_csv.download_button(
            "Daten als CSV",
            data=combined_trajectory_dataframe(results, base_variant).to_csv(index=False).encode("utf-8"),
            file_name="flugbahnen_vergleich.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with table_col:
        st.subheader("Kennwerte")
        st.dataframe(
            summary_display,
            use_container_width=True,
            hide_index=True,
        )
        st.caption(
            "Die Legende nennt immer die geänderten Parameter gegenüber dem Basisfall. "
            "Dadurch lässt sich direkt erkennen, welche Kurve durch welche Variation entstanden ist."
        )


if __name__ == "__main__":
    main()

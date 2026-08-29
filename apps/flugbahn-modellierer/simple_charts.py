from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
from io import BytesIO

import numpy as np
from PIL import Image, ImageDraw, ImageFont


SERIES_COLORS = [
    "#1f77b4",
    "#d62728",
    "#2ca02c",
    "#ff7f0e",
    "#9467bd",
    "#8c564b",
    "#17becf",
    "#bcbd22",
]


@dataclass(slots=True)
class ChartSeries:
    label: str
    points: list[tuple[float, float]]
    color: str
    markers: list[tuple[float, float]] = field(default_factory=list)
    line_width: int = 3


@dataclass(slots=True)
class RenderedChart:
    png_bytes: bytes
    svg_bytes: bytes


def _load_font(size: int) -> ImageFont.ImageFont:
    for font_name in ("arial.ttf", "calibri.ttf", "segoeui.ttf"):
        try:
            return ImageFont.truetype(font_name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _tick_values(min_value: float, max_value: float, count: int = 6) -> list[float]:
    if abs(max_value - min_value) < 1e-12:
        return [min_value]
    return [float(value) for value in np.linspace(min_value, max_value, num=max(2, count))]


def _tick_label(value: float) -> str:
    if abs(value) >= 10:
        return f"{value:.1f}"
    if abs(value) >= 1:
        return f"{value:.2f}"
    return f"{value:.3f}"


def _scale(value: float, data_min: float, data_max: float, pixel_min: float, pixel_max: float) -> float:
    if abs(data_max - data_min) < 1e-12:
        return (pixel_min + pixel_max) / 2.0
    return pixel_min + (value - data_min) / (data_max - data_min) * (pixel_max - pixel_min)


def render_xy_chart(
    series_list: list[ChartSeries],
    title: str,
    x_label: str,
    y_label: str,
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
    width: int = 1100,
    height: int = 650,
    show_legend: bool = True,
) -> RenderedChart:
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)

    font_title = _load_font(28)
    font_axis = _load_font(20)
    font_tick = _load_font(16)
    font_legend = _load_font(16)

    margin_left = 110
    margin_right = 320 if show_legend else 50
    margin_top = 90
    margin_bottom = 95

    plot_left = margin_left
    plot_top = margin_top
    plot_right = width - margin_right
    plot_bottom = height - margin_bottom
    plot_width = plot_right - plot_left
    plot_height = plot_bottom - plot_top

    title_width, _ = _text_size(draw, title, font_title)
    draw.text(((width - title_width) / 2.0, 24), title, fill="#111111", font=font_title)
    draw.text((plot_left, margin_top - 38), y_label, fill="#222222", font=font_axis)

    x_label_width, x_label_height = _text_size(draw, x_label, font_axis)
    draw.text(
        ((plot_left + plot_right - x_label_width) / 2.0, plot_bottom + 42 - x_label_height / 2.0),
        x_label,
        fill="#222222",
        font=font_axis,
    )

    x_ticks = _tick_values(x_min, x_max)
    y_ticks = _tick_values(y_min, y_max)

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{width / 2:.1f}" y="42" text-anchor="middle" font-family="Arial, sans-serif" font-size="28" fill="#111111">{escape(title)}</text>',
        f'<text x="{plot_left}" y="{margin_top - 16}" font-family="Arial, sans-serif" font-size="20" fill="#222222">{escape(y_label)}</text>',
        f'<text x="{(plot_left + plot_right) / 2:.1f}" y="{plot_bottom + 66}" text-anchor="middle" font-family="Arial, sans-serif" font-size="20" fill="#222222">{escape(x_label)}</text>',
    ]

    for tick in x_ticks:
        x_pixel = _scale(tick, x_min, x_max, plot_left, plot_right)
        draw.line((x_pixel, plot_top, x_pixel, plot_bottom), fill="#e3e7eb", width=1)
        svg_parts.append(
            f'<line x1="{x_pixel:.1f}" y1="{plot_top}" x2="{x_pixel:.1f}" y2="{plot_bottom}" stroke="#e3e7eb" stroke-width="1"/>'
        )
        tick_text = _tick_label(tick)
        tick_width, _ = _text_size(draw, tick_text, font_tick)
        draw.text((x_pixel - tick_width / 2.0, plot_bottom + 10), tick_text, fill="#444444", font=font_tick)
        svg_parts.append(
            f'<text x="{x_pixel:.1f}" y="{plot_bottom + 28}" text-anchor="middle" font-family="Arial, sans-serif" font-size="16" fill="#444444">{escape(tick_text)}</text>'
        )

    for tick in y_ticks:
        y_pixel = _scale(tick, y_min, y_max, plot_bottom, plot_top)
        draw.line((plot_left, y_pixel, plot_right, y_pixel), fill="#e3e7eb", width=1)
        svg_parts.append(
            f'<line x1="{plot_left}" y1="{y_pixel:.1f}" x2="{plot_right}" y2="{y_pixel:.1f}" stroke="#e3e7eb" stroke-width="1"/>'
        )
        tick_text = _tick_label(tick)
        tick_width, tick_height = _text_size(draw, tick_text, font_tick)
        draw.text((plot_left - tick_width - 12, y_pixel - tick_height / 2.0), tick_text, fill="#444444", font=font_tick)
        svg_parts.append(
            f'<text x="{plot_left - 14}" y="{y_pixel + 6:.1f}" text-anchor="end" font-family="Arial, sans-serif" font-size="16" fill="#444444">{escape(tick_text)}</text>'
        )

    draw.rectangle((plot_left, plot_top, plot_right, plot_bottom), outline="#666666", width=2)
    svg_parts.append(
        f'<rect x="{plot_left}" y="{plot_top}" width="{plot_width}" height="{plot_height}" fill="none" stroke="#666666" stroke-width="2"/>'
    )

    for series in series_list:
        pixel_points = [
            (
                _scale(x_value, x_min, x_max, plot_left, plot_right),
                _scale(y_value, y_min, y_max, plot_bottom, plot_top),
            )
            for x_value, y_value in series.points
        ]
        if len(pixel_points) >= 2:
            draw.line(pixel_points, fill=series.color, width=series.line_width)
            path_commands = " ".join(
                f'{"M" if index == 0 else "L"} {x_pixel:.2f} {y_pixel:.2f}'
                for index, (x_pixel, y_pixel) in enumerate(pixel_points)
            )
            svg_parts.append(
                f'<path d="{path_commands}" fill="none" stroke="{series.color}" stroke-width="{series.line_width}" stroke-linejoin="round" stroke-linecap="round"/>'
            )
        for x_value, y_value in series.markers:
            x_pixel = _scale(x_value, x_min, x_max, plot_left, plot_right)
            y_pixel = _scale(y_value, y_min, y_max, plot_bottom, plot_top)
            draw.ellipse((x_pixel - 5, y_pixel - 5, x_pixel + 5, y_pixel + 5), fill=series.color, outline="white", width=1)
            svg_parts.append(
                f'<circle cx="{x_pixel:.2f}" cy="{y_pixel:.2f}" r="5" fill="{series.color}" stroke="white" stroke-width="1"/>'
            )

    if show_legend:
        legend_x = plot_right + 32
        legend_y = plot_top + 10
        draw.text((legend_x, legend_y - 30), "Legende", fill="#111111", font=font_axis)
        svg_parts.append(
            f'<text x="{legend_x}" y="{legend_y - 10}" font-family="Arial, sans-serif" font-size="20" fill="#111111">Legende</text>'
        )
        for index, series in enumerate(series_list):
            item_y = legend_y + index * 28
            draw.line((legend_x, item_y, legend_x + 24, item_y), fill=series.color, width=4)
            draw.text((legend_x + 34, item_y - 10), series.label, fill="#222222", font=font_legend)
            svg_parts.append(
                f'<line x1="{legend_x}" y1="{item_y}" x2="{legend_x + 24}" y2="{item_y}" stroke="{series.color}" stroke-width="4"/>'
            )
            svg_parts.append(
                f'<text x="{legend_x + 34}" y="{item_y + 6}" font-family="Arial, sans-serif" font-size="16" fill="#222222">{escape(series.label)}</text>'
            )

    png_buffer = BytesIO()
    image.save(png_buffer, format="PNG")
    png_bytes = png_buffer.getvalue()

    svg_parts.append("</svg>")
    svg_bytes = "\n".join(svg_parts).encode("utf-8")
    return RenderedChart(png_bytes=png_bytes, svg_bytes=svg_bytes)

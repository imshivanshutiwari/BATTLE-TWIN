"""MEDEVAC + Sensors page — VIZ 20-22."""

from dash import html, dcc
import plotly.graph_objects as go
from dashboard.theme import NVG_THEME, PANEL_STYLE, HEADER_STYLE, PLOTLY_TEMPLATE
import numpy as np


def create_medevac_map():
    fig = go.Figure()
    fig.add_trace(
        go.Scattermapbox(
            lat=[34.15, 34.22],
            lon=[-117.35, -117.28],
            text=["URGENT-LZ1", "PRIORITY-LZ2"],
            mode="markers+text",
            marker=dict(size=14, color=[NVG_THEME["hostile"], "#ff6600"]),
            textposition="top right",
        )
    )
    fig.update_layout(
        **PLOTLY_TEMPLATE,
        mapbox_style="carto-darkmatter",
        mapbox=dict(center=dict(lat=34.18, lon=-117.32), zoom=11),
        height=300,
        title="MEDEVAC REQUESTS"
    )
    return dcc.Graph(figure=fig, id="med-map", style={"height": "300px"})


def create_sensor_fusion_timeline():
    fig = go.Figure()
    t = np.arange(100)
    fig.add_trace(
        go.Scatter(x=t, y=np.sin(t * 0.1) * 5, name="Roll°", line=dict(color=NVG_THEME["accent"]))
    )
    fig.add_trace(
        go.Scatter(
            x=t, y=np.cos(t * 0.08) * 3, name="Pitch°", line=dict(color=NVG_THEME["friendly"])
        )
    )
    fig.add_trace(
        go.Scatter(
            x=t, y=np.cumsum(np.random.normal(0, 0.5, 100)), name="Yaw°", line=dict(color="#ffcc00")
        )
    )
    fig.update_layout(**PLOTLY_TEMPLATE, height=200, title="SENSOR FUSION — IMU")
    return dcc.Graph(figure=fig, id="med-sensor", style={"height": "200px"})


def create_sync_status():
    fig = go.Figure()
    fig.add_trace(
        go.Indicator(
            mode="number+delta",
            value=47,
            delta=dict(reference=50),
            title=dict(text="msgs/sec"),
            number=dict(font=dict(color=NVG_THEME["accent"])),
            domain=dict(row=0, column=0),
        )
    )
    fig.add_trace(
        go.Indicator(
            mode="number",
            value=12,
            title=dict(text="latency ms"),
            number=dict(font=dict(color=NVG_THEME["friendly"])),
            domain=dict(row=0, column=1),
        )
    )
    fig.add_trace(
        go.Indicator(
            mode="number",
            value=0.3,
            title=dict(text="divergence m"),
            number=dict(font=dict(color=NVG_THEME["accent"])),
            domain=dict(row=0, column=2),
        )
    )
    fig.update_layout(
        **PLOTLY_TEMPLATE, height=150, title="DIGITAL TWIN SYNC", grid=dict(rows=1, columns=3)
    )
    return dcc.Graph(figure=fig, id="med-sync", style={"height": "150px"})


def medevac_page_layout():
    return html.Div(
        [
            html.H5("MEDEVAC & SENSORS", style=HEADER_STYLE),
            create_medevac_map(),
            html.Div(
                style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "8px"},
                children=[
                    html.Div([create_sensor_fusion_timeline()], style=PANEL_STYLE),
                    html.Div([create_sync_status()], style=PANEL_STYLE),
                ],
            ),
        ]
    )

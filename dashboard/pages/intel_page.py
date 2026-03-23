"""Intelligence page — VIZ 06-09."""

from dash import html, dcc
import plotly.graph_objects as go
from dashboard.theme import NVG_THEME, PANEL_STYLE, HEADER_STYLE, PLOTLY_TEMPLATE
import numpy as np


def create_intel_map():
    fig = go.Figure()
    fig.update_layout(
        **PLOTLY_TEMPLATE,
        mapbox_style="carto-darkmatter",
        mapbox=dict(center=dict(lat=34.25, lon=-117.25), zoom=10),
        height=350,
        title="INTEL OVERLAY — CONTACTS"
    )
    return dcc.Graph(figure=fig, id="intel-map", style={"height": "350px"})


def create_threat_heatmap():
    rng = np.random.default_rng(42)
    z = rng.uniform(0, 0.8, (20, 20))
    z[8:12, 8:12] = rng.uniform(0.6, 1.0, (4, 4))
    fig = go.Figure(
        go.Heatmap(
            z=z,
            colorscale=[[0, "#003300"], [0.5, "#ffcc00"], [1, "#ff3333"]],
            showscale=True,
            colorbar=dict(title="Threat"),
        )
    )
    fig.update_layout(**PLOTLY_TEMPLATE, height=250, title="THREAT ASSESSMENT HEATMAP")
    return dcc.Graph(figure=fig, id="intel-threat-hm", style={"height": "250px"})


def create_contact_timeline():
    fig = go.Figure()
    contacts = ["RED-01", "RED-02", "RED-03", "RED-04", "RED-05"]
    for i, c in enumerate(contacts):
        fig.add_trace(
            go.Bar(
                y=[c], x=[3 + i * 0.5], orientation="h", name=c, marker_color=NVG_THEME["hostile"]
            )
        )
    fig.update_layout(
        **PLOTLY_TEMPLATE,
        height=200,
        title="CONTACT TIMELINE (6H)",
        xaxis_title="Hours",
        barmode="stack"
    )
    return dcc.Graph(figure=fig, id="intel-timeline", style={"height": "200px"})


def create_pattern_of_life():
    fig = go.Figure()
    rng = np.random.default_rng(123)
    lats = 34.2 + rng.normal(0, 0.05, 50)
    lons = -117.2 + rng.normal(0, 0.05, 50)
    fig.add_trace(
        go.Scattermapbox(
            lat=lats,
            lon=lons,
            mode="markers",
            marker=dict(size=5, color=NVG_THEME["accent"], opacity=0.6),
        )
    )
    fig.update_layout(
        **PLOTLY_TEMPLATE,
        mapbox_style="carto-darkmatter",
        mapbox=dict(center=dict(lat=34.2, lon=-117.2), zoom=11),
        height=250,
        title="PATTERN OF LIFE — ADS-B"
    )
    return dcc.Graph(figure=fig, id="intel-pol", style={"height": "250px"})


def intel_page_layout():
    return html.Div(
        [
            html.H5("INTELLIGENCE PICTURE", style=HEADER_STYLE),
            create_intel_map(),
            html.Div(
                style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "8px"},
                children=[
                    html.Div([create_threat_heatmap()], style=PANEL_STYLE),
                    html.Div([create_contact_timeline()], style=PANEL_STYLE),
                ],
            ),
            create_pattern_of_life(),
        ]
    )

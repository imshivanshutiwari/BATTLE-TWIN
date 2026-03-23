"""C2 Main operations page — VIZ 01-05."""

from dash import html, dcc
import plotly.graph_objects as go
from dashboard.theme import NVG_THEME, PANEL_STYLE, HEADER_STYLE, PLOTLY_TEMPLATE


def create_tac_map():
    fig = go.Figure()
    fig.update_layout(
        **PLOTLY_TEMPLATE,
        height=400,
        mapbox_style="carto-darkmatter",
        mapbox=dict(center=dict(lat=34.25, lon=-117.25), zoom=10),
        title="TACTICAL MAP — MGRS OVERLAY",
    )
    return dcc.Graph(
        figure=fig, id="c2-tac-map", config={"displayModeBar": False}, style={"height": "400px"}
    )


def create_force_status():
    fig = go.Figure()
    units = [f"WARHORSE-{i}" for i in range(1, 13)]
    metrics = ["STR%", "AMMO%", "FUEL%", "WATER%", "COMMS"]
    fig.add_trace(
        go.Heatmap(
            z=[
                [85, 70, 90, 80, 1],
                [75, 60, 85, 75, 1],
                [90, 80, 95, 85, 1],
                [65, 50, 70, 60, 0],
                [80, 75, 80, 70, 1],
                [70, 65, 75, 65, 1],
                [85, 80, 90, 80, 1],
                [60, 45, 65, 55, 0],
                [95, 90, 95, 90, 1],
                [70, 60, 75, 70, 1],
                [80, 70, 85, 80, 1],
                [75, 65, 80, 75, 1],
            ],
            x=metrics,
            y=units,
            colorscale=[[0, "#ff3333"], [0.5, "#ffcc00"], [1, "#00ff41"]],
            showscale=False,
        )
    )
    fig.update_layout(**PLOTLY_TEMPLATE, height=300, title="FORCE STATUS MATRIX")
    return dcc.Graph(figure=fig, id="c2-force-status", style={"height": "300px"})


def create_threat_gauges():
    fig = go.Figure()
    for i in range(4):
        fig.add_trace(
            go.Indicator(
                mode="gauge+number",
                value=30 + i * 15,
                gauge=dict(
                    axis=dict(range=[0, 100]),
                    bar=dict(
                        color=NVG_THEME["threat"] if 30 + i * 15 > 70 else NVG_THEME["accent"]
                    ),
                    bgcolor=NVG_THEME["bg"],
                ),
                domain=dict(row=0, column=i),
                title=dict(text=f"U-{i+1}"),
            )
        )
    fig.update_layout(**PLOTLY_TEMPLATE, height=150, grid=dict(rows=1, columns=4))
    return dcc.Graph(figure=fig, id="c2-threat-gauges", style={"height": "150px"})


def create_nats_flow():
    fig = go.Figure(
        go.Sankey(
            node=dict(
                label=["Sensors", "Twin", "Agents", "Dashboard", "UE5"],
                color=[NVG_THEME["accent"]] * 5,
            ),
            link=dict(
                source=[0, 1, 1, 2, 2],
                target=[1, 2, 3, 3, 4],
                value=[100, 80, 50, 60, 40],
                color=NVG_THEME["grid"],
            ),
        )
    )
    fig.update_layout(**PLOTLY_TEMPLATE, height=200, title="NATS MESSAGE FLOW")
    return dcc.Graph(figure=fig, id="c2-nats-flow", style={"height": "200px"})


def create_alert_log():
    return html.Div(
        id="c2-alert-log",
        style={**PANEL_STYLE, "maxHeight": "200px", "overflowY": "auto"},
        children=[
            html.Div(
                "[FLASH] B01 PROXIMITY — Enemy within 2km",
                style={"color": "#ff6600", "fontSize": "9px"},
            ),
            html.Div(
                "[PRIORITY] B03 SUPPLY — Ammo critical",
                style={"color": "#00ccff", "fontSize": "9px"},
            ),
            html.Div("[ROUTINE] NATS sync healthy", style={"color": "#888", "fontSize": "9px"}),
        ],
    )


def c2_main_layout():
    return html.Div(
        [
            html.H5("C2 MAIN — OPERATIONS CENTER", style=HEADER_STYLE),
            create_tac_map(),
            create_force_status(),
            html.Div(
                style={"display": "grid", "gridTemplateColumns": "1fr 1fr 1fr", "gap": "8px"},
                children=[
                    html.Div(
                        [html.H6("THREAT GAUGES", style=HEADER_STYLE), create_threat_gauges()],
                        style=PANEL_STYLE,
                    ),
                    html.Div(
                        [html.H6("NATS FLOW", style=HEADER_STYLE), create_nats_flow()],
                        style=PANEL_STYLE,
                    ),
                    html.Div(
                        [html.H6("ALERT LOG", style=HEADER_STYLE), create_alert_log()],
                        style=PANEL_STYLE,
                    ),
                ],
            ),
        ]
    )

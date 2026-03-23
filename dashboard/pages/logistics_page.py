"""Logistics status page — VIZ 13-15."""
from dash import html, dcc
import plotly.graph_objects as go
from dashboard.theme import NVG_THEME, PANEL_STYLE, HEADER_STYLE, PLOTLY_TEMPLATE


def create_supply_dashboard():
    fig = go.Figure()
    units = [f"B{i:02d}" for i in range(1,7)]
    classes = ["CL-I","CL-III","CL-V","CL-VIII"]
    for j, cl in enumerate(classes):
        vals = [80-j*10-i*5 for i in range(6)]
        fig.add_trace(go.Bar(name=cl, x=units, y=vals,
                             marker_color=[NVG_THEME["accent"],NVG_THEME["friendly"],"#ffcc00",NVG_THEME["hostile"]][j]))
    fig.update_layout(**PLOTLY_TEMPLATE, height=250, title="SUPPLY STATUS BY CLASS", barmode="group")
    return dcc.Graph(figure=fig, id="log-supply", style={"height":"250px"})


def create_logistics_route_map():
    fig = go.Figure()
    fig.update_layout(**PLOTLY_TEMPLATE, mapbox_style="carto-darkmatter",
                      mapbox=dict(center=dict(lat=34.15,lon=-117.35),zoom=10),
                      height=300, title="VRP CONVOY ROUTES")
    return dcc.Graph(figure=fig, id="log-route-map", style={"height":"300px"})


def create_vrp_viz():
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=["Route 1","Route 2","Route 3"],y=[45,62,38],
                             mode="lines+markers",name="Distance (km)",
                             line=dict(color=NVG_THEME["accent"])))
    fig.add_trace(go.Scatter(x=["Route 1","Route 2","Route 3"],y=[90,120,75],
                             mode="lines+markers",name="Time (min)",
                             line=dict(color=NVG_THEME["friendly"]),yaxis="y2"))
    fig.update_layout(**PLOTLY_TEMPLATE, height=200, title="VRP OPTIMIZATION",
                      yaxis2=dict(overlaying="y",side="right",gridcolor=NVG_THEME["grid"]))
    return dcc.Graph(figure=fig, id="log-vrp", style={"height":"200px"})


def logistics_page_layout():
    return html.Div([
        html.H5("LOGISTICS & SUSTAINMENT", style=HEADER_STYLE),
        create_supply_dashboard(),
        html.Div(style={"display":"grid","gridTemplateColumns":"1fr 1fr","gap":"8px"}, children=[
            html.Div([create_logistics_route_map()], style=PANEL_STYLE),
            html.Div([create_vrp_viz()], style=PANEL_STYLE),
        ]),
    ])

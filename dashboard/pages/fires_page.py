"""Fire support page — VIZ 10-12."""
from dash import html, dcc
import plotly.graph_objects as go
from dashboard.theme import NVG_THEME, PANEL_STYLE, HEADER_STYLE, PLOTLY_TEMPLATE


def create_fire_support_map():
    fig = go.Figure()
    fig.update_layout(**PLOTLY_TEMPLATE, mapbox_style="carto-darkmatter",
                      mapbox=dict(center=dict(lat=34.25,lon=-117.25),zoom=10),
                      height=350, title="FIRE SUPPORT COORDINATION")
    return dcc.Graph(figure=fig, id="fires-map", style={"height":"350px"})


def create_fire_mission_timeline():
    fig = go.Figure()
    missions = ["FM-001","FM-002","FM-003"]
    phases = ["REQUEST","CLEAR","FIRE","ASSESS"]
    colors = [NVG_THEME["accent"],NVG_THEME["friendly"],"#ffcc00",NVG_THEME["hostile"]]
    for i, m in enumerate(missions):
        for j, p in enumerate(phases):
            fig.add_trace(go.Bar(y=[m],x=[2],orientation='h',name=p if i==0 else None,
                                marker_color=colors[j],showlegend=i==0))
    fig.update_layout(**PLOTLY_TEMPLATE,height=200,title="FIRE MISSION STATUS",barmode="stack")
    return dcc.Graph(figure=fig,id="fires-timeline",style={"height":"200px"})


def create_weather_fires():
    fig = go.Figure()
    fig.add_trace(go.Barpolar(r=[5,8,12,7,3],theta=["N","NE","E","SE","S"],
                               marker_color=NVG_THEME["accent"],opacity=0.7))
    fig.update_layout(**PLOTLY_TEMPLATE,height=200,title="WIND IMPACT ON FIRES",
                      polar=dict(bgcolor=NVG_THEME["bg"],
                                 radialaxis=dict(gridcolor=NVG_THEME["grid"]),
                                 angularaxis=dict(gridcolor=NVG_THEME["grid"])))
    return dcc.Graph(figure=fig,id="fires-weather",style={"height":"200px"})


def fires_page_layout():
    return html.Div([
        html.H5("FIRE SUPPORT",style=HEADER_STYLE),
        create_fire_support_map(),
        html.Div(style={"display":"grid","gridTemplateColumns":"1fr 1fr","gap":"8px"},children=[
            html.Div([create_fire_mission_timeline()],style=PANEL_STYLE),
            html.Div([create_weather_fires()],style=PANEL_STYLE),
        ]),
    ])

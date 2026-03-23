"""Map-related callbacks for tactical map updates."""
from dash import Input, Output, State
import plotly.graph_objects as go
from dashboard.theme import NVG_THEME, PLOTLY_TEMPLATE


def register_map_callbacks(app, get_state_fn=None):
    """Register callbacks for tactical map updates."""

    @app.callback(Output("c2-tac-map", "figure", allow_duplicate=True),
                  Input("update-interval", "n_intervals"), prevent_initial_call=True)
    def update_tactical_map(_):
        fig = go.Figure()
        state = get_state_fn() if get_state_fn else None
        if state:
            f_lats = [u.lat for u in state.units.values()]
            f_lons = [u.lon for u in state.units.values()]
            f_names = [u.callsign for u in state.units.values()]
            fig.add_trace(go.Scattermapbox(lat=f_lats, lon=f_lons, text=f_names,
                marker=dict(size=12, color=NVG_THEME["friendly"], symbol="circle"),
                mode="markers+text", name="FRIENDLY", textposition="top right",
                textfont=dict(color=NVG_THEME["friendly"], size=8)))
            h_lats = [c.lat for c in state.contacts.values()]
            h_lons = [c.lon for c in state.contacts.values()]
            h_names = [c.callsign for c in state.contacts.values()]
            fig.add_trace(go.Scattermapbox(lat=h_lats, lon=h_lons, text=h_names,
                marker=dict(size=10, color=NVG_THEME["hostile"]),
                mode="markers+text", name="HOSTILE", textposition="top right",
                textfont=dict(color=NVG_THEME["hostile"], size=8)))
        fig.update_layout(**PLOTLY_TEMPLATE, mapbox_style="carto-darkmatter",
                          mapbox=dict(center=dict(lat=34.25, lon=-117.25), zoom=10), height=400)
        return fig

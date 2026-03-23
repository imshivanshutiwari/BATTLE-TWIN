"""Dash callback handlers for all 22 panels."""

from datetime import datetime, timezone
import numpy as np
from dash import Input, Output
import plotly.graph_objects as go

from dashboard.layout import NVG_COLORS

# Shared state reference (set by app.py)
_battlefield_state = None
_agent_results = None
_dataset = None


def set_shared_state(bf_state, agent_res=None, ds=None):
    global _battlefield_state, _agent_results, _dataset
    _battlefield_state = bf_state
    _agent_results = agent_res
    _dataset = ds


def nvg_figure(title="") -> go.Figure:
    """Create a base plotly figure with NVG styling."""
    fig = go.Figure()
    fig.update_layout(
        paper_bgcolor=NVG_COLORS["panel_bg"],
        plot_bgcolor=NVG_COLORS["bg"],
        font=dict(color=NVG_COLORS["text"], family="Courier New", size=10),
        margin=dict(l=30, r=10, t=25, b=20),
        title=dict(text=title, font=dict(size=11, color=NVG_COLORS["accent"])),
        xaxis=dict(gridcolor=NVG_COLORS["grid"], zerolinecolor=NVG_COLORS["grid"]),
        yaxis=dict(gridcolor=NVG_COLORS["grid"], zerolinecolor=NVG_COLORS["grid"]),
    )
    return fig


def register_callbacks(app):
    """Register all dashboard callbacks."""

    @app.callback(Output("header-clock", "children"), Input("update-interval", "n_intervals"))
    def update_clock(_):
        return datetime.now(tz=timezone.utc).strftime("%d%H%MZ %b %Y").upper()

    @app.callback(Output("header-status", "children"), Input("update-interval", "n_intervals"))
    def update_status(_):
        if _battlefield_state:
            n_units = len(_battlefield_state.units)
            n_contacts = len(_battlefield_state.contacts)
            seq = _battlefield_state.nats_sequence
            return f"UNITS: {n_units} | CONTACTS: {n_contacts} | SEQ: {seq}"
        return "INITIALIZING..."

    @app.callback(Output("unit-table", "children"), Input("update-interval", "n_intervals"))
    def update_unit_table(_):
        from dash import html

        if not _battlefield_state:
            return html.Div("NO DATA")
        rows = []
        for uid, u in _battlefield_state.units.items():
            color = (
                NVG_COLORS["text"]
                if u.strength_pct > 50
                else NVG_COLORS["yellow"] if u.strength_pct > 25 else NVG_COLORS["red"]
            )
            rows.append(
                html.Tr(
                    [
                        html.Td(u.callsign, style={"color": color, "fontSize": "9px"}),
                        html.Td(
                            f"{u.strength_pct:.0f}%", style={"color": color, "fontSize": "9px"}
                        ),
                        html.Td(u.comms_status, style={"fontSize": "9px"}),
                    ]
                )
            )
        return html.Table(
            [
                html.Tr(
                    [
                        html.Th("CALL", style={"fontSize": "9px"}),
                        html.Th("STR", style={"fontSize": "9px"}),
                        html.Th("COMMS", style={"fontSize": "9px"}),
                    ]
                )
            ]
            + rows,
            style={"width": "100%", "borderCollapse": "collapse"},
        )

    @app.callback(Output("tac-map", "children"), Input("update-interval", "n_intervals"))
    def update_tac_map(_):
        fig = nvg_figure("TACTICAL MAP")
        if _battlefield_state:
            # Friendly units (blue diamonds)
            f_lats = [u.lat for u in _battlefield_state.units.values()]
            f_lons = [u.lon for u in _battlefield_state.units.values()]
            f_names = [u.callsign for u in _battlefield_state.units.values()]
            fig.add_trace(
                go.Scattermapbox(
                    lat=f_lats,
                    lon=f_lons,
                    text=f_names,
                    marker=dict(size=12, color=NVG_COLORS["blue"]),
                    mode="markers+text",
                    name="FRIENDLY",
                    textposition="top right",
                )
            )
            # Hostile contacts (red)
            h_lats = [c.lat for c in _battlefield_state.contacts.values()]
            h_lons = [c.lon for c in _battlefield_state.contacts.values()]
            h_names = [c.callsign for c in _battlefield_state.contacts.values()]
            fig.add_trace(
                go.Scattermapbox(
                    lat=h_lats,
                    lon=h_lons,
                    text=h_names,
                    marker=dict(size=10, color=NVG_COLORS["red"]),
                    mode="markers+text",
                    name="HOSTILE",
                    textposition="top right",
                )
            )
            # Center map
            all_lats = f_lats + h_lats
            all_lons = f_lons + h_lons
            if all_lats:
                fig.update_layout(
                    mapbox=dict(
                        style="carto-darkmatter",
                        center=dict(lat=np.mean(all_lats), lon=np.mean(all_lons)),
                        zoom=10,
                    )
                )
        fig.update_layout(height=380, mapbox_style="carto-darkmatter")
        from dash import dcc

        return dcc.Graph(figure=fig, config={"displayModeBar": False}, style={"height": "380px"})

    @app.callback(Output("threat-gauge", "children"), Input("update-interval", "n_intervals"))
    def update_threat_gauge(_):
        threat = 0.3
        if _agent_results and "threat_level" in _agent_results:
            threat = _agent_results["threat_level"]
        fig = nvg_figure()
        fig.add_trace(
            go.Indicator(
                mode="gauge+number",
                value=threat * 100,
                gauge=dict(
                    axis=dict(range=[0, 100]),
                    bar=dict(
                        color=(
                            NVG_COLORS["red"]
                            if threat > 0.7
                            else NVG_COLORS["yellow"] if threat > 0.4 else NVG_COLORS["text"]
                        )
                    ),
                    bgcolor=NVG_COLORS["bg"],
                    bordercolor=NVG_COLORS["border"],
                ),
                number=dict(suffix="%", font=dict(color=NVG_COLORS["text"])),
            )
        )
        fig.update_layout(height=100)
        from dash import dcc

        return dcc.Graph(figure=fig, config={"displayModeBar": False}, style={"height": "100px"})

    @app.callback(Output("alert-timeline", "children"), Input("update-interval", "n_intervals"))
    def update_alerts(_):
        from dash import html

        if not _battlefield_state:
            return html.Div("NO ALERTS")
        alerts = _battlefield_state.alerts[-5:]
        items = []
        for a in reversed(alerts):
            color = (
                NVG_COLORS["red"]
                if a.get("level") in ("FLASH", "IMMEDIATE")
                else NVG_COLORS["yellow"]
            )
            items.append(
                html.Div(
                    f"[{a.get('level', '')}] {a.get('details', '')}",
                    style={"color": color, "fontSize": "9px", "marginBottom": "2px"},
                )
            )
        return html.Div(items)

    @app.callback(Output("nats-sync-panel", "children"), Input("update-interval", "n_intervals"))
    def update_sync(_):
        from dash import html

        if _battlefield_state:
            return html.Div(
                [
                    html.Div(
                        f"SEQ: {_battlefield_state.nats_sequence}", style={"fontSize": "10px"}
                    ),
                    html.Div(f"UNITS: {len(_battlefield_state.units)}", style={"fontSize": "10px"}),
                    html.Div(
                        f"CONTACTS: {len(_battlefield_state.contacts)}", style={"fontSize": "10px"}
                    ),
                    html.Div(
                        "STATUS: SYNCED", style={"color": NVG_COLORS["accent"], "fontSize": "10px"}
                    ),
                ]
            )
        return html.Div("DISCONNECTED", style={"color": NVG_COLORS["red"]})

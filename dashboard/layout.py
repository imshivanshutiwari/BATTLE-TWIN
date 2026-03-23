"""
NVG green-on-black Dash C2 dashboard layout.
22 mandatory visualization panels for the BATTLE-TWIN system.
"""

import os

import dash
from dash import dcc, html
import dash_bootstrap_components as dbc

# NVG green-on-black color scheme
NVG_COLORS = {
    "bg": "#0a0a0a",
    "panel_bg": "#0d1117",
    "border": "#00ff41",
    "text": "#00ff41",
    "text_dim": "#00cc33",
    "accent": "#39ff14",
    "red": "#ff3333",
    "yellow": "#ffcc00",
    "blue": "#00ccff",
    "grid": "#003300",
}


def create_panel(title: str, panel_id: str, children=None, height="300px"):
    """Create a styled NVG panel."""
    return html.Div(
        className="nvg-panel",
        id=f"panel-{panel_id}",
        style={
            "backgroundColor": NVG_COLORS["panel_bg"],
            "border": f"1px solid {NVG_COLORS['border']}",
            "borderRadius": "4px",
            "padding": "10px",
            "marginBottom": "8px",
            "minHeight": height,
        },
        children=[
            html.H6(
                title,
                style={
                    "color": NVG_COLORS["accent"],
                    "margin": "0 0 8px 0",
                    "fontFamily": "monospace",
                    "fontSize": "11px",
                    "textTransform": "uppercase",
                    "letterSpacing": "1px",
                },
            ),
            html.Div(children or [], id=panel_id),
        ],
    )


def create_layout():
    """Build the complete 22-panel C2 dashboard layout."""
    return html.Div(
        style={
            "backgroundColor": NVG_COLORS["bg"],
            "color": NVG_COLORS["text"],
            "fontFamily": "'Courier New', monospace",
            "minHeight": "100vh",
            "padding": "8px",
        },
        children=[
            # Header
            html.Div(
                style={
                    "borderBottom": f"2px solid {NVG_COLORS['border']}",
                    "padding": "8px",
                    "marginBottom": "10px",
                    "display": "flex",
                    "justifyContent": "space-between",
                },
                children=[
                    html.H4(
                        "BATTLE-TWIN C2 DASHBOARD",
                        style={"color": NVG_COLORS["accent"], "margin": 0},
                    ),
                    html.Div(id="header-clock", style={"color": NVG_COLORS["text_dim"]}),
                    html.Div(id="header-status", style={"color": NVG_COLORS["accent"]}),
                ],
            ),
            dcc.Interval(id="update-interval", interval=1000, n_intervals=0),
            dcc.Store(id="battlefield-state-store"),
            # Main Grid: 4 columns
            html.Div(
                style={"display": "grid", "gridTemplateColumns": "1fr 2fr 1fr 1fr", "gap": "8px"},
                children=[
                    # Column 1: Unit Status
                    html.Div(
                        [
                            create_panel("1. UNIT TABLE", "unit-table", height="250px"),
                            create_panel("2. UNIT STRENGTH", "unit-strength-bars", height="200px"),
                            create_panel("3. SUPPLY STATUS", "supply-gauges", height="150px"),
                            create_panel("4. COMMS STATUS", "comms-matrix", height="150px"),
                        ]
                    ),
                    # Column 2: Map & Terrain
                    html.Div(
                        [
                            create_panel("5. TACTICAL MAP (MGRS)", "tac-map", height="400px"),
                            html.Div(
                                style={
                                    "display": "grid",
                                    "gridTemplateColumns": "1fr 1fr",
                                    "gap": "8px",
                                },
                                children=[
                                    create_panel("6. DEM ELEVATION", "dem-heatmap", height="180px"),
                                    create_panel(
                                        "7. SLOPE / TRAFFICABILITY", "slope-map", height="180px"
                                    ),
                                ],
                            ),
                            create_panel("8. VIEWSHED / LOS", "viewshed-overlay", height="180px"),
                        ]
                    ),
                    # Column 3: Intel & Threats
                    html.Div(
                        [
                            create_panel("9. THREAT LEVEL GAUGE", "threat-gauge", height="120px"),
                            create_panel(
                                "10. BAYESIAN NETWORK", "bayesian-net-graph", height="200px"
                            ),
                            create_panel("11. MCTS COA TREE", "mcts-tree-viz", height="200px"),
                            create_panel("12. D* LITE PATH", "dstar-path-overlay", height="180px"),
                        ]
                    ),
                    # Column 4: Logistics & Comms
                    html.Div(
                        [
                            create_panel("13. VRP CONVOY ROUTES", "vrp-route-map", height="200px"),
                            create_panel("14. MANET MESH GRAPH", "manet-mesh-viz", height="200px"),
                            create_panel("15. MEDEVAC 9-LINE", "medevac-display", height="150px"),
                            create_panel(
                                "16. FIRE MISSION STATUS", "fire-mission-log", height="150px"
                            ),
                        ]
                    ),
                ],
            ),
            # Bottom Row: Timelines & Alerts
            html.Div(
                style={
                    "display": "grid",
                    "gridTemplateColumns": "1fr 1fr 1fr 1fr 1fr 1fr",
                    "gap": "8px",
                    "marginTop": "8px",
                },
                children=[
                    create_panel("17. ADS-B TRACKS", "adsb-scatter", height="150px"),
                    create_panel("18. WEATHER OVERLAY", "weather-panel", height="150px"),
                    create_panel("19. SENSOR FUSION", "sensor-fusion-bars", height="150px"),
                    create_panel("20. ALERT LOG", "alert-timeline", height="150px"),
                    create_panel("21. FORCE RATIO", "force-ratio-chart", height="150px"),
                    create_panel("22. SYNC STATUS", "nats-sync-panel", height="150px"),
                ],
            ),
        ],
    )


if __name__ == "__main__":
    app = dash.Dash(__name__, external_stylesheets=[dbc.themes.CYBORG])
    app.layout = create_layout()
    port = int(os.environ.get("DASH_PORT", 8050))
    app.run(debug=True, port=port)

"""Agent-related callbacks for LangGraph agent visualization."""
from dash import Input, Output
import plotly.graph_objects as go
from dashboard.theme import NVG_THEME, PLOTLY_TEMPLATE


def register_agent_callbacks(app, get_agent_results_fn=None):
    """Register callbacks for agent decision visualization."""

    @app.callback(Output("c2-threat-gauges", "figure", allow_duplicate=True),
                  Input("update-interval", "n_intervals"), prevent_initial_call=True)
    def update_threat_gauges(_):
        results = get_agent_results_fn() if get_agent_results_fn else {}
        threat = results.get("threat_level", 0.3) if results else 0.3
        fig = go.Figure()
        fig.add_trace(go.Indicator(mode="gauge+number+delta", value=threat*100,
            delta=dict(reference=50),
            gauge=dict(axis=dict(range=[0,100]),
                       bar=dict(color=NVG_THEME["threat"] if threat>0.7 else NVG_THEME["accent"]),
                       bgcolor=NVG_THEME["bg"], bordercolor=NVG_THEME["border"],
                       steps=[dict(range=[0,30],color="#003300"),
                              dict(range=[30,70],color="#333300"),
                              dict(range=[70,100],color="#330000")]),
            number=dict(suffix="%", font=dict(color=NVG_THEME["text"])),
            title=dict(text="THREAT", font=dict(color=NVG_THEME["accent"]))))
        fig.update_layout(**PLOTLY_TEMPLATE, height=150)
        return fig

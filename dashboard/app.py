"""Main Dash app entry point. Assembles layout + callbacks, auto-opens browser."""
import os
import threading
import webbrowser
import dash
import dash_bootstrap_components as dbc
from dashboard.layout import create_layout
from dashboard.main_callbacks import register_callbacks, set_shared_state
from digital_twin.twin_state import BattlefieldState
from utils.logger import get_logger
from utils.config_loader import load_config

log = get_logger("DASHBOARD")


def create_app(battlefield_state=None):
    """Create and configure the Dash app."""
    app = dash.Dash(
        __name__,
        external_stylesheets=[dbc.themes.CYBORG],
        title="BATTLE-TWIN C2",
        update_title=None,
    )
    app.layout = create_layout()

    if battlefield_state is None:
        try:
            config = load_config("battlefield_config")
            battlefield_state = BattlefieldState.from_config(config)
        except Exception:
            battlefield_state = BattlefieldState()

    set_shared_state(battlefield_state)
    register_callbacks(app)
    return app


def run_dashboard(port=None, debug=None, open_browser=True):
    """Run the C2 dashboard server."""
    port = port or int(os.environ.get("DASH_PORT", 8050))
    debug = debug if debug is not None else os.environ.get("DASH_DEBUG", "false").lower() == "true"
    app = create_app()

    if open_browser:
        def _open():
            import time; time.sleep(1.5)
            webbrowser.open(f"http://localhost:{port}")
        threading.Thread(target=_open, daemon=True).start()

    log.info(f"C2 Dashboard starting on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=debug)


if __name__ == "__main__":
    run_dashboard()

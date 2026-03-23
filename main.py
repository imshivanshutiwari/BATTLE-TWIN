"""
BATTLE-TWIN main entry point.
Starts simulation + dashboard, auto-opens browser.
"""

import argparse
import time
from simulation.sim_runner import SimulationRunner
from dashboard.app import run_dashboard
from utils.logger import get_logger
from utils.seed import set_global_seed

log = get_logger("MAIN")


def main():
    parser = argparse.ArgumentParser(description="BATTLE-TWIN Digital Twin System")
    parser.add_argument("--sim-speed", type=float, default=1.0, help="Simulation speed multiplier")
    parser.add_argument("--tick-rate", type=float, default=10.0, help="Simulation tick rate (Hz)")
    parser.add_argument("--port", type=int, default=8050, help="Dashboard port")
    parser.add_argument("--no-browser", action="store_true", help="Don't auto-open browser")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--max-ticks", type=int, default=None, help="Max sim ticks (None=infinite)")
    args = parser.parse_args()

    set_global_seed(args.seed)
    log.info("=" * 60)
    log.info("BATTLE-TWIN DIGITAL TWIN SYSTEM")
    log.info("=" * 60)

    # Start simulation in background thread
    runner = SimulationRunner(sim_speed=args.sim_speed, tick_rate_hz=args.tick_rate)
    runner.run_in_thread(max_ticks=args.max_ticks)
    time.sleep(0.5)

    # Start dashboard (blocks main thread)
    log.info(f"Starting C2 dashboard on port {args.port}")
    run_dashboard(port=args.port, open_browser=not args.no_browser)


if __name__ == "__main__":
    main()

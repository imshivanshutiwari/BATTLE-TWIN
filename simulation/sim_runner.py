"""Simulation runner — orchestrates engine + agents + dashboard."""
import asyncio
import time
import threading
from typing import Optional
from simulation.sim_engine import SimulationEngine
from digital_twin.twin_state import BattlefieldState
from digital_twin.nats_publisher import NATSPublisher
from agents.graph_runner import GraphRunner
from utils.logger import get_logger
from utils.config_loader import load_config
log = get_logger("SIM_RUNNER")


class SimulationRunner:
    """Orchestrates the full simulation pipeline."""

    def __init__(self, sim_speed: float = 1.0, tick_rate_hz: float = 10.0):
        self.sim_speed = sim_speed
        self.tick_rate = tick_rate_hz
        self.engine = SimulationEngine(dt_s=1.0/tick_rate_hz, speed_multiplier=sim_speed)
        self.publisher = NATSPublisher()
        self.graph_runner = GraphRunner()
        self.state: Optional[BattlefieldState] = None
        self._running = False
        self._agent_interval_ticks = int(tick_rate_hz * 5)  # agents every 5s

    def initialize(self):
        try:
            config = load_config("battlefield_config")
            self.state = BattlefieldState.from_config(config)
        except Exception as e:
            log.warning(f"Config load failed: {e}, using defaults")
            self.state = BattlefieldState()
        log.info(f"Simulation initialized: {len(self.state.units)} units, {len(self.state.contacts)} contacts")

    async def run_async(self, max_ticks: Optional[int] = None):
        self._running = True
        self.initialize()
        await self.publisher.connect()
        tick = 0
        interval = 1.0 / self.tick_rate
        log.info(f"Simulation running at {self.tick_rate} Hz")
        while self._running and (max_ticks is None or tick < max_ticks):
            self.engine.step(self.state)
            if tick % self._agent_interval_ticks == 0 and tick > 0:
                try:
                    self.graph_runner.run_all(self.state.to_dict())
                except Exception as e:
                    log.warning(f"Agent cycle failed: {e}")
            if tick % 10 == 0:
                await self.publisher.publish_state(self.state.to_dict())
            tick += 1
            await asyncio.sleep(interval)
        await self.publisher.disconnect()
        log.info(f"Simulation stopped at tick {tick}")

    def run(self, max_ticks=None):
        asyncio.run(self.run_async(max_ticks))

    def stop(self):
        self._running = False

    def run_in_thread(self, max_ticks=None):
        t = threading.Thread(target=self.run, args=(max_ticks,), daemon=True)
        t.start()
        return t


if __name__ == "__main__":
    runner = SimulationRunner(sim_speed=1.0, tick_rate_hz=10)
    runner.run(max_ticks=100)
    print("sim_runner.py OK")

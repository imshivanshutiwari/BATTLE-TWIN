"""
UE5 sync orchestrator for the digital twin.

Manages the synchronization pipeline between the Python
battlefield state and the Unreal Engine 5 visualization.
"""

import asyncio
import time
from typing import Any, Callable, Dict, List, Optional

from digital_twin.nats_publisher import NATSPublisher
from digital_twin.nats_subscriber import NATSSubscriber
from utils.logger import get_logger

log = get_logger("SYNC_MANAGER")


class SyncManager:
    """
    Orchestrates state sync between Python backend and UE5.

    Responsibilities:
    - Manages NATS pub/sub lifecycle
    - Coordinates state update frequency
    - Monitors sync health (latency, divergence)
    - Handles reconnection and error recovery
    """

    def __init__(
        self,
        servers: Optional[List[str]] = None,
        publish_interval_ms: int = 100,
    ):
        self.servers = servers or ["nats://localhost:4222"]
        self.publish_interval_ms = publish_interval_ms
        self.publisher = NATSPublisher(servers=self.servers)
        self.subscriber = NATSSubscriber(servers=self.servers)

        self._running = False
        self._sync_count = 0
        self._last_sync_time = 0.0
        self._latency_samples: List[float] = []
        self._max_latency_samples = 100
        self._state_generator: Optional[Callable] = None
        self._on_state_update: Optional[Callable] = None

    @property
    def running(self) -> bool:
        return self._running

    @property
    def sync_count(self) -> int:
        return self._sync_count

    @property
    def avg_latency_ms(self) -> float:
        if not self._latency_samples:
            return 0.0
        return sum(self._latency_samples) / len(self._latency_samples) * 1000

    async def start(
        self,
        state_generator: Callable,
        on_state_update: Optional[Callable] = None,
    ) -> None:
        """
        Start the sync pipeline.

        Args:
            state_generator: Callable returning current state dict.
            on_state_update: Callback when state update is received.
        """
        self._state_generator = state_generator
        self._on_state_update = on_state_update

        log.info("Starting sync manager")
        await self.publisher.connect()
        await self.subscriber.connect()
        await self.subscriber.subscribe()

        if on_state_update:
            self.subscriber.on("battlefield.state", on_state_update)

        self._running = True
        log.info("Sync manager started")

    async def stop(self) -> None:
        """Stop the sync pipeline."""
        self._running = False
        await self.publisher.disconnect()
        await self.subscriber.disconnect()
        log.info("Sync manager stopped")

    async def sync_loop(
        self,
        max_iterations: Optional[int] = None,
    ) -> None:
        """
        Main sync loop — publishes state at configured rate.

        Args:
            max_iterations: Optional limit for testing.
        """
        interval_s = self.publish_interval_ms / 1000.0
        iteration = 0

        while self._running and (max_iterations is None or iteration < max_iterations):
            if self._state_generator:
                start = time.time()
                state = self._state_generator()
                await self.publisher.publish_state(state)
                latency = time.time() - start

                self._latency_samples.append(latency)
                if len(self._latency_samples) > self._max_latency_samples:
                    self._latency_samples.pop(0)

                self._sync_count += 1
                self._last_sync_time = time.time()

            iteration += 1
            await asyncio.sleep(interval_s)

    def get_sync_status(self) -> Dict[str, Any]:
        """Get sync health status."""
        status = "SYNCED"
        if not self._running:
            status = "DISCONNECTED"
        elif self.avg_latency_ms > 500:
            status = "LAGGING"

        return {
            "status": status,
            "running": self._running,
            "sync_count": self._sync_count,
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "last_sync_time": self._last_sync_time,
            "publisher": self.publisher.get_stats(),
            "subscriber": self.subscriber.get_stats(),
        }


if __name__ == "__main__":
    sm = SyncManager()
    print(f"Sync status: {sm.get_sync_status()}")
    print("sync_manager.py OK")

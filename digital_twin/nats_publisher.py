"""
NATS JetStream publisher for battlefield state synchronization.

Publishes BattlefieldState updates to NATS JetStream subjects
at a configurable rate (default 10 Hz) for consumption by:
- Dash C2 dashboard
- UE5 digital twin plugin
- LangGraph agents
"""

import asyncio
import json
import time
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional

from utils.logger import get_logger

log = get_logger("NATS_PUBLISHER")

# Attempt NATS import
try:
    import nats
    from nats.js.api import StreamConfig, RetentionPolicy
    NATS_AVAILABLE = True
except ImportError:
    NATS_AVAILABLE = False
    log.warning("nats-py not installed, using mock publisher")


class NATSPublisher:
    """
    Publishes battlefield state to NATS JetStream.

    Subjects:
        battlefield.state      — full state update
        battlefield.unit.{uid} — individual unit update
        battlefield.contact    — new contact report
        battlefield.alert      — alert notifications
        battlefield.medevac    — MEDEVAC requests
        battlefield.fires      — fire mission updates
    """

    def __init__(
        self,
        servers: Optional[List[str]] = None,
        stream_name: str = "BATTLEFIELD",
    ):
        self.servers = servers or ["nats://localhost:4222"]
        self.stream_name = stream_name
        self._nc = None
        self._js = None
        self._connected = False
        self._publish_count = 0
        self._last_publish_time = 0.0

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def publish_count(self) -> int:
        return self._publish_count

    async def connect(
        self,
        servers: Optional[List[str]] = None,
    ) -> None:
        """
        Connect to NATS server and set up JetStream.

        Args:
            servers: NATS server URLs. Defaults to localhost.
        """
        if not NATS_AVAILABLE:
            log.warning("NATS not available, running in offline mode")
            self._connected = False
            return

        target_servers = servers or self.servers
        try:
            self._nc = await nats.connect(
                servers=target_servers,
                connect_timeout=5,
                reconnect_time_wait=2,
                max_reconnect_attempts=60,
                error_cb=self._error_callback,
                disconnected_cb=self._disconnected_callback,
                reconnected_cb=self._reconnected_callback,
            )
            self._js = self._nc.jetstream()

            # Create or update stream
            try:
                await self._js.add_stream(
                    name=self.stream_name,
                    subjects=[
                        "battlefield.>",
                    ],
                    retention=RetentionPolicy.LIMITS,
                    max_msgs=10000,
                    max_bytes=100 * 1024 * 1024,  # 100 MB
                )
                log.info(f"JetStream stream '{self.stream_name}' ready")
            except Exception as e:
                log.warning(f"Stream setup warning: {e}")

            self._connected = True
            log.info(f"Connected to NATS: {target_servers}")

        except Exception as e:
            log.error(f"NATS connection failed: {e}")
            self._connected = False

    async def disconnect(self) -> None:
        """Disconnect from NATS."""
        if self._nc and self._connected:
            await self._nc.drain()
            await self._nc.close()
            self._connected = False
            log.info("NATS disconnected")

    async def publish_state(
        self,
        state_dict: Dict[str, Any],
    ) -> None:
        """
        Publish full battlefield state update.

        Args:
            state_dict: Serialized BattlefieldState dictionary.
        """
        await self._publish(
            "battlefield.state",
            json.dumps(state_dict, default=str).encode("utf-8"),
        )

    async def publish_unit_update(
        self,
        uid: str,
        delta: Dict[str, Any],
    ) -> None:
        """
        Publish individual unit state update.

        Args:
            uid: Unit unique identifier.
            delta: State changes for this unit.
        """
        payload = json.dumps({"uid": uid, **delta}, default=str).encode("utf-8")
        await self._publish(f"battlefield.unit.{uid}", payload)

    async def publish_contact(
        self,
        contact_dict: Dict[str, Any],
    ) -> None:
        """Publish a new contact report."""
        await self._publish(
            "battlefield.contact",
            json.dumps(contact_dict, default=str).encode("utf-8"),
        )

    async def publish_alert(
        self,
        alert_dict: Dict[str, Any],
    ) -> None:
        """Publish an alert notification."""
        await self._publish(
            "battlefield.alert",
            json.dumps(alert_dict, default=str).encode("utf-8"),
        )

    async def publish_medevac(
        self,
        medevac_dict: Dict[str, Any],
    ) -> None:
        """Publish a MEDEVAC request."""
        await self._publish(
            "battlefield.medevac",
            json.dumps(medevac_dict, default=str).encode("utf-8"),
        )

    async def publish_fires(
        self,
        fire_dict: Dict[str, Any],
    ) -> None:
        """Publish a fire mission update."""
        await self._publish(
            "battlefield.fires",
            json.dumps(fire_dict, default=str).encode("utf-8"),
        )

    async def _publish(self, subject: str, payload: bytes) -> None:
        """Internal publish with logging."""
        if self._connected and self._js:
            try:
                ack = await self._js.publish(subject, payload)
                self._publish_count += 1
                self._last_publish_time = time.time()
            except Exception as e:
                log.error(f"Publish error on {subject}: {e}")
        else:
            # Offline mode: just count
            self._publish_count += 1
            self._last_publish_time = time.time()

    async def stream_continuous(
        self,
        state_generator: Callable,
        interval_ms: int = 100,
        max_iterations: Optional[int] = None,
    ) -> None:
        """
        Continuously publish state at a fixed rate.

        Args:
            state_generator: Callable returning current state dict.
            interval_ms: Publish interval in milliseconds (default 100ms = 10Hz).
            max_iterations: Optional limit for testing.
        """
        interval_s = interval_ms / 1000.0
        iteration = 0

        log.info(f"Starting continuous publish at {1/interval_s:.0f} Hz")
        while max_iterations is None or iteration < max_iterations:
            state_dict = state_generator()
            await self.publish_state(state_dict)
            iteration += 1
            await asyncio.sleep(interval_s)

    def get_stats(self) -> Dict[str, Any]:
        """Get publisher statistics."""
        return {
            "connected": self._connected,
            "publish_count": self._publish_count,
            "last_publish_time": self._last_publish_time,
            "servers": self.servers,
            "stream_name": self.stream_name,
        }

    async def _error_callback(self, e: Exception) -> None:
        log.error(f"NATS error: {e}")

    async def _disconnected_callback(self) -> None:
        log.warning("NATS disconnected")
        self._connected = False

    async def _reconnected_callback(self) -> None:
        log.info("NATS reconnected")
        self._connected = True


if __name__ == "__main__":
    pub = NATSPublisher()
    print(f"NATS available: {NATS_AVAILABLE}")
    print(f"Stats: {pub.get_stats()}")
    print("nats_publisher.py OK")

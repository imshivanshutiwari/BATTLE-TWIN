"""
NATS JetStream subscriber for receiving battlefield state updates.

Subscribes to NATS subjects and applies updates to the local
BattlefieldState object in real-time.
"""

import asyncio
import json
import time
from typing import Any, Callable, Dict, List, Optional

from utils.logger import get_logger

log = get_logger("NATS_SUBSCRIBER")

try:
    import nats
    from nats.js.api import DeliverPolicy

    NATS_AVAILABLE = True
except ImportError:
    NATS_AVAILABLE = False


class NATSSubscriber:
    """
    Subscribes to NATS JetStream for battlefield state updates.

    Handles:
    - Full state updates (battlefield.state)
    - Individual unit updates (battlefield.unit.{uid})
    - Contact reports (battlefield.contact)
    - Alerts (battlefield.alert)
    - Fire mission updates (battlefield.fires)
    - MEDEVAC requests (battlefield.medevac)
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
        self._subscriptions = []
        self._message_count = 0
        self._last_receive_time = 0.0
        self._callbacks: Dict[str, List[Callable]] = {}
        self._latest_state: Optional[Dict[str, Any]] = None

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def message_count(self) -> int:
        return self._message_count

    @property
    def latest_state(self) -> Optional[Dict[str, Any]]:
        return self._latest_state

    def on(self, subject: str, callback: Callable) -> None:
        """
        Register a callback for a NATS subject.

        Args:
            subject: Subject pattern (e.g., 'battlefield.state').
            callback: Function(data: dict) to call on message.
        """
        if subject not in self._callbacks:
            self._callbacks[subject] = []
        self._callbacks[subject].append(callback)

    async def connect(
        self,
        servers: Optional[List[str]] = None,
    ) -> None:
        """Connect to NATS and set up subscriptions."""
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
            )
            self._js = self._nc.jetstream()
            self._connected = True
            log.info(f"Subscriber connected to NATS: {target_servers}")
        except Exception as e:
            log.error(f"Subscriber connection failed: {e}")
            self._connected = False

    async def subscribe(
        self,
        subjects: Optional[List[str]] = None,
    ) -> None:
        """
        Subscribe to battlefield subjects.

        Args:
            subjects: List of subjects to subscribe to.
                      Defaults to all battlefield subjects.
        """
        if not self._connected or not self._js:
            log.warning("Not connected, cannot subscribe")
            return

        default_subjects = [
            "battlefield.state",
            "battlefield.unit.>",
            "battlefield.contact",
            "battlefield.alert",
            "battlefield.fires",
            "battlefield.medevac",
        ]
        target_subjects = subjects or default_subjects

        for subject in target_subjects:
            try:
                sub = await self._js.subscribe(
                    subject,
                    durable=f"battletwin_{subject.replace('.', '_').replace('>', 'all')}",
                    deliver_policy=DeliverPolicy.LAST,
                )
                self._subscriptions.append((subject, sub))
                log.info(f"Subscribed to: {subject}")
            except Exception as e:
                log.warning(f"Subscribe error for {subject}: {e}")

    async def listen(
        self,
        timeout_s: float = 1.0,
        max_messages: Optional[int] = None,
    ) -> None:
        """
        Listen for messages on all subscriptions.

        Args:
            timeout_s: Timeout per message fetch.
            max_messages: Optional limit for testing.
        """
        msg_count = 0
        while max_messages is None or msg_count < max_messages:
            for subject, sub in self._subscriptions:
                try:
                    msgs = await sub.fetch(batch=10, timeout=timeout_s)
                    for msg in msgs:
                        await self._handle_message(subject, msg)
                        msg_count += 1
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    log.warning(f"Listen error on {subject}: {e}")
            await asyncio.sleep(0.01)

    async def _handle_message(self, subject: str, msg: Any) -> None:
        """Process a received NATS message."""
        try:
            data = json.loads(msg.data.decode("utf-8"))
            self._message_count += 1
            self._last_receive_time = time.time()

            # Store latest full state
            if "battlefield.state" in subject:
                self._latest_state = data

            # Invoke registered callbacks
            for pattern, callbacks in self._callbacks.items():
                if self._subject_matches(pattern, subject):
                    for cb in callbacks:
                        try:
                            cb(data)
                        except Exception as e:
                            log.error(f"Callback error: {e}")

            await msg.ack()

        except json.JSONDecodeError as e:
            log.warning(f"Invalid JSON in message: {e}")

    @staticmethod
    def _subject_matches(pattern: str, subject: str) -> bool:
        """Check if a subject matches a pattern (with > wildcard)."""
        if pattern == subject:
            return True
        if pattern.endswith(">"):
            prefix = pattern[:-1]
            return subject.startswith(prefix)
        return False

    async def disconnect(self) -> None:
        """Disconnect from NATS."""
        for _, sub in self._subscriptions:
            try:
                await sub.unsubscribe()
            except Exception:
                pass
        if self._nc:
            await self._nc.drain()
            await self._nc.close()
        self._connected = False
        self._subscriptions.clear()
        log.info("Subscriber disconnected")

    def get_stats(self) -> Dict[str, Any]:
        """Get subscriber statistics."""
        return {
            "connected": self._connected,
            "message_count": self._message_count,
            "last_receive_time": self._last_receive_time,
            "subscriptions": [s for s, _ in self._subscriptions],
            "has_latest_state": self._latest_state is not None,
        }


if __name__ == "__main__":
    sub = NATSSubscriber()
    print(f"NATS available: {NATS_AVAILABLE}")
    print(f"Stats: {sub.get_stats()}")
    print("nats_subscriber.py OK")

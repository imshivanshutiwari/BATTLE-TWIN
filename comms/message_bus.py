"""Internal message bus for inter-module communication."""
import asyncio
import time
from collections import defaultdict
from typing import Any, Callable, Dict, List
from utils.logger import get_logger
log = get_logger("MSG_BUS")


class Message:
    def __init__(self, topic: str, payload: Any, sender: str = "", priority: int = 0):
        self.topic = topic
        self.payload = payload
        self.sender = sender
        self.priority = priority
        self.timestamp = time.time()
        self.delivered = False

    def __repr__(self):
        return f"Message(topic={self.topic}, sender={self.sender}, priority={self.priority})"


class MessageBus:
    """In-process publish/subscribe message bus for module communication."""

    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._message_log: List[Message] = []
        self._max_log = 10000

    def subscribe(self, topic: str, callback: Callable):
        self._subscribers[topic].append(callback)
        log.debug(f"Subscribed to {topic}")

    def unsubscribe(self, topic: str, callback: Callable):
        if topic in self._subscribers:
            self._subscribers[topic] = [c for c in self._subscribers[topic] if c != callback]

    def publish(self, topic: str, payload: Any, sender: str = "", priority: int = 0):
        msg = Message(topic, payload, sender, priority)
        self._message_log.append(msg)
        if len(self._message_log) > self._max_log:
            self._message_log = self._message_log[-self._max_log:]
        delivered = 0
        for callback in self._subscribers.get(topic, []):
            try:
                callback(msg)
                delivered += 1
            except Exception as e:
                log.warning(f"Subscriber error on {topic}: {e}")
        # Wildcard subscribers
        for pattern, callbacks in self._subscribers.items():
            if pattern.endswith(">") and topic.startswith(pattern[:-1]):
                for cb in callbacks:
                    try:
                        cb(msg)
                        delivered += 1
                    except Exception as e:
                        log.warning(f"Wildcard subscriber error: {e}")
        msg.delivered = delivered > 0
        return delivered

    def get_message_log(self, topic: str = None, limit: int = 50) -> List[Message]:
        if topic:
            return [m for m in self._message_log if m.topic == topic][-limit:]
        return self._message_log[-limit:]

    def get_stats(self) -> Dict:
        topics = defaultdict(int)
        for m in self._message_log:
            topics[m.topic] += 1
        return {
            "total_messages": len(self._message_log),
            "topics": dict(topics),
            "subscribers": {k: len(v) for k, v in self._subscribers.items()},
        }

    def clear(self):
        self._message_log.clear()


# Singleton instance
_bus = MessageBus()


def get_message_bus() -> MessageBus:
    return _bus


if __name__ == "__main__":
    bus = get_message_bus()
    received = []
    bus.subscribe("battlefield.alert", lambda m: received.append(m))
    bus.publish("battlefield.alert", {"level": "FLASH", "msg": "Contact!"}, sender="S2")
    bus.publish("battlefield.alert", {"level": "ROUTINE", "msg": "Status"}, sender="S4")
    print(f"Received: {len(received)} messages")
    print(f"Stats: {bus.get_stats()}")
    print("message_bus.py OK")

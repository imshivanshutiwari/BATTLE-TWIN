"""
Replay engine for past battlefield scenarios.

Records and replays battlefield state sequences for:
- After-action review
- Training scenario replay
- Algorithm testing with historical data
"""

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

from utils.logger import get_logger

log = get_logger("REPLAY_ENGINE")

REPLAY_DIR = Path("data/replays")


@dataclass
class ReplayEvent:
    """Single recorded event in a replay."""

    sequence: int
    timestamp: float
    event_type: str  # state, unit_update, contact, alert
    data: Dict[str, Any]


class ReplayEngine:
    """
    Records and replays battlefield state sequences.

    Supports:
    - Recording live state updates
    - Saving replays to disk
    - Loading and replaying past scenarios
    - Speed control (1x, 2x, 4x, 0.5x)
    - Pause/resume/seek
    """

    def __init__(self, replay_dir: Optional[Path] = None):
        self.replay_dir = replay_dir or REPLAY_DIR
        self.replay_dir.mkdir(parents=True, exist_ok=True)

        self._recording = False
        self._events: List[ReplayEvent] = []
        self._sequence = 0
        self._record_start_time = 0.0

        # Playback state
        self._playing = False
        self._playback_speed = 1.0
        self._playback_index = 0
        self._paused = False

    @property
    def recording(self) -> bool:
        return self._recording

    @property
    def event_count(self) -> int:
        return len(self._events)

    def start_recording(self) -> None:
        """Begin recording state events."""
        self._recording = True
        self._events.clear()
        self._sequence = 0
        self._record_start_time = time.time()
        log.info("Recording started")

    def stop_recording(self) -> int:
        """Stop recording and return event count."""
        self._recording = False
        count = len(self._events)
        log.info(f"Recording stopped: {count} events")
        return count

    def record_event(
        self,
        event_type: str,
        data: Dict[str, Any],
    ) -> None:
        """
        Record a single event during recording.

        Args:
            event_type: Type of event.
            data: Event data dictionary.
        """
        if not self._recording:
            return

        self._events.append(
            ReplayEvent(
                sequence=self._sequence,
                timestamp=time.time() - self._record_start_time,
                event_type=event_type,
                data=data,
            )
        )
        self._sequence += 1

    def save_replay(self, name: str) -> Path:
        """
        Save recorded events to disk.

        Args:
            name: Replay name (used as filename).

        Returns:
            Path to saved replay file.
        """
        filename = f"replay_{name}_{datetime.now(tz=timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
        filepath = self.replay_dir / filename

        replay_data = {
            "name": name,
            "created": datetime.now(tz=timezone.utc).isoformat(),
            "event_count": len(self._events),
            "duration_s": self._events[-1].timestamp if self._events else 0,
            "events": [
                {
                    "seq": e.sequence,
                    "ts": e.timestamp,
                    "type": e.event_type,
                    "data": e.data,
                }
                for e in self._events
            ],
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(replay_data, f, default=str)

        log.info(f"Replay saved: {filepath} ({len(self._events)} events)")
        return filepath

    def load_replay(self, filepath: Path) -> int:
        """
        Load a replay from disk.

        Args:
            filepath: Path to replay JSON file.

        Returns:
            Number of events loaded.
        """
        with open(filepath, "r", encoding="utf-8") as f:
            replay_data = json.load(f)

        self._events = [
            ReplayEvent(
                sequence=e["seq"],
                timestamp=e["ts"],
                event_type=e["type"],
                data=e["data"],
            )
            for e in replay_data["events"]
        ]

        log.info(f"Replay loaded: {len(self._events)} events from {filepath}")
        return len(self._events)

    def replay(
        self,
        speed: float = 1.0,
    ) -> Generator[ReplayEvent, None, None]:
        """
        Replay events as a generator.

        Args:
            speed: Playback speed multiplier (1.0 = real-time).

        Yields:
            ReplayEvent objects in recorded order.
        """
        self._playing = True
        self._playback_speed = speed
        last_ts = 0.0

        for event in self._events:
            if not self._playing:
                break

            while self._paused:
                time.sleep(0.1)

            # Wait for appropriate time
            dt = (event.timestamp - last_ts) / self._playback_speed
            if dt > 0:
                time.sleep(dt)
            last_ts = event.timestamp

            yield event

        self._playing = False

    def replay_events_list(self) -> List[ReplayEvent]:
        """Return all events without waiting (non-blocking)."""
        return list(self._events)

    def pause(self) -> None:
        """Pause playback."""
        self._paused = True

    def resume(self) -> None:
        """Resume playback."""
        self._paused = False

    def stop(self) -> None:
        """Stop playback."""
        self._playing = False

    def set_speed(self, speed: float) -> None:
        """Set playback speed."""
        self._playback_speed = max(0.1, min(10.0, speed))

    def seek(self, sequence: int) -> Optional[ReplayEvent]:
        """Seek to a specific event by sequence number."""
        for event in self._events:
            if event.sequence == sequence:
                return event
        return None

    def list_replays(self) -> List[Dict[str, Any]]:
        """List saved replay files."""
        replays = []
        for f in sorted(self.replay_dir.glob("replay_*.json")):
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                replays.append(
                    {
                        "file": str(f),
                        "name": data.get("name", ""),
                        "created": data.get("created", ""),
                        "event_count": data.get("event_count", 0),
                        "duration_s": data.get("duration_s", 0),
                    }
                )
            except (json.JSONDecodeError, KeyError):
                continue
        return replays


if __name__ == "__main__":
    engine = ReplayEngine()

    # Test recording and replay
    engine.start_recording()
    for i in range(10):
        engine.record_event("state", {"seq": i, "data": f"event_{i}"})
        time.sleep(0.01)
    count = engine.stop_recording()
    print(f"Recorded {count} events")

    # Save and reload
    path = engine.save_replay("test")
    engine2 = ReplayEngine()
    loaded = engine2.load_replay(path)
    print(f"Loaded {loaded} events")

    # Replay (non-blocking)
    events = engine2.replay_events_list()
    print(f"Replay events: {len(events)}")
    for e in events:
        print(f"  seq={e.sequence} type={e.event_type} ts={e.timestamp:.3f}")

    # Cleanup test file
    path.unlink(missing_ok=True)
    print("replay_engine.py OK")

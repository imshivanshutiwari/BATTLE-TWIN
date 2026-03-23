"""
Structured logging for BATTLE-TWIN C2 system.

Provides military-style structured logging with:
- ISO-8601 timestamps
- Component-based log routing
- Severity levels mapped to military alert levels
- File + console dual output
- JSON structured fields for machine parsing
"""

import sys
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict
from pathlib import Path


# Military alert level mapping
ALERT_LEVELS = {
    "ROUTINE": logging.DEBUG,
    "PRIORITY": logging.INFO,
    "IMMEDIATE": logging.WARNING,
    "FLASH": logging.ERROR,
    "OVERRIDE": logging.CRITICAL,
}

LOG_DIR = Path("logs")


class TacticalFormatter(logging.Formatter):
    """
    Custom formatter producing structured tactical log lines.

    Format:
        [ISO-8601] [LEVEL] [COMPONENT] message {structured_fields}
    """

    LEVEL_COLORS = {
        "DEBUG": "\033[36m",  # Cyan - ROUTINE
        "INFO": "\033[32m",  # Green - PRIORITY
        "WARNING": "\033[33m",  # Yellow - IMMEDIATE
        "ERROR": "\033[31m",  # Red - FLASH
        "CRITICAL": "\033[35m",  # Magenta - OVERRIDE
    }
    RESET = "\033[0m"

    def __init__(self, use_color: bool = True):
        super().__init__()
        self.use_color = use_color

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%S.%fZ"
        )
        level = record.levelname
        component = getattr(record, "component", record.name)

        # Extract structured fields
        fields = getattr(record, "fields", {})
        fields_str = ""
        if fields:
            fields_str = " " + json.dumps(fields, default=str, separators=(",", ":"))

        msg = record.getMessage()

        if self.use_color and sys.stderr.isatty():
            color = self.LEVEL_COLORS.get(level, "")
            return f"{color}[{ts}] [{level:8s}] [{component}]{self.RESET} {msg}{fields_str}"
        return f"[{ts}] [{level:8s}] [{component}] {msg}{fields_str}"


class JSONFormatter(logging.Formatter):
    """JSON formatter for machine-parseable log files."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "component": getattr(record, "component", record.name),
            "message": record.getMessage(),
            "fields": getattr(record, "fields", {}),
        }
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = str(record.exc_info[1])
        return json.dumps(log_entry, default=str)


class TacticalLogAdapter(logging.LoggerAdapter):
    """
    Logger adapter that injects component name and structured fields.
    """

    def process(self, msg: str, kwargs: Dict[str, Any]) -> tuple:
        extra = kwargs.setdefault("extra", {})
        extra["component"] = self.extra.get("component", "SYSTEM")
        if "fields" in kwargs:
            extra["fields"] = kwargs.pop("fields")
        else:
            extra["fields"] = {}
        return msg, kwargs

    def tactical(
        self,
        msg: str,
        alert_level: str = "ROUTINE",
        **fields: Any,
    ) -> None:
        """
        Log with military alert level.

        Args:
            msg: Log message.
            alert_level: One of ROUTINE/PRIORITY/IMMEDIATE/FLASH/OVERRIDE.
            **fields: Structured key-value pairs.
        """
        level = ALERT_LEVELS.get(alert_level.upper(), logging.INFO)
        self.log(level, msg, fields=fields)


_loggers: Dict[str, TacticalLogAdapter] = {}


def get_logger(
    component: str,
    log_level: str = "DEBUG",
    log_to_file: bool = True,
) -> TacticalLogAdapter:
    """
    Get or create a component-specific tactical logger.

    Args:
        component: Component name (e.g., 'DIGITAL_TWIN', 'NATS', 'SENSORS').
        log_level: Minimum log level string.
        log_to_file: Whether to also log to file.

    Returns:
        TacticalLogAdapter with component context.
    """
    if component in _loggers:
        return _loggers[component]

    logger = logging.getLogger(f"BT.{component}")
    logger.setLevel(getattr(logging, log_level.upper(), logging.DEBUG))
    logger.propagate = True

    # Console handler with tactical formatting
    if not logger.handlers:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setFormatter(TacticalFormatter(use_color=True))
        console_handler.setLevel(logging.DEBUG)
        logger.addHandler(console_handler)

        # File handler with JSON formatting
        if log_to_file:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(
                LOG_DIR / f"battletwin_{component.lower()}.log",
                encoding="utf-8",
            )
            file_handler.setFormatter(JSONFormatter())
            file_handler.setLevel(logging.DEBUG)
            logger.addHandler(file_handler)

    adapter = TacticalLogAdapter(logger, {"component": component})
    _loggers[component] = adapter
    return adapter


def set_all_log_levels(level: str) -> None:
    """Set log level for all existing loggers."""
    lvl = getattr(logging, level.upper(), logging.DEBUG)
    for adapter in _loggers.values():
        adapter.logger.setLevel(lvl)


if __name__ == "__main__":
    log = get_logger("TEST_MODULE")
    log.debug("Routine diagnostic check", fields={"subsystem": "comms"})
    log.info("System initialized", fields={"units": 12})
    log.warning("Signal degraded on channel 3", fields={"snr_db": 5.2})
    log.error("NATS connection lost", fields={"server": "localhost:4222"})
    log.tactical("Contact report received", alert_level="IMMEDIATE", grid="38TML1234567890")
    log.tactical("FLASH traffic inbound", alert_level="FLASH", source="SIGINT")
    print("logger.py OK")

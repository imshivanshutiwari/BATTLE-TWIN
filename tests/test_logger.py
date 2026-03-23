"""Tests for utils/logger.py — tactical logging."""
import logging
from utils.logger import get_logger, TacticalFormatter, ALERT_LEVELS


def test_get_logger():
    log = get_logger("TEST_COMPONENT")
    assert isinstance(log, logging.Logger)
    assert log.name == "BT.TEST_COMPONENT"


def test_alert_levels_defined():
    assert "ROUTINE" in ALERT_LEVELS
    assert "FLASH" in ALERT_LEVELS
    assert "OVERRIDE" in ALERT_LEVELS


def test_logger_output(caplog):
    log = get_logger("TEST_LOG")
    with caplog.at_level(logging.DEBUG):
        log.info("Test message")
    assert any("Test message" in r.message for r in caplog.records)


def test_tactical_formatter():
    fmt = TacticalFormatter()
    record = logging.LogRecord("test", logging.INFO, "", 0, "msg", (), None)
    formatted = fmt.format(record)
    assert "msg" in formatted

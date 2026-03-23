"""Tests for evaluation/metrics.py."""

import numpy as np
from evaluation.metrics import C2Metrics


def test_c2_latency_under_threshold():
    m = C2Metrics()
    for _ in range(50):
        m.record_latency(np.random.exponential(30))
    stats = m.c2_latency_stats()
    assert stats["p95"] < 500  # under 500ms SLA


def test_twin_sync_accuracy():
    m = C2Metrics()
    for _ in range(50):
        m.record_sync_error(np.random.exponential(0.1))
    stats = m.sync_accuracy_stats()
    assert stats["within_1m_pct"] > 50


def test_sla_check():
    m = C2Metrics()
    for _ in range(100):
        m.record_latency(20)
        m.record_sync_error(0.1)
    sla = m.check_sla()
    assert sla["all_pass"] is True


def test_throughput_recording():
    m = C2Metrics()
    for _ in range(10):
        m.record_message("battlefield.state")
    for _ in range(5):
        m.record_message("battlefield.alert")
    stats = m.throughput_stats()
    assert stats["total_messages"] == 15
    assert stats["by_topic"]["battlefield.state"] == 10

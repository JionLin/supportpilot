"""Mutable runtime knobs for mock latency and failure injection.

@author jiaolin
"""

from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass
class MockRuntimeConfig:
    """In-process mock chaos settings (overridable at runtime)."""

    latency_ms: int = 0
    failure_rate: float = 0.0


_lock = threading.Lock()
_config = MockRuntimeConfig()


def get_mock_runtime() -> MockRuntimeConfig:
    """Return a snapshot of the current mock runtime config.

    Returns:
        MockRuntimeConfig: Copy of latency_ms and failure_rate.
    """
    with _lock:
        return MockRuntimeConfig(
            latency_ms=_config.latency_ms,
            failure_rate=_config.failure_rate,
        )


def set_mock_runtime(
    *,
    latency_ms: int | None = None,
    failure_rate: float | None = None,
) -> MockRuntimeConfig:
    """Update mock runtime settings.

    Args:
        latency_ms: Artificial delay in milliseconds (None keeps current).
        failure_rate: Probability of 503/timeout in [0, 1] (None keeps current).

    Returns:
        MockRuntimeConfig: Updated configuration snapshot.
    """
    with _lock:
        if latency_ms is not None:
            _config.latency_ms = max(0, latency_ms)
        if failure_rate is not None:
            clamped = max(0.0, min(1.0, failure_rate))
            _config.failure_rate = clamped
        return MockRuntimeConfig(
            latency_ms=_config.latency_ms,
            failure_rate=_config.failure_rate,
        )


def reset_mock_runtime(latency_ms: int = 0, failure_rate: float = 0.0) -> None:
    """Reset runtime config (used by tests and app startup).

    Args:
        latency_ms: Initial latency.
        failure_rate: Initial failure rate.
    """
    set_mock_runtime(latency_ms=latency_ms, failure_rate=failure_rate)

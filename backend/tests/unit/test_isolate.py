"""The child process that reads untrusted pages has limits of its own (round 3)."""

from __future__ import annotations

import resource

from licence_kyb.nodes.isolate import run_limited


def cpu_limit() -> int:
    """Runs in the child: its CPU-time limit in seconds."""
    return resource.getrlimit(resource.RLIMIT_CPU)[0]


def test_the_child_cannot_use_more_cpu_time_than_its_limit_allows() -> None:
    """If the parent dies, nothing watches the child: its own CPU limit still stops it."""
    limit = run_limited(cpu_limit, memory_mb=500, seconds=5)

    assert 0 < limit <= 10

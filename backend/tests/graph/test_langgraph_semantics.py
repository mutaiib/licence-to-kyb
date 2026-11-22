"""The LangGraph behaviour this design depends on, pinned by tests.

If a LangGraph upgrade changes any of these, the side-effect rules in data-model.md must be
re-examined before the upgrade merges.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from licence_kyb.graph import compile_graph, open_checkpointer, thread_config
from licence_kyb.state import RunState

CALLS: list[str] = []


def collect(state: RunState) -> dict[str, Any]:
    CALLS.append("collect")
    answer = interrupt({"flagged": ["expiry_date"]})
    return {"action": answer}


def apply(state: RunState) -> dict[str, Any]:
    CALLS.append("apply")
    return {"status": "awaiting_submit"}


def add_nodes(builder: StateGraph[RunState]) -> None:
    builder.add_node("collect", collect)
    builder.add_node("apply", apply)
    builder.add_edge(START, "collect")
    builder.add_edge("collect", "apply")
    builder.add_edge("apply", END)


def test_a_paused_run_survives_a_restart_and_resumes_with_the_reviewers_answer(
    tmp_path: Path,
) -> None:
    CALLS.clear()
    path = tmp_path / "checkpoints.sqlite3"
    graph = compile_graph(add_nodes, open_checkpointer(path))
    first = graph.invoke({"run_id": "r1"}, thread_config("r1"))
    assert "__interrupt__" in first

    # Simulate a restart: a new checkpointer and graph object over the same file.
    restarted = compile_graph(add_nodes, open_checkpointer(path))
    final = restarted.invoke(Command(resume={"expiry_date": "approve"}), thread_config("r1"))

    assert final["status"] == "awaiting_submit"
    assert final["action"] == {"expiry_date": "approve"}


def test_the_interrupting_node_runs_again_from_its_start_on_resume(tmp_path: Path) -> None:
    CALLS.clear()
    graph = compile_graph(add_nodes, open_checkpointer(tmp_path / "c.sqlite3"))
    graph.invoke({"run_id": "r2"}, thread_config("r2"))
    graph.invoke(Command(resume={"decisions": []}), thread_config("r2"))

    # This is why the collecting node must have no side effects.
    assert CALLS == ["collect", "collect", "apply"]


def test_an_empty_resume_payload_does_not_resume_the_run(tmp_path: Path) -> None:
    """So the API always wraps the reviewer's input in a non-empty payload."""
    CALLS.clear()
    graph = compile_graph(add_nodes, open_checkpointer(tmp_path / "e.sqlite3"))
    graph.invoke({"run_id": "r3"}, thread_config("r3"))

    out = graph.invoke(Command(resume={}), thread_config("r3"))

    assert "__interrupt__" in out
    assert "apply" not in CALLS

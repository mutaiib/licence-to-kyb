"""Graph wiring: a LangGraph ``StateGraph`` with a SQLite checkpointer.

Rules for nodes (data-model.md, "Writes and resumption"):
- a node that calls ``interrupt()`` only collects input; on resume LangGraph runs it again
  from its start, so it must have no side effects;
- side effects (decisions, audit events, form versions, submissions) happen in dedicated
  nodes after the interrupt, and every write is keyed, so re-running a node writes nothing new;
- a resume payload is never empty: ``Command(resume={})`` does not resume the run, so the API
  always sends a wrapped payload such as ``{"decisions": [...], "action": ...}``.

Each rule is pinned by tests/graph/test_langgraph_semantics.py.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph

from licence_kyb.state import RunState

GraphBuilder = Callable[[StateGraph[RunState]], None]


def open_checkpointer(path: Path) -> SqliteSaver:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    return SqliteSaver(conn)


def compile_graph(add_nodes: GraphBuilder, checkpointer: SqliteSaver) -> CompiledStateGraph[Any]:
    """Build a graph with ``add_nodes`` and compile it with durable checkpoints."""
    builder: StateGraph[RunState] = StateGraph(RunState)
    add_nodes(builder)
    return builder.compile(checkpointer=checkpointer)


def thread_config(run_id: str) -> RunnableConfig:
    """One LangGraph thread per run."""
    return {"configurable": {"thread_id": run_id}}

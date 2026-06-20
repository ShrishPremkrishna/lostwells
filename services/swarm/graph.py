"""LangGraph `Send` map-reduce swarm (spec §2.3, BUILD_PLAN §5).

A router fans out one `Send` per well to the `investigate` node; results fan in
through an `operator.add` reducer. Per-node try/except lives in the investigator
(returns a partial/error sentinel instead of raising), and a checkpointer lets a
run resume after a superstep failure. `max_concurrency` (set at invoke time)
throttles parallel Claude calls to avoid 429s.
"""
from __future__ import annotations

import operator
import os
import sys
from typing import Annotated, TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from langgraph.checkpoint.memory import MemorySaver

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import investigator  # noqa: E402


class SwarmState(TypedDict):
    wells: list
    dossiers: Annotated[list, operator.add]


def route_to_investigators(state: SwarmState):
    """Map step: one independent Send (branch) per well."""
    return [Send("investigate", {"well": w}) for w in state["wells"]]


def investigate(state: dict) -> dict:
    """Worker node — isolated per-well; never raises (sentinel on failure)."""
    return {"dossiers": [investigator.investigate_well(state["well"])]}


def build_graph():
    g = StateGraph(SwarmState)
    g.add_node("investigate", investigate)
    g.add_conditional_edges(START, route_to_investigators, ["investigate"])
    g.add_edge("investigate", END)
    return g.compile(checkpointer=MemorySaver())

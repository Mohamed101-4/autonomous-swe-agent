"""LangGraph wiring: planner -> localizer -> patcher -> verifier, with retries."""

from __future__ import annotations

from collections.abc import Callable

from langgraph.graph import END, START, StateGraph

from swe_agent.state import AgentState

Node = Callable[[AgentState], AgentState]


def report(state: AgentState) -> AgentState:
    status = "resolved" if state.get("status") == "resolved" else "failed"
    log = list(state.get("log", []))
    log.append(f"report: {status} after {state.get('attempts', 0)} patch attempt(s)")
    return {"status": status, "log": log}


def build_graph(planner: Node, localizer: Node, patcher: Node, verifier: Node, max_retries: int):
    """Compile the graph. A failed patch returns to the patcher up to `max_retries` times."""
    max_attempts = 1 + max_retries

    def after_verifier(state: AgentState) -> str:
        if state.get("status") == "resolved":
            return "report"
        return "patcher" if state.get("attempts", 0) < max_attempts else "report"

    graph = StateGraph(AgentState)
    graph.add_node("planner", planner)
    graph.add_node("localizer", localizer)
    graph.add_node("patcher", patcher)
    graph.add_node("verifier", verifier)
    graph.add_node("report", report)
    graph.add_edge(START, "planner")
    graph.add_edge("planner", "localizer")
    graph.add_edge("localizer", "patcher")
    graph.add_edge("patcher", "verifier")
    graph.add_conditional_edges("verifier", after_verifier, ["patcher", "report"])
    graph.add_edge("report", END)
    return graph.compile()

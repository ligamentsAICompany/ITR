"""LangGraph orchestration layer for ITR classification workflows.

The agent talks to the existing FastAPI API surface only. It does not import or
call the deterministic classifier directly, so deterministic authority remains
behind `/v1/itr-decision` and related endpoints.
"""

import logging
from typing import Any, Protocol, TypedDict

import httpx
from langgraph.graph import END, START, StateGraph

logger = logging.getLogger("itr_agent")

HIGH_RISK_FIELDS = [
    "foreign_assets",
    "business_profession",
    "capital_gains",
    "exemptions_flags",
]


class AgentAPIClient(Protocol):
    def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Call a versioned API endpoint and return its JSON response."""


class HTTPAgentAPIClient:
    """HTTP client for running the agent against a live FastAPI server."""

    def __init__(self, base_url: str = "http://127.0.0.1:8000") -> None:
        self.base_url = base_url.rstrip("/")

    def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        with httpx.Client(base_url=self.base_url, timeout=10.0) as client:
            response = client.post(path, json=payload)
            response.raise_for_status()
            return response.json()


class ITRAgentState(TypedDict, total=False):
    profile: dict[str, Any]
    decision: dict[str, Any]
    missing_fields: list[str]
    questions_asked: list[str]
    confidence: str
    escalation: bool
    escalation_reason: str
    clarification_iterations: int
    explanation: dict[str, Any]
    execution_log: list[str]
    max_clarification_iterations: int
    next_route: str
    routing_reason: str


class ITRAgent:
    """LangGraph-based API orchestration for ITR decision workflows."""

    def __init__(
        self,
        api_client: AgentAPIClient,
        *,
        max_clarification_iterations: int = 3,
    ) -> None:
        self.api_client = api_client
        self.max_clarification_iterations = max_clarification_iterations
        self.graph = self._build_graph().compile()

    def run(self, profile: dict[str, Any]) -> ITRAgentState:
        initial_state: ITRAgentState = {
            "profile": profile,
            "decision": {},
            "missing_fields": [],
            "questions_asked": [],
            "confidence": "",
            "escalation": False,
            "escalation_reason": "",
            "clarification_iterations": 0,
            "execution_log": [],
            "max_clarification_iterations": self.max_clarification_iterations,
            "next_route": "",
            "routing_reason": "",
        }
        return self.graph.invoke(initial_state)

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(ITRAgentState)
        graph.add_node("intake_analyzer", self.intake_analyzer)
        graph.add_node("decision_node", self.decision_node)
        graph.add_node("missing_fields_node", self.missing_fields_node)
        graph.add_node("decision_router_node", self.decision_router_node)
        graph.add_node("clarification_node", self.clarification_node)
        graph.add_node("explanation_node", self.explanation_node)
        graph.add_node("escalation_node", self.escalation_node)

        graph.add_edge(START, "intake_analyzer")
        graph.add_edge("intake_analyzer", "decision_node")
        graph.add_edge("decision_node", "missing_fields_node")
        graph.add_edge("missing_fields_node", "decision_router_node")
        graph.add_conditional_edges(
            "decision_router_node",
            self.route_after_decision_router,
            {
                "clarify": "clarification_node",
                "explain": "explanation_node",
                "escalate": "escalation_node",
            },
        )
        graph.add_edge("clarification_node", "decision_node")
        graph.add_conditional_edges(
            "explanation_node",
            self.route_after_explanation,
            {"escalate": "escalation_node", "end": END},
        )
        graph.add_edge("escalation_node", END)
        return graph

    def intake_analyzer(self, state: ITRAgentState) -> ITRAgentState:
        return self._log(state, "intake_analyzer: profile received")

    def decision_node(self, state: ITRAgentState) -> ITRAgentState:
        self._log(state, "decision_node: calling /v1/itr-decision")
        decision = self.api_client.post("/v1/itr-decision", state["profile"])
        state["decision"] = decision
        state["confidence"] = decision.get("confidence", "")
        return self._log(
            state,
            f"decision_node: candidate={decision.get('candidate_itr')} confidence={state['confidence']}",
        )

    def missing_fields_node(self, state: ITRAgentState) -> ITRAgentState:
        self._log(state, "missing_fields_node: calling /v1/missing-fields")
        response = self.api_client.post("/v1/missing-fields", state["profile"])
        state["missing_fields"] = response.get("missing_fields", [])
        return self._log(state, f"missing_fields_node: missing={state['missing_fields']}")

    def decision_router_node(self, state: ITRAgentState) -> ITRAgentState:
        route, reason = self._determine_route(state)
        state["next_route"] = route
        state["routing_reason"] = reason
        if route == "escalate":
            state["escalation_reason"] = reason
        return self._log(state, f"decision_router_node: route={route} reason={reason}")

    def clarification_node(self, state: ITRAgentState) -> ITRAgentState:
        self._log(state, "clarification_node: calling /v1/clarify")
        response = self.api_client.post(
            "/v1/clarify",
            {
                "missing_fields": state.get("missing_fields", []),
                "context": {"decision": state.get("decision", {})},
            },
        )
        question = response.get("question", "")
        state.setdefault("questions_asked", []).append(question)
        state["clarification_iterations"] = state.get("clarification_iterations", 0) + 1
        return self._log(
            state,
            f"clarification_node: iteration={state['clarification_iterations']} question={question}",
        )

    def explanation_node(self, state: ITRAgentState) -> ITRAgentState:
        self._log(state, "explanation_node: calling /v1/explain")
        state["explanation"] = self.api_client.post("/v1/explain", state["decision"])
        return self._log(state, "explanation_node: explanation received")

    def escalation_node(self, state: ITRAgentState) -> ITRAgentState:
        state["escalation"] = True
        if not state.get("escalation_reason"):
            if state.get("routing_reason"):
                state["escalation_reason"] = state["routing_reason"]
            if state.get("missing_fields") and state.get("clarification_iterations", 0) >= state.get(
                "max_clarification_iterations",
                self.max_clarification_iterations,
            ):
                state["escalation_reason"] = "clarification_limit_reached"
            else:
                state["escalation_reason"] = "low_confidence_or_review_flag"
        return self._log(state, f"escalation_node: reason={state['escalation_reason']}")

    def route_after_decision_router(self, state: ITRAgentState) -> str:
        return state.get("next_route", "escalate")

    def _determine_route(self, state: ITRAgentState) -> tuple[str, str]:
        missing_fields = state.get("missing_fields", [])
        if missing_fields:
            if state.get("clarification_iterations", 0) < state.get(
                "max_clarification_iterations",
                self.max_clarification_iterations,
            ):
                return "clarify", "clarification_available"
            if self._has_high_risk_missing_fields(missing_fields):
                return "escalate", "unresolved_high_risk_missing_fields"
            return "escalate", "clarification_limit_reached"
        if state.get("confidence") == "low":
            return "escalate", "low_confidence"
        return "explain", "no_missing_fields"

    def _has_high_risk_missing_fields(self, missing_fields: list[str]) -> bool:
        return any(
            any(high_risk in missing_field for high_risk in HIGH_RISK_FIELDS)
            for missing_field in missing_fields
        )

    def route_after_explanation(self, state: ITRAgentState) -> str:
        decision = state.get("decision", {})
        reason_codes = decision.get("reason_codes", [])
        if state.get("confidence") == "low" or "HUMAN_REVIEW_SIGNAL_PRESENT" in reason_codes:
            state["escalation_reason"] = "low_confidence_or_review_flag"
            return "escalate"
        return "end"

    def _log(self, state: ITRAgentState, message: str) -> ITRAgentState:
        state.setdefault("execution_log", []).append(message)
        logger.info(message)
        return state

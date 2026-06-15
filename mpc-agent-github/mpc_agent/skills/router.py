from __future__ import annotations

from typing import Any

from .registry import get_skill, list_skills


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _collect_context_text(payload: dict[str, Any]) -> str:
    requirement = str(payload.get("requirement", "")).lower()
    parsed = payload.get("parsed_requirement")
    if isinstance(parsed, dict):
        fields = [
            parsed.get("operation", ""),
            parsed.get("party_count_mode", ""),
            parsed.get("circuit_domain", ""),
            parsed.get("math_structure", ""),
            parsed.get("secret_sharing", ""),
            parsed.get("security_model", ""),
            parsed.get("corruption_model", ""),
            parsed.get("corruption_timing", ""),
            parsed.get("network_model", ""),
            parsed.get("corruption_threshold", ""),
            parsed.get("security_goal", ""),
            parsed.get("latency_priority", ""),
            parsed.get("bandwidth_priority", ""),
            parsed.get("target", ""),
        ]
        requirement = " ".join([requirement, *[str(item).lower() for item in fields]])
    return requirement


def recommend_skills(payload: dict[str, Any]) -> dict[str, Any]:
    requirement = _collect_context_text(payload)
    execute = bool(payload.get("execute", False))
    selected: list[str] = []
    reasons: dict[str, str] = {}

    def add(name: str, reason: str) -> None:
        if get_skill(name) is None:
            return
        if name not in selected:
            selected.append(name)
        reasons[name] = reason

    # Core skill chain
    add("analyze_requirement", "Core step: parse requirement into MPC decision dimensions.")
    add("select_protocol", "Core step: choose protocol candidates and final protocol.")
    add("generate_configuration", "Core step: convert decision into runnable configuration.")
    add("explain_decision", "Core step: provide transparent decision explanation.")

    # Legacy compatibility skill (policy routing)
    add("protocol-selection", "Compatibility skill for policy routing and protocol ranking.")

    if _contains_any(
        requirement,
        ["aggregation", "sum", "mean", "average", "statistics", "machine learning", "ml", "arithmetic"],
    ):
        add("arithmetic-aggregation", "Arithmetic/aggregation workload detected.")
        add("optimize_circuit", "Arithmetic workload benefits from circuit optimization guidance.")

    if _contains_any(
        requirement,
        ["comparison", "compare", "sort", "auction", "psi", "millionaire", "less than", "greater than", "boolean"],
    ):
        add("boolean-comparison", "Boolean/comparison workload detected.")
        add("optimize_circuit", "Boolean workload benefits from depth-sensitive optimizations.")

    if execute or _contains_any(requirement, ["compile", "run", "execute", "mp-spdz"]):
        add("deploy_and_monitor", "Execution intent detected.")
        add("mpspdz-execution", "Execution intent detected; use deterministic script pipeline.")

    if _contains_any(
        requirement,
        ["windows", "wsl", "permission denied", "not enough inputs", "winerror", "access is denied"],
    ):
        add("windows-mpspdz-debug", "Windows/WSL diagnostic signals detected.")

    if _contains_any(requirement, ["malicious", "covert", "production_candidate", "production"]):
        add("simulate_threat", "Security-sensitive scenario detected; run threat simulation.")

    explicit = payload.get("skills")
    if isinstance(explicit, list):
        for item in explicit:
            if isinstance(item, str) and get_skill(item):
                add(item, "Explicitly requested in payload.")

    workflow = [
        {"stage": "analyze", "skill": "analyze_requirement", "enabled": "analyze_requirement" in selected},
        {"stage": "select", "skill": "select_protocol", "enabled": "select_protocol" in selected},
        {"stage": "optimize", "skill": "optimize_circuit", "enabled": "optimize_circuit" in selected},
        {"stage": "generate", "skill": "generate_configuration", "enabled": "generate_configuration" in selected},
        {"stage": "deploy", "skill": "deploy_and_monitor", "enabled": "deploy_and_monitor" in selected},
        {"stage": "explain", "skill": "explain_decision", "enabled": "explain_decision" in selected},
        {"stage": "threat", "skill": "simulate_threat", "enabled": "simulate_threat" in selected},
    ]

    return {
        "recommended": selected,
        "reasons": reasons,
        "workflow": workflow,
        "available": list_skills(),
    }

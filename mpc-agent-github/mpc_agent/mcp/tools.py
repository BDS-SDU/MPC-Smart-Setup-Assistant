from __future__ import annotations

from typing import Any, Callable

from mpc_agent.adapters.config_tool import generate_configuration_tool
from mpc_agent.adapters.parse_tool import parse_requirement_tool
from mpc_agent.adapters.policy_tool import rank_protocols_tool
from mpc_agent.adapters.runner_tool import (
    compile_program_tool,
    diagnose_execution_failure,
    run_protocol_tool,
)
from mpc_agent.case_store import find_similar_cases, list_cases, record_feedback
from mpc_agent.integrations.external_api import call_external_api, list_external_systems
from mpc_agent.knowledge_base import retrieve_knowledge
from mpc_agent.models import ParsedRequirement
from mpc_agent.open_source_catalog import recommend_open_source_protocols
from mpc_agent.runtime_signals import (
    collect_runtime_signals,
    probe_network,
    query_local_hardware,
    summarize_party_hardware,
)
from mpc_agent.skills.executor import execute_skill
from mpc_agent.skills.router import recommend_skills


ToolHandler = Callable[[dict[str, Any]], dict[str, Any]]


def _tool_parse_requirement(arguments: dict[str, Any]) -> dict[str, Any]:
    requirement = str(arguments.get("requirement", "")).strip()
    parties_raw = arguments.get("parties")
    parties = parties_raw if isinstance(parties_raw, int) else None
    extras = {
        key: value
        for key, value in arguments.items()
        if key
        in {
            "operation",
            "party_count_mode",
            "circuit_domain",
            "math_structure",
            "secret_sharing",
            "preprocessing_preference",
            "security_model",
            "corruption_model",
            "corruption_timing",
            "network_model",
            "corruption_threshold",
            "security_goal",
            "latency_priority",
            "bandwidth_priority",
            "target",
        }
    }
    return {
        "parsed_requirement": parse_requirement_tool(requirement, parties, extras=extras),
    }


def _tool_rank_protocols(arguments: dict[str, Any]) -> dict[str, Any]:
    parsed = arguments.get("parsed_requirement")
    if not isinstance(parsed, dict):
        requirement = str(arguments.get("requirement", "")).strip()
        parties_raw = arguments.get("parties")
        parties = parties_raw if isinstance(parties_raw, int) else None
        parsed = parse_requirement_tool(requirement, parties)

    top_k_raw = arguments.get("top_k", 4)
    top_k = top_k_raw if isinstance(top_k_raw, int) else 4

    skills_raw = arguments.get("skills")
    skills = [item for item in skills_raw if isinstance(item, str)] if isinstance(skills_raw, list) else None

    protocol_bias_raw = arguments.get("protocol_bias")
    protocol_bias = (
        {str(k): int(v) for k, v in protocol_bias_raw.items()}
        if isinstance(protocol_bias_raw, dict)
        else None
    )

    return {
        "parsed_requirement": parsed,
        "candidates": rank_protocols_tool(parsed, top_k=top_k, skills=skills, protocol_bias=protocol_bias),
    }


def _tool_recommend_open_source_protocols(arguments: dict[str, Any]) -> dict[str, Any]:
    parsed = arguments.get("parsed_requirement")
    if not isinstance(parsed, dict):
        requirement = str(arguments.get("requirement", "")).strip()
        parties_raw = arguments.get("parties")
        parties = parties_raw if isinstance(parties_raw, int) else None
        extras = {
            key: value
            for key, value in arguments.items()
            if key
            in {
                "operation",
                "party_count_mode",
                "circuit_domain",
                "math_structure",
                "secret_sharing",
                "preprocessing_preference",
                "security_model",
                "corruption_model",
                "corruption_timing",
                "network_model",
                "corruption_threshold",
                "security_goal",
                "latency_priority",
                "bandwidth_priority",
                "target",
            }
        }
        parsed = parse_requirement_tool(requirement, parties, extras=extras)

    top_k_raw = arguments.get("top_k", 6)
    top_k = top_k_raw if isinstance(top_k_raw, int) else 6
    return {
        "parsed_requirement": parsed,
        "recommendations": recommend_open_source_protocols(ParsedRequirement(**parsed), limit=top_k),
    }


def _tool_generate_configuration(arguments: dict[str, Any]) -> dict[str, Any]:
    payload = dict(arguments.get("payload", arguments))
    payload["execute"] = False
    result = generate_configuration_tool(payload)
    return {
        "parsed_requirement": result.get("parsed_requirement"),
        "candidates": result.get("candidates"),
        "skills": result.get("skills"),
        "open_source_recommendations": result.get("open_source_recommendations"),
        "final_configuration": result.get("final_configuration"),
        "decision_explanation": result.get("decision_explanation"),
    }


def _tool_compile_program(arguments: dict[str, Any]) -> dict[str, Any]:
    payload = dict(arguments.get("payload", arguments))
    config_result = generate_configuration_tool({**payload, "execute": False})
    execution = compile_program_tool(
        payload,
        config_result["parsed_requirement"],
        config_result["final_configuration"],
    )
    return {
        "parsed_requirement": config_result["parsed_requirement"],
        "open_source_recommendations": config_result.get("open_source_recommendations"),
        "final_configuration": config_result["final_configuration"],
        "execution": execution,
    }


def _tool_run_protocol(arguments: dict[str, Any]) -> dict[str, Any]:
    payload = dict(arguments.get("payload", arguments))
    config_result = generate_configuration_tool({**payload, "execute": False})
    execution = run_protocol_tool(
        payload,
        config_result["parsed_requirement"],
        config_result["final_configuration"],
    )
    return {
        "parsed_requirement": config_result["parsed_requirement"],
        "open_source_recommendations": config_result.get("open_source_recommendations"),
        "final_configuration": config_result["final_configuration"],
        "execution": execution,
    }


def _tool_diagnose_failure(arguments: dict[str, Any]) -> dict[str, Any]:
    execution = arguments.get("execution")
    if not isinstance(execution, dict):
        raise ValueError("`execution` must be a dict.")
    skills_raw = arguments.get("skills")
    skills = [item for item in skills_raw if isinstance(item, str)] if isinstance(skills_raw, list) else None
    return diagnose_execution_failure(execution, skills=skills)


def _tool_recommend_skills(arguments: dict[str, Any]) -> dict[str, Any]:
    return recommend_skills(arguments)


def _tool_execute_skill(arguments: dict[str, Any]) -> dict[str, Any]:
    name = str(arguments.get("name", "")).strip()
    if not name:
        raise ValueError("`name` is required.")
    payload = arguments.get("payload", {})
    if not isinstance(payload, dict):
        raise ValueError("`payload` must be a JSON object.")
    return execute_skill(name, payload)


def _tool_retrieve_knowledge(arguments: dict[str, Any]) -> dict[str, Any]:
    query = str(arguments.get("query", "")).strip()
    if not query:
        raise ValueError("`query` is required.")
    top_k_raw = arguments.get("top_k", 4)
    top_k = top_k_raw if isinstance(top_k_raw, int) else 4
    return retrieve_knowledge(query, top_k=top_k)


def _tool_list_cases(arguments: dict[str, Any]) -> dict[str, Any]:
    limit_raw = arguments.get("limit", 20)
    limit = limit_raw if isinstance(limit_raw, int) else 20
    return {"cases": list_cases(limit=limit)}


def _tool_find_similar_cases(arguments: dict[str, Any]) -> dict[str, Any]:
    parsed = arguments.get("parsed_requirement")
    if not isinstance(parsed, dict):
        requirement = str(arguments.get("requirement", "")).strip()
        parties_raw = arguments.get("parties")
        parties = parties_raw if isinstance(parties_raw, int) else None
        parsed = parse_requirement_tool(requirement, parties)

    limit_raw = arguments.get("limit", 5)
    limit = limit_raw if isinstance(limit_raw, int) else 5
    return {
        "parsed_requirement": parsed,
        "similar_cases": find_similar_cases(parsed, limit=limit),
    }


def _tool_record_case_feedback(arguments: dict[str, Any]) -> dict[str, Any]:
    case_id = str(arguments.get("case_id", "")).strip()
    if not case_id:
        raise ValueError("`case_id` is required.")
    feedback = arguments.get("feedback", {})
    if not isinstance(feedback, dict):
        raise ValueError("`feedback` must be a JSON object.")
    return {
        "case": record_feedback(case_id, feedback),
    }


def _tool_probe_network(arguments: dict[str, Any]) -> dict[str, Any]:
    hosts_raw = arguments.get("hosts")
    hosts = hosts_raw if isinstance(hosts_raw, list) else []
    if not hosts:
        raise ValueError("`hosts` is required and must be a list.")
    count_raw = arguments.get("count", 3)
    timeout_raw = arguments.get("timeout_ms", 1000)
    count = count_raw if isinstance(count_raw, int) else 3
    timeout_ms = timeout_raw if isinstance(timeout_raw, int) else 1000
    return probe_network(hosts, count=count, timeout_ms=timeout_ms)


def _tool_query_hardware(arguments: dict[str, Any]) -> dict[str, Any]:
    parties_raw = arguments.get("parties")
    if isinstance(parties_raw, list):
        summary = summarize_party_hardware(parties_raw, use_local_when_empty=False)
        local = query_local_hardware()
        return {
            "local": local,
            "parties": summary,
        }
    return {
        "local": query_local_hardware(),
    }


def _tool_collect_runtime_signals(arguments: dict[str, Any]) -> dict[str, Any]:
    payload_raw = arguments.get("payload", arguments)
    payload = payload_raw if isinstance(payload_raw, dict) else {}

    parsed = arguments.get("parsed_requirement")
    if not isinstance(parsed, dict):
        requirement = str(payload.get("requirement", arguments.get("requirement", ""))).strip()
        parties_raw = payload.get("parties", arguments.get("parties"))
        parties = parties_raw if isinstance(parties_raw, int) else None
        parsed = parse_requirement_tool(requirement, parties)
    return collect_runtime_signals(payload, parsed)


def _tool_list_external_systems(arguments: dict[str, Any]) -> dict[str, Any]:
    _ = arguments
    return {"systems": list_external_systems()}


def _tool_call_external_api(arguments: dict[str, Any]) -> dict[str, Any]:
    system_name = str(arguments.get("system_name", "")).strip()
    if not system_name:
        raise ValueError("`system_name` is required.")
    method = str(arguments.get("method", "GET")).strip().upper()
    path = str(arguments.get("path", "")).strip()
    query = arguments.get("query")
    headers = arguments.get("headers")
    body = arguments.get("body")
    timeout_raw = arguments.get("timeout_seconds")
    timeout_seconds = int(timeout_raw) if isinstance(timeout_raw, int) else None
    if query is not None and not isinstance(query, dict):
        raise ValueError("`query` must be a JSON object when provided.")
    if headers is not None and not isinstance(headers, dict):
        raise ValueError("`headers` must be a JSON object when provided.")
    return call_external_api(
        system_name=system_name,
        method=method,
        path=path,
        query=query if isinstance(query, dict) else None,
        headers=headers if isinstance(headers, dict) else None,
        body=body,
        timeout_seconds=timeout_seconds,
    )


TOOLS: dict[str, dict[str, Any]] = {
    "parse_requirement": {
        "description": "Parse MPC requirement text into normalized decision dimensions.",
        "handler": _tool_parse_requirement,
    },
    "rank_protocols": {
        "description": "Rank protocol candidates from parsed requirement or raw requirement text.",
        "handler": _tool_rank_protocols,
    },
    "recommend_open_source_protocols": {
        "description": "Match structured requirements against curated open-source MPC implementations.",
        "handler": _tool_recommend_open_source_protocols,
    },
    "generate_configuration": {
        "description": "Generate final protocol configuration without executing MP-SPDZ.",
        "handler": _tool_generate_configuration,
    },
    "compile_mpspdz_program": {
        "description": "Generate and compile MPC program via MP-SPDZ (compile_only mode).",
        "handler": _tool_compile_program,
    },
    "run_mpspdz_protocol": {
        "description": "Generate, compile, and run selected protocol via MP-SPDZ.",
        "handler": _tool_run_protocol,
    },
    "diagnose_execution_failure": {
        "description": "Provide concise diagnosis and next action from execution output.",
        "handler": _tool_diagnose_failure,
    },
    "recommend_skills": {
        "description": "Recommend skill chain for a requirement payload.",
        "handler": _tool_recommend_skills,
    },
    "execute_skill": {
        "description": "Execute a concrete skill entrypoint.",
        "handler": _tool_execute_skill,
    },
    "retrieve_knowledge": {
        "description": "Retrieve relevant MPC knowledge snippets/sections from local knowledge base.",
        "handler": _tool_retrieve_knowledge,
    },
    "list_cases": {
        "description": "List persisted historical cases from local case store.",
        "handler": _tool_list_cases,
    },
    "find_similar_cases": {
        "description": "Find similar historical cases from parsed requirement or raw requirement.",
        "handler": _tool_find_similar_cases,
    },
    "record_case_feedback": {
        "description": "Attach feedback metadata to an existing case_id.",
        "handler": _tool_record_case_feedback,
    },
    "probe_network": {
        "description": "Probe party network RTT/loss and summarize bandwidth hints.",
        "handler": _tool_probe_network,
    },
    "query_hardware": {
        "description": "Query local hardware and optionally summarize per-party hardware specs.",
        "handler": _tool_query_hardware,
    },
    "collect_runtime_signals": {
        "description": "Collect network/hardware runtime signals and infer protocol bias.",
        "handler": _tool_collect_runtime_signals,
    },
    "list_external_systems": {
        "description": "List configured third-party API systems from EXTERNAL_SYSTEMS_JSON.",
        "handler": _tool_list_external_systems,
    },
    "call_external_api": {
        "description": "Call a configured third-party API by system name.",
        "handler": _tool_call_external_api,
    },
}


def list_tools() -> list[dict[str, str]]:
    return [
        {"name": name, "description": str(spec["description"])}
        for name, spec in TOOLS.items()
    ]


def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    spec = TOOLS.get(name)
    if spec is None:
        raise KeyError(f"Unknown tool: {name}")
    handler = spec["handler"]
    return handler(arguments)

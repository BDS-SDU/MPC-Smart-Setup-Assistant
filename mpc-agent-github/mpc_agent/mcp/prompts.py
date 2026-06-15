from __future__ import annotations

import json
from typing import Any


def _prompt_choose_protocol(arguments: dict[str, Any]) -> dict[str, Any]:
    requirement = str(arguments.get("requirement", "")).strip()
    candidates = arguments.get("candidates", [])
    prompt = (
        "You are an MPC protocol planner.\n"
        "Given requirement text and protocol candidates, select one protocol_id from the candidate list.\n"
        "Explain choice, trade-offs, and assumptions in concise Chinese.\n\n"
        f"Requirement:\n{requirement}\n\n"
        f"Candidates:\n{json.dumps(candidates, ensure_ascii=False, indent=2)}"
    )
    return {"prompt": prompt}


def _prompt_explain_config(arguments: dict[str, Any]) -> dict[str, Any]:
    final_configuration = arguments.get("final_configuration", {})
    knowledge_context = arguments.get("knowledge_context", {})
    prompt = (
        "Explain this MPC final configuration to an engineer.\n"
        "Output sections: protocol rationale / security assumptions / performance implications / operational checks.\n\n"
        f"Configuration:\n{json.dumps(final_configuration, ensure_ascii=False, indent=2)}\n\n"
        f"Knowledge:\n{json.dumps(knowledge_context, ensure_ascii=False, indent=2)}"
    )
    return {"prompt": prompt}


def _prompt_debug_failure(arguments: dict[str, Any]) -> dict[str, Any]:
    execution = arguments.get("execution", {})
    prompt = (
        "Diagnose MP-SPDZ execution failure.\n"
        "Output sections: root cause / immediate fix / verification steps.\n\n"
        f"Execution:\n{json.dumps(execution, ensure_ascii=False, indent=2)}"
    )
    return {"prompt": prompt}


def _prompt_simulate_threat(arguments: dict[str, Any]) -> dict[str, Any]:
    final_configuration = arguments.get("final_configuration", {})
    parsed_requirement = arguments.get("parsed_requirement", {})
    prompt = (
        "Simulate security risks for this MPC setup.\n"
        "Output sections: threat assumptions / potential attacks / mitigations / residual risk.\n\n"
        f"Parsed requirement:\n{json.dumps(parsed_requirement, ensure_ascii=False, indent=2)}\n\n"
        f"Final configuration:\n{json.dumps(final_configuration, ensure_ascii=False, indent=2)}"
    )
    return {"prompt": prompt}


PROMPTS: dict[str, dict[str, Any]] = {
    "choose-protocol": {
        "description": "Build a protocol-selection explanation prompt.",
        "renderer": _prompt_choose_protocol,
    },
    "explain-config": {
        "description": "Build a human-readable final-configuration explanation prompt.",
        "renderer": _prompt_explain_config,
    },
    "debug-mpspdz-failure": {
        "description": "Build a failure-diagnosis prompt from execution output.",
        "renderer": _prompt_debug_failure,
    },
    "simulate-threat": {
        "description": "Build a threat-simulation prompt from parsed requirement/configuration.",
        "renderer": _prompt_simulate_threat,
    },
}


def list_prompts() -> list[dict[str, str]]:
    return [
        {"name": name, "description": str(spec["description"])}
        for name, spec in PROMPTS.items()
    ]


def render_prompt(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    spec = PROMPTS.get(name)
    if spec is None:
        raise KeyError(f"Unknown prompt: {name}")
    renderer = spec["renderer"]
    return renderer(arguments)

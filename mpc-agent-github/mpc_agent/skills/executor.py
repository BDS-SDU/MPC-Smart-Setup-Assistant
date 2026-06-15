from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


SKILLS_ROOT = Path(__file__).resolve().parent


def _load_script_module(skill_name: str, script_name: str):
    script_path = SKILLS_ROOT / skill_name / "scripts" / script_name
    if not script_path.exists():
        raise FileNotFoundError(f"Skill script not found: {script_path}")

    module_name = f"skill_{skill_name.replace('-', '_')}_{script_name.replace('.', '_')}"
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load skill script: {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def _windows_debug_template(execution: dict[str, Any]) -> dict[str, Any]:
    reason = str(execution.get("reason", "")).strip()
    run_stderr = str(execution.get("run", {}).get("stderr", "")).strip()
    compile_stderr = str(execution.get("compile", {}).get("stderr", "")).strip()
    text = "\n".join([reason, run_stderr, compile_stderr]).lower()

    steps: list[str]
    commands: list[str]
    diagnosis = reason or run_stderr or compile_stderr or "Unknown execution failure."

    if "permission denied" in text or "access is denied" in text:
        steps = [
            "Ensure current user has write permissions for MP-SPDZ root, Programs/Source and Player-Data.",
            "Run compile_only=true first to validate compilation path, then run execute=true.",
        ]
        commands = [
            "icacls <MPSPDZ_HOME> /grant %USERNAME%:(OI)(CI)F /T",
        ]
    elif "not enough inputs" in text or "input-p" in text:
        steps = [
            "Create Player-Data/Input-P*-0 files for each party.",
            "Ensure -N party count matches number of input files.",
        ]
        commands = [
            "dir <MPSPDZ_HOME>\\Player-Data\\Input-P*-0",
        ]
    elif "runtime binary not found" in text or "-party.x" in text:
        steps = [
            "Build runtime binary before executing protocol script.",
            "Ensure script/runtime prefix is aligned (for example mascot -> mascot-party.x).",
        ]
        commands = [
            "cd <MPSPDZ_HOME> && make mascot-party.x",
        ]
    elif "script" in text and "not found" in text:
        steps = [
            "Check protocol script exists under Scripts directory.",
            "Prefer .bat scripts on native Windows.",
        ]
        commands = [
            "dir <MPSPDZ_HOME>\\Scripts",
        ]
    else:
        steps = [
            "Inspect execution.compile/execution.run stderr and stdout.",
            "Use compile_only=true to isolate compilation from runtime issues.",
            "Verify MPSPDZ_HOME used by request and server process are consistent.",
        ]
        commands = []

    return {
        "skill": "windows-mpspdz-debug",
        "template": "windows-default-recovery",
        "diagnosis": diagnosis,
        "steps": steps,
        "commands": commands,
    }


def _execute_analyze_requirement(payload: dict[str, Any]) -> dict[str, Any]:
    from mpc_agent.adapters.parse_tool import parse_requirement_tool

    requirement = str(payload.get("requirement", "")).strip()
    parties_raw = payload.get("parties")
    parties = parties_raw if isinstance(parties_raw, int) else None
    parsed = parse_requirement_tool(requirement, parties, extras=payload)
    return {
        "skill": "analyze_requirement",
        "parsed_requirement": parsed,
    }


def _execute_select_protocol(payload: dict[str, Any]) -> dict[str, Any]:
    from mpc_agent.adapters.parse_tool import parse_requirement_tool
    from mpc_agent.adapters.policy_tool import rank_protocols_tool

    parsed = payload.get("parsed_requirement")
    if not isinstance(parsed, dict):
        requirement = str(payload.get("requirement", "")).strip()
        parties_raw = payload.get("parties")
        parties = parties_raw if isinstance(parties_raw, int) else None
        parsed = parse_requirement_tool(requirement, parties)

    top_k_raw = payload.get("top_k", 4)
    top_k = top_k_raw if isinstance(top_k_raw, int) else 4
    skills = payload.get("skills")
    skill_names = [item for item in skills if isinstance(item, str)] if isinstance(skills, list) else None
    protocol_bias_raw = payload.get("protocol_bias")
    protocol_bias = (
        {str(k): int(v) for k, v in protocol_bias_raw.items()}
        if isinstance(protocol_bias_raw, dict)
        else None
    )

    candidates = rank_protocols_tool(
        parsed,
        top_k=top_k,
        skills=skill_names,
        protocol_bias=protocol_bias,
    )
    selected = candidates[0] if candidates else None

    return {
        "skill": "select_protocol",
        "parsed_requirement": parsed,
        "candidates": candidates,
        "selected": selected,
    }


def _execute_optimize_circuit(payload: dict[str, Any]) -> dict[str, Any]:
    parsed = payload.get("parsed_requirement") if isinstance(payload.get("parsed_requirement"), dict) else {}
    operation = str(parsed.get("operation", payload.get("operation", "generic"))).strip().lower()
    domain = str(parsed.get("circuit_domain", payload.get("circuit_domain", "arithmetic"))).strip().lower()

    actions: list[str] = []
    if operation in {"aggregation", "ml"} or domain in {"arithmetic", "mixed"}:
        actions.append("Prefer arithmetic sharing operations and batch arithmetic gates.")
        actions.append("Move multiplication-heavy work into preprocessing-friendly form when possible.")
    if operation == "comparison" or domain in {"boolean", "mixed"}:
        actions.append("Minimize boolean circuit depth for WAN latency sensitivity.")
        actions.append("Group comparisons to reduce cross-domain conversions.")
    if not actions:
        actions.append("Use mixed-circuit split: arithmetic for linear parts, boolean for predicates.")

    return {
        "skill": "optimize_circuit",
        "operation": operation,
        "circuit_domain": domain,
        "actions": actions,
    }


def _execute_generate_configuration(payload: dict[str, Any]) -> dict[str, Any]:
    from mpc_agent.adapters.config_tool import generate_configuration_tool

    local_payload = dict(payload)
    local_payload["execute"] = False
    result = generate_configuration_tool(local_payload)

    return {
        "skill": "generate_configuration",
        "parsed_requirement": result.get("parsed_requirement"),
        "final_configuration": result.get("final_configuration"),
        "candidates": result.get("candidates"),
    }


def _execute_deploy_and_monitor(payload: dict[str, Any]) -> dict[str, Any]:
    from mpc_agent.adapters.config_tool import generate_configuration_tool
    from mpc_agent.adapters.runner_tool import compile_program_tool, run_protocol_tool

    local_payload = dict(payload)
    local_payload["execute"] = True

    config_result = generate_configuration_tool({**local_payload, "execute": False})
    parsed_requirement = config_result["parsed_requirement"]
    final_configuration = config_result["final_configuration"]

    if bool(payload.get("compile_only", False)):
        execution = compile_program_tool(local_payload, parsed_requirement, final_configuration)
    else:
        execution = run_protocol_tool(local_payload, parsed_requirement, final_configuration)

    return {
        "skill": "deploy_and_monitor",
        "parsed_requirement": parsed_requirement,
        "final_configuration": final_configuration,
        "execution": execution,
    }


def _execute_explain_decision(payload: dict[str, Any]) -> dict[str, Any]:
    parsed = payload.get("parsed_requirement") if isinstance(payload.get("parsed_requirement"), dict) else {}
    final_config = payload.get("final_configuration") if isinstance(payload.get("final_configuration"), dict) else {}
    knowledge = payload.get("knowledge_context") if isinstance(payload.get("knowledge_context"), dict) else {}
    candidates = payload.get("candidates") if isinstance(payload.get("candidates"), list) else []

    protocol = str(final_config.get("protocol_id", "unknown"))
    operation = str(parsed.get("operation", "unknown"))
    parties = parsed.get("parties", "unknown")
    security_model = str(parsed.get("security_model", "unknown"))

    top_reason = ""
    if candidates and isinstance(candidates[0], dict):
        reasons = candidates[0].get("reasons")
        if isinstance(reasons, list) and reasons:
            top_reason = str(reasons[0])

    references: list[str] = []
    for section in knowledge.get("sections", []):
        if isinstance(section, dict):
            sec = str(section.get("section", "")).strip()
            title = str(section.get("title", "")).strip()
            if sec and title:
                references.append(f"{sec} {title}")

    explanation = (
        f"Selected `{protocol}` for {parties}-party {operation} under {security_model} security. "
        f"Primary ranking signal: {top_reason or 'policy score + skill bias + memory bias.'}"
    )

    return {
        "skill": "explain_decision",
        "explanation": explanation,
        "references": references,
        "final_protocol": protocol,
    }


def _execute_simulate_threat(payload: dict[str, Any]) -> dict[str, Any]:
    parsed = payload.get("parsed_requirement") if isinstance(payload.get("parsed_requirement"), dict) else {}
    final_config = payload.get("final_configuration") if isinstance(payload.get("final_configuration"), dict) else {}

    security = str(parsed.get("security_model", final_config.get("security_model", "unknown"))).strip().lower()
    corruption = str(parsed.get("corruption_model", final_config.get("corruption_model", "unknown"))).strip().lower()
    protocol = str(final_config.get("protocol_id", "unknown"))

    risks: list[str] = []
    mitigations: list[str] = []
    residual = "medium"

    if security == "semi_honest":
        risks.append("No active-cheating robustness: malicious deviations may break correctness/privacy.")
        mitigations.append("Upgrade to malicious-secure variant for production or adversarial deployments.")
        residual = "high"
    elif security == "covert":
        risks.append("Cheating may be detected probabilistically; deterrence assumptions matter.")
        mitigations.append("Set audit/detection probability and incident response controls explicitly.")
        residual = "medium"
    elif security == "malicious":
        risks.append("Main residual surface is implementation/configuration errors, not protocol class.")
        mitigations.append("Enforce authenticated preprocessing integrity and strict runtime validation.")
        residual = "low"

    if corruption == "honest_majority":
        risks.append("Security relies on honest-majority assumption holding in deployment.")
        mitigations.append("Document trust boundary and monitor party availability/trust drift.")
    elif corruption == "dishonest_majority":
        risks.append("Higher cryptographic overhead and setup complexity under dishonest-majority model.")
        mitigations.append("Benchmark preprocessing throughput and tune offline-online split.")

    if protocol in {"gmw", "semi2k"} and security == "malicious":
        risks.append("Protocol/security mismatch risk if stack does not provide full malicious variant.")
        mitigations.append("Confirm selected script/runtime actually enforces malicious security.")
        residual = "high"

    return {
        "skill": "simulate_threat",
        "protocol": protocol,
        "security_model": security,
        "corruption_model": corruption,
        "risks": risks,
        "mitigations": mitigations,
        "residual_risk": residual,
    }


def execute_skill(name: str, payload: dict[str, Any]) -> dict[str, Any]:
    skill_name = str(name).strip()
    normalized = skill_name.replace("-", "_")

    if normalized == "analyze_requirement":
        return _execute_analyze_requirement(payload)
    if normalized == "select_protocol":
        return _execute_select_protocol(payload)
    if normalized == "optimize_circuit":
        return _execute_optimize_circuit(payload)
    if normalized == "generate_configuration":
        return _execute_generate_configuration(payload)
    if normalized == "deploy_and_monitor":
        return _execute_deploy_and_monitor(payload)
    if normalized == "explain_decision":
        return _execute_explain_decision(payload)
    if normalized == "simulate_threat":
        return _execute_simulate_threat(payload)

    if skill_name == "mpspdz-execution":
        action = str(payload.get("action", "make_inputs")).strip()
        if action == "make_inputs":
            module = _load_script_module("mpspdz-execution", "make_inputs.py")
            mpspdz_home = str(payload.get("mpspdz_home", "")).strip()
            parties = int(payload.get("parties", 2))
            overwrite = bool(payload.get("overwrite", False))
            result = module.make_inputs(mpspdz_home, parties, overwrite=overwrite)
            return {
                "skill": skill_name,
                "action": action,
                "result": result,
            }
        if action == "compile":
            module = _load_script_module("mpspdz-execution", "compile.py")
            raw_payload = payload.get("payload")
            if not isinstance(raw_payload, dict):
                raise ValueError("`payload` must be a dict for action=compile.")
            result = module.compile_from_payload(raw_payload)
            return {"skill": skill_name, "action": action, "result": result}
        if action == "run":
            module = _load_script_module("mpspdz-execution", "run.py")
            raw_payload = payload.get("payload")
            if not isinstance(raw_payload, dict):
                raise ValueError("`payload` must be a dict for action=run.")
            result = module.run_from_payload(raw_payload)
            return {"skill": skill_name, "action": action, "result": result}
        raise ValueError(f"Unsupported action for mpspdz-execution: {action}")

    if skill_name == "windows-mpspdz-debug":
        execution = payload.get("execution")
        if not isinstance(execution, dict):
            raise ValueError("`execution` must be a dict for windows-mpspdz-debug.")
        return _windows_debug_template(execution)

    # Legacy descriptive skills keep no-op behavior.
    if skill_name in {"protocol-selection", "arithmetic-aggregation", "boolean-comparison"}:
        return {
            "skill": skill_name,
            "action": "noop",
            "result": "This skill is policy/routing oriented; no deterministic script executed.",
        }

    raise KeyError(f"Unknown skill: {skill_name}")

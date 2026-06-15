from __future__ import annotations

import os
import time
from typing import Any

from .case_store import append_case, find_similar_cases, summarize_protocol_bias
from .deepseek_client import DeepSeekAdvisor
from .knowledge_base import retrieve_knowledge
from .models import FinalConfiguration
from .open_source_catalog import recommend_open_source_protocols
from .parser import parse_requirement
from .policy import collect_compatibility_notes, get_profile, rank_candidates
from .runtime_runner import RuntimeRunner
from .runtime_signals import collect_runtime_signals
from .skills.executor import execute_skill
from .skills.router import recommend_skills
from .spdz_runner import inspect_protocol_launch_support, resolve_mpspdz_home


def _supports_required_security(required: str, supported: list[str]) -> bool:
    support_set = set(supported)
    if required == "malicious":
        return "malicious" in support_set
    if required == "covert":
        return "covert" in support_set or "malicious" in support_set
    return "semi_honest" in support_set or "malicious" in support_set


def _supports_required_corruption(required: str, assumptions: list[str]) -> bool:
    assumption_set = set(assumptions)
    if required == "dishonest_majority":
        return "dishonest_majority" in assumption_set
    return "honest_majority" in assumption_set or "dishonest_majority" in assumption_set


def _supports_required_domain(required: str, actual: str) -> bool:
    if required == "mixed":
        return actual in {"mixed", "arithmetic", "boolean"}
    if required == "boolean":
        return actual in {"boolean", "mixed"}
    if required == "arithmetic":
        return actual in {"arithmetic", "mixed"}
    return True


def _supports_required_party_count(parties: int, assumptions: list[str]) -> bool:
    assumption_set = set(assumptions)
    if parties == 2:
        return "two_party" in assumption_set or "multi_party" in assumption_set
    return "multi_party" in assumption_set


def _candidate_core_compatible(candidate: dict[str, Any], req_dict: dict[str, Any]) -> bool:
    return (
        _supports_required_security(req_dict["security_model"], candidate.get("security_support", []))
        and _supports_required_corruption(req_dict["corruption_model"], candidate.get("assumptions", []))
        and _supports_required_domain(req_dict["circuit_domain"], str(candidate.get("circuit_domain", "")))
        and _supports_required_party_count(int(req_dict["parties"]), candidate.get("assumptions", []))
    )


def _annotate_execution_support(
    candidates: list[dict[str, Any]],
    payload: dict[str, Any],
) -> dict[str, Any]:
    execute_requested = bool(payload.get("execute", False)) and not bool(payload.get("compile_only", False))
    if not execute_requested:
        return {"checked": False, "reason": "Execution preflight skipped."}

    mpspdz_home, source = resolve_mpspdz_home(payload, None)
    if mpspdz_home is None:
        return {"checked": False, "reason": "MP-SPDZ home unresolved."}
    if not mpspdz_home.exists():
        return {"checked": False, "reason": f"MP-SPDZ home not found: {mpspdz_home}"}

    for candidate in candidates:
        support = inspect_protocol_launch_support(
            mpspdz_home,
            candidate.get("mpspdz_scripts", []),
            require_runtime_binary=True,
        )
        candidate["execution_support"] = support
        reason = str(support.get("reason", "")).strip()
        if support.get("launchable"):
            preferred_script = support.get("preferred_script")
            if preferred_script:
                candidate.setdefault("reasons", []).append(
                    f"Execution preflight passed via {preferred_script}."
                )
        elif reason:
            candidate.setdefault("reasons", []).append(f"Execution preflight: {reason}")

    return {
        "checked": True,
        "mpspdz_home": str(mpspdz_home),
        "mpspdz_home_source": source,
    }


def _select_protocol(
    candidates: list[dict[str, Any]],
    deepseek_advice: dict[str, Any],
    req_dict: dict[str, Any],
    payload: dict[str, Any],
) -> tuple[str, list[str]]:
    if deepseek_advice.get("used") and deepseek_advice.get("recommended_protocol_id"):
        selected = str(deepseek_advice["recommended_protocol_id"]).strip()
        for candidate in candidates:
            if candidate["protocol_id"] == selected:
                rationale = ["DeepSeek recommendation matches local candidates; selected directly."]
                break
        else:
            selected = ""
            rationale = []
    else:
        selected = ""
        rationale = []

    if not selected:
        top = candidates[0]
        selected = str(top["protocol_id"])
        rationale = ["Selected top-ranked protocol from local policy engine."]
        if deepseek_advice.get("used") and deepseek_advice.get("recommended_protocol_id"):
            rationale.append("DeepSeek suggested protocol not in candidate set; ignored.")

    execute_requested = bool(payload.get("execute", False)) and not bool(payload.get("compile_only", False))
    if not execute_requested:
        return selected, rationale

    selected_candidate = next((item for item in candidates if item["protocol_id"] == selected), None)
    support = selected_candidate.get("execution_support", {}) if selected_candidate else {}
    if support.get("launchable"):
        return selected, rationale

    for candidate in candidates:
        candidate_support = candidate.get("execution_support", {})
        if not candidate_support.get("launchable"):
            continue
        if not _candidate_core_compatible(candidate, req_dict):
            continue
        selected_reason = str(support.get("reason", "")).strip() or "runtime unavailable"
        fallback_reason = (
            f"Top candidate `{selected}` is not launchable in current MP-SPDZ checkout ({selected_reason}). "
            f"Fell back to launchable core-compatible candidate `{candidate['protocol_id']}`."
        )
        return str(candidate["protocol_id"]), [fallback_reason]

    if selected_candidate is not None:
        selected_reason = str(support.get("reason", "")).strip() or "runtime unavailable"
        rationale.append(
            f"Current MP-SPDZ checkout cannot launch `{selected}` ({selected_reason}); no launchable core-compatible fallback found."
        )
    return selected, rationale


def _build_final_config(
    protocol_id: str,
    req_dict: dict[str, Any],
    selection_rationale: list[str],
) -> FinalConfiguration:
    profile = get_profile(protocol_id)
    program_name = f"auto_{protocol_id}_{int(time.time())}"
    mpspdz_home = os.getenv("MPSPDZ_HOME", "").strip()
    compile_options: list[str]
    if protocol_id == "yao":
        compile_options = ["-B", "32", "-G"]
    elif req_dict["circuit_domain"] == "boolean":
        compile_options = ["-B", "32"]
    elif protocol_id == "semi2k" or req_dict.get("math_structure") == "ring":
        compile_options = ["-R", "64"]
    else:
        compile_options = []

    compatibility_notes = list(req_dict.get("compatibility_notes", []))
    compatibility_notes.extend(
        collect_compatibility_notes(
            parse_requirement(req_dict),
            profile,
        )
    )

    return FinalConfiguration(
        protocol_id=protocol_id,
        title=profile.title,
        mpspdz_home=mpspdz_home,
        script_candidates=profile.mpspdz_scripts,
        parties=req_dict["parties"],
        security_model=req_dict["security_model"],
        corruption_model=req_dict["corruption_model"],
        circuit_domain=req_dict["circuit_domain"],
        preprocessed=profile.preprocessed,
        compile_options=compile_options,
        source_program_name=program_name,
        rationale=selection_rationale,
        references=profile.references,
        party_count_mode=req_dict.get("party_count_mode", "auto"),
        math_structure=req_dict.get("math_structure", "auto"),
        secret_sharing=req_dict.get("secret_sharing", "auto"),
        preprocessing_preference=req_dict.get("preprocessing_preference", "auto"),
        corruption_timing=req_dict.get("corruption_timing", "auto"),
        network_model=req_dict.get("network_model", "auto"),
        corruption_threshold=req_dict.get("corruption_threshold", "auto"),
        security_goal=req_dict.get("security_goal", "auto"),
        compatibility_notes=list(dict.fromkeys(compatibility_notes)),
        runner_backend="mp_spdz",
        implementation_id=protocol_id,
        framework="MP-SPDZ",
    )


def _normalize_runtime_backend(value: Any) -> str:
    normalized = str(value or "").strip().lower().replace("-", "_")
    if normalized in {"spu", "secretflow_spu", "secretflow"}:
        return "secretflow_spu"
    if normalized in {"crypten", "cryp_ten"}:
        return "crypten"
    if normalized in {"mp_spdz", "mpspdz", "mp_spdz"}:
        return "mp_spdz"
    return "auto"


def _payload_prefers_semi2k(payload: dict[str, Any]) -> bool:
    raw_values = [
        payload.get("preferred_protocol_id"),
        payload.get("preferred_protocol"),
        payload.get("protocol_id"),
        payload.get("protocol"),
        payload.get("preferred_implementation_id"),
        payload.get("requirement"),
    ]
    normalized = " ".join(str(value or "") for value in raw_values).lower()
    compact = normalized.replace("-", "").replace("_", "").replace(" ", "")
    return "semi2k" in compact


def _catalog_match_is_semi2k(match: dict[str, Any]) -> bool:
    raw_values = [
        match.get("implementation_id"),
        match.get("name"),
        match.get("protocol_family"),
    ]
    compact = " ".join(str(value or "") for value in raw_values).lower()
    compact = compact.replace("-", "").replace("_", "").replace(" ", "")
    return "semi2k" in compact


def _select_backend_match(
    payload: dict[str, Any],
    open_source_recommendations: dict[str, Any],
    runner_backend: str,
) -> dict[str, Any] | None:
    matches = open_source_recommendations.get("matches", [])
    if not isinstance(matches, list):
        return None

    preferred = str(payload.get("preferred_implementation_id", "")).strip()
    if preferred:
        for match in matches:
            if (
                isinstance(match, dict)
                and str(match.get("implementation_id", "")).strip() == preferred
                and str(match.get("runner_backend", "")).strip() == runner_backend
            ):
                return match

    if _payload_prefers_semi2k(payload):
        for match in matches:
            if (
                isinstance(match, dict)
                and str(match.get("runner_backend", "")).strip() == runner_backend
                and _catalog_match_is_semi2k(match)
            ):
                return match

    for match in matches:
        if isinstance(match, dict) and str(match.get("runner_backend", "")).strip() == runner_backend:
            return match
    return None


def _build_catalog_final_config(
    match: dict[str, Any] | None,
    req_dict: dict[str, Any],
    selection_rationale: list[str],
    *,
    runner_backend: str,
    unavailable_protocol_id: str,
    unavailable_title: str,
    default_framework: str,
) -> FinalConfiguration:
    if match is None:
        return FinalConfiguration(
            protocol_id=unavailable_protocol_id,
            title=unavailable_title,
            mpspdz_home=os.getenv("MPSPDZ_HOME", "").strip(),
            script_candidates=[],
            parties=req_dict["parties"],
            security_model=req_dict["security_model"],
            corruption_model=req_dict["corruption_model"],
            circuit_domain=req_dict["circuit_domain"],
            preprocessed=req_dict.get("preprocessing_preference") == "required",
            compile_options=[],
            source_program_name=f"auto_{unavailable_protocol_id}_{int(time.time())}",
            rationale=selection_rationale,
            references=[],
            party_count_mode=req_dict.get("party_count_mode", "auto"),
            math_structure=req_dict.get("math_structure", "auto"),
            secret_sharing=req_dict.get("secret_sharing", "auto"),
            preprocessing_preference=req_dict.get("preprocessing_preference", "auto"),
            corruption_timing=req_dict.get("corruption_timing", "auto"),
            network_model=req_dict.get("network_model", "auto"),
            corruption_threshold=req_dict.get("corruption_threshold", "auto"),
            security_goal=req_dict.get("security_goal", "auto"),
            compatibility_notes=list(req_dict.get("compatibility_notes", [])),
            runner_backend=runner_backend,
            implementation_id="",
            framework=default_framework,
        )

    references = [str(item) for item in match.get("reference_urls", []) if isinstance(item, str)]
    compatibility_notes = list(req_dict.get("compatibility_notes", []))
    return FinalConfiguration(
        protocol_id=str(match.get("implementation_id", unavailable_protocol_id)),
        title=str(match.get("name", unavailable_title)),
        mpspdz_home=os.getenv("MPSPDZ_HOME", "").strip(),
        script_candidates=[],
        parties=req_dict["parties"],
        security_model=req_dict["security_model"],
        corruption_model=req_dict["corruption_model"],
        circuit_domain=req_dict["circuit_domain"],
        preprocessed="required" in match.get("preprocessing_support", []),
        compile_options=[],
        source_program_name=f"auto_{str(match.get('implementation_id', unavailable_protocol_id))}_{int(time.time())}",
        rationale=selection_rationale,
        references=references,
        party_count_mode=req_dict.get("party_count_mode", "auto"),
        math_structure=req_dict.get("math_structure", "auto"),
        secret_sharing=req_dict.get("secret_sharing", "auto"),
        preprocessing_preference=req_dict.get("preprocessing_preference", "auto"),
        corruption_timing=req_dict.get("corruption_timing", "auto"),
        network_model=req_dict.get("network_model", "auto"),
        corruption_threshold=req_dict.get("corruption_threshold", "auto"),
        security_goal=req_dict.get("security_goal", "auto"),
        compatibility_notes=list(dict.fromkeys(compatibility_notes)),
        runner_backend=runner_backend,
        implementation_id=str(match.get("implementation_id", "")),
        framework=str(match.get("framework", default_framework)),
    )


def _safe_execute_skill(name: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return execute_skill(name, payload)
    except Exception as error:  # noqa: BLE001
        return {
            "skill": name,
            "status": "error",
            "error": str(error),
        }


def _build_case_record(
    payload: dict[str, Any],
    parsed_requirement: dict[str, Any],
    selected_protocol: str,
    skills: list[str],
    execution: dict[str, Any],
) -> dict[str, Any]:
    return {
        "timestamp": int(time.time()),
        "requirement": str(payload.get("requirement", "")).strip(),
        "parsed_requirement": parsed_requirement,
        "selected_protocol": selected_protocol,
        "recommended_skills": skills,
        "execution_status": execution.get("status", "unknown"),
        "execution_reason": execution.get("reason", ""),
        "execution_duration_seconds": execution.get("run", {}).get("duration_seconds"),
    }


class MpcAutoConfigAgent:
    def __init__(self) -> None:
        self.deepseek = DeepSeekAdvisor()
        self.runner = RuntimeRunner()

    def configure(self, payload: dict[str, Any]) -> dict[str, Any]:
        parsed = parse_requirement(payload)
        parsed_dict = parsed.to_dict()

        skill_plan = recommend_skills({**payload, "parsed_requirement": parsed_dict})
        knowledge_context = retrieve_knowledge(parsed.raw_requirement)
        similar_cases = find_similar_cases(parsed_dict, limit=5)
        history_bias = summarize_protocol_bias(similar_cases)
        runtime_signals = collect_runtime_signals(payload, parsed_dict)
        runtime_bias = runtime_signals.get("protocol_bias", {})

        combined_bias: dict[str, int] = {}
        for key, value in history_bias.items():
            combined_bias[key] = combined_bias.get(key, 0) + int(value)
        for key, value in runtime_bias.items():
            combined_bias[key] = combined_bias.get(key, 0) + int(value)

        candidates = rank_candidates(
            parsed,
            top_k=4,
            skill_names=skill_plan.get("recommended", []),
            protocol_bias=combined_bias,
        )
        candidates_dict = [candidate.to_dict() for candidate in candidates]
        execution_preflight = _annotate_execution_support(candidates_dict, payload)
        open_source_recommendations = recommend_open_source_protocols(parsed, limit=20)
        runtime_backend = _normalize_runtime_backend(payload.get("runtime_backend"))
        spu_match = _select_backend_match(payload, open_source_recommendations, "secretflow_spu")
        crypten_match = _select_backend_match(payload, open_source_recommendations, "crypten")

        deepseek_advice = self.deepseek.advise(parsed_dict, candidates_dict)
        if runtime_backend == "secretflow_spu":
            if spu_match is None:
                selected_protocol_id = "unavailable_spu"
                selection_rationale = [
                    "Requested `runtime_backend=secretflow_spu`, but no matching SecretFlow SPU deployment was found in the current open-source recommendation set.",
                ]
            else:
                selected_protocol_id = str(spu_match.get("implementation_id", "spu"))
                selection_rationale = [
                    f"Requested `runtime_backend=secretflow_spu`; selected `{selected_protocol_id}` from curated open-source matches.",
                ]
            final_config = _build_catalog_final_config(
                spu_match,
                parsed_dict,
                selection_rationale,
                runner_backend="secretflow_spu",
                unavailable_protocol_id="unavailable_spu",
                unavailable_title="No matching SecretFlow SPU deployment",
                default_framework="SecretFlow SPU",
            )
        elif runtime_backend == "crypten":
            if crypten_match is None:
                selected_protocol_id = "unavailable_crypten"
                selection_rationale = [
                    "Requested `runtime_backend=crypten`, but no matching CrypTen deployment was found in the current open-source recommendation set.",
                ]
            else:
                selected_protocol_id = str(crypten_match.get("implementation_id", "crypten"))
                selection_rationale = [
                    f"Requested `runtime_backend=crypten`; selected `{selected_protocol_id}` from curated open-source matches.",
                ]
            final_config = _build_catalog_final_config(
                crypten_match,
                parsed_dict,
                selection_rationale,
                runner_backend="crypten",
                unavailable_protocol_id="unavailable_crypten",
                unavailable_title="No matching CrypTen deployment",
                default_framework="CrypTen",
            )
        else:
            selected_protocol_id, selection_rationale = _select_protocol(
                candidates_dict,
                deepseek_advice,
                parsed_dict,
                payload,
            )
            final_config = _build_final_config(selected_protocol_id, parsed_dict, selection_rationale)

        if deepseek_advice.get("used"):
            rationale_text = deepseek_advice.get("rationale")
            if isinstance(rationale_text, str) and rationale_text.strip():
                final_config.rationale.append(f"DeepSeek rationale: {rationale_text}")
            elif isinstance(rationale_text, list):
                for item in rationale_text:
                    final_config.rationale.append(f"DeepSeek rationale: {item}")

        execution_payload = dict(payload)
        execution_payload["_recommended_skills"] = skill_plan.get("recommended", [])
        execution = self.runner.run(execution_payload, parsed, final_config)

        decision_explanation = _safe_execute_skill(
            "explain_decision",
            {
                "parsed_requirement": parsed_dict,
                "knowledge_context": knowledge_context,
                "candidates": candidates_dict,
                "final_configuration": final_config.to_dict(),
                "skills": skill_plan.get("recommended", []),
            },
        )

        if "simulate_threat" in skill_plan.get("recommended", []):
            threat_simulation = _safe_execute_skill(
                "simulate_threat",
                {
                    "parsed_requirement": parsed_dict,
                    "final_configuration": final_config.to_dict(),
                    "execution": execution,
                },
            )
        else:
            threat_simulation = {
                "skill": "simulate_threat",
                "status": "skipped",
                "reason": "Skill not recommended for current request.",
            }

        case_record = append_case(
            _build_case_record(
                payload,
                parsed_dict,
                selected_protocol_id,
                skill_plan.get("recommended", []),
                execution,
            )
        )

        memory = {
            "case_store_path": os.getenv("MPC_AGENT_CASE_DB", "") or ".mpc_agent_cases.jsonl",
            "similar_cases": similar_cases,
            "protocol_bias": history_bias,
            "runtime_protocol_bias": runtime_bias,
            "combined_protocol_bias": combined_bias,
            "saved_case_id": case_record.get("case_id"),
            "execution_preflight": execution_preflight,
        }

        return {
            "timestamp": int(time.time()),
            "parsed_requirement": parsed_dict,
            "candidates": candidates_dict,
            "skills": skill_plan,
            "knowledge_context": knowledge_context,
            "runtime_signals": runtime_signals,
            "memory": memory,
            "deepseek": deepseek_advice,
            "open_source_recommendations": open_source_recommendations,
            "final_configuration": final_config.to_dict(),
            "decision_explanation": decision_explanation,
            "threat_simulation": threat_simulation,
            "execution": execution,
        }

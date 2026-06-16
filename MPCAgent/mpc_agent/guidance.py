"""Proactive MPC domain guidance and parameter completion."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .normalization import normalize_config
from .schemas import MPCProtocolConfig
from .utils import is_empty


@dataclass(slots=True)
class GuidanceResult:
    config: MPCProtocolConfig
    missing_fields: list[str] = field(default_factory=list)
    clarifying_questions: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    inferred_notes: list[str] = field(default_factory=list)


def apply_proactive_guidance(config: MPCProtocolConfig, message: str) -> GuidanceResult:
    """Infer safe MPC defaults and ask only protocol-shaping questions."""

    guided = normalize_config(config).model_copy(deep=True)
    notes: list[str] = []

    _infer_from_text(guided, message, notes)
    _apply_common_defaults(guided, notes)
    _apply_protocol_family_defaults(guided, notes)
    guided = normalize_config(guided)

    missing, questions = _dynamic_prompts(guided)
    actions = _next_actions(guided, missing)

    return GuidanceResult(
        config=guided,
        missing_fields=missing,
        clarifying_questions=questions,
        next_actions=actions,
        inferred_notes=notes,
    )


def _infer_from_text(config: MPCProtocolConfig, message: str, notes: list[str]) -> None:
    text = message.casefold()

    if is_empty(config.participant_scale.number_of_parties):
        if re.search(r"(三|3)\s*[- ]?party|(三|3)\s*方", text):
            config.participant_scale.number_of_parties = 3
            notes.append("Inferred a 3-party setting from the request.")
        elif re.search(r"(two|2)\s*[- ]?party|(两|二|2)\s*方", text):
            config.participant_scale.number_of_parties = 2
            notes.append("Inferred a 2-party setting from the request.")

    if is_empty(config.adversary.behavior_model):
        if any(marker in text for marker in ["malicious", "active", "恶意", "不按协议"]):
            config.adversary.behavior_model = "Malicious"
            notes.append("Mapped active/deviating behavior to a malicious adversary model.")
        elif any(marker in text for marker in ["semi-honest", "semihonest", "passive", "半诚实"]):
            config.adversary.behavior_model = "Semi-honest"
            notes.append("Mapped passive behavior to a semi-honest adversary model.")

    if is_empty(config.adversary.corruption_threshold):
        if re.search(r"(at most|最多).*(one|1|一).*(corrupt|腐化|坏)", text) or re.search(
            r"(最多).*(corrupt|腐化|坏).*(one|1|一)",
            text,
        ) or re.search(
            r"(one|1|一).*(corrupt|腐化|坏)",
            text,
        ):
            config.adversary.corruption_threshold = "t=1"
            notes.append("Inferred corruption threshold t=1.")
        elif "t < n/3" in text or "t<n/3" in text:
            config.adversary.corruption_threshold = "t < n/3"
            notes.append("Inferred corruption threshold t < n/3.")
        elif "t < n/2" in text or "t<n/2" in text:
            config.adversary.corruption_threshold = "t < n/2"
            notes.append("Inferred corruption threshold t < n/2.")

    if is_empty(config.circuit.form):
        if "mixed" in text or "混合" in text:
            config.circuit.form = "Mixed"
            notes.append("Inferred a mixed circuit form.")
        elif "arithmetic" in text or "算术" in text:
            config.circuit.form = "Arithmetic"
            notes.append("Inferred an arithmetic circuit form.")
        elif any(marker in text for marker in ["boolean", "garbled", "yao", "布尔", "按位"]):
            config.circuit.form = "Boolean"
            notes.append("Inferred a boolean circuit form.")

    if is_empty(config.secret_sharing.scheme) and "shamir" in text:
        config.secret_sharing.scheme = "Shamir"
        notes.append("Inferred Shamir secret sharing.")

    if is_empty(config.preprocessing.enabled) and any(
        marker in text for marker in ["beaver", "triple", "preprocessing", "offline", "预处理", "三元组"]
    ):
        config.preprocessing.enabled = True
        _append_unique(config.preprocessing.materials, "Beaver triples")
        notes.append("Enabled preprocessing and added Beaver triples.")

    if is_empty(config.network.synchrony):
        if "synchronous" in text or "同步" in text:
            config.network.synchrony = "Synchronous"
            notes.append("Inferred a synchronous network model.")
        elif "asynchronous" in text or "异步" in text:
            config.network.synchrony = "Asynchronous"
            notes.append("Inferred an asynchronous network model.")

    if is_empty(config.network.channels) and any(
        marker in text for marker in ["authenticated channel", "authenticated channels", "认证信道"]
    ):
        config.network.channels = "Authenticated channels"
        notes.append("Inferred authenticated channels.")


def _apply_common_defaults(config: MPCProtocolConfig, notes: list[str]) -> None:
    parties = config.participant_scale.number_of_parties
    if parties and not config.participant_scale.compute_parties:
        config.participant_scale.compute_parties = [f"P{index}" for index in range(1, parties + 1)]
        notes.append("Defaulted compute parties to all participants.")

    if config.adversary.behavior_model in {"Malicious", "Semi-honest"}:
        _set_if_empty(config.adversary, "corruption_strategy", "Static", notes, "Defaulted to static corruption.")
        _set_if_empty(config.network, "synchrony", "Synchronous", notes, "Defaulted to a synchronous network.")
        _set_if_empty(
            config.network,
            "channels",
            "Authenticated channels",
            notes,
            "Defaulted to authenticated channels.",
        )
        _set_if_empty(config.security_goals, "privacy", "yes", notes, "Defaulted privacy goal to yes.")
        correctness = "security with abort" if config.adversary.behavior_model == "Malicious" else "yes"
        _set_if_empty(config.security_goals, "correctness", correctness, notes, "Defaulted correctness goal.")

    if config.secret_sharing.scheme == "Shamir":
        _set_if_empty(
            config.math_structure,
            "structure",
            "FiniteField",
            notes,
            "Defaulted Shamir sharing to a finite-field math structure.",
        )

    if config.preprocessing.enabled is True and not config.preprocessing.materials:
        config.preprocessing.materials = ["Beaver triples"]
        notes.append("Defaulted preprocessing materials to Beaver triples.")


def _apply_protocol_family_defaults(config: MPCProtocolConfig, notes: list[str]) -> None:
    parties = config.participant_scale.number_of_parties
    behavior = config.adversary.behavior_model
    threshold = (config.adversary.corruption_threshold or "").casefold()
    honest_majority = "t=1" in threshold or "n/3" in threshold or "honest" in threshold

    if parties == 3 and behavior == "Malicious" and honest_majority:
        _set_if_empty(config.circuit, "form", "Arithmetic", notes, "Selected arithmetic circuits for malicious Shamir.")
        _set_if_empty(config.secret_sharing, "scheme", "Shamir", notes, "Selected Shamir sharing.")
        _set_if_empty(config.math_structure, "structure", "FiniteField", notes, "Selected finite-field arithmetic.")
        _set_if_empty(config.preprocessing, "enabled", True, notes, "Enabled preprocessing for malicious security.")
        _append_unique(config.preprocessing.materials, "Beaver triples")
        _append_unique(config.preprocessing.materials, "sacrifice checks")
        _set_recommendation(
            config,
            family="MP-SPDZ malicious-shamir",
            rationale=(
                "3-party malicious security with at most one corrupted party maps naturally "
                "to the MP-SPDZ malicious-shamir protocol family."
            ),
            targets=["MP-SPDZ"],
        )
        config.confidence = max(config.confidence or 0, 0.86)
        notes.append("Mapped the setting to MP-SPDZ malicious-shamir.")

    elif parties and parties > 3 and behavior == "Malicious":
        _set_if_empty(config.circuit, "form", "Arithmetic", notes, "Selected arithmetic MPC as the default start point.")
        _set_if_empty(config.preprocessing, "enabled", True, notes, "Enabled preprocessing for malicious security.")
        if is_empty(config.secret_sharing.scheme):
            config.secret_sharing.scheme = "Authenticated"
            notes.append("Selected authenticated sharing for n-party malicious security.")
        _set_recommendation(
            config,
            family="MP-SPDZ MASCOT/SPDZ",
            rationale="n-party malicious security is best handled by broad MP-SPDZ protocol families.",
            targets=["MP-SPDZ", "SCALE-MAMBA"],
        )

    elif parties == 2 and behavior == "Semi-honest":
        if config.circuit.form in {"Boolean", "GarbledCircuit"}:
            _set_if_empty(config.math_structure, "structure", "BinaryField", notes, "Selected binary-field execution.")
            _set_if_empty(config.secret_sharing, "scheme", "Additive", notes, "Selected additive/XOR-style sharing.")
            _set_recommendation(
                config,
                family="EMP-sh2pc / Yao",
                rationale="Semi-honest 2PC boolean workloads fit EMP-sh2pc or Yao-style execution.",
                targets=["EMP-sh2pc", "ABY"],
            )
        elif config.circuit.form in {"Mixed", None, ""}:
            _set_if_empty(config.math_structure, "structure", "RingZ2k", notes, "Selected ring arithmetic for efficient 2PC.")
            _set_if_empty(config.secret_sharing, "scheme", "Additive", notes, "Selected additive sharing.")
            _set_recommendation(
                config,
                family="ABY mixed-protocol 2PC",
                rationale="Semi-honest 2PC mixed workloads are a strong fit for ABY mixed protocols.",
                targets=["ABY", "SPU", "EMP-sh2pc"],
            )


def _dynamic_prompts(config: MPCProtocolConfig) -> tuple[list[str], list[str]]:
    missing: list[str] = []
    questions: list[str] = []

    if is_empty(config.participant_scale.number_of_parties):
        missing.append("Participant count")
        questions.append("How many parties should participate: 2, 3, or a specific n-party setting?")

    if is_empty(config.adversary.behavior_model):
        missing.append("Adversary behavior")
        questions.append("Should the adversary be semi-honest, malicious, or another behavior model?")

    if is_empty(config.circuit.form) and not (
        config.adversary.behavior_model == "Malicious"
        and config.participant_scale.number_of_parties == 3
    ):
        missing.append("Circuit form")
        questions.append("Is the workload mainly arithmetic, boolean/comparison-heavy, or mixed?")

    if (
        config.adversary.behavior_model == "Malicious"
        and config.participant_scale.number_of_parties == 3
        and is_empty(config.adversary.corruption_threshold)
    ):
        missing.append("Corruption threshold")
        questions.append(
            "For the 3-party malicious setting, do you need at most one corrupted party, "
            "or a stronger dishonest-majority model?"
        )

    if (
        config.adversary.behavior_model == "Malicious"
        and config.preprocessing.enabled is True
        and is_empty(config.preprocessing.generation_method)
    ):
        missing.append("Preprocessing strategy")
        questions.append(
            "Do you prefer faster online execution with heavier preprocessing, "
            "or lower offline setup cost with more online work?"
        )

    return _dedupe(missing), _dedupe(questions[:2])


def _next_actions(config: MPCProtocolConfig, missing: list[str]) -> list[str]:
    if missing:
        return ["Answer the protocol-shaping question above, then regenerate the backend plan."]
    actions = ["Review the selected backend plan and protocol rationale."]
    if config.recommendation.implementation_targets:
        targets = ", ".join(config.recommendation.implementation_targets)
        actions.append(f"Evaluate the suggested implementation target(s): {targets}.")
    return actions


def _set_if_empty(target: object, field_name: str, value: object, notes: list[str], note: str) -> None:
    if is_empty(getattr(target, field_name)):
        setattr(target, field_name, value)
        notes.append(note)


def _set_recommendation(
    config: MPCProtocolConfig,
    *,
    family: str,
    rationale: str,
    targets: list[str],
) -> None:
    if is_empty(config.recommendation.family):
        config.recommendation.family = family
    if is_empty(config.recommendation.rationale):
        config.recommendation.rationale = rationale
    for target in targets:
        _append_unique(config.recommendation.implementation_targets, target)
    _append_unique(config.assumptions, rationale)


def _append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            result.append(item)
            seen.add(item)
    return result

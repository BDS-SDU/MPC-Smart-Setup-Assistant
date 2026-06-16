"""Canonical value normalization for MPC protocol parameters."""

from __future__ import annotations

from .schemas import MPCProtocolConfig


def _normalize_text(value: str | None, mapping: dict[str, str]) -> str | None:
    if not value:
        return value
    lowered = value.casefold()
    for marker, canonical in mapping.items():
        if marker in lowered:
            return canonical
    return value


ADVERSARY_BEHAVIOR_MAP = {
    "恶意": "Malicious",
    "malicious": "Malicious",
    "active": "Malicious",
    "半诚实": "Semi-honest",
    "semi-honest": "Semi-honest",
    "semihonest": "Semi-honest",
    "passive": "Semi-honest",
    "covert": "Covert",
    "rational": "Rational",
    "fail-stop": "Fail-stop",
    "fail stop": "Fail-stop",
}

CORRUPTION_STRATEGY_MAP = {
    "静态": "Static",
    "static": "Static",
    "自适应": "Adaptive",
    "adaptive": "Adaptive",
    "mobile": "Mobile",
    "rushing": "Rushing",
    "non-rushing": "Non-rushing",
    "non rushing": "Non-rushing",
    "选择性中止": "SelectiveAbort",
    "selective abort": "SelectiveAbort",
}

CIRCUIT_FORM_MAP = {
    "算术": "Arithmetic",
    "arithmetic": "Arithmetic",
    "布尔": "Boolean",
    "boolean": "Boolean",
    "mixed": "Mixed",
    "混合": "Mixed",
    "garbled": "GarbledCircuit",
    "yao": "GarbledCircuit",
    "r1cs": "R1CS",
}

SECRET_SHARING_MAP = {
    "shamir": "Shamir",
    "加法": "Additive",
    "additive": "Additive",
    "xor": "Additive",
    "复制": "Replicated",
    "replicated": "Replicated",
    "packed": "Packed",
    "打包": "Packed",
    "authenticated": "Authenticated",
    "认证": "Authenticated",
}

MATH_STRUCTURE_MAP = {
    "prime field": "PrimeField",
    "有限域": "FiniteField",
    "finite field": "FiniteField",
    "gf(2)": "BinaryField",
    "binary field": "BinaryField",
    "二元域": "BinaryField",
    "z_2^": "RingZ2k",
    "z2^": "RingZ2k",
    "ring": "Ring",
    "环": "Ring",
}

NETWORK_SYNCHRONY_MAP = {
    "同步": "Synchronous",
    "synchronous": "Synchronous",
    "异步": "Asynchronous",
    "asynchronous": "Asynchronous",
    "partial": "PartialSynchrony",
    "部分同步": "PartialSynchrony",
    "wan": "WAN",
    "lan": "LAN",
}

CHANNEL_MAP = {
    "认证": "Authenticated channels",
    "authenticated": "Authenticated channels",
    "私密": "Private channels",
    "private": "Private channels",
    "tls": "TLS channels",
    "pki": "PKI-authenticated channels",
}


def normalize_config(config: MPCProtocolConfig) -> MPCProtocolConfig:
    """Normalize commonly varied natural-language values into canonical labels."""

    normalized = config.model_copy(deep=True)
    normalized.adversary.behavior_model = _normalize_text(
        normalized.adversary.behavior_model,
        ADVERSARY_BEHAVIOR_MAP,
    )
    normalized.adversary.corruption_strategy = _normalize_text(
        normalized.adversary.corruption_strategy,
        CORRUPTION_STRATEGY_MAP,
    )
    normalized.circuit.form = _normalize_text(normalized.circuit.form, CIRCUIT_FORM_MAP)
    normalized.secret_sharing.scheme = _normalize_text(
        normalized.secret_sharing.scheme,
        SECRET_SHARING_MAP,
    )
    normalized.math_structure.structure = _normalize_text(
        normalized.math_structure.structure,
        MATH_STRUCTURE_MAP,
    )
    normalized.network.synchrony = _normalize_text(
        normalized.network.synchrony,
        NETWORK_SYNCHRONY_MAP,
    )
    normalized.network.channels = _normalize_text(normalized.network.channels, CHANNEL_MAP)
    normalized.canonical_parameters = build_canonical_parameters(normalized)
    return normalized


def build_canonical_parameters(config: MPCProtocolConfig) -> dict[str, str]:
    params: dict[str, str] = {}
    candidates = {
        "party_count": config.participant_scale.number_of_parties,
        "circuit_form": config.circuit.form,
        "math_structure": config.math_structure.structure,
        "secret_sharing": config.secret_sharing.scheme,
        "adversary_behavior": config.adversary.behavior_model,
        "corruption_strategy": config.adversary.corruption_strategy,
        "corruption_threshold": config.adversary.corruption_threshold,
        "network_model": config.network.synchrony,
        "channel_model": config.network.channels,
        "preprocessing_enabled": config.preprocessing.enabled,
        "privacy_goal": config.security_goals.privacy,
        "correctness_goal": config.security_goals.correctness,
    }
    for key, value in candidates.items():
        if value is None or value == "" or value == []:
            continue
        params[key] = str(value)
    return params

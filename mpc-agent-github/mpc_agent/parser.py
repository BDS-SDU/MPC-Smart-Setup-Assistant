from __future__ import annotations

import re
from typing import Any

from .models import ParsedRequirement
from .requirement_options import OPTION_VALUES


_CHINESE_NUMBERS = {
    "两": 2,
    "二": 2,
    "俩": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}

_ENGLISH_NUMBER_WORDS = {
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}

_ALIASES: dict[str, dict[str, str]] = {
    "party_count_mode": {
        "2": "two_party",
        "2_party": "two_party",
        "two": "two_party",
        "3": "three_party",
        "3_party": "three_party",
        "three": "three_party",
        "n": "n_party",
        "many": "n_party",
        "multi_party": "n_party",
    },
    "math_structure": {
        "field": "finite_field",
        "finitefield": "finite_field",
    },
    "preprocessing_preference": {
        "yes": "required",
        "true": "required",
        "required_preprocessing": "required",
        "no": "disallowed",
        "false": "disallowed",
        "without_preprocessing": "disallowed",
    },
    "security_goal": {
        "abort": "security_with_abort",
        "god": "guaranteed_output_delivery",
    },
}


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords if keyword)


def _normalize_label(
    value: Any,
    allowed: set[str],
    *,
    alias_map: dict[str, str] | None = None,
) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    if alias_map and normalized in alias_map:
        normalized = alias_map[normalized]
    return normalized if normalized in allowed else None


def _extract_parties_from_text(text: str) -> int | None:
    digit_patterns = [
        r"(\d+)\s*(?:方|party|parties|participants?)",
        r"n\s*=\s*(\d+)",
    ]
    for pattern in digit_patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return max(2, int(match.group(1)))

    chinese_match = re.search(r"([两二俩三四五六七八九十])\s*方", text)
    if chinese_match:
        return _CHINESE_NUMBERS[chinese_match.group(1)]

    for word, value in _ENGLISH_NUMBER_WORDS.items():
        if re.search(rf"\b{word}\b[\s-]*(?:party|parties)\b", text):
            return value

    if _contains_any(text, ["two-party", "2pc", "双方", "两方", "两方计算", "二方"]):
        return 2
    if _contains_any(text, ["three-party", "3pc", "三方"]):
        return 3
    return None


def _choose_from_keywords(
    text: str,
    mapping: dict[str, list[str]],
    *,
    fallback: str | None = None,
) -> str | None:
    best_label: str | None = None
    best_hits = 0
    for label, keywords in mapping.items():
        hits = sum(1 for keyword in keywords if keyword in text)
        if hits > best_hits:
            best_hits = hits
            best_label = label
    if best_label is not None:
        return best_label
    return fallback


def _derive_party_mode(parties: int | None) -> str:
    if parties == 2:
        return "two_party"
    if parties == 3:
        return "three_party"
    if isinstance(parties, int) and parties > 3:
        return "n_party"
    return "auto"


def _infer_party_count_mode(payload: dict[str, Any], text: str, parties: int | None) -> str:
    explicit = _normalize_label(
        payload.get("party_count_mode"),
        OPTION_VALUES["party_count_mode"],
        alias_map=_ALIASES.get("party_count_mode"),
    )
    if explicit and explicit != "auto":
        return explicit

    derived = _derive_party_mode(parties)
    if derived != "auto":
        return derived

    if _contains_any(text, ["two-party", "2pc", "双方", "两方", "二方"]):
        return "two_party"
    if _contains_any(text, ["three-party", "3pc", "三方"]):
        return "three_party"

    extracted = _extract_parties_from_text(text)
    return _derive_party_mode(extracted)


def _resolve_parties(payload: dict[str, Any], text: str, notes: list[str]) -> tuple[int, str]:
    parties_raw = payload.get("parties")
    parties = parties_raw if isinstance(parties_raw, int) and parties_raw >= 2 else None

    party_count_mode = _infer_party_count_mode(payload, text, parties)
    if parties is not None:
        return parties, party_count_mode

    if party_count_mode == "two_party":
        return 2, party_count_mode
    if party_count_mode == "three_party":
        return 3, party_count_mode
    if party_count_mode == "n_party":
        extracted = _extract_parties_from_text(text)
        if extracted and extracted >= 4:
            return extracted, party_count_mode
        notes.append("已选择 n 方，但未给出精确人数；系统暂以 4 方进行协议筛选。")
        return 4, party_count_mode

    extracted = _extract_parties_from_text(text)
    if extracted:
        return extracted, _derive_party_mode(extracted)

    notes.append("未显式提供参与方数量；系统按默认 2 方处理。")
    return 2, "two_party"


def _infer_operation(text: str) -> str:
    return _choose_from_keywords(
        text,
        {
            "comparison": ["比较", "排序", "comparison", "less", "greater", "auction", "bid", "price", "psi"],
            "aggregation": ["求和", "平均", "sum", "mean", "aggregate", "aggregation", "统计", "count", "total"],
            "ml": ["ml", "machine learning", "推理", "训练", "神经网络", "inference", "classification"],
        },
        fallback="generic",
    ) or "generic"


def _infer_circuit_domain(text: str, operation: str) -> str:
    boolean_hits = sum(
        1
        for keyword in [
            "boolean",
            "布尔",
            "比较",
            "less than",
            "greater than",
            "xor",
            "and gate",
            "sort",
            "排序",
            "millionaire",
            "set intersection",
            "psi",
            "bitwise",
            "位运算",
        ]
        if keyword in text
    )
    arithmetic_hits = sum(
        1
        for keyword in [
            "arithmetic",
            "算术",
            "求和",
            "平均",
            "mean",
            "sum",
            "dot",
            "linear",
            "线性",
            "回归",
            "矩阵",
            "乘法",
            "field",
            "fixed-point",
            "float",
        ]
        if keyword in text
    )
    mixed_hits = sum(
        1
        for keyword in [
            "mixed",
            "混合电路",
            "mixed circuit",
            "布尔+算术",
            "boolean and arithmetic",
            "boolean + arithmetic",
        ]
        if keyword in text
    )

    if mixed_hits > 0:
        return "mixed"
    if boolean_hits > 0 and arithmetic_hits > 0:
        return "mixed"
    if boolean_hits > 0:
        return "boolean"
    if arithmetic_hits > 0:
        return "arithmetic"
    if operation == "comparison":
        return "boolean"
    return "arithmetic"


def _infer_math_structure(text: str, circuit_domain: str, secret_sharing: str) -> str:
    explicit = _choose_from_keywords(
        text,
        {
            "ring": [" ring ", "环", "mod 2^", "2^k", "ring-based", "semi2k"],
            "finite_field": ["finite field", "field", "有限域", "prime field", "gf("],
        },
    )
    if explicit:
        return explicit
    if secret_sharing == "shamir":
        return "finite_field"
    if circuit_domain == "boolean":
        return "auto"
    return "auto"


def _infer_secret_sharing(text: str) -> str:
    return _choose_from_keywords(
        text,
        {
            "additive": ["additive sharing", "additive secret sharing", "加法共享"],
            "replicated": ["replicated sharing", "replicate secret sharing", "复制共享"],
            "shamir": ["shamir", "shamir sharing", "shamir secret sharing"],
        },
        fallback="auto",
    ) or "auto"


def _infer_preprocessing_preference(text: str) -> str:
    if _contains_any(
        text,
        ["without preprocessing", "no preprocessing", "无预处理", "不支持预处理", "online only"],
    ):
        return "disallowed"
    if _contains_any(
        text,
        ["preprocessing", "offline", "预处理", "离线阶段", "beaver", "triples", "triple generation"],
    ):
        return "required"
    return "auto"


def _infer_security_model(text: str) -> str:
    return _choose_from_keywords(
        text,
        {
            "malicious": ["malicious", "恶意", "主动攻击", "active security", "actively secure"],
            "covert": ["covert", "可检测作弊", "detectable cheating"],
            "semi_honest": ["semi-honest", "semi honest", "半诚实", "honest-but-curious"],
        },
        fallback="malicious",
    ) or "malicious"


def _infer_corruption_timing(text: str) -> str:
    return _choose_from_keywords(
        text,
        {
            "adaptive": ["adaptive", "自适应", "adaptive corruption"],
            "static": ["static", "静态腐化", "static corruption"],
        },
        fallback="auto",
    ) or "auto"


def _infer_threshold(text: str) -> str:
    if re.search(r"t\s*<\s*n\s*/\s*3", text):
        return "t_lt_n_over_3"
    if re.search(r"t\s*<\s*n\s*/\s*2", text) or re.search(r"2t\s*<\s*n", text):
        return "t_lt_n_over_2"
    if re.search(r"t\s*<\s*n(?!\s*/)", text):
        return "t_lt_n"
    if re.search(r"\bdishonest[-\s]*majority\b", text) or _contains_any(text, ["非诚实多数", "不诚实多数"]):
        return "t_lt_n"
    if re.search(r"\bhonest[-\s]*majority\b", text) or _contains_any(text, ["诚实多数"]):
        return "t_lt_n_over_2"

    return _choose_from_keywords(
        text,
        {
            "t_lt_n_over_3": ["<n/3", "n/3", "三分之一门限"],
            "t_lt_n_over_2": ["honest majority", "诚实多数", "半数以下"],
            "t_lt_n": ["dishonest majority", "非诚实多数", "不诚实多数", "any t<n"],
        },
        fallback="auto",
    ) or "auto"


def _derive_corruption_model(text: str, threshold: str, notes: list[str]) -> str:
    dishonest_majority_detected = bool(re.search(r"\bdishonest[-\s]*majority\b", text)) or _contains_any(
        text,
        ["非诚实多数", "不诚实多数", "dishonest-majority", "any t<n"],
    )
    honest_majority_detected = (
        bool(re.search(r"\bhonest[-\s]*majority\b", text)) and not dishonest_majority_detected
    ) or _contains_any(text, ["诚实多数", "honest-majority", "2t<n"])

    if threshold == "t_lt_n":
        return "dishonest_majority"
    if threshold in {"t_lt_n_over_2", "t_lt_n_over_3"}:
        return "honest_majority"
    if dishonest_majority_detected:
        return "dishonest_majority"
    if honest_majority_detected:
        return "honest_majority"

    notes.append("未显式提供多数假设；系统默认按 dishonest majority 处理。")
    return "dishonest_majority"


def _infer_network_model(text: str) -> str:
    return _choose_from_keywords(
        text,
        {
            "asynchronous": ["asynchronous", "async", "异步"],
            "synchronous": ["synchronous", "同步", "round-based"],
        },
        fallback="auto",
    ) or "auto"


def _infer_security_goal(text: str) -> str:
    return _choose_from_keywords(
        text,
        {
            "guaranteed_output_delivery": [
                "guaranteed output delivery",
                "god",
                "输出可交付",
                "保证输出交付",
            ],
            "security_with_abort": ["security with abort", "abort", "中止安全", "可中止"],
        },
        fallback="auto",
    ) or "auto"


def _build_compatibility_notes(
    *,
    party_count_mode: str,
    parties: int,
    circuit_domain: str,
    math_structure: str,
    secret_sharing: str,
    preprocessing_preference: str,
    corruption_timing: str,
    corruption_model: str,
    corruption_threshold: str,
    network_model: str,
    security_goal: str,
) -> list[str]:
    notes: list[str] = []

    if party_count_mode == "n_party" and parties < 4:
        notes.append("已选择 n 方，但当前精确人数小于 4；建议确认是三方还是一般多方场景。")

    if circuit_domain == "boolean" and math_structure != "auto":
        notes.append("布尔电路通常不会显式依赖环/有限域选择；该约束更常见于算术电路。")

    if circuit_domain == "boolean" and secret_sharing != "auto":
        notes.append("布尔电路不一定直接暴露所选 secret sharing 形式，请确认这是必要约束。")

    if math_structure == "ring" and secret_sharing == "shamir":
        notes.append("Shamir secret sharing 通常建立在有限域上，而不是环上。")

    if preprocessing_preference == "required" and circuit_domain == "boolean":
        notes.append("布尔协议并不一定提供清晰的 offline/online 预处理阶段。")

    if corruption_timing == "adaptive":
        notes.append("自适应腐化通常需要更专门的协议设计；当前候选协议未必原生支持。")

    if network_model == "asynchronous" and security_goal == "guaranteed_output_delivery":
        notes.append("异步网络下还要求 guaranteed output delivery，通常需要更强的协议假设。")

    if corruption_threshold == "t_lt_n" and corruption_model == "honest_majority":
        notes.append("当前门限选择偏向 dishonest majority，但多数假设被标记为 honest majority。")

    if (
        corruption_threshold in {"t_lt_n_over_3", "t_lt_n_over_2"}
        and corruption_model == "dishonest_majority"
    ):
        notes.append("当前门限属于 honest-majority 范围，但多数假设被标记为 dishonest majority。")

    # Deduplicate while preserving order.
    return list(dict.fromkeys(notes))


def parse_requirement(payload: dict[str, Any]) -> ParsedRequirement:
    raw_requirement = str(payload.get("requirement", "")).strip()
    text = raw_requirement.lower()
    notes: list[str] = []

    parties, party_count_mode = _resolve_parties(payload, text, notes)

    operation = _normalize_label(payload.get("operation"), {"comparison", "aggregation", "ml", "generic"})
    if not operation:
        operation = _infer_operation(text)

    circuit_domain = _normalize_label(payload.get("circuit_domain"), {"boolean", "arithmetic", "mixed"})
    if not circuit_domain:
        circuit_domain = _infer_circuit_domain(text, operation)
        notes.append(f"电路形式推断为 {circuit_domain}。")

    secret_sharing = _normalize_label(
        payload.get("secret_sharing"),
        OPTION_VALUES["secret_sharing"],
    )
    if not secret_sharing:
        secret_sharing = _infer_secret_sharing(text)

    math_structure = _normalize_label(
        payload.get("math_structure"),
        OPTION_VALUES["math_structure"],
        alias_map=_ALIASES.get("math_structure"),
    )
    if not math_structure:
        math_structure = _infer_math_structure(text, circuit_domain, secret_sharing)

    preprocessing_preference = _normalize_label(
        payload.get("preprocessing_preference"),
        OPTION_VALUES["preprocessing_preference"],
        alias_map=_ALIASES.get("preprocessing_preference"),
    )
    if not preprocessing_preference:
        preprocessing_preference = _infer_preprocessing_preference(text)

    security_model = _normalize_label(payload.get("security_model"), {"malicious", "covert", "semi_honest"})
    if not security_model:
        security_model = _infer_security_model(text)
        if security_model == "malicious" and not _contains_any(
            text,
            ["malicious", "恶意", "主动攻击", "active security", "actively secure"],
        ):
            notes.append("未显式提供敌手行为模型；系统默认按 malicious 处理。")

    corruption_timing = _normalize_label(
        payload.get("corruption_timing"),
        OPTION_VALUES["corruption_timing"],
    )
    if not corruption_timing:
        corruption_timing = _infer_corruption_timing(text)

    threshold_raw = _normalize_label(
        payload.get("corruption_threshold"),
        OPTION_VALUES["corruption_threshold"],
    )
    corruption_threshold = threshold_raw or _infer_threshold(text)

    corruption_model = _normalize_label(
        payload.get("corruption_model"),
        {"honest_majority", "dishonest_majority"},
    )
    if not corruption_model:
        corruption_model = _derive_corruption_model(text, corruption_threshold, notes)

    latency_priority = _normalize_label(payload.get("latency_priority"), {"high", "normal"})
    if not latency_priority:
        latency_priority = (
            "high"
            if _contains_any(text, ["低延迟", "实时", "latency", "round", "low-latency"])
            else "normal"
        )

    bandwidth_priority = _normalize_label(payload.get("bandwidth_priority"), {"high", "normal"})
    if not bandwidth_priority:
        bandwidth_priority = (
            "high"
            if _contains_any(text, ["低带宽", "带宽敏感", "wan", "bandwidth", "传输成本"])
            else "normal"
        )

    target = _normalize_label(payload.get("target"), {"prototype", "production_candidate"})
    if not target:
        target = (
            "prototype"
            if _contains_any(text, ["演示", "demo", "prototype", "原型", "poc"])
            else "production_candidate"
        )

    network_model = _normalize_label(
        payload.get("network_model"),
        OPTION_VALUES["network_model"],
    )
    if not network_model:
        network_model = _infer_network_model(text)

    security_goal = _normalize_label(
        payload.get("security_goal"),
        OPTION_VALUES["security_goal"],
        alias_map=_ALIASES.get("security_goal"),
    )
    if not security_goal:
        security_goal = _infer_security_goal(text)

    compatibility_notes = _build_compatibility_notes(
        party_count_mode=party_count_mode,
        parties=parties,
        circuit_domain=circuit_domain,
        math_structure=math_structure,
        secret_sharing=secret_sharing,
        preprocessing_preference=preprocessing_preference,
        corruption_timing=corruption_timing,
        corruption_model=corruption_model,
        corruption_threshold=corruption_threshold,
        network_model=network_model,
        security_goal=security_goal,
    )

    return ParsedRequirement(
        raw_requirement=raw_requirement,
        parties=parties,
        operation=operation,
        circuit_domain=circuit_domain,
        security_model=security_model,
        corruption_model=corruption_model,
        latency_priority=latency_priority,
        bandwidth_priority=bandwidth_priority,
        target=target,
        party_count_mode=party_count_mode,
        math_structure=math_structure,
        secret_sharing=secret_sharing,
        preprocessing_preference=preprocessing_preference,
        corruption_timing=corruption_timing,
        network_model=network_model,
        corruption_threshold=corruption_threshold,
        security_goal=security_goal,
        compatibility_notes=compatibility_notes,
        notes=notes,
    )

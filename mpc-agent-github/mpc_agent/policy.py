from __future__ import annotations

from dataclasses import dataclass, field

from .models import ParsedRequirement, ProtocolCandidate


@dataclass(frozen=True)
class ProtocolProfile:
    protocol_id: str
    title: str
    mpspdz_scripts: list[str]
    round_profile: str
    circuit_domain: str
    security_support: list[str]
    assumptions: list[str]
    preprocessed: bool
    references: list[str]
    math_structures: list[str] = field(default_factory=list)
    secret_sharing: list[str] = field(default_factory=list)
    network_models: list[str] = field(default_factory=lambda: ["synchronous"])
    corruption_timing_support: list[str] = field(default_factory=lambda: ["static"])
    threshold_support: list[str] = field(default_factory=list)
    security_goals: list[str] = field(default_factory=lambda: ["security_with_abort"])


THRESHOLD_LEVELS = {
    "t_lt_n_over_3": 1,
    "t_lt_n_over_2": 2,
    "t_lt_n": 3,
}


PROFILES: dict[str, ProtocolProfile] = {
    "yao": ProtocolProfile(
        protocol_id="yao",
        title="Yao Garbled Circuits (2PC)",
        mpspdz_scripts=["Scripts/yao.sh", "Scripts/yao.bat"],
        round_profile="constant",
        circuit_domain="boolean",
        security_support=["semi_honest", "malicious"],
        assumptions=["two_party", "dishonest_majority"],
        preprocessed=False,
        references=[
            "Table 3.1: Yao rounds=constant, circuit=Boolean",
            "Section 3.1: Yao avoids latency growth with circuit depth",
        ],
        threshold_support=["t_lt_n"],
    ),
    "gmw": ProtocolProfile(
        protocol_id="gmw",
        title="GMW (Boolean/Arithmetic Sharing)",
        mpspdz_scripts=["Scripts/semi.sh", "Scripts/semi.bat"],
        round_profile="circuit_depth",
        circuit_domain="mixed",
        security_support=["semi_honest"],
        assumptions=["multi_party", "dishonest_majority"],
        preprocessed=False,
        references=[
            "Table 3.1: GMW rounds=circuit depth",
            "Section 3.2: GMW supports many parties and Boolean/arithmetic circuits",
        ],
        math_structures=["ring", "finite_field"],
        secret_sharing=["additive"],
        threshold_support=["t_lt_n"],
    ),
    "bmr": ProtocolProfile(
        protocol_id="bmr",
        title="BMR (Constant-Round Multi-party Garbling)",
        mpspdz_scripts=["Scripts/bmr.sh", "Scripts/bmr.bat"],
        round_profile="constant",
        circuit_domain="boolean",
        security_support=["semi_honest", "malicious"],
        assumptions=["multi_party", "dishonest_majority"],
        preprocessed=False,
        references=[
            "Section 3.5: BMR constant rounds for multi-party setting",
        ],
        threshold_support=["t_lt_n"],
    ),
    "shamir": ProtocolProfile(
        protocol_id="shamir",
        title="BGW/Shamir-Style Honest-Majority",
        mpspdz_scripts=["Scripts/shamir.sh", "Scripts/shamir.bat"],
        round_profile="circuit_depth",
        circuit_domain="arithmetic",
        security_support=["semi_honest", "malicious"],
        assumptions=["multi_party", "honest_majority"],
        preprocessed=False,
        references=[
            "Section 3.3: BGW over arithmetic circuits with Shamir sharing",
            "Section 3.3: secure for t corruptions where 2t < n (honest majority)",
        ],
        math_structures=["finite_field"],
        secret_sharing=["shamir"],
        threshold_support=["t_lt_n_over_3", "t_lt_n_over_2"],
        security_goals=["security_with_abort", "guaranteed_output_delivery"],
    ),
    "semi2k": ProtocolProfile(
        protocol_id="semi2k",
        title="Semi2k (Dishonest-Majority Semi-honest Arithmetic)",
        mpspdz_scripts=["Scripts/semi2k.sh", "Scripts/semi2k.bat", "Scripts/semi.sh", "Scripts/semi.bat"],
        round_profile="circuit_depth",
        circuit_domain="arithmetic",
        security_support=["semi_honest"],
        assumptions=["multi_party", "dishonest_majority"],
        preprocessed=True,
        references=[
            "Section 3.4: preprocessing triples move major communication offline",
            "Table 3.1 + implementation practice: arithmetic sharing protocols for many parties",
        ],
        math_structures=["ring"],
        secret_sharing=["additive"],
        threshold_support=["t_lt_n"],
    ),
    "mascot": ProtocolProfile(
        protocol_id="mascot",
        title="SPDZ-family with MASCOT Preprocessing",
        mpspdz_scripts=["Scripts/mascot.sh", "Scripts/mascot.bat"],
        round_profile="circuit_depth",
        circuit_domain="arithmetic",
        security_support=["malicious"],
        assumptions=["multi_party", "dishonest_majority"],
        preprocessed=True,
        references=[
            "Section 6.6: SPDZ authenticated sharing for malicious adversaries",
            "Section 3.4 + 6.6: preprocessing triples and online execution split",
            "Table 6.1: BDOZ/SPDZ malicious protocols with preprocessing",
        ],
        math_structures=["finite_field"],
        secret_sharing=["additive"],
        threshold_support=["t_lt_n"],
    ),
}

SKILL_PROTOCOL_BONUS: dict[str, dict[str, int]] = {
    "arithmetic-aggregation": {
        "mascot": 6,
        "semi2k": 6,
        "shamir": 3,
        "gmw": 2,
    },
    "boolean-comparison": {
        "yao": 10,
        "bmr": 8,
        "gmw": 6,
    },
}


def _score_security(req: ParsedRequirement, profile: ProtocolProfile) -> tuple[int, str]:
    supports = set(profile.security_support)
    required = req.security_model

    if required == "malicious":
        if "malicious" in supports:
            return 6, "安全模型匹配 malicious。"
        return -8, "需求为 malicious，但协议不支持 malicious。"

    if required == "covert":
        if "covert" in supports:
            return 4, "安全模型匹配 covert。"
        if "malicious" in supports:
            return 3, "协议提供更强 malicious 安全，可覆盖 covert 需求。"
        if "semi_honest" in supports:
            return -3, "需求为 covert，但协议仅支持 semi_honest。"
        return -5, "安全模型不匹配。"

    if "semi_honest" in supports:
        return 4, "安全模型匹配 semi_honest。"
    if "malicious" in supports:
        return 2, "协议提供更强 malicious 安全。"
    return -4, "安全模型不匹配。"


def _score_corruption(req: ParsedRequirement, profile: ProtocolProfile) -> tuple[int, str]:
    assumptions = set(profile.assumptions)

    if req.corruption_model == "dishonest_majority":
        if "dishonest_majority" in assumptions:
            return 5, "需求为 dishonest majority，协议假设一致。"
        return -8, "协议要求 honest majority，与需求冲突。"

    if "honest_majority" in assumptions:
        return 4, "需求为 honest majority，协议假设一致。"
    if "dishonest_majority" in assumptions:
        return 1, "协议支持更强的 dishonest majority 假设。"
    return -3, "腐化模型不匹配。"


def _score_domain(req: ParsedRequirement, profile: ProtocolProfile) -> tuple[int, str]:
    required = req.circuit_domain
    actual = profile.circuit_domain

    if required == "mixed":
        if actual == "mixed":
            return 5, "需求为 mixed，协议原生支持 mixed。"
        if actual in {"arithmetic", "boolean"}:
            return 2, f"需求为 mixed，协议可部分覆盖（{actual}）。"
        return -2, "电路类型不匹配。"

    if required == actual:
        return 5, f"电路类型匹配（{required}）。"

    if required == "boolean" and actual == "mixed":
        return 3, "需求偏 boolean，mixed 协议可兼容。"
    if required == "arithmetic" and actual == "mixed":
        return 3, "需求偏 arithmetic，mixed 协议可兼容。"

    return -4, "电路类型存在明显不匹配。"


def _score_math_structure(req: ParsedRequirement, profile: ProtocolProfile) -> tuple[int, str]:
    required = req.math_structure
    if required == "auto" or req.circuit_domain == "boolean":
        return 0, "未对底层数学结构施加额外约束。"
    if required in profile.math_structures:
        return 2, f"底层数学结构匹配（{required}）。"
    if not profile.math_structures:
        return -2, "协议未显式暴露所需底层数学结构。"
    return -4, f"协议不支持所需底层数学结构（{required}）。"


def _score_secret_sharing(req: ParsedRequirement, profile: ProtocolProfile) -> tuple[int, str]:
    required = req.secret_sharing
    if required == "auto":
        return 0, "未对 secret sharing 施加额外约束。"
    if required in profile.secret_sharing:
        return 3, f"secret sharing 匹配（{required}）。"
    if not profile.secret_sharing:
        return -2, "协议未直接暴露所需 secret sharing 类型。"
    return -4, f"协议不支持所需 secret sharing（{required}）。"


def _score_preprocessing(req: ParsedRequirement, profile: ProtocolProfile) -> tuple[int, str]:
    required = req.preprocessing_preference
    if required == "auto":
        return 0, "未显式指定预处理阶段要求。"
    if required == "required":
        if profile.preprocessed:
            return 3, "需求偏向预处理，协议具备 offline/online 结构。"
        return -4, "需求要求预处理，但该协议不具备明显预处理优势。"
    if not profile.preprocessed:
        return 2, "需求偏向不使用预处理，协议更贴近该约束。"
    return -3, "需求不希望依赖预处理，但该协议通常带有预处理阶段。"


def _score_timing(req: ParsedRequirement, profile: ProtocolProfile) -> tuple[int, str]:
    required = req.corruption_timing
    if required == "auto":
        return 0, "未显式指定 static / adaptive。"
    if required in profile.corruption_timing_support:
        return 2, f"腐化方式匹配（{required}）。"
    return -5, f"协议未声明支持 {required} 腐化方式。"


def _score_network(req: ParsedRequirement, profile: ProtocolProfile) -> tuple[int, str]:
    required = req.network_model
    if required == "auto":
        return 0, "未显式指定网络模型。"
    if required in profile.network_models:
        return 2, f"网络模型匹配（{required}）。"
    return -4, f"协议画像未覆盖 {required} 网络模型。"


def _max_threshold_level(profile: ProtocolProfile) -> int:
    if not profile.threshold_support:
        return 0
    return max(THRESHOLD_LEVELS.get(item, 0) for item in profile.threshold_support)


def _score_threshold(req: ParsedRequirement, profile: ProtocolProfile) -> tuple[int, str]:
    required = req.corruption_threshold
    if required == "auto":
        return 0, "未显式指定敌手门限。"

    required_level = THRESHOLD_LEVELS.get(required, 0)
    profile_level = _max_threshold_level(profile)
    if profile_level >= required_level:
        if required in profile.threshold_support:
            return 3, f"敌手门限匹配（{required}）。"
        return 1, f"协议可覆盖不弱于 {required} 的门限需求。"
    return -6, f"协议门限能力不足，无法满足 {required}。"


def _score_security_goal(req: ParsedRequirement, profile: ProtocolProfile) -> tuple[int, str]:
    required = req.security_goal
    if required == "auto":
        return 0, "未显式指定更细粒度安全目标。"
    if required in profile.security_goals:
        return 3, f"安全目标匹配（{required}）。"
    return -4, f"协议画像未覆盖 {required}。"


def _score_profile(req: ParsedRequirement, profile: ProtocolProfile) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []

    is_two_party = req.parties == 2
    is_multi_party = req.parties > 2

    if "two_party" in profile.assumptions and is_two_party:
        score += 5
        reasons.append("参与方为 2，匹配 two-party 协议。")
    if "two_party" in profile.assumptions and is_multi_party:
        score -= 10
        reasons.append("协议偏向 2PC，不适合当前多方场景。")
    if "multi_party" in profile.assumptions and is_multi_party:
        score += 5
        reasons.append("参与方大于 2，匹配多方协议。")
    if "multi_party" in profile.assumptions and is_two_party:
        score += 2
        reasons.append("协议支持 2 方，但更偏向多方场景。")

    for scorer in (
        _score_domain,
        _score_security,
        _score_corruption,
        _score_math_structure,
        _score_secret_sharing,
        _score_preprocessing,
        _score_timing,
        _score_network,
        _score_threshold,
        _score_security_goal,
    ):
        delta, reason = scorer(req, profile)
        score += delta
        reasons.append(reason)

    if req.latency_priority == "high":
        if profile.round_profile == "constant":
            score += 3
            reasons.append("低延迟优先，常数轮协议更优。")
        else:
            score -= 2
            reasons.append("低延迟优先，但协议轮数与电路深度相关。")

    if req.bandwidth_priority == "high" and profile.preprocessed:
        score += 2
        reasons.append("带宽敏感，预处理型协议可降低在线传输压力。")
    elif req.bandwidth_priority == "high":
        score -= 1
        reasons.append("带宽敏感，但该协议不具备明显的预处理优势。")

    if req.operation == "comparison" and profile.protocol_id in {"yao", "bmr", "gmw"}:
        score += 2
        reasons.append("比较类任务通常适合 Boolean 路线。")
    if req.operation in {"aggregation", "ml"} and profile.circuit_domain in {"arithmetic", "mixed"}:
        score += 2
        reasons.append("聚合/ML 任务更偏算术电路。")

    if (
        req.parties == 2
        and req.operation == "comparison"
        and req.latency_priority == "high"
        and profile.protocol_id == "yao"
    ):
        score += 3
        reasons.append("2PC 比较且低延迟，Yao 作为优先候选。")

    if (
        req.parties > 2
        and req.security_model == "malicious"
        and req.corruption_model == "dishonest_majority"
        and req.circuit_domain in {"arithmetic", "mixed"}
        and profile.protocol_id == "mascot"
    ):
        score += 4
        reasons.append("多方恶意 + 非诚实多数 + 算术场景：优先 MASCOT。")

    if (
        req.security_model == "semi_honest"
        and req.corruption_model == "dishonest_majority"
        and req.circuit_domain in {"arithmetic", "mixed"}
        and profile.protocol_id == "semi2k"
    ):
        score += 3
        reasons.append("半诚实 + 非诚实多数算术场景：Semi2k 具有实现优势。")

    if req.target == "prototype" and "semi_honest" in profile.security_support:
        score += 1
        reasons.append("原型验证场景：semi-honest 协议迭代成本更低。")

    return score, reasons


def collect_compatibility_notes(req: ParsedRequirement, profile: ProtocolProfile) -> list[str]:
    notes: list[str] = []

    if req.math_structure != "auto" and req.math_structure not in profile.math_structures:
        notes.append(f"{profile.title} 不满足所选底层数学结构：{req.math_structure}。")

    if req.secret_sharing != "auto" and req.secret_sharing not in profile.secret_sharing:
        notes.append(f"{profile.title} 不满足所选 secret sharing：{req.secret_sharing}。")

    if req.preprocessing_preference == "required" and not profile.preprocessed:
        notes.append(f"{profile.title} 不具备明显的预处理阶段。")
    if req.preprocessing_preference == "disallowed" and profile.preprocessed:
        notes.append(f"{profile.title} 通常依赖预处理阶段，与你的偏好不完全一致。")

    if req.corruption_timing != "auto" and req.corruption_timing not in profile.corruption_timing_support:
        notes.append(f"{profile.title} 未声明支持 {req.corruption_timing} 腐化方式。")

    if req.network_model != "auto" and req.network_model not in profile.network_models:
        notes.append(f"{profile.title} 未声明支持 {req.network_model} 网络模型。")

    if req.security_goal != "auto" and req.security_goal not in profile.security_goals:
        notes.append(f"{profile.title} 未声明支持安全目标 {req.security_goal}。")

    if req.corruption_threshold != "auto":
        required_level = THRESHOLD_LEVELS.get(req.corruption_threshold, 0)
        if _max_threshold_level(profile) < required_level:
            notes.append(f"{profile.title} 的门限能力不足以覆盖 {req.corruption_threshold}。")

    return list(dict.fromkeys(notes))


def _apply_skill_bias(
    ranked: list[ProtocolCandidate],
    skill_names: list[str] | None,
) -> None:
    if not skill_names:
        return

    enabled_skills = [skill for skill in skill_names if skill in SKILL_PROTOCOL_BONUS]
    if not enabled_skills:
        return

    for candidate in ranked:
        total_bonus = 0
        for skill in enabled_skills:
            bonus = SKILL_PROTOCOL_BONUS[skill].get(candidate.protocol_id, 0)
            if bonus:
                total_bonus += bonus
                candidate.reasons.append(f"Skill `{skill}` applied: +{bonus} bias.")
        if total_bonus:
            candidate.score += total_bonus


def _apply_protocol_bias(
    ranked: list[ProtocolCandidate],
    protocol_bias: dict[str, int] | None,
) -> None:
    if not protocol_bias:
        return

    for candidate in ranked:
        bonus = int(protocol_bias.get(candidate.protocol_id, 0))
        if bonus == 0:
            continue
        candidate.score += bonus
        sign = "+" if bonus > 0 else ""
        candidate.reasons.append(f"Protocol bias applied: {sign}{bonus}.")


def rank_candidates(
    req: ParsedRequirement,
    top_k: int = 4,
    *,
    skill_names: list[str] | None = None,
    protocol_bias: dict[str, int] | None = None,
) -> list[ProtocolCandidate]:
    ranked: list[ProtocolCandidate] = []
    for profile in PROFILES.values():
        score, reasons = _score_profile(req, profile)
        ranked.append(
            ProtocolCandidate(
                protocol_id=profile.protocol_id,
                title=profile.title,
                score=score,
                mpspdz_scripts=profile.mpspdz_scripts,
                round_profile=profile.round_profile,
                circuit_domain=profile.circuit_domain,
                security_support=profile.security_support,
                assumptions=profile.assumptions,
                reasons=reasons,
                preprocessed=profile.preprocessed,
                math_structures=profile.math_structures,
                secret_sharing=profile.secret_sharing,
                network_models=profile.network_models,
                corruption_timing_support=profile.corruption_timing_support,
                threshold_support=profile.threshold_support,
                security_goals=profile.security_goals,
            )
        )

    _apply_skill_bias(ranked, skill_names)
    _apply_protocol_bias(ranked, protocol_bias)
    ranked.sort(key=lambda item: item.score, reverse=True)
    return ranked[:top_k]


def get_profile(protocol_id: str) -> ProtocolProfile:
    return PROFILES[protocol_id]

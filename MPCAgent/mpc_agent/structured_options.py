"""Mapping from UI option selections to MPC protocol config fields."""

from __future__ import annotations

from .normalization import normalize_config
from .schemas import AgentReply, MPCProtocolConfig, MPCStructuredOptions, find_missing_fields


AUTO_VALUES = {None, "", "auto", "Auto"}


def _selected(value: str | None) -> bool:
    return value not in AUTO_VALUES


def options_to_config(options: MPCStructuredOptions | None) -> MPCProtocolConfig:
    config = MPCProtocolConfig()
    if options is None or not options.has_values():
        return config

    if options.number_of_parties:
        config.participant_scale.number_of_parties = options.number_of_parties
    elif options.participant_scale == "2-party":
        config.participant_scale.number_of_parties = 2
    elif options.participant_scale == "3-party":
        config.participant_scale.number_of_parties = 3

    if options.participant_scale == "n-party" and not options.number_of_parties:
        config.participant_scale.notes = "User selected n-party but did not specify exact n."

    if _selected(options.circuit_form):
        config.circuit.form = options.circuit_form

    if _selected(options.math_structure):
        config.math_structure.structure = options.math_structure
        if options.math_structure == "RingZ2k":
            config.math_structure.notes = "Ring size k was not specified."
        elif options.math_structure == "PrimeField":
            config.math_structure.notes = "Prime modulus was not specified."

    if _selected(options.secret_sharing):
        config.secret_sharing.scheme = options.secret_sharing

    if options.preprocessing == "Required":
        config.preprocessing.enabled = True
        config.preprocessing.materials = ["Beaver triples"]
    elif options.preprocessing == "None":
        config.preprocessing.enabled = False

    if _selected(options.adversary_behavior):
        config.adversary.behavior_model = options.adversary_behavior

    if _selected(options.corruption_strategy):
        config.adversary.corruption_strategy = options.corruption_strategy

    if _selected(options.corruption_threshold):
        config.adversary.corruption_threshold = options.corruption_threshold

    if _selected(options.network_model):
        config.network.synchrony = options.network_model

    if _selected(options.channel_model):
        config.network.channels = options.channel_model

    if options.security_goal == "PrivacyCorrectness":
        config.security_goals.privacy = "yes"
        config.security_goals.correctness = "yes"
    elif options.security_goal == "Abort":
        config.security_goals.correctness = "security with abort"
        config.security_goals.robustness = "abort is allowed"
    elif options.security_goal == "GuaranteedOutputDelivery":
        config.security_goals.guaranteed_output_delivery = "yes"
    elif options.security_goal == "Fairness":
        config.security_goals.fairness = "yes"
    elif options.security_goal == "Robustness":
        config.security_goals.robustness = "yes"

    return config


def options_to_prompt_text(options: MPCStructuredOptions | None) -> str:
    if options is None or not options.has_values():
        return "无"

    labels = {
        "participant_scale": "参与方规模",
        "number_of_parties": "参与方数量",
        "circuit_form": "电路形式",
        "math_structure": "底层数学结构",
        "secret_sharing": "Secret Sharing",
        "preprocessing": "预处理阶段",
        "adversary_behavior": "敌手行为模型",
        "corruption_strategy": "腐化方式",
        "network_model": "网络模型",
        "channel_model": "信道模型",
        "corruption_threshold": "敌手门限",
        "security_goal": "安全目标",
    }
    parts: list[str] = []
    for key, value in options.model_dump().items():
        if value in AUTO_VALUES:
            continue
        parts.append(f"{labels[key]}={value}")
    return "；".join(parts) if parts else "无"


def options_display_text(options: MPCStructuredOptions | None) -> str:
    text = options_to_prompt_text(options)
    return "结构化选项：" + text if text != "无" else ""


MISSING_LABELS = {
    "participant_scale.number_of_parties": "参与方数量",
    "circuit.form": "电路形式",
    "math_structure.structure": "底层数学结构",
    "secret_sharing.scheme": "Secret Sharing",
    "preprocessing.enabled": "是否需要预处理",
    "adversary.behavior_model": "敌手行为模型",
    "adversary.corruption_strategy": "腐化方式",
    "adversary.corruption_threshold": "敌手门限",
    "network.synchrony": "网络模型",
    "security_goals.privacy": "隐私目标",
    "security_goals.correctness": "正确性目标",
}


def build_option_only_reply(
    config: MPCProtocolConfig,
    *,
    had_natural_language: bool,
    fallback_reason: str | None = None,
) -> AgentReply:
    normalized = normalize_config(config)
    summary_parts: list[str] = []
    if normalized.participant_scale.number_of_parties:
        summary_parts.append(f"{normalized.participant_scale.number_of_parties}方")
    if normalized.circuit.form:
        summary_parts.append(normalized.circuit.form)
    if normalized.math_structure.structure:
        summary_parts.append(normalized.math_structure.structure)
    if normalized.secret_sharing.scheme:
        summary_parts.append(normalized.secret_sharing.scheme)
    if normalized.preprocessing.enabled is True:
        summary_parts.append("需要预处理")
    elif normalized.preprocessing.enabled is False:
        summary_parts.append("无预处理")
    if normalized.adversary.behavior_model:
        summary_parts.append(normalized.adversary.behavior_model)
    if normalized.adversary.corruption_strategy:
        summary_parts.append(normalized.adversary.corruption_strategy)
    if normalized.network.synchrony:
        summary_parts.append(normalized.network.synchrony)
    if normalized.security_goals.privacy == "yes" and normalized.security_goals.correctness == "yes":
        summary_parts.append("Privacy + Correctness")

    prefix = "已根据您提供的结构化选项完成配置更新。"
    if had_natural_language:
        prefix = "本轮优先采用了结构化选项，并据此更新配置。"
    if fallback_reason:
        prefix = f"{prefix} 模型结构化解析失败后，系统已回退到确定性选项映射。"

    message = prefix
    if summary_parts:
        message += " 当前配置为：" + "、".join(summary_parts) + "。"

    missing_paths = find_missing_fields(normalized)
    missing_fields = [MISSING_LABELS.get(path, path) for path in missing_paths]

    clarifying_questions: list[str] = []
    if not normalized.participant_scale.input_owners and not normalized.participant_scale.output_recipients:
        clarifying_questions.append("哪些参与方提供输入，哪些参与方接收输出？")
    if normalized.math_structure.structure == "PrimeField" and not normalized.math_structure.modulus:
        clarifying_questions.append("素数域的模数希望使用哪个值？")
    if normalized.network.channels is None:
        clarifying_questions.append("网络是否需要认证信道、私密信道或 TLS 信道？")
    if normalized.preprocessing.enabled and not normalized.preprocessing.materials:
        clarifying_questions.append("预处理阶段是否需要明确材料，例如 Beaver triples 或随机比特？")

    next_actions = [
        "继续补充缺失字段，尤其是输入输出角色、数学参数和网络信道。",
        "根据当前配置生成后端协议执行计划。",
    ]
    if normalized.adversary.behavior_model == "Malicious":
        next_actions.append("优先考虑 MP-SPDZ 等覆盖恶意安全协议的后端。")
    elif normalized.adversary.behavior_model == "Semi-honest":
        next_actions.append("可以优先评估 SPU 或 CrypTen 等更高效的半诚实后端。")

    return AgentReply(
        message=message,
        missing_fields=missing_fields,
        clarifying_questions=clarifying_questions,
        next_actions=next_actions,
    )

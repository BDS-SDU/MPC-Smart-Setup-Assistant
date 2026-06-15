from __future__ import annotations

from typing import Any

from mpc_agent.models import ParsedRequirement
from mpc_agent.policy import rank_candidates


def _coerce_parsed_requirement(value: ParsedRequirement | dict[str, Any]) -> ParsedRequirement:
    if isinstance(value, ParsedRequirement):
        return value
    return ParsedRequirement(**value)


def rank_protocols_tool(
    parsed_requirement: ParsedRequirement | dict[str, Any],
    *,
    top_k: int = 4,
    skills: list[str] | None = None,
    protocol_bias: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    parsed_obj = _coerce_parsed_requirement(parsed_requirement)
    return [
        candidate.to_dict()
        for candidate in rank_candidates(
            parsed_obj,
            top_k=top_k,
            skill_names=skills,
            protocol_bias=protocol_bias,
        )
    ]

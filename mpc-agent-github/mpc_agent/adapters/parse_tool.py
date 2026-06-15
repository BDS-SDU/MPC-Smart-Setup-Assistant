from __future__ import annotations

from typing import Any

from mpc_agent.parser import parse_requirement


def parse_requirement_tool(
    requirement: str,
    parties: int | None = None,
    *,
    extras: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"requirement": requirement}
    if parties is not None:
        payload["parties"] = parties
    if extras:
        payload.update(extras)
    return parse_requirement(payload).to_dict()


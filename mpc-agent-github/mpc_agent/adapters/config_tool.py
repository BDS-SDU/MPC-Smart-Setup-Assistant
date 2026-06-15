from __future__ import annotations

from typing import Any

from mpc_agent.orchestrator import MpcAutoConfigAgent


_AGENT = MpcAutoConfigAgent()


def generate_configuration_tool(payload: dict[str, Any]) -> dict[str, Any]:
    local_payload = dict(payload)
    local_payload.setdefault("execute", False)
    return _AGENT.configure(local_payload)


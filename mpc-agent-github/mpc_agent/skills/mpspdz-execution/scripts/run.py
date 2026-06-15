from __future__ import annotations

import argparse
import json
from typing import Any

from mpc_agent.adapters.config_tool import generate_configuration_tool
from mpc_agent.adapters.runner_tool import run_protocol_tool


def run_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    config = generate_configuration_tool({**payload, "execute": False})
    execution = run_protocol_tool(
        payload,
        config["parsed_requirement"],
        config["final_configuration"],
    )
    return {
        "parsed_requirement": config["parsed_requirement"],
        "final_configuration": config["final_configuration"],
        "execution": execution,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run MPC protocol using adapter workflow.")
    parser.add_argument("--payload-json", required=True, help="JSON string payload for configure/run.")
    args = parser.parse_args()
    payload = json.loads(args.payload_json)
    print(json.dumps(run_from_payload(payload), ensure_ascii=False))


if __name__ == "__main__":
    main()


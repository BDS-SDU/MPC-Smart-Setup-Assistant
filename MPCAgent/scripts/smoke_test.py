"""Smoke test for a running MPC agent FastAPI service."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import requests


DEFAULT_MESSAGE = (
    "测试：四方半诚实MPC，最多腐化一方，使用布尔电路和GMW协议，"
    "同步网络，安全目标是隐私和正确性。"
)


def request_json(method: str, url: str, **kwargs: Any) -> Any:
    response = requests.request(method, url, timeout=90, **kwargs)
    try:
        payload = response.json()
    except ValueError:
        payload = response.text

    if response.status_code >= 400:
        print(f"[FAIL] {method} {url} -> {response.status_code}")
        print(payload)
        raise SystemExit(1)

    print(f"[OK] {method} {url} -> {response.status_code}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test the MPC agent service")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--message", default=DEFAULT_MESSAGE)
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    health = request_json("GET", f"{base_url}/health")
    print(json.dumps(health, ensure_ascii=False, indent=2))

    schema = request_json("GET", f"{base_url}/schema")
    print(f"schema title: {schema.get('title')}")

    result = request_json("POST", f"{base_url}/chat", json={"message": args.message})
    print("summary:", result["summary"])
    config = result.get("current_mpc_config") or result["config"]
    print(
        json.dumps(
            {
                "session_id": result["session_id"],
                "parties": config["participant_scale"]["number_of_parties"],
                "circuit": config["circuit"]["form"],
                "adversary": config["adversary"]["behavior_model"],
                "canonical_parameters": config.get("canonical_parameters", {}),
                "missing_fields": result["missing_fields"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    config = request_json(
        "GET",
        f"{base_url}/sessions/{result['session_id']}/config",
    )
    print("saved config circuit:", config["circuit"]["form"])
    return 0


if __name__ == "__main__":
    sys.exit(main())

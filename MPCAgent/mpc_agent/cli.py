"""Small CLI for quick local testing."""

from __future__ import annotations

import argparse

from .agent import MPCConfigAgent
from .schemas import ChatRequest
from .utils import to_pretty_json


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MPC protocol configuration agent")
    parser.add_argument("message", help="Natural-language MPC requirement")
    parser.add_argument("--session-id", default=None)
    parser.add_argument("--reset", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    agent = MPCConfigAgent()
    response = agent.process(
        ChatRequest(
            message=args.message,
            session_id=args.session_id,
            reset=args.reset,
        )
    )
    print(to_pretty_json(response))


if __name__ == "__main__":
    main()

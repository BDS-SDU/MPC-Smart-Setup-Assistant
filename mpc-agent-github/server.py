from __future__ import annotations

import json
import mimetypes
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from mpc_agent.case_store import find_similar_cases, list_cases, record_feedback
from mpc_agent.integrations.external_api import call_external_api, list_external_systems
from mpc_agent.knowledge_base import list_sections, retrieve_knowledge
from mpc_agent.mcp.server import LocalMcpServer
from mpc_agent.open_source_catalog import (
    catalog_summary,
    list_open_source_deployments,
    list_research_gaps,
    recommend_open_source_protocols,
)
from mpc_agent.orchestrator import MpcAutoConfigAgent
from mpc_agent.requirement_options import list_requirement_options
from mpc_agent.runtime_signals import collect_runtime_signals, probe_network, query_local_hardware
from mpc_agent.skills.executor import execute_skill
from mpc_agent.skills.registry import list_skills
from mpc_agent.skills.router import recommend_skills


PROJECT_ROOT = Path(__file__).resolve().parent
STATIC_DIR = PROJECT_ROOT / "static"
AGENT = MpcAutoConfigAgent()
MCP_SERVER = LocalMcpServer()


class Handler(BaseHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        super().end_headers()

    def log_message(self, format_str: str, *args: Any) -> None:
        print(f"[server] {self.address_string()} - {format_str % args}")

    def _send_json(self, payload: dict[str, Any], status: int = HTTPStatus.OK) -> None:
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_file(self, file_path: Path) -> None:
        if not file_path.exists() or not file_path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return
        content = file_path.read_bytes()
        content_type, _ = mimetypes.guess_type(str(file_path))
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            self._send_json({"status": "ok"})
            return
        if parsed.path == "/api/mcp/capabilities":
            self._send_json({"ok": True, "result": MCP_SERVER.capabilities()})
            return
        if parsed.path == "/api/skills/list":
            self._send_json({"ok": True, "skills": list_skills()})
            return
        if parsed.path == "/api/requirement-options":
            self._send_json({"ok": True, "option_groups": list_requirement_options()})
            return
        if parsed.path == "/api/open-source-protocols":
            self._send_json(
                {
                    "ok": True,
                    "summary": catalog_summary(),
                    "deployments": list_open_source_deployments(),
                    "research_gaps": list_research_gaps(),
                }
            )
            return
        if parsed.path == "/api/knowledge/sections":
            self._send_json({"ok": True, "sections": list_sections()})
            return
        if parsed.path == "/api/cases/list":
            self._send_json({"ok": True, "cases": list_cases(limit=20)})
            return
        if parsed.path == "/api/runtime/hardware":
            self._send_json({"ok": True, "result": query_local_hardware()})
            return
        if parsed.path == "/api/integrations/systems":
            self._send_json({"ok": True, "systems": list_external_systems()})
            return

        if parsed.path in {"/", "/index.html"}:
            self._send_file(STATIC_DIR / "index.html")
            return

        relative = parsed.path.lstrip("/")
        target = (STATIC_DIR / relative).resolve()
        if STATIC_DIR.resolve() not in target.parents and target != STATIC_DIR.resolve():
            self.send_error(HTTPStatus.FORBIDDEN, "Invalid path")
            return
        self._send_file(target)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path not in {
            "/api/configure",
            "/api/mcp",
            "/api/skills/recommend",
            "/api/skills/execute",
            "/api/knowledge/retrieve",
            "/api/cases/similar",
            "/api/cases/feedback",
            "/api/runtime/network/probe",
            "/api/runtime/signals/collect",
            "/api/open-source-protocols/recommend",
            "/api/integrations/call",
        }:
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return

        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length > 0 else b"{}"
        try:
            payload = json.loads(body.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("Payload must be JSON object.")
        except (json.JSONDecodeError, ValueError) as error:
            self._send_json(
                {"error": f"Invalid JSON payload: {error}"},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        if parsed.path == "/api/mcp":
            try:
                result = MCP_SERVER.handle_request(payload)
                self._send_json({"ok": True, "result": result}, status=HTTPStatus.OK)
            except (KeyError, ValueError) as error:
                self._send_json(
                    {"error": "bad_request", "detail": str(error)},
                    status=HTTPStatus.BAD_REQUEST,
                )
            except Exception as error:  # noqa: BLE001
                self._send_json(
                    {
                        "error": "internal_error",
                        "detail": str(error),
                    },
                    status=HTTPStatus.INTERNAL_SERVER_ERROR,
                )
            return

        if parsed.path == "/api/skills/recommend":
            try:
                result = recommend_skills(payload)
                self._send_json({"ok": True, "result": result}, status=HTTPStatus.OK)
            except Exception as error:  # noqa: BLE001
                self._send_json(
                    {
                        "error": "internal_error",
                        "detail": str(error),
                    },
                    status=HTTPStatus.INTERNAL_SERVER_ERROR,
                )
            return

        if parsed.path == "/api/skills/execute":
            try:
                skill_name = str(payload.get("name", "")).strip()
                if not skill_name:
                    raise ValueError("`name` is required.")
                skill_payload = payload.get("payload", {})
                if not isinstance(skill_payload, dict):
                    raise ValueError("`payload` must be a JSON object.")
                result = execute_skill(skill_name, skill_payload)
                self._send_json({"ok": True, "result": result}, status=HTTPStatus.OK)
            except (KeyError, ValueError) as error:
                self._send_json(
                    {"error": "bad_request", "detail": str(error)},
                    status=HTTPStatus.BAD_REQUEST,
                )
            except Exception as error:  # noqa: BLE001
                self._send_json(
                    {
                        "error": "internal_error",
                        "detail": str(error),
                    },
                    status=HTTPStatus.INTERNAL_SERVER_ERROR,
                )
            return

        if parsed.path == "/api/knowledge/retrieve":
            try:
                query = str(payload.get("query", "")).strip()
                if not query:
                    raise ValueError("`query` is required.")
                top_k_raw = payload.get("top_k", 4)
                top_k = top_k_raw if isinstance(top_k_raw, int) else 4
                result = retrieve_knowledge(query, top_k=top_k)
                self._send_json({"ok": True, "result": result}, status=HTTPStatus.OK)
            except (ValueError, KeyError) as error:
                self._send_json(
                    {"error": "bad_request", "detail": str(error)},
                    status=HTTPStatus.BAD_REQUEST,
                )
            except Exception as error:  # noqa: BLE001
                self._send_json(
                    {
                        "error": "internal_error",
                        "detail": str(error),
                    },
                    status=HTTPStatus.INTERNAL_SERVER_ERROR,
                )
            return

        if parsed.path == "/api/cases/similar":
            try:
                parsed_requirement = payload.get("parsed_requirement")
                if not isinstance(parsed_requirement, dict):
                    raise ValueError("`parsed_requirement` is required and must be a JSON object.")
                limit_raw = payload.get("limit", 5)
                limit = limit_raw if isinstance(limit_raw, int) else 5
                result = find_similar_cases(parsed_requirement, limit=limit)
                self._send_json({"ok": True, "similar_cases": result}, status=HTTPStatus.OK)
            except (ValueError, KeyError) as error:
                self._send_json(
                    {"error": "bad_request", "detail": str(error)},
                    status=HTTPStatus.BAD_REQUEST,
                )
            except Exception as error:  # noqa: BLE001
                self._send_json(
                    {
                        "error": "internal_error",
                        "detail": str(error),
                    },
                    status=HTTPStatus.INTERNAL_SERVER_ERROR,
                )
            return

        if parsed.path == "/api/cases/feedback":
            try:
                case_id = str(payload.get("case_id", "")).strip()
                if not case_id:
                    raise ValueError("`case_id` is required.")
                feedback = payload.get("feedback", {})
                if not isinstance(feedback, dict):
                    raise ValueError("`feedback` must be a JSON object.")
                updated = record_feedback(case_id, feedback)
                self._send_json({"ok": True, "case": updated}, status=HTTPStatus.OK)
            except (ValueError, KeyError) as error:
                self._send_json(
                    {"error": "bad_request", "detail": str(error)},
                    status=HTTPStatus.BAD_REQUEST,
                )
            except Exception as error:  # noqa: BLE001
                self._send_json(
                    {
                        "error": "internal_error",
                        "detail": str(error),
                    },
                    status=HTTPStatus.INTERNAL_SERVER_ERROR,
                )
            return

        if parsed.path == "/api/runtime/network/probe":
            try:
                hosts = payload.get("hosts")
                if not isinstance(hosts, list) or not hosts:
                    raise ValueError("`hosts` is required and must be a non-empty list.")
                count_raw = payload.get("count", 3)
                timeout_raw = payload.get("timeout_ms", 1000)
                count = count_raw if isinstance(count_raw, int) else 3
                timeout_ms = timeout_raw if isinstance(timeout_raw, int) else 1000
                result = probe_network(hosts, count=count, timeout_ms=timeout_ms)
                self._send_json({"ok": True, "result": result}, status=HTTPStatus.OK)
            except (ValueError, KeyError) as error:
                self._send_json(
                    {"error": "bad_request", "detail": str(error)},
                    status=HTTPStatus.BAD_REQUEST,
                )
            except Exception as error:  # noqa: BLE001
                self._send_json(
                    {
                        "error": "internal_error",
                        "detail": str(error),
                    },
                    status=HTTPStatus.INTERNAL_SERVER_ERROR,
                )
            return

        if parsed.path == "/api/runtime/signals/collect":
            try:
                parsed_requirement = payload.get("parsed_requirement")
                if not isinstance(parsed_requirement, dict):
                    requirement = str(payload.get("requirement", "")).strip()
                    parties_raw = payload.get("parties")
                    if not requirement:
                        raise ValueError(
                            "Provide `parsed_requirement` or `requirement` for runtime signal collection."
                        )
                    parties = parties_raw if isinstance(parties_raw, int) else None
                    from mpc_agent.adapters.parse_tool import parse_requirement_tool

                    parsed_requirement = parse_requirement_tool(requirement, parties)
                result = collect_runtime_signals(payload, parsed_requirement)
                self._send_json({"ok": True, "result": result}, status=HTTPStatus.OK)
            except (ValueError, KeyError) as error:
                self._send_json(
                    {"error": "bad_request", "detail": str(error)},
                    status=HTTPStatus.BAD_REQUEST,
                )
            except Exception as error:  # noqa: BLE001
                self._send_json(
                    {
                        "error": "internal_error",
                        "detail": str(error),
                    },
                    status=HTTPStatus.INTERNAL_SERVER_ERROR,
                )
            return

        if parsed.path == "/api/open-source-protocols/recommend":
            try:
                parsed_requirement = payload.get("parsed_requirement")
                if not isinstance(parsed_requirement, dict):
                    requirement = str(payload.get("requirement", "")).strip()
                    parties_raw = payload.get("parties")
                    if not requirement and not any(
                        payload.get(key)
                        for key in (
                            "party_count_mode",
                            "circuit_domain",
                            "math_structure",
                            "secret_sharing",
                            "preprocessing_preference",
                            "security_model",
                            "corruption_model",
                            "corruption_timing",
                            "network_model",
                            "corruption_threshold",
                            "security_goal",
                        )
                    ):
                        raise ValueError(
                            "Provide `parsed_requirement`, `requirement`, or structured MPC fields."
                        )
                    parties = parties_raw if isinstance(parties_raw, int) else None
                    from mpc_agent.adapters.parse_tool import parse_requirement_tool

                    extras = {
                        key: value
                        for key, value in payload.items()
                        if key
                        in {
                            "operation",
                            "party_count_mode",
                            "circuit_domain",
                            "math_structure",
                            "secret_sharing",
                            "preprocessing_preference",
                            "security_model",
                            "corruption_model",
                            "corruption_timing",
                            "network_model",
                            "corruption_threshold",
                            "security_goal",
                            "latency_priority",
                            "bandwidth_priority",
                            "target",
                        }
                    }
                    parsed_requirement = parse_requirement_tool(requirement, parties, extras=extras)
                top_k_raw = payload.get("top_k", 6)
                top_k = top_k_raw if isinstance(top_k_raw, int) else 6
                from mpc_agent.models import ParsedRequirement

                result = recommend_open_source_protocols(ParsedRequirement(**parsed_requirement), limit=top_k)
                self._send_json(
                    {
                        "ok": True,
                        "parsed_requirement": parsed_requirement,
                        "result": result,
                    },
                    status=HTTPStatus.OK,
                )
            except (ValueError, KeyError) as error:
                self._send_json(
                    {"error": "bad_request", "detail": str(error)},
                    status=HTTPStatus.BAD_REQUEST,
                )
            except Exception as error:  # noqa: BLE001
                self._send_json(
                    {
                        "error": "internal_error",
                        "detail": str(error),
                    },
                    status=HTTPStatus.INTERNAL_SERVER_ERROR,
                )
            return

        if parsed.path == "/api/integrations/call":
            try:
                system_name = str(payload.get("system_name", "")).strip()
                if not system_name:
                    raise ValueError("`system_name` is required.")
                method = str(payload.get("method", "GET")).strip().upper()
                path = str(payload.get("path", "")).strip()
                query = payload.get("query")
                headers = payload.get("headers")
                body_data = payload.get("body")
                timeout_raw = payload.get("timeout_seconds")
                timeout_seconds = int(timeout_raw) if isinstance(timeout_raw, int) else None
                if query is not None and not isinstance(query, dict):
                    raise ValueError("`query` must be a JSON object when provided.")
                if headers is not None and not isinstance(headers, dict):
                    raise ValueError("`headers` must be a JSON object when provided.")
                result = call_external_api(
                    system_name=system_name,
                    method=method,
                    path=path,
                    query=query if isinstance(query, dict) else None,
                    headers=headers if isinstance(headers, dict) else None,
                    body=body_data,
                    timeout_seconds=timeout_seconds,
                )
                self._send_json({"ok": True, "result": result}, status=HTTPStatus.OK)
            except (KeyError, ValueError, PermissionError) as error:
                self._send_json(
                    {"error": "bad_request", "detail": str(error)},
                    status=HTTPStatus.BAD_REQUEST,
                )
            except Exception as error:  # noqa: BLE001
                self._send_json(
                    {
                        "error": "internal_error",
                        "detail": str(error),
                    },
                    status=HTTPStatus.INTERNAL_SERVER_ERROR,
                )
            return

        try:
            result = AGENT.configure(payload)
            self._send_json(result, status=HTTPStatus.OK)
        except Exception as error:  # noqa: BLE001
            self._send_json(
                {
                    "error": "internal_error",
                    "detail": str(error),
                },
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )


def main() -> None:
    host = os.getenv("MPC_AGENT_HOST", "127.0.0.1")
    port = int(os.getenv("MPC_AGENT_PORT", "8080"))
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"MPC agent server listening on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()

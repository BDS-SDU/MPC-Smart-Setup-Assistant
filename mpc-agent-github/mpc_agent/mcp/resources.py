from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from mpc_agent.case_store import case_store_info, list_cases
from mpc_agent.integrations.external_api import list_external_systems
from mpc_agent.knowledge_base import list_sections
from mpc_agent.open_source_catalog import (
    catalog_summary,
    list_open_source_deployments,
    list_research_gaps,
)
from mpc_agent.policy import PROFILES
from mpc_agent.runtime_signals import get_last_runtime_signals, query_local_hardware


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _tail_text(file_path: Path, *, max_lines: int = 120) -> str:
    if not file_path.exists():
        return ""
    lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[-max_lines:])


def _resource_protocol_catalog() -> dict[str, Any]:
    data = []
    for protocol_id, profile in PROFILES.items():
        data.append(
            {
                "protocol_id": protocol_id,
                "title": profile.title,
                "circuit_domain": profile.circuit_domain,
                "security_support": profile.security_support,
                "assumptions": profile.assumptions,
                "preprocessed": profile.preprocessed,
                "scripts": profile.mpspdz_scripts,
            }
        )
    return {"protocols": data}


def _resource_protocol_references() -> dict[str, Any]:
    references: dict[str, list[str]] = {}
    for protocol_id, profile in PROFILES.items():
        references[protocol_id] = list(profile.references)
    return {"references": references}


def _resource_open_source_protocol_catalog() -> dict[str, Any]:
    return {
        "summary": catalog_summary(),
        "deployments": list_open_source_deployments(),
        "research_gaps": list_research_gaps(),
    }


def _resource_knowledge_sections() -> dict[str, Any]:
    return {"sections": list_sections()}


def _resource_case_store_status() -> dict[str, Any]:
    return case_store_info()


def _resource_case_store_latest() -> dict[str, Any]:
    return {"cases": list_cases(limit=20)}


def _resource_local_hardware() -> dict[str, Any]:
    return query_local_hardware()


def _resource_runtime_signals_latest() -> dict[str, Any]:
    return get_last_runtime_signals()


def _resource_external_systems() -> dict[str, Any]:
    return {"systems": list_external_systems()}


def _resource_mpspdz_status() -> dict[str, Any]:
    mpspdz_home = os.getenv("MPSPDZ_HOME", "").strip()
    path = Path(mpspdz_home).expanduser() if mpspdz_home else None

    exists = bool(path and path.exists())
    compile_exists = bool(path and (path / "compile.py").exists())
    scripts: list[str] = []
    runtimes: list[str] = []
    if path and path.exists():
        scripts_dir = path / "Scripts"
        if scripts_dir.exists():
            scripts = sorted(str(p.relative_to(path)) for p in scripts_dir.glob("*.*"))
        runtimes = sorted(str(p.name) for p in path.glob("*-party.x"))

    return {
        "mpspdz_home": str(path) if path else "",
        "exists": exists,
        "compile_py_exists": compile_exists,
        "scripts": scripts,
        "runtime_binaries": runtimes,
        "is_windows": os.name == "nt",
    }


def _resource_latest_logs() -> dict[str, Any]:
    stdout_path = PROJECT_ROOT / "server_stdout.log"
    stderr_path = PROJECT_ROOT / "server_stderr.log"
    return {
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "stdout_tail": _tail_text(stdout_path),
        "stderr_tail": _tail_text(stderr_path),
    }


RESOURCES: dict[str, dict[str, Any]] = {
    "protocol://catalog": {
        "description": "Protocol profiles and compatibility catalog.",
        "loader": _resource_protocol_catalog,
    },
    "protocol://references/pragmaticmpc": {
        "description": "Protocol reference snippets used by the policy engine.",
        "loader": _resource_protocol_references,
    },
    "protocol://catalog/open-source": {
        "description": "Curated open-source MPC implementation catalog with research-gap markers.",
        "loader": _resource_open_source_protocol_catalog,
    },
    "knowledge://pragmaticmpc/sections": {
        "description": "Structured MPC section notes distilled from pragmatic MPC references.",
        "loader": _resource_knowledge_sections,
    },
    "memory://cases/status": {
        "description": "Case store file location and record count.",
        "loader": _resource_case_store_status,
    },
    "memory://cases/latest": {
        "description": "Latest persisted decision/execution cases.",
        "loader": _resource_case_store_latest,
    },
    "runtime://hardware/local": {
        "description": "Current local hardware snapshot used for protocol trade-off hints.",
        "loader": _resource_local_hardware,
    },
    "runtime://signals/latest": {
        "description": "Latest collected runtime signals and inferred protocol bias.",
        "loader": _resource_runtime_signals_latest,
    },
    "external://systems": {
        "description": "Configured third-party API systems callable by the agent.",
        "loader": _resource_external_systems,
    },
    "env://mpspdz/status": {
        "description": "Current MP-SPDZ environment status and discovered scripts/binaries.",
        "loader": _resource_mpspdz_status,
    },
    "logs://latest": {
        "description": "Tail of latest server stdout/stderr logs.",
        "loader": _resource_latest_logs,
    },
}


def list_resources() -> list[dict[str, str]]:
    return [
        {"uri": uri, "description": str(spec["description"])}
        for uri, spec in RESOURCES.items()
    ]


def read_resource(uri: str) -> dict[str, Any]:
    spec = RESOURCES.get(uri)
    if spec is None:
        raise KeyError(f"Unknown resource: {uri}")
    loader = spec["loader"]
    return loader()

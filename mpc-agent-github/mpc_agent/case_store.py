from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = PROJECT_ROOT / ".mpc_agent_cases.jsonl"


def _db_path() -> Path:
    configured = os.getenv("MPC_AGENT_CASE_DB", "").strip()
    if configured:
        return Path(configured).expanduser()
    return DEFAULT_DB_PATH


def _safe_read_records() -> list[dict[str, Any]]:
    path = _db_path()
    if not path.exists():
        return []

    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            records.append(payload)
    return records


def _write_record(record: dict[str, Any]) -> None:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _requirement_vector(parsed: dict[str, Any]) -> dict[str, Any]:
    return {
        "parties": int(parsed.get("parties", 2)),
        "operation": str(parsed.get("operation", "")).strip().lower(),
        "party_count_mode": str(parsed.get("party_count_mode", "")).strip().lower(),
        "circuit_domain": str(parsed.get("circuit_domain", "")).strip().lower(),
        "math_structure": str(parsed.get("math_structure", "")).strip().lower(),
        "secret_sharing": str(parsed.get("secret_sharing", "")).strip().lower(),
        "security_model": str(parsed.get("security_model", "")).strip().lower(),
        "corruption_model": str(parsed.get("corruption_model", "")).strip().lower(),
        "corruption_timing": str(parsed.get("corruption_timing", "")).strip().lower(),
        "network_model": str(parsed.get("network_model", "")).strip().lower(),
        "corruption_threshold": str(parsed.get("corruption_threshold", "")).strip().lower(),
        "security_goal": str(parsed.get("security_goal", "")).strip().lower(),
        "latency_priority": str(parsed.get("latency_priority", "")).strip().lower(),
        "bandwidth_priority": str(parsed.get("bandwidth_priority", "")).strip().lower(),
    }


def _similarity_score(a: dict[str, Any], b: dict[str, Any]) -> int:
    score = 0
    if a["operation"] and a["operation"] == b["operation"]:
        score += 4
    if a["party_count_mode"] and a["party_count_mode"] == b["party_count_mode"]:
        score += 1
    if a["circuit_domain"] and a["circuit_domain"] == b["circuit_domain"]:
        score += 3
    if a["math_structure"] and a["math_structure"] == b["math_structure"]:
        score += 2
    if a["secret_sharing"] and a["secret_sharing"] == b["secret_sharing"]:
        score += 2
    if a["security_model"] and a["security_model"] == b["security_model"]:
        score += 3
    if a["corruption_model"] and a["corruption_model"] == b["corruption_model"]:
        score += 2
    if a["corruption_timing"] and a["corruption_timing"] == b["corruption_timing"]:
        score += 1
    if a["network_model"] and a["network_model"] == b["network_model"]:
        score += 1
    if a["corruption_threshold"] and a["corruption_threshold"] == b["corruption_threshold"]:
        score += 2
    if a["security_goal"] and a["security_goal"] == b["security_goal"]:
        score += 2
    if a["latency_priority"] and a["latency_priority"] == b["latency_priority"]:
        score += 1
    if a["bandwidth_priority"] and a["bandwidth_priority"] == b["bandwidth_priority"]:
        score += 1

    parties_gap = abs(int(a["parties"]) - int(b["parties"]))
    if parties_gap == 0:
        score += 3
    elif parties_gap == 1:
        score += 1

    return score


def append_case(record: dict[str, Any]) -> dict[str, Any]:
    case_id = str(record.get("case_id", "")).strip() or f"case_{uuid.uuid4().hex[:12]}"
    payload = dict(record)
    payload["case_id"] = case_id
    payload["timestamp"] = int(record.get("timestamp") or time.time())
    _write_record(payload)
    return payload


def list_cases(*, limit: int = 20) -> list[dict[str, Any]]:
    records = _safe_read_records()
    records.sort(key=lambda item: int(item.get("timestamp", 0)), reverse=True)
    if limit <= 0:
        return records
    return records[:limit]


def find_similar_cases(parsed_requirement: dict[str, Any], *, limit: int = 5) -> list[dict[str, Any]]:
    vector = _requirement_vector(parsed_requirement)
    records = _safe_read_records()
    ranked: list[dict[str, Any]] = []

    for item in records:
        parsed = item.get("parsed_requirement")
        if not isinstance(parsed, dict):
            continue
        score = _similarity_score(vector, _requirement_vector(parsed))
        if score <= 0:
            continue
        summary = {
            "case_id": item.get("case_id"),
            "timestamp": item.get("timestamp"),
            "score": score,
            "selected_protocol": item.get("selected_protocol"),
            "execution_status": item.get("execution_status"),
            "parsed_requirement": parsed,
            "feedback": item.get("feedback", {}),
        }
        ranked.append(summary)

    ranked.sort(key=lambda row: (int(row["score"]), int(row.get("timestamp") or 0)), reverse=True)
    return ranked[:limit]


def summarize_protocol_bias(similar_cases: list[dict[str, Any]]) -> dict[str, int]:
    bias: dict[str, int] = {}
    for item in similar_cases:
        protocol_id = str(item.get("selected_protocol", "")).strip()
        if not protocol_id:
            continue
        status = str(item.get("execution_status", "")).strip().lower()
        base = 2
        if status in {"success", "compile_only_success"}:
            base += 2
        elif status in {"run_failed", "compile_failed", "error"}:
            base -= 1

        sim_score = int(item.get("score") or 0)
        bonus = max(0, base + min(3, sim_score // 4))
        if bonus <= 0:
            continue
        bias[protocol_id] = bias.get(protocol_id, 0) + bonus
    return bias


def record_feedback(case_id: str, feedback: dict[str, Any]) -> dict[str, Any]:
    normalized_case_id = str(case_id).strip()
    if not normalized_case_id:
        raise ValueError("`case_id` is required.")

    records = _safe_read_records()
    updated: dict[str, Any] | None = None
    for item in records:
        if str(item.get("case_id", "")).strip() == normalized_case_id:
            existing = item.get("feedback")
            merged = dict(existing) if isinstance(existing, dict) else {}
            merged.update(feedback)
            item["feedback"] = merged
            item["feedback_updated_at"] = int(time.time())
            updated = item
            break

    if updated is None:
        raise KeyError(f"Unknown case_id: {case_id}")

    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(json.dumps(item, ensure_ascii=False) for item in records)
    if content:
        content += "\n"
    path.write_text(content, encoding="utf-8")
    return updated


def case_store_info() -> dict[str, Any]:
    path = _db_path()
    return {
        "path": str(path),
        "exists": path.exists(),
        "record_count": len(_safe_read_records()),
    }

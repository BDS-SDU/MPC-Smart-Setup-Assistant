from __future__ import annotations

import ctypes
import os
import platform
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from mpc_agent.integrations.external_api import call_external_api


_LAST_RUNTIME_SIGNALS: dict[str, Any] = {
    "timestamp": None,
    "network": {"source": "none"},
    "hardware": {"source": "none"},
    "protocol_bias": {},
    "bias_reasons": [],
}


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _pick_float(item: dict[str, Any], keys: list[str]) -> float | None:
    for key in keys:
        value = _safe_float(item.get(key))
        if value is not None:
            return value
    return None


def _pick_int(item: dict[str, Any], keys: list[str]) -> int | None:
    for key in keys:
        value = _safe_int(item.get(key))
        if value is not None:
            return value
    return None


def _run_command(command: list[str], *, timeout: int = 10) -> tuple[int, str, str]:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return result.returncode, result.stdout or "", result.stderr or ""
    except (subprocess.SubprocessError, OSError):
        return -1, "", ""


def _parse_ping_metrics(text: str) -> tuple[float | None, float | None]:
    normalized = text.replace("\r", "\n")

    avg_match = re.search(r"(?:average|平均)[^0-9]*(\d+(?:\.\d+)?)\s*ms", normalized, flags=re.IGNORECASE)
    if avg_match:
        avg_rtt = float(avg_match.group(1))
    else:
        linux_match = re.search(r"=\s*([0-9.]+)/([0-9.]+)/([0-9.]+)/[0-9.]+\s*ms", normalized)
        if linux_match:
            avg_rtt = float(linux_match.group(2))
        else:
            samples = [float(item) for item in re.findall(r"time[=<]\s*([0-9.]+)\s*ms", normalized, flags=re.IGNORECASE)]
            avg_rtt = round(sum(samples) / len(samples), 3) if samples else None

    loss_match = re.search(r"\((\d+)%\s*(?:loss|丢失)?\)", normalized, flags=re.IGNORECASE)
    if loss_match:
        packet_loss = float(loss_match.group(1))
    else:
        packet_loss = None

    return avg_rtt, packet_loss


def _normalize_hosts(hosts: list[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in hosts:
        if isinstance(item, str):
            host = item.strip()
            if not host:
                continue
            normalized.append({"host": host, "name": host})
            continue

        if isinstance(item, dict):
            host = str(item.get("host") or item.get("ip") or "").strip()
            if not host:
                continue
            row = dict(item)
            row.setdefault("host", host)
            row.setdefault("name", host)
            normalized.append(row)
    return normalized


def probe_network(hosts: list[Any], *, count: int = 3, timeout_ms: int = 1000) -> dict[str, Any]:
    entries = _normalize_hosts(hosts)
    if not entries:
        return {
            "source": "none",
            "reason": "No valid hosts provided.",
            "parties": [],
            "summary": {},
        }

    ping_available = bool(shutil.which("ping"))
    parties: list[dict[str, Any]] = []
    avg_samples: list[float] = []
    bandwidth_samples: list[float] = []

    for item in entries:
        host = str(item["host"])
        name = str(item.get("name", host))

        avg_rtt_ms: float | None = None
        packet_loss_pct: float | None = None
        reachable = False

        if ping_available:
            if os.name == "nt":
                command = ["ping", "-n", str(max(1, count)), "-w", str(max(1, timeout_ms)), host]
                timeout = max(5, count * 2)
            else:
                command = ["ping", "-c", str(max(1, count)), "-W", str(max(1, timeout_ms // 1000)), host]
                timeout = max(5, count * 2)

            rc, stdout, stderr = _run_command(command, timeout=timeout)
            avg_rtt_ms, packet_loss_pct = _parse_ping_metrics("\n".join([stdout, stderr]))
            reachable = rc == 0 or avg_rtt_ms is not None

        bandwidth_mbps = _safe_float(item.get("bandwidth_mbps"))
        if bandwidth_mbps is not None:
            bandwidth_samples.append(bandwidth_mbps)
        if avg_rtt_ms is not None:
            avg_samples.append(avg_rtt_ms)

        parties.append(
            {
                "name": name,
                "host": host,
                "reachable": reachable,
                "avg_rtt_ms": avg_rtt_ms,
                "packet_loss_pct": packet_loss_pct,
                "bandwidth_mbps": bandwidth_mbps,
            }
        )

    estimated_bandwidth = round(sum(bandwidth_samples) / len(bandwidth_samples), 3) if bandwidth_samples else None
    avg_rtt = round(sum(avg_samples) / len(avg_samples), 3) if avg_samples else None

    summary = {
        "party_count": len(parties),
        "reachable_count": sum(1 for p in parties if p["reachable"]),
        "avg_rtt_ms": avg_rtt,
        "max_rtt_ms": max(avg_samples) if avg_samples else None,
        "min_rtt_ms": min(avg_samples) if avg_samples else None,
        "estimated_bandwidth_mbps": estimated_bandwidth,
    }

    return {
        "source": "ping" if ping_available else "provided_only",
        "count": max(1, count),
        "timeout_ms": max(1, timeout_ms),
        "parties": parties,
        "summary": summary,
    }


def _json_path_get(payload: Any, path: str | None) -> Any:
    if not path:
        return payload
    current: Any = payload
    for part in path.split("."):
        token = part.strip()
        if not token:
            continue
        if isinstance(current, dict):
            if token not in current:
                return None
            current = current[token]
            continue
        if isinstance(current, list):
            index = _safe_int(token)
            if index is None or index < 0 or index >= len(current):
                return None
            current = current[index]
            continue
        return None
    return current


def _normalize_external_network_payload(raw: Any, *, source: str) -> dict[str, Any]:
    parties_raw: list[Any] = []
    summary_raw: dict[str, Any] = {}

    if isinstance(raw, list):
        parties_raw = raw
    elif isinstance(raw, dict):
        for key in ("parties", "hosts", "nodes", "results", "items"):
            value = raw.get(key)
            if isinstance(value, list):
                parties_raw = value
                break
        summary_value = raw.get("summary")
        summary_raw = summary_value if isinstance(summary_value, dict) else {}
        if not parties_raw and any(key in raw for key in ("avg_rtt_ms", "estimated_bandwidth_mbps")):
            summary_raw = raw

    parties: list[dict[str, Any]] = []
    avg_samples: list[float] = []
    bandwidth_samples: list[float] = []
    for idx, item in enumerate(parties_raw):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("party") or item.get("host") or f"P{idx}")
        host = str(item.get("host") or item.get("ip") or name)
        avg_rtt_ms = _pick_float(item, ["avg_rtt_ms", "rtt_ms", "latency_ms", "ping_ms"])
        packet_loss_pct = _pick_float(item, ["packet_loss_pct", "loss_pct", "packet_loss"])
        bandwidth_mbps = _pick_float(item, ["bandwidth_mbps", "throughput_mbps", "bw_mbps"])
        reachable_raw = item.get("reachable")
        if isinstance(reachable_raw, bool):
            reachable = reachable_raw
        else:
            reachable = avg_rtt_ms is not None

        if avg_rtt_ms is not None:
            avg_samples.append(avg_rtt_ms)
        if bandwidth_mbps is not None:
            bandwidth_samples.append(bandwidth_mbps)

        parties.append(
            {
                "name": name,
                "host": host,
                "reachable": reachable,
                "avg_rtt_ms": avg_rtt_ms,
                "packet_loss_pct": packet_loss_pct,
                "bandwidth_mbps": bandwidth_mbps,
            }
        )

    summary = {
        "party_count": len(parties),
        "reachable_count": sum(1 for row in parties if row["reachable"]),
        "avg_rtt_ms": _safe_float(summary_raw.get("avg_rtt_ms")) or (
            round(sum(avg_samples) / len(avg_samples), 3) if avg_samples else None
        ),
        "max_rtt_ms": _safe_float(summary_raw.get("max_rtt_ms")) or (max(avg_samples) if avg_samples else None),
        "min_rtt_ms": _safe_float(summary_raw.get("min_rtt_ms")) or (min(avg_samples) if avg_samples else None),
        "estimated_bandwidth_mbps": _safe_float(summary_raw.get("estimated_bandwidth_mbps")) or (
            round(sum(bandwidth_samples) / len(bandwidth_samples), 3) if bandwidth_samples else None
        ),
    }

    return {
        "source": source,
        "parties": parties,
        "summary": summary,
    }


def _normalize_external_hardware_payload(raw: Any, *, source: str) -> dict[str, Any]:
    parties_raw: list[Any] = []
    summary_raw: dict[str, Any] = {}

    if isinstance(raw, list):
        parties_raw = raw
    elif isinstance(raw, dict):
        for key in ("parties", "hosts", "nodes", "results", "items"):
            value = raw.get(key)
            if isinstance(value, list):
                parties_raw = value
                break
        summary_value = raw.get("summary")
        summary_raw = summary_value if isinstance(summary_value, dict) else {}

    rows: list[dict[str, Any]] = []
    scores: list[float] = []
    for idx, item in enumerate(parties_raw):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("party") or item.get("host") or f"P{idx}")
        cpu_cores = _pick_int(item, ["cpu_cores", "logical_cores", "vcpus"])
        memory_gb = _pick_float(item, ["memory_gb", "ram_gb", "memory_total_gb"])
        compute_score = _pick_float(item, ["compute_score"])
        if compute_score is None:
            compute_score = round(float(cpu_cores or 0) + float(memory_gb or 0) / 4.0, 3)
        scores.append(compute_score)
        rows.append(
            {
                "name": name,
                "cpu_cores": cpu_cores,
                "memory_gb": memory_gb,
                "compute_score": compute_score,
            }
        )

    summary = {
        "party_count": _pick_int(summary_raw, ["party_count"]) or len(rows),
        "avg_compute_score": _pick_float(summary_raw, ["avg_compute_score"]) or (
            round(sum(scores) / len(scores), 3) if scores else None
        ),
        "min_compute_score": _pick_float(summary_raw, ["min_compute_score"]) or (min(scores) if scores else None),
        "max_compute_score": _pick_float(summary_raw, ["max_compute_score"]) or (max(scores) if scores else None),
        "heterogeneity_ratio": _pick_float(summary_raw, ["heterogeneity_ratio"]) or (
            round((max(scores) / min(scores)), 3) if scores and min(scores) > 0 else None
        ),
    }

    return {
        "source": source,
        "parties": rows,
        "summary": summary,
    }


def _call_external_signal_api(spec: dict[str, Any]) -> dict[str, Any]:
    system_name = str(spec.get("system_name", "")).strip()
    if not system_name:
        raise ValueError("External signal spec requires `system_name`.")

    method = str(spec.get("method", "GET")).strip().upper()
    path = str(spec.get("path", "")).strip()
    query = spec.get("query")
    headers = spec.get("headers")
    body = spec.get("body")
    timeout_raw = spec.get("timeout_seconds")
    timeout_seconds = int(timeout_raw) if isinstance(timeout_raw, int) else None
    if query is not None and not isinstance(query, dict):
        raise ValueError("External signal spec `query` must be a JSON object.")
    if headers is not None and not isinstance(headers, dict):
        raise ValueError("External signal spec `headers` must be a JSON object.")

    result = call_external_api(
        system_name=system_name,
        method=method,
        path=path,
        query=query if isinstance(query, dict) else None,
        headers=headers if isinstance(headers, dict) else None,
        body=body,
        timeout_seconds=timeout_seconds,
    )
    if not result.get("ok"):
        raise RuntimeError(
            f"External API call failed for `{system_name}`: status={result.get('status')} "
            f"reason={result.get('reason', '')}"
        )
    return result


def _collect_external_network(payload: dict[str, Any]) -> dict[str, Any] | None:
    spec = payload.get("external_network_probe")
    if not isinstance(spec, dict):
        return None
    result = _call_external_signal_api(spec)
    data = _json_path_get(result.get("json"), str(spec.get("json_path", "")).strip() or None)
    if data is None:
        raise ValueError("External network probe response is missing JSON payload.")
    return _normalize_external_network_payload(
        data,
        source=f"external_api:{spec.get('system_name', '')}",
    )


def _collect_external_hardware(payload: dict[str, Any]) -> dict[str, Any] | None:
    spec = payload.get("external_hardware_query")
    if not isinstance(spec, dict):
        return None
    result = _call_external_signal_api(spec)
    data = _json_path_get(result.get("json"), str(spec.get("json_path", "")).strip() or None)
    if data is None:
        raise ValueError("External hardware query response is missing JSON payload.")
    return _normalize_external_hardware_payload(
        data,
        source=f"external_api:{spec.get('system_name', '')}",
    )


def _memory_total_gb() -> float | None:
    if os.name == "nt":
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MEMORYSTATUSEX()
        status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return round(status.ullTotalPhys / (1024 ** 3), 3)
        return None

    meminfo = Path("/proc/meminfo")
    if meminfo.exists():
        content = meminfo.read_text(encoding="utf-8", errors="replace")
        match = re.search(r"MemTotal:\s*(\d+)\s*kB", content)
        if match:
            kb = int(match.group(1))
            return round(kb / (1024 ** 2), 3)
    return None


def _cpu_freq_mhz() -> float | None:
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.exists():
        content = cpuinfo.read_text(encoding="utf-8", errors="replace")
        match = re.search(r"cpu MHz\s*:\s*([0-9.]+)", content)
        if match:
            return round(float(match.group(1)), 3)

    if os.name == "nt":
        rc, stdout, _ = _run_command(["wmic", "cpu", "get", "MaxClockSpeed"], timeout=5)
        if rc == 0:
            numbers = [int(item) for item in re.findall(r"\b(\d{3,5})\b", stdout)]
            if numbers:
                return float(numbers[0])
    return None


def _gpu_summary() -> dict[str, Any]:
    nvidia_smi = shutil.which("nvidia-smi")
    if not nvidia_smi:
        return {"available": False, "count": 0, "devices": []}

    command = [nvidia_smi, "--query-gpu=name,memory.total", "--format=csv,noheader"]
    rc, stdout, _ = _run_command(command, timeout=5)
    if rc != 0:
        return {"available": False, "count": 0, "devices": []}

    devices: list[dict[str, Any]] = []
    for line in stdout.splitlines():
        text = line.strip()
        if not text:
            continue
        parts = [part.strip() for part in text.split(",")]
        name = parts[0] if parts else "unknown"
        memory_mb = None
        if len(parts) > 1:
            match = re.search(r"([0-9.]+)", parts[1])
            if match:
                memory_mb = float(match.group(1))
        devices.append({"name": name, "memory_mb": memory_mb})

    return {
        "available": bool(devices),
        "count": len(devices),
        "devices": devices,
    }


def query_local_hardware() -> dict[str, Any]:
    logical_cores = os.cpu_count()
    mem_gb = _memory_total_gb()
    return {
        "source": "local",
        "hostname": platform.node(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python_version": platform.python_version(),
        "cpu": {
            "logical_cores": logical_cores,
            "frequency_mhz": _cpu_freq_mhz(),
        },
        "memory": {
            "total_gb": mem_gb,
        },
        "gpu": _gpu_summary(),
    }


def summarize_party_hardware(parties: list[Any], *, use_local_when_empty: bool = True) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []

    for item in parties:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("party") or f"P{len(rows)}")
        cpu_cores = _safe_int(item.get("cpu_cores") or item.get("logical_cores"))
        memory_gb = _safe_float(item.get("memory_gb") or item.get("ram_gb"))
        rows.append(
            {
                "name": name,
                "cpu_cores": cpu_cores,
                "memory_gb": memory_gb,
            }
        )

    if not rows and use_local_when_empty:
        local = query_local_hardware()
        rows.append(
            {
                "name": local.get("hostname") or "local",
                "cpu_cores": _safe_int(local.get("cpu", {}).get("logical_cores")),
                "memory_gb": _safe_float(local.get("memory", {}).get("total_gb")),
            }
        )

    scores: list[float] = []
    for row in rows:
        cores = float(row["cpu_cores"] or 0)
        memory = float(row["memory_gb"] or 0)
        score = round(cores + (memory / 4.0), 3)
        row["compute_score"] = score
        scores.append(score)

    avg_score = round(sum(scores) / len(scores), 3) if scores else None
    min_score = min(scores) if scores else None
    max_score = max(scores) if scores else None
    heterogeneity = round((max_score / min_score), 3) if scores and min_score and min_score > 0 else None

    return {
        "source": "provided" if parties else "local",
        "parties": rows,
        "summary": {
            "party_count": len(rows),
            "avg_compute_score": avg_score,
            "min_compute_score": min_score,
            "max_compute_score": max_score,
            "heterogeneity_ratio": heterogeneity,
        },
    }


def _apply_bias(bias: dict[str, int], key: str, value: int) -> None:
    bias[key] = bias.get(key, 0) + value


def infer_protocol_bias(
    parsed_requirement: dict[str, Any],
    network: dict[str, Any],
    hardware: dict[str, Any],
) -> tuple[dict[str, int], list[str]]:
    bias: dict[str, int] = {}
    reasons: list[str] = []

    operation = str(parsed_requirement.get("operation", "")).strip().lower()
    domain = str(parsed_requirement.get("circuit_domain", "")).strip().lower()

    network_summary = network.get("summary") if isinstance(network, dict) else {}
    if not isinstance(network_summary, dict):
        network_summary = {}

    avg_rtt = _safe_float(network_summary.get("avg_rtt_ms"))
    bandwidth = _safe_float(network_summary.get("estimated_bandwidth_mbps"))

    if avg_rtt is not None:
        if avg_rtt >= 60:
            _apply_bias(bias, "yao", 6)
            _apply_bias(bias, "bmr", 4)
            _apply_bias(bias, "gmw", -6)
            reasons.append("High measured RTT favors constant-round protocols over GMW.")
        elif avg_rtt >= 25:
            _apply_bias(bias, "yao", 3)
            _apply_bias(bias, "bmr", 2)
            _apply_bias(bias, "gmw", -2)
            reasons.append("Moderate RTT gives slight advantage to constant-round boolean protocols.")
        elif avg_rtt <= 8:
            _apply_bias(bias, "gmw", 2)
            reasons.append("Low RTT makes round-sensitive protocols like GMW more practical.")

    if bandwidth is not None and bandwidth < 40:
        _apply_bias(bias, "mascot", 2)
        _apply_bias(bias, "semi2k", 2)
        _apply_bias(bias, "gmw", -1)
        reasons.append("Low measured bandwidth favors preprocessing-heavy arithmetic protocols.")

    hw_summary = hardware.get("summary") if isinstance(hardware, dict) else {}
    if not isinstance(hw_summary, dict):
        hw_summary = {}

    min_compute = _safe_float(hw_summary.get("min_compute_score"))
    avg_compute = _safe_float(hw_summary.get("avg_compute_score"))
    heterogeneity = _safe_float(hw_summary.get("heterogeneity_ratio"))

    if min_compute is not None and min_compute <= 4:
        _apply_bias(bias, "bmr", -3)
        if operation == "comparison" or domain in {"boolean", "mixed"}:
            _apply_bias(bias, "gmw", 2)
        if operation in {"aggregation", "ml"} or domain in {"arithmetic", "mixed"}:
            _apply_bias(bias, "semi2k", 1)
        reasons.append("Weakest party compute is limited; avoid compute-heavy garbling when possible.")

    if heterogeneity is not None and heterogeneity >= 2.5:
        _apply_bias(bias, "bmr", -2)
        reasons.append("Large cross-party compute heterogeneity penalizes symmetric heavy protocols.")

    if avg_compute is not None and avg_compute >= 12:
        if operation in {"aggregation", "ml"} or domain in {"arithmetic", "mixed"}:
            _apply_bias(bias, "mascot", 1)
        if operation == "comparison" or domain in {"boolean", "mixed"}:
            _apply_bias(bias, "yao", 1)
        reasons.append("Strong average compute allows slightly more compute-intensive secure variants.")

    return bias, reasons


def collect_runtime_signals(payload: dict[str, Any], parsed_requirement: dict[str, Any]) -> dict[str, Any]:
    hosts_raw = payload.get("party_hosts")
    hosts = hosts_raw if isinstance(hosts_raw, list) else []

    network_metrics = payload.get("network_metrics")
    network_errors: list[str] = []
    if isinstance(network_metrics, dict):
        network = dict(network_metrics)
        network.setdefault("source", "provided")
    else:
        network = None
        try:
            network = _collect_external_network(payload)
        except Exception as error:  # noqa: BLE001
            network_errors.append(str(error))

        if network is None and (bool(payload.get("auto_probe_network", False)) or bool(hosts)):
            count = _safe_int(payload.get("network_probe_count")) or 3
            timeout_ms = _safe_int(payload.get("network_timeout_ms")) or 1000
            network = probe_network(hosts, count=count, timeout_ms=timeout_ms)

        if network is None:
            network = {"source": "none", "summary": {}}

    hardware_metrics = payload.get("hardware_metrics")
    hardware_errors: list[str] = []
    if isinstance(hardware_metrics, dict):
        hardware = dict(hardware_metrics)
        hardware.setdefault("source", "provided")
    else:
        hardware = None
        try:
            hardware = _collect_external_hardware(payload)
        except Exception as error:  # noqa: BLE001
            hardware_errors.append(str(error))

        if hardware is None:
            parties_hw_raw = payload.get("hardware_parties")
            parties_hw = parties_hw_raw if isinstance(parties_hw_raw, list) else []
            auto_query = bool(payload.get("auto_query_hardware", True))
            if parties_hw or auto_query:
                hardware = summarize_party_hardware(parties_hw, use_local_when_empty=auto_query)
            else:
                hardware = {"source": "none", "summary": {}, "parties": []}

    protocol_bias, bias_reasons = infer_protocol_bias(parsed_requirement, network, hardware)
    if network_errors:
        bias_reasons.append("External network probe failed; used fallback signals.")
    if hardware_errors:
        bias_reasons.append("External hardware query failed; used fallback signals.")

    result = {
        "timestamp": int(time.time()),
        "network": network,
        "hardware": hardware,
        "network_errors": network_errors,
        "hardware_errors": hardware_errors,
        "protocol_bias": protocol_bias,
        "bias_reasons": bias_reasons,
    }

    global _LAST_RUNTIME_SIGNALS
    _LAST_RUNTIME_SIGNALS = result
    return result


def get_last_runtime_signals() -> dict[str, Any]:
    return dict(_LAST_RUNTIME_SIGNALS)

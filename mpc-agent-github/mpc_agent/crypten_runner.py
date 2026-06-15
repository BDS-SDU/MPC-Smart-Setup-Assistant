from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

from .models import FinalConfiguration, ParsedRequirement


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CRYPTEN_RUNTIME_CONFIG_PATH = PROJECT_ROOT / ".crypten_runtime.json"


def _truncate(text: str | None, limit: int = 4000) -> str:
    if text is None:
        return ""
    if len(text) <= limit:
        return text
    return f"{text[:limit]}\n...<truncated {len(text) - limit} chars>"


def _decode_output(raw: bytes | str | None) -> str:
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw
    for encoding in ("utf-8", "gb18030", "gbk"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _run_command(command: list[str], cwd: Path, timeout: int) -> dict[str, Any]:
    import subprocess

    start = time.time()
    try:
        process = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=False,
            timeout=timeout,
            check=False,
        )
        end = time.time()
        return {
            "command": command,
            "return_code": process.returncode,
            "duration_seconds": round(end - start, 3),
            "stdout": _truncate(_decode_output(process.stdout)),
            "stderr": _truncate(_decode_output(process.stderr)),
        }
    except subprocess.TimeoutExpired as error:
        end = time.time()
        return {
            "command": command,
            "return_code": -1,
            "duration_seconds": round(end - start, 3),
            "stdout": _truncate(_decode_output(error.stdout)),
            "stderr": _truncate(
                _decode_output(error.stderr) or f"Command timed out after {timeout} seconds."
            ),
        }
    except OSError as error:
        end = time.time()
        return {
            "command": command,
            "return_code": -1,
            "duration_seconds": round(end - start, 3),
            "stdout": "",
            "stderr": _truncate(f"Failed to start process: {error}"),
        }


def _load_runtime_defaults() -> dict[str, Any]:
    try:
        payload = json.loads(CRYPTEN_RUNTIME_CONFIG_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _unique_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    result: list[Path] = []
    for path in paths:
        raw = str(path).strip()
        if not raw or raw in seen:
            continue
        seen.add(raw)
        result.append(path)
    return result


def _candidate_user_roots() -> list[Path]:
    candidates: list[Path] = []

    for raw in (os.getenv("USERPROFILE", "").strip(), os.getenv("HOME", "").strip()):
        if raw:
            candidates.append(Path(raw).expanduser())

    try:
        candidates.append(Path.home())
    except RuntimeError:
        pass

    for root in (Path.cwd().resolve(), PROJECT_ROOT.resolve()):
        candidates.append(root)
        candidates.extend(root.parents)

    return _unique_paths(candidates)


def _python_paths_from_root(root: Path) -> list[Path]:
    return [
        root / "Scripts" / "python.exe",
        root / "bin" / "python",
        root / ".venv" / "Scripts" / "python.exe",
        root / ".venv" / "bin" / "python",
        root / "venv" / "Scripts" / "python.exe",
        root / "venv" / "bin" / "python",
    ]


def _crypten_home_hints_from_base(base: Path) -> list[Path]:
    return [
        base / "CrypTen",
        base / "crypten",
    ]


def _crypten_python_candidates() -> list[Path]:
    candidates: list[Path] = []
    for base in _candidate_user_roots():
        candidates.extend(_python_paths_from_root(base))

        venvs_root = base / "venvs"
        if venvs_root.exists():
            for pattern in ("crypten_env", "*crypten*"):
                for match in sorted(venvs_root.glob(pattern), key=lambda item: str(item), reverse=True):
                    candidates.extend(_python_paths_from_root(match))

        conda_root = base / ".conda" / "envs"
        if conda_root.exists():
            for match in sorted(conda_root.glob("*crypten*"), key=lambda item: str(item), reverse=True):
                candidates.extend(_python_paths_from_root(match))

    return _unique_paths(candidates)


def _driver_path() -> Path:
    return Path(__file__).resolve().parent / "crypten_runtime_driver.py"


def _parse_json_payload(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if not text:
        return {}
    for candidate in reversed(text.splitlines()):
        line = candidate.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return {}


def resolve_crypten_python(payload: dict[str, Any]) -> tuple[Path | None, str]:
    explicit = str(payload.get("crypten_python", "")).strip()
    if explicit:
        return Path(explicit).expanduser(), "explicit"

    env_python = os.getenv("CRYPTEN_PYTHON", "").strip()
    if env_python:
        return Path(env_python).expanduser(), "env"

    defaults = _load_runtime_defaults()
    config_python = str(defaults.get("crypten_python") or defaults.get("python") or "").strip()
    if config_python:
        return Path(config_python).expanduser(), "config"

    for candidate in _crypten_python_candidates():
        if candidate.exists():
            return candidate, "auto_detected"

    return None, "unresolved"


def resolve_crypten_home(payload: dict[str, Any]) -> tuple[Path | None, str]:
    explicit = str(payload.get("crypten_home", "")).strip()
    if explicit:
        return Path(explicit).expanduser(), "explicit"

    env_home = os.getenv("CRYPTEN_HOME", "").strip()
    if env_home:
        return Path(env_home).expanduser(), "env"

    defaults = _load_runtime_defaults()
    config_home = str(defaults.get("crypten_home") or defaults.get("home") or "").strip()
    if config_home:
        return Path(config_home).expanduser(), "config"

    for base in _candidate_user_roots():
        for candidate in _crypten_home_hints_from_base(base):
            if (candidate / "crypten").exists() and (candidate / "setup.py").exists():
                return candidate, "auto_detected"

    return None, "unresolved"


def inspect_crypten_runtime_support(
    payload: dict[str, Any],
    config: FinalConfiguration | None = None,
) -> dict[str, Any]:
    crypten_python, python_source = resolve_crypten_python(payload)
    crypten_home, home_source = resolve_crypten_home(payload)
    implementation_id = config.implementation_id if config else ""

    if crypten_home is not None and not crypten_home.exists():
        return {
            "launchable": False,
            "backend": "crypten",
            "implementation_id": implementation_id,
            "reason": f"CrypTen home not found: {crypten_home}",
            "crypten_home": str(crypten_home),
            "crypten_home_source": home_source,
        }

    if crypten_python is None:
        return {
            "launchable": False,
            "backend": "crypten",
            "implementation_id": implementation_id,
            "reason": "Unable to resolve CrypTen python. Set `crypten_python` or `CRYPTEN_PYTHON`.",
            "crypten_home": str(crypten_home) if crypten_home is not None else "",
            "crypten_home_source": home_source,
            "crypten_python_source": python_source,
        }

    if not crypten_python.exists():
        return {
            "launchable": False,
            "backend": "crypten",
            "implementation_id": implementation_id,
            "reason": f"CrypTen python not found: {crypten_python}",
            "crypten_home": str(crypten_home) if crypten_home is not None else "",
            "crypten_home_source": home_source,
            "crypten_python": str(crypten_python),
            "crypten_python_source": python_source,
        }

    timeout_seconds = int(payload.get("timeout_seconds", 300))
    probe = _run_command(
        [
            str(crypten_python),
            str(_driver_path()),
            "--probe",
            "--crypten-home",
            str(crypten_home) if crypten_home is not None else "",
        ],
        PROJECT_ROOT,
        timeout_seconds,
    )
    probe_payload = _parse_json_payload(str(probe.get("stdout", "")))
    if probe["return_code"] != 0 or not bool(probe_payload.get("ok")):
        return {
            "launchable": False,
            "backend": "crypten",
            "implementation_id": implementation_id,
            "crypten_home": str(crypten_home) if crypten_home is not None else "",
            "crypten_home_source": home_source,
            "crypten_python": str(crypten_python),
            "crypten_python_source": python_source,
            "probe": probe,
            "reason": str(probe_payload.get("reason", "")).strip()
            or str(probe.get("stderr", "")).strip()
            or str(probe.get("stdout", "")).strip()
            or "CrypTen runtime probe failed.",
        }

    return {
        "launchable": True,
        "backend": "crypten",
        "implementation_id": implementation_id,
        "crypten_home": str(crypten_home) if crypten_home is not None else "",
        "crypten_home_source": home_source,
        "crypten_python": str(crypten_python),
        "crypten_python_source": python_source,
        "probe": probe,
        "reason": "CrypTen runtime probe succeeded.",
        "python_version": probe_payload.get("python_version", ""),
        "crypten_version": probe_payload.get("crypten_version", ""),
        "torch_version": probe_payload.get("torch_version", ""),
    }


def _default_inputs(req: ParsedRequirement) -> list[Any]:
    if req.operation == "comparison":
        return [7, 3]
    return [index + 1 for index in range(max(2, req.parties))]


def _missing_crypten_match_reason(req: ParsedRequirement) -> str:
    guidance = [
        "No CrypTen implementation matched the current requirement.",
        "CrypTen is currently routed as a semi-honest tensor backend for two or more parties,",
        "best suited for arithmetic or mixed workloads such as aggregation and privacy-preserving ML inference.",
    ]
    if req.security_model != "semi_honest":
        guidance.append("Try `security_model=semi_honest` for the CrypTen path.")
    if req.corruption_model != "dishonest_majority":
        guidance.append("CrypTen currently expects `corruption_model=dishonest_majority` in this catalog.")
    return " ".join(guidance)


class CrypTenRunner:
    def run(
        self,
        payload: dict[str, Any],
        req: ParsedRequirement,
        config: FinalConfiguration,
    ) -> dict[str, Any]:
        if not payload.get("execute", False):
            return {
                "executed": False,
                "status": "skipped",
                "backend": "crypten",
                "reason": "execute=false, only generated configuration.",
            }

        if str(config.runner_backend or payload.get("runtime_backend", "")).strip().lower() != "crypten":
            return {
                "executed": False,
                "status": "error",
                "backend": "crypten",
                "reason": "CrypTen runner was selected without a matching `runner_backend=crypten` configuration.",
            }

        if not config.implementation_id:
            return {
                "executed": False,
                "status": "error",
                "backend": "crypten",
                "reason": _missing_crypten_match_reason(req),
            }

        support = inspect_crypten_runtime_support(payload, config)
        if not support.get("launchable"):
            return {
                "executed": False,
                "status": "error",
                "backend": "crypten",
                "implementation_id": config.implementation_id,
                "execution_preflight": support,
                "reason": str(support.get("reason", "")).strip() or "CrypTen preflight failed.",
            }

        timeout_seconds = int(payload.get("timeout_seconds", 300))
        spec = {
            "crypten_home": str(support.get("crypten_home", "")).strip(),
            "implementation_id": config.implementation_id,
            "parties": int(config.parties),
            "operation": req.operation,
            "compile_only": bool(payload.get("compile_only", False)),
            "inputs": payload.get("crypten_inputs")
            if isinstance(payload.get("crypten_inputs"), list)
            else _default_inputs(req),
        }

        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".json",
            delete=False,
        ) as handle:
            json.dump(spec, handle, ensure_ascii=False)
            spec_path = Path(handle.name)

        try:
            run_cmd = [str(support["crypten_python"]), str(_driver_path()), "--spec", str(spec_path)]
            run_result = _run_command(run_cmd, PROJECT_ROOT, timeout_seconds)
        finally:
            try:
                spec_path.unlink(missing_ok=True)
            except OSError:
                pass

        payload_result = _parse_json_payload(str(run_result.get("stdout", "")))
        if run_result["return_code"] != 0:
            return {
                "executed": True,
                "status": "run_failed",
                "backend": "crypten",
                "implementation_id": config.implementation_id,
                "framework": config.framework,
                "execution_preflight": support,
                "run": run_result,
                "reason": str(payload_result.get("reason", "")).strip()
                or str(run_result.get("stderr", "")).strip()
                or str(run_result.get("stdout", "")).strip()
                or "CrypTen execution failed.",
            }

        status = "compile_only_success" if bool(payload.get("compile_only", False)) else "success"
        return {
            "executed": True,
            "status": status,
            "backend": "crypten",
            "implementation_id": config.implementation_id,
            "framework": config.framework,
            "execution_preflight": support,
            "run": run_result,
            "result": payload_result,
            "reason": str(payload_result.get("reason", "")).strip(),
        }

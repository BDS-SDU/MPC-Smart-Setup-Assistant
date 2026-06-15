from __future__ import annotations

import json
import os
import shlex
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from .models import FinalConfiguration, ParsedRequirement


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SPU_RUNTIME_CONFIG_PATH = PROJECT_ROOT / ".spu_runtime.json"


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


def _python_executable() -> str:
    return sys.executable or "python"


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
        payload = json.loads(SPU_RUNTIME_CONFIG_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _first_nonempty(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _looks_like_windows_path(value: str) -> bool:
    return len(value) >= 2 and value[1] == ":"


def _looks_like_posix_path(value: str) -> bool:
    return value.startswith("/")


def _windows_to_wsl_path(value: str | Path) -> str:
    raw = str(value).strip()
    if not raw:
        return ""
    if _looks_like_posix_path(raw):
        return raw
    if not _looks_like_windows_path(raw):
        return raw.replace("\\", "/")
    drive = raw[0].lower()
    suffix = raw[2:].replace("\\", "/")
    return f"/mnt/{drive}{suffix}"


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

    homedrive = os.getenv("HOMEDRIVE", "").strip()
    homepath = os.getenv("HOMEPATH", "").strip()
    if homedrive and homepath:
        candidates.append(Path(f"{homedrive}{homepath}"))

    try:
        candidates.append(Path.home())
    except RuntimeError:
        pass

    for root in (Path.cwd().resolve(), PROJECT_ROOT.resolve()):
        candidates.append(root)
        candidates.extend(root.parents)

    return _unique_paths(candidates)


def _spu_home_hints_from_base(base: Path) -> list[Path]:
    return [
        base / "spu-main" / "spu-main",
        base / "spu-main",
        base / "spu",
    ]


def _python_paths_from_root(root: Path) -> list[Path]:
    return [
        root / ".venv" / "Scripts" / "python.exe",
        root / ".venv" / "bin" / "python",
        root / "venv" / "Scripts" / "python.exe",
        root / "venv" / "bin" / "python",
    ]


def _common_windows_python_candidates() -> list[Path]:
    candidates: list[Path] = []
    for base in _candidate_user_roots():
        python_root = base / "AppData" / "Local" / "Programs" / "Python"
        if python_root.exists():
            candidates.extend(
                sorted(
                    python_root.glob("Python*/python.exe"),
                    key=lambda item: str(item),
                    reverse=True,
                )
            )

        conda_root = base / ".conda" / "envs"
        if conda_root.exists():
            for pattern in ("*spu*", "*secretflow*"):
                matches = sorted(
                    conda_root.glob(pattern),
                    key=lambda item: str(item),
                    reverse=True,
                )
                candidates.extend(match / "python.exe" for match in matches)

    return _unique_paths(candidates)


def _normalize_runtime_mode(value: Any) -> str:
    normalized = str(value or "").strip().lower().replace("-", "_")
    if normalized in {"wsl", "wsl2", "linux_wsl"}:
        return "wsl"
    return "local"


def _build_wsl_command(
    distro: str,
    command: list[str],
) -> list[str]:
    shell_command = " ".join(shlex.quote(part) for part in command)
    return ["wsl.exe", "-d", distro, "bash", "-lc", shell_command]


def _check_wsl_target(
    distro: str,
    path: str,
    *,
    check_flag: str,
    timeout: int,
) -> dict[str, Any]:
    return _run_command(
        _build_wsl_command(distro, ["test", check_flag, path]),
        PROJECT_ROOT,
        timeout,
    )


def _normalize_runtime_backend(value: Any) -> str:
    normalized = str(value or "").strip().lower().replace("-", "_")
    if normalized in {"spu", "secretflow_spu", "secretflow"}:
        return "secretflow_spu"
    return normalized


def _payload_requests_specific_spu_home(payload: dict[str, Any]) -> bool:
    return bool(
        str(payload.get("spu_home_wsl") or "").strip()
        or str(payload.get("spu_home") or "").strip()
    )


def _driver_path() -> Path:
    return Path(__file__).resolve().parent / "spu_runtime_driver.py"


def _driver_path_wsl() -> str:
    return _windows_to_wsl_path(_driver_path())


def resolve_spu_runtime_mode(payload: dict[str, Any]) -> tuple[str, str]:
    defaults = _load_runtime_defaults()
    explicit = str(payload.get("spu_runtime_mode") or "").strip()
    if explicit:
        return _normalize_runtime_mode(explicit), "explicit"

    env_mode = os.getenv("SPU_RUNTIME_MODE", "").strip()
    if env_mode:
        return _normalize_runtime_mode(env_mode), "env"

    config_mode = _first_nonempty(defaults.get("runtime_mode"), defaults.get("spu_runtime_mode"))
    if config_mode:
        return _normalize_runtime_mode(config_mode), "config"

    return "local", "default"


def resolve_spu_wsl_distro(payload: dict[str, Any]) -> tuple[str, str]:
    defaults = _load_runtime_defaults()
    explicit = str(payload.get("spu_wsl_distro") or "").strip()
    if explicit:
        return explicit, "explicit"

    env_value = os.getenv("SPU_WSL_DISTRO", "").strip()
    if env_value:
        return env_value, "env"

    config_value = _first_nonempty(defaults.get("wsl_distro"), defaults.get("spu_wsl_distro"))
    if config_value:
        return config_value, "config"

    return "", "unresolved"


def resolve_spu_home(
    payload: dict[str, Any],
    config: FinalConfiguration | None = None,
) -> tuple[Path | None, str]:
    defaults = _load_runtime_defaults()
    explicit = str(payload.get("spu_home") or "").strip()
    if explicit:
        return Path(explicit).expanduser(), "explicit"

    env_home = os.getenv("SPU_HOME", "").strip()
    if env_home:
        return Path(env_home).expanduser(), "env"

    config_home = _first_nonempty(defaults.get("spu_home"), defaults.get("spu_home_windows"))
    if config_home:
        return Path(config_home).expanduser(), "config"

    hints: list[Path] = []
    mpspdz_hint = str(payload.get("mpspdz_home") or (config.mpspdz_home if config else "")).strip()
    if mpspdz_hint:
        base = Path(mpspdz_hint).expanduser().resolve().parent
        hints.extend(_spu_home_hints_from_base(base))
    for base in _candidate_user_roots():
        hints.extend(_spu_home_hints_from_base(base))

    for candidate in _unique_paths(hints):
        if (candidate / "pyproject.toml").exists() and (candidate / "spu").exists():
            return candidate, "auto_detected"

    return None, "unresolved"


def resolve_spu_python(payload: dict[str, Any], spu_home: Path | None) -> tuple[Path | None, str]:
    defaults = _load_runtime_defaults()
    explicit = str(payload.get("spu_python") or "").strip()
    if explicit:
        return Path(explicit).expanduser(), "explicit"

    env_python = os.getenv("SPU_PYTHON", "").strip()
    if env_python:
        return Path(env_python).expanduser(), "env"

    config_python = _first_nonempty(defaults.get("spu_python"), defaults.get("spu_python_windows"))
    if config_python and _looks_like_windows_path(config_python):
        return Path(config_python).expanduser(), "config"

    candidates: list[Path] = []
    if spu_home is not None:
        candidates.extend(_python_paths_from_root(spu_home))
        candidates.extend(_python_paths_from_root(spu_home.parent))
        if spu_home.parent != spu_home:
            candidates.extend(_python_paths_from_root(spu_home.parent.parent))

    virtual_env = os.getenv("VIRTUAL_ENV", "").strip()
    if virtual_env:
        candidates.extend(_python_paths_from_root(Path(virtual_env).expanduser()))

    conda_prefix = os.getenv("CONDA_PREFIX", "").strip()
    if conda_prefix:
        candidates.append(Path(conda_prefix).expanduser() / "python.exe")
        candidates.append(Path(conda_prefix).expanduser() / "bin" / "python")

    candidates.extend(_common_windows_python_candidates())

    for candidate in _unique_paths(candidates):
        if candidate.exists():
            return candidate, "auto_detected"

    return None, "unresolved"


def resolve_spu_home_wsl(payload: dict[str, Any], spu_home: Path | None) -> tuple[str, str]:
    defaults = _load_runtime_defaults()
    explicit_wsl = str(payload.get("spu_home_wsl") or "").strip()
    if explicit_wsl:
        return explicit_wsl, "explicit"

    env_wsl = os.getenv("SPU_HOME_WSL", "").strip()
    if env_wsl:
        return env_wsl, "env"

    config_wsl = str(defaults.get("spu_home_wsl") or "").strip()
    if config_wsl:
        return config_wsl, "config"

    explicit_home = str(payload.get("spu_home") or "").strip()
    if _looks_like_posix_path(explicit_home):
        return explicit_home, "explicit"

    config_home = _first_nonempty(defaults.get("spu_home"), defaults.get("spu_home_windows"))
    if _looks_like_posix_path(config_home):
        return config_home, "config"

    if spu_home is not None:
        converted = _windows_to_wsl_path(spu_home)
        if converted:
            return converted, "translated"

    return "", "unresolved"


def resolve_spu_python_wsl(payload: dict[str, Any], spu_home_wsl: str) -> tuple[str, str]:
    defaults = _load_runtime_defaults()
    explicit_wsl = str(payload.get("spu_python_wsl") or "").strip()
    if explicit_wsl:
        return explicit_wsl, "explicit"

    explicit_python = str(payload.get("spu_python") or "").strip()
    if _looks_like_posix_path(explicit_python):
        return explicit_python, "explicit"

    env_wsl = os.getenv("SPU_PYTHON_WSL", "").strip()
    if env_wsl:
        return env_wsl, "env"

    env_python = os.getenv("SPU_PYTHON", "").strip()
    if _looks_like_posix_path(env_python):
        return env_python, "env"

    config_wsl = _first_nonempty(defaults.get("spu_python_wsl"))
    if config_wsl:
        return config_wsl, "config"

    config_python = _first_nonempty(defaults.get("spu_python"), defaults.get("spu_python_windows"))
    if _looks_like_posix_path(config_python):
        return config_python, "config"

    candidates = [
        f"{spu_home_wsl}/.venv/bin/python" if spu_home_wsl else "",
        f"{spu_home_wsl}/venv/bin/python" if spu_home_wsl else "",
    ]
    for candidate in candidates:
        if candidate:
            return candidate, "auto_detected"

    return "", "unresolved"


def _wrap_windows_local_reason(runtime_mode: str, detail: str) -> str:
    if runtime_mode == "wsl" or os.name != "nt":
        return detail
    normalized_detail = detail.strip()
    prefix = (
        "SecretFlow SPU is not supported on native Windows x64. "
        "Use `spu_runtime_mode=wsl` with a WSL2 Python 3.10/3.11 environment, "
        "or run this backend on Linux/macOS."
    )
    if not normalized_detail:
        return prefix
    return f"{prefix} Current detail: {normalized_detail}"


def _build_probe_command(
    *,
    runtime_mode: str,
    spu_python: str,
    spu_home_exec: str,
    wsl_distro: str = "",
) -> list[str]:
    if runtime_mode == "wsl":
        return _build_wsl_command(
            wsl_distro,
            [spu_python, _driver_path_wsl(), "--probe", "--spu-home", spu_home_exec],
        )
    return [spu_python, str(_driver_path()), "--probe", "--spu-home", spu_home_exec]


def _build_run_command(
    *,
    runtime_mode: str,
    spu_python: str,
    spu_home_exec: str,
    spec_path: Path,
    wsl_distro: str = "",
) -> list[str]:
    if runtime_mode == "wsl":
        return _build_wsl_command(
            wsl_distro,
            [
                spu_python,
                _driver_path_wsl(),
                "--spu-home",
                spu_home_exec,
                "--spec",
                _windows_to_wsl_path(spec_path),
            ],
        )
    return [
        spu_python,
        str(_driver_path()),
        "--spu-home",
        spu_home_exec,
        "--spec",
        str(spec_path),
    ]


def inspect_spu_runtime_support(
    payload: dict[str, Any],
    config: FinalConfiguration | None = None,
) -> dict[str, Any]:
    runtime_mode, runtime_mode_source = resolve_spu_runtime_mode(payload)
    spu_home, spu_home_source = resolve_spu_home(payload, config)
    explicit_python = str(payload.get("spu_python") or "").strip()
    if runtime_mode != "wsl" and spu_home is not None and not spu_home.exists():
        return {
            "launchable": False,
            "reason": _wrap_windows_local_reason(
                runtime_mode,
                f"SecretFlow SPU home not found: {spu_home}",
            ),
            "runtime_mode": runtime_mode,
            "runtime_mode_source": runtime_mode_source,
            "spu_home": str(spu_home),
            "spu_home_source": spu_home_source,
        }
    if runtime_mode != "wsl" and spu_home is None and not explicit_python:
        return {
            "launchable": False,
            "reason": _wrap_windows_local_reason(
                runtime_mode,
                (
                    "Unable to resolve SecretFlow SPU home. Set `spu_home` or `SPU_HOME`, "
                    "or provide `spu_python` that already has `spu` installed."
                ),
            ),
            "runtime_mode": runtime_mode,
            "runtime_mode_source": runtime_mode_source,
            "spu_home_source": spu_home_source,
        }

    timeout_seconds = int(payload.get("timeout_seconds", 300))
    if runtime_mode == "wsl":
        wsl_distro, wsl_distro_source = resolve_spu_wsl_distro(payload)
        if not wsl_distro:
            return {
                "launchable": False,
                "reason": "Unable to resolve WSL distro. Set `spu_wsl_distro` or `SPU_WSL_DISTRO`.",
                "runtime_mode": runtime_mode,
                "runtime_mode_source": runtime_mode_source,
            }

        spu_home_wsl, spu_home_wsl_source = resolve_spu_home_wsl(payload, spu_home)
        spu_python_wsl, spu_python_source = resolve_spu_python_wsl(payload, spu_home_wsl)
        if not spu_python_wsl:
            return {
                "launchable": False,
                "reason": (
                    "Unable to resolve SecretFlow SPU WSL python. Set `spu_python_wsl`, "
                    "`SPU_PYTHON_WSL`, or provide a project `.spu_runtime.json`."
                ),
                "runtime_mode": runtime_mode,
                "runtime_mode_source": runtime_mode_source,
                "wsl_distro": wsl_distro,
                "wsl_distro_source": wsl_distro_source,
                "spu_home": str(spu_home) if spu_home is not None else "",
                "spu_home_source": spu_home_source,
                "spu_home_wsl": spu_home_wsl,
                "spu_home_wsl_source": spu_home_wsl_source,
                "spu_python_source": spu_python_source,
            }

        details: dict[str, Any] = {
            "runtime_mode": runtime_mode,
            "runtime_mode_source": runtime_mode_source,
            "wsl_distro": wsl_distro,
            "wsl_distro_source": wsl_distro_source,
            "spu_home": str(spu_home) if spu_home is not None else "",
            "spu_home_source": spu_home_source,
            "spu_home_wsl": spu_home_wsl,
            "spu_home_wsl_source": spu_home_wsl_source,
            "spu_python": spu_python_wsl,
            "spu_python_source": spu_python_source,
        }

        spu_home_exec = spu_home_wsl
        spu_home_exec_source = spu_home_wsl_source if spu_home_wsl else "empty"

        if spu_home_wsl:
            home_check = _check_wsl_target(
                wsl_distro,
                spu_home_wsl,
                check_flag="-d",
                timeout=timeout_seconds,
            )
            details["spu_home_check"] = home_check
            if home_check["return_code"] != 0:
                if _payload_requests_specific_spu_home(payload):
                    return {
                        **details,
                        "launchable": False,
                        "reason": f"SecretFlow SPU WSL home not found: {spu_home_wsl}",
                    }
                spu_home_exec = ""
                spu_home_exec_source = "fallback_empty"
                details["spu_home_warning"] = (
                    "Resolved WSL source tree was not accessible; falling back to the installed `spu` package."
                )

        details["spu_home_exec"] = spu_home_exec
        details["spu_home_exec_source"] = spu_home_exec_source

        python_check = _check_wsl_target(
            wsl_distro,
            spu_python_wsl,
            check_flag="-x",
            timeout=timeout_seconds,
        )
        details["spu_python_check"] = python_check
        if python_check["return_code"] != 0:
            return {
                **details,
                "launchable": False,
                "reason": f"SecretFlow SPU WSL python not found or not executable: {spu_python_wsl}",
            }

        probe = _run_command(
            _build_probe_command(
                runtime_mode=runtime_mode,
                spu_python=spu_python_wsl,
                spu_home_exec=spu_home_exec,
                wsl_distro=wsl_distro,
            ),
            PROJECT_ROOT,
            timeout_seconds,
        )
        details["probe"] = probe
    else:
        spu_python, spu_python_source = resolve_spu_python(payload, spu_home)
        if spu_python is None:
            return {
                "launchable": False,
                "reason": _wrap_windows_local_reason(
                    runtime_mode,
                    (
                        "Unable to resolve SecretFlow SPU python. Set `spu_python` or `SPU_PYTHON` "
                        "to a Python 3.10/3.11/3.12 environment with `spu`, `jax`, and dependencies installed."
                    ),
                ),
                "runtime_mode": runtime_mode,
                "runtime_mode_source": runtime_mode_source,
                "spu_home": str(spu_home),
                "spu_home_source": spu_home_source,
                "spu_python_source": "unresolved",
            }
        if not spu_python.exists():
            return {
                "launchable": False,
                "reason": _wrap_windows_local_reason(
                    runtime_mode,
                    f"SecretFlow SPU python not found: {spu_python}",
                ),
                "runtime_mode": runtime_mode,
                "runtime_mode_source": runtime_mode_source,
                "spu_home": str(spu_home),
                "spu_home_source": spu_home_source,
                "spu_python": str(spu_python),
                "spu_python_source": spu_python_source,
            }

        spu_home_exec = str(spu_home) if spu_home is not None else ""
        probe = _run_command(
            _build_probe_command(
                runtime_mode=runtime_mode,
                spu_python=str(spu_python),
                spu_home_exec=spu_home_exec,
            ),
            PROJECT_ROOT,
            timeout_seconds,
        )
        details = {
            "runtime_mode": runtime_mode,
            "runtime_mode_source": runtime_mode_source,
            "spu_home": str(spu_home) if spu_home is not None else "",
            "spu_home_source": spu_home_source,
            "spu_home_exec": spu_home_exec,
            "spu_home_exec_source": spu_home_source if spu_home_exec else "empty",
            "spu_python": str(spu_python),
            "spu_python_source": spu_python_source,
            "probe": probe,
        }

    if probe["return_code"] != 0:
        return {
            **details,
            "launchable": False,
            "reason": _wrap_windows_local_reason(
                runtime_mode,
                probe.get("stderr") or probe.get("stdout") or "SecretFlow SPU probe failed.",
            ),
        }

    stdout = str(probe.get("stdout", "")).strip()
    try:
        probe_payload = json.loads(stdout) if stdout else {}
    except json.JSONDecodeError:
        probe_payload = {}
    details["probe_payload"] = probe_payload

    if not probe_payload.get("ok", False):
        return {
            **details,
            "launchable": False,
            "reason": _wrap_windows_local_reason(
                runtime_mode,
                str(probe_payload.get("reason", "")).strip() or "SecretFlow SPU probe failed.",
            ),
        }

    return {
        **details,
        "launchable": True,
        "reason": "SecretFlow SPU runtime probe succeeded.",
    }


def _protocol_kind_from_config(config: FinalConfiguration) -> str:
    implementation = config.implementation_id or config.protocol_id
    if implementation == "spu_cheetah":
        return "CHEETAH"
    if implementation in {"spu_semi2k", "semi2k"}:
        return "SEMI2K"
    return "ABY3"


def _field_from_config(req: ParsedRequirement, config: FinalConfiguration) -> str:
    if req.math_structure == "ring":
        return "FM64"
    if config.implementation_id == "spu_aby3":
        return "FM64"
    return "FM64"


def _default_inputs(req: ParsedRequirement) -> list[Any]:
    if req.operation == "comparison":
        return [7, 3]
    return [index + 1 for index in range(max(2, req.parties))]


def _missing_spu_match_reason(req: ParsedRequirement) -> str:
    guidance = [
        "No SecretFlow SPU implementation matched the current requirement.",
        "SPU currently covers semi_honest Cheetah (2PC), semi_honest ABY3 (3PC honest_majority),",
        "and debug-oriented Semi2k for semi_honest arithmetic scenarios.",
    ]
    if req.parties == 2:
        guidance.append("For 2 parties, try `security_model=semi_honest` with `corruption_model=dishonest_majority`.")
    elif req.parties == 3:
        guidance.append("For 3 parties, try `security_model=semi_honest` with `corruption_model=honest_majority` for ABY3.")
    else:
        guidance.append("For n-party SPU, Semi2k is the closest option but is intended mainly for debugging.")
    return " ".join(guidance)


class SpuRunner:
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
                "backend": "secretflow_spu",
                "reason": "execute=false, only generated configuration.",
            }

        if _normalize_runtime_backend(config.runner_backend or payload.get("runtime_backend")) != "secretflow_spu":
            return {
                "executed": False,
                "status": "error",
                "backend": "secretflow_spu",
                "reason": "SecretFlow SPU runner was selected without a matching `runner_backend=secretflow_spu` configuration.",
            }

        if not config.implementation_id:
            return {
                "executed": False,
                "status": "error",
                "backend": "secretflow_spu",
                "reason": _missing_spu_match_reason(req),
            }

        support = inspect_spu_runtime_support(payload, config)
        if not support.get("launchable"):
            return {
                "executed": False,
                "status": "error",
                "backend": "secretflow_spu",
                "implementation_id": config.implementation_id,
                "execution_preflight": support,
                "reason": str(support.get("reason", "")).strip() or "SecretFlow SPU preflight failed.",
            }

        timeout_seconds = int(payload.get("timeout_seconds", 300))
        if "spu_home_exec" in support:
            spu_home_exec = str(support.get("spu_home_exec") or "")
        else:
            spu_home_exec = str(support.get("spu_home_wsl") or support.get("spu_home") or "")

        spec = {
            "spu_home": spu_home_exec,
            "implementation_id": config.implementation_id,
            "protocol_kind": _protocol_kind_from_config(config),
            "field": _field_from_config(req, config),
            "parties": int(config.parties),
            "operation": req.operation,
            "compile_only": bool(payload.get("compile_only", False)),
            "inputs": payload.get("spu_inputs")
            if isinstance(payload.get("spu_inputs"), list)
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
            run_cmd = _build_run_command(
                runtime_mode=str(support.get("runtime_mode") or "local"),
                spu_python=str(support["spu_python"]),
                spu_home_exec=spu_home_exec,
                spec_path=spec_path,
                wsl_distro=str(support.get("wsl_distro") or ""),
            )
            run_result = _run_command(run_cmd, PROJECT_ROOT, timeout_seconds)
        finally:
            try:
                spec_path.unlink(missing_ok=True)
            except OSError:
                pass

        stdout = str(run_result.get("stdout", "")).strip()
        payload_result: dict[str, Any] = {}
        try:
            payload_result = json.loads(stdout) if stdout else {}
        except json.JSONDecodeError:
            payload_result = {}

        if run_result["return_code"] != 0:
            return {
                "executed": True,
                "status": "run_failed",
                "backend": "secretflow_spu",
                "implementation_id": config.implementation_id,
                "framework": config.framework,
                "execution_preflight": support,
                "run": run_result,
                "reason": str(payload_result.get("reason", "")).strip()
                or str(run_result.get("stderr", "")).strip()
                or str(run_result.get("stdout", "")).strip()
                or "SecretFlow SPU execution failed.",
            }

        status = "compile_only_success" if bool(payload.get("compile_only", False)) else "success"
        return {
            "executed": True,
            "status": status,
            "backend": "secretflow_spu",
            "implementation_id": config.implementation_id,
            "framework": config.framework,
            "execution_preflight": support,
            "run": run_result,
            "result": payload_result,
            "reason": str(payload_result.get("reason", "")).strip(),
        }

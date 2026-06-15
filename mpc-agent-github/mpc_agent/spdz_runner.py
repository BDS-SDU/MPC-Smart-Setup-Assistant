from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from .models import FinalConfiguration, ParsedRequirement
from .skills.executor import execute_skill


def _truncate(text: str | None, limit: int = 4000) -> str:
    if text is None:
        return ""
    if len(text) <= limit:
        return text
    return f"{text[:limit]}\n...<truncated {len(text) - limit} chars>"


def _normalize_whitespace(text: str | None) -> str:
    if not text:
        return ""
    return " ".join(str(text).split())


def _looks_like_launcher_noise(text: str) -> bool:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return False

    lowered = text.lower()
    error_signals = (
        "error",
        "failed",
        "not found",
        "timed out",
        "traceback",
        "exception",
        "invalid",
        "denied",
        "too high",
        "no such file",
        "connection refused",
    )
    if any(signal in lowered for signal in error_signals):
        return False

    return all(line.lower().startswith("running ") for line in lines)


def _pick_runtime_reason(run_result: dict[str, Any]) -> str:
    stderr = _normalize_whitespace(run_result.get("stderr"))
    stdout = _normalize_whitespace(run_result.get("stdout"))
    combined = f"{stderr}\n{stdout}".strip()

    missing_input_match = re.search(r"not enough inputs in (\S+)", combined, flags=re.IGNORECASE)
    if missing_input_match:
        missing_path = missing_input_match.group(1)
        return (
            f"Missing MPC input file: {missing_path}. "
            "Prepare per-party input files under Player-Data before runtime execution."
        )

    candidates = [stderr, stdout]
    for candidate in candidates:
        if candidate and not _looks_like_launcher_noise(candidate):
            return candidate

    for candidate in candidates:
        if candidate:
            return candidate

    return "Runtime execution failed."


def _decode_output(raw: bytes | str | None) -> str:
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw

    # MP-SPDZ scripts can emit mixed encodings depending on the environment.
    for encoding in ("utf-8", "gb18030", "gbk"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _build_default_program(req: ParsedRequirement) -> str:
    parties = max(2, req.parties)
    if req.operation == "comparison":
        return """from Compiler.library import print_ln

a = sint.get_input_from(0)
b = sint.get_input_from(1)
res = (a < b)
print_ln('comparison_result=%s', res.reveal())
"""
    if req.operation == "aggregation":
        return f"""from Compiler.types import sint
from Compiler.library import print_ln

n = {parties}
vals = [sint.get_input_from(i) for i in range(n)]
total = vals[0]
for v in vals[1:]:
    total += v
print_ln('sum=%s', total.reveal())
"""
    return f"""from Compiler.types import sint
from Compiler.library import print_ln

n = {parties}
vals = [sint.get_input_from(i) for i in range(n)]
acc = vals[0]
for v in vals[1:]:
    acc += v
print_ln('result=%s', acc.reveal())
"""


def _normalize_program_name(name: str, fallback: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", name.strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or fallback


def resolve_mpspdz_home(
    payload: dict[str, Any],
    config: FinalConfiguration | None = None,
    *,
    mpspdz_home_hint: str = "",
) -> tuple[Path | None, str]:
    explicit = str(payload.get("mpspdz_home") or mpspdz_home_hint or (config.mpspdz_home if config else "")).strip()
    if explicit:
        return Path(explicit).expanduser(), "explicit"

    candidates = [
        os.getenv("MPSPDZ_HOME", "").strip(),
        str(Path.home() / "MP-SPDZ"),
        str(Path.cwd() / "MP-SPDZ"),
    ]

    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate).expanduser()
        if (path / "compile.py").exists():
            return path, "auto_detected"

    return None, "unresolved"


def _resolve_mpspdz_home(payload: dict[str, Any], config: FinalConfiguration) -> tuple[Path | None, str]:
    return resolve_mpspdz_home(payload, config)


def _prepare_source_dir(source_dir: Path) -> tuple[bool, str | None]:
    try:
        source_dir.mkdir(parents=True, exist_ok=True)
        return True, None
    except PermissionError as error:
        return False, f"Permission denied creating source directory: {source_dir}. detail={error}"
    except OSError as error:
        return False, f"Failed to prepare source directory: {source_dir}. detail={error}"


def _resolve_existing_script(mpspdz_home: Path, candidates: list[str]) -> Path | None:
    existing: list[Path] = []
    for relative in candidates:
        script_path = mpspdz_home / relative
        if script_path.exists():
            existing.append(script_path)

    if not existing:
        return None

    preferred_suffixes = [".bat", ".sh"] if os.name == "nt" else [".sh", ".bat"]
    for suffix in preferred_suffixes:
        for script in existing:
            if script.suffix.lower() == suffix:
                return script
    return existing[0]


def _list_script_directory(mpspdz_home: Path) -> list[str]:
    scripts_dir = mpspdz_home / "Scripts"
    if not scripts_dir.exists() or not scripts_dir.is_dir():
        return []
    names = [item.name for item in scripts_dir.iterdir() if item.is_file()]
    names.sort()
    return names


def inspect_protocol_launch_support(
    mpspdz_home: Path,
    script_candidates: list[str],
    *,
    require_runtime_binary: bool = True,
) -> dict[str, Any]:
    existing_scripts = [
        str((mpspdz_home / relative).resolve())
        for relative in script_candidates
        if (mpspdz_home / relative).exists()
    ]
    preferred_script = _resolve_existing_script(mpspdz_home, script_candidates)
    available_scripts = _list_script_directory(mpspdz_home)

    if preferred_script is None:
        return {
            "launchable": False,
            "reason": f"Missing protocol launch scripts: {script_candidates}",
            "existing_scripts": existing_scripts,
            "available_scripts": available_scripts,
        }

    runtime_binary = _infer_runtime_binary(preferred_script, mpspdz_home)
    if require_runtime_binary and runtime_binary and not runtime_binary.exists():
        return {
            "launchable": False,
            "reason": f"Missing runtime binary: {runtime_binary.name}",
            "preferred_script": str(preferred_script),
            "runtime_binary": str(runtime_binary),
            "existing_scripts": existing_scripts,
            "available_scripts": available_scripts,
        }

    return {
        "launchable": True,
        "reason": "Protocol runtime is available in current MP-SPDZ checkout.",
        "preferred_script": str(preferred_script),
        "runtime_binary": str(runtime_binary) if runtime_binary else "",
        "existing_scripts": existing_scripts,
        "available_scripts": available_scripts,
    }


def _prepare_player_inputs(
    mpspdz_home: Path,
    parties: int,
    *,
    overwrite: bool,
) -> dict[str, Any]:
    player_data_dir = mpspdz_home / "Player-Data"
    player_data_dir.mkdir(parents=True, exist_ok=True)

    created_files: list[str] = []
    skipped_existing = 0
    for player_id in range(max(2, parties)):
        input_path = player_data_dir / f"Input-P{player_id}-0"
        if input_path.exists() and not overwrite:
            skipped_existing += 1
            continue
        input_path.write_text("0\n", encoding="utf-8")
        created_files.append(str(input_path))

    return {
        "player_data_dir": str(player_data_dir),
        "created_input_files": created_files,
        "skipped_existing_files": skipped_existing,
    }


def _supports_auto_input_generation(req: ParsedRequirement, payload: dict[str, Any]) -> bool:
    if "auto_prepare_inputs" in payload:
        return bool(payload.get("auto_prepare_inputs"))
    custom_program = str(payload.get("mpc_program", "")).strip()
    if custom_program:
        return False
    return req.operation in {"aggregation", "comparison", "generic"}


def _should_overwrite_inputs(payload: dict[str, Any]) -> bool:
    return bool(payload.get("overwrite_inputs", False))


def _skill_names_from_payload(payload: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for key in ("skills", "_recommended_skills"):
        value = payload.get(key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str) and item not in names:
                    names.append(item)
    return names


def _infer_runtime_binary(script_path: Path, mpspdz_home: Path) -> Path | None:
    script_name = script_path.stem.lower()
    if not script_name:
        return None
    return mpspdz_home / f"{script_name}-party.x"


def _supports_party_count_argument(script_path: Path) -> bool:
    fixed_party_scripts = {"yao"}
    return script_path.stem.lower() not in fixed_party_scripts


def _to_bash_path(path: Path) -> str:
    raw = str(path)
    if os.name != "nt":
        return raw

    normalized = raw.replace("\\", "/")
    if len(normalized) >= 2 and normalized[1] == ":":
        drive = normalized[0].lower()
        remainder = normalized[2:]
        return f"/{drive}{remainder}"
    return normalized


def _run_command(command: list[str], cwd: Path, timeout: int) -> dict[str, Any]:
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


def _python_executable() -> str:
    return sys.executable or "python"


class MpSpdzRunner:
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
                "reason": "execute=false, only generated configuration.",
            }

        mpspdz_home, home_source = _resolve_mpspdz_home(payload, config)
        if mpspdz_home is None:
            return {
                "executed": False,
                "status": "error",
                "reason": "Unable to resolve MP-SPDZ home. Set `mpspdz_home` or `MPSPDZ_HOME`.",
            }
        if not mpspdz_home.exists():
            return {
                "executed": False,
                "status": "error",
                "reason": f"MP-SPDZ home not found: {mpspdz_home}",
            }

        source_dir = mpspdz_home / "Programs" / "Source"
        prepared, source_error = _prepare_source_dir(source_dir)
        if not prepared:
            return {
                "executed": False,
                "status": "error",
                "reason": source_error or f"Failed to prepare Programs/Source under MP-SPDZ home: {source_dir}",
            }

        fallback_program_name = f"auto_mpc_{int(time.time())}"
        requested_name = payload.get("program_name") or config.source_program_name
        program_name = _normalize_program_name(str(requested_name), fallback_program_name)

        source_code = str(payload.get("mpc_program", "")).strip() or _build_default_program(req)
        source_path = source_dir / f"{program_name}.mpc"
        try:
            source_path.write_text(source_code, encoding="utf-8")
        except PermissionError as error:
            return {
                "executed": False,
                "status": "error",
                "source_path": str(source_path),
                "reason": (
                    f"Permission denied writing MPC source: {source_path}. "
                    "Grant write permission for MP-SPDZ/Programs/Source, "
                    "or pass a writable `mpspdz_home` in the request payload."
                ),
                "detail": str(error),
            }
        except OSError as error:
            return {
                "executed": False,
                "status": "error",
                "source_path": str(source_path),
                "reason": f"Failed to write MPC source file: {source_path}",
                "detail": str(error),
            }

        compile_script = mpspdz_home / "compile.py"
        if not compile_script.exists():
            return {
                "executed": False,
                "status": "error",
                "reason": f"compile.py not found: {compile_script}",
            }

        if not payload.get("compile_only", False):
            launch_support = inspect_protocol_launch_support(
                mpspdz_home,
                config.script_candidates,
                require_runtime_binary=True,
            )
            if not launch_support.get("launchable"):
                available_scripts = launch_support.get("available_scripts", [])
                available_preview = ", ".join(available_scripts[:8]) if available_scripts else "<none>"
                support_reason = str(launch_support.get("reason", "")).strip()
                if support_reason.startswith("Missing runtime binary:"):
                    binary_name = support_reason.split(":", 1)[1].strip()
                    formatted_reason = (
                        f"Runtime binary not found: {binary_name}. "
                        f"Build it first (for example: make {binary_name}). "
                        f"Available scripts under Scripts/: {available_preview}"
                    )
                elif support_reason.startswith("Missing protocol launch scripts:"):
                    formatted_reason = (
                        f"No protocol launch script found from candidates: {config.script_candidates}. "
                        f"Available scripts under Scripts/: {available_preview}"
                    )
                else:
                    formatted_reason = (
                        f"Selected protocol is not launchable in current MP-SPDZ checkout. "
                        f"{support_reason}. "
                        f"Available scripts under Scripts/: {available_preview}"
                    ).strip()
                return {
                    "executed": False,
                    "status": "run_failed",
                    "source_path": str(source_path),
                    "mpspdz_home_source": home_source,
                    "execution_preflight": launch_support,
                    "reason": formatted_reason,
                }

        timeout_seconds = int(payload.get("timeout_seconds", 300))
        compile_cmd = [_python_executable(), "compile.py", *config.compile_options, program_name]
        compile_result = _run_command(compile_cmd, mpspdz_home, timeout_seconds)
        if compile_result["return_code"] != 0:
            return {
                "executed": True,
                "status": "compile_failed",
                "source_path": str(source_path),
                "mpspdz_home_source": home_source,
                "compile": compile_result,
            }

        if payload.get("compile_only", False):
            return {
                "executed": True,
                "status": "compile_only_success",
                "source_path": str(source_path),
                "mpspdz_home_source": home_source,
                "compile": compile_result,
                "reason": "compile_only=true, skipped protocol runtime execution.",
            }

        preparation: dict[str, Any] = {}
        skill_names = _skill_names_from_payload(payload)
        use_skill_prepare_inputs = "mpspdz-execution" in skill_names
        if use_skill_prepare_inputs:
            try:
                skill_result = execute_skill(
                    "mpspdz-execution",
                    {
                        "action": "make_inputs",
                        "mpspdz_home": str(mpspdz_home),
                        "parties": int(config.parties),
                        "overwrite": _should_overwrite_inputs(payload),
                    },
                )
                preparation["inputs"] = skill_result.get("result", {})
                preparation["inputs_prepared_by"] = "skill_script"
            except Exception as error:  # noqa: BLE001
                preparation["inputs_prepared_by"] = "skill_script_failed_fallback"
                preparation["inputs_prepare_error"] = str(error)

        if _supports_auto_input_generation(req, payload) and "inputs" not in preparation:
            try:
                preparation["inputs"] = _prepare_player_inputs(
                    mpspdz_home,
                    int(config.parties),
                    overwrite=_should_overwrite_inputs(payload),
                )
                preparation.setdefault("inputs_prepared_by", "runner_builtin")
            except OSError as error:
                return {
                    "executed": True,
                    "status": "run_failed",
                    "source_path": str(source_path),
                    "mpspdz_home_source": home_source,
                    "compile": compile_result,
                    "reason": f"Failed to auto-prepare Player-Data inputs: {error}",
                }

        script_path = _resolve_existing_script(mpspdz_home, config.script_candidates)
        if script_path is None:
            return {
                "executed": True,
                "status": "run_failed",
                "source_path": str(source_path),
                "mpspdz_home_source": home_source,
                "compile": compile_result,
                "reason": f"No protocol launch script found from candidates: {config.script_candidates}",
                "execution_preflight": inspect_protocol_launch_support(
                    mpspdz_home,
                    config.script_candidates,
                    require_runtime_binary=False,
                ),
            }

        runtime_binary = _infer_runtime_binary(script_path, mpspdz_home)
        if runtime_binary and not runtime_binary.exists():
            return {
                "executed": True,
                "status": "run_failed",
                "source_path": str(source_path),
                "mpspdz_home_source": home_source,
                "compile": compile_result,
                "reason": (
                    f"Runtime binary not found: {runtime_binary}. "
                    f"Build it first (for example: make {runtime_binary.name})."
                ),
            }

        run_cmd: list[str]
        party_count = max(2, int(config.parties))
        suffix = script_path.suffix.lower()
        run_args = [program_name]
        if _supports_party_count_argument(script_path):
            run_args.extend(["-N", str(party_count)])

        if suffix == ".sh":
            bash_path = shutil.which("bash")
            if not bash_path:
                return {
                    "executed": True,
                    "status": "run_failed",
                    "source_path": str(source_path),
                    "mpspdz_home_source": home_source,
                    "compile": compile_result,
                    "reason": "Selected protocol script is .sh but `bash` is unavailable.",
                }
            try:
                script_arg = script_path.relative_to(mpspdz_home).as_posix()
            except ValueError:
                script_arg = _to_bash_path(script_path)
            run_cmd = [bash_path, script_arg, *run_args]
        else:
            run_cmd = [str(script_path), *run_args]

        run_result = _run_command(run_cmd, mpspdz_home, timeout_seconds)
        status = "success" if run_result["return_code"] == 0 else "run_failed"
        response = {
            "executed": True,
            "status": status,
            "source_path": str(source_path),
            "mpspdz_home_source": home_source,
            "compile": compile_result,
            "run": run_result,
            "preparation": preparation,
        }
        if status != "success":
            response["reason"] = _truncate(_pick_runtime_reason(run_result), 600)
            if "windows-mpspdz-debug" in skill_names:
                try:
                    response["windows_debug"] = execute_skill(
                        "windows-mpspdz-debug",
                        {"execution": response},
                    )
                except Exception as error:  # noqa: BLE001
                    response["windows_debug_error"] = str(error)
        return response

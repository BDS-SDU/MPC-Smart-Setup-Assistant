from __future__ import annotations

from typing import Any

from mpc_agent.models import FinalConfiguration, ParsedRequirement
from mpc_agent.runtime_runner import RuntimeRunner
from mpc_agent.skills.executor import execute_skill


_RUNNER = RuntimeRunner()


def _coerce_parsed_requirement(value: ParsedRequirement | dict[str, Any]) -> ParsedRequirement:
    if isinstance(value, ParsedRequirement):
        return value
    return ParsedRequirement(**value)


def _coerce_final_config(value: FinalConfiguration | dict[str, Any]) -> FinalConfiguration:
    if isinstance(value, FinalConfiguration):
        return value
    return FinalConfiguration(**value)


def compile_program_tool(
    payload: dict[str, Any],
    parsed_requirement: ParsedRequirement | dict[str, Any],
    final_config: FinalConfiguration | dict[str, Any],
) -> dict[str, Any]:
    local_payload = dict(payload)
    local_payload["execute"] = True
    local_payload["compile_only"] = True
    parsed_obj = _coerce_parsed_requirement(parsed_requirement)
    config_obj = _coerce_final_config(final_config)
    return _RUNNER.run(local_payload, parsed_obj, config_obj)


def run_protocol_tool(
    payload: dict[str, Any],
    parsed_requirement: ParsedRequirement | dict[str, Any],
    final_config: FinalConfiguration | dict[str, Any],
) -> dict[str, Any]:
    local_payload = dict(payload)
    local_payload["execute"] = True
    local_payload["compile_only"] = False
    parsed_obj = _coerce_parsed_requirement(parsed_requirement)
    config_obj = _coerce_final_config(final_config)
    return _RUNNER.run(local_payload, parsed_obj, config_obj)


def diagnose_execution_failure(
    execution: dict[str, Any],
    *,
    skills: list[str] | None = None,
) -> dict[str, Any]:
    status = str(execution.get("status", "unknown"))
    reason = str(execution.get("reason", "")).strip()
    compile_stderr = str(execution.get("compile", {}).get("stderr", "")).strip()
    run_stderr = str(execution.get("run", {}).get("stderr", "")).strip()
    run_stdout = str(execution.get("run", {}).get("stdout", "")).strip()

    if reason:
        diagnosis = reason
    elif run_stderr:
        diagnosis = run_stderr
    elif run_stdout:
        diagnosis = run_stdout
    elif compile_stderr:
        diagnosis = compile_stderr
    else:
        diagnosis = "No detailed error message captured."

    suggestion = "Check compile and run logs."
    lower = diagnosis.lower()
    backend = str(execution.get("backend", "")).strip().lower()
    if "input-p" in lower or "not enough inputs" in lower:
        suggestion = "Prepare Player-Data/Input-P*-0 files for each party."
    elif "runtime binary not found" in lower:
        suggestion = "Build the missing runtime binary under MP-SPDZ root."
    elif "missing protocol launch scripts" in lower or "selected protocol is not launchable" in lower:
        suggestion = "Check MP-SPDZ/Scripts contents, or switch to a locally launchable protocol / execute=false."
    elif "permission denied" in lower:
        suggestion = "Grant write permission to MP-SPDZ directories or use a writable mpspdz_home."
    elif "compile.py not found" in lower:
        suggestion = "Verify mpspdz_home points to a valid MP-SPDZ checkout."
    elif backend == "secretflow_spu" and ("windows x64" in lower or "wsl2" in lower):
        suggestion = "Run SecretFlow SPU through WSL2/Linux; native Windows execution is not supported."
    elif backend == "secretflow_spu" and ("unable to resolve secretflow spu python" in lower or "spu_python" in lower):
        suggestion = "Point `spu_python` to a Python 3.10/3.11 environment with `spu`, `jax`, and dependencies installed."
    elif backend == "secretflow_spu" and ("no module named" in lower or "jax" in lower or "spu" in lower):
        suggestion = "Install `spu` and `jax` into the selected SPU Python environment, or provide the correct `spu_python`."
    elif backend == "secretflow_spu" and ("ab y3 requires exactly 3 parties" in lower or "aby3 requires exactly 3 parties" in lower):
        suggestion = "Use exactly 3 parties for ABY3, or switch the SPU implementation to Cheetah/Semi2k."
    elif backend == "crypten" and ("unable to resolve crypten python" in lower or "crypten_python" in lower):
        suggestion = "Point `crypten_python` to a Python 3.10 environment with `crypten` and `torch` installed."
    elif backend == "crypten" and ("no module named" in lower or "crypten" in lower or "torch" in lower):
        suggestion = "Install `crypten` and `torch` into the selected CrypTen environment, or provide the correct `crypten_python`."

    result: dict[str, Any] = {
        "status": status,
        "diagnosis": diagnosis,
        "suggestion": suggestion,
    }
    skill_names = skills or []
    if "windows-mpspdz-debug" in skill_names:
        try:
            result["windows_debug"] = execute_skill(
                "windows-mpspdz-debug",
                {"execution": execution},
            )
        except Exception as error:  # noqa: BLE001
            result["windows_debug_error"] = str(error)
    return result

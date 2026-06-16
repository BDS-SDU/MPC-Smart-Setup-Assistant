"""Backend-specific execution plan builders."""

from __future__ import annotations

from pathlib import Path

from mpc_agent.config import Settings
from mpc_agent.schemas import MPCProtocolConfig

from .schemas import BackendCandidate, ExecutionPlan


def build_execution_plan(
    candidate: BackendCandidate,
    config: MPCProtocolConfig,
    settings: Settings,
    task_hint: str | None = None,
) -> ExecutionPlan:
    if candidate.backend == "aby":
        return _aby_plan(candidate, config, settings, task_hint)
    if candidate.backend == "emp_sh2pc":
        return _emp_plan(candidate, config, settings, task_hint)
    if candidate.backend == "spu":
        return _spu_plan(candidate, config, settings, task_hint)
    if candidate.backend == "crypten":
        return _crypten_plan(candidate, config, settings, task_hint)
    if candidate.backend == "motion":
        return _motion_plan(candidate, config, settings, task_hint)
    if candidate.backend == "scale_mamba":
        return _scale_mamba_plan(candidate, config, settings, task_hint)
    return _mp_spdz_plan(candidate, config, settings, task_hint)


def _aby_plan(
    candidate: BackendCandidate,
    config: MPCProtocolConfig,
    settings: Settings,
    task_hint: str | None,
) -> ExecutionPlan:
    command = ["python", "backend_repository/aby/run_aby_job.py", "--protocol", candidate.protocol]
    runnable = Path("backend_repository/aby/run_aby_job.py").exists()
    return ExecutionPlan(
        backend="aby",
        protocol=candidate.protocol,
        runnable=runnable,
        command=command,
        environment={"ABY_PROTOCOL": candidate.protocol},
        input_artifacts=["mpc_config.json", "ABY circuit/program description"],
        output_artifacts=["aby_result.json"],
        steps=[
            "Serialize current_mpc_config to backend_repository/aby/mpc_config.json.",
            "Split the workload into arithmetic/boolean/Yao-compatible subcircuits.",
            f"Run ABY using {candidate.protocol}.",
            "Collect outputs and protocol statistics.",
        ],
        notes=[
            "ABY is modeled here as a 2PC mixed-protocol backend adapter stub.",
            f"Task hint: {task_hint or 'not provided'}",
        ],
    )


def _emp_plan(
    candidate: BackendCandidate,
    config: MPCProtocolConfig,
    settings: Settings,
    task_hint: str | None,
) -> ExecutionPlan:
    command = ["python", "backend_repository/emp_sh2pc/run_emp_job.py", "--protocol", candidate.protocol]
    runnable = Path("backend_repository/emp_sh2pc/run_emp_job.py").exists()
    return ExecutionPlan(
        backend="emp_sh2pc",
        protocol=candidate.protocol,
        runnable=runnable,
        command=command,
        environment={"EMP_PROTOCOL": candidate.protocol},
        input_artifacts=["mpc_config.json", "Boolean/garbled-circuit description"],
        output_artifacts=["emp_result.json"],
        steps=[
            "Serialize current_mpc_config to backend_repository/emp_sh2pc/mpc_config.json.",
            "Generate a garbled-circuit style program or adapter input.",
            "Run EMP-sh2pc with the selected 2PC protocol mode.",
            "Collect outputs and runtime metrics.",
        ],
        notes=[
            "EMP-sh2pc is represented as a semi-honest 2PC adapter stub.",
            f"Task hint: {task_hint or 'not provided'}",
        ],
    )


def _spu_plan(
    candidate: BackendCandidate,
    config: MPCProtocolConfig,
    settings: Settings,
    task_hint: str | None,
) -> ExecutionPlan:
    command = ["python", "backend_repository/spu/run_spu_job.py", "--protocol", candidate.protocol]
    runnable = Path("backend_repository/spu/run_spu_job.py").exists()
    return ExecutionPlan(
        backend="spu",
        protocol=candidate.protocol,
        runnable=runnable,
        command=command,
        environment={"SPU_PROTOCOL": candidate.protocol},
        input_artifacts=["mpc_config.json", "SPU cluster/runtime config"],
        output_artifacts=["spu_result.json"],
        steps=[
            "Serialize current_mpc_config to backend_repository/spu/mpc_config.json.",
            "Translate arithmetic/tensor workload to an SPU-compatible program.",
            f"Run SPU with protocol {candidate.protocol}.",
            "Collect result and execution metrics.",
        ],
        notes=[
            "This repository contains an adapter stub; install SecretFlow/SPU before real execution.",
            f"Task hint: {task_hint or 'not provided'}",
        ],
    )


def _crypten_plan(
    candidate: BackendCandidate,
    config: MPCProtocolConfig,
    settings: Settings,
    task_hint: str | None,
) -> ExecutionPlan:
    command = ["python", "backend_repository/crypten/run_crypten_job.py"]
    runnable = Path("backend_repository/crypten/run_crypten_job.py").exists()
    return ExecutionPlan(
        backend="crypten",
        protocol=candidate.protocol,
        runnable=runnable,
        command=command,
        environment={"CRYPTEN_PROTOCOL": candidate.protocol},
        input_artifacts=["mpc_config.json", "PyTorch model or tensor program"],
        output_artifacts=["crypten_result.json"],
        steps=[
            "Serialize current_mpc_config to backend_repository/crypten/mpc_config.json.",
            "Wrap tensors/models as CrypTen inputs.",
            "Run the CrypTen multi-process job.",
            "Collect result and execution metrics.",
        ],
        notes=[
            "This repository contains an adapter stub; install CrypTen/PyTorch before real execution.",
            f"Task hint: {task_hint or 'not provided'}",
        ],
    )


def _mp_spdz_plan(
    candidate: BackendCandidate,
    config: MPCProtocolConfig,
    settings: Settings,
    task_hint: str | None,
) -> ExecutionPlan:
    home = settings.mp_spdz_home
    compiler = str(Path(home) / "compile.py") if home else "compile.py"
    binary = f"{candidate.protocol}-party.x"
    command = ["python", compiler, "mpc_agent_program"]
    runnable = bool(home and Path(home).exists())
    return ExecutionPlan(
        backend="mp_spdz",
        protocol=candidate.protocol,
        runnable=runnable,
        command=command,
        environment={
            "MPC_AGENT_MP_SPDZ_HOME": home or "",
            "MP_SPDZ_BINARY": binary,
        },
        input_artifacts=["mpc_config.json", "Programs/Source/mpc_agent_program.mpc"],
        output_artifacts=["mp_spdz_result.json", "MP-SPDZ runtime logs"],
        steps=[
            "Serialize current_mpc_config to backend_repository/mp_spdz/mpc_config.json.",
            "Generate or select an MP-SPDZ .mpc source program.",
            f"Compile with MP-SPDZ and execute using {binary}.",
            "Collect outputs, abort status, and runtime metrics.",
        ],
        notes=[
            "Set MPC_AGENT_MP_SPDZ_HOME to a built MP-SPDZ checkout to enable real execution.",
            f"Task hint: {task_hint or 'not provided'}",
        ],
    )


def _motion_plan(
    candidate: BackendCandidate,
    config: MPCProtocolConfig,
    settings: Settings,
    task_hint: str | None,
) -> ExecutionPlan:
    command = ["python", "backend_repository/motion/run_motion_job.py", "--protocol", candidate.protocol]
    runnable = Path("backend_repository/motion/run_motion_job.py").exists()
    return ExecutionPlan(
        backend="motion",
        protocol=candidate.protocol,
        runnable=runnable,
        command=command,
        environment={"MOTION_PROTOCOL": candidate.protocol},
        input_artifacts=["mpc_config.json", "MOTION circuit/program adapter input"],
        output_artifacts=["motion_result.json"],
        steps=[
            "Serialize current_mpc_config to backend_repository/motion/mpc_config.json.",
            "Generate boolean/arithmetic or mixed MOTION workload inputs.",
            f"Run MOTION with protocol {candidate.protocol}.",
            "Collect outputs and execution statistics.",
        ],
        notes=[
            "MOTION is represented here as an engineered mixed-protocol backend adapter stub.",
            f"Task hint: {task_hint or 'not provided'}",
        ],
    )


def _scale_mamba_plan(
    candidate: BackendCandidate,
    config: MPCProtocolConfig,
    settings: Settings,
    task_hint: str | None,
) -> ExecutionPlan:
    command = ["python", "backend_repository/scale_mamba/run_scale_mamba_job.py", "--protocol", candidate.protocol]
    runnable = Path("backend_repository/scale_mamba/run_scale_mamba_job.py").exists()
    return ExecutionPlan(
        backend="scale_mamba",
        protocol=candidate.protocol,
        runnable=runnable,
        command=command,
        environment={"SCALE_MAMBA_PROTOCOL": candidate.protocol},
        input_artifacts=["mpc_config.json", "SCALE-MAMBA program input"],
        output_artifacts=["scale_mamba_result.json"],
        steps=[
            "Serialize current_mpc_config to backend_repository/scale_mamba/mpc_config.json.",
            "Generate arithmetic MPC program artifacts for SCALE-MAMBA.",
            f"Run SCALE-MAMBA using protocol {candidate.protocol}.",
            "Collect outputs, preprocessing stats, and runtime metrics.",
        ],
        notes=[
            "SCALE-MAMBA is modeled as an arithmetic/SPDZ-style backend adapter stub.",
            f"Task hint: {task_hint or 'not provided'}",
        ],
    )

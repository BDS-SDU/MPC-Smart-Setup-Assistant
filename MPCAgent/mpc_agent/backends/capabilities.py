"""Backend capability registry."""

from __future__ import annotations

from .schemas import BackendCapability


BACKEND_CAPABILITIES: dict[str, BackendCapability] = {
    "aby": BackendCapability(
        name="aby",
        display_name="ABY",
        summary="Mixed-protocol secure two-party computation backend with arithmetic, boolean, and Yao sharing.",
        strengths=[
            "Strong fit for 2PC workloads that mix arithmetic and boolean/comparison subroutines.",
            "Good choice when protocol switching between arithmetic and Yao-style circuits matters.",
        ],
        limitations=[
            "Focused on two-party computation rather than general n-party MPC.",
            "Semi-honest 2PC is the clearest fit in this selector.",
        ],
        supported_protocols=["ArithmeticSharing", "BooleanSharing", "YaoSharing", "ABY-Mixed"],
        repository_path="backend_repository/aby",
        install_hint="Build ABY and expose its demo or benchmark binaries to the execution environment.",
        docs_url="https://github.com/encryptogroup/ABY",
    ),
    "emp_sh2pc": BackendCapability(
        name="emp_sh2pc",
        display_name="EMP-sh2pc",
        summary="EMP toolkit backend for efficient semi-honest two-party computation based on garbled circuits.",
        strengths=[
            "Very strong fit for 2PC boolean, comparison, and garbled-circuit-style execution.",
            "Useful for lightweight semi-honest two-party protocol prototypes.",
        ],
        limitations=[
            "Not a broad n-party or malicious-security backend in this selector.",
            "Better for boolean/GC-style workloads than arithmetic-heavy malicious MPC.",
        ],
        supported_protocols=["Yao-GC", "SemiHonest2PC"],
        repository_path="backend_repository/emp_sh2pc",
        install_hint="Build EMP-sh2pc and make its binaries available before real execution.",
        docs_url="https://github.com/emp-toolkit/emp-sh2pc",
    ),
    "spu": BackendCapability(
        name="spu",
        display_name="SPU",
        summary="SecretFlow SPU backend for efficient secure computation on tensor/ML workloads.",
        strengths=[
            "Efficient for tensor-style arithmetic workloads and privacy-preserving ML pipelines.",
            "Good fit for 2PC/3PC semi-honest deployments with ring-based arithmetic.",
            "Integrates naturally with the SecretFlow ecosystem.",
        ],
        limitations=[
            "Not the broadest choice for malicious-security protocol research.",
            "Requires external SPU/SecretFlow runtime installation before execution.",
        ],
        supported_protocols=["SEMI2K", "ABY3", "CHEETAH"],
        repository_path="backend_repository/spu",
        install_hint="Install SecretFlow/SPU runtime and expose spu or secretflow commands.",
        docs_url="https://github.com/secretflow/spu",
    ),
    "crypten": BackendCapability(
        name="crypten",
        display_name="CrypTen",
        summary="PyTorch-oriented secure computation backend for privacy-preserving ML experiments.",
        strengths=[
            "Natural fit for PyTorch models, tensor programs, and ML inference/training prototypes.",
            "Simple choice for semi-honest ML research experiments.",
        ],
        limitations=[
            "Less suitable for malicious-security MPC protocol execution.",
            "Project is research-oriented and requires a local CrypTen/PyTorch environment.",
        ],
        supported_protocols=["CrypTen-MPC"],
        repository_path="backend_repository/crypten",
        install_hint="Install CrypTen and PyTorch in the execution environment.",
        docs_url="https://github.com/facebookresearch/CrypTen",
    ),
    "mp_spdz": BackendCapability(
        name="mp_spdz",
        display_name="MP-SPDZ",
        summary="General-purpose MPC protocol backend with broad semi-honest and malicious protocol coverage.",
        strengths=[
            "Best broad-coverage backend for protocol comparison and malicious-security settings.",
            "Supports many arithmetic, binary, ring, dishonest-majority, and honest-majority protocols.",
            "Useful when exact adversary threshold, preprocessing, and security model matter.",
        ],
        limitations=[
            "Heavier build/toolchain than the ML-oriented backends.",
            "Requires compiling MP-SPDZ and protocol-specific binaries before real execution.",
        ],
        supported_protocols=[
            "semi2k",
            "semi-bin",
            "mascot",
            "spdz2k",
            "malicious-shamir",
            "shamir",
            "replicated-ring",
            "yao",
            "lowgear",
        ],
        repository_path="backend_repository/mp_spdz",
        install_hint="Build MP-SPDZ and set MPC_AGENT_MP_SPDZ_HOME to its installation path.",
        docs_url="https://github.com/data61/MP-SPDZ",
    ),
    "motion": BackendCapability(
        name="motion",
        display_name="MOTION",
        summary="Modern secure computation framework with boolean, arithmetic, and mixed-protocol execution.",
        strengths=[
            "Good fit for engineered 2PC mixed workloads across boolean and arithmetic domains.",
            "Attractive when you want an actively engineered execution framework beyond pure research prototypes.",
        ],
        limitations=[
            "Less broad protocol coverage than MP-SPDZ for malicious-security exploration.",
            "Real execution still requires a local MOTION build and adapter integration.",
        ],
        supported_protocols=["BooleanGMW", "ArithmeticGMW", "BMR", "MOTION-Mixed"],
        repository_path="backend_repository/motion",
        install_hint="Build MOTION and configure the adapter binary paths before execution.",
        docs_url="https://github.com/encryptogroup/MOTION",
    ),
    "scale_mamba": BackendCapability(
        name="scale_mamba",
        display_name="SCALE-MAMBA",
        summary="SPDZ-style MPC backend aimed at arithmetic protocols and stronger adversary models.",
        strengths=[
            "Strong alternative for arithmetic malicious-security execution, especially SPDZ-style workflows.",
            "Useful when the protocol recommendation leans toward preprocessing-heavy arithmetic MPC.",
        ],
        limitations=[
            "Less natural than ABY or EMP for pure boolean 2PC tasks.",
            "Requires a dedicated SCALE-MAMBA installation before real execution.",
        ],
        supported_protocols=["SPDZ", "MASCOT", "Shamir"],
        repository_path="backend_repository/scale_mamba",
        install_hint="Install SCALE-MAMBA and expose the relevant runner binaries.",
        docs_url="https://github.com/KULeuven-COSIC/SCALE-MAMBA",
    ),
}


def list_capabilities() -> list[BackendCapability]:
    return list(BACKEND_CAPABILITIES.values())

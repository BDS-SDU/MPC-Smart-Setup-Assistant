"""Heuristic backend selector for MPC execution."""

from __future__ import annotations

import re

from mpc_agent.config import Settings, get_settings
from mpc_agent.normalization import normalize_config
from mpc_agent.schemas import MPCProtocolConfig

from .adapters import build_execution_plan
from .capabilities import BACKEND_CAPABILITIES, list_capabilities
from .schemas import (
    BackendCandidate,
    BackendName,
    BackendPlanRequest,
    BackendPlanResponse,
)


class BackendSelector:
    """Select an execution backend and protocol from an MPC configuration."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def capabilities(self):
        return list_capabilities()

    def plan(self, request: BackendPlanRequest) -> BackendPlanResponse:
        if request.config is None:
            raise ValueError("config is required for backend planning")

        config = normalize_config(request.config)
        candidates = sorted(
            [
                self._score_aby(config, request.task_hint),
                self._score_emp(config, request.task_hint),
                self._score_spu(config, request.task_hint),
                self._score_crypten(config, request.task_hint),
                self._score_motion(config, request.task_hint),
                self._score_scale_mamba(config, request.task_hint),
                self._score_mp_spdz(config, request.task_hint),
            ],
            key=lambda candidate: candidate.score,
            reverse=True,
        )
        selected = self._select_candidate(candidates, request.preferred_backend)
        execution_plan = build_execution_plan(
            selected,
            config,
            self.settings,
            request.task_hint,
        )
        return BackendPlanResponse(
            selected=selected,
            candidates=candidates,
            execution_plan=execution_plan,
            execution_status="planned" if not request.execute else "skipped",
        )

    def _select_candidate(
        self,
        candidates: list[BackendCandidate],
        preferred_backend: BackendName | None,
    ) -> BackendCandidate:
        if preferred_backend:
            for candidate in candidates:
                if candidate.backend == preferred_backend:
                    return candidate
        return candidates[0]

    def _score_spu(self, config: MPCProtocolConfig, task_hint: str | None) -> BackendCandidate:
        score = 0.35
        reasons: list[str] = []
        warnings: list[str] = []

        parties = config.participant_scale.number_of_parties
        behavior = config.adversary.behavior_model
        circuit = config.circuit.form
        math = config.math_structure.structure
        protocol = "SEMI2K"

        if parties in {2, 3}:
            score += 0.16
            reasons.append("SPU is efficient for common 2PC/3PC deployments.")
        if parties == 3:
            protocol = "ABY3"
            reasons.append("3-party configuration maps naturally to ABY3-style execution.")
        if behavior == "Semi-honest":
            score += 0.18
            reasons.append("Semi-honest model matches SPU's efficient execution profile.")
        elif behavior == "Malicious":
            score -= 0.22
            warnings.append("Malicious security is usually better handled by MP-SPDZ in this selector.")
        if circuit in {"Arithmetic", "Mixed"}:
            score += 0.12
            reasons.append("Arithmetic/tensor workloads are a good SPU fit.")
        if math in {"RingZ2k", "Ring", None}:
            score += 0.08
            reasons.append("Ring-style arithmetic often maps well to SPU protocols.")
        if _is_ml_task(task_hint, config):
            score += 0.12
            protocol = "CHEETAH" if parties in {None, 2} else protocol
            reasons.append("Task appears ML/tensor-oriented, where SPU is strong.")

        return self._candidate(
            "spu",
            protocol,
            score,
            reasons,
            warnings,
            "High for semi-honest tensor/arithmetic workloads; medium otherwise.",
        )

    def _score_aby(self, config: MPCProtocolConfig, task_hint: str | None) -> BackendCandidate:
        score = 0.3
        reasons: list[str] = []
        warnings: list[str] = []

        parties = config.participant_scale.number_of_parties
        behavior = config.adversary.behavior_model
        circuit = config.circuit.form
        protocol = "ABY-Mixed"

        if parties in {None, 2}:
            score += 0.2
            reasons.append("ABY is designed for efficient secure two-party computation.")
        else:
            score -= 0.16
            warnings.append("ABY is primarily a 2PC backend, so larger party counts reduce its fit.")
        if behavior == "Semi-honest":
            score += 0.14
            reasons.append("Semi-honest model aligns well with ABY's typical deployment profile.")
        elif behavior == "Malicious":
            score -= 0.18
            warnings.append("Malicious-security tasks are usually better covered by MP-SPDZ or SCALE-MAMBA.")
        if circuit == "Boolean":
            score += 0.16
            protocol = "YaoSharing"
            reasons.append("Boolean/comparison-heavy computation maps well to Yao-style sharing.")
        elif circuit == "Arithmetic":
            score += 0.09
            protocol = "ArithmeticSharing"
        elif circuit == "Mixed":
            score += 0.28
            protocol = "ABY-Mixed"
            reasons.append("Mixed arithmetic/boolean workloads are where ABY stands out.")

        return self._candidate(
            "aby",
            protocol,
            score,
            reasons,
            warnings,
            "High for 2PC mixed or boolean tasks; lower for n-party malicious MPC.",
        )

    def _score_emp(self, config: MPCProtocolConfig, task_hint: str | None) -> BackendCandidate:
        score = 0.26
        reasons: list[str] = []
        warnings: list[str] = []

        parties = config.participant_scale.number_of_parties
        behavior = config.adversary.behavior_model
        circuit = config.circuit.form

        if parties in {None, 2}:
            score += 0.19
            reasons.append("EMP-sh2pc is a strong 2PC backend candidate.")
        else:
            score -= 0.18
            warnings.append("EMP-sh2pc is focused on two-party execution.")
        if behavior == "Semi-honest":
            score += 0.14
            reasons.append("Semi-honest execution is the best fit for EMP-sh2pc.")
        elif behavior == "Malicious":
            score -= 0.22
            warnings.append("EMP-sh2pc is not the preferred malicious-security backend here.")
        if circuit in {"Boolean", "GarbledCircuit"}:
            score += 0.18
            reasons.append("Boolean and garbled-circuit workloads fit EMP-sh2pc well.")
        elif circuit == "Arithmetic":
            score -= 0.06

        return self._candidate(
            "emp_sh2pc",
            "Yao-GC",
            score,
            reasons,
            warnings,
            "High for semi-honest 2PC boolean/garbled-circuit tasks.",
        )

    def _score_crypten(self, config: MPCProtocolConfig, task_hint: str | None) -> BackendCandidate:
        score = 0.28
        reasons: list[str] = []
        warnings: list[str] = []

        if _is_ml_task(task_hint, config):
            score += 0.26
            reasons.append("CrypTen is PyTorch-oriented and fits ML/tensor experiments.")
        if config.adversary.behavior_model == "Semi-honest":
            score += 0.16
            reasons.append("Semi-honest model is the best fit for CrypTen in this selector.")
        elif config.adversary.behavior_model == "Malicious":
            score -= 0.28
            warnings.append("CrypTen is not selected for malicious-security execution.")
        if config.circuit.form in {"Arithmetic", "Mixed", None}:
            score += 0.06
        if config.participant_scale.number_of_parties and config.participant_scale.number_of_parties > 3:
            score -= 0.08
            warnings.append("Large n-party protocol exploration is usually better in MP-SPDZ.")

        return self._candidate(
            "crypten",
            "CrypTen-MPC",
            score,
            reasons,
            warnings,
            "High for PyTorch semi-honest ML prototypes; low for malicious security.",
        )

    def _score_mp_spdz(self, config: MPCProtocolConfig, task_hint: str | None) -> BackendCandidate:
        score = 0.42
        reasons: list[str] = ["MP-SPDZ has the broadest protocol coverage."]
        warnings: list[str] = []
        protocol = self._mp_spdz_protocol(config)

        if config.adversary.behavior_model == "Malicious":
            score += 0.24
            reasons.append("Malicious-security configuration favors MP-SPDZ.")
        if config.secret_sharing.scheme in {"Shamir", "Replicated", "Authenticated"}:
            score += 0.08
            reasons.append("Chosen sharing scheme is well represented by MP-SPDZ protocol families.")
        if config.preprocessing.enabled is True:
            score += 0.06
            reasons.append("Preprocessing-heavy protocols are well supported in MP-SPDZ.")
        if config.adversary.corruption_threshold:
            score += 0.05
            reasons.append("Explicit threshold is useful for MP-SPDZ protocol selection.")
        if _is_ml_task(task_hint, config) and config.adversary.behavior_model == "Semi-honest":
            score -= 0.08
            warnings.append("For pure ML/tensor semi-honest tasks, SPU or CrypTen may be faster to integrate.")

        return self._candidate(
            "mp_spdz",
            protocol,
            score,
            reasons,
            warnings,
            "Best for malicious security and protocol benchmarking; heavier setup.",
        )

    def _score_motion(self, config: MPCProtocolConfig, task_hint: str | None) -> BackendCandidate:
        score = 0.29
        reasons: list[str] = []
        warnings: list[str] = []
        protocol = "MOTION-Mixed"

        parties = config.participant_scale.number_of_parties
        behavior = config.adversary.behavior_model
        circuit = config.circuit.form

        if parties in {None, 2, 3}:
            score += 0.12
            reasons.append("MOTION fits small-party engineered secure computation deployments.")
        if behavior == "Semi-honest":
            score += 0.12
            reasons.append("Semi-honest settings align well with MOTION's practical mixed protocols.")
        elif behavior == "Malicious":
            score -= 0.1
            warnings.append("For strongly malicious settings, MP-SPDZ or SCALE-MAMBA may be safer defaults.")
        if circuit == "Boolean":
            protocol = "BooleanGMW"
            score += 0.1
        elif circuit == "Arithmetic":
            protocol = "ArithmeticGMW"
            score += 0.1
        elif circuit == "Mixed":
            protocol = "MOTION-Mixed"
            score += 0.16
            reasons.append("Mixed boolean/arithmetic tasks are a natural MOTION use case.")

        return self._candidate(
            "motion",
            protocol,
            score,
            reasons,
            warnings,
            "Good practical choice for small-party mixed workloads.",
        )

    def _score_scale_mamba(self, config: MPCProtocolConfig, task_hint: str | None) -> BackendCandidate:
        score = 0.34
        reasons: list[str] = []
        warnings: list[str] = []
        protocol = "SPDZ"

        if config.adversary.behavior_model == "Malicious":
            score += 0.2
            reasons.append("SCALE-MAMBA is a strong arithmetic malicious-security backend candidate.")
        if config.circuit.form == "Arithmetic":
            score += 0.12
            reasons.append("Arithmetic workloads align well with SCALE-MAMBA's protocol family.")
        elif config.circuit.form == "Boolean":
            score -= 0.12
            warnings.append("Pure boolean 2PC is usually better served by ABY or EMP-sh2pc.")
        if config.secret_sharing.scheme == "Shamir":
            score += 0.08
        if config.preprocessing.enabled is True:
            score += 0.07
            protocol = "MASCOT"
        if config.participant_scale.number_of_parties in {None, 2}:
            score -= 0.06
            warnings.append("SCALE-MAMBA is less obviously the best fit for small 2PC tasks.")

        return self._candidate(
            "scale_mamba",
            protocol,
            score,
            reasons,
            warnings,
            "Strong arithmetic malicious backend; narrower than MP-SPDZ.",
        )

    def _mp_spdz_protocol(self, config: MPCProtocolConfig) -> str:
        behavior = config.adversary.behavior_model
        sharing = config.secret_sharing.scheme
        math = config.math_structure.structure
        circuit = config.circuit.form
        threshold = (config.adversary.corruption_threshold or "").casefold()

        if circuit == "Boolean":
            return "yao" if config.participant_scale.number_of_parties in {None, 2} else "semi-bin"
        if behavior == "Malicious":
            if math == "RingZ2k":
                return "spdz2k"
            if sharing == "Shamir" or "n/3" in threshold:
                return "malicious-shamir"
            return "mascot"
        if math == "RingZ2k":
            return "semi2k"
        if sharing == "Replicated":
            return "replicated-ring"
        if sharing == "Shamir":
            return "shamir"
        return "semi2k"

    def _candidate(
        self,
        backend: BackendName,
        protocol: str,
        score: float,
        reasons: list[str],
        warnings: list[str],
        estimated_efficiency: str,
    ) -> BackendCandidate:
        capability = BACKEND_CAPABILITIES[backend]
        return BackendCandidate(
            backend=backend,
            display_name=capability.display_name,
            protocol=protocol,
            score=max(0, min(score, 1)),
            reasons=reasons or ["No strong matching signal; kept as fallback candidate."],
            warnings=warnings,
            estimated_efficiency=estimated_efficiency,
            capability=capability,
        )


def _is_ml_task(task_hint: str | None, config: MPCProtocolConfig) -> bool:
    text = " ".join(
        [
            task_hint or "",
            config.task_intent or "",
            config.math_structure.numeric_domain or "",
            config.recommendation.rationale or "",
            " ".join(config.assumptions),
        ]
    ).casefold()
    return bool(re.search(r"\b(ml|machine learning|inference|training|tensor|pytorch|neural|模型|推理|训练|张量)\b", text))

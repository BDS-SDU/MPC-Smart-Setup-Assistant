from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ParsedRequirement:
    raw_requirement: str
    parties: int
    operation: str
    circuit_domain: str
    security_model: str
    corruption_model: str
    latency_priority: str
    bandwidth_priority: str
    target: str
    party_count_mode: str = "auto"
    math_structure: str = "auto"
    secret_sharing: str = "auto"
    preprocessing_preference: str = "auto"
    corruption_timing: str = "auto"
    network_model: str = "auto"
    corruption_threshold: str = "auto"
    security_goal: str = "auto"
    compatibility_notes: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProtocolCandidate:
    protocol_id: str
    title: str
    score: int
    mpspdz_scripts: list[str]
    round_profile: str
    circuit_domain: str
    security_support: list[str]
    assumptions: list[str]
    reasons: list[str]
    preprocessed: bool = False
    math_structures: list[str] = field(default_factory=list)
    secret_sharing: list[str] = field(default_factory=list)
    network_models: list[str] = field(default_factory=list)
    corruption_timing_support: list[str] = field(default_factory=list)
    threshold_support: list[str] = field(default_factory=list)
    security_goals: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FinalConfiguration:
    protocol_id: str
    title: str
    mpspdz_home: str
    script_candidates: list[str]
    parties: int
    security_model: str
    corruption_model: str
    circuit_domain: str
    preprocessed: bool
    compile_options: list[str]
    source_program_name: str
    rationale: list[str]
    references: list[str]
    party_count_mode: str = "auto"
    math_structure: str = "auto"
    secret_sharing: str = "auto"
    preprocessing_preference: str = "auto"
    corruption_timing: str = "auto"
    network_model: str = "auto"
    corruption_threshold: str = "auto"
    security_goal: str = "auto"
    compatibility_notes: list[str] = field(default_factory=list)
    runner_backend: str = "mp_spdz"
    implementation_id: str = ""
    framework: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

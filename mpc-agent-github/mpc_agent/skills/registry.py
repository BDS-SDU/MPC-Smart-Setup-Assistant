from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


SKILLS_ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class SkillInfo:
    name: str
    description: str
    path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "path": str(self.path),
            "skill_md": str(self.path / "SKILL.md"),
        }


_SKILLS: tuple[SkillInfo, ...] = (
    SkillInfo(
        name="analyze_requirement",
        description="Parse natural language requirement into normalized MPC dimensions.",
        path=SKILLS_ROOT / "analyze_requirement",
    ),
    SkillInfo(
        name="select_protocol",
        description="Choose protocol candidates based on requirements, policy, and memory bias.",
        path=SKILLS_ROOT / "select_protocol",
    ),
    SkillInfo(
        name="optimize_circuit",
        description="Provide circuit-level optimization guidance for boolean/arithmetic workflows.",
        path=SKILLS_ROOT / "optimize_circuit",
    ),
    SkillInfo(
        name="generate_configuration",
        description="Generate runnable MPC configuration for target runtime (for example MP-SPDZ).",
        path=SKILLS_ROOT / "generate_configuration",
    ),
    SkillInfo(
        name="deploy_and_monitor",
        description="Compile/run MPC programs and summarize runtime diagnostics/performance.",
        path=SKILLS_ROOT / "deploy_and_monitor",
    ),
    SkillInfo(
        name="explain_decision",
        description="Explain protocol decision using references and trade-offs for engineers.",
        path=SKILLS_ROOT / "explain_decision",
    ),
    SkillInfo(
        name="simulate_threat",
        description="Qualitative threat-model simulation for the selected protocol configuration.",
        path=SKILLS_ROOT / "simulate_threat",
    ),
    SkillInfo(
        name="protocol-selection",
        description="Parse requirement and rank protocol candidates with explicit assumptions.",
        path=SKILLS_ROOT / "protocol-selection",
    ),
    SkillInfo(
        name="arithmetic-aggregation",
        description="Optimize routing for arithmetic aggregation and ML-like workloads.",
        path=SKILLS_ROOT / "arithmetic-aggregation",
    ),
    SkillInfo(
        name="boolean-comparison",
        description="Optimize routing for comparison/sorting/PSI boolean-heavy workloads.",
        path=SKILLS_ROOT / "boolean-comparison",
    ),
    SkillInfo(
        name="mpspdz-execution",
        description="Deterministic scripts for program generation, compilation, runtime, and inputs.",
        path=SKILLS_ROOT / "mpspdz-execution",
    ),
    SkillInfo(
        name="windows-mpspdz-debug",
        description="Windows/WSL focused diagnostic workflow for MP-SPDZ execution issues.",
        path=SKILLS_ROOT / "windows-mpspdz-debug",
    ),
)


def list_skills() -> list[dict[str, Any]]:
    return [skill.to_dict() for skill in _SKILLS]


def get_skill(name: str) -> dict[str, Any] | None:
    for skill in _SKILLS:
        if skill.name == name:
            return skill.to_dict()
    return None

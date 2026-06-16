"""Schemas for backend protocol selection and execution planning."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from mpc_agent.schemas import MPCProtocolConfig

BackendName = Literal[
    "spu",
    "crypten",
    "mp_spdz",
    "aby",
    "emp_sh2pc",
    "motion",
    "scale_mamba",
]


class BackendSchema(BaseModel):
    model_config = ConfigDict(extra="ignore", validate_assignment=True)


class BackendCapability(BackendSchema):
    name: BackendName
    display_name: str
    summary: str
    strengths: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    supported_protocols: list[str] = Field(default_factory=list)
    repository_path: str
    install_hint: str
    docs_url: str | None = None


class BackendCandidate(BackendSchema):
    backend: BackendName
    display_name: str
    protocol: str
    score: float = Field(ge=0, le=1)
    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    estimated_efficiency: str
    capability: BackendCapability


class ExecutionPlan(BackendSchema):
    backend: BackendName
    protocol: str
    mode: Literal["plan", "dry_run", "run"] = "plan"
    runnable: bool = False
    command: list[str] = Field(default_factory=list)
    environment: dict[str, str] = Field(default_factory=dict)
    input_artifacts: list[str] = Field(default_factory=list)
    output_artifacts: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class BackendPlanRequest(BackendSchema):
    session_id: str | None = None
    config: MPCProtocolConfig | None = None
    task_hint: str | None = Field(
        default=None,
        description="Optional workload hint such as ML inference, statistics, comparison, PSI, etc.",
    )
    preferred_backend: BackendName | None = None
    execute: bool = Field(
        default=False,
        description="Run the selected backend command if it is configured and available.",
    )


class BackendPlanResponse(BackendSchema):
    selected: BackendCandidate
    candidates: list[BackendCandidate]
    execution_plan: ExecutionPlan
    execution_status: Literal["planned", "skipped", "executed", "failed"] = "planned"
    stdout: str | None = None
    stderr: str | None = None

"""Pydantic schemas for extracted MPC protocol configuration."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class BaseSchema(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        validate_assignment=True,
        coerce_numbers_to_str=True,
    )


class ParticipantScale(BaseSchema):
    number_of_parties: int | None = Field(
        default=None,
        description="Total number of protocol participants, n.",
    )
    party_roles: list[str] = Field(
        default_factory=list,
        description="Roles such as input owner, compute party, dealer, client, server, or output receiver.",
    )
    input_owners: list[str] = Field(default_factory=list)
    compute_parties: list[str] = Field(default_factory=list)
    output_recipients: list[str] = Field(default_factory=list)
    notes: str | None = None


class CircuitConfig(BaseSchema):
    form: str | None = Field(
        default=None,
        description="Canonical circuit form: Arithmetic, Boolean, Mixed, GarbledCircuit, R1CS, etc.",
    )
    representation: str | None = Field(
        default=None,
        description="Concrete encoding such as Bristol Fashion, R1CS, bytecode, DAG, or high-level DSL.",
    )
    gate_types: list[str] = Field(default_factory=list)
    fixed_point_precision: str | None = None
    notes: str | None = None


class MathStructure(BaseSchema):
    structure: str | None = Field(
        default=None,
        description="Underlying algebraic domain: finite field, ring Z_2^k, binary field, elliptic-curve group, etc.",
    )
    modulus: str | None = Field(
        default=None,
        description="Prime p, ring size 2^k, field polynomial, or curve identifier.",
    )
    bit_length: int | None = None
    numeric_domain: str | None = Field(
        default=None,
        description="Integers, fixed point, floating point emulation, bits, vectors, tensors, etc.",
    )
    notes: str | None = None


class SecretSharingConfig(BaseSchema):
    scheme: str | None = Field(
        default=None,
        description="Canonical sharing scheme: Shamir, Additive, Replicated, Packed, Authenticated, etc.",
    )
    threshold: str | None = Field(
        default=None,
        description="Reconstruction/privacy threshold such as t < n/2 or t < n/3.",
    )
    share_domain: str | None = None
    mac_or_authentication: str | None = Field(
        default=None,
        description="MAC/authentication mechanism for malicious security, if any.",
    )
    randomness: str | None = Field(
        default=None,
        description="How random masks/shares are sampled or distributed.",
    )
    notes: str | None = None


class PreprocessingConfig(BaseSchema):
    enabled: bool | None = Field(
        default=None,
        description="Whether the protocol has an offline/preprocessing phase.",
    )
    materials: list[str] = Field(
        default_factory=list,
        description="Beaver triples, random bits, edaBits, daBits, multiplication triples, OT correlations, etc.",
    )
    generation_method: str | None = Field(
        default=None,
        description="Trusted dealer, OT extension, somewhat homomorphic encryption, HE, sacrifice checks, etc.",
    )
    offline_online_split: str | None = None
    notes: str | None = None


class AdversaryConfig(BaseSchema):
    behavior_model: str | None = Field(
        default=None,
        description="Canonical adversary behavior: Semi-honest, Malicious, Covert, Rational, Fail-stop.",
    )
    corruption_strategy: str | None = Field(
        default=None,
        description="Canonical corruption strategy: Static, Adaptive, Mobile, Rushing, Non-rushing, SelectiveAbort.",
    )
    corruption_threshold: str | None = Field(
        default=None,
        description="Maximum corrupted parties, for example t < n/2, t < n/3, honest majority, dishonest majority.",
    )
    corruption_scope: str | None = Field(
        default=None,
        description="Which parties may be corrupted and whether input/output clients are included.",
    )
    notes: str | None = None


class NetworkConfig(BaseSchema):
    synchrony: str | None = Field(
        default=None,
        description="Canonical synchrony model: Synchronous, Asynchronous, PartialSynchrony, WAN, LAN.",
    )
    channels: str | None = Field(
        default=None,
        description="Authenticated channels, private channels, PKI/TLS, broadcast channel, bulletin board, etc.",
    )
    topology: str | None = Field(
        default=None,
        description="Point-to-point, star, committee, client-server, full mesh, etc.",
    )
    broadcast: str | None = None
    latency_or_bandwidth_notes: str | None = None


class SecurityGoalConfig(BaseSchema):
    privacy: str | None = None
    correctness: str | None = None
    robustness: str | None = None
    fairness: str | None = None
    guaranteed_output_delivery: str | None = None
    composability: str | None = Field(
        default=None,
        description="Standalone, sequential, UC, simulation-based, etc.",
    )
    leakage: str | None = Field(
        default=None,
        description="Allowed leakage such as party count, circuit size, abort bit, output length, etc.",
    )
    notes: str | None = None


class ProtocolRecommendation(BaseSchema):
    family: str | None = Field(
        default=None,
        description="Candidate protocol family: BGW, GMW, SPDZ, MASCOT, ABY3, BMR, Yao, replicated sharing, etc.",
    )
    rationale: str | None = None
    tradeoffs: list[str] = Field(default_factory=list)
    implementation_targets: list[str] = Field(
        default_factory=list,
        description="Possible downstream targets such as MP-SPDZ, SCALE-MAMBA, EMP-toolkit, ABY, custom compiler.",
    )


class MPCProtocolConfig(BaseSchema):
    schema_version: str = "0.1"
    task_intent: str | None = Field(
        default=None,
        description="User-level goal for the MPC application or function.",
    )
    participant_scale: ParticipantScale = Field(default_factory=ParticipantScale)
    circuit: CircuitConfig = Field(default_factory=CircuitConfig)
    math_structure: MathStructure = Field(default_factory=MathStructure)
    secret_sharing: SecretSharingConfig = Field(default_factory=SecretSharingConfig)
    preprocessing: PreprocessingConfig = Field(default_factory=PreprocessingConfig)
    adversary: AdversaryConfig = Field(default_factory=AdversaryConfig)
    network: NetworkConfig = Field(default_factory=NetworkConfig)
    security_goals: SecurityGoalConfig = Field(default_factory=SecurityGoalConfig)
    recommendation: ProtocolRecommendation = Field(default_factory=ProtocolRecommendation)
    canonical_parameters: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Flat canonical parameter mapping for downstream systems, for example "
            "adversary_behavior=Malicious, circuit_form=Arithmetic."
        ),
    )
    assumptions: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    confidence: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Overall confidence in the extracted configuration.",
    )

    @field_validator("confidence", mode="before")
    @classmethod
    def parse_confidence(cls, value: Any) -> Any:
        if isinstance(value, str):
            lowered = value.strip().casefold()
            if lowered in {"high", "高", "较高"}:
                return 0.85
            if lowered in {"medium", "中", "中等"}:
                return 0.6
            if lowered in {"low", "低", "较低"}:
                return 0.35
            if lowered.endswith("%"):
                try:
                    return float(lowered.rstrip("%")) / 100
                except ValueError:
                    return None
        return value


class MPCDraftResponse(BaseSchema):
    config: MPCProtocolConfig = Field(default_factory=MPCProtocolConfig)
    summary: str = Field(
        default="",
        description="Short Chinese summary of the updated MPC configuration.",
    )
    missing_fields: list[str] = Field(
        default_factory=list,
        description="Important fields still missing or ambiguous.",
    )
    clarifying_questions: list[str] = Field(
        default_factory=list,
        description="Questions to ask the user before finalizing a runnable protocol.",
    )
    next_actions: list[str] = Field(
        default_factory=list,
        description="Suggested implementation or design steps.",
    )


class AgentReply(BaseSchema):
    message: str = Field(
        default="",
        description="Natural-language Chinese reply to the user.",
    )
    missing_fields: list[str] = Field(
        default_factory=list,
        description="Important fields still missing or ambiguous.",
    )
    clarifying_questions: list[str] = Field(
        default_factory=list,
        description="Questions to ask the user before finalizing a runnable protocol.",
    )
    next_actions: list[str] = Field(
        default_factory=list,
        description="Suggested implementation or design steps.",
    )


class MPCStructuredOutput(BaseSchema):
    current_mpc_config: MPCProtocolConfig = Field(
        default_factory=MPCProtocolConfig,
        description="Complete hidden form state after this user turn.",
    )
    agent_reply: AgentReply = Field(
        default_factory=AgentReply,
        description="Conversation-facing reply and next-step metadata.",
    )

    @model_validator(mode="before")
    @classmethod
    def coerce_agent_reply(cls, data: Any) -> Any:
        if isinstance(data, dict) and isinstance(data.get("agent_reply"), str):
            data = dict(data)
            data["agent_reply"] = {"message": data["agent_reply"]}
        return data


class MPCStructuredOptions(BaseSchema):
    participant_scale: str | None = Field(
        default=None,
        description="2-party, 3-party, n-party, or auto.",
    )
    number_of_parties: int | None = Field(default=None, ge=2)
    circuit_form: str | None = Field(
        default=None,
        description="Arithmetic, Boolean, Mixed, GarbledCircuit, R1CS, or auto.",
    )
    math_structure: str | None = Field(
        default=None,
        description="PrimeField, FiniteField, RingZ2k, BinaryField, or auto.",
    )
    secret_sharing: str | None = Field(
        default=None,
        description="Shamir, Additive, Replicated, Authenticated, or auto.",
    )
    preprocessing: str | None = Field(
        default=None,
        description="Required, None, or auto.",
    )
    adversary_behavior: str | None = Field(
        default=None,
        description="Semi-honest, Malicious, Covert, Rational, Fail-stop, or auto.",
    )
    corruption_strategy: str | None = Field(
        default=None,
        description="Static, Adaptive, Mobile, Rushing, Non-rushing, or auto.",
    )
    network_model: str | None = Field(
        default=None,
        description="Synchronous, Asynchronous, PartialSynchrony, WAN, LAN, or auto.",
    )
    channel_model: str | None = Field(
        default=None,
        description="Authenticated channels, Private channels, TLS channels, or auto.",
    )
    corruption_threshold: str | None = Field(
        default=None,
        description="t < n/2, t < n/3, t=1, honest majority, dishonest majority, or auto.",
    )
    security_goal: str | None = Field(
        default=None,
        description="PrivacyCorrectness, Abort, GuaranteedOutputDelivery, Fairness, Robustness, or auto.",
    )

    def has_values(self) -> bool:
        data = self.model_dump()
        return any(value not in (None, "", "auto", "Auto", []) for value in data.values())


class ChatRequest(BaseSchema):
    message: str = Field(default="")
    session_id: str | None = Field(
        default=None,
        description="Conversation/session id. Omit to create a new session.",
    )
    reset: bool = Field(
        default=False,
        description="Reset the session before processing this message.",
    )
    structured_options: MPCStructuredOptions | None = Field(
        default=None,
        description="Optional explicit MPC option selections. These override conflicting natural-language text.",
    )

    @model_validator(mode="after")
    def require_message_or_options(self) -> "ChatRequest":
        if self.message.strip():
            return self
        if self.structured_options and self.structured_options.has_values():
            return self
        raise ValueError("message or structured_options is required")


class ChatResponse(MPCDraftResponse):
    session_id: str
    current_mpc_config: MPCProtocolConfig = Field(default_factory=MPCProtocolConfig)
    agent_reply: AgentReply = Field(default_factory=AgentReply)


REQUIRED_CONFIG_PATHS = (
    "participant_scale.number_of_parties",
    "circuit.form",
    "math_structure.structure",
    "secret_sharing.scheme",
    "preprocessing.enabled",
    "adversary.behavior_model",
    "adversary.corruption_strategy",
    "adversary.corruption_threshold",
    "network.synchrony",
    "security_goals.privacy",
    "security_goals.correctness",
)


def read_path(data: BaseModel, path: str) -> Any:
    value: Any = data
    for part in path.split("."):
        value = getattr(value, part, None)
        if value is None:
            return None
    return value


def find_missing_fields(config: MPCProtocolConfig) -> list[str]:
    missing: list[str] = []
    for path in REQUIRED_CONFIG_PATHS:
        value = read_path(config, path)
        if value is None or value == "" or value == []:
            missing.append(path)
    return missing

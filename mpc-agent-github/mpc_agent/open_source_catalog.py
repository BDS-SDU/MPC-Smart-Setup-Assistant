from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .models import ParsedRequirement


SECURITY_LEVELS = {
    "semi_honest": 1,
    "covert": 2,
    "malicious": 3,
}

THRESHOLD_LEVELS = {
    "t_lt_n_over_3": 1,
    "t_lt_n_over_2": 2,
    "t_lt_n": 3,
}

MATURITY_SCORES = {
    "frontier": 7,
    "active": 5,
    "research_code": 2,
    "prototype": 0,
    "legacy": -2,
    "archived": -6,
}


@dataclass(frozen=True)
class OpenSourceDeployment:
    implementation_id: str
    name: str
    framework: str
    protocol_family: str
    repo_url: str
    reference_urls: list[str]
    runner_backend: str
    maturity: str
    selection_priority: int
    party_count_modes: list[str]
    circuit_domains: list[str]
    security_models: list[str]
    corruption_models: list[str]
    corruption_timing_support: list[str] = field(default_factory=lambda: ["static"])
    network_models: list[str] = field(default_factory=lambda: ["synchronous"])
    corruption_thresholds: list[str] = field(default_factory=list)
    math_structures: list[str] = field(default_factory=list)
    secret_sharing: list[str] = field(default_factory=list)
    preprocessing_support: list[str] = field(default_factory=list)
    security_goals: list[str] = field(default_factory=lambda: ["security_with_abort"])
    target_workloads: list[str] = field(default_factory=lambda: ["generic"])
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ResearchGap:
    gap_id: str
    attribute_group: str
    attribute_value: str
    summary: str
    status: str
    reference_urls: list[str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


DEPLOYMENTS: list[OpenSourceDeployment] = [
    OpenSourceDeployment(
        implementation_id="mp_spdz_mascot",
        name="MP-SPDZ MASCOT",
        framework="MP-SPDZ",
        protocol_family="SPDZ/MASCOT",
        repo_url="https://github.com/data61/MP-SPDZ",
        reference_urls=[
            "https://github.com/data61/MP-SPDZ",
            "https://mp-spdz.readthedocs.io/en/latest/readme.html",
        ],
        runner_backend="mp_spdz",
        maturity="frontier",
        selection_priority=9,
        party_count_modes=["two_party", "three_party", "n_party"],
        circuit_domains=["arithmetic"],
        security_models=["malicious"],
        corruption_models=["dishonest_majority"],
        corruption_thresholds=["t_lt_n"],
        math_structures=["finite_field"],
        secret_sharing=["additive"],
        preprocessing_support=["required"],
        security_goals=["security_with_abort"],
        target_workloads=["generic", "aggregation", "ml"],
        notes=[
            "General-purpose malicious arithmetic stack with broad MP-SPDZ ecosystem support.",
            "Best suited when you want a runnable open-source baseline rather than a niche benchmark artifact.",
        ],
    ),
    OpenSourceDeployment(
        implementation_id="mp_spdz_semi2k",
        name="MP-SPDZ Semi2k",
        framework="MP-SPDZ",
        protocol_family="Semi2k",
        repo_url="https://github.com/data61/MP-SPDZ",
        reference_urls=[
            "https://github.com/data61/MP-SPDZ",
            "https://mp-spdz.readthedocs.io/en/latest/readme.html",
        ],
        runner_backend="mp_spdz",
        maturity="frontier",
        selection_priority=8,
        party_count_modes=["two_party", "three_party", "n_party"],
        circuit_domains=["arithmetic"],
        security_models=["semi_honest"],
        corruption_models=["dishonest_majority"],
        corruption_thresholds=["t_lt_n"],
        math_structures=["ring"],
        secret_sharing=["additive"],
        preprocessing_support=["required"],
        security_goals=["security_with_abort"],
        target_workloads=["generic", "aggregation", "ml"],
        notes=[
            "Semi-honest dishonest-majority arithmetic over rings using MP-SPDZ's Semi2k runtime path.",
            "This is the MP-SPDZ-backed Semi2k option used by the local `semi2k` protocol profile.",
        ],
    ),
    OpenSourceDeployment(
        implementation_id="mp_spdz_spdz2k",
        name="MP-SPDZ SPDZ2k",
        framework="MP-SPDZ",
        protocol_family="SPDZ2k",
        repo_url="https://github.com/data61/MP-SPDZ",
        reference_urls=[
            "https://github.com/data61/MP-SPDZ",
            "https://mp-spdz.readthedocs.io/en/latest/readme.html",
        ],
        runner_backend="mp_spdz",
        maturity="frontier",
        selection_priority=8,
        party_count_modes=["two_party", "three_party", "n_party"],
        circuit_domains=["arithmetic"],
        security_models=["malicious"],
        corruption_models=["dishonest_majority"],
        corruption_thresholds=["t_lt_n"],
        math_structures=["ring"],
        secret_sharing=["additive"],
        preprocessing_support=["required"],
        security_goals=["security_with_abort"],
        target_workloads=["generic", "aggregation", "ml"],
        notes=[
            "Ring-based malicious dishonest-majority arithmetic implementation.",
        ],
    ),
    OpenSourceDeployment(
        implementation_id="mp_spdz_yao",
        name="MP-SPDZ Yao",
        framework="MP-SPDZ",
        protocol_family="Yao Garbled Circuits",
        repo_url="https://github.com/data61/MP-SPDZ",
        reference_urls=[
            "https://github.com/data61/MP-SPDZ",
            "https://mp-spdz.readthedocs.io/en/latest/readme.html",
        ],
        runner_backend="mp_spdz",
        maturity="active",
        selection_priority=7,
        party_count_modes=["two_party"],
        circuit_domains=["boolean"],
        security_models=["semi_honest"],
        corruption_models=["dishonest_majority"],
        corruption_thresholds=["t_lt_n"],
        preprocessing_support=["disallowed"],
        security_goals=["security_with_abort"],
        target_workloads=["generic", "comparison"],
        notes=[
            "Conservative classification based on the current MP-SPDZ protocol table, which lists Yao under semi-honest dishonest-majority garbling.",
        ],
    ),
    OpenSourceDeployment(
        implementation_id="mp_spdz_shamir",
        name="MP-SPDZ Shamir",
        framework="MP-SPDZ",
        protocol_family="Shamir/BGW-style sharing",
        repo_url="https://github.com/data61/MP-SPDZ",
        reference_urls=[
            "https://github.com/data61/MP-SPDZ",
            "https://mp-spdz.readthedocs.io/en/latest/readme.html",
        ],
        runner_backend="mp_spdz",
        maturity="active",
        selection_priority=7,
        party_count_modes=["three_party", "n_party"],
        circuit_domains=["arithmetic"],
        security_models=["semi_honest", "malicious"],
        corruption_models=["honest_majority"],
        corruption_thresholds=["t_lt_n_over_2"],
        math_structures=["finite_field"],
        secret_sharing=["shamir"],
        preprocessing_support=["disallowed"],
        security_goals=["security_with_abort"],
        target_workloads=["generic", "aggregation"],
        notes=[
            "Honest-majority arithmetic option when users explicitly want Shamir sharing over fields.",
        ],
    ),
    OpenSourceDeployment(
        implementation_id="mp_spdz_sy_rep3",
        name="MP-SPDZ SY/SPDZ-wise Replicated 3PC",
        framework="MP-SPDZ",
        protocol_family="SY/SPDZ-wise replicated sharing",
        repo_url="https://github.com/data61/MP-SPDZ",
        reference_urls=[
            "https://github.com/data61/MP-SPDZ",
            "https://mp-spdz.readthedocs.io/en/latest/readme.html",
        ],
        runner_backend="mp_spdz",
        maturity="frontier",
        selection_priority=9,
        party_count_modes=["three_party"],
        circuit_domains=["arithmetic"],
        security_models=["malicious"],
        corruption_models=["honest_majority"],
        corruption_thresholds=["t_lt_n_over_2"],
        math_structures=["ring"],
        secret_sharing=["replicated"],
        security_goals=["security_with_abort"],
        target_workloads=["generic", "aggregation", "ml"],
        notes=[
            "MP-SPDZ documents SY/SPDZ-wise as the most efficient malicious honest-majority three-party option in its stack.",
        ],
    ),
    OpenSourceDeployment(
        implementation_id="motion_mixed",
        name="MOTION",
        framework="MOTION",
        protocol_family="Mixed-protocol GMW/BMR",
        repo_url="https://github.com/encryptogroup/MOTION",
        reference_urls=[
            "https://github.com/encryptogroup/MOTION",
            "https://eprint.iacr.org/2020/1137",
        ],
        runner_backend="external",
        maturity="research_code",
        selection_priority=7,
        party_count_modes=["two_party", "three_party", "n_party"],
        circuit_domains=["mixed"],
        security_models=["semi_honest"],
        corruption_models=["dishonest_majority"],
        corruption_thresholds=["t_lt_n"],
        preprocessing_support=["required"],
        security_goals=["security_with_abort"],
        target_workloads=["generic", "comparison"],
        notes=[
            "Official paper instantiates arithmetic GMW, Boolean GMW, OT-based BMR, and efficient conversions.",
            "Repository explicitly labels the code experimental and not for productive use.",
        ],
    ),
    OpenSourceDeployment(
        implementation_id="aby_mixed",
        name="ABY",
        framework="ABY",
        protocol_family="Mixed arithmetic/boolean/Yao 2PC",
        repo_url="https://github.com/encryptogroup/ABY",
        reference_urls=[
            "https://github.com/encryptogroup/ABY",
        ],
        runner_backend="external",
        maturity="research_code",
        selection_priority=7,
        party_count_modes=["two_party"],
        circuit_domains=["mixed"],
        security_models=["semi_honest"],
        corruption_models=["dishonest_majority"],
        corruption_thresholds=["t_lt_n"],
        preprocessing_support=["required"],
        security_goals=["security_with_abort"],
        target_workloads=["generic", "comparison"],
        notes=[
            "ABY mixes arithmetic sharing, boolean sharing, and Yao garbling with efficient conversions.",
            "The official repository labels it experimental and not for productive use.",
        ],
    ),
    OpenSourceDeployment(
        implementation_id="emp_sh2pc",
        name="EMP-sh2pc",
        framework="EMP Toolkit",
        protocol_family="Semi-honest garbled-circuit 2PC",
        repo_url="https://github.com/emp-toolkit/emp-sh2pc",
        reference_urls=[
            "https://github.com/emp-toolkit/emp-sh2pc",
            "https://github.com/emp-toolkit",
        ],
        runner_backend="external",
        maturity="active",
        selection_priority=8,
        party_count_modes=["two_party"],
        circuit_domains=["boolean"],
        security_models=["semi_honest"],
        corruption_models=["dishonest_majority"],
        corruption_thresholds=["t_lt_n"],
        preprocessing_support=["disallowed"],
        security_goals=["security_with_abort"],
        target_workloads=["generic", "comparison"],
        notes=[
            "Active EMP organization shows ongoing maintenance across the toolkit family.",
        ],
    ),
    OpenSourceDeployment(
        implementation_id="emp_ag2pc",
        name="EMP-ag2pc",
        framework="EMP Toolkit",
        protocol_family="Authenticated garbling 2PC",
        repo_url="https://github.com/emp-toolkit/emp-ag2pc",
        reference_urls=[
            "https://github.com/emp-toolkit/emp-ag2pc",
            "https://github.com/emp-toolkit",
        ],
        runner_backend="external",
        maturity="active",
        selection_priority=8,
        party_count_modes=["two_party"],
        circuit_domains=["boolean"],
        security_models=["malicious"],
        corruption_models=["dishonest_majority"],
        corruption_thresholds=["t_lt_n"],
        security_goals=["security_with_abort"],
        target_workloads=["generic", "comparison"],
        notes=[
            "Good fit when the user explicitly wants malicious 2PC over boolean circuits.",
        ],
    ),
    OpenSourceDeployment(
        implementation_id="emp_agmpc",
        name="EMP-agmpc",
        framework="EMP Toolkit",
        protocol_family="Global-scale garbled MPC",
        repo_url="https://github.com/emp-toolkit/emp-agmpc",
        reference_urls=[
            "https://github.com/emp-toolkit/emp-agmpc",
            "https://eprint.iacr.org/2017/189",
            "https://github.com/emp-toolkit",
        ],
        runner_backend="external",
        maturity="active",
        selection_priority=7,
        party_count_modes=["three_party", "n_party"],
        circuit_domains=["boolean"],
        security_models=["malicious"],
        corruption_models=["dishonest_majority"],
        corruption_thresholds=["t_lt_n"],
        preprocessing_support=["required"],
        security_goals=["security_with_abort"],
        target_workloads=["generic", "comparison"],
        notes=[
            "Official paper targets arbitrary malicious corruptions and large-scale boolean MPC.",
        ],
    ),
    OpenSourceDeployment(
        implementation_id="honeybadgermpc",
        name="HoneyBadgerMPC",
        framework="HoneyBadgerMPC",
        protocol_family="Asynchronous robust MPC",
        repo_url="https://github.com/initc3/HoneyBadgerMPC",
        reference_urls=[
            "https://github.com/initc3/HoneyBadgerMPC",
        ],
        runner_backend="external",
        maturity="prototype",
        selection_priority=9,
        party_count_modes=["three_party", "n_party"],
        circuit_domains=["arithmetic"],
        security_models=["malicious"],
        corruption_models=["honest_majority"],
        corruption_timing_support=["static"],
        network_models=["asynchronous"],
        corruption_thresholds=["t_lt_n_over_3"],
        math_structures=["finite_field"],
        security_goals=["guaranteed_output_delivery"],
        target_workloads=["generic", "blockchain"],
        notes=[
            "Official repository calls it the first MPC toolkit to provide guaranteed output despite Byzantine faults.",
            "The same repository also labels it a research prototype rather than production-ready code.",
        ],
    ),
    OpenSourceDeployment(
        implementation_id="aby3_framework",
        name="ABY3 Framework",
        framework="ABY3",
        protocol_family="Mixed 3PC for ML and databases",
        repo_url="https://github.com/ladnir/aby3",
        reference_urls=[
            "https://github.com/ladnir/aby3",
            "https://eprint.iacr.org/2018/403",
        ],
        runner_backend="external",
        maturity="research_code",
        selection_priority=8,
        party_count_modes=["three_party"],
        circuit_domains=["mixed"],
        security_models=["semi_honest"],
        corruption_models=["honest_majority"],
        corruption_thresholds=["t_lt_n_over_2"],
        math_structures=["ring"],
        secret_sharing=["replicated"],
        security_goals=["security_with_abort"],
        target_workloads=["ml", "aggregation"],
        notes=[
            "Official paper describes efficient switching among arithmetic, binary, and Yao 3PC.",
            "Repository warns that the code is not fully secure and should be treated as proof-of-concept or benchmarking code.",
        ],
    ),
    OpenSourceDeployment(
        implementation_id="spu_aby3",
        name="SecretFlow SPU ABY3",
        framework="SecretFlow SPU",
        protocol_family="ABY3 runtime in SPU",
        repo_url="https://github.com/secretflow/spu",
        reference_urls=[
            "https://github.com/secretflow/spu",
            "https://secretflow.readthedocs.io/en/stable/developer/design/spu.html",
        ],
        runner_backend="secretflow_spu",
        maturity="active",
        selection_priority=8,
        party_count_modes=["three_party"],
        circuit_domains=["mixed"],
        security_models=["semi_honest"],
        corruption_models=["honest_majority"],
        corruption_thresholds=["t_lt_n_over_2"],
        math_structures=["ring"],
        secret_sharing=["replicated"],
        security_goals=["security_with_abort"],
        target_workloads=["ml", "aggregation"],
        notes=[
            "SecretFlow SPU positions ABY3 as its honest-majority 3PC option for privacy-preserving applications.",
        ],
    ),
    OpenSourceDeployment(
        implementation_id="spu_semi2k",
        name="SecretFlow SPU Semi2k",
        framework="SecretFlow SPU",
        protocol_family="Semi2k-style runtime in SPU",
        repo_url="https://github.com/secretflow/spu",
        reference_urls=[
            "https://github.com/secretflow/spu",
            "https://secretflow.readthedocs.io/en/stable/developer/design/spu.html",
        ],
        runner_backend="secretflow_spu",
        maturity="prototype",
        selection_priority=4,
        party_count_modes=["two_party", "three_party", "n_party"],
        circuit_domains=["arithmetic"],
        security_models=["semi_honest"],
        corruption_models=["dishonest_majority"],
        corruption_thresholds=["t_lt_n"],
        math_structures=["ring"],
        preprocessing_support=["required"],
        security_goals=["security_with_abort"],
        target_workloads=["generic", "aggregation", "ml"],
        notes=[
            "SecretFlow docs say the current SPU Semi2k mode relies on a trusted party for offline randomness and should be used for debugging purposes only.",
        ],
    ),
    OpenSourceDeployment(
        implementation_id="spu_cheetah",
        name="SecretFlow SPU Cheetah",
        framework="SecretFlow SPU",
        protocol_family="Cheetah 2PC",
        repo_url="https://github.com/secretflow/spu",
        reference_urls=[
            "https://github.com/secretflow/spu",
            "https://secretflow.readthedocs.io/en/stable/developer/design/spu.html",
        ],
        runner_backend="secretflow_spu",
        maturity="active",
        selection_priority=9,
        party_count_modes=["two_party"],
        circuit_domains=["mixed"],
        security_models=["semi_honest"],
        corruption_models=["dishonest_majority"],
        corruption_thresholds=["t_lt_n"],
        math_structures=["ring"],
        security_goals=["security_with_abort"],
        target_workloads=["ml", "comparison"],
        notes=[
            "SecretFlow docs describe Cheetah as a fast semi-honest 2PC protocol.",
        ],
    ),
    OpenSourceDeployment(
        implementation_id="crypten_tensor",
        name="CrypTen Tensor MPC",
        framework="CrypTen",
        protocol_family="Encrypted tensor MPC runtime",
        repo_url="https://github.com/facebookresearch/CrypTen",
        reference_urls=[
            "https://github.com/facebookresearch/CrypTen",
        ],
        runner_backend="crypten",
        maturity="research_code",
        selection_priority=8,
        party_count_modes=["two_party", "three_party", "n_party"],
        circuit_domains=["arithmetic", "mixed"],
        security_models=["semi_honest"],
        corruption_models=["dishonest_majority"],
        corruption_thresholds=["t_lt_n"],
        math_structures=["ring"],
        secret_sharing=["additive"],
        preprocessing_support=["disallowed"],
        security_goals=["security_with_abort"],
        target_workloads=["ml", "aggregation", "comparison"],
        notes=[
            "CrypTen is a practical encrypted-tensor stack for privacy-preserving ML style workloads.",
            "This backend is routed through an isolated Python environment instead of the MP-SPDZ toolchain.",
        ],
    ),
    OpenSourceDeployment(
        implementation_id="crypten_semi2k",
        name="CrypTen Semi2k-style Tensor MPC",
        framework="CrypTen",
        protocol_family="Semi2k-style additive ring sharing",
        repo_url="https://github.com/facebookresearch/CrypTen",
        reference_urls=[
            "https://github.com/facebookresearch/CrypTen",
        ],
        runner_backend="crypten",
        maturity="research_code",
        selection_priority=6,
        party_count_modes=["two_party", "three_party", "n_party"],
        circuit_domains=["arithmetic"],
        security_models=["semi_honest"],
        corruption_models=["dishonest_majority"],
        corruption_thresholds=["t_lt_n"],
        math_structures=["ring"],
        secret_sharing=["additive"],
        preprocessing_support=["disallowed"],
        security_goals=["security_with_abort"],
        target_workloads=["generic", "aggregation", "ml"],
        notes=[
            "CrypTen uses additive encrypted tensor sharing over ring-like tensor values; this catalog entry exposes it as a Semi2k-style backend.",
            "Use this when callers explicitly want the Semi2k family but need the CrypTen runner.",
        ],
    ),
    OpenSourceDeployment(
        implementation_id="ezpc_porthos",
        name="EzPC Porthos",
        framework="EzPC",
        protocol_family="Porthos 3PC",
        repo_url="https://github.com/mpc-msri/EzPC",
        reference_urls=[
            "https://github.com/mpc-msri/EzPC",
        ],
        runner_backend="external",
        maturity="research_code",
        selection_priority=7,
        party_count_modes=["three_party"],
        circuit_domains=["arithmetic"],
        security_models=["semi_honest"],
        corruption_models=["honest_majority"],
        corruption_thresholds=["t_lt_n_over_2"],
        target_workloads=["ml", "aggregation"],
        notes=[
            "EzPC repository describes Porthos as a semi-honest 3-party protocol geared toward TensorFlow-like applications.",
        ],
    ),
    OpenSourceDeployment(
        implementation_id="ezpc_sci",
        name="EzPC SCI",
        framework="EzPC",
        protocol_family="SCI 2PC inference library",
        repo_url="https://github.com/mpc-msri/EzPC",
        reference_urls=[
            "https://github.com/mpc-msri/EzPC",
        ],
        runner_backend="external",
        maturity="research_code",
        selection_priority=8,
        party_count_modes=["two_party"],
        circuit_domains=["arithmetic"],
        security_models=["semi_honest"],
        corruption_models=["dishonest_majority"],
        corruption_thresholds=["t_lt_n"],
        target_workloads=["ml", "aggregation"],
        notes=[
            "EzPC repository describes SCI as a semi-honest 2PC library for secure fixed-point inference and floating-point computation.",
        ],
    ),
    OpenSourceDeployment(
        implementation_id="fresco_tinytables",
        name="FRESCO TinyTables",
        framework="FRESCO",
        protocol_family="TinyTables",
        repo_url="https://github.com/aicis/fresco",
        reference_urls=[
            "https://github.com/aicis/fresco",
            "https://fresco.readthedocs.io/en/latest/protocol_suites.html",
        ],
        runner_backend="external",
        maturity="active",
        selection_priority=6,
        party_count_modes=["two_party"],
        circuit_domains=["boolean"],
        security_models=["semi_honest"],
        corruption_models=["dishonest_majority"],
        corruption_thresholds=["t_lt_n"],
        preprocessing_support=["required"],
        security_goals=["security_with_abort"],
        target_workloads=["generic", "comparison"],
        notes=[
            "TinyTables is FRESCO's documented boolean 2PC suite.",
        ],
    ),
    OpenSourceDeployment(
        implementation_id="fresco_spdz",
        name="FRESCO SPDZ",
        framework="FRESCO",
        protocol_family="SPDZ",
        repo_url="https://github.com/aicis/fresco",
        reference_urls=[
            "https://github.com/aicis/fresco",
            "https://fresco.readthedocs.io/en/latest/protocol_suites.html",
        ],
        runner_backend="external",
        maturity="active",
        selection_priority=7,
        party_count_modes=["two_party", "three_party", "n_party"],
        circuit_domains=["arithmetic"],
        security_models=["malicious"],
        corruption_models=["dishonest_majority"],
        corruption_thresholds=["t_lt_n"],
        math_structures=["finite_field"],
        secret_sharing=["additive"],
        preprocessing_support=["required"],
        security_goals=["security_with_abort"],
        target_workloads=["generic", "aggregation"],
        notes=[
            "FRESCO docs expose SPDZ as its malicious arithmetic suite for two or more parties.",
        ],
    ),
    OpenSourceDeployment(
        implementation_id="fresco_spdz2k",
        name="FRESCO SPDZ2k",
        framework="FRESCO",
        protocol_family="SPDZ2k",
        repo_url="https://github.com/aicis/fresco",
        reference_urls=[
            "https://github.com/aicis/fresco",
            "https://fresco.readthedocs.io/en/latest/protocol_suites.html",
        ],
        runner_backend="external",
        maturity="active",
        selection_priority=8,
        party_count_modes=["two_party", "three_party", "n_party"],
        circuit_domains=["arithmetic"],
        security_models=["malicious"],
        corruption_models=["dishonest_majority"],
        corruption_thresholds=["t_lt_n"],
        math_structures=["ring"],
        secret_sharing=["additive"],
        preprocessing_support=["required"],
        security_goals=["security_with_abort"],
        target_workloads=["generic", "aggregation", "ml"],
        notes=[
            "FRESCO docs describe SPDZ2k as the ring-based malicious arithmetic suite.",
        ],
    ),
]


RESEARCH_GAPS: list[ResearchGap] = [
    ResearchGap(
        gap_id="adaptive_generic_mpc",
        attribute_group="corruption_timing",
        attribute_value="adaptive",
        summary=(
            "Targeted official-repository search did not surface a maintained, general-purpose open-source MPC "
            "deployment with explicit adaptive-corruption support across the broader option set."
        ),
        status="theory_only_or_no_clear_maintained_oss",
        reference_urls=[
            "https://github.com/data61/MP-SPDZ",
            "https://github.com/initc3/HoneyBadgerMPC",
            "https://github.com/aicis/fresco",
        ],
    ),
]


def list_open_source_deployments() -> list[dict[str, object]]:
    return [deployment.to_dict() for deployment in DEPLOYMENTS]


def list_research_gaps() -> list[dict[str, object]]:
    return [gap.to_dict() for gap in RESEARCH_GAPS]


def catalog_summary() -> dict[str, int]:
    return {
        "deployment_count": len(DEPLOYMENTS),
        "research_gap_count": len(RESEARCH_GAPS),
    }


def _supports_security(required: str, supported: list[str]) -> bool:
    if required == "auto":
        return True
    required_level = SECURITY_LEVELS.get(required, 0)
    return any(SECURITY_LEVELS.get(item, 0) >= required_level for item in supported)


def _supports_corruption_model(required: str, supported: list[str]) -> bool:
    support_set = set(supported)
    if required == "honest_majority":
        return "honest_majority" in support_set or "dishonest_majority" in support_set
    return "dishonest_majority" in support_set


def _supports_party_mode(required: str, parties: int, supported: list[str]) -> bool:
    _ = required
    support_set = set(supported)
    if parties == 2:
        return "two_party" in support_set
    if parties == 3:
        return "three_party" in support_set or "n_party" in support_set
    return "n_party" in support_set


def _supports_domain(required: str, supported: list[str]) -> bool:
    if required == "mixed":
        return "mixed" in supported
    if required == "boolean":
        return "boolean" in supported or "mixed" in supported
    if required == "arithmetic":
        return "arithmetic" in supported or "mixed" in supported
    return True


def _supports_optional_field(required: str, supported: list[str]) -> bool:
    if required == "auto":
        return True
    if not supported:
        return True
    return required in supported


def _supports_threshold(required: str, supported: list[str]) -> bool:
    if required == "auto":
        return True
    if not supported:
        return True
    required_level = THRESHOLD_LEVELS.get(required, 0)
    max_supported = max(THRESHOLD_LEVELS.get(item, 0) for item in supported)
    return max_supported >= required_level


def _production_penalty(req: ParsedRequirement, deployment: OpenSourceDeployment) -> int:
    if req.target != "production_candidate":
        return 0
    if deployment.maturity == "frontier":
        return 2
    if deployment.maturity == "active":
        return 1
    if deployment.maturity == "research_code":
        return -5
    if deployment.maturity == "prototype":
        return -7
    if deployment.maturity == "legacy":
        return -8
    return -10


def _workload_bonus(req: ParsedRequirement, deployment: OpenSourceDeployment) -> int:
    if req.operation in deployment.target_workloads:
        return 3
    if "generic" in deployment.target_workloads:
        return 1
    return 0


def _requests_semi2k(req: ParsedRequirement) -> bool:
    normalized = req.raw_requirement.lower().replace("-", "").replace(" ", "")
    return "semi2k" in normalized


def _is_semi2k_deployment(deployment: OpenSourceDeployment) -> bool:
    joined = " ".join(
        [
            deployment.implementation_id,
            deployment.name,
            deployment.protocol_family,
        ]
    ).lower()
    return "semi2k" in joined.replace("-", "").replace(" ", "")


def _build_reasons(req: ParsedRequirement, deployment: OpenSourceDeployment) -> list[str]:
    reasons = [
        f"Matches {req.parties}-party requirement via {', '.join(deployment.party_count_modes)} coverage.",
        f"Supports {req.circuit_domain} circuit preference.",
        f"Supports {req.security_model} adversary setting or stronger.",
        f"Compatible with {req.corruption_model} corruption assumption.",
    ]

    if _requests_semi2k(req) and _is_semi2k_deployment(deployment):
        reasons.append("Matches explicit Semi2k protocol-family preference.")
    if req.math_structure != "auto" and req.math_structure in deployment.math_structures:
        reasons.append(f"Matches math structure `{req.math_structure}`.")
    if req.secret_sharing != "auto" and req.secret_sharing in deployment.secret_sharing:
        reasons.append(f"Matches secret sharing `{req.secret_sharing}`.")
    if req.preprocessing_preference != "auto" and req.preprocessing_preference in deployment.preprocessing_support:
        reasons.append(f"Matches preprocessing preference `{req.preprocessing_preference}`.")
    if req.network_model != "auto":
        reasons.append(f"Matches network model `{req.network_model}`.")
    if req.security_goal != "auto":
        reasons.append(f"Matches security goal `{req.security_goal}`.")

    reasons.extend(deployment.notes[:2])
    return reasons


def _build_warnings(req: ParsedRequirement, deployment: OpenSourceDeployment) -> list[str]:
    warnings: list[str] = []

    if deployment.maturity == "research_code":
        warnings.append("Official repository or paper describes this as experimental/research code.")
    if deployment.maturity == "prototype":
        warnings.append("Open-source code exists, but the maintainers label it as prototype code.")
    if deployment.maturity == "legacy":
        warnings.append("This looks more like a legacy codebase than a current frontier deployment.")
    if deployment.maturity == "archived":
        warnings.append("Repository is archived and should not be treated as an active deployment target.")

    if req.target == "production_candidate" and deployment.maturity in {"research_code", "prototype"}:
        warnings.append("The user's target is production_candidate, but this implementation is not positioned as production-ready.")

    if req.preprocessing_preference != "auto" and deployment.preprocessing_support == []:
        warnings.append("Preprocessing support was not explicitly documented in the source we found.")

    return warnings


def _score_deployment(req: ParsedRequirement, deployment: OpenSourceDeployment) -> int:
    score = deployment.selection_priority
    score += MATURITY_SCORES.get(deployment.maturity, 0)
    score += _production_penalty(req, deployment)
    score += _workload_bonus(req, deployment)

    if _requests_semi2k(req) and _is_semi2k_deployment(deployment):
        score += 12

    if req.parties == 3 and "three_party" in deployment.party_count_modes:
        score += 2
    if req.parties > 3 and "n_party" in deployment.party_count_modes:
        score += 2
    if req.parties == 2 and deployment.party_count_modes == ["two_party"]:
        score += 2

    if req.security_goal != "auto" and req.security_goal in deployment.security_goals:
        score += 4
    if req.network_model != "auto" and req.network_model in deployment.network_models:
        score += 4
    if req.secret_sharing != "auto" and req.secret_sharing in deployment.secret_sharing:
        score += 2
    if req.math_structure != "auto" and req.math_structure in deployment.math_structures:
        score += 2
    if req.preprocessing_preference != "auto" and req.preprocessing_preference in deployment.preprocessing_support:
        score += 2

    return score


def _compatible(req: ParsedRequirement, deployment: OpenSourceDeployment) -> bool:
    return (
        _supports_party_mode(req.party_count_mode, req.parties, deployment.party_count_modes)
        and _supports_domain(req.circuit_domain, deployment.circuit_domains)
        and _supports_security(req.security_model, deployment.security_models)
        and _supports_corruption_model(req.corruption_model, deployment.corruption_models)
        and _supports_optional_field(req.corruption_timing, deployment.corruption_timing_support)
        and _supports_optional_field(req.network_model, deployment.network_models)
        and _supports_threshold(req.corruption_threshold, deployment.corruption_thresholds)
        and _supports_optional_field(req.math_structure, deployment.math_structures)
        and _supports_optional_field(req.secret_sharing, deployment.secret_sharing)
        and _supports_optional_field(req.preprocessing_preference, deployment.preprocessing_support)
        and _supports_optional_field(req.security_goal, deployment.security_goals)
    )


def _relevant_research_gaps(req: ParsedRequirement) -> list[ResearchGap]:
    gaps: list[ResearchGap] = []
    for gap in RESEARCH_GAPS:
        if gap.attribute_group == "corruption_timing" and req.corruption_timing == gap.attribute_value:
            gaps.append(gap)
    return gaps


def recommend_open_source_protocols(
    req: ParsedRequirement,
    *,
    limit: int = 6,
) -> dict[str, object]:
    matches: list[dict[str, object]] = []
    for deployment in DEPLOYMENTS:
        if not _compatible(req, deployment):
            continue
        matches.append(
            {
                **deployment.to_dict(),
                "score": _score_deployment(req, deployment),
                "reasons": _build_reasons(req, deployment),
                "warnings": _build_warnings(req, deployment),
            }
        )

    matches.sort(key=lambda item: int(item["score"]), reverse=True)
    relevant_gaps = _relevant_research_gaps(req)

    notes: list[str] = []
    if req.network_model == "asynchronous" and not matches:
        notes.append("No open-source deployment in the current catalog matched the requested asynchronous combination.")
    if req.corruption_timing == "adaptive":
        notes.append("Adaptive corruption remains a research gap in this catalog unless you narrow to a very specialized implementation outside the current open-source shortlist.")
    if req.security_goal == "guaranteed_output_delivery" and matches:
        notes.append("Guaranteed output delivery is rare in open-source MPC; current positive match is mainly the HoneyBadgerMPC line.")
    if req.target == "production_candidate" and any(item["maturity"] in {"research_code", "prototype"} for item in matches[:limit]):
        notes.append("Some top matches are still research/prototype code, so they should be treated as recommendation leads rather than drop-in production backends.")

    return {
        "summary": {
            **catalog_summary(),
            "match_count": len(matches),
        },
        "matches": matches[:limit],
        "research_gaps": [gap.to_dict() for gap in relevant_gaps],
        "notes": notes,
    }

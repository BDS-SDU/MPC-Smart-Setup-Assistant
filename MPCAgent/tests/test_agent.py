from mpc_agent.agent import MPCConfigAgent
from mpc_agent.config import Settings
from mpc_agent.schemas import (
    AgentReply,
    ChatRequest,
    MPCDraftResponse,
    MPCProtocolConfig,
    MPCStructuredOutput,
    MPCStructuredOptions,
)


class FakeChain:
    def __init__(self, drafts):
        self._drafts = list(drafts)

    def invoke(self, _payload, **_kwargs):
        return self._drafts.pop(0)


class FailingChain:
    def invoke(self, _payload, **_kwargs):
        raise ValueError("simulated parse failure")


def test_agent_process_merges_new_turn_with_existing_config():
    first_config = MPCProtocolConfig()
    first_config.participant_scale.number_of_parties = 3
    first_config.secret_sharing.scheme = "Shamir"

    second_config = MPCProtocolConfig()
    second_config.secret_sharing.threshold = "t <= 1"
    second_config.network.synchrony = "synchronous"

    agent = MPCConfigAgent(Settings(DEEPSEEK_API_KEY="test-key"))
    agent.__dict__["chain"] = FakeChain(
        [
            MPCDraftResponse(config=first_config, summary="三方 Shamir 配置"),
            MPCDraftResponse(config=second_config, summary="补充门限和网络模型"),
        ]
    )

    first = agent.process(ChatRequest(message="三方，Shamir 分享"))
    second = agent.process(
        ChatRequest(
            session_id=first.session_id,
            message="门限最多 1 个腐化方，同步网络",
        )
    )

    assert second.config.participant_scale.number_of_parties == 3
    assert second.config.secret_sharing.scheme == "Shamir"
    assert second.config.secret_sharing.threshold == "t <= 1"
    assert second.config.network.synchrony == "Synchronous"
    assert second.current_mpc_config.network.synchrony == "Synchronous"
    assert second.agent_reply.message == "补充门限和网络模型"


def test_agent_reset_starts_a_fresh_config():
    first_config = MPCProtocolConfig()
    first_config.participant_scale.number_of_parties = 5

    reset_config = MPCProtocolConfig()
    reset_config.participant_scale.number_of_parties = 2

    agent = MPCConfigAgent(Settings(DEEPSEEK_API_KEY="test-key"))
    agent.__dict__["chain"] = FakeChain(
        [
            MPCDraftResponse(config=first_config, summary="五方配置"),
            MPCDraftResponse(config=reset_config, summary="重置为两方配置"),
        ]
    )

    first = agent.process(ChatRequest(message="五方 MPC"))
    reset = agent.process(
        ChatRequest(
            session_id=first.session_id,
            message="重置：两方 MPC",
            reset=True,
        )
    )

    assert reset.session_id == first.session_id
    assert reset.config.participant_scale.number_of_parties == 2


def test_agent_accepts_hidden_form_structured_output_and_normalizes_values():
    config = MPCProtocolConfig()
    config.participant_scale.number_of_parties = 3
    config.circuit.form = "算术电路"
    config.secret_sharing.scheme = "shamir sharing"
    config.adversary.behavior_model = "不按协议执行的恶意节点"
    config.adversary.corruption_strategy = "静态腐化"
    config.network.synchrony = "同步网络"

    agent = MPCConfigAgent(Settings(DEEPSEEK_API_KEY="test-key"))
    agent.__dict__["chain"] = FakeChain(
        [
            MPCStructuredOutput(
                current_mpc_config=config,
                agent_reply=AgentReply(message="已填充隐藏表单"),
            )
        ]
    )

    response = agent.process(ChatRequest(message="三方恶意安全算术电路"))

    assert response.current_mpc_config.adversary.behavior_model == "Malicious"
    assert response.current_mpc_config.adversary.corruption_strategy == "Static"
    assert response.current_mpc_config.circuit.form == "Arithmetic"
    assert response.current_mpc_config.secret_sharing.scheme == "Shamir"
    assert response.current_mpc_config.network.synchrony == "Synchronous"
    assert response.current_mpc_config.canonical_parameters["adversary_behavior"] == "Malicious"


def test_structured_output_schema_tolerates_common_model_variants():
    output = MPCStructuredOutput.model_validate(
        {
            "current_mpc_config": {
                "participant_scale": {"compute_parties": [1, 2, 3]},
                "confidence": "High",
            },
            "agent_reply": "已更新配置",
        }
    )

    assert output.current_mpc_config.participant_scale.compute_parties == ["1", "2", "3"]
    assert output.current_mpc_config.confidence == 0.85
    assert output.agent_reply.message == "已更新配置"


def test_agent_accepts_options_without_natural_language():
    agent = MPCConfigAgent(Settings(DEEPSEEK_API_KEY="test-key"))
    agent.__dict__["chain"] = FailingChain()

    response = agent.process(
        ChatRequest(
            structured_options=MPCStructuredOptions(
                participant_scale="3-party",
                circuit_form="Arithmetic",
                adversary_behavior="Malicious",
                network_model="Synchronous",
                channel_model="Authenticated channels",
            )
        )
    )

    assert response.config.participant_scale.number_of_parties == 3
    assert response.config.circuit.form == "Arithmetic"
    assert response.config.adversary.behavior_model == "Malicious"
    assert response.config.network.synchrony == "Synchronous"
    assert response.config.network.channels == "Authenticated channels"
    assert "已根据您提供的结构化选项完成配置更新" in response.summary


def test_structured_options_override_conflicting_model_output():
    model_config = MPCProtocolConfig()
    model_config.circuit.form = "Boolean"
    model_config.adversary.behavior_model = "Semi-honest"

    agent = MPCConfigAgent(Settings(DEEPSEEK_API_KEY="test-key"))
    agent.__dict__["chain"] = FakeChain(
        [
            MPCStructuredOutput(
                current_mpc_config=model_config,
                agent_reply=AgentReply(message="模型返回了冲突字段"),
            )
        ]
    )

    response = agent.process(
        ChatRequest(
            message="用布尔电路和半诚实模型",
            structured_options=MPCStructuredOptions(
                circuit_form="Arithmetic",
                adversary_behavior="Malicious",
            ),
        )
    )

    assert response.config.circuit.form == "Arithmetic"
    assert response.config.adversary.behavior_model == "Malicious"


def test_agent_falls_back_to_structured_options_when_llm_parse_fails():
    agent = MPCConfigAgent(Settings(DEEPSEEK_API_KEY="test-key"))
    agent.__dict__["chain"] = FailingChain()

    response = agent.process(
        ChatRequest(
            message="自然语言和选项一起提交",
            structured_options=MPCStructuredOptions(
                participant_scale="2-party",
                number_of_parties=2,
                circuit_form="Arithmetic",
                math_structure="PrimeField",
                secret_sharing="Shamir",
                preprocessing="Required",
                adversary_behavior="Semi-honest",
                corruption_strategy="Static",
                network_model="Synchronous",
                corruption_threshold="t < n/3",
                security_goal="PrivacyCorrectness",
            ),
        )
    )

    assert response.config.participant_scale.number_of_parties == 2
    assert response.config.circuit.form == "Arithmetic"
    assert response.config.adversary.behavior_model == "Semi-honest"
    assert response.config.security_goals.privacy == "yes"
    assert "回退到确定性选项映射" in response.summary


def test_proactive_guidance_infers_malicious_shamir_defaults():
    config = MPCProtocolConfig()
    config.participant_scale.number_of_parties = 3
    config.adversary.behavior_model = "Malicious"
    config.adversary.corruption_threshold = "t=1"

    agent = MPCConfigAgent(Settings(DEEPSEEK_API_KEY="test-key"))
    agent.__dict__["chain"] = FakeChain(
        [
            MPCStructuredOutput(
                current_mpc_config=config,
                agent_reply=AgentReply(message="Recognized the malicious 3PC requirement."),
            )
        ]
    )

    response = agent.process(
        ChatRequest(message="三方恶意安全，最多腐化一方")
    )

    assert response.config.circuit.form == "Arithmetic"
    assert response.config.math_structure.structure == "FiniteField"
    assert response.config.secret_sharing.scheme == "Shamir"
    assert response.config.preprocessing.enabled is True
    assert "Beaver triples" in response.config.preprocessing.materials
    assert response.config.network.synchrony == "Synchronous"
    assert response.config.network.channels == "Authenticated channels"
    assert response.config.recommendation.family == "MP-SPDZ malicious-shamir"
    assert "Circuit form" not in response.missing_fields
    assert "Network model" not in response.missing_fields


def test_proactive_guidance_asks_only_protocol_shaping_questions():
    config = MPCProtocolConfig()
    config.participant_scale.number_of_parties = 3
    config.adversary.behavior_model = "Malicious"

    agent = MPCConfigAgent(Settings(DEEPSEEK_API_KEY="test-key"))
    agent.__dict__["chain"] = FakeChain(
        [
            MPCStructuredOutput(
                current_mpc_config=config,
                agent_reply=AgentReply(
                    message="Recognized a malicious 3PC request.",
                    missing_fields=[
                        "circuit.form",
                        "math_structure.structure",
                        "network.synchrony",
                    ],
                ),
            )
        ]
    )

    response = agent.process(ChatRequest(message="three-party malicious MPC"))

    assert response.missing_fields == ["Corruption threshold"]
    assert response.clarifying_questions == [
        "For the 3-party malicious setting, do you need at most one corrupted party, "
        "or a stronger dishonest-majority model?"
    ]

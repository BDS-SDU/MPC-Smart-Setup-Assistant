from fastapi.testclient import TestClient

from mpc_agent.api import app
from mpc_agent.backends import BackendPlanRequest, BackendSelector
from mpc_agent.memory import InMemoryConversationStore
from mpc_agent.schemas import ChatResponse, MPCProtocolConfig


def test_selector_prefers_mp_spdz_for_malicious_shamir_config():
    config = MPCProtocolConfig()
    config.participant_scale.number_of_parties = 3
    config.circuit.form = "Arithmetic"
    config.secret_sharing.scheme = "Shamir"
    config.adversary.behavior_model = "Malicious"
    config.adversary.corruption_threshold = "t=1"
    config.network.synchrony = "Synchronous"

    response = BackendSelector().plan(BackendPlanRequest(config=config))

    assert response.selected.backend == "mp_spdz"
    assert response.selected.protocol == "malicious-shamir"


def test_selector_prefers_mpc_ml_backend_for_semi_honest_tensor_task():
    config = MPCProtocolConfig()
    config.participant_scale.number_of_parties = 2
    config.circuit.form = "Arithmetic"
    config.adversary.behavior_model = "Semi-honest"
    config.task_intent = "ML inference over tensors"

    response = BackendSelector().plan(
        BackendPlanRequest(config=config, task_hint="PyTorch tensor inference")
    )

    assert response.selected.backend in {"spu", "crypten"}


def test_backends_endpoint_lists_capabilities():
    client = TestClient(app)

    response = client.get("/backends")

    assert response.status_code == 200
    assert {backend["name"] for backend in response.json()} == {
        "aby",
        "crypten",
        "emp_sh2pc",
        "motion",
        "mp_spdz",
        "scale_mamba",
        "spu",
    }


def test_backend_plan_endpoint_accepts_config():
    client = TestClient(app)
    config = MPCProtocolConfig()
    config.adversary.behavior_model = "Malicious"
    config.circuit.form = "Arithmetic"

    response = client.post("/backends/plan", json={"config": config.model_dump(mode="json")})

    assert response.status_code == 200
    assert response.json()["selected"]["backend"] == "mp_spdz"


def test_selector_prefers_aby_for_two_party_mixed_workloads():
    config = MPCProtocolConfig()
    config.participant_scale.number_of_parties = 2
    config.circuit.form = "Mixed"
    config.adversary.behavior_model = "Semi-honest"

    response = BackendSelector().plan(BackendPlanRequest(config=config))

    assert response.selected.backend == "aby"


def test_selector_prefers_emp_for_two_party_boolean_workloads():
    config = MPCProtocolConfig()
    config.participant_scale.number_of_parties = 2
    config.circuit.form = "Boolean"
    config.adversary.behavior_model = "Semi-honest"

    response = BackendSelector().plan(BackendPlanRequest(config=config))

    assert response.selected.backend in {"emp_sh2pc", "aby"}

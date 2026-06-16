from fastapi.testclient import TestClient

from mpc_agent.api import app


def test_index_serves_frontend():
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "MPC Protocol Configuration Workbench" in response.text
    assert "Structured MPC Options" in response.text
    assert "Backend Protocol Execution" in response.text


def test_chat_get_explains_post_usage():
    client = TestClient(app)

    response = client.get("/chat")

    assert response.status_code == 200
    assert response.json()["message"].startswith("Use POST /chat")


def test_schema_endpoint_exposes_protocol_config_schema():
    client = TestClient(app)

    response = client.get("/schema")

    assert response.status_code == 200
    assert response.json()["title"] == "MPCProtocolConfig"


def test_unknown_session_returns_404():
    client = TestClient(app)

    response = client.get("/sessions/not-created")

    assert response.status_code == 404

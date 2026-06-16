from mpc_agent.schemas import MPCProtocolConfig
from mpc_agent.utils import merge_models


def test_merge_models_keeps_existing_values_when_incoming_is_empty():
    existing = MPCProtocolConfig()
    existing.participant_scale.number_of_parties = 3
    existing.secret_sharing.scheme = "Shamir"

    incoming = MPCProtocolConfig()
    incoming.secret_sharing.threshold = "t < n/2"

    merged = merge_models(existing, incoming, MPCProtocolConfig)

    assert merged.participant_scale.number_of_parties == 3
    assert merged.secret_sharing.scheme == "Shamir"
    assert merged.secret_sharing.threshold == "t < n/2"

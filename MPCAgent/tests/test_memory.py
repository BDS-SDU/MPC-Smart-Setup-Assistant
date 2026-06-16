from mpc_agent.memory import InMemoryConversationStore, MemoryLimits
from mpc_agent.schemas import ChatResponse, MPCProtocolConfig


def test_memory_keeps_recent_turns_and_summarizes_overflow():
    store = InMemoryConversationStore(MemoryLimits(max_turns=2, max_summary_chars=500))
    state = store.get_or_create("s1")

    for index in range(3):
        response = ChatResponse(
            session_id=state.session_id,
            config=MPCProtocolConfig(task_intent=f"task-{index}"),
            summary=f"summary-{index}",
        )
        state = store.update(state.session_id, f"message-{index}", response)

    assert len(state.turns) == 2
    assert state.turns[0].user == "message-1"
    assert "message-0" in state.summary
    assert state.current_config.task_intent == "task-2"


def test_message_histories_are_isolated_by_session_id():
    store = InMemoryConversationStore()
    s1 = store.get_or_create("s1")
    s2 = store.get_or_create("s2")

    store.get_history(s1.session_id).add_user_message("session one")
    store.get_history(s2.session_id).add_user_message("session two")

    assert store.get_history("s1").messages[0].content == "session one"
    assert store.get_history("s2").messages[0].content == "session two"


def test_reset_clears_message_history_for_session():
    store = InMemoryConversationStore()
    state = store.get_or_create("s1")
    store.get_history(state.session_id).add_user_message("old message")

    store.reset(state.session_id)

    assert store.get_history("s1").messages == []

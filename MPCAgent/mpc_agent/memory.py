"""Thread-level conversation memory for the MPC agent."""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from uuid import uuid4

from langchain_core.chat_history import InMemoryChatMessageHistory
from pydantic import BaseModel, Field

from .schemas import ChatResponse, MPCProtocolConfig


class ConversationTurn(BaseModel):
    user: str
    assistant_summary: str


class ConversationState(BaseModel):
    session_id: str
    summary: str = ""
    current_config: MPCProtocolConfig = Field(default_factory=MPCProtocolConfig)
    turns: list[ConversationTurn] = Field(default_factory=list)

    def recent_turns_text(self) -> str:
        if not self.turns:
            return "无"
        lines: list[str] = []
        for index, turn in enumerate(self.turns, start=1):
            lines.append(f"{index}. 用户：{turn.user}")
            lines.append(f"   配置摘要：{turn.assistant_summary}")
        return "\n".join(lines)


@dataclass(slots=True)
class MemoryLimits:
    max_turns: int = 12
    max_summary_chars: int = 3000


class InMemoryConversationStore:
    """Simple in-process memory store keyed by session id."""

    def __init__(self, limits: MemoryLimits | None = None) -> None:
        self._limits = limits or MemoryLimits()
        self._sessions: dict[str, ConversationState] = {}
        self._histories: dict[str, InMemoryChatMessageHistory] = {}
        self._lock = RLock()

    def get_or_create(self, session_id: str | None = None) -> ConversationState:
        with self._lock:
            sid = session_id or str(uuid4())
            if sid not in self._sessions:
                self._sessions[sid] = ConversationState(session_id=sid)
            if sid not in self._histories:
                self._histories[sid] = InMemoryChatMessageHistory()
            return self._sessions[sid].model_copy(deep=True)

    def get_history(self, session_id: str) -> InMemoryChatMessageHistory:
        with self._lock:
            if session_id not in self._histories:
                self._histories[session_id] = InMemoryChatMessageHistory()
            return self._histories[session_id]

    def get(self, session_id: str) -> ConversationState | None:
        with self._lock:
            state = self._sessions.get(session_id)
            if state is None:
                return None
            return state.model_copy(deep=True)

    def list_session_ids(self) -> list[str]:
        with self._lock:
            return sorted(set(self._sessions) | set(self._histories))

    def reset(self, session_id: str | None = None) -> ConversationState:
        with self._lock:
            sid = session_id or str(uuid4())
            state = ConversationState(session_id=sid)
            self._sessions[sid] = state
            self._histories[sid] = InMemoryChatMessageHistory()
            return state.model_copy(deep=True)

    def update(self, session_id: str, user_message: str, response: ChatResponse) -> ConversationState:
        with self._lock:
            state = self._sessions.get(session_id) or ConversationState(session_id=session_id)
            state.current_config = response.config
            state.turns.append(
                ConversationTurn(
                    user=user_message,
                    assistant_summary=response.summary,
                )
            )
            if len(state.turns) > self._limits.max_turns:
                overflow = state.turns[: -self._limits.max_turns]
                state.turns = state.turns[-self._limits.max_turns :]
                self._append_to_summary(state, overflow)
            self._sessions[session_id] = state
            return state.model_copy(deep=True)

    def delete(self, session_id: str) -> bool:
        with self._lock:
            deleted_state = self._sessions.pop(session_id, None) is not None
            deleted_history = self._histories.pop(session_id, None) is not None
            return deleted_state or deleted_history

    def _append_to_summary(
        self,
        state: ConversationState,
        overflow: list[ConversationTurn],
    ) -> None:
        additions = [
            f"用户曾提出：{turn.user}；当时配置摘要：{turn.assistant_summary}"
            for turn in overflow
        ]
        combined = "\n".join([state.summary, *additions]).strip()
        state.summary = combined[-self._limits.max_summary_chars :]

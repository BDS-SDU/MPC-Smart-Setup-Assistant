"""MPC protocol configuration agent."""

from typing import TYPE_CHECKING

from .schemas import ChatRequest, ChatResponse, MPCProtocolConfig

if TYPE_CHECKING:
    from .agent import MPCConfigAgent

__all__ = ["MPCConfigAgent", "ChatRequest", "ChatResponse", "MPCProtocolConfig"]


def __getattr__(name: str):
    if name == "MPCConfigAgent":
        from .agent import MPCConfigAgent

        return MPCConfigAgent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

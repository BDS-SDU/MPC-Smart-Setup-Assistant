"""LangChain-powered MPC protocol configuration agent."""

from __future__ import annotations

from functools import cached_property
from typing import Any

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableLambda
from langchain_core.runnables.history import RunnableWithMessageHistory

from .config import Settings, get_settings
from .guidance import apply_proactive_guidance
from .memory import InMemoryConversationStore, MemoryLimits
from .normalization import normalize_config
from .prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from .schemas import (
    AgentReply,
    ChatRequest,
    ChatResponse,
    MPCDraftResponse,
    MPCStructuredOutput,
)
from .structured_options import (
    build_option_only_reply,
    options_display_text,
    options_to_config,
    options_to_prompt_text,
)
from .utils import merge_models, to_pretty_json


class DeepSeekNotConfiguredError(RuntimeError):
    """Raised when the DeepSeek API key is missing."""


class MPCConfigAgent:
    """Extract and update MPC protocol configuration from natural language."""

    def __init__(
        self,
        settings: Settings | None = None,
        memory_store: InMemoryConversationStore | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.memory_store = memory_store or InMemoryConversationStore(
            MemoryLimits(
                max_turns=self.settings.max_turns,
                max_summary_chars=self.settings.max_summary_chars,
            )
        )

    @cached_property
    def prompt(self) -> ChatPromptTemplate:
        return ChatPromptTemplate.from_messages(
            [
                ("system", SYSTEM_PROMPT),
                MessagesPlaceholder(
                    variable_name="history",
                    optional=True,
                    n_messages=self.settings.max_turns * 2,
                ),
                ("human", USER_PROMPT_TEMPLATE),
            ]
        ).partial(
            output_schema_json=to_pretty_json(MPCStructuredOutput.model_json_schema())
        )

    @cached_property
    def llm(self) -> Any:
        if not self.settings.deepseek_api_key:
            raise DeepSeekNotConfiguredError(
                "DEEPSEEK_API_KEY is required before calling the DeepSeek model."
            )

        common_kwargs: dict[str, Any] = {
            "model": self.settings.deepseek_model,
            "temperature": self.settings.temperature,
            "max_tokens": self.settings.max_tokens,
            "timeout": self.settings.request_timeout,
            "max_retries": self.settings.max_retries,
            "api_key": self.settings.deepseek_api_key,
            "base_url": self.settings.deepseek_api_base,
        }

        try:
            from langchain_deepseek import ChatDeepSeek

            return ChatDeepSeek(**common_kwargs)
        except TypeError:
            from langchain_deepseek import ChatDeepSeek

            return ChatDeepSeek(**common_kwargs)
        except ImportError:
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(**common_kwargs)

    @cached_property
    def structured_llm(self) -> Any:
        return self.llm.with_structured_output(
            MPCStructuredOutput,
            method="json_mode",
        )

    @cached_property
    def chain(self) -> Any:
        runnable = self.prompt | self.structured_llm | RunnableLambda(self._as_history_payload)
        return RunnableWithMessageHistory(
            runnable,
            self.memory_store.get_history,
            input_messages_key="message",
            history_messages_key="history",
            output_messages_key="reply_text",
        )

    def process(self, request: ChatRequest) -> ChatResponse:
        state = (
            self.memory_store.reset(request.session_id)
            if request.reset
            else self.memory_store.get_or_create(request.session_id)
        )
        option_config = normalize_config(options_to_config(request.structured_options))
        effective_message = self._effective_message(request)
        if self._should_skip_llm(request):
            output = self._build_option_only_output(request, option_config)
        else:
            try:
                result = self.chain.invoke(
                    self._chain_input(effective_message, state, request),
                    config={"configurable": {"session_id": state.session_id}},
                )
                output = self._coerce_structured_output(result)
            except Exception as exc:
                if request.structured_options and request.structured_options.has_values():
                    output = self._build_option_only_output(
                        request,
                        option_config,
                        fallback_reason=str(exc),
                    )
                else:
                    raise
        response = self._finalize_response(
            state.session_id,
            effective_message,
            state,
            output,
            option_config,
        )
        self.memory_store.update(state.session_id, self._display_message(request), response)
        return response

    async def aprocess(self, request: ChatRequest) -> ChatResponse:
        state = (
            self.memory_store.reset(request.session_id)
            if request.reset
            else self.memory_store.get_or_create(request.session_id)
        )
        option_config = normalize_config(options_to_config(request.structured_options))
        effective_message = self._effective_message(request)
        if self._should_skip_llm(request):
            output = self._build_option_only_output(request, option_config)
        else:
            try:
                result = await self.chain.ainvoke(
                    self._chain_input(effective_message, state, request),
                    config={"configurable": {"session_id": state.session_id}},
                )
                output = self._coerce_structured_output(result)
            except Exception as exc:
                if request.structured_options and request.structured_options.has_values():
                    output = self._build_option_only_output(
                        request,
                        option_config,
                        fallback_reason=str(exc),
                    )
                else:
                    raise
        response = self._finalize_response(
            state.session_id,
            effective_message,
            state,
            output,
            option_config,
        )
        self.memory_store.update(state.session_id, self._display_message(request), response)
        return response

    def _chain_input(self, message: str, state: Any, request: ChatRequest) -> dict[str, str]:
        return {
            "memory_summary": state.summary or "无",
            "current_config_json": to_pretty_json(state.current_config),
            "structured_options": options_to_prompt_text(request.structured_options),
            "recent_turns": state.recent_turns_text(),
            "message": message,
        }

    def _effective_message(self, request: ChatRequest) -> str:
        message = request.message.strip()
        options_text = options_to_prompt_text(request.structured_options)
        if options_text == "无":
            return message
        if not message:
            return f"用户通过结构化选项提交需求。结构化选项（最高优先级）：{options_text}"
        return f"{message}\n\n结构化选项（最高优先级）：{options_text}"

    def _display_message(self, request: ChatRequest) -> str:
        message = request.message.strip()
        option_text = options_display_text(request.structured_options)
        if message and option_text:
            return f"{message}\n{option_text}"
        return message or option_text

    def _should_skip_llm(self, request: ChatRequest) -> bool:
        return bool(
            request.structured_options
            and request.structured_options.has_values()
            and not request.message.strip()
        )

    def _build_option_only_output(
        self,
        request: ChatRequest,
        option_config: Any,
        fallback_reason: str | None = None,
    ) -> MPCStructuredOutput:
        reply = build_option_only_reply(
            option_config,
            had_natural_language=bool(request.message.strip()),
            fallback_reason=fallback_reason,
        )
        return MPCStructuredOutput(
            current_mpc_config=option_config,
            agent_reply=reply,
        )

    def _as_history_payload(self, output: MPCStructuredOutput | dict[str, Any]) -> dict[str, Any]:
        structured = MPCStructuredOutput.model_validate(output)
        reply_text = structured.agent_reply.message.strip() or "配置已更新。"
        return {"reply_text": reply_text, "structured": structured}

    def _coerce_structured_output(self, result: Any) -> MPCStructuredOutput:
        if isinstance(result, MPCStructuredOutput):
            return result
        if isinstance(result, MPCDraftResponse):
            return MPCStructuredOutput(
                current_mpc_config=result.config,
                agent_reply=AgentReply(
                    message=result.summary,
                    missing_fields=result.missing_fields,
                    clarifying_questions=result.clarifying_questions,
                    next_actions=result.next_actions,
                ),
            )
        if isinstance(result, dict) and "structured" in result:
            return MPCStructuredOutput.model_validate(result["structured"])
        return MPCStructuredOutput.model_validate(result)

    def _finalize_response(
        self,
        session_id: str,
        message: str,
        state: Any,
        output: MPCStructuredOutput,
        option_config: Any | None = None,
    ) -> ChatResponse:
        merged_config = merge_models(
            state.current_config,
            output.current_mpc_config,
            type(output.current_mpc_config),
        )
        if option_config is not None:
            merged_config = merge_models(merged_config, option_config, type(merged_config))
        merged_config = normalize_config(merged_config)
        guidance = apply_proactive_guidance(merged_config, message)
        merged_config = guidance.config
        reply = output.agent_reply
        missing = guidance.missing_fields

        summary = reply.message.strip()
        if not summary:
            summary = f"已根据用户输入更新 MPC 协议配置：{message[:120]}"
        if option_config is not None and option_config.canonical_parameters:
            summary = f"{summary}\n当前配置快照已优先采用结构化选项。"
        if guidance.inferred_notes and "malicious-shamir" in (merged_config.recommendation.family or ""):
            summary = (
                f"{summary}\nExpert guidance: inferred MP-SPDZ malicious-shamir defaults "
                "for this 3-party malicious-security setting."
            )
        normalized_reply = AgentReply(
            message=summary,
            missing_fields=missing,
            clarifying_questions=guidance.clarifying_questions,
            next_actions=guidance.next_actions or reply.next_actions,
        )

        return ChatResponse(
            session_id=session_id,
            config=merged_config,
            current_mpc_config=merged_config,
            agent_reply=normalized_reply,
            summary=summary,
            missing_fields=missing,
            clarifying_questions=guidance.clarifying_questions,
            next_actions=guidance.next_actions or reply.next_actions,
        )

from __future__ import annotations

from typing import Any

from .prompts import list_prompts, render_prompt
from .resources import list_resources, read_resource
from .tools import call_tool, list_tools


class LocalMcpServer:
    """Small MCP-style dispatcher for local HTTP integration."""

    def capabilities(self) -> dict[str, Any]:
        return {
            "tools": list_tools(),
            "resources": list_resources(),
            "prompts": list_prompts(),
        }

    def handle_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        action = str(payload.get("action", "")).strip()

        if action == "capabilities":
            return self.capabilities()

        if action == "call_tool":
            tool_name = str(payload.get("name", "")).strip()
            arguments = payload.get("arguments", {})
            if not isinstance(arguments, dict):
                raise ValueError("`arguments` must be a JSON object.")
            return {
                "tool": tool_name,
                "result": call_tool(tool_name, arguments),
            }

        if action == "read_resource":
            uri = str(payload.get("uri", "")).strip()
            return {
                "uri": uri,
                "content": read_resource(uri),
            }

        if action == "render_prompt":
            prompt_name = str(payload.get("name", "")).strip()
            arguments = payload.get("arguments", {})
            if not isinstance(arguments, dict):
                raise ValueError("`arguments` must be a JSON object.")
            return {
                "name": prompt_name,
                "result": render_prompt(prompt_name, arguments),
            }

        raise ValueError(f"Unsupported MCP action: {action}")


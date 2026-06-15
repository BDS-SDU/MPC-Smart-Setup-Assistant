from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlparse


class DeepSeekAdvisor:
    def __init__(self) -> None:
        self.api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
        self.base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1/chat/completions").strip()
        self.model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat").strip()
        self.timeout = int(os.getenv("DEEPSEEK_TIMEOUT", "30"))

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def _is_connection_refused(self, error: urllib.error.URLError) -> bool:
        reason = getattr(error, "reason", None)
        if isinstance(reason, OSError):
            if getattr(reason, "winerror", None) == 10061:
                return True
            if getattr(reason, "errno", None) in {111, 61}:
                return True
        message = str(error)
        return (
            "10061" in message
            or "Connection refused" in message
        )

    def _is_loopback_blackhole_proxy(self, proxy_url: str) -> bool:
        raw = proxy_url.strip()
        if not raw:
            return False
        if "://" not in raw:
            raw = f"http://{raw}"
        parsed = urlparse(raw)
        host = (parsed.hostname or "").lower()
        port = parsed.port
        return host in {"127.0.0.1", "localhost", "::1"} and port == 9

    def _has_loopback_blackhole_proxy(self) -> bool:
        keys = [
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "ALL_PROXY",
            "http_proxy",
            "https_proxy",
            "all_proxy",
        ]
        for key in keys:
            if self._is_loopback_blackhole_proxy(os.getenv(key, "")):
                return True
        return False

    def _should_retry_without_proxy(self, error: urllib.error.URLError) -> bool:
        return self._has_loopback_blackhole_proxy() and self._is_connection_refused(error)

    def _fetch_response(self, body: dict[str, Any], *, ignore_env_proxy: bool) -> str:
        request = urllib.request.Request(
            self.base_url,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        if ignore_env_proxy:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(request, timeout=self.timeout) as response:
                return response.read().decode("utf-8")

        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return response.read().decode("utf-8")

    def _extract_json(self, content: str) -> dict[str, Any]:
        content = content.strip()
        if content.startswith("{") and content.endswith("}"):
            return json.loads(content)
        match = re.search(r"\{[\s\S]*\}", content)
        if not match:
            raise ValueError("DeepSeek response does not contain JSON.")
        return json.loads(match.group(0))

    def advise(
        self,
        parsed_requirement: dict[str, Any],
        candidates: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if not self.enabled:
            return {
                "enabled": False,
                "used": False,
                "reason": "DEEPSEEK_API_KEY is not configured.",
            }

        body = {
            "model": self.model,
            "temperature": 0.1,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an MPC protocol planner. "
                        "Select one protocol id from provided candidates and explain why. "
                        "Return strict JSON only with keys: "
                        "recommended_protocol_id, confidence, rationale, risk_notes, parameter_adjustments."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "parsed_requirement": parsed_requirement,
                            "candidates": candidates,
                            "rule": "recommend exactly one protocol_id from candidate list",
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
        }

        try:
            raw_response = self._fetch_response(body, ignore_env_proxy=False)
        except urllib.error.URLError as error:
            if not self._should_retry_without_proxy(error):
                return {
                    "enabled": True,
                    "used": False,
                    "reason": f"DeepSeek request failed: {error}",
                }
            try:
                raw_response = self._fetch_response(body, ignore_env_proxy=True)
            except (urllib.error.URLError, TimeoutError) as retry_error:
                return {
                    "enabled": True,
                    "used": False,
                    "reason": (
                        "DeepSeek request failed with environment proxy "
                        f"({error}); retry without proxy failed: {retry_error}"
                    ),
                }
        except TimeoutError as error:
            return {
                "enabled": True,
                "used": False,
                "reason": f"DeepSeek request failed: {error}",
            }
        try:
            payload = json.loads(raw_response)
            content = payload["choices"][0]["message"]["content"]
            parsed = self._extract_json(content)
            parsed.update({"enabled": True, "used": True})
            return parsed
        except (KeyError, ValueError, json.JSONDecodeError) as error:
            return {
                "enabled": True,
                "used": False,
                "reason": f"DeepSeek response parsing failed: {error}",
            }

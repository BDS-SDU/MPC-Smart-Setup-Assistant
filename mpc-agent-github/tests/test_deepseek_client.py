from __future__ import annotations

import json
import os
import unittest
import urllib.error
from contextlib import contextmanager
from typing import Iterator

from mpc_agent.deepseek_client import DeepSeekAdvisor


@contextmanager
def temporary_env(overrides: dict[str, str]) -> Iterator[None]:
    sentinel = object()
    previous: dict[str, object | str] = {}
    for key, value in overrides.items():
        previous[key] = os.environ.get(key, sentinel)
        os.environ[key] = value
    try:
        yield
    finally:
        for key, old in previous.items():
            if old is sentinel:
                os.environ.pop(key, None)
            else:
                os.environ[key] = str(old)


class DeepSeekClientTests(unittest.TestCase):
    def test_detect_loopback_blackhole_proxy(self) -> None:
        with temporary_env(
            {"DEEPSEEK_API_KEY": "sk-test", "HTTPS_PROXY": "http://127.0.0.1:9"}
        ):
            advisor = DeepSeekAdvisor()
            self.assertTrue(advisor._has_loopback_blackhole_proxy())

    def test_no_blackhole_proxy_when_not_configured(self) -> None:
        with temporary_env({"DEEPSEEK_API_KEY": "sk-test"}):
            os.environ.pop("HTTP_PROXY", None)
            os.environ.pop("HTTPS_PROXY", None)
            os.environ.pop("ALL_PROXY", None)
            advisor = DeepSeekAdvisor()
            self.assertFalse(advisor._has_loopback_blackhole_proxy())

    def test_advise_retry_without_proxy_when_proxy_refused(self) -> None:
        with temporary_env(
            {"DEEPSEEK_API_KEY": "sk-test", "HTTPS_PROXY": "http://127.0.0.1:9"}
        ):
            advisor = DeepSeekAdvisor()
            first_error = urllib.error.URLError(OSError(10061, "Connection refused"))
            api_payload = {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "recommended_protocol_id": "mascot",
                                    "confidence": 0.8,
                                    "rationale": "ok",
                                    "risk_notes": "none",
                                    "parameter_adjustments": "none",
                                }
                            )
                        }
                    }
                ]
            }
            calls: list[bool] = []
            responses: list[Exception | str] = [first_error, json.dumps(api_payload)]

            original_fetch = advisor._fetch_response

            def fake_fetch(
                body: dict[str, object], *, ignore_env_proxy: bool
            ) -> str:
                calls.append(ignore_env_proxy)
                current = responses.pop(0)
                if isinstance(current, Exception):
                    raise current
                return current

            advisor._fetch_response = fake_fetch  # type: ignore[method-assign]
            result = advisor.advise({"parties": 3}, [{"protocol_id": "mascot"}])
            advisor._fetch_response = original_fetch

        self.assertTrue(result["used"])
        self.assertEqual(result["recommended_protocol_id"], "mascot")
        self.assertEqual(calls, [False, True])


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from socket import socket
from typing import Any

from mpc_agent.integrations.external_api import call_external_api, list_external_systems


class _ExternalApiTestHandler(BaseHTTPRequestHandler):
    def log_message(self, format_str: str, *args: Any) -> None:
        return

    def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        self._send_json({"ok": True, "method": "GET", "path": self.path})

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length > 0 else b"{}"
        payload = json.loads(body.decode("utf-8"))
        self._send_json({"ok": True, "method": "POST", "payload": payload})


def _pick_free_port() -> int:
    sock = socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return int(port)


class ExternalApiIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.port = _pick_free_port()
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", cls.port), _ExternalApiTestHandler)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.httpd.shutdown()
        cls.thread.join(timeout=2)

    def setUp(self) -> None:
        self._old = os.getenv("EXTERNAL_SYSTEMS_JSON")
        os.environ["EXTERNAL_SYSTEMS_JSON"] = json.dumps(
            [
                {
                    "name": "read_system",
                    "base_url": f"http://127.0.0.1:{self.port}",
                    "allow_write": False,
                    "allowed_prefixes": ["v1/"],
                },
                {
                    "name": "rw_system",
                    "base_url": f"http://127.0.0.1:{self.port}",
                    "allow_write": True,
                },
            ]
        )

    def tearDown(self) -> None:
        if self._old is None:
            os.environ.pop("EXTERNAL_SYSTEMS_JSON", None)
        else:
            os.environ["EXTERNAL_SYSTEMS_JSON"] = self._old

    def test_list_external_systems(self) -> None:
        systems = list_external_systems()
        names = {item["name"] for item in systems}
        self.assertEqual(names, {"read_system", "rw_system"})

    def test_call_external_api_get(self) -> None:
        result = call_external_api(
            system_name="read_system",
            method="GET",
            path="/v1/health",
            query={"a": 1},
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], 200)
        self.assertIsInstance(result["json"], dict)

    def test_call_external_api_write_blocked_for_read_only(self) -> None:
        with self.assertRaises(PermissionError):
            call_external_api(
                system_name="read_system",
                method="POST",
                path="/v1/submit",
                body={"x": 1},
            )

    def test_call_external_api_post_success_for_rw_system(self) -> None:
        result = call_external_api(
            system_name="rw_system",
            method="POST",
            path="/submit",
            body={"x": 1},
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], 200)
        self.assertEqual(result["json"]["payload"]["x"], 1)

    def test_call_external_api_prefix_blocked(self) -> None:
        with self.assertRaises(PermissionError):
            call_external_api(
                system_name="read_system",
                method="GET",
                path="/other/path",
            )


if __name__ == "__main__":
    unittest.main()

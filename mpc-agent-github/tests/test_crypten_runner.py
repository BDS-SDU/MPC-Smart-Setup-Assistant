from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import mpc_agent.crypten_runner as crypten_runner_module
from mpc_agent.crypten_runner import (
    CrypTenRunner,
    inspect_crypten_runtime_support,
    resolve_crypten_home,
    resolve_crypten_python,
)
from mpc_agent.models import FinalConfiguration, ParsedRequirement
from mpc_agent.runtime_runner import RuntimeRunner


class CrypTenRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original_loader = crypten_runner_module._load_runtime_defaults
        crypten_runner_module._load_runtime_defaults = lambda: {}  # type: ignore[assignment]

    def tearDown(self) -> None:
        crypten_runner_module._load_runtime_defaults = self._original_loader

    def _parsed_requirement(self, *, parties: int = 2, operation: str = "aggregation") -> ParsedRequirement:
        return ParsedRequirement(
            raw_requirement="test",
            parties=parties,
            operation=operation,
            circuit_domain="mixed" if operation == "comparison" else "arithmetic",
            security_model="semi_honest",
            corruption_model="dishonest_majority",
            latency_priority="normal",
            bandwidth_priority="normal",
            target="production_candidate",
            notes=[],
        )

    def _crypten_config(self, *, parties: int = 2) -> FinalConfiguration:
        return FinalConfiguration(
            protocol_id="crypten_tensor",
            title="CrypTen Tensor MPC",
            mpspdz_home="",
            script_candidates=[],
            parties=parties,
            security_model="semi_honest",
            corruption_model="dishonest_majority",
            circuit_domain="arithmetic",
            preprocessed=False,
            compile_options=[],
            source_program_name="demo_crypten",
            rationale=[],
            references=[],
            runner_backend="crypten",
            implementation_id="crypten_tensor",
            framework="CrypTen",
        )

    def test_resolve_crypten_python_detects_named_venv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            python_path = base / "venvs" / "crypten_env" / "Scripts" / "python.exe"
            python_path.parent.mkdir(parents=True, exist_ok=True)
            python_path.write_text("", encoding="utf-8")

            original_candidate_roots = crypten_runner_module._candidate_user_roots
            crypten_runner_module._candidate_user_roots = lambda: [base]  # type: ignore[assignment]
            try:
                resolved, source = resolve_crypten_python({})
            finally:
                crypten_runner_module._candidate_user_roots = original_candidate_roots

        self.assertEqual(resolved, python_path)
        self.assertEqual(source, "auto_detected")

    def test_resolve_crypten_home_detects_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            home = base / "CrypTen"
            (home / "crypten").mkdir(parents=True, exist_ok=True)
            (home / "setup.py").write_text("from setuptools import setup\n", encoding="utf-8")

            original_candidate_roots = crypten_runner_module._candidate_user_roots
            crypten_runner_module._candidate_user_roots = lambda: [base]  # type: ignore[assignment]
            try:
                resolved, source = resolve_crypten_home({})
            finally:
                crypten_runner_module._candidate_user_roots = original_candidate_roots

        self.assertEqual(resolved, home)
        self.assertEqual(source, "auto_detected")

    def test_inspect_crypten_runtime_support_reports_missing_python(self) -> None:
        original_resolve = crypten_runner_module.resolve_crypten_python
        crypten_runner_module.resolve_crypten_python = lambda payload: (None, "unresolved")  # type: ignore[assignment]
        try:
            result = inspect_crypten_runtime_support({})
        finally:
            crypten_runner_module.resolve_crypten_python = original_resolve

        self.assertFalse(result["launchable"])
        self.assertIn("crypten_python", result["reason"])

    def test_crypten_runner_compile_only_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            python_path = root / "python.exe"
            python_path.write_text("", encoding="utf-8")

            responses = [
                {
                    "command": ["probe"],
                    "return_code": 0,
                    "duration_seconds": 0.01,
                    "stdout": '{"ok": true, "crypten_version": "demo", "torch_version": "demo"}',
                    "stderr": "",
                },
                {
                    "command": ["run"],
                    "return_code": 0,
                    "duration_seconds": 0.01,
                    "stdout": '{"status": "compile_only_success", "reason": "probe only"}',
                    "stderr": "",
                },
            ]

            original_run_command = crypten_runner_module._run_command
            crypten_runner_module._run_command = lambda command, cwd, timeout: responses.pop(0)  # type: ignore[assignment]
            try:
                result = CrypTenRunner().run(
                    {
                        "execute": True,
                        "compile_only": True,
                        "crypten_python": str(python_path),
                    },
                    self._parsed_requirement(),
                    self._crypten_config(),
                )
            finally:
                crypten_runner_module._run_command = original_run_command

        self.assertEqual(result["status"], "compile_only_success")
        self.assertEqual(result["backend"], "crypten")

    def test_crypten_runner_run_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            python_path = root / "python.exe"
            python_path.write_text("", encoding="utf-8")

            responses = [
                {
                    "command": ["probe"],
                    "return_code": 0,
                    "duration_seconds": 0.01,
                    "stdout": '{"ok": true, "crypten_version": "demo", "torch_version": "demo"}',
                    "stderr": "",
                },
                {
                    "command": ["run"],
                    "return_code": 0,
                    "duration_seconds": 0.01,
                    "stdout": '{"status": "success", "result": [3.0]}',
                    "stderr": "",
                },
            ]

            original_run_command = crypten_runner_module._run_command
            crypten_runner_module._run_command = lambda command, cwd, timeout: responses.pop(0)  # type: ignore[assignment]
            try:
                result = CrypTenRunner().run(
                    {
                        "execute": True,
                        "crypten_python": str(python_path),
                    },
                    self._parsed_requirement(),
                    self._crypten_config(),
                )
            finally:
                crypten_runner_module._run_command = original_run_command

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["result"]["result"], [3.0])
        self.assertEqual(result["implementation_id"], "crypten_tensor")

    def test_runtime_runner_dispatches_to_crypten_backend(self) -> None:
        runner = RuntimeRunner()

        class DummyCrypTenRunner:
            def run(self, payload, req, config):  # type: ignore[no-untyped-def]
                return {"backend": "crypten", "status": "success"}

        runner.crypten = DummyCrypTenRunner()  # type: ignore[assignment]
        result = runner.run(
            {"execute": True},
            self._parsed_requirement(),
            self._crypten_config(),
        )
        self.assertEqual(result["backend"], "crypten")


if __name__ == "__main__":
    unittest.main()

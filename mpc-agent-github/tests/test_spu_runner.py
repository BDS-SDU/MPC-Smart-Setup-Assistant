from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from mpc_agent.models import FinalConfiguration, ParsedRequirement
import mpc_agent.spu_runner as spu_runner_module
from mpc_agent.spu_runner import (
    SpuRunner,
    inspect_spu_runtime_support,
    resolve_spu_home,
    resolve_spu_python,
    resolve_spu_runtime_mode,
)


class SpuRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original_loader = spu_runner_module._load_runtime_defaults
        spu_runner_module._load_runtime_defaults = lambda: {}  # type: ignore[assignment]

    def tearDown(self) -> None:
        spu_runner_module._load_runtime_defaults = self._original_loader

    def _parsed_requirement(self, *, parties: int = 3, operation: str = "aggregation") -> ParsedRequirement:
        return ParsedRequirement(
            raw_requirement="test",
            parties=parties,
            operation=operation,
            circuit_domain="mixed" if operation == "comparison" else "arithmetic",
            security_model="semi_honest",
            corruption_model="honest_majority" if parties == 3 else "dishonest_majority",
            latency_priority="normal",
            bandwidth_priority="normal",
            target="production_candidate",
            notes=[],
        )

    def _spu_config(self, *, parties: int = 3, implementation_id: str = "spu_aby3") -> FinalConfiguration:
        return FinalConfiguration(
            protocol_id=implementation_id,
            title="SecretFlow SPU",
            mpspdz_home="",
            script_candidates=[],
            parties=parties,
            security_model="semi_honest",
            corruption_model="honest_majority" if parties == 3 else "dishonest_majority",
            circuit_domain="mixed" if implementation_id == "spu_cheetah" else "arithmetic",
            preprocessed=False,
            compile_options=[],
            source_program_name="demo_spu",
            rationale=[],
            references=[],
            runner_backend="secretflow_spu",
            implementation_id=implementation_id,
            framework="SecretFlow SPU",
        )

    def test_resolve_spu_home_detects_sibling_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            mpspdz = base / "MP-SPDZ"
            spu = base / "spu-main" / "spu-main"
            (mpspdz / "compile.py").parent.mkdir(parents=True, exist_ok=True)
            (mpspdz / "compile.py").write_text("print('ok')\n", encoding="utf-8")
            (spu / "spu").mkdir(parents=True, exist_ok=True)
            (spu / "pyproject.toml").write_text("[project]\nname='spu'\n", encoding="utf-8")

            resolved, source = resolve_spu_home({"mpspdz_home": str(mpspdz)})

        self.assertEqual(resolved, spu)
        self.assertEqual(source, "auto_detected")

    def test_inspect_spu_runtime_support_reports_missing_python(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "spu").mkdir(parents=True, exist_ok=True)
            (root / "pyproject.toml").write_text("[project]\nname='spu'\n", encoding="utf-8")

            original_resolve_python = spu_runner_module.resolve_spu_python
            spu_runner_module.resolve_spu_python = lambda payload, spu_home: (None, "unresolved")  # type: ignore[assignment]
            try:
                result = inspect_spu_runtime_support({"spu_home": str(root)})
            finally:
                spu_runner_module.resolve_spu_python = original_resolve_python

        self.assertFalse(result["launchable"])
        self.assertIn("spu_python", result["reason"])

    def test_resolve_spu_home_detects_repo_from_workspace_parents(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            workspace = base / "Agent" / "Agent"
            workspace.mkdir(parents=True, exist_ok=True)
            spu = base / "spu-main" / "spu-main"
            (spu / "spu").mkdir(parents=True, exist_ok=True)
            (spu / "pyproject.toml").write_text("[project]\nname='spu'\n", encoding="utf-8")

            original_candidate_roots = spu_runner_module._candidate_user_roots
            spu_runner_module._candidate_user_roots = lambda: [workspace, *workspace.parents]  # type: ignore[assignment]
            try:
                resolved, source = resolve_spu_home({})
            finally:
                spu_runner_module._candidate_user_roots = original_candidate_roots

        self.assertEqual(resolved, spu)
        self.assertEqual(source, "auto_detected")

    def test_resolve_spu_python_detects_standard_windows_install(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            python_path = base / "AppData" / "Local" / "Programs" / "Python" / "Python311" / "python.exe"
            python_path.parent.mkdir(parents=True, exist_ok=True)
            python_path.write_text("", encoding="utf-8")

            original_candidate_roots = spu_runner_module._candidate_user_roots
            spu_runner_module._candidate_user_roots = lambda: [base]  # type: ignore[assignment]
            try:
                resolved, source = resolve_spu_python({}, None)
            finally:
                spu_runner_module._candidate_user_roots = original_candidate_roots

        self.assertEqual(resolved, python_path)
        self.assertEqual(source, "auto_detected")

    def test_spu_runner_compile_only_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            python_path = root / "python.exe"
            python_path.write_text("", encoding="utf-8")
            (root / "spu").mkdir(parents=True, exist_ok=True)
            (root / "pyproject.toml").write_text("[project]\nname='spu'\n", encoding="utf-8")

            responses = [
                {
                    "command": ["probe"],
                    "return_code": 0,
                    "duration_seconds": 0.01,
                    "stdout": '{"ok": true, "spu_module": "demo"}',
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

            original_run_command = spu_runner_module._run_command
            spu_runner_module._run_command = lambda command, cwd, timeout: responses.pop(0)  # type: ignore[assignment]
            try:
                result = SpuRunner().run(
                    {
                        "execute": True,
                        "compile_only": True,
                        "spu_home": str(root),
                        "spu_python": str(python_path),
                    },
                    self._parsed_requirement(),
                    self._spu_config(),
                )
            finally:
                spu_runner_module._run_command = original_run_command

        self.assertEqual(result["status"], "compile_only_success")
        self.assertEqual(result["backend"], "secretflow_spu")

    def test_spu_runner_run_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            python_path = root / "python.exe"
            python_path.write_text("", encoding="utf-8")
            (root / "spu").mkdir(parents=True, exist_ok=True)
            (root / "pyproject.toml").write_text("[project]\nname='spu'\n", encoding="utf-8")

            responses = [
                {
                    "command": ["probe"],
                    "return_code": 0,
                    "duration_seconds": 0.01,
                    "stdout": '{"ok": true, "spu_module": "demo"}',
                    "stderr": "",
                },
                {
                    "command": ["run"],
                    "return_code": 0,
                    "duration_seconds": 0.01,
                    "stdout": '{"status": "success", "result": 6, "protocol_kind": "ABY3"}',
                    "stderr": "",
                },
            ]

            original_run_command = spu_runner_module._run_command
            spu_runner_module._run_command = lambda command, cwd, timeout: responses.pop(0)  # type: ignore[assignment]
            try:
                result = SpuRunner().run(
                    {
                        "execute": True,
                        "spu_home": str(root),
                        "spu_python": str(python_path),
                    },
                    self._parsed_requirement(),
                    self._spu_config(),
                )
            finally:
                spu_runner_module._run_command = original_run_command

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["result"]["result"], 6)
        self.assertEqual(result["implementation_id"], "spu_aby3")

    def test_resolve_spu_runtime_mode_reads_project_defaults(self) -> None:
        original_loader = spu_runner_module._load_runtime_defaults
        spu_runner_module._load_runtime_defaults = lambda: {"runtime_mode": "wsl"}  # type: ignore[assignment]
        try:
            mode, source = resolve_spu_runtime_mode({})
        finally:
            spu_runner_module._load_runtime_defaults = original_loader

        self.assertEqual(mode, "wsl")
        self.assertEqual(source, "config")

    def test_inspect_spu_runtime_support_wsl_launchable(self) -> None:
        original_loader = spu_runner_module._load_runtime_defaults
        original_run_command = spu_runner_module._run_command
        commands: list[list[str]] = []

        spu_runner_module._load_runtime_defaults = lambda: {  # type: ignore[assignment]
            "runtime_mode": "wsl",
            "wsl_distro": "Ubuntu",
            "spu_home": r"C:\demo\spu-main\spu-main",
            "spu_python_wsl": "/home/demo/.venvs/agent-spu/bin/python",
        }

        def fake_run(command, cwd, timeout):  # type: ignore[no-untyped-def]
            commands.append(command)
            if command[:3] == ["wsl.exe", "-d", "Ubuntu"] and " test -d " not in " ".join(command) and " test -x " not in " ".join(command):
                return {
                    "command": command,
                    "return_code": 0,
                    "duration_seconds": 0.01,
                    "stdout": '{"ok": true, "spu_module": "demo"}',
                    "stderr": "",
                }
            return {
                "command": command,
                "return_code": 0,
                "duration_seconds": 0.01,
                "stdout": "",
                "stderr": "",
            }

        spu_runner_module._run_command = fake_run  # type: ignore[assignment]
        try:
            result = inspect_spu_runtime_support({})
        finally:
            spu_runner_module._load_runtime_defaults = original_loader
            spu_runner_module._run_command = original_run_command

        self.assertTrue(result["launchable"])
        self.assertEqual(result["runtime_mode"], "wsl")
        self.assertEqual(result["wsl_distro"], "Ubuntu")
        self.assertEqual(result["spu_home_wsl"], "/mnt/c/demo/spu-main/spu-main")
        self.assertEqual(result["spu_home_exec"], "/mnt/c/demo/spu-main/spu-main")
        self.assertEqual(result["spu_python"], "/home/demo/.venvs/agent-spu/bin/python")
        self.assertTrue(any(cmd[:3] == ["wsl.exe", "-d", "Ubuntu"] for cmd in commands))

    def test_inspect_spu_runtime_support_wsl_falls_back_to_installed_package(self) -> None:
        original_loader = spu_runner_module._load_runtime_defaults
        original_run_command = spu_runner_module._run_command
        commands: list[list[str]] = []

        spu_runner_module._load_runtime_defaults = lambda: {  # type: ignore[assignment]
            "runtime_mode": "wsl",
            "wsl_distro": "Ubuntu",
            "spu_home": r"C:\demo\spu-main\spu-main",
            "spu_python_wsl": "/home/demo/.venvs/agent-spu/bin/python",
        }

        def fake_run(command, cwd, timeout):  # type: ignore[no-untyped-def]
            commands.append(command)
            rendered = " ".join(command)
            if " test -d " in rendered:
                return {
                    "command": command,
                    "return_code": 1,
                    "duration_seconds": 0.01,
                    "stdout": "",
                    "stderr": "",
                }
            if " test -x " in rendered:
                return {
                    "command": command,
                    "return_code": 0,
                    "duration_seconds": 0.01,
                    "stdout": "",
                    "stderr": "",
                }
            return {
                "command": command,
                "return_code": 0,
                "duration_seconds": 0.01,
                "stdout": '{"ok": true, "spu_module": "installed_demo"}',
                "stderr": "",
            }

        spu_runner_module._run_command = fake_run  # type: ignore[assignment]
        try:
            result = inspect_spu_runtime_support({})
        finally:
            spu_runner_module._load_runtime_defaults = original_loader
            spu_runner_module._run_command = original_run_command

        self.assertTrue(result["launchable"])
        self.assertEqual(result["spu_home_exec"], "")
        self.assertEqual(result["spu_home_exec_source"], "fallback_empty")
        self.assertIn("installed `spu` package", result["spu_home_warning"])
        probe_commands = [cmd for cmd in commands if "--probe" in " ".join(cmd)]
        self.assertEqual(len(probe_commands), 1)
        self.assertIn("--spu-home ''", " ".join(probe_commands[0]))

    def test_spu_runner_run_success_via_wsl(self) -> None:
        original_loader = spu_runner_module._load_runtime_defaults
        original_run_command = spu_runner_module._run_command
        commands: list[list[str]] = []

        spu_runner_module._load_runtime_defaults = lambda: {  # type: ignore[assignment]
            "runtime_mode": "wsl",
            "wsl_distro": "Ubuntu",
            "spu_home": r"C:\demo\spu-main\spu-main",
            "spu_python_wsl": "/home/demo/.venvs/agent-spu/bin/python",
        }

        def fake_run(command, cwd, timeout):  # type: ignore[no-untyped-def]
            commands.append(command)
            rendered = " ".join(command)
            if "--probe" in rendered:
                return {
                    "command": command,
                    "return_code": 0,
                    "duration_seconds": 0.01,
                    "stdout": '{"ok": true, "spu_module": "demo"}',
                    "stderr": "",
                }
            if "--spec" in rendered:
                return {
                    "command": command,
                    "return_code": 0,
                    "duration_seconds": 0.01,
                    "stdout": '{"status": "success", "result": 6, "protocol_kind": "ABY3"}',
                    "stderr": "",
                }
            return {
                "command": command,
                "return_code": 0,
                "duration_seconds": 0.01,
                "stdout": "",
                "stderr": "",
            }

        spu_runner_module._run_command = fake_run  # type: ignore[assignment]
        try:
            result = SpuRunner().run(
                {
                    "execute": True,
                },
                self._parsed_requirement(),
                self._spu_config(),
            )
        finally:
            spu_runner_module._load_runtime_defaults = original_loader
            spu_runner_module._run_command = original_run_command

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["backend"], "secretflow_spu")
        self.assertEqual(result["result"]["result"], 6)
        self.assertTrue(any("--probe" in " ".join(cmd) for cmd in commands))
        run_commands = [cmd for cmd in commands if "--spec" in " ".join(cmd)]
        self.assertEqual(len(run_commands), 1)
        self.assertEqual(run_commands[0][:3], ["wsl.exe", "-d", "Ubuntu"])

    def test_spu_runner_run_success_via_wsl_installed_package_fallback(self) -> None:
        original_loader = spu_runner_module._load_runtime_defaults
        original_run_command = spu_runner_module._run_command
        commands: list[list[str]] = []

        spu_runner_module._load_runtime_defaults = lambda: {  # type: ignore[assignment]
            "runtime_mode": "wsl",
            "wsl_distro": "Ubuntu",
            "spu_home": r"C:\demo\spu-main\spu-main",
            "spu_python_wsl": "/home/demo/.venvs/agent-spu/bin/python",
        }

        def fake_run(command, cwd, timeout):  # type: ignore[no-untyped-def]
            commands.append(command)
            rendered = " ".join(command)
            if " test -d " in rendered:
                return {
                    "command": command,
                    "return_code": 1,
                    "duration_seconds": 0.01,
                    "stdout": "",
                    "stderr": "",
                }
            if " test -x " in rendered:
                return {
                    "command": command,
                    "return_code": 0,
                    "duration_seconds": 0.01,
                    "stdout": "",
                    "stderr": "",
                }
            if "--probe" in rendered:
                return {
                    "command": command,
                    "return_code": 0,
                    "duration_seconds": 0.01,
                    "stdout": '{"ok": true, "spu_module": "installed_demo"}',
                    "stderr": "",
                }
            if "--spec" in rendered:
                return {
                    "command": command,
                    "return_code": 0,
                    "duration_seconds": 0.01,
                    "stdout": '{"status": "success", "result": 6, "protocol_kind": "ABY3"}',
                    "stderr": "",
                }
            return {
                "command": command,
                "return_code": 0,
                "duration_seconds": 0.01,
                "stdout": "",
                "stderr": "",
            }

        spu_runner_module._run_command = fake_run  # type: ignore[assignment]
        try:
            result = SpuRunner().run(
                {
                    "execute": True,
                },
                self._parsed_requirement(),
                self._spu_config(),
            )
        finally:
            spu_runner_module._load_runtime_defaults = original_loader
            spu_runner_module._run_command = original_run_command

        self.assertEqual(result["status"], "success")
        run_commands = [cmd for cmd in commands if "--spec" in " ".join(cmd)]
        self.assertEqual(len(run_commands), 1)
        self.assertIn("--spu-home ''", " ".join(run_commands[0]))

    def test_spu_runner_reports_actionable_reason_when_no_match(self) -> None:
        result = SpuRunner().run(
            {"execute": True},
            self._parsed_requirement(),
            self._spu_config(implementation_id=""),
        )

        self.assertEqual(result["status"], "error")
        self.assertIn("semi_honest", result["reason"])
        self.assertIn("ABY3", result["reason"])


if __name__ == "__main__":
    unittest.main()

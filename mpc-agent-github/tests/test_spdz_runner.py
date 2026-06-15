from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mpc_agent.models import FinalConfiguration, ParsedRequirement
import mpc_agent.spdz_runner as spdz_runner_module
from mpc_agent.spdz_runner import (
    _decode_output,
    _infer_runtime_binary,
    _pick_runtime_reason,
    _run_command,
    _to_bash_path,
    _truncate,
    MpSpdzRunner,
)


class SpdzRunnerUtilsTests(unittest.TestCase):
    def test_truncate_accepts_none(self) -> None:
        self.assertEqual(_truncate(None), "")

    def test_decode_output_fallback_to_gbk(self) -> None:
        gbk_bytes = b"\xd6\xd0\xce\xc4"  # "中文" in GBK
        self.assertEqual(_decode_output(gbk_bytes), "中文")

    def test_run_command_timeout_returns_result(self) -> None:
        result = _run_command(
            ["python", "-c", "import time; time.sleep(2)"],
            cwd=Path("."),
            timeout=1,
        )
        self.assertEqual(result["return_code"], -1)
        self.assertIn("timed out", result["stderr"].lower())

    def test_infer_runtime_binary_from_script(self) -> None:
        script = Path("Scripts/mascot.sh")
        runtime = _infer_runtime_binary(script, Path("C:/tmp/mp-spdz"))
        self.assertEqual(str(runtime).replace("\\", "/"), "C:/tmp/mp-spdz/mascot-party.x")

    def test_to_bash_path_conversion(self) -> None:
        converted = _to_bash_path(Path(r"C:\Users\demo\MP-SPDZ\Scripts\mascot.sh"))
        if converted.startswith("/"):
            self.assertTrue(converted.startswith("/c/Users/demo/MP-SPDZ/Scripts/mascot.sh"))
        else:
            self.assertEqual(converted, r"C:\Users\demo\MP-SPDZ\Scripts\mascot.sh")

    def test_pick_runtime_reason_prefers_meaningful_output(self) -> None:
        reason = _pick_runtime_reason(
            {
                "stderr": "Running /tmp/mascot-party.x 0 demo -N 3\nRunning /tmp/mascot-party.x 1 demo -N 3",
                "stdout": "Fatal error at demo-0:0 (INPUTMIXED): not enough inputs",
            }
        )
        self.assertIn("Fatal error", reason)

    def test_pick_runtime_reason_reports_missing_input_file(self) -> None:
        reason = _pick_runtime_reason(
            {
                "stderr": "",
                "stdout": "Fatal error at demo-0:0 (INPUTMIXED): not enough inputs in Player-Data/Input-P2-0",
            }
        )
        self.assertIn("Missing MPC input file", reason)
        self.assertIn("Input-P2-0", reason)


class SpdzRunnerFlowTests(unittest.TestCase):
    def test_run_returns_error_when_source_write_denied(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Programs" / "Source").mkdir(parents=True, exist_ok=True)
            (root / "compile.py").write_text("print('compiled')\n", encoding="utf-8")

            req = ParsedRequirement(
                raw_requirement="test",
                parties=3,
                operation="aggregation",
                circuit_domain="arithmetic",
                security_model="malicious",
                corruption_model="dishonest_majority",
                latency_priority="normal",
                bandwidth_priority="normal",
                target="production_candidate",
                notes=[],
            )
            config = FinalConfiguration(
                protocol_id="mascot",
                title="test",
                mpspdz_home=str(root),
                script_candidates=["Scripts/mascot.sh"],
                parties=3,
                security_model="malicious",
                corruption_model="dishonest_majority",
                circuit_domain="arithmetic",
                preprocessed=True,
                compile_options=[],
                source_program_name="demo_perm",
                rationale=[],
                references=[],
            )

            def fake_write_text(*args: object, **kwargs: object) -> int:
                raise PermissionError(13, "Permission denied")

            original_write_text = spdz_runner_module.Path.write_text
            spdz_runner_module.Path.write_text = fake_write_text  # type: ignore[assignment]
            try:
                result = MpSpdzRunner().run(
                    {"execute": True, "mpspdz_home": str(root), "program_name": "demo_perm"},
                    req,
                    config,
                )
            finally:
                spdz_runner_module.Path.write_text = original_write_text

            self.assertEqual(result["status"], "error")
            self.assertFalse(result["executed"])
            self.assertIn("Permission denied writing MPC source", result.get("reason", ""))

    def test_run_reports_missing_runtime_binary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Programs" / "Source").mkdir(parents=True, exist_ok=True)
            (root / "Scripts").mkdir(parents=True, exist_ok=True)
            (root / "Scripts" / "mascot.sh").write_text("#!/bin/sh\n", encoding="utf-8")
            (root / "compile.py").write_text(
                "import sys\nprint('ok')\nsys.exit(0)\n",
                encoding="utf-8",
            )

            req = ParsedRequirement(
                raw_requirement="test",
                parties=3,
                operation="aggregation",
                circuit_domain="arithmetic",
                security_model="malicious",
                corruption_model="dishonest_majority",
                latency_priority="normal",
                bandwidth_priority="normal",
                target="production_candidate",
                notes=[],
            )
            config = FinalConfiguration(
                protocol_id="mascot",
                title="test",
                mpspdz_home=str(root),
                script_candidates=["Scripts/mascot.sh"],
                parties=3,
                security_model="malicious",
                corruption_model="dishonest_majority",
                circuit_domain="arithmetic",
                preprocessed=True,
                compile_options=[],
                source_program_name="demo_prog",
                rationale=[],
                references=[],
            )

            result = MpSpdzRunner().run(
                {"execute": True, "mpspdz_home": str(root), "program_name": "demo_prog"},
                req,
                config,
            )

            self.assertEqual(result["status"], "run_failed")
            self.assertIn("Runtime binary not found", result.get("reason", ""))
            self.assertIn("make mascot-party.x", result.get("reason", ""))

    def test_run_reports_missing_launch_script_in_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Programs" / "Source").mkdir(parents=True, exist_ok=True)
            (root / "Scripts").mkdir(parents=True, exist_ok=True)
            (root / "Scripts" / "semi2k.sh").write_text("#!/bin/sh\n", encoding="utf-8")
            (root / "compile.py").write_text(
                "import sys\nprint('ok')\nsys.exit(0)\n",
                encoding="utf-8",
            )

            req = ParsedRequirement(
                raw_requirement="test",
                parties=3,
                operation="comparison",
                circuit_domain="boolean",
                security_model="malicious",
                corruption_model="dishonest_majority",
                latency_priority="normal",
                bandwidth_priority="normal",
                target="production_candidate",
                notes=[],
            )
            config = FinalConfiguration(
                protocol_id="bmr",
                title="test",
                mpspdz_home=str(root),
                script_candidates=["Scripts/bmr.sh", "Scripts/bmr.bat"],
                parties=3,
                security_model="malicious",
                corruption_model="dishonest_majority",
                circuit_domain="boolean",
                preprocessed=False,
                compile_options=[],
                source_program_name="demo_missing_bmr_script",
                rationale=[],
                references=[],
            )

            result = MpSpdzRunner().run(
                {"execute": True, "mpspdz_home": str(root), "program_name": "demo_missing_bmr_script"},
                req,
                config,
            )

            self.assertEqual(result["status"], "run_failed")
            self.assertIn("No protocol launch script found", result.get("reason", ""))
            self.assertIn("execution_preflight", result)
            self.assertIn("semi2k.sh", result["execution_preflight"].get("available_scripts", []))

    def test_run_auto_creates_source_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "compile.py").write_text(
                "import sys\nprint('compiled')\nsys.exit(0)\n",
                encoding="utf-8",
            )

            req = ParsedRequirement(
                raw_requirement="test",
                parties=2,
                operation="aggregation",
                circuit_domain="arithmetic",
                security_model="malicious",
                corruption_model="dishonest_majority",
                latency_priority="normal",
                bandwidth_priority="normal",
                target="production_candidate",
                notes=[],
            )
            config = FinalConfiguration(
                protocol_id="mascot",
                title="test",
                mpspdz_home=str(root),
                script_candidates=["Scripts/mascot.sh"],
                parties=2,
                security_model="malicious",
                corruption_model="dishonest_majority",
                circuit_domain="arithmetic",
                preprocessed=True,
                compile_options=[],
                source_program_name="demo_auto_source_dir",
                rationale=[],
                references=[],
            )

            result = MpSpdzRunner().run(
                {
                    "execute": True,
                    "compile_only": True,
                    "mpspdz_home": str(root),
                    "program_name": "demo_auto_source_dir",
                },
                req,
                config,
            )

            self.assertEqual(result["status"], "compile_only_success")
            source_path = Path(result["source_path"])
            self.assertTrue(source_path.exists())
            self.assertTrue((root / "Programs" / "Source").exists())

    def test_run_compile_only_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Programs" / "Source").mkdir(parents=True, exist_ok=True)
            (root / "compile.py").write_text(
                "import sys\nprint('compiled')\nsys.exit(0)\n",
                encoding="utf-8",
            )

            req = ParsedRequirement(
                raw_requirement="test",
                parties=2,
                operation="aggregation",
                circuit_domain="arithmetic",
                security_model="malicious",
                corruption_model="dishonest_majority",
                latency_priority="normal",
                bandwidth_priority="normal",
                target="production_candidate",
                notes=[],
            )
            config = FinalConfiguration(
                protocol_id="mascot",
                title="test",
                mpspdz_home=str(root),
                script_candidates=["Scripts/mascot.sh"],
                parties=2,
                security_model="malicious",
                corruption_model="dishonest_majority",
                circuit_domain="arithmetic",
                preprocessed=True,
                compile_options=[],
                source_program_name="demo_compile_only",
                rationale=[],
                references=[],
            )

            result = MpSpdzRunner().run(
                {
                    "execute": True,
                    "compile_only": True,
                    "mpspdz_home": str(root),
                    "program_name": "demo_compile_only",
                },
                req,
                config,
            )

            self.assertEqual(result["status"], "compile_only_success")
            self.assertEqual(result["compile"]["return_code"], 0)
            self.assertIn("compile_only=true", result.get("reason", ""))

    def test_run_auto_prepares_default_input_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Programs" / "Source").mkdir(parents=True, exist_ok=True)
            (root / "Scripts").mkdir(parents=True, exist_ok=True)
            (root / "Scripts" / "mascot.sh").write_text("#!/bin/sh\n", encoding="utf-8")
            (root / "compile.py").write_text("print('compiled')\n", encoding="utf-8")
            (root / "mascot-party.x").write_text("", encoding="utf-8")

            req = ParsedRequirement(
                raw_requirement="test",
                parties=3,
                operation="aggregation",
                circuit_domain="arithmetic",
                security_model="malicious",
                corruption_model="dishonest_majority",
                latency_priority="normal",
                bandwidth_priority="normal",
                target="production_candidate",
                notes=[],
            )
            config = FinalConfiguration(
                protocol_id="mascot",
                title="test",
                mpspdz_home=str(root),
                script_candidates=["Scripts/mascot.sh"],
                parties=3,
                security_model="malicious",
                corruption_model="dishonest_majority",
                circuit_domain="arithmetic",
                preprocessed=True,
                compile_options=[],
                source_program_name="demo_inputs",
                rationale=[],
                references=[],
            )

            original_run_command = spdz_runner_module._run_command
            original_which = spdz_runner_module.shutil.which
            spdz_runner_module._run_command = lambda command, cwd, timeout: {  # type: ignore[assignment]
                "command": command,
                "return_code": 0,
                "duration_seconds": 0.01,
                "stdout": "",
                "stderr": "",
            }
            spdz_runner_module.shutil.which = lambda _: "/bin/bash"  # type: ignore[assignment]
            try:
                result = MpSpdzRunner().run(
                    {"execute": True, "mpspdz_home": str(root), "program_name": "demo_inputs"},
                    req,
                    config,
                )
            finally:
                spdz_runner_module._run_command = original_run_command
                spdz_runner_module.shutil.which = original_which

            self.assertEqual(result["status"], "success")
            prep = result.get("preparation", {}).get("inputs", {})
            created = prep.get("created_input_files", [])
            self.assertEqual(len(created), 3)
            self.assertEqual(result.get("preparation", {}).get("inputs_prepared_by"), "runner_builtin")
            for path_str in created:
                self.assertTrue(Path(path_str).exists())

    def test_run_prefers_skill_make_inputs_when_skill_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Programs" / "Source").mkdir(parents=True, exist_ok=True)
            (root / "Scripts").mkdir(parents=True, exist_ok=True)
            (root / "Scripts" / "mascot.sh").write_text("#!/bin/sh\n", encoding="utf-8")
            (root / "compile.py").write_text("print('compiled')\n", encoding="utf-8")
            (root / "mascot-party.x").write_text("", encoding="utf-8")

            req = ParsedRequirement(
                raw_requirement="test",
                parties=3,
                operation="aggregation",
                circuit_domain="arithmetic",
                security_model="malicious",
                corruption_model="dishonest_majority",
                latency_priority="normal",
                bandwidth_priority="normal",
                target="production_candidate",
                notes=[],
            )
            config = FinalConfiguration(
                protocol_id="mascot",
                title="test",
                mpspdz_home=str(root),
                script_candidates=["Scripts/mascot.sh"],
                parties=3,
                security_model="malicious",
                corruption_model="dishonest_majority",
                circuit_domain="arithmetic",
                preprocessed=True,
                compile_options=[],
                source_program_name="demo_skill_inputs",
                rationale=[],
                references=[],
            )

            original_run_command = spdz_runner_module._run_command
            original_which = spdz_runner_module.shutil.which
            original_execute_skill = spdz_runner_module.execute_skill
            spdz_runner_module._run_command = lambda command, cwd, timeout: {  # type: ignore[assignment]
                "command": command,
                "return_code": 0,
                "duration_seconds": 0.01,
                "stdout": "",
                "stderr": "",
            }
            spdz_runner_module.shutil.which = lambda _: "/bin/bash"  # type: ignore[assignment]
            spdz_runner_module.execute_skill = lambda name, payload: {  # type: ignore[assignment]
                "skill": name,
                "action": payload.get("action"),
                "result": {"created_input_files": ["skill://input"], "skipped_existing_files": 0},
            }
            try:
                result = MpSpdzRunner().run(
                    {
                        "execute": True,
                        "mpspdz_home": str(root),
                        "program_name": "demo_skill_inputs",
                        "skills": ["mpspdz-execution"],
                    },
                    req,
                    config,
                )
            finally:
                spdz_runner_module._run_command = original_run_command
                spdz_runner_module.shutil.which = original_which
                spdz_runner_module.execute_skill = original_execute_skill

            self.assertEqual(result["status"], "success")
            self.assertEqual(result.get("preparation", {}).get("inputs_prepared_by"), "skill_script")
            self.assertEqual(
                result.get("preparation", {}).get("inputs", {}).get("created_input_files"),
                ["skill://input"],
            )

    def test_run_passes_party_count_to_protocol_script(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Programs" / "Source").mkdir(parents=True, exist_ok=True)
            (root / "Scripts").mkdir(parents=True, exist_ok=True)
            (root / "Scripts" / "mascot.sh").write_text("#!/bin/sh\n", encoding="utf-8")
            (root / "compile.py").write_text("print('compiled')\n", encoding="utf-8")
            # Prevent early "runtime binary not found" failure.
            (root / "mascot-party.x").write_text("", encoding="utf-8")

            req = ParsedRequirement(
                raw_requirement="test",
                parties=3,
                operation="aggregation",
                circuit_domain="arithmetic",
                security_model="malicious",
                corruption_model="dishonest_majority",
                latency_priority="normal",
                bandwidth_priority="normal",
                target="production_candidate",
                notes=[],
            )
            config = FinalConfiguration(
                protocol_id="mascot",
                title="test",
                mpspdz_home=str(root),
                script_candidates=["Scripts/mascot.sh"],
                parties=3,
                security_model="malicious",
                corruption_model="dishonest_majority",
                circuit_domain="arithmetic",
                preprocessed=True,
                compile_options=[],
                source_program_name="demo_parties",
                rationale=[],
                references=[],
            )

            seen_commands: list[list[str]] = []

            def fake_run(command: list[str], cwd: Path, timeout: int) -> dict[str, object]:
                seen_commands.append(command)
                return {
                    "command": command,
                    "return_code": 0,
                    "duration_seconds": 0.01,
                    "stdout": "",
                    "stderr": "",
                }

            original_run_command = spdz_runner_module._run_command
            original_which = spdz_runner_module.shutil.which
            spdz_runner_module._run_command = fake_run  # type: ignore[assignment]
            spdz_runner_module.shutil.which = lambda _: "/bin/bash"  # type: ignore[assignment]
            try:
                result = MpSpdzRunner().run(
                    {"execute": True, "mpspdz_home": str(root), "program_name": "demo_parties"},
                    req,
                    config,
                )
            finally:
                spdz_runner_module._run_command = original_run_command
                spdz_runner_module.shutil.which = original_which

            self.assertEqual(result["status"], "success")
            self.assertGreaterEqual(len(seen_commands), 2)
            run_cmd = seen_commands[-1]
            self.assertIn("-N", run_cmd)
            self.assertEqual(run_cmd[run_cmd.index("-N") + 1], "3")


if __name__ == "__main__":
    unittest.main()

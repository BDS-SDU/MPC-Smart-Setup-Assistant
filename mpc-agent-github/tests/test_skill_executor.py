from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mpc_agent.skills.executor import execute_skill


class SkillExecutorTests(unittest.TestCase):
    def test_execute_analyze_requirement(self) -> None:
        result = execute_skill(
            "analyze_requirement",
            {
                "requirement": "two-party comparison with low latency",
            },
        )
        self.assertEqual(result["skill"], "analyze_requirement")
        self.assertEqual(result["parsed_requirement"]["operation"], "comparison")

    def test_execute_mpspdz_make_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = execute_skill(
                "mpspdz-execution",
                {
                    "action": "make_inputs",
                    "mpspdz_home": tmp,
                    "parties": 3,
                    "overwrite": False,
                },
            )
            self.assertEqual(result["skill"], "mpspdz-execution")
            created = result["result"]["created_input_files"]
            self.assertEqual(len(created), 3)
            for item in created:
                self.assertTrue(Path(item).exists())

    def test_execute_windows_debug_template(self) -> None:
        result = execute_skill(
            "windows-mpspdz-debug",
            {
                "execution": {
                    "status": "run_failed",
                    "reason": "Permission denied writing MPC source.",
                }
            },
        )
        self.assertEqual(result["skill"], "windows-mpspdz-debug")
        self.assertTrue(result["steps"])
        self.assertIn("Permission denied", result["diagnosis"])

    def test_execute_explain_and_threat(self) -> None:
        explanation = execute_skill(
            "explain_decision",
            {
                "parsed_requirement": {
                    "parties": 3,
                    "operation": "aggregation",
                    "security_model": "malicious",
                },
                "final_configuration": {"protocol_id": "mascot"},
                "candidates": [{"reasons": ["malicious arithmetic scenario"]}],
                "knowledge_context": {
                    "sections": [{"section": "6.6", "title": "SPDZ Family"}],
                },
            },
        )
        self.assertEqual(explanation["skill"], "explain_decision")
        self.assertIn("mascot", explanation["explanation"].lower())

        threat = execute_skill(
            "simulate_threat",
            {
                "parsed_requirement": {
                    "security_model": "malicious",
                    "corruption_model": "dishonest_majority",
                },
                "final_configuration": {"protocol_id": "mascot"},
            },
        )
        self.assertEqual(threat["skill"], "simulate_threat")
        self.assertTrue(threat["risks"])


if __name__ == "__main__":
    unittest.main()

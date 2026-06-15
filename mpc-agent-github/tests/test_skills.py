from __future__ import annotations

import unittest

from mpc_agent.adapters.runner_tool import diagnose_execution_failure
from mpc_agent.skills.registry import get_skill, list_skills
from mpc_agent.skills.router import recommend_skills


class SkillsRegistryTests(unittest.TestCase):
    def test_registry_contains_expected_skills(self) -> None:
        names = {item["name"] for item in list_skills()}
        self.assertIn("analyze_requirement", names)
        self.assertIn("select_protocol", names)
        self.assertIn("generate_configuration", names)
        self.assertIn("protocol-selection", names)
        self.assertIn("mpspdz-execution", names)
        self.assertIn("windows-mpspdz-debug", names)

    def test_get_skill_returns_none_for_unknown(self) -> None:
        self.assertIsNone(get_skill("not-exist"))


class SkillsRouterTests(unittest.TestCase):
    def test_recommend_aggregation_execution_skills(self) -> None:
        payload = {
            "requirement": "4-party aggregation with low bandwidth and execute on mp-spdz",
            "execute": True,
        }
        plan = recommend_skills(payload)
        recommended = set(plan["recommended"])
        self.assertIn("analyze_requirement", recommended)
        self.assertIn("select_protocol", recommended)
        self.assertIn("generate_configuration", recommended)
        self.assertIn("protocol-selection", recommended)
        self.assertIn("arithmetic-aggregation", recommended)
        self.assertIn("deploy_and_monitor", recommended)
        self.assertIn("mpspdz-execution", recommended)

    def test_recommend_boolean_and_windows_debug_skill(self) -> None:
        payload = {
            "requirement": "windows not enough inputs when running 2pc comparison",
        }
        plan = recommend_skills(payload)
        recommended = set(plan["recommended"])
        self.assertIn("boolean-comparison", recommended)
        self.assertIn("windows-mpspdz-debug", recommended)
        self.assertIn("optimize_circuit", recommended)

    def test_diagnose_with_windows_skill_adds_template(self) -> None:
        result = diagnose_execution_failure(
            {"status": "run_failed", "reason": "Permission denied writing MPC source."},
            skills=["windows-mpspdz-debug"],
        )
        self.assertIn("windows_debug", result)
        self.assertEqual(result["windows_debug"]["skill"], "windows-mpspdz-debug")


if __name__ == "__main__":
    unittest.main()

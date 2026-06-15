from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from mpc_agent.mcp.server import LocalMcpServer


class McpServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._case_dir = tempfile.TemporaryDirectory()
        self._old_case_db = os.getenv("MPC_AGENT_CASE_DB")
        os.environ["MPC_AGENT_CASE_DB"] = str(Path(self._case_dir.name) / "cases.jsonl")
        self.server = LocalMcpServer()

    def tearDown(self) -> None:
        if self._old_case_db is None:
            os.environ.pop("MPC_AGENT_CASE_DB", None)
        else:
            os.environ["MPC_AGENT_CASE_DB"] = self._old_case_db
        self._case_dir.cleanup()

    def test_capabilities_contains_tools_resources_prompts(self) -> None:
        caps = self.server.capabilities()
        self.assertIn("tools", caps)
        self.assertIn("resources", caps)
        self.assertIn("prompts", caps)
        tool_names = {item["name"] for item in caps["tools"]}
        self.assertIn("parse_requirement", tool_names)
        self.assertIn("rank_protocols", tool_names)
        self.assertIn("recommend_open_source_protocols", tool_names)
        self.assertIn("recommend_skills", tool_names)
        self.assertIn("retrieve_knowledge", tool_names)
        self.assertIn("list_cases", tool_names)
        self.assertIn("probe_network", tool_names)
        self.assertIn("query_hardware", tool_names)
        self.assertIn("collect_runtime_signals", tool_names)
        self.assertIn("list_external_systems", tool_names)
        self.assertIn("call_external_api", tool_names)

    def test_call_parse_and_rank_tool(self) -> None:
        parsed = self.server.handle_request(
            {
                "action": "call_tool",
                "name": "parse_requirement",
                "arguments": {"requirement": "two-party comparison with low latency"},
            }
        )
        parsed_req = parsed["result"]["parsed_requirement"]
        self.assertEqual(parsed_req["parties"], 2)

        ranked = self.server.handle_request(
            {
                "action": "call_tool",
                "name": "rank_protocols",
                "arguments": {"parsed_requirement": parsed_req, "top_k": 2},
            }
        )
        self.assertEqual(len(ranked["result"]["candidates"]), 2)

    def test_compile_tool_with_temp_mpspdz(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Programs" / "Source").mkdir(parents=True, exist_ok=True)
            (root / "compile.py").write_text(
                "import sys\nprint('compiled')\nsys.exit(0)\n",
                encoding="utf-8",
            )

            result = self.server.handle_request(
                {
                    "action": "call_tool",
                    "name": "compile_mpspdz_program",
                    "arguments": {
                        "payload": {
                            "requirement": "3-party aggregation with malicious security",
                            "parties": 3,
                            "execute": True,
                            "compile_only": True,
                            "mpspdz_home": str(root),
                        }
                    },
                }
            )
            execution = result["result"]["execution"]
            self.assertEqual(execution["status"], "compile_only_success")
            self.assertEqual(execution["compile"]["return_code"], 0)

    def test_execute_skill_tool(self) -> None:
        result = self.server.handle_request(
            {
                "action": "call_tool",
                "name": "execute_skill",
                "arguments": {
                    "name": "protocol-selection",
                    "payload": {},
                },
            }
        )
        self.assertEqual(result["result"]["skill"], "protocol-selection")

    def test_case_tools_and_feedback(self) -> None:
        config_result = self.server.handle_request(
            {
                "action": "call_tool",
                "name": "generate_configuration",
                "arguments": {
                    "payload": {
                        "requirement": "3-party malicious aggregation",
                        "parties": 3,
                        "execute": False,
                    }
                },
            }
        )
        self.assertIn("final_configuration", config_result["result"])

        cases_result = self.server.handle_request(
            {
                "action": "call_tool",
                "name": "list_cases",
                "arguments": {"limit": 5},
            }
        )
        self.assertTrue(cases_result["result"]["cases"])
        case_id = cases_result["result"]["cases"][0]["case_id"]

        feedback_result = self.server.handle_request(
            {
                "action": "call_tool",
                "name": "record_case_feedback",
                "arguments": {
                    "case_id": case_id,
                    "feedback": {"runtime_seconds": 12.3},
                },
            }
        )
        self.assertEqual(feedback_result["result"]["case"]["case_id"], case_id)

    def test_generate_configuration_preserves_structured_dimensions(self) -> None:
        result = self.server.handle_request(
            {
                "action": "call_tool",
                "name": "generate_configuration",
                "arguments": {
                    "payload": {
                        "requirement": "",
                        "party_count_mode": "three_party",
                        "circuit_domain": "arithmetic",
                        "math_structure": "finite_field",
                        "secret_sharing": "shamir",
                        "security_model": "semi_honest",
                        "corruption_threshold": "t_lt_n_over_2",
                        "security_goal": "guaranteed_output_delivery",
                        "execute": False,
                    }
                },
            }
        )
        parsed = result["result"]["parsed_requirement"]
        final_config = result["result"]["final_configuration"]
        recommendations = result["result"]["open_source_recommendations"]
        self.assertEqual(parsed["party_count_mode"], "three_party")
        self.assertEqual(parsed["secret_sharing"], "shamir")
        self.assertEqual(final_config["security_goal"], "guaranteed_output_delivery")
        self.assertEqual(final_config["math_structure"], "finite_field")
        self.assertIn("matches", recommendations)

    def test_open_source_protocol_resource_and_tool(self) -> None:
        resource = self.server.handle_request(
            {
                "action": "read_resource",
                "uri": "protocol://catalog/open-source",
            }
        )
        self.assertGreater(resource["content"]["summary"]["deployment_count"], 0)
        self.assertTrue(resource["content"]["deployments"])

        result = self.server.handle_request(
            {
                "action": "call_tool",
                "name": "recommend_open_source_protocols",
                "arguments": {
                    "requirement": "",
                    "parties": 3,
                    "party_count_mode": "three_party",
                    "circuit_domain": "mixed",
                    "math_structure": "ring",
                    "secret_sharing": "replicated",
                    "security_model": "semi_honest",
                    "corruption_model": "honest_majority",
                },
            }
        )
        matches = result["result"]["recommendations"]["matches"]
        self.assertTrue(matches)
        self.assertEqual(matches[0]["implementation_id"], "spu_aby3")

    def test_generate_configuration_can_select_secretflow_spu_backend(self) -> None:
        result = self.server.handle_request(
            {
                "action": "call_tool",
                "name": "generate_configuration",
                "arguments": {
                    "payload": {
                        "requirement": "",
                        "runtime_backend": "secretflow_spu",
                        "parties": 3,
                        "party_count_mode": "three_party",
                        "circuit_domain": "mixed",
                        "math_structure": "ring",
                        "secret_sharing": "replicated",
                        "security_model": "semi_honest",
                        "corruption_model": "honest_majority",
                    }
                },
            }
        )

        final_config = result["result"]["final_configuration"]
        self.assertEqual(final_config["runner_backend"], "secretflow_spu")
        self.assertEqual(final_config["implementation_id"], "spu_aby3")

    def test_generate_configuration_can_select_crypten_backend(self) -> None:
        result = self.server.handle_request(
            {
                "action": "call_tool",
                "name": "generate_configuration",
                "arguments": {
                    "payload": {
                        "requirement": "",
                        "runtime_backend": "crypten",
                        "parties": 2,
                        "party_count_mode": "two_party",
                        "circuit_domain": "arithmetic",
                        "math_structure": "ring",
                        "security_model": "semi_honest",
                        "corruption_model": "dishonest_majority",
                    }
                },
            }
        )

        final_config = result["result"]["final_configuration"]
        self.assertEqual(final_config["runner_backend"], "crypten")
        self.assertEqual(final_config["implementation_id"], "crypten_semi2k")

    def test_generate_configuration_can_select_spu_semi2k_backend(self) -> None:
        result = self.server.handle_request(
            {
                "action": "call_tool",
                "name": "generate_configuration",
                "arguments": {
                    "payload": {
                        "requirement": "Semi2k arithmetic aggregation",
                        "runtime_backend": "secretflow_spu",
                        "parties": 2,
                    }
                },
            }
        )

        final_config = result["result"]["final_configuration"]
        self.assertEqual(final_config["runner_backend"], "secretflow_spu")
        self.assertEqual(final_config["implementation_id"], "spu_semi2k")

    def test_generate_configuration_can_select_crypten_semi2k_backend(self) -> None:
        result = self.server.handle_request(
            {
                "action": "call_tool",
                "name": "generate_configuration",
                "arguments": {
                    "payload": {
                        "requirement": "Semi2k arithmetic aggregation",
                        "runtime_backend": "crypten",
                        "parties": 2,
                    }
                },
            }
        )

        final_config = result["result"]["final_configuration"]
        self.assertEqual(final_config["runner_backend"], "crypten")
        self.assertEqual(final_config["implementation_id"], "crypten_semi2k")

    def test_collect_runtime_signals_tool(self) -> None:
        result = self.server.handle_request(
            {
                "action": "call_tool",
                "name": "collect_runtime_signals",
                "arguments": {
                    "payload": {
                        "network_metrics": {
                            "source": "provided",
                            "summary": {
                                "avg_rtt_ms": 80,
                                "estimated_bandwidth_mbps": 30,
                            },
                        },
                        "hardware_parties": [
                            {"name": "P0", "cpu_cores": 4, "memory_gb": 8},
                            {"name": "P1", "cpu_cores": 8, "memory_gb": 16},
                        ],
                    },
                    "parsed_requirement": {
                        "raw_requirement": "comparison",
                        "parties": 2,
                        "operation": "comparison",
                        "circuit_domain": "boolean",
                        "security_model": "malicious",
                        "corruption_model": "dishonest_majority",
                        "latency_priority": "high",
                        "bandwidth_priority": "normal",
                        "target": "production_candidate",
                        "notes": [],
                    },
                },
            }
        )
        bias = result["result"]["protocol_bias"]
        self.assertGreater(bias.get("yao", 0), 0)
        self.assertLess(bias.get("gmw", 0), 0)

    def test_list_external_systems_tool(self) -> None:
        old = os.getenv("EXTERNAL_SYSTEMS_JSON")
        os.environ["EXTERNAL_SYSTEMS_JSON"] = (
            '[{"name":"demo","base_url":"https://api.example.com","allow_write":false}]'
        )
        try:
            result = self.server.handle_request(
                {
                    "action": "call_tool",
                    "name": "list_external_systems",
                    "arguments": {},
                }
            )
            systems = result["result"]["systems"]
            self.assertEqual(len(systems), 1)
            self.assertEqual(systems[0]["name"], "demo")
        finally:
            if old is None:
                os.environ.pop("EXTERNAL_SYSTEMS_JSON", None)
            else:
                os.environ["EXTERNAL_SYSTEMS_JSON"] = old


if __name__ == "__main__":
    unittest.main()

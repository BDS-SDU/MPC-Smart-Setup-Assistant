from __future__ import annotations

import unittest

from mpc_agent.parser import parse_requirement


class ParserTests(unittest.TestCase):
    def test_parse_malicious_multi_party_aggregation(self) -> None:
        payload = {
            "requirement": "3方联合统计，恶意安全，低带宽，任务是求和。",
        }
        parsed = parse_requirement(payload)
        self.assertEqual(parsed.parties, 3)
        self.assertEqual(parsed.operation, "aggregation")
        self.assertEqual(parsed.security_model, "malicious")
        self.assertEqual(parsed.circuit_domain, "arithmetic")

    def test_parse_boolean_comparison_two_party(self) -> None:
        payload = {"requirement": "two-party millionaire comparison with low latency"}
        parsed = parse_requirement(payload)
        self.assertEqual(parsed.parties, 2)
        self.assertEqual(parsed.operation, "comparison")
        self.assertIn(parsed.circuit_domain, {"boolean", "mixed"})
        self.assertEqual(parsed.latency_priority, "high")

    def test_parse_chinese_number_and_honest_majority(self) -> None:
        payload = {
            "requirement": "三方机器学习推理，诚实多数，半诚实模型，低带宽",
        }
        parsed = parse_requirement(payload)
        self.assertEqual(parsed.parties, 3)
        self.assertEqual(parsed.operation, "ml")
        self.assertEqual(parsed.security_model, "semi_honest")
        self.assertEqual(parsed.corruption_model, "honest_majority")
        self.assertEqual(parsed.bandwidth_priority, "high")

    def test_parse_structured_fields_override_text(self) -> None:
        payload = {
            "requirement": "two-party comparison",
            "parties": 5,
            "operation": "aggregation",
            "security_model": "semi_honest",
            "corruption_model": "honest_majority",
            "circuit_domain": "arithmetic",
            "target": "prototype",
        }
        parsed = parse_requirement(payload)
        self.assertEqual(parsed.parties, 5)
        self.assertEqual(parsed.operation, "aggregation")
        self.assertEqual(parsed.security_model, "semi_honest")
        self.assertEqual(parsed.corruption_model, "honest_majority")
        self.assertEqual(parsed.circuit_domain, "arithmetic")
        self.assertEqual(parsed.target, "prototype")

    def test_parse_structured_mpc_dimensions(self) -> None:
        payload = {
            "requirement": "",
            "party_count_mode": "n_party",
            "circuit_domain": "arithmetic",
            "math_structure": "ring",
            "secret_sharing": "shamir",
            "preprocessing_preference": "required",
            "security_model": "malicious",
            "corruption_timing": "adaptive",
            "network_model": "asynchronous",
            "corruption_threshold": "t_lt_n_over_3",
            "security_goal": "guaranteed_output_delivery",
        }
        parsed = parse_requirement(payload)
        self.assertEqual(parsed.parties, 4)
        self.assertEqual(parsed.party_count_mode, "n_party")
        self.assertEqual(parsed.math_structure, "ring")
        self.assertEqual(parsed.secret_sharing, "shamir")
        self.assertEqual(parsed.corruption_threshold, "t_lt_n_over_3")
        self.assertEqual(parsed.security_goal, "guaranteed_output_delivery")
        self.assertTrue(any("Shamir" in note for note in parsed.compatibility_notes))

    def test_parse_semi2k_protocol_family(self) -> None:
        parsed = parse_requirement(
            {
                "requirement": "Semi2k arithmetic aggregation",
                "parties": 2,
            }
        )

        self.assertEqual(parsed.security_model, "semi_honest")
        self.assertEqual(parsed.math_structure, "ring")
        self.assertEqual(parsed.secret_sharing, "additive")


if __name__ == "__main__":
    unittest.main()

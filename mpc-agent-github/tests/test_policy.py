from __future__ import annotations

import unittest

from mpc_agent.parser import parse_requirement
from mpc_agent.policy import rank_candidates


class PolicyTests(unittest.TestCase):
    def test_malicious_arithmetic_prefers_mascot(self) -> None:
        req = parse_requirement(
            {
                "requirement": "4方恶意安全的隐私求和，非诚实多数，在线带宽敏感。",
                "parties": 4,
            }
        )
        candidates = rank_candidates(req, top_k=2)
        top = candidates[0]
        self.assertEqual(top.protocol_id, "mascot")

    def test_two_party_comparison_prefers_yao(self) -> None:
        req = parse_requirement(
            {
                "requirement": "2PC comparison with low latency and malicious security",
                "parties": 2,
            }
        )
        candidates = rank_candidates(req, top_k=2)
        top = candidates[0]
        self.assertEqual(top.protocol_id, "yao")

    def test_dishonest_majority_avoids_honest_majority_protocol(self) -> None:
        req = parse_requirement(
            {
                "requirement": "4-party aggregation, malicious, dishonest majority",
                "parties": 4,
            }
        )
        candidates = rank_candidates(req, top_k=4)
        self.assertNotEqual(candidates[0].protocol_id, "shamir")
        shamir = [item for item in candidates if item.protocol_id == "shamir"]
        if shamir:
            self.assertLess(shamir[0].score, candidates[0].score)

    def test_semi_honest_arithmetic_prefers_semi2k(self) -> None:
        req = parse_requirement(
            {
                "requirement": "5-party arithmetic aggregation, semi-honest, low bandwidth, dishonest majority",
                "parties": 5,
            }
        )
        candidates = rank_candidates(req, top_k=2)
        self.assertEqual(candidates[0].protocol_id, "semi2k")

    def test_skill_bias_can_shift_ranking(self) -> None:
        req = parse_requirement(
            {
                "requirement": "2-party generic task",
                "parties": 2,
            }
        )
        base = rank_candidates(req, top_k=1)
        biased = rank_candidates(req, top_k=1, skill_names=["boolean-comparison"])
        self.assertEqual(base[0].protocol_id, "mascot")
        self.assertEqual(biased[0].protocol_id, "yao")
        self.assertTrue(any("Skill `boolean-comparison` applied" in r for r in biased[0].reasons))

    def test_protocol_bias_supports_penalty(self) -> None:
        req = parse_requirement(
            {
                "requirement": "2-party comparison with low latency",
                "parties": 2,
            }
        )
        base = rank_candidates(req, top_k=2)
        penalized = rank_candidates(req, top_k=2, protocol_bias={"yao": -20})
        self.assertEqual(base[0].protocol_id, "yao")
        self.assertNotEqual(penalized[0].protocol_id, "yao")

    def test_guaranteed_output_delivery_prefers_shamir(self) -> None:
        req = parse_requirement(
            {
                "requirement": "",
                "parties": 3,
                "circuit_domain": "arithmetic",
                "security_model": "semi_honest",
                "corruption_model": "honest_majority",
                "corruption_threshold": "t_lt_n_over_2",
                "security_goal": "guaranteed_output_delivery",
            }
        )
        candidates = rank_candidates(req, top_k=2)
        self.assertEqual(candidates[0].protocol_id, "shamir")


if __name__ == "__main__":
    unittest.main()

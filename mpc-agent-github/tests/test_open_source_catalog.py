from __future__ import annotations

import unittest

from mpc_agent.open_source_catalog import recommend_open_source_protocols
from mpc_agent.parser import parse_requirement


class OpenSourceCatalogTests(unittest.TestCase):
    def test_async_god_prefers_honeybadgermpc(self) -> None:
        req = parse_requirement(
            {
                "requirement": "",
                "parties": 4,
                "party_count_mode": "n_party",
                "circuit_domain": "arithmetic",
                "math_structure": "finite_field",
                "security_model": "malicious",
                "corruption_model": "honest_majority",
                "corruption_threshold": "t_lt_n_over_3",
                "network_model": "asynchronous",
                "security_goal": "guaranteed_output_delivery",
            }
        )

        result = recommend_open_source_protocols(req, limit=3)

        self.assertTrue(result["matches"])
        self.assertEqual(result["matches"][0]["implementation_id"], "honeybadgermpc")

    def test_adaptive_is_marked_as_research_gap(self) -> None:
        req = parse_requirement(
            {
                "requirement": "",
                "parties": 3,
                "party_count_mode": "three_party",
                "circuit_domain": "arithmetic",
                "security_model": "malicious",
                "corruption_model": "honest_majority",
                "corruption_timing": "adaptive",
            }
        )

        result = recommend_open_source_protocols(req, limit=5)

        self.assertEqual(result["matches"], [])
        self.assertEqual(result["research_gaps"][0]["gap_id"], "adaptive_generic_mpc")

    def test_replicated_three_party_prefers_spu_aby3(self) -> None:
        req = parse_requirement(
            {
                "requirement": "",
                "parties": 3,
                "party_count_mode": "three_party",
                "circuit_domain": "mixed",
                "math_structure": "ring",
                "secret_sharing": "replicated",
                "security_model": "semi_honest",
                "corruption_model": "honest_majority",
            }
        )

        result = recommend_open_source_protocols(req, limit=3)

        self.assertTrue(result["matches"])
        self.assertEqual(result["matches"][0]["implementation_id"], "spu_aby3")

    def test_two_party_ring_backend_includes_crypten(self) -> None:
        req = parse_requirement(
            {
                "requirement": "",
                "parties": 2,
                "party_count_mode": "two_party",
                "circuit_domain": "arithmetic",
                "math_structure": "ring",
                "security_model": "semi_honest",
                "corruption_model": "dishonest_majority",
            }
        )

        result = recommend_open_source_protocols(req, limit=20)

        self.assertTrue(result["matches"])
        self.assertTrue(
            any(item["implementation_id"] == "crypten_tensor" for item in result["matches"])
        )


if __name__ == "__main__":
    unittest.main()

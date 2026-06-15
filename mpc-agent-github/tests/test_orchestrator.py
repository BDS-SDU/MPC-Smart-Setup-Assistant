from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mpc_agent.orchestrator import _annotate_execution_support, _build_final_config, _select_protocol
from mpc_agent.parser import parse_requirement
from mpc_agent.policy import rank_candidates


class OrchestratorSelectionTests(unittest.TestCase):
    def test_yao_final_config_uses_garbled_compile_option(self) -> None:
        config = _build_final_config(
            "yao",
            {
                "parties": 2,
                "security_model": "semi_honest",
                "corruption_model": "dishonest_majority",
                "circuit_domain": "boolean",
                "party_count_mode": "two_party",
                "math_structure": "auto",
                "secret_sharing": "auto",
                "preprocessing_preference": "auto",
                "corruption_timing": "auto",
                "network_model": "auto",
                "corruption_threshold": "auto",
                "security_goal": "auto",
                "compatibility_notes": [],
            },
            ["test"],
        )

        self.assertEqual(config.compile_options, ["-B", "32", "-G"])

    def test_select_protocol_falls_back_to_launchable_core_compatible_candidate(self) -> None:
        req = parse_requirement(
            {
                "requirement": "",
                "parties": 3,
                "circuit_domain": "arithmetic",
                "security_model": "semi_honest",
                "corruption_model": "honest_majority",
            }
        )
        candidates = [candidate.to_dict() for candidate in rank_candidates(req, top_k=4)]

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Scripts").mkdir(parents=True, exist_ok=True)
            (root / "Scripts" / "semi2k.sh").write_text("#!/bin/sh\n", encoding="utf-8")
            (root / "semi2k-party.x").write_text("", encoding="utf-8")

            payload = {"execute": True, "mpspdz_home": str(root)}
            _annotate_execution_support(candidates, payload)

            selected, rationale = _select_protocol(
                candidates,
                {"used": False, "recommended_protocol_id": ""},
                req.to_dict(),
                payload,
            )

        self.assertEqual(selected, "semi2k")
        self.assertTrue(any("Fell back to launchable core-compatible candidate" in item for item in rationale))


if __name__ == "__main__":
    unittest.main()

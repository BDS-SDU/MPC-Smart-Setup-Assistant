from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from mpc_agent.case_store import append_case, find_similar_cases, list_cases, record_feedback, summarize_protocol_bias


class CaseStoreTests(unittest.TestCase):
    def test_append_list_similar_feedback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "cases.jsonl"
            old = os.getenv("MPC_AGENT_CASE_DB")
            os.environ["MPC_AGENT_CASE_DB"] = str(db_path)
            try:
                stored = append_case(
                    {
                        "parsed_requirement": {
                            "parties": 3,
                            "operation": "aggregation",
                            "circuit_domain": "arithmetic",
                            "security_model": "malicious",
                            "corruption_model": "dishonest_majority",
                            "latency_priority": "normal",
                            "bandwidth_priority": "normal",
                        },
                        "selected_protocol": "mascot",
                        "execution_status": "success",
                    }
                )
                self.assertTrue(stored["case_id"])

                rows = list_cases(limit=5)
                self.assertEqual(len(rows), 1)

                similar = find_similar_cases(
                    {
                        "parties": 3,
                        "operation": "aggregation",
                        "circuit_domain": "arithmetic",
                        "security_model": "malicious",
                        "corruption_model": "dishonest_majority",
                        "latency_priority": "normal",
                        "bandwidth_priority": "normal",
                    },
                    limit=3,
                )
                self.assertEqual(len(similar), 1)
                self.assertEqual(similar[0]["selected_protocol"], "mascot")

                bias = summarize_protocol_bias(similar)
                self.assertGreater(bias.get("mascot", 0), 0)

                updated = record_feedback(stored["case_id"], {"runtime_seconds": 2.1})
                self.assertEqual(updated["feedback"]["runtime_seconds"], 2.1)
            finally:
                if old is None:
                    os.environ.pop("MPC_AGENT_CASE_DB", None)
                else:
                    os.environ["MPC_AGENT_CASE_DB"] = old


if __name__ == "__main__":
    unittest.main()

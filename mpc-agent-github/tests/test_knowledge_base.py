from __future__ import annotations

import unittest

from mpc_agent.knowledge_base import list_sections, retrieve_knowledge


class KnowledgeBaseTests(unittest.TestCase):
    def test_list_sections(self) -> None:
        sections = list_sections()
        self.assertTrue(sections)
        self.assertTrue(any(item["section"] == "6.6" for item in sections))

    def test_retrieve_knowledge(self) -> None:
        result = retrieve_knowledge("malicious arithmetic spdz", top_k=3)
        self.assertEqual(result["query"], "malicious arithmetic spdz")
        self.assertTrue(result["sections"])


if __name__ == "__main__":
    unittest.main()

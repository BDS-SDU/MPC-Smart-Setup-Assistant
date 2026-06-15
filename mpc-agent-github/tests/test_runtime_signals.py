from __future__ import annotations

import unittest

import mpc_agent.runtime_signals as runtime_signals_module
from mpc_agent.runtime_signals import collect_runtime_signals, infer_protocol_bias, summarize_party_hardware


class RuntimeSignalsTests(unittest.TestCase):
    def test_infer_protocol_bias_from_latency_and_bandwidth(self) -> None:
        parsed = {
            "operation": "comparison",
            "circuit_domain": "boolean",
            "security_model": "malicious",
        }
        network = {
            "summary": {
                "avg_rtt_ms": 90,
                "estimated_bandwidth_mbps": 25,
            }
        }
        hardware = {
            "summary": {
                "min_compute_score": 6,
                "avg_compute_score": 10,
                "heterogeneity_ratio": 1.2,
            }
        }

        bias, reasons = infer_protocol_bias(parsed, network, hardware)
        self.assertGreater(bias.get("yao", 0), 0)
        self.assertGreater(bias.get("bmr", 0), 0)
        self.assertLess(bias.get("gmw", 0), 0)
        self.assertTrue(reasons)

    def test_summarize_party_hardware(self) -> None:
        summary = summarize_party_hardware(
            [
                {"name": "P0", "cpu_cores": 4, "memory_gb": 8},
                {"name": "P1", "cpu_cores": 8, "memory_gb": 16},
            ],
            use_local_when_empty=False,
        )
        self.assertEqual(summary["summary"]["party_count"], 2)
        self.assertGreater(summary["summary"]["avg_compute_score"], 0)

    def test_collect_runtime_signals_prefers_provided_metrics(self) -> None:
        parsed = {
            "operation": "aggregation",
            "circuit_domain": "arithmetic",
            "security_model": "malicious",
            "corruption_model": "dishonest_majority",
        }
        payload = {
            "network_metrics": {
                "source": "provided",
                "summary": {
                    "avg_rtt_ms": 35,
                    "estimated_bandwidth_mbps": 20,
                },
            },
            "hardware_parties": [
                {"name": "P0", "cpu_cores": 2, "memory_gb": 4},
                {"name": "P1", "cpu_cores": 16, "memory_gb": 32},
            ],
        }
        result = collect_runtime_signals(payload, parsed)
        self.assertEqual(result["network"]["source"], "provided")
        self.assertIn("protocol_bias", result)
        self.assertTrue(result["bias_reasons"])

    def test_collect_runtime_signals_from_external_api(self) -> None:
        parsed = {
            "operation": "comparison",
            "circuit_domain": "boolean",
            "security_model": "malicious",
            "corruption_model": "dishonest_majority",
        }

        def fake_call_external_api(
            *,
            system_name: str,
            method: str = "GET",
            path: str = "",
            query: dict[str, object] | None = None,
            headers: dict[str, object] | None = None,
            body: object = None,
            timeout_seconds: int | None = None,
        ) -> dict[str, object]:
            _ = (method, path, query, headers, body, timeout_seconds)
            if system_name == "netprobe":
                return {
                    "ok": True,
                    "json": {
                        "parties": [
                            {"name": "P0", "avg_rtt_ms": 70, "bandwidth_mbps": 30},
                            {"name": "P1", "avg_rtt_ms": 80, "bandwidth_mbps": 28},
                        ]
                    },
                }
            if system_name == "hwprobe":
                return {
                    "ok": True,
                    "json": {
                        "parties": [
                            {"name": "P0", "cpu_cores": 4, "memory_gb": 8},
                            {"name": "P1", "cpu_cores": 6, "memory_gb": 12},
                        ]
                    },
                }
            return {"ok": False, "status": 404, "reason": "not found", "json": None}

        original = runtime_signals_module.call_external_api
        runtime_signals_module.call_external_api = fake_call_external_api  # type: ignore[assignment]
        try:
            result = collect_runtime_signals(
                {
                    "external_network_probe": {
                        "system_name": "netprobe",
                        "path": "/probe",
                        "method": "POST",
                    },
                    "external_hardware_query": {
                        "system_name": "hwprobe",
                        "path": "/hardware",
                        "method": "GET",
                    },
                },
                parsed,
            )
        finally:
            runtime_signals_module.call_external_api = original

        self.assertTrue(str(result["network"]["source"]).startswith("external_api:"))
        self.assertTrue(str(result["hardware"]["source"]).startswith("external_api:"))
        self.assertGreater(result["protocol_bias"].get("yao", 0), 0)
        self.assertLess(result["protocol_bias"].get("gmw", 0), 0)


if __name__ == "__main__":
    unittest.main()

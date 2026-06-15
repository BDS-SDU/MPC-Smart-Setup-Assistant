from __future__ import annotations

from typing import Any

from .crypten_runner import CrypTenRunner
from .models import FinalConfiguration, ParsedRequirement
from .spdz_runner import MpSpdzRunner
from .spu_runner import SpuRunner


def _normalize_backend(value: Any) -> str:
    normalized = str(value or "").strip().lower().replace("-", "_")
    if normalized in {"spu", "secretflow_spu", "secretflow"}:
        return "secretflow_spu"
    if normalized in {"crypten", "cryp_ten"}:
        return "crypten"
    if normalized in {"mp_spdz", "mpspdz", "mp_spdz"}:
        return "mp_spdz"
    return "mp_spdz"


class RuntimeRunner:
    def __init__(self) -> None:
        self.mpspdz = MpSpdzRunner()
        self.secretflow_spu = SpuRunner()
        self.crypten = CrypTenRunner()

    def run(
        self,
        payload: dict[str, Any],
        req: ParsedRequirement,
        config: FinalConfiguration,
    ) -> dict[str, Any]:
        backend = _normalize_backend(config.runner_backend or payload.get("runtime_backend"))
        if backend == "secretflow_spu":
            return self.secretflow_spu.run(payload, req, config)
        if backend == "crypten":
            return self.crypten.run(payload, req, config)
        return self.mpspdz.run(payload, req, config)

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


def _repo_add_path(spu_home: str) -> None:
    if not spu_home:
        return
    root = Path(spu_home).expanduser().resolve()
    if root.exists():
        sys.path.insert(0, str(root))


def _ensure_spu_import_path(spu_home: str) -> None:
    if importlib.util.find_spec("spu") is None:
        _repo_add_path(spu_home)


def _probe(spu_home: str) -> dict[str, Any]:
    _ensure_spu_import_path(spu_home)
    result: dict[str, Any] = {
        "ok": False,
        "spu_home": spu_home,
        "python_executable": sys.executable,
        "python_version": sys.version,
    }

    try:
        import jax  # type: ignore
        import numpy  # type: ignore
        import spu  # type: ignore
    except Exception as error:  # noqa: BLE001
        result["reason"] = str(error)
        return result

    result["ok"] = True
    result["jax_version"] = getattr(jax, "__version__", "")
    result["numpy_version"] = getattr(numpy, "__version__", "")
    result["spu_module"] = getattr(spu, "__file__", "")
    return result


def _normalize_inputs(raw_inputs: list[Any], expected_parties: int) -> list[Any]:
    if raw_inputs:
        return raw_inputs
    return [index + 1 for index in range(expected_parties)]


def _protocol_kind(libspu: Any, protocol_name: str) -> Any:
    mapping = {
        "SEMI2K": libspu.ProtocolKind.SEMI2K,
        "ABY3": libspu.ProtocolKind.ABY3,
        "CHEETAH": libspu.ProtocolKind.CHEETAH,
    }
    return mapping[protocol_name]


def _field_kind(libspu: Any, field_name: str) -> Any:
    mapping = {
        "FM32": libspu.FieldType.FM32,
        "FM64": libspu.FieldType.FM64,
        "FM128": libspu.FieldType.FM128,
    }
    return mapping[field_name]


def _build_function(jnp: Any, operation: str):
    if operation == "comparison":
        def compare(x, y):
            return x < y

        return compare

    if operation == "aggregation":
        def aggregate(*args):
            acc = args[0]
            for item in args[1:]:
                acc = acc + item
            return acc

        return aggregate

    def generic(*args):
        acc = args[0]
        for item in args[1:]:
            acc = acc + item
        return acc

    _ = jnp
    return generic


def _run(spec: dict[str, Any]) -> dict[str, Any]:
    spu_home = str(spec.get("spu_home", "")).strip()
    _ensure_spu_import_path(spu_home)

    import jax.numpy as jnp  # type: ignore
    import numpy as np  # type: ignore
    import spu.libspu as libspu  # type: ignore
    from spu.utils.simulation import Simulator, sim_jax  # type: ignore

    operation = str(spec.get("operation", "generic")).strip().lower()
    implementation_id = str(spec.get("implementation_id", "")).strip()
    protocol_name = str(spec.get("protocol_kind", "ABY3")).strip().upper()
    field_name = str(spec.get("field", "FM64")).strip().upper()
    parties = int(spec.get("parties", 2))
    compile_only = bool(spec.get("compile_only", False))
    raw_inputs = spec.get("inputs", [])
    inputs = _normalize_inputs(raw_inputs if isinstance(raw_inputs, list) else [], parties)

    if protocol_name == "ABY3" and parties != 3:
        raise ValueError("ABY3 requires exactly 3 parties.")
    if protocol_name == "CHEETAH" and parties != 2:
        raise ValueError("Cheetah requires exactly 2 parties.")

    protocol_kind = _protocol_kind(libspu, protocol_name)
    field_kind = _field_kind(libspu, field_name)
    sim = Simulator.simple(parties, protocol_kind, field_kind)
    fn = _build_function(jnp, operation)
    spu_fn = sim_jax(sim, fn)

    normalized_args = [np.array(item) for item in inputs]

    if compile_only:
        return {
            "status": "compile_only_success",
            "implementation_id": implementation_id,
            "protocol_kind": protocol_name,
            "field": field_name,
            "parties": parties,
            "operation": operation,
            "inputs": inputs,
            "reason": "SPU simulator path uses JIT+execution together; compile_only performed preflight validation only.",
        }

    result = spu_fn(*normalized_args)
    if hasattr(result, "tolist"):
        normalized_result = result.tolist()
    else:
        normalized_result = result

    return {
        "status": "success",
        "implementation_id": implementation_id,
        "protocol_kind": protocol_name,
        "field": field_name,
        "parties": parties,
        "operation": operation,
        "inputs": inputs,
        "result": normalized_result,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="SecretFlow SPU external runtime driver.")
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--spu-home", default="")
    parser.add_argument("--spec", default="")
    args = parser.parse_args()

    try:
        if args.probe:
            payload = _probe(args.spu_home)
        else:
            spec_path = Path(args.spec).expanduser()
            payload = _run(json.loads(spec_path.read_text(encoding="utf-8")))
    except Exception as error:  # noqa: BLE001
        payload = {
            "status": "error",
            "reason": str(error),
        }
        print(json.dumps(payload, ensure_ascii=False))
        return 1

    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

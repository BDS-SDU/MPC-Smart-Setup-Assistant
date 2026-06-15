from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import threading
import types
from pathlib import Path
from typing import Any


_CRYPTEN_GENERATOR_TLS = threading.local()


def _repo_add_path(crypten_home: str) -> None:
    if not crypten_home:
        return
    root = Path(crypten_home).expanduser().resolve()
    if root.exists():
        sys.path.insert(0, str(root))


def _ensure_crypten_import_path(crypten_home: str) -> None:
    if importlib.util.find_spec("crypten") is None:
        _repo_add_path(crypten_home)


def _inject_torch_onnx_compat_shim() -> None:
    if importlib.util.find_spec("torch.onnx._internal.registration") is not None:
        return
    module = types.ModuleType("torch.onnx._internal.registration")
    module.registry = None
    sys.modules["torch.onnx._internal.registration"] = module


def _prepare_runtime(crypten_home: str) -> None:
    os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
    _inject_torch_onnx_compat_shim()
    _ensure_crypten_import_path(crypten_home)


def _probe(crypten_home: str) -> dict[str, Any]:
    _prepare_runtime(crypten_home)
    result: dict[str, Any] = {
        "ok": False,
        "crypten_home": crypten_home,
        "python_executable": sys.executable,
        "python_version": sys.version,
    }

    try:
        import crypten  # type: ignore
        import torch  # type: ignore
    except Exception as error:  # noqa: BLE001
        result["reason"] = str(error)
        return result

    result["ok"] = True
    result["crypten_version"] = getattr(crypten, "__version__", "")
    result["torch_version"] = getattr(torch, "__version__", "")
    return result


def _normalize_inputs(raw_inputs: list[Any], expected_parties: int) -> list[Any]:
    if raw_inputs:
        return raw_inputs
    return [index + 1 for index in range(expected_parties)]


def _tensor_from_value(torch_module: Any, value: Any) -> Any:
    if isinstance(value, (list, tuple)):
        return torch_module.tensor(list(value), dtype=torch_module.float32)
    return torch_module.tensor([value], dtype=torch_module.float32)


def _normalize_plaintext(value: Any) -> Any:
    if hasattr(value, "tolist"):
        return value.tolist()
    return value


def _normalize_multiprocess_result(value: Any) -> Any:
    if isinstance(value, list):
        for item in value:
            if item is not None:
                return _normalize_plaintext(item)
        return []
    return _normalize_plaintext(value)


def _build_operation(operation: str, encrypted_inputs: list[Any]) -> Any:
    if operation == "comparison":
        if len(encrypted_inputs) < 2:
            raise ValueError("CrypTen comparison requires at least 2 inputs.")
        return encrypted_inputs[0] < encrypted_inputs[1]

    result = encrypted_inputs[0]
    for item in encrypted_inputs[1:]:
        result = result + item
    return result


class _ThreadLocalGeneratorProxy:
    def __init__(self, fallback: dict[str, dict[Any, Any]]) -> None:
        self._fallback = fallback

    def _mapping(self) -> dict[str, dict[Any, Any]]:
        return getattr(_CRYPTEN_GENERATOR_TLS, "generators", self._fallback)

    def __getitem__(self, key: str) -> dict[Any, Any]:
        return self._mapping()[key]

    def __setitem__(self, key: str, value: dict[Any, Any]) -> None:
        self._mapping()[key] = value

    def __contains__(self, key: object) -> bool:
        return key in self._mapping()

    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter(self._mapping())

    def keys(self):  # type: ignore[no-untyped-def]
        return self._mapping().keys()

    def items(self):  # type: ignore[no-untyped-def]
        return self._mapping().items()

    def values(self):  # type: ignore[no-untyped-def]
        return self._mapping().values()

    def get(self, key: str, default: Any = None) -> Any:
        return self._mapping().get(key, default)


def _build_threadsafe_generators(torch_module: Any) -> dict[str, dict[Any, Any]]:
    mapping: dict[str, dict[Any, Any]] = {
        "prev": {},
        "next": {},
        "local": {},
        "global": {},
    }

    cpu_device = torch_module.device("cpu")
    for key in mapping:
        mapping[key][cpu_device] = torch_module.Generator(device=cpu_device)

    if torch_module.cuda.is_available():
        device_names = ["cuda", *[f"cuda:{index}" for index in range(torch_module.cuda.device_count())]]
        for device_name in device_names:
            device = torch_module.device(device_name)
            for key in mapping:
                mapping[key][device] = torch_module.Generator(device=device)

    return mapping


def _sync_threadsafe_generators(
    crypten_module: Any,
    torch_module: Any,
    mapping: dict[str, dict[Any, Any]],
    next_seed: Any,
    local_seed: int,
    global_seed: Any,
) -> None:
    prev_seed = torch_module.tensor([0], dtype=torch_module.long)
    world_size = crypten_module.communicator.get().get_world_size()
    rank = crypten_module.communicator.get().get_rank()

    if world_size >= 2:
        next_rank = (rank + 1) % world_size
        prev_rank = (next_rank - 2) % world_size

        req0 = crypten_module.communicator.get().isend(next_seed, next_rank)
        req1 = crypten_module.communicator.get().irecv(prev_seed, src=prev_rank)

        req0.wait()
        req1.wait()
    else:
        prev_seed = next_seed

    prev_seed_value = prev_seed.item()
    next_seed_value = next_seed.item()
    global_seed_value = crypten_module.communicator.get().broadcast(global_seed, 0).item()

    for device in mapping["prev"].keys():
        mapping["prev"][device].manual_seed(prev_seed_value)
        mapping["next"][device].manual_seed(next_seed_value)
        mapping["local"][device].manual_seed(local_seed)
        mapping["global"][device].manual_seed(global_seed_value)


def _install_threadsafe_generator_patch(crypten_module: Any, torch_module: Any) -> None:
    if getattr(crypten_module, "_codex_threadsafe_generators_installed", False):
        return

    fallback_generators = crypten_module.generators
    crypten_module.generators = _ThreadLocalGeneratorProxy(fallback_generators)

    def _setup_prng_threadsafe() -> None:
        mapping = _build_threadsafe_generators(torch_module)
        _CRYPTEN_GENERATOR_TLS.generators = mapping

        seed = int.from_bytes(os.urandom(8), "big") - 2**63
        next_seed = torch_module.tensor(seed)
        local_seed = int.from_bytes(os.urandom(8), "big") - 2**63
        global_seed = torch_module.tensor(int.from_bytes(os.urandom(8), "big") - 2**63)

        _sync_threadsafe_generators(
            crypten_module,
            torch_module,
            mapping,
            next_seed,
            local_seed,
            global_seed,
        )

    crypten_module._setup_prng = _setup_prng_threadsafe
    crypten_module._codex_threadsafe_generators_installed = True


def _run_windows_threads(spec: dict[str, Any]) -> dict[str, Any]:
    import crypten  # type: ignore
    import torch  # type: ignore
    from crypten.communicator.in_process_communicator import InProcessCommunicator  # type: ignore

    operation = str(spec.get("operation", "generic")).strip().lower()
    implementation_id = str(spec.get("implementation_id", "")).strip()
    parties = max(2, int(spec.get("parties", 2)))
    raw_inputs = spec.get("inputs", [])
    inputs = _normalize_inputs(raw_inputs if isinstance(raw_inputs, list) else [], parties)

    _install_threadsafe_generator_patch(crypten, torch)

    if len(inputs) < parties:
        inputs = [*inputs, *[0 for _ in range(parties - len(inputs))]]

    results: list[Any | None] = [None for _ in range(parties)]
    errors: list[str] = []
    lock = threading.Lock()

    def worker(rank: int) -> None:
        try:
            crypten.init_thread(rank, parties)
            crypten.set_default_cryptensor_type("mpc")
            encrypted_inputs: list[Any] = []
            for src in range(parties):
                reference = _tensor_from_value(torch, inputs[src])
                local_value = reference if rank == src else torch.zeros_like(reference)
                encrypted_inputs.append(crypten.cryptensor(local_value, src=src))

            result = _build_operation(operation, encrypted_inputs)
            results[rank] = _normalize_plaintext(result.get_plain_text())
        except Exception as error:  # noqa: BLE001
            with lock:
                errors.append(str(error))
        finally:
            if hasattr(_CRYPTEN_GENERATOR_TLS, "generators"):
                delattr(_CRYPTEN_GENERATOR_TLS, "generators")

    threads = [threading.Thread(target=worker, args=(rank,)) for rank in range(parties)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    InProcessCommunicator.shutdown()

    if errors:
        raise RuntimeError(errors[0])

    normalized = _normalize_multiprocess_result(results)
    return {
        "status": "success",
        "implementation_id": implementation_id,
        "parties": parties,
        "operation": operation,
        "inputs": inputs,
        "result": normalized,
    }


def _run(spec: dict[str, Any]) -> dict[str, Any]:
    crypten_home = str(spec.get("crypten_home", "")).strip()
    _prepare_runtime(crypten_home)

    import crypten  # type: ignore
    import crypten.mpc as mpc  # type: ignore
    import torch  # type: ignore

    operation = str(spec.get("operation", "generic")).strip().lower()
    implementation_id = str(spec.get("implementation_id", "")).strip()
    parties = max(2, int(spec.get("parties", 2)))
    compile_only = bool(spec.get("compile_only", False))
    raw_inputs = spec.get("inputs", [])
    inputs = _normalize_inputs(raw_inputs if isinstance(raw_inputs, list) else [], parties)

    if len(inputs) < parties:
        inputs = [*inputs, *[0 for _ in range(parties - len(inputs))]]

    if compile_only:
        return {
            "status": "compile_only_success",
            "implementation_id": implementation_id,
            "parties": parties,
            "operation": operation,
            "inputs": inputs,
            "reason": "CrypTen compile_only performed import and multiprocess preflight only.",
        }

    if os.name == "nt":
        return _run_windows_threads(spec)

    @mpc.run_multiprocess(world_size=parties)
    def _execute() -> Any:
        crypten.init()
        rank = int(crypten.communicator.get().get_rank())
        encrypted_inputs: list[Any] = []
        for src in range(parties):
            reference = _tensor_from_value(torch, inputs[src])
            local_value = reference if rank == src else torch.zeros_like(reference)
            encrypted_inputs.append(crypten.cryptensor(local_value, src=src))

        result = _build_operation(operation, encrypted_inputs)
        return _normalize_plaintext(result.get_plain_text())

    result = _normalize_multiprocess_result(_execute())
    return {
        "status": "success",
        "implementation_id": implementation_id,
        "parties": parties,
        "operation": operation,
        "inputs": inputs,
        "result": result,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="CrypTen external runtime driver.")
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--crypten-home", default="")
    parser.add_argument("--spec", default="")
    args = parser.parse_args()

    try:
        if args.probe:
            payload = _probe(args.crypten_home)
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

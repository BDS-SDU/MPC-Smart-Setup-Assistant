# Backend Repository

This directory contains backend adapters for executing MPC configurations selected by the agent.

The current implementation is intentionally adapter-first:

- `spu/`: SecretFlow SPU execution adapter.
- `crypten/`: CrypTen/PyTorch execution adapter.
- `mp_spdz/`: MP-SPDZ execution adapter.
- `aby/`: ABY mixed-protocol secure two-party computation adapter.
- `emp_sh2pc/`: EMP-sh2pc garbled-circuit two-party computation adapter.
- `motion/`: MOTION mixed boolean/arithmetic execution adapter.
- `scale_mamba/`: SCALE-MAMBA arithmetic/SPDZ-style execution adapter.

The FastAPI service can choose the best backend and return an execution plan through:

```text
GET  /backends
POST /backends/plan
POST /sessions/{session_id}/backend-plan
```

Real execution is disabled unless the corresponding backend runtime is installed and configured. This avoids hiding heavy external setup behind the agent.

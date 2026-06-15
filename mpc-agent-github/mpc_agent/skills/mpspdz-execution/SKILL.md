---
name: mpspdz-execution
description: Deterministic execution workflow for generating program, compiling, running, and preparing default inputs.
---

# MP-SPDZ Execution Skill

Workflow:
1. Build final configuration (`generate_configuration`).
2. Compile (`compile_mpspdz_program`).
3. Run protocol (`run_mpspdz_protocol`) when compile succeeds and runtime is requested.
4. Diagnose failure (`diagnose_execution_failure`) on non-success status.

Deterministic script hooks:
- `scripts/make_inputs.py`: create default `Player-Data/Input-P*-0`
- `scripts/compile.py`: compile-only flow
- `scripts/run.py`: compile+run flow

Safety:
- Keep execution and read-only operations separated.
- Report exact command stderr/stdout in failure path.


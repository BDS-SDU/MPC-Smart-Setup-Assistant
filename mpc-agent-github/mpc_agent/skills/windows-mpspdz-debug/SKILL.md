---
name: windows-mpspdz-debug
description: Diagnose and recover Windows/WSL MP-SPDZ execution failures.
---

# Windows MP-SPDZ Debug Skill

Typical symptoms:
- permission denied
- not enough inputs
- script not found
- runtime binary not found
- port/process conflicts

Workflow:
1. Read `execution.reason`, `run.stderr`, `compile.stderr`.
2. Identify category:
   - filesystem permission
   - missing Player-Data inputs
   - missing scripts/runtime binaries
   - environment path mismatch (`MPSPDZ_HOME`)
   - multi-server process conflict
3. Output concrete PowerShell fix commands and one verification step.

Verification pattern:
- Re-run `compile_only=true`.
- Then run full execute path once.


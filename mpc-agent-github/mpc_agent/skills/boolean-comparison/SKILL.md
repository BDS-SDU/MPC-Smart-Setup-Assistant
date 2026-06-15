---
name: boolean-comparison
description: Use for comparison/sorting/auction/PSI/millionaire-style boolean tasks.
---

# Boolean Comparison Skill

Focus:
- Detect boolean-heavy workloads.
- Prioritize `yao` for 2PC low-latency scenarios.
- Consider `bmr` / `gmw` for multi-party boolean workflows.

Checklist:
1. Confirm operation includes comparison/sorting/PSI signals.
2. Confirm circuit domain boolean/mixed.
3. If `parties==2` and latency is high priority, prefer `yao`.
4. Explain where arithmetic protocols may still be acceptable and what tradeoff they introduce.


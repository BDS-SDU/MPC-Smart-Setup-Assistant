---
name: arithmetic-aggregation
description: Use for arithmetic-heavy workloads such as sum/mean/statistics/linear algebra/training.
---

# Arithmetic Aggregation Skill

Focus:
- Detect arithmetic-dominant workloads.
- Bias toward arithmetic-friendly protocols (`semi2k`, `mascot`, `shamir`) based on security/corruption constraints.

Checklist:
1. Confirm operation is aggregation/ML-like.
2. Confirm circuit domain is arithmetic or mixed.
3. Check security and corruption assumptions:
   - malicious + dishonest majority => prioritize `mascot`
   - semi_honest + dishonest majority => prioritize `semi2k`
   - honest majority => consider `shamir`
4. Explain online/offline communication tradeoff.


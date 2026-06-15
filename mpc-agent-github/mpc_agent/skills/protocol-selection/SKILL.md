---
name: protocol-selection
description: Use when a task requires MPC requirement parsing, candidate ranking, and recommendation explanation.
---

# Protocol Selection Skill

Goal:
1. Parse requirement into parties, operation, circuit domain, security model, corruption model, and performance priorities.
2. Rank protocol candidates.
3. Output top recommendation, alternatives, explicit assumptions, and risk notes.

Workflow:
1. Call `parse_requirement` tool first.
2. Call `rank_protocols` tool.
3. If user asks for final config, call `generate_configuration`.
4. Keep assumptions explicit when fields are inferred/defaulted.

Output format:
- Requirement parsing
- Recommended protocol
- Alternative protocols
- Why this choice
- Risks and assumptions


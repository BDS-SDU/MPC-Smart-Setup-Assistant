from __future__ import annotations

import re
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PRAGMATIC_TXT = PROJECT_ROOT / "pragmaticmpc.txt"

# Section-level distilled notes used for quick retrieval/explanations.
SECTION_NOTES: list[dict[str, Any]] = [
    {
        "section": "3.1",
        "title": "Yao Garbled Circuits",
        "keywords": ["yao", "2pc", "two-party", "boolean", "constant round", "comparison"],
        "summary": (
            "Yao is a strong default for two-party boolean-heavy tasks with low-latency goals "
            "because interaction rounds are constant."
        ),
    },
    {
        "section": "3.2",
        "title": "GMW",
        "keywords": ["gmw", "multi-party", "boolean", "circuit depth", "latency"],
        "summary": (
            "GMW supports multi-party settings but online round complexity scales with circuit depth, "
            "so WAN latency can dominate."
        ),
    },
    {
        "section": "3.3",
        "title": "BGW/Shamir",
        "keywords": ["bgw", "shamir", "honest majority", "arithmetic", "2t<n"],
        "summary": (
            "Shamir/BGW protocols are efficient for arithmetic computation under honest-majority assumptions."
        ),
    },
    {
        "section": "3.4",
        "title": "Preprocessing/Triples",
        "keywords": ["preprocessing", "triples", "beaver", "offline", "online", "bandwidth"],
        "summary": (
            "Preprocessing-based protocols shift communication/computation into an offline phase, "
            "reducing online bottlenecks."
        ),
    },
    {
        "section": "3.5",
        "title": "BMR",
        "keywords": ["bmr", "constant round", "multi-party", "boolean"],
        "summary": "BMR offers constant-round multi-party boolean computation at higher cryptographic cost.",
    },
    {
        "section": "6.6",
        "title": "SPDZ Family",
        "keywords": ["spdz", "mascot", "malicious", "arithmetic", "authenticated sharing"],
        "summary": (
            "SPDZ-family protocols (including MASCOT preprocessing) are practical defaults for "
            "dishonest-majority malicious security in arithmetic workloads."
        ),
    },
]


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def list_sections() -> list[dict[str, Any]]:
    return [dict(item) for item in SECTION_NOTES]


def _snippet_search(query: str, *, max_hits: int = 3) -> list[str]:
    if not query or not PRAGMATIC_TXT.exists():
        return []

    content = PRAGMATIC_TXT.read_text(encoding="utf-8", errors="replace")
    sentences = re.split(r"(?<=[.!?。！？])\s+", content)
    terms = [term for term in re.split(r"[^a-zA-Z0-9_+-]+", query.lower()) if len(term) >= 3]
    if not terms:
        return []

    scored: list[tuple[int, str]] = []
    for sentence in sentences:
        lowered = sentence.lower()
        score = sum(1 for term in terms if term in lowered)
        if score > 0:
            scored.append((score, sentence.strip()))

    scored.sort(key=lambda item: item[0], reverse=True)
    snippets: list[str] = []
    for _, text in scored:
        cleaned = re.sub(r"\s+", " ", text)
        if cleaned and cleaned not in snippets:
            snippets.append(cleaned)
        if len(snippets) >= max_hits:
            break
    return snippets


def retrieve_knowledge(query: str, *, top_k: int = 4) -> dict[str, Any]:
    normalized = _normalize(query)
    matches: list[dict[str, Any]] = []

    for item in SECTION_NOTES:
        score = 0
        for keyword in item["keywords"]:
            if keyword in normalized:
                score += 1
        if score > 0:
            matches.append({"score": score, **item})

    matches.sort(key=lambda entry: int(entry["score"]), reverse=True)
    top_matches = matches[:top_k]

    return {
        "query": query,
        "sections": [
            {
                "section": row["section"],
                "title": row["title"],
                "summary": row["summary"],
                "keywords": row["keywords"],
                "score": row["score"],
            }
            for row in top_matches
        ],
        "snippets": _snippet_search(query, max_hits=min(3, top_k)),
    }

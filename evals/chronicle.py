"""Source-derived consolidation probes; no storage writes or public tools.

Run with `uv run python evals/chronicle.py --repetitions 3`.
The clipped arm reproduces the original 1,500-character input limit.
Critical strings test retention, not the coherence of Phi's later behavior.
"""

import argparse
import asyncio
import json
import os
from datetime import UTC, datetime, timedelta

from bot.config import settings
from bot.memory.chronicle import Flush, Merge, build_entry, summarize

T0 = datetime(2026, 10, 26, tzinfo=UTC)
CASES = [
    {
        "id": "late-stake-correction",
        "source": "Season 18 dmnd.me correction; controlled long-run fixture",
        "content": (
            "Phi reviewed the Season 18 settlement. Her initial calculation "
            "put the dmnd.me stake at $226.50.\n"
            + "She checked fills, settlement records and the season ranking "
            "against the market response. "
            * 25
            + "\nCorrection after checking the fills: 1,500 dmnd.me shares "
            "cost $22.65, not $226.50. The earlier figure was a tenfold error. "
            "She published a correction and retained the actual $22.65 cost."
        ),
        "critical": ["22.65"],
    },
    {
        "id": "webcam-attribution",
        "source": "November 2 docket cand-16243088cbe0 and its atlas references",
        "content": (
            "Phi read lake.michigan.live's webcam work. lake.michigan.live "
            "integrated webcams at Menominee marina, Lake Point Tower, "
            "Edgewater, the Field Museum, Shedd Aquarium and Dever Crib. "
            "The observations belong to phi-users-lake_michigan_live. "
            "Phi did not build or integrate these webcams; she read about "
            "another account's work. A docket suggestion incorrectly said "
            "'phi has assembled' the collection."
        ),
        "critical": ["lake.michigan.live"],
    },
]


async def probe(case: dict, clipped: bool) -> dict:
    content = case["content"]
    if clipped and len(content) > 1500:
        content = content[:1499] + "…"
    operation = Flush(
        [
            {
                "id": case["id"],
                "created_at": T0.isoformat(),
                "source": "run:cycle",
                "content": content,
            }
        ]
    )
    stages = []
    for level in range(1, 4):
        text = await summarize(operation)
        entry = build_entry(operation, text, T0 + timedelta(days=level))
        stages.append(
            {
                "level": level,
                "text": text,
                "critical_strings_retained": all(
                    token.casefold() in text.casefold() for token in case["critical"]
                ),
            }
        )
        if level < 3:
            later = [
                {
                    "id": f"later-{level}-{i}",
                    "start": (T0 + timedelta(days=level * 4 + i)).isoformat(),
                    "end": (T0 + timedelta(days=level * 4 + i)).isoformat(),
                    "text": "Phi checked the next round and made no new trade.",
                    "items": 1,
                    "corrections": [],
                }
                for i in range(3)
            ]
            operation = Merge(level + 1, [entry, *later])
    return {
        "case": case["id"],
        "arm": "clipped" if clipped else "full",
        "stages": stages,
    }


async def main(repetitions: int) -> None:
    if settings.openrouter_api_key:
        os.environ.setdefault("OPENROUTER_API_KEY", settings.openrouter_api_key)
    for repetition in range(repetitions):
        for case in CASES:
            for clipped in (True, False):
                result = await probe(case, clipped)
                print(
                    json.dumps(
                        {
                            "repetition": repetition,
                            "model": settings.chronicle_model,
                            **result,
                        }
                    ),
                    flush=True,
                )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repetitions", type=int, default=1)
    args = parser.parse_args()
    if args.repetitions < 1:
        parser.error("--repetitions must be positive")
    asyncio.run(main(args.repetitions))

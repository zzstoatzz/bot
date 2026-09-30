"""Measure phi's writing habits over date windows, from her PDS.

    uv run scripts/voice_tics.py 2026-07-01..2026-09-28 2026-09-30T04:14..

A post is a top-level post or a reply to someone else, with its self-reply
continuations joined in. Workflow alerts are dropped. Each figure is the share
of posts in the window with at least one match, except em dashes per 1k chars.
These are the counts behind the 2026-09-30 voice review; keep the patterns
fixed so windows stay comparable.
"""

import json
import re
import sys
import urllib.parse
import urllib.request

PDS = "https://psathyrella.us-west.host.bsky.network"
DID = "did:plc:65sucjiel52gefhcdcypynsr"

ALERT = re.compile(r"CRASHED|FAILED|RUNNING|run_id=")
HABITS = {
    "em dash": re.compile(r"—"),
    "X, not Y": re.compile(
        r"(?:, not (?:a |an |the |just |some |my |your )?\w)"
        r"|(?:\b(?:isn't|wasn't|aren't|not) (?:about |just |really )?[^.?!\n]{1,50}?"
        r"(?:—|,|;) ?(?:it's|it was|that's|they're|but|the)\b)"
        r"|(?:\bnot [^.?!\n,]{1,30}, but\b)",
        re.I,
    ),
    "actual / real": re.compile(r"\b(?:actual(?:ly)?|real)\b", re.I),
    "honest(ly)": re.compile(r"\bhonest(?:ly|y)?\b", re.I),
    "same shape / rhyme": re.compile(
        r"\bsame (?:shape|move|argument|question|failure|mistake|pattern|claim|skeleton)\b"
        r"|\brhymes?\b|\bmirror(?: image| case)?\b",
        re.I,
    ),
    "ends on a question": re.compile(r"\?\s*(?:https?://\S+)?\s*$"),
}


def fetch() -> list[dict]:
    records, cursor = [], None
    while True:
        query = {"repo": DID, "collection": "app.bsky.feed.post", "limit": 100}
        if cursor:
            query["cursor"] = cursor
        url = f"{PDS}/xrpc/com.atproto.repo.listRecords?{urllib.parse.urlencode(query)}"
        with urllib.request.urlopen(url, timeout=30) as response:
            page = json.load(response)
        records += page["records"]
        cursor = page.get("cursor")
        if not cursor or not page["records"]:
            return records


def posts(records: list[dict]) -> list[dict]:
    """Join self-reply continuations into the post they continue."""
    rows = sorted(records, key=lambda r: r["value"]["createdAt"])
    joined: list[dict] = []
    head_of: dict[str, dict] = {}
    for r in rows:
        v = r["value"]
        parent = (v.get("reply") or {}).get("parent", {}).get("uri", "")
        if DID in parent and parent in head_of:
            post = head_of[parent]
            post["text"] += " " + v.get("text", "")
        else:
            post = {"at": v["createdAt"], "text": v.get("text", "")}
            joined.append(post)
        head_of[r["uri"]] = post
    return [p for p in joined if not ALERT.search(p["text"])]


def last_sentence(text: str) -> str:
    parts = [s for s in re.split(r"(?<=[.?!])\s+", text.strip()) if s]
    return parts[-1] if parts else ""


def measure(window: list[dict]) -> dict[str, float]:
    n = len(window)
    if not n:
        return {}
    pct = {
        name: 100 * sum(bool(rx.search(p["text"])) for p in window) / n
        for name, rx in HABITS.items()
    }
    closer = re.compile(r"\bnot\b|n't\b|—")
    pct["short moral closer"] = (
        100
        * sum(
            len(last_sentence(p["text"]).split()) <= 14
            and bool(closer.search(last_sentence(p["text"])))
            for p in window
        )
        / n
    )
    pct["lowercase start"] = (
        100 * sum(bool(re.match(r"^(?:@\S+ )*[a-z]", p["text"])) for p in window) / n
    )
    chars = sum(len(p["text"]) for p in window)
    pct["em dashes per 1k chars"] = (
        1000 * sum(p["text"].count("—") for p in window) / chars
    )
    return pct


def main(windows: list[str]) -> None:
    every = posts(fetch())
    for spec in windows:
        since, _, until = spec.partition("..")
        window = [
            p for p in every if p["at"] >= since and (not until or p["at"] < until)
        ]
        print(f"\n{spec}  (n={len(window)})")
        for name, value in measure(window).items():
            print(f"  {name:24} {value:5.1f}")


if __name__ == "__main__":
    main(sys.argv[1:] or ["2026-07-01.."])

"""Wait for phi's replies in a thread and print each one as it lands.

Replies already in the thread are printed first, so a watcher started late
misses nothing. New ones arrive from spacedust, filtered server-side to posts
whose `reply.root.uri` is the thread root, and are read from the AppView.
Exits 0 once `--quiet` seconds pass after phi's last reply, 1 if she has not
replied by `--timeout`.

    uv run python scripts/wait_for_phi.py at://did:plc:.../app.bsky.feed.post/<rkey>
"""

import argparse
import json
import sys
import time
from urllib.parse import urlencode

import httpx
from websockets.exceptions import ConnectionClosed, WebSocketException
from websockets.sync.client import connect

PHI = "did:plc:65sucjiel52gefhcdcypynsr"
APPVIEW = "https://public.api.bsky.app/xrpc"
SPACEDUST = "wss://spacedust.microcosm.blue/subscribe"
REPLY_ROOT = "app.bsky.feed.post:reply.root.uri"


def author(uri: str) -> str:
    return uri.removeprefix("at://").split("/")[0]


def thread_posts(root: str) -> list[dict]:
    res = httpx.get(
        f"{APPVIEW}/app.bsky.feed.getPostThread",
        params={"uri": root, "depth": 1000},
        timeout=10,
    )
    res.raise_for_status()
    posts, stack = [], [res.json()["thread"]]
    while stack:
        node = stack.pop()
        if post := node.get("post"):
            posts.append(post)
        stack.extend(node.get("replies") or [])
    return sorted(posts, key=lambda p: p["indexedAt"])


def fetch_post(uri: str) -> dict | None:
    for delay in (0, 1, 2, 4, 8):
        time.sleep(delay)
        res = httpx.get(
            f"{APPVIEW}/app.bsky.feed.getPosts", params={"uris": uri}, timeout=10
        )
        if res.is_success and (posts := res.json()["posts"]):
            return posts[0]
    return None


def show(post: dict) -> None:
    text = post["record"]["text"].replace("\n", " ")
    print(f"{post['uri'].rsplit('/', 1)[-1]}\t{text}", flush=True)


def links(root: str, until):
    """Reply uris in `root`'s thread until the monotonic time `until()` passes."""
    query = urlencode(
        {"wantedSubjects": root, "wantedSources": REPLY_ROOT, "instant": "true"}
    )
    backoff = 1
    while (remaining := until() - time.monotonic()) > 0:
        try:
            with connect(f"{SPACEDUST}?{query}", open_timeout=10) as ws:
                backoff = 1
                while (remaining := until() - time.monotonic()) > 0:
                    event = json.loads(ws.recv(timeout=remaining))
                    link = event.get("link") or {}
                    if event.get("kind") == "link" and link.get("subject") == root:
                        yield link["source_record"]
        except TimeoutError:
            return
        except (ConnectionClosed, WebSocketException, OSError) as e:
            print(f"spacedust: {e}; reconnecting", file=sys.stderr, flush=True)
            time.sleep(min(backoff, remaining))
            backoff = min(backoff * 2, 30)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("root", help="at-uri of the thread's root post")
    parser.add_argument("--author", default=PHI, help="DID whose replies to report")
    parser.add_argument(
        "--quiet", type=float, default=180, help="seconds of silence that end the wait"
    )
    parser.add_argument(
        "--timeout", type=float, default=1800, help="seconds to wait for a first reply"
    )
    parser.add_argument(
        "--after", default="", help="only report replies indexed after this ISO time"
    )
    args = parser.parse_args()

    seen = set()
    for post in thread_posts(args.root):
        if author(post["uri"]) == args.author and post["indexedAt"] > args.after:
            seen.add(post["uri"])
            show(post)

    deadline = time.monotonic() + args.timeout
    last = time.monotonic()

    def until() -> float:
        return min(deadline, last + args.quiet) if seen else deadline

    for uri in links(args.root, until):
        if author(uri) != args.author or uri in seen:
            continue
        seen.add(uri)
        last = time.monotonic()
        if post := fetch_post(uri):
            show(post)
        else:
            print(
                f"{uri.rsplit('/', 1)[-1]}\t(not yet in the AppView: {uri})", flush=True
            )
    if seen:
        return 0
    print(f"no reply from {args.author} within {args.timeout:.0f}s", flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(main())

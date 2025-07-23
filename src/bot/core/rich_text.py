"""Rich text handling for Bluesky posts"""

import re
from typing import Any

from atproto import Client

MENTION_REGEX = rb"(?:^|[$|\W])(@([a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)"
URL_REGEX = rb"(?:^|[$|\W])(https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*[-a-zA-Z0-9@%_\+~#//=])?)"


def parse_mentions(text: str, client: Client) -> list[dict[str, Any]]:
    """Parse @mentions and create facets with proper byte positions"""
    facets = []
    text_bytes = text.encode("UTF-8")

    for match in re.finditer(MENTION_REGEX, text_bytes):
        handle = match.group(1)[1:].decode("UTF-8")  # Remove @ prefix
        mention_start = match.start(1)
        mention_end = match.end(1)

        try:
            # Resolve handle to DID
            response = client.com.atproto.identity.resolve_handle(
                params={"handle": handle}
            )
            did = response.did

            facets.append(
                {
                    "index": {
                        "byteStart": mention_start,
                        "byteEnd": mention_end,
                    },
                    "features": [
                        {"$type": "app.bsky.richtext.facet#mention", "did": did}
                    ],
                }
            )
        except Exception:
            # Skip if handle can't be resolved
            continue

    return facets


def parse_urls(text: str) -> list[dict[str, Any]]:
    """Parse URLs and create link facets"""
    facets = []
    text_bytes = text.encode("UTF-8")

    for match in re.finditer(URL_REGEX, text_bytes):
        url = match.group(1).decode("UTF-8")
        url_start = match.start(1)
        url_end = match.end(1)

        facets.append(
            {
                "index": {
                    "byteStart": url_start,
                    "byteEnd": url_end,
                },
                "features": [{"$type": "app.bsky.richtext.facet#link", "uri": url}],
            }
        )

    return facets


def create_facets(text: str, client: Client) -> list[dict[str, Any]]:
    """Create all facets for a post (mentions and URLs)"""
    facets = []
    facets.extend(parse_mentions(text, client))
    facets.extend(parse_urls(text))
    return facets

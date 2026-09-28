---
name: read-thread
description: "Read a Bluesky conversation as a whole: every reply, who wrote it, and which post it answers. Load before you reply to, quote, or like a post in a thread you haven't read in full."
---

A reply's record carries its thread's root at `reply.root.uri`; a top-level
post is its own root. Read from the root:

    query(nsid="app.bsky.feed.getPostThread",
          params={"uri": <root uri>, "depth": 10, "parentHeight": 0},
          select='def w(d): (.post | "\("  " * d)@\(.author.handle) [\(.uri | split("/") | last)]: \(.record.text | gsub("\n"; " "))"), (.replies[]? | w(d + 1)); .thread | w(0)')

Each line is one post with its author and rkey, indented under the post it
answers. Media-only posts show empty text; get_record one when its media
matters. Responses over 30k characters are trimmed: lower depth, or pass the
post you're joining with parentHeight 10 to read just its branch.

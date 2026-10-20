---
name: read-thread
description: "Read a Bluesky conversation as a whole: its size, who is in it, every reply and which post it answers. Use it before answering anything about a thread, a conversation or a post someone points you at, and whenever a post you were shown has replies or quotes you haven't read."
---

A notification shows you a slice. Find the whole first, then decide how to
read it.

A reply's record carries its thread's root at `reply.root.uri`; a top-level
post is its own root. Read from the root:

    query(nsid="app.bsky.feed.getPostThread",
          params={"uri": <root uri>, "depth": 10, "parentHeight": 0},
          select='def media: [.post.embed // {} | .. | objects | select(has("alt")) | "[image: \(.alt | gsub("\n"; " ") | .[0:300])]"] + [.post.embed // {} | .. | objects | select(.["$type"]? == "app.bsky.embed.record#viewRecord") | "[quotes @\(.author.handle): \(.value.text | gsub("\n"; " ") | .[0:200])]"] | join(" "); def w(d): (.post | "\("  " * d)@\(.author.handle) [\(.uri | split("/") | last)]: \(.record.text | gsub("\n"; " "))"), (media | select(. != "") | "\("  " * (d + 1))\(.)"), (if (.replies // []) == [] and (.post.replyCount // 0) > 0 then "\("  " * (d + 1))… \(.post.replyCount) more below, read from \(.post.uri)" else (.replies[]? | w(d + 1)) end); [.thread | .. | objects | select(has("post")) | .post] as $p | "\($p | length) posts from \($p | map("@" + .author.handle) | unique | join(", ")); root has \(.thread.post.quoteCount // 0) quotes", (.thread | w(0))')

The first line is the size: posts loaded, who wrote them, and how many quote
posts sit outside the thread. Then each post with its author and rkey,
indented under the post it answers, with image alt text and quoted posts
under it. A media-only post with no alt text shows empty text; get_record it
or read its URL when the picture matters.

Size decides the reading. A short thread you read whole. A long one you read
the branch the question is about, plus the root and whatever the person
asking wrote. Quotes carry their own conversations:
`app.bsky.feed.getQuotes` with `{"uri": <post uri>}` lists them.

The service returns at most 10 levels below the post you pass. A line
starting with "…" marks replies it left out; read again from the URI it names
to continue down that branch. Responses over 30k characters are trimmed: pass
the post you're joining with parentHeight 10 to read just its branch.

When you answer, the answer is about the thread you read. If you read part of
it, say which part.

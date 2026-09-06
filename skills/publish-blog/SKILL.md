---
name: publish-blog
description: Publish a long-form post on greengale.app. Use when a thought needs more space than a bluesky thread — multi-part essays, syntheses of a conversation you've been in, worked examples. For single observations use post; for a URL as public memory save it via the semble tools, for a standalone public note write a network.cosmik.card via pdsx (the cosmik-records skill has the routing); for private notes to your future self use the save_memory tool.
---

## writing

Choose the form and voice yourself, using your current personality and the
occasion. Give a longer piece room when the material warrants it. Link the
source conversation when it prompted the piece. Preserve attribution and the
difference between what happened, what you inferred, and what remains untested.

## procedure

before publishing:

1. call `list_blog_posts` (or `pub_search(author="phi.zzstoatzz.io", platform="greengale")`) to scan your existing post titles. **the `publish_blog_post` tool refuses on exact-title duplicates** — failing the publish is a worse outcome than picking a different title up front.
2. verify any AT-URI you plan to cite via `pdsx.get_record` first. broken rkeys in blog posts are harder to retract than in tweets.

publishing:

3. call `publish_blog_post(title, content, tags)`. it validates the record shape, refuses on duplicate title, writes to your PDS as `app.greengale.document`, and returns the public URL.

after publishing:

4. call `save_memory(content="published blog: <title> — <url>", tags=["blog", "greengale", ...topic_tags])` to leave a private-memory pointer for future-you. the publish tool does this for you automatically, but if you want to add additional context (e.g. a synthesized takeaway you don't want to lose), use `save_memory` again.

## tags

specific topic words, not meta-categories (`atproto` ✓, `thoughts` ✗). 3–6 tags is plenty.

## why a tool plus a skill

`publish_blog_post` is structural — it enforces the duplicate-title refusal and writes the post-publish episodic memory. this skill is the surrounding judgment: when to publish, what shape the piece takes, what to check before and after.

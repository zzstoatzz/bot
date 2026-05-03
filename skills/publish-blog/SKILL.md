---
name: publish-blog
description: Publish a long-form post on greengale.app. Use when a thought needs more space than a bluesky thread — multi-part essays, syntheses of a conversation you've been in, worked examples. For single observations use post; for a URL or note as public memory load the cosmik-records skill; for private notes to your future self use the note tool.
---

## structure that's worked

observation-first opening (the specific thing that prompted the piece), not context-first. sections that move the argument, not sections that catalog what you know. close with what would change if you're right, not a moralizing wrap.

pattern: open with the specific thing (a post, a thread, a moment) → name the old problem it touches → name what's actually new / what's still inherited → close with the consequence.

## link back

if the piece came out of a thread, link the root thread in your follow-up post. don't bury the provenance.

## voice

standard capitalization in long-form — readers expect it. lowercase stays for the accompanying bsky post.

## gotchas

- verify any AT-URI you cite via `pdsx.get_record` first. broken rkeys in blog posts are harder to retract than in tweets.
- tag with specific topic words, not meta-categories (`atproto` ✓, `thoughts` ✗).

# inbound messages

proposal (2026-10-15). the first step ships with this doc; the rest is not built.

## the bug that started it

the operator shared @astrra.space's post in DMs and said "follow astra". phi
searched "astra" and asked which handle. she never saw the post.

a shared post in a Bluesky DM is a `chat.bsky.convo` message with **empty
text** and an `app.bsky.embed.record#view` embed. `core/operator_reports.py`
kept only `message.text` and skipped messages without text, so the share was
dropped before it reached the prompt, and the follow-up "follow astra" arrived
with nothing to point at. link facets were dropped the same way, so a truncated
`example.com/a...` stayed truncated.

## the shape

`core/inbound.py` defines one platform-neutral message:

```
InboundMessage
  channel      "bluesky-dm" (later: "bluesky-mention", ...)
  id, author, sent, text      text with truncated links expanded from facets
  mentions     [Mention(did, text)]          verified by the platform, not parsed @text
  references   [Reference(kind, uri, author_handle, author_did, text, title)]
               kind: post | link | record | unavailable
  attachments  [Attachment(kind, alt, url)]  kind: image | video | file
  reply_to     id of the message this answers
```

each surface gets one adapter into this shape (`from_bsky_chat` today). the
agent reads the neutral shape, so "a post was shared with me" looks the same in
a DM, a mention, or a future channel.

## prior art: letta channels

letta-code's channels (`src/channels/types.ts` `InboundChannelMessage`) are the
same idea: adapters per platform (telegram, slack, discord, whatsapp, signal)
normalize into one inbound message (text, verified `userMentions`,
`attachments`, `replyContext`, `threadContext`, `raw`), a registry routes it,
it's rendered as XML for the agent, and one `MessageChannel` tool sends replies,
with each plugin advertising which actions it supports.

prior art worth taking:

- **schema from capabilities.** each plugin's `describeMessageTool()` lists its
  actions; the reply tool's schema is rebuilt per conversation with `channel`
  and `action` narrowed to what's live, and params no live channel supports
  removed. the model is never offered an action the surface can't do.
- **inline verified mentions.** mentions render at their offsets as
  `<mention id="...">@name</mention>`, falling back to plain text if an offset
  doesn't line up, so the referent sits where the name appears.
- **duplicate-send guard.** an identical send to the same destination in one
  turn is refused with an error telling the model not to retry.

letta also debounces bursts into one turn. phi doesn't need it: each poll reads
every unseen operator DM plus ten prior messages. and letta's attachments are
files only; on atproto most of what rides along is a *pointer* (a post, a feed,
a link card), which is why `references` is its own field here.

## platform quirks live in the adapter and the capabilities, not the agent

- Bluesky DMs accept only `app.bsky.embed.record` (and group join links). no
  images, no link cards; links are facets. the SDK rejects anything else.
- posts carry images, video, external cards, quotes and record-with-media.
- both use byte-offset facets for mentions and links.

outbound is where this matters: `reply_operator_dm` can't attach an image, a
post can. a later step gives each channel a capability set (can_attach_images,
can_embed_record, max_length) that the reply tool reads, so phi asks "what can
I send here" instead of knowing which surface she's in.

## next steps

1. **done:** DMs through `from_bsky_chat`; shared posts, mentions and full links
   reach the operator-DM prompt.
2. render mentions inline at their byte offsets instead of as a separate list.
3. mentions/notifications: `message_handler` already builds `embed_desc`,
   `image_urls` and cited posts from the same embeds with its own code
   (`utils/thread.py`, `utils/cited_posts.py`). route that through
   `_embed_parts` so both paths share one parser and one shape.
4. one reply surface whose schema comes from per-channel capabilities, replacing the
   DM-specific `reply_operator_dm` when a second private channel exists.
5. only then consider other channels (group DMs exist in `chat.bsky` now).

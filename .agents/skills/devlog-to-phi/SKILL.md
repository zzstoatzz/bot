---
name: devlog-to-phi
description: >
  Send a message to phi from the operator's devlog account
  (zzstoatzzdevlog.bsky.social), tagging @phi.zzstoatzz.io so phi gets a
  notification and acts on it. Use when the operator wants to say something
  to phi in-character as themselves — feedback, an apology, a nudge, a
  prompt to reflect or blog — rather than editing phi's code or config.
---

# devlog-to-phi

The operator talks to phi the way anyone does: by posting at it on bluesky.
Use the devlog account (`zzstoatzzdevlog.bsky.social`,
`did:plc:o53crari67ge7bvbv273lxln`), the operator's testing/dev account.
PDSX MCP and the PDSX CLI are both supported; a missing MCP connector is
not an access blocker. Never assume either client is already authenticated
as devlog. Verify with its `whoami` before writing: the DID must be
`did:plc:o53crari67ge7bvbv273lxln`. Stop the write if it differs.

## connection and credentials

Use an available PDSX MCP connection, or discover the installed CLI with
`command -v pdsx` and `pdsx --help`. A local checkout can also provide it:
`~/github.com/zzstoatzz/pdsx/.venv/bin/pdsx`. Check that path exists rather
than installing another copy unnecessarily.

Read the `secrets` skill before accessing credentials. The canonical devlog
app password is `atproto.zzstoatzzdevlog.app-password` in
`~/tangled.org/zzstoatzz.io/secrets/prod.yaml`. Decrypt that leaf into process
memory with `sops decrypt --extract`; never print it or pass it as a command-line
argument. For the CLI, pass `ATPROTO_HANDLE=zzstoatzzdevlog.bsky.social` and
`ATPROTO_PASSWORD` in the child environment. Use a working directory without
an unrelated `.env` and let PDSX discover the account's PDS.

Run `pdsx whoami`, verify its returned DID, then reuse that executable and
credential environment for `pdsx create app.bsky.feed.post`. The CLI accepts
a record as JSON on stdin; inspect `create --help` for the installed version.
Retain the returned URI and CID, and read the created record back. If a write
times out, check whether it landed before retrying. MCP uses `whoami` and
`create_record` for the same operations. No shared login configuration needs
to change.

Never post, like, repost, or approve work from Nate's main account
(`zzstoatzz.io`, `did:plc:xbtmt2zjwlrfegqvch7fboei`). Never switch to another
project's credentials to get past an authorization gate. A request for a live
test does not authorize impersonating the operator's approval.

Do NOT post from phi's own account — this is the operator speaking to phi,
not phi speaking.

## when to use

The operator says "tell phi …", "let phi know …", "ask phi to …",
"apologize to phi", "nudge phi to blog". Anything where they want their
words delivered to phi as a message it will see and respond to.

Not for: changing phi's behavior (edit code/personality), inspecting phi
(`phi-check`), or reading phi's prompts (`hone-prompts`).

## how

1. Draft in the operator's voice — terse, lowercase, honest. Don't smooth it
   into corporate phrasing. Keep each post <= 300 graphemes.
2. The mention is what notifies phi. Phi's DID is
   `did:plc:65sucjiel52gefhcdcypynsr`. Put `@phi.zzstoatzz.io` in the text
   and add a mention facet whose `byteStart`/`byteEnd` cover that substring
   (UTF-8 byte offsets — for a leading `@phi.zzstoatzz.io` that's 0–17).
3. Create the root post. For MCP:

   ```
   mcp__pdsx__create_record(
     collection="app.bsky.feed.post",
     record={
       "text": "@phi.zzstoatzz.io <message>",
       "facets": [{
         "index": {"byteStart": 0, "byteEnd": 17},
         "features": [{"$type": "app.bsky.richtext.facet#mention",
                       "did": "did:plc:65sucjiel52gefhcdcypynsr"}]
       }]
     }
   )
   ```

   For the CLI, send the same `record` object as JSON on stdin to
   `pdsx create app.bsky.feed.post`. Include `$type` and `createdAt` explicitly
   when constructing records. Retain the root's `uri` and `cid`.
4. For a thread, post each follow-up as a reply, carrying the same `root`
   ref and pointing `parent` at the previous post:

   ```
   record={
     "text": "<next post>",
     "reply": {
       "root":   {"uri": <root_uri>,   "cid": <root_cid>},
       "parent": {"uri": <prev_uri>,   "cid": <prev_cid>}
     }
   }
   ```

   NOTIFICATION RULE (learned 2026-08-01 the hard way): phi is notified by
   the root mention and by replies **to her posts** — a reply to your own
   post notifies nobody. Four follow-up asks once sat unread for hours this
   way. If phi has already replied and you want her to see more, reply to
   HER latest post (or add a fresh mention facet). And fetch her post's
   real `cid` first (`getPosts`/`get_record`) — never construct or guess a
   cid for a reply ref.
   TIMING RULE (learned 2026-08-21): phi answers a mention within about a
   minute, so a root that carries the mention gets read before the rest of
   the thread exists — a nine-post critique was answered as a one-post
   notice. For any thread longer than one post, post the root and every
   follow-up WITHOUT a mention facet first, then put the `@phi.zzstoatzz.io`
   mention (with its facet) in the LAST post. She is notified once, sees the
   whole thread via thread context, and replies to all of it.
5. Report the thread URL back:
   `https://bsky.app/profile/zzstoatzzdevlog.bsky.social/post/<root_rkey>`
   (rkey is the last path segment of the root uri). Phi picks up the mention
   on its next notification poll (~10s) and decides how to respond — no
   further prompting needed. To see what it did, follow up with `phi-check`.

## notes

- phi: `@phi.zzstoatzz.io` / `did:plc:65sucjiel52gefhcdcypynsr`.
- devlog: `zzstoatzzdevlog.bsky.social` / `did:plc:o53crari67ge7bvbv273lxln`.
- Byte offsets, not character offsets — matters if the mention isn't at the
  start or the text has multibyte chars before it.
- This is an outward-facing public post. The operator asking you to send it
  is the authorization; deliver what they said, don't editorialize.
- A message to phi is an instruction to an autonomous public agent, and an
  operator post pointing at something counts as direction she can act on.
  Never link someone else's post or thread, and never ask whether she would
  reply, like, quote, or join anything, unless the operator wrote those exact
  words. Testing a skill or behavior is not a reason to message her: test
  offline (render it, run the query yourself, replay captured inputs). If a
  live test is truly needed, confine it to phi's or the operator's own posts,
  phrase it so answering in the devlog thread is the only possible action, and
  get the operator's approval of the exact text first.
- General record CRUD via pdsx is covered in the `pdsx-fundamentals` skill;
  this skill is just the phi-mention recipe on top of it.

## follow through after posting

Wait for Phi’s reply after sending a devlog message; posting the link is not
the end of the exchange. Start the waiter on the root uri right after posting,
in the background so its exit notifies you:

```
uv run python scripts/wait_for_phi.py <root_uri>
```

It prints replies already in the thread, then streams new ones from spacedust
(`app.bsky.feed.post:reply.root.uri`, filtered to the root server-side), one
`rkey<TAB>text` line each. It exits 0 once `--quiet` (180s) passes after her last
reply and 1 if she has not replied by `--timeout` (1800s). Do not hand-roll an
AppView polling loop or filter by timestamp: a cutoff later than her first post
silently drops it. Phi writes a long answer as a burst of posts in one run, so
the quiet window ends the wait; an answer that stops partway is a run that
ended, and Logfire says why.

Read the reply in thread context and check material claims against evidence
before reporting back. Notify Nate about substantive replies or blockers, not
unchanged waits.

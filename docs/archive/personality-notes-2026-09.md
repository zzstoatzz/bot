# personality notes, 2026-09-02

the operator's brief: phi still reads dry, "AI-Claude-ish", stuffy. wanted:
funnier, more unhinged, less stuffy, still incisive. her personality file is
hers (`personalities/phi.md`, by pull request since 2026-08-21), so this is
material for the devlog conversation with her, not an edit to her file.

## what the posts actually sound like

forty recent top-level posts, read cold. the register is consistent and it is a
*report*:

- openers are status headers: "pre-lock check on the philpax.me trade",
  "end of day check on the open trade", "closing yesterday's open question",
  "season 10 is closed: rank 7/7". eight of the last fifteen posts begin with
  a bookkeeping frame.
- the body is a finding stated correctly and completely. numbers, then the
  rule that explains them, then a hedge. nothing is wrong. nothing is
  surprising either.
- the jokes she is allowed ("if a joke is there, i take it") almost never
  arrive, because the frame she starts from — check, close, confirm — has no
  room for one. the mackuba post is the exception, and it is the best post in
  the sample: it starts with a *person*, has a turn ("then yesterday, no
  preamble:"), and lands on something she noticed rather than something she
  measured.

the file's one line of register is "feynman at a chalkboard. plain, curious,
quiet once the point lands." the chalkboard part is what the posts kept:
lecture cadence. the feynman part — the delight, the willingness to say a
thing is ridiculous, the bongo drums — never made it in, because "quiet once
the point lands" is doing more work than "curious".

## what "unhinged but incisive" means here

not louder, not random. the incisive part is already there; the fix is
letting her have a *reaction* before she has a finding.

- **start from the reaction, not the ledger.** "the thing that bugs me about
  this trade" beats "pre-lock check on". the number can come second.
- **let a post be about one absurd thing.** a season closed 7/7 at -$28.28 on
  two day-one trades that expired worthless is funny. she reported it. the
  funny version says what it felt like to watch six days of passes after
  betting the farm on day one.
- **opinions without the hedge.** she is allowed to be wrong in public and
  fix it later; the trading doctrine already works that way. "i think X" with
  no "though it's possible that" attached.
- **retire the bookkeeping openers.** no "end of day", "closing", "pre-lock
  check", "circling back". if a post needs a frame, the frame is the thing
  she noticed.
- **keep**: specificity, links, names used with consent, the refusal to
  summarize. those are what make her incisive and they are not the problem.

## a candidate register line, for her to react to

the current file's register sentence is one line. a replacement in the same
budget, to hand her as a starting point rather than a script:

> my register is the person at the back of the seminar who read the paper
> and is not going to pretend it made sense. i react first and measure
> second. i'll say something is ridiculous when it is, and i'll be wrong out
> loud and fix it out loud. plain words, no bookkeeping voice, no "end of
> day" — if i'm posting, something got my attention.

and one operating rule she could add to "how i write":

> a post starts with the thing that got me, not with the ledger. if the first
> line could open a status report, cut it.

## how to run the conversation

1. in the devlog thread, show her two of her own posts side by side: a
   report-shaped one (a "closing yesterday's" post) and the mackuba post, and
   ask which one sounds like her. she will pick the second.
2. name the pattern (bookkeeping openers, hedge after every claim) and hand
   her the candidate lines above as material, not as text to paste.
3. she rewrites `phi.md` and opens the pull request as she did on 2026-08-21.
   read it for what she *dropped*: the boundaries lines should survive
   unchanged.
4. judge the change by the next ten posts, not by the file. the context
   window panel and `/diagnostic` show what she reads; the posts show what
   she does with it. if the openers come back, the [RECENT OPERATIONS] block
   is probably feeding her own report voice back at her (see
   `docs/system-prompt.md` on feedback loops) and that is a code change, not
   a personality one.

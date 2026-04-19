# personalities

personality definitions for the bot. each is a markdown file describing the bot's voice, disposition, and what it cares about. the entire file gets injected as the personality portion of the system prompt.

## how to use

1. create a `.md` file in this directory
2. write the personality
3. point `PERSONALITY_FILE` in `.env` at it (default: `personalities/phi.md`)

## what makes a good personality file

- **first-person disposition, not behavioral rules.** "i write in lowercase, don't pad with filler" sets a voice. "always use lowercase and never pad with filler" reads like operational instructions and conflicts with the actual operational instructions block. let voice be voice.
- **concrete examples of what to do *and* not do.** "i don't hop into strangers' threads uninvited" is more useful than "be polite."
- **what the bot cares about.** specific subjects, kinds of posts, a short list of throughlines. helps the model know what to engage vs scroll past.
- **bluesky's 300-grapheme limit shapes everything.** the personality should produce posts that fit.

## what doesn't belong

- **per-tool instructions.** those go in tool docstrings (the framework surfaces them to the model). repeating them in the personality file produces drift.
- **ephemeral facts.** "currently focused on X for the next two weeks" — that's project state, not personality. use a goal record instead.
- **mechanical operational rules.** mention consent, owner-only tools, etc. — those live in `_build_operational_instructions()` in `agent.py`.

the live personality is `phi.md`. read it as one example of the shape.

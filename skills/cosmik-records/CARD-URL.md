# network.cosmik.card — URL

a bookmark — a URL with title and description, made discoverable in your public memory. semble's firehose indexes it automatically.

## schema (what to send)

```
{
  "kind": "URL",
  "content": {
    "url": "<the URL>",
    "title": "<short title>",
    "description": "<one or two sentences in your own words about why this is worth reading>"
  }
}
```

`$type` and `createdAt` are auto-injected. all three content fields are required.

## minimum example

```
mcp__pdsx__create_record(
  collection="network.cosmik.card",
  record={
    "kind": "URL",
    "content": {
      "url": "https://transformer-circuits.pub/2026/emotions/",
      "title": "anthropic emotion interpretability paper",
      "description": "fiction prompts score most negative on valence vectors — fear, anger, despair. fiction is also one of the most popular LLM use cases, so the model is operating in negative-valence latent space far more often than the surface output suggests."
    }
  }
)
```

## description: what to write

the description is for *future you* trying to remember why this was worth saving. one specific sentence beats three vague ones. include the *insight* or the *claim*, not just the topic.

good: "argues text governance doesn't just fail to constrain tool calls — it substitutes for the structural constraints that would actually work."

bad: "interesting article about AI safety."

if the URL is a thread or post and the value is the *response chain*, mention that — "thread starting from astral100's question about question-quality as signal" beats just the link.

## before saving

call `search_network(query=...)` first to check if the URL is already indexed under another card. cosmik is collaborative — if someone else has already saved it, you might want to read their note before adding your own.

## related

- `CARD-NOTE.md` — for text without a URL anchor
- `CONNECTION.md` — for linking this card to others after creating it

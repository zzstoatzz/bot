# Public delivery review

The judge enforces contact norms, factual integrity and privacy. Phi owns her
wording, interests, tone, length and structure. Explanations, unfamiliar topics,
humor and rhetorical phrasing are not grounds for refusal. `public_form` remains
descriptive metadata; no form category overrides the policy verdict.

Publication adapters supply verified contact targets, conversation evidence and
the complete composition. Invitation or specific operator authorization is needed
for each directed contact. Permission does not override requests for silence,
pile-on prevention or the other policies. These checks apply across Bluesky and
other AT Protocol applications, regardless of the publication's shape.

`public-etiquette` checks factual integrity and privacy, including bios and every
part of split threads. It does not require citations for every sentence or assess
whether a topic is interesting. The independent judge remains fail-closed for
composed public communication when unavailable. See [safety](safety.md).

## Optional editing and reflection

`skills/humanizer/SKILL.md` is an optional editing reference for Phi, not a judge
input or publication requirement. Its pinned upstream source and license remain
available. Phi decides whether its suggestions improve her writing.

A rejection returns the policy, reason and attempt ID. Phi may record her own
private assessment with `document_public_revision`; it is not required before
another attempt. Every new draft still receives the full policy check. Historical
rejections remain in the journal without holding unrelated future actions.

The SQLite journal preserves rule version, outcome, reason and optional private
revision note. `/api/etiquette` exposes counts, public-safe reasons and whether a
note exists, never its body. The `pending` count describes undocumented historical
rejections, not publication holds. Approval proves neither publication nor quality.

`core/etiquette.py` owns the integrity contract and journal; `core/policy.py` owns
verdict handling and interaction policies. Earlier form and phrasing restrictions
are history in [CHANGELOG.md](../CHANGELOG.md), not current instructions.

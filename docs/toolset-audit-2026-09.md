# toolset audit, 2026-09-02

what phi carries into every run, weighed against what she actually uses, read
with the suspicion that a tool built under an earlier paradigm may not belong
under the current one. this is an assessment; nothing here was removed.

evidence:

- **weight**: `/api/context/budget` on 2026-09-02 (exact counts through the
  provider). tool definitions are 30,425 of the 40,600-token fixed prompt.
- **usage**: logfire, `span_name = 'running tool'`, last 30 days: 67 of 95
  tools called at least once, 2,565 function-tool calls, 1,300 MCP calls.
- **age**: first commit of each tool module or server wiring (`git log
  --diff-filter=A`, `git log -S`).
- **paradigm**: which gate existed when the tool was written. the consent
  layer and policy judge arrived 2026-04/05, safe-mode override 2026-07-25,
  the own-source pull-request loop 2026-08-21, and code changes moved to
  issues-for-gardener on 2026-09-02.

## by origin

| origin | tools | tokens | calls / 30d | since |
|---|---|---|---|---|
| her own function tools | 30 | 11,931 | 2,565 | 2026-04-04 |
| tangled MCP | 26 | 5,529 | 146 | 2026-07-06 |
| prefect MCP | 14 | 5,316 | 108 | 2026-04-24 |
| pub-search MCP | 7 | 2,891 | 50 | 2026-02-12 |
| pdsx MCP | 8 | 2,071 | 618 | 2026-02-12 |
| skills toolset | 3 | 987 | 105 | 2026-04-21 |
| semble MCP | 3 | 730 | 228 | 2026-06-11 |
| lexidraw MCP | 3 | 616 | 39 | 2026-08-11 |
| provider tool-use framing | 1 | 354 | — | — |

## never called in 30 days (28 tools, 8,012 tokens)

| tokens | tool | why it exists | the skeptical reading |
|---|---|---|---|
| 736 | `propose_goal_change` (owner-gated) | 2026-04-18; owner authorizes a goal edit by liking her request post | the like-as-approval mechanic predates issues. `update_goal_progress` (208 calls) covers everything she actually does with goals. **remove**; a new goal is an issue or a conversation with the operator |
| 628 | `manage_feeds` (owner-gated) | 2026-04-04; graze feeds, create/delete | never used, high blast radius, from the era before safe mode. **remove**; `read_feed` stays |
| 330 | `generate_image` | 2026-07-22; images to her own PDS | never called; her drawing went to lexidraw (39 calls). the grain-photos skill depends on it and was never loaded. **retire both** or keep behind a skill that says when an image is worth it |
| 319 | `manage_account` (owner-gated) | 2026-04-04; self-labels and the mention opt-in list | the opt-in list is now maintained elsewhere (mention consent is a PDS record the operator edits). **remove** unless she needs to read the list; a read tool is a fraction of the weight |
| 229 | `follow_user` (owner-gated) | 2026-04-04; the original like-as-approval demo | never used in 30 days. following is a social act she could own like `persona`; either un-gate it with a policy norm, or **remove** |
| 722+516+461+237+201+126+123+77 = 2,463 | prefect MCP: `read_events`, `get_automations`, `get_flows`, `docs_search_prefect`, `docs_get_release_notes`, `get_object_schema`, `get_identity`, `orientation` | 2026-04-24; the whole prefect server exposed | she uses `get_flow_runs` (58), `get_flow_run_logs` (39), `get_deployments` (7). the docs and schema tools are for people building prefect, not for an agent watching one. **filter the toolset to the three she uses** (plus `get_task_runs` if `check_infra` ever needs it) |
| 505+377+328+235 = 1,445 | pub-search: `recommended_by_top_authors`, `author_profile`, `describe_cluster`, `find_similar` | 2026-02-12; the oldest server | `pub_get_document` (35) and `discover_focal_post` (12) carry the publication-curation pass; `pub_search` itself was called 3 times. **filter to `search`, `get_document`, `discover_focal_post`** and let the curation skill say which to use |
| 230+162+154+126+122 = 794 | tangled issues: `update_issue`, `set_issue_state`, `comment_on_issue`, `delete_issue`, `get_issue` | 2026-07-06 | `create_issue` becomes her only code-change path (2026-09-02). she needs `create_issue` and `get_issue`/`comment_on_issue` to follow up; `delete_issue`, `set_issue_state`, `update_issue` are lifecycle mutations on the operator's repos she has no role for. **remove those three** |
| 215+178+173+168 = 734 | tangled: `compare`, `list_pipelines`, `list_branches`, `list_tags` | 2026-07-06 | git-plumbing reads she has never needed; own-source uses `read_file`, `list_files`, `commit_log`. **filter out** |
| 196 | skills `list_skills` | 2026-04-21 | the skill catalog is already rendered into her instructions by the skills toolset; the tool duplicates it. check whether `load_skill` needs it; likely **remove** |
| 138 | pdsx `whoami` | 2026-02-12 | she knows who she is from [SELF]. **filter out** |

## lightly used, worth a second look

- `tangled_create_pull` (10), `update_pull` (3), `set_pull_state` (3): the own-source
  pull-request loop for her personality file. per the 2026-09-02 decision, code
  changes go through issues and gardener; the personality file can follow the
  same path. **remove all three** and `get_pull_file` once own-source is
  rewritten; keep `get_pull`, `get_pull_patch`, `comment_on_pull` for reviewing
  gardener's pulls.
- `persona` (1 call, 433 tokens): a July experiment in agency that she has used
  once. keep only if the operator wants it as a standing capability; otherwise it
  is 433 tokens of prompt for a thing that did not take.
- `prefect_get_task_runs`, `prefect_get_work_pools` (1 each): fold into the
  prefect filter decision above.
- `pdsx delete_record` (5 calls): the structural guard already refuses feed
  writes; deletes on her own repo are hers. keep.
- `get_own_likes` (4), `list_goals` (5): cheap (114, 87 tokens); keep.

## the heavy hitters, for context

the ten heaviest tools are her own: `check_infra` 1,194, `propose_goal_change`
736, `place_chicken_trade` 731, `check_top_chicken` 696, `update_goal_progress`
681, `manage_feeds` 628, `update_chicken_strategy` 626, `write_bio` 598,
`post` 590, `search_memory` 560. the weight is in docstrings that carry
operating rules. two of those ten are on the remove list above; the chicken
trio (2,053 tokens) is the cost of a whole hobby and earns its place by usage
(139 + 42 + 37 calls).

## paradigm drift, in one paragraph

five owner-gated tools (`follow_user`, `propose_goal_change`, `manage_feeds`,
`manage_account`, `write_self`) share the like-as-approval mechanic from
April: she posts a request, the operator's like authorizes it, the tool acts on
the next batch. only `write_self` (27 calls) is alive. the mechanic was the
first consent layer; since then the policy judge, safe-mode override, issues,
and gardener arrived, and the operator's approval increasingly lives on tangled
(a merge) rather than on bluesky (a like). the four dead ones should go, and
`write_self` is the one place the like mechanic still earns its keep.

## if every recommendation above were taken

roughly 12,000 tokens off a 40,600-token fixed prompt (about 30%), 33 fewer
tool definitions for the model to choose among, and no capability she used in
the last 30 days lost. the mechanism is `AbstractToolset.filtered()` per MCP
server in `agent.py` (no server changes) plus deleting the dead function tools
and their `RISK` entries.

## how to redo this

the procedure is the `agent-toolset-audit` skill (zzstoatzz.io/skills). the
three inputs are `/api/context/budget` (weight), the logfire query in that skill
(usage), and `git log` (age). rerun it after any change to the toolset; the
panel on `/operator` shows the weight immediately and usage needs a month.

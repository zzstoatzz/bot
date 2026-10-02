# toolset audit, 2026-10-02

the second audit. the first (`toolset-audit-2026-09.md`, 2026-09-02) recommended
about 12,000 tokens of cuts and none were taken. since then the toolset grew
from 95 tools and 30,425 tokens to 110 tools and 36,573 tokens. this one adds
the question the first skipped: what the client can do besides delete a tool.
this is an assessment; nothing here was removed.

evidence:

- **weight**: `/api/context/budget` on 2026-10-02 (exact counts through the
  provider). tool definitions are 36,573 of the 52,222-token fixed prompt.
- **usage**: `/api/tool-usage`, 2026-09-06 to 2026-10-02 (26 days, 487 runs).
  per-run family reach and skill loads come from logfire, 2026-09-18 to
  2026-10-02 (267 runs). the window is four days short of the 30 the skill
  asks for and misses nothing slower than the monthly character retro, which
  ran on 2026-10-01.
- **client**: read from the installed packages in `.venv` and from
  pydantic-ai-slim 2.53.0 fetched into a scratch environment. the cache
  behaviour of each option is read from source and has not been measured.

## what the client can do

phi runs pydantic-ai 1.80.0 against `claude-sonnet-5-5` on the Anthropic API,
with the tool block cached for an hour as its own segment
(`core/cache_stability.py`). the cache is a prefix match in the order tools,
instructions, messages, so any change to the tool list rewrites everything
behind it. on the request spans logfire holds for the last week, 82% of her
input tokens were cache reads.

| mechanism | on 1.80.0 today | what the model sees | effect on the cache |
|---|---|---|---|
| filter (`toolset.filtered()`) | yes | the tool is gone | none; the list is fixed |
| client-side deferral (`toolset.defer_loading([...])`, `defer_loading=True` on a native tool) | yes | a `search_tools` tool; a hidden tool appears after a search names it | the tool list grows on the request after a discovery, so that request rewrites the whole prefix |
| native Anthropic tool search (`defer_loading` on the wire) | no; 1.80.0 raises `NotImplementedError` on a tool-search block | the same search, run by the API | none; the declared list never changes and a reveal is appended |
| meta-tool server | already in use | two tools in front of a whole api | none |
| skills | already in use | one catalog line per skill, body on `load_skill` | none |

notes on each:

- **client-side deferral** matches keywords as substrings against tool names
  and descriptions, any term, at most ten results. a run that needs a hidden
  tool pays one extra model turn for the search and one prefix rewrite.
- **native tool search** is in pydantic-ai 2.53.0, whose Anthropic profile
  enables it for any model id starting `claude-sonnet-5`. getting there is a
  major-version upgrade from 1.80.0 that this audit did not attempt.
  Anthropic's own guidance is that tool search pays once schemas pass roughly
  10,000 tokens; phi's are at 36,573.
- **meta-tool server**: semble already carries 51 sdk methods behind
  `search_tools` and `call_tool` for 342 tokens. this is the cheapest form of
  disclosure and it is a property of the server, so it works on any client.
- **skills**: 15 skills cost 987 tokens of tool definitions. loads in 14 days:
  `cosmik-records` 24, `coral-editorial` 13, `self-presentation` 3,
  `publish-blog` 2, `publication-curation` 2, `read-thread` 2, `own-source` 1,
  `phi-prompt-inspect` 1. never loaded: `choose-influences`, `grain-photos`,
  `lexidraw-craft`, `operator-notes`, `pdsx-fundamentals`, `self-traces`.

the choice per tool follows from how often a run needs it:

- **no role**: filter. deferral keeps a tool discoverable, which is the wrong
  outcome for a tool she should not have.
- **a real capability used in a few percent of runs**: defer. the search turn
  and the prefix rewrite are paid only in those runs.
- **used in most runs**: leave it loaded.

## by origin

| origin | tools | tokens | calls / 26d | runs touching it / 267 (14d) | never called |
|---|---|---|---|---|---|
| her own function tools | 46 | 17,790 | 2,638 | 232 | 5 |
| tangled MCP | 26 | 5,655 | 120 | 3 | 14 |
| prefect MCP | 14 | 5,316 | 71 | 16 | 10 |
| pdsx MCP and skills toolset | 11 | 3,526 | 588 | 59 (pdsx) | 2 |
| pub-search MCP | 7 | 3,042 | 68 | 24 | 4 |
| lexidraw MCP | 3 | 616 | 0 | 0 | 3 |
| semble MCP | 2 | 342 | 233 | 25 | 0 |
| provider tool-use framing | 1 | 286 | | | |

tangled is the clearest case: 5,655 tokens in every request for a server
touched in 3 of 267 runs.

## never called in 26 days (38 tools, 10,470 tokens)

| tokens | tools | reading | recommendation |
|---|---|---|---|
| 3,270 | prefect: `read_events`, `get_task_runs`, `get_automations`, `get_work_pools`, `docs_search_prefect`, `docs_get_release_notes`, `get_dashboard`, `get_object_schema`, `get_identity`, `orientation` | same finding as september. she uses `get_flow_runs` (42), `get_flow_run_logs` (23), `get_deployments` (4), `get_flows` (2) | **filter** to those four |
| 2,886 | tangled: `update_pull`, `create_issue`, `list_pulls`, `list_issues`, `update_issue`, `commit_log`, `compare`, `list_pipelines`, `set_pull_state`, `list_tags`, `set_issue_state`, `comment_on_issue`, `delete_issue`, `get_issue` | issue lifecycle and git plumbing. `create_issue` was named her code-change path on 2026-09-02 and has not been called since | **filter** the lifecycle mutations and plumbing; **defer** `create_issue`, `get_issue`, `comment_on_issue`, `list_issues` with the rest of tangled |
| 1,511 | pub-search: `recommended_by_top_authors`, `author_profile`, `describe_cluster`, `find_similar` | same finding as september. she uses `get_document` (49), `discover_focal_post` (11), `search` (8) | **filter** to those three |
| 616 | lexidraw: `save`, `open`, `list` | 39 calls in the august window, none in this one. her personality still says she draws | **defer**; drawing is hers to pick back up |
| 628 | `manage_feeds` | owner-gated, never used, flagged in september | **remove** |
| 433 | `persona` | one call in august, none since | operator's call; **remove** unless it is wanted as a standing capability |
| 432 | `manage_account` | carries thread mute and unmute since september, which reply delivery depends on | **keep**; it is a standing valve |
| 221 | `operator_workflow_status` | added 2026-09-20, never called | too young to judge; recheck next audit |
| 139 | `restore_memory` | added 2026-09-12 as the undo for memory retirement | **keep**; an undo earns its weight unused |
| 196 | skills `list_skills` | the catalog is already in her instructions | **filter** |
| 138 | pdsx `whoami` | she knows who she is from [SELF] | **filter** |

## called three times or fewer (13 tools, 5,281 tokens)

- `call_xrpc` (1), `describe_lexicon` (1): two days old. no reading yet.
- `read_archive` (1, 595 tokens), `inspect_atlas` (1, 548), `request_workflow`
  (2, 606), `generate_image` (3, 383): real capabilities she reaches for
  rarely. **defer** candidates.
- `propose_goal_change` (2, 580), `follow_user` (1, 229), `write_personality`
  (2, 310): owner-gated. `write_personality` is the tool behind the 2026-09-30
  rewrite and stays. the other two are the like-as-approval mechanic the
  september audit called dead; two calls and one call do not change that.
- `tangled_create_pull` (1), `tangled_list_branches` (1), `tangled_get_record`
  (1), `prefect_get_flows` (2): fold into the family decisions above.

## the heavy hitters

`post` is now the heaviest tool at 1,141 tokens, up from 590 in september. it
is also the most used (355 calls). the growth is operating rules written into
its docstring. the next four are `check_infra` 926, `check_top_chicken` 779,
`place_chicken_trade` 731, `update_goal_progress` 639. all are used. the
september note still holds: rules that apply to several tools belong in the
instructions once.

## recommendation

two steps, in this order.

**1. filter, on the current client.** every row marked filter or remove above:
prefect to four tools, pub-search to three, the tangled lifecycle and plumbing
tools, `whoami`, `list_skills`, `manage_feeds`, and `persona` if the operator
agrees. that is 28 tools and about 8,300 tokens, 16% of the fixed prompt, with
no capability lost that she used in 26 days and no effect on the cache. the
mechanism is `filtered()` per MCP server in `_mcp_toolsets` plus deleting the
dead function tools and their `RISK` entries.

**2. defer what is real and rare.** the remaining 16 tangled tools (about
3,550 tokens), lexidraw (616), and the four rare native tools (2,132): 23
tools and about 6,300 tokens more. on 1.80.0 this is client-side deferral. the cost is a prefix
rewrite in the runs that discover a tool, which for tangled is 3 runs in 267.
that is acceptable. it stops being acceptable for anything used in a tenth of
runs or more, which is the reason to leave pdsx, pub-search and prefect loaded
after filtering.

taken together, about 14,600 tokens off a 52,222-token prompt (28%) and the
visible tool count down from 110 to 60, counting the search tool.

what would change this plan: moving to pydantic-ai 2.x makes deferral
cache-neutral, at which point pub-search and prefect become defer candidates
too. that upgrade should be judged on its own; it is a larger change than
anything above.

two things to check when implementing step 2:

- `_run_with_mcp_retry` identifies a failed server by the toolset's `url`
  attribute, and `defer_loading()` returns a wrapper without one.
- a deferred tool is findable only by words in its name and description. the
  skills that send her to tangled and lexidraw (`own-source`, `lexidraw-craft`)
  should name the tools so the search has something to match.

## how to redo this

the procedure is the `toolset-audit` project skill. after step 1 lands the
weight is visible at once on `/operator`; usage needs another month.

## what landed, 2026-10-02

step 1 shipped the same day, smaller than recommended: 24 tools and about
7,000 tokens. the difference is the gotcha this audit's own skill warns about.
three tools with no calls are named by text phi reads, so removing them would
have sent her after tools that were gone: `tangled_commit_log` and
`tangled_compare` in the own-source skill, `tangled_update_pull` in the
pull-review prompt. `persona` was left for the operator.

phi's reply to the plan asked that, when step 2 puts tangled and lexidraw
behind search, `own-source` and `lexidraw-craft` say to search for those tools.

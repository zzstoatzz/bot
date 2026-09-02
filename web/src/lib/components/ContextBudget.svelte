<script lang="ts">
	// context budget: what phi's next run would send, against what her model
	// can hold. the headline is one bar — used of window — segmented by what
	// the tokens are for. everything below it answers "which sections, how
	// heavy, and does the last real run agree".
	//
	// two numbers, deliberately kept apart: the composed prompt (counted or
	// estimated from a fresh render, right now) and the provider's own usage
	// on the last run (measured, past). the panel names which is which.
	import { onMount } from 'svelte';
	import { getContextBudget } from '$lib/api';
	import type { ContextBudget, ContextSection, ContextSectionKind } from '$lib/types';
	import { relativeWhen, whenTooltip } from '$lib/time';

	let data = $state<ContextBudget | null>(null);
	let loading = $state(true);
	let err = $state<string | null>(null);
	let kindFilter = $state<ContextSectionKind | 'all'>('all');
	let sortBy = $state<'tokens' | 'order'>('tokens');
	let selectedName = $state<string | null>(null);

	async function load() {
		loading = true;
		err = null;
		const budget = await getContextBudget();
		if (budget) {
			data = budget;
		} else {
			err = 'budget unavailable (rate limited, or the agent is still starting)';
		}
		loading = false;
	}
	onMount(load);

	const num = (n: number) => n.toLocaleString('en-US');
	function tokens(n: number): string {
		if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}m`;
		if (n >= 1000) return `${(n / 1000).toFixed(n >= 10_000 ? 0 : 1)}k`;
		return String(n);
	}
	const pct = (part: number, whole: number) => (whole ? (part / whole) * 100 : 0);
	const pctLabel = (part: number, whole: number) => `${pct(part, whole).toFixed(pct(part, whole) < 1 ? 2 : 1)}%`;

	const window = $derived(data?.model.max_input_tokens ?? null);
	const prompt = $derived(data?.totals.prompt ?? 0);
	// the last run's largest request is the fullest the window got: the
	// composed prompt plus the conversation that grew on top of it
	const lastPeak = $derived(
		data?.last_run ? Math.max(0, ...data.last_run.requests.map((r) => r.billed_prefix)) : null
	);
	const kinds = ['static', 'blocks', 'tools'] as const;
	const kindTitle = {
		static: 'static instructions — personality + operational rules, cached 1h',
		blocks: 'dynamic context blocks — recomposed every run',
		tools: 'tool definitions — function, skills, and MCP tools, cached 1h'
	} as const;

	const rows = $derived.by(() => {
		if (!data) return [];
		const filtered =
			kindFilter === 'all' ? data.sections : data.sections.filter((s) => s.kind === kindFilter);
		return sortBy === 'tokens' ? [...filtered].sort((a, b) => b.tokens - a.tokens) : filtered;
	});
	const selected = $derived(data?.sections.find((s) => s.name === selectedName) ?? null);
	const originLabel = (s: ContextSection) => (s.kind === 'tool' ? s.origin : s.kind);
	const counted = $derived(data?.counting === 'exact' ? 'counted' : 'estimated');
</script>

<section class="budget">
	<div class="head">
		<h2>context window</h2>
		<button class="refresh" onclick={load} disabled={loading}>
			{loading ? 'weighing…' : 'refresh'}
		</button>
	</div>

	{#if loading && !data}
		<div class="status">composing the next run…</div>
	{:else if err && !data}
		<div class="status">{err}</div>
	{:else if data}
		<p class="model">
			<span class="mono">{data.model.spec}</span>
			{#if window !== null}
				· window <span class="mono">{num(window)}</span> tokens
				<span class="dim" title="context window size comes from a public model catalog, not the provider's API">
					({data.model.source})
				</span>
			{:else}
				· window <strong>unknown</strong>
				<span class="dim">— not in the model catalog; the bar below has no ceiling</span>
			{/if}
		</p>

		<div class="bar-block">
			<div class="bar-label">
				<span>
					next run starts at <strong class="mono">{tokens(prompt)}</strong> tokens
					<span class="dim">({counted}{window !== null ? `, ${pctLabel(prompt, window)} of the window` : ''})</span>
				</span>
				{#if lastPeak !== null && data.last_run}
					<span>
						last run peaked at <strong class="mono">{tokens(lastPeak)}</strong>
						<span class="dim">(measured, {data.last_run.label}, {relativeWhen(data.last_run.started_at)})</span>
					</span>
				{/if}
			</div>
			<div class="bar" role="img" aria-label="context window usage">
				{#each kinds as k (k)}
					{@const part = data.totals[k]}
					<div
						class="seg seg-{k}"
						style:width="{window !== null ? pct(part, window) : pct(part, prompt)}%"
						title="{kindTitle[k]}: {num(part)} tokens ({pctLabel(part, prompt)} of the prompt)"
					></div>
				{/each}
				{#if lastPeak !== null && lastPeak > prompt}
					<div
						class="seg seg-conv"
						style:width="{window !== null ? pct(lastPeak - prompt, window) : 0}%"
						title="conversation growth on the last run: tool calls and results on top of the prompt, {num(lastPeak - prompt)} tokens"
					></div>
				{/if}
			</div>
			<div class="legend">
				{#each kinds as k (k)}
					<span><i class="sw seg-{k}"></i>{k} <span class="mono">{tokens(data.totals[k])}</span></span>
				{/each}
				{#if lastPeak !== null && lastPeak > prompt}
					<span><i class="sw seg-conv"></i>conversation <span class="mono">{tokens(lastPeak - prompt)}</span></span>
				{/if}
			</div>
		</div>

		<div class="controls">
			<div class="filters" role="tablist" aria-label="section kind">
				{#each ['all', 'static', 'block', 'tool'] as const as k (k)}
					<button class:on={kindFilter === k} role="tab" aria-selected={kindFilter === k} onclick={() => (kindFilter = k)}>
						{k}
					</button>
				{/each}
			</div>
			<button class="linkish" onclick={() => (sortBy = sortBy === 'tokens' ? 'order' : 'tokens')}>
				sorted by {sortBy === 'tokens' ? 'weight' : 'prompt order'}
			</button>
		</div>

		<div class="panes">
			<ul class="list" role="listbox" aria-label="context sections">
				{#each rows as s (s.name)}
					<li>
						<button
							class="row"
							class:active={s.name === selectedName}
							role="option"
							aria-selected={s.name === selectedName}
							onclick={() => (selectedName = selectedName === s.name ? null : s.name)}
						>
							<span class="origin mono dim">{originLabel(s)}</span>
							<span class="name mono">{s.name}</span>
							{#if s.error}
								<span class="err" title={s.error}>error</span>
							{/if}
							<span class="weight">
								<i class="fill seg-{s.kind === 'block' ? 'blocks' : s.kind === 'tool' ? 'tools' : 'static'}" style:width="{pct(s.tokens, prompt)}%"></i>
							</span>
							<span class="tok mono">{s.tokens > 0 ? tokens(s.tokens) : '·'}</span>
							<span class="share mono dim">{s.tokens > 0 ? pctLabel(s.tokens, prompt) : ''}</span>
						</button>
					</li>
				{/each}
			</ul>
			{#if selected}
				<div class="detail">
					<div class="d-name mono">{selected.name}</div>
					<div class="d-meta">
						<span>{originLabel(selected)}</span>
						<span><span class="mono">{num(selected.tokens)}</span> tokens {counted}</span>
						<span><span class="mono">{num(selected.chars)}</span> chars</span>
						{#if selected.kind !== 'tool'}
							<span><span class="mono">{selected.ms}</span> ms to render</span>
						{/if}
					</div>
					{#if selected.error}
						<div class="d-err mono">{selected.error}</div>
					{:else if selected.chars === 0}
						<div class="dim">renders nothing on a scheduled run; it needs a notifications batch to react to.</div>
					{:else if selected.kind !== 'tool'}
						<a class="linkish" href="/diagnostic">read it as phi would →</a>
					{/if}
				</div>
			{/if}
		</div>

		{#if data.last_run}
			<div class="run">
				<span class="dim">last run · {data.last_run.label} · {data.last_run.model}</span>
				<span class="dim" title={whenTooltip(data.last_run.started_at)}>{relativeWhen(data.last_run.started_at)}</span>
				<span class="reqs">
					{#each data.last_run.requests as r, i (i)}
						<span
							class="req mono"
							title="request {i + 1}: {num(r.billed_prefix)} tokens in — {num(r.cache_read)} read from cache, {num(r.cache_write)} written, {num(r.input_tokens)} uncached"
						>
							{tokens(r.billed_prefix)}
						</span>
					{/each}
				</span>
				{#if data.last_run.trace_url}
					<a class="linkish" href={data.last_run.trace_url} target="_blank" rel="noreferrer">trace ↗</a>
				{/if}
			</div>
		{/if}
		<p class="foot dim">
			composed {relativeWhen(data.generated_at)} for a {data.path} run. the cache panel below is the cost view of the same requests.
		</p>
	{/if}
</section>

<style>
	.budget {
		margin-top: 2.5rem;
		padding-top: 1.5rem;
		border-top: 1px solid var(--line-mid, #2a3140);
	}
	.head {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
	}
	h2 {
		font-size: 1rem;
		margin: 0 0 0.5rem;
	}
	.refresh,
	.linkish,
	.filters button {
		background: none;
		border: 1px solid var(--line-mid, #2a3140);
		color: var(--text-mid);
		font: inherit;
		font-size: 0.8rem;
		padding: 0.15rem 0.6rem;
		cursor: pointer;
	}
	.linkish {
		border: none;
		padding: 0;
		text-decoration: underline dotted;
		color: var(--text-mid);
	}
	.refresh:disabled {
		opacity: 0.5;
		cursor: default;
	}
	.status,
	.dim,
	.foot {
		color: var(--text-dim);
		font-size: 0.85rem;
	}
	.model {
		margin: 0.25rem 0 1rem;
		font-size: 0.9rem;
	}
	.mono {
		font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
	}
	.bar-block {
		margin-bottom: 1rem;
	}
	.bar-label {
		display: flex;
		justify-content: space-between;
		flex-wrap: wrap;
		gap: 0.5rem 1.5rem;
		font-size: 0.85rem;
		margin-bottom: 0.35rem;
	}
	.bar {
		display: flex;
		height: 14px;
		width: 100%;
		background: var(--bg-elev, #141a26);
		border: 1px solid var(--line-mid, #2a3140);
		overflow: hidden;
	}
	.seg {
		height: 100%;
		min-width: 1px;
	}
	.seg-static {
		background: var(--scan-hot, #7ec0d4);
	}
	.seg-blocks {
		background: var(--scan-mid, #4a8b9a);
	}
	.seg-tools {
		background: var(--hud-mid, #b86b3a);
	}
	.seg-conv {
		background: var(--warn, #c9a05a);
	}
	.legend {
		display: flex;
		gap: 1.25rem;
		flex-wrap: wrap;
		font-size: 0.8rem;
		margin-top: 0.35rem;
		color: var(--text-mid);
	}
	.sw {
		display: inline-block;
		width: 10px;
		height: 10px;
		margin-right: 0.35rem;
		vertical-align: -1px;
	}
	.controls {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin: 0.5rem 0;
	}
	.filters {
		display: flex;
		gap: 0.25rem;
	}
	.filters button.on {
		color: var(--text);
		border-color: var(--text-mid);
	}
	.panes {
		display: grid;
		grid-template-columns: minmax(0, 1fr);
		gap: 1rem;
	}
	@media (min-width: 720px) {
		.panes:has(.detail) {
			grid-template-columns: minmax(0, 3fr) minmax(0, 2fr);
		}
	}
	.list {
		list-style: none;
		margin: 0;
		padding: 0;
		max-height: 24rem;
		overflow-y: auto;
		border: 1px solid var(--line-mid, #2a3140);
	}
	.row {
		display: grid;
		grid-template-columns: 6.5rem minmax(0, 1fr) auto 6rem 3.5rem 3.5rem;
		gap: 0.6rem;
		align-items: center;
		width: 100%;
		text-align: left;
		background: none;
		border: none;
		border-bottom: 1px solid var(--line-dim, #1c2230);
		color: var(--text);
		font: inherit;
		font-size: 0.82rem;
		padding: 0.3rem 0.6rem;
		cursor: pointer;
	}
	.row:hover,
	.row.active {
		background: var(--bg-elev, #141a26);
	}
	.name {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.err {
		color: var(--danger, #a04848);
		font-size: 0.75rem;
	}
	.weight {
		display: block;
		height: 6px;
		background: var(--bg-deep, #0d1119);
	}
	.fill {
		display: block;
		height: 100%;
		min-width: 1px;
	}
	.tok,
	.share {
		text-align: right;
	}
	.detail {
		border: 1px solid var(--line-mid, #2a3140);
		padding: 0.75rem;
		font-size: 0.85rem;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		align-self: start;
	}
	.d-meta {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem 1rem;
		color: var(--text-mid);
	}
	.d-err {
		color: var(--danger, #a04848);
		white-space: pre-wrap;
	}
	.run {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.5rem 1rem;
		margin-top: 1rem;
		font-size: 0.85rem;
	}
	.reqs {
		display: flex;
		gap: 0.25rem;
	}
	.req {
		padding: 0 0.4rem;
		border: 1px solid var(--line-mid, #2a3140);
		font-size: 0.78rem;
	}
	.foot {
		margin-top: 0.75rem;
	}
</style>

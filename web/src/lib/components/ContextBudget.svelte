<script lang="ts">
	// context window: one number and one shape.
	//
	// the number is how much of the model's window the next run occupies
	// before it does anything. the shape is a donut of what that prompt is
	// made of — five slices at most, because a part-to-whole is only
	// readable at a glance. everything finer (115 sections, per-tool
	// weights, last run's requests) lives behind "details" and stays there
	// unless asked for.
	//
	// two numbers are deliberately kept apart: the composed prompt (counted
	// or estimated from a fresh render, now) and the provider's own usage on
	// the last real run (measured, past). the panel names which is which.
	import { onMount } from 'svelte';
	import { getContextBudget } from '$lib/api';
	import type { ContextBudget, ContextSection } from '$lib/types';
	import { relativeWhen, whenTooltip } from '$lib/time';

	let data = $state<ContextBudget | null>(null);
	let loading = $state(true);
	let err = $state<string | null>(null);
	let showDetails = $state(false);
	let hovered = $state<string | null>(null);
	let sortBy = $state<'tokens' | 'order'>('tokens');

	async function load() {
		loading = true;
		err = null;
		const budget = await getContextBudget();
		if (budget) {
			data = budget;
		} else {
			err = 'unavailable — rate limited, or phi is still starting';
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
	function pctLabel(part: number, whole: number): string {
		const p = pct(part, whole);
		return `${p.toFixed(p < 1 ? 2 : p < 10 ? 1 : 0)}%`;
	}

	// the five slices: a fixed order and a fixed color each, validated for
	// the dark surface (dataviz reference palette, slots 1–5)
	const SLICES = [
		{ key: 'static', label: 'instructions', color: '#3987e5' },
		{ key: 'blocks', label: 'context blocks', color: '#d95926' },
		{ key: 'function', label: 'her own tools', color: '#199e70' },
		{ key: 'mcp', label: 'mcp tools', color: '#c98500' },
		{ key: 'other', label: 'skills + framing', color: '#d55181' }
	] as const;
	type SliceKey = (typeof SLICES)[number]['key'];

	function sliceOf(s: ContextSection): SliceKey {
		if (s.kind === 'static') return 'static';
		if (s.kind === 'block') return 'blocks';
		if (s.origin === 'function') return 'function';
		if (s.origin.startsWith('mcp:')) return 'mcp';
		return 'other';
	}

	const window = $derived(data?.model.max_input_tokens ?? null);
	const prompt = $derived(data?.totals.prompt ?? 0);
	const counted = $derived(data?.counting === 'exact' ? 'counted' : 'estimated');
	const sliceTotals = $derived.by(() => {
		const totals: Record<SliceKey, number> = { static: 0, blocks: 0, function: 0, mcp: 0, other: 0 };
		for (const s of data?.sections ?? []) totals[sliceOf(s)] += s.tokens;
		return totals;
	});
	const sliceSum = $derived(Object.values(sliceTotals).reduce((a, b) => a + b, 0));
	// the last run's largest request is the fullest the window got: the
	// composed prompt plus the conversation that grew on top of it
	const lastPeak = $derived(
		data?.last_run ? Math.max(0, ...data.last_run.requests.map((r) => r.billed_prefix)) : null
	);

	// donut geometry: radius 1, drawn as stroked arcs with a 2px surface gap
	const R = 42;
	const STROKE = 14;
	const C = 2 * Math.PI * R;
	const arcs = $derived.by(() => {
		let offset = 0;
		return SLICES.map((slice) => {
			const share = sliceSum ? sliceTotals[slice.key] / sliceSum : 0;
			const arc = { ...slice, tokens: sliceTotals[slice.key], share, dash: share * C, offset };
			offset += share * C;
			return arc;
		}).filter((a) => a.tokens > 0);
	});
	const hoveredArc = $derived(arcs.find((a) => a.key === hovered) ?? null);

	const rows = $derived.by(() => {
		if (!data) return [];
		return sortBy === 'tokens' ? [...data.sections].sort((a, b) => b.tokens - a.tokens) : data.sections;
	});
	const originLabel = (s: ContextSection) => (s.kind === 'tool' ? s.origin : s.kind);
</script>

<section class="ctx">
	<div class="head">
		<h2>context window</h2>
		<button class="refresh" onclick={load} disabled={loading}>{loading ? 'weighing…' : 'refresh'}</button>
	</div>

	{#if loading && !data}
		<div class="status">composing the next run…</div>
	{:else if err && !data}
		<div class="status">{err}</div>
	{:else if data}
		<div class="headline">
			{#if window !== null}
				<span class="big">{pctLabel(prompt, window)}</span>
				<span class="big-t">of the window, before she does anything</span>
			{:else}
				<span class="big">{tokens(prompt)}</span>
				<span class="big-t">tokens before she does anything · window unknown</span>
			{/if}
		</div>
		<p class="sub">
			<span class="mono">{data.model.spec}</span>
			{#if window !== null}
				· <span class="mono">{tokens(prompt)}</span> of <span class="mono">{tokens(window)}</span> tokens, {counted}
				<span class="faint" title="window size comes from a public model catalog; no provider reports it">({data.model.source})</span>
			{:else}
				· <span class="faint">not in the model catalog, so there is no ceiling to measure against</span>
			{/if}
		</p>

		<div class="figure">
			<svg viewBox="0 0 100 100" class="donut" role="img" aria-label="what the prompt is made of">
				<circle cx="50" cy="50" r={R} fill="none" stroke="var(--bg-elev)" stroke-width={STROKE} />
				{#each arcs as a (a.key)}
					<!-- svelte-ignore a11y_no_static_element_interactions -->
					<circle
						cx="50"
						cy="50"
						r={R}
						fill="none"
						stroke={a.color}
						stroke-width={hovered === a.key ? STROKE + 2 : STROKE}
						stroke-dasharray="{Math.max(a.dash - 2, 0)} {C - Math.max(a.dash - 2, 0)}"
						stroke-dashoffset={-(a.offset + 1)}
						transform="rotate(-90 50 50)"
						opacity={hovered && hovered !== a.key ? 0.35 : 1}
						onmouseenter={() => (hovered = a.key)}
						onmouseleave={() => (hovered = null)}
					>
						<title>{a.label}: {num(a.tokens)} tokens, {pctLabel(a.tokens, sliceSum)} of the prompt</title>
					</circle>
				{/each}
				<text x="50" y="47" text-anchor="middle" class="center-n">
					{hoveredArc ? tokens(hoveredArc.tokens) : tokens(prompt)}
				</text>
				<text x="50" y="58" text-anchor="middle" class="center-t">
					{hoveredArc ? hoveredArc.label : 'tokens'}
				</text>
			</svg>
			<ul class="legend" aria-label="slices">
				{#each arcs as a (a.key)}
					<!-- svelte-ignore a11y_no_static_element_interactions -->
					<li
						class:dim={hovered !== null && hovered !== a.key}
						onmouseenter={() => (hovered = a.key)}
						onmouseleave={() => (hovered = null)}
					>
						<i class="sw" style:background={a.color}></i>
						<span class="l-name">{a.label}</span>
						<span class="l-n mono">{tokens(a.tokens)}</span>
						<span class="l-p mono faint">{pctLabel(a.tokens, sliceSum)}</span>
					</li>
				{/each}
			</ul>
		</div>

		{#if data.last_run && lastPeak !== null}
			<div class="facts">
				<div class="fact">
					<span class="fact-n">{tokens(lastPeak)}</span>
					<span class="fact-t">
						the fullest request on her last run ({data.last_run.label},
						<span title={whenTooltip(data.last_run.started_at)}>{relativeWhen(data.last_run.started_at)}</span>)
						— measured by the provider, not composed here. the gap above the prompt is the conversation:
						tool calls and their results piling up as the run went on
					</span>
				</div>
				{#if window !== null}
					<div class="fact">
						<span class="fact-n">{pctLabel(lastPeak, window)}</span>
						<span class="fact-t">of the window at that peak</span>
					</div>
				{/if}
			</div>
		{/if}

		<button class="details-toggle" onclick={() => (showDetails = !showDetails)} aria-expanded={showDetails}>
			{showDetails ? 'hide' : 'show'} every section ({data.sections.length})
		</button>

		{#if showDetails}
			<div class="details">
				<div class="controls">
					<span class="faint">each row is one thing she reads, {counted} in tokens</span>
					<button class="linkish" onclick={() => (sortBy = sortBy === 'tokens' ? 'order' : 'tokens')}>
						sorted by {sortBy === 'tokens' ? 'weight' : 'prompt order'}
					</button>
				</div>
				<ul class="list">
					{#each rows as s (s.name + s.origin)}
						<li class="row">
							<i class="sw" style:background={SLICES.find((x) => x.key === sliceOf(s))?.color}></i>
							<span class="origin mono faint">{originLabel(s)}</span>
							<span class="name mono" title={s.error ?? ''}>{s.name}{s.error ? ' ⚠' : ''}</span>
							<span class="weight"><i class="fill" style:width="{pct(s.tokens, prompt)}%" style:background={SLICES.find((x) => x.key === sliceOf(s))?.color}></i></span>
							<span class="tok mono">{s.tokens > 0 ? tokens(s.tokens) : '·'}</span>
						</li>
					{/each}
				</ul>
				{#if data.last_run}
					<div class="run faint">
						last run's requests:
						{#each data.last_run.requests as r, i (i)}
							<span class="req mono" title="request {i + 1}: {num(r.billed_prefix)} tokens in — {num(r.cache_read)} read from cache, {num(r.cache_write)} written, {num(r.input_tokens)} uncached">{tokens(r.billed_prefix)}</span>
						{/each}
						{#if data.last_run.trace_url}
							<a class="linkish" href={data.last_run.trace_url} target="_blank" rel="noreferrer">trace ↗</a>
						{/if}
						· <a class="linkish" href="/diagnostic">read each block as phi would →</a>
					</div>
				{/if}
			</div>
		{/if}
	{/if}
</section>

<style>
	.ctx {
		margin-top: 2.5rem;
		padding-top: 1.5rem;
		border-top: 1px solid var(--line-mid);
	}
	.head {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
	}
	h2 {
		font-family: var(--font-chrome);
		text-transform: uppercase;
		letter-spacing: 0.12em;
		font-weight: 500;
		font-size: 1.1rem;
		margin: 0 0 0.75rem;
		color: var(--hud-hot);
	}
	.mono {
		font-family: var(--font-mono);
	}
	.faint,
	.status {
		color: var(--text-dim);
	}
	.status {
		font-size: 0.85rem;
	}
	.refresh,
	.details-toggle,
	.linkish {
		background: none;
		border: 1px solid var(--line-mid);
		color: var(--text-mid);
		font-family: var(--font-mono);
		font-size: 0.78rem;
		padding: 0.15rem 0.6rem;
		cursor: pointer;
	}
	.refresh:disabled {
		opacity: 0.5;
		cursor: default;
	}
	.linkish {
		border: none;
		padding: 0;
		text-decoration: underline dotted;
	}
	.headline {
		display: flex;
		align-items: baseline;
		gap: 0.75rem;
		flex-wrap: wrap;
	}
	.big {
		font-family: var(--font-chrome);
		font-size: 2.6rem;
		line-height: 1;
		color: var(--scan-hot);
	}
	.big-t {
		font-family: var(--font-chrome);
		text-transform: uppercase;
		letter-spacing: 0.1em;
		color: var(--text);
		font-size: 0.85rem;
	}
	.sub {
		margin: 0.4rem 0 1.25rem;
		color: var(--text-dim);
		font-size: 0.85rem;
	}
	.figure {
		display: grid;
		grid-template-columns: 180px minmax(0, 1fr);
		gap: 1.5rem;
		align-items: center;
	}
	@media (max-width: 520px) {
		.figure {
			grid-template-columns: 1fr;
			justify-items: center;
		}
	}
	.donut {
		width: 180px;
		height: 180px;
	}
	.donut circle {
		transition: opacity 120ms ease, stroke-width 120ms ease;
	}
	.center-n {
		font-family: var(--font-chrome);
		font-size: 13px;
		fill: var(--text);
	}
	.center-t {
		font-family: var(--font-mono);
		font-size: 6px;
		fill: var(--text-dim);
		letter-spacing: 0.08em;
	}
	.legend {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
		font-size: 0.85rem;
	}
	.legend li {
		display: grid;
		grid-template-columns: 10px minmax(0, 1fr) 4rem 3.5rem;
		gap: 0.6rem;
		align-items: center;
		cursor: default;
		transition: opacity 120ms ease;
	}
	.legend li.dim {
		opacity: 0.4;
	}
	.sw {
		display: inline-block;
		width: 10px;
		height: 10px;
	}
	.l-n,
	.l-p,
	.tok {
		text-align: right;
	}
	.facts {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
		gap: 1rem 2rem;
		margin: 1.5rem 0 1rem;
	}
	.fact {
		display: flex;
		gap: 0.75rem;
		align-items: baseline;
	}
	.fact-n {
		font-family: var(--font-chrome);
		font-size: 1.6rem;
		color: var(--scan-hot);
		white-space: nowrap;
	}
	.fact-t {
		color: var(--text-dim);
		font-size: 0.8rem;
		line-height: 1.45;
	}
	.details-toggle {
		margin-top: 0.5rem;
	}
	.details {
		margin-top: 1rem;
	}
	.controls {
		display: flex;
		justify-content: space-between;
		align-items: center;
		font-size: 0.8rem;
		margin-bottom: 0.4rem;
	}
	.list {
		list-style: none;
		margin: 0;
		padding: 0;
		max-height: 22rem;
		overflow-y: auto;
		border: 1px solid var(--line-mid);
	}
	.row {
		display: grid;
		grid-template-columns: 10px 7rem minmax(0, 1fr) 6rem 3.5rem;
		gap: 0.6rem;
		align-items: center;
		font-size: 0.8rem;
		padding: 0.25rem 0.6rem;
		border-bottom: 1px solid var(--line-dim);
	}
	.name {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.weight {
		display: block;
		height: 5px;
		background: var(--bg-deep);
	}
	.fill {
		display: block;
		height: 100%;
		min-width: 1px;
	}
	.run {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.4rem;
		margin-top: 0.75rem;
		font-size: 0.8rem;
	}
	.req {
		padding: 0 0.35rem;
		border: 1px solid var(--line-mid);
	}
</style>

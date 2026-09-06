<script lang="ts">
	import { onMount } from 'svelte';
	import { getToolUsage, type ToolUsage } from '$lib/tool-usage';

	let data = $state<ToolUsage | null>(null);
	let error = $state('');
	let loading = $state(false);
	let filter = $state('all');
	let query = $state('');
	let sort = $state('calls');
	let selected = $state<string | null>(null);
	let updated = $state<Date | null>(null);
	const number = new Intl.NumberFormat();
	const date = new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
	const totals = $derived({
		calls: data?.tools.reduce((sum, tool) => sum + tool.calls, 0) ?? 0,
		used: data?.tools.filter(tool => tool.calls > 0).length ?? 0,
		unused: data?.tools.filter(tool => tool.requests > 0 && tool.calls === 0).length ?? 0,
		unseen: data?.tools.filter(tool => tool.requests === 0 && tool.calls === 0).length ?? 0
	});
	const filters = $derived([
		{ id: 'all', label: 'All tools', count: data?.tools.length ?? 0 },
		{ id: 'used', label: 'Invoked', count: totals.used },
		{ id: 'unused', label: 'Offered, unused', count: totals.unused },
		{ id: 'unseen', label: 'Not observed', count: totals.unseen }
	]);
	const rows = $derived((data?.tools ?? []).filter(tool =>
		tool.name.toLowerCase().includes(query.trim().toLowerCase()) &&
		(filter === 'all' || (filter === 'used' ? tool.calls > 0 : filter === 'unused' ? tool.requests > 0 && tool.calls === 0 : tool.requests === 0 && tool.calls === 0))
	).toSorted((a, b) => (sort === 'calls' ? b.calls - a.calls : sort === 'offers' ? b.requests - a.requests : 0) || a.name.localeCompare(b.name)));
	const maxCalls = $derived(Math.max(1, ...rows.map(tool => tool.calls)));

	async function refresh() {
		if (loading) return;
		loading = true;
		try { data = await getToolUsage(); updated = new Date(); error = ''; }
		catch (cause) { error = cause instanceof Error ? cause.message : 'Tool usage unavailable'; }
		finally { loading = false; }
	}
	function reset() { query = ''; filter = 'all'; }
	onMount(() => {
		void refresh();
		const timer = setInterval(() => { if (!document.hidden) void refresh(); }, 60000);
		return () => clearInterval(timer);
	});
</script>

<section class="tool-usage" id="tool-use" aria-labelledby="tool-use-title">
	<header class="usage-heading">
		<div><h2 id="tool-use-title">Tool use</h2><p>What Phi reaches for. What stays untouched.</p></div>
		<button class="refresh" onclick={refresh} disabled={loading} aria-label="Refresh tool usage">{loading ? 'Reading…' : 'Refresh'}</button>
	</header>
	{#if error}<p class="error" role="alert">{error}. {data ? 'Showing the last successful read.' : 'Use Refresh to try again.'}</p>{/if}
	{#if data}
		<div class="observation">
			<p><strong>{number.format(totals.calls)}</strong> invocations across <strong>{totals.used}</strong> tools</p>
			<span title={data.since ? new Date(data.since).toLocaleString() : ''}>{data.since ? `Observed from ${date.format(new Date(data.since))}` : 'Waiting for the first observation'}<span class="window">Rolling {data.windowDays}-day window</span></span>
		</div>
		<nav class="filters" aria-label="Tool use filters">
			{#each filters as choice}
				<button class:chosen={filter === choice.id} aria-pressed={filter === choice.id} onclick={() => { filter = choice.id; selected = null; }}><span>{choice.label}</span><b>{choice.count}</b></button>
			{/each}
		</nav>
		<div class="toolbar">
			<label class="search"><span class="sr-only">Find a tool</span><input type="search" bind:value={query} placeholder="Find a tool…" /></label>
			<label class="sort"><span>Sort</span><select bind:value={sort}><option value="calls">Most calls</option><option value="offers">Most offered</option><option value="name">Name</option></select></label>
		</div>
		<div class="results-caption" aria-live="polite"><span>{rows.length} of {data.tools.length} tools</span><span>Select a tool to inspect</span></div>
		<div class="inventory" role="region" aria-label="Tool observations">
			<table>
				<thead><tr><th scope="col">Tool</th><th scope="col" class="numeric">Calls</th><th scope="col" class="numeric">Offered<span>requests</span></th><th scope="col" class="numeric">Runs</th></tr></thead>
				<tbody>
					{#each rows as row (row.name)}
						<tr class:active={selected === row.name} class:unused={row.calls === 0}>
							<th scope="row"><button class="tool-name" aria-expanded={selected === row.name} aria-controls={`tool-${row.name}`} onclick={() => selected = selected === row.name ? null : row.name}><span class="disclosure" aria-hidden="true">{selected === row.name ? '−' : '+'}</span><span>{#each row.name.split('_') as part, index}{index ? '_' : ''}<wbr />{part}{/each}</span></button></th>
							<td class="numeric volume"><span class="call-bar" style:width={`${100 * row.calls / maxCalls}%`} aria-hidden="true"></span><span class="count">{number.format(row.calls)}</span></td>
							<td class="numeric">{number.format(row.requests)}</td><td class="numeric">{number.format(row.runs)}</td>
						</tr>
						{#if selected === row.name}
							{@const calls = data.recent.filter(call => call.name === row.name)}
							<tr class="detail-row"><td colspan="4"><div class="tool-detail" id={`tool-${row.name}`}>
								<div class="detail-heading"><h3>{row.name}</h3><span>{row.calls ? `${totals.calls ? (100 * row.calls / totals.calls).toFixed(1) : 0}% of all invocations` : row.requests ? 'Offered, never invoked in this window' : 'No exposure or invocation observed'}</span></div>
								{#if row.offeredTraceUrl}<a class="offered-trace" href={row.offeredTraceUrl} target="_blank" rel="noreferrer">Inspect last run offered ↗</a>{/if}
								<dl><div><dt>Returned</dt><dd>{row.returned}</dd></div><div><dt>Raised</dt><dd class:warning={row.raised > 0}>{row.raised}</dd></div><div><dt>Unfinished</dt><dd class:warning={row.unfinished > 0}>{row.unfinished}</dd></div><div><dt>Last invoked</dt><dd>{row.lastCalled ? date.format(new Date(row.lastCalled)) : 'Not recorded'}</dd></div></dl>
								{#if calls.length}<ul class="trace-list">{#each calls as call}<li><span><time datetime={call.at} title={new Date(call.at).toLocaleString()}>{date.format(new Date(call.at))}</time><span class="outcome" class:warning={call.outcome === 'raised'}>{call.outcome}</span></span>{#if call.url}<a href={call.url} target="_blank" rel="noreferrer">Open trace ↗</a>{:else}<span>Trace unavailable</span>{/if}</li>{/each}</ul><p class="detail-note">Matches among the latest {data.recent.length} invocations across all tools.</p>
								{:else}<p class="detail-note">{row.calls ? 'No calls from this tool in the latest 40 invocations. Older activity contributes to the totals above.' : row.requests ? 'Phi received this tool definition. Open a run in Logfire to see the context and what she chose instead.' : 'This is not evidence that the tool was available and ignored.'}</p>{/if}
								<p class="detail-note">Returned includes refusals and text errors. Raised means execution threw. Neither proves an external action succeeded.</p>
							</div></td></tr>
						{/if}
					{/each}
				</tbody>
			</table>
			{#if !rows.length}<div class="empty"><p>No tools match this view.</p><button onclick={reset}>Show all tools</button></div>{/if}
		</div>
		<footer class="usage-footer"><details><summary>What these counts mean</summary><p>Offered counts model requests containing the tool definition; runs count distinct runs that offered it. Calls count invocations, including retries and refusals. Low use is a reason to investigate, not a quota.</p><p>Earlier activity is unknown. Undiscovered remote tools are absent. Calls nested inside a code-mode tool are not counted separately. Bars compare call counts within this view.</p></details><span>{updated ? `Read ${date.format(updated)}` : ''}</span></footer>
	{:else if !error}<p class="loading" role="status">Reading tool observations…</p>{/if}
</section>

<style>
	.tool-usage { --edge: #34515e; --cyan: #91cdda; --quiet: #a8b8bf; --warm: #efb47c; min-width: 0; scroll-margin-top: 118px; }
	.usage-heading { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
	.usage-heading p { color: var(--quiet); margin-top: 5px; }
	.tool-usage button, .tool-usage input, .tool-usage select { font: inherit; border: 1px solid var(--edge); color: #e3e8e6; background: #0b1821; min-height: 44px; }
	.tool-usage button { cursor: pointer; }
	.refresh { padding: 8px 16px; }
	.tool-usage button:disabled { opacity: .6; cursor: wait; }
	.observation { display: flex; align-items: center; justify-content: space-between; gap: 20px; padding: 22px 0; }
	.observation p { color: var(--quiet); font-size: 15px; }
	.observation strong { font-family: var(--font-chrome); font-size: 32px; font-weight: 400; color: #e4e7df; vertical-align: baseline; }
	.window { display: block; }.offered-trace { display: inline-block; margin-top: 10px; padding-block: 6px; font-size: 12px; }
	.observation > span { text-align: right; color: var(--quiet); font-size: 12px; }
	.filters { display: grid; grid-template-columns: repeat(4, 1fr); border-bottom: 1px solid var(--edge); gap: 4px; }
	.filters button { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 10px 12px; border-color: transparent; background: transparent; color: var(--quiet); text-transform: none; letter-spacing: 0; }
	.filters button.chosen { color: #ffe1c3; border-bottom: 2px solid var(--warm); background: #312b25; }
	.filters b { font-variant-numeric: tabular-nums; font-weight: 400; }
	.toolbar { display: flex; gap: 16px; margin: 18px 0 12px; align-items: center; }
	.search { flex: 1; min-width: 0; }.search input { width: 100%; padding: 9px 12px; box-sizing: border-box; }
	.sort { display: flex; align-items: center; gap: 8px; color: var(--quiet); font-size: 13px; }.sort select { padding: 9px; }
	.results-caption { display: flex; justify-content: space-between; gap: 8px; color: var(--quiet); font-size: 12px; margin-bottom: 8px; }
	.inventory { max-height: 540px; overflow: auto; border: 1px solid var(--edge); scrollbar-color: #45606c #09131b; }
	table { width: 100%; border-collapse: collapse; table-layout: fixed; font-size: 14px; }
	thead th { position: sticky; top: 0; z-index: 1; background: #152630; color: var(--quiet); font-weight: 400; font-size: 12px; text-align: left; height: 45px; padding: 5px 12px; border-bottom: 1px solid var(--edge); }
	thead th:first-child { width: 48%; }thead th span { display: block; font-size: 10px; }
	tbody th, tbody td { border-bottom: 1px solid #243b47; padding: 0 12px; height: 48px; font-weight: 400; }
	.numeric { text-align: right; font-variant-numeric: tabular-nums; }
	.tool-name { display: flex; gap: 10px; align-items: center; width: 100%; text-align: left; padding: 8px 0; background: transparent !important; border: none !important; box-shadow: none; text-transform: none !important; letter-spacing: 0 !important; color: var(--cyan) !important; overflow-wrap: anywhere; font-size: 13px !important; font-family: var(--font-mono) !important; }
	.disclosure { width: 12px; flex-shrink: 0; color: var(--quiet); }
	.volume { position: relative; }.call-bar { position: absolute; height: 22px; top: calc(50% - 11px); right: 0; background: #28596a; opacity: .65; }.count { position: relative; }
	.unused { color: #83969f; }.unused .tool-name { color: #a8b8bf !important; }
	.active { background: #28302e; }.active .tool-name { color: var(--warm) !important; }
	tbody tr:hover:not(.detail-row) { background: #192e39; }
	.detail-row > td { padding: 0; }.tool-detail { padding: 18px 20px; background: #091820; border-left: 2px solid var(--warm); }
	.detail-heading { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; flex-wrap: wrap; }.detail-heading h3 { overflow-wrap: anywhere; text-transform: none; letter-spacing: 0; color: var(--warm); }.detail-heading > span { color: var(--quiet); font-size: 12px; }
	dl { display: flex; gap: 16px 32px; flex-wrap: wrap; margin: 16px 0; }dt { color: var(--quiet); font-size: 12px; }dd { margin: 3px 0 0; font-variant-numeric: tabular-nums; }.warning { color: var(--warm); }
	.trace-list { list-style: none; padding: 0; margin: 0; }.trace-list li { display: flex; justify-content: space-between; gap: 12px; align-items: center; border-top: 1px solid #243b47; padding: 8px 0; font-size: 12px; }.trace-list li > span { display: flex; gap: 12px; flex-wrap: wrap; }.outcome { color: var(--quiet); }.trace-list a { padding: 8px 0; white-space: nowrap; }
	.tool-detail .detail-note { font-size: 12px; color: var(--quiet); max-width: 75ch; margin-top: 12px; }
	.usage-footer { display: flex; align-items: baseline; justify-content: space-between; gap: 20px; margin-top: 14px; font-size: 12px; color: var(--quiet); }.usage-footer > span { white-space: nowrap; }summary { cursor: pointer; min-height: 32px; }details p { margin-top: 8px; max-width: 75ch; }
	.empty, .loading { padding: 24px 12px; }.empty button { margin-top: 12px; padding: 8px 12px; }.error { color: #ffb6a2; margin-block: 12px; }
	.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; }
	.tool-usage :is(button, input, select, summary):focus-visible, .inventory:focus-visible { outline: 2px solid var(--warm); outline-offset: 2px; }
	@media (max-width: 640px) {
		.tool-usage { scroll-margin-top: 146px; }
		.observation { align-items: flex-start; flex-direction: column; gap: 6px; padding: 16px 0; }.observation > span { text-align: left; }
		.filters { grid-template-columns: repeat(2, 1fr); }.filters button { gap: 8px; padding: 8px; font-size: 13px; }.toolbar { gap: 8px; }.sort > span { display: none; }.sort select { max-width: 130px; }
		thead th:first-child { width: 46%; }thead th { padding: 5px 6px; font-size: 11px; }tbody th, tbody td { padding: 0 6px; }.tool-name { font-size: 12px !important; gap: 5px; }table { font-size: 12px; }.inventory { max-height: 480px; }
		.tool-detail { padding: 14px 12px; }.usage-footer { flex-direction: column; gap: 4px; }.trace-list li { align-items: flex-start; }.trace-list li > span { flex-direction: column; gap: 2px; }
	}
</style>

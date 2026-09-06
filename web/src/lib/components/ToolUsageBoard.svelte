<script lang="ts">
	import { onMount } from 'svelte';
	import { getToolUsage, type ToolUsage } from '$lib/tool-usage';

	let data = $state<ToolUsage | null>(null);
	let error = $state('');
	let loading = $state(false);
	let query = $state('');
	let selected = $state<string | null>(null);
	const number = new Intl.NumberFormat();
	const date = new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
	const total = $derived(data?.tools.reduce((sum, tool) => sum + tool.calls, 0) ?? 0);
	const rows = $derived((data?.tools ?? []).filter(tool => tool.name.toLowerCase().includes(query.trim().toLowerCase().replaceAll(' ', '_'))).toSorted((a, b) => b.calls - a.calls || a.name.localeCompare(b.name)));
	const maxCalls = $derived(Math.max(1, ...rows.map(tool => tool.calls)));

	async function refresh() {
		if (loading) return;
		loading = true;
		try { data = await getToolUsage(); error = ''; }
		catch (cause) { error = cause instanceof Error ? cause.message : 'Tool usage unavailable'; }
		finally { loading = false; }
	}
	onMount(() => {
		void refresh();
		const timer = setInterval(() => { if (!document.hidden) void refresh(); }, 60000);
		return () => clearInterval(timer);
	});
</script>

<section class="tool-usage" id="tool-use" aria-labelledby="tool-use-title">
	<header class="usage-heading">
		<div><h2 id="tool-use-title">Tool use</h2>{#if data}<p class="observation">{number.format(total)} calls{#if data.since}{' since '}<time datetime={data.since} title={new Date(data.since).toLocaleString()}>{date.format(new Date(data.since))}</time>{/if}</p>{/if}</div>
		<button class="quiet-button" onclick={refresh} disabled={loading} aria-label="Refresh tool usage">{loading ? 'Refreshing…' : 'Refresh'}</button>
	</header>
	{#if error}<p class="error" role="alert">{error}. {data ? 'Showing the last successful read.' : 'Try refreshing.'}</p>{/if}
	{#if data}
		<label class="search"><span class="sr-only">Search tools</span><input type="search" bind:value={query} placeholder="Search tools" /></label>
		<div class="inventory" role="region" aria-label="Tools, ordered by call count">
			<ul class="tool-list">
				{#each rows as row (row.name)}
					<li class:active={selected === row.name}>
						<button class="tool-row" aria-expanded={selected === row.name} aria-controls={selected === row.name ? `tool-${row.name}` : undefined} onclick={() => selected = selected === row.name ? null : row.name}>
							<span class="tool-name">{#each row.name.split('_') as part, index}{index ? '_' : ''}<wbr />{part}{/each}</span>
							<span class="volume"><span class="bar" style:width={`${100 * row.calls / maxCalls}%`} aria-hidden="true"></span><span class="count">{number.format(row.calls)}<span class="sr-only"> calls</span></span></span><span class="disclosure" aria-hidden="true">{selected === row.name ? '−' : '+'}</span>
						</button>
						{#if selected === row.name}
							{@const calls = data.recent.filter(call => call.name === row.name)}
							<div class="tool-detail" id={`tool-${row.name}`}>
								<p>{row.requests ? `Available in ${number.format(row.requests)} model requests across ${number.format(row.runs)} runs.` : 'Not yet observed in a model request.'}{row.requests && !row.calls ? ' No calls recorded.' : ''}</p>
								{#if row.offeredTraceUrl}<a class="offered-trace" href={row.offeredTraceUrl} target="_blank" rel="noreferrer">View last run ↗</a>{/if}
								{#if row.calls}<dl><div><dt>Returned</dt><dd>{row.returned}</dd></div><div><dt>Raised an error</dt><dd>{row.raised}</dd></div>{#if row.unfinished}<div><dt>Unfinished</dt><dd>{row.unfinished}</dd></div>{/if}</dl>{/if}
								{#if calls.length}<ul class="trace-list">{#each calls as call}<li><span><time datetime={call.at} title={new Date(call.at).toLocaleString()}>{date.format(new Date(call.at))}</time><span class="outcome">{call.outcome}</span></span>{#if call.url}<a href={call.url} target="_blank" rel="noreferrer">Trace ↗</a>{:else}<span>Trace unavailable</span>{/if}</li>{/each}</ul><p class="note">From the latest {data.recent.length} calls across all tools. A returned result may still be a refusal.</p>{:else if row.calls}<p class="note">No matches in the latest 40 calls. Last called {row.lastCalled ? date.format(new Date(row.lastCalled)) : 'at an unknown time'}.</p>{/if}
							</div>
						{/if}
					</li>
				{/each}
			</ul>
			{#if !rows.length}<div class="empty" role="status"><p>{query ? `No tools match “${query}”.` : 'No observations yet.'}</p>{#if query}<button class="quiet-button" onclick={() => query = ''}>Clear search</button>{/if}</div>{/if}
		</div>
		<details class="measurement"><summary>About these counts</summary><p>Calls include retries and refusals. We keep {data.windowDays} days of observations; earlier activity is unknown. A tool with no calls may simply not have been needed. Expand it to see whether it was available.</p><p>Remote tools appear after discovery. Work inside code-mode tools is not counted separately. Bars compare the calls in this list.</p></details>
	{:else if !error}<p role="status">Loading…</p>{/if}
</section>

<style>
	.tool-usage { font-family: var(--font-chrome); font-size: 18px; min-width: 0; scroll-margin-top: 118px; }
	.usage-heading { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
	.tool-usage .observation { margin-top: 5px; color: var(--text-mid); font: 17px/1.5 var(--font-chrome); }
	.tool-usage .quiet-button { min-height: 44px; padding: 8px 10px; font: 17px var(--font-chrome); text-transform: none; letter-spacing: 0; background: transparent; box-shadow: none; border: 1px solid transparent; color: var(--scan-hot); border-radius: 4px; }
	.tool-usage .quiet-button:hover { background: #89c9d30c; border-color: var(--line-mid); }
	.search { display: block; margin: 20px 0 12px; }
	.tool-usage .search input { width: 100%; box-sizing: border-box; min-height: 46px; padding: 10px 12px; font: 18px var(--font-chrome); color: var(--text); background: #08131b88; border: 1px solid var(--line-mid); border-radius: 4px; }
	.search input::placeholder { color: var(--text-mid); opacity: 1; }
	.inventory { max-height: 540px; overflow-y: auto; scrollbar-color: #45606c #09131b; }
	.tool-list, .trace-list { list-style: none; margin: 0; padding: 0; }
	.tool-list > li { border-bottom: 1px solid #354b554d; }
	.tool-usage .tool-row { width: 100%; display: flex; gap: 14px; align-items: center; text-align: left; min-height: 50px; padding: 10px 8px; font: 19px/1.4 var(--font-chrome); letter-spacing: 0; text-transform: none; color: var(--text); background: transparent; border: 0; box-shadow: none; border-radius: 4px; }
	.tool-usage .tool-row:hover { background: #88c9d309; color: var(--scan-hot); }
	.tool-usage .active > .tool-row { color: var(--hud-hot); background: #efb47c09; }
	.tool-name { flex: 1; min-width: 0; overflow-wrap: anywhere; }
	.volume { flex: 0 0 25%; position: relative; text-align: right; padding: 0 8px; font-variant-numeric: tabular-nums; }
	.bar { position: absolute; right: 0; top: 50%; transform: translateY(-50%); height: 22px; border-radius: 2px; background: #548c9c26; }
	.count { position: relative; }.disclosure { font-size: 16px; width: 12px; color: var(--text-mid); text-align: center; }
	.tool-detail { padding: 8px 12px 18px; color: var(--text-mid); font: 17px/1.5 var(--font-chrome); }
	.tool-detail .offered-trace { display: inline-block; padding: 10px 0; }
	dl { display: flex; flex-wrap: wrap; gap: 24px; margin: 8px 0 14px; }dt { font-size: 15px; }dd { margin: 0; color: var(--text); font-variant-numeric: tabular-nums; }
	.trace-list li { display: flex; align-items: center; justify-content: space-between; gap: 12px; border-top: 1px solid #354b554d; padding: 6px 0; }
	.trace-list li > span { display: flex; flex-wrap: wrap; gap: 4px 16px; }.trace-list a { padding: 8px; }.outcome { color: var(--text-mid); }
	.tool-detail .note { margin-top: 8px; font-size: 15px; max-width: 75ch; }
	.measurement { margin-top: 14px; color: var(--text-mid); font-size: 16px; }summary { cursor: pointer; min-height: 40px; display: list-item; padding: 6px 0; box-sizing: border-box; }.measurement p { max-width: 75ch; margin-top: 8px; }
	.empty { padding: 24px 10px; }.empty .quiet-button { margin-top: 8px; }.tool-usage .error { color: #ffb6a2; margin: 12px 0; }
	.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; }
	.tool-usage :is(button, input, summary):focus-visible { outline: 2px solid var(--scan-hot); outline-offset: -2px; }
	@media (max-width: 640px) { .tool-usage { scroll-margin-top: 146px; }.tool-usage .tool-row { font-size: 18px; gap: 8px; }.inventory { max-height: 480px; }.tool-detail { padding-inline: 8px; }.trace-list li > span { flex-direction: column; gap: 0; } }
</style>

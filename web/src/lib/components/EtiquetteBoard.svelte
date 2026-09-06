<script lang="ts">
	import { onMount } from 'svelte';
	import { getEtiquette, type EtiquetteBoard } from '$lib/etiquette';
	let data = $state<EtiquetteBoard | null>(null);
	let error = $state('');
	let loading = $state(false);
	async function refresh() {
		if (loading) return;
		loading = true;
		try { data = await getEtiquette(); error = ''; }
		catch (e) { error = e instanceof Error ? e.message : 'Etiquette unavailable'; }
		finally { loading = false; }
	}
	onMount(() => {
		void refresh();
		const timer = setInterval(() => { if (!document.hidden) void refresh(); }, 60_000);
		return () => clearInterval(timer);
	});
	const judged = $derived(data ? (data.counts.allow ?? 0) + (data.counts.warn ?? 0) + (data.counts.block ?? 0) : 0);
</script>
<section class="etiquette">
	<header><h2>Public etiquette</h2><button onclick={refresh} disabled={loading}>{loading ? 'Checking…' : 'Refresh'}</button></header>
	<p>Public drafts pass the classifier before publication. Short posts use deadpan form; blogs develop a connected piece. Private thinking and memory keep their own form.</p>
	{#if error}<p role="alert">{error}. {data ? 'Showing the last successful read.' : ''}</p>{/if}
	{#if data}
		<div class="readout"><strong>{data.counts.block ?? 0}<small>rejected / {judged} judged</small></strong><strong>{judged ? Math.round((data.counts.block ?? 0) / judged * 100) + '%' : '—'}<small>rejection rate</small></strong><strong>{data.pending}<small>awaiting Phi’s private note</small></strong></div>
		<p>{data.counts.error ?? 0} classifier outages, counted separately. Approval is permission to attempt publication, not proof it succeeded.</p>
		<p>Current rule: {data.version}. Totals include all versions. {data.since ? `Recording since ${new Date(data.since).toLocaleString()}` : 'No attempts recorded yet.'}</p>
		{#if data.reasons.length}<p>Rejections by rule: {data.reasons.map(r => `${r.policy} (${r.count})`).join(', ')}</p>{/if}
		<ol>{#each data.recent as attempt (attempt.id)}
			<li class:rejected={attempt.outcome === 'block'}><div><strong>{attempt.outcome}</strong> · {attempt.tool} · {attempt.version} <time datetime={attempt.at}>{new Date(attempt.at).toLocaleString()}</time></div>
				{#if attempt.reason}<p>{attempt.policy}: {attempt.reason}</p>{/if}
				{#if attempt.outcome === 'block'}<small>{attempt.documented_at ? 'Phi documented a revision privately' : 'Waiting for Phi’s revision note'}</small>{/if}
			</li>
		{/each}</ol>
	{:else if !error}<p>Loading classifier history…</p>{/if}
</section>
<style>
	.etiquette { border-top: 1px solid var(--hud-line, #345361); padding-block: 1.5rem; }
	header { display: flex; justify-content: space-between; align-items: center; gap: 1rem; }
	h2 { margin: 0; }
	.readout { display: flex; flex-wrap: wrap; gap: 1.5rem 3rem; margin-block: 1.5rem; color: var(--hud-cyan, #80c9dd); }
	.readout strong { font-size: 2rem; font-weight: 400; }
	small { display: block; font-size: .85rem; color: var(--text-muted, #b7b5aa); }
	ol { list-style: none; padding: 0; }
	li { padding: 1rem; border-left: 2px solid #345361; margin-block: .75rem; background: #101b23; overflow-wrap: anywhere; }
	li.rejected { border-color: #df9863; }
	li p { margin-block: .5rem; }
	time { display: block; font-size: .85rem; color: #b7b5aa; }
	button { background: #172832; color: #dbe5e6; border: 1px solid #80c9dd; padding: .6rem 1rem; font: inherit; cursor: pointer; }
	button:focus-visible { outline: 2px solid #df9863; outline-offset: 3px; }
	button:disabled { opacity: .6; cursor: wait; }
</style>

<script lang="ts">
	import { onMount } from 'svelte';
	import DiscoveryCard from '$lib/components/DiscoveryCard.svelte';
	import { getDiscoveryPool, OWNER_HANDLE } from '$lib/api';
	import type { DiscoveryEntry } from '$lib/types';

	let entries = $state<DiscoveryEntry[]>([]);
	let loaded = $state(false);

	onMount(async () => {
		entries = await getDiscoveryPool();
		loaded = true;
	});
</script>

<div class="container">
	<header>
		<h1>discovery</h1>
		<p class="muted">
			what surfaces for attention. high-signal candidates phi sees in her prompt — strangers worth
			considering. matches what phi sees: the upstream pool minus people she's already engaged with.
		</p>
		<p class="source faint">
			source: @{OWNER_HANDLE}'s recent likes (one signal among possible others; future sources can
			feed the same surface).
		</p>
	</header>

	{#if !loaded}
		<p class="faint">loading…</p>
	{:else if entries.length === 0}
		<p class="faint">nothing surfacing right now.</p>
	{:else}
		{#each entries as entry (entry.did)}
			<DiscoveryCard {entry} />
		{/each}
	{/if}
</div>

<style>
	header {
		margin-bottom: 24px;
	}

	header p {
		max-width: 600px;
		font-size: 13px;
		line-height: 1.5;
	}

	.source {
		font-size: 12px;
		margin-top: 8px;
	}
</style>

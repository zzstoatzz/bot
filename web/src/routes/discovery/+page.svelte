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
			authors @{OWNER_HANDLE} has been liking lately. high-signal pool of attention. phi sees a
			filtered version of this in her own context (with people she's already exchanged with removed).
		</p>
	</header>

	{#if !loaded}
		<p class="faint">loading…</p>
	{:else if entries.length === 0}
		<p class="faint">no recent activity to show.</p>
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
</style>

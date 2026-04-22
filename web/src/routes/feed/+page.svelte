<script lang="ts">
	import { onMount } from 'svelte';
	import PostCard from '$lib/components/PostCard.svelte';
	import { getActivity } from '$lib/api';
	import type { ActivityItem, ActivityType } from '$lib/types';

	let items = $state<ActivityItem[]>([]);
	let loaded = $state(false);
	let err = $state<string | null>(null);
	let filter = $state<ActivityType | 'all'>('all');

	onMount(async () => {
		try {
			items = await getActivity();
		} catch (e) {
			err = (e as Error).message;
		}
		loaded = true;
	});

	const filtered = $derived(filter === 'all' ? items : items.filter((i) => i.type === filter));

	const FILTERS: { value: ActivityType | 'all'; label: string }[] = [
		{ value: 'all', label: 'all' },
		{ value: 'post', label: 'posts' },
		{ value: 'note', label: 'notes' },
		{ value: 'url', label: 'bookmarks' }
	];
</script>

<div class="container">
	<header>
		<h1>feed</h1>
		<p class="muted">phi's recent posts, notes, and bookmarked URLs across surfaces.</p>
	</header>

	<div class="filters">
		{#each FILTERS as f (f.value)}
			<button class:active={filter === f.value} onclick={() => (filter = f.value)}>
				{f.label}
			</button>
		{/each}
	</div>

	{#if !loaded}
		<p class="faint">loading…</p>
	{:else if err}
		<p class="faint">failed to load: {err}</p>
	{:else if filtered.length === 0}
		<p class="faint">nothing to show.</p>
	{:else}
		{#each filtered as item (item.uri)}
			<PostCard {item} />
		{/each}
	{/if}
</div>

<style>
	header {
		margin-bottom: 24px;
	}

	.filters {
		display: flex;
		gap: 8px;
		margin-bottom: 20px;
		flex-wrap: wrap;
	}

	button.active {
		border-color: var(--accent-blue);
		color: var(--accent-blue);
	}
</style>

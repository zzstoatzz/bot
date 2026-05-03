<script lang="ts">
	import { onMount } from 'svelte';
	import Logbook from '$lib/components/Logbook.svelte';
	import Constellation from '$lib/components/Constellation.svelte';
	import { getActivity, getBlogDocs } from '$lib/api';
	import type { ActivityItem, BlogDoc } from '$lib/types';

	let items = $state<ActivityItem[]>([]);
	let blog = $state<BlogDoc[]>([]);
	let loaded = $state(false);
	let err = $state<string | null>(null);
	let filter = $state<'all' | 'post' | 'note' | 'url' | 'blog'>('all');

	onMount(async () => {
		try {
			const [a, b] = await Promise.allSettled([getActivity(), getBlogDocs()]);
			if (a.status === 'fulfilled') items = a.value;
			if (b.status === 'fulfilled') blog = b.value;
		} catch (e) {
			err = (e as Error).message;
		}
		loaded = true;
	});

	const blogAsActivity = $derived(
		blog.map(
			(d): ActivityItem & { _blogRef: BlogDoc } => ({
				type: 'url',
				text: d.content.slice(0, 280),
				title: d.title,
				time: d.publishedAt,
				uri: `at://greengale/${d.rkey}`,
				url: d.url,
				_blogRef: d
			})
		)
	);

	const all = $derived(
		[
			...items.map((i) => ({ ...i, _kind: i.type as 'post' | 'note' | 'url' })),
			...blogAsActivity.map((b) => ({ ...b, _kind: 'blog' as const }))
		].sort((a, b) => (a.time < b.time ? 1 : -1))
	);

	const filtered = $derived(filter === 'all' ? all : all.filter((i) => i._kind === filter));

	const FILTERS = [
		{ value: 'all', label: 'all' },
		{ value: 'post', label: 'posts' },
		{ value: 'note', label: 'notes' },
		{ value: 'url', label: 'urls' },
		{ value: 'blog', label: 'blog' }
	] as const;
</script>

<svelte:head>
	<title>phi · output</title>
</svelte:head>

<div class="lens">
	<div class="filter-bar chrome">
		{#each FILTERS as f (f.value)}
			<button class:active={filter === f.value} onclick={() => (filter = f.value)}>
				{f.label}
			</button>
		{/each}
	</div>

	{#if !loaded}
		<div class="overlay chrome muted">acquiring telemetry…</div>
	{:else if err}
		<div class="overlay chrome muted">signal lost · {err}</div>
	{:else if filtered.length === 0}
		<div class="overlay chrome muted">no emissions</div>
	{:else}
		<Constellation items={filtered} />
	{/if}
</div>

<Logbook />

<style>
	.lens {
		position: absolute;
		inset: 0;
	}

	.overlay {
		position: absolute;
		inset: 0;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 11px;
		color: var(--text-mid);
		letter-spacing: 0.18em;
	}

	.filter-bar {
		position: absolute;
		top: 80px;
		left: 50%;
		transform: translateX(-50%);
		display: flex;
		gap: 1px;
		background: var(--bg-panel);
		border: 1px solid var(--line-mid);
		backdrop-filter: blur(8px);
		-webkit-backdrop-filter: blur(8px);
		z-index: 5;
		clip-path: polygon(
			6px 0,
			100% 0,
			100% calc(100% - 6px),
			calc(100% - 6px) 100%,
			0 100%,
			0 6px
		);
	}

	.filter-bar button {
		border: none;
		font-size: 10px;
		padding: 6px 12px;
	}

	@media (max-width: 640px) {
		.filter-bar {
			top: 60px;
			max-width: calc(100vw - 16px);
		}
		.filter-bar button {
			font-size: 9px;
			padding: 8px 10px;
			min-height: 32px;
		}
	}
</style>

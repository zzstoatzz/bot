<script lang="ts">
	import type { DiscoveryEntry } from '$lib/types';
	import { relativeWhen } from '$lib/time';

	interface Props {
		entry: DiscoveryEntry;
	}

	let { entry }: Props = $props();

	const age = $derived(relativeWhen(entry.last_liked_at));
</script>

<div class="card">
	<div class="header">
		<a class="handle" href="https://bsky.app/profile/{entry.handle}" target="_blank" rel="noopener">
			@{entry.handle}
		</a>
		<span class="faint">
			{entry.likes_in_window} like{entry.likes_in_window === 1 ? '' : 's'}
			{#if age}· {age}{/if}
		</span>
	</div>
	{#if entry.sample_posts.length > 0}
		<ul class="samples">
			{#each entry.sample_posts as p (p.uri)}
				{#if p.text}
					<li>{p.text.length > 200 ? p.text.slice(0, 200) + '…' : p.text}</li>
				{/if}
			{/each}
		</ul>
	{/if}
</div>

<style>
	.card {
		border-left-color: var(--accent-green);
	}

	.header {
		display: flex;
		align-items: center;
		gap: 12px;
		margin-bottom: 8px;
		flex-wrap: wrap;
		font-size: 13px;
	}

	.handle {
		font-weight: 500;
		color: var(--text);
	}

	.handle:hover {
		color: var(--accent-green);
	}

	.samples {
		margin: 0;
		padding-left: 18px;
		font-size: 13px;
		color: var(--text-muted);
		line-height: 1.5;
	}

	.samples li {
		margin-bottom: 4px;
	}
</style>

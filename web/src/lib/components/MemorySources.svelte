<script lang="ts">
	import { memorySourceLink } from '$lib/person-memory';
	let { uris }: { uris: string[] } = $props();
	const sources = $derived(
		uris.map((uri, i) => ({
			uri,
			href: memorySourceLink(uri),
			label: `${uri.includes('/app.bsky.feed.post/') ? 'Post' : uri.startsWith('at://') ? 'Record' : 'Source'} ${i + 1}`,
		})),
	);
</script>

{#snippet links()}
	<div class="sources">
		{#each sources as source}{#if source.href}<a
					href={source.href}
					title={source.uri}
					target="_blank"
					rel="noopener noreferrer">{source.label} ↗</a
				>{:else}<span class="unlinked">{source.uri}</span>{/if}{/each}
	</div>
{/snippet}
{#if sources.length > 3}<details>
		<summary>{sources.length} sources</summary>{@render links()}
	</details>
{:else if sources.length}{@render links()}
{:else}<span class="missing">No source attached</span>{/if}

<style>
	.sources {
		display: flex;
		gap: 4px 16px;
		flex-wrap: wrap;
	}
	a {
		display: inline-flex;
		align-items: center;
		min-height: 44px;
		color: var(--scan-hot);
		text-decoration: none;
		font-size: 13px;
	}
	a:hover {
		text-decoration: underline;
	}
	summary {
		min-height: 44px;
		padding: 10px 0;
		cursor: pointer;
		color: var(--scan-hot);
	}
	a:focus-visible,
	summary:focus-visible {
		outline: 2px solid var(--scan-hot);
		outline-offset: 3px;
	}
	.missing,
	.unlinked {
		color: var(--text-mid);
		font-size: 12px;
		overflow-wrap: anywhere;
	}
</style>

<script lang="ts">
	import type { BlogDoc } from '$lib/types';
	import { relativeWhen } from '$lib/time';

	interface Props {
		doc: BlogDoc;
	}

	let { doc }: Props = $props();

	function excerpt(content: string, maxChars = 240): string {
		const stripped = content
			.replace(/^#+\s+.+$/gm, '')
			.replace(/\n{2,}/g, ' ')
			.replace(/^\s+|\s+$/g, '');
		if (stripped.length <= maxChars) return stripped;
		return stripped.slice(0, maxChars).replace(/\s+\S*$/, '') + '…';
	}

	const age = $derived(relativeWhen(doc.publishedAt));
</script>

<div class="card">
	<a href={doc.url} target="_blank" rel="noopener" class="title">{doc.title}</a>
	<div class="excerpt muted">{excerpt(doc.content)}</div>
	<div class="meta">
		{#if age}<span class="faint">{age}</span>{/if}
		{#if doc.tags.length > 0}
			<span class="tags">
				{#each doc.tags as tag, i (tag)}
					<span class="tag">{tag}</span>{#if i < doc.tags.length - 1}<span
							class="tag-sep faint"
							>·</span
						>{/if}
				{/each}
			</span>
		{/if}
	</div>
</div>

<style>
	.card {
		border-left-color: var(--accent-purple);
	}

	.title {
		display: block;
		font-size: 16px;
		color: var(--text);
		margin-bottom: 8px;
		text-decoration: none;
	}

	.title:hover {
		color: var(--accent-purple);
	}

	.excerpt {
		font-size: 13px;
		line-height: 1.5;
		margin-bottom: 10px;
	}

	.meta {
		font-size: 12px;
		display: flex;
		align-items: center;
		gap: 12px;
		flex-wrap: wrap;
	}

	.tags {
		display: inline-flex;
		gap: 4px;
		flex-wrap: wrap;
	}

	.tag {
		color: var(--text-muted);
		font-family: 'SF Mono', monospace;
		font-size: 11px;
	}

	.tag-sep {
		font-size: 11px;
	}
</style>

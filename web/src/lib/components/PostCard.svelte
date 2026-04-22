<script lang="ts">
	import type { ActivityItem } from '$lib/types';
	import { relativeWhen } from '$lib/time';

	interface Props {
		item: ActivityItem;
	}

	let { item }: Props = $props();

	const ACCENT: Record<ActivityItem['type'], string> = {
		post: 'var(--accent-blue)',
		note: 'var(--accent-purple)',
		url: 'var(--accent-green)'
	};

	const LABEL: Record<ActivityItem['type'], string> = {
		post: 'bluesky',
		note: 'note',
		url: 'bookmark'
	};

	function linkify(text: string): string {
		return text.replace(
			/(https?:\/\/[^\s<>"]+)/g,
			'<a href="$1" target="_blank" rel="noopener">$1</a>'
		);
	}

	function getDomain(url: string | null | undefined): string {
		if (!url) return '';
		try {
			return new URL(url).hostname.replace(/^www\./, '');
		} catch {
			return '';
		}
	}

	function viewUrl(item: ActivityItem): string {
		if (item.url) return item.url;
		if (item.uri.startsWith('at://')) return `https://pds.ls/${item.uri}`;
		return '';
	}

	const accent = $derived(ACCENT[item.type]);
	const label = $derived(LABEL[item.type]);
	const age = $derived(relativeWhen(item.time));
	const domain = $derived(item.type === 'url' ? getDomain(item.url) : '');
	const link = $derived(viewUrl(item));
	const text = $derived(item.text.length > 300 ? item.text.slice(0, 300) + '…' : item.text);
</script>

<div class="card" style="border-left-color: {accent}">
	<div class="header">
		<span class="type" style="color: {accent}">{label}</span>
	</div>
	{#if domain}
		<div class="domain">
			<a href={item.url} target="_blank" rel="noopener">{domain}</a>
		</div>
	{/if}
	{#if item.title}
		<div class="title">{item.title}</div>
	{/if}
	<!-- eslint-disable-next-line svelte/no-at-html-tags -->
	<div class="text">{@html linkify(text)}</div>
	<div class="meta faint">
		{#if age}<span>{age}</span>{/if}
		{#if link}
			<span>·</span>
			<a href={link} target="_blank" rel="noopener">view</a>
		{/if}
	</div>
</div>

<style>
	.header {
		margin-bottom: 6px;
	}

	.type {
		font-size: 11px;
		text-transform: uppercase;
		letter-spacing: 0.5px;
	}

	.domain {
		font-size: 12px;
		margin-bottom: 6px;
	}

	.domain a {
		color: var(--text-muted);
	}

	.title {
		font-size: 14px;
		color: var(--text);
		margin-bottom: 4px;
	}

	.text {
		font-size: 14px;
		line-height: 1.5;
		margin-bottom: 8px;
		white-space: pre-wrap;
		word-break: break-word;
	}

	.meta {
		font-size: 12px;
		display: flex;
		gap: 6px;
	}

	.meta a {
		color: var(--text-faint);
	}

	.meta a:hover {
		color: var(--text-muted);
	}
</style>

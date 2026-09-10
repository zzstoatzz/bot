<script lang="ts">
	import '$lib/reading.css';
	import { onMount } from 'svelte';
	import { getCapabilities, getSkills } from '$lib/api';
	import type { Capability, Skill } from '$lib/types';
	let caps = $state<Capability[]>([]);
	let skills = $state<Skill[]>([]);
	let loading = $state(true);
	let failures = $state<string[]>([]);
	let query = $state('');
	let kind = $state<'all' | 'skill' | 'tool'>('all');
	const entries = $derived(
		[
			...skills.map((skill) => ({
				...skill,
				kind: 'skill' as const,
				operator_only: false,
			})),
			...caps.map((tool) => ({
				...tool,
				kind: 'tool' as const,
				resources: [],
			})),
		].sort((a, b) => a.name.localeCompare(b.name)),
	);
	const visible = $derived(
		entries.filter(
			(entry) =>
				(kind === 'all' || entry.kind === kind) &&
				`${entry.name} ${entry.description}`
					.toLowerCase()
					.includes(query.trim().toLowerCase()),
		),
	);
	async function load() {
		loading = true;
		failures = [];
		const [tools, guidance] = await Promise.allSettled([
			getCapabilities(),
			getSkills(),
		]);
		if (tools.status === 'fulfilled') caps = tools.value;
		else failures.push('Tools could not be refreshed.');
		if (guidance.status === 'fulfilled') skills = guidance.value;
		else failures.push('Skills could not be refreshed.');
		loading = false;
	}
	onMount(load);
</script>

<svelte:head><title>Phi · Capabilities</title></svelte:head>
<main class="reading-page">
	<div class="reading-inner">
		<header class="page-heading">
			<div>
				<h1>Capabilities</h1>
				<p class="intro">
					Tools Phi can call, and skills she can load for a task.
				</p>
			</div>
			<button onclick={load} disabled={loading}
				>{loading ? 'Refreshing…' : 'Refresh'}</button
			>
		</header>
		{#if failures.length}<div class="notice" role="alert">
				{failures.join(' ')}
				{entries.length
					? 'Showing available results, including any previously loaded entries.'
					: 'Use Refresh to try again.'}
			</div>{/if}
		<section aria-label="Browse capabilities">
			<label class="search"
				>Search capabilities<input
					type="search"
					bind:value={query}
					placeholder="Memory, images, workflows…"
				/></label
			>
			<div class="filters" aria-label="Capability types">
				<button
					class:chosen={kind === 'all'}
					aria-pressed={kind === 'all'}
					onclick={() => (kind = 'all')}>All</button
				><button
					class:chosen={kind === 'skill'}
					aria-pressed={kind === 'skill'}
					onclick={() => (kind = 'skill')}>Skills</button
				><button
					class:chosen={kind === 'tool'}
					aria-pressed={kind === 'tool'}
					onclick={() => (kind = 'tool')}>Tools</button
				>
			</div>
			<p class="inventory-note">
				{#if loading}Reading the inventory…{:else}{visible.length} shown{failures.length
						? ' · Partial inventory'
						: ` · ${skills.length} skills and ${caps.length} native tools`}{/if}
			</p>
			{#if !loading && !visible.length}<div class="empty" role="status">
					{query || kind !== 'all'
						? 'No matches.'
						: failures.length
							? 'The inventory is unavailable.'
							: 'No capabilities were returned.'}{#if query || kind !== 'all'}
						<button
							onclick={() => {
								query = '';
								kind = 'all';
							}}>Clear filters</button
						>{/if}
				</div>{/if}
			{#each visible as entry (entry.kind + entry.name)}
				<details class="capability">
					<summary
						><span
							><strong
								>{entry.name.replaceAll('_', ' ').replaceAll('-', ' ')}</strong
							><span class="preview"
								>{entry.description.split('\n')[0] ||
									'No description supplied.'}</span
							></span
						><span class="kind">{entry.kind}</span></summary
					>
					<div class="description">
						{#if entry.operator_only}<p class="authorization">
								Requires Nate’s authorization.
							</p>{/if}{#each entry.description.split(/\n\s*\n/) as paragraph}<p
							>
								{paragraph}
							</p>{/each}
						<details class="reference">
							<summary>Technical reference</summary><code>{entry.name}</code
							>{#if entry.resources.length}<ul>
									{#each entry.resources as resource}<li>{resource}</li>{/each}
								</ul>{/if}
						</details>
					</div>
				</details>
			{/each}
		</section>
		<footer>
			Inventory from this release. Remote MCP tools are discovered separately
			during runs; availability and permission checks still apply.
		</footer>
	</div>
</main>

<style>
	.search {
		display: grid;
		gap: 8px;
		color: var(--text-mid);
	}
	.search input {
		width: 100%;
		box-sizing: border-box;
		min-height: 48px;
		padding: 12px;
		font: 16px var(--font-content);
		color: var(--text);
		background: #0b1720;
		border: 1px solid #52707b;
	}
	.filters {
		display: flex;
		gap: 8px;
		margin: 16px 0;
	}
	.filters button {
		min-width: 72px;
		min-height: 44px;
	}
	.filters .chosen {
		color: #ffe4c3;
		border-color: var(--hud-hot);
		background: #3b2e24;
	}
	.inventory-note {
		color: var(--text-mid);
		padding-bottom: 16px;
		font-size: 13px;
	}
	.capability {
		border-top: 1px solid #45616b70;
	}
	.capability > summary {
		display: flex;
		gap: 16px;
		justify-content: space-between;
		align-items: baseline;
		cursor: pointer;
		padding: 18px 0;
		list-style: none;
	}
	.capability > summary::-webkit-details-marker {
		display: none;
	}
	.capability > summary::after {
		content: '+';
		color: var(--scan-hot);
		font-size: 22px;
	}
	.capability[open] > summary::after {
		content: '−';
	}
	.capability > summary > span:first-child {
		flex: 1;
		min-width: 0;
	}
	strong {
		display: block;
		font: 400 24px/1.25 var(--font-chrome);
		color: #f0d1ad;
		overflow-wrap: anywhere;
		text-shadow: 0 2px 2px #0009;
	}
	.preview {
		display: -webkit-box;
		line-clamp: 2;
		-webkit-line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow: hidden;
		margin-top: 6px;
		color: #b4c3c8;
	}
	.capability[open] .preview {
		display: none;
	}
	.kind {
		color: #a0d9e6;
		font-size: 13px;
	}
	.description {
		padding: 0 0 22px;
		max-width: 75ch;
		overflow-wrap: anywhere;
	}
	.description p {
		white-space: pre-wrap;
		margin-bottom: 12px;
	}
	.authorization {
		color: #f1c496;
	}
	.reference {
		color: var(--text-mid);
		margin-top: 18px;
	}
	.reference summary {
		cursor: pointer;
		min-height: 44px;
	}
	code {
		font-size: 13px;
	}
	@media (max-width: 600px) {
		.capability > summary {
			gap: 10px;
		}
		strong {
			font-size: 23px;
		}
		.preview {
			font-size: 14px;
		}
	}
	@media (max-width: 360px) { .page-heading { flex-wrap: wrap; } }
</style>

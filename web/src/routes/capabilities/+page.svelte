<script lang="ts">
	import '$lib/reading.css';
	import { onMount, tick } from 'svelte';
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
	let selected = $state('');
	let inspecting = $state(false);
	let surface = $state<HTMLElement>();
	let detailHeading = $state<HTMLHeadingElement>();
	let listScroll = 0;
	let lastButton: HTMLButtonElement | undefined;
	const active = $derived(
		visible.find((entry) => `${entry.kind}:${entry.name}` === selected) ??
			visible.find((entry) => entry.kind === 'skill') ??
			visible[0],
	);
	async function inspect(key: string, button: HTMLButtonElement) {
		listScroll = surface?.scrollTop ?? 0;
		lastButton = button;
		selected = key;
		inspecting = true;
		await tick();
		if (window.matchMedia('(max-width:760px)').matches) {
			surface?.scrollTo({ top: 0 });
			detailHeading?.focus({ preventScroll: true });
		}
	}
	async function back() {
		inspecting = false;
		await tick();
		surface?.scrollTo({ top: listScroll });
		lastButton?.focus({ preventScroll: true });
	}
	onMount(load);
</script>

<svelte:head><title>Phi · Capabilities</title></svelte:head>
<main bind:this={surface} class="capabilities" class:inspecting>
	<header class="heading">
		<div>
			<h1>Capabilities</h1>
			<p>Tools Phi can call. Skills she can load.</p>
		</div>
		<button class="refresh" onclick={load} disabled={loading}
			>{loading ? 'Reading…' : 'Refresh'}</button
		>
	</header>
	{#if failures.length}<p class="failure" role="alert">
			{failures.join(' ')} Available results remain below.
		</p>{/if}
	<div class="workbench">
		<nav class="index" aria-label="Capability index">
			<div class="index-controls">
				<label
					><span class="sr-only">Search capabilities</span><input
						type="search"
						placeholder="Name or purpose"
						bind:value={query}
					/></label
				>
				<div class="filters">
					<button
						class:chosen={kind === 'all'}
						aria-pressed={kind === 'all'}
						onclick={() => (kind = 'all')}>All</button
					><button
						class:chosen={kind === 'skill'}
						aria-pressed={kind === 'skill'}
						onclick={() => (kind = 'skill')}
						>Skills <span>{skills.length}</span></button
					><button
						class:chosen={kind === 'tool'}
						aria-pressed={kind === 'tool'}
						onclick={() => (kind = 'tool')}
						>Tools <span>{caps.length}</span></button
					>
				</div>
			</div>
			<div class="index-list">
				{#if loading && !entries.length}<p class="empty" role="status">
						Reading the inventory…
					</p>{/if}
				{#each ['skill', 'tool'] as group}
					{@const members = visible.filter((entry) => entry.kind === group)}
					{#if members.length}<h2 class:skill={group === 'skill'}>
							{group === 'skill' ? 'Skills' : 'Native tools'}
							<span>{members.length}</span>
						</h2>
						{#each members as entry (entry.kind + entry.name)}<button
								class="entry"
								class:active={active === entry}
								class:skill={entry.kind === 'skill'}
								onclick={(event) =>
									inspect(`${entry.kind}:${entry.name}`, event.currentTarget)}
								aria-current={active === entry ? 'true' : undefined}
								><span class="entry-mark" aria-hidden="true"
									>{entry.kind === 'skill' ? '◇' : '⌁'}</span
								><span
									>{entry.name.replaceAll('_', ' ').replaceAll('-', ' ')}</span
								><span class="entry-arrow" aria-hidden="true">›</span></button
							>{/each}
					{/if}
				{/each}
				{#if !loading && !visible.length}<p class="empty">
						{failures.length && !entries.length
							? 'Inventory unavailable. Use Refresh to retry.'
							: 'No matches.'}
					</p>{/if}
			</div>
			<p class="index-note">Remote MCP tools are discovered during runs.</p>
		</nav>
		<article class="inspector" class:skill={active?.kind === 'skill'}>
			<button class="back" onclick={back}>‹ All capabilities</button>
			{#if active}
				<p class="kind">
					{active.kind === 'skill'
						? 'Skill · loaded when needed'
						: 'Native tool'}
				</p>
				<h2 bind:this={detailHeading} tabindex="-1">
					{active.name.replaceAll('_', ' ').replaceAll('-', ' ')}
				</h2>
				<div class="description">
					{#each active.description.split(/\n\s*\n/) as paragraph}<p>
							{paragraph}
						</p>{/each}
				</div>
				{#if active.operator_only}<p class="permission">
						<span aria-hidden="true">◇</span> Requires Nate’s authorization
					</p>{/if}
				<div class="technical">
					<span>Identifier</span><code>{active.name}</code
					>{#if active.resources.length}<span>Resources</span
						>{#each active.resources as resource}<code>{resource}</code
							>{/each}{/if}
				</div>
				<p class="inspector-note">
					{active.kind === 'skill'
						? 'A skill supplies instructions and supporting material. Phi chooses when to load it.'
						: 'Listed in this release. Permission and availability checks still apply when called.'}
				</p>
			{:else}<p class="empty">
					{loading
						? 'Reading the inventory…'
						: entries.length
							? 'Try a different name or purpose.'
							: 'The inventory is unavailable.'}
				</p>{/if}
		</article>
	</div>
</main>

<style>
	.capabilities {
		position: absolute;
		inset: 0;
		padding: 118px 32px 64px;
		color: #e8e7df;
		overflow: auto;
		display: flex;
		flex-direction: column;
		max-width: 1280px;
		margin: auto;
	}
	.heading {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 20px;
		margin-bottom: 24px;
	}
	h1 {
		font: 400 38px/1.1 var(--font-chrome);
		letter-spacing: 0.07em;
		color: #efbe91;
		margin: 0;
		text-shadow: 0 2px 2px #000;
	}
	.heading p {
		color: #a6b9c5;
		margin: 10px 0 0;
		font-size: 14px;
	}
	button,
	.index-controls label {
		display: grid;
		gap: 8px;
		color: #b3c5cf;
		font-size: 12px;
	}
	input {
		font: inherit;
	}
	button {
		cursor: pointer;
	}
	button:focus-visible,
	input:focus-visible {
		outline: 2px solid #a1e5ec;
		outline-offset: 3px;
	}
	.refresh {
		color: #d8d5cd;
		background: #17232c;
		border: 1px solid #526b77;
		padding: 10px 16px;
		min-height: 44px;
		font-family: var(--font-chrome);
	}
	.workbench {
		display: grid;
		grid-template-columns: 320px minmax(0, 1fr);
		min-height: 0;
		flex: 1;
		border: 1px solid #415461;
		border-top: 1px solid #aa8763;
		box-shadow:
			inset 0 1px 0 #ffffff14,
			0 14px 35px #0006;
		background: #0c1721;
	}
	.index {
		display: flex;
		flex-direction: column;
		min-height: 0;
		border-right: 1px solid #40525e;
		background: #0b141d;
	}
	.index-controls {
		padding: 16px;
		border-bottom: 1px solid #354653;
	}
	.index-controls label {
		display: grid;
		gap: 8px;
		color: #b3c5cf;
		font-size: 12px;
	}
	input {
		width: 100%;
		padding: 12px;
		box-sizing: border-box;
		background: #111f2a;
		border: 1px solid #42606d;
		color: #eff6f5;
		font-size: 16px;
	}
	.filters {
		display: flex;
		gap: 4px;
		margin-top: 12px;
	}
	.filters button {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 4px;
		white-space: nowrap;
		flex: 1;
		padding: 9px 4px;
		background: none;
		border: 0;
		border-bottom: 2px solid transparent;
		color: #a7bbc8;
		min-height: 44px;
		font: 18px var(--font-chrome);
		text-transform: none;
		letter-spacing: 0;
	}
	.filters button.chosen {
		color: #fff0db;
		border-color: #e0ad79;
		background: #322a23;
	}
	.filters span {
		font: 12px var(--font-mono);
		color: #8ca4b0;
		margin-left: 3px;
	}
	.index-list {
		overflow: auto;
		flex: 1;
		padding: 8px 12px 20px;
	}
	.index h2 {
		display: flex;
		justify-content: space-between;
		padding: 18px 10px 8px;
		margin: 0;
		font: 17px var(--font-chrome);
		color: #84d5e3;
	}
	.index h2.skill {
		color: #bea8e0;
	}
	.index h2 span {
		font: 12px var(--font-mono);
	}
	.entry {
		display: flex;
		align-items: center;
		gap: 10px;
		width: 100%;
		min-height: 44px;
		text-align: left;
		padding: 10px;
		color: #cad5db;
		background: none;
		border: 1px solid transparent;
		font: 19px/1.2 var(--font-chrome);
		text-transform: none;
		letter-spacing: 0;
	}
	.entry-mark {
		color: #79c5d8;
		width: 18px;
		flex-shrink: 0;
	}
	.entry.skill .entry-mark {
		color: #b99bdc;
	}
	.entry-arrow {
		margin-left: auto;
		color: #78909e;
	}
	.entry:hover {
		background: #182a37;
	}
	.entry.active {
		background: #213542;
		border-color: #638b98;
		color: #fff;
		box-shadow: inset 3px 0 #8fdbe5;
	}
	.entry.active.skill {
		background: #28263b;
		border-color: #75698d;
		box-shadow: inset 3px 0 #b5a0d6;
	}
	.index-note {
		font-size: 12px;
		color: #91a6b4;
		border-top: 1px solid #30424f;
		padding: 14px 18px;
		margin: 0;
	}
	.inspector {
		--accent: #90dce4;
		position: relative;
		padding: 40px;
		overflow: auto;
		background:
			radial-gradient(ellipse at 100% 0, #24415266, transparent 65%),
			linear-gradient(145deg, #152631, #0b151f);
	}
	.inspector.skill {
		--accent: #c5b2e9;
		background:
			radial-gradient(ellipse at 100% 0, #50416544, transparent 65%),
			linear-gradient(145deg, #1c2430, #0c1620);
	}
	.kind {
		color: var(--accent);
		font: 16px var(--font-chrome);
		margin: 0 0 8px;
	}
	.inspector h2 {
		color: #fff0d9;
		font: 400 36px/1.1 var(--font-chrome);
		margin: 0 0 24px;
		overflow-wrap: anywhere;
	}
	.description {
		max-width: 66ch;
		font: 16px/1.75 var(--font-content);
		color: #dde3e6;
	}
	.description p {
		white-space: pre-wrap;
		margin: 0 0 18px;
	}
	.permission {
		display: flex;
		gap: 10px;
		color: #f0c698;
		border-left: 2px solid #d9a270;
		background: #382b224d;
		padding: 12px 14px;
		font-size: 14px;
	}
	.technical {
		margin-top: 36px;
		border-top: 1px solid #456071;
		padding-top: 20px;
		display: grid;
		gap: 10px;
	}
	.technical span {
		font-size: 12px;
		color: #9db2c1;
	}
	code {
		font: 13px var(--font-mono);
		overflow-wrap: anywhere;
		color: var(--accent);
	}
	.inspector-note {
		color: #92a6b3;
		font-size: 13px;
		line-height: 1.6;
		margin-top: 28px;
		max-width: 60ch;
	}
	.back {
		display: none;
	}
	.empty,
	.failure {
		padding: 18px;
		color: #d5bca1;
		line-height: 1.6;
	}
	@media (max-width: 760px) {
		.capabilities {
			padding: 146px 14px 65px;
		}
		.heading {
			align-items: start;
			margin-bottom: 20px;
		}
		h1 {
			font-size: 32px;
		}
		.heading p {
			font-size: 13px;
		}
		.workbench {
			display: block;
			flex: none;
		}
		.index {
			border-right: 0;
		}
		.index-list {
			overflow: visible;
		}
		.inspector {
			display: none;
			padding: 24px;
		}
		.inspecting .index {
			display: none;
		}
		.inspecting .inspector {
			display: block;
		}
		.back {
			display: block;
			color: #a5d9e7;
			background: none;
			border: 0;
			padding: 0 0 22px;
			min-height: 44px;
			text-transform: none;
		}
		.inspector h2 {
			font-size: 34px;
		}
		.technical {
			margin-top: 26px;
		}
		.entry {
			min-height: 49px;
			font-size: 21px;
		}
	}
</style>

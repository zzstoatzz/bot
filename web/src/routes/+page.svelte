<script lang="ts">
	import { onMount } from 'svelte';
	import MindMap from '$lib/components/MindMap.svelte';
	import Logbook from '$lib/components/Logbook.svelte';
	import {
		getMemoryGraph,
		getDiscoveryPool,
		getActiveObservations,
		getGoals,
		PHI_HANDLE
	} from '$lib/api';
	import type { GraphNode, DiscoveryEntry, Observation, Goal } from '$lib/types';

	let goals = $state<Goal[]>([]);
	let observations = $state<Observation[]>([]);
	let known = $state<GraphNode[]>([]);
	let candidates = $state<DiscoveryEntry[]>([]);
	let avatars = $state<Record<string, string>>({});
	let loaded = $state(false);
	let err = $state<string | null>(null);

	async function fetchAvatars(handles: string[]): Promise<Record<string, string>> {
		const map: Record<string, string> = {};
		const filtered = handles.filter((h) => h && !h.includes('example'));
		for (let i = 0; i < filtered.length; i += 25) {
			const chunk = filtered.slice(i, i + 25);
			const params = chunk.map((h) => `actors=${encodeURIComponent(h)}`).join('&');
			try {
				const res = await fetch(
					`https://typeahead.waow.tech/xrpc/app.bsky.actor.getProfiles?${params}`
				);
				if (!res.ok) continue;
				const data: { profiles: { handle: string; avatar?: string }[] } = await res.json();
				for (const p of data.profiles) if (p.avatar) map[p.handle] = p.avatar;
			} catch {
				/* skip */
			}
		}
		return map;
	}

	onMount(async () => {
		try {
			const [graphR, discR, obsR, goalsR] = await Promise.allSettled([
				getMemoryGraph(),
				getDiscoveryPool(),
				getActiveObservations(),
				getGoals()
			]);

			if (graphR.status === 'fulfilled') {
				known = graphR.value.nodes.filter((n) => n.type === 'user') as GraphNode[];
			}
			if (discR.status === 'fulfilled') candidates = discR.value;
			if (obsR.status === 'fulfilled') observations = obsR.value;
			if (goalsR.status === 'fulfilled') goals = goalsR.value;

			const handles = new Set<string>([PHI_HANDLE]);
			for (const n of known) handles.add(n.label.replace(/^@/, ''));
			for (const c of candidates) handles.add(c.handle);
			avatars = await fetchAvatars([...handles]);
		} catch (e) {
			err = (e as Error).message;
		} finally {
			loaded = true;
		}
	});
</script>

<svelte:head>
	<title>phi · mind</title>
</svelte:head>

<div class="lens">
	{#if !loaded}
		<div class="overlay chrome muted">acquiring map…</div>
	{:else if err}
		<div class="overlay chrome muted">connection lost · {err}</div>
	{:else}
		<MindMap {goals} {observations} {known} {candidates} {avatars} />
	{/if}

	<!-- Bottom-of-map orientation key -->
	<div class="key chrome">
		<span class="kii"><span class="hex" style="color: var(--hud-hot)"></span>self</span>
		<span class="sep"></span>
		<span class="kii"><span class="hex" style="color: var(--warn)"></span>anchor</span>
		<span class="kii"><span class="hex" style="color: var(--scan-mid)"></span>attention</span>
		<span class="kii"><span class="dot solid"></span>known</span>
		<span class="kii"><span class="dot dashed"></span>horizon</span>
	</div>
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

	.key {
		position: absolute;
		bottom: 60px;
		left: 50%;
		transform: translateX(-50%);
		display: flex;
		gap: 14px;
		font-size: 10px;
		color: var(--text-dim);
		background: var(--bg-panel);
		border: 1px solid var(--line-mid);
		backdrop-filter: blur(8px);
		-webkit-backdrop-filter: blur(8px);
		padding: 7px 14px;
		pointer-events: none;
		clip-path: polygon(
			6px 0,
			100% 0,
			100% calc(100% - 6px),
			calc(100% - 6px) 100%,
			0 100%,
			0 6px
		);
	}

	.kii {
		display: flex;
		align-items: center;
		gap: 6px;
	}

	.sep {
		width: 1px;
		height: 10px;
		background: var(--line-mid);
	}

	.dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		display: inline-block;
	}

	.dot.solid {
		background: var(--text);
	}

	.dot.dashed {
		background: transparent;
		border: 1px dashed var(--text-dim);
	}

	@media (max-width: 640px) {
		.key {
			bottom: 44px;
			gap: 8px;
			font-size: 9px;
			padding: 5px 10px;
			max-width: calc(100vw - 16px);
			flex-wrap: wrap;
			justify-content: center;
		}
	}
</style>

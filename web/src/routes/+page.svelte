<script lang="ts">
	import { onMount } from 'svelte';
	import Atlas from '$lib/components/Atlas.svelte';
	import Logbook from '$lib/components/Logbook.svelte';
	import {
		getMemoryGraph,
		getDiscoveryPool,
		getActiveObservations,
		getGoals,
		PHI_HANDLE
	} from '$lib/api';
	import type { AtlasPoint, LogbookEntry, GraphNode, DiscoveryEntry, Observation, Goal } from '$lib/types';

	let points = $state<AtlasPoint[]>([]);
	let edges = $state<{ source: string; target: string }[]>([]);
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

	function entryFor(p: AtlasPoint): LogbookEntry {
		if (p.kind === 'handle-engaged' || p.kind === 'handle-candidate') {
			const pl = p.payload as { handle: string; did?: string };
			return {
				kind: 'handle',
				handle: pl.handle,
				did: pl.did,
				engaged: p.kind === 'handle-engaged',
				payload: pl
			};
		}
		if (p.kind === 'observation') return { kind: 'observation', observation: p.payload as Observation };
		if (p.kind === 'goal') return { kind: 'goal', goal: p.payload as Goal };
		// phi has no logbook (own self)
		return { kind: 'handle', handle: PHI_HANDLE, engaged: true, payload: {} };
	}

	function jitter(seed: string, amplitude: number): [number, number] {
		// deterministic position based on string hash, in [-amp, amp]
		let h1 = 2166136261;
		let h2 = 5381;
		for (let i = 0; i < seed.length; i++) {
			h1 ^= seed.charCodeAt(i);
			h1 = Math.imul(h1, 16777619);
			h2 = ((h2 << 5) + h2 + seed.charCodeAt(i)) | 0;
		}
		const a = ((h1 >>> 0) % 10000) / 10000; // 0..1
		const b = ((h2 >>> 0) % 10000) / 10000;
		const angle = a * Math.PI * 2;
		const r = b * amplitude;
		return [Math.cos(angle) * r, Math.sin(angle) * r];
	}

	onMount(async () => {
		try {
			const [graphR, discR, obsR, goalsR] = await Promise.allSettled([
				getMemoryGraph(),
				getDiscoveryPool(),
				getActiveObservations(),
				getGoals()
			]);

			const handles: string[] = [PHI_HANDLE];
			const pts: AtlasPoint[] = [];

			if (graphR.status === 'fulfilled') {
				const data = graphR.value;
				for (const n of data.nodes as GraphNode[]) {
					if (n.type === 'phi') {
						pts.push({
							id: n.id,
							kind: 'phi',
							label: 'phi',
							x: 0,
							y: 0,
							payload: {}
						});
					} else {
						const handle = n.label.replace(/^@/, '');
						handles.push(handle);
						pts.push({
							id: n.id,
							kind: 'handle-engaged',
							label: n.label,
							x: n.x ?? 0,
							y: n.y ?? 0,
							payload: { handle }
						});
					}
				}
				edges = data.edges.map((e) => ({ source: e.source, target: e.target }));
			}

			if (discR.status === 'fulfilled') {
				const cands = discR.value as DiscoveryEntry[];
				const engagedHandles = new Set(
					pts.filter((p) => p.kind === 'handle-engaged').map((p) => (p.payload as { handle: string }).handle)
				);
				for (const c of cands) {
					if (engagedHandles.has(c.handle)) continue; // already in graph
					handles.push(c.handle);
					// position candidates on the periphery (radius ~0.85 from center)
					const [jx, jy] = jitter(c.handle, 0.85);
					pts.push({
						id: `cand-${c.did}`,
						kind: 'handle-candidate',
						label: `@${c.handle}`,
						x: jx,
						y: jy,
						payload: { handle: c.handle, did: c.did, entry: c }
					});
				}
			}

			if (obsR.status === 'fulfilled') {
				const obs = obsR.value as Observation[];
				for (const o of obs) {
					const [jx, jy] = jitter(o.rkey, 0.45);
					pts.push({
						id: `obs-${o.rkey}`,
						kind: 'observation',
						label: o.content,
						x: jx,
						y: jy,
						payload: o
					});
				}
			}

			if (goalsR.status === 'fulfilled') {
				const goals = goalsR.value as Goal[];
				for (const g of goals) {
					const [jx, jy] = jitter(g.rkey, 0.65);
					pts.push({
						id: `goal-${g.rkey}`,
						kind: 'goal',
						label: g.title,
						x: jx,
						y: jy,
						payload: g
					});
				}
			}

			// load avatars and attach to points
			const avatars = await fetchAvatars(handles);
			for (const p of pts) {
				if (p.kind === 'handle-engaged' || p.kind === 'handle-candidate' || p.kind === 'phi') {
					const handle =
						p.kind === 'phi'
							? PHI_HANDLE
							: (p.payload as { handle: string }).handle;
					p.avatar = avatars[handle] ?? null;
				}
			}

			points = pts;
			loaded = true;
		} catch (e) {
			err = (e as Error).message;
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
		<div class="overlay chrome muted">signal lost · {err}</div>
	{:else if points.length === 0}
		<div class="overlay chrome muted">empty map · no objects in attention</div>
	{:else}
		<Atlas {points} {edges} {entryFor} />
	{/if}

	<div class="legend chrome">
		<span class="li"><span class="hex" style="color: var(--hud-hot)"></span>self</span>
		<span class="li"><span class="hex" style="color: var(--text)"></span>in memory</span>
		<span class="li"
			><span class="hex ring" style="color: var(--text-dim)"></span>on radar</span
		>
		<span class="li"><span class="hex" style="color: var(--scan-mid)"></span>attention</span>
		<span class="li"><span class="hex" style="color: var(--warn)"></span>goal</span>
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

	.legend {
		position: absolute;
		bottom: 60px;
		left: 50%;
		transform: translateX(-50%);
		display: flex;
		gap: 18px;
		font-size: 10px;
		color: var(--text-dim);
		background: var(--bg-panel);
		border: 1px solid var(--line-mid);
		backdrop-filter: blur(8px);
		-webkit-backdrop-filter: blur(8px);
		padding: 8px 14px;
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

	@media (max-width: 640px) {
		.legend {
			bottom: 44px;
			gap: 10px;
			font-size: 9px;
			padding: 6px 10px;
			max-width: calc(100vw - 16px);
			flex-wrap: wrap;
			justify-content: center;
		}
	}

	.li {
		display: flex;
		align-items: center;
		gap: 6px;
	}
</style>

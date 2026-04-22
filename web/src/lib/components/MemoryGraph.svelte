<script lang="ts">
	import { onMount } from 'svelte';
	import * as d3 from 'd3';
	import { getMemoryGraph, PHI_HANDLE } from '$lib/api';
	import type { GraphData, GraphNode } from '$lib/types';

	let container: HTMLDivElement;
	let loading = $state(true);
	let err = $state<string | null>(null);

	const RADII: Record<GraphNode['type'], number> = { phi: 14, user: 9 };
	const COLORS: Record<GraphNode['type'], string> = {
		phi: 'var(--accent-blue)',
		user: 'var(--accent-green)'
	};

	async function fetchAvatars(nodes: GraphNode[]): Promise<Record<string, string>> {
		const handles = nodes
			.filter((d) => d.type === 'phi' || d.type === 'user')
			.map((d) => (d.type === 'phi' ? PHI_HANDLE : d.label.replace(/^@/, '')))
			.filter((h) => h && !h.includes('example'));
		if (handles.length === 0) return {};
		const map: Record<string, string> = {};
		for (let i = 0; i < handles.length; i += 25) {
			const chunk = handles.slice(i, i + 25);
			const params = chunk.map((h) => `actors=${encodeURIComponent(h)}`).join('&');
			try {
				const res = await fetch(
					`https://typeahead.waow.tech/xrpc/app.bsky.actor.getProfiles?${params}`
				);
				if (!res.ok) continue;
				const data: { profiles: { handle: string; avatar?: string }[] } = await res.json();
				for (const p of data.profiles) {
					if (p.avatar) map[p.handle] = p.avatar;
				}
			} catch {
				/* skip */
			}
		}
		return map;
	}

	function render(data: GraphData, avatars: Record<string, string>) {
		const width = container.clientWidth;
		const height = container.clientHeight;
		const pad = 60;

		type SimNode = GraphNode &
			d3.SimulationNodeDatum & {
				sx: number;
				sy: number;
				avatar?: string;
				_patternId?: string;
			};

		const nodes: SimNode[] = data.nodes.map((d) => {
			const avatar = d.type === 'phi' ? avatars[PHI_HANDLE] : avatars[d.label.replace(/^@/, '')];
			const sx =
				d.x != null ? pad + ((d.x + 1) / 2) * (width - 2 * pad) : width / 2;
			const sy =
				d.y != null ? pad + ((d.y + 1) / 2) * (height - 2 * pad) : height / 2;
			return { ...d, x: sx, y: sy, sx, sy, avatar };
		});

		const tooltip = d3.select(container).append('div').attr('class', 'tooltip');

		const svg = d3
			.select(container)
			.append('svg')
			.attr('width', width)
			.attr('height', height);

		const defs = svg.append('defs');
		const g = svg.append('g');
		let currentZoom: d3.ZoomTransform = d3.zoomIdentity;

		nodes
			.filter((n) => n.avatar)
			.forEach((n, i) => {
				const pid = `avatar-${i}`;
				n._patternId = pid;
				defs
					.append('pattern')
					.attr('id', pid)
					.attr('width', 1)
					.attr('height', 1)
					.attr('patternContentUnits', 'objectBoundingBox')
					.append('image')
					.attr('href', n.avatar!)
					.attr('width', 1)
					.attr('height', 1)
					.attr('preserveAspectRatio', 'xMidYMid slice');
			});

		const zoom = d3
			.zoom<SVGSVGElement, unknown>()
			.scaleExtent([0.2, 5])
			.on('zoom', (e) => {
				g.attr('transform', e.transform.toString());
				currentZoom = e.transform;
				label.attr('font-size', (d) => {
					const base = d.type === 'phi' ? 13 : 10;
					return base / Math.max(currentZoom.k, 0.5);
				});
			});

		svg.call(zoom);

		const simulation = d3
			.forceSimulation(nodes as unknown as d3.SimulationNodeDatum[])
			.force(
				'link',
				d3
					.forceLink(data.edges)
					.id((d: unknown) => (d as SimNode).id)
					.distance(40)
			)
			.force('charge', d3.forceManyBody().strength(-80))
			.force('x', d3.forceX((d) => (d as SimNode).sx).strength(0.3))
			.force('y', d3.forceY((d) => (d as SimNode).sy).strength(0.3))
			.force(
				'collision',
				d3.forceCollide().radius((d) => RADII[(d as SimNode).type] + 4)
			);

		const link = g
			.append('g')
			.selectAll('line')
			.data(data.edges)
			.join('line')
			.attr('stroke', 'var(--border-dim)')
			.attr('stroke-width', 1)
			.attr('stroke-opacity', 0.5);

		const node = g
			.append('g')
			.selectAll('circle')
			.data(nodes)
			.join('circle')
			.attr('r', (d) => RADII[d.type])
			.attr('fill', (d) => (d._patternId ? `url(#${d._patternId})` : COLORS[d.type]))
			.attr('stroke', (d) => (d._patternId ? COLORS[d.type] : 'var(--bg)'))
			.attr('stroke-width', (d) => (d._patternId ? 2 : 1.5))
			.style('cursor', 'grab')
			.on('mouseover', (_, d) => {
				tooltip
					.style('opacity', 1)
					.html(
						`<strong>${d.label}</strong><br><span style="color:${COLORS[d.type]}">${d.type}</span>`
					);
			})
			.on('mousemove', (e: MouseEvent) => {
				tooltip.style('left', `${e.pageX + 12}px`).style('top', `${e.pageY - 12}px`);
			})
			.on('mouseout', () => tooltip.style('opacity', 0));

		const drag = d3
			.drag<SVGCircleElement, SimNode>()
			.on('start', (e, d) => {
				if (!e.active) simulation.alphaTarget(0.3).restart();
				d.fx = d.x;
				d.fy = d.y;
			})
			.on('drag', (e, d) => {
				d.fx = e.x;
				d.fy = e.y;
			})
			.on('end', (e, d) => {
				if (!e.active) simulation.alphaTarget(0);
				d.fx = null;
				d.fy = null;
			});

		(node as d3.Selection<SVGCircleElement, SimNode, SVGGElement, unknown>).call(drag);

		const label = g
			.append('g')
			.selectAll('text')
			.data(nodes)
			.join('text')
			.text((d) => d.label)
			.attr('font-size', (d) => (d.type === 'phi' ? 13 : 10))
			.attr('font-family', "'SF Mono', monospace")
			.attr('fill', 'var(--text-muted)')
			.attr('text-anchor', 'middle')
			.attr('dy', (d) => RADII[d.type] + 14);

		simulation.on('tick', () => {
			link
				.attr('x1', (d) => (d.source as unknown as SimNode).x!)
				.attr('y1', (d) => (d.source as unknown as SimNode).y!)
				.attr('x2', (d) => (d.target as unknown as SimNode).x!)
				.attr('y2', (d) => (d.target as unknown as SimNode).y!);
			node.attr('cx', (d) => d.x!).attr('cy', (d) => d.y!);
			label.attr('x', (d) => d.x!).attr('y', (d) => d.y!);
		});
	}

	onMount(async () => {
		try {
			const data = await getMemoryGraph();
			loading = false;
			if (data.nodes.length === 0) return;
			const avatars = await fetchAvatars(data.nodes);
			render(data, avatars);
		} catch (e) {
			err = (e as Error).message;
			loading = false;
		}
	});
</script>

<div class="wrap" bind:this={container}>
	{#if loading}
		<div class="overlay faint">loading graph…</div>
	{:else if err}
		<div class="overlay faint">failed to load: {err}</div>
	{/if}
</div>

<style>
	.wrap {
		position: relative;
		width: 100%;
		height: 70vh;
		background: var(--bg);
		border: 1px solid var(--border);
		border-radius: 8px;
		overflow: hidden;
	}

	.overlay {
		position: absolute;
		inset: 0;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 13px;
	}

	:global(.tooltip) {
		position: absolute;
		padding: 8px 12px;
		background: var(--bg-elev);
		border: 1px solid var(--border);
		border-radius: 6px;
		font-size: 13px;
		pointer-events: none;
		opacity: 0;
		color: var(--text);
		max-width: 280px;
		z-index: 100;
	}
</style>

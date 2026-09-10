<script lang="ts">
	import type { Atlas } from '$lib/types';
	import { atlasPalette } from '$lib/atlas-palette';
	let { atlas, onclick }: { atlas: Atlas; onclick: () => void } = $props();

	const coordinates = $derived(
		atlas.points.flatMap((point) =>
			point.x !== undefined &&
			point.y !== undefined &&
			Number.isFinite(point.x) &&
			Number.isFinite(point.y)
				? [{ x: point.x, y: point.y, kind: point.kind ?? 'other' }]
				: [],
		),
	);
	const bounds = $derived({
		minX: Math.min(...coordinates.map((point) => point.x)),
		maxX: Math.max(...coordinates.map((point) => point.x)),
		minY: Math.min(...coordinates.map((point) => point.y)),
		maxY: Math.max(...coordinates.map((point) => point.y)),
	});
	const dots = $derived(
		coordinates
			.filter(
				(_, index) =>
					index % Math.max(1, Math.ceil(coordinates.length / 600)) === 0,
			)
			.map((point) => ({
				x:
					20 +
					((point.x - bounds.minX) /
						Math.max(0.001, bounds.maxX - bounds.minX)) *
						280,
				y:
					16 +
					((point.y - bounds.minY) /
						Math.max(0.001, bounds.maxY - bounds.minY)) *
						138,
				color: (atlasPalette[point.kind] ?? atlasPalette.other).core,
			})),
	);
</script>

<button class="atlas-preview" {onclick} aria-label="Explore memory atlas">
	{#if dots.length}
		<svg viewBox="0 0 320 170" aria-hidden="true">
			<path
				class="grid"
				d="M0 42H320M0 85H320M0 127H320M80 0V170M160 0V170M240 0V170"
			/>
			{#each dots as dot}<circle
					cx={dot.x}
					cy={dot.y}
					r="1.8"
					fill={dot.color}
				/>{/each}
		</svg>
	{:else}<span class="missing">Map preview unavailable</span>{/if}
	<span class="caption"
		><span
			><strong>{atlas.points.length.toLocaleString()}</strong> records
			<span class="groups">· {atlas.clusters_coarse.length} groups</span></span
		><span class="open" aria-hidden="true">↗</span></span
	>
</button>

<style>
	.atlas-preview {
		display: block;
		width: 100%;
		margin-top: 14px;
		padding: 0;
		border: 1px solid #426470;
		background: #08151c;
		color: #e3f0f1;
		box-shadow: inset 0 1px 0 #ffffff09;
		cursor: pointer;
		text-align: left;
		text-transform: none;
		letter-spacing: 0;
	}
	.atlas-preview:hover {
		border-color: #9cdae3;
		background: #0a1c26;
	}
	.atlas-preview:focus-visible {
		outline: 2px solid #a2e4ef;
		outline-offset: 4px;
	}
	svg {
		display: block;
		width: 100%;
		height: auto;
		max-height: 190px;
	}
	.grid {
		stroke: #7dbbcc;
		stroke-width: 0.5;
		opacity: 0.1;
		fill: none;
	}
	circle {
		opacity: 0.78;
	}
	.caption {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 8px;
		padding: 12px;
		border-top: 1px solid #243e4b;
		font: 12px var(--font-content);
	}
	strong {
		font: 22px var(--font-chrome);
		color: #d6f3f5;
		margin-right: 3px;
	}
	.groups {
		color: #9cbac7;
	}
	.open {
		font-size: 22px;
		color: #bce9ef;
	}
	.missing {
		display: block;
		padding: 32px 16px;
		font: 14px var(--font-content);
		color: #a9c1cb;
	}
</style>

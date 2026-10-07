<script lang="ts">
	import type { AtlasPreview } from '$lib/atlas-preview';
	import { atlasPalette } from '$lib/atlas-palette';
	let {
		preview,
		opening,
		onclick,
	}: { preview: AtlasPreview; opening: boolean; onclick: () => void } =
		$props();

	const dots = $derived(
		preview.dots.map(([x, y, kind]) => ({
			x: 20 + x * 280,
			y: 16 + y * 138,
			color: (atlasPalette[kind] ?? atlasPalette.other).core,
		})),
	);
</script>

<button
	class="atlas-preview"
	{onclick}
	disabled={opening}
	aria-label="Explore memory atlas"
>
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
			><strong>{preview.point_count.toLocaleString()}</strong> records in
			{preview.group_count} groups</span
		><span class="open">{opening ? 'Opening…' : 'Explore'}</span></span
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
	.open {
		font: 500 17px var(--font-chrome);
		color: #bce9ef;
	}
	.atlas-preview:disabled {
		cursor: progress;
	}
	.missing {
		display: block;
		padding: 32px 16px;
		font: 14px var(--font-content);
		color: #a9c1cb;
	}
</style>

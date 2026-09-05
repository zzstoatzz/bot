<script lang="ts">
	import { money, nearestObservation } from '$lib/chicken';
	let { series }: { series: [number, number][] } = $props();
	let selected = $state<number | null>(null);
	let dragging = false;
	const index = $derived(Math.min(selected ?? series.length - 1, series.length - 1));
	const point = $derived(series[index]);
	const chart = $derived.by(() => {
		const first = series[0],
			last = series[series.length - 1];
		if (!first || !last) return null;
		const low = Math.min(10_000_000, ...series.map((p) => p[1]));
		const high = Math.max(10_000_000, ...series.map((p) => p[1]));
		const spread = Math.max(high - low, 100_000);
		const y = (v: number) => 210 - ((v - low + spread * 0.15) / (spread * 1.3)) * 185;
		const x = (t: number) => 12 + ((t - first[0]) / Math.max(1, last[0] - first[0])) * 676;
		const coords = series.map(([t, v]) => `${x(t)},${y(v)}`).join(' ');
		return {
			first,
			last,
			x,
			y,
			line: coords,
			area: `12,230 ${coords} ${x(last[0])},230`,
			low,
			high,
			baseline: y(10_000_000)
		};
	});
	function date(ts: number, time = false) {
		return new Date(ts * 1000).toLocaleString(
			'en-US',
			time
				? {
						month: 'short',
						day: 'numeric',
						hour: 'numeric',
						minute: '2-digit',
						timeZoneName: 'short'
					}
				: { month: 'short', day: 'numeric' }
		);
	}
	function inspect(e: PointerEvent) {
		if (!chart || !(e.currentTarget instanceof HTMLElement)) return;
		const rect = e.currentTarget.getBoundingClientRect();
		const ratio = Math.max(
			0,
			Math.min(1, (((e.clientX - rect.left) / rect.width) * 700 - 12) / 676)
		);
		selected = nearestObservation(
			series,
			chart.first[0] + ratio * (chart.last[0] - chart.first[0])
		);
	}
	function down(e: PointerEvent) {
		if (e.button !== 0 || !(e.currentTarget instanceof HTMLElement)) return;
		dragging = true;
		e.currentTarget.setPointerCapture(e.pointerId);
		inspect(e);
	}
	function move(e: PointerEvent) {
		if (dragging || e.pointerType === 'mouse') inspect(e);
	}
	function up(e: PointerEvent) {
		dragging = false;
		if (e.currentTarget instanceof HTMLElement && e.currentTarget.hasPointerCapture(e.pointerId))
			e.currentTarget.releasePointerCapture(e.pointerId);
	}
	function key(e: KeyboardEvent) {
		const changes: Record<string, number> = {
			ArrowLeft: index - 1,
			ArrowDown: index - 1,
			ArrowRight: index + 1,
			ArrowUp: index + 1,
			Home: 0,
			End: series.length - 1
		};
		if (!(e.key in changes)) return;
		e.preventDefault();
		selected = Math.max(0, Math.min(series.length - 1, changes[e.key]));
	}
</script>

{#if chart && point}
	<div class="plot-readout">
		<strong>{money(point[1])}</strong><time datetime={new Date(point[0] * 1000).toISOString()}
			>{date(point[0], true)}</time
		>
	</div>
	<div
		class="plot"
		role="slider"
		tabindex="0"
		aria-label="Season net worth timeline"
		aria-orientation="horizontal"
		aria-valuemin="0"
		aria-valuemax={series.length - 1}
		aria-valuenow={index}
		aria-valuetext={`${date(point[0], true)}, ${money(point[1])}`}
		onpointerdown={down}
		onpointermove={move}
		onpointerup={up}
		onpointercancel={up}
		onkeydown={key}
	>
		<svg viewBox="0 0 700 240" preserveAspectRatio="none" aria-hidden="true">
			<defs
				><linearGradient id="market-fill" x1="0" y1="0" x2="0" y2="1"
					><stop offset="0%" stop-color="#7ec0d4" stop-opacity=".2" /><stop
						offset="100%"
						stop-color="#7ec0d4"
						stop-opacity="0"
					/></linearGradient
				></defs
			>
			{#each [12, 181, 350, 519, 688] as x}<line
					x1={x}
					x2={x}
					y1="12"
					y2="230"
					class="grid"
				/>{/each}
			{#each [35, 95, 155, 215] as y}<line x1="12" x2="688" y1={y} y2={y} class="grid" />{/each}
			<polygon points={chart.area} fill="url(#market-fill)" />
			<line x1="12" x2="688" y1={chart.baseline} y2={chart.baseline} class="baseline" />
			<polyline points={chart.line} class="trace-glow" /><polyline
				points={chart.line}
				class="trace"
			/>
			<line x1={chart.x(point[0])} x2={chart.x(point[0])} y1="12" y2="230" class="crosshair" />
			<line
				x1="12"
				x2="688"
				y1={chart.y(point[1])}
				y2={chart.y(point[1])}
				class="crosshair horizontal"
			/>
		</svg>
		<span
			class="reticle"
			style:left={`${chart.x(point[0]) / 7}%`}
			style:top={`${chart.y(point[1]) / 2.4}%`}
		></span>
		<span class="plot-ceiling">{money(chart.high)}</span>
	</div>
	<div class="plot-axis">
		<span>{date(chart.first[0])}</span><span>Drag to inspect</span><span>{date(chart.last[0])}</span
		>
	</div>
	<p class="plot-note">Dashed line: $1,000 season start. Focus the chart to use arrow keys.</p>
{:else}<p class="plot-note">No net-worth observations since this wallet reset.</p>{/if}

<style>
	.plot-readout {
		display: flex;
		flex-wrap: wrap;
		gap: 8px 18px;
		align-items: baseline;
		margin: 20px 0 10px;
	}
	.plot-readout strong {
		font: 400 23px var(--font-mono);
		color: var(--scan-hot);
	}
	.plot-readout time {
		font: 12px var(--font-mono);
		color: var(--text-mid);
	}
	.plot {
		position: relative;
		height: 240px;
		touch-action: pan-y;
		cursor: crosshair;
		outline: none;
		background: linear-gradient(180deg, rgba(24, 47, 58, 0.22), rgba(7, 14, 22, 0.28));
		border-block: 1px solid rgba(126, 192, 212, 0.22);
	}
	.plot:focus-visible {
		outline: 2px solid var(--scan-hot);
		outline-offset: 5px;
	}
	.plot svg {
		width: 100%;
		height: 100%;
		display: block;
		overflow: visible;
	}
	.grid {
		stroke: rgba(126, 192, 212, 0.11);
		stroke-width: 1;
		vector-effect: non-scaling-stroke;
	}
	.baseline {
		stroke: #a89779;
		stroke-dasharray: 3 5;
		stroke-width: 1;
		vector-effect: non-scaling-stroke;
	}
	.trace,
	.trace-glow {
		fill: none;
		stroke: #9cdeed;
		stroke-width: 2;
		stroke-linejoin: round;
		vector-effect: non-scaling-stroke;
	}
	.trace-glow {
		stroke: #7ec0d4;
		stroke-width: 7;
		opacity: 0.1;
	}
	.crosshair {
		stroke: #e9af7a;
		stroke-width: 1;
		opacity: 0.8;
		vector-effect: non-scaling-stroke;
	}
	.horizontal {
		opacity: 0.2;
		stroke-dasharray: 2 5;
	}
	.reticle {
		position: absolute;
		transform: translate(-50%, -50%);
		width: 10px;
		height: 10px;
		background: #eff9f6;
		border: 2px solid #15232c;
		box-shadow:
			0 0 0 1px #e9af7a,
			0 0 12px rgba(224, 144, 96, 0.45);
		pointer-events: none;
	}
	.plot-ceiling {
		position: absolute;
		top: 8px;
		right: 12px;
		font: 11px var(--font-mono);
		color: var(--text-mid);
		pointer-events: none;
	}
	.plot-axis {
		display: flex;
		justify-content: space-between;
		gap: 10px;
		margin-top: 12px;
		font: 12px var(--font-mono);
		color: var(--text-mid);
	}
	.plot-axis span:nth-child(2) {
		font: 14px var(--font-chrome);
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--scan-hot);
	}
	.plot-note {
		font-size: 12px;
		color: var(--text-dim);
		margin-top: 12px;
	}
	@media (max-width: 600px) {
		.plot {
			height: 200px;
		}
		.plot-readout strong {
			font-size: 21px;
		}
		.plot-readout time {
			font-size: 11px;
		}
	}
</style>

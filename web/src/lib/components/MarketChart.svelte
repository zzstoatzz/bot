<script lang="ts">
	import { money, nearestObservation, observationSegments } from '$lib/chicken';
	let {
		series,
		current,
		seasonStart
	}: { series: [number, number][]; current: [number, number] | null; seasonStart: number } =
		$props();
	let view = $state('season');
	const segments = $derived(observationSegments(series));
	const activity = $derived(segments.find((segment) => segment.length > 1) ?? series);
	const samples = $derived(
		view === 'history'
			? series.filter(([t]) => t >= (activity[0]?.[0] ?? seasonStart))
			: current
				? [...series, current]
				: series
	);
	let selected = $state<number | null>(null);
	let dragging = false;
	const index = $derived(Math.min(selected ?? samples.length - 1, samples.length - 1));
	const point = $derived(samples[index]);
	const chart = $derived.by(() => {
		const first = samples[0],
			last = samples[samples.length - 1];
		if (!first || !last) return null;
		const low = Math.min(10_000_000, ...samples.map((p) => p[1]));
		const high = Math.max(10_000_000, ...samples.map((p) => p[1]));
		const spread = Math.max(high - low, 100_000);
		const y = (v: number) => 210 - ((v - low + spread * 0.15) / (spread * 1.3)) * 185;
		const x = (t: number) => 12 + ((t - first[0]) / Math.max(1, last[0] - first[0])) * 676;
		const paths = observationSegments(samples).map((segment) => ({
			points: segment.map(([t, v]) => `${x(t)},${y(v)}`).join(' '),
			area: `${x(segment[0][0])},230 ${segment.map(([t, v]) => `${x(t)},${y(v)}`).join(' ')} ${x(segment[segment.length - 1][0])},230`
		}));
		const gaps = samples
			.slice(1)
			.flatMap((p, i) =>
				p[0] - samples[i][0] > 3600 ? [{ start: x(samples[i][0]), end: x(p[0]) }] : []
			);
		return {
			first,
			last,
			x,
			y,
			paths,
			gaps,
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
			samples,
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
			End: samples.length - 1
		};
		if (!(e.key in changes)) return;
		e.preventDefault();
		selected = Math.max(0, Math.min(samples.length - 1, changes[e.key]));
	}
</script>

<div class="chart-views" aria-label="Chart period">
	<button
		class:active={view === 'season'}
		onclick={() => {
			view = 'season';
			selected = null;
		}}>Season to today</button
	>
	<button
		class:active={view === 'history'}
		onclick={() => {
			view = 'history';
			selected = null;
		}}>Recorded activity</button
	>
</div>
{#if series.length}<p class="plot-note">
		Recorded history ends {date(series[series.length - 1][0], true)}. {#if current}Wallet checked {date(
				current[0],
				true
			)}.{/if}
	</p>{/if}
{#if chart && point}
	<div class="plot-readout">
		<strong>{money(point[1])}</strong><span class="point-label"
			>{current && point === current ? 'Current wallet' : 'Historical observation'}</span
		><time datetime={new Date(point[0] * 1000).toISOString()}>{date(point[0], true)}</time>
	</div>
	<div
		class="plot"
		role="slider"
		tabindex="0"
		aria-label="Season net worth timeline"
		aria-orientation="horizontal"
		aria-valuemin="0"
		aria-valuemax={samples.length - 1}
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
			{#each chart.gaps as gap}<rect
					x={gap.start}
					y="12"
					width={gap.end - gap.start}
					height="218"
					fill="#e9af7a"
					opacity=".045"
				/>{/each}
			{#each chart.paths as path}<polygon points={path.area} fill="url(#market-fill)" />{/each}
			<line x1="12" x2="688" y1={chart.baseline} y2={chart.baseline} class="baseline" />
			{#each chart.paths as path}<polyline points={path.points} class="trace-glow" /><polyline
					points={path.points}
					class="trace"
				/>{/each}
			{#each samples as sample}<circle
					cx={chart.x(sample[0])}
					cy={chart.y(sample[1])}
					r="1.5"
					fill="#9cdeed"
				/>{/each}
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
		{#each chart.gaps as gap}{#if gap.end - gap.start > 85}<span
					class="gap-label"
					style:left={`${(gap.start + gap.end) / 14}%`}>No observations</span
				>{/if}{/each}
		<span class="plot-ceiling">{money(chart.high)}</span>
	</div>
	<div class="plot-axis">
		<span>{date(chart.first[0])}</span><span>Drag to inspect</span><span>{date(chart.last[0])}</span
		>
	</div>
	<p class="plot-note">
		Gaps have no recorded observations; no value is inferred between them. Dashed line: $1,000
		starting balance. Arrow keys also inspect the chart.
	</p>
{:else}<p class="plot-note">No net-worth observations since this wallet reset.</p>{/if}

<style>
	.chart-views {
		display: flex;
		gap: 8px;
		margin-top: 16px;
		flex-wrap: wrap;
	}
	.chart-views button {
		min-height: 44px;
		padding: 8px 14px;
		font: 16px var(--font-chrome);
		text-transform: uppercase;
		letter-spacing: 0.04em;
		border: 1px solid var(--scan-hot);
		color: var(--text-mid);
		background: transparent;
	}
	.chart-views button.active {
		color: #eff9f6;
		background: #224450;
		box-shadow: inset 0 -2px var(--scan-hot);
	}
	.gap-label {
		position: absolute;
		top: 45%;
		transform: translateX(-50%);
		font: 12px var(--font-chrome);
		text-transform: uppercase;
		color: var(--text-mid);
		pointer-events: none;
		white-space: nowrap;
	}
	.point-label {
		font: 13px var(--font-chrome);
		text-transform: uppercase;
		color: var(--text-mid);
	}

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

<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { hudReadout, logbook } from '$lib/state.svelte';
	import { relativeWhen } from '$lib/time';
	import type { ActivityItem, BlogDoc, LogbookEntry } from '$lib/types';

	type Item = ActivityItem & { _kind: 'post' | 'note' | 'url' | 'blog'; _blogRef?: BlogDoc };

	interface Props {
		items: Item[];
	}

	let { items }: Props = $props();

	let canvas: HTMLCanvasElement;
	let dpr = 1;
	let W = 0,
		H = 0;
	let frameRequested = false;
	const view = $state({ z: 1, py: 0 });
	const minZoom = 0.5;
	const maxZoom = 4;

	const KIND_COLORS: Record<Item['_kind'], string> = {
		post: '--hud-mid',
		note: '--hud-hot',
		url: '--scan-mid',
		blog: '--warn'
	};

	type Placed = Item & { sx: number; sy: number; r: number };
	let placed = $state<Placed[]>([]);
	let hovered = $state<Placed | null>(null);

	function resolveColor(name: string): string {
		return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || '#888';
	}

	function place() {
		if (!items.length || W === 0 || H === 0) {
			placed = [];
			return;
		}
		// time spiral: t goes from now → past as you spiral outward
		// each item gets a position on the spiral; angle = phase, radius = age
		const now = Date.now();
		const padded: Placed[] = [];
		const margin = 80;
		const innerR = 40;
		const maxAge = items.reduce((acc, it) => {
			const t = new Date(it.time).getTime();
			return Math.max(acc, isNaN(t) ? 0 : now - t);
		}, 0);
		const safeMaxAge = Math.max(maxAge, 1);
		const cx = W / 2;
		const cy = H / 2 + view.py;
		const maxR = Math.min(W, H) / 2 - margin;
		const turns = 2.6; // total spiral revolutions across the dataset

		for (let i = 0; i < items.length; i++) {
			const it = items[i];
			const t = new Date(it.time).getTime();
			const age = isNaN(t) ? safeMaxAge : now - t;
			const ageNorm = age / safeMaxAge; // 0..1
			const r = innerR + ageNorm * (maxR - innerR) * view.z;
			const angle = ageNorm * turns * Math.PI * 2 - Math.PI / 2; // start at top
			const sx = cx + Math.cos(angle) * r;
			const sy = cy + Math.sin(angle) * r;
			const radius = it._kind === 'blog' ? 6 : 4;
			padded.push({ ...it, sx, sy, r: radius });
		}
		placed = padded;
	}

	function scheduleFrame() {
		if (!frameRequested) {
			frameRequested = true;
			requestAnimationFrame(draw);
		}
	}

	function draw() {
		frameRequested = false;
		if (!canvas) return;
		const ctx = canvas.getContext('2d');
		if (!ctx) return;

		ctx.save();
		ctx.scale(dpr, dpr);
		ctx.clearRect(0, 0, W, H);

		// faint spiral guide
		drawSpiralGuide(ctx);

		// connection trail along time
		ctx.lineWidth = 1;
		ctx.strokeStyle = resolveColor('--line-dim');
		ctx.beginPath();
		for (let i = 0; i < placed.length; i++) {
			const p = placed[i];
			if (i === 0) ctx.moveTo(p.sx, p.sy);
			else ctx.lineTo(p.sx, p.sy);
		}
		ctx.stroke();

		// points
		for (const p of placed) {
			const color = resolveColor(KIND_COLORS[p._kind]);
			ctx.beginPath();
			ctx.arc(p.sx, p.sy, p.r, 0, Math.PI * 2);
			ctx.fillStyle = color;
			ctx.globalAlpha = 0.9;
			ctx.fill();
			ctx.globalAlpha = 1;

			// glow on hover
			if (hovered === p) {
				ctx.beginPath();
				ctx.arc(p.sx, p.sy, p.r * 2.5, 0, Math.PI * 2);
				const grd = ctx.createRadialGradient(p.sx, p.sy, p.r, p.sx, p.sy, p.r * 2.5);
				grd.addColorStop(0, color);
				grd.addColorStop(1, 'rgba(0,0,0,0)');
				ctx.fillStyle = grd;
				ctx.globalAlpha = 0.4;
				ctx.fill();
				ctx.globalAlpha = 1;
				drawReticle(ctx, p.sx, p.sy, p.r + 5);
			}
		}

		ctx.restore();
	}

	function drawSpiralGuide(ctx: CanvasRenderingContext2D) {
		ctx.strokeStyle = resolveColor('--grid');
		ctx.lineWidth = 1;
		const cx = W / 2;
		const cy = H / 2 + view.py;
		const innerR = 40;
		const margin = 80;
		const maxR = Math.min(W, H) / 2 - margin;
		const turns = 2.6;
		const steps = 200;
		ctx.beginPath();
		for (let i = 0; i <= steps; i++) {
			const t = i / steps;
			const r = innerR + t * (maxR - innerR) * view.z;
			const angle = t * turns * Math.PI * 2 - Math.PI / 2;
			const x = cx + Math.cos(angle) * r;
			const y = cy + Math.sin(angle) * r;
			if (i === 0) ctx.moveTo(x, y);
			else ctx.lineTo(x, y);
		}
		ctx.stroke();
		// center marker (now)
		ctx.fillStyle = resolveColor('--hud-hot');
		ctx.beginPath();
		ctx.arc(cx, cy, 3, 0, Math.PI * 2);
		ctx.fill();
		ctx.font = '9px "Saira Condensed", sans-serif';
		ctx.fillStyle = resolveColor('--text-dim');
		ctx.textAlign = 'center';
		ctx.fillText('NOW', cx, cy - 12);
	}

	function drawReticle(ctx: CanvasRenderingContext2D, cx: number, cy: number, r: number) {
		ctx.lineWidth = 1.2;
		ctx.strokeStyle = resolveColor('--hud-hot');
		const arm = 5;
		for (const [sx, sy] of [
			[-1, -1],
			[1, -1],
			[-1, 1],
			[1, 1]
		]) {
			const x = cx + sx * r;
			const y = cy + sy * r;
			ctx.beginPath();
			ctx.moveTo(x, y - sy * arm);
			ctx.lineTo(x, y);
			ctx.lineTo(x - sx * arm, y);
			ctx.stroke();
		}
	}

	function entryFor(p: Placed): LogbookEntry {
		if (p._kind === 'blog' && p._blogRef) return { kind: 'blog', doc: p._blogRef };
		return { kind: 'activity', item: p };
	}

	function readoutFor(p: Placed): string {
		const k = p._kind.toUpperCase();
		const age = relativeWhen(p.time);
		const text = (p.title ?? p.text ?? '').slice(0, 60);
		return `${k} · ${age} · ${text}`;
	}

	function pointAt(mx: number, my: number): Placed | null {
		let best: Placed | null = null;
		let bestD = Infinity;
		for (const p of placed) {
			const dx = mx - p.sx;
			const dy = my - p.sy;
			const d2 = dx * dx + dy * dy;
			if (d2 < (p.r + 8) * (p.r + 8) && d2 < bestD) {
				bestD = d2;
				best = p;
			}
		}
		return best;
	}

	// Pointer events: mouse hover + wheel; touch single-tap-to-open + pinch-zoom.
	const activePointers = new Map<number, { x: number; y: number }>();
	let panStartX = 0,
		panStartY = 0;
	let pinchStartDist = 0;
	let pinchStartZoom = 1;
	let pinching = false;
	const TAP_THRESHOLD = 8;

	function onPointerDown(e: PointerEvent) {
		canvas.setPointerCapture(e.pointerId);
		activePointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
		if (activePointers.size === 1) {
			panStartX = e.clientX;
			panStartY = e.clientY;
			pinching = false;
		} else if (activePointers.size === 2) {
			pinching = true;
			const [a, b] = [...activePointers.values()];
			pinchStartDist = Math.hypot(b.x - a.x, b.y - a.y);
			pinchStartZoom = view.z;
		}
	}

	function onPointerMove(e: PointerEvent) {
		const rect = canvas.getBoundingClientRect();
		const mx = e.clientX - rect.left;
		const my = e.clientY - rect.top;

		if (activePointers.has(e.pointerId)) {
			activePointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
		}

		if (pinching && activePointers.size >= 2) {
			const [a, b] = [...activePointers.values()];
			const dist = Math.hypot(b.x - a.x, b.y - a.y);
			if (pinchStartDist > 0) {
				view.z = Math.max(minZoom, Math.min(maxZoom, pinchStartZoom * (dist / pinchStartDist)));
				place();
				scheduleFrame();
			}
			return;
		}

		if (e.pointerType === 'mouse' && activePointers.size === 0) {
			const p = pointAt(mx, my);
			if (p !== hovered) {
				hovered = p;
				hudReadout.set(p ? readoutFor(p) : '');
				canvas.style.cursor = p ? 'pointer' : 'default';
				scheduleFrame();
			}
		}
	}

	function onPointerUp(e: PointerEvent) {
		const wasTap =
			Math.abs(e.clientX - panStartX) < TAP_THRESHOLD &&
			Math.abs(e.clientY - panStartY) < TAP_THRESHOLD &&
			!pinching;

		activePointers.delete(e.pointerId);
		try {
			canvas.releasePointerCapture(e.pointerId);
		} catch {
			/* may not have capture */
		}

		if (activePointers.size < 2) pinching = false;

		if (activePointers.size === 0 && wasTap && e.pointerType !== 'mouse') {
			const rect = canvas.getBoundingClientRect();
			const p = pointAt(e.clientX - rect.left, e.clientY - rect.top);
			if (p) logbook.set(entryFor(p));
		}
	}

	function onClick(e: MouseEvent) {
		if ((e as PointerEvent).pointerType && (e as PointerEvent).pointerType !== 'mouse') return;
		const rect = canvas.getBoundingClientRect();
		const p = pointAt(e.clientX - rect.left, e.clientY - rect.top);
		if (p) logbook.set(entryFor(p));
	}

	function onWheel(e: WheelEvent) {
		e.preventDefault();
		const factor = Math.exp(-e.deltaY * 0.0015);
		view.z = Math.max(minZoom, Math.min(maxZoom, view.z * factor));
		place();
		scheduleFrame();
	}

	function resize() {
		if (!canvas) return;
		const rect = canvas.parentElement!.getBoundingClientRect();
		W = rect.width;
		H = rect.height;
		dpr = window.devicePixelRatio || 1;
		canvas.width = W * dpr;
		canvas.height = H * dpr;
		canvas.style.width = `${W}px`;
		canvas.style.height = `${H}px`;
		place();
		scheduleFrame();
	}

	let ro: ResizeObserver | null = null;
	onMount(() => {
		resize();
		ro = new ResizeObserver(resize);
		if (canvas?.parentElement) ro.observe(canvas.parentElement);
	});

	onDestroy(() => {
		ro?.disconnect();
		hudReadout.set('');
	});

	$effect(() => {
		// re-place when items change
		if (W > 0 && items) place();
		scheduleFrame();
	});
</script>

<div class="host">
	<canvas
		bind:this={canvas}
		onpointerdown={onPointerDown}
		onpointermove={onPointerMove}
		onpointerup={onPointerUp}
		onpointercancel={onPointerUp}
		onpointerleave={() => {
			hovered = null;
			hudReadout.set('');
			scheduleFrame();
		}}
		onclick={onClick}
		onwheel={onWheel}
	></canvas>
</div>

<style>
	.host {
		position: absolute;
		inset: 0;
	}

	canvas {
		display: block;
		touch-action: none;
	}
</style>

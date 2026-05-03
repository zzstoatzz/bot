<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { hudReadout, logbook } from '$lib/state.svelte';
	import type { AtlasPoint, LogbookEntry } from '$lib/types';

	interface Props {
		points: AtlasPoint[];
		// optional: edges to render between points (e.g. phi -> handles)
		edges?: { source: string; target: string }[];
		// callback that turns a point into a logbook entry on click
		entryFor: (p: AtlasPoint) => LogbookEntry;
	}

	let { points, edges = [], entryFor }: Props = $props();

	let canvas: HTMLCanvasElement;
	let dpr = 1;
	let W = 0,
		H = 0;

	// view state — pan + zoom in screen space
	const view = $state({ z: 1, px: 0, py: 0 });
	const minZoom = 0.4;
	const maxZoom = 8;

	// kind → color mapping (resolved at render time from CSS vars)
	const KIND_COLORS: Record<string, string> = {
		phi: '--hud-hot',
		'handle-engaged': '--text',
		'handle-candidate': '--text-dim',
		observation: '--scan-mid',
		goal: '--warn'
	};

	// avatar cache — patternId-style images, but using offscreen canvas blits
	const avatarCache = new Map<string, HTMLImageElement>();
	const avatarLoading = new Set<string>();
	const avatarFailed = new Set<string>();

	function loadAvatar(p: AtlasPoint) {
		if (!p.avatar) return;
		const key = p.id;
		if (avatarCache.has(key) || avatarLoading.has(key) || avatarFailed.has(key)) return;
		avatarLoading.add(key);
		const img = new Image();
		// Note: not setting crossOrigin — bsky CDN doesn't send Access-Control-Allow-Origin,
		// so anonymous requests are blocked. Leaving it unset lets the browser fetch and
		// drawImage anyway; we just can't getImageData() (which we don't need).
		img.onload = () => {
			avatarCache.set(key, img);
			avatarLoading.delete(key);
			scheduleFrame();
		};
		img.onerror = () => {
			avatarFailed.add(key);
			avatarLoading.delete(key);
		};
		img.src = p.avatar;
	}

	let frameRequested = false;
	function scheduleFrame() {
		if (!frameRequested) {
			frameRequested = true;
			requestAnimationFrame(draw);
		}
	}

	// transform: normalized point.x/y in [-1,1] → screen pixels
	function worldToScreen(x: number, y: number): [number, number] {
		const scale = Math.min(W, H) * 0.42 * view.z;
		return [W / 2 + x * scale + view.px, H / 2 + y * scale + view.py];
	}

	function resolveColor(name: string): string {
		const root = document.documentElement;
		return getComputedStyle(root).getPropertyValue(name).trim() || '#888';
	}

	let hovered = $state<AtlasPoint | null>(null);

	function pointAt(mx: number, my: number): AtlasPoint | null {
		// reverse: pick the point closest to (mx,my) within radius
		let best: AtlasPoint | null = null;
		let bestDist = Infinity;
		for (const p of points) {
			const [sx, sy] = worldToScreen(p.x, p.y);
			const r = radiusFor(p);
			const dx = sx - mx;
			const dy = sy - my;
			const d2 = dx * dx + dy * dy;
			if (d2 < r * r * 1.6 && d2 < bestDist) {
				bestDist = d2;
				best = p;
			}
		}
		return best;
	}

	function radiusFor(p: AtlasPoint): number {
		// phi is largest, then engaged handles, then candidates, then concepts
		const base =
			p.kind === 'phi' ? 14 : p.kind === 'handle-engaged' ? 10 : p.kind === 'handle-candidate' ? 7 : 6;
		return base * Math.max(0.7, Math.min(1.6, view.z));
	}

	function fadeIn(z: number, start: number, range: number) {
		return Math.max(0, Math.min(1, (z - start) / range));
	}

	function draw() {
		frameRequested = false;
		if (!canvas) return;
		const ctx = canvas.getContext('2d');
		if (!ctx) return;

		ctx.save();
		ctx.scale(dpr, dpr);
		ctx.clearRect(0, 0, W, H);

		// faint grid — subtle scan-visor reference
		drawGrid(ctx);

		// edges
		ctx.lineWidth = 1;
		ctx.strokeStyle = resolveColor('--line-dim');
		const idIndex = new Map(points.map((p) => [p.id, p]));
		for (const e of edges) {
			const a = idIndex.get(e.source);
			const b = idIndex.get(e.target);
			if (!a || !b) continue;
			const [ax, ay] = worldToScreen(a.x, a.y);
			const [bx, by] = worldToScreen(b.x, b.y);
			ctx.beginPath();
			ctx.moveTo(ax, ay);
			ctx.lineTo(bx, by);
			ctx.stroke();
		}

		// points
		for (const p of points) {
			const [sx, sy] = worldToScreen(p.x, p.y);
			const r = radiusFor(p);
			const colorVar = KIND_COLORS[p.kind] ?? '--text-dim';
			const color = resolveColor(colorVar);

			const img = avatarCache.get(p.id);
			if (img && p.kind !== 'handle-candidate') {
				// engaged handles get avatar fill
				ctx.save();
				ctx.beginPath();
				ctx.arc(sx, sy, r, 0, Math.PI * 2);
				ctx.clip();
				ctx.drawImage(img, sx - r, sy - r, r * 2, r * 2);
				ctx.restore();
				ctx.lineWidth = 1.5;
				ctx.strokeStyle = color;
				ctx.beginPath();
				ctx.arc(sx, sy, r, 0, Math.PI * 2);
				ctx.stroke();
			} else if (p.kind === 'handle-candidate') {
				// candidates: dim outline only, ghosted
				ctx.lineWidth = 1;
				ctx.strokeStyle = color;
				ctx.setLineDash([2, 2]);
				ctx.beginPath();
				ctx.arc(sx, sy, r, 0, Math.PI * 2);
				ctx.stroke();
				ctx.setLineDash([]);
			} else if (p.kind === 'phi') {
				// phi: filled ring with glow
				ctx.beginPath();
				ctx.arc(sx, sy, r * 1.6, 0, Math.PI * 2);
				const grd = ctx.createRadialGradient(sx, sy, r * 0.4, sx, sy, r * 1.6);
				grd.addColorStop(0, color);
				grd.addColorStop(1, 'rgba(184,107,58,0)');
				ctx.fillStyle = grd;
				ctx.fill();
				ctx.beginPath();
				ctx.arc(sx, sy, r, 0, Math.PI * 2);
				ctx.fillStyle = color;
				ctx.fill();
			} else {
				// observations + goals: small filled dots
				ctx.beginPath();
				ctx.arc(sx, sy, r, 0, Math.PI * 2);
				ctx.fillStyle = color;
				ctx.globalAlpha = 0.85;
				ctx.fill();
				ctx.globalAlpha = 1;
			}
		}

		// labels — fade in at zoom >= 0.9
		const labelAlpha = fadeIn(view.z, 0.9, 0.5);
		if (labelAlpha > 0.01) {
			ctx.font = '10px "JetBrains Mono", monospace';
			ctx.textAlign = 'center';
			ctx.textBaseline = 'top';
			for (const p of points) {
				const [sx, sy] = worldToScreen(p.x, p.y);
				const r = radiusFor(p);
				const label = labelFor(p);
				if (!label) continue;
				ctx.fillStyle = resolveColor('--text-mid');
				ctx.globalAlpha = labelAlpha * (p.kind === 'phi' ? 1 : p.kind === 'handle-engaged' ? 0.9 : 0.5);
				ctx.fillText(label, sx, sy + r + 6);
			}
			ctx.globalAlpha = 1;
		}

		// reticle on hovered point
		if (hovered) {
			const [hx, hy] = worldToScreen(hovered.x, hovered.y);
			drawReticle(ctx, hx, hy, radiusFor(hovered) + 4);
		}

		ctx.restore();
	}

	function labelFor(p: AtlasPoint): string {
		if (p.kind === 'phi') return 'phi';
		if (p.kind === 'handle-engaged' || p.kind === 'handle-candidate') return p.label;
		// observations + goals: don't label by default — too noisy. Only when zoomed in further.
		if (view.z >= 1.6) return p.label.length > 32 ? p.label.slice(0, 32) + '…' : p.label;
		return '';
	}

	function drawReticle(ctx: CanvasRenderingContext2D, cx: number, cy: number, r: number) {
		ctx.lineWidth = 1.2;
		ctx.strokeStyle = resolveColor('--hud-hot');
		const arm = 6;
		// four corners
		const corners = [
			[-1, -1],
			[1, -1],
			[-1, 1],
			[1, 1]
		];
		for (const [sx, sy] of corners) {
			const x = cx + sx * r;
			const y = cy + sy * r;
			ctx.beginPath();
			ctx.moveTo(x, y - sy * arm);
			ctx.lineTo(x, y);
			ctx.lineTo(x - sx * arm, y);
			ctx.stroke();
		}
	}

	function drawGrid(ctx: CanvasRenderingContext2D) {
		// concentric circles around center, scaled to zoom — scaffolding only
		ctx.strokeStyle = resolveColor('--grid');
		ctx.lineWidth = 1;
		const cx = W / 2 + view.px;
		const cy = H / 2 + view.py;
		const baseR = Math.min(W, H) * 0.18 * view.z;
		for (let i = 1; i <= 4; i++) {
			ctx.beginPath();
			ctx.arc(cx, cy, baseR * i, 0, Math.PI * 2);
			ctx.stroke();
		}
		// crosshairs
		ctx.beginPath();
		ctx.moveTo(cx - W, cy);
		ctx.lineTo(cx + W, cy);
		ctx.moveTo(cx, cy - H);
		ctx.lineTo(cx, cy + H);
		ctx.stroke();
	}

	// --- input ---
	// Pointer events: support mouse (hover + wheel + click) and touch
	// (single-finger pan, two-finger pinch zoom, tap to open logbook).
	// Hover/readout is mouse-only — touch users get tap-opens-logbook.

	const activePointers = new Map<number, { x: number; y: number; type: string }>();
	let dragging = false;
	let lastX = 0,
		lastY = 0;
	let panStartX = 0,
		panStartY = 0;
	let pinchStartDist = 0;
	let pinchStartZoom = 1;
	let pinchCx = 0,
		pinchCy = 0;
	let pinching = false;
	const TAP_THRESHOLD = 8; // px movement allowed for a tap

	function applyZoomAt(mx: number, my: number, newZ: number) {
		newZ = Math.max(minZoom, Math.min(maxZoom, newZ));
		const ratio = newZ / view.z;
		view.px = mx - (mx - W / 2 - view.px) * ratio - W / 2;
		view.py = my - (my - H / 2 - view.py) * ratio - H / 2;
		view.z = newZ;
	}

	function onPointerDown(e: PointerEvent) {
		canvas.setPointerCapture(e.pointerId);
		activePointers.set(e.pointerId, { x: e.clientX, y: e.clientY, type: e.pointerType });

		if (activePointers.size === 1) {
			dragging = true;
			pinching = false;
			lastX = e.clientX;
			lastY = e.clientY;
			panStartX = e.clientX;
			panStartY = e.clientY;
		} else if (activePointers.size === 2) {
			pinching = true;
			dragging = false;
			const [a, b] = [...activePointers.values()];
			pinchStartDist = Math.hypot(b.x - a.x, b.y - a.y);
			pinchStartZoom = view.z;
			const rect = canvas.getBoundingClientRect();
			pinchCx = (a.x + b.x) / 2 - rect.left;
			pinchCy = (a.y + b.y) / 2 - rect.top;
		}
	}

	function onPointerMove(e: PointerEvent) {
		const rect = canvas.getBoundingClientRect();
		const mx = e.clientX - rect.left;
		const my = e.clientY - rect.top;

		if (activePointers.has(e.pointerId)) {
			activePointers.set(e.pointerId, { x: e.clientX, y: e.clientY, type: e.pointerType });
		}

		if (pinching && activePointers.size >= 2) {
			const [a, b] = [...activePointers.values()];
			const dist = Math.hypot(b.x - a.x, b.y - a.y);
			if (pinchStartDist > 0) {
				applyZoomAt(pinchCx, pinchCy, pinchStartZoom * (dist / pinchStartDist));
				scheduleFrame();
			}
			return;
		}

		if (dragging) {
			view.px += e.clientX - lastX;
			view.py += e.clientY - lastY;
			lastX = e.clientX;
			lastY = e.clientY;
			scheduleFrame();
			return;
		}

		// hover (mouse only — touch fingers without buttons aren't here)
		if (e.pointerType === 'mouse') {
			const p = pointAt(mx, my);
			if (p !== hovered) {
				hovered = p;
				hudReadout.set(p ? readoutFor(p) : '');
				canvas.style.cursor = p ? 'pointer' : 'grab';
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

		if (activePointers.size === 0) {
			dragging = false;
			pinching = false;
			// touch tap → open logbook (mouse uses onClick separately)
			if (wasTap && e.pointerType !== 'mouse') {
				const rect = canvas.getBoundingClientRect();
				const p = pointAt(e.clientX - rect.left, e.clientY - rect.top);
				if (p) logbook.set(entryFor(p));
			}
		} else if (activePointers.size === 1) {
			pinching = false;
			const [first] = [...activePointers.values()];
			lastX = first.x;
			lastY = first.y;
			panStartX = first.x;
			panStartY = first.y;
			dragging = true;
		}
	}

	function onClick(e: MouseEvent) {
		// mouse-only — touch handled in onPointerUp
		if ((e as PointerEvent).pointerType && (e as PointerEvent).pointerType !== 'mouse') return;
		const rect = canvas.getBoundingClientRect();
		const p = pointAt(e.clientX - rect.left, e.clientY - rect.top);
		if (p) logbook.set(entryFor(p));
	}

	function onWheel(e: WheelEvent) {
		e.preventDefault();
		const rect = canvas.getBoundingClientRect();
		applyZoomAt(e.clientX - rect.left, e.clientY - rect.top, view.z * Math.exp(-e.deltaY * 0.0015));
		scheduleFrame();
	}

	function readoutFor(p: AtlasPoint): string {
		const kindLabels: Record<string, string> = {
			phi: 'self',
			'handle-engaged': 'in memory',
			'handle-candidate': 'on radar',
			observation: 'attention',
			goal: 'goal'
		};
		return `${kindLabels[p.kind]} · ${p.label}`;
	}

	// --- resize ---

	let ro: ResizeObserver | null = null;
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
		scheduleFrame();
	}

	onMount(() => {
		resize();
		ro = new ResizeObserver(resize);
		if (canvas?.parentElement) ro.observe(canvas.parentElement);
		// preload avatars
		for (const p of points) loadAvatar(p);
		scheduleFrame();
	});

	onDestroy(() => {
		ro?.disconnect();
		hudReadout.set('');
	});

	// reload avatars when points change
	$effect(() => {
		for (const p of points) loadAvatar(p);
		scheduleFrame();
	});
</script>

<div class="atlas-host">
	<canvas
		bind:this={canvas}
		onpointerdown={onPointerDown}
		onpointermove={onPointerMove}
		onpointerup={onPointerUp}
		onpointercancel={onPointerUp}
		onpointerleave={() => {
			hovered = null;
			hudReadout.set('');
			canvas.style.cursor = 'grab';
			scheduleFrame();
		}}
		onclick={onClick}
		onwheel={onWheel}
	></canvas>
</div>

<style>
	.atlas-host {
		position: absolute;
		inset: 0;
	}

	canvas {
		display: block;
		cursor: grab;
		touch-action: none;
	}
</style>

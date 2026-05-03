<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { hudReadout, logbook } from '$lib/state.svelte';
	import type {
		AtlasPoint,
		LogbookEntry,
		Goal,
		Observation,
		DiscoveryEntry,
		GraphNode
	} from '$lib/types';
	import { PHI_HANDLE } from '$lib/api';
	import { relativeWhen } from '$lib/time';

	/**
	 * Phi-centric concentric rings:
	 *   0.18 — anchors (goals)
	 *   0.32 — attention (active observations)
	 *   0.55 — memory (people phi has notes about)
	 *   0.85 — horizon (people on phi's radar via discovery)
	 *
	 * Phi is fixed at center. Each ring is drawn as a faint orange circle
	 * with a chrome tick + label at 12 o'clock so the structure is legible.
	 * Items snap to their ring radius. Angular position has meaning per ring
	 * (see place()).
	 */

	interface Props {
		goals: Goal[];
		observations: Observation[];
		known: GraphNode[]; // user-type nodes from /api/memory/graph (we use only their (x,y) to derive angle)
		candidates: DiscoveryEntry[];
		avatars: Record<string, string>;
	}

	let { goals, observations, known, candidates, avatars }: Props = $props();

	let canvas: HTMLCanvasElement;
	let dpr = 1;
	let W = 0,
		H = 0;

	const RING = {
		anchors: 0.18,
		attention: 0.32,
		memory: 0.55,
		horizon: 0.85
	} as const;

	const RING_LABELS: { r: number; label: string }[] = [
		{ r: RING.anchors, label: 'anchors' },
		{ r: RING.attention, label: 'attention' },
		{ r: RING.memory, label: 'in memory' },
		{ r: RING.horizon, label: 'on the horizon' }
	];

	// hover/select state
	let hovered = $state<AtlasPoint | null>(null);

	// avatar image cache
	const imageCache = new Map<string, HTMLImageElement>();
	const imageLoading = new Set<string>();
	const imageFailed = new Set<string>();

	function loadImage(url: string) {
		if (imageCache.has(url) || imageLoading.has(url) || imageFailed.has(url)) return;
		imageLoading.add(url);
		const img = new Image();
		img.onload = () => {
			imageCache.set(url, img);
			imageLoading.delete(url);
			scheduleFrame();
		};
		img.onerror = () => {
			imageFailed.add(url);
			imageLoading.delete(url);
		};
		img.src = url;
	}

	// Compute placed points each time data changes.
	let points = $state<AtlasPoint[]>([]);

	function place(): AtlasPoint[] {
		const out: AtlasPoint[] = [];

		// phi at center
		out.push({
			id: 'phi',
			kind: 'phi',
			label: 'phi',
			x: 0,
			y: 0,
			avatar: avatars[PHI_HANDLE] ?? null,
			payload: {}
		});

		// goals — sort by created_at ascending so older anchors are stable; even angular distribution
		const sortedGoals = [...goals].sort((a, b) => a.created_at.localeCompare(b.created_at));
		for (let i = 0; i < sortedGoals.length; i++) {
			const g = sortedGoals[i];
			const angle = (-Math.PI / 2) + (i / Math.max(sortedGoals.length, 1)) * Math.PI * 2;
			out.push({
				id: `goal-${g.rkey}`,
				kind: 'goal',
				label: g.title,
				x: Math.cos(angle) * RING.anchors,
				y: Math.sin(angle) * RING.anchors,
				payload: g
			});
		}

		// observations — same idea, by rkey order (TID-sortable, so chronological)
		const sortedObs = [...observations].sort((a, b) => a.rkey.localeCompare(b.rkey));
		for (let i = 0; i < sortedObs.length; i++) {
			const o = sortedObs[i];
			const angle = (-Math.PI / 2) + (i / Math.max(sortedObs.length, 1)) * Math.PI * 2;
			out.push({
				id: `obs-${o.rkey}`,
				kind: 'observation',
				label: o.content,
				x: Math.cos(angle) * RING.attention,
				y: Math.sin(angle) * RING.attention,
				payload: o
			});
		}

		// known people — preserve angular hint from graph embedding (x,y → angle), snap to ring radius
		const knownEntries = known.filter((n) => n.type === 'user');
		for (const n of knownEntries) {
			const handle = n.label.replace(/^@/, '');
			const angle = n.x != null && n.y != null && (n.x !== 0 || n.y !== 0)
				? Math.atan2(n.y, n.x)
				: hashAngle(handle);
			out.push({
				id: n.id,
				kind: 'handle-engaged',
				label: n.label,
				x: Math.cos(angle) * RING.memory,
				y: Math.sin(angle) * RING.memory,
				avatar: avatars[handle] ?? null,
				payload: { handle }
			});
		}

		// candidates — angular position by recency (most recent at top, clockwise)
		const sortedCands = [...candidates].sort(
			(a, b) => b.last_liked_at.localeCompare(a.last_liked_at)
		);
		const knownHandles = new Set(
			knownEntries.map((n) => n.label.replace(/^@/, ''))
		);
		const filteredCands = sortedCands.filter((c) => !knownHandles.has(c.handle));
		for (let i = 0; i < filteredCands.length; i++) {
			const c = filteredCands[i];
			const angle = (-Math.PI / 2) + (i / Math.max(filteredCands.length, 1)) * Math.PI * 2;
			out.push({
				id: `cand-${c.did}`,
				kind: 'handle-candidate',
				label: `@${c.handle}`,
				x: Math.cos(angle) * RING.horizon,
				y: Math.sin(angle) * RING.horizon,
				avatar: avatars[c.handle] ?? null,
				payload: { handle: c.handle, did: c.did, entry: c }
			});
		}

		return out;
	}

	// Stable hash for angle when graph embedding has no info.
	function hashAngle(s: string): number {
		let h = 2166136261;
		for (let i = 0; i < s.length; i++) {
			h ^= s.charCodeAt(i);
			h = Math.imul(h, 16777619);
		}
		return ((h >>> 0) % 10000) / 10000 * Math.PI * 2;
	}

	$effect(() => {
		// reactive on inputs — read into a local first so we don't re-read
		// `points` (which we just wrote) and trigger Svelte's depth check.
		void goals;
		void observations;
		void known;
		void candidates;
		void avatars;
		const placed = place();
		for (const p of placed) if (p.avatar) loadImage(p.avatar);
		points = placed;
		scheduleFrame();
	});

	// ---- coordinate / draw ----

	function unit(): number {
		return Math.min(W, H) * 0.42;
	}

	function worldToScreen(x: number, y: number): [number, number] {
		const u = unit();
		return [W / 2 + x * u, H / 2 + y * u];
	}

	function resolve(name: string): string {
		return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || '#888';
	}

	function radiusFor(p: AtlasPoint): number {
		if (p.kind === 'phi') return 26;
		if (p.kind === 'handle-engaged') return 11;
		if (p.kind === 'handle-candidate') return 5;
		if (p.kind === 'goal') return 7;
		if (p.kind === 'observation') return 5;
		return 5;
	}

	let frameRequested = false;
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

		drawRings(ctx);
		drawAnchorSpokes(ctx);
		drawPoints(ctx);
		drawRingLabels(ctx);
		if (hovered) drawReticle(ctx, hovered);

		ctx.restore();
	}

	function drawRings(ctx: CanvasRenderingContext2D) {
		const u = unit();
		const cx = W / 2,
			cy = H / 2;
		ctx.strokeStyle = resolve('--grid');
		ctx.lineWidth = 1;
		for (const { r } of RING_LABELS) {
			ctx.beginPath();
			ctx.arc(cx, cy, r * u, 0, Math.PI * 2);
			ctx.stroke();
		}
		// faint axes
		ctx.beginPath();
		ctx.moveTo(cx - W, cy);
		ctx.lineTo(cx + W, cy);
		ctx.moveTo(cx, cy - H);
		ctx.lineTo(cx, cy + H);
		ctx.stroke();
	}

	function drawRingLabels(ctx: CanvasRenderingContext2D) {
		const u = unit();
		const cx = W / 2,
			cy = H / 2;
		ctx.font = '9px "Saira Condensed", sans-serif';
		ctx.textAlign = 'left';
		ctx.textBaseline = 'middle';
		for (const { r, label } of RING_LABELS) {
			const y = cy - r * u;
			// short tick + dash
			ctx.strokeStyle = resolve('--hud-mid');
			ctx.lineWidth = 1;
			ctx.beginPath();
			ctx.moveTo(cx - 4, y);
			ctx.lineTo(cx + 4, y);
			ctx.stroke();
			ctx.fillStyle = resolve('--text-dim');
			ctx.fillText(label.toUpperCase(), cx + 10, y);
		}
	}

	function drawAnchorSpokes(ctx: CanvasRenderingContext2D) {
		// Subtle radial lines from phi → anchors (goals) and attention (observations).
		// These are the only "edges" — they show what's tethered to phi's center.
		const cx = W / 2,
			cy = H / 2;
		ctx.strokeStyle = resolve('--line-dim');
		ctx.lineWidth = 1;
		for (const p of points) {
			if (p.kind !== 'goal' && p.kind !== 'observation') continue;
			const [sx, sy] = worldToScreen(p.x, p.y);
			ctx.beginPath();
			ctx.moveTo(cx, cy);
			ctx.lineTo(sx, sy);
			ctx.stroke();
		}
	}

	function drawPoints(ctx: CanvasRenderingContext2D) {
		for (const p of points) {
			const [sx, sy] = worldToScreen(p.x, p.y);
			const r = radiusFor(p);

			if (p.kind === 'phi') drawPhi(ctx, sx, sy, r, p);
			else if (p.kind === 'handle-engaged') drawKnown(ctx, sx, sy, r, p);
			else if (p.kind === 'handle-candidate') drawCandidate(ctx, sx, sy, r, p);
			else if (p.kind === 'goal') drawHex(ctx, sx, sy, r, '--warn');
			else if (p.kind === 'observation') drawHex(ctx, sx, sy, r, '--scan-mid');
		}
	}

	function drawHex(
		ctx: CanvasRenderingContext2D,
		cx: number,
		cy: number,
		r: number,
		colorVar: string
	) {
		ctx.fillStyle = resolve(colorVar);
		ctx.beginPath();
		// Pointy-top hex
		for (let i = 0; i < 6; i++) {
			const a = (-Math.PI / 2) + (i * Math.PI) / 3;
			const x = cx + Math.cos(a) * r;
			const y = cy + Math.sin(a) * r;
			if (i === 0) ctx.moveTo(x, y);
			else ctx.lineTo(x, y);
		}
		ctx.closePath();
		ctx.fill();
	}

	function drawPhi(
		ctx: CanvasRenderingContext2D,
		cx: number,
		cy: number,
		r: number,
		p: AtlasPoint
	) {
		// Glow halo
		const grd = ctx.createRadialGradient(cx, cy, r * 0.4, cx, cy, r * 2.2);
		grd.addColorStop(0, resolve('--hud-hot'));
		grd.addColorStop(1, 'rgba(184,107,58,0)');
		ctx.fillStyle = grd;
		ctx.beginPath();
		ctx.arc(cx, cy, r * 2.2, 0, Math.PI * 2);
		ctx.fill();

		// Hexagonal frame
		const drawHexPath = (radius: number) => {
			ctx.beginPath();
			for (let i = 0; i < 6; i++) {
				const a = (-Math.PI / 2) + (i * Math.PI) / 3;
				const x = cx + Math.cos(a) * radius;
				const y = cy + Math.sin(a) * radius;
				if (i === 0) ctx.moveTo(x, y);
				else ctx.lineTo(x, y);
			}
			ctx.closePath();
		};

		// Avatar inside, clipped to hex
		const img = p.avatar ? imageCache.get(p.avatar) : null;
		if (img) {
			ctx.save();
			drawHexPath(r);
			ctx.clip();
			ctx.drawImage(img, cx - r, cy - r, r * 2, r * 2);
			ctx.restore();
		} else {
			ctx.fillStyle = resolve('--hud-hot');
			drawHexPath(r);
			ctx.fill();
		}

		// Outer hex ring
		ctx.strokeStyle = resolve('--hud-hot');
		ctx.lineWidth = 1.5;
		drawHexPath(r);
		ctx.stroke();

		// Label below
		ctx.font = '10px "Saira Condensed", sans-serif';
		ctx.fillStyle = resolve('--hud-hot');
		ctx.textAlign = 'center';
		ctx.textBaseline = 'top';
		ctx.fillText('PHI', cx, cy + r + 6);
	}

	function drawKnown(
		ctx: CanvasRenderingContext2D,
		cx: number,
		cy: number,
		r: number,
		p: AtlasPoint
	) {
		const img = p.avatar ? imageCache.get(p.avatar) : null;
		ctx.save();
		ctx.beginPath();
		ctx.arc(cx, cy, r, 0, Math.PI * 2);
		if (img) {
			ctx.clip();
			ctx.drawImage(img, cx - r, cy - r, r * 2, r * 2);
		} else {
			ctx.fillStyle = resolve('--text-mid');
			ctx.fill();
		}
		ctx.restore();
		// outline
		ctx.strokeStyle = img ? resolve('--text') : resolve('--text-mid');
		ctx.lineWidth = 1.2;
		ctx.beginPath();
		ctx.arc(cx, cy, r, 0, Math.PI * 2);
		ctx.stroke();
	}

	function drawCandidate(
		ctx: CanvasRenderingContext2D,
		cx: number,
		cy: number,
		r: number,
		_p: AtlasPoint
	) {
		ctx.strokeStyle = resolve('--text-dim');
		ctx.lineWidth = 1;
		ctx.setLineDash([2, 2]);
		ctx.beginPath();
		ctx.arc(cx, cy, r, 0, Math.PI * 2);
		ctx.stroke();
		ctx.setLineDash([]);
	}

	function drawReticle(ctx: CanvasRenderingContext2D, p: AtlasPoint) {
		const [cx, cy] = worldToScreen(p.x, p.y);
		const r = radiusFor(p) + 4;
		ctx.strokeStyle = resolve('--hud-hot');
		ctx.lineWidth = 1.2;
		const arm = 6;
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

	// ---- input ----

	function pointAt(mx: number, my: number): AtlasPoint | null {
		let best: AtlasPoint | null = null;
		let bestD = Infinity;
		for (const p of points) {
			const [sx, sy] = worldToScreen(p.x, p.y);
			const r = radiusFor(p);
			const dx = sx - mx,
				dy = sy - my;
			const d2 = dx * dx + dy * dy;
			const hit = (r + 6) * (r + 6);
			if (d2 < hit && d2 < bestD) {
				bestD = d2;
				best = p;
			}
		}
		return best;
	}

	function readoutFor(p: AtlasPoint): string {
		const labels: Record<string, string> = {
			phi: 'self',
			'handle-engaged': 'in memory',
			'handle-candidate': 'on horizon',
			goal: 'anchor',
			observation: 'attention'
		};
		return `${labels[p.kind] ?? p.kind} · ${p.label}`;
	}

	function entryFor(p: AtlasPoint): LogbookEntry | null {
		if (p.kind === 'phi') return null;
		if (p.kind === 'handle-engaged') {
			const pl = p.payload as { handle: string };
			return {
				kind: 'handle',
				handle: pl.handle,
				engaged: true,
				payload: pl
			};
		}
		if (p.kind === 'handle-candidate') {
			const pl = p.payload as { handle: string; did: string; entry: DiscoveryEntry };
			return { kind: 'discovery', entry: pl.entry };
		}
		if (p.kind === 'goal') return { kind: 'goal', goal: p.payload as Goal };
		if (p.kind === 'observation')
			return { kind: 'observation', observation: p.payload as Observation };
		return null;
	}

	function onPointerMove(e: PointerEvent) {
		const rect = canvas.getBoundingClientRect();
		const mx = e.clientX - rect.left;
		const my = e.clientY - rect.top;
		const p = pointAt(mx, my);
		if (p !== hovered) {
			hovered = p;
			hudReadout.set(p ? readoutFor(p) : '');
			canvas.style.cursor = p && p.kind !== 'phi' ? 'pointer' : 'default';
			scheduleFrame();
		}
	}

	function onClick(e: MouseEvent) {
		const rect = canvas.getBoundingClientRect();
		const p = pointAt(e.clientX - rect.left, e.clientY - rect.top);
		if (!p) return;
		const entry = entryFor(p);
		if (entry) logbook.set(entry);
	}

	// ---- resize ----

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
	});

	onDestroy(() => {
		ro?.disconnect();
		hudReadout.set('');
	});
</script>

<div class="host">
	<canvas
		bind:this={canvas}
		onpointermove={onPointerMove}
		onpointerleave={() => {
			hovered = null;
			hudReadout.set('');
			canvas.style.cursor = 'default';
			scheduleFrame();
		}}
		onclick={onClick}
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

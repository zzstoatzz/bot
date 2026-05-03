<script lang="ts">
	import { onMount } from 'svelte';
	import { getCapabilities } from '$lib/api';
	import type { Capability } from '$lib/types';

	let caps = $state<Capability[]>([]);
	let selectedIdx = $state(0);
	let loaded = $state(false);
	let err = $state<string | null>(null);

	const sorted = $derived([...caps].sort((a, b) => a.name.localeCompare(b.name)));
	const total = $derived(sorted.length);
	const opCount = $derived(sorted.filter((c) => c.operator_only).length);
	const selected = $derived(sorted[selectedIdx] ?? null);

	onMount(async () => {
		try {
			caps = await getCapabilities();
			selectedIdx = 0;
		} catch (e) {
			err = (e as Error).message;
		} finally {
			loaded = true;
		}
	});

	function pick(i: number) {
		selectedIdx = i;
	}

	function onListKey(e: KeyboardEvent) {
		if (e.key === 'ArrowDown' && selectedIdx < total - 1) {
			e.preventDefault();
			selectedIdx++;
		} else if (e.key === 'ArrowUp' && selectedIdx > 0) {
			e.preventDefault();
			selectedIdx--;
		}
	}

	function pad(n: number, w = 2): string {
		return String(n + 1).padStart(w, '0');
	}
</script>

<svelte:head>
	<title>phi · capabilities</title>
</svelte:head>

<div class="lens">
	<div class="frame-wrap">
		<header class="head">
			<div class="head-rule">
				<span class="head-tag chrome">phi · capabilities</span>
				<span class="head-status chrome">
					{#if loaded && !err}
						<span class="num mono">{pad(total - 1)}</span>
						<span class="dim">entries</span>
						{#if opCount > 0}
							<span class="seg"></span>
							<span class="num mono">{pad(opCount - 1)}</span>
							<span class="dim">operator-gated</span>
						{/if}
					{:else if err}
						<span class="dim">connection lost</span>
					{:else}
						<span class="dim">acquiring…</span>
					{/if}
				</span>
			</div>
			<h1 class="title chrome">what i can do</h1>
		</header>

		<div class="panes">
			<!-- list pane -->
			<aside class="list-pane">
				<div class="pane-rule chrome">capabilities</div>
				{#if !loaded}
					<div class="empty chrome muted">acquiring…</div>
				{:else if err}
					<div class="empty chrome muted">unreachable · {err}</div>
				{:else if sorted.length === 0}
					<div class="empty chrome muted">none registered</div>
				{:else}
					<ul
						class="list scroll"
						role="listbox"
						tabindex="0"
						aria-label="capabilities"
						onkeydown={onListKey}
					>
						{#each sorted as cap, i (cap.name)}
							<li>
								<button
									class="row"
									class:active={i === selectedIdx}
									role="option"
									aria-selected={i === selectedIdx}
									onclick={() => pick(i)}
								>
									<span class="bar" aria-hidden="true"></span>
									<span class="idx mono">{pad(i)}</span>
									<span class="name mono">{cap.name}</span>
									{#if cap.operator_only}
										<span class="op-dot" title="requires nate's authorization"></span>
									{/if}
								</button>
							</li>
						{/each}
					</ul>
				{/if}
			</aside>

			<!-- detail pane -->
			<section class="detail-pane">
				<div class="pane-rule chrome">readout</div>
				{#if selected}
					<div class="detail scroll">
						<div class="d-head">
							<div class="d-name mono">{selected.name}</div>
							<div class="d-meta chrome">
								<span class="dim">entry</span>
								<span class="num mono">{pad(selectedIdx)}</span>
								<span class="dim">of</span>
								<span class="num mono">{pad(total - 1)}</span>
								{#if selected.operator_only}
									<span class="seg"></span>
									<span class="op-tag chrome">operator-gated</span>
								{/if}
							</div>
						</div>
						<div class="d-rule"></div>
						{#if selected.description}
							<div class="d-body">
								{#each selected.description.split(/\n\s*\n/) as para, i (i)}
									<p>{para}</p>
								{/each}
							</div>
						{:else}
							<div class="d-body muted">no description recorded.</div>
						{/if}
					</div>
				{:else}
					<div class="empty chrome muted">no entry selected</div>
				{/if}
			</section>
		</div>
	</div>
</div>

<style>
	.lens {
		position: absolute;
		inset: 0;
		display: flex;
		justify-content: center;
		padding: 76px 28px 56px;
		overflow: hidden;
	}

	.frame-wrap {
		position: relative;
		width: 100%;
		max-width: 980px;
		height: 100%;
		display: grid;
		grid-template-rows: auto 1fr;
		gap: 14px;
		background:
			linear-gradient(180deg, rgba(20, 26, 38, 0.55) 0%, rgba(13, 17, 25, 0.4) 100%),
			var(--bg-deep);
		border: 1px solid var(--line-mid);
		clip-path: polygon(
			16px 0,
			100% 0,
			100% calc(100% - 16px),
			calc(100% - 16px) 100%,
			0 100%,
			0 16px
		);
		padding: 18px 20px 16px;
		box-shadow:
			inset 0 0 60px rgba(184, 107, 58, 0.04),
			inset 1px 0 0 rgba(184, 107, 58, 0.05);
	}

	/* anchored corner brackets */
	.frame-wrap::before,
	.frame-wrap::after {
		content: '';
		position: absolute;
		width: 18px;
		height: 18px;
		border-color: var(--hud-hot);
		border-style: solid;
		border-width: 0;
		pointer-events: none;
		opacity: 0.7;
	}
	.frame-wrap::before {
		top: 4px;
		left: 4px;
		border-top-width: 1px;
		border-left-width: 1px;
	}
	.frame-wrap::after {
		bottom: 4px;
		right: 4px;
		border-bottom-width: 1px;
		border-right-width: 1px;
	}

	/* ---------- header ---------- */

	.head {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.head-rule {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		font-size: 9px;
		gap: 12px;
		padding-bottom: 8px;
		border-bottom: 1px solid var(--line-dim);
	}

	.head-tag {
		color: var(--hud-hot);
		letter-spacing: 0.22em;
	}

	.head-status {
		display: flex;
		gap: 6px;
		align-items: baseline;
		color: var(--scan-mid);
		letter-spacing: 0.1em;
	}

	.dim {
		color: var(--text-dim);
		font-size: 9px;
	}

	.num {
		color: var(--scan-hot);
		font-size: 10px;
	}

	.seg {
		display: inline-block;
		width: 1px;
		height: 8px;
		background: var(--line-mid);
		margin: 0 4px;
		vertical-align: middle;
	}

	.title {
		font-size: 28px;
		font-weight: 500;
		letter-spacing: 0.12em;
		color: var(--text);
		margin: 0;
		line-height: 1;
	}

	/* ---------- panes ---------- */

	.panes {
		display: grid;
		grid-template-columns: 320px 1fr;
		gap: 12px;
		min-height: 0;
	}

	.list-pane,
	.detail-pane {
		display: flex;
		flex-direction: column;
		min-height: 0;
		background: var(--bg-void);
		border: 1px solid var(--line-dim);
	}

	.pane-rule {
		font-size: 9px;
		color: var(--text-dim);
		letter-spacing: 0.22em;
		padding: 6px 12px;
		border-bottom: 1px solid var(--line-dim);
		background: linear-gradient(
			90deg,
			rgba(184, 107, 58, 0.08) 0%,
			rgba(184, 107, 58, 0) 90%
		);
	}

	.empty {
		flex: 1;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 10px;
		letter-spacing: 0.18em;
	}

	/* ---------- list ---------- */

	.list {
		flex: 1;
		list-style: none;
		padding: 4px 0;
		margin: 0;
		overflow-y: auto;
		outline: none;
	}

	.list:focus-visible {
		box-shadow: inset 0 0 0 1px var(--hud-mid);
	}

	.row {
		display: flex;
		align-items: center;
		gap: 10px;
		width: 100%;
		padding: 6px 12px 6px 8px;
		background: transparent;
		border: none;
		border-radius: 0;
		font-family: inherit;
		text-transform: none;
		letter-spacing: 0;
		text-align: left;
		color: var(--text-mid);
		cursor: pointer;
		transition:
			color 0.12s,
			background 0.12s;
		min-height: 30px;
	}

	.row .bar {
		display: block;
		width: 2px;
		height: 22px;
		background: transparent;
		flex-shrink: 0;
		transition: background 0.12s;
	}

	.row:hover {
		color: var(--text);
		background: rgba(184, 107, 58, 0.04);
	}

	.row.active {
		color: var(--hud-hot);
		background: linear-gradient(
			90deg,
			rgba(184, 107, 58, 0.18) 0%,
			rgba(184, 107, 58, 0.04) 60%,
			transparent 100%
		);
	}

	.row.active .bar {
		background: var(--hud-hot);
		box-shadow: 0 0 6px rgba(224, 144, 96, 0.6);
	}

	.idx {
		font-size: 10px;
		color: var(--text-dim);
		flex-shrink: 0;
	}

	.row.active .idx {
		color: var(--hud-mid);
	}

	.name {
		flex: 1;
		font-size: 12px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.op-dot {
		display: inline-block;
		width: 6px;
		height: 6px;
		background: var(--warn);
		clip-path: polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%);
		flex-shrink: 0;
		opacity: 0.8;
	}

	/* ---------- detail ---------- */

	.detail {
		flex: 1;
		padding: 18px 22px 22px;
		overflow-y: auto;
		display: flex;
		flex-direction: column;
		gap: 12px;
	}

	.d-head {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}

	.d-name {
		font-size: 22px;
		color: var(--text);
		text-transform: none;
		letter-spacing: 0.02em;
		line-height: 1.1;
	}

	.d-meta {
		display: flex;
		gap: 6px;
		align-items: baseline;
		font-size: 9px;
		letter-spacing: 0.18em;
		color: var(--text-dim);
	}

	.op-tag {
		color: var(--warn);
		font-size: 9px;
		letter-spacing: 0.22em;
	}

	.d-rule {
		height: 1px;
		background: repeating-linear-gradient(
			90deg,
			var(--hud-mid) 0px,
			var(--hud-mid) 8px,
			transparent 8px,
			transparent 14px
		);
		opacity: 0.6;
	}

	.d-body {
		font-size: 13px;
		line-height: 1.65;
		color: var(--text);
	}

	.d-body p {
		margin: 0 0 12px 0;
		white-space: pre-wrap;
	}

	.d-body p:last-child {
		margin-bottom: 0;
	}

	/* ---------- mobile ---------- */

	@media (max-width: 720px) {
		.lens {
			padding: 64px 12px 52px;
		}
		.frame-wrap {
			padding: 12px 14px 14px;
			gap: 10px;
		}
		.title {
			font-size: 22px;
		}
		.panes {
			grid-template-columns: 1fr;
			grid-template-rows: minmax(180px, 38vh) 1fr;
		}
	}
</style>

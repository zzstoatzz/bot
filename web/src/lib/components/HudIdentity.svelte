<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { getHealth, PHI_HANDLE } from '$lib/api';
	import type { HealthInfo } from '$lib/types';

	let health = $state<HealthInfo | null>(null);
	let timer: ReturnType<typeof setInterval> | null = null;

	async function poll() {
		try {
			health = await getHealth();
		} catch {
			health = null;
		}
	}

	onMount(() => {
		poll();
		timer = setInterval(poll, 15000);
	});

	onDestroy(() => {
		if (timer) clearInterval(timer);
	});

	const status = $derived.by(() => {
		if (!health) return { color: 'var(--danger)', label: 'offline', pulse: false };
		if (health.paused) return { color: 'var(--warn)', label: 'paused', pulse: true };
		if (health.polling_active) return { color: 'var(--hud-hot)', label: 'online', pulse: true };
		return { color: 'var(--text-dim)', label: 'idle', pulse: false };
	});
</script>

<div class="ident">
	<div class="glyph-wrap" style="color: {status.color}">
		<div class="glyph-bg"></div>
		<div class="glyph" class:pulse={status.pulse}>⌬</div>
	</div>
	<div class="meta">
		<div class="name chrome">phi</div>
		<div class="line">
			<span class="hex" style="color: {status.color}" class:pulse={status.pulse}></span>
			<span class="state chrome muted">{status.label}</span>
			<span class="sep">·</span>
			<a href="https://bsky.app/profile/{PHI_HANDLE}" target="_blank" rel="noopener" class="handle"
				>@{PHI_HANDLE}</a
			>
		</div>
	</div>
</div>

<style>
	.ident {
		display: flex;
		gap: 12px;
		align-items: center;
	}

	.glyph-wrap {
		position: relative;
		width: 32px;
		height: 32px;
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.glyph-bg {
		position: absolute;
		inset: 0;
		background: currentColor;
		opacity: 0.08;
		clip-path: polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%);
	}

	.glyph-wrap::before {
		content: '';
		position: absolute;
		inset: 1px;
		clip-path: polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%);
		box-shadow: inset 0 0 0 1px currentColor;
		opacity: 0.4;
	}

	.glyph {
		font-size: 18px;
		line-height: 1;
		position: relative;
		z-index: 1;
	}

	@media (max-width: 640px) {
		.glyph-wrap {
			width: 26px;
			height: 26px;
		}
		.glyph {
			font-size: 14px;
		}
		.name {
			font-size: 12px;
		}
		.handle {
			display: none;
		}
		.sep {
			display: none;
		}
	}

	.meta {
		display: flex;
		flex-direction: column;
		gap: 2px;
	}

	.name {
		font-size: 14px;
		color: var(--hud-hot);
		letter-spacing: 0.18em;
	}

	.line {
		display: flex;
		gap: 6px;
		align-items: center;
		font-size: 10px;
	}


	.state {
		font-size: 9px;
	}

	.sep {
		color: var(--text-dim);
	}

	.handle {
		font-family: var(--font-mono);
		font-size: 10px;
		color: var(--scan-mid);
	}
</style>

<script lang="ts">
	import { onMount } from 'svelte';
	import { getHealth, PHI_HANDLE } from '$lib/api';
	import type { HealthInfo } from '$lib/types';

	let health = $state<HealthInfo | null>(null);
	let err = $state<string | null>(null);

	onMount(async () => {
		try {
			health = await getHealth();
		} catch (e) {
			err = (e as Error).message;
		}
	});
</script>

<div class="container">
	<header>
		<h1>status</h1>
		<p class="muted">runtime health of the phi process. operational view.</p>
	</header>

	{#if err}
		<p class="faint">unreachable: {err}</p>
	{:else if !health}
		<p class="faint">loading…</p>
	{:else}
		<div class="grid">
			<div class="metric">
				<div class="value" style="color: {health.polling_active ? 'var(--accent-green)' : 'var(--text-faint)'}">
					{health.polling_active ? 'online' : 'offline'}
				</div>
				<div class="label">status</div>
			</div>
			<div class="metric">
				<div class="value" style="color: {health.paused ? 'var(--accent-yellow)' : 'var(--text)'}">
					{health.paused ? 'yes' : 'no'}
				</div>
				<div class="label">paused</div>
			</div>
			<div class="metric">
				<div class="value">{health.status}</div>
				<div class="label">health</div>
			</div>
			<div class="metric">
				<div class="value">@{PHI_HANDLE}</div>
				<div class="label">handle</div>
			</div>
		</div>
	{/if}
</div>

<style>
	header {
		margin-bottom: 24px;
	}

	.grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
		gap: 10px;
	}

	.metric {
		background: var(--bg-elev);
		border-radius: 8px;
		padding: 16px;
	}

	.value {
		font-size: 18px;
		color: var(--text);
		margin-bottom: 4px;
		word-break: break-word;
	}

	.label {
		font-size: 11px;
		text-transform: uppercase;
		letter-spacing: 0.4px;
		color: var(--text-muted);
	}
</style>

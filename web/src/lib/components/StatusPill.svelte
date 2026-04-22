<script lang="ts">
	import { onMount } from 'svelte';
	import { getHealth } from '$lib/api';
	import type { HealthInfo } from '$lib/types';

	let health = $state<HealthInfo | null>(null);
	let failed = $state(false);

	onMount(async () => {
		try {
			health = await getHealth();
		} catch {
			failed = true;
		}
	});

	const status = $derived.by(() => {
		if (failed) return { color: 'var(--accent-red)', text: 'unreachable' };
		if (!health) return { color: 'var(--text-faint)', text: '…' };
		if (health.paused) return { color: 'var(--accent-yellow)', text: 'paused' };
		if (health.polling_active) return { color: 'var(--accent-green)', text: 'online' };
		return { color: 'var(--text-faint)', text: 'offline' };
	});
</script>

<span class="pill">
	<span class="dot" style="background: {status.color}"></span>
	<span class="text">{status.text}</span>
</span>

<style>
	.pill {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		font-size: 12px;
		color: var(--text-muted);
	}

	.dot {
		display: inline-block;
		width: 8px;
		height: 8px;
		border-radius: 50%;
	}
</style>

<script lang="ts">
	import { hudReadout } from '$lib/state.svelte';

	const text = $derived(hudReadout.value || '');
</script>

<div class="readout chrome muted" class:has={!!text}>
	<span class="dot"></span>
	<span class="t">{text || 'idle'}</span>
</div>

<style>
	.readout {
		display: flex;
		gap: 6px;
		align-items: center;
		font-size: 10px;
		color: var(--text-dim);
	}

	.dot {
		width: 5px;
		height: 5px;
		border-radius: 50%;
		background: var(--text-dim);
		display: inline-block;
		transition: background 0.12s;
	}

	.has .dot {
		background: var(--hud-hot);
	}

	.has .t {
		color: var(--hud-hot);
	}
</style>

<script lang="ts">
	import type { Observation } from '$lib/types';
	import { relativeWhen } from '$lib/time';

	interface Props {
		observation: Observation;
	}

	let { observation }: Props = $props();

	const age = $derived(relativeWhen(observation.created_at));
</script>

<div class="card">
	<div class="content">{observation.content}</div>
	{#if observation.reasoning}
		<div class="reasoning">
			<span class="label">reasoning</span>
			<span>{observation.reasoning}</span>
		</div>
	{/if}
	<div class="meta faint">
		{#if age}<span>{age}</span>{/if}
		<span class="mono">rkey {observation.rkey}</span>
	</div>
</div>

<style>
	.card {
		border-left-color: var(--accent-yellow);
	}

	.content {
		font-size: 14px;
		color: var(--text);
		margin-bottom: 8px;
		white-space: pre-wrap;
	}

	.reasoning {
		font-size: 13px;
		color: var(--text-muted);
		margin-bottom: 8px;
		padding: 6px 10px;
		background: rgba(210, 153, 34, 0.06);
		border-radius: 4px;
	}

	.label {
		display: inline-block;
		text-transform: uppercase;
		letter-spacing: 0.4px;
		font-size: 10px;
		color: var(--accent-yellow);
		margin-right: 8px;
	}

	.meta {
		font-size: 11px;
		display: flex;
		gap: 12px;
	}
</style>

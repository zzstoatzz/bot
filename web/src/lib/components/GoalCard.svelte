<script lang="ts">
	import type { Goal } from '$lib/types';

	interface Props {
		goal: Goal;
	}

	let { goal }: Props = $props();
</script>

<div class="card">
	<div class="title">{goal.title}</div>
	<div class="body muted">{goal.description}</div>
	{#if goal.progress_signal}
		<div class="progress">
			<span class="label">progress</span>
			<span>{goal.progress_signal}</span>
		</div>
	{/if}
	<div class="meta faint">
		<span class="mono">rkey {goal.rkey}</span>
	</div>
</div>

<style>
	.card {
		border-left-color: var(--accent-blue);
	}

	.title {
		font-size: 16px;
		color: var(--text);
		margin-bottom: 6px;
	}

	.body {
		font-size: 14px;
		margin-bottom: 10px;
		white-space: pre-wrap;
	}

	.progress {
		font-size: 13px;
		color: var(--text-muted);
		margin-bottom: 8px;
		padding: 6px 10px;
		background: rgba(88, 166, 255, 0.06);
		border-radius: 4px;
	}

	.label {
		display: inline-block;
		text-transform: uppercase;
		letter-spacing: 0.4px;
		font-size: 10px;
		color: var(--accent-blue);
		margin-right: 8px;
	}

	.meta {
		font-size: 11px;
		margin-top: 4px;
	}
</style>

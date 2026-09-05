<script lang="ts">
	import { onMount } from 'svelte';
	import { getGoals, getActivity, getMemoryGraph, getDocket } from '$lib/api';
	import { mindCounts } from '$lib/state.svelte';

	let goalsCount = $state<number | null>(null);
	let outputCount = $state<number | null>(null);
	let peopleCount = $state<number | null>(null);
	let candidateCount = $state<number | null>(null);

	const displayed = $derived(
		mindCounts.value.loaded
			? mindCounts.value
			: {
					goals: goalsCount,
					out: outputCount,
					ppl: peopleCount,
					cand: candidateCount
				}
	);

	onMount(async () => {
		const [goals, activity, graph, docket] = await Promise.allSettled([
			getGoals(),
			getActivity(),
			getMemoryGraph(),
			getDocket()
		]);
		goalsCount = goals.status === 'fulfilled' ? goals.value.length : null;
		outputCount = activity.status === 'fulfilled' ? activity.value.length : null;
		peopleCount =
			graph.status === 'fulfilled'
				? graph.value.nodes.filter((n) => n.type === 'user').length
				: null;
		candidateCount = docket.status === 'fulfilled' ? (docket.value?.candidates.length ?? 0) : null;
	});
</script>

<div class="ticker" title="A dash means this count is loading or unavailable.">
	<div class="row">
		<span class="kv"
			><span class="k chrome">goals</span><span class="v mono">{displayed.goals ?? '—'}</span></span
		>
		<span class="kv"
			><span class="k chrome">people</span><span class="v mono">{displayed.ppl ?? '—'}</span></span
		>
		<span class="kv"
			><span class="k chrome">cand</span><span class="v mono">{displayed.cand ?? '—'}</span></span
		>
		<span class="kv"
			><span class="k chrome">out</span><span class="v mono">{displayed.out ?? '—'}</span></span
		>
	</div>
</div>

<style>
	.ticker {
		font-size: 10px;
	}

	.row {
		display: flex;
		gap: 14px;
		flex-wrap: wrap;
	}

	.kv {
		display: flex;
		gap: 6px;
		align-items: baseline;
	}

	.k {
		font-size: 9px;
		color: var(--text-dim);
	}

	.v {
		color: var(--scan-hot);
		font-size: 11px;
	}

	@media (max-width: 640px) {
		.row {
			gap: 10px;
			justify-content: space-between;
		}
		.k {
			font-size: 8px;
		}
		.v {
			font-size: 10px;
		}
	}
</style>

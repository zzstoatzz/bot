<script lang="ts">
	import { onMount } from 'svelte';
	import {
		getActiveObservations,
		getGoals,
		getActivity,
		getMemoryGraph,
		getDiscoveryPool
	} from '$lib/api';

	let counts = $state({
		obs: 0,
		goals: 0,
		out: 0,
		ppl: 0,
		cand: 0,
		loaded: false
	});

	onMount(async () => {
		const [obs, goals, activity, graph, disc] = await Promise.allSettled([
			getActiveObservations(),
			getGoals(),
			getActivity(),
			getMemoryGraph(),
			getDiscoveryPool()
		]);
		counts = {
			obs: obs.status === 'fulfilled' ? obs.value.length : 0,
			goals: goals.status === 'fulfilled' ? goals.value.length : 0,
			out: activity.status === 'fulfilled' ? activity.value.length : 0,
			ppl:
				graph.status === 'fulfilled'
					? graph.value.nodes.filter((n) => n.type === 'user').length
					: 0,
			cand: disc.status === 'fulfilled' ? disc.value.length : 0,
			loaded: true
		};
	});
</script>

<div class="ticker">
	<div class="row">
		<span class="kv"><span class="k chrome">attn</span><span class="v mono">{counts.obs}</span></span>
		<span class="kv"
			><span class="k chrome">goals</span><span class="v mono">{counts.goals}</span></span
		>
		<span class="kv"
			><span class="k chrome">people</span><span class="v mono">{counts.ppl}</span></span
		>
		<span class="kv"
			><span class="k chrome">cand</span><span class="v mono">{counts.cand}</span></span
		>
		<span class="kv"><span class="k chrome">out</span><span class="v mono">{counts.out}</span></span>
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

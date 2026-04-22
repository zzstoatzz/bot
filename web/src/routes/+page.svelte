<script lang="ts">
	import { onMount } from 'svelte';
	import StatusPill from '$lib/components/StatusPill.svelte';
	import GoalCard from '$lib/components/GoalCard.svelte';
	import ObservationCard from '$lib/components/ObservationCard.svelte';
	import PostCard from '$lib/components/PostCard.svelte';
	import { getActivity, getActiveObservations, getGoals, PHI_HANDLE } from '$lib/api';
	import type { ActivityItem, Goal, Observation } from '$lib/types';

	let goals = $state<Goal[]>([]);
	let observations = $state<Observation[]>([]);
	let recent = $state<ActivityItem[]>([]);
	let loaded = $state(false);

	onMount(async () => {
		const [g, o, a] = await Promise.allSettled([
			getGoals(),
			getActiveObservations(),
			getActivity()
		]);
		if (g.status === 'fulfilled') goals = g.value;
		if (o.status === 'fulfilled') observations = o.value;
		if (a.status === 'fulfilled') recent = a.value.slice(0, 5);
		loaded = true;
	});
</script>

<div class="container">
	<header>
		<h1>phi</h1>
		<div class="sub">
			<StatusPill />
			<span>·</span>
			<a href="https://bsky.app/profile/{PHI_HANDLE}" target="_blank" rel="noopener"
				>@{PHI_HANDLE}</a
			>
		</div>
		<p class="desc muted">
			a bluesky bot. small attention pool, durable goals, episodic memory, scout for community
			infrastructure.
		</p>
	</header>

	<section>
		<h2>active observations</h2>
		<p class="hint faint">
			what phi is currently attending to. small set, mutates often, archived after.
		</p>
		{#if !loaded}
			<p class="faint">loading…</p>
		{:else if observations.length === 0}
			<p class="faint">nothing in the active pool right now.</p>
		{:else}
			{#each observations as obs (obs.rkey)}
				<ObservationCard observation={obs} />
			{/each}
		{/if}
	</section>

	<section>
		<h2>goals</h2>
		<p class="hint faint">durable anchors. mutated through owner-approval (like-as-auth gate).</p>
		{#if !loaded}
			<p class="faint">loading…</p>
		{:else if goals.length === 0}
			<p class="faint">no goals set.</p>
		{:else}
			{#each goals as goal (goal.rkey)}
				<GoalCard {goal} />
			{/each}
		{/if}
	</section>

	<section>
		<div class="section-header">
			<h2>recent activity</h2>
			<a href="/feed" class="more">see all →</a>
		</div>
		{#if !loaded}
			<p class="faint">loading…</p>
		{:else if recent.length === 0}
			<p class="faint">nothing recent.</p>
		{:else}
			{#each recent as item (item.uri)}
				<PostCard {item} />
			{/each}
		{/if}
	</section>
</div>

<style>
	header {
		margin-bottom: 36px;
	}

	.sub {
		display: flex;
		align-items: center;
		gap: 8px;
		font-size: 13px;
		color: var(--text-muted);
		margin-top: 4px;
	}

	.desc {
		font-size: 14px;
		line-height: 1.6;
		margin-top: 16px;
		max-width: 540px;
	}

	section {
		margin-bottom: 36px;
	}

	.section-header {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		margin-bottom: 6px;
	}

	.section-header h2 {
		margin-bottom: 0;
	}

	.more {
		font-size: 12px;
		color: var(--text-muted);
	}

	.hint {
		font-size: 12px;
		margin-top: 0;
		margin-bottom: 16px;
		max-width: 540px;
	}

	h2 {
		margin-bottom: 6px;
	}
</style>

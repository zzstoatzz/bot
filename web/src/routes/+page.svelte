<script lang="ts">
	import '$lib/reading.css';
	import { onMount } from 'svelte';
	import Logbook from '$lib/components/Logbook.svelte';
	import CommandK from '$lib/components/CommandK.svelte';
	import AtlasOverlay from '$lib/components/AtlasOverlay.svelte';
	import { logbook, mindCounts } from '$lib/state.svelte';
	import { getMemoryGraph, getGoals, getDocket, getAtlas, getActivity } from '$lib/api';
	import type { GraphNode, Goal, Docket, Atlas, ActivityItem } from '$lib/types';
	let goals = $state<Goal[]>([]);
	let known = $state<GraphNode[]>([]);
	let docket = $state<Docket | null>(null);
	let atlas = $state<Atlas | null>(null);
	let activity = $state<ActivityItem[]>([]);
	type Source = 'activity' | 'goals' | 'people' | 'atlas' | 'docket';
	let states = $state<Record<Source, 'loading' | 'ready' | 'error'>>({
		activity: 'loading',
		goals: 'loading',
		people: 'loading',
		atlas: 'loading',
		docket: 'loading'
	});
	let refreshing = $state(false);
	let atlasOpen = $state(false);
	let query = $state('');
	let showAll = $state(false);
	const people = $derived(
		known
			.filter((p) => p.label.toLowerCase().includes(query.toLowerCase()))
			.slice(0, query ? 50 : 12)
	);
	const shownActivity = $derived(activity.slice(0, showAll ? 30 : 5));
	async function read<T>(source: Source, fetcher: () => Promise<T>, accept: (value: T) => void) {
		states[source] = 'loading';
		try {
			accept(await fetcher());
			states[source] = 'ready';
		} catch {
			states[source] = 'error';
		}
	}
	async function refresh() {
		refreshing = true;
		mindCounts.set({ goals: 0, out: 0, ppl: 0, cand: 0, loaded: false });
		await Promise.all([
			read(
				'activity',
				getActivity,
				(r) => (activity = r.toSorted((a, b) => Date.parse(b.time) - Date.parse(a.time)))
			),
			read('goals', getGoals, (r) => (goals = r)),
			read(
				'people',
				getMemoryGraph,
				(r) =>
					(known = r.nodes
						.filter((n) => n.type === 'user')
						.toSorted((a, b) => a.label.localeCompare(b.label)))
			),
			read('atlas', getAtlas, (r) => (atlas = r)),
			read('docket', getDocket, (r) => (docket = r))
		]);
		mindCounts.set({
			goals: goals.length,
			out: activity.length,
			ppl: known.length,
			cand: docket?.candidates.length ?? 0,
			loaded: Object.values(states).every((s) => s === 'ready')
		});
		refreshing = false;
	}
	onMount(() => {
		void refresh();
	});
	function date(value: string) {
		const d = new Date(value);
		return Number.isNaN(d.getTime())
			? 'Date unavailable'
			: d.toLocaleString('en-US', {
					month: 'short',
					day: 'numeric',
					year: 'numeric',
					hour: 'numeric',
					minute: '2-digit'
				});
	}
	function sourceLink(item: ActivityItem) {
		if (item.url?.startsWith('https://')) return item.url;
		const parts = item.uri.split('/');
		return parts[3] === 'app.bsky.feed.post'
			? `https://bsky.app/profile/${parts[2]}/post/${parts[4]}`
			: `https://pdsls.dev/${item.uri}`;
	}
</script>

<svelte:head><title>Phi · Mind</title></svelte:head>
<main class="reading-page">
	<div class="reading-inner">
		<header class="page-heading">
			<div>
				<p class="eyebrow">Activity & memory</p>
				<h1>Mind</h1>
				<p class="intro">What Phi has been doing, working toward, and remembering.</p>
			</div>
			<button onclick={refresh} disabled={refreshing}
				>{refreshing ? 'Refreshing…' : 'Refresh'}</button
			>
		</header>
		<div class="mind-layout">
			<div class="main-column">
				<section class="activity-section">
					<div class="section-heading">
						<div>
							<h2>Recent activity</h2>
							<p class="muted">Published posts, notes, and saved links.</p>
						</div>
					</div>
					{#if states.activity === 'loading'}<p class="empty" role="status">
							Loading activity…
						</p>{:else if states.activity === 'error'}<p class="notice" role="alert">
							Activity could not be loaded. Use Refresh to try again.
						</p>{:else if !activity.length}<p class="empty">No activity returned.</p>{:else}<div
							class="activity-list"
						>
							{#each shownActivity as item}<article>
									<div class="entry-meta">
										<span
											>{item.type === 'url'
												? 'Saved link'
												: item.type === 'note'
													? 'Note'
													: 'Post'}</span
										><time datetime={item.time}>{date(item.time)}</time>
									</div>
									{#if item.title}<h3>{item.title}</h3>{/if}
									<p class="entry-text">{item.text}</p>
									<a href={sourceLink(item)} target="_blank" rel="noreferrer">Read original ↗</a>
								</article>{/each}
						</div>
						{#if activity.length > 5}<button class="more" onclick={() => (showAll = !showAll)}
								>{showAll
									? 'Show fewer'
									: `Show more activity (${Math.min(activity.length, 30)})`}</button
							>{/if}{/if}
					<p class="footnote">
						This is published activity. It does not include every encounter or decision to stay
						silent.
					</p>
				</section>
				<section>
					<div class="section-heading"><h2>Current goals</h2></div>
					{#if states.goals === 'loading'}<p class="empty">
							Loading goals…
						</p>{:else if states.goals === 'error'}<p class="notice">
							Goals could not be loaded.
						</p>{:else if !goals.length}<p class="empty">
							No active goals returned.
						</p>{:else}{#each goals as goal}<article class="goal">
								<h3>{goal.title}</h3>
								<p>{goal.description}</p>
								{#if goal.progress_signal}<p class="muted">
										Progress: {goal.progress_signal}
									</p>{/if}
								<div class="goal-footer">
									<time datetime={goal.updated_at}>Updated {date(goal.updated_at)}</time><button
										onclick={() => logbook.set({ kind: 'goal', goal })}>View goal</button
									>
								</div>
							</article>{/each}{/if}
				</section>
			</div>
			<aside>
				<section class="memory-section">
					<h2>Stored memory</h2>
					<p class="muted">
						Look up a person to read stored exchanges, observations, and their sources.
					</p>
					<div class="lookup"><CommandK inline /></div>
					{#if states.people === 'loading'}<p class="empty">
							Loading people…
						</p>{:else if states.people === 'error'}<p class="notice">
							The people index could not be loaded. Person lookup is still available.
						</p>{:else}<details class="people-browser">
							<summary>Browse {known.length} people</summary><label class="person-filter"
								>Filter stored people<input
									type="search"
									placeholder="Filter by handle"
									bind:value={query}
								/></label
							>
							<div class="people">
								{#each people as person}<button
										onclick={() =>
											logbook.set({
												kind: 'handle',
												handle: person.label.replace(/^@/, ''),

												engaged: true,
												payload: person
											})}
										>{person.label.startsWith('@') ? person.label : `@${person.label}`}<span
											aria-hidden="true"
										>
											→</span
										></button
									>{/each}
							</div>
							{#if !people.length}<p class="empty">No matching people in this index.</p>{:else}<p
									class="footnote"
								>
									Alphabetical · showing {people.length}{query ? ' matches' : ` of ${known.length}`}
								</p>{/if}
						</details>{/if}
				</section>
				<section>
					<h2>Memory atlas</h2>
					<p class="muted">Explore related memories and public records by topic.</p>
					{#if states.atlas === 'loading'}<p class="empty">
							Loading atlas…
						</p>{:else if states.atlas === 'error'}<p class="notice">
							The atlas could not be loaded.
						</p>{:else if atlas}<p class="atlas-count">
							{atlas.points.length.toLocaleString()} mapped records
						</p>
						<p class="muted">{atlas.clusters_coarse.length} topic groups</p>
						<p class="footnote">
							Generated {date(atlas.generated_at)}. This is a periodic projection; it can omit
							recent or unindexed memories.
						</p>
						<button class="more" onclick={() => (atlasOpen = true)}>Explore atlas ↗</button
						>{:else}<p class="empty">No atlas has been published yet.</p>{/if}
				</section>
				<section>
					<h2>Ideas under consideration</h2>
					<p class="muted">Suggestions from the daily review, not commitments.</p>
					{#if states.docket === 'loading'}<p class="empty">
							Loading suggestions…
						</p>{:else if states.docket === 'error'}<p class="notice">
							Suggestions could not be loaded.
						</p>{:else if docket?.candidates.length}<p class="footnote">
							Generated {date(docket.generated_at)}
						</p>
						{#each docket.candidates.slice(0, 3) as candidate}<button
								class="idea"
								onclick={() => logbook.set({ kind: 'docket', candidate })}
								>{candidate.title}<span aria-hidden="true"> →</span></button
							>{/each}<button
							class="more"
							onclick={() => docket && logbook.set({ kind: 'docket-list', docket })}
							>View all {docket.candidates.length} suggestions</button
						>{:else}<p class="empty">No suggestions available.</p>{/if}
				</section>
			</aside>
		</div>
	</div>
</main>
<Logbook />
{#if atlasOpen && atlas}<AtlasOverlay {atlas} onClose={() => (atlasOpen = false)} />{/if}

<style>
	.people-browser summary {
		cursor: pointer;
		min-height: 44px;
		padding: 10px 0;
		color: #7ec0d4;
	}
	.people-browser[open] summary {
		margin-bottom: 12px;
	}
	.mind-layout {
		display: grid;
		grid-template-columns: minmax(0, 1.7fr) minmax(0, 1fr);
		gap: 24px;
	}
	.main-column,
	aside {
		min-width: 0;
	}
	.activity-section,
	.memory-section {
		border-top: 0;
		padding-top: 24px;
	}
	.activity-list article {
		padding: 24px 0;
		border-bottom: 1px solid #28313b;
	}
	.entry-meta {
		display: flex;
		flex-wrap: wrap;
		gap: 6px 14px;
		align-items: baseline;
		font-size: 12px;
		color: #a8b0b7;
		margin-bottom: 12px;
	}
	.entry-meta > span {
		color: #e09060;
	}
	.entry-text {
		white-space: pre-wrap;
		overflow-wrap: anywhere;
		line-height: 1.8;
		margin: 8px 0 12px;
	}
	.activity-list a {
		font-size: 13px;
	}
	.more {
		margin-top: 18px;
	}
	.goal {
		padding: 24px 0;
		border-bottom: 1px solid #28313b;
	}
	.goal > p {
		margin-top: 12px;
		white-space: pre-wrap;
		overflow-wrap: anywhere;
	}
	.goal-footer {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
		margin-top: 18px;
	}
	.goal time {
		font-size: 12px;
		color: #a8b0b7;
	}
	aside h2 {
		font-size: 23px;
	}
	aside section > p {
		margin-top: 10px;
	}
	.lookup {
		margin: 20px 0;
	}
	.person-filter {
		display: grid;
		gap: 8px;
		font-size: 13px;
		color: #a8b0b7;
	}
	.person-filter input {
		font: inherit;
		font-size: 16px;
		width: 100%;
		min-height: 44px;
		background: #141b25;
		border: 1px solid #43505e;
		border-radius: 6px;
		color: #e9e4da;
		padding: 10px 12px;
	}
	.people {
		margin-top: 12px;
	}
	.people button,
	.idea {
		font-family: var(--font-content);
		text-transform: none;
		letter-spacing: 0;
		box-shadow: none;
		display: block;
		background: transparent;
		border: 0;
		border-bottom: 1px solid #28313b;
		border-radius: 0;
		width: 100%;
		padding: 12px 0;
		text-align: left;
		font-size: 14px;
		overflow-wrap: anywhere;
	}
	.people button {
		color: #7ec0d4;
	}
	.people span,
	.idea span {
		color: #a8b0b7;
	}
	.atlas-count {
		font-size: 22px;
	}
	.idea {
		margin-top: 8px;
		line-height: 1.7;
	}
	@media (max-width: 760px) {
		.mind-layout {
			display: flex;
			flex-direction: column;
			gap: 0;
		}
		aside {
			order: -1;
			display: contents;
		}
		.main-column {
			display: contents;
		}
		.memory-section {
			order: -2;
		}
		.activity-section {
			order: -1;
		}
		.mind-layout section {
			padding: 20px 16px;
		}
		.mind-layout .memory-section {
			padding: 20px 16px;
		}
		.people {
			display: grid;
			grid-template-columns: repeat(2, minmax(0, 1fr));
			gap: 0 16px;
		}
		.people button {
			font-size: 13px;
		}
	}
</style>

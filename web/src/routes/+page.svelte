<script lang="ts">
	import '$lib/reading.css';
	import { onMount } from 'svelte';
	import Logbook from '$lib/components/Logbook.svelte';
	import CommandK from '$lib/components/CommandK.svelte';
	import AtlasOverlay from '$lib/components/AtlasOverlay.svelte';
	import { logbook, mindCounts } from '$lib/state.svelte';
	import { getPeople, getGoals, getDocket, getAtlas, getActivity } from '$lib/api';
	import type { Goal, Docket, Atlas, ActivityItem } from '$lib/types';
	let goals = $state<Goal[]>([]);
	let known = $state<string[]>([]);
	let docket = $state<Docket | null>(null);
	let atlas = $state<Atlas | null>(null);
	let activity = $state<ActivityItem[]>([]);
	type Source = 'activity' | 'goals' | 'people' | 'atlas' | 'docket';
	let states = $state<Record<Source, 'idle' | 'loading' | 'ready' | 'error'>>({
		activity: 'loading',
		goals: 'loading',
		people: 'idle',
		atlas: 'loading',
		docket: 'loading'
	});
	let refreshing = $state(false);
	let atlasOpen = $state(false);
	let query = $state('');
	let showAll = $state(false);
	let peopleLimit = $state(12);
	const matchingPeople = $derived(known.filter((handle) => handle.includes(query.toLowerCase().replace(/^@/, ''))));
	const people = $derived(matchingPeople.slice(0, peopleLimit));
	async function loadPeople() {
		if (states.people === 'loading') return;
		await read('people', getPeople, (handles) => (known = handles));
		mindCounts.set({ ...mindCounts.value, ppl: states.people === 'ready' ? known.length : null });
	}
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
		mindCounts.set({ goals: 0, out: 0, ppl: null, cand: 0, loaded: false });
		await Promise.all([
			read(
				'activity',
				getActivity,
				(r) => (activity = r.toSorted((a, b) => Date.parse(b.time) - Date.parse(a.time)))
			),
			read('goals', getGoals, (r) => (goals = r)),
			read('atlas', getAtlas, (r) => (atlas = r)),
			read('docket', getDocket, (r) => (docket = r))
		]);
		mindCounts.set({
			goals: goals.length,
			out: activity.length,
			ppl: states.people === 'ready' ? known.length : null,
			cand: docket?.candidates.length ?? 0,
			loaded: Object.entries(states).every(([key, state]) => key === 'people' || state === 'ready')
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
							<p class="muted">Top-level posts, their threads, and saved links.</p>
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
					<h2>Conversations & notes</h2>
					<p class="muted">
						Explore Phi’s conversations and the notes it kept.
					</p>
					<div class="lookup"><CommandK inline /></div>
					<details class="people-browser" ontoggle={(event) => {
						if (event.currentTarget.open && states.people === 'idle') void loadPeople();
					}}>
						<summary>Browse saved accounts</summary>
						{#if states.people === 'loading'}
							<p class="empty" role="status">Loading accounts…</p>
						{:else if states.people === 'error'}
							<p class="empty" role="alert">The account list couldn’t be loaded.</p>
							<button onclick={loadPeople}>Try again</button>
						{:else if states.people === 'ready'}
							<label class="person-filter">Filter accounts<input type="search" placeholder="Filter by handle" bind:value={query} oninput={() => (peopleLimit = 12)} /></label>
							<div class="people">
								{#each people as handle}<button onclick={() => logbook.set({kind: 'handle', handle, engaged: true, payload: null})}>@{handle}<span aria-hidden="true"> →</span></button>{/each}
							</div>
							{#if !people.length}<p class="empty">No matching accounts.</p>{/if}
							{#if matchingPeople.length > people.length}<button class="more" onclick={() => (peopleLimit += 12)}>Show 12 more</button>{/if}
							{#if people.length}<p class="footnote">{people.length} of {matchingPeople.length} accounts</p>{/if}
						{/if}
					</details>
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
		color: #a0d9e6;
		display: flex;
		justify-content: space-between;
		gap: 12px;
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
	.people-browser summary {
		cursor: pointer;
		color: #a1d4df;
		padding: 8px 0;
	}
	.person-filter {
		margin-top: 16px;
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
		color: #a0d9e6;
		display: flex;
		justify-content: space-between;
		gap: 12px;
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
			grid-template-columns: minmax(0, 1fr);
			gap: 0 16px;
		}
		.people button {
			font-size: 13px;
		}
	}
</style>

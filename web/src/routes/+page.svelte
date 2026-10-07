<script lang="ts">
	import '$lib/reading.css';
	import { onMount } from 'svelte';
	import CommandK from '$lib/components/CommandK.svelte';
	import AtlasPreview from '$lib/components/AtlasPreview.svelte';
	import { logbook, mindCounts } from '$lib/state.svelte';
	import {
		getPeople,
		getGoals,
		getDocket,
		getAtlas,
		getAtlasPreview,
		getActivity,
	} from '$lib/api';
	import { absoluteCT, relativeWhen } from '$lib/time';
	import type { AtlasPreview as Preview } from '$lib/atlas-preview';
	import type { Goal, Docket, Atlas, ActivityItem } from '$lib/types';

	const STALE_AFTER_MS = 60_000;
	const EARLIER_SHOWN = 6;

	let goals = $state<Goal[]>([]);
	let known = $state<string[]>([]);
	let docket = $state<Docket | null>(null);
	let preview = $state<Preview | null>(null);
	let atlas = $state<Atlas | null>(null);
	let activity = $state<ActivityItem[]>([]);
	type Source = 'activity' | 'goals' | 'people' | 'atlas' | 'docket';
	let states = $state<Record<Source, 'idle' | 'loading' | 'ready' | 'error'>>({
		activity: 'loading',
		goals: 'loading',
		people: 'idle',
		atlas: 'loading',
		docket: 'loading',
	});
	let refreshing = $state(false);
	let loadedAt = $state<number | null>(null);
	let now = $state(Date.now());
	let atlasState = $state<'closed' | 'opening' | 'open' | 'failed'>('closed');
	let query = $state('');
	let showAll = $state(false);
	let peopleLimit = $state(12);

	const matchingPeople = $derived(
		known.filter((handle) =>
			handle.includes(query.toLowerCase().replace(/^@/, '')),
		),
	);
	const people = $derived(matchingPeople.slice(0, peopleLimit));
	const latest = $derived(activity.at(0));
	const earlier = $derived(activity.slice(1, showAll ? 30 : 1 + EARLIER_SHOWN));

	async function loadPeople() {
		if (states.people === 'loading') return;
		await read('people', getPeople, (handles) => (known = handles));
		mindCounts.set({
			...mindCounts.value,
			ppl: states.people === 'ready' ? known.length : null,
		});
	}
	async function read<T>(
		source: Source,
		fetcher: () => Promise<T>,
		accept: (value: T) => void,
	) {
		if (states[source] !== 'ready') states[source] = 'loading';
		try {
			accept(await fetcher());
			states[source] = 'ready';
		} catch {
			states[source] = 'error';
		}
	}
	async function refresh() {
		if (refreshing) return;
		refreshing = true;
		await Promise.all([
			read(
				'activity',
				getActivity,
				(r) =>
					(activity = r.toSorted(
						(a, b) => Date.parse(b.time) - Date.parse(a.time),
					)),
			),
			read('goals', getGoals, (r) => (goals = r)),
			read('atlas', getAtlasPreview, (r) => (preview = r)),
			read('docket', getDocket, (r) => (docket = r)),
		]);
		mindCounts.set({
			goals: goals.length,
			out: activity.length,
			ppl: states.people === 'ready' ? known.length : null,
			cand: docket?.candidates.length ?? 0,
			loaded: Object.entries(states).every(
				([key, state]) => key === 'people' || state === 'ready',
			),
		});
		loadedAt = Date.now();
		now = loadedAt;
		refreshing = false;
	}
	async function openAtlas() {
		atlasState = 'opening';
		try {
			atlas ??= await getAtlas();
			atlasState = atlas ? 'open' : 'failed';
		} catch {
			atlasState = 'failed';
		}
	}

	onMount(() => {
		void refresh();
		const tick = setInterval(() => (now = Date.now()), 30_000);
		const onVisible = () => {
			if (document.visibilityState !== 'visible') return;
			now = Date.now();
			if (loadedAt && now - loadedAt > STALE_AFTER_MS) void refresh();
		};
		document.addEventListener('visibilitychange', onVisible);
		return () => {
			clearInterval(tick);
			document.removeEventListener('visibilitychange', onVisible);
		};
	});

	function kind(item: ActivityItem) {
		return item.type === 'url'
			? 'Saved link'
			: item.type === 'note'
				? 'Note'
				: 'Post';
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
<main class="reading-page mind">
	<div class="reading-inner">
		<div class="mind-layout">
			<div class="main-column">
				<section class="latest" aria-labelledby="latest-heading">
					<div class="section-top">
						<h1 id="latest-heading">Latest from Phi</h1>
						<button class="quiet" onclick={refresh} disabled={refreshing}
							>{refreshing
								? 'Updating…'
								: loadedAt
									? now - loadedAt < STALE_AFTER_MS
										? 'Updated just now'
										: `Updated ${relativeWhen(new Date(loadedAt).toISOString(), now)}`
									: 'Update'}</button
						>
					</div>
					{#if states.activity === 'loading'}
						<div class="lead placeholder" role="status">
							<span class="visually-hidden">Loading activity…</span>
						</div>
					{:else if states.activity === 'error'}
						<p class="notice" role="alert">
							Activity could not be loaded.
							<button class="quiet" onclick={refresh}>Try again</button>
						</p>
					{:else if !latest}
						<p class="empty">Phi has not published anything yet.</p>
					{:else}
						<article class="lead">
							<p class="entry-meta">
								<span class="kind">{kind(latest)}</span>
								<time datetime={latest.time} title={absoluteCT(latest.time)}
									>{relativeWhen(latest.time, now)}</time
								>
							</p>
							{#if latest.title}<h2>{latest.title}</h2>{/if}
							<p class="lead-text">{latest.text}</p>
							<a href={sourceLink(latest)} target="_blank" rel="noreferrer"
								>Read the original</a
							>
						</article>
						{#if earlier.length}
							<ol class="earlier">
								{#each earlier as item (item.uri)}
									<li>
										<a href={sourceLink(item)} target="_blank" rel="noreferrer">
											<span class="entry-meta">
												<span class="kind">{kind(item)}</span>
												<time datetime={item.time} title={absoluteCT(item.time)}
													>{relativeWhen(item.time, now)}</time
												>
											</span>
											<span class="row-text">{item.title || item.text}</span>
										</a>
									</li>
								{/each}
							</ol>
							{#if activity.length > 1 + EARLIER_SHOWN}
								<button class="quiet more" onclick={() => (showAll = !showAll)}
									>{showAll
										? 'Show fewer'
										: `Show ${Math.min(activity.length, 30) - 1 - EARLIER_SHOWN} more`}</button
								>
							{/if}
						{/if}
						<p class="footnote">
							Only what Phi published. Encounters it stayed silent on are not
							listed.
						</p>
					{/if}
				</section>

				<section aria-labelledby="goals-heading">
					<h2 id="goals-heading">Working toward</h2>
					{#if states.goals === 'loading'}
						<p class="empty" role="status">Loading goals…</p>
					{:else if states.goals === 'error'}
						<p class="notice">Goals could not be loaded.</p>
					{:else if !goals.length}
						<p class="empty">Phi has no active goals.</p>
					{:else}
						<div class="goals">
							{#each goals as goal (goal.rkey)}
								<details class="goal">
									<summary>
										<span class="goal-title">{goal.title}</span>
										<time
											datetime={goal.updated_at}
											title={absoluteCT(goal.updated_at)}
											>{relativeWhen(goal.updated_at, now)}</time
										>
									</summary>
									<p>{goal.description}</p>
									{#if goal.progress_signal}
										<p class="progress">{goal.progress_signal}</p>
									{/if}
									<button
										class="quiet"
										onclick={() => logbook.set({ kind: 'goal', goal })}
										>Open goal record</button
									>
								</details>
							{/each}
						</div>
					{/if}
				</section>
			</div>

			<aside>
				<section aria-labelledby="memory-heading">
					<h2 id="memory-heading">Memory</h2>
					<p class="muted">Look up what Phi kept about someone.</p>
					<div class="lookup"><CommandK inline /></div>
					{#if states.atlas === 'loading'}
						<div class="atlas-placeholder" role="status">
							<span class="visually-hidden">Loading atlas…</span>
						</div>
					{:else if states.atlas === 'error'}
						<p class="notice">The memory map could not be loaded.</p>
					{:else if preview}
						<AtlasPreview
							{preview}
							opening={atlasState === 'opening'}
							onclick={openAtlas}
						/>
						{#if atlasState === 'failed'}
							<p class="notice" role="alert">
								The full map could not be opened.
							</p>
						{/if}
						{#if preview.generated_at}
							<p class="footnote">
								Mapped {relativeWhen(preview.generated_at, now)}. Newer memories
								may not appear yet.
							</p>
						{/if}
					{:else}
						<p class="empty">No memory map has been published yet.</p>
					{/if}
					<details
						class="people-browser"
						ontoggle={(event) => {
							if (event.currentTarget.open && states.people === 'idle')
								void loadPeople();
						}}
					>
						<summary>Browse saved accounts</summary>
						{#if states.people === 'loading'}
							<p class="empty" role="status">Loading accounts…</p>
						{:else if states.people === 'error'}
							<p class="empty" role="alert">
								The account list couldn’t be loaded.
							</p>
							<button class="quiet" onclick={loadPeople}>Try again</button>
						{:else if states.people === 'ready'}
							<label class="person-filter"
								>Filter accounts<input
									type="search"
									placeholder="Filter by handle"
									bind:value={query}
									oninput={() => (peopleLimit = 12)}
								/></label
							>
							<div class="people">
								{#each people as handle (handle)}<button
										onclick={() =>
											logbook.set({
												kind: 'handle',
												handle,
												engaged: true,
												payload: null,
											})}>@{handle}</button
									>{/each}
							</div>
							{#if !people.length}<p class="empty">
									No matching accounts.
								</p>{/if}
							{#if matchingPeople.length > people.length}<button
									class="quiet more"
									onclick={() => (peopleLimit += 12)}>Show 12 more</button
								>{/if}
							{#if people.length}<p class="footnote">
									{people.length} of {matchingPeople.length} accounts
								</p>{/if}
						{/if}
					</details>
				</section>

				<section aria-labelledby="ideas-heading">
					<h2 id="ideas-heading">Considering</h2>
					{#if states.docket === 'loading'}
						<p class="empty" role="status">Loading suggestions…</p>
					{:else if states.docket === 'error'}
						<p class="notice">Suggestions could not be loaded.</p>
					{:else if docket?.candidates.length}
						<p class="muted">Possibilities from the daily review.</p>
						<ol class="ideas">
							{#each docket.candidates.slice(0, 3) as candidate}<li>
									<button
										class="idea"
										onclick={() => logbook.set({ kind: 'docket', candidate })}
										>{candidate.title}</button
									>
								</li>{/each}
						</ol>
						<button
							class="quiet more"
							onclick={() =>
								docket && logbook.set({ kind: 'docket-list', docket })}
							>See all {docket.candidates.length} suggestions</button
						>
						<p class="footnote">
							Reviewed {relativeWhen(docket.generated_at, now)}.
						</p>
					{:else}
						<p class="empty">Nothing is under consideration right now.</p>
					{/if}
				</section>
			</aside>
		</div>
	</div>
</main>
{#if logbook.value}
	{#await import('$lib/components/Logbook.svelte') then { default: Logbook }}
		<Logbook />
	{/await}
{/if}
{#if atlasState === 'open' && atlas}
	{#await import('$lib/components/AtlasOverlay.svelte') then { default: AtlasOverlay }}
		<AtlasOverlay {atlas} onClose={() => (atlasState = 'closed')} />
	{/await}
{/if}

<style>
	/* The home page reads as a log on open ground: the shared bevelled panels
	   and uppercase headings are switched off here. */
	.mind {
		font-size: 15px;
		line-height: 1.6;
	}
	.mind section {
		padding: 0;
		margin: 0;
	}
	.mind section::before,
	.mind section::after {
		display: none;
	}
	.mind h1,
	.mind h2 {
		font: 500 22px/1.2 var(--font-chrome);
		letter-spacing: 0.01em;
		text-transform: none;
		text-shadow: none;
		color: #f0d1ad;
	}
	.mind-layout {
		display: grid;
		grid-template-columns: minmax(0, 1fr);
		gap: 40px;
	}
	.main-column,
	aside {
		min-width: 0;
		display: grid;
		gap: 40px;
		align-content: start;
	}
	.section-top {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 12px;
		margin-bottom: 14px;
	}

	.mind .quiet {
		min-height: 44px;
		padding: 0;
		border: 0;
		background: none;
		box-shadow: none;
		font: 14px var(--font-content);
		letter-spacing: 0;
		text-transform: none;
		color: #a0d9e6;
	}
	.mind .quiet:hover {
		background: none;
		color: #d2f4fb;
		text-decoration: underline;
	}
	.mind .section-top .quiet {
		color: var(--text-mid);
		font-size: 13px;
	}
	.mind .more {
		display: block;
	}

	.entry-meta {
		display: flex;
		gap: 10px;
		align-items: baseline;
		font-size: 13px;
		color: var(--text-mid);
	}
	.kind {
		color: var(--hud-hot);
	}

	.lead {
		padding: 18px 18px 14px;
		border-left: 2px solid var(--hud-mid);
		background: linear-gradient(150deg, #1b2a34, #0e1720);
	}
	.lead h2 {
		margin-top: 8px;
		font-size: 24px;
		color: #f4eadb;
	}
	.lead-text {
		margin-top: 8px;
		font-size: 17px;
		line-height: 1.55;
		color: #f1ece2;
		white-space: pre-wrap;
		overflow-wrap: anywhere;
		display: -webkit-box;
		-webkit-box-orient: vertical;
		-webkit-line-clamp: 9;
		line-clamp: 9;
		overflow: hidden;
	}
	.lead a {
		display: inline-flex;
		align-items: center;
		min-height: 44px;
		font-size: 14px;
	}
	.lead.placeholder {
		min-height: 220px;
	}
	.atlas-placeholder {
		aspect-ratio: 320 / 214;
		margin-top: 14px;
		background: #08151c;
		border: 1px solid #1d323c;
	}

	.earlier {
		list-style: none;
		margin: 6px 0 0;
		padding: 0;
	}
	.earlier li {
		border-bottom: 1px solid #1f2933;
	}
	.earlier a {
		display: block;
		padding: 14px 0;
		color: inherit;
		text-shadow: none;
	}
	.earlier a:hover {
		text-decoration: none;
	}
	.earlier a:hover .row-text {
		color: #fff;
	}
	.row-text {
		display: -webkit-box;
		-webkit-box-orient: vertical;
		-webkit-line-clamp: 2;
		line-clamp: 2;
		overflow: hidden;
		margin-top: 3px;
		overflow-wrap: anywhere;
		color: #dcd7cd;
	}
	.mind .footnote {
		margin-top: 12px;
		font-size: 13px;
		color: var(--text-dim);
	}
	.mind .empty {
		padding: 14px 0;
	}

	.goals {
		margin-top: 8px;
	}
	.goal {
		border-bottom: 1px solid #1f2933;
	}
	.goal summary {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 16px;
		min-height: 52px;
		padding: 14px 0;
		cursor: pointer;
		list-style: none;
	}
	.goal summary::-webkit-details-marker {
		display: none;
	}
	.goal-title {
		flex: 1;
		font-size: 16px;
		color: #ece6da;
	}
	.goal summary::after {
		content: '';
		flex-shrink: 0;
		align-self: center;
		width: 7px;
		height: 7px;
		border-right: 1.5px solid var(--text-dim);
		border-bottom: 1.5px solid var(--text-dim);
		transform: rotate(45deg) translateY(-2px);
	}
	.goal[open] summary::after {
		transform: rotate(-135deg) translateY(-2px);
	}
	.goal[open] {
		padding-bottom: 14px;
	}
	.goal[open] .goal-title {
		color: #fff;
	}
	.goal time {
		flex-shrink: 0;
		font-size: 13px;
		color: var(--text-dim);
	}
	.goal > p {
		white-space: pre-wrap;
		overflow-wrap: anywhere;
		color: #d5d0c6;
	}
	.goal .progress {
		margin-top: 10px;
		padding-left: 12px;
		border-left: 2px solid var(--scan-dim);
		color: var(--text-mid);
	}

	aside .muted {
		margin-top: 4px;
		font-size: 14px;
	}
	.lookup {
		margin: 14px 0 0;
	}
	.people-browser {
		margin-top: 6px;
	}
	.people-browser summary {
		min-height: 44px;
		padding: 12px 0;
		cursor: pointer;
		color: #a0d9e6;
		font-size: 14px;
	}
	.person-filter {
		display: grid;
		gap: 8px;
		font-size: 13px;
		color: var(--text-mid);
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
		margin-top: 8px;
	}
	.mind .people button,
	.mind .idea {
		display: block;
		width: 100%;
		min-height: 44px;
		padding: 12px 0;
		border: 0;
		border-bottom: 1px solid #1f2933;
		border-radius: 0;
		background: none;
		box-shadow: none;
		font: 15px/1.5 var(--font-content);
		letter-spacing: 0;
		text-transform: none;
		text-align: left;
		overflow-wrap: anywhere;
	}
	.mind .people button {
		color: #a0d9e6;
	}
	.ideas {
		list-style: none;
		margin: 8px 0 0;
		padding: 0;
	}
	.mind .idea {
		color: #ece6da;
	}
	.mind .idea:hover,
	.mind .people button:hover {
		background: none;
		color: #fff;
	}

	.visually-hidden {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip-path: inset(50%);
		white-space: nowrap;
	}

	@media (min-width: 900px) {
		.mind-layout {
			grid-template-columns: minmax(0, 1.7fr) minmax(0, 1fr);
			gap: 56px;
		}
		.lead {
			padding: 24px 26px 18px;
		}
		.lead-text {
			font-size: 18px;
		}
	}
	@media (prefers-reduced-motion: no-preference) {
		.placeholder,
		.atlas-placeholder {
			animation: breathe 1.6s ease-in-out infinite alternate;
		}
		@keyframes breathe {
			from {
				opacity: 0.55;
			}
			to {
				opacity: 1;
			}
		}
	}
</style>

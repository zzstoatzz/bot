<script lang="ts">
	import { logbook } from '$lib/state.svelte';
	import { relativeWhen, whenTooltip } from '$lib/time';
	import { memoryDate, exchangePreview } from '$lib/person-memory';
	import MemorySources from './MemorySources.svelte';
	import { PHI_HANDLE, PHI_DID, OWNER_HANDLE, getUserView } from '$lib/api';
	import ViewIn from './ViewIn.svelte';
	import type {
		Goal,
		ActivityItem,
		BlogDoc,
		DocketCandidate,
		Docket,
		DiscoveryEntry,
		GraphNode,
		Atlas,
		UserView
	} from '$lib/types';

	type MemoryCandidate = {
		handle: string;
		point?: Atlas['points'][number];
		weight: number;
		clusterLabel?: string;
	};

	type MemoryPreview = MemoryCandidate & {
		view: UserView | null;
	};

	// Resolve an at-uri or a record reference into the bits ViewIn needs.
	function rkeyFromUri(uri: string): string {
		return uri.split('/').pop() ?? '';
	}
	function collectionFromUri(uri: string): string {
		// at://did/collection/rkey -> "collection"
		const parts = uri.replace(/^at:\/\//, '').split('/');
		return parts[1] ?? '';
	}
	function repoFromUri(uri: string): string {
		const parts = uri.replace(/^at:\/\//, '').split('/');
		return parts[0] ?? PHI_DID;
	}

	function atlasKindCounts(atlas: Atlas | null | undefined): [string, number][] {
		const counts = new Map<string, number>();
		for (const point of atlas?.points ?? []) {
			const kind = point.kind ?? 'other';
			counts.set(kind, (counts.get(kind) ?? 0) + 1);
		}
		return [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 8);
	}

	function atlasPointHandle(point: Atlas['points'][number]): string | null {
		const refs = point.refs as { handle?: string; observation_count?: number } | undefined;
		if (refs?.handle) return refs.handle.replace(/^@/, '');
		if (point.label) return point.label.replace(/^@/, '');
		return null;
	}

	function atlasObservationCount(point: Atlas['points'][number]): number {
		const refs = point.refs as { observation_count?: number } | undefined;
		return refs?.observation_count ?? 0;
	}

	function isPublicPersonHandle(handle: string): boolean {
		const h = handle.replace(/^@/, '').toLowerCase();
		return (
			!h.includes('example') &&
			h !== PHI_HANDLE &&
			h !== OWNER_HANDLE &&
			!h.startsWith('zzstoatzz')
		);
	}

	function clusterLabel(atlas: Atlas | null | undefined, point: Atlas['points'][number]): string | undefined {
		const fine = atlas?.clusters_fine.find((c) => c.id === point.cluster_fine);
		if (fine?.label) return fine.label;
		const coarse = atlas?.clusters_coarse.find((c) => c.id === point.cluster_coarse);
		return coarse?.label;
	}

	function memoryCandidates(store: {
		known?: GraphNode[];
		atlas?: Atlas | null;
	}): MemoryCandidate[] {
		const byHandle = new Map<string, MemoryCandidate>();
		for (const point of store.atlas?.points ?? []) {
			if (point.kind !== 'handle-engaged') continue;
			const handle = atlasPointHandle(point);
			if (!handle) continue;
			if (!isPublicPersonHandle(handle)) continue;
			byHandle.set(handle, {
				handle,
				point,
				weight: atlasObservationCount(point),
				clusterLabel: clusterLabel(store.atlas, point)
			});
		}
		for (const node of store.known ?? []) {
			const handle = node.label.replace(/^@/, '');
			if (!isPublicPersonHandle(handle)) continue;
			if (!byHandle.has(handle)) {
				byHandle.set(handle, { handle, weight: 0 });
			}
		}
		return [...byHandle.values()]
			.sort((a, b) => b.weight - a.weight || a.handle.localeCompare(b.handle));
	}

	const entry = $derived(logbook.value);
	let dialog = $state<HTMLDialogElement>();
	let returnFocus = $state<HTMLElement | null>(null);

	function close() {
		dialog?.close();
		logbook.set(null);
		returnFocus?.focus();
	}

	function openDialog(node: HTMLDialogElement) {
		const active = document.activeElement;
		returnFocus = active instanceof HTMLElement && active !== document.body
			? active
			: document.querySelector<HTMLButtonElement>('button[aria-label="search who phi knows"]');
		node.showModal();
		return { destroy: () => node.close() };
	}

	// User-view fetch: when the entry is a 'handle' or 'discovery', go pull
	// /api/users/{handle}. This is the rich state phi carries about a person —
	// histogram, summary, recent observations.
	//
	// `lastFetchedHandle` is a plain `let` (not $state) so the effect doesn't
	// track it — otherwise Svelte detects the read+write of the same piece of
	// state and throws effect_update_depth_exceeded.
	let userView = $state<UserView | null>(null);
	let userViewLoading = $state(false);
	let lastFetchedHandle: string | null = null;
	let memoryPreview = $state<MemoryPreview[]>([]);
	let memoryPreviewLoading = $state(false);
	let lastMemoryPreviewKey: string | null = null;

	$effect(() => {
		if (!entry) {
			userView = null;
			lastFetchedHandle = null;
			return;
		}
		const handle =
			entry.kind === 'handle'
				? entry.handle
				: entry.kind === 'discovery'
					? entry.entry.handle
					: null;
		if (!handle) {
			userView = null;
			lastFetchedHandle = null;
			return;
		}
		if (handle === lastFetchedHandle) return;
		lastFetchedHandle = handle;
		userView = null;
		userViewLoading = true;
		getUserView(handle).then((uv) => {
			if (handle === lastFetchedHandle) {
				userView = uv;
				userViewLoading = false;
			}
		});
	});

	$effect(() => {
		if (!entry || entry.kind !== 'store' || entry.store !== 'memory') {
			memoryPreview = [];
			memoryPreviewLoading = false;
			lastMemoryPreviewKey = null;
			return;
		}
		const store = entry as {
			kind: 'store';
			store: 'memory';
			known?: GraphNode[];
			atlas?: Atlas | null;
		};
		const candidates = memoryCandidates(store).slice(0, 12);
		const key = candidates.map((c) => `${c.handle}:${c.weight}`).join('|');
		if (key === lastMemoryPreviewKey) return;
		lastMemoryPreviewKey = key;
		memoryPreview = candidates.map((c) => ({ ...c, view: null }));
		memoryPreviewLoading = candidates.length > 0;
		Promise.allSettled(candidates.map((c) => getUserView(c.handle))).then((results) => {
			if (key !== lastMemoryPreviewKey) return;
			memoryPreview = candidates.map((candidate, i) => ({
				...candidate,
				view: results[i].status === 'fulfilled' ? results[i].value : null
			}));
			memoryPreviewLoading = false;
		});
	});

	function openPerson(handle: string) {
		logbook.set({ kind: 'handle', handle, engaged: true, payload: { handle } });
	}
</script>

{#if entry}
	<dialog bind:this={dialog} class="drawer" aria-label="logbook entry" use:openDialog oncancel={close}>
		<header>
			<div class="kind chrome">
				{#if entry.kind === 'handle'}conversations{:else if entry.kind === 'goal'}goal{:else if entry.kind === 'docket'}promotion pressure{:else if entry.kind === 'activity'}emission · {entry.item.type}{:else if entry.kind === 'blog'}long form{:else if entry.kind === 'discovery'}on my radar{/if}
				{#if entry.kind === 'docket-list'}public candidates{:else if entry.kind === 'store'}memory store{/if}
			</div>
			<button class="close" onclick={close} aria-label="Close details">Close</button>
		</header>

		<div class="detail-body scroll">
		{#if entry.kind === 'handle'}
			<div class="person-heading">
				<h1>@{entry.handle}</h1>
				<a href={`https://bsky.app/profile/${entry.did || entry.handle}`} target="_blank" rel="noopener">Bluesky profile ↗</a>
			</div>
			{#if userViewLoading}<p class="muted" role="status">Loading conversations…</p>
			{:else if userView}
				{#if userView.summary}
					<section class="person-section orientation">
						<h2>Phi’s summary</h2>
						<p class="person-date">Written {memoryDate(userView.summary.created_at)}. This summary may not include later corrections.</p>
						<details class="summary-reading">
							<summary aria-label="Toggle full summary"><span class="summary-preview">{userView.summary.content}</span><span class="read-toggle"><span class="read-open">Read full summary</span><span class="read-close">Close full summary</span></span></summary>
							<p class="memory-prose">{userView.summary.content}</p>
						</details>
					</section>
				{:else}<p class="muted">{userView.recent_observations.length || userView.recent_interactions?.length ? 'Phi hasn’t written a summary of these conversations yet.' : userView.recent_interactions == null ? 'No summary is available.' : 'No saved conversations or notes for this account yet.'}</p>{/if}
				{#if userView.recent_observations.length}
					<section class="person-section"><h2>Recent notes</h2>
						<ul class="memory-notes">{#each userView.recent_observations as note}<li>
							<p>{note.content}</p><div class="memory-links"><span>Saved {memoryDate(note.created_at)}</span>
							<MemorySources uris={note.source_uris} /></div>
						</li>{/each}</ul>
					</section>
				{/if}
				{#if userView.recent_interactions == null || userView.recent_interactions.length}
				<section class="person-section"><h2>Conversations</h2>
					{#if userView.recent_interactions == null}<p class="muted">Conversation history couldn’t be loaded.</p>
					{:else if !userView.recent_interactions.length}<p class="muted">No saved exchanges yet.</p>
					{:else}<p class="person-date">Latest {userView.recent_interactions.length} saved exchanges. Some encounters aren’t saved here.</p>
						{#each userView.recent_interactions as exchange (exchange.id)}<details class="conversation">
							<summary><span class="person-date">Saved {memoryDate(exchange.created_at)}</span><span>{exchangePreview(exchange.content)}</span></summary>
							<p class="memory-prose">{exchange.content}</p>
							<div class="memory-links"><MemorySources uris={exchange.source_uris} /></div>
						</details>{/each}
					{/if}
				</section>
				{/if}
				{#if userView.counts.observation || userView.counts.interaction || userView.counts.summary}
				<details class="memory-coverage"><summary>About this history</summary><p>Replacement history is not available in this view yet. Dates show when notes were saved, not necessarily when events happened.</p>
					<p>{userView.counts.observation} notes and {userView.counts.interaction} exchanges returned from saved memory. These counts aren’t a complete history of interactions.</p>
					{#if userView.first_seen}<p>Earliest saved record: {memoryDate(userView.first_seen)}.</p>{/if}
					{#if userView.last_seen}<p>Latest saved record: {memoryDate(userView.last_seen)}.</p>{/if}
				</details>
				{/if}
			{:else}<p class="muted" role="status">Couldn’t load this conversation history. Close this panel and try again.</p>{/if}
		{:else if entry.kind === 'goal'}
			{@const goalE = entry as { kind: 'goal'; goal: Goal }}
			{@const goalTs = goalE.goal.updated_at || goalE.goal.created_at}
			<h1>{goalE.goal.title}</h1>
			<p class="content">{goalE.goal.description}</p>
			{#if goalE.goal.progress_signal}
				<div class="block">
					<div class="block-label chrome">how i'll know it's working</div>
					<div class="muted">{goalE.goal.progress_signal}</div>
				</div>
			{/if}
			<div class="meta">
				<span class="faint" title={whenTooltip(goalTs)}
					>last touched {relativeWhen(goalTs)}</span
				>
			</div>
			<div class="actions">
				<ViewIn
					kind="record"
					handle={PHI_HANDLE}
					did={PHI_DID}
					collection="io.zzstoatzz.phi.goal"
					rkey={goalE.goal.rkey}
				/>
			</div>
		{:else if entry.kind === 'docket'}
			{@const docket = entry as {
				kind: 'docket';
				candidate: DocketCandidate;
			}}
			<h1>{docket.candidate.title}</h1>
			<p class="content">{docket.candidate.rationale}</p>
			<div class="hist">
				<div class="hist-cell">
					<div class="hist-num mono">{docket.candidate.private_evidence.length}</div>
					<div class="hist-lbl chrome">private</div>
				</div>
				<div class="hist-cell">
					<div class="hist-num mono">{docket.candidate.existing_public_anchors.length}</div>
					<div class="hist-lbl chrome">public</div>
				</div>
				<div class="hist-cell">
					<div class="hist-num mono">{docket.candidate.suggested_shape}</div>
					<div class="hist-lbl chrome">form</div>
				</div>
			</div>
			<p class="muted">
				Form is the suggested way this private pattern might become public work.
			</p>
			{#if docket.candidate.private_evidence.length > 0}
				<div class="block">
					<div class="block-label chrome">private evidence</div>
					<ul class="obs-list">
						{#each docket.candidate.private_evidence as ev (ev.atlas_point_id)}
							<li class="obs">
								<div class="obs-text">{ev.snippet}</div>
								<div class="obs-meta faint mono">{ev.kind} · {ev.atlas_point_id}</div>
							</li>
						{/each}
					</ul>
				</div>
			{/if}
			{#if docket.candidate.related_tags.length > 0}
				<div class="block">
					<div class="block-label chrome">tags</div>
					<div class="tags mono">{docket.candidate.related_tags.join(' · ')}</div>
				</div>
			{/if}
		{:else if entry.kind === 'docket-list'}
			{@const docketList = entry as { kind: 'docket-list'; docket: Docket }}
			<h1>public candidates</h1>
			<p class="muted">
				Private atlas evidence that may be ready to become public work. The form is a suggestion
				for how to publish it, such as a thread, note, reply, or longer piece.
			</p>
			<div class="hist">
				<div class="hist-cell">
					<div class="hist-num mono">{docketList.docket.candidates.length}</div>
					<div class="hist-lbl chrome">candidates</div>
				</div>
				<div class="hist-cell">
					<div class="hist-num mono">{docketList.docket.atlas_point_count}</div>
					<div class="hist-lbl chrome">atlas points</div>
				</div>
				<div class="hist-cell">
					<div class="hist-num mono">{docketList.docket.generated_at.slice(5, 10)}</div>
					<div class="hist-lbl chrome">generated</div>
				</div>
			</div>
			<div class="block">
				<div class="block-label chrome">ranked work</div>
				<ul class="obs-list">
					{#each docketList.docket.candidates as candidate (candidate.id)}
						<li class="obs">
							<button class="obs-button" onclick={() => logbook.set({ kind: 'docket', candidate })}>
								<div class="obs-text">{candidate.title}</div>
								<div class="obs-meta faint">
									<span>{candidate.private_evidence.length} private</span>
									<span>{candidate.existing_public_anchors.length} public</span>
									<span>form: {candidate.suggested_shape}</span>
								</div>
							</button>
						</li>
					{/each}
				</ul>
			</div>
		{:else if entry.kind === 'store'}
			{@const store = entry as {
				kind: 'store';
				store: 'pds' | 'memory' | 'atlas';
				goals?: Goal[];
				known?: GraphNode[];
				atlas?: Atlas | null;
			}}
			{#if store.store === 'pds'}
				<h1>PDS state</h1>
				<p class="muted">
					Small durable records that phi carries into future runs.
				</p>
				<div class="hist">
					<div class="hist-cell">
						<div class="hist-num mono">{store.goals?.length ?? 0}</div>
						<div class="hist-lbl chrome">goals</div>
					</div>
					<div class="hist-cell">
						<div class="hist-num mono">PDS</div>
						<div class="hist-lbl chrome">source</div>
					</div>
				</div>
				{#if store.goals && store.goals.length > 0}
					<div class="block">
						<div class="block-label chrome">intent</div>
						<ul class="obs-list">
							{#each store.goals as goal (goal.rkey)}
								<li class="obs">
									<div class="obs-text">{goal.title}</div>
									<div class="obs-meta faint">{goal.description}</div>
								</li>
							{/each}
						</ul>
					</div>
				{/if}
			{:else if store.store === 'memory'}
				<h1>people memory</h1>
				<p class="muted">
					Relationship memory carried per person: impressions, observations, and traces of
					exchange.
				</p>
				<div class="hist">
					<div class="hist-cell">
						<div class="hist-num mono">
							{Math.max(store.known?.length ?? 0, memoryCandidates(store).length)}
						</div>
						<div class="hist-lbl chrome">people</div>
					</div>
					<div class="hist-cell">
						<div class="hist-num mono">{memoryPreview.reduce((n, p) => n + (p.view?.counts.observation ?? p.weight), 0)}</div>
						<div class="hist-lbl chrome">notes</div>
					</div>
					<div class="hist-cell">
						<div class="hist-num mono">{memoryPreview.filter((p) => p.view?.summary).length}</div>
						<div class="hist-lbl chrome">impressions</div>
					</div>
				</div>
				{#if memoryPreviewLoading}
					<p class="muted">recalling relationship index…</p>
				{/if}
				{#if memoryPreview.length > 0}
					<div class="block">
						<div class="block-label chrome">strongest carried people</div>
						<div class="person-grid">
							{#each memoryPreview as person (person.handle)}
								<button class="person-card" onclick={() => openPerson(person.handle)}>
									<div class="person-top">
										<span class="person-handle mono">@{person.handle}</span>
										<span class="person-count mono">
											{person.view?.counts.observation ?? person.weight} obs · {person.view?.counts.interaction ?? 0} exch
										</span>
									</div>
									{#if person.view?.summary}
										<div class="person-summary">{person.view.summary.content}</div>
									{:else if person.view?.recent_observations?.[0]}
										<div class="person-summary">{person.view.recent_observations[0].content}</div>
									{:else if person.clusterLabel}
										<div class="person-summary">near {person.clusterLabel}</div>
									{:else}
										<div class="person-summary faint">carried in the relationship graph</div>
									{/if}
									<div class="person-meta faint">
										{#if person.clusterLabel}
											<span>{person.clusterLabel}</span>
										{/if}
										{#if person.view?.last_seen}
											<span title={whenTooltip(person.view.last_seen)}
												>{relativeWhen(person.view.last_seen)}</span
											>
										{/if}
									</div>
								</button>
							{/each}
						</div>
					</div>
				{:else if !memoryPreviewLoading}
					<p class="muted">No people memory loaded for this pass.</p>
				{/if}
			{:else}
				<h1>atlas</h1>
				<p class="muted">
					The large daily blob: clustered private points used to find patterns and promote
					candidates into public work.
				</p>
				<div class="hist">
					<div class="hist-cell">
						<div class="hist-num mono">{store.atlas?.points.length ?? 0}</div>
						<div class="hist-lbl chrome">points</div>
					</div>
					<div class="hist-cell">
						<div class="hist-num mono">{store.atlas?.clusters_coarse.length ?? 0}</div>
						<div class="hist-lbl chrome">coarse</div>
					</div>
					<div class="hist-cell">
						<div class="hist-num mono">{store.atlas?.clusters_fine.length ?? 0}</div>
						<div class="hist-lbl chrome">fine</div>
					</div>
				</div>
				{#if store.atlas}
					<div class="block">
						<div class="block-label chrome">point kinds</div>
						<div class="tags mono">
							{atlasKindCounts(store.atlas)
								.map(([kind, count]) => `${kind}:${count}`)
								.join(' · ')}
						</div>
					</div>
				{/if}
				{#if store.atlas?.clusters_fine?.length}
					<div class="block">
						<div class="block-label chrome">largest fine clusters</div>
						<ul class="obs-list">
							{#each [...store.atlas.clusters_fine].sort((a, b) => (b.count ?? 0) - (a.count ?? 0)).slice(0, 12) as cluster (cluster.id)}
								<li class="obs">
									<div class="obs-text">{cluster.label ?? `cluster ${cluster.id}`}</div>
									<div class="obs-meta faint">{cluster.count ?? 0} points</div>
								</li>
							{/each}
						</ul>
					</div>
				{/if}
			{/if}
		{:else if entry.kind === 'activity'}
			{@const act = entry as { kind: 'activity'; item: ActivityItem }}
			{@const kindLabel =
				act.item.type === 'post'
					? 'i posted'
					: act.item.type === 'note'
						? 'i made a note'
						: 'i bookmarked'}
			<h1 class="chrome">{kindLabel}</h1>
			{#if act.item.title}
				<div class="title">{act.item.title}</div>
			{/if}
			<p class="content">{act.item.text}</p>
			<div class="meta">
				<span class="faint" title={whenTooltip(act.item.time)}>{relativeWhen(act.item.time)}</span>
			</div>
			<div class="actions">
				{#if act.item.type === 'post' && act.item.uri.startsWith('at://')}
					<ViewIn
						kind="post"
						handle={PHI_HANDLE}
						did={repoFromUri(act.item.uri)}
						collection={collectionFromUri(act.item.uri)}
						rkey={rkeyFromUri(act.item.uri)}
					/>
				{:else if act.item.uri.startsWith('at://')}
					<ViewIn
						kind="record"
						handle={PHI_HANDLE}
						did={repoFromUri(act.item.uri)}
						collection={collectionFromUri(act.item.uri)}
						rkey={rkeyFromUri(act.item.uri)}
					/>
				{/if}
				{#if act.item.url}
					<a class="extlink" href={act.item.url} target="_blank" rel="noopener"
						>open the link ↗</a
					>
				{/if}
			</div>
		{:else if entry.kind === 'blog'}
			{@const blog = entry as { kind: 'blog'; doc: BlogDoc }}
			<h1>{blog.doc.title}</h1>
			<div class="content prose">{blog.doc.content}</div>
			<div class="meta">
				<span class="faint" title={whenTooltip(blog.doc.publishedAt)}
					>written {relativeWhen(blog.doc.publishedAt)}</span
				>
			</div>
			<div class="actions">
				<ViewIn
					kind="blog"
					handle={PHI_HANDLE}
					did={PHI_DID}
					collection="app.greengale.document"
					rkey={blog.doc.rkey}
				/>
			</div>
		{:else if entry.kind === 'discovery'}
			{@const disc = entry as { kind: 'discovery'; entry: DiscoveryEntry }}
			<h1 class="mono">@{disc.entry.handle}</h1>
			{#if userView && !userView.is_stranger}
				<p class="muted">someone i already carry, also surfacing on my radar:</p>
				<div class="hist">
					<div class="hist-cell">
						<div class="hist-num mono">{userView.counts.observation}</div>
						<div class="hist-lbl chrome">obs</div>
					</div>
					<div class="hist-cell">
						<div class="hist-num mono">{userView.counts.interaction}</div>
						<div class="hist-lbl chrome">exch</div>
					</div>
					<div class="hist-cell">
						<div class="hist-num mono">{disc.entry.likes_in_window}</div>
						<div class="hist-lbl chrome">likes</div>
					</div>
				</div>
			{:else}
				<p class="muted">
					not in my memory yet. nate liked {disc.entry.likes_in_window} thing{disc.entry
						.likes_in_window === 1
						? ''
						: 's'} they wrote, most recently {relativeWhen(disc.entry.last_liked_at)}.
				</p>
			{/if}
			{#if disc.entry.sample_posts.length}
				<div class="block">
					<div class="block-label chrome">what nate liked</div>
					{#each disc.entry.sample_posts as post (post.uri)}
						<div class="sample">
							<div class="sample-text">{post.text}</div>
							<div class="sample-meta faint">{relativeWhen(post.liked_at)}</div>
						</div>
					{/each}
				</div>
			{/if}
			<div class="actions">
				<ViewIn kind="profile" handle={disc.entry.handle} did={disc.entry.did} />
			</div>
		{/if}

		</div>
	</dialog>
{/if}

<style>
	.person-heading { padding-block: 8px 12px; }
	.person-heading h1 { font-size: 28px; overflow-wrap: anywhere; }
	.person-heading a { display: inline-block; padding-block: 10px; color: var(--scan-hot); font-size: 13px; }
	.person-section { padding-block: 12px; }
	.person-section h2 { margin: 0 0 6px; font: 400 23px/1.2 var(--font-chrome); color: var(--scan-hot); }
	.person-date { color: var(--text-dim); font-size: 12px; line-height: 1.5; margin: 0 0 12px; }
	.orientation { border-top: 1px solid var(--line-scan); border-bottom: 1px solid var(--line-scan); }
	.summary-reading summary { list-style: none; cursor: pointer; }
	.summary-reading summary::-webkit-details-marker { display: none; }
	.summary-preview { display: -webkit-box; line-clamp: 5; -webkit-line-clamp: 5; -webkit-box-orient: vertical; overflow: hidden; font-size: 15px; line-height: 1.65; }
	.read-toggle { display: block; padding-block: 10px; font-size: 13px; color: var(--scan-hot); }
	.summary-reading[open] .summary-preview { display: none; }
	.read-close, .summary-reading[open] .read-open { display: none; }
	.summary-reading[open] .read-close { display: inline; }
	.memory-prose { white-space: pre-wrap; overflow-wrap: anywhere; font-size: 14px; line-height: 1.65; margin: 0 0 12px; }
	.memory-notes { list-style: none; padding: 0; margin: 0; }
	.memory-notes li { padding-block: 14px; border-bottom: 1px solid var(--line-dim); }
	.memory-notes li:last-child { border: 0; }
	.memory-notes p { margin: 0 0 6px; font-size: 14px; line-height: 1.6; }
	.memory-links { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 16px; color: var(--text-dim); font-size: 12px; }
	.conversation { border-bottom: 1px solid var(--line-dim); }
	.conversation summary { padding: 14px 22px 14px 0; cursor: pointer; font-size: 14px; line-height: 1.5; }
	.conversation summary .person-date { display: block; margin-bottom: 5px; }
	.conversation summary > span:last-child { display: -webkit-box; line-clamp: 2; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
	.conversation[open] summary > span:last-child { display: none; }
	.memory-coverage { border-top: 1px solid var(--line-mid); margin-top: 16px; font-size: 12px; color: var(--text-dim); line-height: 1.6; }
	.memory-coverage summary { padding-block: 16px; cursor: pointer; }
	.summary-reading summary:focus-visible, .conversation summary:focus-visible, .memory-coverage summary:focus-visible { outline: 2px solid var(--hud-hot); outline-offset: 3px; }
	.drawer::backdrop {
		background: rgba(0, 0, 0, 0.4);
	}

	.drawer {
		margin: 0 0 0 auto;
		color: var(--text);
		border: 0;
		max-width: 100%;
		max-height: 100dvh;
		height: 100dvh;
		position: fixed;
		top: 0;
		right: 0;
		bottom: 0;
		width: min(520px, 92vw);
		background: var(--bg-deep);
		border-left: 1px solid var(--line-mid);
		box-shadow: inset 8px 0 24px rgba(184, 107, 58, 0.06);
		z-index: 51;
		padding: 22px 26px 26px;
		animation: slide 220ms cubic-bezier(0.16, 0.84, 0.3, 1);
		display: flex;
		flex-direction: column;
		gap: 12px;
	}
	.detail-body {
		min-height: 0;
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 12px;
		overflow-y: auto;
		overscroll-behavior: contain;
		overflow-wrap: anywhere;
	}
	.detail-body > :global(*) {
		flex-shrink: 0;
	}

	.drawer::before,
	.drawer::after {
		content: '';
		position: absolute;
		left: -1px;
		width: 12px;
		height: 12px;
		border-color: var(--hud-mid);
		border-style: solid;
		border-width: 0;
		pointer-events: none;
	}

	.drawer::before {
		top: -1px;
		border-top-width: 1px;
		border-left-width: 1px;
	}

	.drawer::after {
		bottom: -1px;
		border-bottom-width: 1px;
		border-left-width: 1px;
	}

	header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding-bottom: 10px;
		border-bottom: 1px solid var(--line-mid);
	}

	.kind {
		font-size: 10px;
		color: var(--scan-mid);
		letter-spacing: 0.18em;
	}

	.close {
		font-size: 14px;
		min-height: 44px;
		min-width: 64px;
		padding: 8px 12px;
	}

	h1 {
		font-family: var(--font-chrome);
		font-weight: 400;
		font-size: 22px;
		letter-spacing: 0.04em;
		color: var(--text);
		margin: 0;
	}

	h1.mono {
		font-family: var(--font-mono);
		text-transform: none;
		letter-spacing: 0;
		font-size: 18px;
	}

	h1.chrome {
		font-size: 14px;
		color: var(--hud-hot);
	}

	.title {
		font-size: 14px;
		color: var(--text);
	}

	.content {
		font-size: 13px;
		line-height: 1.6;
		color: var(--text);
		white-space: pre-wrap;
		word-break: break-word;
	}

	.prose {
		max-height: 60vh;
		overflow-y: auto;
		padding-right: 4px;
	}

	.block {
		border-left: 2px solid var(--line-mid);
		padding: 6px 12px;
		margin: 4px 0;
	}

	.block-label {
		font-size: 9px;
		color: var(--text-dim);
		margin-bottom: 4px;
	}

	.meta {
		display: flex;
		gap: 6px;
		flex-wrap: wrap;
		align-items: baseline;
		font-size: 11px;
		margin-top: 6px;
	}

	.actions {
		display: flex;
		gap: 8px;
		flex-wrap: wrap;
		align-items: center;
		margin-top: 8px;
	}

	/* user-view histogram */
	.hist {
		display: flex;
		gap: 0;
		margin: 6px 0 4px;
		border: 1px solid var(--line-mid);
		clip-path: polygon(
			6px 0,
			100% 0,
			100% calc(100% - 6px),
			calc(100% - 6px) 100%,
			0 100%,
			0 6px
		);
	}

	.hist-cell {
		flex: 1;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		padding: 10px 8px 8px;
		gap: 2px;
		background: rgba(184, 107, 58, 0.04);
		border-right: 1px solid var(--line-dim);
	}

	.hist-cell:last-child {
		border-right: none;
	}

	.hist-num {
		font-size: 20px;
		color: var(--scan-hot);
		line-height: 1;
	}

	.hist-lbl {
		font-size: 8px;
		color: var(--text-dim);
		letter-spacing: 0.18em;
	}

	.obs-list {
		list-style: none;
		padding: 0;
		margin: 0;
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.obs {
		padding: 6px 0;
		border-bottom: 1px solid var(--line-dim);
	}

	.obs:last-child {
		border-bottom: none;
	}

	.obs-text {
		font-size: 12px;
		line-height: 1.5;
		color: var(--text);
		margin-bottom: 4px;
		white-space: pre-wrap;
	}

	.obs-button {
		display: block;
		width: 100%;
		padding: 0;
		border: 0;
		background: transparent;
		color: inherit;
		font: inherit;
		text-align: left;
		cursor: pointer;
	}

	.obs-button:hover .obs-text {
		color: var(--hud-hot);
	}

	.obs-meta {
		display: flex;
		gap: 8px;
		font-size: 10px;
	}

	.tags {
		color: var(--scan-mid);
		font-size: 9px;
	}

	.extlink {
		font-size: 11px;
		color: var(--scan-mid);
		padding: 6px 10px;
		border: 1px solid var(--line-dim);
	}

	.extlink:hover {
		color: var(--scan-hot);
		border-color: var(--line-mid);
	}

	.sample {
		padding: 8px 0;
		border-bottom: 1px solid var(--line-dim);
	}

	.sample:last-child {
		border-bottom: none;
	}

	.sample-text {
		font-size: 12px;
		color: var(--text);
		margin-bottom: 4px;
		white-space: pre-wrap;
	}

	.sample-meta {
		font-size: 10px;
	}

	.person-grid {
		display: grid;
		grid-template-columns: 1fr;
		gap: 8px;
	}

	.person-card {
		display: flex;
		flex-direction: column;
		gap: 6px;
		text-align: left;
		text-transform: none;
		letter-spacing: 0;
		padding: 10px 12px;
		background:
			linear-gradient(120deg, rgba(74, 139, 154, 0.07), transparent 44%),
			rgba(7, 9, 15, 0.46);
		border: 1px solid var(--line-dim);
		border-radius: 4px;
		color: var(--text);
		cursor: pointer;
	}

	.person-card:hover {
		border-color: var(--scan-mid);
		background:
			linear-gradient(120deg, rgba(74, 139, 154, 0.12), transparent 48%),
			rgba(7, 9, 15, 0.62);
	}

	.person-top,
	.person-meta {
		display: flex;
		justify-content: space-between;
		gap: 10px;
		align-items: baseline;
	}

	.person-handle {
		font-size: 11px;
		color: var(--scan-hot);
		text-transform: none;
	}

	.person-count {
		font-size: 9px;
		color: var(--text-dim);
		white-space: nowrap;
	}

	.person-summary {
		font-size: 12px;
		line-height: 1.45;
		color: var(--text);
		line-clamp: 3;
		display: -webkit-box;
		-webkit-line-clamp: 3;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}

	.person-meta {
		font-size: 9px;
	}

	@media (max-width: 760px) {
		.drawer {
			width: 100%;
			padding: max(12px, env(safe-area-inset-top)) 16px max(12px, env(safe-area-inset-bottom));
			font-size: 15px;
		}
	}
	@media (prefers-reduced-motion: reduce) {
		.drawer { animation: none; }
	}

	@keyframes slide {
		from {
			transform: translateX(20px);
			opacity: 0;
		}
		to {
			transform: translateX(0);
			opacity: 1;
		}
	}
</style>

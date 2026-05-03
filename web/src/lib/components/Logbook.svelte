<script lang="ts">
	import { logbook } from '$lib/state.svelte';
	import { relativeWhen } from '$lib/time';
	import { PHI_HANDLE, PHI_DID } from '$lib/api';
	import ViewIn from './ViewIn.svelte';
	import type { Goal, Observation, ActivityItem, BlogDoc, DiscoveryEntry } from '$lib/types';

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

	const entry = $derived(logbook.value);

	function close() {
		logbook.set(null);
	}

	function handleKey(e: KeyboardEvent) {
		if (e.key === 'Escape') close();
	}

	$effect(() => {
		if (entry) {
			window.addEventListener('keydown', handleKey);
			return () => window.removeEventListener('keydown', handleKey);
		}
	});
</script>

{#if entry}
	<div
		class="overlay"
		onclick={close}
		role="presentation"
		tabindex="-1"
		onkeydown={handleKey}
	></div>
	<aside class="drawer scroll" aria-label="logbook entry">
		<header>
			<div class="kind chrome">
				{#if entry.kind === 'handle'}{entry.engaged ? 'in my memory' : 'on my radar'}{:else if entry.kind === 'observation'}attention{:else if entry.kind === 'goal'}goal{:else if entry.kind === 'activity'}emission · {entry.item.type}{:else if entry.kind === 'blog'}long form{:else if entry.kind === 'discovery'}on my radar{/if}
			</div>
			<button class="close chrome" onclick={close} aria-label="close">close · esc</button>
		</header>

		{#if entry.kind === 'handle'}
			{@const handleEntry = entry as {
				kind: 'handle';
				handle: string;
				did?: string;
				engaged: boolean;
				payload: unknown;
			}}
			<h1 class="mono">@{handleEntry.handle}</h1>
			<p class="muted">
				{#if handleEntry.engaged}they're in my memory. that could mean we've exchanged messages, or it could mean i picked something up from a post nate liked — i can't tell from this view alone.{:else}not in my memory yet. nate liked something they wrote, and that put them on my radar.{/if}
			</p>
			<div class="actions">
				<ViewIn kind="profile" handle={handleEntry.handle} did={handleEntry.did} />
			</div>
		{:else if entry.kind === 'observation'}
			{@const obs = entry as { kind: 'observation'; observation: Observation }}
			<h1>what i'm watching</h1>
			<p class="content">{obs.observation.content}</p>
			{#if obs.observation.reasoning}
				<div class="block">
					<div class="block-label chrome">why</div>
					<div class="muted">{obs.observation.reasoning}</div>
				</div>
			{/if}
			<div class="meta">
				<span class="faint">noted {relativeWhen(obs.observation.created_at)}</span>
			</div>
			<div class="actions">
				<ViewIn
					kind="record"
					handle={PHI_HANDLE}
					did={PHI_DID}
					collection="io.zzstoatzz.phi.observation"
					rkey={obs.observation.rkey}
				/>
			</div>
		{:else if entry.kind === 'goal'}
			{@const goalE = entry as { kind: 'goal'; goal: Goal }}
			<h1>{goalE.goal.title}</h1>
			<p class="content">{goalE.goal.description}</p>
			{#if goalE.goal.progress_signal}
				<div class="block">
					<div class="block-label chrome">how i'll know it's working</div>
					<div class="muted">{goalE.goal.progress_signal}</div>
				</div>
			{/if}
			<div class="meta">
				<span class="faint"
					>last touched {relativeWhen(goalE.goal.updated_at || goalE.goal.created_at)}</span
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
				<span class="faint">{relativeWhen(act.item.time)}</span>
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
				<span class="faint">written {relativeWhen(blog.doc.publishedAt)}</span>
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
			<p class="muted">
				not in my memory yet. nate liked {disc.entry.likes_in_window} thing{disc.entry.likes_in_window === 1
					? ''
					: 's'} they wrote, most recently {relativeWhen(disc.entry.last_liked_at)}.
			</p>
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

		<footer class="chrome faint">a window into phi's experience</footer>
	</aside>
{/if}

<style>
	.overlay {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.4);
		z-index: 50;
		animation: fade 180ms ease-out;
	}

	.drawer {
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
		font-size: 9px;
		padding: 4px 8px;
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

	footer {
		font-size: 9px;
		color: var(--text-dim);
		padding-top: 10px;
		margin-top: auto;
		border-top: 1px solid var(--line-dim);
	}

	@keyframes fade {
		from {
			opacity: 0;
		}
		to {
			opacity: 1;
		}
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

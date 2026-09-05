<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { logbook } from '$lib/state.svelte';

	let { inline = false }: { inline?: boolean } = $props();

	interface Actor {
		did: string;
		handle: string;
		displayName?: string;
		avatar?: string;
	}

	let open = $state(false);
	let query = $state('');
	let actors = $state<Actor[]>([]);
	let selected = $state(0);
	let searching = $state(false);
	let inputEl = $state<HTMLInputElement | null>(null);

	const TYPEAHEAD = 'https://typeahead.waow.tech/xrpc/app.bsky.actor.searchActorsTypeahead';

	let debounceTimer: ReturnType<typeof setTimeout> | undefined;
	let seq = 0;
	let launcher: HTMLButtonElement | undefined;

	function show() {
		open = true;
		query = '';
		actors = [];
		selected = 0;
		// input mounts on next tick
		setTimeout(() => inputEl?.focus(), 0);
	}

	function hide() {
		open = false;
		launcher?.focus();
	}

	function search(q: string) {
		clearTimeout(debounceTimer);
		if (!q.trim()) {
			actors = [];
			searching = false;
			return;
		}
		searching = true;
		debounceTimer = setTimeout(async () => {
			const mySeq = ++seq;
			try {
				const res = await fetch(`${TYPEAHEAD}?q=${encodeURIComponent(q.trim())}&limit=8`);
				if (!res.ok) return;
				const data: { actors: Actor[] } = await res.json();
				if (mySeq === seq) {
					actors = data.actors;
					selected = 0;
				}
			} catch {
				/* typeahead is best-effort */
			} finally {
				if (mySeq === seq) searching = false;
			}
		}, 150);
	}

	function pick(actor: Actor) {
		hide();
		logbook.set({
			kind: 'handle',
			handle: actor.handle,
			did: actor.did,
			engaged: true,
			payload: { handle: actor.handle, did: actor.did }
		});
	}

	function handleGlobalKey(e: KeyboardEvent) {
		if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
			e.preventDefault();
			open ? hide() : show();
		}
	}

	function handlePaletteKey(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			e.stopPropagation();
			hide();
		} else if (e.key === 'ArrowDown') {
			e.preventDefault();
			selected = Math.min(selected + 1, actors.length - 1);
		} else if (e.key === 'ArrowUp') {
			e.preventDefault();
			selected = Math.max(selected - 1, 0);
		} else if (e.key === 'Enter' && actors[selected]) {
			pick(actors[selected]);
		}
	}

	onMount(() => {
		window.addEventListener('keydown', handleGlobalKey);
	});
	onDestroy(() => {
		if (typeof window !== 'undefined') window.removeEventListener('keydown', handleGlobalKey);
	});
</script>

<!-- launcher chip: keyboard hint on desktop, tap target on mobile -->
<button
	bind:this={launcher}
	class="launcher"
	class:inline
	onclick={show}
	aria-label="search who phi knows"
>
	<span class="key mono">⌘K</span>
	<span class="lbl">Look up a person</span>
</button>

{#if open}
	<div class="veil" onclick={hide} role="presentation"></div>
	<div
		class="palette cut"
		role="dialog"
		aria-label="find a person"
		tabindex="-1"
		onkeydown={handlePaletteKey}
	>
		<div class="search-row">
			<span class="prompt mono">&gt;</span>
			<input
				bind:this={inputEl}
				bind:value={query}
				oninput={() => search(query)}
				placeholder="handle or name — anyone on the network"
				spellcheck="false"
				autocomplete="off"
			/>
			<button class="dismiss chrome" onclick={hide} aria-label="Close search">close</button>
		</div>
		{#if query.trim()}
			<ul class="results" role="listbox">
				{#if actors.length === 0}
					<li class="empty mono">{searching ? 'scanning…' : 'nobody found'}</li>
				{:else}
					{#each actors as actor, i (actor.did)}
						<li>
							<button
								class="result"
								class:active={i === selected}
								role="option"
								aria-selected={i === selected}
								onclick={() => pick(actor)}
								onmouseenter={() => (selected = i)}
							>
								{#if actor.avatar}
									<img class="avatar" src={actor.avatar} alt="" loading="lazy" />
								{:else}
									<span class="avatar placeholder"></span>
								{/if}
								<span class="name">{actor.displayName || actor.handle}</span>
								<span class="handle mono">@{actor.handle}</span>
							</button>
						</li>
					{/each}
				{/if}
			</ul>
		{:else}
			<div class="empty mono">
				type to search the network — pick a person to see what phi remembers
			</div>
		{/if}
	</div>
{/if}

<style>
	.launcher {
		position: fixed;
		top: 18px;
		left: 50%;
		transform: translateX(-50%);
		z-index: 11;
		display: flex;
		align-items: center;
		gap: 8px;
		background: var(--bg-panel);
		backdrop-filter: blur(8px);
		-webkit-backdrop-filter: blur(8px);
		border: 1px solid var(--line-mid);
		padding: 6px 12px;
		font-size: 10px;
		letter-spacing: 0.12em;
		color: var(--text-mid);
	}
	.launcher.inline {
		position: static;
		transform: none;
		min-height: 48px;
		font-family: var(--font-chrome);
		font-size: 17px;
		letter-spacing: 0;
		border-radius: 0;
		padding: 12px 16px;
	}
	.launcher:hover {
		color: var(--hud-hot);
		border-color: var(--hud-mid);
	}
	.launcher .key {
		font-size: 10px;
		color: var(--scan-mid);
		border: 1px solid var(--line-dim);
		padding: 1px 5px;
	}

	.veil {
		position: fixed;
		inset: 0;
		z-index: 40;
		background: rgba(7, 9, 15, 0.75);
		backdrop-filter: blur(2px);
		-webkit-backdrop-filter: blur(2px);
	}

	.palette {
		position: fixed;
		z-index: 41;
		top: 16vh;
		left: 50%;
		transform: translateX(-50%);
		width: min(560px, calc(100vw - 28px));
		background: var(--bg-elev);
		border: 1px solid var(--line-mid);
	}

	.search-row {
		display: flex;
		align-items: center;
		gap: 10px;
		padding: 12px 14px;
		border-bottom: 1px solid var(--line-dim);
	}
	.prompt {
		color: var(--hud-mid);
		font-size: 13px;
	}
	input {
		flex: 1;
		background: transparent;
		border: none;
		outline: none;
		color: var(--text);
		font-family: var(--font-mono);
		font-size: 14px;
	}
	input::placeholder {
		color: var(--text-dim);
	}
	.results {
		list-style: none;
		margin: 0;
		padding: 6px;
		max-height: 320px;
		overflow-y: auto;
	}
	.result {
		display: flex;
		align-items: center;
		gap: 10px;
		width: 100%;
		text-align: left;
		background: transparent;
		border: 1px solid transparent;
		padding: 8px 10px;
		cursor: pointer;
		text-transform: none;
		letter-spacing: normal;
	}
	.result.active {
		border-color: var(--line-mid);
		background: rgba(184, 107, 58, 0.08);
	}
	.avatar {
		width: 24px;
		height: 24px;
		border-radius: 50%;
		object-fit: cover;
		border: 1px solid var(--line-dim);
		flex-shrink: 0;
	}
	.avatar.placeholder {
		display: inline-block;
		background: var(--bg-deep);
	}
	.name {
		font-family: var(--font-content);
		font-size: 13px;
		color: var(--text);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.handle {
		font-size: 11px;
		color: var(--scan-mid);
		margin-left: auto;
		flex-shrink: 0;
	}

	.empty {
		padding: 18px 14px;
		font-size: 11px;
		color: var(--text-dim);
	}

	@media (max-width: 760px) {
		.launcher {
			position: relative;
			inset: auto;
			transform: none;
			margin: 0 14px;
			width: calc(100% - 28px);
			min-height: 44px;
			font-size: 13px;
		}
		.launcher .key {
			display: none;
		}
		.palette {
			top: 10vh;
		}
	}
	.dismiss {
		min-height: 44px;
		min-width: 44px;
		flex-shrink: 0;
	}
</style>

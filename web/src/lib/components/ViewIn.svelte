<script lang="ts">
	/**
	 * Open a record in the user's preferred atproto client.
	 *
	 * Inspired by pdsls's record-link pattern
	 * (https://tangled.org/pds.ls/pdsls). Click the favicon to open in the
	 * remembered viewer; click the chevron to switch viewers (choice is
	 * persisted in localStorage per kind).
	 *
	 * If only one viewer is available for the given kind, the chevron is
	 * suppressed.
	 */

	import { onMount, onDestroy } from 'svelte';
	import {
		VIEWERS_BY_KIND,
		defaultViewer,
		setStoredViewer,
		type ViewKind,
		type Viewer
	} from '$lib/clients';

	interface Props {
		kind: ViewKind;
		handle: string;
		did?: string;
		collection?: string;
		rkey?: string;
	}

	let { kind, handle, did, collection, rkey }: Props = $props();

	let chosen = $state<Viewer | null>(null);
	let menuOpen = $state(false);

	const viewers = $derived(VIEWERS_BY_KIND[kind]);

	onMount(() => {
		chosen = defaultViewer(kind);
	});

	function pick(v: Viewer) {
		chosen = v;
		setStoredViewer(kind, v.id);
		menuOpen = false;
	}

	function favicon(domain: string): string {
		// Direct favicon — most clients have one. If it 404s the fallback monogram shows.
		return `https://${domain}/favicon.ico`;
	}

	function monogram(label: string): string {
		return label.slice(0, 2).toUpperCase();
	}

	function onDocClick(e: MouseEvent) {
		const t = e.target as HTMLElement;
		if (t.closest('.viewin-host')) return;
		menuOpen = false;
	}

	$effect(() => {
		if (menuOpen) {
			document.addEventListener('click', onDocClick);
			return () => document.removeEventListener('click', onDocClick);
		}
	});

	onDestroy(() => {
		document.removeEventListener('click', onDocClick);
	});

	const link = $derived(
		chosen ? chosen.url({ handle, did, collection, rkey }) : ''
	);
</script>

{#if chosen}
	<div class="viewin-host">
		<a class="primary" href={link} target="_blank" rel="noopener" title="open in {chosen.label}">
			<span class="favwrap">
				<img
					class="fav"
					src={favicon(chosen.domain)}
					alt=""
					onerror={(e) => {
						(e.currentTarget as HTMLImageElement).style.display = 'none';
						const sib = (e.currentTarget as HTMLImageElement).nextElementSibling as HTMLElement;
						if (sib) sib.style.display = 'flex';
					}}
				/>
				<span class="mono-fb chrome">{monogram(chosen.label)}</span>
			</span>
			<span class="lbl chrome">view in {chosen.label}</span>
			<span class="arrow">↗</span>
		</a>
		{#if viewers.length > 1}
			<button
				class="cycle"
				aria-label="switch viewer"
				onclick={(e) => {
					e.stopPropagation();
					menuOpen = !menuOpen;
				}}>⌃</button
			>
			{#if menuOpen}
				<div class="menu" role="menu">
					{#each viewers as v (v.id)}
						<button
							class="opt"
							class:active={v.id === chosen.id}
							onclick={() => pick(v)}
							role="menuitem"
						>
							<span class="favwrap small">
								<img
									class="fav"
									src={favicon(v.domain)}
									alt=""
									onerror={(e) => {
										(e.currentTarget as HTMLImageElement).style.display = 'none';
										const sib = (e.currentTarget as HTMLImageElement)
											.nextElementSibling as HTMLElement;
										if (sib) sib.style.display = 'flex';
									}}
								/>
								<span class="mono-fb chrome">{monogram(v.label)}</span>
							</span>
							<span class="opt-lbl">{v.label}</span>
							{#if v.id === chosen.id}
								<span class="check">●</span>
							{/if}
						</button>
					{/each}
					<div class="credit chrome">
						chooser modeled after <a href="https://tangled.org/pds.ls/pdsls" target="_blank" rel="noopener">pdsls</a>
					</div>
				</div>
			{/if}
		{/if}
	</div>
{/if}

<style>
	.viewin-host {
		position: relative;
		display: inline-flex;
		align-items: stretch;
	}

	.primary {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		padding: 6px 10px;
		background: var(--bg-elev);
		border: 1px solid var(--line-mid);
		color: var(--text);
		text-decoration: none;
		transition:
			border-color 0.12s,
			color 0.12s;
		font-size: 11px;
		clip-path: polygon(
			5px 0,
			100% 0,
			100% calc(100% - 5px),
			calc(100% - 5px) 100%,
			0 100%,
			0 5px
		);
	}

	.primary:hover {
		color: var(--hud-hot);
		border-color: var(--hud-mid);
	}

	.lbl {
		font-size: 10px;
		letter-spacing: 0.1em;
	}

	.arrow {
		font-size: 11px;
		color: var(--text-dim);
	}

	.cycle {
		padding: 0 8px;
		background: var(--bg-elev);
		border: 1px solid var(--line-mid);
		border-left: none;
		color: var(--text-dim);
		font-family: var(--font-mono);
		font-size: 11px;
		min-height: 32px;
		min-width: 28px;
		cursor: pointer;
		transition:
			color 0.12s,
			border-color 0.12s;
	}

	.cycle:hover {
		color: var(--hud-hot);
		border-color: var(--hud-mid);
	}

	.favwrap {
		position: relative;
		width: 14px;
		height: 14px;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
	}

	.favwrap.small {
		width: 12px;
		height: 12px;
	}

	.fav {
		width: 100%;
		height: 100%;
		object-fit: contain;
		display: block;
	}

	.mono-fb {
		display: none;
		position: absolute;
		inset: 0;
		align-items: center;
		justify-content: center;
		font-size: 8px;
		color: var(--text-dim);
		border: 1px solid var(--line-dim);
	}

	.menu {
		position: absolute;
		top: calc(100% + 4px);
		right: 0;
		background: var(--bg-deep);
		border: 1px solid var(--line-mid);
		min-width: 180px;
		z-index: 60;
		display: flex;
		flex-direction: column;
		padding: 4px;
		animation: fadeIn 120ms ease-out;
	}

	.opt {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 6px 8px;
		background: transparent;
		border: none;
		color: var(--text);
		text-transform: none;
		letter-spacing: 0;
		font-size: 12px;
		font-family: var(--font-content);
		cursor: pointer;
		text-align: left;
	}

	.opt:hover {
		background: rgba(184, 107, 58, 0.06);
		color: var(--hud-hot);
	}

	.opt.active {
		color: var(--hud-hot);
	}

	.check {
		margin-left: auto;
		font-size: 8px;
		color: var(--hud-hot);
	}

	.opt-lbl {
		flex: 1;
	}

	.credit {
		font-size: 8px;
		color: var(--text-dim);
		padding: 6px 8px 4px;
		border-top: 1px solid var(--line-dim);
		margin-top: 2px;
		text-transform: none;
		letter-spacing: 0;
		font-family: var(--font-content);
	}

	.credit a {
		color: var(--text-mid);
	}

	.credit a:hover {
		color: var(--scan-mid);
	}

	@keyframes fadeIn {
		from {
			opacity: 0;
			transform: translateY(-4px);
		}
		to {
			opacity: 1;
			transform: translateY(0);
		}
	}
</style>

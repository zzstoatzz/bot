<script lang="ts">
	import '$lib/reading.css';
	import { onMount } from 'svelte';
	import { Agent } from '@atproto/api';
	import type { OAuthSession } from '@atproto/oauth-client-browser';
	import { initOAuth, OVERRIDE_COLLECTION } from '$lib/operator/oauth';
	import { fetchOverride, OPERATOR_DID, type Override } from '$lib/operator/override';
	import CachePanel from '$lib/components/CachePanel.svelte';
	import ContextBudget from '$lib/components/ContextBudget.svelte';

	let oauth = $state<Awaited<ReturnType<typeof initOAuth>> | null>(null);
	let session = $state<OAuthSession | null>(null);
	let handleInput = $state('');
	let status = $state('');
	let loaded = $state(false);

	// the operator's live override (what the bot actually obeys) — public read
	let live = $state<Override | null>(null);
	// editor state (writes to the signed-in user's OWN repo)
	let active = $state(false);
	let message = $state('');
	let saving = $state(false);

	const isOperator = $derived(session?.did === OPERATOR_DID);

	onMount(async () => {
		live = await fetchOverride();
		// NEVER throw out of init: a failed OAuth init degrades to signed-out.
		try {
			oauth = await initOAuth();
			const result = await oauth.init(); // parses OAuth return params
			if (result?.session) {
				session = result.session;
				await loadOwn();
			}
		} catch (err) {
			console.error('oauth init failed; continuing signed out:', err);
		}
		loaded = true;
	});

	async function loadOwn() {
		if (!session) return;
		const own = await fetchOverride(session.did);
		if (own) {
			active = own.active;
			message = own.message;
		}
	}

	async function signIn(e: SubmitEvent) {
		e.preventDefault();
		if (!oauth || !handleInput.trim()) return;
		status = 'taking you to sign in…';
		try {
			await oauth.signIn(handleInput.trim().replace(/^@/, ''));
		} catch (err) {
			status = `sign in failed: ${String(err)}`;
		}
	}

	async function signOut() {
		if (oauth && session) await oauth.revoke(session.did);
		session = null;
		status = '';
	}

	async function save(e: SubmitEvent) {
		e.preventDefault();
		if (!session) return;
		saving = true;
		status = '';
		try {
			const agent = new Agent(session);
			await agent.com.atproto.repo.putRecord({
				repo: session.did,
				collection: OVERRIDE_COLLECTION,
				rkey: 'self',
				record: {
					$type: OVERRIDE_COLLECTION,
					active,
					message,
					updatedAt: new Date().toISOString()
				}
			});
			status = active ? 'override set — phi will see it within ~60s' : 'override lifted';
			if (isOperator) live = { active, message };
		} catch (err) {
			status = `save failed: ${String(err)}`;
		} finally {
			saving = false;
		}
	}
</script>

<svelte:head><title>Phi · Operator</title></svelte:head>

<main class="reading-page operator-page">
	<div class="reading-inner">
		<header class="page-heading">
			<h1>Operator</h1>
			<span class="mode" class:paused={live?.active}>
				{live ? (live.active ? 'Public actions paused' : 'Public actions enabled') : (loaded ? 'Override status unavailable' : 'Reading status…')}
			</span>
		</header>
		<section class="control-panel" aria-labelledby="control-heading">
		<h2 id="control-heading">Public action control</h2>

		<p class="explainer">
			An active override pauses Phi's public actions and puts your message in her context.
			Phi follows the override on Nate's account. Signing in with another account only lets
			you edit that account's record.
		</p>

		{#if live}
			<div class="live {live.active ? 'live-active' : ''}">
				<span class="live-label">Saved directive</span>
				{#if live.active}
					<strong>Paused</strong>
					<blockquote>{live.message}</blockquote>
				{:else}
					Public actions are enabled. Phi follows her normal policies.
				{/if}
			</div>
		{/if}

		{#if !loaded}
			<div class="status">loading…</div>
		{:else if !session}
			<form onsubmit={signIn} class="login">
				<label for="operator-handle">Your AT Protocol handle</label>
				<input id="operator-handle" type="text" placeholder="e.g. zzstoatzz.io" bind:value={handleInput} />
				<button type="submit">sign in with atproto</button>
			</form>
		{:else}
			<div class="session-row">
				signed in as <code>{session.did}</code>
				{#if !isOperator}
					<span class="warn">
						(not the operator — you can write this record to your own repo, but phi won't obey it)
					</span>
				{/if}
				<button class="linkish" onclick={signOut}>sign out</button>
			</div>

			<form onsubmit={save} class="editor">
				<label class="toggle">
					<input type="checkbox" bind:checked={active} />
					Pause public actions
				</label>
				<label for="override-message">Message to Phi</label>
				<textarea
					id="override-message"
					rows="6"
					placeholder="your message to phi — why the override is on, and how to reach you. shown to her verbatim."
					bind:value={message}
				></textarea>
				<button type="submit" disabled={saving || (active && !message.trim())}>
					{saving ? 'saving…' : 'save override record'}
				</button>
			</form>
		{/if}

		{#if status}
			<div class="status" role="status">{status}</div>
		{/if}

		</section>
		<ContextBudget />
		<CachePanel />
	</div>
</main>

<style>
	.operator-page {
		z-index: 1;
	}
	.mode {
		font: 16px var(--font-chrome);
		color: var(--scan-hot);
		padding: 8px 12px;
		border-left: 2px solid currentColor;
		background: #17333b70;
	}
	.mode.paused {
		color: var(--warn-hot);
		background: #49341c70;
	}
	.explainer {
		color: var(--text-mid);
		max-width: 70ch;
		margin-top: 12px;
	}
	.live {
		border-left: 2px solid var(--scan-hot);
		background: #09141b;
		padding: 16px 20px;
		margin: 20px 0;
	}
	.live-active {
		border-color: var(--warn-hot);
		background: #211b14;
	}
	.live-label {
		display: block;
		color: var(--text-mid);
		font: 14px var(--font-chrome);
		margin-bottom: 6px;
	}
	.live strong {
		color: var(--warn-hot);
	}
	.live blockquote {
		margin: 8px 0 0;
		white-space: pre-wrap;
		overflow-wrap: anywhere;
	}
	.login, .editor {
		display: grid;
		gap: 12px;
		margin-top: 20px;
	}
	.login {
		max-width: 480px;
	}
	.login input, .editor textarea {
		width: 100%;
		min-width: 0;
		box-sizing: border-box;
		font: 15px/1.65 var(--font-content);
		padding: 12px 14px;
		color: var(--text);
		background: #070d14;
		border: 1px solid #47606a;
		border-radius: 0;
		box-shadow: inset 0 2px 8px #0008;
	}
	.editor textarea {
		resize: vertical;
		min-height: 160px;
	}
	.editor textarea:focus-visible {
		outline: 2px solid var(--scan-hot);
		outline-offset: 3px;
	}
	.toggle {
		display: flex;
		align-items: center;
		gap: 12px;
		min-height: 48px;
		color: #f0d8bc;
		font: 22px var(--font-chrome);
		cursor: pointer;
	}
	.toggle input {
		width: 22px;
		height: 22px;
		accent-color: var(--hud-hot);
	}
	.operator-page :global(button) {
		min-height: 44px;
		font: 16px var(--font-chrome);
		padding: 8px 12px;
	}
	.editor button, .login button {
		justify-self: start;
	}
	.session-row {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 8px 12px;
		color: var(--text-mid);
	}
	.session-row code {
		overflow-wrap: anywhere;
		font: 12px var(--font-mono);
		color: var(--scan-hot);
	}
	.warn {
		flex-basis: 100%;
		color: var(--warn-hot);
	}
	.status {
		margin-top: 16px;
		color: var(--scan-hot);
	}
	.operator-page :global(.ctx), .operator-page :global(.cache) {
		margin-top: 0;
		border-top: 0;
		padding: 24px;
	}
	.operator-page :global(.head) {
		flex-wrap: wrap;
		gap: 12px;
	}
	.operator-page :global(.ctx h2), .operator-page :global(.cache h2) {
		font-size: 25px;
		letter-spacing: 0.07em;
	}
	.operator-page :global(.samples) {
		display: block;
		max-width: 100%;
		overflow-x: auto;
	}
	@media (max-width: 760px) {
		.operator-page .page-heading {
			align-items: start;
			flex-direction: column;
			gap: 12px;
		}
		.operator-page :global(.ctx), .operator-page :global(.cache) {
			padding: 20px 16px;
		}
		.live {
			padding: 14px;
		}
		.editor button, .login button {
			width: 100%;
		}
	}
</style>

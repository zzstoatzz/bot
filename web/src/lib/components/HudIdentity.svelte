<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { getHealth, getPhiProfile, PHI_HANDLE, type PhiProfile } from '$lib/api';
	import type { HealthInfo } from '$lib/types';

	let health = $state<HealthInfo | null>(null);
	let profile = $state<PhiProfile | null>(null);
	const bio = $derived(profile?.bio ?? null);
	let healthTimer: ReturnType<typeof setInterval> | null = null;
	let bioTimer: ReturnType<typeof setInterval> | null = null;

	async function pollHealth() {
		try {
			health = await getHealth();
		} catch {
			health = null;
		}
	}

	async function pollBio() {
		profile = (await getPhiProfile()) ?? profile;
	}

	onMount(() => {
		pollHealth();
		pollBio();
		healthTimer = setInterval(pollHealth, 15_000);
		// Bio changes only at phi's startup (rare). 5 min refresh is enough.
		bioTimer = setInterval(pollBio, 5 * 60_000);
	});

	onDestroy(() => {
		if (healthTimer) clearInterval(healthTimer);
		if (bioTimer) clearInterval(bioTimer);
	});

	const status = $derived.by(() => {
		if (!health) return { color: 'var(--text-dim)', label: 'status unavailable', pulse: false };
		if (health.status !== 'healthy')
			return { color: 'var(--danger)', label: 'stalled', pulse: false };
		if (health.paused) return { color: 'var(--warn)', label: 'paused', pulse: true };
		if (health.polling_active) return { color: 'var(--hud-hot)', label: 'online', pulse: false };
		return { color: 'var(--text-dim)', label: 'idle', pulse: false };
	});
</script>

<a class="ident" href="/" aria-label="Phi home">
	<span class="portrait" style="color: {status.color}">
		{#if profile?.avatar}
			<img src={profile.avatar} alt="" width="34" height="34" decoding="async" />
		{:else}
			<span class="initial" aria-hidden="true">ϕ</span>
		{/if}
	</span>
	<div class="meta">
		<div class="name chrome">phi</div>
		<div class="line">
			<span class="dot" style="color: {status.color}" class:pulse={status.pulse}></span>
			<span class="state chrome muted">{status.label}</span>
			<span class="sep">·</span>
			<span class="handle">@{PHI_HANDLE}</span>
		</div>
		{#if bio}
			<div class="bio" title={bio}>{bio}</div>
		{/if}
	</div>
</a>

<style>
	.ident {
		text-decoration: none;
		color: inherit;
		display: flex;
		gap: 12px;
		align-items: center;
	}

	.ident:focus-visible { outline: 2px solid var(--scan-hot); outline-offset: 6px; }

	/* phi's own profile picture; the ring carries her status */
	.portrait {
		display: grid;
		place-items: center;
		flex-shrink: 0;
		width: 34px;
		height: 34px;
		border-radius: 50%;
		overflow: hidden;
		background: #1a232d;
		box-shadow: 0 0 0 1.5px currentColor;
	}
	.portrait img {
		display: block;
		width: 100%;
		height: 100%;
		object-fit: cover;
	}
	.initial {
		font: 400 20px/1 var(--font-content);
		color: var(--hud-hot);
	}

	.meta {
		min-width: 0;
		display: flex;
		flex-direction: column;
		gap: 2px;
	}

	.name {
		font-size: 20px;
		color: var(--hud-hot);
		letter-spacing: 0.18em;
	}

	.dot {
		width: 7px;
		height: 7px;
		border-radius: 50%;
		background: currentColor;
		flex-shrink: 0;
	}

	.line {
		display: flex;
		gap: 6px;
		align-items: center;
		font-size: 10px;
	}

	.state {
		font-size: 12px;
	}

	.sep {
		color: var(--text-dim);
	}

	.handle {
		font-family: var(--font-mono);
		font-size: 10px;
		color: var(--scan-mid);
	}

	.bio {
		font-size: 11px;
		color: var(--text-mid);
		font-style: italic;
		line-height: 1.35;
		max-width: 340px;
		margin-top: 2px;
		cursor: help;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}


	@media (max-width: 760px) {
		.ident {
			gap: 10px;
		}
		.portrait {
			width: 30px;
			height: 30px;
		}
		.meta {
			flex: 1;
			flex-direction: row;
			align-items: baseline;
			justify-content: space-between;
			gap: 12px;
		}
		.name {
			font-size: 19px;
		}
		.state {
			font-size: 13px;
		}
		.sep,
		.handle,
		.bio {
			display: none;
		}
	}
</style>

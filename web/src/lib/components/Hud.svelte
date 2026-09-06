<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import HudIdentity from './HudIdentity.svelte';
	import HudLensCycler from './HudLensCycler.svelte';
	import HudCounts from './HudCounts.svelte';
	import HudReadout from './HudReadout.svelte';

	const LENSES = [
		{ key: 'mind', href: '/', label: 'mind' },
		{ key: 'capabilities', href: '/capabilities', label: 'capabilities', shortLabel: 'tools' },
		{ key: 'market', href: '/market', label: 'market' },
		{ key: 'architecture', href: '/architecture', label: 'architecture', shortLabel: 'system' }
	] as const;

	const current = $derived.by(() => {
		const path = page.url.pathname;
		if (path === '/') return 'mind';
		if (path.startsWith('/capabilities')) return 'capabilities';
		if (path.startsWith('/market')) return 'market';
		if (path.startsWith('/operator')) return 'operator';
		if (path.startsWith('/architecture')) return 'architecture';
		return 'mind';
	});

	function handleKey(e: KeyboardEvent) {
		if (e.target instanceof HTMLInputElement) return;
		if (e.target instanceof HTMLTextAreaElement) return;
		if (e.target instanceof HTMLSelectElement) return;
		if (e.key === '1') goto('/');
		if (e.key === '2') goto('/capabilities');
		if (e.key === '3') goto('/market');
		if (e.key === '4') goto('/architecture');
	}

	onMount(() => {
		window.addEventListener('keydown', handleKey);
	});

	onDestroy(() => {
		if (typeof window !== 'undefined') window.removeEventListener('keydown', handleKey);
	});
</script>

<header class="cockpit-header">
	<div class="identity"><HudIdentity /></div>
	<nav aria-label="Cockpit pages"><HudLensCycler {current} {LENSES} /></nav>
</header>

<div class="hud-bottom">
	<div class="hud hud-br">
		<HudReadout />
	</div>
	{#if current !== 'mind' && current !== 'market'}
		<div class="hud hud-bl"><HudCounts /></div>
	{/if}
</div>

<style>
	.cockpit-header {
		position: fixed;
		z-index: 10;
		inset: 0 0 auto;
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 24px;
		padding: 14px 24px;
		background: linear-gradient(180deg, #18222cef, #090f18fa);
		border-top: 1px solid #71604b;
		border-bottom: 1px solid #3a4b56;
		box-shadow:
			0 4px 0 #060b12,
			0 5px 0 #172633,
			0 10px 26px #00000040;
	}
	.identity {
		min-width: 0;
		max-width: 380px;
	}
	nav {
		flex-shrink: 0;
	}
	@media (max-width: 760px) {
		.cockpit-header {
			display: grid;
			grid-template-columns: minmax(0, 1fr);
			justify-content: stretch;
			gap: 10px;
			padding: 10px 14px 12px;
		}
		.identity {
			min-width: 0;
		}
		nav {
			width: 100%;
		}
	}
	@media (max-width: 360px) {
		.cockpit-header {
			padding-inline: 10px;
		}
	}
</style>

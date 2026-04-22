<script lang="ts">
	import { page } from '$app/state';

	const links = [
		{ href: '/', label: 'phi' },
		{ href: '/feed', label: 'feed' },
		{ href: '/mind', label: 'mind' },
		{ href: '/blog', label: 'blog' },
		{ href: '/discovery', label: 'discovery' },
		{ href: '/skills', label: 'skills' },
		{ href: '/status', label: 'status' }
	];
</script>

<nav>
	<div class="nav-inner">
		{#each links as link (link.href)}
			{@const active =
				link.href === '/' ? page.url.pathname === '/' : page.url.pathname.startsWith(link.href)}
			<a href={link.href} class:active>{link.label}</a>
		{/each}
	</div>
</nav>

<style>
	nav {
		border-bottom: 1px solid var(--border);
		background: var(--bg);
		position: sticky;
		top: 0;
		z-index: 10;
	}

	.nav-inner {
		max-width: 760px;
		margin: 0 auto;
		padding: 12px 20px;
		display: flex;
		gap: 18px;
		font-size: 13px;
		flex-wrap: wrap;
	}

	a {
		color: var(--text-muted);
		text-decoration: none;
	}

	a:hover {
		color: var(--text);
	}

	a.active {
		color: var(--accent-blue);
	}
</style>

<script lang="ts">
	import MemoryGraph from '$lib/components/MemoryGraph.svelte';
</script>

<div class="container">
	<header>
		<h1>mind</h1>
		<p class="muted">
			phi's social memory — handles she's exchanged with, positioned by semantic similarity of her
			observations about them. drag, zoom, hover.
		</p>
	</header>

	<MemoryGraph />

	<section class="future">
		<h2>coming next</h2>
		<ul class="muted">
			<li>per-handle observation browser (search by handle, see what phi knows + citations + ages)</li>
			<li>archive search across past observations and aged-out attention items</li>
		</ul>
	</section>
</div>

<style>
	header {
		margin-bottom: 24px;
	}

	header p {
		max-width: 600px;
		font-size: 13px;
		line-height: 1.5;
	}

	.future {
		margin-top: 32px;
		font-size: 13px;
	}

	.future ul {
		padding-left: 20px;
		line-height: 1.6;
	}

	.future li {
		margin-bottom: 4px;
	}
</style>

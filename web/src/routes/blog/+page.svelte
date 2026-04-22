<script lang="ts">
	import { onMount } from 'svelte';
	import BlogCard from '$lib/components/BlogCard.svelte';
	import { getBlogDocs } from '$lib/api';
	import type { BlogDoc } from '$lib/types';

	let docs = $state<BlogDoc[]>([]);
	let loaded = $state(false);
	let err = $state<string | null>(null);

	onMount(async () => {
		try {
			docs = await getBlogDocs();
		} catch (e) {
			err = (e as Error).message;
		}
		loaded = true;
	});
</script>

<div class="container">
	<header>
		<h1>blog</h1>
		<p class="muted">long-form posts published to greengale.app.</p>
	</header>

	{#if !loaded}
		<p class="faint">loading…</p>
	{:else if err}
		<p class="faint">failed to load: {err}</p>
	{:else if docs.length === 0}
		<p class="faint">no posts yet.</p>
	{:else}
		{#each docs as doc (doc.rkey)}
			<BlogCard {doc} />
		{/each}
	{/if}
</div>

<style>
	header {
		margin-bottom: 24px;
	}
</style>

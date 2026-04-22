<script lang="ts">
	import '../app.css';
	import Nav from '$lib/components/Nav.svelte';

	interface Props {
		children?: import('svelte').Snippet;
	}

	let { children }: Props = $props();
</script>

<Nav />
{@render children?.()}

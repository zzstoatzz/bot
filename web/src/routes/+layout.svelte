<script lang="ts">
	import '../app.css';
	import Hud from '$lib/components/Hud.svelte';

	interface Props {
		children?: import('svelte').Snippet;
	}

	let { children }: Props = $props();
</script>

<div class="cockpit">
	<div class="viewport">
		{@render children?.()}
	</div>
	<Hud />
</div>

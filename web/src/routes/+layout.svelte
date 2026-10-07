<script lang="ts">
	import '@fontsource/saira-condensed/latin-400.css';
	import '@fontsource/saira-condensed/latin-500.css';
	import '@fontsource-variable/inter/wght.css';
	import '../app.css';
	import { onMount } from 'svelte';
	import Hud from '$lib/components/Hud.svelte';
	import OverrideBanner from '$lib/components/OverrideBanner.svelte';

	interface Props {
		children?: import('svelte').Snippet;
	}

	let { children }: Props = $props();

	onMount(() => {
		document.getElementById('boot')?.remove();
		document.getElementById('boot-note')?.remove();
	});
</script>

<div class="cockpit">
	<OverrideBanner />
	<div class="viewport">
		{@render children?.()}
	</div>
	<Hud />
</div>

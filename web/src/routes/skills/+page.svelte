<script lang="ts">
	// skills are static, defined in bot/skills/ at build time. for now we
	// inline the descriptions; later we could expose a backend endpoint that
	// scans the skills/ directory at runtime if the set grows beyond a few.

	const skills = [
		{
			name: 'publish-blog',
			description:
				"Publish a long-form post on greengale.app. Use when a thought needs more space than a bluesky thread — multi-part essays, syntheses of a conversation you've been in, worked examples. For single observations use post instead; for a URL + commentary use note or save_url."
		}
	];
</script>

<div class="container">
	<header>
		<h1>skills</h1>
		<p class="muted">
			progressive-disclosure capability packs phi can load on demand. each is a description (always
			visible to phi) plus a body she pulls in via load_skill when relevant.
		</p>
	</header>

	{#each skills as skill (skill.name)}
		<div class="card">
			<div class="name mono">{skill.name}</div>
			<div class="desc">{skill.description}</div>
		</div>
	{/each}
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

	.card {
		border-left-color: var(--accent-purple);
	}

	.name {
		font-size: 14px;
		color: var(--accent-purple);
		margin-bottom: 8px;
	}

	.desc {
		font-size: 13px;
		line-height: 1.6;
		color: var(--text-muted);
	}
</style>

<script lang="ts">
	import { CAPABILITIES, OPERATOR_ONLY } from '$lib/abilities';

	const sorted = [...CAPABILITIES].sort();
	const total = sorted.length;
	const operatorCount = sorted.filter((n) => OPERATOR_ONLY.has(n)).length;
</script>

<svelte:head>
	<title>phi · capabilities</title>
</svelte:head>

<div class="lens">
	<div class="screen">
		<header>
			<h1 class="chrome">what i can do</h1>
			<p class="line">
				<span class="num mono">{total}</span>
				<span class="lbl">things i can do</span>
				{#if operatorCount > 0}
					<span class="sep">·</span>
					<span class="num mono">{operatorCount}</span>
					<span class="lbl"
						>{operatorCount === 1 ? 'requires' : 'require'} nate's authorization</span
					>
				{/if}
			</p>
		</header>

		<ul class="list">
			{#each sorted as name (name)}
				<li>
					<span class="hex" style="color: var(--hud-mid)"></span>
					<span class="name mono">{name}</span>
					{#if OPERATOR_ONLY.has(name)}
						<span class="op chrome">operator</span>
					{/if}
				</li>
			{/each}
		</ul>
	</div>
</div>

<style>
	.lens {
		position: absolute;
		inset: 0;
		display: flex;
		justify-content: center;
		padding: 84px 32px 64px;
		overflow: hidden;
	}

	.screen {
		position: relative;
		width: 100%;
		max-width: 680px;
		max-height: 100%;
		overflow-y: auto;
		padding: 28px 36px 32px;
		background: var(--bg-deep);
		border: 1px solid var(--line-mid);
		clip-path: polygon(
			14px 0,
			100% 0,
			100% calc(100% - 14px),
			calc(100% - 14px) 100%,
			0 100%,
			0 14px
		);
	}

	/* corner brackets — purely decorative chrome */
	.screen::before,
	.screen::after {
		content: '';
		position: absolute;
		width: 14px;
		height: 14px;
		border-color: var(--hud-mid);
		border-style: solid;
		border-width: 0;
		pointer-events: none;
	}
	.screen::before {
		top: 4px;
		left: 4px;
		border-top-width: 1px;
		border-left-width: 1px;
	}
	.screen::after {
		bottom: 4px;
		right: 4px;
		border-bottom-width: 1px;
		border-right-width: 1px;
	}

	header {
		margin-bottom: 22px;
		padding-bottom: 16px;
		border-bottom: 1px solid var(--line-dim);
	}

	h1 {
		font-size: 24px;
		font-weight: 500;
		margin: 0 0 8px 0;
		color: var(--text);
		letter-spacing: 0.1em;
	}

	.line {
		display: flex;
		gap: 6px;
		flex-wrap: wrap;
		align-items: baseline;
		font-size: 12px;
		color: var(--text-mid);
		margin: 0;
	}

	.num {
		color: var(--scan-hot);
		font-size: 13px;
	}

	.lbl {
		font-size: 12px;
	}

	.sep {
		color: var(--text-dim);
	}

	.list {
		list-style: none;
		padding: 0;
		margin: 0;
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
		gap: 4px 28px;
	}

	li {
		display: flex;
		align-items: center;
		gap: 10px;
		padding: 4px 0;
		font-size: 13px;
	}

	.name {
		color: var(--text);
		font-size: 12px;
	}

	.op {
		font-size: 8px;
		color: var(--warn);
		letter-spacing: 0.18em;
		margin-left: 2px;
	}

	@media (max-width: 640px) {
		.lens {
			padding: 64px 12px 52px;
		}
		.screen {
			padding: 18px 20px 22px;
		}
		h1 {
			font-size: 20px;
		}
		.list {
			grid-template-columns: 1fr;
		}
	}
</style>

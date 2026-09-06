<script lang="ts">
	interface Lens {
		readonly key: string;
		readonly href: string;
		readonly label: string;
		readonly shortLabel?: string;
	}

	interface Props {
		current: string;
		LENSES: readonly Lens[];
	}

	let { current, LENSES }: Props = $props();
</script>

<div class="cycler">
	<div class="row">
		{#each LENSES as lens, i (lens.key)}
			<a
				href={lens.href}
				class="opt chrome"
				class:active={current === lens.key}
				aria-current={current === lens.key ? 'page' : undefined}
			>
				<span class="num">{i + 1}</span>
				<span class="lbl" class:has-short={Boolean(lens.shortLabel)}>{lens.label}</span>
				{#if lens.shortLabel}<span class="short-label">{lens.shortLabel}</span>{/if}
			</a>
		{/each}
	</div>
</div>

<style>
	.cycler {
		filter: drop-shadow(0 3px 2px #00000060);
	}
	.row {
		position: relative;
		isolation: isolate;
		display: flex;
		gap: 1px;
		padding: 1px;
		background: linear-gradient(135deg, #8b8c7e, #4e6570 38%, #293945 65%, #89765b);
		clip-path: polygon(8px 0, 100% 0, 100% calc(100% - 8px), calc(100% - 8px) 100%, 0 100%, 0 8px);
	}
	.row::before {
		content: '';
		position: absolute;
		inset: 1px;
		z-index: -1;
		background: #0b121c;
		clip-path: polygon(7px 0, 100% 0, 100% calc(100% - 7px), calc(100% - 7px) 100%, 0 100%, 0 7px);
	}
	.opt {
		position: relative;
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 8px;
		min-height: 42px;
		padding: 8px 17px;
		font-size: 16px;
		letter-spacing: 0.08em;
		color: #d7d4c8;
		text-decoration: none;
		background: linear-gradient(180deg, #202e3b, #0c1520);
		box-shadow:
			inset 0 1px 0 #ffffff0b,
			inset 0 -2px 0 #00000055;
		transition:
			background 0.12s,
			color 0.12s;
	}
	.opt:first-child {
		clip-path: polygon(7px 0, 100% 0, 100% 100%, 0 100%, 0 7px);
	}
	.opt:last-child {
		clip-path: polygon(0 0, 100% 0, 100% calc(100% - 7px), calc(100% - 7px) 100%, 0 100%);
	}
	.opt:hover {
		color: #fff0dc;
		background: linear-gradient(180deg, #3b3b37, #202628);
	}
	.opt.active {
		color: #24190f;
		background: linear-gradient(180deg, #f0be8d 0%, #dfa06b 45%, #bf804f 100%);
		box-shadow:
			inset 0 1px 0 #fff2d6,
			inset 0 -3px 0 #794c2d;
		text-shadow: 0 1px 0 #ffffff35;
	}
	.opt:focus-visible {
		outline: 0;
		box-shadow:
			inset 0 0 0 2px #c2f1fc,
			inset 0 -3px 0 #7ec0d4;
	}
	.short-label { display: none; }
	.num {
		font: 10px var(--font-mono);
		color: #99acb6;
	}
	.opt.active .num {
		color: #4d3421;
	}
	@media (max-width: 760px) {
		.has-short { display: none; }
		.short-label { display: inline; }
		.row {
			width: 100%;
			display: grid;
			grid-template-columns: repeat(5, minmax(0, 1fr));
		}
		.opt {
			flex: 1;
			min-height: 44px;
			padding: 8px 3px;
			min-width: 0;
			font-size: 13px;
			letter-spacing: 0.06em;
		}
		.num {
			display: none;
		}
	}
	@media (max-width: 360px) {
		.opt {
			font-size: 12px;
			padding-inline: 5px;
			letter-spacing: 0.04em;
		}
	}
</style>

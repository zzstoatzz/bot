<script lang="ts">
	import audit from '$lib/voice-request-audit.json';
	let selected = $state(0);
	const circumference = 2 * Math.PI * 76;
	const arcs = audit.rows.map((row, index) => ({
		...row,
		index,
		share: row.chars / audit.total,
		offset: audit.rows.slice(0, index).reduce((sum, item) => sum + item.chars, 0) / audit.total * circumference
	}));
	const current = $derived(arcs[selected]);
	const number = (n: number) => n.toLocaleString('en-US');
</script>

<section class="voice-audit" id="voice-request" aria-labelledby="voice-request-title">
	<header>
		<p class="eyebrow">A captured failure · Sep 8, 11:58 PM CDT · Sonnet 5</p>
		<h2 id="voice-request-title">Where the voice direction went</h2>
		<p>The request that produced the plays.bot article. Personality and public voice occupied <strong>1.4%</strong> of the visible material.</p>
	</header>
	<div class="breakdown">
		<svg viewBox="0 0 200 200" role="img" aria-label="Captured request by character count: voice 1.4 percent, history 16.7 percent, other instructions 10.6 percent, tools 38.5 percent, conversation 32.8 percent">
			{#each arcs as arc}
				<circle cx="100" cy="100" r="76" fill="none" stroke={arc.color} stroke-width={selected === arc.index ? 23 : 18} stroke-dasharray={`${arc.share * circumference} ${circumference}`} stroke-dashoffset={-arc.offset} transform="rotate(-90 100 100)" opacity={selected === arc.index ? 1 : 0.65} />
			{/each}
			<text x="100" y="96" text-anchor="middle" class="percent">{(current.share * 100).toFixed(1)}%</text>
			<text x="100" y="119" text-anchor="middle" class="unit">of visible characters</text>
		</svg>
		<div class="legend" aria-label="Request sections">
			{#each arcs as arc}
				<button class:chosen={selected === arc.index} aria-pressed={selected === arc.index} onclick={() => selected = arc.index}>
					<span class="swatch" style:background={arc.color}></span><span>{arc.label}</span><strong>{(arc.share * 100).toFixed(1)}%</strong>
				</button>
			{/each}
		</div>
	</div>
	<div class="inspection" aria-live="polite">
		<h3>{current.label} <span>{number(current.chars)} characters</span></h3>
		<p>{current.detail}</p>
		<details>
			<summary>See the breakdown</summary>
			<ul>{#each current.sections as section}<li><span>{section.label}</span><span>{number(section.chars)}</span></li>{/each}</ul>
		</details>
	</div>
	<p class="finding"><strong>The instruction arrived. The output failed.</strong> Removing SELF and stripping most ambient instructions in private trials still produced the familiar review voice. Size alone does not explain the failure.</p>
	<details class="method">
		<summary>Source and counting method</summary>
		<p>This is a fixed historical capture, not the current base-context snapshot below. {number(audit.total)} visible characters: instruction text, conversation content, tool names, descriptions and compact parameter JSON. No duplicated instruction fields, internal Python signatures or unavailable reasoning. These are character shares, not token shares or measures of influence.</p>
		<p>Trace <code>{audit.trace}</code><br />Request <code>{audit.span}</code><br />Captured <time datetime={audit.capturedAt}>{audit.capturedAt}</time></p>
		<p>Full rendered request stays in the local investigation archive; this panel contains counts and labels only.</p>
	</details>
</section>

<style>
	.voice-audit { scroll-margin-top: 130px; margin: 2rem 0; padding: clamp(1.1rem, 3vw, 2rem); background: linear-gradient(140deg, #152632, #0d1821); border: 1px solid #45616b; border-top: 2px solid #d5a574; box-shadow: 0 6px 18px #0005, inset 0 1px #e4c59b12; color: #e5e1d8; }
	.eyebrow { color: #9cb5bc; font: 0.8rem 'JetBrains Mono', monospace; }
	h2, h3 { font-family: 'Saira Condensed', sans-serif; font-weight: 500; color: #f0d1ad; text-shadow: 0 2px 2px #0009; margin: 0; }
	h2 { font-size: 2rem; }
	h3 { font-size: 1.4rem; }
	p { line-height: 1.6; margin: .65rem 0; }
	.breakdown { display: grid; grid-template-columns: minmax(180px, 260px) 1fr; align-items: center; gap: 2rem; margin: 1.5rem 0; }
	svg { width: 100%; overflow: visible; }
	.percent { fill: #f0d1ad; font: 30px 'Saira Condensed', sans-serif; }
	.unit { fill: #b6c7ca; font: 8px 'JetBrains Mono', monospace; }
	.legend { display: grid; gap: .35rem; }
	button { display: grid; grid-template-columns: 8px 1fr auto; align-items: center; gap: .8rem; padding: .8rem; text-align: left; background: transparent; color: inherit; font: inherit; border: 1px solid transparent; cursor: pointer; min-height: 48px; }
	button.chosen { background: #263640; border-color: #758a91; }
	button:hover { background: #22313b; }
	button:focus-visible, summary:focus-visible { outline: 2px solid #f4b77f; outline-offset: 3px; }
	.swatch { width: 8px; height: 20px; }
	button strong { font: 1rem 'JetBrains Mono', monospace; }
	.inspection { border-top: 1px solid #45616b; padding-top: 1rem; }
	h3 span { color: #a7bec6; font: .85rem 'JetBrains Mono', monospace; margin-left: .75rem; white-space: nowrap; }
	summary { cursor: pointer; color: #a0d9e6; padding: .6rem 0; }
	ul { list-style: none; padding: 0; max-height: 280px; overflow: auto; }
	li { display: flex; justify-content: space-between; gap: 1rem; padding: .45rem 0; border-bottom: 1px solid #45616b44; font-size: .85rem; overflow-wrap: anywhere; }
	.finding { margin-top: 1.4rem; }
	.method { margin-top: .8rem; color: #b6c7ca; font-size: .85rem; }
	code { overflow-wrap: anywhere; }
	@media(max-width: 600px) { .breakdown { grid-template-columns: 1fr; gap: .5rem; } svg { max-width: 210px; margin: auto; } h2 { font-size: 1.65rem; } h3 span { display: block; margin: .25rem 0; } button { font-size: .9rem; gap: .55rem; padding: .7rem .35rem; } }
</style>

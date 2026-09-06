<script lang="ts">
	import { onMount } from 'svelte';
	import { getArchitecture, type Architecture, type Component } from '$lib/architecture';
	let model = $state<Architecture | null>(null);
	let error = $state('');
	let loading = $state(false);
	let lens = $state('all');
	let selected = $state('agent');
	let query = $state('');
	const lenses = [{id:'all', label:'Whole system'}, {id:'memory', label:'Memory & context'}, {id:'delivery', label:'Public delivery'}, {id:'source', label:'Python source'}];
	const lanes = ['Wake & discover', 'Persistent material', 'Think & act', 'Control & observe'];
	const visible = $derived(model?.nodes.filter(n => lens === 'all' || lens === 'source' || n.tags.includes(lens)) ?? []);
	const active = $derived(model?.nodes.find(n => n.id === selected));
	const connections = $derived(model?.edges.filter(e => e.source === selected || e.target === selected) ?? []);
	const modules = $derived(model?.modules.filter(m => `${m.name} ${m.imports.join(' ')}`.toLowerCase().includes(query.toLowerCase())) ?? []);
	const packages = $derived([...new Set(modules.map(m => m.package))]);
	async function refresh() {
		if (loading) return;
		loading = true; error = '';
		try { model = await getArchitecture(); } catch (e) { error = e instanceof Error ? e.message : 'Could not load the architecture'; } finally { loading = false; }
	}
	function chooseLens(id: string) { lens = id; if (id !== 'all' && id !== 'source' && !active?.tags.includes(id)) selected = id === 'memory' ? 'memory' : 'judge'; }
	function inspect(id: string) {
		selected = id;
		if (window.matchMedia('(max-width:600px)').matches) requestAnimationFrame(() => document.querySelector('.inspector')?.scrollIntoView({block:'start'}));
	}
	function related(id: string) { return id === selected || connections.some(e => e.source === id || e.target === id); }
	function label(id: string) { return model?.nodes.find(n => n.id === id)?.label ?? id; }
	function wire(a: Component, b: Component) {
		const forward = b.lane >= a.lane;
		const x1 = a.lane * 250 + (forward ? 226 : 24), x2 = b.lane * 250 + (forward ? 24 : 226);
		const y1 = a.row * 94 + 46, y2 = b.row * 94 + 46;
		const bend = Math.max(35, Math.abs(x2 - x1) * .45);
		return `M ${x1} ${y1} C ${x1 + (forward ? bend : -bend)} ${y1}, ${x2 - (forward ? bend : -bend)} ${y2}, ${x2} ${y2}`;
	}
	onMount(refresh);
</script>

<svelte:head><title>Architecture · Phi</title><meta name="description" content="Inspect Phi's architecture: context, memory, tools, external services and source dependencies." /></svelte:head>

<main class="architecture-page">
	<div class="page-heading">
		<div><h1>Architecture</h1><p>The machinery around a thought.</p></div>
		<button class="refresh" onclick={refresh} disabled={loading}>{loading ? 'Reading source…' : 'Refresh model'}</button>
	</div>
	<nav class="lenses" aria-label="Architecture views">{#each lenses as l}<button class:chosen={lens === l.id} aria-pressed={lens === l.id} onclick={() => chooseLens(l.id)}>{l.label}</button>{/each}</nav>
	{#if error}<p class="error" role="alert">{error}. {model ? 'Showing the last successful model.' : 'Use Refresh model to retry.'}</p>{/if}
	{#if model}
		<div class="model-note"><span class="signal"></span>Source-backed model <span>·</span> {model.nodes.length} components <span>·</span> {model.modules.length} Python modules <span class="timestamp">Read {new Date(model.generatedAt).toLocaleTimeString([], {hour:'numeric', minute:'2-digit'})}</span></div>
		{#if lens === 'source'}
			<section class="source-view">
				<h2>Inside the Python packages</h2><p>Discovered from the running release. Imports show code dependencies, not the sequence of a run.</p>
				<label class="search">Find a module or import<input bind:value={query} type="search" placeholder="agent, memory, core.policy…" /></label>
				<div class="source-grid">{#each packages as pkg}<section class="package"><h3>{pkg === 'root' ? 'bot' : `bot/${pkg}`}</h3>{#each modules.filter(m => m.package === pkg) as m}<details><summary>{m.name.replace('bot.', '')}</summary><a href={`https://github.com/zzstoatzz/bot/blob/main/${m.path}`} target="_blank" rel="noreferrer">Open source ↗</a><p>{m.imports.length ? 'Imports within bot' : 'No imports within bot'}</p>{#each m.imports as dependency}<button class="import" onclick={() => query = dependency}>{dependency}</button>{/each}<small>{m.functions.length} functions / classes indexed</small></details>{/each}</section>{/each}</div>
				{#if !modules.length}<p>No modules match “{query}”.</p>{/if}
			</section>
		{:else}
			<div class="workspace">
				<section class="schematic" aria-label="Architecture components">
					<div class="lane-headings">{#each lanes as name}<h2>{name}</h2>{/each}</div>
					<div class="drawing">
						<svg viewBox="0 0 1000 666" preserveAspectRatio="none" aria-hidden="true"><defs><marker id="flow-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,1 L7,4 L0,7" fill="none" stroke="currentColor" /></marker></defs>
							{#each model.edges as edge}{@const a = visible.find(n => n.id === edge.source)}{@const b = visible.find(n => n.id === edge.target)}{#if a && b}<path d={wire(a,b)} class:hot={edge.source === selected || edge.target === selected} class:future={edge.planned} marker-end="url(#flow-arrow)" />{/if}{/each}
						</svg>
						{#each visible as node}<button class="component" class:active={selected === node.id} class:dim={!related(node.id)} class:planned={node.status === 'planned'} style={`--column:${node.lane};--row:${node.row}`} onclick={() => selected = node.id} aria-pressed={selected === node.id}><span class="component-title">{node.label}</span><span class="component-summary">{node.summary}</span>{#if node.status === 'planned'}<span class="future-label">Unconnected</span>{/if}</button>{/each}
					</div>
					<div class="mobile-components">{#each lanes as lane,i}<details open={i === 2}><summary>{lane}</summary><div>{#each visible.filter(n=>n.lane===i) as node}<button class:active={node.id===selected} onclick={()=>inspect(node.id)}><strong>{node.label}</strong><span>{node.summary}</span>{#if node.status==='planned'}<em>Unconnected</em>{/if}</button>{/each}</div></details>{/each}</div>
					<div class="legend"><span>→ Direction of material or control</span><span class="dashed">┄ Planned connection</span><span>Select a component to trace its neighbors</span></div>
				</section>
				{#if active}<aside class="inspector" aria-live="polite" aria-label="Selected component">
					<button class="back-to-map" onclick={()=>document.querySelector('.schematic')?.scrollIntoView({block:'start'})}>← Components</button><div class="inspector-heading"><small>{active.status === 'planned' ? 'Unconnected work' : 'Component inspection'}</small><h2>{active.label}</h2></div>
					<p>{active.details}</p>
					{#if active.id === 'agent'}<dl><dt>Main model</dt><dd>{model.configuration.main}</dd><dt>Memory helpers</dt><dd>{model.configuration.memory}</dd></dl>{/if}
					{#if active.id === 'judge'}<dl><dt>Policy model</dt><dd>{model.configuration.policy}</dd><dt>Etiquette version</dt><dd>{model.configuration.etiquette}</dd></dl><a href="/operator">Inspect judgments ↗</a>{/if}
					{#if active.id === 'prefect'}<p class="config">Prefect authentication {model.configuration.prefect ? 'configured' : 'not configured'}; connectivity is not checked here.</p>{/if}
					{#if active.id === 'semble'}<p class="config">Semble writes {model.configuration.semble ? 'configured' : 'not configured'}; connectivity is not checked here.</p>{/if}
					<h3>Connections</h3><ul class="connections">{#each connections as edge}{@const incoming=edge.target===selected}{@const neighbor=incoming?edge.source:edge.target}<li><button onclick={()=>inspect(neighbor)}><span>{incoming?'← From':'→ To'} {label(neighbor)}</span><small>{edge.label}{edge.planned?' · not connected':''}</small></button></li>{/each}</ul>
					<h3>Source references</h3><ul class="sources">{#each active.sources as ref}<li><a href={ref.url} target="_blank" rel="noreferrer">{ref.repo === 'bot' ? '' : `${ref.repo}/`}{ref.path}{ref.symbol ? ` · ${ref.symbol}` : ''} ↗</a><small>{ref.evidence}{ref.line ? ` · line ${ref.line}` : ''}</small></li>{/each}</ul>
				</aside>{/if}
			</div>
		{/if}
		<details class="construction"><summary>How this model stays accurate</summary><p><a href="/api/architecture" target="_blank" rel="noreferrer">Open model JSON ↗</a> · <a href="https://github.com/zzstoatzz/bot/blob/main/docs/architecture-map.md" target="_blank" rel="noreferrer">Maintenance guide ↗</a></p><p>{model.basis} Semantic connections are reviewed in a versioned manifest; tests check its references. This is an architecture model, not a live execution trace.</p><p>The atlas maps remembered material. This page maps the components that produce, store, retrieve and act on that material. Phi does not yet maintain this model automatically.</p><div class="inventory"><section><h3>{model.entryPoints.length} entry points</h3>{#each model.entryPoints as entry}<a href={`https://github.com/zzstoatzz/bot/blob/main/src/bot/agent.py#L${entry.line}`}>{entry.name}</a>{/each}</section><section><h3>{model.promptBlocks.length} context functions</h3>{#each model.promptBlocks as entry}<a href={`https://github.com/zzstoatzz/bot/blob/main/src/bot/agent.py#L${entry.line}`}>{entry.name}</a>{/each}</section><section><h3>{model.skills.length} runtime skills</h3>{#each model.skills as skill}<a href={`https://github.com/zzstoatzz/bot/blob/main/skills/${skill}/SKILL.md`}>{skill}</a>{/each}</section></div></details>
	{:else if loading}<div class="loading" role="status">Reading the system model…</div>{/if}
</main>

<style>
	.architecture-page{height:100%;overflow:auto;padding:104px 28px 90px;color:var(--text);scrollbar-color:var(--scan-dim) transparent}
	.page-heading{display:flex;justify-content:space-between;align-items:center;gap:18px;max-width:1600px;margin:auto}
	h1{font:400 38px var(--font-chrome);letter-spacing:.06em;margin:0;color:var(--hud-hot)}
	.page-heading p{margin:2px 0 18px;color:var(--text-mid);font-size:14px}
	.back-to-map{display:none}
	button{font:inherit;color:inherit;cursor:pointer}button:focus-visible,a:focus-visible,summary:focus-visible,input:focus-visible{outline:2px solid var(--scan-hot);outline-offset:3px}
	.refresh,.lenses button{background:#101c27;border:1px solid #344753;padding:10px 16px;min-height:42px}.refresh:disabled{opacity:.6;cursor:wait}
	.lenses{display:flex;gap:6px;flex-wrap:wrap;max-width:1600px;margin:8px auto 16px}.lenses .chosen{border-color:var(--hud-hot);background:#352820;color:#f4ceb1}
	.model-note{max-width:1600px;margin:0 auto 14px;display:flex;gap:9px;align-items:center;color:var(--text-dim);font:11px var(--font-mono);flex-wrap:wrap}.signal{height:6px;width:6px;border:1px solid var(--scan-hot);display:inline-block;transform:rotate(45deg)}.timestamp{margin-left:auto}
	.workspace{display:grid;grid-template-columns:minmax(0,1fr) 310px;gap:18px;max-width:1600px;margin:auto;align-items:start}
	.schematic{background:linear-gradient(135deg,#101d28e8,#0b141fe8);border:1px solid #304451;border-top:2px solid #637c82;box-shadow:inset 0 1px #142d3a;min-width:0}
	.lane-headings{display:grid;grid-template-columns:repeat(4,1fr);padding:12px 0 0}.lane-headings h2{font:400 16px var(--font-chrome);color:#b9c9c9;padding:0 8%;margin:0}
	.drawing{position:relative;aspect-ratio:1000/666;background:repeating-linear-gradient(90deg,transparent 0,transparent calc(25% - 1px),#21323d65 calc(25% - 1px),#21323d65 25%)}
	svg{position:absolute;inset:0;width:100%;height:100%;overflow:visible;color:var(--scan-mid)}svg>path{fill:none;stroke:#38515c;stroke-width:1;opacity:.25}svg>path.hot{stroke:var(--scan-hot);stroke-width:1.8;opacity:.9}svg>path.future{stroke-dasharray:6 5}
	.component{text-transform:none;letter-spacing:normal;position:absolute;left:calc(var(--column)*25% + 2.4%);top:calc(var(--row)*14.114% + 2.2%);width:20.2%;height:10%;padding:6px 9px;text-align:left;border:1px solid #3c5866;border-left:2px solid #638c97;background:linear-gradient(135deg,#192c38,#111c28);box-shadow:0 3px 0 #060d13;display:flex;flex-direction:column;justify-content:center;gap:3px;transition:opacity .15s,border-color .15s}
	.component-title{font:500 clamp(12px,1.1vw,18px) var(--font-chrome);line-height:1.1;color:#d2e1e0}.component-summary{font-size:clamp(9px,.72vw,12px);line-height:1.25;color:#aabcc2}.component.dim{opacity:.82}.component.active{border-color:var(--hud-hot);background:linear-gradient(135deg,#503727,#242326);box-shadow:0 3px #080d13,inset 0 1px #b2815650;opacity:1}.component.active .component-title{color:#ffdbb8}.component.planned{border-style:dashed}.future-label{color:var(--warn);font:9px var(--font-mono)}
	.legend{display:flex;gap:14px;flex-wrap:wrap;border-top:1px solid #2d424d;padding:12px;color:var(--text-dim);font-size:10px}.dashed{color:var(--warn)}
	.inspector{background:#101b25;border:1px solid #354953;border-top:2px solid var(--hud-mid);padding:19px;min-width:0}.inspector-heading small{color:var(--hud-hot);font:11px var(--font-mono)}.inspector h2{font:400 29px var(--font-chrome);line-height:1.1;margin:10px 0 18px}.inspector p{font-size:12px;line-height:1.7;color:#c0c7c8}.inspector h3{font:500 18px var(--font-chrome);color:#a5c2cc;margin:24px 0 9px}.inspector dl{font-size:11px;overflow-wrap:anywhere}.inspector dt{color:var(--text-dim);margin-top:9px}.inspector dd{margin:3px 0;font-family:var(--font-mono)}
	.connections,.sources{list-style:none;padding:0;margin:0}.connections li+li{border-top:1px solid #273a46}.connections button{text-transform:none;letter-spacing:normal;border:0;background:none;text-align:left;width:100%;padding:9px 0;display:flex;flex-direction:column;gap:3px;font-size:12px}.connections button span{color:var(--scan-hot)}.connections small,.sources small{color:var(--text-dim);font-size:10px;display:block}.sources li{margin-bottom:12px;overflow-wrap:anywhere}a{color:var(--scan-hot);text-decoration:none}a:hover{text-decoration:underline}.sources a{font:10px var(--font-mono)}
	.construction,.source-view{max-width:1600px;margin:20px auto;background:#101923;border:1px solid #293e4a;padding:18px}.construction summary{cursor:pointer;color:var(--scan-hot)}.construction p,.source-view p{max-width:80ch;color:var(--text-mid)}.inventory{display:grid;grid-template-columns:repeat(3,1fr);gap:25px}.inventory a{display:block;font:11px/1.9 var(--font-mono);overflow-wrap:anywhere}.inventory h3,.source-view h2,.package h3{font:400 22px var(--font-chrome)}
	.search{display:flex;flex-direction:column;gap:6px;max-width:480px;margin:20px 0}.search input{background:#09121b;border:1px solid #3b5462;color:var(--text);padding:12px;font:inherit}.source-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px}.package{min-width:0}.package h3{color:var(--hud-hot);border-bottom:1px solid #38505d;padding-bottom:8px}.package details{border-bottom:1px solid #243641;padding:8px 0;font:11px var(--font-mono);overflow-wrap:anywhere}.package summary{cursor:pointer;padding:4px 0}.package small{display:block;color:var(--text-dim);margin:9px 0}.import{display:block;border:0;background:none;color:var(--scan-hot);padding:4px 0;text-align:left;font:inherit}.loading{padding:70px;text-align:center;color:var(--scan-hot)}.error{color:var(--warn);max-width:1600px;margin:auto}.mobile-components{display:none}
	@media(max-width:1000px){.workspace{grid-template-columns:1fr}.inspector{display:block}.drawing{max-height:none}.component-title{font-size:16px}.component-summary{font-size:11px}.source-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
	@media(max-width:600px){.back-to-map{display:block;background:none;border:0;padding:0 0 16px;color:var(--scan-hot)}.inspector,.schematic{scroll-margin-top:145px}.architecture-page{padding:146px 16px 80px}.page-heading{align-items:start}h1{font-size:32px}.page-heading p{font-size:12px}.refresh{font-size:11px;padding:8px}.lenses button{flex:1 1 40%;padding:9px 6px;font-size:12px}.timestamp{margin-left:0;width:100%}.drawing,.lane-headings{display:none}.mobile-components{display:block;padding:8px 14px}.mobile-components summary{font:400 21px var(--font-chrome);color:#a8c6cc;cursor:pointer;padding:12px 0}.mobile-components details+details{border-top:1px solid #2c414c}.mobile-components details>div{display:grid;grid-template-columns:1fr 1fr;gap:8px;padding-bottom:12px}.mobile-components button{text-transform:none;letter-spacing:normal;background:#152633;border:1px solid #385666;text-align:left;padding:12px;min-height:80px;display:flex;flex-direction:column;gap:5px}.mobile-components button.active{border-color:var(--hud-hot);background:#3a2c24}.mobile-components strong{font:500 18px/1.1 var(--font-chrome)}.mobile-components span{font-size:11px;color:var(--text-mid)}.mobile-components em{font-size:10px;color:var(--warn)}.legend{font-size:10px}.inventory,.source-grid{grid-template-columns:1fr}.inspector{padding:18px}.model-note{font-size:10px}}
	@media(prefers-reduced-motion:reduce){.component{transition:none}}
</style>

<script lang="ts">
	import { onMount } from 'svelte';
	import { getArchitecture, type Architecture } from '$lib/architecture';
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
		requestAnimationFrame(() => document.querySelector('.focus-map')?.scrollIntoView({block:'start'}));
	}
	function label(id: string) { return model?.nodes.find(n => n.id === id)?.label ?? id; }
	const incoming = $derived(connections.filter(e => e.target === selected));
	const outgoing = $derived(connections.filter(e => e.source === selected));
	onMount(refresh);
</script>

<svelte:head><title>Architecture · Phi</title><meta name="description" content="Inspect Phi's architecture: context, memory, tools, external services and source dependencies." /></svelte:head>

<main class="architecture-page">
	<div class="page-heading">
		<div><h1>Architecture</h1><p>Follow what reaches Phi, what she uses, and what happens next.</p></div>
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
			<section class="system-index" aria-label="Architecture components">
				{#each lanes as lane,i}<section class="subsystem"><h2>{lane}</h2><div class="component-list">
					{#each visible.filter(n=>n.lane===i) as node}<button class="component" class:active={node.id===selected} class:planned={node.status==='planned'} aria-pressed={node.id===selected} onclick={()=>inspect(node.id)}><span>{node.label}</span>{#if node.status==='planned'}<small>Unconnected</small>{/if}</button>{/each}
				</div></section>{/each}
			</section>
			<div class="focus-map" aria-label="Selected component and its connections">
				<section class="flow-side inputs"><h2>Inputs <span>→</span></h2><p class="flow-caption">What reaches this component</p>
					{#each incoming as edge}<button class="connection" class:planned={edge.planned} onclick={()=>inspect(edge.source)}><strong>{label(edge.source)}</strong><span>{edge.label}</span>{#if edge.planned}<small>Not connected</small>{/if}</button>{/each}
					{#if !incoming.length}<p class="empty">No incoming connections in this model.</p>{/if}
				</section>
				{#if active}<aside class="inspector" aria-live="polite" aria-label="Selected component">
					<button class="back-to-map" onclick={()=>document.querySelector('.system-index')?.scrollIntoView({block:'start'})}>↑ All components</button><div class="inspector-heading"><small>{active.status === 'planned' ? 'Unconnected work' : 'Component inspection'}</small><h2>{active.label}</h2></div>
					<p>{active.details}</p>
					{#if active.id === 'agent'}<dl><dt>Main model</dt><dd>{model.configuration.main}</dd><dt>Memory helpers</dt><dd>{model.configuration.memory}</dd></dl>{/if}
					{#if active.id === 'judge'}<dl><dt>Policy model</dt><dd>{model.configuration.policy}</dd><dt>Etiquette version</dt><dd>{model.configuration.etiquette}</dd></dl><a href="/operator">Inspect judgments ↗</a>{/if}
					{#if active.id === 'prefect'}<p class="config">Prefect authentication {model.configuration.prefect ? 'configured' : 'not configured'}; connectivity is not checked here.</p>{/if}
					{#if active.id === 'semble'}<p class="config">Semble writes {model.configuration.semble ? 'configured' : 'not configured'}; connectivity is not checked here.</p>{/if}
					<details class="source-references"><summary>Source references ({active.sources.length})</summary><ul class="sources">{#each active.sources as ref}<li><a href={ref.url} target="_blank" rel="noreferrer">{ref.repo === 'bot' ? '' : `${ref.repo}/`}{ref.path}{ref.symbol ? ` · ${ref.symbol}` : ''} ↗</a><small>{ref.evidence}{ref.line ? ` · line ${ref.line}` : ''}</small></li>{/each}</ul></details>
				</aside>{/if}
				<section class="flow-side outputs"><h2><span>→</span> Outputs</h2><p class="flow-caption">Where it sends material or control</p>
					{#each outgoing as edge}<button class="connection" class:planned={edge.planned} onclick={()=>inspect(edge.target)}><strong>{label(edge.target)}</strong><span>{edge.label}</span>{#if edge.planned}<small>Not connected</small>{/if}</button>{/each}
					{#if !outgoing.length}<p class="empty">No outgoing connections in this model.</p>{/if}
				</section>
			</div>
		{/if}
		<details class="construction"><summary>How this model stays accurate</summary><p><a href="/api/architecture" target="_blank" rel="noreferrer">Open model JSON ↗</a> · <a href="https://github.com/zzstoatzz/bot/blob/main/docs/architecture-map.md" target="_blank" rel="noreferrer">Maintenance guide ↗</a></p><p>{model.basis} Semantic connections are reviewed in a versioned manifest; tests check its references. This is an architecture model, not a live execution trace.</p><p>The atlas maps remembered material. This page maps the components that produce, store, retrieve and act on that material. Phi does not yet maintain this model automatically.</p><div class="inventory"><section><h3>{model.entryPoints.length} entry points</h3>{#each model.entryPoints as entry}<a href={`https://github.com/zzstoatzz/bot/blob/main/src/bot/agent.py#L${entry.line}`}>{entry.name}</a>{/each}</section><section><h3>{model.promptBlocks.length} context functions</h3>{#each model.promptBlocks as entry}<a href={`https://github.com/zzstoatzz/bot/blob/main/src/bot/agent.py#L${entry.line}`}>{entry.name}</a>{/each}</section><section><h3>{model.skills.length} runtime skills</h3>{#each model.skills as skill}<a href={`https://github.com/zzstoatzz/bot/blob/main/skills/${skill}/SKILL.md`}>{skill}</a>{/each}</section></div></details>
	{:else if loading}<div class="loading" role="status">Reading the system model…</div>{/if}
</main>

<style>
	.architecture-page{container-type:inline-size;height:100%;overflow:auto;padding:104px 28px 90px;color:var(--text);scrollbar-color:var(--scan-dim) transparent}
	.page-heading{display:flex;justify-content:space-between;align-items:center;gap:18px;max-width:1600px;margin:auto}
	h1{font:400 38px var(--font-chrome);letter-spacing:.06em;margin:0;color:var(--hud-hot)}
	.page-heading p{margin:2px 0 18px;color:var(--text-mid);font-size:14px}
	button{font:inherit;color:inherit;cursor:pointer}button:focus-visible,a:focus-visible,summary:focus-visible,input:focus-visible{outline:2px solid var(--scan-hot);outline-offset:3px}
	.refresh,.lenses button{background:#101c27;border:1px solid #344753;padding:10px 16px;min-height:42px}.refresh:disabled{opacity:.6;cursor:wait}
	.lenses{display:flex;gap:6px;flex-wrap:wrap;max-width:1600px;margin:8px auto 16px}.lenses .chosen{border-color:var(--hud-hot);background:#352820;color:#f4ceb1}
	.model-note{max-width:1600px;margin:0 auto 14px;display:flex;gap:9px;align-items:center;color:var(--text-dim);font:11px var(--font-mono);flex-wrap:wrap}.signal{height:6px;width:6px;border:1px solid var(--scan-hot);display:inline-block;transform:rotate(45deg)}.timestamp{margin-left:auto}

	.system-index{max-width:1500px;margin:auto;display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,12rem),1fr));gap:0;background:#0e1a24;border:1px solid #354c59;border-top:2px solid #73939c;scroll-margin-top:150px}
	.subsystem{padding:20px;min-width:0}.subsystem+.subsystem{border-left:1px solid #30434e}.subsystem h2{font:400 1.35rem/1.3 var(--font-chrome);margin:0 0 14px;color:#9fc6cf}
	.component-list{display:flex;flex-direction:column;gap:2px}.component{text-transform:none;letter-spacing:normal;display:flex;align-items:baseline;justify-content:space-between;flex-wrap:wrap;gap:4px 8px;text-align:left;background:transparent;border:1px solid transparent;border-left:2px solid #304956;padding:9px 10px;min-height:44px;font:400 1.1rem/1.4 var(--font-chrome);overflow-wrap:anywhere}.component:hover{background:#1b303c;border-color:#527987}.component.active{color:#ffdbb8;background:#3c2d24;border-color:#dc9d6a}.component small{font:0.65rem/1.4 var(--font-mono);color:#dab568}.component.planned{border-left-style:dashed}
	.focus-map{max-width:1500px;margin:32px auto 0;display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.3fr) minmax(0,1fr);gap:40px;align-items:start;scroll-margin-top:150px}
	.flow-side{min-width:0}.flow-side h2{font:400 1.6rem/1.3 var(--font-chrome);color:#b9d5dc;margin:0}.flow-side h2 span{color:#7bb4c2}.inputs h2{display:flex;justify-content:space-between}.flow-caption{color:#9facb1;font-size:0.8rem;line-height:1.5;margin:4px 0 18px}
	.connection{text-transform:none;letter-spacing:normal;position:relative;width:100%;display:flex;flex-direction:column;gap:6px;background:#11222e;border:1px solid #375664;border-left:3px solid #719aa5;padding:16px;text-align:left;margin:0 0 12px;overflow-wrap:anywhere}.connection strong{font:400 1.3rem/1.3 var(--font-chrome);color:#d6e3e4}.connection span{font-size:0.85rem;line-height:1.5;color:#adbdc4}.connection:hover{background:#1a3341;border-color:#a3d0db}.connection small{font:0.7rem var(--font-mono);color:#dab568}.connection.planned{border-style:dashed}.empty{color:#a6b5bb;font-size:0.85rem;line-height:1.6}
	.inspector{min-width:0;background:linear-gradient(135deg,#26303a,#121d29);border:1px solid #a67651;border-top:3px solid #e5a46f;padding:26px;box-shadow:0 8px 24px #0003}.back-to-map{display:block;background:none;border:0;padding:0;margin:0 0 22px;color:#9bc4d1;font:0.75rem var(--font-mono);text-transform:none;letter-spacing:normal}.inspector-heading small{color:#d5ad89;font:0.75rem/1.5 var(--font-mono)}.inspector h2{font:400 2rem/1.15 var(--font-chrome);color:#ffdbb8;margin:10px 0 20px;overflow-wrap:anywhere}.inspector p{font-size:0.95rem;line-height:1.75;color:#d1d7d9}.inspector dl{font-size:0.8rem;overflow-wrap:anywhere;border-top:1px solid #45505a;margin-top:24px;padding-top:10px}.inspector dt{color:#aab9bf;margin-top:14px}.inspector dd{margin:6px 0;font:0.75rem/1.6 var(--font-mono)}
	.source-references{margin-top:26px;border-top:1px solid #45505a;padding-top:18px}.source-references summary{cursor:pointer;color:#a7cbd7;font-size:0.85rem}.sources{list-style:none;padding:0;margin:16px 0 0}.sources li{margin-bottom:16px;overflow-wrap:anywhere}.sources small{display:block;color:#a5b4ba;font-size:0.7rem;margin-top:5px}.sources a{font:0.75rem/1.6 var(--font-mono)}a{color:var(--scan-hot);text-decoration:none}a:hover{text-decoration:underline}
	.construction,.source-view{max-width:1600px;margin:20px auto;background:#101923;border:1px solid #293e4a;padding:18px}.construction summary{cursor:pointer;color:var(--scan-hot)}.construction p,.source-view p{max-width:80ch;color:var(--text-mid)}.inventory{display:grid;grid-template-columns:repeat(3,1fr);gap:25px}.inventory a{display:block;font:11px/1.9 var(--font-mono);overflow-wrap:anywhere}.inventory h3,.source-view h2,.package h3{font:400 22px var(--font-chrome)}
	.search{display:flex;flex-direction:column;gap:6px;max-width:480px;margin:20px 0}.search input{background:#09121b;border:1px solid #3b5462;color:var(--text);padding:12px;font:inherit}.source-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px}.package{min-width:0}.package h3{color:var(--hud-hot);border-bottom:1px solid #38505d;padding-bottom:8px}.package details{border-bottom:1px solid #243641;padding:8px 0;font:11px var(--font-mono);overflow-wrap:anywhere}.package summary{cursor:pointer;padding:4px 0}.package small{display:block;color:var(--text-dim);margin:9px 0}.import{display:block;border:0;background:none;color:var(--scan-hot);padding:4px 0;text-align:left;font:inherit}.loading{padding:70px;text-align:center;color:var(--scan-hot)}.error{color:var(--warn);max-width:1600px;margin:auto}

	@media(max-width:1100px){.subsystem{padding:14px}.focus-map{gap:20px}.inspector{padding:20px}.source-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
	@media(max-width:800px){.system-index{grid-template-columns:repeat(2,minmax(0,1fr))}.subsystem:nth-child(3){border-left:0}.subsystem:nth-child(n+3){border-top:1px solid #30434e}.focus-map{grid-template-columns:repeat(2,minmax(0,1fr))}.inspector{grid-column:1/-1;grid-row:1}.inputs{grid-column:1}.outputs{grid-column:2}.page-heading{align-items:start}.timestamp{margin-left:0}.architecture-page{padding-top:155px}}
	@media(max-width:480px){.architecture-page{padding:155px 16px 80px}.page-heading{flex-wrap:wrap;gap:0}.refresh{margin-bottom:16px}.subsystem{padding:12px}.subsystem h2{font-size:1.2rem}.component{padding:8px 6px}.focus-map{grid-template-columns:1fr;gap:24px}.inputs,.outputs{grid-column:1}.inventory,.source-grid{grid-template-columns:1fr}.lenses button{flex:1 1 40%;padding:9px 6px}.model-note{font-size:10px}.construction{padding:14px}}
	@container(max-width:48rem){.focus-map{grid-template-columns:repeat(2,minmax(0,1fr))}.inspector{grid-column:1/-1;grid-row:1}.inputs{grid-column:1}.outputs{grid-column:2}}
	@container(max-width:30rem){.focus-map{grid-template-columns:1fr}.inputs,.outputs{grid-column:1}}
</style>

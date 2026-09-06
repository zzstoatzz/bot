<script lang="ts">
 import { onMount } from 'svelte';
 import { getToolUsage, type ToolUsage } from '$lib/tool-usage';
 let data = $state<ToolUsage | null>(null);
 let error = $state(''); let loading = $state(false); let filter = $state('unused'); let query = $state('');
 const rows = $derived(data?.tools.filter(t => t.name.includes(query) && (filter === 'all' || (filter === 'unused' ? t.requests > 0 && t.calls === 0 : t.requests === 0 && t.calls === 0))) ?? []);
 async function refresh() {
  if (loading) return; loading = true;
  try { data = await getToolUsage(); error = ''; } catch (e) { error = e instanceof Error ? e.message : 'Tool usage unavailable'; } finally { loading = false; }
 }
 onMount(() => { void refresh(); const timer = setInterval(() => { if (!document.hidden) void refresh(); }, 60000); return () => clearInterval(timer); });
</script>
<section class="tool-usage">
 <header><h2>Tool use</h2><button onclick={refresh} disabled={loading}>{loading ? 'Reading…' : 'Refresh'}</button></header>
 <p>Which tools reached model requests, and which Phi invoked. Low use is a reason to investigate, not a quota to fill.</p>
 {#if error}<p role="alert">{error}. {data ? 'Showing the previous read.' : ''}</p>{/if}
 {#if data}
  <p class="muted">Rolling {data.windowDays} days. {data.since ? `Observed since ${new Date(data.since).toLocaleString()}.` : 'Waiting for the first observed model request.'} Earlier use is unknown.</p>
  <nav aria-label="Tool use filters">{#each [{id:'unused',label:'Offered, unused'}, {id:'unseen',label:'Not observed'}, {id:'all',label:'All tools'}] as choice}<button class:chosen={filter===choice.id} aria-pressed={filter===choice.id} onclick={()=>filter=choice.id}>{choice.label}</button>{/each}</nav>
  <label>Find a tool<input type="search" bind:value={query} placeholder="search_memory, query_traces…" /></label>
  <p class="muted">Request counts mean a tool definition was included, not that the model understood it. Remote tools not yet discovered are absent. Calls inside a code-mode tool are not counted individually.</p>
  <div class="tools">{#each rows as row}<article><h3>{row.name}</h3><dl><div><dt>Requests</dt><dd>{row.requests}</dd></div><div><dt>Runs</dt><dd>{row.runs}</dd></div><div><dt>Calls</dt><dd>{row.calls}</dd></div><div><dt>Raised</dt><dd>{row.raised}</dd></div></dl><small>{row.lastCalled ? `Last invoked ${new Date(row.lastCalled).toLocaleString()}` : row.requests ? 'Offered but no invocation recorded' : 'No exposure or invocation observed'}</small>{#if row.unfinished}<small>{row.unfinished} invocation(s) without a recorded completion</small>{/if}</article>{/each}</div>
  {#if !rows.length}<p>No tools match this view.</p>{/if}
  <details><summary>Recent invocations and traces ({data.recent.length})</summary><p>“Returned” includes refusals and text errors. “Raised” means execution threw; neither proves whether an external side effect occurred.</p>{#each data.recent as call}<article class="invocation"><strong>{call.name}</strong><span>{call.outcome} · {new Date(call.at).toLocaleString()}</span>{#if call.url}<a href={call.url} target="_blank" rel="noreferrer">Inspect trace ↗</a>{:else}<small>Trace link unavailable</small>{/if}</article>{/each}</details>
 {:else if !error}<p>Loading tool observations…</p>{/if}
</section>
<style>
 .tool-usage{border-top:1px solid #345361;padding-block:1.5rem}header{display:flex;align-items:center;justify-content:space-between;gap:12px}h2{margin:0}p{max-width:80ch;line-height:1.6}.muted,small{color:#afbdc2;font-size:.85rem}button{background:#142632;color:#dce6e8;border:1px solid #466575;padding:10px 14px;cursor:pointer;font:inherit}button.chosen{border-color:#dca36d;background:#392d25}nav{display:flex;flex-wrap:wrap;gap:8px}label{display:flex;flex-direction:column;gap:8px;margin:18px 0;max-width:480px}input{padding:12px;background:#0b1721;border:1px solid #466575;color:inherit;font:inherit}.tools{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,260px),1fr));gap:12px}article{padding:16px;background:#10212d;border:1px solid #345361;min-width:0}h3{font:400 1.2rem var(--font-chrome);margin:0 0 12px;color:#9bc8d4;overflow-wrap:anywhere}dl{display:flex;flex-wrap:wrap;gap:12px 24px;margin:0 0 12px}dt{font-size:.75rem;color:#afbdc2}dd{margin:4px 0;font-family:var(--font-mono)}small{display:block}details{margin-top:24px}summary{cursor:pointer;color:#9bc8d4}.invocation{display:flex;flex-wrap:wrap;gap:8px 20px;margin-top:8px;overflow-wrap:anywhere}.invocation span{color:#afbdc2}a{color:#9bc8d4}button:focus-visible,input:focus-visible,summary:focus-visible{outline:2px solid #e6ad78;outline-offset:3px}
</style>

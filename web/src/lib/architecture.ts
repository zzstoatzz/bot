// Boundary contract for /api/architecture. No inferred health or runtime execution edges.
function record(v: unknown): Record<string, unknown> {
	if (!v || typeof v !== 'object' || Array.isArray(v)) throw new Error('Invalid architecture record');
	return Object.fromEntries(Object.entries(v));
}
function text(v: unknown): string { if (typeof v !== 'string') throw new Error('Invalid architecture text'); return v; }
function integer(v: unknown): number { if (typeof v !== 'number' || !Number.isInteger(v) || v < 0) throw new Error('Invalid architecture coordinate'); return v; }
function flag(v: unknown): boolean { if (typeof v !== 'boolean') throw new Error('Invalid architecture flag'); return v; }
function list<T>(v: unknown, parse: (item: unknown) => T): T[] { if (!Array.isArray(v)) throw new Error('Invalid architecture list'); return v.map(parse); }
function symbol(v: unknown) { const d = record(v); return { name: text(d.name), line: integer(d.line) }; }
function source(v: unknown) {
	const d = record(v); const url = text(d.url);
	if (!url.startsWith('https://github.com/zzstoatzz/')) throw new Error('Unexpected source host');
	return {path: text(d.path), symbol: text(d.symbol), repo: text(d.repo), evidence: text(d.evidence), url, line: d.line === null ? null : integer(d.line)};
}
function component(v: unknown) {
	const d = record(v); const lane = integer(d.lane); const row = integer(d.row); const status = text(d.status);
	if (lane > 3 || row > 6 || !['implemented', 'planned'].includes(status)) throw new Error('Invalid component placement');
	return {id: text(d.id), label: text(d.label), lane, row, summary: text(d.summary), details: text(d.details), status, tags: list(d.tags, text), sources: list(d.sources, source)};
}
export function parseArchitecture(v: unknown) {
	const d = record(v); const c = record(d.configuration);
	const nodes = list(d.nodes, component);
	const edges = list(d.edges, (v) => { const e = record(v); return {source: text(e.source), target: text(e.target), label: text(e.label), planned: flag(e.planned)}; });
	const ids = new Set(nodes.map(n => n.id));
	if (ids.size !== nodes.length || edges.some(e => !ids.has(e.source) || !ids.has(e.target))) throw new Error('Architecture contains broken references');
	return {nodes, edges, generatedAt: text(d.generated_at), basis: text(d.basis),
		modules: list(d.modules, v => { const m = record(v); return {name: text(m.name), path: text(m.path), package: text(m.package), imports: list(m.imports, text), functions: list(m.functions, symbol)}; }),
		entryPoints: list(d.entry_points, symbol), promptBlocks: list(d.prompt_blocks, symbol), skills: list(d.skills, text),
		configuration: {main: text(c.main_model), policy: text(c.policy_model), memory: text(c.memory_model), etiquette: text(c.etiquette), prefect: flag(c.prefect_authenticated), semble: flag(c.semble_writes_configured)}
	};
}
export type Architecture = ReturnType<typeof parseArchitecture>;
export type Component = Architecture['nodes'][number];
export async function getArchitecture(): Promise<Architecture> {
	const response = await fetch('/api/architecture', {cache: 'no-store', signal: AbortSignal.timeout(20_000)});
	if (!response.ok) throw new Error(`Architecture unavailable (${response.status})`);
	return parseArchitecture(await response.json());
}

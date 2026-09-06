function record(value: unknown): Record<string, unknown> {
 if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('Invalid tool usage response');
 return Object.fromEntries(Object.entries(value));
}
function text(value: unknown): string { if (typeof value !== 'string') throw new Error('Invalid tool name'); return value; }
function count(value: unknown): number { if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 0) throw new Error('Invalid tool count'); return value; }
function list(value: unknown): unknown[] { if (!Array.isArray(value)) throw new Error('Invalid usage list'); return value; }
function optionalText(value: unknown) { return value === null ? null : text(value); }
export function parseToolUsage(value: unknown) {
 const data = record(value);
 return {
  since: optionalText(data.since), windowDays: count(data.window_days),
  tools: list(data.tools).map(value => { const row = record(value); return {
   name: text(row.name), requests: count(row.requests), runs: count(row.runs), calls: count(row.calls),
   returned: count(row.returned), raised: count(row.raised), unfinished: count(row.unfinished), lastCalled: optionalText(row.last_called)
  }; }),
  recent: list(data.recent).map(value => { const row = record(value); const url = optionalText(row.trace_url);
   if (url && !url.startsWith('https://logfire')) throw new Error('Invalid trace link');
   return {name: text(row.tool), at: text(row.at), outcome: text(row.outcome), trace: text(row.trace), url};
  })
 };
}
export type ToolUsage = ReturnType<typeof parseToolUsage>;
export async function getToolUsage() {
 const response = await fetch('/api/tool-usage', {cache:'no-store', signal:AbortSignal.timeout(15000)});
 if (!response.ok) throw new Error(`Tool usage unavailable (${response.status})`);
 return parseToolUsage(await response.json());
}

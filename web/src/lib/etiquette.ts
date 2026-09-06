// Public /api/etiquette contract. Private drafts and notes never enter this API.
export type EtiquetteAttempt = {
	id: string; at: string; tool: string; outcome: string; policy: string;
	reason: string; documented_at: string | null;
};
export type EtiquetteBoard = {
	version: string; since: string | null; counts: Record<string, number>;
	pending: number; reasons: {policy: string; count: number}[]; recent: EtiquetteAttempt[];
};
function record(value: unknown): Record<string, unknown> {
	if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('Invalid etiquette response');
	return Object.fromEntries(Object.entries(value));
}
function string(value: unknown): string {
	if (typeof value !== 'string') throw new Error('Invalid etiquette text');
	return value;
}
function number(value: unknown): number {
	if (typeof value !== 'number' || !Number.isFinite(value) || value < 0) throw new Error('Invalid etiquette count');
	return value;
}
export function parseEtiquette(value: unknown): EtiquetteBoard {
	const d = record(value);
	if (!Array.isArray(d.reasons)) throw new Error('Invalid etiquette reasons');
	if (!Array.isArray(d.recent)) throw new Error('Invalid etiquette attempts');
	return {
		version: string(d.version), since: d.since === null ? null : string(d.since),
		pending: number(d.pending), reasons: d.reasons.map(value => { const r = record(value); return {policy: string(r.policy), count: number(r.count)}; }),
		counts: Object.fromEntries(Object.entries(record(d.counts)).map(([k, v]) => [k, number(v)])),
		recent: d.recent.map((value) => {
			const a = record(value);
			return {id: string(a.id), at: string(a.at), tool: string(a.tool), outcome: string(a.outcome),
				policy: string(a.policy), reason: string(a.reason), documented_at: a.documented_at === null ? null : string(a.documented_at)};
		})
	};
}
export async function getEtiquette(): Promise<EtiquetteBoard> {
	const r = await fetch('/api/etiquette', { cache: 'no-store', signal: AbortSignal.timeout(15_000) });
	if (!r.ok) throw new Error(`Etiquette unavailable (${r.status})`);
	return parseEtiquette(await r.json());
}

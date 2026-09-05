import type { ChickenTrader, ChickenMarket, ChickenResultRound } from './types';

// Parse the external market once, at the API boundary. Missing season data
// must not silently turn lifetime history into a current-season chart.
function object(value: unknown): Record<string, unknown> {
	if (!value || typeof value !== 'object' || Array.isArray(value))
		throw new Error('Invalid market response');
	return Object.fromEntries(Object.entries(value));
}
function number(value: unknown): number {
	if (typeof value !== 'number' || !Number.isFinite(value))
		throw new Error('Invalid market number');
	return value;
}
function string(value: unknown): string {
	if (typeof value !== 'string') throw new Error('Invalid market text');
	return value;
}
function array(value: unknown): unknown[] {
	if (!Array.isArray(value)) throw new Error('Invalid market list');
	return value;
}
function optionalNumber(value: unknown): number | undefined {
	return value == null ? undefined : number(value);
}
function optionalString(value: unknown): string | undefined {
	return value == null ? undefined : string(value);
}
export function parseTrader(value: unknown): ChickenTrader {
	const v = object(value);
	return {
		did: string(v.did),
		handle: string(v.handle),
		balance_subc: number(v.balance_subc),
		networth_subc: number(v.networth_subc),
		pnl_subc: number(v.pnl_subc),
		season_start: number(v.season_start),
		positions: array(v.positions).map((value) => {
			const p = object(value);
			return {
				round_id: optionalString(p.round_id),
				round: optionalString(p.round),
				contender_did: optionalString(p.contender_did),
				contender_handle: optionalString(p.contender_handle),
				shares: optionalNumber(p.shares),
				avg_price_subc: optionalNumber(p.avg_price_subc),
				cost_subc: optionalNumber(p.cost_subc)
			};
		}),
		trades: array(v.trades).map((value) => {
			const t = object(value);
			const side = string(t.side);
			if (side !== 'buy' && side !== 'sell') throw new Error('Invalid trade side');
			return {
				ts: number(t.ts),
				round_id: string(t.round_id),
				contender_did: string(t.contender_did),
				contender_handle: string(t.contender_handle),
				side,
				shares: number(t.shares),
				price_subc: number(t.price_subc),
				total_subc: number(t.total_subc),
				source: string(t.source)
			};
		}),
		networth_series: array(v.networth_series).map((value) => {
			const pair = array(value);
			return [number(pair[0]), number(pair[1])];
		}),
		past_seasons: array(v.past_seasons).map((value) => {
			const p = object(value);
			return {
				season: number(p.season),
				pnl_subc: number(p.pnl_subc),
				rank: number(p.rank),
				trades: number(p.trades),
				networth_subc: number(p.networth_subc)
			};
		})
	};
}
export function parseMarket(value: unknown): ChickenMarket {
	const v = object(value);
	const s = object(v.season);
	if (typeof s.settling !== 'boolean') throw new Error('Invalid season status');
	const r = v.round == null ? null : object(v.round);
	return {
		season: {
			num: number(s.num),
			day: number(s.day),
			total_days: number(s.total_days),
			start_round: string(s.start_round),
			end_round: string(s.end_round),
			settling: s.settling,
			ends_at: number(s.ends_at)
		},
		round: r
			? {
					id: string(r.id),
					status: string(r.status),
					contenders: array(r.contenders).map((value) => {
						const c = object(value);
						return {
							did: string(c.did),
							handle: string(c.handle),
							likes: number(c.likes),
							p: c.p == null ? null : number(c.p),
							mid_subc: c.mid_subc == null ? null : number(c.mid_subc),
							bid_subc: c.bid_subc == null ? null : number(c.bid_subc),
							ask_subc: c.ask_subc == null ? null : number(c.ask_subc)
						};
					})
				}
			: null
	};
}
export function parseResults(value: unknown): ChickenResultRound[] {
	return array(object(value).rounds).map((value) => {
		const r = object(value);
		return {
			id: string(r.id),
			status: string(r.status),
			winner_did: r.winner_did == null ? '' : string(r.winner_did),
			winner_handle: r.winner_handle == null ? '' : string(r.winner_handle),
			winner_likes: r.winner_likes == null ? 0 : number(r.winner_likes)
		};
	});
}
export function seasonSeries(trader: ChickenTrader): [number, number][] {
	return trader.networth_series
		.filter(([ts]) => ts >= trader.season_start)
		.sort((a, b) => a[0] - b[0]);
}
export function money(value: number, signed = false): string {
	return new Intl.NumberFormat('en-US', {
		style: 'currency',
		currency: 'USD',
		signDisplay: signed ? 'exceptZero' : 'auto'
	}).format(value / 10_000);
}
export function price(value: number): string {
	return `${(value / 100).toLocaleString('en-US', { maximumFractionDigits: 2 })}¢`;
}

export function nearestObservation(series: [number, number][], timestamp: number): number {
	let nearest = 0;
	for (let i = 1; i < series.length; i++) {
		if (Math.abs(series[i][0] - timestamp) < Math.abs(series[nearest][0] - timestamp)) nearest = i;
	}
	return nearest;
}

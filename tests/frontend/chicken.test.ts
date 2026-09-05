import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import {
	parseTrader,
	parseMarket,
	seasonSeries,
	nearestObservation,
	money,
	price
} from '../../web/src/lib/chicken';

const wallet = {
	did: 'did:plc:test',
	handle: 'test.example',
	balance_subc: 10_000_000,
	networth_subc: 10_000_000,
	pnl_subc: 0,
	season_start: 200,
	positions: [],
	trades: [
		{
			ts: 100,
			round_id: '2026-07-02',
			contender_did: 'did:plc:other',
			contender_handle: 'other.example',
			side: 'buy',
			shares: 10,
			price_subc: 42,
			total_subc: 420,
			source: 'atproto'
		}
	],
	networth_series: [
		[100, 18_000_000],
		[200, 10_000_000],
		[220, 10_200_000]
	],
	past_seasons: []
};
test('season chart excludes prior bankroll, while empty holdings stay empty despite historical buys', () => {
	const parsed = parseTrader(wallet);
	assert.deepEqual(seasonSeries(parsed), [
		[200, 10_000_000],
		[220, 10_200_000]
	]);
	assert.deepEqual(parsed.positions, []);
	assert.equal(parsed.trades.length, 1);
});
test('missing reset timestamp is an error, not permission to graph all history', () => {
	assert.throws(() => parseTrader({ ...wallet, season_start: undefined }));
});
test('unpriced contenders do not hide the season', () => {
	const parsed = parseMarket({
		season: {
			num: 11,
			day: 6,
			total_days: 7,
			start_round: '2026-08-31',
			end_round: '2026-09-06',
			settling: false,
			ends_at: 123
		},
		round: {
			id: '2026-09-05',
			status: 'open',
			contenders: [
				{
					did: 'did:plc:other',
					handle: 'other.example',
					likes: 0,
					p: null,
					mid_subc: null,
					bid_subc: null,
					ask_subc: null
				}
			]
		}
	});
	assert.equal(parsed.season.num, 11);
	assert.equal(parsed.round?.contenders[0].ask_subc, null);
});
test('sub-cent quotes and negative currency keep their meaning', () => {
	assert.equal(price(42), '0.42¢');
	assert.equal(money(-282800, true), '-$28.28');
});

test('chart inspection follows time spacing rather than evenly spaced sample indices', () => {
	assert.equal(
		nearestObservation(
			[
				[0, 1],
				[1, 2],
				[100, 3]
			],
			60
		),
		2
	);
	assert.equal(
		nearestObservation(
			[
				[0, 1],
				[1, 2],
				[100, 3]
			],
			-100
		),
		0
	);
	assert.equal(
		nearestObservation(
			[
				[0, 1],
				[1, 2],
				[100, 3]
			],
			500
		),
		2
	);
});

<script lang="ts">
	import '$lib/reading.css';
	import { onMount } from 'svelte';
	import MarketChart from '$lib/components/MarketChart.svelte';
	import { getChickenResults, getChickenMarket, getChickenTrader } from '$lib/api';
	import { money, price, seasonSeries } from '$lib/chicken';
	import type { ChickenResultRound, ChickenMarket, ChickenTrader, ChickenTrade } from '$lib/types';
	let trader = $state<ChickenTrader | null>(null);
	let market = $state<ChickenMarket | null>(null);
	let results = $state<ChickenResultRound[]>([]);
	let loading = $state(true);
	let errors = $state<string[]>([]);
	let updated = $state<Date | null>(null);
	let scope = $state('season');
	let side = $state('all');
	async function refresh() {
		loading = true;
		errors = [];
		const reads = await Promise.allSettled([
			getChickenTrader(),
			getChickenMarket(),
			getChickenResults()
		]);
		const [wallet, season, rounds] = reads;
		trader = wallet.status === 'fulfilled' ? wallet.value : null;
		market = season.status === 'fulfilled' ? season.value : null;
		results = rounds.status === 'fulfilled' ? rounds.value : [];
		errors = reads.flatMap((r) =>
			r.status === 'rejected'
				? [r.reason instanceof Error ? r.reason.message : 'Market data unavailable']
				: []
		);
		updated = new Date();
		loading = false;
	}
	onMount(() => {
		void refresh();
	});
	function date(ts: number, time = false) {
		return new Date(ts * 1000).toLocaleString(
			'en-US',
			time
				? {
						month: 'short',
						day: 'numeric',
						hour: 'numeric',
						minute: '2-digit',
						timeZoneName: 'short'
					}
				: { month: 'short', day: 'numeric', year: 'numeric' }
		);
	}
	function roundDate(id: string) {
		return new Date(`${id}T12:00:00Z`).toLocaleDateString('en-US', {
			month: 'short',
			day: 'numeric',
			timeZone: 'UTC'
		});
	}
	const series = $derived(trader ? seasonSeries(trader) : []);
	const trades = $derived(
		(trader?.trades ?? [])
			.filter(
				(t) =>
					(scope === 'all' || t.ts >= (trader?.season_start ?? Infinity)) &&
					(side === 'all' || t.side === side)
			)
			.toSorted((a, b) => b.ts - a.ts)
	);
	const past = $derived((trader?.past_seasons ?? []).toSorted((a, b) => b.season - a.season));
	function outcome(t: ChickenTrade) {
		const round = results.find((r) => r.id === t.round_id);
		if (round?.winner_did)
			return round.winner_did === t.contender_did
				? 'Selected account won'
				: `Winner: @${round.winner_handle || round.winner_did}`;
		return 'Result unavailable';
	}
</script>

<svelte:head><title>Phi · Market</title></svelte:head>
<main class="reading-page">
	<div class="reading-inner">
		<header class="page-heading">
			<div>
				<p class="eyebrow">Top Chicken · Play money</p>
				<h1>Market</h1>
			</div>
			<button onclick={refresh} disabled={loading}>{loading ? 'Refreshing…' : 'Refresh'}</button>
		</header>
		{#if errors.length}<div class="notice" role="alert">
				{errors.join('. ')}. Refresh to try again.
			</div>{/if}
		{#if loading && !trader}<p class="empty" role="status">Loading the wallet and season…</p>
		{:else if trader}
			<section class="season-summary">
				<div class="section-heading">
					<div>
						<h2>{market ? `Season ${market.season.num}` : 'Current wallet'}</h2>
						<p class="muted">
							{#if market}{roundDate(market.season.start_round)} – {roundDate(
									market.season.end_round
								)} · {market.season.settling
									? 'Settling'
									: `Day ${market.season.day} of ${market.season.total_days}`}{:else}Season details
								unavailable{/if}
						</p>
					</div>
					<a href="https://topchicken.cee.wtf" target="_blank" rel="noreferrer"
						>Open Top Chicken ↗</a
					>
				</div>
				<div class="balance-row">
					<div>
						<p class="muted">Net worth</p>
						<p class="balance">{money(trader.networth_subc)}</p>
						<p class:positive={trader.pnl_subc > 0} class:negative={trader.pnl_subc < 0}>
							{money(trader.pnl_subc, true)} this season
						</p>
					</div>
					<dl class="wallet-details">
						<div>
							<dt>Cash available</dt>
							<dd>{money(trader.balance_subc)}</dd>
						</div>
						<div>
							<dt>Open positions</dt>
							<dd>{trader.positions.length}</dd>
						</div>
						<div>
							<dt>Season trades</dt>
							<dd>
								{trader.trades.filter((t) => t.ts >= (trader?.season_start ?? Infinity)).length}
							</dd>
						</div>
					</dl>
				</div>
				<div class="chart-heading">
					<h3>Net worth this season</h3>
					<span class="muted">Wallet reset {date(trader.season_start)}</span>
				</div>
				<MarketChart {series} />
				<p class="footnote">Earlier seasons are shown separately below.</p>
			</section>
			<section>
				<div class="section-heading">
					<h2>Open positions</h2>
					<span class="muted">From the current wallet</span>
				</div>
				{#if !trader.positions.length}<p class="empty">
						No open positions. Phi’s balance is currently held in cash.
					</p>{:else}<div class="positions">
						{#each trader.positions as p}<article>
								<h3>
									{p.contender_handle
										? `@${p.contender_handle}`
										: (p.contender_did ?? 'Account unavailable')}
								</h3>
								<p>
									{p.shares ?? 'Unknown'} shares · Average price {p.avg_price_subc == null
										? 'unavailable'
										: price(p.avg_price_subc)}
								</p>
								<p class="muted">
									Round {p.round_id ?? p.round ?? 'unavailable'}
								</p>
							</article>{/each}
					</div>{/if}
			</section>
			<section>
				<div class="section-heading">
					<div>
						<h2>Trades</h2>
						<p class="muted">Executed orders, newest first.</p>
					</div>
					<span class="muted">{trades.length} shown</span>
				</div>
				<div class="filters">
					<label
						>Period<select bind:value={scope}
							><option value="season">This season</option><option value="all"
								>All available history</option
							></select
						></label
					><label
						>Action<select bind:value={side}
							><option value="all">Buys and sells</option><option value="buy">Buys</option><option
								value="sell">Sells</option
							></select
						></label
					>
				</div>
				{#if !trades.length}<p class="empty">No trades in this view.</p>{:else}<div
						class="trade-list"
					>
						{#each trades as t}<article class="trade">
								<div class="trade-date">
									<time datetime={new Date(t.ts * 1000).toISOString()}>{date(t.ts, true)}</time
									><span>Round {roundDate(t.round_id)}</span>
								</div>
								<div class="trade-account">
									<a
										href={`https://bsky.app/profile/${t.contender_did}`}
										target="_blank"
										rel="noreferrer">@{t.contender_handle || t.contender_did}</a
									><span
										>{t.side === 'buy' ? 'Bought' : 'Sold'}
										{t.shares.toLocaleString()} shares at {price(t.price_subc)}</span
									>
								</div>
								<div class="trade-total">
									<strong>{money(t.total_subc)}</strong><span
										>{t.side === 'buy' ? 'Paid' : 'Received'}</span
									>
								</div>
								<p class="trade-result">{outcome(t)}</p>
							</article>{/each}
					</div>{/if}
				<p class="footnote">
					Round results describe the winning account, not profit on an individual order. Older
					results may be outside the available history.
				</p>
			</section>
			<section>
				<div class="section-heading">
					<div>
						<h2>Past seasons</h2>
						<p class="muted">Final wallet values, before each reset.</p>
					</div>
				</div>
				{#if past.length}<div class="history">
						{#each past as s}<article>
								<h3>Season {s.season}</h3>
								<p class="return" class:positive={s.pnl_subc > 0} class:negative={s.pnl_subc < 0}>
									{money(s.pnl_subc, true)}
								</p>
								<p>{money(s.networth_subc)} final balance</p>
								<p class="muted">
									Rank {s.rank} · {s.trades}
									{s.trades === 1 ? 'trade' : 'trades'}
								</p>
							</article>{/each}
					</div>{:else}<p class="empty">No completed-season summaries available.</p>{/if}
			</section>
			<footer>
				<p>
					This market predicts the daily most-liked-post winner. A winning share pays $1 in play
					money.
				</p>
				<p>
					{updated
						? `Fetched ${updated.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}.`
						: ''} Market data can be cached for up to a minute.
				</p>
			</footer>
		{:else if !errors.length}<p class="empty">Phi does not have a trading wallet yet.</p>{/if}
	</div>
</main>

<style>
	.season-summary {
		border-top: 0;
		padding-top: 24px;
	}
	.balance-row {
		display: flex;
		justify-content: space-between;
		gap: 28px;
		padding: 24px 0 32px;
	}
	.balance {
		font-family: var(--font-mono);
		font-size: clamp(30px, 5vw, 46px);
		letter-spacing: -0.045em;
		line-height: 1.2;
		margin: 6px 0;
		font-variant-numeric: tabular-nums;
	}
	.wallet-details {
		display: grid;
		gap: 14px;
		min-width: 220px;
		align-content: center;
	}
	.wallet-details div {
		display: flex;
		justify-content: space-between;
		gap: 30px;
	}
	.wallet-details dt {
		font: 16px var(--font-chrome);
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: #a8b0b7;
	}
	.wallet-details dd {
		margin: 0;
		font-variant-numeric: tabular-nums;
	}
	.chart-heading {
		display: flex;
		justify-content: space-between;
		gap: 12px;
		align-items: baseline;
	}

	.filters {
		display: flex;
		gap: 16px;
		margin: 22px 0;
	}
	.filters label {
		display: grid;
		gap: 6px;
		font-size: 13px;
	}
	.filters select {
		min-height: 44px;
	}
	.trade {
		display: grid;
		grid-template-columns: 185px minmax(0, 1fr) 110px;
		gap: 10px 20px;
		padding: 20px 0;
		border-top: 1px solid #28313b;
	}
	.trade-date,
	.trade-account,
	.trade-total {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}
	.trade-date,
	.trade span,
	.trade-result {
		font-size: 13px;
		color: #a8b0b7;
	}
	.trade-total {
		text-align: right;
	}
	.trade-total strong {
		font-size: 16px;
		color: #e9e4da;
		font-variant-numeric: tabular-nums;
	}
	.trade-result {
		grid-column: 2 / 4;
		margin: 0;
	}
	.trade-account a {
		font: 19px var(--font-chrome);
		overflow-wrap: anywhere;
	}
	.history {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 0 28px;
	}
	.history article {
		padding: 22px 0;
		border-bottom: 1px solid #28313b;
	}
	.history p {
		margin: 6px 0;
	}
	.return {
		font: 22px var(--font-mono);
		font-variant-numeric: tabular-nums;
	}
	.positions article {
		padding: 18px 0;
	}
	@media (max-width: 600px) {
		.balance-row {
			display: block;
		}
		.wallet-details {
			margin: 20px 0 0;
			display: grid;
			grid-template-columns: repeat(3, minmax(0, 1fr));
			gap: 12px;
		}
		.wallet-details div {
			display: flex;
			flex-direction: column;
			gap: 6px;
		}
		.wallet-details dt {
			font-size: 14px;
		}
		.wallet-details dd {
			font: 12px var(--font-mono);
		}
		.chart-heading {
			display: block;
		}
		.chart-heading span {
			font-size: 13px;
		}
		.trade {
			grid-template-columns: minmax(0, 1fr) auto;
			gap: 14px;
		}
		.trade-date {
			grid-column: 1 / 3;
			flex-direction: row;
			flex-wrap: wrap;
			justify-content: space-between;
		}
		.trade-result {
			grid-column: 1 / 3;
		}
		.history {
			grid-template-columns: repeat(2, minmax(0, 1fr));
			gap: 0 18px;
		}
		.filters {
			gap: 12px;
		}
		.filters label {
			min-width: 0;
			flex: 1;
		}
		.filters select {
			width: 100%;
		}
	}
</style>

"""Replay a declared Top Chicken policy over settled rounds.

The policy is a small set of parameters. Replay walks each round in fixed
steps, reads every tracked name's chart at that moment, and applies the
policy's cuts, adds and entries in that order. Fills use the chart price at
the step plus the house spread (2%, at least 2 subcents) and a size curve fitted from live
`/api/quote` samples on 2026-11-23: the first $25 fills at the ask, and the
average fill rises to about 1.03x at $50, 1.08x at $100, 1.3x at $250 and
1.9x at $500, the same at every price sampled (0.02¢ to 5.4¢). The curve is
applied in odds space so prices stay below $1. Two corners are rough: below
about 0.05¢ the house filled $500 with no slippage, so the model overcharges
the cheapest names; and nothing above 5.4¢ was sampled, so fills on expensive
names are the least certain.

Scoring is walk-forward. Rounds before the holdout are where a policy gets
tuned; only the holdout says whether it works, and each look at the holdout
spends some of it.
"""

import bisect
import itertools
import math
import statistics
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from bot.core.chicken_history import Round

SPREAD = 0.02
MIN_SPREAD = 0.0002
SUBCENT = 0.0001
SIZE_CURVE = [
    (0.0, 1.0),
    (25.0, 1.0),
    (50.0, 1.027),
    (100.0, 1.08),
    (250.0, 1.30),
    (500.0, 1.90),
]
MAX_FILL_USD = 500.0
STARTING_CASH = 1000.0
RUIN_FLOOR = 500.0
TRADING_OPENS_H = 6.0
TRADING_LOCKS_H = 30.0


class Policy(BaseModel):
    """A declared policy. Hours count from the start of the round's posting day (00:00 UTC); trading runs from hour 6 to the lock at hour 30."""

    rank_by: Literal["likes", "price"] = Field(
        "likes", description="How names are ranked when choosing candidates"
    )
    top_k: int = Field(
        5, ge=1, le=25, description="Only the top K names by rank_by are candidates"
    )
    start_hour: float = Field(8.0, ge=TRADING_OPENS_H, le=TRADING_LOCKS_H)
    end_hour: float = Field(24.0, ge=TRADING_OPENS_H, le=TRADING_LOCKS_H)
    step_minutes: int = Field(10, ge=1, le=240)
    entry_min_price: float = Field(0.0, ge=0, le=1)
    entry_max_price: float = Field(0.05, ge=0, le=1)
    entry_min_likes: int = Field(0, ge=0)
    entry_min_velocity: float = Field(0.0, ge=0, description="likes per hour")
    max_names: int = Field(5, ge=1, le=25)
    stake_usd: float = Field(25.0, gt=0, le=MAX_FILL_USD)
    round_budget_usd: float = Field(150.0, gt=0)
    add_leader_ratio: float | None = Field(
        None,
        gt=1,
        description="Add once to a held name that leads the runner-up's likes by this ratio",
    )
    add_usd: float = Field(0.0, ge=0, le=MAX_FILL_USD)
    add_max_price: float = Field(0.4, ge=0, le=1)
    cut_velocity_below: float | None = Field(
        None, ge=0, description="Sell a held name whose velocity falls below this"
    )
    cut_drawdown: float | None = Field(
        None,
        gt=0,
        lt=1,
        description="Sell a held name whose price falls this fraction below its average fill",
    )

    @model_validator(mode="after")
    def _ordered(self) -> "Policy":
        if self.end_hour <= self.start_hour:
            raise ValueError("end_hour must be after start_hour")
        if self.entry_max_price < self.entry_min_price:
            raise ValueError("entry_max_price must be at least entry_min_price")
        return self


def _size_multiplier(usd: float) -> float:
    for (x0, y0), (x1, y1) in itertools.pairwise(SIZE_CURVE):
        if usd <= x1:
            return y0 + (y1 - y0) * (usd - x0) / (x1 - x0)
    return SIZE_CURVE[-1][1]


def _odds_scale(price: float, factor: float) -> float:
    price = min(max(price, 1e-9), 1 - 1e-9)
    odds = price / (1 - price) * factor
    return odds / (1 + odds)


def buy_fill_price(p: float, usd: float) -> float:
    ask = math.ceil(max(p * (1 + SPREAD), p + MIN_SPREAD) / SUBCENT) * SUBCENT
    return _odds_scale(ask, _size_multiplier(usd))


def sell_fill_price(p: float, usd: float) -> float:
    bid = p * (1 - SPREAD)
    return _odds_scale(bid, 1 / _size_multiplier(usd)) if bid > 0 else 0.0


@dataclass
class Entry:
    round: str
    did: str
    fill_price: float
    market_p: float
    won: bool | None = None


@dataclass
class RoundResult:
    round: str
    pnl: float
    spent: float
    held_winner: bool
    void: bool
    floor_refusals: int
    entries: list[Entry] = field(default_factory=list)


@dataclass
class _Position:
    shares: float = 0.0
    cost: float = 0.0
    added: bool = False


def _state_at(ticks: list[tuple], times: list[int], t: float) -> tuple | None:
    i = bisect.bisect_right(times, t) - 1
    return ticks[i] if i >= 0 else None


def replay_round(policy: Policy, rnd: Round, cash: float) -> tuple[RoundResult, float]:
    """Replay one round from a starting cash balance; return its result and the ending cash."""
    series = [
        (c.did, c.ticks, [tk[0] for tk in c.ticks]) for c in rnd.charts if c.ticks
    ]
    held: dict[str, _Position] = {}
    cut: set[str] = set()
    entries: list[Entry] = []
    spent = 0.0
    refusals = 0
    cash_start = cash

    def buy(did: str, p: float, usd: float) -> bool:
        nonlocal cash, spent, refusals
        if cash - usd < RUIN_FLOOR:
            refusals += 1
            return False
        price = buy_fill_price(p, usd)
        pos = held.setdefault(did, _Position())
        pos.shares += usd / price
        pos.cost += usd
        cash -= usd
        spent += usd
        entries.append(Entry(rnd.id, did, price, p))
        return True

    step = policy.step_minutes * 60
    t = rnd.window_start + policy.start_hour * 3600
    stop = min(rnd.window_start + policy.end_hour * 3600, rnd.lock_at)
    while t <= stop:
        board = {}
        for did, ticks, times in series:
            st = _state_at(ticks, times, t)
            if st is not None:
                board[did] = st
        if board:
            key = 1 if policy.rank_by == "price" else 2
            ranked = sorted(board, key=lambda d: board[d][key], reverse=True)
            for did in list(held):
                pos = held[did]
                _, p, _likes, vel = board.get(did, (0, 0.0, 0, 0.0))
                avg = pos.cost / pos.shares if pos.shares else 0
                slow = (
                    policy.cut_velocity_below is not None
                    and vel < policy.cut_velocity_below
                )
                fell = policy.cut_drawdown is not None and p < avg * (
                    1 - policy.cut_drawdown
                )
                if slow or fell:
                    proceeds = pos.shares * sell_fill_price(p, pos.shares * p)
                    cash += proceeds
                    cut.add(did)
                    del held[did]
            if policy.add_leader_ratio and policy.add_usd and len(ranked) > 1:
                by_likes = sorted(board, key=lambda d: board[d][2], reverse=True)
                lead, runner = by_likes[0], by_likes[1]
                pos = held.get(lead)
                _, p, likes, _ = board[lead]
                if (
                    pos
                    and not pos.added
                    and likes >= policy.add_leader_ratio * max(board[runner][2], 1)
                    and p <= policy.add_max_price
                    and spent + policy.add_usd <= policy.round_budget_usd
                    and buy(lead, p, policy.add_usd)
                ):
                    pos.added = True
            for did in ranked[: policy.top_k]:
                if (
                    len(held) >= policy.max_names
                    or spent + policy.stake_usd > policy.round_budget_usd
                ):
                    break
                if did in held or did in cut:
                    continue
                _, p, likes, vel = board[did]
                if (
                    policy.entry_min_price <= p <= policy.entry_max_price
                    and likes >= policy.entry_min_likes
                    and vel >= policy.entry_min_velocity
                ):
                    buy(did, p, policy.stake_usd)
        t += step

    void = rnd.status == "void"
    for did, pos in held.items():
        if void:
            cash += pos.cost
        elif did == rnd.winner_did:
            cash += pos.shares
    for e in entries:
        e.won = None if void else e.did == rnd.winner_did
    result = RoundResult(
        round=rnd.id,
        pnl=cash - cash_start,
        spent=spent,
        held_winner=not void and rnd.winner_did in held,
        void=void,
        floor_refusals=refusals,
        entries=entries,
    )
    return result, cash


def replay(policy: Policy, rounds: Iterable[Round]) -> list[RoundResult]:
    """Replay every round in order, resetting cash to $1,000 on each Monday round (a new season)."""
    results = []
    cash = STARTING_CASH
    for rnd in rounds:
        if date.fromisoformat(rnd.id).weekday() == 0:
            cash = STARTING_CASH
        result, cash = replay_round(policy, rnd, cash)
        results.append(result)
    return results


@dataclass
class Summary:
    rounds: int
    traded: int
    total_pnl: float
    median_pnl: float
    worst_round: float
    max_drawdown: float
    held_winner_rate: float
    floor_refusals: int
    entries: int
    hit_rate: float
    hit_rate_se: float
    mean_fill: float
    market_log_loss: float | None


def summarize(results: list[RoundResult]) -> Summary:
    traded = [r for r in results if r.spent > 0 and not r.void]
    pnls = [r.pnl for r in results]
    peak = run = dd = 0.0
    for x in pnls:
        run += x
        peak = max(peak, run)
        dd = max(dd, peak - run)
    entries = [e for r in results for e in r.entries if e.won is not None]
    hits = sum(1 for e in entries if e.won)
    n = len(entries)
    hit = hits / n if n else 0.0
    loss = None
    if n:
        loss = -statistics.fmean(
            math.log(min(max(e.market_p if e.won else 1 - e.market_p, 1e-6), 1))
            for e in entries
        )
    return Summary(
        rounds=len(results),
        traded=len(traded),
        total_pnl=sum(pnls),
        median_pnl=statistics.median(pnls) if pnls else 0.0,
        worst_round=min(pnls, default=0.0),
        max_drawdown=dd,
        held_winner_rate=sum(r.held_winner for r in traded) / len(traded)
        if traded
        else 0.0,
        floor_refusals=sum(r.floor_refusals for r in results),
        entries=n,
        hit_rate=hit,
        hit_rate_se=math.sqrt(hit * (1 - hit) / n) if n else 0.0,
        mean_fill=statistics.fmean(e.fill_price for e in entries) if entries else 0.0,
        market_log_loss=loss,
    )


def walk_forward(
    policy: Policy, rounds: Iterable[Round], holdout: int
) -> tuple[Summary, Summary, str]:
    """Replay all rounds once (so season cash carries), then split results at the holdout."""
    results = replay(policy, rounds)
    cut = max(len(results) - holdout, 0)
    first = results[cut].round if cut < len(results) else "none"
    return summarize(results[:cut]), summarize(results[cut:]), first


def _line(label: str, s: Summary) -> str:
    edge = s.hit_rate - s.mean_fill
    ll = f"{s.market_log_loss:.3f}" if s.market_log_loss is not None else "—"
    return (
        f"{label}: {s.rounds} rounds, traded {s.traded}, P&L ${s.total_pnl:,.0f} "
        f"(median ${s.median_pnl:,.0f}, worst ${s.worst_round:,.0f}, max drawdown ${s.max_drawdown:,.0f}), "
        f"held the winner in {s.held_winner_rate:.0%} of traded rounds, {s.floor_refusals} buys refused by the floor. "
        f"{s.entries} entries: hit {s.hit_rate:.1%} ± {s.hit_rate_se:.1%} vs mean fill {s.mean_fill:.1%} "
        f"(edge {edge:+.1%}); market log loss at those entries {ll}"
    )


def report(policy: Policy, rounds: Iterable[Round], holdout: int) -> str:
    tuned, held_out, first = walk_forward(policy, rounds, holdout)
    if held_out.rounds == 0:
        return (
            "no settled rounds are stored yet; the market history hasn't been loaded."
        )
    lines = [
        _line(f"holdout (from {first})", held_out),
        _line("before holdout", tuned),
        "edge is hit rate minus average price paid; it needs to clear about two standard errors before it means much.",
        "a buy fills at the chart price + 2% spread + the size curve; heavy order flow at the time isn't in the history, so busy rounds fill better here than they would live.",
        "only each round's final top 25 have charts, so every candidate here is a name that ended top 25. keep top_k small: the bias is mildest among current leaders.",
    ]
    if held_out.rounds < 30:
        lines.append(
            f"the holdout is {held_out.rounds} rounds; fewer than 30 is not enough to go live on."
        )
    return "\n".join(lines)

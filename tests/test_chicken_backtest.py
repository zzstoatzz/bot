"""Replay of declared chicken policies over stored rounds."""

import pytest
from pydantic import ValidationError

from bot.core import chicken_history
from bot.core.chicken_backtest import (
    Policy,
    buy_fill_price,
    replay,
    replay_round,
    report,
    sell_fill_price,
    walk_forward,
)
from bot.core.chicken_history import Chart, Round

WS = 1_795_132_800  # 2026-11-20 00:00Z, a Friday
H = 3600


def _chart(did: str, points: list[tuple[float, float, int, float]]) -> Chart:
    ticks = [(int(WS + h * H), p, likes, vel) for h, p, likes, vel in points]
    return Chart(did, f"{did}.test", points[-1][2], ticks)


def _round(
    winner: str | None, *charts: Chart, rid: str = "2026-11-20", status: str = "settled"
) -> Round:
    return Round(rid, status, WS, WS + 30 * H, winner, list(charts))


CHEAP_WINNER = _chart("cheap", [(7, 0.02, 40, 10), (20, 0.6, 300, 12)])
FAVORITE = _chart("fav", [(7, 0.6, 100, 5), (20, 0.3, 200, 2)])


# live /api/quote samples from 2026-11-23: (p, dollars, average fill in subcents)
MEASURED_QUOTES = [
    (0.0543, 25, 555),
    (0.0543, 100, 599),
    (0.0543, 250, 717),
    (0.0543, 500, 1024),
    (0.0279, 50, 294),
    (0.0279, 500, 548),
    (0.0125, 250, 168),
    (0.0029, 100, 34),
    (0.0016, 500, 35),
]


@pytest.mark.parametrize(("p", "usd", "avg_subc"), MEASURED_QUOTES)
def test_fill_model_tracks_measured_house_quotes(p, usd, avg_subc):
    assert buy_fill_price(p, usd) * 10000 == pytest.approx(avg_subc, rel=0.06)


def test_fill_model_charges_more_than_the_house_at_the_tick_floor():
    # at 0.01¢ the house ladder has ~$250 rungs and filled $500 at 3 subcents;
    # the model charges its curve anyway, erring against the cheapest names
    assert buy_fill_price(0.0001, 500) * 10000 > 3


def test_fills_stay_below_a_dollar_and_sells_pay_the_spread():
    assert buy_fill_price(0.98, 500) < 1
    assert sell_fill_price(0.05, 25) < 0.05


def test_a_cheap_entry_on_the_winner_pays_out():
    policy = Policy(entry_max_price=0.05, stake_usd=25, start_hour=8, end_hour=9)
    result, cash = replay_round(policy, _round("cheap", CHEAP_WINNER, FAVORITE), 1000)
    assert result.held_winner
    assert len(result.entries) == 1
    assert result.pnl == pytest.approx(25 / buy_fill_price(0.02, 25) - 25)
    assert cash == pytest.approx(1000 + result.pnl)


def test_a_losing_entry_costs_its_stake():
    policy = Policy(entry_max_price=0.05, stake_usd=25, start_hour=8, end_hour=9)
    result, _ = replay_round(policy, _round("fav", CHEAP_WINNER, FAVORITE), 1000)
    assert not result.held_winner
    assert result.pnl == pytest.approx(-25)


def test_a_void_round_refunds_held_positions_at_cost():
    policy = Policy(entry_max_price=0.05, start_hour=8, end_hour=9)
    result, cash = replay_round(policy, _round(None, CHEAP_WINNER, status="void"), 1000)
    assert result.void
    assert result.pnl == 0
    assert cash == 1000
    assert all(e.won is None for e in result.entries)


def test_buys_that_would_breach_the_ruin_floor_are_refused():
    policy = Policy(
        entry_max_price=0.05,
        stake_usd=100,
        round_budget_usd=500,
        start_hour=8,
        end_hour=9,
    )
    result, cash = replay_round(policy, _round("cheap", CHEAP_WINNER), 550)
    assert result.spent == 0
    assert result.floor_refusals > 0
    assert cash == 550


def test_a_cut_sells_and_the_name_is_not_bought_back():
    fading = _chart(
        "fade", [(7, 0.04, 50, 10), (10, 0.01, 55, 0.5), (12, 0.04, 80, 10)]
    )
    policy = Policy(
        entry_max_price=0.05, cut_velocity_below=1, start_hour=8, end_hour=14
    )
    result, _ = replay_round(policy, _round("other", fading), 1000)
    assert len(result.entries) == 1
    assert -25 < result.pnl < 0


def test_add_follows_a_held_name_once_it_leads():
    leader = _chart("lead", [(7, 0.03, 40, 10), (12, 0.2, 400, 30)])
    runner = _chart("run", [(7, 0.5, 100, 5), (12, 0.5, 120, 2)])
    policy = Policy(
        entry_max_price=0.05,
        top_k=2,
        add_leader_ratio=2,
        add_usd=50,
        start_hour=8,
        end_hour=14,
    )
    result, _ = replay_round(policy, _round("lead", leader, runner), 1000)
    assert [round(e.market_p, 2) for e in result.entries] == [0.03, 0.2]


def test_top_k_by_price_follows_the_favorite():
    policy = Policy(
        rank_by="price",
        top_k=1,
        max_names=1,
        entry_min_price=0.4,
        entry_max_price=0.9,
        stake_usd=100,
        start_hour=8,
        end_hour=9,
    )
    result, _ = replay_round(policy, _round("fav", CHEAP_WINNER, FAVORITE), 1000)
    assert [e.did for e in result.entries] == ["fav"]


def test_cash_resets_on_each_monday_round():
    losing = Policy(
        entry_max_price=0.05,
        stake_usd=100,
        round_budget_usd=500,
        max_names=5,
        start_hour=8,
        end_hour=9,
    )
    rounds = [
        _round("fav", CHEAP_WINNER, FAVORITE, rid=d)
        for d in ("2026-11-20", "2026-11-21", "2026-11-22", "2026-11-23")
    ]
    results = replay(losing, rounds)
    assert [r.spent for r in results] == [100, 100, 100, 100]
    assert results[-1].round == "2026-11-23"


def test_walk_forward_scores_the_holdout_apart():
    policy = Policy(entry_max_price=0.05, start_hour=8, end_hour=9)
    rounds = [
        _round("cheap", CHEAP_WINNER, rid=f"2026-11-{d:02d}") for d in range(1, 11)
    ]
    tuned, held, first = walk_forward(policy, rounds, holdout=3)
    assert (tuned.rounds, held.rounds, first) == (7, 3, "2026-11-08")
    text = report(policy, rounds, holdout=3)
    assert text.startswith("holdout (from 2026-11-08)")
    assert "fewer than 30" in text
    assert "ended top 25" in text


def test_policy_rejects_an_empty_window():
    with pytest.raises(ValidationError):
        Policy(start_hour=20, end_hour=10)


def test_history_round_trips_and_never_refetches(tmp_path, monkeypatch):
    calls: list[str] = []

    class Resp:
        def __init__(self, status: int, body: dict):
            self.status_code, self._body = status, body

        def json(self):
            return self._body

        def raise_for_status(self):
            pass

    async def fake_get(client, url):
        calls.append(url)
        if url.endswith("/results/2026-11-20"):
            meta = {
                "status": "settled",
                "window_start": WS,
                "lock_at": WS + 30 * H,
                "winner_did": "did:a",
            }
            return Resp(
                200,
                {
                    "round": meta,
                    "standings": [{"did": "did:a", "handle": "a.test", "likes": 9}],
                },
            )
        if "/chart/" in url:
            return Resp(200, {"ticks": [[WS + 7 * H, 0.123456789, 3, 1.234, 0.1]]})
        return Resp(404, {})

    monkeypatch.setattr(chicken_history, "_get", fake_get)
    db = tmp_path / "h.sqlite3"
    import asyncio
    from datetime import date

    assert asyncio.run(chicken_history.sync(db, today=date(2026, 11, 21))) == 1
    first = len(calls)
    assert asyncio.run(chicken_history.sync(db, today=date(2026, 11, 21))) == 0
    assert not any("2026-11-20" in u for u in calls[first:])
    (rnd,) = [r for r in chicken_history.load(db) if r.id == "2026-11-20"]
    assert rnd.winner_did == "did:a"
    assert rnd.charts[0].ticks == [(WS + 7 * H, 0.123457, 3, 1.23)]


def test_a_limited_sync_never_backfills(tmp_path, monkeypatch):
    import asyncio
    from datetime import date

    calls: list[str] = []

    async def fake_get(client, url):
        calls.append(url)
        raise AssertionError("a limited sync on an empty store must not fetch")

    monkeypatch.setattr(chicken_history, "_get", fake_get)
    db = tmp_path / "empty.sqlite3"
    assert asyncio.run(chicken_history.sync(db, today=date(2026, 11, 21), limit=3)) == 0
    assert calls == []


def test_report_says_when_no_history_is_loaded():
    assert "hasn't been loaded" in report(Policy(), [], holdout=30)

"""The provider watch: a Fly event that reaches the operator's checks is one DM.

2026-10-16: pds.zzstoatzz.io went down during Fly's platform-wide rolling host
reboots, posted 28 minutes before they began, and nothing told the operator
the outage was Fly's. The fixture is evergreen's /providers response from that
incident, trimmed to three of its nineteen checks.
"""

from unittest.mock import AsyncMock

import pytest

from bot.core import provider_watch
from bot.core.provider_watch import PROVIDER_NAMESPACE, provider_notices

REBOOTS_URL = "https://status.flyio.net//incidents/01M52RAWMVC0NKEBRDKC3VXT3K"
REBOOTS = {
    "kind": "incident",
    "id": "01M52RAWMVC0NKEBRDKC3VXT3K",
    "name": "Platform Wide Rolling Host Reboots",
    "url": REBOOTS_URL,
    "status": "identified",
    "impact": "partial_outage",
    "startsAt": None,
    "endsAt": None,
    "updatedAt": "2026-10-17T00:05:47.809Z",
    "regions": ["ewr", "iad", "ord"],
    "fleetWide": False,
    "services": [
        {"project": "plyr.fm", "name": "api", "url": "https://api.plyr.fm/health"},
        {
            "project": "pds.zzstoatzz.io",
            "name": "PDS",
            "url": "https://pds.zzstoatzz.io/xrpc/_health",
        },
        {"project": "status", "name": "status", "url": "https://status.zzstoatzz.io"},
    ],
}


def _report(*events):
    return {"checkedAt": "2026-10-17T00:19:40.860Z", "fly": {"events": list(events)}}


def test_the_reboot_incident_names_the_checks_it_reaches():
    [(key, text)] = provider_notices(_report(REBOOTS))
    assert key == f"{PROVIDER_NAMESPACE}fly:incident:01M52RAWMVC0NKEBRDKC3VXT3K"
    assert text.startswith(
        "fly.io incident: Platform Wide Rolling Host Reboots (partial outage)."
    )
    assert "reaches 3 of your checks (ewr, iad, ord)" in text
    assert "pds.zzstoatzz.io PDS" in text
    assert text.endswith(REBOOTS_URL)


def test_scheduled_maintenance_warns_with_its_window_under_its_own_key():
    scheduled = {
        **REBOOTS,
        "kind": "scheduled",
        "name": "Network Maintenance in ORD",
        "impact": None,
        "startsAt": "2026-10-20T09:00:00Z",
        "endsAt": "2026-10-20T11:00:00Z",
        "regions": ["ord"],
    }
    [(key, text)] = provider_notices(_report(scheduled))
    assert key.startswith(f"{PROVIDER_NAMESPACE}fly:scheduled:")
    assert text.startswith(
        "fly.io maintenance scheduled Oct 20 09:00 UTC to Oct 20 11:00 UTC: Network Maintenance in ORD."
    )


def test_events_that_reach_no_check_and_unreadable_reports_are_silent():
    assert provider_notices(_report({**REBOOTS, "services": []})) == []
    assert provider_notices(_report({**REBOOTS, "kind": "outage"})) == []
    assert provider_notices(None) == []
    assert provider_notices({"error": "Provider status unavailable"}) == []


def test_a_long_service_list_is_summarized_within_the_dm_limit():
    many = [
        {"project": f"p{i}", "name": "check", "url": f"https://p{i}.example"}
        for i in range(40)
    ]
    [(_, text)] = provider_notices(_report({**REBOOTS, "services": many}))
    assert "and 34 more" in text
    assert len(text) <= 1000


@pytest.fixture
def journal(monkeypatch):
    states: dict[str, str] = {}
    sent: list[tuple[str, str]] = []

    async def report_state(key):
        return {"incident": key, "state": states.get(key, "not-sent")}

    async def send_report(key, text):
        sent.append((key, text))
        states[key] = "sent"
        return {"incident": key, "state": "sent"}

    monkeypatch.setattr(provider_watch.operator_reports, "report_state", report_state)
    monkeypatch.setattr(provider_watch.operator_reports, "send_report", send_report)
    monkeypatch.setattr(
        provider_watch,
        "fetch_provider_report",
        AsyncMock(return_value=_report(REBOOTS)),
    )
    monkeypatch.setattr(
        provider_watch, "get_override", AsyncMock(return_value={"active": False})
    )
    monkeypatch.setattr(provider_watch.bot_status, "paused", False)
    return states, sent


async def test_each_event_is_sent_once_across_polls(journal):
    states, sent = journal
    await provider_watch.check_provider_watch()
    await provider_watch.check_provider_watch()
    assert [key for key, _ in sent] == [
        f"{PROVIDER_NAMESPACE}fly:incident:{REBOOTS['id']}"
    ]


async def test_an_uncertain_send_is_never_repeated(journal):
    states, sent = journal
    states[f"{PROVIDER_NAMESPACE}fly:incident:{REBOOTS['id']}"] = "uncertain"
    await provider_watch.check_provider_watch()
    assert sent == []


async def test_override_and_pause_keep_phi_quiet(journal, monkeypatch):
    _, sent = journal
    monkeypatch.setattr(
        provider_watch, "get_override", AsyncMock(return_value={"active": True})
    )
    await provider_watch.check_provider_watch()
    monkeypatch.setattr(
        provider_watch, "get_override", AsyncMock(return_value={"active": False})
    )
    monkeypatch.setattr(provider_watch.bot_status, "paused", True)
    await provider_watch.check_provider_watch()
    assert sent == []

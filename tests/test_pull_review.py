"""phi reviews pulls other people open on the operator's repo.

Stage one of handing review off to her: prefect's autofix opens a pull as
gardener and wakes phi through the control API with the pull as material.
She comments a verdict; she never merges — the endpoint hands her the pull,
nothing else.
"""

from unittest.mock import AsyncMock, Mock

from starlette.testclient import TestClient

import bot.main as m
from bot.config import settings

client = TestClient(m.app)


def _wire(monkeypatch) -> Mock:
    monkeypatch.setattr(settings, "control_token", "t")
    poller = Mock()
    poller.handler = Mock()
    poller.handler.pull_review = AsyncMock()
    poller.handler.cycle = AsyncMock()
    monkeypatch.setattr(m.app.state, "poller", poller, raising=False)
    return poller.handler


def test_pull_review_is_a_trigger_slot_that_needs_material():
    assert "pull-review" in m._TRIGGER_SLOTS
    assert "pull-review" in m._MATERIAL_SLOTS


def test_pull_review_wakes_phi_with_the_pull(monkeypatch):
    handler = _wire(monkeypatch)
    material = "at://did:plc:gardener/sh.tangled.repo.pull/3abc — strata: skip"
    r = client.post(
        "/api/control/trigger/pull-review",
        json={"material": material},
        headers={"authorization": "Bearer t"},
    )
    assert r.status_code == 200, r.text
    handler.pull_review.assert_awaited_once_with(material)


def test_pull_review_without_material_is_refused(monkeypatch):
    handler = _wire(monkeypatch)
    r = client.post(
        "/api/control/trigger/pull-review",
        headers={"authorization": "Bearer t"},
    )
    assert r.status_code == 400
    handler.pull_review.assert_not_awaited()


def test_clock_slots_ignore_the_body(monkeypatch):
    handler = _wire(monkeypatch)
    r = client.post(
        "/api/control/trigger/cycle",
        json={"material": "ignored"},
        headers={"authorization": "Bearer t"},
    )
    assert r.status_code == 200
    handler.cycle.assert_awaited_once_with()


def test_the_review_prompt_keeps_phi_a_reviewer():
    import inspect

    from bot.agent import PhiAgent

    src = inspect.getsource(PhiAgent.process_pull_review)
    assert "VERDICT: approve" in src
    assert "never merge" in src
    assert "tangled_get_pull_patch" in src

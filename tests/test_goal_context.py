from bot.core.self_state import _format_goals_block


def test_old_interest_keeps_its_account_without_inventing_a_failure():
    rendered = _format_goals_block(
        [
            {
                "title": "Read when something catches my attention",
                "kind": "interest",
                "last_step": "Read a source 5h ago",
                "last_step_at": "2026-01-01T00:00:00Z",
                "next_step": "Nothing needed now",
            }
        ]
    )
    assert "stalled" not in rendered
    assert "last step: recorded 2026-01-01T00:00:00Z" in rendered
    assert "Relative dates inside a saved note" in rendered
    assert "Read a source 5h ago" in rendered
    assert "Nothing needed now" in rendered

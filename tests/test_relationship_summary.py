from datetime import UTC, datetime, timedelta

import pytest

from bot.memory.namespace_memory import summary_is_current


@pytest.mark.parametrize(
    "age,expected", [(timedelta(hours=3), True), (timedelta(days=108), False)]
)
def test_legacy_summary_search_excludes_stale_impressions(age, expected):
    assert summary_is_current((datetime.now(UTC) - age).isoformat()) is expected


def test_undated_summary_is_not_current():
    assert not summary_is_current("")

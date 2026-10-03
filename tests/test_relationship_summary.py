from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from bot.memory.namespace_memory import NamespaceMemory


def _memory(created_at: str) -> NamespaceMemory:
    mem = NamespaceMemory.__new__(NamespaceMemory)
    ns = Mock()
    ns.query.return_value = SimpleNamespace(
        rows=[SimpleNamespace(content="an impression", created_at=created_at)]
    )
    mem.get_user_namespace = Mock(return_value=ns)
    return mem


@pytest.mark.parametrize(
    ("age", "expected"),
    [(timedelta(hours=3), "an impression"), (timedelta(days=108), None)],
)
async def test_a_summary_the_flow_stopped_refreshing_is_not_recalled(age, expected):
    created_at = (datetime.now(UTC) - age).isoformat()
    assert await _memory(created_at).get_relationship_summary("someone") == expected


async def test_a_summary_without_a_timestamp_is_not_recalled():
    assert await _memory("").get_relationship_summary("someone") is None

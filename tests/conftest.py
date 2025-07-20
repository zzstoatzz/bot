"""Pytest configuration"""

from unittest.mock import Mock

import pytest

from bot.core.atproto_client import BotClient


@pytest.fixture
def mock_client():
    """Mock AT Protocol client"""
    client = Mock(spec=BotClient)
    client.is_authenticated = True
    return client
